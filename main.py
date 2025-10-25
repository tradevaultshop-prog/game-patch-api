import os
import json
import boto3
from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from datetime import datetime
from functools import lru_cache
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

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

async def verify_key(x_api_key: Optional[str] = Header(None)):
    if not API_KEY:
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Geçersiz API Anahtarı")

app = FastAPI()

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Dashboard'unuzun RENDER_EXTERNAL_URL'si ile değiştirilebilir
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@lru_cache(maxsize=10) 
def fetch_from_s3(filename: str):
    """
    Belirtilen dosyayı S3'ten çeker ve cache'ler.
    Bu fonksiyon hem '_latest.json' hem de arşivlenmiş dosyalar (örn: valorant/...) için kullanılır.
    """
    # logging.info(f"CACHE MISS: S3'ten çekiliyor: {filename}")
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=filename)
        content = response['Body'].read()
        return json.loads(content)
    except s3_client.exceptions.NoSuchKey:
        return None 
    except Exception as e:
        # logging.error(f"S3 Okuma Hatası (fetch_from_s3): {e}")
        raise HTTPException(status_code=500, detail=f"S3 Okuma Hatası: {e}")

# --- Temel Endpoint'ler ---
@app.get("/")
def root():
    return {"message": "Game Patch Notes Intelligence API (v4.1 w/Archive)", "docs": "/docs"}

@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

# --- Public Endpoint'ler (Dashboard için) ---
@app.get("/public/patches") 
def get_public_patches(game: str = None):
    if game is None:
        raise HTTPException(status_code=400, detail="Lütfen bir oyun adı belirtin (örn: /public/patches?game=Valorant).")

    safe_name = game.lower().replace(" ", "_").replace("-", "_").replace(".", "")
    filename = f"{safe_name}_latest.json"
    
    data = fetch_from_s3(filename)
    
    if data:
        return JSONResponse(content=data)
    else:
        raise HTTPException(status_code=404, detail=f"'{game}' için yama notu bulunamadı.")

# --- YENİ EKLENDİ: Arşiv Listesi Endpoint'i ---
@app.get("/public/patches/history")
def get_public_patch_history(game: str = None):
    """
    Bir oyun için arşivlenmiş tüm yama notlarının listesini döner.
    Dashboard'daki "Tarih Seçici" bu endpoint'i besler.
    """
    if game is None:
        raise HTTPException(status_code=400, detail="Lütfen bir oyun adı belirtin (örn: /public/patches/history?game=Valorant).")

    safe_name = game.lower().replace(" ", "_").replace("-", "_").replace(".", "")
    prefix = f"{safe_name}/" # S3'teki 'klasörü' (prefix) belirtir
    
    archives = []
    try:
        # S3'teki o 'klasör' içindeki tüm nesneleri listele
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=prefix)

        for page in pages:
            if "Contents" in page:
                for obj in page["Contents"]:
                    archives.append({
                        "key": obj["Key"], # Dosyanın tam yolu (örn: valorant/20251025_173045.json)
                        "date": obj["LastModified"].isoformat(),
                        "size_kb": round(obj["Size"] / 1024, 2)
                    })
        
        # Listeyi en yeniden en eskiye doğru sırala
        archives.sort(key=lambda x: x["date"], reverse=True)
        return {"game": game, "archive_count": len(archives), "archives": archives}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 Arşiv Listeleme Hatası: {e}")

# --- YENİ EKLENDİ: Arşiv Detay Endpoint'i ---
@app.get("/public/patches/archive")
def get_public_archive_detail(key: str = Query(..., description="S3'ten çekilecek dosyanın tam anahtarı (key)")):
    """
    'key' parametresiyle belirtilen tek bir arşivlenmiş JSON dosyasının içeriğini döner.
    Bu endpoint, mevcut 'fetch_from_s3' cache mekanizmasını [cite: 75-76] yeniden kullanır.
    """
    if not key or "/" not in key:
        raise HTTPException(status_code=400, detail="Geçerli bir S3 'key' gereklidir (örn: valorant/20251025_173045.json).")

    data = fetch_from_s3(filename=key) # Cache'li fonksiyonu yeniden kullan
    
    if data:
        return JSONResponse(content=data)
    else:
        # fetch_from_s3 'None' dönerse (NoSuchKey)
        raise HTTPException(status_code=4404, detail=f"'{key}' anahtarlı arşivlenmiş yama notu bulunamadı.")

# --- MEVCUT /patches ENDPOINT'İNİZ (Anahtarla Korunan) ---
@app.get("/patches", dependencies=[Depends(verify_key)])
def get_patches(game: str = None):
    if game is None:
        raise HTTPException(status_code=400, detail="Lütfen bir oyun adı belirtin (örn: /patches?game=Valorant).")

    safe_name = game.lower().replace(" ", "_").replace("-", "_").replace(".", "")
    filename = f"{safe_name}_latest.json"
    
    data = fetch_from_s3(filename)
    
    if data:
        return JSONResponse(content=data)
    else:
        raise HTTPException(status_code=404, detail=f"'{game}' için yama notu bulunamadı.")