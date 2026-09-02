"""
Promotional broadcast module.
Automatically sends a beautiful invitation message to all chats every 10 minutes.
"""

import asyncio
import logging
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ContextTypes, CommandHandler
from database import get_all_chat_ids, get_chat_settings, update_chat_setting
from modules.utils import admin_only

logger = logging.getLogger(__name__)

PROMO_TEXT = (
    "🔥 🔞 <b>সিক্রেট ভিআইপি লাইভ চ্যাট রুম</b> 🔞 🔥\n"
    "🌟 আনলিমিটেড লাইভ আড্ডা ও এক্সক্লুসিভ সেশনে ফ্রিতে যুক্ত হতে:\n"
    "👥 গ্রুপে ৫ জন বন্ধুকে অ্যাড করুন এবং নিচের বাটনে ক্লিক করুন 👇"
)

async def _auto_delete(message, delay: int = 60) -> None:
    """Auto-deletes a message after specified seconds."""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


_promo_running = False


async def promo_loop(app: Application) -> None:
    """Infinite loop that broadcasts promo message every 10 minutes (600 seconds)."""
    global _promo_running
    if _promo_running:
        logger.info("ℹ️ Promo loop is already running, skipping duplicate initialization.")
        return
    _promo_running = True

    # Wait 10 seconds after bot startup before the first broadcast
    await asyncio.sleep(10)
    
    while True:
        try:
            chat_ids = await get_all_chat_ids()
        except Exception as e:
            logger.error(f"Error fetching chat IDs for promo broadcast: {e}")
            await asyncio.sleep(600)
            continue

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(text="🔴 🍒💋 গোপন ক্যামেরায় ধরা পড়া ক্লিপ 🫣🔥", url="https://techandclick.site/bot/")],
            [InlineKeyboardButton(text="🟢 🔞🔥 সরাসরি লাইভ চ্যাটে যুক্ত হোন 💬💋", url="https://techandclick.site/bot/")],
        ])

        # Collect all valid target chats (both Channels and Groups)
        # Avoid double-posting if a group is linked to a channel already receiving the broadcast
        all_unique_ids = set(chat_ids)
        target_chats = set()

        for cid in all_unique_ids:
            try:
                if not cid:
                    continue
                c = await app.bot.get_chat(cid)
                if c.type == "private":
                    continue
                # If this is a group whose linked channel is already in our target list,
                # Telegram will automatically mirror the channel post into this group,
                # so we don't send a duplicate direct message to the group.
                if c.type in ("group", "supergroup") and c.linked_chat_id and (c.linked_chat_id in all_unique_ids):
                    continue
                target_chats.add(cid)
            except Exception:
                target_chats.add(cid)

        for chat_id in target_chats:
            try:
                # Check if promo sticker is set for this chat
                try:
                    settings = await get_chat_settings(chat_id)
                    stk_id = settings.get("promo_sticker")
                    if stk_id and stk_id.strip():
                        stk = await app.bot.send_sticker(chat_id=chat_id, sticker=stk_id.strip())
                        asyncio.create_task(_auto_delete(stk, 60))
                except Exception:
                    pass

                sent = await app.bot.send_message(
                    chat_id=chat_id,
                    text=PROMO_TEXT,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                # Automatically delete promo message after 1 minute (60 seconds)
                asyncio.create_task(_auto_delete(sent, 60))
            except Exception as e:
                logger.debug(f"Failed to send promo message to chat {chat_id}: {e}")

        # Sleep for 10 minutes (600 seconds)
        await asyncio.sleep(600)


@admin_only
async def set_promo_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set animated sticker for promotional broadcast by replying to a sticker or passing ID."""
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
                text="📌 <b>যে অ্যানিমেটেড স্টিকারটি বিজ্ঞাপনে সেট করতে চান:</b>\nগ্রুপে সেই স্টিকারে <b>Reply</b> করে <code>/setpromosticker</code> লিখুন।",
                parse_mode="HTML"
            )
        except Exception:
            pass
        return

    await update_chat_setting(chat_id, "promo_sticker", stk_id)
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="✅ <b>বিজ্ঞাপনের অ্যানিমেটেড স্টিকার সফলভাবে সেট ও সক্রিয় করা হয়েছে!</b>\n\n👇 নিচে বিজ্ঞাপনের স্টিকারের টেস্ট প্রিভিউ দেখানো হলো:",
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
async def del_promo_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove promotional broadcast sticker."""
    chat_id = update.effective_chat.id
    await update_chat_setting(chat_id, "promo_sticker", "")
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🗑️ <b>বিজ্ঞাপনের স্টিকার মুছে ফেলা হয়েছে।</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass


def register(app: Application) -> None:
    app.add_handler(CommandHandler(["setpromosticker"], set_promo_sticker))
    app.add_handler(CommandHandler(["delpromosticker"], del_promo_sticker))
    logger.info("✅ Promo module handlers registered")
