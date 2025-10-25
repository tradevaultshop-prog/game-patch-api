import json
import os
import logging
from dotenv import load_dotenv
from google import genai  

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# YENİ EKLENDİ: Sistemin genel kurallarını belirleyen bir "system instruction"
# Bu, prompt'un her zaman en üstünde yer alacak ve AI'nin rolünü tanımlayacak.
SYSTEM_INSTRUCTION = """
Sen bir "Game Patch Note Analyst" (Oyun Yama Notu Analisti) asistanısın.
Görevin, sana verilen ham metni analiz etmek ve KESİNLİKLE JSON formatında bir çıktı üretmektir.
Kuralların:
1.  Sadece JSON döndür. Başka hiçbir açıklama, giriş veya son söz ekleme.
2.  `target` alanı KISA olmalı (1-3 kelime). Asla tam bir cümle olmamalı.
3.  `details` alanı bir obje olmalı ve `tr` (Türkçe) ve `en` (İngilizce) olmak üzere İKİ anahtar da içermelidir.
4.  `details.tr` alanı ZORUNLU olarak Türkçe olmalıdır. Metin İngilizce ise onu çevir.
5.  `details.en` alanı ZORUNLU olarak İngilizce olmalıdır. Metin Türkçe ise onu çevir.
"""

def analyze_with_gemini(raw_text: str, game_name: str, send_alert: callable):
    
    # YENİ GÜNCELLENMİŞ PROMPT:
    # Daha net talimatlar ve "target" alanı için bir örnek (few-shot) eklendi.
    prompt = f"""
    Aşağıdaki oyun yama notu metnini analiz et.
    
    KURALLAR:
    - `target`: SADECE 1-3 kelimelik ana hedef (örn: "Jett", "Anvil Haritası", "Hortlak Pelerini").
    - `ability`: SADECE 1-3 kelimelik yetenek adı (yoksa "Genel" yaz).
    - `details`: `tr` ve `en` anahtarlarını İÇERMEK ZORUNDA.
    - `details.tr`: Detayların TÜRKÇE özeti.
    - `details.en`: Detayların İNGİLİZCE özeti.

    JSON FORMATI:
    {{
      "game": "{game_name}",
      "patch_version": "bilinmiyorsa 'unknown'",
      "date": "bilinmiyorsa 'unknown'",
      "changes": [
        {{
          "type": "nerf|buff|new|fix",
          "target": "1-3 kelimelik ana hedef",
          "ability": "1-3 kelimelik yetenek (veya 'Genel')",
          "details": {{
            "tr": "detayın TÜRKÇE özeti",
            "en": "detayın İNGİLİZCE özeti"
          }}
        }}
      ]
    }}

    ÖRNEK METİN:
    "Horse Update: Carpets, leads, name tags, hay bales, and horses were introduced..."
    
    ÖRNEK ÇIKTI (SADECE JSON):
    {{
      "game": "{game_name}",
      "patch_version": "Horse Update",
      "date": "unknown",
      "changes": [
        {{
          "type": "new",
          "target": "Yeni Eşyalar ve Atlar",
          "ability": "Genel",
          "details": {{
            "tr": "Oyuna Halılar, Kayışlar, İsim Etiketleri, Saman Balyaları ve Atlar eklendi.",
            "en": "Carpets, leads, name tags, hay bales, and horses were introduced to the game."
          }}
        }}
      ]
    }}

    ---
    ŞİMDİ BU METNİ ANALİZ ET:

    Metin:
    {raw_text}
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt,
            # YENİ EKLENDİ: Sistem talimatını API çağrısına ekliyoruz
            system_instruction=SYSTEM_INSTRUCTION,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json" 
            ),
        )
        
        content = response.text.strip()
        
        # Temizleme (Bu kısım aynı kalıyor)
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3]
            
        json_data = json.loads(content)
        return json_data

    except Exception as e:
        error_msg = f"❌ Gemini API JSON analizi hatası ({game_name}): {e}\nPrompt: {prompt[:200]}..."
        logging.error(error_msg)
        send_alert(error_msg) 
        return None

