"""
Service Alert Module — Automated Official Service Girl & Anti-Scam Notice System.
Broadcasts periodic warning messages to protect members from fake scam profiles,
directs members to the verified service girl, and promotes the main Dark Romance group.
All settings are controllable via the Web Admin Dashboard.
"""

import asyncio
import logging
import random
import time
import html
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ContextTypes, CommandHandler
from database import (
    get_all_chat_ids, get_chat_settings, get_users_for_chat,
    get_all_global_settings, DEFAULT_SERVICE_ALERT_TEXT
)
from modules.utils import admin_only, auto_delete_message

logger = logging.getLogger(__name__)

ALERT_LIFETIME_SECONDS = 180  # Messages auto-delete after 3 minutes (180s) to keep chats clean


def generate_service_alert_message(users: list, g_settings: dict) -> tuple:
    """
    Generates a personalized Service Girl & Anti-Scam notification message,
    tags active chat members for high visibility, and returns (text, keyboard).
    """
    girl_name = g_settings.get("service_girl_name", "Sadia Jahan") or "Sadia Jahan"
    girl_username = (g_settings.get("service_girl_username", "sadia4392") or "sadia4392").lstrip("@")
    girl_link = g_settings.get("service_girl_link") or f"https://t.me/{girl_username}"
    btn_text = g_settings.get("service_alert_btn_text", "💬 সরাসরি সাদিয়াকে ইনবক্স করুন ➜") or "💬 সরাসরি সাদিয়াকে ইনবক্স করুন ➜"
    btn_url = g_settings.get("service_alert_btn_url") or girl_link
    main_group_link = g_settings.get("site_gate_custom_link", "https://t.me/alltimefantasyzone") or "https://t.me/alltimefantasyzone"
    raw_template = g_settings.get("service_alert_text") or DEFAULT_SERVICE_ALERT_TEXT

    # Select random active members from chat database to tag (up to 20 users)
    if users and len(users) > 0:
        sample_size = min(20, len(users))
        selected_users = random.sample(users, sample_size)
        tags = []
        for u in selected_users:
            fname = html.escape(u.get("first_name") or "Member")
            uid = u.get("user_id")
            tags.append(f"<a href=\"tg://user?id={uid}\">{fname}</a>")
        mentions_text = " • ".join(tags)
    else:
        mentions_text = "অনলাইন মেম্বাররা"

    # Replace placeholders safely
    formatted_text = (
        raw_template
        .replace("{service_girl_name}", html.escape(girl_name))
        .replace("{service_girl_username}", html.escape(girl_username))
        .replace("{service_girl_link}", girl_link)
        .replace("{mentions_text}", mentions_text)
        .replace("{main_group_link}", main_group_link)
    )

    # Share URL for viral forwarding
    share_text_encoded = urllib.parse.quote(
        f"⚠️ প্রতারক থেকে সাবধান! আমাদের অফিশিয়াল ভেরিফায়েড সার্ভিস গার্ল {girl_name} (@{girl_username}) এর সাথে যোগাযোগ করতে যুক্ত হোন: {main_group_link}"
    )
    forward_link = f"https://t.me/share/url?url={main_group_link}&text={share_text_encoded}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(text=btn_text, url=btn_url)],
        [InlineKeyboardButton(text="🔥 মূল গ্রুপে জয়েন করুন (Dark Romance)", url=main_group_link)],
        [InlineKeyboardButton(text="📤 বন্ধুদের শেয়ার করুন (Share) 🔓", url=forward_link)],
        [InlineKeyboardButton(text="🔞 হট ভিডিও গ্যালারি (Web)", url="https://techandclick.site/bot/videos.html")],
    ])

    return formatted_text, keyboard


async def _auto_delete(message, delay: int = ALERT_LIFETIME_SECONDS) -> None:
    """Auto-deletes a broadcast message after delay (default 180s)."""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


_service_alert_running = False


async def service_alert_loop(app: Application) -> None:
    """
    Background loop that broadcasts the official service girl alert notice
    to all groups periodically based on admin dashboard settings (default 30 mins).
    """
    global _service_alert_running
    if _service_alert_running:
        logger.info("ℹ️ Service alert loop is already running, skipping duplicate initialization.")
        return
    _service_alert_running = True

    # Initial delay after bot boot
    await asyncio.sleep(15)

    while True:
        try:
            g_settings = await get_all_global_settings()
        except Exception as e:
            logger.error(f"Error reading global settings for service alert: {e}")
            await asyncio.sleep(60)
            continue

        enabled = (g_settings.get("service_alert_enabled", "1") == "1")
        try:
            interval_mins = max(1, int(g_settings.get("service_alert_interval", "30") or 30))
        except (ValueError, TypeError):
            interval_mins = 30

        if not enabled:
            # Check back in 30 seconds if feature is re-enabled from dashboard
            await asyncio.sleep(30)
            continue

        try:
            chat_ids = await get_all_chat_ids()
        except Exception as e:
            logger.error(f"Error fetching chat IDs for service alert broadcast: {e}")
            await asyncio.sleep(interval_mins * 60)
            continue

        all_unique_ids = set(chat_ids)
        target_chats = set()

        for cid in all_unique_ids:
            try:
                if not cid:
                    continue
                c = await app.bot.get_chat(cid)
                if c.type == "private":
                    continue
                if c.type in ("group", "supergroup") and c.linked_chat_id and (c.linked_chat_id in all_unique_ids):
                    continue
                target_chats.add(cid)
            except Exception:
                target_chats.add(cid)

        for chat_id in target_chats:
            try:
                users = await get_users_for_chat(chat_id)
                alert_text, keyboard = generate_service_alert_message(users, g_settings)

                sent_msg = await app.bot.send_message(
                    chat_id=chat_id,
                    text=alert_text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                    disable_web_page_preview=True
                )
                if sent_msg:
                    asyncio.create_task(_auto_delete(sent_msg, delay=ALERT_LIFETIME_SECONDS))
            except Exception as e:
                logger.debug(f"Failed to send service alert message to chat {chat_id}: {e}")

        # Sleep for the configured interval in minutes
        await asyncio.sleep(interval_mins * 60)


@admin_only
async def cmd_service_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trigger an instant service alert broadcast in the current chat."""
    chat = update.effective_chat
    users = await get_users_for_chat(chat.id)
    g_settings = await get_all_global_settings()
    alert_text, keyboard = generate_service_alert_message(users, g_settings)

    sent_msg = await context.bot.send_message(
        chat_id=chat.id,
        text=alert_text,
        parse_mode="HTML",
        reply_markup=keyboard,
        disable_web_page_preview=True
    )
    if sent_msg:
        asyncio.create_task(_auto_delete(sent_msg, delay=ALERT_LIFETIME_SECONDS))


def register(app: Application) -> None:
    app.add_handler(CommandHandler(["servicealert", "sendalert", "girlnotice"], cmd_service_alert))
    logger.info("✅ Service Alert module handlers registered")
