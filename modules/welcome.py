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
    "🔞 <b>ভিআইপি লাইভ চ্যাট রুম আনলক করতে:</b>\n"
    "👥 গ্রুপে ৫ জন বন্ধুকে অ্যাড করুন এবং নিচের বাটনে ক্লিক করে যুক্ত হোন 👇"
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


def _build_button(settings: dict):
    """ওয়েলকাম মেসেজের সাথে আকর্ষণীয় ২-সারির কালারফুল বাটন তৈরি করে।"""
    custom_btn = (settings.get("welcome_button_text") or "").strip()
    custom_url = (settings.get("welcome_button_url") or "").strip()
    
    # If admin set a single custom button text in dashboard
    if custom_btn and custom_url:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton(text=custom_btn, url=custom_url)
        ]])

    # Default: 2-Row High-Converting Colorful Buttons
    target_url = custom_url if custom_url else DEFAULT_BUTTON_URL
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="🔴 🍒💋 গোপন ক্যামেরায় ধরা পড়া ক্লিপ 🫣🔥", url=target_url)],
        [InlineKeyboardButton(text="🟢 🔞🔥 সরাসরি লাইভ চ্যাটে যুক্ত হোন 💬💋", url=target_url)],
    ])


# ── Event handlers ────────────────────────────────

async def handle_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_member_update = update.chat_member
    if not chat_member_update:
        return

    old_status = chat_member_update.old_chat_member.status
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
        if user.is_bot:
            return

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
        except Exception:
            pass

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
    chat_id = update.effective_chat.id
    stk_id = None
    media_type = "sticker"

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
    elif context.args:
        stk_id = context.args[0].strip()

    if not stk_id:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="📌 <b>যে অ্যানিমেটেড স্টিকারটি সেট করতে চান:</b>\nগ্রুপে সেই স্টিকারে <b>Reply</b> করে <code>/setwelcomesticker</code> লিখুন।",
                parse_mode="HTML"
            )
        except Exception:
            pass
        return

    await update_chat_setting(chat_id, "welcome_sticker", stk_id)
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="✅ <b>ওয়েলকাম অ্যানিমেটেড স্টিকার সফলভাবে সেট ও সক্রিয় করা হয়েছে!</b>\n\n👇 নিচে স্টিকারের টেস্ট প্রিভিউ দেখানো হলো:",
            parse_mode="HTML"
        )
    except Exception:
        pass

    # Send a quick verification preview of the sticker in the chat
    try:
        if media_type == "animation":
            await context.bot.send_animation(chat_id=chat_id, animation=stk_id)
        elif media_type == "document":
            await context.bot.send_document(chat_id=chat_id, document=stk_id)
        else:
            await context.bot.send_sticker(chat_id=chat_id, sticker=stk_id)
    except Exception:
        try:
            await context.bot.send_sticker(chat_id=chat_id, sticker=stk_id)
        except Exception:
            pass


@admin_only
async def del_welcome_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove welcome sticker."""
    chat_id = update.effective_chat.id
    await update_chat_setting(chat_id, "welcome_sticker", "")
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🗑️ <b>ওয়েলকাম স্টিকার মুছে ফেলা হয়েছে।</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass


def register(app) -> None:
    app.add_handler(ChatMemberHandler(handle_chat_member, ChatMemberHandler.CHAT_MEMBER))
    # app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER,  handle_left_member))
    app.add_handler(CommandHandler("setwelcome",  set_welcome))
    app.add_handler(CommandHandler("setgoodbye",  set_goodbye))
    app.add_handler(CommandHandler("welcome",     toggle_welcome))
    app.add_handler(CommandHandler("goodbye",     toggle_goodbye))
    app.add_handler(CommandHandler("resetwelcome",reset_welcome))
    app.add_handler(CommandHandler("resetgoodbye",reset_goodbye))
    app.add_handler(CommandHandler(["setwelcomesticker", "setsticker"], set_welcome_sticker))
    app.add_handler(CommandHandler(["delwelcomesticker", "delsticker"], del_welcome_sticker))
