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
import hashlib
import sys
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

# --- YENİ EKLENDİ: Telegram Değişkenleri ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- YENİ EKLENDİ: Telegram Mesaj Gönderme Fonksiyonu ---
def send_telegram_message(message_text, parse_mode="HTML"):
    """Telegram'a formatlı bir mesaj gönderir."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID tanımlı değil. Telegram bildirimi atlanıyor.")
        return

    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message_text,
        'parse_mode': parse_mode
    }
    try:
        requests.post(api_url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Telegram bildirimi gönderilemedi: {e}")

# --- GÜNCELLENDİ: send_alert (Artık Telegram'a da Hata Gönderiyor) ---
def send_alert(message):
    """Sistemin hata uyarılarını hem Slack'e hem Telegram'a gönderir."""
    
    # 1. Slack (Mevcut)
    if not SLACK_WEBHOOK_URL:
        logging.warning("SLACK_WEBHOOK_URL tanımlı değil. Slack bildirimi atlanıyor.")
    else:
        try:
            payload = {"text": f"🚨 **GPNAI Servis Uyarısı** 🚨\n\n```{message}```"}
            requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        except Exception as e:
            logging.error(f"Slack bildirimi gönderilemedi: {e}")

    # 2. Telegram (Yeni)
    # Telegram'a gönderirken formatlamayı kaldırıyoruz, çünkü hatalar '```' içermemeli
    telegram_error_message = f"🚨 GPNAI Servis Uyarısı 🚨\n\n{message}"
    send_telegram_message(telegram_error_message, parse_mode=None) # Düz metin olarak gönder

# --- YENİ EKLENDİ: Başarılı Yama Notlarını Formatlama Fonksiyonu ---
def format_patch_notes_for_telegram(json_data):
    """
    Analiz edilmiş JSON verisini profesyonel bir Telegram mesajına dönüştürür.
    JSON formatı kılavuza göredir [cite: 183-196].
    """
    try:
        game = json_data.get('game', 'Bilinmeyen Oyun')
        version = json_data.get('patch_version', 'unknown')
        date = json_data.get('date', 'unknown')
        changes = json_data.get('changes', [])

        message = f"✅ <b>{game} için Yeni Yama Notları Analiz Edildi!</b>\n\n"
        message += f"<b>Versiyon:</b> <code>{version}</code>\n"
        message += f"<b>Tarih:</b> <code>{date}</code>\n"
        message += "-----------------------------------\n"

        if not changes:
            # Kılavuzda belirtildiği gibi, boş 'changes' bir hata değildir[cite: 202].
            message += "ℹ️ <i>Analiz tamamlandı ancak raporlanacak (nerf, buff, new, fix) önemli bir değişiklik bulunamadı.</i>"
            return message

        # Değişiklikleri gruplayalım (buff, nerf, new, fix)
        change_map = {"buff": [], "nerf": [], "new": [], "fix": []}
        other = []

        for change in changes:
            change_type = change.get('type', 'other').lower()
            target = change.get('target', 'Bilinmiyor')
            details = change.get('details', 'Detay yok')
            
            # Yetenek varsa ekleyelim
            ability = change.get('ability')
            if ability and ability.lower() not in ['unknown', 'n/a', '']:
                 target_str = f"{target} ({ability})"
            else:
                 target_str = target
            
            entry = f"  - <b>{target_str}:</b> <i>{details}</i>"
            
            if change_type in change_map:
                change_map[change_type].append(entry)
            else:
                other.append(entry)

        if change_map["buff"]:
            message += "🟢 <b>Güçlendirmeler (Buffs):</b>\n" + "\n".join(change_map["buff"]) + "\n\n"
        if change_map["nerf"]:
            message += "🔴 <b>Zayıflatmalar (Nerfs):</b>\n" + "\n".join(change_map["nerf"]) + "\n\n"
        if change_map["new"]:
            message += "✨ <b>Yeni İçerik/Değişiklikler:</b>\n" + "\n".join(change_map["new"]) + "\n\n"
        if change_map["fix"]:
            message += "🔧 <b>Hata Düzeltmeleri (Fixes):</b>\n" + "\n".join(change_map["fix"]) + "\n\n"
        if other:
            message += "📋 <b>Diğer Değişiklikler:</b>\n" + "\n".join(other) + "\n\n"

        return message.strip()

    except Exception as e:
        logging.error(f"Telegram formatlama hatası: {e}")
        return f"❌ <b>{json_data.get('game', 'Bilinmeyen Oyun')} için formatlama hatası oluştu.</b>\n\nVeri S3'e kaydedildi ancak Telegram'a gönderilemedi. Detay: {e}"


# --- Ana Kod (Değişiklik Yok) ---
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

def get_hash_from_s3(safe_name):
    hash_key = f"{safe_name}_latest.hash"
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=hash_key)
        return response['Body'].read().decode('utf-8')
    except s3_client.exceptions.NoSuchKey:
        return None 
    except Exception as e:
        logging.warning(f"S3'ten hash okuma hatası ({hash_key}): {e}")
        return None

def save_hash_to_s3(safe_name, new_hash):
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

def fetch_game_data(game_config, session):
    game_name = game_config['game']
    safe_name = game_config['safe_name']
    fetch_function_name = game_config['fetch_function']
    
    try:
        logging.info(f"THREAD 🔍: {game_name} için veri çekiliyor...")
        fetch_function = getattr(scrapers, fetch_function_name)
        raw_data = fetch_function(session)
        
        if not raw_data:
            logging.warning(f"THREAD ⚠️: {game_name} için veri bulunamadı.")
            return game_name, None, game_config, None 

        new_hash = hashlib.sha256(raw_data.encode('utf-8')).hexdigest()
        old_hash = get_hash_from_s3(safe_name)
        
        if new_hash == old_hash:
            logging.info(f"THREAD ⏩: {game_name} verisi değişmemiş. Gemini analizi atlanıyor.")
            return game_name, raw_data, game_config, "SKIPPED" 
        
        return game_name, raw_data, game_config, new_hash 
        
    except Exception as e:
        logging.error(f"THREAD ❌: {game_name} veri çekme hatası: {e}")
        return game_name, None, game_config, None

def run_health_check():
    logging.info("🩺 Proaktif Sağlık Kontrolü (Selector Health Check) başlıyor...")
    try:
        with open("sources.yaml", "r", encoding="utf-8") as f:
            games_config = yaml.safe_load(f)
    except FileNotFoundError:
        send_alert("CRITICAL (Health Check): `sources.yaml` dosyası bulunamadı!")
        return

    broken_selectors = []
    
    logging.info("Sağlık kontrolü için kaynaklar çekiliyor...")
    session = create_session()
    
    for config in games_config:
        game_name = config['game']
        fetch_function_name = config['fetch_function']
        try:
            fetch_function = getattr(scrapers, fetch_function_name)
            data = fetch_function(session) 
            if data is None:
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

def run_scrape():
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

        # Sıralı Analiz
        for i, (game_name, raw_data, config, hash_or_flag) in enumerate(fetched_data):
            
            if hash_or_flag == "SKIPPED":
                continue 
            
            safe_name = config['safe_name']

            if not raw_data:
                fallback = f"{game_name} received balance changes and new content."
                logging.warning(f"⚠️  {game_name} için veri yok. Fallback metin kullanılıyor.")
                raw_data = fallback
            else:
                logging.info(f"ANALİZ 🧠: {game_name} verisi işleniyor (Hash: {hash_or_flag[:7]}...).")

            # 'send_alert' fonksiyonu utils.py'ye parametre olarak geçilir [cite: 104-105].
            # Artık güncellenmiş send_alert (Telegram + Slack) fonksiyonumuzu kullanacak.
            result = analyze_with_gemini(raw_data, game_name, send_alert) 
            
            if result:
                save_json_to_s3(result, safe_name)
                
                if hash_or_flag not in [None, "SKIPPED"]:
                    save_hash_to_s3(safe_name, hash_or_flag)
                
                # --- YENİ EKLENDİ: Başarılı Sonucu Telegram'a Gönder ---
                logging.info(f"TELEGRAM ✉️: {game_name} için başarılı analiz sonucu gönderiliyor...")
                formatted_message = format_patch_notes_for_telegram(result)
                send_telegram_message(formatted_message, parse_mode="HTML")
                # ----------------------------------------------------
                
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

if __name__ == "__main__":
    args = dict(arg.split('=') for arg in sys.argv[1:] if '=' in arg)
    run_mode = args.get('--run', 'scrape') 

    if run_mode == 'health':
        run_health_check()
    elif run_mode == 'scrape':
        run_scrape()
    else:
        logging.error(f"Geçersiz çalışma modu: {run_mode}. '--run=scrape' veya '--run=health' kullanın.")