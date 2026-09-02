"""
Main entry point for the Group Manager Bot.
Run: python main.py
"""

import asyncio
import logging
import os

from telegram import Update, BotCommand, BotCommandScopeDefault, BotCommandScopeAllChatAdministrators
from telegram.ext import Application, ContextTypes
from telegram.request import HTTPXRequest

from config import BOT_TOKEN
from database import init_db

# ── Modules ──────────────────────────────────────
from modules import help, welcome, spam, moderation, admin, notes, promo, tagall

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(app: Application) -> None:
    """Runs after the bot is initialized — set up DB and bot commands."""
    await init_db()
    logger.info("✅ MySQL Database initialized")

    # 1. Commands for general members (সাধারণ সদস্যদের জন্য মেনু)
    user_commands = [
        BotCommand("start",         "বট শুরু করুন"),
        BotCommand("help",          "সাহায্য মেনু"),
        BotCommand("rules",         "গ্রুপের নিয়ম দেখুন"),
        BotCommand("notes",         "নোট তালিকা"),
        BotCommand("adminlist",     "অ্যাডমিন তালিকা"),
        BotCommand("id",            "ID দেখুন"),
        BotCommand("info",          "ব্যবহারকারীর তথ্য"),
        BotCommand("chatinfo",      "গ্রুপের তথ্য"),
    ]
    await app.bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())

    # 2. Commands for group administrators (শুধুমাত্র অ্যাডমিনদের জন্য মেনু)
    admin_commands = [
        BotCommand("settings",      "গ্রুপ সেটিংস কন্ট্রোল প্যানেল"),
        BotCommand("panel",         "মডারেশন ও কন্ট্রোল প্যানেল"),
        BotCommand("tagall",        "সবাইকে মেনশন করুন (/all)"),
        BotCommand("cancel",        "মেনশন থামান (/tagstop)"),
        BotCommand("warn",          "সতর্ক করুন"),
        BotCommand("warns",         "ওয়ার্ন তালিকা দেখুন"),
        BotCommand("ban",           "ব্যান করুন"),
        BotCommand("kick",          "কিক করুন"),
        BotCommand("mute",          "মিউট করুন"),
        BotCommand("unmute",        "আনমিউট করুন"),
        BotCommand("pin",           "মেসেজ পিন করুন"),
        BotCommand("unpin",         "পিন সরান"),
        BotCommand("lock",          "চ্যাট লক করুন"),
        BotCommand("unlock",        "চ্যাট আনলক করুন"),
        BotCommand("addadmin",      "গ্রুপ অ্যাডমিন বানান (/promote)"),
        BotCommand("demote",        "গ্রুপ অ্যাডমিন সরান"),
        BotCommand("rules",         "গ্রুপের নিয়ম দেখুন"),
        BotCommand("notes",         "নোট তালিকা"),
        BotCommand("adminlist",     "অ্যাডমিন তালিকা"),
    ]
    await app.bot.set_my_commands(admin_commands, scope=BotCommandScopeAllChatAdministrators())
    logger.info("✅ Bot commands registered with dedicated member and admin scopes.")

    # Start the promo loop task when event loop is active
    from modules import promo
    asyncio.create_task(promo.promo_loop(app))
    logger.info("✅ Repeating promotional broadcast task registered in active event loop")

    # Start the group title and member count synchronization task
    asyncio.create_task(sync_group_info(app))
    logger.info("✅ Group info and member count synchronization task registered")


async def sync_group_info(app: Application) -> None:
    """Periodically fetches and saves group title and member counts for all groups."""
    from database import get_all_chat_ids, update_chat_info
    # Small initial delay to let bot finish starting
    await asyncio.sleep(5)
    while True:
        try:
            chat_ids = await get_all_chat_ids()
            for chat_id in chat_ids:
                try:
                    chat = await app.bot.get_chat(chat_id)
                    title = chat.title or ""
                    try:
                        count = await chat.get_member_count()
                    except Exception:
                        count = 0
                    if title or count > 0:
                        await update_chat_info(chat_id, title=title, member_count=count)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Group sync error: {e}")
        await asyncio.sleep(300) # Sync every 5 minutes


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
    tagall.register(app)      # /tagall /all /cancel
    promo.register(app)       # /setpromosticker /delpromosticker
    spam.register(app)        # message filter (last — catches all text)

    app.add_error_handler(error_handler)

    logger.info("🚀 Bot is starting...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
