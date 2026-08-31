"""
Moderation module.
Commands (admin only):
  /warn   [reply|id] [reason]
  /unwarn [reply|id]
  /warns  [reply|id]
  /resetwarn [reply|id]
  /ban    [reply|id] [reason]
  /unban  [reply|id]
  /kick   [reply|id] [reason]
  /mute   [reply|id] [time]   — e.g. 10m, 2h, 1d
  /unmute [reply|id]
  /tmute  [reply|id] [time]   — alias for /mute
  /tban   [reply|id] [time]
"""

import time
import asyncio
from datetime import datetime, timezone

from telegram import Update, ChatMember, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.helpers import mention_html
from database import add_warn, get_warns, reset_warns, remove_last_warn, get_chat_settings
from modules.utils import admin_only, get_target_user, parse_time_string
from config import OWNER_ID


def _ts_to_str(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


async def _is_admin_user(chat, user_id: int) -> bool:
    try:
        m = await chat.get_member(user_id)
        return m.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER)
    except Exception:
        return False


# ── Full unmute permissions (Bot API 7.0+ granular fields) ──────────
def _full_permissions() -> ChatPermissions:
    """Return ChatPermissions that restores all member rights."""
    return ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
    )


# ── WARN ────────────────────────────────────────

@admin_only
async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    by   = update.effective_user
    user, reason = await get_target_user(update, context)
    if not user:
        await update.message.reply_text(reason)
        return
    if user.id == OWNER_ID:
        await update.message.reply_text("⛔ মালিককে ওয়ার্ন করা যাবে না।")
        return
    if await _is_admin_user(chat, user.id):
        await update.message.reply_text("⛔ অ্যাডমিনকে ওয়ার্ন করা যাবে না।")
        return

    settings    = await get_chat_settings(chat.id)
    max_w       = int(settings.get("max_warns") or 3)
    warn_action = settings.get("warn_action") or "ban"

    count = await add_warn(chat.id, user.id, reason or "কোনো কারণ উল্লেখ নেই", by.id)

    if count >= max_w:
        await reset_warns(chat.id, user.id)
        if warn_action == "ban":
            try:
                await context.bot.ban_chat_member(chat.id, user.id)
            except Exception:
                pass
            action_text = f"সর্বোচ্চ ওয়ার্ন ({max_w}) পূর্ণ হওয়ায় <b>ব্যান</b> করা হয়েছে।"
        elif warn_action == "kick":
            try:
                await context.bot.ban_chat_member(chat.id, user.id)
                await context.bot.unban_chat_member(chat.id, user.id)
            except Exception:
                pass
            action_text = f"সর্বোচ্চ ওয়ার্ন ({max_w}) পূর্ণ হওয়ায় <b>কিক</b> করা হয়েছে।"
        else:  # mute
            try:
                await context.bot.restrict_chat_member(
                    chat.id, user.id, ChatPermissions(can_send_messages=False)
                )
            except Exception:
                pass
            action_text = f"সর্বোচ্চ ওয়ার্ন ({max_w}) পূর্ণ হওয়ায় <b>মিউট</b> করা হয়েছে।"

        await update.message.reply_html(
            f"🔴 <b>সর্বোচ্চ ওয়ার্ন পূর্ণ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {mention_html(user.id, user.first_name)}\n"
            f"{'📝 কারণ: ' + reason if reason else ''}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔨 {action_text}"
        )
    else:
        await update.message.reply_html(
            f"⚠️ <b>সতর্কতা জারি!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {mention_html(user.id, user.first_name)}\n"
            f"🔢 ওয়ার্ন: <b>{count}/{max_w}</b>\n"
            f"📝 {'কারণ: ' + reason if reason else 'কারণ: উল্লেখ নেই'}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>সর্বোচ্চ {max_w}টিতে {warn_action} করা হবে।</i>"
        )


@admin_only
async def cmd_unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user, _ = await get_target_user(update, context)
    if not user:
        await update.message.reply_text("কাকে টার্গেট করবেন তা উল্লেখ করুন।")
        return
    removed = await remove_last_warn(update.effective_chat.id, user.id)
    if removed:
        await update.message.reply_html(
            f"✅ {mention_html(user.id, user.first_name)}-এর সর্বশেষ ওয়ার্ন সরানো হয়েছে।"
        )
    else:
        await update.message.reply_html(
            f"ℹ️ {mention_html(user.id, user.first_name)}-এর কোনো সক্রিয় ওয়ার্ন নেই।"
        )


async def cmd_warns(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user, _ = await get_target_user(update, context)
    if not user:
        user = update.effective_user
    warns = await get_warns(update.effective_chat.id, user.id)
    if not warns:
        await update.message.reply_html(
            f"✅ {mention_html(user.id, user.first_name)}-এর কোনো সক্রিয় ওয়ার্ন নেই।"
        )
        return
    lines = [
        f"  <b>{i+1}.</b> {r or 'কারণ নেই'}\n      🕐 <i>{_ts_to_str(ts)}</i>"
        for i, (r, ts) in enumerate(warns)
    ]
    await update.message.reply_html(
        f"⚠️ <b>ওয়ার্ন তালিকা</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {mention_html(user.id, user.first_name)}\n"
        f"🔢 মোট: <b>{len(warns)}টি</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines)
    )


@admin_only
async def cmd_resetwarn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user, _ = await get_target_user(update, context)
    if not user:
        await update.message.reply_text("কাকে টার্গেট করবেন তা উল্লেখ করুন।")
        return
    count = await reset_warns(update.effective_chat.id, user.id)
    await update.message.reply_html(
        f"🗑️ {mention_html(user.id, user.first_name)}-এর সকল <b>{count}টি</b> ওয়ার্ন মুছে দেওয়া হয়েছে।"
    )


# ── BAN / KICK ──────────────────────────────────

@admin_only
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user, reason = await get_target_user(update, context)
    if not user:
        await update.message.reply_text(reason)
        return
    if user.id == OWNER_ID:
        await update.message.reply_text("⛔ মালিককে ব্যান করা যাবে না।")
        return
    if await _is_admin_user(chat, user.id):
        await update.message.reply_text("⛔ অ্যাডমিনকে ব্যান করা যাবে না।")
        return
    try:
        await context.bot.ban_chat_member(chat.id, user.id)
        await update.message.reply_html(
            f"🔨 <b>ব্যান!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {mention_html(user.id, user.first_name)}\n"
            f"🚫 স্থায়ীভাবে ব্যান।"
            + (f"\n📝 কারণ: {reason}" if reason else "")
        )
    except Exception as e:
        await update.message.reply_text(f"❌ ব্যান ব্যর্থ: {e}")


@admin_only
async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user, _ = await get_target_user(update, context)
    if not user:
        await update.message.reply_text("কাকে আনব্যান করবেন তা উল্লেখ করুন।")
        return
    try:
        await context.bot.unban_chat_member(chat.id, user.id, only_if_banned=True)
        await update.message.reply_html(
            f"✅ {mention_html(user.id, user.first_name)} আনব্যান করা হয়েছে।"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ আনব্যান ব্যর্থ: {e}")


@admin_only
async def cmd_kick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user, reason = await get_target_user(update, context)
    if not user:
        await update.message.reply_text(reason)
        return
    if user.id == OWNER_ID:
        await update.message.reply_text("⛔ মালিককে কিক করা যাবে না।")
        return
    if await _is_admin_user(chat, user.id):
        await update.message.reply_text("⛔ অ্যাডমিনকে কিক করা যাবে না।")
        return
    try:
        await context.bot.ban_chat_member(chat.id, user.id)
        await context.bot.unban_chat_member(chat.id, user.id)
        await update.message.reply_html(
            f"👢 <b>কিক!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {mention_html(user.id, user.first_name)}\n"
            f"🚪 গ্রুপ থেকে বের করা হয়েছে।"
            + (f"\n📝 কারণ: {reason}" if reason else "")
        )
    except Exception as e:
        await update.message.reply_text(f"❌ কিক ব্যর্থ: {e}")


@admin_only
async def cmd_tban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user, extra = await get_target_user(update, context)
    if not user:
        await update.message.reply_text(extra)
        return
    time_arg = extra.split()[0] if extra else ""
    duration = parse_time_string(time_arg)
    if not duration:
        await update.message.reply_text("সময় উল্লেখ করুন। যেমন: /tban <id> 1h")
        return
    until = int(time.time()) + duration
    try:
        await context.bot.ban_chat_member(chat.id, user.id, until_date=until)
        await update.message.reply_html(
            f"⏳ <b>সাময়িক ব্যান!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {mention_html(user.id, user.first_name)}\n"
            f"🕐 সময়সীমা: <b>{time_arg}</b>"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ ব্যর্থ: {e}")


# ── MUTE ────────────────────────────────────────

@admin_only
async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user, extra = await get_target_user(update, context)
    if not user:
        await update.message.reply_text(extra)
        return
    if user.id == OWNER_ID:
        await update.message.reply_text("⛔ মালিককে মিউট করা যাবে না।")
        return
    if await _is_admin_user(chat, user.id):
        await update.message.reply_text("⛔ অ্যাডমিনকে মিউট করা যাবে না।")
        return

    time_arg = extra.split()[0] if extra else ""
    duration = parse_time_string(time_arg)
    until    = int(time.time()) + duration if duration else None

    try:
        await context.bot.restrict_chat_member(
            chat.id, user.id,
            ChatPermissions(can_send_messages=False),
            until_date=until
        )
        time_text = f"<b>{time_arg}</b> এর জন্য" if duration else "অনির্দিষ্টকালের জন্য"
        await update.message.reply_html(
            f"🔇 <b>মিউট!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {mention_html(user.id, user.first_name)}\n"
            f"🕐 {time_text}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ মিউট ব্যর্থ: {e}")


@admin_only
async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user, _ = await get_target_user(update, context)
    if not user:
        await update.message.reply_text("কাকে আনমিউট করবেন তা উল্লেখ করুন।")
        return
    try:
        # Fix #14: restore all granular permissions (Bot API 7.0+)
        await context.bot.restrict_chat_member(
            chat.id, user.id, _full_permissions()
        )
        await update.message.reply_html(
            f"🔊 <b>আনমিউট!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {mention_html(user.id, user.first_name)}\n"
            f"✅ সব অনুমতি পুনরায় দেওয়া হয়েছে।"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ আনমিউট ব্যর্থ: {e}")


async def cmd_tmute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_mute(update, context)


@admin_only
async def cmd_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("⛔ এই কমান্ড শুধুমাত্র গ্রুপে ব্যবহার করা যাবে।")
        return
        
    msg = update.message
    if not msg.reply_to_message:
        await update.message.reply_text("⛔ কাউকে কন্ট্রোল করতে তার মেসেজে reply করে /panel লিখুন।")
        return

    target_user = msg.reply_to_message.from_user
    target_msg_id = msg.reply_to_message.message_id

    # Sudo admins / Owner cannot be moderated
    if target_user.id == OWNER_ID:
        await update.message.reply_text("⛔ মালিকের বিরুদ্ধে কোনো অ্যাকশন নেওয়া যাবে না।")
        return
    if await _is_admin_user(chat, target_user.id):
        await update.message.reply_text("⛔ অ্যাডমিনদের বিরুদ্ধে কোনো অ্যাকশন নেওয়া যাবে না।")
        return

    text = (
        f"👮 <b>মডারেশন প্যানেল</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 টার্গেট: {mention_html(target_user.id, target_user.first_name)} (<code>{target_user.id}</code>)\n"
        f"💬 অ্যাকশন নির্বাচন করুন:"
    )

    buttons = [
        [
            InlineKeyboardButton("⚠️ ওয়ার্ন (Warn)", callback_data=f"mod_warn:{target_user.id}:{target_msg_id}"),
            InlineKeyboardButton("🚫 ব্যান (Ban)", callback_data=f"mod_ban:{target_user.id}")
        ],
        [
            InlineKeyboardButton("🔇 মিউট ১ ঘণ্টা", callback_data=f"mod_mute:{target_user.id}:3600"),
            InlineKeyboardButton("🚪 কিক (Kick)", callback_data=f"mod_kick:{target_user.id}")
        ],
        [
            InlineKeyboardButton("📌 পিন (Pin)", callback_data=f"mod_pin:{target_msg_id}"),
            InlineKeyboardButton("🗑️ ডিলিট (Delete)", callback_data=f"mod_del:{target_msg_id}")
        ]
    ]

    await update.message.reply_html(text, reply_markup=InlineKeyboardMarkup(buttons))


async def moderation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat = update.effective_chat
    user = update.effective_user
    
    # Check if clicker is admin
    from modules.utils import is_admin
    if not await is_admin(update, user_id=user.id):
        await query.answer("⛔ আপনি অ্যাডমিন নন!", show_alert=True)
        return

    data = query.data
    parts = data.split(":")
    action = parts[0]
    
    # Parse target info
    target_id = int(parts[1]) if len(parts) > 1 else None

    # Synthesize action success text
    success_text = "✅ সম্পন্ন হয়েছে!"

    try:
        if action == "mod_warn":
            msg_id = int(parts[2])
            settings = await get_chat_settings(chat.id)
            max_w = int(settings.get("max_warns") or 3)
            warn_action = settings.get("warn_action") or "ban"
            
            count = await add_warn(chat.id, target_id, "কন্ট্রোল প্যানেল থেকে সতর্কবার্তা", user.id)
            await query.answer(f"সতর্কবার্তা দেওয়া হয়েছে! ({count}/{max_w})")
            
            if count >= max_w:
                await reset_warns(chat.id, target_id)
                if warn_action == "ban":
                    await context.bot.ban_chat_member(chat.id, target_id)
                    success_text = f"🚨 সর্বোচ্চ ওয়ার্ন পূর্ণ হওয়ায় ব্যান করা হয়েছে।"
                elif warn_action == "kick":
                    await context.bot.ban_chat_member(chat.id, target_id)
                    await context.bot.unban_chat_member(chat.id, target_id)
                    success_text = f"🚪 সর্বোচ্চ ওয়ার্ন পূর্ণ হওয়ায় কিক করা হয়েছে।"
                else:
                    await context.bot.restrict_chat_member(
                        chat.id, target_id, ChatPermissions(can_send_messages=False)
                    )
                    success_text = f"🔇 সর্বোচ্চ ওয়ার্ন পূর্ণ হওয়ায় মিউট করা হয়েছে।"
            else:
                success_text = f"⚠️ সতর্ক করা হয়েছে! মোট ওয়ার্ন: {count}/{max_w}"

        elif action == "mod_ban":
            await context.bot.ban_chat_member(chat.id, target_id)
            await query.answer("ইউজারকে ব্যান করা হয়েছে।")
            success_text = "🚫 ইউজারকে সফলভাবে <b>ব্যান</b> করা হয়েছে।"

        elif action == "mod_kick":
            await context.bot.ban_chat_member(chat.id, target_id)
            await context.bot.unban_chat_member(chat.id, target_id)
            await query.answer("ইউজারকে কিক করা হয়েছে।")
            success_text = "🚪 ইউজারকে সফলভাবে <b>কিক</b> করা হয়েছে।"

        elif action == "mod_mute":
            duration = int(parts[2])
            until = int(time.time()) + duration
            await context.bot.restrict_chat_member(
                chat.id, target_id, ChatPermissions(can_send_messages=False), until_date=until
            )
            await query.answer("ইউজারকে মিউট করা হয়েছে।")
            success_text = "🔇 ইউজারকে ১ ঘণ্টার জন্য <b>মিউট</b> করা হয়েছে।"

        elif action == "mod_pin":
            msg_id = int(parts[1]) # parts[1] is replied_msg_id for pin
            await context.bot.pin_chat_message(chat.id, msg_id)
            await query.answer("মেসেজ পিন করা হয়েছে।")
            success_text = "📌 মেসেজটি পিন করা হয়েছে।"

        elif action == "mod_del":
            msg_id = int(parts[1]) # parts[1] is replied_msg_id for del
            await context.bot.delete_message(chat.id, msg_id)
            await query.answer("মেসেজ ডিলিট করা হয়েছে।")
            success_text = "🗑️ মেসেজটি ডিলিট করা হয়েছে।"

        # Edit current menu message to show status
        await query.edit_message_text(
            f"👮 <b>মডারেশন অ্যাকশন:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{success_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"অ্যাকশন নিয়েছেন: {mention_html(user.id, user.first_name)}",
            parse_mode="HTML"
        )
        
        # Auto delete the panel output after 4 seconds to keep chat clean
        async def _del_panel_msg(msg_obj):
            await asyncio.sleep(4)
            try:
                await msg_obj.delete()
            except Exception:
                pass
        
        asyncio.create_task(_del_panel_msg(query.message))

    except Exception as e:
        await query.answer(f"ভুল হয়েছে: {e}", show_alert=True)


def register(app) -> None:
    app.add_handler(CommandHandler("warn",      cmd_warn))
    app.add_handler(CommandHandler("unwarn",    cmd_unwarn))
    app.add_handler(CommandHandler("warns",     cmd_warns))
    app.add_handler(CommandHandler("resetwarn", cmd_resetwarn))
    app.add_handler(CommandHandler("ban",       cmd_ban))
    app.add_handler(CommandHandler("unban",     cmd_unban))
    app.add_handler(CommandHandler("kick",      cmd_kick))
    app.add_handler(CommandHandler("tban",      cmd_tban))
    app.add_handler(CommandHandler("mute",      cmd_mute))
    app.add_handler(CommandHandler("unmute",    cmd_unmute))
    app.add_handler(CommandHandler("tmute",     cmd_tmute))
    app.add_handler(CommandHandler("panel",     cmd_panel))
    app.add_handler(CommandHandler("control",   cmd_panel))
    app.add_handler(CallbackQueryHandler(moderation_callback, pattern=r"^mod_"))
