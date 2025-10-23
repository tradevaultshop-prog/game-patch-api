# utils.py
import json
import os
from dotenv import load_dotenv
from google import genai  # Yeni kütüphane

load_dotenv()
# Anahtar ismi GEMINI_API_KEY olarak değişti
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Fonksiyon adı Gemini'ye göre güncellendi
def analyze_with_gemini(raw_text: str, game_name: str):
    # Prompt (istek metni) aynı kalabilir.
    prompt = f"""
    Aşağıdaki oyun yama notlarından sadece dengesizlik (nerf/buff), yeni içerik veya önemli değişiklikleri çıkar.
    Sadece geçerli JSON döndür. Hiçbir açıklama ekleme.
    Format:
    {{
      "game": "{game_name}",
      "patch_version": "bilinmiyorsa 'unknown'",
      "date": "bilinmiyorsa 'unknown'",
      "changes": [
        {{
          "type": "nerf|buff|new|fix",
          "target": "karakter/silah/harita/özellik",
          "ability": "yetenek (varsa, yoksa boş bırakma ama anahtar olsun)",
          "details": "açıklama"
        }}
      ]
    }}

    Metin:
    {raw_text}
    """

    try:
        # Gemini API çağrısı ve JSON ayarı
        response = client.models.generate_content(
            model="gemini-2.5-flash",  # Hızlı ve yetenekli model
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                # JSON çıktısını zorunlu kılar
                response_mime_type="application/json" 
            ),
        )
        
        # Yanıt içeriği doğrudan JSON olarak dönecektir
        content = response.text.strip()
        
        # Gemini bazen yine de Markdown (```json) ekleyebilir, temizleyelim.
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3]
            
        # JSON yükleme ve doğrulama
        json_data = json.loads(content)
        return json_data

    except Exception as e:
        # Hata durumunda (JSON bozulması, API hatası vb.) None döner
        print(f"Gemini API Hatası: {e}")
        return None