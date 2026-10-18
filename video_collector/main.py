"""
Video Collector Userbot — Powered by Telethon & MTProto
Monitors source channels/groups (WITHOUT requiring admin permissions),
extracts incoming videos, delivers them cleanly to your delivery channel(s),
and immediately deletes the processing task from the MySQL database.
"""

import sys
import os
import asyncio
import logging

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat

from video_collector.config import (
    TG_API_ID, TG_API_HASH, SESSION_NAME, FORWARD_DELAY_SECONDS
)
from video_collector.database import (
    init_db, get_source_channel_targets, get_delivery_channel_targets,
    add_queue_item, delete_queue_item, increment_forwarded_count,
    get_collector_stats, get_setting
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("video_collector")

# Path to session file in video_collector folder
session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), SESSION_NAME)
client = TelegramClient(session_path, TG_API_ID, TG_API_HASH)


def _is_video_message(message) -> bool:
    """Check if a Telethon message contains a video or animation."""
    if not message or not message.media:
        return False
    if getattr(message, "video", None):
        return True
    if getattr(message, "document", None):
        mime = getattr(message.document, "mime_type", "") or ""
        if mime.startswith("video/"):
            return True
    return False


@client.on(events.NewMessage)
async def handle_new_message(event: events.NewMessage.Event) -> None:
    """Triggered on every new message in joined channels/groups."""
    msg = event.message
    if not msg:
        return

    # 1. Quick check: must have video media
    if not _is_video_message(msg):
        return

    # 2. Check if collector is enabled
    is_active = await get_setting("is_collector_active", "1")
    if is_active != "1":
        return

    # 3. Check if chat is in registered source channels
    chat_id = event.chat_id
    try:
        chat = await event.get_chat()
        chat_title = getattr(chat, "title", "Unknown")
        chat_username = (getattr(chat, "username", "") or "").lower()
    except Exception:
        chat_title = "Unknown"
        chat_username = ""

    sources = await get_source_channel_targets()
    matched = False
    if chat_id in sources["ids"]:
        matched = True
    elif chat_username and chat_username in sources["usernames"]:
        matched = True

    if not matched:
        return

    logger.info(f"📥 New video detected from source: {chat_title} (ID: {chat_id}) - Msg ID: {msg.id}")

    # 4. Insert into MySQL queue
    caption = msg.text or ""
    file_repr = str(msg.id)
    try:
        queue_id = await add_queue_item(chat_id, msg.id, file_repr, caption)
        logger.info(f"📝 Video queued in MySQL with ID: #{queue_id}")
    except Exception as e_db:
        logger.error(f"❌ Failed to insert into MySQL queue: {e_db}")
        queue_id = None

    # 5. Fetch delivery targets
    deliveries = await get_delivery_channel_targets()
    if not deliveries:
        logger.warning("⚠️ No active delivery channels configured in admin panel! Video skipped.")
        return

    # 6. Deliver video to all target delivery channels
    successful_deliveries = 0
    custom_caption = await get_setting("custom_caption", "")
    final_caption = custom_caption if custom_caption else caption

    for target in deliveries:
        try:
            logger.info(f"🚀 Sending video to delivery channel: {target}...")
            # send_file delivers the video cleanly without 'Forwarded from' tag
            await client.send_file(
                target,
                file=msg.media,
                caption=final_caption,
                supports_streaming=True
            )
            successful_deliveries += 1
            logger.info(f"✅ Successfully delivered video to: {target}")
            if FORWARD_DELAY_SECONDS > 0:
                await asyncio.sleep(FORWARD_DELAY_SECONDS)
        except Exception as e:
            logger.error(f"❌ Delivery failed for {target}: {e}")

    # 7. Immediately delete task from MySQL database once delivered
    if successful_deliveries > 0 and queue_id:
        try:
            await delete_queue_item(queue_id)
            await increment_forwarded_count()
            logger.info(f"🗑️ Video task #{queue_id} immediately deleted from MySQL database. Total count incremented.")
        except Exception as e:
            logger.error(f"Failed to delete queue item #{queue_id}: {e}")

        # 8. Optional: Delete source message if admin permissions exist in source
        delete_source = await get_setting("delete_source_message", "0")
        if delete_source == "1":
            try:
                await event.delete()
                logger.info(f"🧹 Source message {msg.id} deleted from {chat_id}")
            except Exception:
                pass


# ── Owner Command Listener in Private / Saved Messages ──

@client.on(events.NewMessage(pattern=r"^/status$"))
async def cmd_status(event: events.NewMessage.Event) -> None:
    """Send stats when /status is typed to the client (e.g. in Saved Messages)."""
    stats = await get_collector_stats()
    is_active = await get_setting("is_collector_active", "1")
    status_str = "সক্রিয় 🟢" if is_active == "1" else "বন্ধ 🔴"

    text = (
        f"📊 <b>ভিডিও অটো-কালেক্টর স্ট্যাটাস:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔘 অবস্থা: <b>{status_str}</b>\n"
        f"📥 সোর্স চ্যানেল: <b>{stats['source_count']} টি</b>\n"
        f"📤 ডেলিভারি চ্যানেল: <b>{stats['delivery_count']} টি</b>\n"
        f"🚀 মোট ফরওয়ার্ডকৃত: <b>{stats['total_forwarded']} টি</b>\n"
        f"⏳ ডাটাবেজ কিউ: <b>{stats['queue_count']} টি</b>"
    )
    await event.reply(text, parse_mode="html")


async def main() -> None:
    logger.info("Initializing Video Collector database tables...")
    await init_db()

    logger.info("Starting Telethon Client...")
    await client.start()

    me = await client.get_me()
    logger.info(f"✅ Logged in successfully as: {me.first_name} (@{me.username or me.phone}) [ID: {me.id}]")

    # Auto-resolve delivery channel @darkromance4u
    try:
        from video_collector.database import update_channel_id_by_username
        del_ent = await client.get_entity("darkromance4u")
        logger.info(f"🎯 Delivery channel resolved: {getattr(del_ent, 'title', 'Dark Romance')} [ID: {del_ent.id}]")
        await update_channel_id_by_username("darkromance4u", del_ent.id)
    except Exception as e_del:
        logger.info(f"Delivery channel @darkromance4u will be resolved on first delivery ({e_del})")

    logger.info("🎯 Video Collector is now actively monitoring all registered source channels!")

    await client.run_until_disconnected()


if __name__ == "__main__":
    client.loop.run_until_complete(main())
