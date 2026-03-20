"""
handlers.py — Yordamchi AI Bot (to'liq o'zbekcha, katta tugmalar)
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, Application
)
from telegram.constants import ChatAction, ParseMode

from config import Config
from database import Database
from ai_service import AIService, REJIMLAR

logger = logging.getLogger("Handlers")


# ── Yordamchi funksiyalar ─────────────────────────────────────────

def res(context):
    cfg: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    if "ai" not in context.bot_data:
        context.bot_data["ai"] = AIService(cfg.GROQ_API_KEY)
    return cfg, db, context.bot_data["ai"]


def ensure(db, update):
    u = update.effective_user
    db.upsert_user(u.id, u.username, u.first_name, u.last_name, u.language_code or "uz")
    return db.get_user(u.id)


def rate_ok(cfg, db, user):
    lim = cfg.limits(user["plan"])
    used = db.get_today_usage(user["user_id"])
    return used < lim["daily"], used, lim["daily"]


def tarif(plan):
    return {"free": "🆓 Bepul", "pro": "⭐ Pro", "elite": "👑 Elite"}.get(plan, plan)


async def yozmoqda(update, context):
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)


def xotira_saqla(db, cfg, user, data):
    if data:
        lim = cfg.limits(user["plan"])
        if db.count_memories(user["user_id"]) < lim["mem"]:
            db.add_memory(user["user_id"], data["content"], data.get("category", "umumiy"), 2)


def asosiy_tugmalar():
    """Ikkinchi rasmdagi kabi katta tugmalar — 2x4 grid."""
    return ReplyKeyboardMarkup([
        ["💎 Premium",        "📊 Statistika"],
        ["🎭 Rejim tanlash",  "🧠 Mening profilim"],
        ["📁 Loyihalarim",    "⚙️ Sozlamalar"],
        ["📖 Yordam",         "🔄 Suhbatni tozalash"],
    ], resize_keyboard=True)


# ── /start ────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg, db, _ = res(context)
    user = ensure(db, update)
    ism = update.effective_user.first_name or "Do'stim"

    matn = (
        f"👋 Salom, *{ism}*!\n\n"
        f"Men *Yordamchi AI* — sizning aqlli shaxsiy yordamchingizman.\n\n"
        f"🤖 *Nima qila olaman:*\n"
        f"• Har qanday savolga aniq javob beraman\n"
        f"• 📸 Rasmlarni tahlil qilaman\n"
        f"• 🎥 Videolarni ko'rib chiqaman\n"
        f"• 🎙️ Ovozli xabarlarni tushunaman\n"
        f"• ✍️ Matnlar, hikoyalar, kodlar yozaman\n"
        f"• 🎨 Rasm yaratish uchun prompt beraman\n"
        f"• 🧠 Siz haqingizda eslab qolaman\n\n"
        f"Sizning tarifingiz: {tarif(user['plan'])}\n\n"
        f"_Menga xabar yozing yoki rasm, ovoz yuboring!_"
    )

    await update.message.reply_text(
        matn,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=asosiy_tugmalar()
    )


# ── /help ─────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg, db, _ = res(context)
    ensure(db, update)
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg: return

    matn = (
        "📖 *Yordamchi AI — Qo'llanma*\n\n"
        "*Asosiy imkoniyatlar:*\n"
        "• Matn yozing → AI javob beradi\n"
        "• 📸 Rasm yuboring → tahlil qiladi\n"
        "• 🎥 Video yuboring → ko'rib chiqadi\n"
        "• 🎙️ Ovoz yuboring → eshitib javob beradi\n\n"
        "*Maxsus so'rovlar:*\n"
        "• `Rasm yarat: [tavsif]` → prompt beradi\n"
        "• `Hikoya yoz: [mavzu]` → hikoya yozadi\n"
        "• `Tarjima qil: [matn]` → tarjima qiladi\n"
        "• `Kod yoz: [vazifa]` → kod yozadi\n\n"
        "*Rejimlar:*\n"
        "• 🤖 Umumiy — har qanday savol\n"
        "• ✍️ Ijodiy — hikoya, she'r, ssenariy\n"
        "• 💻 Dasturchi — kod, debug\n"
        "• 💼 Biznes — marketing, brending\n\n"
        "_Pastdagi tugmalardan foydalaning!_"
    )
    await msg.reply_text(matn, parse_mode=ParseMode.MARKDOWN, reply_markup=asosiy_tugmalar())


# ── /mode ─────────────────────────────────────────────────────────

async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg, db, _ = res(context)
    ensure(db, update)
    user = db.get_user(update.effective_user.id)
    joriy = user.get("ai_mode", "assistant")
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg: return

    tugmalar = []
    for k, r in REJIMLAR.items():
        belgi = "✅ " if k == joriy else ""
        tugmalar.append([InlineKeyboardButton(
            f"{belgi}{r['emoji']} {r['nomi']}",
            callback_data=f"rejim:{k}"
        )])

    await msg.reply_text(
        "🎭 *Rejim tanlang:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(tugmalar)
    )


# ── /memory ───────────────────────────────────────────────────────

async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg, db, _ = res(context)
    ensure(db, update)
    uid = update.effective_user.id
    xotiralar = db.get_memories(uid)
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg: return

    if not xotiralar:
        await msg.reply_text(
            "🧠 *Profilingiz bo'sh*\n\n"
            "Men suhbat davomida siz haqingizda avtomatik eslab qolaman.\n\n"
            "Masalan: _'Men dasturchi bo'lib ishlayman'_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=asosiy_tugmalar()
        )
        return

    qatorlar = ["🧠 *Mening Profilim:*\n"]
    for x in xotiralar:
        qatorlar.append(f"• [{x['category'].upper()}] {x['content']}")
    qatorlar.append(f"\n_{len(xotiralar)} ta ma'lumot saqlangan_")

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🗑️ Hammasini o'chirish", callback_data="xotira:tozalash_tasdiq")
    ]])
    await msg.reply_text("\n".join(qatorlar), parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


# ── /projects ─────────────────────────────────────────────────────

async def cmd_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg, db, _ = res(context)
    ensure(db, update)
    uid = update.effective_user.id
    loyihalar = db.get_projects(uid)
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg: return

    if not loyihalar:
        await msg.reply_text(
            "📁 *Loyihalar yo'q*\n\n"
            "Katta javob kelganda *💾 Saqlash* tugmasini bosing.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=asosiy_tugmalar()
        )
        return

    qatorlar = ["📁 *Mening Loyihalarim:*\n"]
    for l in loyihalar[:10]:
        sana = l["created_at"][:10]
        ko = l["content"][:50].replace("\n", " ") + "..."
        qatorlar.append(f"📄 *{l['title']}* _{sana}_\n   _{ko}_\n")

    tugmalar = [[InlineKeyboardButton(
        f"📂 {l['title'][:25]}", callback_data=f"loyiha:kor:{l['id']}"
    )] for l in loyihalar[:6]]

    await msg.reply_text(
        "\n".join(qatorlar),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(tugmalar)
    )


# ── /stats ────────────────────────────────────────────────────────

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg, db, _ = res(context)
    user = ensure(db, update)
    uid = user["user_id"]
    lim = cfg.limits(user["plan"])
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg: return

    rejim = REJIMLAR.get(user.get("ai_mode", "assistant"), REJIMLAR["assistant"])

    matn = (
        f"📊 *Statistika*\n\n"
        f"👤 Tarif: {tarif(user['plan'])}\n"
        f"🎭 Rejim: {rejim['emoji']} {rejim['nomi']}\n"
        f"📅 A'zo: {user['joined_at'][:10]}\n\n"
        f"📈 *Foydalanish:*\n"
        f"• Bugun: {db.get_today_usage(uid)}/{lim['daily']} xabar\n"
        f"• Jami: {user['total_messages']} xabar\n"
        f"• Xotira: {db.count_memories(uid)}/{lim['mem']} ta\n"
        f"• Loyihalar: {db.count_projects(uid)}/{lim['proj']} ta"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("💎 Tarifni yaxshilash", callback_data="tarif:pro")
    ]])
    await msg.reply_text(matn, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


# ── /plan ─────────────────────────────────────────────────────────

async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg, db, _ = res(context)
    ensure(db, update)
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg: return

    matn = (
        f"💎 *Tariflar*\n\n"
        f"🆓 *Bepul*\n"
        f"• {cfg.FREE_DAILY} xabar/kun • {cfg.FREE_MEM} xotira • {cfg.FREE_PROJ} loyiha\n\n"
        f"⭐ *Pro — {cfg.PRO_PRICE}*\n"
        f"• {cfg.PRO_DAILY} xabar/kun • {cfg.PRO_MEM} xotira • {cfg.PRO_PROJ} loyiha\n\n"
        f"👑 *Elite — {cfg.ELITE_PRICE}*\n"
        f"• Cheksiz xabarlar • {cfg.ELITE_MEM} xotira • {cfg.ELITE_PROJ} loyiha"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Pro olish", callback_data="tarif:pro"),
         InlineKeyboardButton("👑 Elite olish", callback_data="tarif:elite")],
        [InlineKeyboardButton("📩 Admin bilan bog'lanish", callback_data="tarif:boglanish")],
    ])
    await msg.reply_text(matn, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


# ── /settings ─────────────────────────────────────────────────────

async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg, db, _ = res(context)
    ensure(db, update)
    uid = update.effective_user.id
    s = db.get_user_settings(uid)
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg: return

    def belgi(k, d=True): return "✅" if s.get(k, d) else "❌"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"{belgi('transkriptsiya')} Ovoz transkriptsiyasi",
            callback_data="sozlama:transkriptsiya")],
        [InlineKeyboardButton(
            f"{belgi('avtosaqla')} Katta javoblarni avtosaqlash",
            callback_data="sozlama:avtosaqla")],
    ])
    await msg.reply_text("⚙️ *Sozlamalar*", parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


# ── /reset ────────────────────────────────────────────────────────

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg, db, _ = res(context)
    ensure(db, update)
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg: return

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Ha", callback_data="reset:ha"),
        InlineKeyboardButton("❌ Yo'q", callback_data="reset:yoq"),
    ]])
    await msg.reply_text(
        "🔄 Suhbat tarixini tozalashni xohlaysizmi?",
        reply_markup=kb
    )


# ── /admin ────────────────────────────────────────────────────────

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg, db, _ = res(context)
    uid = update.effective_user.id
    if uid not in cfg.ADMIN_IDS:
        await update.message.reply_text("❌ Ruxsat yo'q.")
        return
    ensure(db, update)
    stats = db.get_latest_analytics()
    users = db.get_all_users()

    matn = (
        f"🛡️ *Admin Panel*\n\n"
        f"👥 Jami: {stats.get('total_users', len(users))}\n"
        f"🟢 Bugun faol: {stats.get('active_today', '?')}\n"
        f"💬 Xabarlar: {stats.get('total_messages', '?')}\n"
        f"🆓 {stats.get('free_users','?')} | ⭐ {stats.get('pro_users','?')} | 👑 {stats.get('elite_users','?')}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Xabar yuborish", callback_data="admin:xabar"),
         InlineKeyboardButton("👥 Ro'yxat",        callback_data="admin:royxat")],
        [InlineKeyboardButton("🤖 AI Tahlil",      callback_data="admin:tahlil"),
         InlineKeyboardButton("📊 Snapshot",        callback_data="admin:snapshot")],
        [InlineKeyboardButton("👑 Pro berish",      callback_data="admin:pro"),
         InlineKeyboardButton("🚫 Ban",             callback_data="admin:ban")],
    ])
    await update.message.reply_text(matn, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


# ── REJIMNI MATNDAN ANIQLASH ──────────────────────────────────────

def rejim_aniqlash(matn: str) -> str | None:
    """Foydalanuvchi yozganidan rejimni aniqlaydi."""
    m = matn.lower()
    if any(w in m for w in ["kod yoz", "dastur", "python", "javascript", "debug", "xato tuzat"]):
        return "dasturlash"
    if any(w in m for w in ["hikoya", "she'r", "sheir", "ssenariy", "ijod", "yoz matn"]):
        return "ijod"
    if any(w in m for w in ["biznes", "marketing", "brending", "startap", "reklama"]):
        return "biznes"
    if any(w in m for w in ["tarjima", "translate", "inglizcha", "ruscha", "o'zbekcha"]):
        return "tarjimon"
    return None


# ── ASOSIY MATN HANDLERI ──────────────────────────────────────────

async def handle_matn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg, db, ai = res(context)
    user = ensure(db, update)
    uid = user["user_id"]
    matn = update.message.text.strip()

    if user["is_banned"]:
        await update.message.reply_text("🚫 Hisobingiz bloklangan.")
        return

    # Tugma bosishlari
    if matn == "💎 Premium":
        await cmd_plan(update, context); return
    if matn == "📊 Statistika":
        await cmd_stats(update, context); return
    if matn == "🎭 Rejim tanlash":
        await cmd_mode(update, context); return
    if matn == "🧠 Mening profilim":
        await cmd_memory(update, context); return
    if matn == "📁 Loyihalarim":
        await cmd_projects(update, context); return
    if matn == "⚙️ Sozlamalar":
        await cmd_settings(update, context); return
    if matn == "📖 Yordam":
        await cmd_help(update, context); return
    if matn == "🔄 Suhbatni tozalash":
        await cmd_reset(update, context); return

    ruxsat, used, lim = rate_ok(cfg, db, user)
    if not ruxsat:
        await update.message.reply_text(
            f"⚠️ Kunlik limit tugadi ({used}/{lim}).\n💎 Tarifni yaxshilash: /plan"
        )
        return

    # Admin holatlari
    if uid in cfg.ADMIN_IDS:
        if await admin_matn_holati(update, context, matn, cfg, db, ai):
            return

    # Loyiha nomi kutilmoqda
    if context.user_data.get("loyiha_nom"):
        await loyiha_nom_saqla(update, context, matn, user, cfg, db)
        return

    # Rasm yaratish
    if any(matn.lower().startswith(p) for p in ["rasm yarat:", "rasm chiz:", "draw:"]):
        await rasm_prompt(update, context, matn, user, cfg, db, ai)
        return

    # Rejimni avtomatik aniqlash
    auto_rejim = rejim_aniqlash(matn)
    rejim = auto_rejim or user.get("ai_mode", "assistant")

    await yozmoqda(update, context)
    lim_data = cfg.limits(user["plan"])
    tarix = db.get_history(uid, limit=lim_data["ctx"])
    xotiralar = db.get_memories(uid, limit=20)
    ism = update.effective_user.first_name or "Foydalanuvchi"

    try:
        javob, xotira_data = ai.suhbat(matn, tarix, rejim, xotiralar, ism)
    except Exception as e:
        logger.error(f"Suhbat xatosi: {e}")
        await update.message.reply_text(f"⚠️ {str(e)[:200]}")
        return

    db.add_message(uid, "user", matn)
    db.add_message(uid, "model", javob)
    db.increment_usage(uid)
    xotira_saqla(db, cfg, user, xotira_data)

    settings = db.get_user_settings(uid)
    if len(javob) > 500 and settings.get("avtosaqla", True):
        context.user_data["oxirgi_javob"] = javob
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("💾 Loyiha sifatida saqlash", callback_data="loyiha:saqla")
        ]])
        await update.message.reply_text(javob, reply_markup=kb)
    else:
        await update.message.reply_text(javob)


async def rasm_prompt(update, context, matn, user, cfg, db, ai):
    await yozmoqda(update, context)
    tavsif = matn.split(":", 1)[1].strip() if ":" in matn else matn
    xotiralar = db.get_memories(user["user_id"])
    rejim = user.get("ai_mode", "assistant")
    ism = update.effective_user.first_name or "Foydalanuvchi"
    try:
        javob = ai.rasm_yaratish_prompti(tavsif, rejim, xotiralar, ism)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Xato: {str(e)[:200]}")
        return
    db.increment_usage(user["user_id"])
    context.user_data["oxirgi_javob"] = javob
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("💾 Saqlash", callback_data="loyiha:saqla")]])
    await update.message.reply_text(f"🎨 *Rasm prompti:*\n\n{javob}", parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


# ── RASM ─────────────────────────────────────────────────────────

async def handle_rasm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg, db, ai = res(context)
    user = ensure(db, update)
    uid = user["user_id"]
    if user["is_banned"]: return
    ruxsat, u, l = rate_ok(cfg, db, user)
    if not ruxsat:
        await update.message.reply_text(f"⚠️ Limit: {u}/{l}. /plan"); return

    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_PHOTO)
    rasm = update.message.photo[-1]
    fayl = await context.bot.get_file(rasm.file_id)
    baytlar = bytes(await fayl.download_as_bytearray())
    caption = update.message.caption or ""
    xotiralar = db.get_memories(uid)
    rejim = user.get("ai_mode", "assistant")
    ism = update.effective_user.first_name or "Foydalanuvchi"

    try:
        javob, xd = ai.rasm_tahlil(baytlar, "image/jpeg", caption, rejim, xotiralar, ism)
    except Exception as e:
        await update.message.reply_text("⚠️ Rasmni tahlil qilib bo'lmadi."); return

    db.add_message(uid, "user", f"[RASM]{': '+caption if caption else ''}", "rasm")
    db.add_message(uid, "model", javob)
    db.increment_usage(uid)
    xotira_saqla(db, cfg, user, xd)
    context.user_data["oxirgi_javob"] = javob
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("💾 Saqlash", callback_data="loyiha:saqla")]])
    await update.message.reply_text(javob, reply_markup=kb)


# ── VIDEO ─────────────────────────────────────────────────────────

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg, db, ai = res(context)
    user = ensure(db, update)
    uid = user["user_id"]
    if user["is_banned"]: return
    ruxsat, u, l = rate_ok(cfg, db, user)
    if not ruxsat:
        await update.message.reply_text(f"⚠️ Limit: {u}/{l}. /plan"); return

    video = update.message.video or update.message.document
    lim_data = cfg.limits(user["plan"])
    if (getattr(video, "file_size", 0) or 0) > lim_data["video_mb"] * 1024 * 1024:
        await update.message.reply_text(f"⚠️ Video juda katta. Limit: {lim_data['video_mb']}MB"); return

    await update.message.reply_text("🎥 Video tahlil qilinmoqda...")
    fayl = await context.bot.get_file(video.file_id)
    baytlar = bytes(await fayl.download_as_bytearray())
    caption = update.message.caption or ""
    xotiralar = db.get_memories(uid)
    rejim = user.get("ai_mode", "assistant")
    ism = update.effective_user.first_name or "Foydalanuvchi"

    try:
        javob, xd = ai.video_tahlil(baytlar, getattr(video, "mime_type", "video/mp4") or "video/mp4", caption, rejim, xotiralar, ism)
    except Exception as e:
        await update.message.reply_text("⚠️ Videoni tahlil qilib bo'lmadi."); return

    db.add_message(uid, "user", f"[VIDEO]", "video")
    db.add_message(uid, "model", javob)
    db.increment_usage(uid)
    xotira_saqla(db, cfg, user, xd)
    context.user_data["oxirgi_javob"] = javob
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("💾 Saqlash", callback_data="loyiha:saqla")]])
    await update.message.reply_text(javob, reply_markup=kb)


# ── OVOZ ─────────────────────────────────────────────────────────

async def handle_ovoz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg, db, ai = res(context)
    user = ensure(db, update)
    uid = user["user_id"]
    if user["is_banned"]: return
    ruxsat, u, l = rate_ok(cfg, db, user)
    if not ruxsat:
        await update.message.reply_text(f"⚠️ Limit: {u}/{l}. /plan"); return

    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.RECORD_VOICE)
    ovoz = update.message.voice or update.message.audio
    fayl = await context.bot.get_file(ovoz.file_id)
    baytlar = bytes(await fayl.download_as_bytearray())
    lim_data = cfg.limits(user["plan"])
    tarix = db.get_history(uid, limit=lim_data["ctx"])
    xotiralar = db.get_memories(uid)
    rejim = user.get("ai_mode", "assistant")
    ism = update.effective_user.first_name or "Foydalanuvchi"
    settings = db.get_user_settings(uid)

    try:
        transkriptsiya, javob, xd = ai.ovoz_transkripsiya_va_javob(
            baytlar, "audio/ogg", rejim, xotiralar, ism, tarix
        )
    except Exception as e:
        logger.error(f"Ovoz xatosi: {e}")
        await update.message.reply_text("⚠️ Ovozni qayta ishlashda xato. Qayta urinib ko'ring.")
        return

    db.add_message(uid, "user", transkriptsiya, "ovoz")
    db.add_message(uid, "model", javob)
    db.increment_usage(uid)
    xotira_saqla(db, cfg, user, xd)

    korsatish = settings.get("transkriptsiya", True)
    tolik = f"🎙️ _{transkriptsiya}_\n\n{javob}" if korsatish else javob
    await update.message.reply_text(tolik, parse_mode=ParseMode.MARKDOWN)


# ── HUJJAT ────────────────────────────────────────────────────────

async def handle_hujjat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg, db, ai = res(context)
    user = ensure(db, update)
    uid = user["user_id"]
    if user["is_banned"]: return
    ruxsat, u, l = rate_ok(cfg, db, user)
    if not ruxsat:
        await update.message.reply_text(f"⚠️ Limit: {u}/{l}"); return

    hujjat = update.message.document
    mime = hujjat.mime_type or ""
    caption = update.message.caption or ""
    xotiralar = db.get_memories(uid)
    rejim = user.get("ai_mode", "assistant")
    ism = update.effective_user.first_name or "Foydalanuvchi"

    if mime.startswith("image/"):
        fayl = await context.bot.get_file(hujjat.file_id)
        baytlar = bytes(await fayl.download_as_bytearray())
        try:
            javob, xd = ai.rasm_tahlil(baytlar, mime, caption, rejim, xotiralar, ism)
        except:
            await update.message.reply_text("⚠️ Rasmni tahlil qilib bo'lmadi."); return
        db.add_message(uid, "user", "[RASM_HUJJAT]", "rasm")
        db.add_message(uid, "model", javob)
        db.increment_usage(uid)
        await update.message.reply_text(javob)
    elif mime.startswith("video/"):
        lim_data = cfg.limits(user["plan"])
        if (hujjat.file_size or 0) > lim_data["video_mb"] * 1024 * 1024:
            await update.message.reply_text(f"⚠️ Juda katta. Limit: {lim_data['video_mb']}MB"); return
        await update.message.reply_text("🎥 Video tahlil qilinmoqda...")
        fayl = await context.bot.get_file(hujjat.file_id)
        baytlar = bytes(await fayl.download_as_bytearray())
        try:
            javob, xd = ai.video_tahlil(baytlar, mime, caption, rejim, xotiralar, ism)
        except:
            await update.message.reply_text("⚠️ Videoni tahlil qilib bo'lmadi."); return
        db.add_message(uid, "user", "[VIDEO_HUJJAT]", "video")
        db.add_message(uid, "model", javob)
        db.increment_usage(uid)
        await update.message.reply_text(javob)
    else:
        await update.message.reply_text(
            f"📄 *{hujjat.file_name}* qabul qilindi.\n\n"
            "Matnli fayllar uchun: matnni nusxa olib yuboring.",
            parse_mode=ParseMode.MARKDOWN
        )


# ── CALLBACK ──────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cfg, db, ai = res(context)
    uid = q.from_user.id
    user = ensure(db, update)
    data = q.data

    if data.startswith("rejim:"):
        kalit = data.split(":")[1]
        if kalit in REJIMLAR:
            db.update_user(uid, ai_mode=kalit)
            r = REJIMLAR[kalit]
            await q.edit_message_text(
                f"✅ *{r['emoji']} {r['nomi']}* rejimi tanlandi!\n\n_{r['tavsif']}_",
                parse_mode=ParseMode.MARKDOWN
            )

    elif data == "reset:ha":
        db.clear_history(uid)
        await q.edit_message_text("✅ Suhbat tarixi tozalandi!")
    elif data == "reset:yoq":
        await q.edit_message_text("❌ Bekor qilindi.")

    elif data == "xotira:tozalash_tasdiq":
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🗑️ Ha, o'chir", callback_data="xotira:tozala"),
            InlineKeyboardButton("❌ Yo'q",        callback_data="xotira:bekor"),
        ]])
        await q.edit_message_text("⚠️ Barcha xotiralarni o'chirishni tasdiqlaysizmi?", reply_markup=kb)
    elif data == "xotira:tozala":
        db.clear_memories(uid)
        await q.edit_message_text("🧠 Xotiralar o'chirildi.")
    elif data == "xotira:bekor":
        await q.edit_message_text("❌ Bekor qilindi.")

    elif data == "loyiha:saqla":
        oxirgi = context.user_data.get("oxirgi_javob", "")
        if not oxirgi:
            await q.answer("Saqlanadigan kontent yo'q!", show_alert=True); return
        context.user_data["loyiha_nom"] = True
        await q.message.reply_text("💾 Loyiha nomini kiriting:")

    elif data.startswith("loyiha:kor:"):
        lid = int(data.split(":")[2])
        loyiha = db.get_project(lid, uid)
        if not loyiha:
            await q.answer("Topilmadi!", show_alert=True); return
        ko = loyiha["content"][:800]
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🗑️ O'chirish", callback_data=f"loyiha:ochir:{lid}")
        ]])
        await q.message.reply_text(
            f"📁 *{loyiha['title']}*\n\n{ko}{'...' if len(loyiha['content']) > 800 else ''}",
            parse_mode=ParseMode.MARKDOWN, reply_markup=kb
        )

    elif data.startswith("loyiha:ochir:"):
        lid = int(data.split(":")[2])
        db.delete_project(lid, uid)
        await q.edit_message_text("🗑️ Loyiha o'chirildi.")

    elif data.startswith("sozlama:"):
        kalit = data.split(":")[1]
        joriy = db.get_user_settings(uid).get(kalit, True)
        db.set_user_setting(uid, kalit, not joriy)
        holat = "yoqildi ✅" if not joriy else "o'chirildi ❌"
        await q.edit_message_text(f"⚙️ *{kalit}* — {holat}", parse_mode=ParseMode.MARKDOWN)

    elif data in ("tarif:pro", "tarif:elite"):
        t = data.split(":")[1].upper()
        await q.edit_message_text(
            f"💳 *{t} tarif:*\n\n1. Admin bilan bog'laning\n2. To'lovni amalga oshiring\n3. 24 soat ichida faollashadi\n\nAdmin: @admin_username",
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "tarif:boglanish":
        await q.edit_message_text("📩 Admin: @admin_username")

    elif data.startswith("admin:") and uid in cfg.ADMIN_IDS:
        await admin_callback(q, context, data, cfg, db, ai)


async def admin_callback(q, context, data, cfg, db, ai):
    harakat = data.split(":")[1]
    if harakat == "snapshot":
        db.snapshot_analytics()
        s = db.get_latest_analytics()
        await q.edit_message_text(f"📊 Snapshot!\nFoydalanuvchilar: {s.get('total_users')}\nFaol: {s.get('active_today')}\nXabarlar: {s.get('total_messages')}")
    elif harakat == "royxat":
        users = db.get_all_users()[:15]
        q2 = ["👥 *Foydalanuvchilar:*\n"]
        for u in users:
            n = u.get("first_name") or u.get("username") or str(u["user_id"])
            q2.append(f"• {n} | {tarif(u['plan'])} | {u['total_messages']} xabar")
        await q.edit_message_text("\n".join(q2), parse_mode=ParseMode.MARKDOWN)
    elif harakat == "tahlil":
        users = db.get_all_users()
        xulosa = ai.admin_tahlil([{"id": u["user_id"], "tarif": u["plan"], "xabarlar": u["total_messages"]} for u in users])
        await q.edit_message_text(f"🤖 *AI Tahlil:*\n\n{xulosa}", parse_mode=ParseMode.MARKDOWN)
    elif harakat == "xabar":
        context.user_data["admin_holat"] = "xabar"
        await q.edit_message_text("📢 Xabaringizni yozing:")
    elif harakat == "pro":
        context.user_data["admin_holat"] = "pro"
        await q.edit_message_text("Pro berish uchun user ID yozing:")
    elif harakat == "ban":
        context.user_data["admin_holat"] = "ban"
        await q.edit_message_text("Ban qilish uchun user ID yozing:")


async def admin_matn_holati(update, context, matn, cfg, db, ai) -> bool:
    uid = update.effective_user.id
    holat = context.user_data.get("admin_holat")
    if not holat: return False
    context.user_data.pop("admin_holat")

    if holat == "xabar":
        users = db.get_all_users()
        yuborildi = 0
        for u in users:
            try:
                await context.bot.send_message(u["user_id"], f"📢 {matn}")
                yuborildi += 1
            except: pass
        db.log_broadcast(uid, matn, yuborildi)
        await update.message.reply_text(f"✅ {yuborildi} ta foydalanuvchiga yuborildi.")
        return True
    if holat == "pro":
        try:
            db.update_user(int(matn), plan="pro")
            await update.message.reply_text(f"✅ {matn} ga Pro berildi.")
        except: await update.message.reply_text("❌ Noto'g'ri ID.")
        return True
    if holat == "ban":
        try:
            db.ban_user(int(matn))
            await update.message.reply_text(f"🚫 {matn} bloklandi.")
        except: await update.message.reply_text("❌ Noto'g'ri ID.")
        return True
    return False


async def loyiha_nom_saqla(update, context, matn, user, cfg, db):
    context.user_data.pop("loyiha_nom", None)
    uid = user["user_id"]
    oxirgi = context.user_data.get("oxirgi_javob", "")
    lim = cfg.limits(user["plan"])
    if db.count_projects(uid) >= lim["proj"]:
        await update.message.reply_text(f"⚠️ Limit ({lim['proj']}). Eski loyihalarni o'chiring.")
        return
    lid = db.save_project(uid, matn, oxirgi)
    await update.message.reply_text(
        f"✅ Loyiha saqlandi!\n\n📁 *{matn}* (ID: {lid})\n\n/projects",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=asosiy_tugmalar()
    )


async def handle_barcha_matn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg, db, ai = res(context)
    uid = update.effective_user.id

    if context.user_data.get("loyiha_nom"):
        user = db.get_user(uid) or ensure(db, update)
        await loyiha_nom_saqla(update, context, update.message.text.strip(), user, cfg, db)
        return
    if uid in cfg.ADMIN_IDS:
        if await admin_matn_holati(update, context, update.message.text.strip(), cfg, db, ai):
            return
    await handle_matn(update, context)


def register_handlers(app: Application):
    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("mode",     cmd_mode))
    app.add_handler(CommandHandler("memory",   cmd_memory))
    app.add_handler(CommandHandler("projects", cmd_projects))
    app.add_handler(CommandHandler("stats",    cmd_stats))
    app.add_handler(CommandHandler("plan",     cmd_plan))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("reset",    cmd_reset))
    app.add_handler(CommandHandler("admin",    cmd_admin))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_barcha_matn))
    app.add_handler(MessageHandler(filters.PHOTO, handle_rasm))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_ovoz))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_hujjat))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Barcha handlerlar ro'yxatga olindi.")