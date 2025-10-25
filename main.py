import os
import json
import boto3
import time
import threading
import logging
import asyncio
from fastapi import FastAPI, HTTPException, Header, Depends, Query, Request, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
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
app = FastAPI(title="Game Patch Notes Intelligence API", version="4.4")

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Dilersen sadece dashboard domainini yazabilirsin
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
# =========   YENİ: SSE (Server-Sent Events)  ==========
# ======================================================

sse_latest_etags = {}
sse_lock = asyncio.Lock()

async def check_r2_for_updates():
    """R2'deki _latest.json dosyalarını kontrol eder ve değişiklik varsa ETag'i günceller."""
    global sse_latest_etags
    supported_games_safe_names = [
        "valorant", "roblox", "minecraft", "league_of_legends",
        "counter_strike_2", "fortnite"
    ]

    updated_games = []
    for safe_name in supported_games_safe_names:
        latest_key = f"{safe_name}_latest.json"
        try:
            response = s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=latest_key)
            current_etag = response.get("ETag")

            async with sse_lock:
                last_etag = sse_latest_etags.get(safe_name)
                if current_etag and current_etag != last_etag:
                    logging.info(f"SSE: '{safe_name}' için yeni ETag tespit edildi: {current_etag}")
                    sse_latest_etags[safe_name] = current_etag
                    updated_games.append(safe_name)

        except s3_client.exceptions.NoSuchKey:
            continue
        except Exception as e:
            logging.warning(f"SSE R2 check hatası ({latest_key}): {e}")

    return updated_games


async def event_generator(request: Request):
    """Client'a SSE olaylarını gönderir. Periyodik olarak R2'yi kontrol eder."""
    global sse_latest_etags

    async with sse_lock:
        if not sse_latest_etags:
            logging.info("SSE: İlk bağlantı, mevcut ETag'ler R2'den okunuyor...")
            await check_r2_for_updates()
            logging.info(f"SSE: Başlangıç ETag'leri: {sse_latest_etags}")

    last_check_time = time.time()
    check_interval = 30  # saniye

    try:
        while True:
            if await request.is_disconnected():
                logging.info("SSE: Client bağlantısı koptu.")
                break

            current_time = time.time()
            if current_time - last_check_time >= check_interval:
                last_check_time = current_time
                local_copy_etags = {}
                async with sse_lock:
                    local_copy_etags = sse_latest_etags.copy()

                supported_games_safe_names = list(local_copy_etags.keys()) or [
                    "valorant", "roblox", "minecraft", "league_of_legends",
                    "counter_strike_2", "fortnite"
                ]

                for safe_name in supported_games_safe_names:
                    latest_key = f"{safe_name}_latest.json"
                    try:
                        response = s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=latest_key)
                        current_etag = response.get("ETag")
                        last_etag = local_copy_etags.get(safe_name)

                        if current_etag and current_etag != last_etag:
                            logging.info(f"SSE: '{safe_name}' için değişiklik tespit edildi!")
                            async with sse_lock:
                                sse_latest_etags[safe_name] = current_etag
                            event_data = json.dumps({"type": "new_patch", "game": safe_name})
                            yield f"data: {event_data}\n\n"

                    except s3_client.exceptions.NoSuchKey:
                        continue
                    except Exception as e:
                        logging.warning(f"SSE R2 check hatası ({latest_key}): {e}")

            await asyncio.sleep(5)

    except asyncio.CancelledError:
        logging.info("SSE: Generator iptal edildi.")
    finally:
        logging.info("SSE: Event generator sonlandı.")


@app.get("/events")
async def sse_endpoint(request: Request):
    """Client'ların SSE akışına abone olacağı endpoint."""
    return StreamingResponse(event_generator(request), media_type="text/event-stream")


# ======================================================
# ================   ENDPOINTLER   =====================
# ======================================================

@app.get("/")
def root():
    return {"message": "Game Patch Notes Intelligence API (v4.4 w/Logs + SSE)", "docs": "/docs"}


@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/public/patches")
def get_public_patches(game: str = None):
    if not game:
        raise HTTPException(status_code=400, detail="Lütfen bir oyun adı belirtin.")
    safe_name = game.lower().replace(" ", "_").replace("-", "_").replace(".", "")
    filename = f"{safe_name}_latest.json"

    data = fetch_from_s3(filename)
    if data:
        return JSONResponse(content=data)
    raise HTTPException(status_code=404, detail=f"'{game}' için yama notu bulunamadı.")


@app.get("/public/patches/history")
def get_public_patch_history(game: str = None):
    if not game:
        raise HTTPException(status_code=400, detail="Lütfen bir oyun adı belirtin.")
    safe_name = game.lower().replace(" ", "_").replace("-", "_").replace(".", "")
    index_key = f"{safe_name}/index.json"

    data = fetch_from_s3(filename=index_key)
    if data and "history" in data:
        archives = data.get("history", [])
        return {"game": game, "archive_count": len(archives), "archives": archives}
    elif data is None:
        return {"game": game, "archive_count": 0, "archives": []}
    raise HTTPException(status_code=500, detail=f"'{game}' için index dosyası okunamadı.")


@app.get("/public/patches/archive")
def get_public_archive_detail(key: str = Query(..., description="S3'teki dosya anahtarı")):
    if not key or "/" not in key:
        raise HTTPException(status_code=400, detail="Geçerli bir S3 'key' gereklidir.")
    data = fetch_from_s3(filename=key)
    if data:
        return JSONResponse(content=data)
    raise HTTPException(status_code=404, detail=f"'{key}' anahtarlı arşiv bulunamadı.")


@app.get("/patches", dependencies=[Depends(verify_key)])
def get_patches(game: str = None):
    if not game:
        raise HTTPException(status_code=400, detail="Lütfen bir oyun adı belirtin.")
    safe_name = game.lower().replace(" ", "_").replace("-", "_").replace(".", "")
    filename = f"{safe_name}_latest.json"

    data = fetch_from_s3(filename)
    if data:
        return JSONResponse(content=data)
    raise HTTPException(status_code=404, detail=f"'{game}' için yama notu bulunamadı.")


@app.get("/public/stats")
def get_usage_stats():
    """R2’deki loglardan özet istatistik döner."""
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
