"""
One-click manual trigger to deliver collected videos from queue or directly from source channels to @darkromanceadda
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
    add_queue_item, get_setting, get_pool, is_media_processed, is_message_processed
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
        # Check sessions/ folder for any authorized session
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

    deliveries = await get_delivery_channel_targets()
    print(f"🎯 ডেলিভারি চ্যানেল তালিকা: {deliveries}")
    if not deliveries:
        print("❌ কোনো ডেলিভারি চ্যানেল ডাটাবেজে পাওয়া যায়নি!")
        await client.disconnect()
        return

    pool = await get_pool()
    queue_cnt = 0
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM vc_queue")
            queue_cnt = (await cur.fetchone())[0]

    print(f"⏳ ডাটাবেজ কিউতে অপেক্ষমান ভিডিও সংখ্যা: {queue_cnt} টি")

    delivered = 0

    # ── Phase 1: Try delivering from existing queue ─────────────────
    if queue_cnt > 0:
        print(f"\n📦 কিউ থেকে ভিডিও পাঠানোর চেষ্টা করা হচ্ছে...")
        attempts = 0
        max_attempts = max(10, count * 3)

        while delivered < count and attempts < max_attempts:
            attempts += 1
            item = await get_next_queue_item()
            if not item:
                break

            queue_id = item["id"]
            source_chat = item["source_chat_id"]
            msg_id = item["source_message_id"]

            print(f"👉 কিউ আইটেম #{queue_id} চেক করা হচ্ছে (সোর্স চ্যাট: {source_chat}, মেসেজ ID: {msg_id})...")

            try:
                orig_msg = await client.get_messages(source_chat, ids=msg_id)
            except Exception as e_fetch:
                err_text = str(e_fetch).lower()
                if "input entity" in err_text or "could not find" in err_text:
                    print(f"   ⚠️ সোর্স চ্যাট ID ({source_chat}) টেলিগ্রামে পাওয়া যাচ্ছে না (পুরনো বা অচল)।")
                    print(f"   🧹 এই অচল চ্যাটের বাকি সব পুরনো কিউ আইটেম ডাটাবেজ থেকে মুছে ফেলা হচ্ছে...")
                    async with pool.acquire() as conn:
                        async with conn.cursor() as cur:
                            await cur.execute("DELETE FROM vc_queue WHERE source_chat_id = %s", (source_chat,))
                    break
                else:
                    print(f"   ⚠️ মেসেজ অ্যাক্সেস এরর: {e_fetch}")
                    orig_msg = None

            if not orig_msg or not orig_msg.media:
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

    # ── Phase 2: Direct Crawl & Deliver from Source Channels ────────
    if delivered < count:
        needed = count - delivered
        print(f"\n🔍 কিউতে আর কোনো সচল ভিডিও নেই। এখন সরাসরি সোর্স চ্যানেলগুলো থেকে {needed}টি নতুন ভিডিও সংগ্রহ করে পাঠানো হচ্ছে...")

        cand_sources = []
        sources_data = await get_source_channel_targets()
        for r in sources_data.get("rows", []):
            t = r.get("channel_username") or r.get("channel_id")
            if t and t not in cand_sources:
                cand_sources.append(t)

        # Also inspect user's joined channels from dialogs
        try:
            async for d in client.iter_dialogs(limit=30):
                if d.is_channel or d.is_group:
                    ent = d.entity
                    uname = (getattr(ent, "username", "") or "").lower()
                    title = (getattr(ent, "title", "") or "").lower()
                    if "darkromanceadda" not in uname and "dark romance" not in title:
                        cand = uname if uname else d.id
                        if cand not in cand_sources:
                            cand_sources.append(cand)
        except Exception:
            pass

        # Fallback public active source channels
        for df in ["ayssorbonas420", "pfff_boom", "adult_desi30"]:
            if df not in cand_sources:
                cand_sources.append(df)

        print(f"📥 মোট স্ক্যানযোগ্য সোর্স চ্যানেল: {len(cand_sources)} টি")

        for src in cand_sources:
            if delivered >= count:
                break
            try:
                print(f"   ➜ সোর্স চ্যানেল চেক করা হচ্ছে: {src}...")
                entity = await client.get_entity(src)
                async for msg in client.iter_messages(entity, limit=35):
                    if delivered >= count:
                        break
                    if _is_video_message(msg, min_duration=5):
                        media_id = get_media_unique_id(msg)
                        chat_id = getattr(entity, "id", 0)

                        if media_id and await is_media_processed(media_id):
                            continue
                        if await is_message_processed(chat_id, msg.id, media_id):
                            continue

                        custom_caption = await get_setting("custom_caption", "")
                        clean_caption = custom_caption.strip() if custom_caption else clean_source_caption(msg.text or "")

                        success = False
                        for target in deliveries:
                            print(f"🚀 নতুন ভিডিও (Msg ID: #{msg.id}) পাঠানো হচ্ছে -> {target}...")
                            try:
                                target_ent = await client.get_entity(target)
                            except Exception:
                                target_ent = target
                            ok = await deliver_video_message(msg, target_ent, clean_caption, client_instance=client)
                            if ok:
                                success = True
                                print(f"   ✅ সফলভাবে চ্যানেলে পোস্ট হয়েছে: {target}")
                                try:
                                    await sync_video_to_portal_vault(msg, clean_caption)
                                except Exception:
                                    pass

                        if success:
                            delivered += 1
                            await mark_message_processed(chat_id, msg.id, media_id)
                            await increment_forwarded_count()
                            print(f"   🎉 সফল ডেলিভারি: [{delivered}/{count}]")
                            await asyncio.sleep(2)
            except Exception as e_crawl:
                print(f"      ❌ {src} থেকে সংগ্রহ করতে সমস্যা: {e_crawl}")

    print("\n" + "=" * 65)
    print(f"🏁 কাজ সম্পন্ন! মোট সফল ডেলিভারি: {delivered} টি ভিডিও।")
    print("=" * 65 + "\n")

    try:
        await client.disconnect()
    except Exception:
        pass


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 2
    asyncio.run(run_deliver_now(count))
