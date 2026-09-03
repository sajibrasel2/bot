import asyncio
import logging
import random
import time
import html
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ContextTypes, CommandHandler
from database import get_all_chat_ids, get_chat_settings, update_chat_setting, get_users_for_chat
from modules.utils import admin_only

logger = logging.getLogger(__name__)

# ── Dynamic Profiles Dataset (Generates millions of unique combinations) ──────
GIRL_NAMES = [
    "আনিকা", "মিম", "সুমি", "রিয়া", "প্রিয়া", "সাদিয়া", "নুসরাত", "তানহা",
    "বৃষ্টি", "জান্নাত", "তানিয়া", "ফারাহ", "ববি", "পূজা", "কেয়া", "মৌ",
    "আশা", "স্নেহা", "নেহা", "রূপা", "মুন্নি", "সোনিয়া", "এশা", "লাবনী",
    "লিমা", "মারিয়া", "মিতু", "নিপা", "শিলা", "তাসনিম", "জেরিন", "নদী",
    "তিথি", "অর্পা", "রিমি", "পলি", "দোলা", "রশ্নি", "মেঘলা", "শিমু",
    "রিতু", "পায়রা", "হিমি", "তনু", "শম্পা"
]

DISTRICTS = [
    "ঢাকা", "চট্টগ্রাম", "খুলনা", "রাজশাহী", "সিলেট", "বরিশাল", "রংপুর", "ময়মনসিংহ",
    "কুমিল্লা", "বগুড়া", "যশোর", "নোয়াখালী", "পাবনা", "ফরিদপুর", "টাঙ্গাইল", "দিনাজপুর",
    "কুষ্টিয়া", "জামালপুর", "ফেনী", "কক্সবাজার", "ব্রাহ্মণবাড়িয়া", "সিরাজগঞ্জ", "গাজীপুর",
    "নারায়ণগঞ্জ", "মানিকগঞ্জ", "নওগাঁ", "ভোলা", "পটুয়াখালী", "ঝিনাইদহ", "চাঁদপুর",
    "নরসিংদী", "নেত্রকোণা", "কিশোরগঞ্জ", "সাতক্ষীরা", "মাগুরা", "নাটোর", "লক্ষ্মীপুর",
    "মুন্সিগঞ্জ", "গোপালগঞ্জ", "হবিগঞ্জ", "মৌলভীবাজার", "সুনামগঞ্জ", "বাগেরহাট", "চুয়াডাঙ্গা"
]

STATUSES = [
    "এখন অনলাইনে একা আছি, ভিডিও চ্যাট করতে নক দাও...",
    "ইমোতে ফ্রি আছি জান, সরাসরি লাইভে আসো...",
    "আজকে সারা রাত আড্ডা দেব, ইনবক্স করো সোনা...",
    "শুধু ভালো মনের একজন ফ্রেন্ড খুঁজছি, চ্যাটে আসো...",
    "ক্যামেরা অন করে কথা বলতে চাইলে জলদি নক দাও...",
    "লাইভ ভিডিও কল করতে চাইলে এখনই অ্যাড হও...",
    "তোমার সাথে একটু মনের কথা বলতে চাই...",
    "অনলাইনে লাইভ রুমে অপেক্ষা করছি, দেরি করো না..."
]

OPERATOR_PREFIXES = ["০১৭", "০১৩", "০১৯", "০১৪", "০১৮", "০১৬"]

# Viral Telegram share URL (Prompts user to forward/share the group link to 5 friends/groups)
SHARE_GROUP_URL = "https://t.me/alltimefantasyzone"
SHARE_TEXT_ENCODED = urllib.parse.quote("🔥 সরাসরি মেয়েদের সাথে লাইভ ভিডিও চ্যাট ও আড্ডা দিতে এখনই জয়েন করুন! 🔞👉 " + SHARE_GROUP_URL)
FORWARD_LINK = f"https://t.me/share/url?url={SHARE_GROUP_URL}&text={SHARE_TEXT_ENCODED}"


def generate_promo_message(users: list) -> tuple:
    """Generates a dynamic partner profile, tags 2-3 random chat members, and returns (text, keyboard)."""
    name = random.choice(GIRL_NAMES)
    district = random.choice(DISTRICTS)
    age = random.randint(19, 25)
    prefix = random.choice(OPERATOR_PREFIXES)
    suffix = str(random.randint(10, 99)).translate(str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯"))
    phone = f"{prefix}****{suffix}"
    status = random.choice(STATUSES)

    # Pick 2-3 random active members from chat database to tag
    if users and len(users) > 0:
        sample_size = min(3, len(users))
        selected_users = random.sample(users, sample_size)
        tags = []
        for u in selected_users:
            fname = html.escape(u.get("first_name") or "Member")
            uid = u.get("user_id")
            tags.append(f"<a href=\"tg://user?id={uid}\">{fname}</a>")
        mentions_text = " • ".join(tags)
    else:
        mentions_text = "অনলাইন মেম্বাররা"

    text = (
        f"🔥 🔞 <b>সিক্রেট ভিআইপি লাইভ পার্টনার</b> 🔞 🔥\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌸 <b>নাম:</b> {name} ({age} বছর)\n"
        f"📍 <b>জেলা:</b> {district}\n"
        f"📱 <b>ইমো/হোয়াটসঅ্যাপ:</b> <code>{phone}</code>\n"
        f"💬 <b>স্ট্যাটাস:</b> <i>\"{status}\"</i>\n\n"
        f"👉 <b>একটিভ পার্টনার:</b> {mentions_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔓 <b>ফুল নাম্বার ও লাইভ ভিডিও কল আনলক করতে:</b>\n"
        f"১. নিচের <b>\"📤 ৫ জনকে শেয়ার করুন\"</b> বাটনে ক্লিক করে ৫টি গ্রুপ বা বন্ধুদের ফরোয়ার্ড করুন।\n"
        f"২. নিচের <b>\"🔴 সরাসরি চ্যাট করুন\"</b> বাটনে ক্লিক করে রুমে যুক্ত হোন!"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(text="📤 ৫ জনকে শেয়ার/ফরোয়ার্ড করুন (Unlock) 🔓", url=FORWARD_LINK)],
        [InlineKeyboardButton(text="🔴 🍒💋 গোপন ক্যামেরায় ধরা পড়া ক্লিপ 🫣🔥", url="https://techandclick.site/bot/")],
        [InlineKeyboardButton(text="🟢 🔞🔥 সরাসরি লাইভ চ্যাটে যুক্ত হোন 💬💋", url="https://techandclick.site/bot/")],
    ])

    return text, keyboard


async def _auto_delete(message, delay: int = 60) -> None:
    """Auto-deletes a message after specified seconds."""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


_promo_running = False


async def promo_loop(app: Application) -> None:
    """Infinite loop that broadcasts dynamic promo message every 10 minutes (600 seconds)."""
    global _promo_running
    if _promo_running:
        logger.info("ℹ️ Promo loop is already running, skipping duplicate initialization.")
        return
    _promo_running = True

    # Wait 10 seconds after bot startup before the first broadcast
    await asyncio.sleep(10)
    
    while True:
        try:
            chat_ids = await get_all_chat_ids()
        except Exception as e:
            logger.error(f"Error fetching chat IDs for promo broadcast: {e}")
            await asyncio.sleep(600)
            continue

        # Collect all valid target chats (both Channels and Groups)
        all_unique_ids = set(chat_ids)
        target_chats = set()

        for cid in all_unique_ids:
            try:
                if not cid:
                    continue
                c = await app.bot.get_chat(cid)
                if c.type == "private":
                    continue
                # If this is a group whose linked channel is already in our target list,
                # Telegram will automatically mirror the channel post into this group,
                # so we don't send a duplicate direct message to the group.
                if c.type in ("group", "supergroup") and c.linked_chat_id and (c.linked_chat_id in all_unique_ids):
                    continue
                target_chats.add(cid)
            except Exception:
                target_chats.add(cid)

        for chat_id in target_chats:
            try:
                # Fetch active users in this chat to tag 2-3 members randomly
                users = await get_users_for_chat(chat_id)
                promo_text, keyboard = generate_promo_message(users)

                # Check if promo sticker is set for this chat
                try:
                    settings = await get_chat_settings(chat_id)
                    stk_id = settings.get("promo_sticker")
                    if stk_id and stk_id.strip():
                        stk = await app.bot.send_sticker(chat_id=chat_id, sticker=stk_id.strip())
                        asyncio.create_task(_auto_delete(stk, 60))
                except Exception:
                    pass

                sent = await app.bot.send_message(
                    chat_id=chat_id,
                    text=promo_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                # Automatically delete promo message after 1 minute (60 seconds)
                asyncio.create_task(_auto_delete(sent, 60))
            except Exception as e:
                logger.debug(f"Failed to send promo message to chat {chat_id}: {e}")

        # Sleep for 10 minutes (600 seconds)
        await asyncio.sleep(600)


@admin_only
async def set_promo_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set animated sticker for promotional broadcast by replying to a sticker or passing ID."""
    msg = update.effective_message
    chat_id = update.effective_chat.id
    stk_id = None
    media_type = "sticker"

    reply = msg.reply_to_message if msg else None
    if reply:
        if reply.sticker:
            stk_id = reply.sticker.file_id
            media_type = "sticker"
        elif reply.animation:
            stk_id = reply.animation.file_id
            media_type = "animation"
        elif reply.document:
            stk_id = reply.document.file_id
            media_type = "document"
    elif msg and msg.sticker:
        stk_id = msg.sticker.file_id
        media_type = "sticker"
    elif msg and msg.animation:
        stk_id = msg.animation.file_id
        media_type = "animation"
    elif context.args:
        stk_id = context.args[0].strip()

    if not stk_id:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="📌 <b>যে অ্যানিমেটেড স্টিকারটি বিজ্ঞাপনে সেট করতে চান:</b>\nগ্রুপে সেই স্টিকারে <b>Reply</b> করে <code>/setpromosticker</code> লিখুন।",
                parse_mode="HTML"
            )
        except Exception:
            pass
        return

    await update_chat_setting(chat_id, "promo_sticker", stk_id)
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="✅ <b>বিজ্ঞাপনের অ্যানিমেটেড স্টিকার সফলভাবে সেট ও সক্রিয় করা হয়েছে!</b>\n\n👇 নিচে বিজ্ঞাপনের স্টিকারের টেস্ট প্রিভিউ দেখানো হলো:",
            parse_mode="HTML"
        )
    except Exception:
        pass

    # Send a quick verification preview of the sticker in the chat
    try:
        if media_type == "animation":
            await context.bot.send_animation(chat_id=chat_id, animation=stk_id)
        elif media_type == "document":
            await context.bot.send_document(chat_id=chat_id, document=stk_id)
        else:
            await context.bot.send_sticker(chat_id=chat_id, sticker=stk_id)
    except Exception:
        try:
            await context.bot.send_sticker(chat_id=chat_id, sticker=stk_id)
        except Exception:
            pass


@admin_only
async def del_promo_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove promotional broadcast sticker."""
    chat_id = update.effective_chat.id
    await update_chat_setting(chat_id, "promo_sticker", "")
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🗑️ <b>বিজ্ঞাপনের স্টিকার মুছে ফেলা হয়েছে।</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass


@admin_only
async def cmd_sendpromo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trigger an instant promotional broadcast in the current chat."""
    chat = update.effective_chat
    users = await get_users_for_chat(chat.id)
    promo_text, keyboard = generate_promo_message(users)
    
    # Check sticker
    try:
        settings = await get_chat_settings(chat.id)
        stk_id = settings.get("promo_sticker")
        if stk_id and stk_id.strip():
            stk = await context.bot.send_sticker(chat_id=chat.id, sticker=stk_id.strip())
            asyncio.create_task(_auto_delete(stk, 60))
    except Exception:
        pass

    sent = await context.bot.send_message(
        chat_id=chat.id,
        text=promo_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    asyncio.create_task(_auto_delete(sent, 60))


def register(app: Application) -> None:
    app.add_handler(CommandHandler(["setpromosticker"], set_promo_sticker))
    app.add_handler(CommandHandler(["delpromosticker"], del_promo_sticker))
    app.add_handler(CommandHandler(["promo", "sendpromo", "broadcast"], cmd_sendpromo))
    logger.info("✅ Promo module handlers registered")
