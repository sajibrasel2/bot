"""
One-time Login Helper for Video Collector Userbot
Run this script interactively in your cPanel terminal:
  python video_collector/login.py
"""

import sys
import os
import asyncio

# Ensure project root in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from video_collector.config import TG_API_ID, TG_API_HASH, SESSION_NAME

session_dir = os.path.dirname(os.path.abspath(__file__))
session_path = os.path.join(session_dir, SESSION_NAME)


def remove_session_files():
    """Safely remove existing session files to allow clean fresh login."""
    for ext in [".session", ".session-journal"]:
        p = session_path + ext
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass


def format_phone_number(raw: str) -> str:
    """Format Bangladeshi or international phone numbers to E.164 standard."""
    p = raw.strip().replace(" ", "").replace("-", "")
    if p.startswith("01"):
        return "+88" + p
    if p.startswith("1") and len(p) == 10:
        return "+880" + p
    if not p.startswith("+"):
        return "+" + p
    return p


async def main():
    print("\n" + "=" * 65)
    print("🔐 টেলিগ্রাম ইউজারবট ওয়ান-টাইম লগইন সিস্টেম")
    print("=" * 65)
    print(f"App API ID   : {TG_API_ID}")
    print(f"Session Path : {session_path}")
    print("=" * 65 + "\n")

    # Check if existing session exists and check if it's a bot
    need_clean_login = True
    session_file = session_path + ".session"
    if os.path.exists(session_file):
        test_client = TelegramClient(session_path, TG_API_ID, TG_API_HASH)
        await test_client.connect()
        if await test_client.is_user_authorized():
            me = await test_client.get_me()
            if getattr(me, "bot", False):
                print(f"⚠️ শনাক্ত: আপনি বট টোকেন (@{me.username}) দিয়ে লগইন অবস্থায় আছেন।")
                print("❌ টেলিগ্রামের নিয়মে বট অন্যের চ্যানেল থেকে ভিডিও পড়তে পারে না।")
                print("🔄 পূর্বের বট সেশন ডিলিট করে নতুন ফোন নাম্বার দিয়ে লগইন করা হচ্ছে...\n")
                await test_client.disconnect()
                remove_session_files()
            else:
                print(f"✅ ইতিমধ্যে ইউজার একাউন্ট দিয়ে লগইন আছেন: {me.first_name} (@{me.username or me.id})")
                await test_client.disconnect()
                print("👉 ব্যাকগ্রাউন্ডে সার্ভিস চালু করতে রান করুন:")
                print("nohup python video_collector/main.py >> video_collector.log 2>&1 &\n")
                return
        else:
            await test_client.disconnect()
            remove_session_files()

    # Clean fresh client instance
    client = TelegramClient(session_path, TG_API_ID, TG_API_HASH)
    await client.connect()

    print("💡 অন্যের চ্যানেল/গ্রুপ থেকে ভিডিও আনতে আপনার টেলিগ্রাম ফোন নাম্বার দিয়ে লগইন করুন:")
    raw_phone = input("\n👉 আপনার টেলিগ্রাম ফোন নাম্বার দিন (e.g. 017xxxxxxxx বা +88017xxxxxxxx): ").strip()
    phone = format_phone_number(raw_phone)
    print(f"📞 টেলিগ্রামে কোড পাঠানো হচ্ছে: {phone}...")

    # Start login flow (Telethon will prompt for Telegram OTP code)
    await client.start(phone=phone)

    me = await client.get_me()
    account_type = "বট একাউন্ট (Bot)" if getattr(me, "bot", False) else "ইউজার একাউন্ট (Userbot - সঠিক)"
    print("\n" + "🎉" * 20)
    print("✅ লগইন সফল হয়েছে!")
    print(f"👤 নাম: {me.first_name} {me.last_name or ''}")
    print(f"🆔 টেলিগ্রাম আইডি: {me.id}")
    print(f"🔖 ইউজারনেম: @{me.username if me.username else 'নেই'}")
    print(f"🏷️ একাউন্ট টাইপ: {account_type}")
    print(f"📁 সেশন ফাইল সেভ হয়েছে: {session_path}.session")
    print("🎉" * 20 + "\n")

    print("🚀 ইউজারবট রেডি! এখন আপনি যেকোনো পাবলিক সোর্স চ্যানেল থেকে স্বয়ংক্রিয়ভাবে ভিডিও আনতে পারবেন।")
    print("\n👉 ব্যাকগ্রাউন্ডে সার্ভিস চালু করার কমান্ড:")
    print("nohup python video_collector/main.py >> video_collector.log 2>&1 &\n")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
