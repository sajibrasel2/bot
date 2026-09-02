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
    if not chat:
        return False
    if chat.type == "private":
        return True

    # 1. Anonymous admin / Channel sender in group
    msg = update.effective_message
    if msg:
        if msg.sender_chat and msg.sender_chat.id == chat.id:
            return True
        if msg.from_user and msg.from_user.id in (1087968824, 777000): # GroupAnonymousBot / Service
            return True

    # 2. Check user ID
    user = update.effective_user
    uid = user_id or (user.id if user else None)
    if not uid:
        return False

    # 3. Known bot owner IDs & database bot admins
    if uid in (OWNER_ID, 8904339611, 5888198325):
        return True
    
    try:
        from database import is_bot_admin
        if await is_bot_admin(uid):
            return True
    except Exception:
        pass

    # 4. Check chat member status
    try:
        member = await chat.get_member(uid)
        if member and member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER, "administrator", "creator", "admin"):
            return True
    except Exception:
        pass

    # 5. Check chat administrators list as fallback
    try:
        admins = await chat.get_administrators()
        for a in admins:
            if a.user.id == uid:
                return True
    except Exception:
        pass

    return False


async def is_owner(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    return user.id in (OWNER_ID, 8904339611, 5888198325)


import asyncio


async def auto_delete_message(message, delay: int = 5) -> None:
    """Auto-deletes a message after `delay` seconds."""
    if not message:
        return
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


def admin_only(func):
    """Decorator: only allow admins/owner to run the command with auto-clean in groups."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_chat.type == "private":
            return await func(update, context, *args, **kwargs)

        msg = update.effective_message

        # 1. Check admin authorization
        if not await is_admin(update):
            try:
                sent = await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⛔ এই কমান্ড শুধুমাত্র অ্যাডমিনরা ব্যবহার করতে পারবেন।"
                )
                asyncio.create_task(auto_delete_message(sent, delay=5))
            except Exception:
                pass
            if msg:
                asyncio.create_task(auto_delete_message(msg, delay=2))
            return

        # 2. Auto-delete bot reply after 6 seconds for clean group chat
        orig_reply_text = update.message.reply_text if update.message else None
        orig_reply_html = update.message.reply_html if update.message else None

        async def _wrapped_reply_text(*r_args, **r_kwargs):
            try:
                sent = await orig_reply_text(*r_args, **r_kwargs)
            except Exception:
                text = r_args[0] if r_args else r_kwargs.get("text", "")
                sent = await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            asyncio.create_task(auto_delete_message(sent, delay=6))
            return sent

        async def _wrapped_reply_html(*r_args, **r_kwargs):
            try:
                sent = await orig_reply_html(*r_args, **r_kwargs)
            except Exception:
                text = r_args[0] if r_args else r_kwargs.get("text", "")
                sent = await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode="HTML")
            asyncio.create_task(auto_delete_message(sent, delay=6))
            return sent

        cmd_name = func.__name__
        exempt = ("cmd_tagall", "cmd_rules", "set_welcome_sticker", "set_promo_sticker", "del_welcome_sticker", "del_promo_sticker")
        if update.message and cmd_name not in exempt:
            update.message.reply_text = _wrapped_reply_text
            update.message.reply_html = _wrapped_reply_html

        try:
            return await func(update, context, *args, **kwargs)
        finally:
            if msg and cmd_name not in exempt:
                asyncio.create_task(auto_delete_message(msg, delay=3))
    return wrapper


def owner_only(func):
    """Decorator: only allow the bot owner with auto-clean in groups."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_chat.type == "private":
            return await func(update, context, *args, **kwargs)

        msg = update.effective_message

        if not await is_owner(update):
            try:
                sent = await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⛔ এই কমান্ড শুধুমাত্র বট মালিক ব্যবহার করতে পারবেন।"
                )
                asyncio.create_task(auto_delete_message(sent, delay=5))
            except Exception:
                pass
            if msg:
                asyncio.create_task(auto_delete_message(msg, delay=2))
            return

        try:
            return await func(update, context, *args, **kwargs)
        finally:
            if msg:
                asyncio.create_task(auto_delete_message(msg, delay=3))
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
