# scrapers.py (YENİ - Modüler)

import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin # Göreceli URL'leri birleştirmek için

def fetch_html_generic(session, config):
    """
    sources.yaml'dan gelen 'html' stratejisine göre veri çeker.
    
    İki modu destekler:
    1. 'link' seçicisi varsa (List-Detail): Ana sayfadan linki bulur, o linke gider, içeriği çeker.
    2. 'link' seçicisi yoksa (Direct): Ana sayfadan doğrudan içeriği çeker.
    """
    url = config['url']
    selectors = config['selectors']
    base_url = config.get('base_url', url) # base_url yoksa, ana url'i kullan
    text_limit = config.get('text_limit', 3500)
    
    try:
        res = session.get(url, timeout=15)
        res.raise_for_status() # Hatalı yanıt (4xx, 5xx) varsa exception fırlat
        soup = BeautifulSoup(res.text, 'html.parser')
        
        content_text = None
        
        # Mod 1: List-Detail (örn: Valorant, Minecraft, LoL, Fortnite)
        if 'link' in selectors and selectors['link']:
            link_element = soup.select_one(selectors['link'])
            
            if link_element and link_element.get('href'):
                # Göreceli linkleri (örn: "/en-us/news/...") tam URL'ye çevir
                detail_url = urljoin(base_url, link_element['href'])
                
                logging.info(f"  -> Detay sayfasına gidiliyor: {detail_url}")
                detail_res = session.get(detail_url, timeout=15)
                detail_res.raise_for_status()
                detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
                
                content_element = detail_soup.select_one(selectors['content'])
                if content_element:
                    content_text = content_element.get_text(separator="\n", strip=True)
                else:
                    logging.warning(f"({config['game']}) Detay sayfasında 'content' seçicisi bulunamadı: {selectors['content']}")
            else:
                 logging.warning(f"({config['game']}) Ana sayfada 'link' seçicisi bulunamadı: {selectors['link']}")

        # Mod 2: Direct (örn: Counter-Strike 2)
        else:
            content_element = soup.select_one(selectors['content'])
            if content_element:
                content_text = content_element.get_text(separator="\n", strip=True)
            else:
                logging.warning(f"({config['game']}) Ana sayfada 'content' seçicisi bulunamadı: {selectors['content']}")

        if content_text:
            return content_text[:text_limit] # Metni AI'a göndermeden önce kırp
            
        logging.warning(f"({config['game']}) İçin {url} adresinden veri çekilemedi.")
        return None

    except Exception as e:
        logging.warning(f"({config['game']}) scraping hatası (generic_html): {e}")
        return None

def fetch_rss_generic(session, config):
    """
    sources.yaml'dan gelen 'rss' stratejisine göre veri çeker.
    (Örn: Roblox)
    """
    url = config['url']
    selectors = config['selectors']
    text_limit = config.get('text_limit', 1000)
    
    try:
        res = session.get(url, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "lxml-xml") # RSS/XML için lxml parser
        
        item = soup.find("item") # Genellikle ilk 'item' en yenisidir
        if not item:
            logging.warning(f"({config['game']}) RSS akışında <item> bulunamadı: {url}")
            return None
            
        content_parts = []
        for tag in selectors['content']: # ['title', 'description']
            element = item.find(tag)
            if element:
                content_parts.append(element.get_text(strip=True))
        
        if content_parts:
            return "\n".join(content_parts)[:text_limit]
            
        logging.warning(f"({config['game']}) RSS akışında seçiciler bulunamadı: {selectors['content']}")
        return None

    except Exception as e:
        logging.warning(f"({config['game']}) scraping hatası (generic_rss): {e}")
        return None