"""
One-click manual trigger to deliver 2 collected videos from queue or source channels directly to @darkromanceadda
Run: python deliver_now.py
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
    add_queue_item, get_setting
)
from video_collector.main import (
    clean_source_caption, deliver_video_message, sync_video_to_portal_vault,
    auto_join_channel, _is_video_message, get_media_unique_id
)

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger("deliver_now")


async def run_deliver_now(count: int = 2):
    print("\n" + "=" * 65)
    print("🚀 ডেলিভারি চ্যানেল (@darkromanceadda) এ ২টি ভিডিও প্রেরণের প্রক্রিয়া শুরু হচ্ছে...")
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
    account_type = "বট একাউন্ট (@" + (me.username or "") + ")" if is_bot else f"ইউজার একাউন্ট ({me.first_name} @{me.username or me.phone})"
    print(f"👤 বর্তমানে সংযুক্ত: {account_type}")

    deliveries = await get_delivery_channel_targets()
    print(f"🎯 ডেলিভারি চ্যানেল তালিকা: {deliveries}")
    if not deliveries:
        print("❌ কোনো ডেলিভারি চ্যানেল ডাটাবেজে পাওয়া যায়নি!")
        await client.disconnect()
        return

    # Check queue count in MySQL
    import aiomysql
    from video_collector.database import get_pool
    pool = await get_pool()
    queue_cnt = 0
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM vc_queue")
            queue_cnt = (await cur.fetchone())[0]

    print(f"⏳ ডাটাবেজ কিউতে অপেক্ষমান ভিডিও সংখ্যা: {queue_cnt} টি")

    # If queue is empty, attempt to crawl sources now
    if queue_cnt == 0:
        print("\n🔍 কিউ খালি রয়েছে! সোর্স চ্যানেলগুলো থেকে নতুন ভিডিও সংগ্রহ করার চেষ্টা করা হচ্ছে...")
        sources_data = await get_source_channel_targets()
        rows = sources_data.get("rows", [])
        print(f"📥 মোট সোর্স চ্যানেল: {len(rows)} টি")

        if is_bot:
            print("⚠️ সতর্কতা: আপনি বট (@" + (me.username or "") + ") হিসেবে কানেক্টেড আছেন।")
            print("💡 টেলিগ্রামের নিয়মে বট অন্যের চ্যানেলের ভিডিও রিড করতে পারে না যতক্ষণ না বটকে সেই সোর্স চ্যানেলে এডমিন করা হয়।")
            print("👉 অন্যের যেকোনো পাবলিক চ্যানেল থেকে আনলিমিটেড ভিডিও আনতে আপনার নিজস্ব একাউন্ট দিয়ে একবার লগইন করুন:")
            print("   python video_collector/login.py\n")

        new_found = 0
        for r in rows:
            target = r.get("channel_username") or r.get("channel_id")
            if not target:
                continue
            try:
                print(f"   ➜ সোর্স চ্যানেল চেক করা হচ্ছে: {target}...")
                entity = await client.get_entity(target)
                async for msg in client.iter_messages(entity, limit=20):
                    if _is_video_message(msg):
                        media_id = get_media_unique_id(msg)
                        clean_caption = clean_source_caption(msg.text or "")
                        chat_id = getattr(entity, "id", 0)
                        qid = await add_queue_item(chat_id, msg.id, str(msg.id), clean_caption, media_id=media_id)
                        if qid:
                            new_found += 1
                            print(f"      ✅ নতুন ভিডিও কিউতে যুক্ত হয়েছে! ID: #{qid}")
                            if new_found >= 5:
                                break
            except Exception as e_crawl:
                print(f"      ❌ {target} থেকে রিড করতে সমস্যা: {e_crawl}")

        print(f"🎉 সংগ্রহ সমাপ্ত: মোট {new_found} টি নতুন ভিডিও কিউতে যুক্ত হয়েছে।\n")

    # Now deliver requested number of videos
    delivered = 0
    print(f"📤 এখন {count}টি ভিডিও ডেলিভারি করা হচ্ছে...")
    for idx in range(count):
        item = await get_next_queue_item()
        if not item:
            print(f"ℹ️ কিউতে আর কোনো ভিডিও নেই। (ডেলিভারি সম্পন্ন: {delivered} টি)")
            break

        queue_id = item["id"]
        source_chat = item["source_chat_id"]
        msg_id = item["source_message_id"]

        try:
            orig_msg = await client.get_messages(source_chat, ids=msg_id)
            if not orig_msg or not orig_msg.media:
                await delete_queue_item(queue_id)
                continue

            custom_caption = await get_setting("custom_caption", "")
            caption = custom_caption.strip() if custom_caption else clean_source_caption(orig_msg.text or item.get("caption") or "")

            success = False
            for target in deliveries:
                print(f"🚀 ভিডিও #{queue_id} পাঠানো হচ্ছে -> {target}...")
                ok = await deliver_video_message(orig_msg, target, caption)
                if ok:
                    success = True
                    print(f"✅ সফলভাবে পাঠানো হয়েছে: {target}")
                    try:
                        await sync_video_to_portal_vault(orig_msg, caption)
                    except Exception:
                        pass

            await delete_queue_item(queue_id)
            await mark_message_processed(source_chat, msg_id)

            if success:
                delivered += 1
                await increment_forwarded_count()
                print(f"🗑️ কিউ থেকে #{queue_id} ডিলিট করা হয়েছে। ({delivered}/{count} টি পাঠানো হলো)")
                await asyncio.sleep(2)

        except Exception as e_del:
            print(f"❌ ভিডিও #{queue_id} পাঠাতে এরর: {e_del}")
            await delete_queue_item(queue_id)

    print("\n" + "=" * 65)
    print(f"🏁 কাজ সম্পন্ন! মোট সফল ডেলিভারি: {delivered} টি ভিডিও।")
    print("=" * 65 + "\n")

    await client.disconnect()


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 2
    asyncio.run(run_deliver_now(count))
