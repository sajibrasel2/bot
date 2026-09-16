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

import json
ALERT_LIFETIME_SECONDS = 30  # Messages auto-delete after 30 seconds to keep chats clean

BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def generate_service_alert_message(users: list, g_settings: dict) -> str:
    """
    Generates a personalized Service Girl & Anti-Scam notification message,
    tags active chat members for high visibility, and returns text with clickable links.
    Supports single or multiple service girls dynamically.
    """
    # Parse girls list from JSON or fallback
    raw_girls_json = g_settings.get("service_girls_json", "")
    girls = []
    if raw_girls_json:
        try:
            girls = json.loads(raw_girls_json)
        except Exception:
            girls = []
    if not isinstance(girls, list) or not girls:
        # Fallback to single girl fields
        name = g_settings.get("service_girl_name", "জেরিন (Zerin)") or "জেরিন (Zerin)"
        uname = (g_settings.get("service_girl_username", "zerin627") or "zerin627").lstrip("@")
        glink = g_settings.get("service_girl_link") or f"https://t.me/{uname}"
        girls = [{"name": name, "username": uname, "link": glink}]

    # Format the service girls block
    if len(girls) == 1:
        g = girls[0]
        g_name = html.escape(str(g.get("name") or "সার্ভিস গার্ল").strip())
        g_uname = html.escape(str(g.get("username") or "zerin627").strip().lstrip("@"))
        g_link = str(g.get("link") or f"https://t.me/{g_uname}").strip()
        girls_block = (
            f"👉 <b>সার্ভিস গার্ল:</b> <b>{g_name}</b> (👉 <a href=\"{g_link}\">@{g_uname}</a>)\n"
            f"💬 <b>ইনবক্স মেসেজ লিংক:</b> <a href=\"{g_link}\">উনাকে সরাসরি মেসেজ দিতে এখানে চাপ দিন ➜</a>"
        )
    else:
        lines = ["👉 <b>আমাদের অফিসিয়াল ভেরিফায়েড সার্ভিস গার্লস তালিকা:</b>"]
        for idx, g in enumerate(girls, 1):
            bn_num = str(idx).translate(BN_DIGITS)
            g_name = html.escape(str(g.get("name") or f"সার্ভিস গার্ল {idx}").strip())
            g_uname = html.escape(str(g.get("username") or "").strip().lstrip("@"))
            g_link = str(g.get("link") or f"https://t.me/{g_uname}").strip()
            lines.append(f"{bn_num}. 👑 <b>{g_name}:</b> <a href=\"{g_link}\">@{g_uname}</a> (👉 <a href=\"{g_link}\">মেসেজ দিতে এখানে চাপুন ➜</a>)")
        girls_block = "\n".join(lines)

    first_girl = girls[0] if girls else {"name": "জেরিন (Zerin)", "username": "zerin627", "link": "https://t.me/zerin627"}
    first_name = html.escape(str(first_girl.get("name") or "জেরিন (Zerin)"))
    first_uname = html.escape(str(first_girl.get("username") or "zerin627").lstrip("@"))
    first_link = str(first_girl.get("link") or f"https://t.me/{first_uname}")

    admin_username = (g_settings.get("service_admin_username", "rafi0002") or "rafi0002").lstrip("@")
    admin_link = g_settings.get("service_admin_link") or f"https://t.me/{admin_username}"
    main_group_link = g_settings.get("site_gate_custom_link", "https://t.me/alltimefantasyzone") or "https://t.me/alltimefantasyzone"
    raw_template = g_settings.get("service_alert_text") or DEFAULT_SERVICE_ALERT_TEXT

    # Select random active members from chat database to tag (up to 20 users)
    if users and len(users) > 0:
        sample_size = min(20, len(users))
        selected_users = random.sample(users, sample_size)
        tags = []
        for u in selected_users:
            uid = u.get("user_id")
            if not uid or not str(uid).isdigit() or int(uid) <= 0:
                continue
            raw_name = str(u.get("first_name") or "Member").strip()
            fname = html.escape(raw_name) if raw_name else "Member"
            tags.append(f"<a href=\"tg://user?id={uid}\">{fname}</a>")
        mentions_text = " • ".join(tags) if tags else "অনলাইন মেম্বাররা"
    else:
        mentions_text = "অনলাইন মেম্বাররা"

    # If raw_template still has old {service_girl_name} placeholder instead of {service_girls_block}, replace gracefully
    formatted_text = (
        raw_template
        .replace("{service_girls_block}", girls_block)
        .replace("{service_girl_name}", first_name)
        .replace("{service_girl_username}", first_uname)
        .replace("{service_girl_link}", first_link)
        .replace("{admin_username}", html.escape(admin_username))
        .replace("{admin_link}", admin_link)
        .replace("{mentions_text}", mentions_text)
        .replace("{main_group_link}", main_group_link)
    )

    return formatted_text


async def _auto_delete(message, delay: int = ALERT_LIFETIME_SECONDS) -> None:
    """Auto-deletes a broadcast message after delay (default 30s)."""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


_service_alert_running = False


async def service_alert_loop(app: Application) -> None:
    """
    Background loop that broadcasts the official service girl alert notice
    to all groups periodically based on admin dashboard settings (default 15 mins).
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
            interval_mins = max(1, int(g_settings.get("service_alert_interval", "15") or 15))
        except (ValueError, TypeError):
            interval_mins = 15

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
                alert_text = generate_service_alert_message(users, g_settings)

                sent_msg = await app.bot.send_message(
                    chat_id=chat_id,
                    text=alert_text,
                    parse_mode="HTML",
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
    alert_text = generate_service_alert_message(users, g_settings)

    sent_msg = await context.bot.send_message(
        chat_id=chat.id,
        text=alert_text,
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    if sent_msg:
        asyncio.create_task(_auto_delete(sent_msg, delay=ALERT_LIFETIME_SECONDS))


def register(app: Application) -> None:
    app.add_handler(CommandHandler(["servicealert", "sendalert", "girlnotice"], cmd_service_alert))
    logger.info("✅ Service Alert module handlers registered")
