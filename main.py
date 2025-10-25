import os
import json
import boto3
import time
import threading
import logging
from fastapi import FastAPI, HTTPException, Header, Depends, Query, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from datetime import datetime
from functools import lru_cache
from typing import Optional

# --- Ortam değişkenlerini yükle ---
load_dotenv()

# --- Loglama yapılandırması ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- S3 Client Kurulumu ---
s3_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("S3_ENDPOINT_URL"),
    aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
    region_name="auto",
)
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
API_KEY = os.getenv("API_KEY")

# --- API Anahtarı Doğrulama ---
async def verify_key(x_api_key: Optional[str] = Header(None)):
    if not API_KEY:
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Geçersiz API Anahtarı")

# --- FastAPI Uygulaması ---
app = FastAPI(title="Game Patch Notes Intelligence API", version="4.3")

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Dilersen dashboard domain’iyle sınırlandırabilirsin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================================================
# ==========   KULLANIM LOG MIDDLEWARE (YENİ)  =========
# ======================================================

log_buffer = []
log_lock = threading.Lock()
MAX_LOG_BUFFER_SIZE = 50  # 50 istekte bir R2’ye yaz

def write_logs_to_r2():
    """Bellekteki logları R2'ye toplu halde yazar ve belleği temizler."""
    global log_buffer

    with log_lock:
        if not log_buffer:
            return
        logs_to_write = log_buffer.copy()
        log_buffer = []

    try:
        log_content = "\n".join(json.dumps(log) for log in logs_to_write)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        log_key = f"logs/usage_{timestamp}.jsonl"

        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=log_key,
            Body=log_content.encode("utf-8"),
            ContentType="application/jsonl",
        )
        logging.info(f"✅ {len(logs_to_write)} adet log R2'ye yazıldı: {log_key}")
    except Exception as e:
        logging.error(f"❌ Log yazma hatası: {e}")
        with log_lock:
            log_buffer.extend(logs_to_write)  # Geri ekle, veri kaybı olmasın

@app.middleware("http")
async def log_api_usage(request: Request, call_next):
    """Her API isteğini loglar ve gerekirse R2’ye flush eder."""
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000

    path = request.url.path
    if path.startswith("/public/patches") or path == "/patches":
        game = request.query_params.get("game", "unknown")
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "path": path,
            "method": request.method,
            "status_code": response.status_code,
            "game_query": game,
            "process_time_ms": round(duration_ms, 2),
            "client_ip": request.client.host,
        }

        with log_lock:
            log_buffer.append(log_entry)
            if len(log_buffer) >= MAX_LOG_BUFFER_SIZE:
                if "background" not in response.__dict__:
                    response.background = BackgroundTasks()
                response.background.add_task(write_logs_to_r2)

    return response

# ======================================================
# ==========   S3 OKUMA / CACHE MEKANİZMASI  ===========
# ======================================================

@lru_cache(maxsize=10)
def fetch_from_s3(filename: str):
    """Belirtilen dosyayı S3’ten çeker ve cache’ler."""
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=filename)
        content = response["Body"].read()
        return json.loads(content)
    except s3_client.exceptions.NoSuchKey:
        return None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 Okuma Hatası: {e}")

# ======================================================
# ================   ENDPOINTLER   =====================
# ======================================================

@app.get("/")
def root():
    return {"message": "Game Patch Notes Intelligence API (v4.3 w/Index + Logs)", "docs": "/docs"}

@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

# --- Public Endpoint: Son yama verisi ---
@app.get("/public/patches")
def get_public_patches(game: str = None):
    if not game:
        raise HTTPException(status_code=400, detail="Lütfen bir oyun adı belirtin (örn: /public/patches?game=Valorant).")
    safe_name = game.lower().replace(" ", "_").replace("-", "_").replace(".", "")
    filename = f"{safe_name}_latest.json"

    data = fetch_from_s3(filename)
    if data:
        return JSONResponse(content=data)
    raise HTTPException(status_code=404, detail=f"'{game}' için yama notu bulunamadı.")

# --- Arşiv Listesi Endpoint’i (Index Dosyasından) ---
@app.get("/public/patches/history")
def get_public_patch_history(game: str = None):
    if not game:
        raise HTTPException(status_code=400, detail="Lütfen bir oyun adı belirtin (örn: /public/patches/history?game=Valorant).")
    safe_name = game.lower().replace(" ", "_").replace("-", "_").replace(".", "")
    index_key = f"{safe_name}/index.json"

    data = fetch_from_s3(filename=index_key)
    if data and "history" in data:
        archives = data.get("history", [])
        return {"game": game, "archive_count": len(archives), "archives": archives}
    elif data is None:
        return {"game": game, "archive_count": 0, "archives": []}
    raise HTTPException(status_code=500, detail=f"'{game}' için index dosyası okunamadı veya formatı bozuk.")

# --- Arşiv Detay Endpoint’i ---
@app.get("/public/patches/archive")
def get_public_archive_detail(
    key: str = Query(..., description="S3'teki dosya anahtarı (örn: valorant/20251025_173045.json)")
):
    if not key or "/" not in key:
        raise HTTPException(status_code=400, detail="Geçerli bir S3 'key' gereklidir (örn: valorant/20251025_173045.json).")

    data = fetch_from_s3(filename=key)
    if data:
        return JSONResponse(content=data)
    raise HTTPException(status_code=404, detail=f"'{key}' anahtarlı arşivlenmiş yama notu bulunamadı.")

# --- API Key Koruması Olan Endpoint ---
@app.get("/patches", dependencies=[Depends(verify_key)])
def get_patches(game: str = None):
    if not game:
        raise HTTPException(status_code=400, detail="Lütfen bir oyun adı belirtin (örn: /patches?game=Valorant).")
    safe_name = game.lower().replace(" ", "_").replace("-", "_").replace(".", "")
    filename = f"{safe_name}_latest.json"

    data = fetch_from_s3(filename)
    if data:
        return JSONResponse(content=data)
    raise HTTPException(status_code=404, detail=f"'{game}' için yama notu bulunamadı.")

# --- YENİ: Kullanım İstatistikleri Endpoint’i ---
@app.get("/public/stats")
def get_usage_stats():
    """
    R2’deki son log dosyalarını okur ve özet istatistik döner.
    """
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix="logs/", MaxKeys=20)

        all_logs = []
        for page in pages:
            if "Contents" not in page:
                continue
            for obj in page["Contents"]:
                try:
                    response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=obj["Key"])
                    content = response["Body"].read().decode("utf-8")
                    for line in content.splitlines():
                        if line.strip():
                            all_logs.append(json.loads(line))
                except Exception:
                    continue

        if not all_logs:
            return {"message": "Henüz yeterli istatistik yok."}

        total_requests = len(all_logs)
        errors = [log for log in all_logs if log["status_code"] >= 400]
        game_counts = {}
        for log in all_logs:
            game = log.get("game_query", "unknown")
            game_counts[game] = game_counts.get(game, 0) + 1

        return {
            "total_requests_analyzed": total_requests,
            "total_errors": len(errors),
            "most_popular_game": max(game_counts, key=game_counts.get) if game_counts else "N/A",
            "requests_by_game": game_counts,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"İstatistik okuma hatası: {e}")

