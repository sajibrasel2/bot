"""
Interactive Login Helper for Member Auto-Adder
Allows adding and managing multiple Telegram accounts (e.g. nikita967).
Usage:
  python login_adder.py [account_name]
Example:
  python login_adder.py nikita967
"""

import sys
import os
import asyncio
import re

# Ensure project root in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telethon import TelegramClient
from video_collector.config import TG_API_ID, TG_API_HASH
import pymysql
from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB


def get_db():
    return pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASSWORD,
        database=MYSQL_DB, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def set_active_account(account_name: str) -> None:
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO member_adder_settings (setting_key, setting_val)
                VALUES ('active_account', %s)
                ON DUPLICATE KEY UPDATE setting_val = VALUES(setting_val)
            """, (account_name,))
        conn.close()
    except Exception as e:
        print(f"Note: Could not update active account in DB: {e}")


def register_account_in_db(account_name: str, tg_id: int, fname: str, lname: str, username: str, phone: str = "") -> None:
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS member_adder_accounts (
                    account_name VARCHAR(100) PRIMARY KEY,
                    phone VARCHAR(30) DEFAULT '',
                    telegram_id BIGINT DEFAULT NULL,
                    first_name VARCHAR(150) DEFAULT '',
                    last_name VARCHAR(150) DEFAULT '',
                    username VARCHAR(100) DEFAULT '',
                    status VARCHAR(50) DEFAULT 'authorized',
                    status_detail VARCHAR(255) DEFAULT 'সক্রিয়',
                    last_used DATETIME DEFAULT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            cur.execute("""
                INSERT INTO member_adder_accounts (account_name, phone, telegram_id, first_name, last_name, username, status, status_detail)
                VALUES (%s, %s, %s, %s, %s, %s, 'authorized', 'সক্রিয়')
                ON DUPLICATE KEY UPDATE
                    phone = VALUES(phone),
                    telegram_id = VALUES(telegram_id),
                    first_name = VALUES(first_name),
                    last_name = VALUES(last_name),
                    username = VALUES(username),
                    status = 'authorized',
                    status_detail = 'সক্রিয়'
            """, (account_name, phone, tg_id, fname, lname or "", username or ""))
        conn.close()
    except Exception as e:
        print(f"Note: Could not register in member_adder_accounts: {e}")


def format_phone_number(raw: str) -> str:
    """Format Bangladeshi or international phone numbers to E.164 format."""
    p = raw.strip().replace(" ", "").replace("-", "")
    if p.startswith("01"):
        return "+88" + p
    if p.startswith("1") and len(p) == 10:
        return "+880" + p
    if not p.startswith("+"):
        return "+" + p
    return p


async def main():
    print("\n" + "═" * 65)
    print("🔐 টেলিগ্রাম মেম্বার অটো-অ্যাডার একাউন্ট লগইন সিস্টেম")
    print("═" * 65)

    # 1. Determine account name
    if len(sys.argv) > 1:
        account_name = sys.argv[1].strip().lstrip("@")
    else:
        acc_input = input("👉 একাউন্টের একটি সহজ নাম দিন (ডিফল্ট: nikita967): ").strip().lstrip("@")
        account_name = acc_input if acc_input else "nikita967"

    # Sanitize account name for filename
    clean_name = re.sub(r"[^\w\-]", "_", account_name).lower()

    # Ensure sessions directory exists
    sessions_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")
    os.makedirs(sessions_dir, exist_ok=True)

    session_path = os.path.join(sessions_dir, clean_name)
    session_file = session_path + ".session"

    print(f"📁 সেশন ফাইল: sessions/{clean_name}.session")
    print(f"🆔 App API ID: {TG_API_ID}")
    print("═" * 65 + "\n")

    # Check if this account is already authorized
    if os.path.exists(session_file):
        print(f"🔍 পূর্বে সংরক্ষিত সেশন পাওয়া গেছে: {clean_name}")
        test_client = TelegramClient(session_path, TG_API_ID, TG_API_HASH)
        await test_client.connect()
        if await test_client.is_user_authorized():
            me = await test_client.get_me()
            print(f"✅ এই একাউন্টটি ইতিমধ্যে সফলভাবে লগইন অবস্থায় আছে:")
            print(f"   👤 নাম: {me.first_name} {me.last_name or ''}")
            print(f"   🆔 আইডি: {me.id}")
            print(f"   🔖 ইউজারনেম: @{me.username or 'নেই'}")
            await test_client.disconnect()

            relogin = input("\nআপনি কি এই একাউন্টটি পুনরায় লগইন করতে চান? (y/N): ").strip().lower()
            if relogin != "y":
                set_active_account(clean_name)
                register_account_in_db(clean_name, me.id, me.first_name, me.last_name or "", me.username or "")
                print(f"🎯 সক্রিয় একাউন্ট হিসেবে '{clean_name}' সেট করা হয়েছে।")
                print("\n👉 মেম্বার অ্যাড শুরু করতে নিচের কমান্ড দিন:")
                print(f"python auto_member_adder.py --account {clean_name}\n")
                return
            else:
                try:
                    os.remove(session_file)
                except Exception:
                    pass
        else:
            await test_client.disconnect()
            try:
                os.remove(session_file)
            except Exception:
                pass

    # Clean fresh client instance
    client = TelegramClient(session_path, TG_API_ID, TG_API_HASH)
    await client.connect()

    print(f"💡 @{account_name} আইডির সাথে যুক্ত টেলিগ্রাম ফোন নাম্বারটি লিখুন:")
    raw_phone = input("👉 ফোন নাম্বার দিন (e.g. 017xxxxxxxx বা +88017xxxxxxxx): ").strip()
    phone = format_phone_number(raw_phone)
    print(f"📞 টেলিগ্রামে কোড পাঠানো হচ্ছে: {phone}...")

    # Start login flow (Telethon will prompt for Telegram code & 2FA if enabled)
    await client.start(phone=phone)

    me = await client.get_me()
    print("\n" + "🎉" * 20)
    print("✅ লগইন সফল হয়েছে!")
    print(f"👤 নাম: {me.first_name} {me.last_name or ''}")
    print(f"🆔 টেলিগ্রাম আইডি: {me.id}")
    print(f"🔖 ইউজারনেম: @{me.username if me.username else 'নেই'}")
    print(f"📁 সেশন সংরক্ষিত হয়েছে: sessions/{clean_name}.session")
    print("🎉" * 20 + "\n")

    set_active_account(clean_name)
    register_account_in_db(clean_name, me.id, me.first_name, me.last_name or "", me.username or "", phone=phone)
    print(f"🎯 সক্রিয় একাউন্ট হিসেবে '{clean_name}' ডাটাবেজে সেট করা হয়েছে।")

    print("\n👉 মেম্বার অ্যাড স্ক্রিপ্ট চালু করতে নিচের কমান্ডটি রান করুন:")
    print(f"python auto_member_adder.py --account {clean_name}\n")
    print("👉 ব্যাকগ্রাউন্ডে চালাতে:")
    print(f"nohup python auto_member_adder.py --account {clean_name} --daemon > auto_adder.log 2>&1 &\n")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
