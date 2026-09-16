"""
Database module — async MySQL via aiomysql.
Tables: warns, chat_settings, notes, users
"""

import time
import json
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
                ("promo_sticker", "VARCHAR(255) DEFAULT ''"),
                ("force_add_enabled", "TINYINT DEFAULT 0"),
                ("force_add_count", "INT DEFAULT 5"),
                ("antilink_required_invites", "INT DEFAULT 10"),
                ("antiforward_required_invites", "INT DEFAULT 10")
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
                    first_name VARCHAR(200),
                    added_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS user_invites (
                    id         INT AUTO_INCREMENT PRIMARY KEY,
                    chat_id    BIGINT NOT NULL,
                    inviter_id BIGINT NOT NULL,
                    invited_id BIGINT NOT NULL,
                    timestamp  INT NOT NULL,
                    UNIQUE KEY uniq_invite (chat_id, inviter_id, invited_id),
                    INDEX idx_chat_inviter (chat_id, inviter_id)
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
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS banned_users (
                    id         INT AUTO_INCREMENT PRIMARY KEY,
                    chat_id    BIGINT NOT NULL,
                    user_id    BIGINT NOT NULL,
                    first_name VARCHAR(200),
                    username   VARCHAR(100),
                    reason     TEXT,
                    banned_by  BIGINT,
                    timestamp  INT NOT NULL,
                    UNIQUE KEY uniq_ban (chat_id, user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS user_name_history (
                    id          INT AUTO_INCREMENT PRIMARY KEY,
                    user_id     BIGINT NOT NULL,
                    first_name  VARCHAR(200),
                    username    VARCHAR(100),
                    recorded_at INT NOT NULL,
                    INDEX idx_user_id (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS global_settings (
                    setting_key VARCHAR(100) PRIMARY KEY,
                    setting_val TEXT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            await cur.execute("INSERT IGNORE INTO global_settings (setting_key, setting_val) VALUES ('site_gate_enabled', '1')")
            await cur.execute("INSERT IGNORE INTO global_settings (setting_key, setting_val) VALUES ('site_gate_required_invites', '10')")
            await cur.execute("INSERT IGNORE INTO global_settings (setting_key, setting_val) VALUES ('site_gate_custom_link', 'https://t.me/alltimefantasyzone')")
            await cur.execute("INSERT IGNORE INTO global_settings (setting_key, setting_val) VALUES ('service_alert_enabled', '1')")
            await cur.execute("INSERT INTO global_settings (setting_key, setting_val) VALUES ('service_alert_interval', '15') ON DUPLICATE KEY UPDATE setting_val=VALUES(setting_val)")
            default_girls_json = json.dumps([{"name": "জেরিন (Zerin)", "username": "zerin627", "link": "https://t.me/zerin627"}], ensure_ascii=False)
            await cur.execute("INSERT IGNORE INTO global_settings (setting_key, setting_val) VALUES ('service_girls_json', %s)", (default_girls_json,))
            await cur.execute("INSERT INTO global_settings (setting_key, setting_val) VALUES ('service_girl_name', 'জেরিন (Zerin)') ON DUPLICATE KEY UPDATE setting_val=VALUES(setting_val)")
            await cur.execute("INSERT INTO global_settings (setting_key, setting_val) VALUES ('service_girl_username', 'zerin627') ON DUPLICATE KEY UPDATE setting_val=VALUES(setting_val)")
            await cur.execute("INSERT INTO global_settings (setting_key, setting_val) VALUES ('service_girl_link', 'https://t.me/zerin627') ON DUPLICATE KEY UPDATE setting_val=VALUES(setting_val)")
            await cur.execute("INSERT INTO global_settings (setting_key, setting_val) VALUES ('service_admin_username', 'rafi0002') ON DUPLICATE KEY UPDATE setting_val=VALUES(setting_val)")
            await cur.execute("INSERT INTO global_settings (setting_key, setting_val) VALUES ('service_admin_link', 'https://t.me/rafi0002') ON DUPLICATE KEY UPDATE setting_val=VALUES(setting_val)")
            await cur.execute("INSERT INTO global_settings (setting_key, setting_val) VALUES ('service_alert_text', %s) ON DUPLICATE KEY UPDATE setting_val=VALUES(setting_val)", (DEFAULT_SERVICE_ALERT_TEXT,))
            await cur.execute(
                "UPDATE chat_settings SET rules_text=%s WHERE rules_text IS NULL",
                (DEFAULT_RULES,)
            )
            await cur.execute(
                "UPDATE chat_settings SET welcome_sticker=%s WHERE welcome_sticker IS NULL",
                (DEFAULT_WELCOME_STICKER,)
            )
            await cur.execute(
                "UPDATE chat_settings SET promo_sticker=%s WHERE promo_sticker IS NULL",
                (DEFAULT_PROMO_STICKER,)
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
    "force_add_enabled", "force_add_count",
    "antilink_required_invites", "antiforward_required_invites",
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


DEFAULT_WELCOME_STICKER = ""
DEFAULT_PROMO_STICKER   = ""

DEFAULT_SERVICE_ALERT_TEXT = (
    "🌸 <b>আমাদের গ্রুপের অফিসিয়াল ভেরিফায়েড সার্ভিস গার্ল</b> 🌸\n"
    "━━━━━━━━━━━━━━━━━━━━━━━\n"
    "⚠️ <b>সতর্কবার্তা:</b> আমাদের গ্রুপে আমাদের নিজস্ব সার্ভিস গার্ল আছে, দয়া করে প্রতারিত না হয়ে সরাসরি তাদের নক দিন।\n\n"
    "{service_girls_block}\n\n"
    "👑 <b>এডমিন আইডি:</b> <a href=\"{admin_link}\">@{admin_username}</a>\n"
    "📢 <i>কোনো মেয়ে গ্রুপের ভেরিফাইড হতে চাইলে এডমিনকে মেসেজ করুন। ধন্যবাদ।</i>\n\n"
    "👉 <b>অনলাইন সদস্যরা:</b> {mentions_text}\n"
    "━━━━━━━━━━━━━━━━━━━━━━━\n"
    "🔞 <b>আমাদের মূল গ্রুপে জয়েন থাকুন:</b>\n"
    "👉 <a href=\"{main_group_link}\">Dark Romance ১৮+ আড্ডা</a>"
)


async def get_chat_settings(chat_id: int) -> dict:
    """Return settings dict with safe defaults; never returns {}."""
    defaults = {
        "chat_id": chat_id,
        "welcome_enabled": 1, "welcome_text": "",
        "goodbye_enabled": 0, "goodbye_text": "",
        "antiflood_enabled": 0, "antilink_enabled": 0,
        "antilink_required_invites": 10,
        "badwords_enabled": 1, "badwords_list": "ছেলে,ও ছেলে,স্কেমার,বাটপার,প্রতারক,chele,o chele,sele,o sele,chala,scammer,skeimer,skemer,scamer,skeimar",
        "rules_text": DEFAULT_RULES, "lock_messages": 0,
        "lock_media": 0, "lock_stickers": 0,
        "max_warns": 3, "warn_action": "ban",
        "badword_strike_limit": 3, "badword_mute_duration": 60,
        "antiforward_enabled": 0, "antiforward_required_invites": 10,
        "lock_media_msg": 0,
        "welcome_button_text": "🔞 সরাসরি চ্যাট করুন (Live)", "welcome_button_url": "https://techandclick.site/bot/",
        "welcome_sticker": DEFAULT_WELCOME_STICKER, "promo_sticker": DEFAULT_PROMO_STICKER,
        "force_add_enabled": 0, "force_add_count": 5,
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


# ── USER tracking & Name Change History ────────────

async def check_and_track_user_name(user_id: int, chat_id: int, username: str, first_name: str) -> dict:
    """
    Checks if a user has changed their Name or Username compared to previously recorded history.
    Records any changes in user_name_history table.
    """
    pool = await get_pool()
    current_fn = (first_name or "").strip()
    current_un = (username or "").strip().lstrip("@")

    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # 1. Fetch the latest recorded name for this user from user_name_history
            await cur.execute(
                "SELECT first_name, username, recorded_at FROM user_name_history WHERE user_id=%s ORDER BY id DESC LIMIT 1",
                (user_id,)
            )
            latest_hist = await cur.fetchone()

            if not latest_hist:
                # Check users table if history table doesn't have it yet
                await cur.execute(
                    "SELECT first_name, username FROM users WHERE user_id=%s LIMIT 1",
                    (user_id,)
                )
                latest_hist = await cur.fetchone()

            has_changed = False
            prev_fn = ""
            prev_un = ""

            if latest_hist:
                prev_fn = (latest_hist.get("first_name") or "").strip()
                prev_un = (latest_hist.get("username") or "").strip().lstrip("@")

                # Compare names and usernames
                if prev_fn and current_fn and (prev_fn != current_fn or prev_un.lower() != current_un.lower()):
                    has_changed = True
                    # Insert the new name record into history
                    await cur.execute(
                        "INSERT INTO user_name_history (user_id, first_name, username, recorded_at) VALUES (%s, %s, %s, %s)",
                        (user_id, current_fn, current_un, int(time.time()))
                    )
            else:
                # First time seeing this user -> record initial entry
                await cur.execute(
                    "INSERT INTO user_name_history (user_id, first_name, username, recorded_at) VALUES (%s, %s, %s, %s)",
                    (user_id, current_fn, current_un, int(time.time()))
                )

            # Update users table
            await cur.execute(
                "INSERT INTO users (user_id, chat_id, username, first_name) VALUES (%s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE username=VALUES(username), first_name=VALUES(first_name)",
                (user_id, chat_id, current_un, current_fn)
            )

            # Fetch all past name history
            await cur.execute(
                "SELECT DISTINCT first_name, username, recorded_at FROM user_name_history WHERE user_id=%s ORDER BY id ASC",
                (user_id,)
            )
            all_history = await cur.fetchall() or []

            return {
                "has_changed": has_changed,
                "prev_first_name": prev_fn,
                "prev_username": prev_un,
                "current_first_name": current_fn,
                "current_username": current_un,
                "history": all_history
            }


async def get_user_name_history(user_id: int) -> list:
    """Returns all recorded name and username changes for a user."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT first_name, username, recorded_at FROM user_name_history WHERE user_id=%s ORDER BY id ASC",
                (user_id,)
            )
            return await cur.fetchall() or []


async def upsert_user(user_id: int, chat_id: int, username: str, first_name: str) -> None:
    await check_and_track_user_name(user_id, chat_id, username, first_name)


async def get_users_for_chat(chat_id: int) -> list:
    """Returns list of users recorded in the specified chat, combining all known database users."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT user_id, first_name, username FROM users WHERE chat_id=%s ORDER BY user_id DESC",
                (chat_id,)
            )
            chat_users = await cur.fetchall() or []

            # Also fetch all distinct active users in database
            await cur.execute(
                "SELECT DISTINCT user_id, first_name, username FROM users WHERE user_id > 0 ORDER BY user_id DESC"
            )
            all_users = await cur.fetchall() or []

            seen = set()
            combined = []
            for u in chat_users + all_users:
                uid = u["user_id"]
                if uid and uid not in seen:
                    seen.add(uid)
                    combined.append(u)
            return combined


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


async def add_banned_user(chat_id: int, user_id: int, first_name: str = "", username: str = "", reason: str = "", banned_by: int = 0) -> None:
    """Records a banned user in the database."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO banned_users (chat_id, user_id, first_name, username, reason, banned_by, timestamp) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "first_name=VALUES(first_name), username=VALUES(username), reason=VALUES(reason), banned_by=VALUES(banned_by), timestamp=VALUES(timestamp)",
                (chat_id, user_id, first_name or "", username or "", reason or "", banned_by or 0, int(time.time()))
            )


async def remove_banned_user(chat_id: int, user_id: int) -> None:
    """Removes a user from the banned list in the database."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM banned_users WHERE chat_id=%s AND user_id=%s", (chat_id, user_id))


async def get_banned_users(chat_id: int) -> list:
    """Returns all banned users for a specific group."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT user_id, first_name, username, reason, banned_by, timestamp FROM banned_users WHERE chat_id=%s ORDER BY timestamp DESC",
                (chat_id,)
            )
            return await cur.fetchall() or []


# ── INVITE / FORCE ADD Helpers ─────────────────────

async def add_invite(chat_id: int, inviter_id: int, invited_id: int) -> int:
    """Records an invite and returns the total invite count for the inviter."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "INSERT INTO user_invites (chat_id, inviter_id, invited_id, timestamp) "
                "VALUES (%s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE timestamp=VALUES(timestamp)",
                (chat_id, inviter_id, invited_id, int(time.time()))
            )
            await cur.execute(
                "SELECT COUNT(*) as cnt FROM user_invites WHERE chat_id=%s AND inviter_id=%s",
                (chat_id, inviter_id)
            )
            row = await cur.fetchone()
            if not row:
                return 0
            if isinstance(row, dict):
                return row.get("cnt", 0)
            return row[0] if len(row) > 0 else 0


async def get_user_invite_count(chat_id: int, user_id: int) -> int:
    """Returns total confirmed invites by a user in a group (fallback to overall confirmed invites if 0)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT COUNT(*) as cnt FROM user_invites WHERE chat_id=%s AND inviter_id=%s",
                (chat_id, user_id)
            )
            row = await cur.fetchone()
            cnt = 0
            if row:
                cnt = row.get("cnt", 0) if isinstance(row, dict) else (row[0] if len(row) > 0 else 0)
            
            if cnt == 0:
                await cur.execute(
                    "SELECT COUNT(*) as cnt FROM user_invites WHERE inviter_id=%s",
                    (user_id,)
                )
                row2 = await cur.fetchone()
                if row2:
                    cnt = row2.get("cnt", 0) if isinstance(row2, dict) else (row2[0] if len(row2) > 0 else 0)
            return cnt


async def get_top_inviters(chat_id: int, limit: int = 10) -> list:
    """Returns top inviters for leaderboard."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT ui.inviter_id, COUNT(*) as invite_count, u.first_name, u.username "
                "FROM user_invites ui "
                "LEFT JOIN users u ON (ui.chat_id=u.chat_id AND ui.inviter_id=u.user_id) "
                "WHERE ui.chat_id=%s "
                "GROUP BY ui.inviter_id, u.first_name, u.username "
                "ORDER BY invite_count DESC LIMIT %s",
                (chat_id, limit)
            )
            return await cur.fetchall() or []


async def get_global_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a global system setting value."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT setting_val FROM global_settings WHERE setting_key=%s LIMIT 1", (key,))
            row = await cur.fetchone()
            return row[0] if row else default


async def set_global_setting(key: str, val: str) -> None:
    """Set or update a global system setting value."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO global_settings (setting_key, setting_val) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE setting_val=VALUES(setting_val)",
                (key, str(val))
            )


async def get_all_global_settings() -> dict:
    """Get all global system settings with defaults."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT setting_key, setting_val FROM global_settings")
            rows = await cur.fetchall()
            res = {
                "site_gate_enabled": "1",
                "site_gate_required_invites": "10",
                "site_gate_custom_link": "https://t.me/alltimefantasyzone",
                "service_alert_enabled": "1",
                "service_alert_interval": "15",
                "service_girls_json": json.dumps([{"name": "জেরিন (Zerin)", "username": "zerin627", "link": "https://t.me/zerin627"}], ensure_ascii=False),
                "service_girl_name": "জেরিন (Zerin)",
                "service_girl_username": "zerin627",
                "service_girl_link": "https://t.me/zerin627",
                "service_admin_username": "rafi0002",
                "service_admin_link": "https://t.me/rafi0002",
                "service_alert_text": DEFAULT_SERVICE_ALERT_TEXT
            }
            if rows:
                for k, v in rows:
                    res[k] = v
            return res

