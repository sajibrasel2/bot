"""
Safe Telegram Member Auto-Adder Script (Telethon Userbot)
Safely adds users from MySQL database (users table) to target Telegram group.
Supports multiple Telegram accounts (e.g. nikita967) with dedicated sessions.

Key Safety Features:
- Multi-Account Support: Easily switch or rotate between accounts (e.g. nikita967).
- Safe Daily Limit: Default 35 members per day per account (prevents bans).
- Human-like Random Delays: 60-110 seconds between successful adds.
- Smart Skip: Skips users with privacy restrictions, already in group, or deleted accounts.
- Emergency Brake: Immediately halts on PeerFloodError to protect user account.
- History Tracking: Records all attempts in member_add_history table with account attribution.
"""

import sys
import os
import shutil
import asyncio
import logging
import random
import argparse
import warnings
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

# Suppress harmless MySQL warning notices from aiomysql
warnings.filterwarnings("ignore", category=Warning, module="aiomysql")

# Ensure project root in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telethon import TelegramClient
from telethon.tl.functions.channels import InviteToChannelRequest, JoinChannelRequest
from telethon.errors import (
    UserPrivacyRestrictedError,
    UserAlreadyParticipantError,
    PeerFloodError,
    UserNotMutualContactError,
    UserIdInvalidError,
    UserChannelsTooMuchError,
    UserDeactivatedError,
    UserBannedInChannelError,
    FloodWaitError,
    ChatAdminRequiredError
)

import aiomysql
import pymysql
from config import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER,
    MYSQL_PASSWORD, MYSQL_DB
)
from video_collector.config import TG_API_ID, TG_API_HASH

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("member_adder")


# ── Session Resolution ──────────────────────────────────────────────
def resolve_session_path(account_name: Optional[str] = None) -> str:
    """Ensure dedicated userbot session path based on account name or active DB setting."""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    sessions_dir = os.path.join(project_dir, "sessions")
    os.makedirs(sessions_dir, exist_ok=True)

    target_acc = (account_name or "").strip().lstrip("@")

    # If account_name not passed via CLI, look up active_account in database
    if not target_acc:
        try:
            conn = pymysql.connect(
                host=MYSQL_HOST, port=MYSQL_PORT,
                user=MYSQL_USER, password=MYSQL_PASSWORD,
                database=MYSQL_DB, charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor
            )
            with conn.cursor() as cur:
                cur.execute("SELECT setting_val FROM member_adder_settings WHERE setting_key='active_account'")
                row = cur.fetchone()
                if row and row.get("setting_val"):
                    target_acc = row["setting_val"].strip().lstrip("@")
            conn.close()
        except Exception:
            pass

    if not target_acc:
        target_acc = "nikita967"

    session_path = os.path.join(sessions_dir, target_acc)
    return session_path


# ── Database Helpers ────────────────────────────────────────────────
_pool: Optional[aiomysql.Pool] = None

async def get_db_pool() -> aiomysql.Pool:
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
            maxsize=5,
        )
    return _pool


async def init_adder_tables() -> None:
    """Ensure member_add_history & settings tables exist."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS member_add_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(100),
                    first_name VARCHAR(200),
                    target_chat VARCHAR(100) NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    added_by_account VARCHAR(100) DEFAULT 'nikita967',
                    error_message TEXT,
                    attempted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uniq_target_user (target_chat, user_id),
                    INDEX idx_status (status),
                    INDEX idx_target (target_chat),
                    INDEX idx_account (added_by_account)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Ensure added_by_account column exists for existing tables
            try:
                await cur.execute("ALTER TABLE member_add_history ADD COLUMN added_by_account VARCHAR(100) DEFAULT 'nikita967'")
            except Exception:
                pass

            await cur.execute("""
                CREATE TABLE IF NOT EXISTS member_adder_settings (
                    setting_key VARCHAR(100) PRIMARY KEY,
                    setting_val TEXT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            # Default settings
            await cur.execute("INSERT IGNORE INTO member_adder_settings VALUES ('daily_limit', '35')")
            await cur.execute("INSERT IGNORE INTO member_adder_settings VALUES ('min_delay', '60')")
            await cur.execute("INSERT IGNORE INTO member_adder_settings VALUES ('max_delay', '110')")
            await cur.execute("INSERT IGNORE INTO member_adder_settings VALUES ('target_group', 'darkfantasyloverzone')")
            await cur.execute("INSERT IGNORE INTO member_adder_settings VALUES ('active_account', 'nikita967')")
    logger.info("✅ Member adder database tables ready.")


async def record_attempt(user_id: int, username: str, first_name: str, target: str, status: str, account: str = "nikita967", error: str = "") -> None:
    """Record member addition attempt in history."""
    pool = await get_db_pool()
    clean_user = (username or "").strip().lstrip("@")
    clean_target = (target or "").strip().lstrip("@")
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO member_add_history (user_id, username, first_name, target_chat, status, added_by_account, error_message, attempted_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE 
                    status = VALUES(status),
                    added_by_account = VALUES(added_by_account),
                    error_message = VALUES(error_message),
                    attempted_at = NOW()
            """, (user_id, clean_user, first_name or "", clean_target, status, account, error[:250]))


async def get_added_today_count(target: str, account: str = "") -> int:
    """Get number of members successfully added today by this account for target."""
    pool = await get_db_pool()
    clean_target = (target or "").strip().lstrip("@")
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            if account:
                await cur.execute("""
                    SELECT COUNT(*) FROM member_add_history 
                    WHERE target_chat = %s 
                      AND status = 'added' 
                      AND DATE(attempted_at) = CURDATE()
                      AND (added_by_account = %s OR added_by_account IS NULL)
                """, (clean_target, account))
            else:
                await cur.execute("""
                    SELECT COUNT(*) FROM member_add_history 
                    WHERE target_chat = %s 
                      AND status = 'added' 
                      AND DATE(attempted_at) = CURDATE()
                """, (clean_target,))
            row = await cur.fetchone()
            return int(row[0]) if row else 0


async def get_db_settings() -> Dict[str, Any]:
    """Fetch current adder settings from database table."""
    pool = await get_db_pool()
    settings = {
        "daily_limit": 35,
        "min_delay": 60,
        "max_delay": 110,
        "target_group": "darkfantasyloverzone",
        "active_account": "nikita967"
    }
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT setting_key, setting_val FROM member_adder_settings")
                rows = await cur.fetchall()
                for k, v in rows:
                    if k in ["daily_limit", "min_delay", "max_delay"]:
                        try:
                            settings[k] = int(v)
                        except Exception:
                            pass
                    elif k in ["target_group", "active_account"]:
                        settings[k] = (v or "").strip().lstrip("@")
    except Exception as e:
        logger.warning(f"Could not load settings from DB: {e}")
    return settings


async def update_account_status(account_name: str, status: str, detail: str = "", tg_id: Optional[int] = None, fname: str = "", username: str = "") -> None:
    """Update account operational status in member_adder_accounts table."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO member_adder_accounts (account_name, telegram_id, first_name, username, status, status_detail, last_used)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                        status = VALUES(status),
                        status_detail = VALUES(status_detail),
                        last_used = NOW(),
                        telegram_id = COALESCE(VALUES(telegram_id), telegram_id),
                        first_name = COALESCE(NULLIF(VALUES(first_name), ''), first_name),
                        username = COALESCE(NULLIF(VALUES(username), ''), username)
                """, (account_name, tg_id, fname or "", username or "", status, detail[:250]))
    except Exception as e:
        logger.debug(f"Could not update account status for {account_name}: {e}")


async def get_candidate_users(target: str, limit: int = 500) -> List[Dict[str, Any]]:
    """
    Fetch candidate users from database who have not yet been attempted for this target group.
    Prioritizes users with usernames first for maximum resolution success.
    """
    pool = await get_db_pool()
    clean_target = (target or "").strip().lstrip("@")
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT DISTINCT u.user_id, u.username, u.first_name
                FROM users u
                LEFT JOIN member_add_history h 
                  ON h.user_id = u.user_id AND h.target_chat = %s
                WHERE h.id IS NULL
                ORDER BY 
                  CASE WHEN u.username IS NOT NULL AND u.username != '' THEN 0 ELSE 1 END,
                  u.user_id DESC
                LIMIT %s
            """, (clean_target, limit))
            return await cur.fetchall()


# ── Member Adder Core Logic ──────────────────────────────────────────
async def run_member_adder(
    target_group: str,
    daily_limit: int = 35,
    min_delay: int = 60,
    max_delay: int = 110,
    account_name: Optional[str] = None
) -> Dict[str, Any]:
    """Execute safe member addition batch using specified Telegram account."""
    session_path = resolve_session_path(account_name)
    current_acc = os.path.basename(session_path)
    clean_target = target_group.strip().lstrip("@")

    stats = {
        "added": 0,
        "privacy_restricted": 0,
        "already_member": 0,
        "skipped": 0,
        "errors": 0,
        "stopped_reason": None,
        "account": current_acc
    }

    logger.info(f"🚀 Initializing Userbot Client with account: [{current_acc}] for target: @{clean_target}...")
    logger.info(f"📁 Session file: {session_path}.session")

    if not os.path.exists(session_path + ".session"):
        logger.error(f"❌ Session file not found: {session_path}.session")
        logger.error(f"👉 Please log in to this account first by running:")
        logger.error(f"   python login_adder.py {current_acc}\n")
        stats["stopped_reason"] = "session_not_found"
        return stats

    client = TelegramClient(session_path, TG_API_ID, TG_API_HASH)
    try:
        await client.connect()

        if not await client.is_user_authorized():
            logger.error(f"❌ Userbot session [{current_acc}] is not authorized!")
            logger.error(f"👉 Please log in by running: python login_adder.py {current_acc}")
            await update_account_status(current_acc, "unauthorized", "লগআউট হয়েছে")
            stats["stopped_reason"] = "unauthorized"
            return stats

        me = await client.get_me()
        logger.info(f"✅ Logged in successfully as: {me.first_name} (@{me.username or me.id}) [ID: {me.id}]")
        await update_account_status(current_acc, "authorized", "সক্রিয়", tg_id=me.id, fname=me.first_name, username=me.username or "")

        # Check today's progress for this specific account
        added_today = await get_added_today_count(clean_target, account=current_acc)
        logger.info(f"📊 Already added today by [{current_acc}] for @{clean_target}: {added_today}/{daily_limit}")
        if added_today >= daily_limit:
            logger.info(f"🎉 Today's limit of {daily_limit} members has already been reached for [{current_acc}]! Skipping.")
            await update_account_status(current_acc, "authorized", f"আজকের কোটা পূর্ণ ({added_today}/{daily_limit})")
            stats["stopped_reason"] = "daily_limit_already_reached"
            return stats

        remaining_quota = daily_limit - added_today

        # Resolve target group entity
        try:
            target_entity = await client.get_entity(clean_target)
            try:
                await client(JoinChannelRequest(target_entity))
            except Exception:
                pass
            logger.info(f"🎯 Target Group confirmed: {getattr(target_entity, 'title', clean_target)} [ID: {getattr(target_entity, 'id', None)}]")
        except Exception as e:
            logger.error(f"❌ Failed to resolve target group '@{clean_target}': {e}")
            await update_account_status(current_acc, "error", f"গ্রুপে সমস্যা: {str(e)[:50]}")
            stats["stopped_reason"] = f"target_group_error: {e}"
            return stats

        # Fetch candidate users
        candidates = await get_candidate_users(clean_target, limit=remaining_quota * 15)
        logger.info(f"🔍 Found {len(candidates)} unattempted candidate members in database.")

        if not candidates:
            logger.info("📭 No more candidate users left to add in database!")
            stats["stopped_reason"] = "no_candidates_left"
            return stats

        added_in_this_session = 0

        for user in candidates:
            if added_in_this_session >= remaining_quota:
                logger.info(f"🎉 Successfully reached today's target quota ({daily_limit} members) for [{current_acc}]! Session finished.")
                await update_account_status(current_acc, "authorized", f"আজকের কোটা সম্পন্ন ({added_today + added_in_this_session}/{daily_limit})")
                stats["stopped_reason"] = "quota_reached"
                break

            uid = user["user_id"]
            uname = (user.get("username") or "").strip().lstrip("@")
            fname = user.get("first_name") or "User"
            user_identifier = f"@{uname}" if uname else f"ID:{uid} ({fname})"

            # Resolve user input entity
            user_entity = None
            try:
                if uname:
                    user_entity = await client.get_entity(uname)
                else:
                    user_entity = await client.get_entity(uid)
            except ValueError:
                await record_attempt(uid, uname, fname, clean_target, "uncached_id", account=current_acc, error="Numeric ID not seen in dialog cache")
                stats["skipped"] += 1
                continue
            except Exception as e_res:
                await record_attempt(uid, uname, fname, clean_target, "resolve_failed", account=current_acc, error=str(e_res))
                stats["skipped"] += 1
                continue

            if not user_entity:
                stats["skipped"] += 1
                continue

            # Attempt to invite
            try:
                logger.info(f"➕ [{added_in_this_session + 1}/{remaining_quota}] Account [{current_acc}] inviting {user_identifier} to @{clean_target}...")
                await client(InviteToChannelRequest(target_entity, [user_entity]))

                # Success!
                added_in_this_session += 1
                stats["added"] += 1
                await record_attempt(uid, uname, fname, clean_target, "added", account=current_acc)
                logger.info(f"✅ Successfully added {user_identifier}! (Total today by [{current_acc}]: {added_today + added_in_this_session}/{daily_limit})")

                # Human-like delay after successful addition
                delay = random.randint(min_delay, max_delay)
                logger.info(f"⏳ Sleeping {delay} seconds before next add to maintain safety...")
                await asyncio.sleep(delay)

            except UserPrivacyRestrictedError:
                logger.warning(f"🔒 [Privacy] {user_identifier} has privacy settings preventing group invites. Skipping...")
                await record_attempt(uid, uname, fname, clean_target, "privacy_restricted", account=current_acc, error="UserPrivacyRestrictedError")
                stats["privacy_restricted"] += 1
                await asyncio.sleep(random.randint(5, 10))

            except UserNotMutualContactError:
                logger.warning(f"🔒 [Non-Contact] {user_identifier} only allows mutual contacts. Skipping...")
                await record_attempt(uid, uname, fname, clean_target, "privacy_restricted", account=current_acc, error="UserNotMutualContactError")
                stats["privacy_restricted"] += 1
                await asyncio.sleep(random.randint(5, 10))

            except UserAlreadyParticipantError:
                logger.info(f"ℹ️ [Already Member] {user_identifier} is already in @{clean_target}.")
                await record_attempt(uid, uname, fname, clean_target, "already_in_group", account=current_acc)
                stats["already_member"] += 1
                await asyncio.sleep(random.randint(3, 6))

            except UserChannelsTooMuchError:
                logger.warning(f"⚠️ [Full] {user_identifier} is already in maximum allowed groups/channels.")
                await record_attempt(uid, uname, fname, clean_target, "channels_full", account=current_acc, error="UserChannelsTooMuchError")
                stats["skipped"] += 1
                await asyncio.sleep(5)

            except UserBannedInChannelError:
                logger.warning(f"🚫 [Banned] {user_identifier} is banned in @{clean_target}.")
                await record_attempt(uid, uname, fname, clean_target, "banned_in_channel", account=current_acc, error="UserBannedInChannelError")
                stats["skipped"] += 1
                await asyncio.sleep(3)

            except UserDeactivatedError:
                logger.warning(f"❌ [Deleted] {user_identifier} account has been deleted.")
                await record_attempt(uid, uname, fname, clean_target, "account_deleted", account=current_acc, error="UserDeactivatedError")
                stats["skipped"] += 1
                await asyncio.sleep(3)

            except ChatAdminRequiredError:
                logger.error(f"❌ [Admin Required] Account [{current_acc}] needs Admin permissions with 'Add Members' right in @{clean_target}!")
                await update_account_status(current_acc, "admin_required", "টার্গেট গ্রুপে অ্যাডমিন পারমিশন নেই (Add Members)")
                stats["stopped_reason"] = "admin_required"
                break

            except PeerFloodError:
                logger.error(f"🛑 [CRITICAL PEER_FLOOD] Telegram has paused invites for [{current_acc}] today!")
                logger.error("🛑 Halting auto-adder immediately to protect this account from ban.")
                await record_attempt(uid, uname, fname, clean_target, "peer_flood", account=current_acc, error="Telegram PeerFloodError")
                await update_account_status(current_acc, "peer_flood", "আজকের জন্য টেলিগ্রাম সাময়িক বিরতি দিয়েছে (PeerFlood)")
                stats["stopped_reason"] = "peer_flood_protection"
                break

            except FloodWaitError as e_flood:
                logger.warning(f"⏳ [FloodWait] Telegram requested waiting {e_flood.seconds} seconds.")
                if e_flood.seconds > 300:
                    logger.warning("FloodWait > 5 minutes. Halting for today to maintain account health.")
                    stats["stopped_reason"] = f"flood_wait_{e_flood.seconds}s"
                    break
                else:
                    await asyncio.sleep(e_flood.seconds + 5)

            except Exception as e_unknown:
                logger.error(f"❌ Unexpected error inviting {user_identifier}: {e_unknown}")
                await record_attempt(uid, uname, fname, clean_target, "error", account=current_acc, error=str(e_unknown))
                stats["errors"] += 1
                await asyncio.sleep(8)

    finally:
        try:
            if client.is_connected():
                await client.disconnect()
        except Exception:
            pass

    logger.info("\n" + "═" * 60)
    logger.info(f"📋 AUTO-ADDER SESSION REPORT FOR [{current_acc}]:")
    logger.info(f"✅ Newly Added       : {stats['added']} members")
    logger.info(f"🔒 Privacy Blocked   : {stats['privacy_restricted']} members")
    logger.info(f"ℹ️ Already in Group  : {stats['already_member']} members")
    logger.info(f"⏭️ Skipped/Deleted   : {stats['skipped']} members")
    logger.info(f"⚠️ Errors            : {stats['errors']}")
    logger.info(f"🛑 Reason Stopped    : {stats['stopped_reason'] or 'Batch Completed'}")
    logger.info("═" * 60 + "\n")
    return stats


def get_available_accounts() -> List[str]:
    """List all account names found in sessions/ directory."""
    sessions_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")
    if not os.path.exists(sessions_dir):
        return []
    return [f[:-8] for f in os.listdir(sessions_dir) if f.endswith(".session")]


# ── Main Entrypoint ──────────────────────────────────────────────────
async def main_async():
    parser = argparse.ArgumentParser(description="Telegram Safe Member Auto-Adder (Multi-Account)")
    parser.add_argument("--account", default=None, help="Telegram account name (e.g. nikita967)")
    parser.add_argument("--all", action="store_true", help="Rotate across all logged-in accounts in sessions/ sequentially")
    parser.add_argument("--target", default="darkfantasyloverzone", help="Target group username (without @)")
    parser.add_argument("--limit", type=int, default=35, help="Daily safe member addition limit per account (default: 35)")
    parser.add_argument("--min-delay", type=int, default=60, help="Minimum delay between adds in seconds (default: 60)")
    parser.add_argument("--max-delay", type=int, default=110, help="Maximum delay between adds in seconds (default: 110)")
    parser.add_argument("--daemon", action="store_true", help="Run in continuous background loop (repeats every 24 hours)")
    args = parser.parse_args()

    await init_adder_tables()

    try:
        while True:
            # Dynamically read latest settings configured from Admin Panel
            db_cfg = await get_db_settings()
            current_target = db_cfg.get("target_group", "darkfantasyloverzone") if args.target == "darkfantasyloverzone" else args.target
            current_limit = db_cfg.get("daily_limit", 35) if args.limit == 35 else args.limit
            current_min_delay = db_cfg.get("min_delay", 60) if args.min_delay == 60 else args.min_delay
            current_max_delay = db_cfg.get("max_delay", 110) if args.max_delay == 110 else args.max_delay

            if args.all:
                accounts = get_available_accounts()
                if not accounts:
                    logger.error("❌ No accounts found in sessions/! Please add an account from Admin Panel.")
                    break
                logger.info(f"🔄 Multi-Account Rotation: Found {len(accounts)} accounts ({', '.join(accounts)}).")
                logger.info(f"🎯 Target Group: @{current_target} | 🛡️ Daily Limit per Account: {current_limit} members | ⏱️ Delay: {current_min_delay}-{current_max_delay}s")
                total_added_all = 0
                for acc in accounts:
                    logger.info(f"\n▶️ Starting batch for account: [{acc}] (Daily Target: {current_limit} members)...")
                    stats = await run_member_adder(
                        target_group=current_target,
                        daily_limit=current_limit,
                        min_delay=current_min_delay,
                        max_delay=current_max_delay,
                        account_name=acc
                    )
                    total_added_all += stats.get("added", 0)
                    await asyncio.sleep(5)
                logger.info(f"\n🎉 All {len(accounts)} accounts completed today's batches! Total added: {total_added_all} members.")
            else:
                chosen_account = args.account or db_cfg.get("active_account", "nikita967")
                stats = await run_member_adder(
                    target_group=current_target,
                    daily_limit=current_limit,
                    min_delay=current_min_delay,
                    max_delay=current_max_delay,
                    account_name=chosen_account
                )

            if not args.daemon:
                break

            # Smart Date-Aware Sleep: Sleep in intervals, wake at midnight for new day's quota
            now = datetime.now()
            tomorrow = datetime(now.year, now.month, now.day) + timedelta(days=1, minutes=2)
            seconds_until_midnight = max(60, int((tomorrow - now).total_seconds()))

            # Sleep at most 45 minutes per check interval, or until midnight if closer
            sleep_interval = min(seconds_until_midnight, 2700)
            logger.info(f"🛌 All accounts processed. Resting {sleep_interval // 60} minutes before next check (resets at midnight)...")
            await asyncio.sleep(sleep_interval)
    finally:
        global _pool
        if _pool:
            _pool.close()
            await _pool.wait_closed()


if __name__ == "__main__":
    asyncio.run(main_async())
