import os
import json
import time
import random
import logging
import boto3
import requests
import yaml # <-- YENİ EKLENDİ
import scrapers # <-- YENİ EKLENDİ (scrapers.py dosyamız)
import concurrent.futures # <-- YENİ EKLENDİ (paralel işleme için)
from datetime import datetime
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from utils import analyze_with_gemini 

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

s3_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("S3_ENDPOINT_URL"),
    aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
    region_name="auto", 
)
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

def send_alert(message):
    if not SLACK_WEBHOOK_URL:
        logging.warning("SLACK_WEBHOOK_URL tanımlı değil. Bildirim atlanıyor.")
        return
    try:
        payload = {"text": f"🚨 **GPNAI Cron Job Hatası** 🚨\n\n```{message}```"}
        requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
    except Exception as e:
        logging.error(f"Slack bildirimi gönderilemedi: {e}")

if not GEMINI_API_KEY or not S3_BUCKET_NAME:
    error_msg = "❌ .env dosyasında GEMINI_API_KEY veya S3 bilgileri eksik!"
    send_alert(error_msg) 
    raise ValueError(error_msg)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("scraper.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

def create_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
    })
    return session

# --- ARTIK GEREKLİ DEĞİL ---
# Tüm 'fetch_*' fonksiyonları 'scrapers.py' dosyasına taşındı.
# ---------------------------

def save_json_to_s3(data, base_name):
    filename = f"{base_name}_latest.json"
    try:
        json_string = json.dumps(data, indent=2, ensure_ascii=False)
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=filename,
            Body=json_string,
            ContentType="application/json"
        )
        logging.info(f"✅ JSON S3'e kaydedildi: {S3_BUCKET_NAME}/{filename}")
    except Exception as e:
        logging.error(f"❌ S3'e yazma hatası ({filename}): {e}")
        send_alert(f"❌ S3'e yazma hatası ({filename}): {e}")

# --- YENİ EKLENDİ: Paralel Veri Çekme Fonksiyonu ---
def fetch_game_data(game_config, session):
    """
    Bir oyunun verisini çekmek için iş parçacığı (thread) tarafından çalıştırılan fonksiyon.
    """
    game_name = game_config['game']
    fetch_function_name = game_config['fetch_function']
    
    try:
        logging.info(f"THREAD 🔍: {game_name} için veri çekiliyor...")
        # 'scrapers.py' modülünden fonksiyonu ismine göre bul ve çalıştır
        fetch_function = getattr(scrapers, fetch_function_name)
        raw_data = fetch_function(session)
        return game_name, raw_data, game_config
    except Exception as e:
        logging.error(f"THREAD ❌: {game_name} veri çekme hatası: {e}")
        return game_name, None, game_config
# ----------------------------------------------------

# --- GÜNCELLENDİ: Ana Çalıştırma Bloğu (Paralel + Sıralı) ---
if __name__ == "__main__":
    logging.info("🚀 Faz 2: Paralel veri çekme ve sıralı analiz başlatılıyor...")
    
    try:
        # Adım 1: Yapılandırmayı Yükle
        with open("sources.yaml", "r", encoding="utf-8") as f:
            games_config = yaml.safe_load(f)
        
        session = create_session()
        fetched_data = [] # (game_name, raw_data, config) listesi

        # Adım 2: Veri Çekme (Paralel)
        # ThreadPoolExecutor kullanarak tüm I/O (bekleme) işlemlerini aynı anda yap
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(games_config)) as executor:
            # Her 'fetch_game_data' işlevine 'game_config' ve 'session'ı haritala
            futures = [executor.submit(fetch_game_data, config, session) for config in games_config]
            
            for future in concurrent.futures.as_completed(futures):
                fetched_data.append(future.result())

        logging.info(f"✅ Paralel veri çekme tamamlandı. {len(fetched_data)} oyun işlenecek.")
        session.close() # Session'ı artık kapatabiliriz.

        # Adım 3: Analiz ve Kaydetme (Sıralı)
        # Gemini API limitlerine takılmamak için bu adımı sırayla (tek tek) yapıyoruz.
        for i, (game_name, raw_data, config) in enumerate(fetched_data):
            
            safe_name = config['safe_name']

            if not raw_data:
                fallback = f"{game_name} received balance changes and new content."
                logging.warning(f"⚠️  {game_name} için veri yok. Fallback metin kullanılıyor.")
                raw_data = fallback
            else:
                logging.info(f"ANALİZ 🧠: {game_name} verisi işleniyor...")

            # Gemini fonksiyonunu çağır (API anahtarını korumak için sıralı)
            result = analyze_with_gemini(raw_data, game_name, send_alert)
            
            if result:
                save_json_to_s3(result, safe_name)
            else:
                logging.error(f"❌ {game_name} analizi başarısız.")
            
            # API limitleri için bekleme (son oyun hariç)
            if i < len(fetched_data) - 1:
                delay = random.uniform(5, 12)
                logging.info(f"⏳ Gemini rate limit koruması için {delay:.1f} saniye bekleniyor...")
                time.sleep(delay)
        
        logging.info("✅ Tüm oyunların yama analizi başarıyla tamamlandı.")
        
    except Exception as e:
        logging.error(f"CRITICAL: Cron Job'da beklenmedik hata: {e}", exc_info=True)
        send_alert(f"CRITICAL: Cron Job'un tamamı çöktü: {e}")
# -----------------------------------------------------------------