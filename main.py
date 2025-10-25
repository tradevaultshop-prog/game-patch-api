import os
import json
import boto3
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from datetime import datetime
from functools import lru_cache, wraps
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware # <-- YENİ EKLENDİ

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

# --- YENİ EKLENDİ: CORS Middleware ---
# Bu, başka domain'lerden (React uygulamanızdan) gelen isteklere izin verir.
# "simplest" çözüm için origins="*" (herkese izin ver) kullanıyoruz.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Daha güvenli bir dünyada buraya ["https-gpnai-dashboard.onrender.com"] yazardık.
    allow_credentials=True,
    allow_methods=["*"], # Sadece GET'e izin vermek daha iyi olurdu: ["GET"]
    allow_headers=["*"],
)
# ------------------------------------

@app.get("/")
def root():
    return {"message": "Game Patch Notes Intelligence API", "docs": "/docs"}

@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@lru_cache(maxsize=10) 
def fetch_from_s3(filename: str):
    # logging.info(f"CACHE MISS: S3'ten çekiliyor: {filename}") # Loglamayı açabilirsiniz
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=filename)
        content = response['Body'].read()
        return json.loads(content)
    except s3_client.exceptions.NoSuchKey:
        return None 
    except Exception as e:
        # logging.error(f"S3 Okuma Hatası (fetch_from_s3): {e}") # Loglamayı açabilirsiniz
        raise HTTPException(status_code=500, detail=f"S3 Okuma Hatası: {e}")

# --- YENİ EKLENDİ: Public Patches Endpoint'i ---
# Bu, /patches'in BİREBİR AYNISI ama "dependencies=[Depends(verify_key)]" kısmı yok.
# Dashboard'umuz bu endpoint'i kullanacak.
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
# ------------------------------------------------

# --- MEVCUT /patches ENDPOINT'İNİZ (DOKUNULMAMIŞ) ---
# Bu, API müşterileriniz için anahtarla korunmaya devam ediyor.
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