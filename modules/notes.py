"""
Notes module — save and retrieve per-chat notes/snippets.
Commands:
  /save <name> <content>      — save a note (admin only)
  /get  <name>  OR  #name     — retrieve a note
  /notes                      — list all notes
  /delnote <name>             — delete a note (admin only)
  /clear                      — delete all notes in chat (admin only)
"""

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

from database import save_note, get_note, delete_note, list_notes
from modules.utils import admin_only


@admin_only
async def cmd_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parts = update.message.text.split(None, 2)
    if len(parts) < 3:
        # Check if there's a replied message to save
        if update.message.reply_to_message and len(parts) >= 2:
            name = parts[1].lower()
            content = update.message.reply_to_message.text or update.message.reply_to_message.caption or ""
            if not content:
                await update.message.reply_text("Reply করা মেসেজে কোনো টেক্সট নেই।")
                return
        else:
            await update.message.reply_text("ব্যবহার: /save <নাম> <কনটেন্ট>\nঅথবা কোনো মেসেজ reply করে: /save <নাম>")
            return
    else:
        name = parts[1].lower()
        content = parts[2]

    await save_note(update.effective_chat.id, name, content)
    await update.message.reply_html(f"✅ নোট <code>{name}</code> সেভ করা হয়েছে।")


async def cmd_get(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("ব্যবহার: /get <নোটের নাম>")
        return
    name = context.args[0].lower()
    content = await get_note(update.effective_chat.id, name)
    if content:
        await update.message.reply_html(f"📝 <b>{name}:</b>\n\n{content}")
    else:
        await update.message.reply_text(f"❌ <code>{name}</code> নামে কোনো নোট নেই।", parse_mode="HTML")


async def cmd_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    notes = await list_notes(update.effective_chat.id)
    if not notes:
        await update.message.reply_text("এই গ্রুপে কোনো নোট সেভ করা নেই।")
        return
    lines = "\n".join(f"• <code>#{n}</code>" for n in notes)
    await update.message.reply_html(f"📚 <b>সেভ করা নোটসমূহ:</b>\n\n{lines}\n\n<i>#নাম লিখে নোট দেখুন।</i>")


@admin_only
async def cmd_delnote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("ব্যবহার: /delnote <নাম>")
        return
    name = context.args[0].lower()
    deleted = await delete_note(update.effective_chat.id, name)
    if deleted:
        await update.message.reply_html(f"🗑️ <code>{name}</code> নোট মুছে দেওয়া হয়েছে।")
    else:
        await update.message.reply_text(f"❌ <code>{name}</code> নামে কোনো নোট নেই।", parse_mode="HTML")


@admin_only
async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    notes = await list_notes(update.effective_chat.id)
    for name in notes:
        await delete_note(update.effective_chat.id, name)
    await update.message.reply_text(f"✅ {len(notes)}টি নোট মুছে দেওয়া হয়েছে।")


async def hashtag_get(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Auto-respond when user sends #notename"""
    msg = update.message
    if not msg or not msg.text:
        return
    text = msg.text.strip()
    if text.startswith("#") and " " not in text:
        name = text[1:].lower()
        if name:
            content = await get_note(update.effective_chat.id, name)
            if content:
                await msg.reply_html(f"📝 <b>{name}:</b>\n\n{content}")


def register(app) -> None:
    app.add_handler(CommandHandler("save", cmd_save))
    app.add_handler(CommandHandler("get", cmd_get))
    app.add_handler(CommandHandler("notes", cmd_notes))
    app.add_handler(CommandHandler("delnote", cmd_delnote))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r"^#\w+$") & filters.ChatType.GROUPS,
        hashtag_get
    ))
