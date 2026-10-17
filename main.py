"""
Main entry point for the Group Manager Bot.
Run: python main.py
"""

import asyncio
import logging
import os

from telegram import (
    Update, BotCommand, BotCommandScopeDefault,
    BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats,
    BotCommandScopeAllChatAdministrators
)
from telegram.ext import Application, ContextTypes
from telegram.request import HTTPXRequest

from config import BOT_TOKEN
from database import init_db

# ── Modules ──────────────────────────────────────
from modules import help, welcome, spam, moderation, admin, notes, promo, tagall, forceadd, service_alert

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(app: Application) -> None:
    """Runs after the bot is initialized — set up DB and bot commands."""
    await init_db()
    logger.info("✅ MySQL Database initialized")

    # 1. Commands for private chat with bot (ব্যক্তিগত চ্যাটে মেনু)
    private_commands = [
        BotCommand("start",         "বট শুরু করুন"),
        BotCommand("help",          "সাহায্য মেনু ও সকল কমান্ড"),
        BotCommand("settings",      "গ্রুপ সেটিংস কন্ট্রোল প্যানেল"),
        BotCommand("panel",         "মডারেশন ও কন্ট্রোল প্যানেল"),
        BotCommand("forceadd",      "ফোর্স অ্যাড সেটিংস"),
        BotCommand("forceunlock",   "চ্যাট সরাসরি আজীবন আনলক করতে"),
        BotCommand("forcelock",     "চ্যাট পুনরায় লক করতে"),
        BotCommand("rules",         "গ্রুপের নিয়ম দেখুন"),
        BotCommand("restart",       "বট রিস্টার্ট করুন"),
    ]
    await app.bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())

    # 2. Commands for general members in groups (গ্রুপের সাধারণ সদস্যদের জন্য মেনু)
    group_member_commands = [
        BotCommand("rules", "গ্রুপের নিয়ম দেখুন"),
        BotCommand("myinvites", "আপনার ইনভাইট অগ্রগতি"),
        BotCommand("top", "সেরা ইনভাইটার লিডারবোর্ড"),
    ]
    await app.bot.set_my_commands(group_member_commands, scope=BotCommandScopeAllGroupChats())

    # 3. Commands for group administrators (শুধুমাত্র অ্যাডমিনদের জন্য সম্পূর্ণ কন্ট্রোল মেনু)
    admin_commands = [
        BotCommand("settings",      "গ্রুপ সেটিংস কন্ট্রোল প্যানেল"),
        BotCommand("panel",         "মডারেশন ও কন্ট্রোল প্যানেল"),
        BotCommand("forceadd",      "ফোর্স অ্যাড সেটিংস"),
        BotCommand("forceunlock",   "চ্যাট সরাসরি আজীবন আনলক করতে"),
        BotCommand("forcelock",     "চ্যাট পুনরায় লক করতে"),
        BotCommand("restart",       "বট রিস্টার্ট করুন"),
        BotCommand("tagall",        "সবাইকে মেনশন করুন (/all)"),
        BotCommand("cancel",        "মেনশন থামান (/tagstop)"),
        BotCommand("autotag",       "রাত ১১টার অটো-ট্যাগ শিডিউল"),
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
        BotCommand("setwelcomesticker", "ওয়েলকাম স্টিকার সেট করুন"),
        BotCommand("delwelcomesticker", "ওয়েলকাম স্টিকার মুছুন"),
        BotCommand("promo",             "লাইভ পার্টনার বিজ্ঞাপন পাঠান"),
        BotCommand("servicealert",      "সার্ভিস গার্ল নোটিশ পাঠান"),
        BotCommand("rules",             "গ্রুপের নিয়ম দেখুন"),
        BotCommand("notes",             "নোট তালিকা"),
        BotCommand("top",               "সেরা ইনভাইটার লিডারবোর্ড"),
    ]
    await app.bot.set_my_commands(admin_commands, scope=BotCommandScopeAllChatAdministrators())
    # 4. Default fallback scope
    await app.bot.set_my_commands(admin_commands, scope=BotCommandScopeDefault())
    logger.info("✅ Bot commands registered with private, group member, admin, and default scopes.")

    # Start the promo loop task when event loop is active
    from modules import promo
    asyncio.create_task(promo.promo_loop(app))
    logger.info("✅ Repeating promotional broadcast task registered in active event loop")

    # Start the service alert loop task
    asyncio.create_task(service_alert.service_alert_loop(app))
    logger.info("✅ Repeating service alert broadcast task registered in active event loop")

    # Start the group title and member count synchronization task
    asyncio.create_task(sync_group_info(app))
    logger.info("✅ Group info and member count synchronization task registered")

    # Start the daily 11:00 PM auto-tagall scheduler task (Bangladesh Time UTC+6)
    from modules import tagall
    asyncio.create_task(tagall.scheduled_daily_tagall_loop(app))
    logger.info("✅ Daily 11:00 PM auto-tagall scheduler task registered")


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
    err_str = str(context.error or "").lower()
    logger.error("Exception while handling update:", exc_info=context.error)
    # Ignore routine Telegram API messages like message deleted, chat not found, etc.
    if any(k in err_str for k in ("message to reply not found", "message to be replied not found", "message can't be deleted", "message is not modified", "chat not found", "bot was blocked", "have no rights")):
        return


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
    service_alert.register(app) # /servicealert /sendalert /girlnotice
    forceadd.register(app)    # /forceadd /myinvites /top + chat unlock enforcement
    spam.register(app)        # message filter (last — catches all text)

    app.add_error_handler(error_handler)

    logger.info("🚀 Bot is starting...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
