"""
Video Collector Bot — Main Service
Collects videos from registered source channels/groups,
delivers them to designated delivery channels,
and immediately deletes the task from MySQL database.
"""

import sys
import os
import asyncio
import logging

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, BotCommand, BotCommandScopeDefault
from telegram.ext import (
    Application, ContextTypes, MessageHandler, CommandHandler, filters
)
from telegram.request import HTTPXRequest

from video_collector.config import (
    VC_BOT_TOKEN, VC_BOT_USERNAME, VC_OWNER_ID, FORWARD_DELAY_SECONDS
)
from video_collector.database import (
    init_db, get_source_channel_ids, get_delivery_channel_ids,
    add_queue_item, delete_queue_item, increment_forwarded_count,
    get_collector_stats, get_setting, add_channel, get_all_channels
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("video_collector")


async def handle_incoming_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Triggered when a video is posted in a channel or group."""
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat:
        return

    # Check if collector is globally enabled
    is_active = await get_setting("is_collector_active", "1")
    if is_active != "1":
        return

    # Check if chat is in registered source channels
    source_ids = await get_source_channel_ids()
    if chat.id not in source_ids:
        return

    # Determine file_id and media type
    file_id = None
    if msg.video:
        file_id = msg.video.file_id
    elif msg.animation:
        file_id = msg.animation.file_id
    elif msg.document and msg.document.mime_type and msg.document.mime_type.startswith("video/"):
        file_id = msg.document.file_id

    if not file_id:
        return

    logger.info(f"📥 New video detected from source: {chat.title} ({chat.id}) - Msg ID: {msg.message_id}")

    # 1. Store in MySQL queue
    caption = msg.caption_html or msg.caption or ""
    queue_id = await add_queue_item(chat.id, msg.message_id, file_id, caption)
    logger.info(f"📝 Video queued in MySQL with ID: {queue_id}")

    # 2. Get delivery channels
    delivery_ids = await get_delivery_channel_ids()
    if not delivery_ids:
        logger.warning("⚠️ No active delivery channels configured! Video queued but not delivered.")
        return

    # 3. Send video to all delivery channels
    successful_deliveries = 0
    for target_id in delivery_ids:
        try:
            # Use copy_message to preserve original quality, formatting, and stream attributes
            await context.bot.copy_message(
                chat_id=target_id,
                from_chat_id=chat.id,
                message_id=msg.message_id,
                caption=caption if caption else None,
                parse_mode="HTML" if caption else None
            )
            successful_deliveries += 1
            logger.info(f"🚀 Video forwarded to delivery channel {target_id}")
            if FORWARD_DELAY_SECONDS > 0:
                await asyncio.sleep(FORWARD_DELAY_SECONDS)
        except Exception as e:
            logger.error(f"❌ Failed to forward video to {target_id}: {e}")

    # 4. Immediately delete from MySQL database once delivered
    if successful_deliveries > 0:
        await delete_queue_item(queue_id)
        await increment_forwarded_count()
        logger.info(f"🗑️ Video task #{queue_id} immediately deleted from MySQL database. Total forwarded updated.")

        # 5. Optionally delete the video from source channel if enabled in settings
        delete_source = await get_setting("delete_source_message", "0")
        if delete_source == "1":
            try:
                await msg.delete()
                logger.info(f"🧹 Source message {msg.message_id} deleted from {chat.id}")
            except Exception as e:
                logger.warning(f"Could not delete source message: {e}")


# ── Bot Admin Commands ─────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    stats = await get_collector_stats()
    text = (
        f"🤖 <b>ভিডিও অটো-কালেক্টর ও ডেলিভারি বট</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 স্বাগতম {user.first_name if user else ''}!\n\n"
        f"📊 <b>বর্তমান পরিসংখ্যান:</b>\n"
        f"  • সোর্স চ্যানেল: <b>{stats['source_count']} টি</b>\n"
        f"  • ডেলিভারি চ্যানেল: <b>{stats['delivery_count']} টি</b>\n"
        f"  • মোট সফল ডেলিভারি: <b>{stats['total_forwarded']} টি</b>\n\n"
        f"⚙️ ওয়েব অ্যাডমিন প্যানেল থেকে সোর্স ও ডেলিভারি চ্যানেল যুক্ত বা ডিলিট করুন।"
    )
    await update.message.reply_html(text)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    stats = await get_collector_stats()
    is_active = await get_setting("is_collector_active", "1")
    del_source = await get_setting("delete_source_message", "0")

    status_str = "সক্রিয় (Active) 🟢" if is_active == "1" else "স্থগিত (Paused) 🔴"
    del_str = "হ্যাঁ (Yes) 🗑️" if del_source == "1" else "না (No) ❌"

    channels = await get_all_channels()
    sources = [c for c in channels if c.get("channel_type") == "source"]
    deliveries = [c for c in channels if c.get("channel_type") == "delivery"]

    lines = [
        f"📊 <b>ভিডিও কালেক্টর স্ট্যাটাস:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━",
        f"🔘 বটের অবস্থা: <b>{status_str}</b>",
        f"🧹 সোর্স মেসেজ ডিলিট: <b>{del_str}</b>",
        f"🚀 মোট ফরওয়ার্ডকৃত: <b>{stats['total_forwarded']} টি</b>",
        f"⏳ অপেক্ষমান কিউ: <b>{stats['queue_count']} টি</b>\n",
        f"📥 <b>সোর্স চ্যানেল ({len(sources)}):</b>"
    ]

    if sources:
        for s in sources:
            name = s.get("channel_title") or s.get("channel_username") or "চ্যানেল"
            lines.append(f"  • {name} (<code>{s['channel_id']}</code>)")
    else:
        lines.append("  <i>কোনো সোর্স চ্যানেল নেই</i>")

    lines.append(f"\n📤 <b>ডেলিভারি চ্যানেল ({len(deliveries)}):</b>")
    if deliveries:
        for d in deliveries:
            name = d.get("channel_title") or d.get("channel_username") or "চ্যানেল"
            lines.append(f"  • {name} (<code>{d['channel_id']}</code>)")
    else:
        lines.append("  <i>কোনো ডেলিভারি চ্যানেল নেই</i>")

    await update.message.reply_html("\n".join(lines))


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    await update.message.reply_html(
        f"🆔 <b>তথ্য:</b>\n"
        f"💬 চ্যাট ID: <code>{chat.id}</code>\n"
        f"👤 আপনার ID: <code>{user.id if user else ''}</code>\n"
        f"📋 চ্যাট টাইপ: {chat.type}"
    )


async def post_init(app: Application) -> None:
    await init_db()
    commands = [
        BotCommand("start", "বটের পরিচিতি ও মেনু"),
        BotCommand("status", "সোর্স ও ডেলিভারি চ্যানেলের স্ট্যাটাস"),
        BotCommand("id", "চ্যানেল বা ইউজারের আইডি দেখুন"),
    ]
    await app.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    logger.info("✅ Video Collector Bot initialized and commands registered.")


def main() -> None:
    token = VC_BOT_TOKEN
    if not token:
        try:
            import pymysql
            from video_collector.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB
            conn = pymysql.connect(
                host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER,
                password=MYSQL_PASSWORD, database=MYSQL_DB
            )
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM vc_settings WHERE key_name = 'vc_bot_token'")
                row = cur.fetchone()
                if row and row[0]:
                    token = row[0].strip()
            conn.close()
        except Exception:
            pass

    if not token:
        logger.error("❌ VC_BOT_TOKEN is not configured! Please set VC_BOT_TOKEN in .env or via Web Panel.")
        print("\n" + "="*60)
        print("⚠️  VC_BOT_TOKEN খালি আছে! দয়া করে .env ফাইলে অথবা")
        print("    ওয়েব অ্যাডমিন প্যানেলে বটের টোকেন প্রদান করুন।")
        print("="*60 + "\n")
        sys.exit(1)

    req = HTTPXRequest(
        connection_pool_size=16,
        connect_timeout=20.0,
        read_timeout=30.0,
        write_timeout=30.0,
    )

    app = (
        Application.builder()
        .token(token)
        .request(req)
        .post_init(post_init)
        .build()
    )

    # Video handler for channel posts and group messages
    video_filter = (filters.VIDEO | filters.ANIMATION | filters.Document.VIDEO)
    app.add_handler(MessageHandler(video_filter, handle_incoming_video))

    # Basic Commands
    app.add_handler(CommandHandler(["start", "help"], cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler(["id", "chatid"], cmd_id))

    logger.info("🚀 Starting Video Collector Bot polling...")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
