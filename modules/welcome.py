"""
Welcome / Goodbye module.
Commands (admin only):
  /setwelcome <text>  — ওয়েলকাম মেসেজ সেট করুন
  /setgoodbye <text>  — গুডবাই মেসেজ সেট করুন
  /welcome on|off     — ওয়েলকাম চালু/বন্ধ
  /goodbye on|off     — গুডবাই চালু/বন্ধ
  /resetwelcome       — ডিফল্টে রিসেট
  /resetgoodbye       — ডিফল্টে রিসেট

Placeholders: {first} {last} {full} {username} {mention} {count} {chatname}
"""

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import ContextTypes, MessageHandler, CommandHandler, filters, ChatMemberHandler
from telegram.helpers import mention_html

from database import get_chat_settings, update_chat_setting, upsert_user, update_chat_info
from modules.utils import admin_only

AUTO_DELETE_SECONDS = 60   # ওয়েলকাম/গুডবাই মেসেজ এত সেকেন্ড পর অটো ডিলিট


async def _auto_delete(message, delay: int = AUTO_DELETE_SECONDS) -> None:
    """নির্দিষ্ট সময় পর মেসেজ ডিলিট করে।"""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


DEFAULT_WELCOME = (
    "🌟 <b>স্বাগতম {mention}!</b> 🌸\n"
    "🏠 <b>{chatname}</b> • আপনি আমাদের <b>#{count}</b> তম সদস্য।\n\n"
    "🔞 <b>হট ও ভাইরাল ভিডিও ক্যাটাগরি দেখতে নিচে ক্লিক করুন:</b>\n"
    "👇 আপনার পছন্দের ক্যাটাগরি বেছে নিন এবং সরাসরি সাইটে প্রবেশ করুন 👇"
)

DEFAULT_GOODBYE = (
    "━━━━━━━━━━━━━━━━━━━━━━━\n"
    "👋  <b>বিদায়!</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━\n"
    "😢 <b>{full}</b> আমাদের ছেড়ে চলে গেলেন।\n\n"
    "🌟 <i>যেখানেই থাকুন ভালো থাকুন!</i>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━"
)

DEFAULT_BUTTON_TEXT = "🔥 🔞 🔴 𝗟𝗜𝗩𝗘 𝗖𝗛𝗔𝗧 • সরাসরি চ্যাট করুন 🔞 🔥"
DEFAULT_BUTTON_URL  = "https://techandclick.site/bot/"


def _format(text: str, user, chat, count) -> str:
    uname = f"@{user.username}" if user.username else user.full_name
    return text.format(
        first    = user.first_name or "",
        last     = user.last_name  or "",
        full     = user.full_name,
        username = uname,
        mention  = mention_html(user.id, user.first_name or user.full_name),
        count    = count,
        chatname = chat.title or "",
    )


import random

# Dynamic Multi-Category Viral Buttons Dataset (Thousands of unique rotating combinations)
VIRAL_BUTTON_SETS = {
    "videos": [
        "🔞 👰‍♀️ বউ ও শ্বশুর স্পেশাল গোপন ভিডিও 🔥",
        "🔥 🔞 শ্বশুর ও নতুন বউয়ের ভাইরাল ক্লিপ 🎬",
        "🔞 💋 নতুন বউ ও শ্বশুরের রাতের গোপন ভিডিও 📹",
        "🔥 🤤 গ্রামের বউ ও শ্বশুরের ফাঁস হওয়া ক্লিপ 🔞",
        "🔞 🤫 শ্বশুর ও বউয়ের রিয়েল রুম ভিডিও 💋",
        "🎬 🔞 হট ভাবি ও দেবরের সিক্রেট ক্যামেরা ভিডিও 🔥",
        "🔞 🔥 দেবর ও প্রবাসীর বউয়ের আনকাট ভিডিও 🤤",
        "🔞 💃 দেবর-ভাবি স্পেশাল রোমান্স ভিডিও 🎬",
        "🔥 🔞 পরকীয়া রোমান্স ও গোপন সম্পর্কের ভিডিও 🔞",
        "🎬 🔞 হোটেল রুমের গোপন ক্যামেরার ফুল ভিডিও 🔥",
        "🔞 🍒 অবিবাহিত মেয়েদের লিক হওয়া ফুল ভিডিও 🎬",
        "🔥 🔞 মধ্যরাতের গোপন ক্যাম ও ফুল ভিডিও ক্লিপ 📹",
    ],
    "categories": [
        "🔞 💃 দেবর-ভাবি ও পরকীয়া রোমান্স রুম 🍒",
        "💋 👩‍❤️‍👨 রিয়েল ডেটিং ও পরকীয়া চ্যাট রুম 🔥",
        "🍒 🔞 প্রবাসীর একাকী বউদের রোমান্স ক্লাব 💋",
        "🔥 🤤 ভাবি ও দেবরের আনলিমিটেড মাস্তির আসর 🔞",
        "🔞 💋 রিয়েল সার্ভিস ও সিক্রেট মিটআপ রুম 🍓",
        "💃 🔞 অভিজাত এলাকার সুন্দরী ভাবিদের চ্যাট রুম 🍒",
        "🔥 👰‍♀️ ডিভোর্সি ও একাকী ভাবিদের রোমান্স আড্ডা 💋",
        "🍒 🔞 সরাসরি রিয়েল সার্ভিস ও পার্টনার বুকিং 🔥",
        "🔞 💬 মধ্যরাতের পরকীয়া প্রেমের গোপন আসর 🤤",
        "🍓 🔞 ভিআইপি সিক্রেট রোমান্স ও ডেটিং ক্যাটাগরি 💋",
    ],
    "girls": [
        "🔴 💋 কলেজ ছাত্রী ও ভাবির ১-অন-১ লাইভ চ্যাট 💬",
        "💬 🌸 ভার্সিটি গার্ল ও সুন্দরী মেয়েদের প্রোফাইল 📱",
        "🔴 🔥 ইমো ও হোয়াটসঅ্যাপে সরাসরি লাইভ ভিডিও কল 📹",
        "💋 💃 সুন্দরী ভাবিদের সরাসরি ব্যক্তিগত নাম্বার 📱",
        "🔴 🤤 এখন অনলাইনে ফ্রি মেয়েদের সাথে চ্যাট 💬",
        "🌸 💋 গ্রামের কিউট মেয়েদের ইমো নাম্বার ও চ্যাট 📱",
        "🔴 🔞 লাইভ রুমে ক্যামেরা অন করে কথা বলুন 📹",
        "💬 🍓 হট মেয়েদের সাথে আনলিমিটেড প্রাইভেট চ্যাট 💋",
        "🔴 👩‍🦰 রাত জাগা মেয়েদের লাইভ ভিডিও আড্ডা 💬",
        "📱 💋 সরাসরি সুন্দরী ভাবি ও মেয়েদের সাথে যুক্ত হোন 🔴",
    ],
    "extra": [
        ("🎤 🎧 মেয়েদের পার্সোনাল হট ভয়েস নোট শুনুন 💋", "/voice.html"),
        ("🎡 💖 লাকি হুইল ঘুরিয়ে ২ সেকেন্ডে পার্টনার পান 🎁", "/wheel.html"),
        ("🟢 🔥 সরাসরি ফুল ভিডিও ও চ্যাট রুমে ঢুকুন ➜", "/index.html"),
        ("🔓 🔞 সকল গোপন ভিডিও ও ক্যামেরা আনলক করুন ➜", "/videos.html"),
        ("🎧 🤤 সুন্দরী মেয়েদের গভীর রাতের অডিও বার্তা 💋", "/voice.html"),
        ("🟢 💬 এখনই সাইটে ঢুকে লাইভ আড্ডা শুরু করুন ➜", "/index.html"),
    ]
}


import urllib.parse

# Viral Telegram share URL (Prompts user to forward/share the group link to 5 friends/groups)
SHARE_GROUP_URL = "https://t.me/alltimefantasyzone"
SHARE_TEXT_ENCODED = urllib.parse.quote("🔥 সরাসরি মেয়েদের সাথে লাইভ ভিডিও চ্যাট ও আড্ডা দিতে এখনই জয়েন করুন! 🔞👉 " + SHARE_GROUP_URL)
FORWARD_LINK = f"https://t.me/share/url?url={SHARE_GROUP_URL}&text={SHARE_TEXT_ENCODED}"


def _build_button(settings: dict):
    """ওয়েলকাম মেসেজের সাথে আকর্ষণীয় ডায়নামিক ও পরিবর্তনশীল ভাইরাল বাটন তৈরি করে (প্রোমো মেসেজের মতো)।"""
    custom_url = (settings.get("welcome_button_url") or "").strip()
    base_url = custom_url.rstrip("/") if (custom_url and "techandclick.site" in custom_url) else "https://techandclick.site/bot"
    
    btn_vid = random.choice(VIRAL_BUTTON_SETS["videos"])
    btn_cat = random.choice(VIRAL_BUTTON_SETS["categories"])
    btn_girl = random.choice(VIRAL_BUTTON_SETS["girls"])
    extra_txt, extra_path = random.choice(VIRAL_BUTTON_SETS["extra"])

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="📤 ৫ জনকে শেয়ার/ফরোয়ার্ড করুন (Unlock) 🔓", url=FORWARD_LINK)],
        [InlineKeyboardButton(text=btn_vid, url=f"{base_url}/videos.html")],
        [InlineKeyboardButton(text=btn_cat, url=f"{base_url}/categories.html")],
        [InlineKeyboardButton(text=btn_girl, url=f"{base_url}/girls.html")],
        [InlineKeyboardButton(text=extra_txt, url=f"{base_url}{extra_path}")],
    ])


import time
import logging

logger = logging.getLogger(__name__)

# Debounce cache to prevent duplicate welcome messages within 8 seconds for the same user in same chat
_recent_welcomes: dict = {}


async def _send_welcome(chat, user, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Core function to format and send the welcome message and sticker."""
    if not chat or not user or user.is_bot:
        return

    key = (chat.id, user.id)
    now = time.time()
    if key in _recent_welcomes and (now - _recent_welcomes[key]) < 8:
        return
    _recent_welcomes[key] = now

    # Prune old cache entries
    for k in list(_recent_welcomes.keys()):
        if now - _recent_welcomes[k] > 60:
            del _recent_welcomes[k]

    asyncio.create_task(upsert_user(user.id, chat.id, user.username or "", user.first_name or ""))

    settings = await get_chat_settings(chat.id)
    if not settings.get("welcome_enabled", 1):
        return

    try:
        count = await chat.get_member_count()
        asyncio.create_task(update_chat_info(chat.id, title=chat.title or "", member_count=count))
    except Exception:
        count = "?"

    text = settings.get("welcome_text") or DEFAULT_WELCOME
    try:
        formatted = _format(text, user, chat, count)
    except (KeyError, ValueError):
        formatted = text

    # Send animated sticker if set
    stk_id = settings.get("welcome_sticker")
    if stk_id and stk_id.strip():
        try:
            stk = await context.bot.send_sticker(chat_id=chat.id, sticker=stk_id.strip())
            asyncio.create_task(_auto_delete(stk))
        except Exception:
            try:
                stk = await context.bot.send_animation(chat_id=chat.id, animation=stk_id.strip())
                asyncio.create_task(_auto_delete(stk))
            except Exception:
                pass

    try:
        sent = await context.bot.send_message(
            chat_id=chat.id,
            text=formatted,
            parse_mode="HTML",
            reply_markup=_build_button(settings)
        )
        asyncio.create_task(_auto_delete(sent))
        logger.info(f"👋 Welcome message sent to user {user.id} ({user.first_name}) in chat {chat.id} ({chat.title})")
    except Exception as e:
        logger.warning(f"Error sending welcome message in chat {chat.id}: {e}")


# ── Event handlers ────────────────────────────────

async def handle_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_member_update = update.chat_member
    if not chat_member_update:
        return

    old_status = chat_member_update.old_chat_member.status
    new_status = chat_member_update.new_chat_member.status

    if new_status == ChatMember.BANNED:
        user = chat_member_update.new_chat_member.user
        chat = update.effective_chat
        admin_user = update.effective_user
        from database import add_banned_user
        asyncio.create_task(add_banned_user(
            chat.id, user.id, user.first_name or "", user.username or "",
            "Telegram Admin Ban", admin_user.id if admin_user else 0
        ))
        return

    if new_status in [ChatMember.MEMBER, ChatMember.LEFT] and old_status in [ChatMember.BANNED, 'kicked']:
        user = chat_member_update.new_chat_member.user
        chat = update.effective_chat
        from database import remove_banned_user
        asyncio.create_task(remove_banned_user(chat.id, user.id))

    if new_status == ChatMember.MEMBER and old_status in [ChatMember.LEFT, ChatMember.BANNED, ChatMember.RESTRICTED, 'left', 'kicked', 'restricted', None]:
        chat = update.effective_chat
        user = chat_member_update.new_chat_member.user
        await _send_welcome(chat, user, context)


async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not update.message or not update.message.new_chat_members:
        return
    for user in update.message.new_chat_members:
        await _send_welcome(chat, user, context)

async def handle_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat     = update.effective_chat
    settings = await get_chat_settings(chat.id)

    if not settings.get("goodbye_enabled", 0):
        return

    member = update.message.left_chat_member
    if not member or member.is_bot:
        return

    text = settings.get("goodbye_text") or DEFAULT_GOODBYE
    try:
        formatted = _format(text, member, chat, 0)
    except (KeyError, ValueError):
        formatted = text

    sent = await update.message.reply_html(formatted)
    # ৫ সেকেন্ড পর অটো ডিলিট
    asyncio.create_task(_auto_delete(sent))


# ── Admin commands ────────────────────────────────

@admin_only
async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = update.message.text.partition(" ")[2].strip()
    if not args:
        await update.message.reply_text(
            "ব্যবহার: /setwelcome <টেক্সট>\n\n"
            "Placeholders: {first} {full} {mention} {count} {chatname}"
        )
        return
    await update_chat_setting(update.effective_chat.id, "welcome_text", args)
    await update_chat_setting(update.effective_chat.id, "welcome_enabled", 1)
    await update.message.reply_html(f"✅ ওয়েলকাম মেসেজ সেট হয়েছে:\n\n{args}")


@admin_only
async def set_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = update.message.text.partition(" ")[2].strip()
    if not args:
        await update.message.reply_text(
            "ব্যবহার: /setgoodbye <টেক্সট>\n\n"
            "Placeholders: {first} {full} {mention}"
        )
        return
    await update_chat_setting(update.effective_chat.id, "goodbye_text", args)
    await update_chat_setting(update.effective_chat.id, "goodbye_enabled", 1)
    await update.message.reply_html(f"✅ গুডবাই মেসেজ সেট হয়েছে:\n\n{args}")


@admin_only
async def toggle_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or args[0].lower() not in ("on", "off"):
        await update.message.reply_text("ব্যবহার: /welcome on অথবা /welcome off")
        return
    val = 1 if args[0].lower() == "on" else 0
    await update_chat_setting(update.effective_chat.id, "welcome_enabled", val)
    await update.message.reply_text(f"ওয়েলকাম মেসেজ {'চালু ✅' if val else 'বন্ধ ❌'}")


@admin_only
async def toggle_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or args[0].lower() not in ("on", "off"):
        await update.message.reply_text("ব্যবহার: /goodbye on অথবা /goodbye off")
        return
    val = 1 if args[0].lower() == "on" else 0
    await update_chat_setting(update.effective_chat.id, "goodbye_enabled", val)
    await update.message.reply_text(f"গুডবাই মেসেজ {'চালু ✅' if val else 'বন্ধ ❌'}")


@admin_only
async def reset_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update_chat_setting(update.effective_chat.id, "welcome_text", "")
    await update.message.reply_text("✅ ওয়েলকাম মেসেজ ডিফল্টে রিসেট হয়েছে।")


@admin_only
async def reset_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update_chat_setting(update.effective_chat.id, "goodbye_text", "")
    await update.message.reply_text("✅ গুডবাই মেসেজ ডিফল্টে রিসেট হয়েছে।")


@admin_only
async def set_welcome_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set animated sticker for welcome messages by replying to a sticker or passing ID."""
    msg = update.effective_message
    chat = update.effective_chat
    chat_id = chat.id
    stk_id = None
    media_type = "sticker"

    # If called in private chat with a target chat_id argument: /setwelcomesticker <chat_id>
    if chat.type == "private" and context.args:
        try:
            target_id = int(context.args[0])
            chat_id = target_id
        except ValueError:
            pass

    reply = msg.reply_to_message if msg else None
    if reply:
        if reply.sticker:
            stk_id = reply.sticker.file_id
            media_type = "sticker"
        elif reply.animation:
            stk_id = reply.animation.file_id
            media_type = "animation"
        elif reply.document:
            stk_id = reply.document.file_id
            media_type = "document"
    elif msg and msg.sticker:
        stk_id = msg.sticker.file_id
        media_type = "sticker"
    elif msg and msg.animation:
        stk_id = msg.animation.file_id
        media_type = "animation"
    elif context.args and not str(context.args[0]).startswith("-"):
        stk_id = context.args[0].strip()

    if not stk_id:
        try:
            sent = await context.bot.send_message(
                chat_id=chat.id,
                text="📌 <b>যে অ্যানিমেটেড স্টিকারটি সেট করতে চান:</b>\n"
                     "গ্রুপে সেই স্টিকারে <b>Reply</b> করে <code>/setwelcomesticker</code> লিখুন।",
                parse_mode="HTML"
            )
            asyncio.create_task(_auto_delete(sent, delay=10))
        except Exception as e:
            logger.warning(f"Error sending set_welcome_sticker hint: {e}")
        return

    await update_chat_setting(chat_id, "welcome_sticker", stk_id)
    logger.info(f"🎨 Welcome sticker set for chat {chat_id}: {stk_id}")
    try:
        sent = await context.bot.send_message(
            chat_id=chat.id,
            text=f"✅ <b>ওয়েলকাম অ্যানিমেটেড স্টিকার সফলভাবে সেট করা হয়েছে!</b>\n"
                 f"গ্রুপ: <code>{chat_id}</code>",
            parse_mode="HTML"
        )
        asyncio.create_task(_auto_delete(sent, delay=10))
    except Exception as e:
        logger.warning(f"Error sending set_welcome_sticker confirmation: {e}")


@admin_only
async def del_welcome_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove welcome sticker for the current group or all groups."""
    chat = update.effective_chat
    chat_id = chat.id

    # If called in private chat with a target chat_id argument: /delwelcomesticker <chat_id> or 'all'
    if chat.type == "private" and context.args:
        arg = context.args[0].strip().lower()
        if arg == "all":
            from database import get_all_chat_ids
            all_ids = await get_all_chat_ids()
            for cid in all_ids:
                await update_chat_setting(cid, "welcome_sticker", "")
            logger.info("🗑️ Welcome sticker deleted for ALL groups")
            try:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text="🗑️ <b>সকল গ্রুপের ওয়েলকাম স্টিকার মুছে ফেলা হয়েছে।</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass
            return
        else:
            try:
                chat_id = int(arg)
            except ValueError:
                pass

    await update_chat_setting(chat_id, "welcome_sticker", "")
    logger.info(f"🗑️ Welcome sticker deleted and cleared for chat {chat_id}")
    try:
        sent = await context.bot.send_message(
            chat_id=chat.id,
            text=f"🗑️ <b>ওয়েলকাম স্টিকার সফলভাবে মুছে ফেলা হয়েছে!</b>\n"
                 f"গ্রুপ: <code>{chat_id}</code>\n"
                 f"<i>এখন থেকে নতুন সদস্য জয়েন করলে কোনো স্টিকার পাঠানো হবে না।</i>",
            parse_mode="HTML"
        )
        asyncio.create_task(_auto_delete(sent, delay=10))
    except Exception as e:
        logger.warning(f"Error sending del_welcome_sticker confirmation: {e}")


def register(app) -> None:
    app.add_handler(ChatMemberHandler(handle_chat_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members))
    # app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER,  handle_left_member))
    app.add_handler(CommandHandler("setwelcome",  set_welcome))
    app.add_handler(CommandHandler("setgoodbye",  set_goodbye))
    app.add_handler(CommandHandler("welcome",     toggle_welcome))
    app.add_handler(CommandHandler("goodbye",     toggle_goodbye))
    app.add_handler(CommandHandler("resetwelcome",reset_welcome))
    app.add_handler(CommandHandler("resetgoodbye",reset_goodbye))
    app.add_handler(CommandHandler(["setwelcomesticker", "setsticker"], set_welcome_sticker))
    app.add_handler(CommandHandler(["delwelcomesticker", "delsticker"], del_welcome_sticker))
