"""
Main entry point for the Group Manager Bot.
Run: python main.py
"""

import asyncio
import logging
import os

from telegram import Update
from telegram.ext import Application, ContextTypes
from telegram.request import HTTPXRequest

from config import BOT_TOKEN
from database import init_db

# ── Modules ──────────────────────────────────────
from modules import help, welcome, spam, moderation, admin, notes, promo

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(app: Application) -> None:
    """Runs after the bot is initialized — set up DB and bot commands."""
    await init_db()
    logger.info("✅ MySQL Database initialized")

    await app.bot.set_my_commands([
        ("start",         "বট শুরু করুন"),
        ("help",          "সাহায্য মেনু"),
        ("settings",      "গ্রুপ সেটিংস কন্ট্রোল প্যানেল"),
        ("rules",         "গ্রুপের নিয়ম দেখুন"),
        ("warn",          "ব্যবহারকারীকে সতর্ক করুন"),
        ("warns",         "ওয়ার্ন তালিকা দেখুন"),
        ("ban",           "ব্যান করুন"),
        ("kick",          "কিক করুন"),
        ("mute",          "মিউট করুন"),
        ("unmute",        "আনমিউট করুন"),
        ("pin",           "মেসেজ পিন করুন"),
        ("unpin",         "পিন সরান"),
        ("lock",          "চ্যাট লক করুন"),
        ("unlock",        "চ্যাট আনলক করুন"),
        ("notes",         "নোট তালিকা"),
        ("adminlist",     "অ্যাডমিন তালিকা"),
        ("id",            "ID দেখুন"),
        ("info",          "ব্যবহারকারীর তথ্য"),
        ("chatinfo",      "গ্রুপের তথ্য"),
    ])
    logger.info("✅ Bot commands registered.")

    # Start the promo loop task when event loop is active
    from modules import promo
    asyncio.create_task(promo.promo_loop(app))
    logger.info("✅ Repeating promotional broadcast task registered in active event loop")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("⚠️ একটি অপ্রত্যাশিত ত্রুটি হয়েছে। অনুগ্রহ করে আবার চেষ্টা করুন।")
        except Exception:
            pass


def main() -> None:
    # Increase timeouts for slow/unstable connections
    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(request)
        .post_init(post_init)
        .build()
    )

    # Register all module handlers (order matters for filters)
    help.register(app)        # /start /help /id etc.
    welcome.register(app)     # new/left member + admin welcome commands
    moderation.register(app)  # warn/ban/kick/mute
    admin.register(app)       # pin/lock/rules/promote
    notes.register(app)       # save/get/notes
    spam.register(app)        # message filter (last — catches all text)

    app.add_error_handler(error_handler)

    logger.info("🚀 Bot is starting...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
