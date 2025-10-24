import os
import json
import boto3
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

# --- YENİ EKLENDİ: S3 Client Kurulumu ---
s3_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("S3_ENDPOINT_URL"),
    aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
    region_name="auto",
)
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
# -----------------------------------------

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Game Patch Notes Intelligence API", "docs": "/docs"}

# --- DEĞİŞTİRİLDİ: get_patches fonksiyonu artık S3'ten okuyor ---
@app.get("/patches")
def get_patches(game: str = None):
    if game is None:
        # Tüm oyunları listelemek S3'te daha karmaşık, şimdilik tek oyun desteği
        raise HTTPException(status_code=400, detail="Lütfen bir oyun adı belirtin (örn: /patches?game=Valorant).")

    safe_name = game.lower().replace(" ", "_").replace("-", "_").replace(".", "")
    filename = f"{safe_name}_latest.json"
    
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=filename)
        content = response['Body'].read()
        data = json.loads(content)
        # Direkt JSON içeriğini döndürmek yerine JSONResponse kullanmak daha sağlıklıdır
        return JSONResponse(content=data)
    except s3_client.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail=f"'{game}' için yama notu bulunamadı.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sunucu hatası: {e}")
# ----------------------------------------------------------------