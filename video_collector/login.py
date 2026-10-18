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


async def main():
    print("\n" + "=" * 65)
    print("🔐 টেলিগ্রাম ইউজারবট ওয়ান-টাইম লগইন সিস্টেম")
    print("=" * 65)
    print(f"App API ID   : {TG_API_ID}")
    print(f"Session Path : {session_path}")
    print("=" * 65 + "\n")

    client = TelegramClient(session_path, TG_API_ID, TG_API_HASH)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        if getattr(me, "bot", False):
            print("⚠️ সতর্কতা: আপনি বর্তমানে 'বট টোকেন' (@" + str(me.username) + ") দিয়ে লগইন আছেন!")
            print("❌ টেলিগ্রামের নিয়মে বট অন্য মানুষের চ্যানেলে অ্যাডমিন ছাড়া মেসেজ/ভিডিও রিড করতে পারে না।")
            print("👉 অন্যের পাবলিক চ্যানেল থেকে ভিডিও কালেক্ট করতে আপনার নিজস্ব টেলিগ্রাম ফোন নাম্বার দিয়ে লগইন করতে হবে।\n")
            choice = input("আপনি কি সেশন রিসেট করে আপনার ফোন নাম্বার দিয়ে লগইন করতে চান? (y/n): ").strip().lower()
            if choice == "y":
                await client.log_out()
                print("🔄 পূর্বের বট সেশন মুছে ফেলা হয়েছে।")
            else:
                print(f"বর্তমান সেশন রাখা হলো: {me.first_name} (@{me.username})")
                await client.disconnect()
                return

    # Prompt explicitly for phone number if not authorized
    if not await client.is_user_authorized():
        print("💡 অন্যের চ্যানেল/গ্রুপ থেকে ভিডিও আনতে আপনার টেলিগ্রাম ফোন নাম্বার দিয়ে লগইন করুন:")
        phone = input("\n👉 আপনার টেলিগ্রাম ফোন নাম্বার দিন (e.g. +88017xxxxxxxx): ").strip()
        await client.start(phone=phone)

    me = await client.get_me()
    account_type = "বট একাউন্ট (Bot)" if getattr(me, "bot", False) else "ইউজার একাউন্ট (Userbot - সঠিক)"
    print("\n" + "🎉" * 20)
    print("✅ লগইন সফল হয়েছে!")
    print(f"👤 নাম: {me.first_name} {me.last_name or ''}")
    print(f"🆔 টেলিগ্রাম আইডি: {me.id}")
    print(f"🔖 ইউজারনেম: @{me.username if me.username else 'নেই'}")
    print(f"🏷️ একাউন্ট টাইপ: {account_type}")
    print(f"📁 সেশন ফাইল: {session_path}.session")
    print("🎉" * 20 + "\n")

    if getattr(me, "bot", False):
        print("⚠️ মনে রাখবেন: বট শুধুমাত্র সেই চ্যানেলগুলোর ভিডিও পাবে যেগুলোতে এই বটকে অ্যাডমিন করা আছে।")
    else:
        print("🚀 ইউজারবট রেডি! এখন আপনি যেকোনো পাবলিক সোর্স চ্যানেল থেকে স্বয়ংক্রিয়ভাবে ভিডিও আনতে পারবেন।")

    print("\n👉 ব্যাকগ্রাউন্ডে সার্ভিস চালু করার কমান্ড:")
    print("nohup python video_collector/main.py >> video_collector.log 2>&1 &\n")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
