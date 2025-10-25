import json
import os
import logging
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field, ValidationError # YENİ EKLENDİ
from typing import Dict, List, Literal, Optional # YENİ EKLENDİ

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- YENİ EKLENDİ: Pydantic Modelleri (AI Çıktı Şeması) ---

class PatchDetails(BaseModel):
    # Çevirilerin zorunlu olduğunu belirtiyoruz
    tr: str = Field(..., min_length=5)
    en: str = Field(..., min_length=5)

class Change(BaseModel):
    type: Literal["nerf", "buff", "new", "fix", "other"]
    # Target alanının 1-8 kelime arası olmasını zorunlu kılıyoruz (örn: "Jett Rüzgar Gibi" 3 kelime)
    target: str = Field(..., min_length=2, max_length=80) 
    ability: Optional[str] = "Genel"
    details: PatchDetails

class PatchResult(BaseModel):
    game: str
    patch_version: str
    date: str
    changes: List[Change]

# --- GÜNCELLENDİ: SISTEM TALİMATI (v4) ---
# Kuralları daha da katılaştırıyoruz
SYSTEM_INSTRUCTION = """
Sen bir "Game Patch Note Analyst" (Oyun Yama Notu Analisti) asistanısın.
Görevin, sana verilen ham metni analiz etmek ve KESİNLİKLE JSON formatında bir çıktı üretmektir.
ANA KURALLAR:
1.  Sadece ve sadece JSON döndür. Başka hiçbir metin (açıklama, giriş, "```json" vb.) ekleme.
2.  `target` alanı ÇOK KISA olmalı (1-5 kelime). Örn: "Jett", "Anvil Haritası", "Hortlak Pelerini". ASLA tam bir cümle veya uzun bir liste olmamalı.
3.  `ability` alanı 1-3 kelime olmalı, yoksa "Genel" yaz.
4.  `details` alanı bir obje olmalı ve `tr` (Türkçe) ve `en` (İngilizce) olmak üzere İKİ anahtar da ZORUNLU olarak içermelidir.
5.  `details.tr` alanı ZORUNLU olarak TÜRKÇE olmalıdır. Kaynak metin İngilizce ise onu çevir.
6.  `details.en` alanı ZORUNLU olarak İNGİLİZCE olmalıdır. Kaynak metin Türkçe ise onu çevir.
7.  `type` alanı SADECE şunlardan biri olabilir: "nerf", "buff", "new", "fix", "other".
"""

def analyze_with_gemini(raw_text: str, game_name: str, send_alert: callable):
    
    # GÜNCELLENMİŞ PROMPT (v4) - JSON Formatı Pydantic'e uyumlu hale getirildi
    prompt = f"""
    Aşağıdaki oyun yama notu metnini analiz et.
    
    KURALLAR (TEKRAR):
    - `target`: SADECE 1-5 kelimelik ana hedef (örn: "Jett", "Anvil Haritası"). UZUN LİSTE YASAK.
    - `ability`: SADECE 1-3 kelimelik yetenek adı (yoksa "Genel" yaz).
    - `type`: Sadece "nerf", "buff", "new", "fix", "other" olabilir.
    - `details.tr`: Detayların TÜRKÇE özeti. ÇEVİRİ ZORUNLUDUR.
    - `details.en`: Detayların İNGİLİZCE özeti. ÇEVİRİ ZORUNLUDUR.

    JSON FORMATI:
    {{
      "game": "{game_name}",
      "patch_version": "bilinmiyorsa 'unknown'",
      "date": "bilinmiyorsa 'unknown'",
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
            model="gemini-2.5-flash", # Model adını güncelledim
            contents=prompt,
            system_instruction=SYSTEM_INSTRUCTION,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json" 
            ),
        )
        
        content = response.text.strip()
            
        # --- YENİ EKLENDİ: Pydantic Doğrulaması ---
        try:
            # 1. Ham JSON'u Python dict'ine çevir
            raw_json_data = json.loads(content)
            
            # 2. Pydantic modeline göre doğrula
            # Bu, 'tr', 'en' eksikse veya 'target' çok uzunsa hata fırlatır
            validated_data = PatchResult.parse_obj(raw_json_data)
            
            # 3. Pydantic modelini tekrar standart dict'e çevirerek döndür
            return validated_data.dict()

        except ValidationError as e:
            # Pydantic doğrulaması başarısız oldu (örn: 'tr' anahtarı eksik, 'target' çok uzun)
            error_msg = f"❌ Gemini Pydantic Şema Hatası ({game_name}): AI, kurallara uymayan JSON döndürdü. Hata: {e}\n\nAI Çıktısı:\n{content}"
            logging.error(error_msg)
            send_alert(error_msg) 
            return None
        except json.JSONDecodeError as e:
            # AI, JSON olmayan bir şey döndürdü
            error_msg = f"❌ Gemini JSONDecode Hatası ({game_name}): AI, JSON olmayan bir yanıt döndürdü. Hata: {e}\n\nAI Çıktısı:\n{content}"
            logging.error(error_msg)
            send_alert(error_msg) 
            return None
        # --- Doğrulama Sonu ---

    except Exception as e:
        # API çağrısının kendisi başarısız oldu (kota, bağlantı vb.)
        error_msg = f"❌ Gemini API Çağrı Hatası ({game_name}): {e}\nResponse: {response.text if 'response' in locals() else 'No response'}"
        logging.error(error_msg)
        send_alert(error_msg) 
        return None