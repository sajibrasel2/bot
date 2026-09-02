"""
Database module — async MySQL via aiomysql.
Tables: warns, chat_settings, notes, users
"""

import time
from typing import Optional
import aiomysql
from config import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER,
    MYSQL_PASSWORD, MYSQL_DB, WARN_EXPIRY_DAYS, OWNER_ID
)

# ── Connection pool ───────────────────────────────
_pool: Optional[aiomysql.Pool] = None   # Fix #25: use Optional, not X|Y (requires Python 3.10+)


async def get_pool() -> aiomysql.Pool:
    global _pool
    if _pool is None:
        _pool = await aiomysql.create_pool(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            db=MYSQL_DB,
            charset="utf8mb4",
            autocommit=True,
            minsize=1,
            maxsize=10,
        )
    return _pool


async def init_db() -> None:
    """Ensure all tables exist (idempotent)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS warns (
                    id        INT AUTO_INCREMENT PRIMARY KEY,
                    chat_id   BIGINT NOT NULL,
                    user_id   BIGINT NOT NULL,
                    reason    TEXT,
                    warned_by BIGINT,
                    timestamp INT NOT NULL,
                    INDEX idx_chat_user (chat_id, user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_settings (
                    chat_id           BIGINT PRIMARY KEY,
                    welcome_enabled   TINYINT DEFAULT 1,
                    welcome_text      TEXT,
                    goodbye_enabled   TINYINT DEFAULT 0,
                    goodbye_text      TEXT,
                    antiflood_enabled TINYINT DEFAULT 1,
                    antilink_enabled  TINYINT DEFAULT 0,
                    badwords_enabled  TINYINT DEFAULT 1,
                    badwords_list     TEXT,
                    rules_text        TEXT,
                    lock_messages     TINYINT DEFAULT 0,
                    lock_media        TINYINT DEFAULT 0,
                    lock_stickers     TINYINT DEFAULT 0,
                    max_warns         INT DEFAULT 3,
                    warn_action       VARCHAR(10) DEFAULT 'ban',
                    badword_strike_limit  INT DEFAULT 3,
                    badword_mute_duration INT DEFAULT 60,
                    antiforward_enabled   TINYINT DEFAULT 0,
                    lock_media_msg        TINYINT DEFAULT 0,
                    welcome_button_text   VARCHAR(100),
                    welcome_button_url    VARCHAR(500)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Ensure new columns exist in chat_settings (dynamic migration for existing tables)
            columns_to_add = [
                ("badword_strike_limit", "INT DEFAULT 3"),
                ("badword_mute_duration", "INT DEFAULT 60"),
                ("antiforward_enabled", "TINYINT DEFAULT 0"),
                ("lock_media_msg", "TINYINT DEFAULT 0"),
                ("welcome_button_text", "VARCHAR(100)"),
                ("welcome_button_url", "VARCHAR(500)"),
                ("chat_title", "VARCHAR(255) DEFAULT ''"),
                ("member_count", "INT DEFAULT 0"),
                ("welcome_sticker", "VARCHAR(255) DEFAULT ''"),
                ("promo_sticker", "VARCHAR(255) DEFAULT ''")
            ]
            for col_name, col_type in columns_to_add:
                await cur.execute(f"SHOW COLUMNS FROM chat_settings LIKE '{col_name}'")
                col_exists = await cur.fetchone()
                if not col_exists:
                    await cur.execute(f"ALTER TABLE chat_settings ADD COLUMN `{col_name}` {col_type}")
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id      INT AUTO_INCREMENT PRIMARY KEY,
                    chat_id BIGINT NOT NULL,
                    name    VARCHAR(100) NOT NULL,
                    content TEXT NOT NULL,
                    UNIQUE KEY uniq_note (chat_id, name)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id    BIGINT NOT NULL,
                    chat_id    BIGINT NOT NULL,
                    username   VARCHAR(100),
                    first_name VARCHAR(200),
                    PRIMARY KEY (user_id, chat_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS bot_admins (
                    user_id    BIGINT PRIMARY KEY,
                    username   VARCHAR(100),
                    first_name VARCHAR(200)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            await cur.execute(
                "INSERT INTO bot_admins (user_id, username, first_name) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE username=VALUES(username), first_name=VALUES(first_name)",
                (5888198325, "nikitaa92", "Nikita Jahan")
            )
            await cur.execute(
                "INSERT INTO bot_admins (user_id, username, first_name) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE username=VALUES(username), first_name=VALUES(first_name)",
                (8904339611, "sadia4392", "Sadia Jahan")
            )
            await cur.execute(
                "UPDATE chat_settings SET rules_text=%s WHERE rules_text IS NULL OR rules_text=''",
                (DEFAULT_RULES,)
            )


# ── WARN helpers ──────────────────────────────────

async def add_warn(chat_id: int, user_id: int, reason: str, warned_by: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO warns (chat_id,user_id,reason,warned_by,timestamp) VALUES (%s,%s,%s,%s,%s)",
                (chat_id, user_id, reason, warned_by, int(time.time()))
            )
            cutoff = (int(time.time()) - WARN_EXPIRY_DAYS * 86400) if WARN_EXPIRY_DAYS else 0
            await cur.execute(
                "SELECT COUNT(*) FROM warns WHERE chat_id=%s AND user_id=%s AND timestamp>=%s",
                (chat_id, user_id, cutoff)
            )
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_warns(chat_id: int, user_id: int) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            cutoff = (int(time.time()) - WARN_EXPIRY_DAYS * 86400) if WARN_EXPIRY_DAYS else 0
            await cur.execute(
                "SELECT reason, timestamp FROM warns "
                "WHERE chat_id=%s AND user_id=%s AND timestamp>=%s ORDER BY timestamp",
                (chat_id, user_id, cutoff)
            )
            return await cur.fetchall()


async def reset_warns(chat_id: int, user_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM warns WHERE chat_id=%s AND user_id=%s",
                (chat_id, user_id)
            )
            row = await cur.fetchone()
            count = row[0] if row else 0
            await cur.execute(
                "DELETE FROM warns WHERE chat_id=%s AND user_id=%s",
                (chat_id, user_id)
            )
            return count


async def remove_last_warn(chat_id: int, user_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM warns WHERE chat_id=%s AND user_id=%s ORDER BY timestamp DESC LIMIT 1",
                (chat_id, user_id)
            )
            row = await cur.fetchone()
            if not row:
                return False
            await cur.execute("DELETE FROM warns WHERE id=%s", (row[0],))
            return True


# ── CHAT SETTINGS helpers ─────────────────────────

# Whitelist of valid column names — prevents SQL injection via key param
_VALID_SETTINGS_KEYS = {
    "welcome_enabled", "welcome_text", "goodbye_enabled", "goodbye_text",
    "antiflood_enabled", "antilink_enabled", "badwords_enabled", "badwords_list",
    "rules_text", "lock_messages", "lock_media", "lock_stickers",
    "max_warns", "warn_action",
    "badword_strike_limit", "badword_mute_duration",
    "antiforward_enabled", "lock_media_msg",
    "welcome_button_text", "welcome_button_url",
    "welcome_sticker", "promo_sticker",
}


DEFAULT_RULES = (
    "📜 <b>গ্রুপের সাধারণ নিয়মাবলী (Group Rules)</b> 📜\n"
    "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "১. 👥 <b>সম্মান বজায় রাখুন:</b>\n"
    "   ▸ গ্রুপের সকল সদস্যের সাথে মার্জিত ও সম্মানজনক আচরণ করুন।\n"
    "   ▸ কাউকে অযথা আক্রমণ, গালিগালাজ বা হয়রানি করা সম্পূর্ণ নিষিদ্ধ।\n\n"
    "২. 🚫 <b>স্প্যামিং ও ফ্লাডিং নিষিদ্ধ:</b>\n"
    "   ▸ অপ্রয়োজনীয় মেসেজ বা অতিরিক্ত স্টিকার দিয়ে চ্যাট বক্স ভরিয়ে ফেলা যাবে না।\n\n"
    "৩. 🔗 <b>অনাকাঙ্ক্ষিত লিংক ও প্রচার নিষিদ্ধ:</b>\n"
    "   ▸ অ্যাডমিনের অনুমতি ব্যতীত কোনো বাহ্যিক লিংক বা অন্যান্য গ্রুপ/চ্যানেলের ইনভাইট লিংক শেয়ার করা যাবে না।\n\n"
    "৪. 🔞 <b>ভিআইপি লাইভ চ্যাট রুম:</b>\n"
    "   ▸ আমাদের ভিআইপি রুমে সরাসরি যুক্ত হতে গ্রুপে ৫ জন বন্ধুকে ইনভাইট (Add) করুন এবং ওয়েলকাম বাটনের লিংকে ক্লিক করুন।\n\n"
    "৫. 👮 <b>অ্যাডমিনদের সিদ্ধান্ত:</b>\n"
    "   ▸ গ্রুপের শৃঙ্খলা রক্ষার্থে অ্যাডমিনদের সিদ্ধান্তই চূড়ান্ত। নিয়ম ভঙ্গ করলে সতর্কবার্তা (Warn) অথবা সরাসরি ব্যান করা হতে পারে।\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━\n"
    "🌸 <i>নিয়ম মেনে চলুন, সুন্দর ও নিরাপদ আড্ডা উপভোগ করুন!</i> 🌸"
)


async def get_chat_settings(chat_id: int) -> dict:
    """Return settings dict with safe defaults; never returns {}."""
    defaults = {
        "chat_id": chat_id,
        "welcome_enabled": 1, "welcome_text": "",
        "goodbye_enabled": 0, "goodbye_text": "",
        "antiflood_enabled": 0, "antilink_enabled": 0,
        "badwords_enabled": 1, "badwords_list": "ছেলে,ও ছেলে,স্কেমার,বাটপার,প্রতারক,chele,o chele,sele,o sele,chala,scammer,skeimer,skemer,scamer,skeimar",
        "rules_text": DEFAULT_RULES, "lock_messages": 0,
        "lock_media": 0, "lock_stickers": 0,
        "max_warns": 3, "warn_action": "ban",
        "badword_strike_limit": 3, "badword_mute_duration": 60,
        "antiforward_enabled": 0, "lock_media_msg": 0,
        "welcome_button_text": "🔞 সরাসরি চ্যাট করুন (Live)", "welcome_button_url": "https://techandclick.site/bot/",
        "welcome_sticker": "", "promo_sticker": "",
    }
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM chat_settings WHERE chat_id=%s", (chat_id,)
            )
            row = await cur.fetchone()
            if row:
                return {**defaults, **{k: v for k, v in dict(row).items() if v is not None}}
            # Row missing — insert defaults then return them
            await cur.execute(
                "INSERT IGNORE INTO chat_settings (chat_id) VALUES (%s)", (chat_id,)
            )
            return defaults


async def update_chat_setting(chat_id: int, key: str, value) -> None:
    """Update a single setting. Key must be whitelisted."""
    if key not in _VALID_SETTINGS_KEYS:
        raise ValueError(f"Invalid settings key: {key}")
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT IGNORE INTO chat_settings (chat_id) VALUES (%s)", (chat_id,)
            )
            await cur.execute(
                f"UPDATE chat_settings SET `{key}`=%s WHERE chat_id=%s",
                (value, chat_id)
            )


# ── NOTES helpers ─────────────────────────────────

async def save_note(chat_id: int, name: str, content: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO notes (chat_id,name,content) VALUES (%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE content=VALUES(content)",
                (chat_id, name.lower(), content)
            )


async def get_note(chat_id: int, name: str) -> Optional[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT content FROM notes WHERE chat_id=%s AND name=%s",
                (chat_id, name.lower())
            )
            row = await cur.fetchone()
            return row[0] if row else None


async def delete_note(chat_id: int, name: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM notes WHERE chat_id=%s AND name=%s",
                (chat_id, name.lower())
            )
            row = await cur.fetchone()
            if not row:
                return False
            await cur.execute(
                "DELETE FROM notes WHERE chat_id=%s AND name=%s",
                (chat_id, name.lower())
            )
            return True


async def list_notes(chat_id: int) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT name FROM notes WHERE chat_id=%s ORDER BY name", (chat_id,)
            )
            rows = await cur.fetchall()
            return [r[0] for r in rows]


# ── USER tracking ─────────────────────────────────

async def upsert_user(user_id: int, chat_id: int, username: str, first_name: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO users (user_id,chat_id,username,first_name) VALUES (%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE username=VALUES(username), first_name=VALUES(first_name)",
                (user_id, chat_id, username, first_name)
            )


async def get_users_for_chat(chat_id: int) -> list:
    """Returns list of users recorded in the specified chat."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT user_id, first_name, username FROM users WHERE chat_id=%s ORDER BY user_id DESC",
                (chat_id,)
            )
            return await cur.fetchall() or []


async def is_bot_admin(user_id: int) -> bool:
    if user_id == OWNER_ID or user_id == 5888198325:
        return True
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1 FROM bot_admins WHERE user_id=%s", (user_id,))
            row = await cur.fetchone()
            return row is not None


async def get_all_chat_ids() -> list:
    """Returns a list of all unique chat IDs stored in chat_settings."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT chat_id FROM chat_settings")
            rows = await cur.fetchall()
            return [row[0] for row in rows]


async def update_chat_info(chat_id: int, title: str = "", member_count: int = 0) -> None:
    """Updates group title and member count in chat_settings."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO chat_settings (chat_id, chat_title, member_count) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "chat_title=IF(VALUES(chat_title)!='', VALUES(chat_title), chat_title), "
                "member_count=IF(VALUES(member_count)>0, VALUES(member_count), member_count)",
                (chat_id, title or "", member_count or 0)
            )
