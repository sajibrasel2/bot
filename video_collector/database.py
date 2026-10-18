"""
Database module for Video Collector Bot — Async MySQL via aiomysql.
Tables: vc_channels, vc_queue, vc_settings, vc_stats, vc_processed
"""

import logging
import warnings
from typing import Optional, List, Dict, Any, Set
import aiomysql
from video_collector.config import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER,
    MYSQL_PASSWORD, MYSQL_DB
)

# Suppress harmless MySQL warning notices from aiomysql
warnings.filterwarnings("ignore", category=Warning, module="aiomysql")

logger = logging.getLogger(__name__)

_pool: Optional[aiomysql.Pool] = None


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
    """Initialize database tables for Video Collector (idempotent)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # 1. Registered Channels (Source and Delivery)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS vc_channels (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    channel_id BIGINT DEFAULT NULL,
                    channel_title VARCHAR(255) DEFAULT '',
                    channel_username VARCHAR(255) DEFAULT '',
                    channel_type VARCHAR(50) NOT NULL DEFAULT 'source',
                    last_scanned_id INT DEFAULT 0,
                    is_active TINYINT(1) DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_chan_type (channel_id, channel_type),
                    INDEX idx_user_type (channel_username, channel_type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # Safely drop old unique constraint on (channel_id, channel_type) if present
            try:
                await cur.execute("ALTER TABLE vc_channels DROP INDEX uq_chan_type")
            except Exception:
                pass

            try:
                await cur.execute("ALTER TABLE vc_channels MODIFY channel_id BIGINT DEFAULT NULL")
            except Exception:
                pass

            # Ensure channel_type supports VARCHAR(50) so 'delivery_linked_group' is never truncated
            try:
                await cur.execute("ALTER TABLE vc_channels MODIFY channel_type VARCHAR(50) NOT NULL DEFAULT 'source'")
            except Exception:
                pass

            # Ensure last_scanned_id column exists for backlog pagination
            try:
                await cur.execute("ALTER TABLE vc_channels ADD COLUMN last_scanned_id INT DEFAULT 0")
            except Exception:
                pass

            # 2. Video processing queue (Deleted immediately after successful delivery)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS vc_queue (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    source_chat_id BIGINT NOT NULL,
                    source_message_id INT NOT NULL,
                    file_id VARCHAR(255) NOT NULL,
                    caption TEXT,
                    status VARCHAR(50) DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_chat_msg (source_chat_id, source_message_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # 3. Settings table
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS vc_settings (
                    key_name VARCHAR(100) PRIMARY KEY,
                    value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # 4. Overall stats table
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS vc_stats (
                    stat_name VARCHAR(100) PRIMARY KEY,
                    stat_value BIGINT DEFAULT 0
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # 5. Processed messages history (to prevent duplicates even after queue record is deleted)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS vc_processed (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    source_chat_id BIGINT NOT NULL,
                    message_id INT NOT NULL,
                    media_id BIGINT DEFAULT NULL,
                    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_chat_msg (source_chat_id, message_id),
                    INDEX idx_proc_media (media_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # Ensure media_id column exists on existing vc_processed table
            try:
                await cur.execute("ALTER TABLE vc_processed ADD COLUMN media_id BIGINT DEFAULT NULL")
            except Exception:
                pass
            try:
                await cur.execute("ALTER TABLE vc_processed ADD INDEX idx_proc_media (media_id)")
            except Exception:
                pass

            # Ensure media_id column exists on existing vc_queue table
            try:
                await cur.execute("ALTER TABLE vc_queue ADD COLUMN media_id BIGINT DEFAULT NULL")
            except Exception:
                pass
            try:
                await cur.execute("ALTER TABLE vc_queue ADD INDEX idx_queue_media (media_id)")
            except Exception:
                pass

            # Clean up discussion groups / delivery chats accidentally marked as 'source'
            await cur.execute("""
                DELETE FROM vc_channels 
                WHERE channel_type = 'source' 
                  AND (channel_id IN (4446159364, -1004446159364, 4342232814, -1004342232814) 
                       OR LOWER(channel_title) LIKE '%dark romance%')
            """)

            # Clean up discussion groups accidentally marked as 'delivery'
            await cur.execute("""
                DELETE FROM vc_channels 
                WHERE channel_type = 'delivery' 
                  AND (channel_id IN (4446159364, -1004446159364) OR LOWER(channel_title) LIKE '%discussion%')
            """)

            # Purge any self-messages from vc_queue
            await cur.execute("""
                DELETE FROM vc_queue 
                WHERE source_chat_id IN (4446159364, -1004446159364, 4342232814, -1004342232814)
            """)

            # Insert default settings if not exists, and enforce 15-minute delivery interval
            await cur.execute("""
                INSERT INTO vc_settings (key_name, value)
                VALUES 
                ('delete_source_message', '0'),
                ('is_collector_active', '1'),
                ('collect_from_all_joined', '1'),
                ('custom_caption', ''),
                ('delivery_interval_minutes', '15'),
                ('trigger_immediate_send', '0')
                ON DUPLICATE KEY UPDATE value = IF(key_name = 'delivery_interval_minutes', '15', value)
            """)

            await cur.execute("""
                INSERT IGNORE INTO vc_stats (stat_name, stat_value)
                VALUES ('total_forwarded', 0)
            """)

            # Pre-seed default delivery channel @darkromance4u if not exists
            await cur.execute("""
                INSERT INTO vc_channels (channel_id, channel_title, channel_username, channel_type, is_active)
                SELECT NULL, 'Dark Romance 4U', 'darkromance4u', 'delivery', 1
                WHERE NOT EXISTS (
                    SELECT 1 FROM vc_channels WHERE channel_username = 'darkromance4u' AND channel_type = 'delivery'
                )
            """)

            # Pre-seed initial source channels requested by user
            initial_sources = [
                ("ayssorbonas420", "Ays Sorbonas"),
                ("pfff_boom", "Pfff Boom"),
                ("adult_desi30", "Adult Desi 30")
            ]
            for u, t in initial_sources:
                await cur.execute("""
                    INSERT INTO vc_channels (channel_id, channel_title, channel_username, channel_type, is_active)
                    SELECT NULL, %s, %s, 'source', 1
                    WHERE NOT EXISTS (
                        SELECT 1 FROM vc_channels WHERE channel_username = %s AND channel_type = 'source'
                    )
                """, (t, u, u))
    logger.info("✅ Video Collector database tables initialized successfully.")


# ── Channel Management ─────────────────────────────

async def get_source_channel_targets() -> Dict[str, Any]:
    """Return dict of IDs set, usernames set, and full records for active source channels."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, channel_id, channel_title, channel_username FROM vc_channels WHERE channel_type = 'source' AND is_active = 1")
            rows = await cur.fetchall()
            ids = set()
            usernames = set()
            for r in rows:
                if r.get("channel_id"):
                    cid = int(r["channel_id"])
                    ids.add(cid)
                    # Support variations of Telegram channel/supergroup ID prefixes
                    raw = abs(cid)
                    if str(raw).startswith("100"):
                        bare = int(str(raw)[3:])
                        ids.add(bare)
                        ids.add(-bare)
                        ids.add(-raw)
                if r.get("channel_username"):
                    usernames.add(r["channel_username"].lower().strip().lstrip("@"))
            return {"ids": ids, "usernames": usernames, "rows": rows}


async def get_delivery_channel_targets() -> List[Any]:
    """Return list of targets (integers or usernames) for active delivery channels only (excluding groups)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT channel_id, channel_username, channel_title FROM vc_channels WHERE channel_type = 'delivery' AND is_active = 1"
            )
            rows = await cur.fetchall()
            targets = []
            seen = set()
            for r in rows:
                title = (r.get("channel_title") or "").lower()
                # Strictly filter out discussion groups that might have been marked as delivery
                if "discussion" in title or (r.get("channel_id") and abs(int(r["channel_id"])) in (4446159364, 1004446159364)):
                    continue

                username = (r.get("channel_username") or "").strip().lstrip("@")
                cid = int(r["channel_id"]) if (r.get("channel_id") and int(r["channel_id"]) != 0) else None

                if username and username.lower() not in seen:
                    targets.append(username)
                    seen.add(username.lower())
                elif cid and cid not in seen:
                    targets.append(cid)
                    seen.add(cid)

            # Fallback default if none configured
            if not targets:
                targets.append("darkromance4u")
            return targets


async def record_excluded_delivery_group(group_id: int, title: str = "") -> None:
    """Record a linked discussion group so it is never crawled as a source, and never delivered to directly."""
    pool = await get_pool()
    cid = abs(group_id)
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO vc_channels (channel_id, channel_title, channel_username, channel_type, is_active)
                SELECT %s, %s, '', 'delivery_linked_group', 1
                WHERE NOT EXISTS (
                    SELECT 1 FROM vc_channels WHERE channel_id = %s AND channel_type = 'delivery_linked_group'
                )
            """, (cid, title or "Linked Discussion Group", cid))


async def get_channel_last_scanned_id(channel_id: int) -> int:
    """Get the oldest scanned message ID for backlog crawling."""
    pool = await get_pool()
    cid = abs(channel_id)
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT last_scanned_id FROM vc_channels WHERE channel_id IN (%s, %s, %s, %s) LIMIT 1",
                (channel_id, cid, -cid, -abs(channel_id))
            )
            row = await cur.fetchone()
            return int(row[0]) if (row and row[0]) else 0


async def update_channel_last_scanned_id(channel_id: int, last_id: int) -> None:
    """Update oldest scanned message ID for a channel to paginate deeper on next crawl."""
    pool = await get_pool()
    cid = abs(channel_id)
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE vc_channels SET last_scanned_id = %s WHERE channel_id IN (%s, %s, %s, %s)",
                (last_id, channel_id, cid, -cid, -abs(channel_id))
            )


async def update_channel_id_by_username(username: str, channel_id: int) -> None:
    """Update numeric channel_id for a username once resolved by Telethon."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE vc_channels SET channel_id = %s WHERE channel_username = %s AND (channel_id = 0 OR channel_id IS NULL)",
                (channel_id, username.lower().strip().lstrip("@"))
            )


async def get_all_channels() -> List[Dict[str, Any]]:
    """Return all channels formatted as dictionaries."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM vc_channels ORDER BY channel_type ASC, id DESC")
            return await cur.fetchall()


async def add_channel(channel_id: Optional[int], channel_title: str, channel_username: str, channel_type: str) -> bool:
    """Add a source or delivery channel with proper deduplication."""
    pool = await get_pool()
    clean_user = channel_username.lower().strip().lstrip("@") if channel_username else ""
    cid = channel_id if channel_id and channel_id != 0 else None

    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # Check existing
            existing_id = None
            if clean_user:
                await cur.execute(
                    "SELECT id FROM vc_channels WHERE channel_username = %s AND channel_type = %s",
                    (clean_user, channel_type)
                )
                r = await cur.fetchone()
                if r:
                    existing_id = r["id"]
            if not existing_id and cid is not None:
                await cur.execute(
                    "SELECT id FROM vc_channels WHERE channel_id = %s AND channel_type = %s",
                    (cid, channel_type)
                )
                r = await cur.fetchone()
                if r:
                    existing_id = r["id"]

            if existing_id:
                await cur.execute("""
                    UPDATE vc_channels
                    SET channel_id = COALESCE(%s, channel_id),
                        channel_title = %s,
                        channel_username = %s,
                        is_active = 1
                    WHERE id = %s
                """, (cid, channel_title, clean_user, existing_id))
            else:
                await cur.execute("""
                    INSERT INTO vc_channels (channel_id, channel_title, channel_username, channel_type, is_active)
                    VALUES (%s, %s, %s, %s, 1)
                """, (cid, channel_title, clean_user, channel_type))
            return True


async def delete_channel_by_id(pk_id: int) -> bool:
    """Delete channel by primary key."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM vc_channels WHERE id = %s", (pk_id,))
            return cur.rowcount > 0


async def is_channel_deactivated(channel_id: Optional[int], channel_username: str = "") -> bool:
    """Check if a channel was explicitly deactivated/disabled by admin."""
    pool = await get_pool()
    clean_user = channel_username.lower().strip().lstrip("@") if channel_username else ""
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            if clean_user:
                await cur.execute(
                    "SELECT 1 FROM vc_channels WHERE channel_username = %s AND is_active = 0",
                    (clean_user,)
                )
                if await cur.fetchone():
                    return True
            if channel_id:
                raw = abs(channel_id)
                await cur.execute(
                    "SELECT 1 FROM vc_channels WHERE (channel_id = %s OR channel_id = %s) AND is_active = 0",
                    (channel_id, -raw)
                )
                if await cur.fetchone():
                    return True
            return False


async def auto_register_source_channel(channel_id: Optional[int], channel_title: str, channel_username: str) -> None:
    """Auto-register newly discovered channel from user's account if not already in DB."""
    clean_user = channel_username.lower().strip().lstrip("@") if channel_username else ""
    cid = channel_id if channel_id and channel_id != 0 else None

    # Never auto-register delivery channels or discussion groups as source
    if cid and await is_delivery_chat(cid, clean_user, channel_title):
        return
    if clean_user and await is_delivery_chat(cid or 0, clean_user, channel_title):
        return
    if "dark romance" in (channel_title or "").lower():
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            if clean_user:
                await cur.execute("SELECT id FROM vc_channels WHERE channel_username = %s", (clean_user,))
                if await cur.fetchone():
                    return
            if cid:
                await cur.execute("SELECT id FROM vc_channels WHERE channel_id = %s", (cid,))
                if await cur.fetchone():
                    return

            title = channel_title or (f"@{clean_user}" if clean_user else f"Channel {cid}")
            await cur.execute("""
                INSERT INTO vc_channels (channel_id, channel_title, channel_username, channel_type, is_active)
                VALUES (%s, %s, %s, 'source', 1)
            """, (cid, title, clean_user))


async def is_delivery_chat(chat_id: int, chat_username: str = "", chat_title: str = "") -> bool:
    """Check if a chat is a designated delivery channel or its linked discussion group."""
    clean_user = (chat_username or "").lower().strip().lstrip("@")
    title_lower = (chat_title or "").lower()

    # Exclude delivery channel and its discussion groups by title/username
    if "dark romance" in title_lower or clean_user == "darkromance4u":
        return True

    # Known linked group ID for Dark Romance: -1004446159364 / 4446159364
    chat_raw = abs(chat_id)
    if chat_raw in (4446159364, 4342232814):
        return True

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT channel_id, channel_username FROM vc_channels WHERE channel_type IN ('delivery', 'delivery_linked_group')"
            )
            rows = await cur.fetchall()
            for r in rows:
                if r.get("channel_username") and r["channel_username"].lower().strip().lstrip("@") == clean_user and clean_user != "":
                    return True
                if r.get("channel_id"):
                    raw = abs(int(r["channel_id"]))
                    if raw == chat_raw:
                        return True
                    if str(raw).startswith("100") and int(str(raw)[3:]) == chat_raw:
                        return True
                    if str(chat_raw).startswith("100") and int(str(chat_raw)[3:]) == raw:
                        return True
    return False


async def purge_delivery_items_from_queue() -> None:
    """Purge any accidentally queued messages originating from delivery channel or its linked group."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                DELETE FROM vc_queue 
                WHERE source_chat_id IN (4446159364, -1004446159364, 4342232814, -1004342232814)
            """)
            await cur.execute("""
                DELETE FROM vc_channels 
                WHERE channel_type = 'source' 
                  AND (channel_id IN (4446159364, -1004446159364, 4342232814, -1004342232814) 
                       OR LOWER(channel_title) LIKE '%dark romance%')
            """)


# ── Queue & Deletion (Sequential FIFO) ─────────────

async def is_media_processed(media_id: Optional[int]) -> bool:
    """Check if a video with this Telegram media_id was already delivered."""
    if not media_id:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1 FROM vc_processed WHERE media_id = %s LIMIT 1", (media_id,))
            return bool(await cur.fetchone())


async def is_media_in_queue(media_id: Optional[int]) -> bool:
    """Check if a video with this Telegram media_id is already waiting in the queue."""
    if not media_id:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1 FROM vc_queue WHERE media_id = %s LIMIT 1", (media_id,))
            return bool(await cur.fetchone())


async def is_message_processed(source_chat_id: int, message_id: int, media_id: Optional[int] = None) -> bool:
    """Check if message or media_id was already processed/delivered."""
    if media_id and await is_media_processed(media_id):
        return True
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM vc_processed WHERE source_chat_id = %s AND message_id = %s",
                (source_chat_id, message_id)
            )
            return bool(await cur.fetchone())


async def mark_message_processed(source_chat_id: int, message_id: int, media_id: Optional[int] = None) -> None:
    """Record message as processed to prevent duplicate collection."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO vc_processed (source_chat_id, message_id, media_id)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE media_id = COALESCE(%s, media_id)
            """, (source_chat_id, message_id, media_id, media_id))


async def is_message_in_queue(source_chat_id: int, message_id: int, media_id: Optional[int] = None) -> bool:
    """Check if message is already waiting in queue."""
    if media_id and await is_media_in_queue(media_id):
        return True
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM vc_queue WHERE source_chat_id = %s AND source_message_id = %s",
                (source_chat_id, message_id)
            )
            return bool(await cur.fetchone())


async def add_queue_item(source_chat_id: int, source_message_id: int, file_id: str, caption: str, media_id: Optional[int] = None) -> Optional[int]:
    """Add video to queue before sending, avoiding duplicates by message and media_id."""
    if await is_message_processed(source_chat_id, source_message_id, media_id):
        return None
    if await is_message_in_queue(source_chat_id, source_message_id, media_id):
        return None

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO vc_queue (source_chat_id, source_message_id, file_id, caption, status, media_id)
                VALUES (%s, %s, %s, %s, 'pending', %s)
            """, (source_chat_id, source_message_id, file_id, caption or "", media_id))
            return cur.lastrowid


async def get_next_queue_item() -> Optional[Dict[str, Any]]:
    """Get the next sequential video from the queue (FIFO order)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM vc_queue ORDER BY id ASC LIMIT 1")
            return await cur.fetchone()


async def delete_queue_item(queue_id: int) -> None:
    """Immediately delete video record from database once forwarded."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM vc_queue WHERE id = %s", (queue_id,))


async def increment_forwarded_count() -> None:
    """Increment total forwarded counter."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                UPDATE vc_stats 
                SET stat_value = stat_value + 1 
                WHERE stat_name = 'total_forwarded'
            """)


async def get_queue_items(limit: int = 50) -> List[Dict[str, Any]]:
    """Get list of current queued videos for display in dashboard."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM vc_queue ORDER BY id ASC LIMIT %s", (limit,))
            return await cur.fetchall()


async def get_collector_stats() -> Dict[str, Any]:
    """Return dictionary of summary stats."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM vc_channels WHERE channel_type = 'source' AND is_active = 1")
            (sources,) = await cur.fetchone()

            await cur.execute("SELECT COUNT(*) FROM vc_channels WHERE channel_type = 'delivery' AND is_active = 1")
            (deliveries,) = await cur.fetchone()

            await cur.execute("SELECT stat_value FROM vc_stats WHERE stat_name = 'total_forwarded'")
            row = await cur.fetchone()
            total_forwarded = row[0] if row else 0

            await cur.execute("SELECT COUNT(*) FROM vc_queue")
            (queue_count,) = await cur.fetchone()

            return {
                "source_count": sources,
                "delivery_count": deliveries,
                "total_forwarded": total_forwarded,
                "queue_count": queue_count
            }


# ── Settings ───────────────────────────────────────

async def get_setting(key: str, default: str = "") -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT value FROM vc_settings WHERE key_name = %s", (key,))
            row = await cur.fetchone()
            return row[0] if row else default


async def set_setting(key: str, value: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO vc_settings (key_name, value)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE value = VALUES(value)
            """, (key, value))
