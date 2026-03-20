"""config.py — MUSE AI Bot sozlamalari"""

import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    TELEGRAM_TOKEN: str  = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    GROQ_API_KEY: str    = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    DATABASE_URL: str    = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    ADMIN_IDS: List[int] = field(default_factory=lambda: [
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
    ])

    # Kunlik xabar limiti
    FREE_DAILY:  int = 20
    PRO_DAILY:   int = 200
    ELITE_DAILY: int = 99999

    # Kontekst oynasi
    FREE_CTX:  int = 10
    PRO_CTX:   int = 40
    ELITE_CTX: int = 100

    # Xotira slotlari
    FREE_MEM:  int = 15
    PRO_MEM:   int = 100
    ELITE_MEM: int = 500

    # Loyiha slotlari
    FREE_PROJ:  int = 5
    PRO_PROJ:   int = 50
    ELITE_PROJ: int = 300

    # Video hajmi (MB)
    FREE_VIDEO_MB:  int = 15
    PRO_VIDEO_MB:   int = 50
    ELITE_VIDEO_MB: int = 200

    BOT_NAME:    str = "MUSE AI"
    PRO_PRICE:   str = "29,900 so'm/oy"
    ELITE_PRICE: str = "79,900 so'm/oy"

    def validate(self):
        if not self.TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN .env faylida yo'q!")
        if not self.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY .env faylida yo'q! console.groq.com dan oling")
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL .env faylida yo'q!")

    def limits(self, plan: str) -> dict:
        p = plan.lower()
        if p == "pro":
            return dict(daily=self.PRO_DAILY, ctx=self.PRO_CTX,
                        mem=self.PRO_MEM, proj=self.PRO_PROJ, video_mb=self.PRO_VIDEO_MB)
        if p == "elite":
            return dict(daily=self.ELITE_DAILY, ctx=self.ELITE_CTX,
                        mem=self.ELITE_MEM, proj=self.ELITE_PROJ, video_mb=self.ELITE_VIDEO_MB)
        return dict(daily=self.FREE_DAILY, ctx=self.FREE_CTX,
                    mem=self.FREE_MEM, proj=self.FREE_PROJ, video_mb=self.FREE_VIDEO_MB)
