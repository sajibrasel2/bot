"""
One-click manual trigger to deliver 2 collected videos from queue or source channels directly to @darkromanceadda
Run: python deliver_now.py [count]
"""

import os
import sys
import asyncio
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telethon import TelegramClient
from video_collector.config import TG_API_ID, TG_API_HASH, SESSION_NAME, VC_BOT_TOKEN
from video_collector.database import (
    init_db, get_next_queue_item, delete_queue_item, mark_message_processed,
    increment_forwarded_count, get_delivery_channel_targets, get_source_channel_targets,
    add_queue_item, get_setting, get_pool
)
from video_collector.main import (
    clean_source_caption, deliver_video_message, sync_video_to_portal_vault,
    auto_join_channel, _is_video_message, get_media_unique_id
)

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger("deliver_now")


async def run_deliver_now(count: int = 2):
    print("\n" + "=" * 65)
    print(f"🚀 ডেলিভারি চ্যানেল (@darkromanceadda) এ {count}টি ভিডিও প্রেরণের প্রক্রিয়া শুরু হচ্ছে...")
    print("=" * 65 + "\n")

    await init_db()

    session_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "video_collector")
    session_path = os.path.join(session_dir, SESSION_NAME)
    client = TelegramClient(session_path, TG_API_ID, TG_API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        # Check sessions/ folder for any authorized member adder session
        project_root = os.path.dirname(os.path.abspath(__file__))
        sessions_dir = os.path.join(project_root, "sessions")
        found_sess = None
        if os.path.isdir(sessions_dir):
            for fname in os.listdir(sessions_dir):
                if fname.endswith(".session"):
                    cand_base = os.path.join(sessions_dir, fname[:-8])
                    try:
                        cand_c = TelegramClient(cand_base, TG_API_ID, TG_API_HASH)
                        await cand_c.connect()
                        if await cand_c.is_user_authorized():
                            found_sess = cand_base
                            await cand_c.disconnect()
                            break
                        await cand_c.disconnect()
                    except Exception:
                        pass

        if found_sess:
            import shutil
            logger.info(f"🔄 Using existing authorized account from {found_sess}.session")
            shutil.copyfile(found_sess + ".session", session_path + ".session")
            await client.disconnect()
            await client.connect()

        if not await client.is_user_authorized():
            if VC_BOT_TOKEN:
                logger.info("🤖 Starting Telethon client using VC_BOT_TOKEN (@videocoolect_bot)...")
                await client.start(bot_token=VC_BOT_TOKEN)
            else:
                logger.error("❌ No authorized session and no VC_BOT_TOKEN found!")
                return

    me = await client.get_me()
    is_bot = getattr(me, "bot", False)
    account_type = f"বট একাউন্ট (@{me.username})" if is_bot else f"ইউজার একাউন্ট ({me.first_name} @{me.username or me.phone or me.id})"
    print(f"👤 বর্তমানে সংযুক্ত: {account_type}")

    if is_bot:
        print("\n" + "!" * 65)
        print("⚠️ অত্যন্ত গুরুত্বপূর্ণ নোটিশ:")
        print(f"   আপনি টেলিগ্রাম বট (@{me.username}) হিসেবে কানেক্টেড আছেন।")
        print("   টেলিগ্রামের নিয়মে বট কখনো অন্যের চ্যানেল থেকে ভিডিও রিড/কালেক্ট করতে পারে না।")
        print("   সোর্স চ্যানেল থেকে সরাসরি রিয়েল ভিডিও এনে ডেলিভারি করতে")
        print("   আপনার ফোন নাম্বার দিয়ে মাত্র একবার নিচের কমান্ড দিয়ে লগইন করুন:")
        print("   ➜ python video_collector/login.py")
        print("!" * 65 + "\n")

    deliveries = await get_delivery_channel_targets()
    print(f"🎯 ডেলিভারি চ্যানেল তালিকা: {deliveries}")
    if not deliveries:
        print("❌ কোনো ডেলিভারি চ্যানেল ডাটাবেজে পাওয়া যায়নি!")
        await client.disconnect()
        return

    # Check queue count in MySQL
    pool = await get_pool()
    queue_cnt = 0
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM vc_queue")
            queue_cnt = (await cur.fetchone())[0]

    print(f"⏳ ডাটাবেজ কিউতে অপেক্ষমান ভিডিও সংখ্যা: {queue_cnt} টি")

    # Helper function to crawl source channels if needed
    async def crawl_fresh_videos(target_count: int = 5) -> int:
        print("\n🔍 সোর্স চ্যানেলগুলো থেকে নতুন ভিডিও সংগ্রহ করার চেষ্টা করা হচ্ছে...")
        if is_bot:
            print("❌ আপনি বট হিসেবে আছেন। বট অন্যের চ্যানেল থেকে ভিডিও সংগ্রহ করতে পারে না!")
            print("👉 অনুগ্রহ করে 'python video_collector/login.py' দিয়ে আপনার একাউন্টে লগইন করুন।\n")
            return 0

        sources_data = await get_source_channel_targets()
        rows = sources_data.get("rows", [])
        print(f"📥 মোট সোর্স চ্যানেল: {len(rows)} টি")
        new_found = 0
        for r in rows:
            target = r.get("channel_username") or r.get("channel_id")
            if not target:
                continue
            try:
                print(f"   ➜ সোর্স চ্যানেল চেক করা হচ্ছে: {target}...")
                entity = await client.get_entity(target)
                async for msg in client.iter_messages(entity, limit=30):
                    if _is_video_message(msg):
                        media_id = get_media_unique_id(msg)
                        clean_caption = clean_source_caption(msg.text or "")
                        chat_id = getattr(entity, "id", 0)
                        qid = await add_queue_item(chat_id, msg.id, str(msg.id), clean_caption, media_id=media_id)
                        if qid:
                            new_found += 1
                            print(f"      ✅ নতুন ভিডিও কিউতে যুক্ত হয়েছে! ID: #{qid}")
                            if new_found >= target_count:
                                break
                if new_found >= target_count:
                    break
            except Exception as e_crawl:
                print(f"      ❌ {target} থেকে রিড করতে সমস্যা: {e_crawl}")
        print(f"🎉 সংগ্রহ সমাপ্ত: মোট {new_found} টি নতুন ভিডিও কিউতে যুক্ত হয়েছে।\n")
        return new_found

    # If queue is empty, attempt to crawl sources now
    if queue_cnt == 0:
        await crawl_fresh_videos(target_count=count * 2)

    # Now deliver requested number of videos
    delivered = 0
    print(f"\n📤 এখন {count}টি ভিডিও ডেলিভারি করা হচ্ছে...")
    attempts = 0
    max_attempts = max(15, count * 5)

    while delivered < count and attempts < max_attempts:
        attempts += 1
        item = await get_next_queue_item()
        if not item:
            if not is_bot and delivered < count:
                print("ℹ️ কিউ খালি হয়ে গেছে। সোর্স চ্যানেল থেকে নতুন ভিডিও আনা হচ্ছে...")
                added = await crawl_fresh_videos(target_count=count - delivered)
                if added > 0:
                    continue
            print(f"ℹ️ কিউতে আর কোনো ভিডিও নেই। (মোট ডেলিভারি সম্পন্ন: {delivered} টি)")
            break

        queue_id = item["id"]
        source_chat = item["source_chat_id"]
        msg_id = item["source_message_id"]

        print(f"👉 কিউ আইটেম #{queue_id} প্রসেস করা হচ্ছে (সোর্স চ্যাট: {source_chat}, মেসেজ ID: {msg_id})...")

        try:
            orig_msg = await client.get_messages(source_chat, ids=msg_id)
        except Exception as e_fetch:
            print(f"   ⚠️ সোর্স মেসেজ অ্যাক্সেস করতে সমস্যা: {e_fetch}")
            orig_msg = None

        if not orig_msg or not orig_msg.media:
            if is_bot:
                print(f"   ⚠️ বট একাউন্ট দিয়ে সোর্স চ্যাট {source_chat} এর ভিডিও দেখা সম্ভব নয়।")
                print("   💡 এই ভিডিওটি কিউতে রেখে দেওয়া হলো যাতে ইউজারবট লগইন করার পর পাঠানো যায়।")
                break
            else:
                print(f"   🗑️ সোর্স চ্যাটে ভিডিওটি পাওয়া যায়নি বা মুছে ফেলা হয়েছে। কিউ থেকে #{queue_id} সরানো হলো।")
                await delete_queue_item(queue_id)
                continue

        custom_caption = await get_setting("custom_caption", "")
        caption = custom_caption.strip() if custom_caption else clean_source_caption(orig_msg.text or item.get("caption") or "")

        success = False
        for target in deliveries:
            print(f"🚀 ভিডিও #{queue_id} পাঠানো হচ্ছে -> {target}...")
            try:
                target_ent = await client.get_entity(target)
            except Exception:
                target_ent = target
            ok = await deliver_video_message(orig_msg, target_ent, caption, client_instance=client)
            if ok:
                success = True
                print(f"   ✅ সফলভাবে চ্যানেলে পোস্ট হয়েছে: {target}")
                try:
                    await sync_video_to_portal_vault(orig_msg, caption)
                except Exception:
                    pass

        await delete_queue_item(queue_id)
        await mark_message_processed(source_chat, msg_id)

        if success:
            delivered += 1
            await increment_forwarded_count()
            print(f"   🎉 সফল ডেলিভারি: [{delivered}/{count}]")
            await asyncio.sleep(2)
        else:
            print(f"   ❌ ভিডিও #{queue_id} পাঠানো ব্যর্থ হয়েছে।")

    print("\n" + "=" * 65)
    print(f"🏁 কাজ সম্পন্ন! মোট সফল ডেলিভারি: {delivered} টি ভিডিও।")
    if is_bot and delivered == 0:
        print("\n💡 সমাধান:")
        print("টেলিগ্রামের নিরাপত্তা বিধিমালার কারণে বট দিয়ে অন্যের চ্যানেল স্ক্র্যাপ করা যায় না।")
        print("সরাসরি সোর্স চ্যানেল থেকে ভিডিও অটো-পোস্ট করতে একবার নিচের কমান্ডটি রান করুন:")
        print("➜ python video_collector/login.py")
    print("=" * 65 + "\n")

    try:
        await client.disconnect()
    except Exception:
        pass


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 2
    asyncio.run(run_deliver_now(count))
