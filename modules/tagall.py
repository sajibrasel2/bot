"""
TagAll / Mention All module.
Allows group admins to mention all members in batches.
Features:
  - Dynamic initial-based mention (~100 members/msg up to Telegram 4096 char limit)
  - Auto-delete of admin commands and bot notices
  - Daily automated 11:00 PM (23:00 BST) scheduled tagall for all active groups

Commands:
  /tagall [message]  — সবাইকে মেনশন করুন (~১০০ জন/মেসেজ)
  /all    [message]  — /tagall এর শর্টকাট
  /mention [message] — /tagall এর শর্টকাট
  /tag    [message]  — /tagall এর শর্টকাট
  /cancel            — চলমান মেনশন বন্ধ করুন
  /tagstop           — চলমান মেনশন বন্ধ করুন
  /autotag           — রাত ১১টার অটো-ট্যাগ শিডিউল দেখুন / টেস্ট করুন
"""

import asyncio
import datetime
import html
import logging
from telegram import Update
from telegram.ext import Application, ContextTypes, CommandHandler

from database import get_users_for_chat, get_all_chat_ids
from modules.utils import admin_only

logger = logging.getLogger(__name__)

# Track active tagging sessions per chat: {chat_id: bool}
_active_tags: dict = {}

# Bangladesh Standard Time timezone (UTC+6)
BST = datetime.timezone(datetime.timedelta(hours=6))


async def _auto_delete(message, delay: int = 90) -> None:
    """Auto-deletes a message after specified seconds (default 90s / 1.5 mins)."""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


async def execute_tagall(bot, chat_id: int, custom_msg: str = "") -> bool:
    """Core tagall engine: mentions all group members in dynamic initials batches (~100/msg)."""
    if _active_tags.get(chat_id):
        logger.info(f"TagAll already running in chat {chat_id}, skipping duplicate.")
        return False

    header_text = f"📢 <b>{html.escape(custom_msg)}</b>" if custom_msg else "📢 <b>সবার মনোযোগ আকর্ষণ করা হচ্ছে!</b>"

    users = await get_users_for_chat(chat_id)

    # Dynamically merge all chat administrators into the tagging list
    try:
        chat = await bot.get_chat(chat_id)
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
        no_users = await bot.send_message(
            chat_id=chat_id,
            text="ℹ️ <b>এখনো কোনো সদস্যের তথ্য ডেটাবেজে জমা হয়নি!</b>\n"
                 "মেম্বাররা গ্রুপে মেসেজ দিলে বা নতুন মেম্বার জয়েন করলে বট স্বয়ংক্রিয়ভাবে তালিকায় যুক্ত করে নেবে।",
            parse_mode="HTML"
        )
        if no_users:
            asyncio.create_task(_auto_delete(no_users, delay=15))
        return False

    _active_tags[chat_id] = True
    total_users = len(users)

    # Pre-build dynamic batches (packing ~100+ members up to 3900 chars safety limit using name initial)
    batches = []
    current_batch = []
    current_len = len(header_text) + 10  # header + "\n👉 "

    for u in users:
        uid = u["user_id"]
        name = (u["first_name"] or "").strip()
        char = html.escape(name[0]) if name else "👤"
        mention = f'<a href="tg://user?id={uid}">{char}</a>'

        added_len = len(mention) + 1  # mention + space
        if current_len + added_len > 3900 and current_batch:
            batches.append(current_batch)
            current_batch = [mention]
            current_len = len(header_text) + 10 + len(mention)
        else:
            current_batch.append(mention)
            current_len += added_len

    if current_batch:
        batches.append(current_batch)

    total_batches = len(batches)

    init_msg = await bot.send_message(
        chat_id=chat_id,
        text=f"🚀 <b>মেনশন প্রক্রিয়া শুরু হচ্ছে...</b>\n"
             f"👥 মোট সদস্য: <b>{total_users}</b> জন (প্রতি মেসেজে সর্বোচ্চ ~১০০ জন)\n"
             f"📦 মোট ব্যাচ: <b>{total_batches}</b> টি\n"
             f"🛑 বন্ধ করতে লিখুন: <code>/cancel</code>",
        parse_mode="HTML"
    )
    if init_msg:
        asyncio.create_task(_auto_delete(init_msg, delay=60))

    try:
        for batch_idx, batch_mentions in enumerate(batches, start=1):
            if not _active_tags.get(chat_id):
                stop_msg = await bot.send_message(
                    chat_id=chat_id,
                    text="🛑 <b>মেনশন প্রক্রিয়া বন্ধ করা হয়েছে।</b>",
                    parse_mode="HTML"
                )
                if stop_msg:
                    asyncio.create_task(_auto_delete(stop_msg, delay=30))
                return False

            text = f"{header_text}\n👉 " + " ".join(batch_mentions)

            try:
                sent_msg = await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="HTML"
                )
                if sent_msg:
                    asyncio.create_task(_auto_delete(sent_msg, delay=90))
            except Exception as e:
                logger.debug(f"Tagall batch {batch_idx} error in chat {chat_id}: {e}")

            # Sleep 1.2 seconds between batches (optimized for Telegram rate limits)
            await asyncio.sleep(1.2)

        if _active_tags.get(chat_id):
            done_msg = await bot.send_message(
                chat_id=chat_id,
                text="✅ <b>সফলভাবে সকল সদস্যকে মেনশন করা সম্পন্ন হয়েছে!</b>",
                parse_mode="HTML"
            )
            if done_msg:
                asyncio.create_task(_auto_delete(done_msg, delay=30))

        return True
    finally:
        _active_tags[chat_id] = False


@admin_only
async def cmd_tagall(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("⛔ এই কমান্ডটি শুধুমাত্র গ্রুপে ব্যবহার করা যাবে।")
        return

    chat_id = chat.id

    # Auto-delete admin's /tagall command message in 3 seconds (keeps group clean)
    if update.message:
        asyncio.create_task(_auto_delete(update.message, delay=3))

    if _active_tags.get(chat_id):
        warn_msg = await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ ইতিমধ্যে একটি মেনশন সেশন চলছে!\nবন্ধ করতে /cancel অথবা /tagstop লিখুন。"
        )
        if warn_msg:
            asyncio.create_task(_auto_delete(warn_msg, delay=10))
        return

    # Extract optional custom message
    custom_msg = " ".join(context.args).strip() if context.args else ""
    await execute_tagall(context.bot, chat_id, custom_msg)


@admin_only
async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    chat_id = chat.id

    if update.message:
        asyncio.create_task(_auto_delete(update.message, delay=3))

    if _active_tags.get(chat_id):
        _active_tags[chat_id] = False
        reply = await context.bot.send_message(chat_id=chat_id, text="🛑 <b>মেনশন প্রক্রিয়া তাৎক্ষণিক থামানো হয়েছে!</b>", parse_mode="HTML")
        if reply:
            asyncio.create_task(_auto_delete(reply, delay=15))
    else:
        reply = await context.bot.send_message(chat_id=chat_id, text="ℹ️ বর্তমানে কোনো সক্রিয় মেনশন প্রক্রিয়া চলছে না (বা ইতিমধ্যে শেষ হয়ে গেছে)।")
        if reply:
            asyncio.create_task(_auto_delete(reply, delay=10))


@admin_only
async def cmd_autotag_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows auto-tag schedule info and allows manual test trigger."""
    chat = update.effective_chat
    if update.message:
        asyncio.create_task(_auto_delete(update.message, delay=3))

    arg = (context.args[0].lower() if context.args else "")
    if arg == "test":
        reply = await context.bot.send_message(
            chat_id=chat.id,
            text="⚡ <b>রাত ১১:০০ টার অটো-ট্যাগ টেস্ট শুরু করা হচ্ছে...</b>",
            parse_mode="HTML"
        )
        if reply:
            asyncio.create_task(_auto_delete(reply, delay=10))
        await execute_tagall(context.bot, chat.id, custom_msg="রাত ১১:০০ টা! সবার জন্য বিশেষ আড্ডা ও নোটিশ 🔞")
        return

    now_bst = datetime.datetime.now(BST)
    curr_time_str = now_bst.strftime("%I:%M:%S %p")
    info_msg = await context.bot.send_message(
        chat_id=chat.id,
        text=(
            f"⏰ <b>অটো-ট্যাগ শিডিউল ইনফো</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🕒 <b>বর্তমান সময় (বাংলাদেশ):</b> <code>{curr_time_str}</code>\n"
            f"🔔 <b>নির্ধারিত সময়:</b> প্রতিদিন রাত <b>১১:০০ টা (23:00 BST)</b>\n"
            f"🎯 <b>টার্গেট:</b> গ্রুপের সকল সদস্যকে অটো-ট্যাগ (~১০০ জন/মেসেজ)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>এখনই টেস্ট করতে লিখুন:</i> <code>/autotag test</code>"
        ),
        parse_mode="HTML"
    )
    if info_msg:
        asyncio.create_task(_auto_delete(info_msg, delay=30))


async def scheduled_daily_tagall_loop(app: Application) -> None:
    """Runs daily at 11:00 PM (23:00 BST / UTC+6) to automatically tag all members in active groups."""
    last_run_date = ""

    # Initial delay to let bot boot completely
    await asyncio.sleep(15)

    while True:
        try:
            now = datetime.datetime.now(BST)
            today_str = now.strftime("%Y-%m-%d")

            # Check if it's 11:00 PM (23:00) Bangladesh Time and hasn't run today yet
            if now.hour == 23 and now.minute == 0 and last_run_date != today_str:
                last_run_date = today_str
                logger.info(f"⏰ [AutoTagAll] Triggering scheduled 11:00 PM tagall on {today_str} (BST)")

                chat_ids = await get_all_chat_ids()
                # Target active groups only (chat_id < 0)
                group_ids = [cid for cid in set(chat_ids) if cid and cid < 0]

                for cid in group_ids:
                    try:
                        c = await app.bot.get_chat(cid)
                        if c.type in ("group", "supergroup"):
                            logger.info(f"📢 [AutoTagAll] Starting 11:00 PM auto-tagall in {cid} ({c.title})")
                            await execute_tagall(
                                app.bot,
                                cid,
                                custom_msg="রাত ১১:০০ টা! সবার জন্য বিশেষ আড্ডা ও নোটিশ 🔞"
                            )
                            await asyncio.sleep(5)  # Pause between groups
                    except Exception as e:
                        logger.debug(f"[AutoTagAll] Could not tag group {cid}: {e}")

            # Sleep 25 seconds before checking again
            await asyncio.sleep(25)
        except Exception as e:
            logger.error(f"[AutoTagAll] Scheduler error: {e}")
            await asyncio.sleep(30)


def register(app: Application) -> None:
    app.add_handler(CommandHandler(["tagall", "all", "mention", "tag"], cmd_tagall))
    app.add_handler(CommandHandler(["cancel", "tagstop", "canceltag", "stop"], cmd_cancel))
    app.add_handler(CommandHandler(["autotag", "autotagall"], cmd_autotag_info))
    logger.info("✅ TagAll / Mention module registered")
