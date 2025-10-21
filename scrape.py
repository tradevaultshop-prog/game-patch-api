# scrape.py
import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# 🔐 .env dosyasındaki çevresel değişkenleri yükle
load_dotenv()

# 🔑 OpenAI API anahtarını ortam değişkenlerinden al
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def analyze_patch_notes_with_openai(raw_text: str, game_name: str = "Valorant"):
    client = OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""
    Aşağıdaki oyun yama notlarından sadece dengesizlik (nerf/buff), yeni içerik veya önemli değişiklikleri çıkar.
    Sadece geçerli JSON döndür. Hiçbir açıklama, açıklama satırı veya ek metin ekleme.
    Format:
    {{
      "game": "{game_name}",
      "patch_version": "bilinmiyorsa 'unknown'",
      "date": "bilinmiyorsa 'unknown'",
      "changes": [
        {{
          "type": "nerf|buff|new|fix",
          "target": "karakter/silah/özellik adı",
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

        # OpenAI bazen yanıtı ```json ile başlatabilir, bunu temizleyelim
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()

        return json.loads(content)
    except Exception as e:
        print("❌ OpenAI hatası:", e)
        print("OpenAI yanıtı:", response.choices[0].message.content if 'response' in locals() else "Yok")
        return None

def save_patch_to_file(data, filename="valorant_openai.json"):
    os.makedirs("patches", exist_ok=True)
    filepath = os.path.join("patches", filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ JSON kaydedildi: {filepath}")

if __name__ == "__main__":
    # 🧪 Örnek yama notu (test amaçlı)
    example_text = """
    Jett's Updraft ability cooldown increased from 12s to 16s.
    Operator damage falloff reduced by 15%.
    New map 'Sunset' added to competitive rotation.
    Fixed a crash when using melee during ult.
    """

    print("🔍 OpenAI ile yama notlarını analiz ediyorum...")
    result = analyze_patch_notes_with_openai(example_text, "Valorant")

    if result:
        save_patch_to_file(result, "valorant_openai.json")
        print("\n📄 Sonuç:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("❌ JSON oluşturulamadı.")
