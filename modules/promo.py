"""
Promotional broadcast module.
Automatically sends a beautiful invitation message to all chats every 10 minutes.
"""

import asyncio
import logging
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application
from database import get_all_chat_ids

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
            InlineKeyboardButton(text="🔞 সরাসরি চ্যাট করুন (Live)", web_app=WebAppInfo(url="https://techandclick.site/bot/"))
        ]])

        for chat_id in chat_ids:
            try:
                # Basic check to make sure chat_id looks valid (positive or negative large integer)
                if chat_id:
                    await app.bot.send_message(
                        chat_id=chat_id,
                        text=PROMO_TEXT,
                        parse_mode="HTML",
                        reply_markup=keyboard
                    )
            except Exception as e:
                # Discard warning for deactivated/kicked chats to keep logs clean
                logger.debug(f"Failed to send promo message to chat {chat_id}: {e}")

        # Sleep for 10 minutes (600 seconds)
        await asyncio.sleep(600)

def register(app: Application) -> None:
    # Start the promo loop in the background of the running event loop
    asyncio.create_task(promo_loop(app))
    logger.info("✅ Repeating promotional broadcast task registered (every 10 minutes)")
