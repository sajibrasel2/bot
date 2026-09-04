"""
Force Add / Chat Unlock Module.
Requires users to add a specified number of members to the group before they are allowed to send messages.
Can be toggled ON/OFF and configured from the Web Dashboard or Telegram admin commands.
"""

import asyncio
import logging
import html
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from telegram.helpers import mention_html

from database import (
    get_chat_settings, update_chat_setting, add_invite,
    get_user_invite_count, get_top_inviters
)
from modules.utils import admin_only, is_admin
from config import OWNER_ID

logger = logging.getLogger(__name__)


async def _auto_delete(message, delay: int = 7) -> None:
    """Auto-deletes a message after specified seconds."""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


# ── 1. Track New Members Added By Users ──────────────

async def handle_member_invites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tracks when an existing user adds new friends/members to the group."""
    msg = update.effective_message
    chat = update.effective_chat
    inviter = update.effective_user

    if not msg or not msg.new_chat_members or not chat or not inviter:
        return
    if chat.type == "private" or inviter.is_bot:
        return

    settings = await get_chat_settings(chat.id)
    req_count = int(settings.get("force_add_count") or 5)
    enabled = int(settings.get("force_add_enabled", 0))

    added_count = 0
    total_invites = 0

    for new_user in msg.new_chat_members:
        # Ignore bots and self-joins
        if new_user.is_bot or new_user.id == inviter.id:
            continue
        total_invites = await add_invite(chat.id, inviter.id, new_user.id)
        added_count += 1

    if added_count > 0 and enabled:
        # If the user just reached or crossed the unlock requirement
        if total_invites == req_count or (total_invites - added_count < req_count and total_invites >= req_count):
            try:
                congrats = await msg.reply_html(
                    f"🎉 <b>অভিনন্দন {mention_html(inviter.id, inviter.first_name)}!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"✅ আপনি সফলভাবে <b>{total_invites} জন</b> বন্ধুকে গ্রুপে অ্যাড করেছেন।\n"
                    f"🔓 আপনার চ্যাট ও মেসেজ লক <b>সম্পূর্ণ আনলক</b> করা হয়েছে!\n"
                    f"💬 এখন আপনি গ্রুপে যেকোনো মেসেজ ও চ্যাট করতে পারবেন।"
                )
                asyncio.create_task(_auto_delete(congrats, 15))
            except Exception:
                pass


# ── 2. Message Enforcement (Chat Lock for Non-Admins) ──

async def check_force_add_lock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Intercepts messages in groups to verify if the sender has unlocked chat by adding required friends."""
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not msg or not chat or not user or user.is_bot:
        return
    if chat.type == "private":
        return

    # Check if user is an admin or owner
    is_adm = (user.id == OWNER_ID) or await is_admin(update, user_id=user.id)
    if is_adm:
        return

    # Exempt public allowed commands
    text = (msg.text or msg.caption or "").strip().lower()
    if text.startswith(("/myinvites", "/invites", "/top", "/topinvites", "/rules", "/start", "/help")):
        return

    # Check settings for this group
    settings = await get_chat_settings(chat.id)
    enabled = int(settings.get("force_add_enabled", 0) or 0)
    req_count = int(settings.get("force_add_count") or 5)
    user_invites = await get_user_invite_count(chat.id, user.id)

    logger.info(f"🔍 ForceAdd check: user={user.id} ({user.first_name}) in chat={chat.id} ({chat.title}): enabled={enabled}, invites={user_invites}/{req_count}")

    if enabled != 1:
        return

    if user_invites < req_count:
        logger.info(f"⛔ ForceAdd Locking user {user.id} in chat {chat.id} ({user_invites}/{req_count})")
        # Delete the unauthorized message
        try:
            await msg.delete()
        except Exception as e:
            logger.warning(f"Could not delete message in chat {chat.id} from user {user.id}: {e}")

        remaining = req_count - user_invites
        alert_text = (
            f"⛔ <b>চ্যাট লক করা আছে!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {mention_html(user.id, user.first_name)} (<code>{user.id}</code>)\n"
            f"🔒 গ্রুপে মেসেজ লিখতে ও চ্যাট করতে হলে আপনাকে অবশ্যই <b>{req_count} জন বন্ধুকে</b> অ্যাড করতে হবে।\n\n"
            f"📊 <b>আপনার অগ্রগতি:</b> <code>{user_invites}/{req_count}</code> জন\n"
            f"👉 <i>দয়া করে আরও <b>{remaining} জন</b> বন্ধুকে গ্রুপে অ্যাড করে চ্যাট আনলক করুন!</i>"
        )

        invite_link = ""
        try:
            if chat.username:
                invite_link = f"https://t.me/{chat.username}"
            elif chat.invite_link:
                invite_link = chat.invite_link
            else:
                invite_link = await chat.export_invite_link()
        except Exception:
            invite_link = f"https://t.me/{chat.username}" if chat.username else "https://techandclick.site/bot/"

        share_text = urllib.parse.quote(f"🔥 {chat.title or 'আমাদের গ্রুপে'} জয়েন করুন এবং সরাসরি আড্ডা দিন! 💬")
        share_url = f"https://t.me/share/url?url={invite_link}&text={share_text}"

        buttons = [
            [
                InlineKeyboardButton(text="👥 বন্ধুদের ইনভাইট পাঠান (Invite/Share)", url=share_url),
            ],
            [
                InlineKeyboardButton(text="📊 আমার অগ্রগতি", callback_data=f"myinv_{user.id}"),
                InlineKeyboardButton(text="🏆 সেরা ইনভাইটার", callback_data=f"topinv_{chat.id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)

        try:
            sent = await context.bot.send_message(
                chat_id=chat.id,
                text=alert_text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            # Message stays visible for 60 seconds (1 minute) so user has plenty of time to read & act
            asyncio.create_task(_auto_delete(sent, 60))
        except Exception as e:
            logger.warning(f"Could not send force add lock notice in chat {chat.id}: {e}")


# ── 3. Member Commands ─────────────────────────────

async def cmd_myinvites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows user's current invite count and progress."""
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    settings = await get_chat_settings(chat.id)
    req_count = int(settings.get("force_add_count") or 5)
    enabled = int(settings.get("force_add_enabled", 0))
    count = await get_user_invite_count(chat.id, user.id)

    if enabled:
        if count >= req_count:
            status_text = "✅ <b>স্ট্যাটাস:</b> চ্যাট সম্পূর্ণ আনলকড (Unlocked) 🎉"
        else:
            status_text = f"🔒 <b>স্ট্যাটাস:</b> লকড (আরও {req_count - count} জন অ্যাড বাকি)"
    else:
        status_text = "ℹ️ এই গ্রুপে বর্তমানে ফোর্স-অ্যাড সিস্টেম নিষ্ক্রিয়।"

    text = (
        f"📊 <b>আপনার ইনভাইট অগ্রগতি</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {mention_html(user.id, user.first_name)} (<code>{user.id}</code>)\n"
        f"👥 আপনার মোট অ্যাড: <b>{count} জন</b>\n"
        f"🎯 প্রয়োজনীয় টার্গেট: <b>{req_count} জন</b>\n"
        f"{status_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 সেরা ইনভাইটারদের দেখতে <code>/top</code> লিখুন।"
    )

    try:
        sent = await update.message.reply_html(text)
        asyncio.create_task(_auto_delete(sent, 6))
        if update.message:
            asyncio.create_task(_auto_delete(update.message, 1))
    except Exception:
        pass


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows leaderboard of top 10 inviters in the group."""
    chat = update.effective_chat
    if not chat:
        return

    top_list = await get_top_inviters(chat.id, limit=10)
    if not top_list:
        try:
            sent = await update.message.reply_html("📊 <b>এখনও কোনো সদস্য নতুন কাউকে ইনভাইট করেনি।</b>")
            asyncio.create_task(_auto_delete(sent, 6))
            if update.message:
                asyncio.create_task(_auto_delete(update.message, 1))
        except Exception:
            pass
        return

    badges = ["👑", "🥇", "🥈", "🥉", "🎖️", "🎖️", "🎖️", "🎖️", "🎖️", "🎖️"]
    lines = []

    for i, row in enumerate(top_list):
        badge = badges[i] if i < len(badges) else "▫️"
        fname = html.escape(row.get("first_name") or f"User {row['inviter_id']}")
        uname = f" (@{row['username']})" if row.get("username") else ""
        cnt = row.get("invite_count", 0)
        lines.append(f"{badge} <b>{i+1}. {fname}</b>{uname} ─ <b>{cnt} জন</b>")

    text = (
        f"🏆 <b>সেরা ইনভাইটার লিডারবোর্ড</b> 🏆\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines) +
        f"\n━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 আপনার অগ্রগতি দেখতে <code>/myinvites</code> লিখুন।"
    )

    try:
        sent = await update.message.reply_html(text)
        asyncio.create_task(_auto_delete(sent, 10))
        if update.message:
            asyncio.create_task(_auto_delete(update.message, 1))
    except Exception:
        pass


# ── 4. Admin Control Command ────────────────────────

@admin_only
async def cmd_forceadd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Configure Force Add via Telegram command: /forceadd on | off | <count>."""
    chat = update.effective_chat
    args = context.args

    if not args:
        settings = await get_chat_settings(chat.id)
        en = "চালু (ON) ✅" if settings.get("force_add_enabled", 0) else "বন্ধ (OFF) ❌"
        cnt = settings.get("force_add_count") or 5
        await update.message.reply_html(
            f"⚙️ <b>ফোর্স অ্যাড (চ্যাট আনলক) সেটিংস:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔘 বর্তমান অবস্থা: <b>{en}</b>\n"
            f"🎯 প্রয়োজনীয় সংখ্যা: <b>{cnt} জন</b>\n\n"
            f"<b>কমান্ড ব্যবহার:</b>\n"
            f"• <code>/forceadd on</code> ─ চালু করুন\n"
            f"• <code>/forceadd off</code> ─ বন্ধ করুন\n"
            f"• <code>/forceadd 5</code> ─ সংখ্যা সেট করুন"
        )
        return

    arg = args[0].strip().lower()
    if arg in ("on", "enable", "true", "1"):
        await update_chat_setting(chat.id, "force_add_enabled", 1)
        await update.message.reply_html("✅ <b>ফোর্স অ্যাড সিস্টেম চালু করা হয়েছে!</b>\nমেম্বারদের চ্যাট করতে হলে নির্ধারিত সংখ্যক বন্ধু অ্যাড করতে হবে।")
    elif arg in ("off", "disable", "false", "0"):
        await update_chat_setting(chat.id, "force_add_enabled", 0)
        await update.message.reply_html("❌ <b>ফোর্স অ্যাড সিস্টেম বন্ধ করা হয়েছে!</b>\nসবাই সাধারণভাবে চ্যাট করতে পারবে।")
    elif arg.isdigit():
        new_cnt = max(1, int(arg))
        await update_chat_setting(chat.id, "force_add_count", new_cnt)
        await update_chat_setting(chat.id, "force_add_enabled", 1)
        await update.message.reply_html(f"✅ <b>টার্গেট আপডেট:</b> এখন চ্যাট আনলক করতে <b>{new_cnt} জন</b> বন্ধুকে অ্যাড করতে হবে।")
    else:
        await update.message.reply_text("ভুল ইনপুট! ব্যবহার: /forceadd on | off | <সংখ্যা>")


# ── 5. Inline Button Callback Queries ─────────────────

async def callback_forceadd_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    if data.startswith("myinv_"):
        try:
            target_user_id = int(data.split("_")[1])
        except (ValueError, IndexError):
            return

        if query.from_user.id != target_user_id:
            await query.answer("⚠️ এটি অন্য মেম্বারের নোটিশ! নিজের অগ্রগতি দেখতে গ্রুপে /myinvites লিখুন।", show_alert=True)
            return

        chat_id = query.message.chat_id if query.message else None
        if not chat_id:
            await query.answer("তথ্য পাওয়া যায়নি।", show_alert=True)
            return

        settings = await get_chat_settings(chat_id)
        req_count = int(settings.get("force_add_count") or 5)
        invites = await get_user_invite_count(chat_id, target_user_id)
        remaining = max(0, req_count - invites)

        if invites >= req_count:
            await query.answer(f"🎉 অভিনন্দন! আপনার চ্যাট সম্পূর্ণ আনলকড ({invites}/{req_count} জন অ্যাড করা হয়েছে)।", show_alert=True)
        else:
            await query.answer(f"📊 আপনার অগ্রগতি: {invites}/{req_count} জন\n👉 চ্যাট আনলক করতে আরও {remaining} জন বন্ধুকে গ্রুপে অ্যাড করুন!", show_alert=True)

    elif data.startswith("topinv_"):
        chat_id = query.message.chat_id if query.message else None
        if not chat_id:
            return
        top_list = await get_top_inviters(chat_id, limit=5)
        if not top_list:
            await query.answer("এখনও কোনো সদস্য ইনভাইট করেনি।", show_alert=True)
            return
        lines = []
        for i, row in enumerate(top_list):
            fname = row.get("first_name") or f"User {row['inviter_id']}"
            cnt = row.get("invite_count", 0)
            lines.append(f"{i+1}. {fname}: {cnt} জন")
        await query.answer("🏆 শীর্ষ ইনভাইটার:\n" + "\n".join(lines), show_alert=True)


# ── 6. Register Handlers ─────────────────────────────

def register(app: Application) -> None:
    # Handler for members adding friends
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_member_invites), group=1)

    # Handler for checking message lock (Runs at top priority group -1 before any other group)
    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND & filters.ChatType.GROUPS,
            check_force_add_lock
        ),
        group=-1
    )

    # Commands
    app.add_handler(CommandHandler(["myinvites", "invites", "myadd"], cmd_myinvites))
    app.add_handler(CommandHandler(["top", "topinvites", "leaderboard"], cmd_top))
    app.add_handler(CommandHandler(["forceadd", "force_add"], cmd_forceadd))

    # Button Callbacks
    app.add_handler(CallbackQueryHandler(callback_forceadd_query, pattern=r"^(myinv_|topinv_)"))
    logger.info("✅ Force Add module handlers registered successfully")
