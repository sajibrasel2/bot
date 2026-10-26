"""
Spam protection module.
Features:
  - Auto-delete  : বটের নিজস্ব সতর্কতা মেসেজ ৩ মিনিট (১৮০ সেকেন্ড) পর অটো ডিলিট
  - Anti-flood   : rate limit — অতিরিক্ত মেসেজে ১ মিনিট মিউট
  - Anti-link    : URL/invite লিংক ডিলিট
  - Bad words    : নিষিদ্ধ শব্দ ডিলিট + ৩বার ব্যবহারে ১ মিনিট মিউট
  - Anti-forward : forwarded মেসেজ ব্লক (/antiforward on|off)

Admin commands:
  /antiflood on|off
  /antilink  on|off
  /badwords  on|off
  /addbadword <word>
  /delbadword <word>
  /badwordlist
  /antiforward on|off
"""

import re
import time
import asyncio
import logging
import urllib.parse
import html
import unicodedata
from collections import defaultdict

logger = logging.getLogger(__name__)

from telegram import Update, ChatPermissions, Message, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CommandHandler, filters
from telegram.helpers import mention_html

from database import (
    get_chat_settings, update_chat_setting, upsert_user, update_chat_info,
    get_user_invite_count
)
from modules.utils import is_admin, admin_only
from config import MAX_FLOOD_MESSAGES, FLOOD_WINDOW_SECONDS

# ── In-memory trackers ────────────────────────────
# Flood: {chat_id: {user_id: [timestamps]}}
_flood: dict = defaultdict(lambda: defaultdict(list))

# Bad word strike tracker: {chat_id: {user_id: strike_count}}
# Resets when mute is applied or after BADWORD_STRIKE_WINDOW seconds
_badword_strikes: dict = defaultdict(lambda: defaultdict(int))
_badword_strike_time: dict = defaultdict(lambda: defaultdict(float))

# Anti-link strike tracker: {chat_id: {user_id: strike_count}}
# Resets when mute is applied or after ANTILINK_STRIKE_WINDOW seconds
_antilink_strikes: dict = defaultdict(lambda: defaultdict(int))
_antilink_strike_time: dict = defaultdict(lambda: defaultdict(float))

# Anti-forward strike tracker: {chat_id: {user_id: strike_count}}
# Resets when mute is applied or after ANTIFORWARD_STRIKE_WINDOW seconds
_antiforward_strikes: dict = defaultdict(lambda: defaultdict(int))
_antiforward_strike_time: dict = defaultdict(lambda: defaultdict(float))

# Anti-Bio-Link cache & alert debounce tracker
# User bio cache: {user_id: (timestamp, bio_str_or_none)}
_user_bio_cache: dict = {}
BIO_CACHE_TTL = 180  # 3 minutes cache TTL
_bio_alert_time: dict = defaultdict(lambda: defaultdict(float))
_charlimit_alert_time: dict = defaultdict(lambda: defaultdict(float))

DEFAULT_BIOLINK_WHITELIST = "https://t.me/darkromance4u, https://t.me/darkfantasyloverzone, https://t.me/mastiunlimitedzone"

BIO_URL_PATTERN = re.compile(
    r"(https?://[^\s]+|ftp://[^\s]+|www\.[^\s]+|t\.me/[^\s]+|telegram\.me/[^\s]+|telegram\.dog/[^\s]+|tg://[^\s]+|"
    r"wa\.me/[^\s]+|discord\.gg/[^\s]+|bit\.ly/[^\s]+|tinyurl\.com/[^\s]+|cutt\.ly/[^\s]+|rb\.gy/[^\s]+|is\.gd/[^\s]+|"
    r"\b[a-zA-Z0-9.-]+\.(com|net|org|io|me|info|xyz|site|top|online|club|live|vip|link|app|co|bd|in|gg|ly|be|cc|ru|biz|tech|store|shop|pro|win|fun|icu|page)\b(/[^\s]*)?)",
    re.IGNORECASE
)
BIO_MENTION_PATTERN = re.compile(r"(?<!\w)@([a-zA-Z0-9_]{4,32})", re.IGNORECASE)

def _normalize_bio_target(target: str) -> str:
    target = target.strip().lower()
    target = re.sub(r"^https?://", "", target)
    target = re.sub(r"^www\.", "", target)
    target = re.sub(r"^(t\.me|telegram\.me|telegram\.dog)/", "", target)
    target = target.lstrip("@").strip("/")
    return target

def _parse_biolink_whitelist(whitelist_raw: str | None) -> set:
    if not whitelist_raw or not whitelist_raw.strip():
        whitelist_raw = DEFAULT_BIOLINK_WHITELIST
    items = set()
    tokens = re.split(r"[,\n\r\t]+", whitelist_raw)
    for t in tokens:
        t = t.strip()
        if not t:
            continue
        items.add(t.lower())
        norm = _normalize_bio_target(t)
        if norm:
            items.add(norm)
    return items

def check_bio_unauthorized(bio: str | None, whitelist_raw: str | None) -> tuple[bool, list[str]]:
    if not bio or not bio.strip():
        return False, []
    
    whitelist = _parse_biolink_whitelist(whitelist_raw)
    unauthorized = []
    
    # 1. Check URLs in bio
    for match in BIO_URL_PATTERN.finditer(bio):
        raw_url = match.group(0).strip(".,!?;:()[]{}")
        norm = _normalize_bio_target(raw_url)
        if raw_url.lower() in whitelist or norm in whitelist:
            continue
        if any(norm == w or norm.startswith(w + "/") for w in whitelist if w):
            continue
        unauthorized.append(raw_url)
        
    # 2. Check @mentions in bio
    for match in BIO_MENTION_PATTERN.finditer(bio):
        handle = match.group(1).lower()
        if handle in whitelist or f"@{handle}" in whitelist:
            continue
        unauthorized.append(f"@{handle}")
        
    return len(unauthorized) > 0, unauthorized

async def get_user_bio(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    now = time.time()
    cached = _user_bio_cache.get(user_id)
    if cached and (now - cached[0] < BIO_CACHE_TTL):
        return cached[1]
    
    try:
        chat_obj = await context.bot.get_chat(user_id)
        bio = getattr(chat_obj, "bio", None) or ""
        _user_bio_cache[user_id] = (now, bio)
        return bio
    except Exception as e:
        logger.debug(f"Failed to fetch bio for user {user_id}: {e}")
        _user_bio_cache[user_id] = (now - BIO_CACHE_TTL + 60, None)
        return None

BADWORD_STRIKE_WINDOW      = 300     # ৫ মিনিটের মধ্যে strike expiry
ANTILINK_STRIKE_WINDOW     = 3600    # ১ ঘণ্টার মধ্যে strike expiry
ANTILINK_STRIKE_LIMIT      = 3       # সর্বোচ্চ ৩ বার লিংক দিলে মিউট
ANTILINK_MUTE_DURATION     = 3600    # ১ ঘণ্টা (৩৬০০ সেকেন্ড) মিউট

ANTIFORWARD_STRIKE_WINDOW  = 3600    # ১ ঘণ্টার মধ্যে strike expiry
ANTIFORWARD_STRIKE_LIMIT   = 3       # সর্বোচ্চ ৩ বার ফরোয়ার্ড দিলে মিউট
ANTIFORWARD_MUTE_DURATION  = 3600    # ১ ঘণ্টা (৩৬০০ সেকেন্ড) মিউট

BOT_MSG_AUTO_DELETE        = 30     # বটের সতর্কতা মেসেজ ৩০ সেকেন্ড পর ডিলিট হবে

URL_PATTERN = re.compile(
    r"(https?://|ftp://|www\.|t\.me/|telegram\.me/|telegram\.dog/|tg://|"
    r"wa\.me/|discord\.gg/|bit\.ly/|tinyurl\.com/|cutt\.ly/|rb\.gy/|is\.gd/|"
    r"\b[a-zA-Z0-9.-]+\.(com|net|org|io|me|info|xyz|site|top|online|club|live|vip|link|app|co|bd|in|gg|ly|be|cc|ru|biz|tech|store|shop|pro|win|fun|icu|page)\b(/[^\s]*)?)",
    re.IGNORECASE
)


async def is_whitelisted_link_admin(chat, user_id: int, username: str, whitelist_raw: str) -> bool:
    """Checks if an admin is whitelisted/permitted to post links in the group."""
    if not user_id:
        return False

    # 1. Bot owner / super admin IDs from config
    from config import OWNER_ID
    if user_id in (OWNER_ID, 8904339611, 5888198325):
        return True

    # 2. Database bot admins
    try:
        from database import is_bot_admin
        if await is_bot_admin(user_id):
            return True
    except Exception:
        pass

    # 3. Check chat creator / owner
    try:
        member = await chat.get_member(user_id)
        if member and member.status in (ChatMember.OWNER, "creator"):
            return True
    except Exception:
        pass

    # 4. Check whitelist string (User IDs or Usernames)
    if whitelist_raw:
        tokens = [t.strip().lower().lstrip("@") for t in re.split(r"[\s,;]+", str(whitelist_raw)) if t.strip()]
        if str(user_id) in tokens:
            return True
        if username and username.lower().lstrip("@") in tokens:
            return True

    return False


def _clean_flood(timestamps: list, now: float) -> list:
    return [t for t in timestamps if now - t < FLOOD_WINDOW_SECONDS]


MAIN_DARK_ROMANCE_GROUP = "https://t.me/darkfantasyloverzone"
BACKUP_MASTI_GROUP = "https://t.me/mastiunlimitedzone"

try:
    from telegram import LinkPreviewOptions
    _DISABLE_PREVIEW = {"link_preview_options": LinkPreviewOptions(is_disabled=True)}
except Exception:
    _DISABLE_PREVIEW = {"disable_web_page_preview": True}

def _build_action_buttons(chat_id: int, user_id: int, chat_title: str) -> InlineKeyboardMarkup:
    """Action buttons to drive engagement and show member invite stats."""
    share_text = urllib.parse.quote(f"🔥 Join our exclusive group & live video chat! 🔞👉 {MAIN_DARK_ROMANCE_GROUP}")
    share_url = f"https://t.me/share/url?url={MAIN_DARK_ROMANCE_GROUP}&text={share_text}"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(text="👥 Add Members", url=share_url),
            InlineKeyboardButton(text="🔥 Group 1", url=MAIN_DARK_ROMANCE_GROUP),
            InlineKeyboardButton(text="🔥 Group 2", url=BACKUP_MASTI_GROUP)
        ],
        [
            InlineKeyboardButton(text="📊 My Progress", callback_data=f"myinv_{user_id}"),
            InlineKeyboardButton(text="🏆 Top Inviters", callback_data=f"topinv_{chat_id}")
        ]
    ])


async def _auto_delete(message: Message, delay: int = BOT_MSG_AUTO_DELETE) -> None:
    """নির্দিষ্ট সময় পর বটের মেসেজ অটো ডিলিট করে।"""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


async def _send_and_delete(context, chat_id: int, text: str, reply_markup=None, delay: int = BOT_MSG_AUTO_DELETE) -> None:
    """মেসেজ পাঠাও এবং নির্দিষ্ট সময় পরে ডিলিট করো।"""
    try:
        sent = await context.bot.send_message(
            chat_id, text, parse_mode="HTML", reply_markup=reply_markup,
            **_DISABLE_PREVIEW
        )
        asyncio.create_task(_auto_delete(sent, delay=delay))
    except Exception:
        pass


async def _mute_user(context, chat_id: int, user, duration: int = 60) -> None:
    """ব্যবহারকারীকে নির্দিষ্ট সময়ের জন্য মিউট করে।"""
    until = int(time.time()) + duration
    await context.bot.restrict_chat_member(
        chat_id, user.id,
        ChatPermissions(can_send_messages=False),
        until_date=until
    )



def is_forward_or_channel_post(msg: Message, chat) -> tuple[bool, str]:
    """
    Checks if a message is forwarded from any user/chat/channel, or posted as an external channel.
    Returns (is_forwarded, reason).
    """
    if not msg:
        return False, ""

    # 1. Automatic forwards from group's own linked channel are allowed
    if getattr(msg, "is_automatic_forward", False):
        return False, ""

    # 2. External channel sender (posting as a channel)
    sender_chat = getattr(msg, "sender_chat", None)
    if sender_chat:
        # Group itself (anonymous admin) is allowed
        if sender_chat.id == chat.id:
            return False, ""
        # Linked discussion channel is allowed
        linked_id = getattr(chat, "linked_chat_id", None)
        if linked_id and sender_chat.id == linked_id:
            return False, ""
        # Any other channel posting in the group is blocked
        return True, "channel_sender"

    # 3. Telegram Bot API 7.0+ MessageOrigin (User, HiddenUser, Chat, Channel)
    origin = getattr(msg, "forward_origin", None)
    if origin is not None:
        origin_type = getattr(origin, "type", "")
        if origin_type == "channel":
            return True, "channel_forward"
        return True, "forward_origin"

    # 4. Legacy Telegram forward attributes
    if getattr(msg, "forward_from_chat", None) is not None:
        from_chat = getattr(msg, "forward_from_chat", None)
        if getattr(from_chat, "type", "") == "channel":
            return True, "channel_forward"
        return True, "forward_legacy"

    if (
        getattr(msg, "forward_date", None) is not None or
        getattr(msg, "forward_from", None) is not None or
        getattr(msg, "forward_sender_name", None) is not None
    ):
        return True, "forward_legacy"

    # 5. Telegram Stories
    if getattr(msg, "story", None) is not None:
        return True, "story"

    return False, ""


# ── Main filter ───────────────────────────────────

async def spam_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """সব মেসেজ চেক করে — forwards, flood, links, bad words, media locks।"""
    msg = update.message or update.edited_message
    if not msg:
        return

    chat = update.effective_chat
    if not chat:
        return

    # Track video messages for 1-click group video cleaner
    if getattr(msg, "video", None) or getattr(msg, "video_note", None):
        try:
            from database import record_group_video
            asyncio.create_task(record_group_video(chat.id, msg.message_id, update.effective_user.id if update.effective_user else None))
        except Exception:
            pass

    settings = await get_chat_settings(chat.id)
    user = msg.from_user or update.effective_user

    # ── 0. Admin Anti-Link & Anti-Promo Protection (মনোনীত অ্যাডমিন ছাড়া অন্য অ্যাডমিনদের লিংক ব্লক) ────
    user_is_admin = await is_admin(update)
    if user_is_admin:
        if settings.get("admin_antilink_enabled", 1):
            user_id = user.id if user else 0
            username = user.username or ""
            wl_raw = settings.get("admin_link_whitelist") or ""

            is_whitelisted = await is_whitelisted_link_admin(chat, user_id, username, wl_raw)
            if not is_whitelisted:
                content_text = (msg.text or msg.caption or "").strip()
                has_admin_link = False

                # 1. Regex check on text or caption
                if content_text and URL_PATTERN.search(content_text):
                    has_admin_link = True

                # 2. Telegram entities (url, text_link)
                if not has_admin_link:
                    entities = list(msg.entities or []) + list(msg.caption_entities or [])
                    for ent in entities:
                        if ent.type in ("url", "text_link"):
                            has_admin_link = True
                            break

                # 3. Inline keyboard buttons with URLs
                if not has_admin_link and msg.reply_markup and msg.reply_markup.inline_keyboard:
                    for row in msg.reply_markup.inline_keyboard:
                        for btn in row:
                            if getattr(btn, "url", None):
                                has_admin_link = True
                                break

                # 4. Forwarded channel posts / promotions
                if not has_admin_link:
                    is_fwd, fwd_reason = is_forward_or_channel_post(msg, chat)
                    if is_fwd and (fwd_reason == "channel_forward" or getattr(msg, "forward_from_chat", None)):
                        has_admin_link = True

                # 5. External channel sender
                if not has_admin_link and msg.sender_chat and msg.sender_chat.id != chat.id:
                    has_admin_link = True

                if has_admin_link:
                    # SILENT DELETION: Deleted immediately without any bot reply / warning!
                    try:
                        await msg.delete()
                        logger.info(f"🚫 Silently deleted unauthorized link/promo from admin {user_id} (@{username}) in chat {chat.id}")
                    except Exception as e:
                        logger.debug(f"Could not delete admin link: {e}")
                    return

        # Whitelisted admins or normal non-link admin messages are exempt from member limits
        return

    # ── 1. Anti-forward & Anti-Channel Protection (কঠোর ফরোয়ার্ড ও চ্যানেল ব্লক) ────
    forward_blocked = bool(
        settings.get("antiforward_enabled", 1) or
        settings.get("lock_messages", 0)
    )

    is_fwd, fwd_reason = is_forward_or_channel_post(msg, chat)
    if forward_blocked and is_fwd:
        # Delete forwarded message / channel post immediately
        try:
            await msg.delete()
        except Exception:
            pass

        # Handle external channel sender (posting as a channel)
        if fwd_reason == "channel_sender" and msg.sender_chat:
            try:
                await context.bot.ban_chat_sender_chat(chat_id=chat.id, sender_chat_id=msg.sender_chat.id)
                logger.info(f"🚫 Banned external channel {msg.sender_chat.id} from chat {chat.id}")
            except Exception as e:
                logger.debug(f"Could not ban sender chat: {e}")

            channel_title = html.escape(getattr(msg.sender_chat, "title", "Channel") or "Channel")
            alert_text = (
                f"📵 <b>Channel Posts Prohibited!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📢 <b>Channel:</b> {channel_title}\n"
                f"🆔 <b>Channel ID:</b> <code>{msg.sender_chat.id}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔒 Posting as a channel or sending channel messages is not permitted."
            )
            await _send_and_delete(context, chat.id, alert_text, delay=BOT_MSG_AUTO_DELETE)
            return

        # Handle standard user forward (channel forward, user forward, media forward, story)
        user = msg.from_user or update.effective_user
        if user:
            now = time.time()
            last_strike = _antiforward_strike_time[chat.id][user.id]
            if now - last_strike > ANTIFORWARD_STRIKE_WINDOW:
                _antiforward_strikes[chat.id][user.id] = 0

            _antiforward_strikes[chat.id][user.id] += 1
            _antiforward_strike_time[chat.id][user.id] = now
            strike_count = _antiforward_strikes[chat.id][user.id]

            reply_markup = _build_action_buttons(chat.id, user.id, chat.title or "")

            if strike_count >= ANTIFORWARD_STRIKE_LIMIT:
                _antiforward_strikes[chat.id][user.id] = 0
                try:
                    await _mute_user(context, chat.id, user, duration=ANTIFORWARD_MUTE_DURATION)
                except Exception:
                    pass

                action_desc = "channel posts" if fwd_reason == "channel_forward" else "forwarded messages"
                mute_alert = (
                    f"🚨 <b>Muted for 1 Hour!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>User:</b> {mention_html(user.id, user.first_name)} (<code>{user.id}</code>)\n"
                    f"🚫 <b>Violations:</b> <code>{strike_count}/{ANTIFORWARD_STRIKE_LIMIT}</code> (Strike Limit Exceeded)\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"⚠️ <i>You have been muted for <b>1 hour</b> due to repeatedly forwarding {action_desc}.</i>\n\n"
                    f"👉 <i>Please follow group rules after unmuting to avoid permanent penalties.</i>"
                )
                await _send_and_delete(
                    context, chat.id,
                    mute_alert,
                    reply_markup=reply_markup,
                    delay=BOT_MSG_AUTO_DELETE
                )
            else:
                strikes_left = ANTIFORWARD_STRIKE_LIMIT - strike_count
                if fwd_reason == "channel_forward":
                    warning_title = "📵 <b>Channel Forwards Prohibited!</b>"
                    warning_desc = "Forwarding posts or media from channels is strictly prohibited. Your message has been removed."
                else:
                    warning_title = "📵 <b>Forwarded Messages Prohibited!</b>"
                    warning_desc = "Forwarding messages, media, or stories is strictly prohibited. Your message has been removed."

                alert_text = (
                    f"{warning_title}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>User:</b> {mention_html(user.id, user.first_name)} (<code>{user.id}</code>)\n"
                    f"⚠️ <b>Warning:</b> <code>{strike_count}/{ANTIFORWARD_STRIKE_LIMIT}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔒 {warning_desc}\n\n"
                    f"⚠️ <i>Note: 3 violations will result in a <b>1-hour mute</b>. (Remaining: <b>{strikes_left}</b>)</i>"
                )
                await _send_and_delete(
                    context, chat.id,
                    alert_text,
                    reply_markup=reply_markup,
                    delay=BOT_MSG_AUTO_DELETE
                )
        return

    # If not a forward, require a valid user for tracking other features
    user = msg.from_user or update.effective_user
    if not user:
        return

    # Record user and chat title in database for accurate stats
    asyncio.create_task(upsert_user(user.id, chat.id, user.username or "", user.first_name or ""))
    if chat.type != "private" and chat.title:
        asyncio.create_task(update_chat_info(chat.id, title=chat.title))

    # ── 100 Characters Limit Protection (১০০ অক্ষরের বেশি মেসেজ প্রতিরোধ) ───────────
    max_chars = int(settings.get("max_message_chars") or 100)
    if max_chars > 0:
        text_content = (msg.text or msg.caption or "").strip()
        if text_content and len(text_content) > max_chars:
            try:
                await msg.delete()
            except Exception:
                pass

            now = time.time()
            last_alert = _charlimit_alert_time[chat.id][user.id]
            if now - last_alert > 8:
                _charlimit_alert_time[chat.id][user.id] = now
                char_count = len(text_content)
                alert_text = (
                    f"⚠️ <b>Message Too Long! / মেসেজ অতিরিক্ত বড়!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>User:</b> {mention_html(user.id, user.first_name)} (<code>{user.id}</code>)\n"
                    f"📏 <b>Length:</b> <code>{char_count}</code> / <b>{max_chars} characters max</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🚫 <i>১০০ অক্ষরের বেশি মেসেজ পাঠানো নিষিদ্ধ। অনুগ্রহ করে সংক্ষেপে লিখুন।</i>\n"
                    f"ℹ️ <i>Messages exceeding {max_chars} characters are restricted. Please keep it brief.</i>"
                )
                await _send_and_delete(context, chat.id, alert_text, delay=BOT_MSG_AUTO_DELETE)
            return

    # ── Anti-Bio-Link (অননুমোদিত প্রোফাইল বায়ো লিংক প্রটেকশন) ────────────────
    if settings.get("antibiolink_enabled", 1):
        user_bio = await get_user_bio(user.id, context)
        if user_bio:
            wl_raw = settings.get("antibiolink_whitelist")
            is_unauth, bad_links = check_bio_unauthorized(user_bio, wl_raw)
            if is_unauth:
                try:
                    await msg.delete()
                except Exception:
                    pass

                now = time.time()
                last_alert = _bio_alert_time[chat.id][user.id]
                if now - last_alert > 15:
                    _bio_alert_time[chat.id][user.id] = now
                    alert_text = (
                        f"⚠️ <b>বায়ো লিংক নিষিদ্ধ!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 {mention_html(user.id, user.first_name)} (<code>{user.id}</code>)\n"
                        f"🔒 আপনার প্রোফাইল বায়োতে অননুমোদিত লিংক থাকায় মেসেজ মুছে দেওয়া হয়েছে।"
                    )
                    await _send_and_delete(context, chat.id, alert_text, delay=5)
                return

    # ── Anti-flood (স্বাভাবিক ফ্লাড প্রটেকশন) ──────────────────────────────────
    if settings.get("antiflood_enabled", 0):
        now   = time.time()
        times = _flood[chat.id][user.id]
        times = _clean_flood(times, now)
        times.append(now)
        _flood[chat.id][user.id] = times

        if len(times) >= MAX_FLOOD_MESSAGES:
            _flood[chat.id][user.id] = []
            try:
                await _mute_user(context, chat.id, user, 60)
                try:
                    await msg.delete()
                except Exception:
                    pass
                await _send_and_delete(
                    context, chat.id,
                    f"🚨 <b>Flood Warning!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 {mention_html(user.id, user.first_name)} (<code>{user.id}</code>)\n"
                    f"⚡ <i>Sending messages too quickly!</i>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔇 Muted for <b>1 minute</b>."
                )
            except Exception:
                pass
            return

    # ── Anti-link / Anti-Promo (১০ জন মেম্বার অ্যাড করলে অটোমেটিক লিংক ও প্রমোশন অনুমতি) ───────────
    if settings.get("antilink_enabled", 0):
        content_text = (msg.text or msg.caption or "").strip()
        has_link = False
        bot_uname = (context.bot.username or "").lower()

        # 1. Regex check on text or caption for actual web links / invite URLs
        if content_text:
            if URL_PATTERN.search(content_text):
                has_link = True

        # 2. Check Telegram entities (url and text_link only — allowing member mentions)
        if not has_link:
            entities = list(msg.entities or []) + list(msg.caption_entities or [])
            for ent in entities:
                if ent.type in ("url", "text_link"):
                    has_link = True
                    break

        if has_link:
            # Check user confirmed invites from database
            user_invites = await get_user_invite_count(chat.id, user.id)
            required_invites = int(settings.get("antilink_required_invites") or 10)

            if user_invites >= required_invites:
                # User has added 10 or more members -> AUTOMATICALLY PERMITTED!
                pass
            else:
                # User has not added 10 members -> Delete link/promo, track strike, warn or mute for 1 hour
                try:
                    await msg.delete()
                except Exception:
                    pass

                now = time.time()
                last_strike = _antilink_strike_time[chat.id][user.id]
                if now - last_strike > ANTILINK_STRIKE_WINDOW:
                    _antilink_strikes[chat.id][user.id] = 0

                _antilink_strikes[chat.id][user.id] += 1
                _antilink_strike_time[chat.id][user.id] = now
                strike_count = _antilink_strikes[chat.id][user.id]

                remaining_invites = max(0, required_invites - user_invites)

                reply_markup = _build_action_buttons(chat.id, user.id, chat.title or "")

                if strike_count >= ANTILINK_STRIKE_LIMIT:
                    # Strike limit reached (3 times) -> Mute user for 1 hour (3600s)
                    _antilink_strikes[chat.id][user.id] = 0
                    try:
                        await _mute_user(context, chat.id, user, duration=ANTILINK_MUTE_DURATION)
                    except Exception:
                        pass

                    mute_alert = (
                        f"🚨 <b>Muted for 1 Hour!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 <b>User:</b> {mention_html(user.id, user.first_name)} (<code>{user.id}</code>)\n"
                        f"🚫 <b>Violations:</b> <code>{strike_count}/{ANTILINK_STRIKE_LIMIT}</code> (Strike Limit Exceeded)\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"⚠️ <i>You have been muted for <b>1 hour</b> for sharing unauthorized links or promotions without meeting member add requirements ({required_invites} members).</i>"
                    )

                    await _send_and_delete(
                        context, chat.id,
                        mute_alert,
                        reply_markup=reply_markup,
                        delay=BOT_MSG_AUTO_DELETE
                    )
                else:
                    strikes_left = ANTILINK_STRIKE_LIMIT - strike_count
                    alert_text = (
                        f"🔗 <b>Links & Promotions Restricted!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 <b>User:</b> {mention_html(user.id, user.first_name)} (<code>{user.id}</code>)\n"
                        f"⚠️ <b>Warning:</b> <code>{strike_count}/{ANTILINK_STRIKE_LIMIT}</code>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🔒 Sharing links, channels, or usernames requires adding <b>{required_invites} members</b>.\n\n"
                        f"📊 <b>Your Progress:</b> <code>{user_invites}/{required_invites}</code> members\n"
                        f"👉 <i>Add <b>{remaining_invites} more member(s)</b> to unlock link sharing automatically!</i>\n\n"
                        f"⚠️ <i>Note: 3 violations will result in a <b>1-hour mute</b>. (Remaining: <b>{strikes_left}</b>)</i>"
                    )

                    await _send_and_delete(
                        context, chat.id,
                        alert_text,
                        reply_markup=reply_markup,
                        delay=BOT_MSG_AUTO_DELETE
                    )
                return

    # ── Bad words / Spam keywords (স্ট্রাইক সিস্টেম) ────────────
    check_text = (msg.text or msg.caption or "").strip()
    if settings.get("badwords_enabled", 1) and check_text:
        bw_raw = settings.get("badwords_list")
        if not bw_raw or not bw_raw.strip():
            bw_raw = (
                "ছেলে,ও ছেলে,স্কেমার,বাটপার,প্রতারক,chele,o chele,sele,o sele,chala,scammer,skeimer,skemer,scamer,skeimar,"
                "গ্রুপ লাগলে,ইনবক্স করো,ইনবক্সে আসো,ইনবক্স নক,ভিডিও সেল,সেল হবে,চ্যানেল সাবস্ক্রাইব,dm me,pm me,contact me,paid group,ভিডিও গ্রুপ"
            )
        bad_words = [unicodedata.normalize("NFC", w.strip().lower()) for w in bw_raw.split(",") if w.strip()]
        text_lower = unicodedata.normalize("NFC", check_text.lower())

        matched = False
        for bw in bad_words:
            if not bw:
                continue
            
            # Check if badword contains non-ASCII characters (e.g. Bengali script)
            chars_only = bw.replace("*", "")
            is_ascii = all(ord(c) < 128 for c in chars_only) if chars_only else True

            if "*" in bw:
                parts = [re.escape(p) for p in bw.split("*") if p]
                core_pat = r"[\s\W_]*".join(parts) if parts else r"\*"
                if is_ascii:
                    pattern = rf"\b{core_pat}\b"
                else:
                    pattern = core_pat
            else:
                if is_ascii:
                    # Use word boundaries for English to avoid matching parts of other words (e.g. "ass" in "class")
                    pattern = rf"\b{re.escape(bw)}\b"
                else:
                    # For non-ASCII (Bengali), substring presence
                    pattern = re.escape(bw)

            try:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    matched = True
                    break
            except Exception:
                if bw in text_lower:
                    matched = True
                    break

        if matched:
            try:
                await msg.delete()
            except Exception:
                pass

            # DB থেকে strike limit ও mute duration নাও
            strike_limit   = int(settings.get("badword_strike_limit")  or 3)
            mute_duration  = int(settings.get("badword_mute_duration") or 60)

            # Strike expiry check
            now = time.time()
            last_strike = _badword_strike_time[chat.id][user.id]
            if now - last_strike > BADWORD_STRIKE_WINDOW:
                _badword_strikes[chat.id][user.id] = 0

            _badword_strikes[chat.id][user.id]     += 1
            _badword_strike_time[chat.id][user.id]  = now
            strike_count = _badword_strikes[chat.id][user.id]

            if strike_count >= strike_limit:
                # strike_limit বারে মিউট
                _badword_strikes[chat.id][user.id] = 0
                mute_min = mute_duration // 60
                mute_text = f"{mute_min} minute(s)" if mute_duration >= 60 else f"{mute_duration} seconds"
                try:
                    await _mute_user(context, chat.id, user, mute_duration)
                except Exception:
                    pass
                await _send_and_delete(
                    context, chat.id,
                    f"🔇 <b>User Muted!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 {mention_html(user.id, user.first_name)}\n"
                    f"🚫 Muted for <b>{mute_text}</b> due to prohibited language.\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"<i>Please adhere to community standards.</i>"
                )
            else:
                remaining = strike_limit - strike_count
                await _send_and_delete(
                    context, chat.id,
                    f"⚠️ <b>Inappropriate Language Warning!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 {mention_html(user.id, user.first_name)}\n"
                    f"🚫 Strike: <b>{strike_count}/{strike_limit}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"<i>Please be respectful. Further violations will result in a temporary mute.</i>"
                )
            return



    # ── Media lock (DB-driven: lock_media_msg) ────
    if settings.get("lock_media_msg", 0):
        has_media = bool(
            msg.photo or msg.video or msg.document or
            msg.audio or msg.voice or msg.video_note or
            msg.animation
        )
        if has_media:
            try:
                await msg.delete()
            except Exception:
                pass
            await _send_and_delete(
                context, chat.id,
                f"🖼️ <b>Media Restricted!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {mention_html(user.id, user.first_name)}\n"
                f"🚫 Sending photos, videos, or files is restricted in this group."
            )
            return

# ── Admin commands ────────────────────────────────

@admin_only
async def cmd_antiflood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or args[0].lower() not in ("on", "off"):
        await update.message.reply_text("ব্যবহার: /antiflood on অথবা /antiflood off")
        return
    val = 1 if args[0].lower() == "on" else 0
    await update_chat_setting(update.effective_chat.id, "antiflood_enabled", val)
    await update.message.reply_text(f"Anti-flood {'চালু ✅' if val else 'বন্ধ ❌'}")


@admin_only
async def cmd_antilink(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or args[0].lower() not in ("on", "off"):
        await update.message.reply_text(
            "📖 <b>ব্যবহার:</b> <code>/antilink on</code> অথবা <code>/antilink off</code>\n"
            "💡 <i>নোট: Anti-link চালু থাকলে ১০ জন মেম্বার অ্যাড করা ইউজাররা অটোমেটিক লিংক শেয়ারের অনুমতি পাবে।</i>",
            parse_mode="HTML"
        )
        return
    val = 1 if args[0].lower() == "on" else 0
    await update_chat_setting(update.effective_chat.id, "antilink_enabled", val)
    if len(args) > 1 and args[1].isdigit():
        custom_req = int(args[1])
        await update_chat_setting(update.effective_chat.id, "antilink_required_invites", custom_req)
        await update.message.reply_text(
            f"🔗 Anti-link <b>চালু ✅</b> (প্রতি মেম্বারকে <b>{custom_req} জন</b> অ্যাড করতে হবে)।",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            f"🔗 Anti-link {'<b>চালু ✅</b> (১০ জন মেম্বার অ্যাড করলে অটো আনলক)' if val else '<b>বন্ধ ❌</b>'}",
            parse_mode="HTML"
        )


@admin_only
async def cmd_adminlink(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle Admin Anti-Link protection on or off."""
    args = context.args
    if not args or args[0].lower() not in ("on", "off"):
        await update.message.reply_text(
            "📖 <b>ব্যবহার:</b> <code>/adminlink on</code> অথবা <code>/adminlink off</code>\n\n"
            "🛡️ <b>অ্যাডমিন লিংক প্রটেকশন:</b> চালু থাকলে মনোনীত/অনুমোদিত অ্যাডমিন ছাড়া অন্য কোনো অ্যাডমিন গ্রুপে লিংক দিলে তা কোনো রিপ্লাই ছাড়াই স্বয়ংক্রিয়ভাবে মুছে ফেলা হবে।",
            parse_mode="HTML"
        )
        return
    val = 1 if args[0].lower() == "on" else 0
    await update_chat_setting(update.effective_chat.id, "admin_antilink_enabled", val)
    await update.message.reply_text(
        f"🛡️ অ্যাডমিন লিংক প্রমোশন প্রটেকশন {'<b>চালু ✅</b> (মনোনীত ছাড়া অন্য এডমিনদের লিংক সরাসরি ডিলিট হবে)' if val else '<b>বন্ধ ❌</b>'}",
        parse_mode="HTML"
    )


@admin_only
async def cmd_allowlink(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add an admin to the allowed link whitelist."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "📖 <b>ব্যবহার:</b> <code>/allowlink @username</code> অথবা <code>/allowlink user_id</code>\n"
            "💡 <i>যেকোনো নির্দিষ্ট অ্যাডমিনকে গ্রুপে লিংক দেওয়ার অনুমতি দিতে এই কমান্ডটি দিন।</i>",
            parse_mode="HTML"
        )
        return
    target = args[0].strip()
    chat_id = update.effective_chat.id
    settings = await get_chat_settings(chat_id)
    current_wl = settings.get("admin_link_whitelist") or ""
    tokens = [t.strip() for t in re.split(r"[\s,;]+", current_wl) if t.strip()]
    if target.lower() not in [t.lower() for t in tokens]:
        tokens.append(target)
        new_wl = ", ".join(tokens)
        await update_chat_setting(chat_id, "admin_link_whitelist", new_wl)
        await update.message.reply_text(
            f"✅ অ্যাডমিন <b>{target}</b> সফলভাবে লিংক হোয়াইটলিস্টে যুক্ত হয়েছেন!\n"
            f"এখন থেকে তিনি গ্রুপে লিংক শেয়ার করতে পারবেন।",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            f"ℹ️ অ্যাডমিন <b>{target}</b> ইতিমধ্যে লিংক হোয়াইটলিস্টে আছেন।",
            parse_mode="HTML"
        )


@admin_only
async def cmd_disallowlink(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove an admin from the allowed link whitelist."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "📖 <b>ব্যবহার:</b> <code>/disallowlink @username</code> অথবা <code>/disallowlink user_id</code>\n"
            "💡 <i>কোনো অ্যাডমিনের লিংক শেয়ারের অনুমতি বাতিল করতে এই কমান্ডটি দিন।</i>",
            parse_mode="HTML"
        )
        return
    target = args[0].strip().lower().lstrip("@")
    chat_id = update.effective_chat.id
    settings = await get_chat_settings(chat_id)
    current_wl = settings.get("admin_link_whitelist") or ""
    tokens = [t.strip() for t in re.split(r"[\s,;]+", current_wl) if t.strip()]
    new_tokens = [t for t in tokens if t.strip().lower().lstrip("@") != target]
    new_wl = ", ".join(new_tokens)
    await update_chat_setting(chat_id, "admin_link_whitelist", new_wl)
    await update.message.reply_text(
        f"🚫 অ্যাডমিন <b>{args[0]}</b> এর লিংক শেয়ারের অনুমতি প্রত্যাহার করা হয়েছে।",
        parse_mode="HTML"
    )


@admin_only
async def cmd_linkadmins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of whitelisted link admins."""
    chat_id = update.effective_chat.id
    settings = await get_chat_settings(chat_id)
    enabled = settings.get("admin_antilink_enabled", 1)
    wl_raw = settings.get("admin_link_whitelist") or ""
    tokens = [t.strip() for t in re.split(r"[\s,;]+", wl_raw) if t.strip()]

    text = (
        f"🛡️ <b>অ্যাডমিন লিংক প্রমোশন স্ট্যাটাস</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ <b>অবস্থা:</b> {'সক্রিয় (ACTIVE) ✅' if enabled else 'নিষ্ক্রিয় (OFF) ❌'}\n"
        f"👑 <b>গ্রুপ ওনার:</b> সর্বদা অনুমোদিত (Always Permitted)\n"
    )
    if tokens:
        text += f"\n👥 <b>মনোনীত অনুমোদিত অ্যাডমিনবৃন্দ ({len(tokens)}জন):</b>\n"
        for idx, t in enumerate(tokens, 1):
            text += f"  {idx}. <code>{t}</code>\n"
    else:
        text += "\nℹ️ <i>গ্রুপ ওনার ছাড়া অন্য কোনো অ্যাডমিন বর্তমানে লিংক দেওয়ার জন্য অনুমোদিত নয়।</i>\n"

    text += (
        f"\n━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 নতুন অ্যাডমিনকে অনুমতি দিতে: <code>/allowlink @username</code>\n"
        f"💡 অনুমতি বাতিল করতে: <code>/disallowlink @username</code>"
    )
    await update.message.reply_text(text, parse_mode="HTML")


@admin_only
async def cmd_antiforward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or args[0].lower() not in ("on", "off"):
        await update.message.reply_text(
            "ব্যবহার: <code>/antiforward on</code> অথবা <code>/antiforward off</code>\n\n"
            "💡 <i>নোট: Anti-forward চালু থাকলে সাধারণ সদস্যদের জন্য মেসেজ, মিডিয়া এবং চ্যানেলের পোস্ট ফরোয়ার্ড করা সম্পূর্ণ নিষিদ্ধ থাকবে। ৩ বার ফরোয়ার্ড করলে স্বয়ংক্রিয়ভাবে ১ ঘণ্টার জন্য মিউট করা হবে।</i>",
            parse_mode="HTML"
        )
        return
    val = 1 if args[0].lower() == "on" else 0
    await update_chat_setting(update.effective_chat.id, "antiforward_enabled", val)
    await update.message.reply_text(
        f"📵 Anti-forward {'<b>চালু ✅</b> (মেম্বারদের জন্য ফরোয়ার্ড ও চ্যানেল পোস্ট সম্পূর্ণ বন্ধ)' if val else '<b>বন্ধ ❌</b>'}",
        parse_mode="HTML"
    )


@admin_only
async def cmd_antibiolink(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    args = context.args
    if not args or args[0].lower() not in ("on", "off"):
        settings = await get_chat_settings(chat_id)
        status = "চালু ✅" if settings.get("antibiolink_enabled") else "বন্ধ ❌"
        wl = settings.get("antibiolink_whitelist") or DEFAULT_BIOLINK_WHITELIST
        await update.message.reply_html(
            f"🛡️ <b>Anti-Bio-Link সেটিংস:</b> {status}\n\n"
            f"📋 <b>অনুমোদিত লিংকসমূহ (Whitelist):</b>\n<code>{wl}</code>\n\n"
            f"💡 ব্যবহার: <code>/antibiolink on</code> অথবা <code>/antibiolink off</code>"
        )
        return
    val = 1 if args[0].lower() == "on" else 0
    await update_chat_setting(chat_id, "antibiolink_enabled", val)
    await update.message.reply_html(
        f"🛡️ Anti-Bio-Link {'<b>চালু ✅</b> (প্রোফাইলে অননুমোদিত বায়ো লিংক থাকলে মেসেজ সাথে সাথে মুছে যাবে)' if val else '<b>বন্ধ ❌</b>'}"
    )


@admin_only
async def cmd_badwords_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or args[0].lower() not in ("on", "off"):
        await update.message.reply_text("ব্যবহার: /badwords on অথবা /badwords off")
        return
    val = 1 if args[0].lower() == "on" else 0
    await update_chat_setting(update.effective_chat.id, "badwords_enabled", val)
    await update.message.reply_text(f"Bad-words ফিল্টার {'চালু ✅' if val else 'বন্ধ ❌'}")


@admin_only
async def cmd_addbadword(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("ব্যবহার: /addbadword <শব্দ>")
        return
    word = context.args[0].lower().strip()
    chat_id = update.effective_chat.id
    settings = await get_chat_settings(chat_id)
    existing = settings.get("badwords_list") or ""
    words = [w.strip() for w in existing.split(",") if w.strip()]
    if word not in words:
        words.append(word)
    await update_chat_setting(chat_id, "badwords_list", ",".join(words))
    await update.message.reply_html(f"✅ <code>{word}</code> নিষিদ্ধ শব্দ তালিকায় যোগ করা হয়েছে।")


@admin_only
async def cmd_delbadword(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("ব্যবহার: /delbadword <শব্দ>")
        return
    word = context.args[0].lower().strip()
    chat_id = update.effective_chat.id
    settings = await get_chat_settings(chat_id)
    existing = settings.get("badwords_list") or ""
    words = [w.strip() for w in existing.split(",") if w.strip() and w.strip() != word]
    await update_chat_setting(chat_id, "badwords_list", ",".join(words))
    await update.message.reply_html(f"✅ <code>{word}</code> তালিকা থেকে সরানো হয়েছে।")


@admin_only
async def cmd_badwordlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = await get_chat_settings(update.effective_chat.id)
    existing = settings.get("badwords_list") or ""
    words = [w.strip() for w in existing.split(",") if w.strip()]
    if not words:
        await update.message.reply_text("এই গ্রুপে কোনো নিষিদ্ধ শব্দ নেই।")
        return
    word_list = "\n".join(f"• <code>{w}</code>" for w in words)
    await update.message.reply_html(f"🚫 <b>নিষিদ্ধ শব্দ তালিকা:</b>\n\n{word_list}")


@admin_only
async def cmd_charlimit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set maximum character limit for member messages (default 100, or 'off')."""
    chat = update.effective_chat
    if not chat:
        return
    args = context.args
    if not args:
        settings = await get_chat_settings(chat.id)
        current = settings.get("max_message_chars", 100)
        status_str = f"<b>{current} characters</b>" if current and int(current) > 0 else "<b>Disabled (Off)</b>"
        await update.message.reply_html(
            f"📏 <b>Character Limit Setting / ক্যারেক্টার লিমিট</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Current limit:</b> {status_str}\n\n"
            f"💡 <b>Usage:</b>\n"
            f"• <code>/charlimit 100</code> (মেসেজ সর্বোচ্চ ১০০ অক্ষর নির্ধারণ)\n"
            f"• <code>/charlimit 50</code> (কাস্টম লিমিট সেট করুন)\n"
            f"• <code>/charlimit off</code> (ক্যারেক্টার লিমিট বন্ধ করুন)"
        )
        return

    arg = args[0].strip().lower()
    if arg in ("off", "disable", "0"):
        await update_chat_setting(chat.id, "max_message_chars", 0)
        await update.message.reply_html("✅ <b>মেসেজ ক্যারেক্টার লিমিট বন্ধ করা হয়েছে (Unlimited)।</b>")
    elif arg.isdigit():
        val = int(arg)
        if val < 10:
            await update.message.reply_html("⚠️ ক্যারেক্টার লিমিট সর্বনিম্ন ১০ হতে হবে।")
            return
        await update_chat_setting(chat.id, "max_message_chars", val)
        await update.message.reply_html(f"✅ <b>মেসেজ লিমিট সফলভাবে {val} অক্ষরে নির্ধারণ করা হয়েছে!</b>")
    else:
        await update.message.reply_html("⚠️ ব্যবহার: <code>/charlimit 100</code> অথবা <code>/charlimit off</code>")


# ── Unknown / Spam Slash Command Cleaner ──────────
VALID_COMMANDS = {
    # Member & General
    "start", "help", "rules", "id", "info", "chatinfo", "adminlist",
    "myinvites", "invites", "myadd", "top", "topinvites", "leaderboard",
    "hotvideo", "hotvideos", "videos", "video", "hot",
    # Admin / Management
    "settings", "panel", "forceadd", "force_add", "forceunlock", "funlock", "forcelock", "flock", "restart", "reboot",
    "tagall", "all", "cancel", "tagstop", "autotag", "autotagall",
    "warn", "warns", "resetwarns", "resetwarn", "unwarn", "ban", "unban", "tban", "kick", "mute", "unmute", "tmute",
    "pin", "pinsilent", "unpin", "unpinall", "lock", "unlock",
    "setrules", "setwarnaction", "setwarnlimit",
    "promote", "addadmin", "setadmin", "makeadmin", "demote", "removeadmin", "deladmin", "unadmin",
    "del", "delete", "purge", "cleanvideos", "delvideos", "purgevideos", "cleanvideo", "delvideo", "scanvideos", "scanvideo", "setgrouptitle", "setdesc",
    "setwelcome", "setgoodbye", "welcome", "goodbye", "resetwelcome", "setwelcomesticker", "delwelcomesticker", "setwelcomebtn", "delwelcomebtn", "welcometest", "testwelcome",
    "promo", "sendpromo", "setpromosticker", "delpromosticker",
    "servicealert", "sendalert", "girlnotice",
    "antiflood", "antilink", "antiforward", "antibiolink", "charlimit", "setcharlimit", "badwords", "addbadword", "delbadword", "badwordlist",
    "adminlink", "allowlink", "disallowlink", "linkadmins",
    "notes", "save", "get", "clear"
}


async def unknown_command_cleaner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Instantly deletes any unknown or spam slash commands (e.g. /Sawya, /video, /xxx) sent in groups."""
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not msg.text or not chat:
        return

    text = msg.text.strip()
    if not text.startswith("/"):
        return

    # Extract command keyword (e.g. "/Sawya@bot" -> "sawya")
    cmd = text.split()[0].lstrip("/").split("@")[0].lower()
    if not cmd:
        return

    # If it is not a recognized bot command:
    if cmd not in VALID_COMMANDS:
        if not await is_admin(update):
            try:
                await msg.delete()
                logger.info(f"🗑️ Deleted unknown command /{cmd} from user {update.effective_user.id} in chat {chat.id}")
            except Exception as e:
                logger.debug(f"Failed to delete unknown command /{cmd}: {e}")


def register(app) -> None:
    # 1. FORWARDED handler (catches ALL forwards: text, photos, videos, stickers, polls, locations, etc.)
    app.add_handler(MessageHandler(
        filters.FORWARDED & ~filters.StatusUpdate.ALL & filters.ChatType.GROUPS,
        spam_filter
    ))
    # 2. General messages & media (flood, link, badword, media lock)
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.ATTACHMENT) & ~filters.COMMAND & ~filters.StatusUpdate.ALL & filters.ChatType.GROUPS,
        spam_filter
    ))
    # 3. Unknown / spam command cleaner (catches all /command messages not in VALID_COMMANDS)
    app.add_handler(MessageHandler(
        (filters.COMMAND | filters.Regex(r"^/[a-zA-Z0-9_]+")) & filters.ChatType.GROUPS,
        unknown_command_cleaner
    ))
    app.add_handler(CommandHandler("antiflood",   cmd_antiflood))
    app.add_handler(CommandHandler("antilink",    cmd_antilink))
    app.add_handler(CommandHandler("adminlink",   cmd_adminlink))
    app.add_handler(CommandHandler("allowlink",   cmd_allowlink))
    app.add_handler(CommandHandler("disallowlink",cmd_disallowlink))
    app.add_handler(CommandHandler("linkadmins",  cmd_linkadmins))
    app.add_handler(CommandHandler("antiforward", cmd_antiforward))
    app.add_handler(CommandHandler("antibiolink", cmd_antibiolink))
    app.add_handler(CommandHandler(["charlimit", "setcharlimit"], cmd_charlimit))
    app.add_handler(CommandHandler("badwords",    cmd_badwords_toggle))
    app.add_handler(CommandHandler("addbadword",  cmd_addbadword))
    app.add_handler(CommandHandler("delbadword",  cmd_delbadword))
    app.add_handler(CommandHandler("badwordlist", cmd_badwordlist))
