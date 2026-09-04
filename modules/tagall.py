"""
TagAll / Mention All module.
Allows group admins to mention all members in batches.

Commands:
  /tagall [message]  — সবাইকে মেনশন করুন (batches of 5 members)
  /all    [message]  — /tagall এর শর্টকাট
  /mention [message] — /tagall এর শর্টকাট
  /tag    [message]  — /tagall এর শর্টকাট
  /cancel            — চলমান মেনশন বন্ধ করুন
  /tagstop           — চলমান মেনশন বন্ধ করুন
"""

import asyncio
import html
import logging
from telegram import Update
from telegram.ext import Application, ContextTypes, CommandHandler

from database import get_users_for_chat
from modules.utils import admin_only

logger = logging.getLogger(__name__)

# Track active tagging sessions per chat: {chat_id: bool}
_active_tags: dict = {}


async def _auto_delete(message, delay: int = 90) -> None:
    """Auto-deletes a message after specified seconds (default 90s / 1.5 mins)."""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


@admin_only
async def cmd_tagall(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("⛔ এই কমান্ডটি শুধুমাত্র গ্রুপে ব্যবহার করা যাবে।")
        return

    chat_id = chat.id
    if _active_tags.get(chat_id):
        await update.message.reply_text(
            "⚠️ ইতিমধ্যে একটি মেনশন সেশন চলছে!\n"
            "বন্ধ করতে /cancel অথবা /tagstop লিখুন।"
        )
        return

    # Extract optional custom message
    custom_msg = " ".join(context.args).strip() if context.args else ""
    header_text = f"📢 <b>{html.escape(custom_msg)}</b>" if custom_msg else "📢 <b>সবার মনোযোগ আকর্ষণ করা হচ্ছে!</b>"

    users = await get_users_for_chat(chat_id)

    # Dynamically merge all chat administrators into the tagging list
    try:
        admins = await chat.get_administrators()
        existing_uids = {u["user_id"] for u in (users or [])}
        for a in admins:
            if not a.user.is_bot and a.user.id not in existing_uids:
                users.append({
                    "user_id": a.user.id,
                    "first_name": a.user.first_name or "Admin",
                    "username": a.user.username or ""
                })
                existing_uids.add(a.user.id)
    except Exception:
        pass

    if not users:
        await update.message.reply_html(
            "ℹ️ <b>এখনো কোনো সদস্যের তথ্য ডেটাবেজে জমা হয়নি!</b>\n"
            "মেম্বাররা গ্রুপে মেসেজ দিলে বা নতুন মেম্বার জয়েন করলে বট স্বয়ংক্রিয়ভাবে তালিকায় যুক্ত করে নেবে।"
        )
        return

    _active_tags[chat_id] = True
    total_users = len(users)

    init_msg = await update.message.reply_html(
        f"🚀 <b>মেনশন প্রক্রিয়া শুরু হচ্ছে...</b>\n"
        f"👥 মোট সদস্য: <b>{total_users}</b> জন (প্রতি মেসেজে ২০ জন)\n"
        f"🛑 বন্ধ করতে লিখুন: <code>/cancel</code>"
    )
    if init_msg:
        asyncio.create_task(_auto_delete(init_msg, delay=90))

    batch_size = 20
    try:
        for i in range(0, total_users, batch_size):
            if not _active_tags.get(chat_id):
                stop_msg = await context.bot.send_message(chat_id=chat_id, text="🛑 <b>মেনশন প্রক্রিয়া বন্ধ করা হয়েছে।</b>", parse_mode="HTML")
                if stop_msg:
                    asyncio.create_task(_auto_delete(stop_msg, delay=90))
                return

            batch = users[i:i + batch_size]
            mentions = []
            for u in batch:
                uid = u["user_id"]
                fname = html.escape(u["first_name"] or "Member")
                mentions.append(f"<a href=\"tg://user?id={uid}\">{fname}</a>")

            text = f"{header_text}\n👉 " + " • ".join(mentions)

            try:
                sent_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="HTML"
                )
                if sent_msg:
                    asyncio.create_task(_auto_delete(sent_msg, delay=90))
            except Exception as e:
                logger.debug(f"Tagall batch error in chat {chat_id}: {e}")

            # Sleep 2 seconds between batches
            await asyncio.sleep(2)

        if _active_tags.get(chat_id):
            done_msg = await context.bot.send_message(chat_id=chat_id, text="✅ <b>সফলভাবে সকল সদস্যকে মেনশন করা সম্পন্ন হয়েছে!</b>", parse_mode="HTML")
            if done_msg:
                asyncio.create_task(_auto_delete(done_msg, delay=90))

    finally:
        _active_tags[chat_id] = False


@admin_only
async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    chat_id = chat.id

    if _active_tags.get(chat_id):
        _active_tags[chat_id] = False
        await update.message.reply_html("🛑 <b>মেনশন প্রক্রিয়া তাৎক্ষণিক থামানো হয়েছে!</b>")
    else:
        await update.message.reply_text("ℹ️ বর্তমানে কোনো সক্রিয় মেনশন প্রক্রিয়া চলছে না (বা ইতিমধ্যে শেষ হয়ে গেছে)।")


def register(app: Application) -> None:
    app.add_handler(CommandHandler(["tagall", "all", "mention", "tag"], cmd_tagall))
    app.add_handler(CommandHandler(["cancel", "tagstop", "canceltag", "stop"], cmd_cancel))
    logger.info("✅ TagAll / Mention module registered")
