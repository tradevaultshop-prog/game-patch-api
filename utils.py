import json
import os
import logging # <- YENİ: Hata loglaması için eklendi
from dotenv import load_dotenv
from google import genai  

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# send_alert parametresi (önceki güncellemelerden)
def analyze_with_gemini(raw_text: str, game_name: str, send_alert: callable):
    
    # GÜNCELLENDİ: Prompt artık "details" alanı için TR ve EN olmak üzere 
    # iki dil (multi-lang) [cite: 1.1] istiyor.
    prompt = f"""
    Aşağıdaki oyun yama notlarından sadece dengesizlik (nerf/buff), yeni içerik veya önemli değişiklikleri çıkar.
    Sadece geçerli JSON döndür. Hiçbir açıklama ekleme.
    
    ÇOK ÖNEMLİ: Tüm "details" açıklamalarını hem Türkçe ('tr') hem de İngilizce ('en') olarak, 
    aşağıdaki JSON formatında sağla:

    Format:
    {{
      "game": "{game_name}",
      "patch_version": "bilinmiyorsa 'unknown'",
      "date": "bilinmiyorsa 'unknown'",
      "changes": [
        {{
          "type": "nerf|buff|new|fix",
          "target": "karakter/silah/harita/özellik (ÇEVİRME)",
          "ability": "yetenek (varsa, ÇEVİRME)",
          "details": {{
             "tr": "Değişikliğin Türkçe açıklaması",
             "en": "English description of the change"
          }}
        }}
      ]
    }}

    Metin:
    {raw_text}
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", # gemini-2.5-flash veya daha gelişmiş bir model
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json" 
            ),
        )
        
        content = response.text.strip()
        
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
            
        json_data = json.loads(content)
        return json_data

    except Exception as e:
        error_msg = f"❌ Gemini API Hatası ({game_name}): {e}\nYanıt: {response.text if 'response' in locals() else 'Yanıt alınamadı'}"
        logging.error(error_msg)
        send_alert(error_msg) 
        return None
