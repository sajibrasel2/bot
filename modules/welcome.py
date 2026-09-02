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
    "╔═══════════════════════╗\n"
    "        ✨  <b>স্বাগতম!</b>  ✨\n"
    "╚═══════════════════════╝\n\n"
    "👋 হ্যালো {mention}!\n"
    "━━━━━━━━━━━━━━━━━━━━━━━\n"
    "🏠 <b>{chatname}</b> গ্রুপে আপনাকে\n"
    "    সাদর স্বাগত জানাই! 🌸\n"
    "━━━━━━━━━━━━━━━━━━━━━━━\n"
    "👥 আপনি আমাদের <b>{count}</b> তম সদস্য\n\n"
    "🔞 <b>আপনার ফ্যান্টাসির দুনিয়া আনলক করতে:</b>\n"
    "👥 গ্রুপে ৫ জন বন্ধুকে অ্যাড (Invite/Add) করুন!\n\n"
    "🎁 ৫ জন মেম্বার অ্যাড করা শেষ হলে নিচের লিংকে ক্লিক করে সরাসরি চ্যাট রুমে যুক্ত হোন:\n"
    "🔗 https://techandclick.site/bot/\n\n"
    "💬 <i>নিয়ম মেনে চলুন, সুন্দর থাকুন!</i> 💙"
)

DEFAULT_GOODBYE = (
    "━━━━━━━━━━━━━━━━━━━━━━━\n"
    "👋  <b>বিদায়!</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━\n"
    "😢 <b>{full}</b> আমাদের ছেড়ে চলে গেলেন।\n\n"
    "🌟 <i>যেখানেই থাকুন ভালো থাকুন!</i>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━"
)


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
    """ওয়েলকাম মেসেজের সাথে inline button তৈরি করে (যদি সেট থাকে)।"""
    btn_text = (settings.get("welcome_button_text") or "").strip()
    btn_url  = (settings.get("welcome_button_url")  or "").strip()
    if btn_text and btn_url:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton(text=btn_text, url=btn_url)
        ]])
    return None


# ── Event handlers ────────────────────────────────

async def handle_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_member_update = update.chat_member
    if not chat_member_update:
        return

    old_status = chat_member_update.old_chat_member.status
    new_status = chat_member_update.new_chat_member.status

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


def register(app) -> None:
    app.add_handler(ChatMemberHandler(handle_chat_member, ChatMemberHandler.CHAT_MEMBER))
    # app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER,  handle_left_member))
    app.add_handler(CommandHandler("setwelcome",  set_welcome))
    app.add_handler(CommandHandler("setgoodbye",  set_goodbye))
    app.add_handler(CommandHandler("welcome",     toggle_welcome))
    app.add_handler(CommandHandler("goodbye",     toggle_goodbye))
    app.add_handler(CommandHandler("resetwelcome",reset_welcome))
    app.add_handler(CommandHandler("resetgoodbye",reset_goodbye))
