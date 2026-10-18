"""
One-time Login Helper for Video Collector Userbot
Run this script interactively in your cPanel terminal once:
  python video_collector/login.py
It will ask for your phone number (+880...) and Telegram login OTP.
Once logged in, your session is saved permanently in collector_userbot.session!
"""

import sys
import os
import asyncio

# Ensure project root in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from video_collector.config import TG_API_ID, TG_API_HASH, SESSION_NAME

session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), SESSION_NAME)


async def main():
    print("\n" + "=" * 60)
    print("🔐 টেলিগ্রাম ইউজারবট ওয়ান-টাইম লগইন সিস্টেম")
    print("=" * 60)
    print(f"App API ID   : {TG_API_ID}")
    print(f"Session Path : {session_path}")
    print("=" * 60 + "\n")

    client = TelegramClient(session_path, TG_API_ID, TG_API_HASH)
    await client.start()

    me = await client.get_me()
    print("\n" + "🎉" * 20)
    print(f"✅ লগইন সফল হয়েছে!")
    print(f"👤 নাম: {me.first_name} {me.last_name or ''}")
    print(f"🆔 টেলিগ্রাম আইডি: {me.id}")
    print(f"🔖 ইউজারনেম: @{me.username if me.username else 'নেই'}")
    print(f"📁 সেশন ফাইল সেভ হয়েছে: {session_path}.session")
    print("🎉" * 20 + "\n")
    print("👉 এখন আপনি nohup দিয়ে ব্যাকগ্রাউন্ডে main.py চালু করতে পারবেন:")
    print("nohup python video_collector/main.py >> video_collector.log 2>&1 &\n")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
