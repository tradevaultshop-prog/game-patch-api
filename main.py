import os
import json
import boto3
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from datetime import datetime
from functools import lru_cache, wraps
from typing import Optional

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

# --- YENİ EKLENDİ: API Anahtarı Güvenliği (Öneri 3.2) ---
API_KEY = os.getenv("API_KEY")

async def verify_key(x_api_key: Optional[str] = Header(None)):
    if not API_KEY:
        # API_KEY ayarlanmamışsa, güvenliği devredışı bırak (geliştirme için)
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Geçersiz API Anahtarı")
# ----------------------------------------------------

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Game Patch Notes Intelligence API", "docs": "/docs"}

# --- YENİ EKLENDİ: Healthcheck Endpoint'i (Öneri 4.2) ---
@app.get("/health")
def health_check():
    # Bu endpoint, harici bir monitör (UptimeRobot vb.) tarafından izlenebilir
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
# ----------------------------------------------------

# --- YENİ EKLENDİ: Akıllı Önbellekleme (Öneri 3.3) ---
# S3'ten veri çeken fonksiyonu ayırıyoruz
# maxsize=10 (6 oyun + birkaç popüler sorgu)
# TTL (Time-to-Live) eklemek için 'cachetools' kullanılabilir, 
# ancak basitlik için lru_cache ile başlıyoruz.
@lru_cache(maxsize=10) 
def fetch_from_s3(filename: str):
    logging.info(f"CACHE MISS: S3'ten çekiliyor: {filename}")
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=filename)
        content = response['Body'].read()
        return json.loads(content)
    except s3_client.exceptions.NoSuchKey:
        return None # Hata yönetimi get_patches içinde yapılacak
    except Exception as e:
        logging.error(f"S3 Okuma Hatası (fetch_from_s3): {e}")
        # Hata durumunda cache'lememek için istisna fırlat
        raise HTTPException(status_code=500, detail=f"S3 Okuma Hatası: {e}")
# ----------------------------------------------------

# --- GÜNCELLENDİ: 'get_patches' artık Caching ve Güvenlik kullanıyor ---
@app.get("/patches", dependencies=[Depends(verify_key)])
def get_patches(game: str = None):
    if game is None:
        raise HTTPException(status_code=400, detail="Lütfen bir oyun adı belirtin (örn: /patches?game=Valorant).")

    safe_name = game.lower().replace(" ", "_").replace("-", "_").replace(".", "")
    filename = f"{safe_name}_latest.json"
    
    # Önbellekli fonksiyonu çağır
    data = fetch_from_s3(filename)
    
    if data:
        return JSONResponse(content=data)
    else:
        # fetch_from_s3 None döndürdüyse (NoSuchKey)
        raise HTTPException(status_code=4404, detail=f"'{game}' için yama notu bulunamadı.")
# ----------------------------------------------------------------