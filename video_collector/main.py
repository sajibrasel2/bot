"""
Video Collector Userbot — Powered by Telethon & MTProto
Monitors source channels/groups (WITHOUT requiring admin permissions),
extracts videos, delivers them sequentially (1 video every 30 minutes)
to your delivery channel (@darkromance4u), and immediately deletes
delivered videos from the MySQL queue database.
"""

import sys
import os
import asyncio
import logging
from typing import Optional, Any, List, Dict, Set

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient, events
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import Channel, Chat

from video_collector.config import (
    TG_API_ID, TG_API_HASH, SESSION_NAME, FORWARD_DELAY_SECONDS
)
from video_collector.database import (
    init_db, get_source_channel_targets, get_delivery_channel_targets,
    update_channel_id_by_username, add_queue_item, delete_queue_item,
    get_next_queue_item, is_message_processed, is_message_in_queue,
    mark_message_processed, increment_forwarded_count, get_collector_stats,
    get_setting, set_setting, is_channel_deactivated, auto_register_source_channel,
    is_delivery_chat
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("video_collector")

session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), SESSION_NAME)
client = TelegramClient(session_path, TG_API_ID, TG_API_HASH)


def _is_video_message(message) -> bool:
    """Check if a Telethon message contains a video or video document."""
    if not message or not message.media:
        return False
    if getattr(message, "video", None):
        return True
    if getattr(message, "document", None):
        mime = getattr(message.document, "mime_type", "") or ""
        if mime.startswith("video/"):
            return True
    return False


async def auto_join_channel(channel_target) -> Optional[Any]:
    """Resolve channel entity and attempt to join if public."""
    try:
        entity = await client.get_entity(channel_target)
        try:
            await client(JoinChannelRequest(entity))
        except Exception:
            pass  # Already joined, or private, or permission not needed to view
        return entity
    except Exception as e:
        logger.warning(f"Could not resolve entity '{channel_target}': {e}")
        return None


async def crawl_source_channels(limit_per_source: int = 15, max_queue_buffer: int = 80) -> int:
    """
    Crawl past messages across active channels to keep a healthy FIFO queue (up to max_queue_buffer).
    Supports Option A: All joined channels/groups, or Option B: Specific registered channels.
    """
    stats = await get_collector_stats()
    current_queue = stats.get("queue_count", 0)
    if current_queue >= max_queue_buffer:
        logger.info(f"📦 Queue already has {current_queue} videos (Target: {max_queue_buffer}). Backlog crawl skipped.")
        return 0

    collect_all = await get_setting("collect_from_all_joined", "1")
    total_added = 0

    if collect_all == "1":
        logger.info("🔍 Auto-crawling across ALL joined channels and groups on this user account...")
        try:
            async for dialog in client.iter_dialogs(limit=50):
                if current_queue + total_added >= max_queue_buffer:
                    break
                if not (dialog.is_channel or dialog.is_group):
                    continue

                chat_id = dialog.id
                chat_entity = dialog.entity
                chat_username = (getattr(chat_entity, "username", "") or "").lower()
                chat_title = getattr(dialog, "name", "") or getattr(chat_entity, "title", "Unknown")

                # Strictly exclude delivery channels to prevent recursive loops
                if await is_delivery_chat(chat_id, chat_username):
                    continue

                # Check if admin deactivated this channel
                if await is_channel_deactivated(chat_id, chat_username):
                    continue

                # Auto register channel in DB for dashboard visibility
                await auto_register_source_channel(chat_id, chat_title, chat_username)

                # Fetch chronological messages (oldest to newest)
                async for msg in client.iter_messages(chat_entity, limit=limit_per_source, reverse=True):
                    if current_queue + total_added >= max_queue_buffer:
                        break
                    if _is_video_message(msg):
                        qid = await add_queue_item(chat_id, msg.id, str(msg.id), msg.text or "")
                        if qid:
                            total_added += 1

        except Exception as e_dialogs:
            logger.error(f"Error during all-dialogs crawl: {e_dialogs}")

    else:
        # Crawl only specific registered channels
        sources_data = await get_source_channel_targets()
        rows = sources_data.get("rows", [])
        logger.info(f"🔍 Crawling registered {len(rows)} source channels...")

        for row in rows:
            if current_queue + total_added >= max_queue_buffer:
                break
            target = row.get("channel_username") or row.get("channel_id")
            if not target:
                continue

            try:
                entity = await auto_join_channel(target)
                if not entity:
                    continue

                if (not row.get("channel_id") or row["channel_id"] == 0) and getattr(entity, "id", None):
                    await update_channel_id_by_username(str(target), entity.id)

                chat_id = getattr(entity, "id", 0)

                async for msg in client.iter_messages(entity, limit=limit_per_source, reverse=True):
                    if current_queue + total_added >= max_queue_buffer:
                        break
                    if _is_video_message(msg):
                        qid = await add_queue_item(chat_id, msg.id, str(msg.id), msg.text or "")
                        if qid:
                            total_added += 1

            except Exception as e:
                logger.error(f"Error crawling source channel '{target}': {e}")

    logger.info(f"✅ Crawl complete. Added {total_added} new sequential videos to MySQL queue (Total queue: {current_queue + total_added}).")
    return total_added


@client.on(events.NewMessage)
async def handle_new_message(event: events.NewMessage.Event) -> None:
    """Real-time listener for incoming new videos from joined channels/groups."""
    msg = event.message
    if not msg or not _is_video_message(msg):
        return

    is_active = await get_setting("is_collector_active", "1")
    if is_active != "1":
        return

    # Do not collect from private 1-on-1 chats or DMs
    if event.is_private:
        return

    chat_id = event.chat_id
    try:
        chat = await event.get_chat()
        chat_title = getattr(chat, "title", "Unknown")
        chat_username = (getattr(chat, "username", "") or "").lower()
    except Exception:
        chat_title = "Unknown"
        chat_username = ""

    # Strictly protect delivery channel(s) from self-collection
    if await is_delivery_chat(chat_id, chat_username):
        return

    collect_all = await get_setting("collect_from_all_joined", "1")
    matched = False

    if collect_all == "1":
        # Mode A: All joined channels & groups
        if not await is_channel_deactivated(chat_id, chat_username):
            matched = True
            # Auto-register source channel into DB
            await auto_register_source_channel(chat_id, chat_title, chat_username)
    else:
        # Mode B: Explicit registered source channels only
        sources = await get_source_channel_targets()
        if chat_id in sources["ids"] or (chat_username and chat_username in sources["usernames"]):
            matched = True

    if not matched:
        return

    logger.info(f"📥 New video detected from {chat_title} (ID: {chat_id}, Msg: {msg.id})")

    # add_queue_item guarantees deduplication against both vc_processed and vc_queue
    qid = await add_queue_item(chat_id, msg.id, str(msg.id), msg.text or "")
    if qid:
        logger.info(f"📝 Video queued in MySQL with ID: #{qid}")


async def deliver_video_message(orig_msg, target: Any, caption: str) -> bool:
    """Deliver a video to target channel, automatically bypassing protected chat restrictions if needed."""
    try:
        # Fast path: direct media reference
        await client.send_file(
            target,
            file=orig_msg.media,
            caption=caption,
            supports_streaming=True
        )
        return True
    except Exception as e_send:
        err_msg = str(e_send).lower()
        if "protected chat" in err_msg or "forward" in err_msg or "restricted" in err_msg:
            logger.info("🛡️ Protected content detected! Downloading video locally to bypass forwarding restriction...")
            temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_downloads")
            os.makedirs(temp_dir, exist_ok=True)
            downloaded = await client.download_media(orig_msg, file=temp_dir)
            if downloaded and os.path.exists(downloaded):
                try:
                    logger.info(f"📤 Uploading bypass video ({os.path.basename(downloaded)}) to {target}...")
                    await client.send_file(
                        target,
                        file=downloaded,
                        caption=caption,
                        supports_streaming=True
                    )
                    return True
                finally:
                    try:
                        if os.path.exists(downloaded):
                            os.remove(downloaded)
                            logger.info(f"🧹 Temporary video cleaned up: {os.path.basename(downloaded)}")
                    except Exception:
                        pass
            else:
                logger.error("❌ Failed to download protected video locally.")
                return False
        else:
            logger.error(f"❌ Delivery error for target {target}: {e_send}")
            return False


async def delivery_worker_loop() -> None:
    """
    Sequential Delivery Worker:
    Delivers 1 video every 30 minutes (or configured interval) from the MySQL queue,
    and immediately deletes each video record from the database once delivered.
    """
    logger.info("🚀 30-Minute Sequential Delivery Worker initialized.")
    # Initial pause to allow client and startup crawl to finish
    await asyncio.sleep(5)

    while True:
        try:
            is_active = await get_setting("is_collector_active", "1")
            if is_active != "1":
                await asyncio.sleep(10)
                continue

            # Fetch next video in FIFO order
            item = await get_next_queue_item()
            if not item:
                logger.info("📭 Video queue is currently empty. Running crawl on source channels...")
                added = await crawl_source_channels(limit_per_source=60)
                if added > 0:
                    item = await get_next_queue_item()

            if item:
                queue_id = item["id"]
                source_chat = item["source_chat_id"]
                msg_id = item["source_message_id"]
                logger.info(f"📦 Next in queue: #{queue_id} (Source Chat: {source_chat}, Msg ID: {msg_id})")

                deliveries = await get_delivery_channel_targets()
                if not deliveries:
                    logger.warning("⚠️ No active delivery channels configured! Skipping delivery cycle.")
                    await asyncio.sleep(60)
                    continue

                delivery_success = False
                try:
                    # Retrieve the original message
                    orig_msg = await client.get_messages(source_chat, ids=msg_id)
                    if orig_msg and _is_video_message(orig_msg):
                        custom_caption = await get_setting("custom_caption", "")
                        caption = custom_caption if custom_caption else (orig_msg.text or item.get("caption") or "")

                        for target in deliveries:
                            try:
                                logger.info(f"🚀 Delivering video #{queue_id} to channel: {target}...")
                                res = await deliver_video_message(orig_msg, target, caption)
                                if res:
                                    delivery_success = True
                                    logger.info(f"✅ Video #{queue_id} successfully delivered to: {target}")
                                    if FORWARD_DELAY_SECONDS > 0:
                                        await asyncio.sleep(FORWARD_DELAY_SECONDS)
                            except Exception as e_deliv:
                                logger.error(f"❌ Failed to send video to delivery target '{target}': {e_deliv}")
                    else:
                        logger.warning(f"⚠️ Source video message {msg_id} was deleted or inaccessible in {source_chat}.")
                        # Mark success so this missing item is removed from queue
                        delivery_success = True

                except Exception as e_proc:
                    logger.error(f"❌ Error retrieving video for queue #{queue_id}: {e_proc}")
                    delivery_success = True

                # IMMEDIATELY DELETE FROM MYSQL QUEUE TABLE
                await delete_queue_item(queue_id)
                await mark_message_processed(source_chat, msg_id)

                if delivery_success:
                    await increment_forwarded_count()
                    logger.info(f"🗑️ Video #{queue_id} immediately deleted from MySQL. Total forwarded incremented.")

                    # Calculate sleep time based on interval setting (default: 30 minutes)
                    try:
                        interval_min = int(await get_setting("delivery_interval_minutes", "30"))
                    except Exception:
                        interval_min = 30

                    wait_seconds = max(10, interval_min * 60)
                    logger.info(f"⏳ 1 video delivered! Waiting {interval_min} minutes ({wait_seconds}s) for next video delivery...")

                    # Interruptible sleep in 5-second intervals to allow manual "Send Now" button trigger
                    for _ in range(wait_seconds // 5):
                        await asyncio.sleep(5)
                        trigger_now = await get_setting("trigger_immediate_send", "0")
                        if trigger_now == "1":
                            await set_setting("trigger_immediate_send", "0")
                            logger.info("⚡ Immediate delivery triggered by Admin! Delivering next video now...")
                            break
                else:
                    # Retry in 30 seconds if failed
                    await asyncio.sleep(30)
            else:
                # Queue empty even after crawl, wait 60s
                logger.info("😴 No videos available in sources. Waiting 60 seconds before next check...")
                await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info("Delivery worker task cancelled.")
            break
        except Exception as e_loop:
            logger.error(f"Unexpected error in delivery worker: {e_loop}", exc_info=True)
            await asyncio.sleep(30)


@client.on(events.NewMessage(pattern=r"^/status$"))
async def cmd_status(event: events.NewMessage.Event) -> None:
    """Send stats when /status is sent to the userbot."""
    stats = await get_collector_stats()
    is_active = await get_setting("is_collector_active", "1")
    interval = await get_setting("delivery_interval_minutes", "30")
    status_str = "সক্রিয় 🟢" if is_active == "1" else "বন্ধ 🔴"

    text = (
        f"📊 <b>ভিডিও অটো-কালেক্টর ও ডেলিভারি স্ট্যাটাস:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔘 অবস্থা: <b>{status_str}</b>\n"
        f"⏱️ ডেলিভারি বিরতি: <b>প্রতি {interval} মিনিট পর পর ১টি</b>\n"
        f"📥 সোর্স চ্যানেল: <b>{stats['source_count']} টি</b>\n"
        f"📤 ডেলিভারি চ্যানেল: <b>{stats['delivery_count']} টি</b>\n"
        f"🚀 মোট ডেলিভারিকৃত: <b>{stats['total_forwarded']} টি</b>\n"
        f"⏳ ডাটাবেজ কিউ অপেক্ষা করছে: <b>{stats['queue_count']} টি</b>"
    )
    await event.reply(text, parse_mode="html")


async def main() -> None:
    logger.info("Initializing Video Collector database tables...")
    await init_db()

    logger.info("Starting Telethon Client...")
    await client.start()

    me = await client.get_me()
    logger.info(f"✅ Logged in successfully as: {me.first_name} (@{me.username or me.phone}) [ID: {me.id}]")

    # Auto-resolve delivery channels (e.g. @darkromance4u)
    deliveries = await get_delivery_channel_targets()
    for d in deliveries:
        try:
            ent = await client.get_entity(d)
            logger.info(f"🎯 Delivery channel confirmed: {getattr(ent, 'title', d)} [ID: {ent.id}]")
            if isinstance(d, str):
                await update_channel_id_by_username(d, ent.id)
        except Exception as e_del:
            logger.warning(f"Could not resolve delivery channel '{d}': {e_del}")

    # Auto-resolve source channels
    sources = await get_source_channel_targets()
    for u in sources.get("usernames", []):
        try:
            ent = await auto_join_channel(u)
            if ent:
                logger.info(f"📥 Source channel confirmed & joined: {getattr(ent, 'title', u)} [ID: {ent.id}]")
                await update_channel_id_by_username(u, ent.id)
        except Exception as e_src:
            logger.warning(f"Could not auto-resolve source channel '{u}': {e_src}")

    # Initial crawl of source channels into MySQL queue
    asyncio.create_task(crawl_source_channels(limit_per_source=80))

    # Start 30-minute sequential delivery worker
    asyncio.create_task(delivery_worker_loop())

    logger.info("🎯 Video Collector is now running! (1 video every 30 mins -> @darkromance4u)")
    await client.run_until_disconnected()


if __name__ == "__main__":
    client.loop.run_until_complete(main())
