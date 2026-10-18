"""
Force Add / Chat Unlock Module.
Requires users to add a specified number of members to the group before they are allowed to send messages.
Can be toggled ON/OFF and configured from the Web Dashboard or Telegram admin commands.
"""

import asyncio
import time
import logging
import html
import urllib.parse
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from telegram.helpers import mention_html

from database import (
    get_chat_settings, update_chat_setting, add_invite,
    get_user_invite_count, get_top_inviters,
    is_user_forceadd_unlocked, unlock_user_forceadd, lock_user_forceadd
)
from modules.utils import admin_only, is_admin
from config import OWNER_ID

logger = logging.getLogger(__name__)

MAIN_DARK_ROMANCE_GROUP = "https://t.me/alltimefantasyzone"

try:
    from telegram import LinkPreviewOptions
    _DISABLE_PREVIEW = {"link_preview_options": LinkPreviewOptions(is_disabled=True)}
except Exception:
    _DISABLE_PREVIEW = {"disable_web_page_preview": True}

# Debounce tracker: {chat_id: {user_id: last_alert_timestamp}} to avoid Telegram 429 FloodWait
_last_forceadd_alert: dict = defaultdict(lambda: defaultdict(float))


def _to_int(val, default: int = 0) -> int:
    if val is None:
        return default
    if isinstance(val, (bytes, bytearray)):
        try:
            return int.from_bytes(val, "big")
        except Exception:
            return default
    try:
        return int(val)
    except Exception:
        return default


async def _auto_delete(message, delay: int = 7) -> None:
    """Auto-deletes a message after specified seconds."""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Failed to auto-delete force add alert: {e}")


# ── 1. Track New Members Added By Users ──────────────

async def handle_member_invites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tracks when an existing user adds new friends/members to the group."""
    msg = update.effective_message
    chat = update.effective_chat
    inviter = update.effective_user

    if not msg or not msg.new_chat_members or not chat or not inviter:
        return
    if getattr(chat, "type", "") not in ("group", "supergroup") or inviter.is_bot:
        return

    settings = await get_chat_settings(chat.id)
    req_count = _to_int(settings.get("force_add_count"), 5)
    enabled = _to_int(settings.get("force_add_enabled"), 0)

    added_count = 0
    total_invites = 0

    for new_user in msg.new_chat_members:
        # Ignore bots and self-joins
        if new_user.is_bot or new_user.id == inviter.id:
            continue
        total_invites = await add_invite(chat.id, inviter.id, new_user.id)
        added_count += 1

    if added_count > 0 and enabled:
        # Check if user has already unlocked previously
        already_unlocked = await is_user_forceadd_unlocked(chat.id, inviter.id)
        if not already_unlocked and total_invites >= req_count:
            # Permanently mark as unlocked so raising requirement later will never re-lock them!
            await unlock_user_forceadd(chat.id, inviter.id)
            try:
                congrats_markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton(text="🔥 Join Main Group", url=MAIN_DARK_ROMANCE_GROUP)]
                ])
                congrats = await msg.reply_html(
                    f"🎉 <b>Congratulations {mention_html(inviter.id, inviter.first_name)}!</b>\n"
                    f"✅ You added <b>{total_invites} members</b>. Messaging access is now permanently unlocked! 🔓",
                    reply_markup=congrats_markup,
                    **_DISABLE_PREVIEW
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

    if not msg or not chat or not user:
        return
    if getattr(chat, "type", "") not in ("group", "supergroup"):
        return

    # Ignore service status messages (e.g. member joins, leaves, pins) so welcome and tracking always run
    if bool(msg.new_chat_members or msg.left_chat_member or msg.pinned_message or msg.group_chat_created or msg.supergroup_chat_created):
        return

    # Check if user is our own bot, owner, or chat admin
    if user.id == context.bot.id:
        return
    is_adm = (user.id == OWNER_ID) or await is_admin(update, user_id=user.id)
    if is_adm:
        return

    # Delete messages from unauthorized non-admin external bots immediately
    if user.is_bot:
        try:
            await msg.delete()
        except Exception:
            pass
        return

    # Exempt public allowed commands
    text = (msg.text or msg.caption or "").strip().lower()
    if text.startswith(("/myinvites", "/invites", "/top", "/topinvites", "/rules", "/start", "/help")):
        return

    # Check settings for this group
    settings = await get_chat_settings(chat.id)
    enabled = _to_int(settings.get("force_add_enabled"), 0)
    req_count = _to_int(settings.get("force_add_count"), 5)
    user_invites = await get_user_invite_count(chat.id, user.id)

    logger.info(f"🔍 ForceAdd check: user={user.id} ({user.first_name}) in chat={chat.id} ({chat.title}): enabled={enabled}, invites={user_invites}/{req_count}")

    if enabled != 1:
        return

    # 1. If user is already permanently unlocked, allow them immediately!
    if await is_user_forceadd_unlocked(chat.id, user.id):
        return

    # 2. Check user's current invites in this group
    user_invites = await get_user_invite_count(chat.id, user.id)

    # If user currently meets or exceeds the required count, permanently unlock them now!
    if user_invites >= req_count:
        await unlock_user_forceadd(chat.id, user.id)
        return

    logger.info(f"⛔ ForceAdd Locking user {user.id} in chat {chat.id} ({user_invites}/{req_count})")
    # Delete the unauthorized message
    try:
        await msg.delete()
    except Exception as e:
        logger.warning(f"Could not delete message in chat {chat.id} from user {user.id}: {e}")

    # Debounce: only send alert notice once every 30 seconds per user per chat
    now = time.time()
    if now - _last_forceadd_alert[chat.id][user.id] < 30:
        return
    _last_forceadd_alert[chat.id][user.id] = now

    remaining = req_count - user_invites
    alert_text = (
        f"⛔ <b>Chat Locked!</b> {mention_html(user.id, user.first_name)} (<code>{user.id}</code>)\n"
        f"🔒 Please add <b>{remaining} more member(s)</b> to unlock messaging.\n"
        f"📊 Your Progress: <code>{user_invites}/{req_count}</code> members"
    )

    share_text = urllib.parse.quote(f"🔥 Join our exclusive group & live video chat! 🔞👉 {MAIN_DARK_ROMANCE_GROUP}")
    share_url = f"https://t.me/share/url?url={MAIN_DARK_ROMANCE_GROUP}&text={share_text}"

    buttons = [
        [
            InlineKeyboardButton(text="👥 Add Members", url=share_url),
            InlineKeyboardButton(text="🔥 Main Group", url=MAIN_DARK_ROMANCE_GROUP),
        ],
        [
            InlineKeyboardButton(text="📊 My Progress", callback_data=f"myinv_{user.id}"),
            InlineKeyboardButton(text="🏆 Top Inviters", callback_data=f"topinv_{chat.id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    try:
        sent = await context.bot.send_message(
            chat_id=chat.id,
            text=alert_text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            **_DISABLE_PREVIEW
        )
        # Message stays visible for 15 seconds then auto-deletes
        asyncio.create_task(_auto_delete(sent, 15))
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
    req_count = _to_int(settings.get("force_add_count"), 5)
    enabled = _to_int(settings.get("force_add_enabled"), 0)
    count = await get_user_invite_count(chat.id, user.id)
    is_unlocked = await is_user_forceadd_unlocked(chat.id, user.id) or (count >= req_count)

    if enabled:
        if is_unlocked:
            status_text = "✅ <b>Status:</b> Permanently Unlocked 🎉"
        else:
            remaining = max(1, req_count - count)
            status_text = f"🔒 <b>Status:</b> Locked (Need {remaining} more)"
    else:
        status_text = "ℹ️ Member invite verification is currently disabled in this group."

    text = (
        f"📊 <b>Your Invite Progress</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {mention_html(user.id, user.first_name)} (<code>{user.id}</code>)\n"
        f"👥 Total Invited: <b>{count} members</b>\n"
        f"🎯 Target Required: <b>{req_count} members</b>\n"
        f"{status_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Use <code>/top</code> to view leaderboard."
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
            sent = await update.message.reply_html("📊 <b>No members have invited anyone yet.</b>")
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
        lines.append(f"{badge} <b>{i+1}. {fname}</b>{uname} ─ <b>{cnt} members</b>")

    text = (
        f"🏆 <b>Top Inviters Leaderboard</b> 🏆\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines) +
        f"\n━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 Check your progress with <code>/myinvites</code>"
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
        en_val = _to_int(settings.get("force_add_enabled"), 0)
        en = "চালু (ON) ✅" if en_val == 1 else "বন্ধ (OFF) ❌"
        cnt = _to_int(settings.get("force_add_count"), 5)
        await update.message.reply_html(
            f"⚙️ <b>ফোর্স অ্যাড (চ্যাট আনলক) সেটিংস:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔘 বর্তমান অবস্থা: <b>{en}</b>\n"
            f"🎯 প্রয়োজনীয় সংখ্যা: <b>{cnt} জন</b>\n\n"
            f"<b>কমান্ড তালিকা ও ব্যবহার:</b>\n"
            f"• <code>/forceadd on</code> ─ সিস্টেম চালু করুন\n"
            f"• <code>/forceadd off</code> ─ সিস্টেম বন্ধ করুন\n"
            f"• <code>/forceadd 5</code> ─ সংখ্যা নির্ধারণ করুন\n"
            f"• <code>/forceunlock</code> বা <code>/forceunlock [USER_ID]</code> ─ চ্যাট সরাসরি আজীবন আনলক করতে\n"
            f"• <code>/forcelock</code> বা <code>/forcelock [USER_ID]</code> ─ চ্যাট পুনরায় লক করতে\n\n"
            f"💡 <i>কোনো মেম্বারের মেসেজে রিপ্লাই দিয়ে অথবা সরাসরি টেলিগ্রাম আইডি লিখে আনলক/লক করতে পারেন।</i>"
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
            await query.answer("⚠️ This notification is for another member. Use /myinvites to check yours.", show_alert=True)
            return

        chat_id = query.message.chat_id if query.message else None
        if not chat_id:
            await query.answer("Information not found.", show_alert=True)
            return

        settings = await get_chat_settings(chat_id)
        req_count = _to_int(settings.get("force_add_count"), 5)
        invites = await get_user_invite_count(chat_id, target_user_id)
        is_unlocked = await is_user_forceadd_unlocked(chat_id, target_user_id) or (invites >= req_count)

        if is_unlocked:
            await query.answer(f"🎉 Congratulations! Your chat access is permanently unlocked ({invites} members added).", show_alert=True)
        else:
            remaining = max(0, req_count - invites)
            await query.answer(f"📊 Your Progress: {invites}/{req_count} members\n👉 Please add {remaining} more member(s) to unlock chat access.", show_alert=True)

    elif data.startswith("topinv_"):
        chat_id = query.message.chat_id if query.message else None
        if not chat_id:
            return
        top_list = await get_top_inviters(chat_id, limit=5)
        if not top_list:
            await query.answer("No members have invited anyone yet.", show_alert=True)
            return
        lines = []
        for i, row in enumerate(top_list):
            fname = row.get("first_name") or f"User {row['inviter_id']}"
            cnt = row.get("invite_count", 0)
            lines.append(f"{i+1}. {fname}: {cnt} members")
        await query.answer("🏆 Top Inviters:\n" + "\n".join(lines), show_alert=True)


# ── 6. Admin Manual Unlock / Lock Commands ───────────

@admin_only
async def cmd_force_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to manually permanently unlock a user: /forceunlock <user_id or reply>"""
    chat = update.effective_chat
    msg = update.effective_message
    if not chat or not msg:
        return

    target_id = None
    target_name = "User"
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target_id = msg.reply_to_message.from_user.id
        target_name = msg.reply_to_message.from_user.mention_html()
    elif context.args and context.args[0].isdigit():
        target_id = int(context.args[0])
        target_name = f"ইউজার (<code>{target_id}</code>)"

    if not target_id:
        await msg.reply_html(
            "ℹ️ <b>চ্যাট সরাসরি আজীবন আনলক করার নিয়ম:</b>\n\n"
            "১. মেম্বারের মেসেজে রিপ্লাই দিয়ে লিখুন: <code>/forceunlock</code>\n"
            "অথবা,\n"
            "২. সরাসরি আইডি দিয়ে লিখুন: <code>/forceunlock USER_ID</code>"
        )
        return

    await unlock_user_forceadd(chat.id, target_id)
    await msg.reply_html(f"🔓 {target_name} এর চ্যাট এই গ্রুপে <b>সরাসরি আজীবন আনলক</b> করা হয়েছে।")


@admin_only
async def cmd_force_lock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to manually re-lock a user: /forcelock <user_id or reply>"""
    chat = update.effective_chat
    msg = update.effective_message
    if not chat or not msg:
        return

    target_id = None
    target_name = "User"
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target_id = msg.reply_to_message.from_user.id
        target_name = msg.reply_to_message.from_user.mention_html()
    elif context.args and context.args[0].isdigit():
        target_id = int(context.args[0])
        target_name = f"ইউজার (<code>{target_id}</code>)"

    if not target_id:
        await msg.reply_html(
            "ℹ️ <b>চ্যাট পুনরায় লক করার নিয়ম:</b>\n\n"
            "১. মেম্বারের মেসেজে রিপ্লাই দিয়ে লিখুন: <code>/forcelock</code>\n"
            "অথবা,\n"
            "২. সরাসরি আইডি দিয়ে লিখুন: <code>/forcelock USER_ID</code>"
        )
        return

    await lock_user_forceadd(chat.id, target_id)
    await msg.reply_html(f"🔒 {target_name} এর চ্যাট পুনরায় <b>লক</b> করা হয়েছে।")


# ── 7. Register Handlers ─────────────────────────────

def register(app: Application) -> None:
    # Handler for members adding friends
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_member_invites), group=1)

    # Handler for checking message lock (Runs at top priority group -1 for user messages)
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.ATTACHMENT) & ~filters.COMMAND & filters.ChatType.GROUPS,
            check_force_add_lock
        ),
        group=-1
    )

    # Commands
    app.add_handler(CommandHandler(["myinvites", "invites", "myadd"], cmd_myinvites))
    app.add_handler(CommandHandler(["top", "topinvites", "leaderboard"], cmd_top))
    app.add_handler(CommandHandler(["forceadd", "force_add"], cmd_forceadd))
    app.add_handler(CommandHandler(["forceunlock", "funlock"], cmd_force_unlock))
    app.add_handler(CommandHandler(["forcelock", "flock"], cmd_force_lock))

    # Button Callbacks
    app.add_handler(CallbackQueryHandler(callback_forceadd_query, pattern=r"^(myinv_|topinv_)"))
    logger.info("✅ Force Add module handlers registered successfully")
