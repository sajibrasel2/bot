#!/usr/bin/env python3
"""
check_db.py — Diagnostic utility to inspect the bot's database,
member statistics, candidate status, and historical data.
"""

import asyncio
import sys
import os
import aiomysql
from datetime import datetime

# Load configuration
try:
    from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB
except Exception as e:
    print(f"❌ Failed to load config: {e}")
    sys.exit(1)


async def main():
    print("\n" + "═" * 65)
    print("      📊 BOT DATABASE & MEMBER ADDER DIAGNOSTIC REPORT")
    print("═" * 65)
    print(f"🌐 Host     : {MYSQL_HOST}:{MYSQL_PORT}")
    print(f"🗄️  Database : {MYSQL_DB}")
    print(f"👤 User     : {MYSQL_USER}")
    print("─" * 65)

    try:
        pool = await aiomysql.create_pool(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            db=MYSQL_DB,
            charset="utf8mb4",
            autocommit=True
        )
    except Exception as e:
        print(f"❌ Could not connect to MySQL: {e}")
        print("👉 Please verify MySQL credentials in config.py or .env")
        return

    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # 1. Check Tables List
            await cur.execute("SHOW TABLES")
            tables = [list(r.values())[0] for r in await cur.fetchall()]
            print(f"📁 Tables Found ({len(tables)}): {', '.join(tables)}")
            print("─" * 65)

            # Check if users table exists
            if "users" not in tables:
                print("❌ 'users' table not found in database!")
                pool.close()
                await pool.wait_closed()
                return

            # Dynamic migration: ensure created_at & updated_at columns exist
            try:
                await cur.execute("SHOW COLUMNS FROM users LIKE 'created_at'")
                if not await cur.fetchone():
                    print("🔄 'users' টেবিলে 'created_at' কলাম তৈরি ও ইনডেক্স করা হচ্ছে...")
                    await cur.execute("ALTER TABLE users ADD COLUMN `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                    await cur.execute("ALTER TABLE users ADD COLUMN `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
                    await cur.execute("ALTER TABLE users ADD INDEX `idx_users_created` (created_at)")
                    print("✅ কলাম সফলভাবে তৈরি হয়েছে!")
            except Exception as e:
                pass

            # Backfill timestamps from user_name_history & user_invites
            try:
                await cur.execute("SELECT COUNT(*) as cnt FROM user_name_history")
                unh_cnt = (await cur.fetchone())["cnt"]
                await cur.execute("SELECT COUNT(*) as cnt FROM user_invites")
                ui_cnt = (await cur.fetchone())["cnt"]
                print(f"📜 হিস্টোরি ডেটা: Name History: {unh_cnt:,} টি | Invites: {ui_cnt:,} টি")

                await cur.execute("""
                    UPDATE users u
                    JOIN (
                        SELECT user_id, MIN(recorded_at) as first_seen, MAX(recorded_at) as last_seen 
                        FROM user_name_history 
                        GROUP BY user_id
                    ) unh ON u.user_id = unh.user_id
                    SET u.created_at = FROM_UNIXTIME(unh.first_seen),
                        u.updated_at = FROM_UNIXTIME(unh.last_seen)
                    WHERE unh.first_seen > 0
                """)
                unh_updated = cur.rowcount

                await cur.execute("""
                    UPDATE users u
                    JOIN (
                        SELECT invited_id, MAX(timestamp) as last_invite 
                        FROM user_invites 
                        GROUP BY invited_id
                    ) ui ON u.user_id = ui.invited_id
                    SET u.created_at = GREATEST(COALESCE(u.created_at, FROM_UNIXTIME(ui.last_invite)), FROM_UNIXTIME(ui.last_invite))
                    WHERE ui.last_invite > 0
                """)
                ui_updated = cur.rowcount
                if unh_updated > 0 or ui_updated > 0:
                    print(f"✅ {unh_updated + ui_updated:,} জন মেম্বারের আসল যোগদানের সময় সফলভাবে সিংক হয়েছে!")
            except Exception as e:
                print(f"⚠️ Timestamp sync notice: {e}")

            # Check columns in users
            await cur.execute("SHOW COLUMNS FROM users")
            u_cols = [c["Field"] for c in await cur.fetchall()]
            has_created_at = "created_at" in u_cols

            # 2. Users Table Summary
            await cur.execute("SELECT COUNT(DISTINCT user_id) as total_users FROM users")
            total_users = (await cur.fetchone())["total_users"]

            await cur.execute("SELECT COUNT(DISTINCT user_id) as with_un FROM users WHERE username IS NOT NULL AND username != ''")
            with_un = (await cur.fetchone())["with_un"]
            without_un = total_users - with_un

            pct_un = (with_un / total_users * 100) if total_users > 0 else 0
            print(f"👥 TOTAL MEMBERS IN DATABASE : {total_users:,} জন")
            print(f"   ├─ ইউজারনেম আছে (@username) : {with_un:,} জন ({pct_un:.1f}%)")
            print(f"   └─ ইউজারনেম নেই (Numeric ID) : {without_un:,} জন ({100 - pct_un:.1f}%)")
            print("─" * 65)

            # 3. Newest Members in Database (Last 10)
            print("🆕 সম্প্রতি ডেটাবেজে যুক্ত হওয়া ১০ জন মেম্বার (Newest Members):")
            if has_created_at:
                await cur.execute("""
                    SELECT user_id, 
                           MAX(username) as username, 
                           MAX(first_name) as first_name,
                           MAX(COALESCE(created_at, '2000-01-01')) as join_time
                    FROM users
                    GROUP BY user_id
                    ORDER BY join_time DESC, user_id DESC
                    LIMIT 10
                """)
            else:
                await cur.execute("""
                    SELECT user_id, MAX(username) as username, MAX(first_name) as first_name, 'N/A' as join_time
                    FROM users
                    GROUP BY user_id
                    ORDER BY user_id DESC
                    LIMIT 10
                """)
            new_users = await cur.fetchall()
            for idx, u in enumerate(new_users, 1):
                un = f"@{u['username']}" if u.get('username') else "[No Username]"
                fn = (u.get('first_name') or 'N/A')[:18]
                jt = u.get('join_time') or 'N/A'
                print(f"   {idx:2d}. ID: {u['user_id']:<11} | {un:<20} | {fn:<18} | Time: {jt}")
            print("─" * 65)

            # 4. Target Group Adder Stats
            target_group = "darkromanceadda24"
            # Read from settings if present
            if "member_adder_settings" in tables:
                await cur.execute("SELECT setting_val FROM member_adder_settings WHERE setting_key='target_group'")
                s_row = await cur.fetchone()
                if s_row and s_row.get("setting_val"):
                    target_group = s_row["setting_val"].strip().lstrip("@")

            print(f"🎯 টার্গেট গ্রুপ (@{target_group}) এর অটো-অ্যাডার স্ট্যাটাস:")
            if "member_add_history" in tables:
                await cur.execute("""
                    SELECT status, COUNT(*) as cnt 
                    FROM member_add_history 
                    WHERE target_chat = %s 
                    GROUP BY status
                """, (target_group,))
                hist_rows = await cur.fetchall()
                status_counts = {r["status"]: r["cnt"] for r in hist_rows}
                added = status_counts.get("added", 0)
                already = status_counts.get("already_in_group", 0)
                privacy = status_counts.get("privacy_restricted", 0)
                uncached = status_counts.get("uncached_id", 0)
                other = sum(v for k, v in status_counts.items() if k not in ["added", "already_in_group", "privacy_restricted", "uncached_id"])

                print(f"   ├─ ✅ সফলভাবে যুক্ত (Added)       : {added:,} জন")
                print(f"   ├─ ℹ️  আগে থেকেই গ্রুপে ছিল       : {already:,} জন")
                print(f"   ├─ 🔒 প্রাইভেসি রেস্ট্রিক্টেড      : {privacy:,} জন")
                print(f"   ├─ ⚠️ আইডি ক্যাশে নেই (Uncached) : {uncached:,} জন")
                if other > 0:
                    print(f"   ├─ ⏭️ অন্যান্য স্কিপ/এরর         : {other:,} জন")
                print(f"   └─ 📊 মোট হিস্টোরি এন্ট্রি        : {sum(status_counts.values()):,} টি")

                # Candidates remaining
                if has_created_at:
                    await cur.execute("""
                        SELECT 
                            COUNT(DISTINCT u.user_id) as rem_total,
                            SUM(CASE WHEN u.username IS NOT NULL AND u.username != '' THEN 1 ELSE 0 END) as rem_un
                        FROM users u
                        LEFT JOIN member_add_history h 
                          ON h.user_id = u.user_id AND h.target_chat = %s
                        WHERE h.id IS NULL
                    """, (target_group,))
                else:
                    await cur.execute("""
                        SELECT 
                            COUNT(DISTINCT u.user_id) as rem_total,
                            SUM(CASE WHEN u.username IS NOT NULL AND u.username != '' THEN 1 ELSE 0 END) as rem_un
                        FROM users u
                        LEFT JOIN member_add_history h 
                          ON h.user_id = u.user_id AND h.target_chat = %s
                        WHERE h.id IS NULL
                    """, (target_group,))
                c_row = await cur.fetchone()
                rem_total = c_row["rem_total"] if c_row else 0
                rem_un = c_row["rem_un"] if c_row and c_row["rem_un"] else 0
                print(f"\n   🚀 ইনভাইটের জন্য বাকি রয়েছে (Candidates): {rem_total:,} জন")
                print(f"      ├─ ইউজারনেম যুক্ত (Priority 1) : {rem_un:,} জন")
                print(f"      └─ শুধু নিউমেরিক আইডি (ID Only) : {rem_total - rem_un:,} জন")
            else:
                print("   ⚠️ 'member_add_history' টেবিল এখনো তৈরি হয়নি (অ্যাডার রান হলে তৈরি হবে)।")
            print("─" * 65)

            # 5. Connected Groups in Database
            print("🏢 ডেটাবেজে সংরক্ষিত গ্রুপসমূহ (Groups in DB):")
            await cur.execute("""
                SELECT u.chat_id, COUNT(DISTINCT u.user_id) as member_count, 
                       COALESCE(cs.chat_title, 'Unknown Group') as title
                FROM users u
                LEFT JOIN chat_settings cs ON cs.chat_id = u.chat_id
                WHERE u.chat_id < 0
                GROUP BY u.chat_id
                ORDER BY member_count DESC
            """)
            g_rows = await cur.fetchall()
            if g_rows:
                for idx, g in enumerate(g_rows, 1):
                    print(f"   {idx}. Chat ID: {g['chat_id']:<15} | মেম্বার: {g['member_count']:<6} জন | নাম: {g['title']}")
            else:
                print("   ℹ️ কোনো নির্দিষ্ট গ্রুপ আইডি ফিল্টার নেই।")
            print("─" * 65)

            # 6. Check other MySQL databases on server (to answer "আগের ডাটাবেজ কানেক্ট")
            try:
                await cur.execute("SHOW DATABASES")
                all_dbs = [list(r.values())[0] for r in await cur.fetchall()]
                # filter out system databases
                user_dbs = [d for d in all_dbs if d not in ["information_schema", "mysql", "performance_schema", "sys"]]
                print(f"🗃️  আপনার cPanel সার্ভারে মোট ডেটাবেজ ({len(user_dbs)}):")
                for d in user_dbs:
                    current_tag = " (👈 বর্তমান বট ডেটাবেজ)" if d == MYSQL_DB else ""
                    print(f"   • {d}{current_tag}")
                    if d != MYSQL_DB and "bot" in d:
                        try:
                            await cur.execute(f"SHOW TABLES FROM `{d}` LIKE 'users'")
                            if await cur.fetchone():
                                await cur.execute(f"SELECT COUNT(*) as cnt FROM `{d}`.users")
                                other_cnt = (await cur.fetchone())["cnt"]
                                print(f"     └─ 🔍 এই ডেটাবেজেও 'users' টেবিল আছে! মোট মেম্বার: {other_cnt:,} জন")
                        except Exception:
                            pass
            except Exception:
                pass
            print("═" * 65 + "\n")

    pool.close()
    await pool.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
