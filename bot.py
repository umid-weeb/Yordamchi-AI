"""
MUSE AI Bot — To'liq O'zbekcha AI yordamchi
Groq (LLaMA 3.3) + Supabase PostgreSQL
"""

import logging
import sys
from telegram.ext import Application
from telegram import BotCommand
from config import Config
from database import Database
from handlers import register_handlers
from scheduler import setup_scheduler

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("muse_bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("MuseBot")


async def post_init(application: Application) -> None:
    commands = [
        BotCommand("start",    "🚀 Botni boshlash"),
        BotCommand("help",     "📖 Yordam"),
        BotCommand("mode",     "🎭 Rejimni o'zgartirish"),
        BotCommand("memory",   "🧠 Mening profilim"),
        BotCommand("projects", "📁 Mening loyihalarim"),
        BotCommand("stats",    "📊 Statistika"),
        BotCommand("plan",     "💎 Tariflar"),
        BotCommand("settings", "⚙️ Sozlamalar"),
        BotCommand("reset",    "🔄 Suhbatni tozalash"),
        BotCommand("admin",    "🛡️ Admin panel"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Buyruqlar ro'yxatga olindi.")


def main():
    cfg = Config()
    cfg.validate()

    db = Database(cfg.DATABASE_URL)
    db.init()

    app = (
        Application.builder()
        .token(cfg.TELEGRAM_TOKEN)
        .post_init(post_init)
        .concurrent_updates(True)
        .build()
    )

    app.bot_data["config"] = cfg
    app.bot_data["db"] = db

    register_handlers(app)
    setup_scheduler(app)

    logger.info("🚀 Yordamchi AI Bot ishga tushdi!")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
