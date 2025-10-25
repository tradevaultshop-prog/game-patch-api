import json
import os
import logging
from dotenv import load_dotenv
from google import genai  

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# GÜNCELLENMİŞ SİSTEM TALİMATI (v3)
SYSTEM_INSTRUCTION = """
Sen bir "Game Patch Note Analyst" (Oyun Yama Notu Analisti) asistanısın.
Görevin, sana verilen ham metni analiz etmek ve KESİNLİKLE JSON formatında bir çıktı üretmektir.
ANA KURALLAR:
1.  Sadece ve sadece JSON döndür. Başka hiçbir metin (açıklama, giriş, "```json" vb.) ekleme.
2.  `target` alanı KISA olmalı (1-3 kelime). Asla tam bir cümle veya uzun bir liste olmamalı.
3.  `details` alanı bir obje olmalı ve `tr` (Türkçe) ve `en` (İngilizce) olmak üzere İKİ anahtar da ZORUNLU olarak içermelidir.
4.  `details.tr` alanı ZORUNLU olarak TÜRKÇE olmalıdır. Kaynak metin İngilizce ise onu çevir.
5.  `details.en` alanı ZORUNLU olarak İNGİLİZCE olmalıdır. Kaynak metin Türkçe ise onu çevir.
6.  `ability` alanı 1-3 kelime olmalı, yoksa "Genel" (TR) / "General" (EN) gibi bir varsayılan KULLANMA. Sadece "Genel" yaz.
"""

def analyze_with_gemini(raw_text: str, game_name: str, send_alert: callable):
    
    # GÜNCELLENMİŞ PROMPT (v3)
    prompt = f"""
    Aşağıdaki oyun yama notu metnini analiz et.
    
    KURALLAR (TEKRAR):
    - `target`: SADECE 1-3 kelimelik ana hedef (örn: "Jett", "Anvil Haritası", "Hortlak Pelerini"). UZUN LİSTE YASAK.
    - `ability`: SADECE 1-3 kelimelik yetenek adı (yoksa "Genel" yaz).
    - `details.tr`: Detayların TÜRKÇE özeti. ÇEVİRİ ZORUNLUDUR.
    - `details.en`: Detayların İNGİLİZCE özeti. ÇEVİRİ ZORUNLUDUR.

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
            "tr": "detayın TÜRKÇE özeti (ÇEVİRİ ZORUNLU)",
            "en": "detayın İNGİLİZCE özeti (ÇEVİRİ ZORUNLU)"
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
          "target": "Atlar ve Yeni Eşyalar",
          "ability": "Genel",
          "details": {{
            "tr": "Oyuna Halılar, Kayışlar, İsim Etiketleri, Saman Balyaları ve Atlar eklendi.",
            "en": "Carpets, leads, name tags, hay bales, and horses were introduced to the game."
          }}
        }}
      ]
    }}

    ---
    ŞİMDİ BU METNİ ANALİZ ET (SADECE JSON DÖNDÜR):

    Metin:
    {raw_text}
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt,
            system_instruction=SYSTEM_INSTRUCTION,
            config=genai.types.GenerateContentConfig(
                # Sadece JSON döndürmesini zorunlu kıl
                response_mime_type="application/json" 
            ),
        )
        
        # Artık '```json' temizliğine gerek yok, çünkü response_mime_type bunu hallediyor.
        content = response.text.strip()
            
        json_data = json.loads(content)
        return json_data

    except Exception as e:
        error_msg = f"❌ Gemini API JSON analizi hatası ({game_name}): {e}\nResponse: {response.text if 'response' in locals() else 'No response'}"
        logging.error(error_msg)
        send_alert(error_msg) 
        return None

