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
    "🔞 <b>আপনার ফ্যান্টাসির দুনিয়া আনলক করতে চান?</b> 🔞\n"
    "━━━━━━━━━━━━━━━━━━━━━━━\n"
    "👥 আমাদের গ্রুপে আপনার <b>৫ জন বন্ধুকে অ্যাড করুন (Invite/Add)</b>!\n\n"
    "🎁 ৫ জন মেম্বার অ্যাড করা সম্পূর্ণ হলে নিচের লিংকে ক্লিক করে সরাসরি আমাদের ভিআইপি চ্যাট রুমে যুক্ত হয়ে যান:\n\n"
    "🔗 <a href=\"https://techandclick.site/bot/\">এখানে ক্লিক করে চ্যাট শুরু করুন</a>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━\n"
    "👉 <i>ইনভাইট করা শেষ হলে লিংকে ক্লিক করতে ভুলবেন না! 🌸</i>"
)

async def _auto_delete(message, delay: int = 60) -> None:
    """Auto-deletes a message after specified seconds."""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


async def promo_loop(app: Application) -> None:
    """Infinite loop that broadcasts promo message every 10 minutes (600 seconds)."""
    # Wait 10 seconds after bot startup before the first broadcast
    await asyncio.sleep(10)
    
    while True:
        try:
            chat_ids = await get_all_chat_ids()
        except Exception as e:
            logger.error(f"Error fetching chat IDs for promo broadcast: {e}")
            await asyncio.sleep(600)
            continue

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(text="🔞 সরাসরি চ্যাট করুন (Live)", url="https://techandclick.site/bot/")
        ]])

        for chat_id in chat_ids:
            try:
                # Basic check to make sure chat_id looks valid (positive or negative large integer)
                if chat_id:
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
                # Discard warning for deactivated/kicked chats to keep logs clean
                logger.debug(f"Failed to send promo message to chat {chat_id}: {e}")

        # Sleep for 10 minutes (600 seconds)
        await asyncio.sleep(600)


@admin_only
async def set_promo_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set animated sticker for promotional broadcast by replying to a sticker or passing ID."""
    msg = update.effective_message
    chat_id = update.effective_chat.id
    stk_id = None

    if msg and msg.reply_to_message and msg.reply_to_message.sticker:
        stk_id = msg.reply_to_message.sticker.file_id
    elif msg and msg.sticker:
        stk_id = msg.sticker.file_id
    elif context.args:
        stk_id = context.args[0].strip()

    if not stk_id:
        try:
            sent = await context.bot.send_message(
                chat_id=chat_id,
                text="📌 <b>যে অ্যানিমেটেড স্টিকারটি বিজ্ঞাপনে সেট করতে চান:</b>\nগ্রুপে সেই স্টিকারে <b>Reply</b> করে <code>/setpromosticker</code> লিখুন।",
                parse_mode="HTML"
            )
            asyncio.create_task(_auto_delete(sent, delay=10))
        except Exception:
            pass
        return

    await update_chat_setting(chat_id, "promo_sticker", stk_id)
    try:
        sent = await context.bot.send_message(
            chat_id=chat_id,
            text="✅ <b>বিজ্ঞাপনের অ্যানিমেটেড স্টিকার সফলভাবে সেট ও সক্রিয় করা হয়েছে!</b>",
            parse_mode="HTML"
        )
        asyncio.create_task(_auto_delete(sent, delay=10))
    except Exception:
        pass

    # Send a quick verification preview of the sticker in the chat
    try:
        preview = await context.bot.send_sticker(chat_id=chat_id, sticker=stk_id)
        asyncio.create_task(_auto_delete(preview, delay=10))
    except Exception:
        pass


@admin_only
async def del_promo_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove promotional broadcast sticker."""
    chat_id = update.effective_chat.id
    await update_chat_setting(chat_id, "promo_sticker", "")
    try:
        sent = await context.bot.send_message(
            chat_id=chat_id,
            text="🗑️ <b>বিজ্ঞাপনের স্টিকার মুছে ফেলা হয়েছে।</b>",
            parse_mode="HTML"
        )
        asyncio.create_task(_auto_delete(sent, delay=8))
    except Exception:
        pass


def register(app: Application) -> None:
    app.add_handler(CommandHandler(["setpromosticker"], set_promo_sticker))
    app.add_handler(CommandHandler(["delpromosticker"], del_promo_sticker))
    logger.info("✅ Promo module handlers registered")
