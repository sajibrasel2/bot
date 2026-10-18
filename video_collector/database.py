"""
Database module for Video Collector Bot — Async MySQL via aiomysql.
Tables: vc_channels, vc_queue, vc_settings, vc_stats
"""

import logging
from typing import Optional, List, Dict, Any, Set
import aiomysql
from video_collector.config import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER,
    MYSQL_PASSWORD, MYSQL_DB
)

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
                    channel_id BIGINT NOT NULL,
                    channel_title VARCHAR(255) DEFAULT '',
                    channel_username VARCHAR(255) DEFAULT '',
                    channel_type ENUM('source', 'delivery') NOT NULL,
                    is_active TINYINT(1) DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_chan_type (channel_id, channel_type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # 2. Video processing queue (Deleted immediately after successful delivery)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS vc_queue (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    source_chat_id BIGINT NOT NULL,
                    source_message_id INT NOT NULL,
                    file_id VARCHAR(255) NOT NULL,
                    caption TEXT,
                    status VARCHAR(50) DEFAULT 'processing',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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

            # Insert default settings if not exists
            await cur.execute("""
                INSERT IGNORE INTO vc_settings (key_name, value)
                VALUES 
                ('delete_source_message', '0'),
                ('is_collector_active', '1'),
                ('custom_caption', '')
            """)

            await cur.execute("""
                INSERT IGNORE INTO vc_stats (stat_name, stat_value)
                VALUES ('total_forwarded', 0)
            """)

            # Pre-seed default delivery channel darkromance4u if not exists
            await cur.execute("""
                INSERT INTO vc_channels (channel_id, channel_title, channel_username, channel_type, is_active)
                SELECT 0, 'Dark Romance 4U', 'darkromance4u', 'delivery', 1
                WHERE NOT EXISTS (
                    SELECT 1 FROM vc_channels WHERE channel_username = 'darkromance4u' AND channel_type = 'delivery'
                )
            """)
    logger.info("✅ Video Collector database tables initialized successfully.")


# ── Channel Management ─────────────────────────────

async def get_source_channel_ids() -> Set[int]:
    """Return set of all active source channel/group IDs."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT channel_id FROM vc_channels WHERE channel_type = 'source' AND is_active = 1")
            rows = await cur.fetchall()
            return {int(r[0]) for r in rows}


async def get_source_channel_targets() -> Dict[str, Any]:
    """Return dict of IDs set and usernames set for active source channels."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT channel_id, channel_username FROM vc_channels WHERE channel_type = 'source' AND is_active = 1")
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
            return {"ids": ids, "usernames": usernames}


async def get_delivery_channel_ids() -> List[int]:
    """Return list of all active delivery channel IDs."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT channel_id FROM vc_channels WHERE channel_type = 'delivery' AND is_active = 1")
            rows = await cur.fetchall()
            return [int(r[0]) for r in rows]


async def get_delivery_channel_targets() -> List[Any]:
    """Return list of targets (integers or usernames) for active delivery channels."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT channel_id, channel_username FROM vc_channels WHERE channel_type = 'delivery' AND is_active = 1")
            rows = await cur.fetchall()
            targets = []
            for r in rows:
                if r.get("channel_username") and r["channel_username"].strip():
                    targets.append(r["channel_username"].strip().lstrip("@"))
                elif r.get("channel_id") and int(r["channel_id"]) != 0:
                    targets.append(int(r["channel_id"]))
            # Fallback default if none configured
            if not targets:
                targets.append("darkromance4u")
            return targets


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


async def add_channel(channel_id: int, channel_title: str, channel_username: str, channel_type: str) -> bool:
    """Add a source or delivery channel."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO vc_channels (channel_id, channel_title, channel_username, channel_type, is_active)
                VALUES (%s, %s, %s, %s, 1)
                ON DUPLICATE KEY UPDATE 
                    channel_title = VALUES(channel_title),
                    channel_username = VALUES(channel_username),
                    is_active = 1
            """, (channel_id, channel_title, channel_username, channel_type))
            return True


async def delete_channel_by_id(pk_id: int) -> bool:
    """Delete channel by primary key."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM vc_channels WHERE id = %s", (pk_id,))
            return cur.rowcount > 0


# ── Queue & Deletion ───────────────────────────────

async def add_queue_item(source_chat_id: int, source_message_id: int, file_id: str, caption: str) -> int:
    """Add video to queue before sending."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO vc_queue (source_chat_id, source_message_id, file_id, caption, status)
                VALUES (%s, %s, %s, %s, 'processing')
            """, (source_chat_id, source_message_id, file_id, caption or ""))
            return cur.lastrowid


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
