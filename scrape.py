import os
import json
import time
import random
import logging
import boto3
import requests # <-- YENİ EKLENDİ
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

# --- YENİ EKLENDİ: Slack Hata Bildirimi (Öneri 4.1) ---
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
# -----------------------------------------------------------

if not GEMINI_API_KEY or not S3_BUCKET_NAME:
    error_msg = "❌ .env dosyasında GEMINI_API_KEY veya S3 bilgileri eksik!"
    send_alert(error_msg) # <-- Hata bildirimi eklendi
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
    # ... (Bu fonksiyon değişmedi)
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
    })
    return session

session = create_session()

# --- SCRAPER FONKSİYONLARI ---
# ... (fetch_valorant_patch_notes, fetch_roblox_patch_notes vb. fonksiyonlar değişmedi)
def fetch_valorant_patch_notes():
    url = "https://playvalorant.com/en-us/news/game-updates/"
    try:
        res = session.get(url, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        links = soup.find_all("a", href=True)
        for link in links:
            href = link["href"]
            if any(kw in href for kw in ["/patch-notes", "/game-updates/", "/news/updates/"]):
                full_url = "https://playvalorant.com" + href
                detail_res = session.get(full_url, timeout=15)
                detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
                content_div = detail_soup.find("div", class_="news-item-content")
                if content_div:
                    return content_div.get_text(separator="\n", strip=True)[:3000]
        return None
    except Exception as e:
        logging.warning(f"Valorant scraping hatası: {e}")
        return None

def fetch_roblox_patch_notes():
    try:
        res = session.get("https://create.roblox.com/docs/reference/updates.rss", timeout=15)
        soup = BeautifulSoup(res.text, "lxml-xml") 
        item = soup.find("item")
        if item:
            title = item.find("title").text if item.find("title") else "Roblox Update"
            desc = item.find("description").text if item.find("description") else ""
            return f"{title}\n{desc}"[:500]
        return "Roblox platform updates."
    except Exception as e:
        logging.warning(f"Roblox RSS hatası: {e}")
        return "Roblox updated core systems."

def fetch_minecraft_patch_notes():
    try:
        res = session.get("https://www.minecraft.net/en-us/feeds/community-content/rss", timeout=15)
        soup = BeautifulSoup(res.text, "lxml-xml")
        item = soup.find("item")
        if item:
            title = item.find("title").text if item.find("title") else "Minecraft Update"
            desc = item.find("description").text if item.find("description") else ""
            return f"{title}\n{desc}"[:500]
        return "Minecraft new features added."
    except Exception as e:
        logging.warning(f"Minecraft scraping hatası: {e}")
        return "Minecraft added new biomes and mobs."

def fetch_league_patch_notes():
    try:
        res = session.get("https://www.leagueoflegends.com/en-us/news/tags/patch-notes/", timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        link = soup.find("a", href=lambda x: x and "/en-us/news/game-updates/" in x)
        if link:
            full_url = "https://www.leagueoflegends.com" + link["href"]
            detail = session.get(full_url, timeout=15)
            dsoup = BeautifulSoup(detail.text, 'html.parser')
            content = dsoup.find("div", class_="article-content")
            return content.get_text(separator="\n", strip=True)[:3000] if content else "New LoL patch."
        return "League of Legends balance changes."
    except Exception as e:
        logging.warning(f"LoL scraping hatası: {e}")
        return "Jhin damage reduced. New rune added."

def fetch_cs2_patch_notes():
    try:
        res = session.get("https://blog.counter-strike.net/index.php/category/updates/", timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        post = soup.find("div", class_="post")
        if post:
            title = post.find("h2").get_text(strip=True) if post.find("h2") else "CS2 Update"
            content = post.get_text(separator="\n", strip=True)
            return f"{title}\n{content}"[:3000]
        return "CS2 bug fixes."
    except Exception as e:
        logging.warning(f"CS2 scraping hatası: {e}")
        return "CS2: Fixed smoke grenade collision."

def fetch_fortnite_patch_notes():
    try:
        res = session.get("https://www.epicgames.com/fortnite/news/patch-notes", timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        first_link = soup.find("a", href=lambda x: x and "/fortnite/news/patch-notes/" in x)
        if first_link:
            full_url = "https://www.epicgames.com" + first_link["href"]
            detail = session.get(full_url, timeout=15)
            dsoup = BeautifulSoup(detail.text, 'html.parser')
            main = dsoup.find("main") or dsoup.find("div", class_="blog-content")
            return main.get_text(separator="\n", strip=True)[:3000] if main else "Fortnite new season."
        return "Fortnite: New weapons and map changes."
    except Exception as e:
        logging.warning(f"Fortnite scraping hatası: {e}")
        return "Added Shockwave Grenade. Tilted Towers returns."

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
        send_alert(f"❌ S3'e yazma hatası ({filename}): {e}") # <-- Hata bildirimi eklendi

if __name__ == "__main__":
    logging.info("🚀 Tüm oyunların yama analizi başlatılıyor...")
    
    # --- YENİ EKLENDİ: Tüm betik için hata yakalama ---
    try:
        games = {
            "Valorant": fetch_valorant_patch_notes,
            "Roblox": fetch_roblox_patch_notes,
            "Minecraft": fetch_minecraft_patch_notes,
            "League of Legends": fetch_league_patch_notes,
            "Counter-Strike 2": fetch_cs2_patch_notes,
            "Fortnite": fetch_fortnite_patch_notes,
        }

        for i, (game_name, fetch_fn) in enumerate(games.items()):
            logging.info(f"🔍 {game_name} için veri çekiliyor...")
            raw = fetch_fn()
            if not raw:
                fallback = f"{game_name} received balance changes and new content."
                logging.warning(f"⚠️  {game_name} için veri yok. Fallback metin kullanılıyor.")
                raw = fallback

            result = analyze_with_gemini(raw, game_name, send_alert) # send_alert fonksiyonunu utils'e iletiyoruz
            
            if result:
                safe_name = game_name.lower().replace(" ", "_").replace("-", "_").replace(".", "")
                save_json_to_s3(result, safe_name)
            else:
                logging.error(f"❌ {game_name} analizi başarısız.")
                # utils.py içinde zaten hata bildirimi yapıldı
            
            if i < len(games) - 1:
                delay = random.uniform(5, 12)
                logging.info(f"⏳ Gemini rate limit koruması için {delay:.1f} saniye bekleniyor...")
                time.sleep(delay)
        
        logging.info("✅ Tüm oyunların yama analizi başarıyla tamamlandı.")
        
    except Exception as e:
        logging.error(f"CRITICAL: Cron Job'da beklenmedik hata: {e}", exc_info=True)
        send_alert(f"CRITICAL: Cron Job'un tamamı çöktü: {e}")
    # ----------------------------------------------------