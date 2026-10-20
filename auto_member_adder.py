"""
Safe Telegram Member Auto-Adder Script (Telethon Userbot)
Safely adds users from MySQL database (users table) to target Telegram group.

Key Safety Features:
- Safe Daily Limit: Default 35 members per day (prevents Telegram account bans).
- Human-like Random Delays: 60-110 seconds between successful adds.
- Smart Skip: Skips users with privacy restrictions, already in group, or deleted accounts.
- Emergency Brake: Immediately halts on PeerFloodError to protect user account.
- History Tracking: Records all attempts in member_add_history table.
- Independent Session: Clones collector_userbot session to prevent SQLite locks with video_collector.
"""

import sys
import os
import shutil
import asyncio
import logging
import random
import argparse
from datetime import datetime
from typing import Optional, Dict, Any, List

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
def resolve_session_path() -> str:
    """Ensure dedicated userbot session for adder to avoid SQLite locks."""
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "video_collector")
    adder_session = os.path.join(base_dir, "adder_userbot")
    collector_session = os.path.join(base_dir, "collector_userbot")

    # If adder session does not exist but collector session exists, clone it
    if not os.path.exists(adder_session + ".session") and os.path.exists(collector_session + ".session"):
        try:
            shutil.copy2(collector_session + ".session", adder_session + ".session")
            logger.info("📋 Created independent adder_userbot.session from collector session.")
        except Exception as e:
            logger.warning(f"Could not clone session, using collector_userbot: {e}")
            return collector_session

    return adder_session if os.path.exists(adder_session + ".session") else collector_session


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
    """Ensure member_add_history table exists."""
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
                    error_message TEXT,
                    attempted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uniq_target_user (target_chat, user_id),
                    INDEX idx_status (status),
                    INDEX idx_target (target_chat)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
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
    logger.info("✅ Member adder database tables ready.")


async def record_attempt(user_id: int, username: str, first_name: str, target: str, status: str, error: str = "") -> None:
    """Record member addition attempt in history."""
    pool = await get_db_pool()
    clean_user = (username or "").strip().lstrip("@")
    clean_target = (target or "").strip().lstrip("@")
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO member_add_history (user_id, username, first_name, target_chat, status, error_message, attempted_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE 
                    status = VALUES(status),
                    error_message = VALUES(error_message),
                    attempted_at = NOW()
            """, (user_id, clean_user, first_name or "", clean_target, status, error[:250]))


async def get_added_today_count(target: str) -> int:
    """Get number of members successfully added today."""
    pool = await get_db_pool()
    clean_target = (target or "").strip().lstrip("@")
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT COUNT(*) FROM member_add_history 
                WHERE target_chat = %s 
                  AND status = 'added' 
                  AND DATE(attempted_at) = CURDATE()
            """, (clean_target,))
            row = await cur.fetchone()
            return int(row[0]) if row else 0


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
async def run_member_adder(target_group: str, daily_limit: int = 35, min_delay: int = 60, max_delay: int = 110) -> Dict[str, Any]:
    """Execute safe member addition batch."""
    session_path = resolve_session_path()
    client = TelegramClient(session_path, TG_API_ID, TG_API_HASH)
    clean_target = target_group.strip().lstrip("@")

    stats = {
        "added": 0,
        "privacy_restricted": 0,
        "already_member": 0,
        "skipped": 0,
        "errors": 0,
        "stopped_reason": None
    }

    logger.info(f"🚀 Initializing Userbot Client for target: @{clean_target}...")
    await client.connect()

    if not await client.is_user_authorized():
        logger.error("❌ Userbot session is not authorized! Please run 'python video_collector/login.py' first.")
        await client.disconnect()
        stats["stopped_reason"] = "unauthorized"
        return stats

    me = await client.get_me()
    logger.info(f"✅ Logged in as: {me.first_name} (@{me.username or me.id})")

    # Check today's progress
    added_today = await get_added_today_count(clean_target)
    logger.info(f"📊 Already added today for @{clean_target}: {added_today}/{daily_limit}")
    if added_today >= daily_limit:
        logger.info(f"🎉 Today's limit of {daily_limit} members has already been reached! Stopping.")
        await client.disconnect()
        stats["stopped_reason"] = "daily_limit_already_reached"
        return stats

    remaining_quota = daily_limit - added_today

    # Resolve target group entity
    try:
        target_entity = await client.get_entity(clean_target)
        # Attempt to auto-join if not joined
        try:
            await client(JoinChannelRequest(target_entity))
        except Exception:
            pass
        logger.info(f"🎯 Target Group confirmed: {getattr(target_entity, 'title', clean_target)} [ID: {getattr(target_entity, 'id', None)}]")
    except Exception as e:
        logger.error(f"❌ Failed to resolve target group '@{clean_target}': {e}")
        await client.disconnect()
        stats["stopped_reason"] = f"target_group_error: {e}"
        return stats

    # Fetch candidate users
    candidates = await get_candidate_users(clean_target, limit=remaining_quota * 15)
    logger.info(f"🔍 Found {len(candidates)} unattempted candidate members in database.")

    if not candidates:
        logger.info("📭 No more candidate users left to add in database!")
        await client.disconnect()
        stats["stopped_reason"] = "no_candidates_left"
        return stats

    added_in_this_session = 0

    for user in candidates:
        if added_in_this_session >= remaining_quota:
            logger.info(f"🎉 Successfully reached today's target quota ({daily_limit} members)! Session finished.")
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
            # Cannot resolve uncached numeric ID
            await record_attempt(uid, uname, fname, clean_target, "uncached_id", "Numeric ID not seen in dialog cache")
            stats["skipped"] += 1
            continue
        except Exception as e_res:
            await record_attempt(uid, uname, fname, clean_target, "resolve_failed", str(e_res))
            stats["skipped"] += 1
            continue

        if not user_entity:
            stats["skipped"] += 1
            continue

        # Attempt to invite
        try:
            logger.info(f"➕ [{added_in_this_session + 1}/{remaining_quota}] Inviting {user_identifier} to @{clean_target}...")
            await client(InviteToChannelRequest(target_entity, [user_entity]))

            # Success!
            added_in_this_session += 1
            stats["added"] += 1
            await record_attempt(uid, uname, fname, clean_target, "added")
            logger.info(f"✅ Successfully added {user_identifier}! (Total today: {added_today + added_in_this_session}/{daily_limit})")

            # Human-like delay after successful addition
            delay = random.randint(min_delay, max_delay)
            logger.info(f"⏳ Sleeping {delay} seconds before next add to maintain safety...")
            await asyncio.sleep(delay)

        except UserPrivacyRestrictedError:
            logger.warning(f"🔒 [Privacy] {user_identifier} has privacy settings preventing group invites. Skipping...")
            await record_attempt(uid, uname, fname, clean_target, "privacy_restricted", "UserPrivacyRestrictedError")
            stats["privacy_restricted"] += 1
            await asyncio.sleep(random.randint(5, 10))

        except UserNotMutualContactError:
            logger.warning(f"🔒 [Non-Contact] {user_identifier} only allows mutual contacts. Skipping...")
            await record_attempt(uid, uname, fname, clean_target, "privacy_restricted", "UserNotMutualContactError")
            stats["privacy_restricted"] += 1
            await asyncio.sleep(random.randint(5, 10))

        except UserAlreadyParticipantError:
            logger.info(f"ℹ️ [Already Member] {user_identifier} is already in @{clean_target}.")
            await record_attempt(uid, uname, fname, clean_target, "already_in_group")
            stats["already_member"] += 1
            await asyncio.sleep(random.randint(3, 6))

        except UserChannelsTooMuchError:
            logger.warning(f"⚠️ [Full] {user_identifier} is already in maximum allowed groups/channels.")
            await record_attempt(uid, uname, fname, clean_target, "channels_full", "UserChannelsTooMuchError")
            stats["skipped"] += 1
            await asyncio.sleep(5)

        except UserBannedInChannelError:
            logger.warning(f"🚫 [Banned] {user_identifier} is banned in @{clean_target}.")
            await record_attempt(uid, uname, fname, clean_target, "banned_in_channel", "UserBannedInChannelError")
            stats["skipped"] += 1
            await asyncio.sleep(3)

        except UserDeactivatedError:
            logger.warning(f"❌ [Deleted] {user_identifier} account has been deleted.")
            await record_attempt(uid, uname, fname, clean_target, "account_deleted", "UserDeactivatedError")
            stats["skipped"] += 1
            await asyncio.sleep(3)

        except ChatAdminRequiredError:
            logger.error(f"❌ [Admin Required] Your account needs Admin permissions with 'Add Members' right in @{clean_target}!")
            stats["stopped_reason"] = "admin_required"
            break

        except PeerFloodError:
            # CRITICAL EMERGENCY BRAKE: Telegram flagged too many invites
            logger.error("🛑 [CRITICAL PEER_FLOOD] Telegram has paused invites for this account today!")
            logger.error("🛑 Halting auto-adder immediately to protect your account from ban.")
            await record_attempt(uid, uname, fname, clean_target, "peer_flood", "Telegram PeerFloodError")
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
            await record_attempt(uid, uname, fname, clean_target, "error", str(e_unknown))
            stats["errors"] += 1
            await asyncio.sleep(8)

    await client.disconnect()
    logger.info("\n" + "═" * 60)
    logger.info("📋 AUTO-ADDER SESSION REPORT:")
    logger.info(f"✅ Newly Added       : {stats['added']} members")
    logger.info(f"🔒 Privacy Blocked   : {stats['privacy_restricted']} members")
    logger.info(f"ℹ️ Already in Group  : {stats['already_member']} members")
    logger.info(f"⏭️ Skipped/Deleted   : {stats['skipped']} members")
    logger.info(f"⚠️ Errors            : {stats['errors']}")
    logger.info(f"🛑 Reason Stopped    : {stats['stopped_reason'] or 'Batch Completed'}")
    logger.info("═" * 60 + "\n")
    return stats


# ── Main Entrypoint ──────────────────────────────────────────────────
async def main_async():
    parser = argparse.ArgumentParser(description="Telegram Safe Member Auto-Adder")
    parser.add_argument("--target", default="darkfantasyloverzone", help="Target group username (without @)")
    parser.add_argument("--limit", type=int, default=35, help="Daily safe member addition limit (default: 35)")
    parser.add_argument("--min-delay", type=int, default=60, help="Minimum delay between adds in seconds (default: 60)")
    parser.add_argument("--max-delay", type=int, default=110, help="Maximum delay between adds in seconds (default: 110)")
    parser.add_argument("--daemon", action="store_true", help="Run in continuous background loop (repeats every 24 hours)")
    args = parser.parse_args()

    await init_adder_tables()

    while True:
        stats = await run_member_adder(
            target_group=args.target,
            daily_limit=args.limit,
            min_delay=args.min_delay,
            max_delay=args.max_delay
        )

        if not args.daemon:
            break

        logger.info("🛌 Daemon mode active: Sleeping 24 hours until tomorrow's safe add batch...")
        await asyncio.sleep(86400)


if __name__ == "__main__":
    asyncio.run(main_async())
