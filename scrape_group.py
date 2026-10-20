#!/usr/bin/env python3
"""
scrape_group.py — Scrape members from an old or source Telegram group
and save them into the bot database (users table) as candidates.

Usage:
    python scrape_group.py <group_username_or_link> [account_name]

Example:
    python scrape_group.py alltimefantasyzone sajib
    python scrape_group.py @myoldgroup
"""

import sys
import os
import asyncio
import logging
import aiomysql
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest

from config import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB
)

TG_API_ID = 39868770
TG_API_HASH = "8f29bf42ea3ab7207c2e0b1ba5a98bf6"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("scraper")


async def get_db_pool():
    return await aiomysql.create_pool(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        db=MYSQL_DB,
        charset="utf8mb4",
        autocommit=True
    )


def get_available_session(requested_acc: str = "") -> str:
    if requested_acc:
        clean = requested_acc.replace(".session", "").strip()
        path = os.path.join(SESSIONS_DIR, clean)
        if os.path.exists(path + ".session"):
            return path
        logger.warning(f"Session '{requested_acc}' not found. Checking other sessions...")

    if not os.path.exists(SESSIONS_DIR):
        os.makedirs(SESSIONS_DIR, exist_ok=True)

    files = [f for f in os.listdir(SESSIONS_DIR) if f.endswith(".session")]
    if not files:
        logger.error("❌ No Telegram account sessions found in sessions/ folder!")
        logger.error("👉 Please log in at least one account via Admin Panel or 'python login_adder.py <name>'")
        sys.exit(1)

    return os.path.join(SESSIONS_DIR, files[0].replace(".session", ""))


async def main():
    if len(sys.argv) < 2:
        print("\n" + "═" * 65)
        print("    📥 TELEGRAM GROUP MEMBER SCRAPER TO BOT DATABASE")
        print("═" * 65)
        print("ব্যবহারের নিয়ম:")
        print("    python scrape_group.py <source_group> [account_name]\n")
        print("উদাহরণ:")
        print("    python scrape_group.py alltimefantasyzone sajib")
        print("    python scrape_group.py https://t.me/oldgroup\n")
        return

    raw_target = sys.argv[1].strip()
    source_group = raw_target.split("/")[-1].lstrip("@")
    requested_acc = sys.argv[2] if len(sys.argv) > 2 else ""

    session_path = get_available_session(requested_acc)
    account_name = os.path.basename(session_path)

    logger.info(f"🚀 Using account: [{account_name}] to scrape group: @{source_group}")

    client = TelegramClient(session_path, TG_API_ID, TG_API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        logger.error(f"❌ Account [{account_name}] is not authorized! Run 'python login_adder.py {account_name}'")
        return

    me = await client.get_me()
    logger.info(f"✅ Logged in as: {me.first_name} (@{me.username or me.id})")

    # Resolve source group
    try:
        group_entity = await client.get_entity(source_group)
        try:
            await client(JoinChannelRequest(group_entity))
        except Exception:
            pass
        title = getattr(group_entity, "title", source_group)
        chat_id = getattr(group_entity, "id", 0)
        logger.info(f"🎯 Connected to group: '{title}' [ID: {chat_id}]")
    except Exception as e:
        logger.error(f"❌ Failed to access group '@{source_group}': {e}")
        return

    pool = await get_db_pool()

    # Ensure users table exists with created_at
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id    BIGINT NOT NULL,
                    chat_id    BIGINT NOT NULL,
                    username   VARCHAR(100),
                    first_name VARCHAR(200),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, chat_id),
                    INDEX idx_users_created (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            try:
                await cur.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            except Exception:
                pass
            try:
                await cur.execute("ALTER TABLE users ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
            except Exception:
                pass

    logger.info("⏳ Scraping group participants from Telegram... (Please wait)")

    saved_count = 0
    with_un_count = 0
    without_un_count = 0
    batch = []

    try:
        async for p in client.iter_participants(group_entity, limit=10000):
            if not p or not getattr(p, "id", None) or getattr(p, "bot", False) or getattr(p, "deleted", False):
                continue

            uid = p.id
            un = (getattr(p, "username", "") or "").strip().lstrip("@")
            fn = (getattr(p, "first_name", "") or "User")[:200]

            if un:
                with_un_count += 1
            else:
                without_un_count += 1

            batch.append((uid, chat_id, un, fn))

            if len(batch) >= 100:
                async with pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.executemany("""
                            INSERT INTO users (user_id, chat_id, username, first_name, created_at)
                            VALUES (%s, %s, %s, %s, NOW())
                            ON DUPLICATE KEY UPDATE 
                                username = VALUES(username),
                                first_name = VALUES(first_name),
                                updated_at = NOW()
                        """, batch)
                saved_count += len(batch)
                print(f"\r📥 Scraped & Saved: {saved_count:,} members...", end="", flush=True)
                batch = []

        if batch:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.executemany("""
                        INSERT INTO users (user_id, chat_id, username, first_name, created_at)
                        VALUES (%s, %s, %s, %s, NOW())
                        ON DUPLICATE KEY UPDATE 
                            username = VALUES(username),
                            first_name = VALUES(first_name),
                            updated_at = NOW()
                    """, batch)
            saved_count += len(batch)

        print()
        logger.info("═" * 55)
        logger.info(f"🎉 SCRAPING COMPLETE FOR '{title}'!")
        logger.info(f"✅ Total Members Saved to DB : {saved_count:,} জন")
        logger.info(f"   ├─ ইউজারনেম যুক্ত (@username) : {with_un_count:,} জন")
        logger.info(f"   └─ ইউজারনেম ছাড়া (ID only)  : {without_un_count:,} জন")
        logger.info("💡 Note: All scraped members are now in local session cache & DB candidates!")
        logger.info("═" * 55)

    except Exception as e:
        logger.error(f"❌ Error during scraping: {e}")
    finally:
        await client.disconnect()
        pool.close()
        await pool.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
