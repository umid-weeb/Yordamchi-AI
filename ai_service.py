"""
ai_service.py — MUSE AI xizmati (Groq LLaMA 3.3 + Whisper)
- [XOTIRA:...] teglari foydalanuvchiga ko'rinmaydi
- Ovoz: O'zbek/Rus/Ingliz auto-detect (Groq Whisper)
- Rejimlar: Umumiy, Ijodiy, Dasturchi, Biznes
"""

import logging
import re
import time
import base64
import io
from typing import List, Dict, Optional, Tuple
from datetime import date

from groq import Groq

logger = logging.getLogger("AIService")

ASOSIY_MODEL  = "llama-3.3-70b-versatile"
ZAXIRA_MODEL  = "llama3-8b-8192"
VISION_MODEL  = "llama-3.2-11b-vision-preview"
WHISPER_MODEL = "whisper-large-v3-turbo"

# Updated Groq client initialization
def _create_groq_client(api_key):
    try:
        return Groq(api_key=api_key)
    except TypeError as e:
        if "proxies" in str(e):
            # Handle older Groq versions
            return Groq(api_key=api_key, version="0.11.0")
        raise

REJIMLAR = {
    "assistant": {
        "nomi":   "Umumiy Yordamchi",
        "emoji":  "🤖",
        "tavsif": "Har qanday savolga aniq javob beraman",
        "prompt": (
            "Siz Yordamchi AI — aqlli va foydali shaxsiy yordamchisiz. "
            "Har qanday savolga aniq, tushunarli va to'liq javob beraman. "
            "Foydalanuvchi qaysi tilda yozsa — o'sha tilda javob beraman. "
            "O'zbek → o'zbekcha, Rus → ruscha, Ingliz → inglizcha. "
            "Javoblar qisqa, aniq va foydali bo'lishiga harakat qilaman."
        ),
    },
    "ijod": {
        "nomi":   "Ijodiy Yozuvchi",
        "emoji":  "✍️",
        "tavsif": "Hikoya, she'r, ssenariy yozadi",
        "prompt": (
            "Siz MUSE AI — professional ijodiy yozuvchisiz. "
            "Hikoyalar, she'rlar, ssenariylar, maqolalar yozasiz. "
            "Ijodiy, original va qiziqarli kontentlar yaratasiz. "
            "Foydalanuvchi tilida javob bering."
        ),
    },
    "dasturlash": {
        "nomi":   "Dasturchi Yordamchi",
        "emoji":  "💻",
        "tavsif": "Kod yozadi, xatolarni tuzatadi",
        "prompt": (
            "Siz MUSE AI — tajribali dasturchi yordamchisiz. "
            "Har qanday dasturlash tilida kod yozasiz, xatolarni tuzatasiz. "
            "Kodni tushuntirish bilan birga bering. "
            "Foydalanuvchi tilida javob bering."
        ),
    },
    "biznes": {
        "nomi":   "Biznes Maslahatchi",
        "emoji":  "💼",
        "tavsif": "Biznes, marketing, brending maslahatlar",
        "prompt": (
            "Siz MUSE AI — professional biznes maslahatchiisiz. "
            "Marketing, brending, startap, moliya bo'yicha amaliy maslahatlar berasiz. "
            "Aniq va strategik fikr yuritasiz. "
            "Foydalanuvchi tilida javob bering."
        ),
    },
    "xamroh_ai": {
        "nomi":   "Xamroh AI",
        "emoji":  "💖",
        "tavsif": "Yaqin do'st bo'lib, yordam beraman",
        "prompt": (
            "Siz Xamroh AI — yaqin do'st bo'lib, yordam beruvchi xushmuomala inson bo'lisiz. "
            "Foydalanuvchi bilan do'st bo'lib, qo'shimcha ma'lumotlar so'rab, samimiy va foydali javoblar berasiz. "
            "Foydalanuvchi tilida javob bering."
        ),
    },
}

XOTIRA_KATEGORIYALARI = ["shaxsiy", "ish", "maqsad", "uslub", "til", "qiziqish"]


def _qayta_urinish(fn, max_urinish=3):
    for urinish in range(max_urinish):
        try:
            return fn()
        except Exception as e:
            xato = str(e)
            rate = any(k in xato for k in ["429", "rate_limit", "rate limit", "RateLimitError"])
            if rate:
                kutish = 15 * (urinish + 1)
                logger.warning(f"Rate limit — {urinish+1}/{max_urinish}, {kutish}s kutilmoqda")
                if urinish < max_urinish - 1:
                    time.sleep(kutish)
                else:
                    raise Exception("⏳ Minutiga so'rovlar limiti tugadi. 1 daqiqa kutib qayta yuboring.")
            else:
                raise


class AIService:
    def __init__(self, api_key: str):
        self.client = _create_groq_client(api_key)
        self.model  = ASOSIY_MODEL
        logger.info(f"Groq AI tayyor: {self.model}")

    def _tizim_prompti(self, rejim: str, xotiralar: List[Dict], ism: str) -> str:
        r = REJIMLAR.get(rejim, REJIMLAR["assistant"])
        bugun = date.today().strftime("%d.%m.%Y")

        xotira_blok = ""
        if xotiralar:
            faktlar = "\n".join(
                f"  - [{x['category'].upper()}] {x['content']}"
                for x in xotiralar[:20]
            )
            xotira_blok = f"\n\n{ism} haqida ma'lumotlar:\n{faktlar}\n"

        return (
            f"{r['prompt']}\n"
            f"{xotira_blok}\n"
            f"Qo'shimcha:\n"
            f"- Ismingiz: MUSE AI. Foydalanuvchi: {ism}. Bugun: {bugun}\n"
            f"- Rejim: {r['nomi']} {r['emoji']}\n"
            f"- Foydalanuvchi tilini aniqlab, o'SHA TILDA javob bering\n"
            f"- Agar foydalanuvchi o'zi haqida muhim ma'lumot bersa, "
            f"javob oxirida FAQAT shu formatda yozing (boshqa hech narsa qo'shmang):\n"
            f"  [XOTIRA:kat=<kategoriya>|qiymat=<bir gap>]\n"
            f"  Kategoriyalar: {', '.join(XOTIRA_KATEGORIYALARI)}\n"
            f"  Bu teg foydalanuvchiga ko'rinmaydi, faqat tizim uchun."
        )

    def _xotira_ajrat(self, matn: str) -> Tuple[str, Optional[Dict]]:
        """[XOTIRA:...] tegni ajratadi va matndan o'chiradi."""
        pattern = r'\[XOTIRA:kat=([^\|]+)\|qiymat=([^\]]+)\]'
        m = re.search(pattern, matn)
        if m:
            # Tegni va atrofidagi bo'sh joylarni o'chiramiz
            toza = re.sub(pattern, "", matn).strip()
            # Oxiridagi b
            # o'sh qatorlarni ham tozalaymiz
            toza = re.sub(r'\n\s*\n\s*$', '', toza).strip()
            return toza, {"category": m.group(1).strip(), "content": m.group(2).strip()}
        return matn, None

    def _yuborish(self, xabarlar: list, model: str = None) -> str:
        m = model or self.model
        def chaqir():
            j = self.client.chat.completions.create(
                model=m, messages=xabarlar,
                max_tokens=2048, temperature=0.8,
            )
            return j.choices[0].message.content.strip()
        try:
            return _qayta_urinish(chaqir)
        except Exception as e:
            if "model" in str(e).lower() or "not found" in str(e).lower():
                logger.warning(f"Zaxira model: {ZAXIRA_MODEL}")
                self.model = ZAXIRA_MODEL
                return _qayta_urinish(lambda: self.client.chat.completions.create(
                    model=ZAXIRA_MODEL, messages=xabarlar,
                    max_tokens=2048, temperature=0.8,
                ).choices[0].message.content.strip())
            raise

    # ── Asosiy suhbat ─────────────────────────────────────────────

    def suhbat(self, xabar: str, tarix: List[Dict],
               rejim: str, xotiralar: List[Dict], ism: str
               ) -> Tuple[str, Optional[Dict]]:
        tizim = self._tizim_prompti(rejim, xotiralar, ism)
        msgs = [{"role": "system", "content": tizim}]
        for t in tarix:
            msgs.append({
                "role": "user" if t["role"] == "user" else "assistant",
                "content": t["content"]
            })
        msgs.append({"role": "user", "content": xabar})
        javob = self._yuborish(msgs)
        return self._xotira_ajrat(javob)

    # ── Rasm tahlili ──────────────────────────────────────────────

    def rasm_tahlil(self, rasm_baytlar: bytes, mime: str,
                    sorov: str, rejim: str,
                    xotiralar: List[Dict], ism: str
                    ) -> Tuple[str, Optional[Dict]]:
        tizim = self._tizim_prompti(rejim, xotiralar, ism)
        savol = sorov or (
            "Bu rasmni batafsil tahlil qiling:\n"
            "- Nimani ko'ryapsiz?\n"
            "- Agar matn bo'lsa — o'qib bering\n"
            "- Agar jadval/grafik bo'lsa — tushuntiring\n"
            "- Fikr va tavsiyalaringiz"
        )
        b64 = base64.b64encode(rasm_baytlar).decode("utf-8")
        data_url = f"data:{mime};base64,{b64}"

        def chaqir():
            try:
                j = self.client.chat.completions.create(
                    model=VISION_MODEL,
                    messages=[
                        {"role": "system", "content": tizim},
                        {"role": "user", "content": [
                            {"type": "image_url", "image_url": {"url": data_url}},
                            {"type": "text", "text": savol},
                        ]},
                    ],
                    max_tokens=1500, temperature=0.7,
                )
                return j.choices[0].message.content.strip()
            except Exception as e:
                if "model" in str(e).lower() and "decommissioned" in str(e).lower():
                    logger.warning(f"Vision model {VISION_MODEL} decommissioned. Using text fallback.")
                    return (
                        "Rasmni ko'rdim, lekin tahlil qilishda muammo bo'ldi.\n"
                        "Iltimos rasm haqida qisqacha tasvirlab bering — "
                        "keyin batafsil javob beraman!"
                    )
                raise

        try:
            javob = _qayta_urinish(chaqir)
        except Exception as e:
            logger.warning(f"Vision xatosi: {e}")
            javob = (
                "Rasmni ko'rdim, lekin tahlil qilishda muammo bo'ldi.\n"
                "Iltimos rasm haqida qisqacha tasvirlab bering — "
                "keyin batafsil javob beraman!"
            )
        return self._xotira_ajrat(javob)

    # ── Ovoz transkriptsiyasi (3 tilda) ──────────────────────────

    def ovoz_transkripsiya_va_javob(self, audio_baytlar: bytes, mime: str,
                                     rejim: str, xotiralar: List[Dict],
                                     ism: str, tarix: List[Dict]
                                     ) -> Tuple[str, str, Optional[Dict]]:
        """
        Groq Whisper large-v3-turbo:
        - O'zbek, Rus, Ingliz tillarini avtomatik aniqlaydi
        - Bepul va juda tez
        """
        try:
            audio_fayl = io.BytesIO(audio_baytlar)
            audio_fayl.name = "ovoz.ogg"

            # language=None → Whisper o'zi tilni aniqlaydi (auto-detect)
            natija = self.client.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=audio_fayl,
                response_format="verbose_json",  # til ma'lumoti ham keladi
            )

            if hasattr(natija, 'text'):
                transkriptsiya = natija.text.strip()
                til = getattr(natija, 'language', 'unknown')
                logger.info(f"Ovoz tili aniqlandi: {til}")
            elif isinstance(natija, str):
                transkriptsiya = natija.strip()
            else:
                transkriptsiya = str(natija).strip()

            if not transkriptsiya:
                transkriptsiya = "[Ovoz aniqlanmadi]"

        except Exception as e:
            logger.error(f"Transkriptsiya xatosi: {e}")
            # Oddiy format bilan qayta urinish
            try:
                audio_fayl2 = io.BytesIO(audio_baytlar)
                audio_fayl2.name = "ovoz.ogg"
                natija2 = self.client.audio.transcriptions.create(
                    model=WHISPER_MODEL,
                    file=audio_fayl2,
                    response_format="text",
                )
                transkriptsiya = natija2.strip() if isinstance(natija2, str) else str(natija2).strip()
            except Exception as e2:
                logger.error(f"Ikkinchi urinish ham xato: {e2}")
                transkriptsiya = "[Ovozni o'qib bo'lmadi]"

        javob, xotira = self.suhbat(transkriptsiya, tarix, rejim, xotiralar, ism)
        return transkriptsiya, javob, xotira

    # ── Video tahlili ─────────────────────────────────────────────

    def video_tahlil(self, video_baytlar: bytes, mime: str,
                     sorov: str, rejim: str,
                     xotiralar: List[Dict], ism: str
                     ) -> Tuple[str, Optional[Dict]]:
        s = sorov or "video"
        javob, xotira = self.suhbat(
            f"Foydalanuvchi video yubordi: '{s}'\n\n"
            f"Video mutaxassisi sifatida:\n"
            f"1. Videoni tahlil qilish uchun 3 ta aniq savol bering\n"
            f"2. '{s}' mavzusida umumiy tavsiyalar bering\n"
            f"3. Video bilan nima qilish mumkinligi haqida g'oyalar\n\n"
            f"Foydalanuvchiga: 'Videongiz haqida qisqacha tasvirlab bering!'",
            [], rejim, xotiralar, ism
        )
        return javob, xotira

    # ── Rasm yaratish prompti ─────────────────────────────────────

    def rasm_yaratish_prompti(self, tavsif: str, rejim: str,
                               xotiralar: List[Dict], ism: str) -> str:
        javob, _ = self.suhbat(
            f"Quyidagi tavsif uchun professional rasm yaratish prompti yozing:\n\n"
            f"Tavsif: {tavsif}\n\n"
            f"Bering:\n"
            f"1. **Inglizcha prompt** (Midjourney/DALL-E uchun, batafsil)\n"
            f"2. **O'zbekcha tushuntirish** (bu prompt qanday rasm beradi)\n"
            f"3. **Midjourney parametrlari** (--ar 16:9 --q 2 --v 6)\n"
            f"4. **2 ta alternativ variant**\n\n"
            f"4K ultra-realistic formatda bo'lsin.",
            [], rejim, xotiralar, ism
        )
        return javob

    # ── Admin tahlili ─────────────────────────────────────────────

    def admin_tahlil(self, foydalanuvchilar: List[Dict]) -> str:
        import json
        msgs = [
            {"role": "system", "content": "Mahsulot tahlilchisisiz. Qisqa va foydali."},
            {"role": "user", "content": (
                f"Telegram bot foydalanuvchi ma'lumotlarini tahlil qilib "
                f"5 ta muhim xulosani emoji bilan bering:\n"
                f"{json.dumps(foydalanuvchilar[:30], indent=2)[:2000]}"
            )},
        ]
        return self._yuborish(msgs)