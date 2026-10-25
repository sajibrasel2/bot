"""
Video Collector Userbot — Powered by Telethon & MTProto
Monitors source channels/groups (WITHOUT requiring admin permissions),
extracts videos, delivers them sequentially (1 video every 30 minutes)
to your delivery channel (@darkromance4u), and immediately deletes
delivered videos from the MySQL queue database.
"""

import sys
import os
import re
import asyncio
import logging
import warnings
from typing import Optional, Any, List, Dict, Set

# Suppress harmless MySQL warning notices from aiomysql
warnings.filterwarnings("ignore", category=Warning, module="aiomysql")

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient, events
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import Channel, Chat, DocumentAttributeAnimated, DocumentAttributeVideo

from video_collector.config import (
    TG_API_ID, TG_API_HASH, SESSION_NAME, FORWARD_DELAY_SECONDS
)
from video_collector.database import (
    init_db, get_source_channel_targets, get_delivery_channel_targets,
    update_channel_id_by_username, add_queue_item, delete_queue_item,
    get_next_queue_item, is_message_processed, is_message_in_queue,
    mark_message_processed, increment_forwarded_count, get_collector_stats,
    get_setting, set_setting, is_channel_deactivated, auto_register_source_channel,
    is_delivery_chat, purge_delivery_items_from_queue, is_media_processed,
    record_excluded_delivery_group, get_channel_last_scanned_id,
    update_channel_last_scanned_id, add_portal_video_auto_rotate
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("video_collector")

session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), SESSION_NAME)
client = TelegramClient(session_path, TG_API_ID, TG_API_HASH)


def get_video_duration(message) -> Optional[float]:
    """Extract video duration in seconds from message attributes or file helper."""
    if not message or not message.media:
        return None
    try:
        if hasattr(message, "file") and message.file and message.file.duration is not None:
            return float(message.file.duration)
    except Exception:
        pass

    doc = getattr(message, "document", None) or getattr(message, "video", None)
    if doc:
        attrs = getattr(doc, "attributes", []) or []
        for attr in attrs:
            if isinstance(attr, DocumentAttributeVideo):
                return float(getattr(attr, "duration", 0))
            if hasattr(attr, "duration") and "video" in type(attr).__name__.lower():
                try:
                    return float(attr.duration)
                except Exception:
                    pass
    return None


async def get_min_video_duration() -> float:
    """Fetch minimum video duration in seconds from database settings (default: 20s)."""
    try:
        val = await get_setting("min_video_duration", "20")
        return float(val)
    except Exception:
        return 20.0


def _is_video_message(message, min_duration: float = 20.0) -> bool:
    """
    Check if a Telethon message contains a genuine video file,
    strictly excluding GIFs, animations, video stickers, round video notes,
    and videos shorter than min_duration seconds (default: 20 seconds).
    """
    if not message or not message.media:
        return False

    # 1. Reject Telegram GIFs, stickers, and round video notes
    if getattr(message, "gif", None):
        return False
    if getattr(message, "video_note", None):
        return False
    if getattr(message, "sticker", None):
        return False

    doc = getattr(message, "document", None) or getattr(message, "video", None)
    if not doc:
        return False

    mime = (getattr(doc, "mime_type", "") or "").lower()
    if mime == "image/gif":
        return False

    # Inspect document attributes for DocumentAttributeAnimated
    attrs = getattr(doc, "attributes", []) or []
    for attr in attrs:
        if isinstance(attr, DocumentAttributeAnimated):
            return False
        if "animated" in type(attr).__name__.lower():
            return False

    # Check file name extension
    file_name = (getattr(message.file, "name", "") or "").lower() if hasattr(message, "file") and message.file else ""
    if file_name.endswith(".gif"):
        return False

    # 2. Check genuine video
    is_video = False
    if getattr(message, "video", None):
        is_video = True
    elif mime.startswith("video/"):
        is_video = True

    if not is_video:
        return False

    # 3. Check video duration (Must be >= min_duration, default: 20 seconds)
    if min_duration > 0:
        duration = get_video_duration(message)
        if duration is None or duration < min_duration:
            return False

    return True


def get_media_unique_id(message) -> Optional[int]:
    """Extract Telegram's global 64-bit document/video ID to uniquely identify duplicate video files."""
    if not message or not message.media:
        return None
    if getattr(message, "video", None):
        return getattr(message.video, "id", None)
    if getattr(message, "document", None):
        return getattr(message.document, "id", None)
    return None


COMMERCIAL_AD_PATTERN = re.compile(
    r'(?i)(?:'
    r'টাকা|টাকায়|টাকায়|দাম|অফার|ডিসকাউন্ট|ছাড়|ছাড়|লাইফ\s*টাইম|আজীবন|মেসেজ\s*কর|ইনবক্স|কিনতে|বিক্রি|যোগাযোগ|'
    r'প্রিমিয়াম\s*গ্রুপ|প্রিমিয়াম\s*গ্রুপ|ভিআইপি\s*গ্রুপ|প্যাকেজ|প্যাক|বিকাশ|নগদ|রকেট|সীমিত\s*সময়|সীমিত\s*সময়|'
    r'বাচ্চা|বাচ্চাদের|ধর্ষণ|ধর্ষন|রেপ|'
    r'price|taka|\btk\b|offer|discount|lifetime|inbox|dm\s*me|contact\s*admin|buy|sell|paid\s*group|premium\s*group|vip\s*group|'
    r'child|rape|cp\b'
    r')'
)

LIST_ITEM_PATTERN = re.compile(
    r'(?:^|\n)\s*[\d\u09E6-\u09EF\U0001D7CE-\U0001D7FF]{1,3}\s*[\.\/\)\-\:]'
)


def clean_source_caption(text: str) -> str:
    """
    Cleans caption by removing source channel names, mentions (@channel),
    all links/URLs, promotional phrases, and large commercial advertisement blocks.
    If the text is an advertisement, list menu, or too long, returns empty string
    so video delivers completely clean.
    """
    if not text:
        return ""

    raw_text = text.strip()

    # Rule 1: Commercial advertisement / paid group / pricing / blacklist check
    if COMMERCIAL_AD_PATTERN.search(raw_text):
        return ""

    # Rule 2: Package menu / numbered list detection (e.g. 1/, 2/, 3/ or 1., 2., 3.)
    if len(LIST_ITEM_PATTERN.findall(raw_text)) >= 2:
        return ""

    # Rule 3: Reject large text blocks (more than 4 lines or more than 220 characters)
    raw_lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    if len(raw_lines) > 4 or len(raw_text) > 220:
        return ""

    url_pattern = re.compile(
        r'(?:https?://\S+|www\.\S+|(?:t|telegram)\.me/\S+|\b[a-zA-Z0-9-]+\.(?:com|net|org|io|me|ru|site|xyz|info|vip|club|top|link|online|cc|to|tv|co|in|app|biz|pro|live|shop|tube|sexy|adult|porn|xxx)\b\S*)',
        re.IGNORECASE
    )
    mention_pattern = re.compile(r'@[A-Za-z0-9_]+')

    # Promotional / attribution call-to-actions (English + Bengali)
    promo_words_pattern = re.compile(
        r'(?i)\b(?:source|comments?|channel|subscribe|join|follow|watch|click|videos?|credits?|sponsored|download|backup|links?|leaks?|contact|admin|direct|invite|group|vip|exclusive)\b|'
        r'(?:চ্যানেল|জয়েন|সাবস্ক্রাইব|লিংক|ভিডিও|সোর্স|ক্লিক|গ্রুপ)'
    )

    cleaned_lines = []

    for line in raw_lines:
        # Rule 4: ANY line containing an external URL or Telegram link is promo/source attribution -> Drop completely
        if url_pattern.search(line):
            continue

        # Rule 5: If a line has a mention (@channel) and promo words, drop completely
        has_mention = bool(mention_pattern.search(line))
        has_promo = bool(promo_words_pattern.search(line))
        if has_mention and has_promo:
            continue

        # Strip mentions and symbols to inspect remaining text
        stripped = mention_pattern.sub('', line)
        stripped = re.sub(r'[-—:>=><~|•_#\*\.\s\?&/\\\(\)\[\]{}!@$%^+=]+', ' ', stripped).strip()

        # Rule 6: If what remains has no real letters/words, drop it
        letters_only = re.sub(r'[^\w]|_', '', stripped)
        if len(letters_only) < 3:
            continue

        # Rule 7: If what remains is predominantly promotional keywords (e.g. "Direct Link", "Join Channel")
        non_promo = promo_words_pattern.sub('', stripped)
        non_promo_letters = re.sub(r'[^\w]|_', '', non_promo)
        if len(non_promo_letters) < 3:
            continue

        # Clean trailing/leading symbols from valid title line
        cleaned = mention_pattern.sub('', line)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        cleaned = re.sub(r'^[-—:>=><~|•_#\*\.\s/]+', '', cleaned)
        cleaned = re.sub(r'[-—:>=><~|•_#\*\.\s/]+$', '', cleaned).strip()

        if cleaned:
            cleaned_lines.append(cleaned)

    # Rule 8: Genuine video captions are concise titles (max 2 lines)
    if len(cleaned_lines) > 2:
        return ""

    final_text = '\n'.join(cleaned_lines).strip()

    # Rule 9: Max length of genuine title is 120 characters
    if len(final_text) > 120:
        return ""

    return final_text


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
    Crawl past messages across active channels to find previously undelivered videos
    whenever no new videos are available.
    """
    stats = await get_collector_stats()
    current_queue = stats.get("queue_count", 0)
    if current_queue >= max_queue_buffer:
        logger.info(f"📦 Queue already has {current_queue} videos (Target: {max_queue_buffer}). Backlog crawl skipped.")
        return 0

    collect_all = await get_setting("collect_from_all_joined", "1")
    total_added = 0
    min_duration = await get_min_video_duration()

    if collect_all == "1":
        logger.info("🔍 Auto-crawling across joined channels & groups for previous undelivered videos...")
        try:
            async for dialog in client.iter_dialogs(limit=60):
                if current_queue + total_added >= max_queue_buffer:
                    break
                if not (dialog.is_channel or dialog.is_group):
                    continue

                chat_id = dialog.id
                chat_entity = dialog.entity
                chat_username = (getattr(chat_entity, "username", "") or "").lower()
                chat_title = getattr(dialog, "name", "") or getattr(chat_entity, "title", "Unknown")

                # Strictly exclude delivery channels and discussion groups
                if await is_delivery_chat(chat_id, chat_username, chat_title):
                    continue

                # Check if admin deactivated this channel
                if await is_channel_deactivated(chat_id, chat_username):
                    continue

                # Auto register channel in DB for dashboard visibility
                await auto_register_source_channel(chat_id, chat_title, chat_username)

                # Backlog pagination: scan backwards from last_scanned_id if set
                last_offset = await get_channel_last_scanned_id(chat_id)
                kwargs = {"limit": limit_per_source}
                if last_offset > 0:
                    kwargs["offset_id"] = last_offset

                min_seen_id = None
                async for msg in client.iter_messages(chat_entity, **kwargs):
                    if current_queue + total_added >= max_queue_buffer:
                        break
                    if min_seen_id is None or msg.id < min_seen_id:
                        min_seen_id = msg.id

                    if _is_video_message(msg, min_duration=min_duration):
                        media_id = get_media_unique_id(msg)
                        clean_caption = clean_source_caption(msg.text or "")
                        qid = await add_queue_item(chat_id, msg.id, str(msg.id), clean_caption, media_id=media_id)
                        if qid:
                            total_added += 1

                # Update pagination pointer to continue from older messages next time
                if min_seen_id is not None:
                    if min_seen_id <= 1:
                        await update_channel_last_scanned_id(chat_id, 0)
                    else:
                        await update_channel_last_scanned_id(chat_id, min_seen_id)

        except Exception as e_dialogs:
            logger.error(f"Error during all-dialogs crawl: {e_dialogs}")

    else:
        # Crawl only specific registered channels
        sources_data = await get_source_channel_targets()
        rows = sources_data.get("rows", [])
        logger.info(f"🔍 Crawling registered {len(rows)} source channels for previous undelivered videos...")

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
                if await is_delivery_chat(chat_id, row.get("channel_username", ""), row.get("channel_title", "")):
                    continue

                last_offset = await get_channel_last_scanned_id(chat_id)
                kwargs = {"limit": limit_per_source}
                if last_offset > 0:
                    kwargs["offset_id"] = last_offset

                min_seen_id = None
                async for msg in client.iter_messages(entity, **kwargs):
                    if current_queue + total_added >= max_queue_buffer:
                        break
                    if min_seen_id is None or msg.id < min_seen_id:
                        min_seen_id = msg.id

                    if _is_video_message(msg, min_duration=min_duration):
                        media_id = get_media_unique_id(msg)
                        clean_caption = clean_source_caption(msg.text or "")
                        qid = await add_queue_item(chat_id, msg.id, str(msg.id), clean_caption, media_id=media_id)
                        if qid:
                            total_added += 1

                if min_seen_id is not None:
                    if min_seen_id <= 1:
                        await update_channel_last_scanned_id(chat_id, 0)
                    else:
                        await update_channel_last_scanned_id(chat_id, min_seen_id)

            except Exception as e:
                logger.error(f"Error crawling source channel '{target}': {e}")

    logger.info(f"✅ Crawl complete. Added {total_added} undelivered videos to MySQL queue (Total queue: {current_queue + total_added}).")
    return total_added


@client.on(events.NewMessage)
async def handle_new_message(event: events.NewMessage.Event) -> None:
    """Real-time listener for incoming new videos from joined channels/groups."""
    msg = event.message
    if not msg:
        return

    is_active = await get_setting("is_collector_active", "1")
    if is_active != "1":
        return

    min_duration = await get_min_video_duration()
    if not _is_video_message(msg, min_duration=min_duration):
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

    # Strictly protect delivery channel(s) and their discussion groups from self-collection
    if await is_delivery_chat(chat_id, chat_username, chat_title):
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

    media_id = get_media_unique_id(msg)
    clean_caption = clean_source_caption(msg.text or "")
    qid = await add_queue_item(chat_id, msg.id, str(msg.id), clean_caption, media_id=media_id)
    if qid:
        logger.info(f"📝 Video queued in MySQL with ID: #{qid} (Media ID: {media_id})")
        # Auto-sync newly collected video to website portal (maintaining latest 10 videos FIFO)
        try:
            await sync_video_to_portal_vault(msg, clean_caption)
        except Exception as e_sync:
            logger.warning(f"Portal sync notice: {e_sync}")


async def sync_video_to_portal_vault(msg, caption: str) -> None:
    """Auto-sync newly collected video to website portal (maintains latest 10 videos FIFO)."""
    import random
    
    # Duration
    dur_sec = get_video_duration(msg) or 320
    mins = int(dur_sec // 60)
    secs = int(dur_sec % 60)
    duration_str = f"{mins:02d}:{secs:02d}"

    # Enticing English category & title
    categories = ["exclusive", "desi", "vip", "live", "viral"]
    chosen_cat = random.choice(categories)
    
    title_cand = ""
    if caption and len(caption.strip()) > 5:
        title_cand = caption.strip().split("\n")[0][:60]
        title_cand = re.sub(r"https?://\S+|t\.me/\S+|@[a-zA-Z0-9_]+", "", title_cand).strip()

    if not title_cand:
        titles_pool = [
            f"Hot Viral Leak #{msg.id} Full 1080p",
            f"Private Couple Bedroom Secret MMS #{msg.id}",
            f"VIP Luxury Suite Uncensored Cam Session #{msg.id}",
            f"Late Night Live 1-on-1 Web Show #{msg.id}",
            f"College Friends Private Night Party MMS #{msg.id}",
            f"Exclusive Uncut Private Call Recording #{msg.id}",
            f"VIP Penthouse Model Hidden Cam #{msg.id}",
            f"Trending Desi Viral Video Full HD #{msg.id}"
        ]
        title_cand = random.choice(titles_pool)

    # Rotating model posters from assets/img
    posters = [
        "assets/img/mitu.jpg", "assets/img/sadia.jpg", "assets/img/riya.jpg",
        "assets/img/tania.jpg", "assets/img/mim.jpg", "assets/img/nusrat.jpg",
        "assets/img/video1.jpg", "assets/img/video2.jpg", "assets/img/video3.jpg"
    ]
    thumb = random.choice(posters)

    # Reliable video streams
    stream_samples = [
        "https://www.w3schools.com/html/mov_bbb.mp4",
        "https://www.w3schools.com/html/movie.mp4",
        "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
        "https://vjs.zencdn.net/v/oceans.mp4"
    ]
    # Auto-generate high-converting Google SEO keywords
    kw_parts = [
        title_cand,
        f"{chosen_cat} viral video",
        "telegram leak link",
        "uncut full video",
        "mms video download",
        "private tape 1080p"
    ]
    seo_keywords = ", ".join(kw_parts)

    await add_portal_video_auto_rotate(
        title=title_cand,
        category_slug=chosen_cat,
        video_url=v_url,
        thumb_url=thumb,
        duration=duration_str,
        keywords=seo_keywords
    )
    logger.info(f"✨ Portal updated: '{title_cand}' added (Latest 10 videos rotated with SEO keywords).")



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
    Sequential Batch Delivery Worker:
    Delivers 3 videos (or configured batch size) together every cycle from the MySQL queue,
    and immediately deletes each video record from the database once delivered.
    """
    logger.info("🚀 Sequential Batch Delivery Worker initialized (Default: 3 videos per batch).")
    # Initial pause to allow client and startup crawl to finish
    await asyncio.sleep(5)

    while True:
        try:
            is_active = await get_setting("is_collector_active", "1")
            if is_active != "1":
                await asyncio.sleep(10)
                continue

            # Batch size setting (default: 3 videos together)
            try:
                batch_size = int(await get_setting("delivery_batch_size", "3"))
            except Exception:
                batch_size = 3
            if batch_size < 1:
                batch_size = 3

            deliveries = await get_delivery_channel_targets()
            if not deliveries:
                logger.warning("⚠️ No active delivery channels configured! Skipping delivery cycle.")
                await asyncio.sleep(60)
                continue

            delivered_in_this_batch = 0
            attempts = 0
            max_attempts = max(10, batch_size * 5)

            while delivered_in_this_batch < batch_size and attempts < max_attempts:
                attempts += 1

                # Fetch next video in FIFO order
                item = await get_next_queue_item()
                if not item:
                    logger.info("📭 Video queue is empty. Running crawl on source channels to replenish...")
                    added = await crawl_source_channels(limit_per_source=60)
                    if added > 0:
                        item = await get_next_queue_item()

                if not item:
                    # No more items available even after crawl
                    break

                queue_id = item["id"]
                source_chat = item["source_chat_id"]
                msg_id = item["source_message_id"]
                stored_media_id = item.get("media_id")
                batch_label = f"[{delivered_in_this_batch + 1}/{batch_size}]"
                logger.info(f"📦 Batch {batch_label} | Next in queue: #{queue_id} (Source Chat: {source_chat}, Msg ID: {msg_id})")

                # If this media_id was already delivered previously, skip immediately without waiting
                if stored_media_id and await is_media_processed(stored_media_id):
                    logger.warning(f"⚠️ Video content (Media ID: {stored_media_id}) already delivered previously! Skipping duplicate queue #{queue_id}.")
                    await delete_queue_item(queue_id)
                    await mark_message_processed(source_chat, msg_id, stored_media_id)
                    continue

                delivery_success = False
                current_media_id = stored_media_id
                try:
                    # Retrieve the original message
                    orig_msg = await client.get_messages(source_chat, ids=msg_id)
                    min_duration = await get_min_video_duration()
                    if not orig_msg or not _is_video_message(orig_msg, min_duration=min_duration):
                        dur = get_video_duration(orig_msg) if orig_msg else None
                        logger.warning(f"⚠️ Queue item #{queue_id} (Msg {msg_id} in {source_chat}) is not a genuine video >= {min_duration}s (Duration: {dur}s). Skipping immediately...")
                        await delete_queue_item(queue_id)
                        await mark_message_processed(source_chat, msg_id, stored_media_id)
                        continue

                    current_media_id = get_media_unique_id(orig_msg) or stored_media_id

                    # Extra check: If current_media_id was already delivered previously, skip immediately
                    if current_media_id and await is_media_processed(current_media_id):
                        logger.warning(f"⚠️ Video content (Media ID: {current_media_id}) already delivered previously! Skipping duplicate queue #{queue_id}.")
                        await delete_queue_item(queue_id)
                        await mark_message_processed(source_chat, msg_id, current_media_id)
                        continue

                    custom_caption = await get_setting("custom_caption", "")
                    if custom_caption and custom_caption.strip():
                        caption = custom_caption.strip()
                    else:
                        raw_caption = orig_msg.text or item.get("caption") or ""
                        caption = clean_source_caption(raw_caption)

                    for target in deliveries:
                        try:
                            logger.info(f"🚀 Delivering video {batch_label} #{queue_id} to channel: {target}...")
                            res = await deliver_video_message(orig_msg, target, caption)
                            if res:
                                delivery_success = True
                                logger.info(f"✅ Video #{queue_id} successfully delivered to: {target}")
                                if FORWARD_DELAY_SECONDS > 0:
                                    await asyncio.sleep(FORWARD_DELAY_SECONDS)
                        except Exception as e_deliv:
                            logger.error(f"❌ Failed to send video to delivery target '{target}': {e_deliv}")

                except Exception as e_proc:
                    logger.error(f"❌ Error retrieving video for queue #{queue_id}: {e_proc}")
                    await delete_queue_item(queue_id)
                    await mark_message_processed(source_chat, msg_id, stored_media_id)
                    continue

                # IMMEDIATELY DELETE FROM MYSQL QUEUE TABLE
                await delete_queue_item(queue_id)
                await mark_message_processed(source_chat, msg_id, current_media_id)

                if delivery_success:
                    await increment_forwarded_count()
                    delivered_in_this_batch += 1
                    logger.info(f"🗑️ Video #{queue_id} deleted from MySQL. Progress: {delivered_in_this_batch}/{batch_size} delivered in this batch.")

                    # Short safety pause between videos in the same batch
                    if delivered_in_this_batch < batch_size:
                        await asyncio.sleep(3)

            if delivered_in_this_batch > 0:
                # Calculate sleep time based on interval setting (default: 15 minutes)
                try:
                    interval_min = int(await get_setting("delivery_interval_minutes", "15"))
                except Exception:
                    interval_min = 15

                wait_seconds = max(10, interval_min * 60)
                logger.info(f"⏳ Batch complete ({delivered_in_this_batch} videos delivered)! Waiting {interval_min} minutes ({wait_seconds}s) for next batch delivery...")

                # Interruptible sleep in 5-second intervals to allow manual "Send Now" button trigger
                for _ in range(wait_seconds // 5):
                    await asyncio.sleep(5)
                    trigger_now = await get_setting("trigger_immediate_send", "0")
                    if trigger_now == "1":
                        await set_setting("trigger_immediate_send", "0")
                        logger.info("⚡ Immediate delivery triggered by Admin! Delivering next batch now...")
                        break
            else:
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

    # Purge any delivery items that accidentally entered queue
    await purge_delivery_items_from_queue()

    # Auto-resolve delivery channels (e.g. @darkromance4u)
    deliveries = await get_delivery_channel_targets()
    for d in deliveries:
        try:
            ent = await client.get_entity(d)
            logger.info(f"🎯 Delivery channel confirmed: {getattr(ent, 'title', d)} [ID: {ent.id}]")
            if isinstance(d, str):
                await update_channel_id_by_username(d, ent.id)
            # Detect linked discussion group for exclusion
            try:
                from telethon.tl.functions.channels import GetFullChannelRequest
                from video_collector.database import record_excluded_delivery_group
                full_chan = await client(GetFullChannelRequest(ent))
                linked_id = getattr(full_chan.full_chat, "linked_chat_id", None)
                if linked_id:
                    logger.info(f"🔗 Linked discussion group detected for exclusion: ID {linked_id}")
                    await record_excluded_delivery_group(linked_id, "Dark Romance Discussion Group")
            except Exception:
                pass
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

    # Start 15-minute sequential delivery worker
    asyncio.create_task(delivery_worker_loop())

    logger.info("🎯 Video Collector is now running! (1 video every 15 mins -> @darkromance4u)")
    await client.run_until_disconnected()


if __name__ == "__main__":
    client.loop.run_until_complete(main())
