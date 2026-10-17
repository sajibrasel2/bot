"""
Help module — /start, /help, /id, /info, /chatinfo, /adminlist
"""

import html
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from config import WEB_APP_URL
from database import upsert_user
from modules.utils import admin_only

HELP_SECTIONS = {
    "welcome": {
        "title": "👋 ওয়েলকাম",
        "text": (
            "<b>ওয়েলকাম / গুডবাই কমান্ড:</b>\n\n"
            "/setwelcome &lt;টেক্সট&gt; — ওয়েলকাম মেসেজ সেট করুন\n"
            "/setgoodbye &lt;টেক্সট&gt; — গুডবাই মেসেজ সেট করুন\n"
            "/welcome on|off — ওয়েলকাম চালু/বন্ধ\n"
            "/goodbye on|off — গুডবাই চালু/বন্ধ\n"
            "/resetwelcome — ডিফল্টে ফিরিয়ে আনুন\n\n"
            "<b>Placeholders:</b> {first} {full} {mention} {count} {chatname}"
        ),
    },
    "moderation": {
        "title": "🔨 মডারেশন",
        "text": (
            "<b>মডারেশন কমান্ড:</b>\n\n"
            "/panel — ইনলাইন মডারেশন প্যানেল\n"
            "/warn — ব্যবহারকারীকে সতর্ক করুন\n"
            "/unwarn — শেষ ওয়ার্ন সরান\n"
            "/warns — ওয়ার্ন গণনা দেখুন\n"
            "/resetwarn — সব ওয়ার্ন মুছুন\n"
            "/ban — ব্যান করুন\n"
            "/unban — আনব্যান করুন\n"
            "/tban &lt;সময়&gt; — নির্দিষ্ট সময়ের জন্য ব্যান (1h, 2d)\n"
            "/kick — গ্রুপ থেকে বের করুন\n"
            "/mute — মিউট করুন\n"
            "/unmute — আনমিউট করুন\n"
            "/tmute &lt;সময়&gt; — নির্দিষ্ট সময়ের জন্য মিউট\n"
            "/forceunlock [ID|Reply] — চ্যাট সরাসরি আজীবন আনলক করতে\n"
            "/forcelock [ID|Reply] — চ্যাট পুনরায় লক করতে"
        ),
    },
    "spam": {
        "title": "🛡️ স্প্যাম প্রটেকশন",
        "text": (
            "<b>স্প্যাম প্রটেকশন কমান্ড:</b>\n\n"
            "/antiflood on|off — ফ্লাড প্রটেকশন\n"
            "/antilink on|off — লিংক ব্লক\n"
            "/antiforward on|off — ফরোয়ার্ড ব্লক\n"
            "/badwords on|off — নিষিদ্ধ শব্দ ফিল্টার\n"
            "/addbadword &lt;শব্দ&gt; — নিষিদ্ধ শব্দ যোগ করুন\n"
            "/delbadword &lt;শব্দ&gt; — নিষিদ্ধ শব্দ সরান\n"
            "/badwordlist — নিষিদ্ধ শব্দ তালিকা"
        ),
    },
    "admin": {
        "title": "⚙️ অ্যাডমিন টুলস",
        "text": (
            "<b>অ্যাডমিন কমান্ড:</b>\n\n"
            "/settings — গ্রুপ সেটিংস কন্ট্রোল প্যানেল\n"
            "/panel — ইনলাইন মডারেশন প্যানেল\n"
            "/forceadd on|off|&lt;সংখ্যা&gt; — ফোর্স অ্যাড সেটিংস\n"
            "/forceunlock &lt;ID|Reply&gt; — চ্যাট সরাসরি আজীবন আনলক করতে\n"
            "/forcelock &lt;ID|Reply&gt; — চ্যাট পুনরায় লক করতে\n"
            "/tagall &lt;বার্তা&gt; — সবাইকে মেনশন করুন (/all)\n"
            "/cancel — চলমান মেনশন বন্ধ করুন\n"
            "/autotag on|off — রাত ১১টার অটো-ট্যাগ শিডিউল\n"
            "/pin — মেসেজ পিন করুন\n"
            "/pinsilent — নীরবে পিন\n"
            "/unpin — পিন সরান\n"
            "/unpinall — সব পিন সরান\n"
            "/lock &lt;টাইপ&gt; — লক করুন (all|media|stickers)\n"
            "/unlock &lt;টাইপ&gt; — আনলক করুন\n"
            "/promote /addadmin — গ্রুপ অ্যাডমিন বানান\n"
            "/demote /removeadmin — অ্যাডমিন থেকে সরান\n"
            "/del — মেসেজ মুছুন\n"
            "/purge &lt;N&gt; — শেষ N মেসেজ মুছুন\n"
            "/setwarnaction ban|kick|mute\n"
            "/setwarnlimit &lt;সংখ্যা&gt;\n"
            "/restart — বট রিস্টার্ট করুন"
        ),
    },
    "forceadd": {
        "title": "👥 ফোর্স অ্যাড (চ্যাট আনলক)",
        "text": (
            "<b>👥 ফোর্স অ্যাড ও চ্যাট আনলক কমান্ড:</b>\n\n"
            "/forceadd — বর্তমান অবস্থা ও সেটিংস দেখুন\n"
            "/forceadd on|off — ফোর্স অ্যাড চালু বা বন্ধ করুন\n"
            "/forceadd &lt;সংখ্যা&gt; — প্রয়োজনীয় ইনভাইট সংখ্যা নির্ধারণ\n"
            "/forceunlock &lt;ID|Reply&gt; — চ্যাট সরাসরি আজীবন আনলক করতে\n"
            "/forcelock &lt;ID|Reply&gt; — চ্যাট পুনরায় লক করতে\n"
            "/myinvites — মেম্বারের ইনভাইট অগ্রগতি ও আনলক অবস্থা\n"
            "/top — সেরা ইনভাইটার লিডারবোর্ড\n\n"
            "💡 <i>টিপস: কোনো মেম্বারের মেসেজে রিপ্লাই দিয়ে অথবা সরাসরি ইউজার আইডি বসিয়ে আজীবন আনলক বা লক করা যায়।</i>"
        ),
    },
    "notes": {
        "title": "📝 নোটস",
        "text": (
            "<b>নোটস কমান্ড:</b>\n\n"
            "/save &lt;নাম&gt; &lt;কনটেন্ট&gt; — নোট সেভ করুন\n"
            "/get &lt;নাম&gt; — নোট দেখুন\n"
            "#নাম — দ্রুত নোট দেখুন\n"
            "/notes — সব নোট তালিকা\n"
            "/delnote &lt;নাম&gt; — নোট মুছুন\n"
            "/setrules &lt;নিয়ম&gt; — গ্রুপ নিয়ম সেট করুন\n"
            "/rules — নিয়ম দেখুন"
        ),
    },
}


def _main_keyboard():
    buttons = [
        [
            InlineKeyboardButton("👋 ওয়েলকাম", callback_data="help_welcome"),
            InlineKeyboardButton("🔨 মডারেশন", callback_data="help_moderation"),
        ],
        [
            InlineKeyboardButton("🛡️ স্প্যাম", callback_data="help_spam"),
            InlineKeyboardButton("⚙️ অ্যাডমিন", callback_data="help_admin"),
        ],
        [
            InlineKeyboardButton("👥 ফোর্স অ্যাড", callback_data="help_forceadd"),
            InlineKeyboardButton("📝 নোটস", callback_data="help_notes"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def _start_keyboard():
    buttons = [
        [
            InlineKeyboardButton("💋 লাইভ চ্যাট শুরু করুন (Web App)", web_app=WebAppInfo(url=WEB_APP_URL))
        ],
        [
            InlineKeyboardButton("📖 বট ব্যবহার গাইড", callback_data="help_main")
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def _back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("« ফিরে যান", callback_data="help_main")]])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if user and chat:
        asyncio.create_task(upsert_user(user.id, chat.id, user.username or "", user.first_name or ""))
    if chat.type != "private":
        sent = await update.message.reply_html(
            f"👋 হ্যালো {user.mention_html()}!\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 আমি এই গ্রুপের ম্যানেজার বট।\n"
            f"📖 বিস্তারিত দেখতে আমাকে ইনবক্সে /help পাঠান।"
        )
        from modules.utils import auto_delete_message
        asyncio.create_task(auto_delete_message(sent, delay=5))
        asyncio.create_task(auto_delete_message(update.message, delay=5))
        return
    await update.message.reply_html(
        f"╔═══════════════════════╗\n"
        f"     🌸  <b>হ্যালো!</b>  🌸\n"
        f"╚═══════════════════════╝\n\n"
        f"👋 স্বাগতম, <b>{user.first_name}</b>!\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 আমি একটি প্রফেশনাল\n"
        f"   <b>গ্রুপ ম্যানেজার বট</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>শুরু করতে:</b>\n"
        f"  ▸ আমাকে আপনার গ্রুপে যোগ করুন\n"
        f"  ▸ Admin পারমিশন দিন\n"
        f"  ▸ নিচের বাটন থেকে কমান্ড দেখুন\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=_start_keyboard()
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if user and chat:
        asyncio.create_task(upsert_user(user.id, chat.id, user.username or "", user.first_name or ""))
    if chat and chat.type != "private":
        sent = await update.message.reply_html(
            "📖 <b>কমান্ড তালিকা দেখতে আমাকে ইনবক্সে /help পাঠান।</b>"
        )
        from modules.utils import auto_delete_message
        asyncio.create_task(auto_delete_message(sent, delay=5))
        asyncio.create_task(auto_delete_message(update.message, delay=5))
        return
    await update.message.reply_html(
        "📖 <b>কমান্ড তালিকা</b> — বিভাগ বেছে নিন:",
        reply_markup=_main_keyboard()
    )


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "help_main":
        await query.edit_message_text(
            "📖 <b>কমান্ড তালিকা</b> — বিভাগ বেছে নিন:",
            parse_mode="HTML",
            reply_markup=_main_keyboard()
        )
        return

    key = data.replace("help_", "")
    section = HELP_SECTIONS.get(key)
    if section:
        await query.edit_message_text(
            section["text"],
            parse_mode="HTML",
            reply_markup=_back_keyboard()
        )


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        await update.message.reply_html(
            f"👤 <b>ব্যবহারকারী ID:</b> <code>{target.id}</code>\n"
            f"💬 <b>চ্যাট ID:</b> <code>{chat.id}</code>"
        )
    else:
        await update.message.reply_html(
            f"👤 <b>আপনার ID:</b> <code>{user.id}</code>\n"
            f"💬 <b>চ্যাট ID:</b> <code>{chat.id}</code>"
        )


async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
    else:
        user = update.effective_user

    uname = f"@{user.username}" if user.username else "নেই"
    await update.message.reply_html(
        f"👤 <b>ব্যবহারকারীর তথ্য</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📛 নাম: {user.mention_html()}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"🔖 Username: {uname}\n"
        f"🤖 বট: {'হ্যাঁ ✅' if user.is_bot else 'না ❌'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━"
    )


async def cmd_chatinfo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    try:
        count = await chat.get_member_count()
    except Exception:
        count = "?"
    await update.message.reply_html(
        f"💬 <b>গ্রুপের তথ্য</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📛 নাম: <b>{chat.title}</b>\n"
        f"🆔 ID: <code>{chat.id}</code>\n"
        f"👥 মোট সদস্য: <b>{count} জন</b>\n"
        f"🔖 Username: {'@' + chat.username if chat.username else 'নেই'}\n"
        f"📋 ধরন: {chat.type}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━"
    )


@admin_only
async def cmd_adminlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        admins = await update.effective_chat.get_administrators()
        lines = []
        for a in admins:
            if a.user.is_bot:
                continue
            title = f" ─ <i>{html.escape(a.custom_title)}</i>" if a.custom_title else ""
            fname = html.escape(a.user.first_name or "Admin")
            crown = "👑" if a.status == "creator" else "🛡️"
            lines.append(f"  {crown} <b>{fname}</b> (<code>{a.user.id}</code>){title}")
        text = (
            f"👮 <b>অ্যাডমিন তালিকা</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            + "\n".join(lines) +
            f"\n━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👑 মালিক  🛡️ অ্যাডমিন"
        )
        await update.message.reply_html(text)
    except Exception as e:
        await update.message.reply_text(f"❌ তালিকা আনা সম্ভব হয়নি: {e}")


def register(app) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("info", cmd_info))
    app.add_handler(CommandHandler("chatinfo", cmd_chatinfo))
    app.add_handler(CommandHandler("adminlist", cmd_adminlist))
    app.add_handler(CallbackQueryHandler(help_callback, pattern=r"^help_"))
