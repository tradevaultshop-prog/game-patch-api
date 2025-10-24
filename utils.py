import json
import os
from dotenv import load_dotenv
from google import genai  

load_dotenv()
# Anahtar ismi GEMINI_API_KEY olarak değişti
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# YENİ EKLENDİ: send_alert parametresi
def analyze_with_gemini(raw_text: str, game_name: str, send_alert: callable):
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
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json" 
            ),
        )
        
        content = response.text.strip()
        
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3]
            
        json_data = json.loads(content)
        return json_data

    except Exception as e:
        # Hata durumunda (JSON bozulması, API hatası vb.) None döner
        error_msg = f"❌ Gemini API Hatası ({game_name}): {e}"
        logging.error(error_msg)
        send_alert(error_msg) # <-- YENİ EKLENDİ: Hata bildirimi
        return None