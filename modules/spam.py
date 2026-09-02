"""
Spam protection module.
Features:
  - Auto-delete  : বটের নিজস্ব সতর্কতা মেসেজ ৫ সেকেন্ড পর অটো ডিলিট
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
from collections import defaultdict

from telegram import Update, ChatPermissions, Message
from telegram.ext import ContextTypes, MessageHandler, CommandHandler, filters
from telegram.helpers import mention_html

from database import get_chat_settings, update_chat_setting, upsert_user, update_chat_info
from modules.utils import is_admin, admin_only
from config import MAX_FLOOD_MESSAGES, FLOOD_WINDOW_SECONDS

# ── In-memory trackers ────────────────────────────
# Flood: {chat_id: {user_id: [timestamps]}}
_flood: dict = defaultdict(lambda: defaultdict(list))

# Bad word strike tracker: {chat_id: {user_id: strike_count}}
# Resets when mute is applied or after BADWORD_STRIKE_WINDOW seconds
_badword_strikes: dict = defaultdict(lambda: defaultdict(int))
_badword_strike_time: dict = defaultdict(lambda: defaultdict(float))

BADWORD_STRIKE_WINDOW = 300    # ৫ মিনিটের মধ্যে strike expiry
BOT_MSG_AUTO_DELETE   = 5      # বটের মেসেজ কত সেকেন্ড পর ডিলিট হবে

URL_PATTERN = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/)",
    re.IGNORECASE
)


def _clean_flood(timestamps: list, now: float) -> list:
    return [t for t in timestamps if now - t < FLOOD_WINDOW_SECONDS]


async def _auto_delete(message: Message, delay: int = BOT_MSG_AUTO_DELETE) -> None:
    """নির্দিষ্ট সময় পর বটের মেসেজ অটো ডিলিট করে।"""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


async def _send_and_delete(context, chat_id: int, text: str) -> None:
    """মেসেজ পাঠাও এবং BOT_MSG_AUTO_DELETE সেকেন্ড পরে ডিলিট করো।"""
    try:
        sent = await context.bot.send_message(
            chat_id, text, parse_mode="HTML"
        )
        asyncio.create_task(_auto_delete(sent))
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


# ── Main filter ───────────────────────────────────

async def spam_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """সব মেসেজ চেক করে — flood, links, bad words, forwards।"""
    msg = update.message or update.edited_message
    if not msg or not msg.from_user:
        return

    chat = update.effective_chat
    user = msg.from_user

    # Record user and chat title in database for accurate stats
    if user and chat:
        asyncio.create_task(upsert_user(user.id, chat.id, user.username or "", user.first_name or ""))
        if chat.type != "private" and chat.title:
            asyncio.create_task(update_chat_info(chat.id, title=chat.title))

    # অ্যাডমিনরা বাদ
    if await is_admin(update):
        return

    settings = await get_chat_settings(chat.id)

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
                    f"🚨 <b>ফ্লাড সতর্কতা!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 {mention_html(user.id, user.first_name)}\n"
                    f"⚡ অতিরিক্ত দ্রুত মেসেজ পাঠাচ্ছেন!\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔇 <b>১ মিনিট</b> মিউট করা হয়েছে।"
                )
            except Exception:
                pass
            return

    # ── Anti-link ────────────────────────────────
    if settings.get("antilink_enabled", 0) and msg.text:
        if URL_PATTERN.search(msg.text):
            try:
                await msg.delete()
            except Exception:
                pass
            await _send_and_delete(
                context, chat.id,
                f"🔗 <b>লিংক শেয়ার নিষিদ্ধ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {mention_html(user.id, user.first_name)}\n"
                f"🚫 এই গ্রুপে লিংক শেয়ার করা যাবে না।\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>পুনরায় করলে ব্যবস্থা নেওয়া হবে।</i>"
            )
            return

    # ── Bad words (স্ট্রাইক সিস্টেম) ────────────
    if settings.get("badwords_enabled", 1) and msg.text:
        bw_raw = settings.get("badwords_list")
        if not bw_raw or not bw_raw.strip():
            bw_raw = "ছেলে,ও ছেলে,স্কেমার,বাটপার,প্রতারক,chele,o chele,sele,o sele,chala,scammer,skeimer,skemer,scamer,skeimar"
        bad_words = [w.strip().lower() for w in bw_raw.split(",") if w.strip()]
        text_lower = msg.text.lower()

        matched = False
        for bw in bad_words:
            if not bw:
                continue
            
            # Check if badword contains non-ASCII characters (e.g. Bengali script)
            is_ascii = all(ord(c) < 128 for c in bw)
            if is_ascii:
                # Use word boundaries for English to avoid matching parts of other words (e.g. "ass" in "class")
                pattern = rf"\b{re.escape(bw)}\b"
            else:
                # For non-ASCII (Bengali), standard \b word boundaries do not work in Python.
                # Check for simple substring presence
                pattern = re.escape(bw)

            if re.search(pattern, text_lower):
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
                mute_text = f"{mute_min} মিনিট" if mute_duration >= 60 else f"{mute_duration} সেকেন্ড"
                try:
                    await _mute_user(context, chat.id, user, mute_duration)
                except Exception:
                    pass
                await _send_and_delete(
                    context, chat.id,
                    f"🔇 <b>মিউট!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 {mention_html(user.id, user.first_name)}\n"
                    f"🚫 {strike_limit}বার নিষিদ্ধ শব্দ ব্যবহারের কারণে\n"
                    f"🔕 <b>{mute_text}</b> মিউট করা হয়েছে।\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"<i>সংযত ভাষা ব্যবহার করুন।</i>"
                )
            else:
                remaining = strike_limit - strike_count
                await _send_and_delete(
                    context, chat.id,
                    f"🤬 <b>অনুপযুক্ত শব্দ!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 {mention_html(user.id, user.first_name)}\n"
                    f"⚠️ স্ট্রাইক: <b>{strike_count}/{strike_limit}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"আরও <b>{remaining}বার</b> করলে মিউট হবেন।"
                )
            return

    # ── Anti-forward (DB-driven) ──────────────────
    forward_blocked = (
        settings.get("antiforward_enabled", 0) or
        settings.get("lock_messages", 0)
    )
    if forward_blocked and msg.forward_origin is not None:
        try:
            await msg.delete()
        except Exception:
            pass
        await _send_and_delete(
            context, chat.id,
            f"📵 <b>ফরোয়ার্ড নিষিদ্ধ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {mention_html(user.id, user.first_name)}\n"
            f"🚫 এই গ্রুপে ফরোয়ার্ড করা যাবে না।"
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
                f"🖼️ <b>মিডিয়া নিষিদ্ধ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {mention_html(user.id, user.first_name)}\n"
                f"🚫 এই গ্রুপে ছবি/ভিডিও/ফাইল পাঠানো যাবে না।"
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
        await update.message.reply_text("ব্যবহার: /antilink on অথবা /antilink off")
        return
    val = 1 if args[0].lower() == "on" else 0
    await update_chat_setting(update.effective_chat.id, "antilink_enabled", val)
    await update.message.reply_text(f"Anti-link {'চালু ✅' if val else 'বন্ধ ❌'}")


@admin_only
async def cmd_antiforward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or args[0].lower() not in ("on", "off"):
        await update.message.reply_text("ব্যবহার: /antiforward on অথবা /antiforward off")
        return
    val = 1 if args[0].lower() == "on" else 0
    await update_chat_setting(update.effective_chat.id, "antiforward_enabled", val)
    await update.message.reply_text(f"Anti-forward {'চালু ✅' if val else 'বন্ধ ❌'}")


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


def register(app) -> None:
    # TEXT filter (flood, link, badword, forward)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
        spam_filter
    ))
    # MEDIA filter (photo, video, document, audio etc.)
    app.add_handler(MessageHandler(
        (filters.PHOTO | filters.VIDEO | filters.Document.ALL |
         filters.AUDIO | filters.VOICE | filters.VIDEO_NOTE | filters.ANIMATION)
        & filters.ChatType.GROUPS,
        spam_filter
    ))
    app.add_handler(CommandHandler("antiflood",   cmd_antiflood))
    app.add_handler(CommandHandler("antilink",    cmd_antilink))
    app.add_handler(CommandHandler("antiforward", cmd_antiforward))
    app.add_handler(CommandHandler("badwords",    cmd_badwords_toggle))
    app.add_handler(CommandHandler("addbadword",  cmd_addbadword))
    app.add_handler(CommandHandler("delbadword",  cmd_delbadword))
    app.add_handler(CommandHandler("badwordlist", cmd_badwordlist))
