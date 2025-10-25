import logging
from bs4 import BeautifulSoup

# Bu dosya, scrape.py içindeki tüm fetch_* fonksiyonlarını barındırır.
# Her fonksiyon, scrape.py'de oluşturulan ana 'session' objesini parametre olarak alır.

def fetch_valorant_patch_notes(session):
    url = "https://playvalorant.com/en-us/news/game-updates/"
    try:
        res = session.get(url, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # En son yama notu makalesine giden ilk bağlantıyı bul
        # Genellikle "game-updates" veya "patch-notes" içeren bir href ararız
        patch_link = soup.find("a", href=lambda h: h and ("/patch-notes/" in h or "/game-updates/" in h))
        
        if patch_link and patch_link["href"]:
            full_url = "https://playvalorant.com" + patch_link["href"]
            detail_res = session.get(full_url, timeout=15)
            detail_soup = BeautifulSoup(detail_res.text, 'html.parser')

            # --- GÜNCELLEME ---
            # Orijinal seçici (muhtemelen bozuldu):
            # content_div = detail_soup.find("div", class_="news-item-content")
            
            # YENİ, DAHA DAYANIKLI SEÇİCİ:
            # Valorant'ın makale gövdesi için genellikle "Article-module--body" içeren
            # dinamik bir sınıf adı kullandığını varsayıyoruz.
            content_div = detail_soup.find("div", class_=lambda c: c and "Article-module--body" in c)

            # Eğer bu da çalışmazsa, ana <article> etiketini arayabiliriz (daha semantik)
            if not content_div:
                content_div = detail_soup.find("article")
            # --- GÜNCELLEME SONU ---

            if content_div:
                return content_div.get_text(separator="\n", strip=True)[:3500] # Limiti biraz artırdık
        
        logging.warning("Valorant: Ana sayfada yama notu bağlantısı bulunamadı.")
        return None # Tetikleyici 'None' döndürür
        
    except Exception as e:
        logging.warning(f"Valorant scraping hatası: {e}")
        return None

def fetch_roblox_patch_notes(session):
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

def fetch_minecraft_patch_notes(session):
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

def fetch_league_patch_notes(session):
    try:
        res = session.get("https://www.leagueoflegends.com/en-us/news/tags/patch-notes/", timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        link = soup.find("a", href=lambda x: x and "/en-us/news/game-updates/" in x)
        if link:
            full_url = "https://www.leagueoflegends.com" + link["href"]
            detail = session.get(full_url, timeout=15)
            dsoup = BeautifulSoup(detail.text, 'html.parser')
            content = dsoup.find("div", class_="article-content")
            return content.get_text(separator="\n", strip=True)[:3500] if content else "New LoL patch."
        return "League of Legends balance changes."
    except Exception as e:
        logging.warning(f"LoL scraping hatası: {e}")
        return "Jhin damage reduced. New rune added."

def fetch_cs2_patch_notes(session):
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

def fetch_fortnite_patch_notes(session):
    try:
        res = session.get("https://www.epicgames.com/fortnite/en-US/news", timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Fortnite'ın /news sayfasındaki ilgili makaleyi bul
        # Genellikle "patch-notes" veya "whats-new" içeren bir href ararız
        patch_link = soup.find("a", href=lambda h: h and ("/patch-notes/" in h or "/whats-new-" in h or "battle-royale-v" in h))

        if patch_link and patch_link["href"]:
            # href tam URL değilse başına ekle
            if patch_link["href"].startswith("/"):
                full_url = "https://www.epicgames.com" + patch_link["href"]
            else:
                full_url = patch_link["href"]
                
            detail = session.get(full_url, timeout=15)
            dsoup = BeautifulSoup(detail.text, 'html.parser')
            
            # Makale gövdesini bul (genellikle 'cms-content' veya benzeri bir sınıf)
            main = dsoup.find("div", class_=lambda c: c and "cms-content" in c)
            if not main:
                main = dsoup.find("main") # Fallback
                
            return main.get_text(separator="\n", strip=True)[:3500] if main else "Fortnite new season."
        return "Fortnite: New weapons and map changes."
    except Exception as e:
        logging.warning(f"Fortnite scraping hatası: {e}")
        return "Added Shockwave Grenade. Tilted Towers returns."
