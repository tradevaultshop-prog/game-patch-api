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

# --- Ortam Değişkenlerini Yükle ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- S3 Client Kurulumu ---
s3_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("S3_ENDPOINT_URL"),
    aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
    region_name="auto", 
)
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# --- Bildirim Anahtarları ---
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- Etki Skoru Hesaplama ---
def calculate_impact_score(changes_array):
    if not changes_array:
        return 0
    score = 0
    for change in changes_array:
        change_type = change.get("type", "").lower()
        if change_type in ["nerf", "buff", "new"]:
            score += 2
        else:
            score += 1
    return min(10, score)

def get_impact_label(score):
    if score >= 8:
        return "Büyük"
    elif score >= 4:
        return "Orta"
    else:
        return "Küçük"

# --- Bildirim Fonksiyonları ---
def send_telegram_message(message_text, parse_mode="HTML"):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID tanımlı değil. Telegram bildirimi atlanıyor.")
        return
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message_text, 'parse_mode': parse_mode}
    try:
        requests.post(api_url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Telegram bildirimi gönderilemedi: {e}")

def send_alert(message):
    if SLACK_WEBHOOK_URL:
        try:
            payload = {"text": f"🚨 **GPNAI Servis Uyarısı** 🚨\n\n```{message}```"}
            requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        except Exception as e:
            logging.error(f"Slack bildirimi gönderilemedi: {e}")
    else:
        logging.warning("SLACK_WEBHOOK_URL tanımlı değil. Slack bildirimi atlanıyor.")

    telegram_error_message = f"🚨 GPNAI Servis Uyarısı 🚨\n\n{message}"
    send_telegram_message(telegram_error_message, parse_mode=None)

# --- Telegram Mesaj Formatlama ---
def format_patch_notes_for_telegram(json_data):
    try:
        game = json_data.get('game', 'Bilinmeyen Oyun')
        version = json_data.get('patch_version', 'unknown')
        date = json_data.get('date', 'unknown')
        changes = json_data.get('changes', [])
        
        score = json_data.get('impact_score', 0)
        label = json_data.get('impact_label', 'Küçük')
        emoji = "🔥" if label == "Büyük" else ("⚠️" if label == "Orta" else "ℹ️")

        message = f"✅ <b>{game} için Yeni Yama Notları Analiz Edildi!</b>\n\n"
        message += f"<b>{emoji} Yama Etki Skoru: {label} ({score}/10)</b>\n\n"
        message += f"<b>Versiyon:</b> <code>{version}</code>\n"
        message += f"<b>Tarih:</b> <code>{date}</code>\n"
        message += "-----------------------------------\n"

        if not changes:
            message += "<i>Analiz tamamlandı ancak raporlanacak (nerf, buff, new, fix) önemli bir değişiklik bulunamadı.</i>"
            return message

        change_map = {"buff": [], "nerf": [], "new": [], "fix": []}
        other = []
        for change in changes:
            change_type = change.get('type', 'other').lower()
            target = change.get('target', 'Bilinmiyor')
            details_data = change.get('details', 'Detay yok')
            if isinstance(details_data, dict):
                details = details_data.get('tr', details_data.get('en', 'Detay yok'))
            else:
                details = str(details_data)
            ability = change.get('ability')
            target_str = f"{target} ({ability})" if ability and ability.lower() not in ['unknown', 'n/a', ''] else target
            entry = f"  - <b>{target_str}:</b> <i>{details}</i>"
            if change_type in change_map: change_map[change_type].append(entry)
            else: other.append(entry)
        
        if change_map["buff"]: message += "🟢 <b>Güçlendirmeler (Buffs):</b>\n" + "\n".join(change_map["buff"]) + "\n\n"
        if change_map["nerf"]: message += "🔴 <b>Zayıflatmalar (Nerfs):</b>\n" + "\n".join(change_map["nerf"]) + "\n\n"
        if change_map["new"]: message += "✨ <b>Yeni İçerik/Değişiklikler:</b>\n" + "\n".join(change_map["new"]) + "\n\n"
        if change_map["fix"]: message += "🔧 <b>Hata Düzeltmeleri (Fixes):</b>\n" + "\n".join(change_map["fix"]) + "\n\n"
        if other: message += "📋 <b>Diğer Değişiklikler:</b>\n" + "\n".join(other)
        return message.strip()
    except Exception as e:
        logging.error(f"Telegram formatlama hatası: {e}")
        return f"❌ <b>{json_data.get('game', 'Bilinmeyen Oyun')} için formatlama hatası oluştu.</b>"

# --- Sistem Kontrolü ---
if not GEMINI_API_KEY or not S3_BUCKET_NAME:
    error_msg = "❌ .env dosyasında GEMINI_API_KEY veya S3 bilgileri eksik!"
    send_alert(error_msg)
    raise ValueError(error_msg)

# --- Loglama ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("scraper.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# --- Yardımcı Fonksiyonlar ---
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
            Bucket=S3_BUCKET_NAME, Key=hash_key, Body=new_hash.encode('utf-8'), ContentType="text/plain"
        )
    except Exception as e:
        logging.error(f"S3'e hash yazma hatası ({hash_key}): {e}")
        send_alert(f"❌ S3'e hash yazma hatası ({hash_key}): {e}")

# --- YENİ: INDEX GÜNCELLEME ---
def update_index_file_in_s3(safe_name, archive_key, patch_data, timestamp_str):
    index_key = f"{safe_name}/index.json"
    try:
        try:
            response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=index_key)
            content = response['Body'].read()
            index_data = json.loads(content)
        except s3_client.exceptions.NoSuchKey:
            index_data = {"game": patch_data.get("game"), "history": []}
        except Exception as e:
            logging.warning(f"S3 Index okuma hatası ({index_key}): {e}. Yeni index oluşturulacak.")
            index_data = {"game": patch_data.get("game"), "history": []}

        new_entry = {
            "key": archive_key,
            "date": timestamp_str,
            "patch_version": patch_data.get("patch_version", "unknown"),
            "impact_score": patch_data.get("impact_score", 0),
            "impact_label": patch_data.get("impact_label", "Küçük")
        }

        index_data["history"] = [entry for entry in index_data["history"] if entry["key"] != archive_key]
        index_data["history"].insert(0, new_entry)

        index_string = json.dumps(index_data, indent=2, ensure_ascii=False)
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME, Key=index_key, Body=index_string, ContentType="application/json"
        )
        logging.info(f"✅ INDEX S3'e kaydedildi: {S3_BUCKET_NAME}/{index_key}")
    except Exception as e:
        logging.error(f"❌ S3 Index yazma hatası ({index_key}): {e}")
        send_alert(f"❌ S3 Index yazma hatası ({index_key}): {e}")

# --- Güncellenmiş S3 Kaydetme Fonksiyonu ---
def save_json_to_s3_and_archive(data, base_name):
    try:
        json_string = json.dumps(data, indent=2, ensure_ascii=False)
        timestamp = datetime.utcnow()
        timestamp_str_file = timestamp.strftime('%Y%m%d_%H%M%S')
        timestamp_str_iso = timestamp.isoformat()

        archive_filename = f"{base_name}/{timestamp_str_file}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME, Key=archive_filename, Body=json_string, ContentType="application/json"
        )
        logging.info(f"✅ ARŞİV S3'e kaydedildi: {S3_BUCKET_NAME}/{archive_filename}")

        latest_filename = f"{base_name}_latest.json"
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME, Key=latest_filename, Body=json_string, ContentType="application/json"
        )
        logging.info(f"✅ GÜNCEL S3'e kaydedildi: {S3_BUCKET_NAME}/{latest_filename}")

        try:
            update_index_file_in_s3(base_name, archive_filename, data, timestamp_str_iso)
        except Exception as e:
            logging.error(f"Index güncelleme fonksiyonu çağrılırken hata: {e}")

    except Exception as e:
        logging.error(f"❌ S3'e yazma hatası ({base_name}): {e}")
        send_alert(f"❌ S3'e yazma hatası ({base_name}): {e}")

# --- Veri Çekme (GÜNCELLENDİ) ---
def fetch_game_data(game_config, session):
    game_name = game_config.get('game')
    safe_name = game_config.get('safe_name')
    
    # --- YENİ Strateji Tabanlı Yönlendirme ---
    strategy = game_config.get('strategy')
    fetch_function = None
    
    if strategy == 'html':
        fetch_function = getattr(scrapers, 'fetch_html_generic', None)
    elif strategy == 'rss':
        fetch_function = getattr(scrapers, 'fetch_rss_generic', None)
    else:
        # Eski fonksiyon adlarını destekleyebilirsiniz (opsiyonel)
        fetch_function_name = game_config.get('fetch_function')
        if fetch_function_name and hasattr(scrapers, fetch_function_name):
            fetch_function = getattr(scrapers, fetch_function_name)
        else:
            logging.error(f"THREAD ❌: {game_name} için 'strategy' (html/rss) tanımlanmamış ve fetch_function bulunamadı. Atlanıyor.")
            return game_name, None, game_config, None
    # --- Yönlendirme Sonu ---

    try:
        logging.info(f"THREAD 🔍: {game_name} için veri çekiliyor (Strateji: {strategy})...")
        
        # Genel fonksiyona 'session' ve tüm 'config' objesini gönderiyoruz
        raw_data = fetch_function(session, game_config) 
        
        if not raw_data:
            logging.warning(f"THREAD ⚠️: {game_name} için veri bulunamadı.")
            return game_name, None, game_config, None
            
        new_hash = hashlib.sha256(raw_data.encode('utf-8')).hexdigest()
        old_hash = get_hash_from_s3(safe_name)
        
        if new_hash == old_hash:
            logging.info(f"THREAD ⏩: {game_name} verisi değişmemiş. Gemini analizi atlanıyor.")
            return game_name, raw_data, game_config, "SKIPPED"
            
        # Değişiklik var, yeni hash ile devam et
        return game_name, raw_data, game_config, new_hash
        
    except Exception as e:
        logging.error(f"THREAD ❌: {game_name} veri çekme hatası (Strateji: {strategy}): {e}", exc_info=True)
        return game_name, None, game_config, None

# --- Sağlık Kontrolü (GÜNCELLENDİ) ---
def run_health_check():
    logging.info("🩺 Proaktif Sağlık Kontrolü başlıyor...")
    try:
        with open("sources.yaml", "r", encoding="utf-8") as f:
            games_config = yaml.safe_load(f)
    except FileNotFoundError:
        send_alert("CRITICAL (Health Check): `sources.yaml` dosyası bulunamadı!")
        return
        
    broken_scrapers = []
    session = create_session()
    
    for config in games_config:
        game_name = config.get('game')
        strategy = config.get('strategy')
        fetch_function = None
        
        if strategy == 'html':
            fetch_function = getattr(scrapers, 'fetch_html_generic', None)
        elif strategy == 'rss':
            fetch_function = getattr(scrapers, 'fetch_rss_generic', None)
        else:
            # Fallback: eski fetch_function adı
            fetch_function_name = config.get('fetch_function')
            if fetch_function_name and hasattr(scrapers, fetch_function_name):
                fetch_function = getattr(scrapers, fetch_function_name)
            else:
                logging.warning(f"HEALTH ⚠️: {game_name} için 'strategy' yok ve fetch_function tanımlı değil. Atlanıyor.")
                continue
            
        try:
            # Genel fonksiyona 'session' ve 'config' gönder
            data = fetch_function(session, config)
            if data is None:
                broken_scrapers.append(f"{game_name} (Strateji: {strategy} - Veri 'None' döndü)")
        except Exception as e:
            logging.error(f"HEALTH ❌: {game_name} (Strateji: {strategy}) scraper'ı çöktü: {e}")
            broken_scrapers.append(f"{game_name} (Strateji: {strategy} - Çöktü)")
            
    session.close()
    
    if broken_scrapers:
        send_alert("❌ PROAKTİF UYARI: Şu scraper'lar bozulmuş olabilir:\n- " + "\n- ".join(broken_scrapers))
    else:
        logging.info("✅ Sağlık Kontrolü tamamlandı. Tüm (generic) scraper'lar çalışıyor.")

# --- Ana Scraper ---
def run_scrape():
    logging.info("🚀 Tam Kapsamlı Yama Analizi başlıyor...")
    try:
        with open("sources.yaml", "r", encoding="utf-8") as f:
            games_config = yaml.safe_load(f)
        session = create_session()
        fetched_data = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(games_config)) as executor:
            futures = [executor.submit(fetch_game_data, config, session) for config in games_config]
            for future in concurrent.futures.as_completed(futures):
                fetched_data.append(future.result())
        session.close()

        for i, (game_name, raw_data, config, hash_or_flag) in enumerate(fetched_data):
            if hash_or_flag == "SKIPPED":
                continue
            safe_name = config.get('safe_name')
            if not raw_data:
                raw_data = f"{game_name} received balance changes and new content."
                logging.warning(f"⚠️  {game_name} için veri yok. Fallback metin kullanılıyor.")
            else:
                logging.info(f"ANALİZ 🧠: {game_name} verisi işleniyor (Hash: {str(hash_or_flag)[:7]}...).")

            result = analyze_with_gemini(raw_data, game_name, send_alert)
            if result:
                changes = result.get("changes", [])
                score = calculate_impact_score(changes)
                label = get_impact_label(score)
                result["impact_score"] = score
                result["impact_label"] = label

                save_json_to_s3_and_archive(result, safe_name)

                if hash_or_flag not in [None, "SKIPPED"]:
                    save_hash_to_s3(safe_name, hash_or_flag)

                formatted_message = format_patch_notes_for_telegram(result)
                send_telegram_message(formatted_message, parse_mode="HTML")
            else:
                logging.error(f"❌ {game_name} analizi başarısız.")

            if i < len(fetched_data) - 1:
                delay = random.uniform(5, 12)
                logging.info(f"⏳ Bekleniyor ({delay:.1f}s)...")
                time.sleep(delay)

        logging.info("✅ Tüm oyunların yama analizi tamamlandı.")
    except Exception as e:
        logging.error(f"CRITICAL: Cron Job'da hata: {e}", exc_info=True)
        send_alert(f"CRITICAL: Cron Job çöktü: {e}")

# --- Giriş Noktası ---
if __name__ == "__main__":
    args = dict(arg.split('=') for arg in sys.argv[1:] if '=' in arg)
    run_mode = args.get('--run', 'scrape')
    if run_mode == 'health':
        run_health_check()
    elif run_mode == 'scrape':
        run_scrape()
    else:
        logging.error(f"Geçersiz çalışma modu: {run_mode}. '--run=scrape' veya '--run=health' kullanın.")
