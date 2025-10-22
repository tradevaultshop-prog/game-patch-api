# scrape.py
import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup

# 🔐 .env dosyasını yükle
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("❌ .env dosyasında OPENAI_API_KEY tanımlı değil!")

client = OpenAI(api_key=OPENAI_API_KEY)

def fetch_valorant_patch_notes():
    """Valorant'in son yama sayfasından metni çeker."""
    url = "https://playvalorant.com/en-us/news/game-updates/"
    try:
        print("🌐 Valorant yama sayfası yükleniyor...")
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')

        # Tüm makale bağlantılarını bul
        links = soup.find_all("a", href=True)
        for link in links:
            href = link["href"]
            if "/en-us/news/game-updates/patch-notes" in href:
                full_url = "https://playvalorant.com" + href
                print(f"📄 Yama notu bulundu: {full_url}")
                # İçeriği çek
                detail_res = requests.get(full_url, timeout=10)
                detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
                # Ana içerik metnini al (basit yöntem)
                content_div = detail_soup.find("div", class_="news-item-content")
                if content_div:
                    text = content_div.get_text(separator="\n", strip=True)
                    return text[:3000]  # İlk 3000 karakter yeterli
        return None
    except Exception as e:
        print("❌ Web scraping hatası:", e)
        return None

def analyze_with_openai(raw_text: str):
    """OpenAI ile metni analiz edip JSON döner."""
    prompt = f"""
    Aşağıdaki oyun yama notlarından sadece dengesizlik (nerf/buff), yeni içerik veya önemli değişiklikleri çıkar.
    Sadece geçerli JSON döndür. Hiçbir açıklama ekleme.
    Format:
    {{
      "game": "Valorant",
      "patch_version": "bilinmiyorsa 'unknown'",
      "date": "bilinmiyorsa 'unknown'",
      "changes": [
        {{
          "type": "nerf|buff|new|fix",
          "target": "karakter/silah",
          "ability": "yetenek (varsa)",
          "details": "açıklama"
        }}
      ]
    }}

    Metin:
    {raw_text}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        content = response.choices[0].message.content.strip()

        # ```json ... ``` bloklarını temizle
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()

        return json.loads(content)
    except Exception as e:
        print("❌ OpenAI JSON hatası:", e)
        return None

def save_json(data, filename="valorant_latest.json"):
    os.makedirs("patches", exist_ok=True)
    path = os.path.join("patches", filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ JSON kaydedildi: {path}")

if __name__ == "__main__":
    print("🚀 Otomatik yama analizi başlatılıyor...")
    
    # 1. Web'den metin çek
    raw_text = fetch_valorant_patch_notes()
    if not raw_text:
        print("⚠️  Web'den veri alınamadı. Elle örnek metin kullanılıyor.")
        raw_text = """
        Jett's Updraft cooldown increased from 12s to 16s.
        Operator damage falloff reduced by 15%.
        New map 'Sunset' added.
        """

    print("\n📝 Ham metin:\n", raw_text[:200], "...\n")

    # 2. OpenAI ile analiz et
    result = analyze_with_openai(raw_text)
    
    if result:
        save_json(result, "valorant_latest.json")
        print("\n🧠 OpenAI Sonucu:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("❌ Analiz başarısız.")