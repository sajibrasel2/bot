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
            "<b>👋 ওয়েলকাম / গুডবাই কমান্ড:</b>\n\n"
            "• <code>/testwelcome</code> — নতুন ইংরেজি ওয়েলকাম মেসেজ প্রিভিউ/টেস্ট করুন\n"
            "• <code>/setwelcome &lt;text&gt;</code> — কাস্টম ওয়েলকাম মেসেজ সেট করুন\n"
            "• <code>/welcome on|off</code> — ওয়েলকাম মেসেজ চালু/বন্ধ করুন\n"
            "• <code>/resetwelcome</code> — ডিফল্ট ইংরেজি ওয়েলকামে রিসেট করুন\n"
            "• <code>/setwelcomesticker</code> — স্টিকারে রিপ্লাই করে ওয়েলকাম স্টিকার সেট\n"
            "• <code>/delwelcomesticker</code> — ওয়েলকাম স্টিকার মুছে ফেলুন\n"
            "• <code>/names [ID|Reply]</code> — ইউজারের পূর্বের নাম পরিবর্তনের ইতিহাস\n"
            "• <code>/setgoodbye &lt;text&gt;</code> — গুডবাই মেসেজ সেট করুন\n"
            "• <code>/goodbye on|off</code> — গুডবাই চালু/বন্ধ করুন\n\n"
            "<b>Placeholders:</b> <code>{first} {full} {mention} {count} {chatname}</code>"
        ),
    },
    "moderation": {
        "title": "🔨 মডারেশন",
        "text": (
            "<b>🔨 মডারেশন ও শাস্তিমূলক কমান্ড:</b>\n\n"
            "• <code>/panel</code> — ইনলাইন মডারেশন প্যানেল চালু করুন\n"
            "• <code>/warn [Reply]</code> — মেম্বারকে সতর্ক/ওয়ার্ন করুন\n"
            "• <code>/unwarn [Reply]</code> — শেষ ওয়ার্ন প্রত্যাহার করুন\n"
            "• <code>/warns [Reply]</code> — মোট ওয়ার্ন সংখ্যা দেখুন\n"
            "• <code>/resetwarn [Reply]</code> — সকল ওয়ার্ন ক্লিয়ার করুন\n"
            "• <code>/mute [Reply]</code> — চিরতরে মিউট করুন\n"
            "• <code>/tmute &lt;সময়&gt; [Reply]</code> — সাময়িক মিউট (যেমন: 1h, 2d, 30m)\n"
            "• <code>/unmute [Reply]</code> — মিউট তুলে নিন\n"
            "• <code>/kick [Reply]</code> — গ্রুপ থেকে বের করে দিন\n"
            "• <code>/ban [Reply]</code> — চিরতরে ব্যান করুন\n"
            "• <code>/tban &lt;সময়&gt; [Reply]</code> — নির্দিষ্ট সময়ের জন্য ব্যান\n"
            "• <code>/unban &lt;User ID&gt;</code> — ব্যান তুলে নিন\n"
            "• <code>/del [Reply]</code> — টার্গেট মেসেজ মুছে দিন\n"
            "• <code>/purge &lt;সংখ্যা&gt;</code> — শেষ N টি মেসেজ একসাথে ডিলিট করুন\n"
            "• <code>/cleanvideos</code> (বা <code>/delvideos</code>) — এক ক্লিকে গ্রুপের সব ভিডিও মুছুন"
        ),
    },
    "spam": {
        "title": "🛡️ স্প্যাম প্রটেকশন",
        "text": (
            "<b>🛡️ স্প্যাম ও সিকিউরিটি প্রটেকশন:</b>\n\n"
            "• <code>/charlimit 100</code> — মেম্বারদের মেসেজ ১০০ অক্ষর লিমিট সেট\n"
            "• <code>/charlimit off</code> — মেসেজ ক্যারেক্টার লিমিট বন্ধ\n"
            "• <code>/antiforward on|off</code> — ফরোয়ার্ড ও চ্যানেল পোস্ট সম্পূর্ণ ব্লক\n"
            "• <code>/antilink on|off</code> — লিংক ও ইউজারনেম শেয়ারিং ব্লক\n"
            "• <code>/antibiolink on|off</code> — প্রোফাইল বায়ো লিংক প্রটেকশন\n"
            "• <code>/antiflood on|off</code> — দ্রুত মেসেজ ফ্লাড প্রতিরোধ\n"
            "• <code>/badwords on|off</code> — নিষিদ্ধ শব্দ ফিল্টার চালু/বন্ধ\n"
            "• <code>/addbadword &lt;word&gt;</code> — নতুন নিষিদ্ধ শব্দ যোগ করুন\n"
            "• <code>/delbadword &lt;word&gt;</code> — নিষিদ্ধ শব্দ মুছে দিন\n"
            "• <code>/badwordlist</code> — গ্রুপের নিষিদ্ধ শব্দের তালিকা দেখুন"
        ),
    },
    "admin": {
        "title": "⚙️ অ্যাডমিন টুলস",
        "text": (
            "<b>⚙️ অ্যাডমিন ও ম্যানেজমেন্ট টুলস:</b>\n\n"
            "• <code>/settings</code> — গ্রুপ সেটিংস কন্ট্রোল প্যানেল\n"
            "• <code>/tagall &lt;বার্তা&gt;</code> বা <code>/all</code> — সবাইকে ১০০ জনের ব্যাচে আকর্ষণীয় মেনশন\n"
            "• <code>/cancel</code> বা <code>/tagstop</code> — চলমান মেনশন তাৎক্ষণিক বন্ধ\n"
            "• <code>/nightpromo</code> — রাত ১১টার ১৮+ গ্রুপ লিংক ব্রডকাস্ট পাঠানো\n"
            "• <code>/autotag test</code> — রাত ১১টার অটো-ট্যাগ শিডিউল টেস্ট\n"
            "• <code>/promo</code> বা <code>/sendpromo</code> — ইনস্ট্যান্ট লাইভ পার্টনার বিজ্ঞাপন\n"
            "• <code>/servicealert</code> বা <code>/girlnotice</code> — সার্ভিস গার্ল নোটিশ পাঠানো\n"
            "• <code>/setpromosticker</code> — বিজ্ঞাপনে অ্যানিমেটেড স্টিকার সেট\n"
            "• <code>/pin [Reply]</code> — মেসেজ পিন করুন\n"
            "• <code>/pinsilent [Reply]</code> — নোটিফিকেশন ছাড়া পিন\n"
            "• <code>/unpin</code> / <code>/unpinall</code> — পিন মেসেজ সরান\n"
            "• <code>/lock all|media|stickers</code> — গ্রুপ চ্যাট বা মিডিয়া লক\n"
            "• <code>/unlock all|media|stickers</code> — চ্যাট আনলক করুন\n"
            "• <code>/promote [Reply]</code> — কাউকে গ্রুপ অ্যাডমিন বানান\n"
            "• <code>/demote [Reply]</code> — অ্যাডমিন থেকে সাধারণ সদস্য করুন\n"
            "• <code>/restart</code> — বট স্ক্রিপ্ট রিস্টার্ট করুন"
        ),
    },
    "forceadd": {
        "title": "👥 ফোর্স অ্যাড",
        "text": (
            "<b>👥 ফোর্স অ্যাড ও চ্যাট আনলক কমান্ড:</b>\n\n"
            "• <code>/forceadd</code> — বর্তমান অবস্থা ও সেটিংস দেখুন\n"
            "• <code>/forceadd on|off</code> — ফোর্স অ্যাড চালু বা বন্ধ করুন\n"
            "• <code>/forceadd &lt;সংখ্যা&gt;</code> — প্রয়োজনীয় ইনভাইট সংখ্যা নির্ধারণ (যেমন: 5)\n"
            "• <code>/forceunlock &lt;ID|Reply&gt;</code> — মেম্বারের চ্যাট সরাসরি আজীবন আনলক\n"
            "• <code>/forcelock &lt;ID|Reply&gt;</code> — মেম্বারের চ্যাট পুনরায় লক করুন\n"
            "• <code>/myinvites</code> — নিজের ইনভাইট অগ্রগতি ও আনলক অবস্থা\n"
            "• <code>/top</code> — গ্রুপের সেরা ইনভাইটার লিডারবোর্ড"
        ),
    },
    "notes": {
        "title": "📝 নোটস ও নিয়ম",
        "text": (
            "<b>📝 নোটস ও গ্রুপ রুলস কমান্ড:</b>\n\n"
            "• <code>/rules</code> — গ্রুপের নিয়ম দেখুন\n"
            "• <code>/setrules &lt;টেক্সট&gt;</code> — গ্রুপের নিয়ম সেট করুন\n"
            "• <code>/notes</code> — সেভ করা সকল নোটের তালিকা\n"
            "• <code>/save &lt;নাম&gt; &lt;কনটেন্ট&gt;</code> — নতুন নোট সেভ করুন\n"
            "• <code>/get &lt;নাম&gt;</code> বা <code>#নাম</code> — সেভ করা নোট দেখুন\n"
            "• <code>/clear &lt;নাম&gt;</code> — নোট মুছে ফেলুন\n"
            "• <code>/adminlist</code> — গ্রুপের অ্যাডমিন তালিকা দেখুন\n"
            "• <code>/id [Reply]</code> — ইউজার ও চ্যাট আইডি দেখুন"
        ),
    },
    "all": {
        "title": "📋 সকল কমান্ড",
        "text": (
            "📋 <b>বটের পূর্ণাঙ্গ অ্যাডমিন কমান্ড শিট:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👋 <b>ওয়েলকাম:</b>\n"
            "• <code>/testwelcome</code> — নতুন ওয়েলকাম মেসেজ টেস্ট\n"
            "• <code>/welcome on|off</code> — ওয়েলকাম অন/অফ\n"
            "• <code>/resetwelcome</code> — ডিফল্ট ইংরেজি ওয়েলকামে রিসেট\n"
            "• <code>/setwelcomesticker</code> — স্টিকার সেট\n"
            "• <code>/delwelcomesticker</code> — স্টিকার রিমুভ\n"
            "• <code>/names [ID|Reply]</code> — পূর্বের নামের হিস্টোরি\n\n"
            "🛡️ <b>স্প্যাম ও সিকিউরিটি:</b>\n"
            "• <code>/charlimit 100</code> — ১০০ অক্ষরের বেশি মেসেজ ব্লক\n"
            "• <code>/charlimit off</code> — লিমিট বন্ধ\n"
            "• <code>/antiforward on|off</code> — ফরোয়ার্ড ও চ্যানেল ব্লক\n"
            "• <code>/antilink on|off</code> — লিংক ও ইউজারনেম ব্লক\n"
            "• <code>/antibiolink on|off</code> — বায়ো লিংক প্রটেকশন\n"
            "• <code>/antiflood on|off</code> — ফ্লাড রোধ\n"
            "• <code>/badwords on|off</code> — খারাপ শব্দ ফিল্টার\n\n"
            "🔨 <b>মডারেশন:</b>\n"
            "• <code>/panel</code> — ইনলাইন মডারেশন প্যানেল\n"
            "• <code>/warn</code> / <code>/unwarn</code> / <code>/warns</code> — ওয়ার্ন সিস্টেম\n"
            "• <code>/mute</code> / <code>/tmute 1h</code> / <code>/unmute</code> — মিউট\n"
            "• <code>/kick</code> / <code>/ban</code> / <code>/tban 1d</code> / <code>/unban</code> — ব্যান\n"
            "• <code>/del</code> / <code>/purge 10</code> — মেসেজ ডিলিট\n"
            "• <code>/cleanvideos</code> — গ্রুপের সব ভিডিও মুছুন\n\n"
            "⚙️ <b>ম্যানেজমেন্ট ও ব্রডকাস্ট:</b>\n"
            "• <code>/settings</code> — সেটিংস ড্যাশবোর্ড\n"
            "• <code>/tagall &lt;বার্তা&gt;</code> — সবাইকে ১০০ জনের ব্যাচে মেনশন\n"
            "• <code>/cancel</code> — মেনশন থামান\n"
            "• <code>/nightpromo</code> — রাত ১১টার ১৮+ গ্রুপ লিংক পাঠান\n"
            "• <code>/promo</code> — লাইভ পার্টনার বিজ্ঞাপন\n"
            "• <code>/servicealert</code> — সার্ভিস গার্ল নোটিশ\n"
            "• <code>/lock</code> / <code>/unlock</code> — চ্যাট লক/আনলক\n"
            "• <code>/forceadd 5</code> — ফোর্স অ্যাড ইনভাইট সংখ্যা\n"
            "• <code>/forceunlock</code> / <code>/forcelock</code> — মেম্বার চ্যাট আনলক/লক\n"
            "• <code>/pin</code> / <code>/unpin</code> — পিন মেসেজ কন্ট্রোল\n"
            "• <code>/hotvideo</code> — মেম্বারদের জন্য হট ভিডিও ও লাইভ বাটন (১০ সে. অটো-ডিলিট)\n"
            "• <code>/rules</code> / <code>/notes</code> — নিয়ম ও নোটস\n"
            "━━━━━━━━━━━━━━━━━━━━━━━"
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
            InlineKeyboardButton("🛡️ স্প্যাম ও ফিল্টার", callback_data="help_spam"),
            InlineKeyboardButton("⚙️ অ্যাডমিন টুলস", callback_data="help_admin"),
        ],
        [
            InlineKeyboardButton("👥 ফোর্স অ্যাড", callback_data="help_forceadd"),
            InlineKeyboardButton("📝 নোটস ও নিয়ম", callback_data="help_notes"),
        ],
        [
            InlineKeyboardButton("📋 সকল কমান্ড একসাথে দেখুন", callback_data="help_all"),
        ]
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

    is_group = bool(chat and chat.type != "private")
    from modules.utils import is_admin
    admin_user = await is_admin(update)

    if is_group and not admin_user:
        sent = await update.message.reply_html(
            "📖 <b>কমান্ড তালিকা দেখতে আমাকে ইনবক্সে /help পাঠান।</b>"
        )
        from modules.utils import auto_delete_message
        asyncio.create_task(auto_delete_message(sent, delay=5))
        asyncio.create_task(auto_delete_message(update.message, delay=5))
        return

    # If argument passed e.g. "/help all" or "/help admin":
    if context.args:
        arg = context.args[0].lower().strip()
        if arg in HELP_SECTIONS:
            sec = HELP_SECTIONS[arg]
            await update.message.reply_html(
                sec["text"],
                reply_markup=_back_keyboard()
            )
            return

    await update.message.reply_html(
        "📖 <b>বটের সম্পূর্ণ কমান্ড তালিকা ও কন্ট্রোল প্যানেল</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "নিচের বাটনগুলো চেপে নির্দিষ্ট ক্যাটাগরির কমান্ড দেখুন অথবা '📋 সকল কমান্ড' চাপুন:",
        reply_markup=_main_keyboard()
    )


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "help_main":
        await query.edit_message_text(
            "📖 <b>বটের সম্পূর্ণ কমান্ড তালিকা ও কন্ট্রোল প্যানেল</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "নিচের বাটনগুলো চেপে নির্দিষ্ট ক্যাটাগরির কমান্ড দেখুন অথবা '📋 সকল কমান্ড' চাপুন:",
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
    app.add_handler(CommandHandler(["help", "commands", "admincommands", "cmds"], cmd_help))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("info", cmd_info))
    app.add_handler(CommandHandler("chatinfo", cmd_chatinfo))
    app.add_handler(CommandHandler("adminlist", cmd_adminlist))
    app.add_handler(CallbackQueryHandler(help_callback, pattern=r"^help_"))
