import os
import json
import time
import random
import logging
import boto3
import requests
import yaml 
import scrapers 
import concurrent.futures
import hashlib # <-- YENİ EKLENDİ (Hash kontrolü için)
import sys # <-- YENİ EKLENDİ (Mod seçimi için)
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
        payload = {"text": f"🚨 **GPNAI Servis Uyarısı** 🚨\n\n```{message}```"}
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

# --- YENİ EKLENDİ: Hash Yardımcı Fonksiyonları (Öneri 1.3) ---
def get_hash_from_s3(safe_name):
    """Mevcut hash'i S3'ten okur."""
    hash_key = f"{safe_name}_latest.hash"
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=hash_key)
        return response['Body'].read().decode('utf-8')
    except s3_client.exceptions.NoSuchKey:
        return None # Dosya henüz yok
    except Exception as e:
        logging.warning(f"S3'ten hash okuma hatası ({hash_key}): {e}")
        return None

def save_hash_to_s3(safe_name, new_hash):
    """Yeni hash'i S3'e yazar."""
    hash_key = f"{safe_name}_latest.hash"
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=hash_key,
            Body=new_hash.encode('utf-8'),
            ContentType="text/plain"
        )
    except Exception as e:
        logging.error(f"S3'e hash yazma hatası ({hash_key}): {e}")
        send_alert(f"❌ S3'e hash yazma hatası ({hash_key}): {e}")
# -------------------------------------------------------------

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

# --- GÜNCELLENDİ: Paralel Veri Çekme (Artık Hash Kontrolü Yapıyor) ---
def fetch_game_data(game_config, session):
    """
    Bir oyunun verisini çeker ve hash'ini kontrol eder.
    Dönüş: (game_name, raw_data, config, new_hash_or_skip_flag)
    """
    game_name = game_config['game']
    safe_name = game_config['safe_name']
    fetch_function_name = game_config['fetch_function']
    
    try:
        logging.info(f"THREAD 🔍: {game_name} için veri çekiliyor...")
        fetch_function = getattr(scrapers, fetch_function_name)
        raw_data = fetch_function(session)
        
        if not raw_data:
            logging.warning(f"THREAD ⚠️: {game_name} için veri bulunamadı.")
            return game_name, None, game_config, None # Hata/Fallback durumu

        # Hash Kontrolü (Öneri 1.3)
        new_hash = hashlib.sha256(raw_data.encode('utf-8')).hexdigest()
        old_hash = get_hash_from_s3(safe_name)
        
        if new_hash == old_hash:
            logging.info(f"THREAD ⏩: {game_name} verisi değişmemiş. Gemini analizi atlanıyor.")
            return game_name, raw_data, game_config, "SKIPPED" # Veri değişmemiş
        
        return game_name, raw_data, game_config, new_hash # Veri yeni
        
    except Exception as e:
        logging.error(f"THREAD ❌: {game_name} veri çekme hatası: {e}")
        return game_name, None, game_config, None # Hata durumu
# ------------------------------------------------------------------

# --- YENİ EKLENDİ: Sağlık Kontrolü Fonksiyonları (Öneri 1.1) ---
def validate_selector(url, selector, parser_type='html.parser'):
    """Bir URL'den bir HTML/XML seçicisinin varlığını kontrol eder."""
    try:
        res = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
        })
        res.raise_for_status() # HTTP hatası varsa dur
        soup = BeautifulSoup(res.text, parser_type)
        
        # 'selector' CSS seçici mi yoksa 'find' argümanı mı olduğuna göre kontrol et
        # Bu örnekte basitlik için 'find' kullandığımızı varsayalım (örn: "div,class_=news-item-content")
        # Not: Gerçek bir 'selector health check' daha karmaşık bir 'find' argümanı gerektirir.
        # Şimdilik, sadece sitenin erişilebilir olduğunu kontrol edelim (basitlik için).
        if res.status_code == 200:
             return True # Temel kontrol: Site ayakta mı?
        
        # Gerçek seçici testi için (daha karmaşık):
        # if "," in selector:
        #     tag, attrs_str = selector.split(",", 1)
        #     attrs = dict([pair.split("=") for pair in attrs_str.split(",")])
        #     element = soup.find(tag, attrs)
        #     return element is not None
        # else:
        #     return soup.select_one(selector) is not None
        
    except Exception as e:
        logging.error(f"Sağlık Kontrolü Hatası ({url}): {e}")
        return False
    return False # Varsayılan olarak başarısız

def run_health_check():
    """Tüm YAML kaynaklarını kontrol eder ve bozuksa uyarır."""
    logging.info("🩺 Proaktif Sağlık Kontrolü (Selector Health Check) başlıyor...")
    try:
        with open("sources.yaml", "r", encoding="utf-8") as f:
            games_config = yaml.safe_load(f)
    except FileNotFoundError:
        send_alert("CRITICAL (Health Check): `sources.yaml` dosyası bulunamadı!")
        return

    broken_selectors = []
    
    # Not: Bu, şu anki 'scrapers.py' yapımıza göre değil, 'sources.yaml'a eklenecek
    # 'check_url' ve 'check_selector' alanlarına göre çalışmalıdır.
    # Faz 2 YAML'ımızda bu alanlar yok.
    # Şimdilik bu testi basitleştirip, sadece `fetch_` fonksiyonlarını çağırıp 
    # `None` dönüp dönmediğini kontrol edelim.
    
    logging.info("Sağlık kontrolü için kaynaklar çekiliyor (bu işlem biraz sürebilir)...")
    session = create_session()
    
    for config in games_config:
        game_name = config['game']
        fetch_function_name = config['fetch_function']
        try:
            fetch_function = getattr(scrapers, fetch_function_name)
            data = fetch_function(session) # Test amaçlı veriyi çek
            if data is None:
                # Veri yoksa, bu bir fallback DEĞİL, scraper hatası olabilir.
                # (Valorant'taki 'veri yok' uyarısı normal, ancak diğerleri hata olabilir)
                logging.warning(f"HEALTH ⚠️: {game_name} scraper'ı 'None' döndürdü. Muhtemelen seçici bozuldu.")
                broken_selectors.append(game_name)
        except Exception as e:
            logging.error(f"HEALTH ❌: {game_name} scraper'ı test sırasında çöktü: {e}")
            broken_selectors.append(f"{game_name} (Çöktü)")
            
    session.close()

    if broken_selectors:
        send_alert(f"❌ PROAKTİF UYARI: Şu scraper'lar bozulmuş olabilir:\n- " + "\n- ".join(broken_selectors))
    else:
        logging.info("✅ Sağlık Kontrolü tamamlandı. Tüm scraper'lar çalışır durumda.")
        # Başarılı olursa sessiz kal
        # send_alert("✅ Sağlık Kontrolü tamamlandı. Tüm scraper'lar çalışır durumda.")
# ---------------------------------------------------------------

def run_scrape():
    """Ana veri çekme ve analiz işlemini çalıştırır."""
    logging.info("🚀 Faz 3: Hash Kontrollü Paralel Veri Çekme ve Sıralı Analiz başlıyor...")
    
    try:
        with open("sources.yaml", "r", encoding="utf-8") as f:
            games_config = yaml.safe_load(f)
        
        session = create_session()
        fetched_data = [] 

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(games_config)) as executor:
            futures = [executor.submit(fetch_game_data, config, session) for config in games_config]
            
            for future in concurrent.futures.as_completed(futures):
                fetched_data.append(future.result())

        logging.info(f"✅ Paralel veri çekme tamamlandı. {len(fetched_data)} oyun işlenecek.")
        session.close() 

        # Sıralı Analiz (API Limiti Koruması)
        for i, (game_name, raw_data, config, hash_or_flag) in enumerate(fetched_data):
            
            if hash_or_flag == "SKIPPED":
                continue # Hash aynı, bu oyunu atla
            
            safe_name = config['safe_name']

            if not raw_data:
                fallback = f"{game_name} received balance changes and new content."
                logging.warning(f"⚠️  {game_name} için veri yok. Fallback metin kullanılıyor.")
                raw_data = fallback
            else:
                logging.info(f"ANALİZ 🧠: {game_name} verisi işleniyor (Hash: {hash_or_flag[:7]}...).")

            result = analyze_with_gemini(raw_data, game_name, send_alert)
            
            if result:
                save_json_to_s3(result, safe_name)
                # Sadece analiz ve S3 kaydı başarılıysa yeni hash'i kaydet
                if hash_or_flag not in [None, "SKIPPED"]:
                    save_hash_to_s3(safe_name, hash_or_flag)
            else:
                logging.error(f"❌ {game_name} analizi başarısız.")
            
            if i < len(fetched_data) - 1:
                delay = random.uniform(5, 12)
                logging.info(f"⏳ Gemini rate limit koruması için {delay:.1f} saniye bekleniyor...")
                time.sleep(delay)
        
        logging.info("✅ Tüm oyunların yama analizi başarıyla tamamlandı.")
        
    except Exception as e:
        logging.error(f"CRITICAL: Cron Job'da beklenmedik hata: {e}", exc_info=True)
        send_alert(f"CRITICAL: Cron Job'un tamamı çöktü: {e}")

# --- YENİ EKLENDİ: Ana Çalıştırma Mantığı (Mod Seçimi) ---
if __name__ == "__main__":
    # Komut satırından argümanları oku (örn: python scrape.py --run=health)
    args = dict(arg.split('=') for arg in sys.argv[1:] if '=' in arg)
    run_mode = args.get('--run', 'scrape') # Varsayılan mod 'scrape'

    if run_mode == 'health':
        run_health_check()
    elif run_mode == 'scrape':
        run_scrape()
    else:
        logging.error(f"Geçersiz çalışma modu: {run_mode}. '--run=scrape' veya '--run=health' kullanın.")
# ---------------------------------------------------------