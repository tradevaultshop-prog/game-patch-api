import os
import json
import time
import random
import logging
from datetime import datetime
# Yeni sistemde OpenAI kald?r?ld?
# from openai import OpenAI 
from dotenv import load_dotenv
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
# ?? Duzeltme: save_json bu dosyada oldu?u icin sadece analyze_with_gemini ice aktar?l?yor
from utils import analyze_with_gemini 

# ?? .env dosyas?n? yukle
load_dotenv()
# Anahtar ismi GEMINI_API_KEY olarak de?i?ti
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    # Hata kontrolunu Gemini anahtar?na gore guncelleyin
    raise ValueError("? .env dosyas?nda GEMINI_API_KEY tan?ml? de?il!")

# ?? Logging ayar? 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("scraper.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# ?? Guvenilir session 
def create_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
    })
    return session

session = create_session()

# ================================
# ?? SCRAPER FONKS?YONLARI 
# ================================
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
        logging.warning(f"Valorant scraping hatas?: {e}")
        return None

def fetch_roblox_patch_notes():
    try:
        res = session.get("https://create.roblox.com/docs/reference/updates.rss", timeout=15)
        # DUZELTME: XML ayr??t?r?c?s? olarak 'lxml-xml' kullan?l?yor.
        soup = BeautifulSoup(res.text, "lxml-xml") 
        item = soup.find("item")
        if item:
            title = item.find("title").text if item.find("title") else "Roblox Update"
            desc = item.find("description").text if item.find("description") else ""
            return f"{title}\n{desc}"[:500]
        return "Roblox platform updates."
    except Exception as e:
        logging.warning(f"Roblox RSS hatas?: {e}")
        return "Roblox updated core systems."

def fetch_minecraft_patch_notes():
    try:
        res = session.get("https://www.minecraft.net/en-us/feeds/community-content/rss", timeout=15)
        # DUZELTME: XML ayr??t?r?c?s? olarak 'lxml-xml' kullan?l?yor.
        soup = BeautifulSoup(res.text, "lxml-xml")
        item = soup.find("item")
        if item:
            title = item.find("title").text if item.find("title") else "Minecraft Update"
            desc = item.find("description").text if item.find("description") else ""
            return f"{title}\n{desc}"[:500]
        return "Minecraft new features added."
    except Exception as e:
        logging.warning(f"Minecraft scraping hatas?: {e}")
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
        logging.warning(f"LoL scraping hatas?: {e}")
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
        logging.warning(f"CS2 scraping hatas?: {e}")
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
        logging.warning(f"Fortnite scraping hatas?: {e}")
        return "Added Shockwave Grenade. Tilted Towers returns."

# ================================
# ?? Kaydet (BU FONKS?YON BU DOSYADA KALMALI)
# ================================
def save_json(data, base_name):
    os.makedirs("patches", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{base_name}_latest_{timestamp}.json"
    path = os.path.join("patches", filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logging.info(f"? JSON kaydedildi: {path}")

# ================================
# ?? Ana Cal??t?rma (Gemini ile guncellendi)
# ================================

if __name__ == "__main__":
    logging.info("?? Tum oyunlar?n yama analizi ba?lat?l?yor...")

    games = {
        "Valorant": fetch_valorant_patch_notes,
        "Roblox": fetch_roblox_patch_notes,
        "Minecraft": fetch_minecraft_patch_notes,
        "League of Legends": fetch_league_patch_notes,
        "Counter-Strike 2": fetch_cs2_patch_notes,
        "Fortnite": fetch_fortnite_patch_notes, # <-- SOZD?Z?M? HATASI DUZELT?LD?
    }

    for i, (game_name, fetch_fn) in enumerate(games.items()):
        logging.info(f"?? {game_name} icin veri cekiliyor...")
        raw = fetch_fn()
        if not raw:
            fallback = f"{game_name} received balance changes and new content."
            logging.warning(f"??? {game_name} icin veri yok. Fallback metin kullan?l?yor.")
            raw = fallback

        # ?? Gemini fonksiyonu ca?r?l?yor
        result = analyze_with_gemini(raw, game_name) 
        
        if result:
            safe_name = game_name.lower().replace(" ", "_").replace("-", "_").replace(".", "")
            save_json(result, safe_name)
        else:
            logging.error(f"? {game_name} analizi ba?ar?s?z.")

        # Rate limit korumas?: bekleme suresi ayn? kald?, 
        if i < len(games) - 1:  # Son o?e icin bekleme gerekmez
            delay = random.uniform(5, 12)
            logging.info(f"? Gemini rate limit korumas? icin {delay:.1f} saniye bekleniyor...")
            time.sleep(delay)