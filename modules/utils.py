"""
Shared utility helpers used across modules.
"""

import functools
from telegram import Update, ChatMember
from telegram.ext import ContextTypes
from config import OWNER_ID


async def is_admin(update: Update, user_id: int = None) -> bool:
    """Return True if user_id (or message sender) is an admin/creator."""
    chat = update.effective_chat
    if chat.type == "private":
        return True
    uid = user_id or update.effective_user.id
    if uid == OWNER_ID:
        return True
    from database import is_bot_admin
    if await is_bot_admin(uid):
        return True
    try:
        member = await chat.get_member(uid)
        return member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER)
    except Exception:
        return False


async def is_owner(update: Update) -> bool:
    return update.effective_user.id == OWNER_ID


def admin_only(func):
    """Decorator: only allow admins/owner to run the command."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_chat.type == "private":
            return await func(update, context, *args, **kwargs)
        if not await is_admin(update):
            await update.message.reply_text("⛔ এই কমান্ড শুধুমাত্র অ্যাডমিনরা ব্যবহার করতে পারবেন।")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def owner_only(func):
    """Decorator: only allow the bot owner."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not await is_owner(update):
            await update.message.reply_text("⛔ এই কমান্ড শুধুমাত্র বট মালিক ব্যবহার করতে পারবেন।")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def parse_time_string(t: str) -> int:
    """Convert '10m', '2h', '1d' to seconds. Returns 0 if invalid."""
    if not t:
        return 0
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    suffix = t[-1].lower()
    if suffix in units:
        try:
            return int(t[:-1]) * units[suffix]
        except ValueError:
            return 0
    try:
        return int(t)
    except ValueError:
        return 0


async def get_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Resolve target user from command.
    Priority:
      1. Reply to a message  → user = replied message author
      2. Integer user_id in first arg → fetch via get_member
    Returns (user, reason_string) or (None, error_text).

    NOTE: @username lookup removed — context.bot.get_chat() returns Chat,
    not User, causing AttributeError at callsites that expect a User object.
    Use reply or numeric ID instead.
    """
    msg = update.message
    reason = " ".join(context.args[1:]) if context.args else ""

    # Priority 1: reply
    if msg.reply_to_message:
        user = msg.reply_to_message.from_user
        reason = " ".join(context.args) if context.args else ""
        return user, reason

    # Priority 2: integer user_id
    if context.args:
        target = context.args[0]
        try:
            uid = int(target)
            member = await update.effective_chat.get_member(uid)
            return member.user, reason
        except (ValueError, Exception):
            pass

    return None, "কাকে টার্গেট করবেন তা উল্লেখ করুন (reply করুন অথবা user ID দিন)।"
