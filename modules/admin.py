"""
Admin utilities module.
Commands (admin only):
  /pin [reply]          — পিন (লাউড)
  /pinsilent [reply]    — নীরবে পিন
  /unpin                — আনপিন
  /unpinall             — সব আনপিন
  /lock  <type>         — লক (all|messages|media|stickers)
  /unlock <type>        — আনলক
  /setrules <text>      — নিয়ম সেট
  /rules                — নিয়ম দেখুন
  /setwarnaction ban|kick|mute
  /setwarnlimit <number>
  /promote [reply|id]   — অ্যাডমিন করুন
  /demote  [reply|id]   — অ্যাডমিন সরান
  /setgrouptitle <title>
  /setdesc <desc>
  /del                  — রিপ্লাই মেসেজ মুছুন
  /purge [count]        — শেষ N মেসেজ মুছুন (max 100)
"""

import asyncio
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from database import get_chat_settings, update_chat_setting
from modules.utils import admin_only, get_target_user, is_admin


# ── PIN / UNPIN ─────────────────────────────────

@admin_only
async def cmd_pin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message.reply_to_message:
        await update.message.reply_text("পিন করতে কোনো মেসেজ reply করুন।")
        return
    try:
        await context.bot.pin_chat_message(
            update.effective_chat.id,
            update.message.reply_to_message.message_id,
            disable_notification=False
        )
        await update.message.reply_text("📌 মেসেজ পিন করা হয়েছে।")
    except Exception as e:
        await update.message.reply_text(f"❌ পিন ব্যর্থ: {e}")


@admin_only
async def cmd_pinsilent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message.reply_to_message:
        await update.message.reply_text("পিন করতে কোনো মেসেজ reply করুন।")
        return
    try:
        await context.bot.pin_chat_message(
            update.effective_chat.id,
            update.message.reply_to_message.message_id,
            disable_notification=True
        )
        await update.message.reply_text("📌 মেসেজ নীরবে পিন করা হয়েছে।")
    except Exception as e:
        await update.message.reply_text(f"❌ পিন ব্যর্থ: {e}")


@admin_only
async def cmd_unpin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if update.message.reply_to_message:
            await context.bot.unpin_chat_message(
                update.effective_chat.id,
                update.message.reply_to_message.message_id
            )
        else:
            await context.bot.unpin_chat_message(update.effective_chat.id)
        await update.message.reply_text("📌 মেসেজ আনপিন করা হয়েছে।")
    except Exception as e:
        await update.message.reply_text(f"❌ আনপিন ব্যর্থ: {e}")


@admin_only
async def cmd_unpinall(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await context.bot.unpin_all_chat_messages(update.effective_chat.id)
        await update.message.reply_text("✅ সব পিন করা মেসেজ সরানো হয়েছে।")
    except Exception as e:
        await update.message.reply_text(f"❌ ব্যর্থ: {e}")


# ── LOCK / UNLOCK ───────────────────────────────
# Fix #8: removed "forward" and "polls" from docstring — they're handled by /antiforward
# Fix #9: _apply_lock now correctly reads DB state and applies real permissions

_LOCK_TYPES = {
    "all":      ("lock_messages", "lock_media", "lock_stickers"),
    "messages": ("lock_messages",),
    "media":    ("lock_media",),
    "stickers": ("lock_stickers",),
}


async def _apply_permissions(chat_id: int, bot) -> None:
    """Read current lock flags from DB and apply to Telegram chat permissions."""
    settings = await get_chat_settings(chat_id)
    msgs_locked     = bool(settings.get("lock_messages", 0))
    media_locked    = bool(settings.get("lock_media", 0))
    stickers_locked = bool(settings.get("lock_stickers", 0))

    perms = ChatPermissions(
        can_send_messages=not msgs_locked,
        can_send_photos=not media_locked,
        can_send_videos=not media_locked,
        can_send_audios=not media_locked,
        can_send_documents=not media_locked,
        can_send_video_notes=not media_locked,
        can_send_voice_notes=not media_locked,
        can_send_other_messages=not stickers_locked,   # stickers/GIFs
        can_add_web_page_previews=True,
        can_send_polls=True,
        can_change_info=False,
        can_invite_users=True,
        can_pin_messages=False,
    )
    await bot.set_chat_permissions(chat_id, perms)


@admin_only
async def cmd_lock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lock_type = (context.args[0].lower() if context.args else "all")
    if lock_type not in _LOCK_TYPES:
        await update.message.reply_text(f"লক টাইপ: {', '.join(_LOCK_TYPES.keys())}")
        return
    chat_id = update.effective_chat.id
    for key in _LOCK_TYPES[lock_type]:
        await update_chat_setting(chat_id, key, 1)
    try:
        await _apply_permissions(chat_id, context.bot)
        await update.message.reply_html(f"🔒 <b>{lock_type}</b> লক করা হয়েছে।")
    except Exception as e:
        await update.message.reply_text(f"❌ লক ব্যর্থ: {e}")


@admin_only
async def cmd_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lock_type = (context.args[0].lower() if context.args else "all")
    if lock_type not in _LOCK_TYPES:
        await update.message.reply_text(f"লক টাইপ: {', '.join(_LOCK_TYPES.keys())}")
        return
    chat_id = update.effective_chat.id
    for key in _LOCK_TYPES[lock_type]:
        await update_chat_setting(chat_id, key, 0)     # Fix #9: set to 0 BEFORE applying
    try:
        await _apply_permissions(chat_id, context.bot)
        await update.message.reply_html(f"🔓 <b>{lock_type}</b> আনলক করা হয়েছে।")
    except Exception as e:
        await update.message.reply_text(f"❌ আনলক ব্যর্থ: {e}")


# ── RULES ─────────────────────────────────────

@admin_only
async def cmd_setrules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.partition(" ")[2].strip()
    if not text:
        await update.message.reply_text("ব্যবহার: /setrules <নিয়মাবলী>")
        return
    await update_chat_setting(update.effective_chat.id, "rules_text", text)
    await update.message.reply_text("✅ গ্রুপের নিয়মাবলী সেট করা হয়েছে।")


async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = await get_chat_settings(update.effective_chat.id)
    rules = settings.get("rules_text") or ""
    if not rules:
        await update.message.reply_text("এই গ্রুপে এখনো কোনো নিয়ম সেট করা হয়নি।")
        return
    await update.message.reply_html(f"📋 <b>গ্রুপের নিয়মাবলী:</b>\n\n{rules}")


# ── WARN SETTINGS ─────────────────────────────

@admin_only
async def cmd_setwarnaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or args[0].lower() not in ("ban", "kick", "mute"):
        await update.message.reply_text("ব্যবহার: /setwarnaction ban|kick|mute")
        return
    await update_chat_setting(update.effective_chat.id, "warn_action", args[0].lower())
    await update.message.reply_html(f"✅ ওয়ার্ন অ্যাকশন: <b>{args[0].lower()}</b>")


@admin_only
async def cmd_setwarnlimit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args:
        await update.message.reply_text("ব্যবহার: /setwarnlimit <সংখ্যা>")
        return
    try:
        n = int(args[0])
        if n < 1 or n > 10:
            raise ValueError
    except ValueError:
        await update.message.reply_text("সংখ্যাটি ১–১০ এর মধ্যে হতে হবে।")
        return
    await update_chat_setting(update.effective_chat.id, "max_warns", n)
    await update.message.reply_html(f"✅ ম্যাক্স ওয়ার্ন: <b>{n}</b>")


# ── PROMOTE / DEMOTE (অ্যাডমিন বানানো / সরানো) ──

@admin_only
async def cmd_promote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user, custom_title = await get_target_user(update, context)
    if not user:
        await update.message.reply_text("কাকে অ্যাডমিন বানাবেন তা উল্লেখ করুন।\nব্যবহার: ইউজারের মেসেজে reply করে /addadmin লিখুন অথবা /addadmin <user_id> দিন।")
        return
    try:
        await context.bot.promote_chat_member(
            chat.id, user.id,
            can_delete_messages=True,
            can_restrict_members=True,
            can_pin_messages=True,
            can_invite_users=True,
            can_manage_chat=True,
            can_manage_video_chats=True,
        )
        if custom_title and custom_title.strip():
            try:
                await context.bot.set_chat_administrator_custom_title(
                    chat.id, user.id, custom_title.strip()[:16]
                )
            except Exception:
                pass

        await update.message.reply_html(
            f"👑 <b>নতুন গ্রুপ অ্যাডমিন!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <a href='tg://user?id={user.id}'>{user.first_name}</a>\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"👮 গ্রুপ অ্যাডমিন হিসেবে সফলভাবে যুক্ত করা হয়েছে। ✅"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ অ্যাডমিন বানাতে ব্যর্থ: {e}\n(বটকে গ্রুপে 'Add New Admins' পারমিশন দেওয়া আছে কিনা চেক করুন)")


@admin_only
async def cmd_demote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user, _ = await get_target_user(update, context)
    if not user:
        await update.message.reply_text("কাকে অ্যাডমিন থেকে সরাবেন তা উল্লেখ করুন।\nব্যবহার: ইউজারের মেসেজে reply করে /demote লিখুন অথবা /demote <user_id> দিন।")
        return
    try:
        await context.bot.promote_chat_member(
            chat.id, user.id,
            can_change_info=False,
            can_post_messages=False,
            can_edit_messages=False,
            can_delete_messages=False,
            can_restrict_members=False,
            can_pin_messages=False,
            can_invite_users=False,
            can_manage_chat=False,
            can_manage_video_chats=False,
            can_promote_members=False,
        )
        await update.message.reply_html(
            f"⬇️ <b>অ্যাডমিন পদ বাতিল!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <a href='tg://user?id={user.id}'>{user.first_name}</a>\n"
            f"🔻 অ্যাডমিন পদ থেকে সফলভাবে সরানো হয়েছে।"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ অ্যাডমিন পদ সরাতে ব্যর্থ: {e}")


# ── DELETE / PURGE ────────────────────────────

@admin_only
async def cmd_del(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.reply_to_message:
        try:
            await update.message.reply_to_message.delete()
            await update.message.delete()
        except Exception as e:
            await update.message.reply_text(f"❌ ডিলিট ব্যর্থ: {e}")
    else:
        await update.message.reply_text("কোনো মেসেজ reply করুন।")


@admin_only
async def cmd_purge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    chat = update.effective_chat
    try:
        count = int(context.args[0]) if context.args else 10
        count = min(count, 100)
    except ValueError:
        count = 10

    ids = list(range(msg.message_id - count, msg.message_id + 1))
    deleted = 0
    try:
        await context.bot.delete_messages(chat.id, ids)
        deleted = len(ids)
    except Exception:
        for mid in ids:
            try:
                await context.bot.delete_message(chat.id, mid)
                deleted += 1
            except Exception:
                pass
    try:
        notice = await context.bot.send_message(
            chat.id, f"🗑️ ~{deleted}টি মেসেজ মুছে দেওয়া হয়েছে।"
        )
        await asyncio.sleep(3)
        await notice.delete()
    except Exception:
        pass


# ── GROUP INFO ────────────────────────────────

@admin_only
async def cmd_setgrouptitle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    title = update.message.text.partition(" ")[2].strip()
    if not title:
        await update.message.reply_text("ব্যবহার: /setgrouptitle <নাম>")
        return
    try:
        await context.bot.set_chat_title(update.effective_chat.id, title)
        await update.message.reply_html(f"✅ গ্রুপের নাম: <b>{title}</b>")
    except Exception as e:
        await update.message.reply_text(f"❌ ব্যর্থ: {e}")


@admin_only
async def cmd_setdesc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    desc = update.message.text.partition(" ")[2].strip()
    try:
        await context.bot.set_chat_description(update.effective_chat.id, desc)
        await update.message.reply_text("✅ গ্রুপের বিবরণ আপডেট হয়েছে।")
    except Exception as e:
        await update.message.reply_text(f"❌ ব্যর্থ: {e}")


def _settings_markup(settings):
    """Generate the settings inline keyboard markup based on current DB values."""
    buttons = [
        [
            InlineKeyboardButton(
                f"👋 ওয়েলকাম: {'✅' if settings.get('welcome_enabled') else '❌'}",
                callback_data="set_toggle:welcome_enabled"
            ),
            InlineKeyboardButton(
                f"👋 গুডবাই: {'✅' if settings.get('goodbye_enabled') else '❌'}",
                callback_data="set_toggle:goodbye_enabled"
            )
        ],
        [
            InlineKeyboardButton(
                f"🔗 Antilink: {'✅' if settings.get('antilink_enabled') else '❌'}",
                callback_data="set_toggle:antilink_enabled"
            ),
            InlineKeyboardButton(
                f"🌊 Antiflood: {'✅' if settings.get('antiflood_enabled') else '❌'}",
                callback_data="set_toggle:antiflood_enabled"
            ),
            InlineKeyboardButton(
                f"🚫 Badwords: {'✅' if settings.get('badwords_enabled') else '❌'}",
                callback_data="set_toggle:badwords_enabled"
            )
        ],
        [
            InlineKeyboardButton(
                f"💬 Msg Lock: {'🔒' if settings.get('lock_messages') else '🔓'}",
                callback_data="set_toggle:lock_messages"
            ),
            InlineKeyboardButton(
                f"🖼️ Media Lock: {'🔒' if settings.get('lock_media') else '🔓'}",
                callback_data="set_toggle:lock_media"
            ),
            InlineKeyboardButton(
                f"👾 Sticker Lock: {'🔒' if settings.get('lock_stickers') else '🔓'}",
                callback_data="set_toggle:lock_stickers"
            )
        ],
        [
            InlineKeyboardButton("❌ প্যানেল বন্ধ করুন", callback_data="set_close")
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def _settings_text(chat_title, settings):
    """Generate the formatted settings text."""
    return (
        f"⚙️ <b>গ্রুপ সেটিংস কন্ট্রোল প্যানেল</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 গ্রুপ: <b>{chat_title}</b>\n\n"
        f"👋 <b>ওয়েলকাম সেটিংস:</b>\n"
        f"  • ওয়েলকাম মেসেজ: {'✅ চালু' if settings.get('welcome_enabled') else '❌ বন্ধ'}\n"
        f"  • গুডবাই মেসেজ: {'✅ চালু' if settings.get('goodbye_enabled') else '❌ বন্ধ'}\n\n"
        f"🛡️ <b>স্প্যাম প্রটেকশন:</b>\n"
        f"  • লিংক ব্লক (Antilink): {'✅ চালু' if settings.get('antilink_enabled') else '❌ বন্ধ'}\n"
        f"  • ফ্লাড প্রটেকশন (Antiflood): {'✅ চালু' if settings.get('antiflood_enabled') else '❌ বন্ধ'}\n"
        f"  • নিষিদ্ধ শব্দ ফিল্টার: {'✅ চালু' if settings.get('badwords_enabled') else '❌ বন্ধ'}\n\n"
        f"🔒 <b>চ্যাট লকিং:</b>\n"
        f"  • টেক্সট মেসেজ লক: {'🔒 লকড (Locked)' if settings.get('lock_messages') else '🔓 আনলকড (Unlocked)'}\n"
        f"  • মিডিয়া ফাইল লক: {'🔒 লকড (Locked)' if settings.get('lock_media') else '🔓 আনলকড (Unlocked)'}\n"
        f"  • স্টিকার লক: {'🔒 লকড (Locked)' if settings.get('lock_stickers') else '🔓 আনলকড (Unlocked)'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>নিচের বাটনগুলো ক্লিক করে সেটিংস পরিবর্তন করুন:</i>"
    )


@admin_only
async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("⛔ এই সেটিংস প্যানেল শুধুমাত্র গ্রুপে ব্যবহার করা যাবে।")
        return

    settings = await get_chat_settings(chat.id)
    text = _settings_text(chat.title, settings)
    markup = _settings_markup(settings)
    await update.message.reply_html(text, reply_markup=markup)


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat = update.effective_chat
    user = update.effective_user

    # Only admins can click buttons
    if not await is_admin(update, user_id=user.id):
        await query.answer("⛔ আপনি এই গ্রুপের অ্যাডমিন নন!", show_alert=True)
        return

    data = query.data
    if data == "set_close":
        await query.message.delete()
        await query.answer("প্যানেল বন্ধ করা হয়েছে।")
        return

    if data.startswith("set_toggle:"):
        key = data.split(":")[1]
        settings = await get_chat_settings(chat.id)
        current_val = int(settings.get(key) or 0)
        new_val = 0 if current_val == 1 else 1

        # Save to DB
        await update_chat_setting(chat.id, key, new_val)
        await query.answer("সেটিংস আপডেট করা হয়েছে।")

        # If it was a lock status, apply changes to Telegram chat permissions
        if key in ("lock_messages", "lock_media", "lock_stickers"):
            try:
                await _apply_permissions(chat.id, context.bot)
            except Exception as e:
                print(f"Failed to apply permissions: {e}")

        # Fetch updated settings and edit the message
        updated_settings = await get_chat_settings(chat.id)
        text = _settings_text(chat.title, updated_settings)
        markup = _settings_markup(updated_settings)
        try:
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            pass


def register(app) -> None:
    app.add_handler(CommandHandler("pin",            cmd_pin))
    app.add_handler(CommandHandler("pinsilent",      cmd_pinsilent))
    app.add_handler(CommandHandler("unpin",          cmd_unpin))
    app.add_handler(CommandHandler("unpinall",       cmd_unpinall))
    app.add_handler(CommandHandler("lock",           cmd_lock))
    app.add_handler(CommandHandler("unlock",         cmd_unlock))
    app.add_handler(CommandHandler("setrules",       cmd_setrules))
    app.add_handler(CommandHandler("rules",          cmd_rules))
    app.add_handler(CommandHandler("setwarnaction",  cmd_setwarnaction))
    app.add_handler(CommandHandler("setwarnlimit",   cmd_setwarnlimit))
    app.add_handler(CommandHandler(["promote", "addadmin", "setadmin", "makeadmin"], cmd_promote))
    app.add_handler(CommandHandler(["demote", "removeadmin", "deladmin", "unadmin"], cmd_demote))
    app.add_handler(CommandHandler(["del", "delete"], cmd_del))
    app.add_handler(CommandHandler("purge",          cmd_purge))
    app.add_handler(CommandHandler("setgrouptitle",  cmd_setgrouptitle))
    app.add_handler(CommandHandler("setdesc",        cmd_setdesc))
    app.add_handler(CommandHandler("settings",       cmd_settings))
    app.add_handler(CallbackQueryHandler(settings_callback, pattern=r"^set_"))
