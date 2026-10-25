"""
Web Admin Panel — Flask
Run : python web/app.py
URL : http://localhost:5000
Login: admin / (PANEL_PASSWORD from .env)
"""

import sys
import os
import re
import json
import subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime as dt
import pymysql
import pymysql.cursors
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, flash, make_response
)
from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB

app = Flask(__name__)
# Fix #38: secret key from env, fallback to random bytes
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(24)

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, post-check=0, pre-check=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Fix #15: credentials from .env
ADMIN_USERNAME = os.environ.get("PANEL_USER", "admin")
ADMIN_PASSWORD = os.environ.get("PANEL_PASSWORD", "nikita2024")

# Whitelist of safe column names for update (Fix #4)
_SAFE_KEYS = {
    "welcome_enabled", "welcome_text", "goodbye_enabled", "goodbye_text",
    "antiflood_enabled", "antilink_enabled", "badwords_enabled", "badwords_list",
    "rules_text", "lock_messages", "lock_media", "lock_stickers",
    "max_warns", "warn_action",
    "badword_strike_limit", "badword_mute_duration",
    "antiforward_enabled", "lock_media_msg",
    "welcome_button_text", "welcome_button_url",
    "chat_title", "member_count",
    "welcome_sticker", "promo_sticker",
    "force_add_enabled", "force_add_count",
    "antilink_required_invites", "antiforward_required_invites",
    "antibiolink_enabled", "antibiolink_whitelist",
}

# ── Jinja2 filters ────────────────────────────────

@app.template_filter("datetime")
def fmt_datetime(ts):
    try:
        return dt.datetime.fromtimestamp(int(ts)).strftime("%d %b %Y, %H:%M")
    except Exception:
        return str(ts)


# ── Auth ──────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# Fix: Flask <int:> doesn't accept negative numbers (Telegram group IDs are negative).
# Convert chat_id string to int in every route automatically.
def with_int_chat_id(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "chat_id" in kwargs:
            try:
                kwargs["chat_id"] = int(kwargs["chat_id"])
            except (ValueError, TypeError):
                return "Invalid chat_id", 400
        return f(*args, **kwargs)
    return decorated


# ── DB helpers ────────────────────────────────────

def get_db():
    return pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASSWORD,
        database=MYSQL_DB, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def _query(sql: str, args=(), fetchone=False, fetchall=False):
    """Execute a query with automatic connection close."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            if fetchone:
                return cur.fetchone()
            if fetchall:
                return cur.fetchall()
    finally:
        conn.close()


def _execute(sql: str, args=()):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
    finally:
        conn.close()


def ensure_db_schema():
    """Ensure all required columns and tables exist in MySQL."""
    try:
        conn = get_db()
        try:
            with conn.cursor() as cur:
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
                    ("antiforward_required_invites", "INT DEFAULT 10"),
                    ("antibiolink_enabled", "TINYINT DEFAULT 1"),
                    ("antibiolink_whitelist", "TEXT")
                ]
                for col_name, col_type in columns_to_add:
                    cur.execute(f"SHOW COLUMNS FROM chat_settings LIKE '{col_name}'")
                    if not cur.fetchone():
                        cur.execute(f"ALTER TABLE chat_settings ADD COLUMN `{col_name}` {col_type}")
                
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_invites (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        chat_id BIGINT NOT NULL,
                        inviter_id BIGINT NOT NULL,
                        joined_user_id BIGINT NOT NULL,
                        timestamp BIGINT NOT NULL,
                        UNIQUE KEY uniq_invite (chat_id, joined_user_id),
                        INDEX idx_inviter (chat_id, inviter_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)

                # Portal schema
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS portal_categories (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        slug VARCHAR(100) NOT NULL UNIQUE,
                        icon VARCHAR(50) DEFAULT 'fa-fire',
                        order_num INT DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS portal_videos (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        title VARCHAR(255) NOT NULL,
                        category_slug VARCHAR(100) NOT NULL,
                        video_url VARCHAR(500) NOT NULL,
                        thumb_url VARCHAR(500) DEFAULT '',
                        duration VARCHAR(50) DEFAULT '04:15',
                        views INT DEFAULT 1200,
                        is_active TINYINT(1) DEFAULT 1,
                        order_num INT DEFAULT 0,
                        keywords TEXT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_cat (category_slug),
                        INDEX idx_active (is_active)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                try:
                    cur.execute("ALTER TABLE portal_videos ADD COLUMN keywords TEXT NULL")
                except Exception:
                    pass
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS portal_settings (
                        setting_key VARCHAR(100) PRIMARY KEY,
                        setting_val TEXT
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)

                # Seed portal default categories if empty
                cur.execute("SELECT COUNT(*) AS cnt FROM portal_categories")
                c_row = cur.fetchone()
                if c_row and (c_row.get("cnt") or 0) == 0:
                    cur.executemany(
                        "INSERT IGNORE INTO portal_categories (name, slug, icon, order_num) VALUES (%s, %s, %s, %s)",
                        [
                            ("ভাইরাল ভাইরাল", "viral", "fa-fire", 1),
                            ("দেশি হট", "desi", "fa-heart", 2),
                            ("এক্সক্লুসিভ", "exclusive", "fa-crown", 3),
                            ("ভিআইপি লিকস", "vip", "fa-gem", 4),
                            ("লাইভ ক্যাম", "live", "fa-bolt", 5)
                        ]
                    )

                # Seed portal default settings if empty
                cur.execute("SELECT COUNT(*) AS cnt FROM portal_settings")
                s_row = cur.fetchone()
                if s_row and (s_row.get("cnt") or 0) == 0:
                    cur.executemany(
                        "INSERT IGNORE INTO portal_settings (setting_key, setting_val) VALUES (%s, %s)",
                        [
                            ("portal_title", "EXCLUSIVE DESI & VIRAL VAULT"),
                            ("portal_blur", "15"),
                            ("telegram_group_url", "https://t.me/darkfantasyloverzone"),
                            ("popunder_enabled", "1"),
                            ("popunder_url", "https://t.me/darkfantasyloverzone"),
                            ("popunder_script", ""),
                            ("social_ad_enabled", "1"),
                            ("social_ad_script", "")
                        ]
                    )
        finally:
            conn.close()
    except Exception as e:
        print(f"Warning: DB schema migration check: {e}")

try:
    ensure_db_schema()
except Exception:
    pass


def get_all_chats():
    try:
        rows = _query("SELECT * FROM chat_settings ORDER BY chat_id", fetchall=True)
    except Exception:
        rows = []
    chats = []
    for idx, r in enumerate(rows or [], 1):
        cid = r.get("chat_id")
        title = r.get("chat_title")
        m_count = r.get("member_count")
        chats.append({
            "chat_id": cid,
            "title": title if (title and str(title).strip()) else f"গ্রুপ #{idx}",
            "member_count": int(m_count) if (m_count and str(m_count).isdigit()) else 0
        })
    return chats


def get_settings(chat_id: int):
    try:
        row = _query("SELECT * FROM chat_settings WHERE chat_id=%s", (chat_id,), fetchone=True)
        if not row:
            _execute("INSERT IGNORE INTO chat_settings (chat_id) VALUES (%s)", (chat_id,))
            row = _query("SELECT * FROM chat_settings WHERE chat_id=%s", (chat_id,), fetchone=True)
        return row or {}
    except Exception:
        return {}



def save_settings(chat_id: int, data: dict):
    # Fix #4: only allow whitelisted keys
    safe = {k: v for k, v in data.items() if k in _SAFE_KEYS}
    _execute("INSERT IGNORE INTO chat_settings (chat_id) VALUES (%s)", (chat_id,))
    for key, val in safe.items():
        _execute(f"UPDATE chat_settings SET `{key}`=%s WHERE chat_id=%s", (val, chat_id))


def get_warns_for_chat(chat_id: int):
    return _query(
        "SELECT user_id, reason, warned_by, timestamp FROM warns "
        "WHERE chat_id=%s ORDER BY timestamp DESC LIMIT 50",
        (chat_id,), fetchall=True
    ) or []


def get_notes_for_chat(chat_id: int):
    return _query(
        "SELECT name, content FROM notes WHERE chat_id=%s ORDER BY name",
        (chat_id,), fetchall=True
    ) or []


def get_banned_users_for_chat(chat_id: int):
    try:
        return _query(
            "SELECT user_id, first_name, username, reason, banned_by, timestamp FROM banned_users "
            "WHERE chat_id=%s ORDER BY timestamp DESC LIMIT 100",
            (chat_id,), fetchall=True
        ) or []
    except Exception:
        return []


def get_top_inviters_for_chat(chat_id: int, limit: int = 10):
    try:
        return _query(
            "SELECT ui.inviter_id, COUNT(*) as invite_count, u.first_name, u.username "
            "FROM user_invites ui "
            "LEFT JOIN users u ON (ui.chat_id=u.chat_id AND ui.inviter_id=u.user_id) "
            "WHERE ui.chat_id=%s "
            "GROUP BY ui.inviter_id, u.first_name, u.username "
            "ORDER BY invite_count DESC LIMIT %s",
            (chat_id, limit), fetchall=True
        ) or []
    except Exception:
        return []


def get_stats():
    # Fix #5: handle missing tables gracefully
    result = {"groups": 0, "warns": 0, "notes": 0, "users": 0}
    conn = get_db()
    try:
        with conn.cursor() as cur:
            for key, table in [("groups","chat_settings"),("warns","warns"),
                                ("notes","notes")]:
                try:
                    cur.execute(f"SELECT COUNT(*) as c FROM `{table}`")
                    row = cur.fetchone()
                    result[key] = row["c"] if row else 0
                except Exception:
                    result[key] = 0
            try:
                cur.execute("SELECT COALESCE(SUM(member_count), 0) as total_m FROM chat_settings")
                row_m = cur.fetchone()
                total_m = int(row_m["total_m"]) if row_m and row_m["total_m"] else 0

                cur.execute("SELECT COUNT(DISTINCT user_id) as c FROM users")
                row_u = cur.fetchone()
                recorded_u = int(row_u["c"]) if row_u and row_u["c"] else 0

                result["users"] = max(total_m, recorded_u)
            except Exception:
                result["users"] = 0
    finally:
        conn.close()
    return result


# ── Routes ────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        error = "ভুল username বা password!"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def dashboard():
    if session.get("logged_in"):
        return render_template("dashboard.html",
                               stats=get_stats(), chats=get_all_chats(), active="dashboard")
    # Serve index.html statically from the root directory
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    index_path = os.path.join(root_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            resp = make_response(f.read())
            resp.headers["Content-Type"] = "text/html; charset=utf-8"
            return resp
    return "Landing page not found", 404


@app.route("/<string:page_name>.html")
def serve_html_page(page_name):
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    page_path = os.path.join(root_dir, f"{page_name}.html")
    if os.path.exists(page_path) and os.path.isfile(page_path):
        with open(page_path, "r", encoding="utf-8") as f:
            resp = make_response(f.read())
            resp.headers["Content-Type"] = "text/html; charset=utf-8"
            return resp
    return "Page not found", 404


@app.route("/group/<string:chat_id>")
@login_required
def group_overview(chat_id):
    chat_id = int(chat_id)
    s = get_settings(chat_id)
    if not s:
        flash("গ্রুপটি পাওয়া যায়নি।", "error")
        return redirect(url_for("dashboard"))
    return render_template("group_overview.html", s=s, chat_id=chat_id, active="groups")


@app.route("/group/<string:chat_id>/welcome", methods=["GET", "POST"])
@login_required
def group_welcome(chat_id):
    chat_id = int(chat_id)
    if request.method == "POST":
        save_settings(chat_id, {
            "welcome_enabled": 1 if request.form.get("welcome_enabled") else 0,
            "welcome_text":    request.form.get("welcome_text", "")[:4000],
            "goodbye_enabled": 1 if request.form.get("goodbye_enabled") else 0,
            "goodbye_text":    request.form.get("goodbye_text", "")[:4000],
            "welcome_button_text": request.form.get("welcome_button_text", "")[:100],
            "welcome_button_url":  request.form.get("welcome_button_url",  "")[:500],
            "welcome_sticker":     request.form.get("welcome_sticker", "")[:255],
        })
        flash("✅ ওয়েলকাম সেটিংস সেভ হয়েছে!", "success")
        return redirect(url_for("group_welcome", chat_id=chat_id))
    s = get_settings(chat_id)
    return render_template("group_welcome.html", s=s, chat_id=chat_id, active="groups")


@app.route("/group/<string:chat_id>/spam", methods=["GET", "POST"])
@login_required
def group_spam(chat_id):
    chat_id = int(chat_id)
    if request.method == "POST":
        save_settings(chat_id, {
            "antiflood_enabled":     1 if request.form.get("antiflood_enabled") else 0,
            "antilink_enabled":             1 if request.form.get("antilink_enabled")  else 0,
            "antilink_required_invites":    max(1, int(request.form.get("antilink_required_invites", 10) or 10)),
            "badwords_enabled":             1 if request.form.get("badwords_enabled")  else 0,
            "badwords_list":                request.form.get("badwords_list", "")[:2000],
            "antiforward_enabled":          1 if request.form.get("antiforward_enabled") else 0,
            "antiforward_required_invites": max(1, int(request.form.get("antiforward_required_invites", 10) or 10)),
            "lock_media_msg":               1 if request.form.get("lock_media_msg") else 0,
            "lock_stickers":                1 if request.form.get("lock_stickers") else 0,
            "badword_strike_limit":         max(1, min(5, int(request.form.get("badword_strike_limit",  3) or 3))),
            "badword_mute_duration":        max(60, int(request.form.get("badword_mute_duration", 60) or 60)),
            "antibiolink_enabled":          1 if request.form.get("antibiolink_enabled") else 0,
            "antibiolink_whitelist":        request.form.get("antibiolink_whitelist", "").strip()[:2000],
        })
        flash("✅ স্প্যাম সেটিংস সেভ হয়েছে!", "success")
        return redirect(url_for("group_spam", chat_id=chat_id))
    s = get_settings(chat_id)
    return render_template("group_spam.html", s=s, chat_id=chat_id, active="groups")


@app.route("/group/<string:chat_id>/moderation", methods=["GET", "POST"])
@login_required
def group_moderation(chat_id):
    chat_id = int(chat_id)
    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "force_add":
            try:
                f_count = max(1, min(50, int(request.form.get("force_add_count", 5))))
            except (ValueError, TypeError):
                f_count = 5
            enabled = 1 if request.form.get("force_add_enabled") else 0
            save_settings(chat_id, {
                "force_add_enabled": enabled,
                "force_add_count":   f_count,
            })
            if enabled:
                flash(f"✅ ফোর্স অ্যাড সক্রিয় করা হয়েছে! (টার্গেট: {f_count} জন বন্ধু)", "success")
            else:
                flash("❌ ফোর্স অ্যাড বন্ধ করা হয়েছে।", "warning")
            return redirect(url_for("group_moderation", chat_id=chat_id))
        elif form_type == "warn":
            try:
                max_w = max(1, min(10, int(request.form.get("max_warns", 3))))
            except (ValueError, TypeError):
                max_w = 3
            save_settings(chat_id, {
                "max_warns":   max_w,
                "warn_action": request.form.get("warn_action", "ban"),
            })
            flash("✅ ওয়ার্ন সেটিংস সেভ হয়েছে!", "success")
            return redirect(url_for("group_moderation", chat_id=chat_id))
        else:
            try:
                max_w = max(1, min(10, int(request.form.get("max_warns", 3))))
            except (ValueError, TypeError):
                max_w = 3
            try:
                f_count = max(1, min(50, int(request.form.get("force_add_count", 5))))
            except (ValueError, TypeError):
                f_count = 5
            save_settings(chat_id, {
                "max_warns":          max_w,
                "warn_action":        request.form.get("warn_action", "ban"),
                "force_add_enabled":  1 if request.form.get("force_add_enabled") else 0,
                "force_add_count":    f_count,
            })
            flash("✅ মডারেশন ও ফোর্স অ্যাড সেটিংস সেভ হয়েছে!", "success")
            return redirect(url_for("group_moderation", chat_id=chat_id))
    s     = get_settings(chat_id)
    warns = get_warns_for_chat(chat_id)
    top_inviters = get_top_inviters_for_chat(chat_id, limit=10)
    return render_template("group_moderation.html",
                           s=s, chat_id=chat_id,
                           warns=list(enumerate(warns)),
                           top_inviters=list(enumerate(top_inviters)),
                           active="groups")


@app.route("/group/<string:chat_id>/notes", methods=["GET", "POST"])
@login_required
def group_notes(chat_id):
    chat_id = int(chat_id)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            name    = request.form.get("name", "").strip().lower()[:100]
            content = request.form.get("content", "").strip()[:4000]
            if name and content:
                _execute(
                    "INSERT INTO notes (chat_id,name,content) VALUES (%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE content=VALUES(content)",
                    (chat_id, name, content)
                )
                flash(f"✅ নোট '{name}' সেভ হয়েছে!", "success")
        elif action == "delete":
            name = request.form.get("name", "").strip().lower()
            _execute("DELETE FROM notes WHERE chat_id=%s AND name=%s", (chat_id, name))
            flash(f"🗑️ নোট '{name}' মুছে দেওয়া হয়েছে।", "success")
        return redirect(url_for("group_notes", chat_id=chat_id))
    notes = get_notes_for_chat(chat_id)
    s     = get_settings(chat_id)
    return render_template("group_notes.html",
                           s=s, chat_id=chat_id, notes=notes, active="groups")


@app.route("/group/<string:chat_id>/rules", methods=["GET", "POST"])
@login_required
def group_rules(chat_id):
    chat_id = int(chat_id)
    if request.method == "POST":
        save_settings(chat_id, {
            "rules_text": request.form.get("rules_text", "")[:4000]
        })
        flash("✅ নিয়মাবলী সেভ হয়েছে!", "success")
        return redirect(url_for("group_rules", chat_id=chat_id))
    s = get_settings(chat_id)
    return render_template("group_rules.html", s=s, chat_id=chat_id, active="groups")


@app.route("/group/<string:chat_id>/banlist", methods=["GET", "POST"])
@login_required
def group_banlist(chat_id):
    chat_id = int(chat_id)
    error = None

    if request.method == "POST":
        action  = request.form.get("action")
        user_id = request.form.get("user_id")
        if action == "unban" and user_id:
            try:
                import asyncio, telegram
                bot = telegram.Bot(token=os.environ.get("BOT_TOKEN") or
                                   __import__("config").BOT_TOKEN)
                async def _unban():
                    async with bot:
                        await bot.unban_chat_member(
                            chat_id, int(user_id), only_if_banned=True
                        )
                asyncio.run(_unban())
            except Exception:
                pass

            try:
                _execute("DELETE FROM banned_users WHERE chat_id=%s AND user_id=%s", (chat_id, int(user_id)))
                flash("✅ সদস্যকে সফলভাবে আনব্যান করা হয়েছে।", "success")
            except Exception as e:
                flash(f"❌ ডাটাবেজ আপডেট ব্যর্থ: {e}", "error")
        return redirect(url_for("group_banlist", chat_id=chat_id))

    # GET — fetch ban list from Database
    banned_rows = get_banned_users_for_chat(chat_id)
    banned = list(enumerate(banned_rows))
    s = get_settings(chat_id)

    return render_template("group_banlist.html",
                           s=s, chat_id=chat_id, banned=banned,
                           error=error, active="groups")


def _get_global_settings():
    _execute("""
        CREATE TABLE IF NOT EXISTS global_settings (
            setting_key VARCHAR(100) PRIMARY KEY,
            setting_val TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    rows = _query("SELECT setting_key, setting_val FROM global_settings", fetchall=True) or []
    try:
        from database import DEFAULT_SERVICE_ALERT_TEXT
    except Exception:
        DEFAULT_SERVICE_ALERT_TEXT = (
            "🌸 <b>আমাদের গ্রুপের অফিসিয়াল ভেরিফায়েড সার্ভিস গার্ল</b> 🌸\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <b>সতর্কবার্তা:</b> আমাদের গ্রুপে আমাদের নিজস্ব সার্ভিস গার্ল আছে, দয়া করে প্রতারিত না হয়ে সরাসরি উনাকে নক দিন।\n\n"
            "👉 <b>সার্ভিস গার্ল:</b> <b>{service_girl_name}</b> (👉 <a href=\"{service_girl_link}\">@{service_girl_username}</a>)\n"
            "💬 <b>ইনবক্স মেসেজ লিংক:</b> <a href=\"{service_girl_link}\">উনাকে সরাসরি মেসেজ দিতে এখানে চাপ দিন ➜</a>\n\n"
            "👑 <b>এডমিন আইডি:</b> <a href=\"{admin_link}\">@{admin_username}</a>\n"
            "📢 <i>কোনো মেয়ে গ্রুপের ভেরিফাইড হতে চাইলে এডমিনকে মেসেজ করুন। ধন্যবাদ।</i>\n\n"
            "👉 <b>অনলাইন সদস্যরা:</b> {mentions_text}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔞 <b>আমাদের মূল ১৮+ গ্রুপগুলোতে জয়েন থাকুন:</b>\n"
            "👉 <a href=\"{main_group_link}\">Dark Romance ১৮+ আড্ডা (Group 1)</a>\n"
            "👉 <a href=\"https://t.me/mastiunlimitedzone\">Masti Unlimited ১৮+ আড্ডা (Group 2)</a>"
        )
    settings = {
        "site_gate_enabled": "0",
        "site_gate_required_invites": "10",
        "site_gate_custom_link": "https://t.me/darkfantasyloverzone",
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
    for r in rows:
        settings[r["setting_key"]] = r["setting_val"]
    return settings


def _set_global_setting(key, val):
    _execute("""
        CREATE TABLE IF NOT EXISTS global_settings (
            setting_key VARCHAR(100) PRIMARY KEY,
            setting_val TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    _execute(
        "INSERT INTO global_settings (setting_key, setting_val) VALUES (%s, %s) "
        "ON DUPLICATE KEY UPDATE setting_val=VALUES(setting_val)",
        (key, str(val))
    )


# ── API ───────────────────────────────────────────

@app.route("/api/stats")
@login_required
def api_stats():
    return jsonify(get_stats())


@app.route("/api/check_invites", methods=["GET", "POST"])
def api_check_invites():
    settings = _get_global_settings()
    gate_enabled = (settings.get("site_gate_enabled", "1") == "1")
    required = int(settings.get("site_gate_required_invites", "10") or 10)
    custom_link = settings.get("site_gate_custom_link", "https://t.me/darkfantasyloverzone")

    action = request.args.get("action") or (request.get_json(silent=True) or {}).get("action") or ""
    if action == "gate_status":
        return jsonify({
            "success": True,
            "gate_enabled": gate_enabled,
            "site_gate_enabled": 1 if gate_enabled else 0,
            "required": required,
            "custom_link": custom_link
        })

    if not gate_enabled:
        return jsonify({
            "success": True,
            "unlocked": True,
            "gate_enabled": False,
            "invites": 0,
            "required": 0,
            "remaining": 0,
            "message": "টেলিগ্রাম ভেরিফিকেশন গেট বন্ধ রয়েছে, সরাসরি আনলক করা হয়েছে।"
        })

    raw_input = request.args.get("user_id") or request.args.get("username") or ""
    if not raw_input and request.is_json:
        data = request.get_json(silent=True) or {}
        raw_input = data.get("user_id") or data.get("username") or ""
    if not raw_input and request.form:
        raw_input = request.form.get("user_id") or request.form.get("username") or ""

    raw_input = str(raw_input).strip()
    if not raw_input:
        return jsonify({
            "success": False,
            "unlocked": False,
            "invites": 0,
            "required": required,
            "message": "অনুগ্রহ করে আপনার টেলিগ্রাম ইউজার আইডি বা @ইউজারনেম লিখুন।"
        })

    clean_input = raw_input.lstrip("@")
    user_id = None
    username = ""
    first_name = ""

    if clean_input.isdigit():
        user_id = int(clean_input)
        u = _query("SELECT user_id, username, first_name FROM users WHERE user_id=%s LIMIT 1", (user_id,), fetchone=True)
        if u:
            username = u.get("username") or ""
            first_name = u.get("first_name") or ""
    else:
        u = _query("SELECT user_id, username, first_name FROM users WHERE LOWER(username)=LOWER(%s) LIMIT 1", (clean_input,), fetchone=True)
        if u:
            user_id = int(u.get("user_id"))
            username = u.get("username") or ""
            first_name = u.get("first_name") or ""

    if not user_id:
        return jsonify({
            "success": False,
            "unlocked": False,
            "invites": 0,
            "required": required,
            "remaining": required,
            "message": f"❌ টেলিগ্রাম আইডি '{raw_input}' পাওয়া যায়নি। আপনি কি গ্রুপে কাউকে এড করেছেন? টেলিগ্রাম গ্রুপে /myinvites লিখে আপনার সঠিক আইডি দেখে নিন।"
        })

    # Count actual invites
    row = _query("SELECT COUNT(*) as cnt FROM user_invites WHERE inviter_id=%s", (user_id,), fetchone=True)
    invite_count = int(row.get("cnt") or 0) if row else 0
    unlocked = (invite_count >= required)
    remaining = max(0, required - invite_count)

    return jsonify({
        "success": True,
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "invites": invite_count,
        "required": required,
        "remaining": remaining,
        "unlocked": unlocked,
        "message": f"✅ অভিনন্দন! আপনি সফলভাবে {invite_count} জন মেম্বার এড করেছেন।" if unlocked else f"❌ আপনি মাত্র {invite_count} জন মেম্বার এড করেছেন! সাইটের কন্টেন্ট আনলক করতে আরও {remaining} জন বন্ধুকে টেলিগ্রাম গ্রুপে এড করতে হবে।"
    })


@app.route("/site_settings", methods=["GET", "POST"])
@login_required
def site_settings():
    if request.method == "POST":
        gate_en = "1" if request.form.get("site_gate_enabled") == "1" else "0"
        req_inv = request.form.get("site_gate_required_invites", "10").strip()
        custom_link = request.form.get("site_gate_custom_link", "https://t.me/darkfantasyloverzone").strip()

        try:
            req_inv_int = max(1, int(req_inv))
        except Exception:
            req_inv_int = 10

        try:
            _set_global_setting("site_gate_enabled", gate_en)
            _set_global_setting("site_gate_required_invites", str(req_inv_int))
            _set_global_setting("site_gate_custom_link", custom_link)
            flash("✅ ওয়েবসাইট গেট সেটিংস সফলভাবে সংরক্ষণ করা হয়েছে।", "success")
        except Exception as e:
            flash(f"❌ সেটিংস আপডেট ব্যর্থ: {e}", "error")

        return redirect(url_for("site_settings"))

    settings = _get_global_settings()
    return render_template("site_settings.html", settings=settings, active="site_settings")


@app.route("/service_alert", methods=["GET", "POST"])
@login_required
def service_alert():
    if request.method == "POST":
        alert_en = "1" if request.form.get("service_alert_enabled") == "1" else "0"
        interval_val = request.form.get("service_alert_interval", "15").strip()
        admin_user = request.form.get("service_admin_username", "rafi0002").strip().lstrip("@")
        admin_link = request.form.get("service_admin_link", "").strip() or f"https://t.me/{admin_user}"
        alert_text = request.form.get("service_alert_text", "").strip()

        # Collect multiple service girls from dynamic form lists
        girl_names = request.form.getlist("girl_name[]")
        girl_usernames = request.form.getlist("girl_username[]")
        girl_links = request.form.getlist("girl_link[]")

        girls_list = []
        for n, u, l in zip(girl_names, girl_usernames, girl_links):
            n_str = str(n or "").strip()
            u_str = str(u or "").strip().lstrip("@")
            l_str = str(l or "").strip()
            if u_str or n_str:
                if not l_str and u_str:
                    l_str = f"https://t.me/{u_str}"
                if not n_str:
                    n_str = u_str
                girls_list.append({
                    "name": n_str,
                    "username": u_str,
                    "link": l_str
                })

        if not girls_list:
            # Fallback if submitted as single inputs
            g_name = request.form.get("service_girl_name", "জেরিন (Zerin)").strip()
            g_user = request.form.get("service_girl_username", "zerin627").strip().lstrip("@")
            g_link = request.form.get("service_girl_link", "").strip() or f"https://t.me/{g_user}"
            girls_list = [{"name": g_name or "জেরিন (Zerin)", "username": g_user or "zerin627", "link": g_link or "https://t.me/zerin627"}]

        try:
            interval_int = max(1, min(1440, int(interval_val)))
        except Exception:
            interval_int = 15

        try:
            _set_global_setting("service_alert_enabled", alert_en)
            _set_global_setting("service_alert_interval", str(interval_int))
            _set_global_setting("service_girls_json", json.dumps(girls_list, ensure_ascii=False))
            if girls_list:
                _set_global_setting("service_girl_name", girls_list[0]["name"])
                _set_global_setting("service_girl_username", girls_list[0]["username"])
                _set_global_setting("service_girl_link", girls_list[0]["link"])
            _set_global_setting("service_admin_username", admin_user)
            _set_global_setting("service_admin_link", admin_link)
            if alert_text:
                _set_global_setting("service_alert_text", alert_text)

            flash("✅ সার্ভিস গার্লস ও অ্যান্টি-স্ক্যাম নোটিশ সেটিংস সফলভাবে সংরক্ষণ করা হয়েছে।", "success")
        except Exception as e:
            flash(f"❌ সেটিংস আপডেট ব্যর্থ: {e}", "error")

        return redirect(url_for("service_alert"))

    settings = _get_global_settings()
    raw_girls = settings.get("service_girls_json", "[]")
    try:
        girls_list = json.loads(raw_girls) if raw_girls else []
    except Exception:
        girls_list = []
    if not isinstance(girls_list, list) or not girls_list:
        girls_list = [{
            "name": settings.get("service_girl_name", "জেরিন (Zerin)") or "জেরিন (Zerin)",
            "username": (settings.get("service_girl_username", "zerin627") or "zerin627").lstrip("@"),
            "link": settings.get("service_girl_link", "https://t.me/zerin627") or "https://t.me/zerin627"
        }]
    return render_template("service_alert.html", settings=settings, girls_list=girls_list, active="service_alert")


@app.route("/bot_admins", methods=["GET", "POST"])
@login_required
def bot_admins():
    if request.method == "POST":
        action = request.form.get("action")
        user_id = request.form.get("user_id")
        username = request.form.get("username", "").strip()
        first_name = request.form.get("first_name", "").strip()

        # Clean username symbol
        if username.startswith("@"):
            username = username[1:]

        if action == "add" and user_id:
            try:
                _execute(
                    "INSERT INTO bot_admins (user_id, username, first_name) VALUES (%s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE username=%s, first_name=%s",
                    (int(user_id), username, first_name, username, first_name)
                )
                flash("✅ নতুন বট অ্যাডমিন যুক্ত করা হয়েছে।", "success")
            except Exception as e:
                flash(f"❌ যোগ করতে ব্যর্থ: {e}", "error")
        elif action == "delete" and user_id:
            try:
                _execute("DELETE FROM bot_admins WHERE user_id=%s", (int(user_id),))
                flash("✅ বট অ্যাডমিন ডিলিট করা হয়েছে।", "success")
            except Exception as e:
                flash(f"❌ ডিলিট করতে ব্যর্থ: {e}", "error")
        return redirect(url_for("bot_admins"))

    # Fetch all admins from DB
    admins = _query("SELECT * FROM bot_admins ORDER BY user_id", fetchall=True) or []
    return render_template("bot_admins.html", admins=admins, active="bot_admins")


# ── Video Collector Routes ─────────────────────────

@app.route("/video-collector", methods=["GET"])
@login_required
def video_collector():
    try:
        # Ensure tables exist (ignore if already created)
        try:
            _execute("""
                CREATE TABLE IF NOT EXISTS vc_channels (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    channel_id BIGINT DEFAULT NULL,
                    channel_title VARCHAR(255) DEFAULT '',
                    channel_username VARCHAR(255) DEFAULT '',
                    channel_type VARCHAR(50) NOT NULL DEFAULT 'source',
                    is_active TINYINT(1) DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_chan_type (channel_id, channel_type),
                    INDEX idx_user_type (channel_username, channel_type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        except Exception:
            pass

        try:
            _execute("ALTER TABLE vc_channels MODIFY channel_type VARCHAR(50) NOT NULL DEFAULT 'source'")
        except Exception:
            pass

        try:
            _execute("""
                CREATE TABLE IF NOT EXISTS vc_settings (
                    key_name VARCHAR(100) PRIMARY KEY,
                    value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        except Exception:
            pass

        try:
            _execute("""
                CREATE TABLE IF NOT EXISTS vc_stats (
                    stat_name VARCHAR(100) PRIMARY KEY,
                    stat_value BIGINT DEFAULT 0
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        except Exception:
            pass

        try:
            _execute("""
                CREATE TABLE IF NOT EXISTS vc_queue (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    source_chat_id BIGINT NOT NULL,
                    source_message_id INT NOT NULL,
                    file_id VARCHAR(255) NOT NULL,
                    caption TEXT,
                    status VARCHAR(50) DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        except Exception:
            pass

        # Pre-seed default delivery channel @darkromance4u if not exists
        try:
            _execute("""
                INSERT INTO vc_channels (channel_id, channel_title, channel_username, channel_type, is_active)
                SELECT NULL, 'Dark Romance 4U', 'darkromance4u', 'delivery', 1
                WHERE NOT EXISTS (
                    SELECT 1 FROM vc_channels WHERE channel_username = 'darkromance4u' AND channel_type = 'delivery'
                )
            """)
        except Exception:
            pass

        # Pre-seed initial source channels requested by user
        initial_sources = [
            ("ayssorbonas420", "Ays Sorbonas"),
            ("pfff_boom", "Pfff Boom"),
            ("adult_desi30", "Adult Desi 30")
        ]
        for u, t in initial_sources:
            try:
                _execute("""
                    INSERT INTO vc_channels (channel_id, channel_title, channel_username, channel_type, is_active)
                    SELECT NULL, %s, %s, 'source', 1
                    WHERE NOT EXISTS (
                        SELECT 1 FROM vc_channels WHERE channel_username = %s AND channel_type = 'source'
                    )
                """, (t, u, u))
            except Exception:
                pass

        # Clean up any discussion group accidentally marked as delivery channel or source
        try:
            _execute("""
                DELETE FROM vc_channels 
                WHERE channel_type = 'delivery' 
                  AND (channel_id IN (4446159364, -1004446159364) OR LOWER(channel_title) LIKE '%discussion%')
            """)
            _execute("""
                DELETE FROM vc_channels 
                WHERE channel_type = 'source' 
                  AND (channel_id IN (4446159364, -1004446159364, 4342232814, -1004342232814) 
                       OR LOWER(channel_title) LIKE '%dark romance%')
            """)
        except Exception:
            pass

        sources = _query("SELECT * FROM vc_channels WHERE channel_type='source' ORDER BY id DESC", fetchall=True) or []
        deliveries = _query("SELECT * FROM vc_channels WHERE channel_type='delivery' ORDER BY id DESC", fetchall=True) or []

        settings_rows = _query("SELECT key_name, value FROM vc_settings", fetchall=True) or []
        settings = {
            "delete_source_message": "0",
            "is_collector_active": "1",
            "collect_from_all_joined": "1",
            "delivery_interval_minutes": "15",
            "delivery_batch_size": "3",
            "min_video_duration": "20",
            "custom_caption": "",
            "vc_bot_token": os.environ.get("VC_BOT_TOKEN", "8949426682:AAEPX3e3kOrVYFGqTfE3PiiW3CYnSGjY8jc"),
            "vc_bot_username": os.environ.get("VC_BOT_USERNAME", "newideos_bot")
        }
        for r in settings_rows:
            settings[r["key_name"]] = r["value"]

        stat_row = _query("SELECT stat_value FROM vc_stats WHERE stat_name='total_forwarded'", fetchone=True)
        total_forwarded = stat_row["stat_value"] if stat_row else 0

        queue_count_row = _query("SELECT COUNT(*) as cnt FROM vc_queue", fetchone=True)
        queue_count = queue_count_row["cnt"] if queue_count_row else 0

        queue_items = _query("SELECT * FROM vc_queue ORDER BY id ASC LIMIT 10", fetchall=True) or []

        return render_template(
            "video_collector.html",
            sources=sources,
            deliveries=deliveries,
            settings=settings,
            total_forwarded=total_forwarded,
            queue_count=queue_count,
            queue_items=queue_items,
            active="video_collector"
        )
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        return f"<div style='background:#111;color:#ff6b6b;font-family:monospace;padding:24px;border-radius:10px;'><h3>❌ Error loading Video Collector:</h3><pre>{err_msg}</pre></div>", 500


@app.route("/video-collector/add", methods=["POST"])
@login_required
def video_collector_add():
    raw_id = request.form.get("channel_id", "").strip()
    channel_title = request.form.get("channel_title", "").strip()
    raw_user = request.form.get("channel_username", "").strip()
    channel_type = request.form.get("channel_type", "").strip().lower()

    if channel_type not in ("source", "delivery"):
        flash("❌ সঠিক চ্যানেল টাইপ নির্বাচন করুন।", "error")
        return redirect(url_for("video_collector"))

    # Extract username if link was provided
    username = raw_user.lstrip("@").strip()
    cid = None

    target_str = raw_id
    if "t.me/" in target_str:
        parts = target_str.rstrip("/").split("t.me/")
        if len(parts) > 1:
            username = parts[1].lstrip("@").strip()
    elif target_str.startswith("@"):
        username = target_str.lstrip("@").strip()
    elif target_str.lstrip("-").isdigit():
        cid = int(target_str)
    elif target_str and not username:
        username = target_str.strip()

    if not username and cid is None:
        flash("❌ সঠিক চ্যানেল লিংক, আইডি বা ইউজারনেম (e.g. @darkromance4u) দিন।", "error")
        return redirect(url_for("video_collector"))

    title = channel_title or (f"@{username}" if username else f"Channel {cid}")

    try:
        if username:
            existing = _query(
                "SELECT id FROM vc_channels WHERE channel_username = %s AND channel_type = %s",
                (username, channel_type),
                fetchone=True
            )
        else:
            existing = _query(
                "SELECT id FROM vc_channels WHERE channel_id = %s AND channel_type = %s",
                (cid, channel_type),
                fetchone=True
            )

        if existing:
            _execute("""
                UPDATE vc_channels 
                SET channel_id = COALESCE(%s, channel_id),
                    channel_title = %s,
                    channel_username = %s,
                    is_active = 1
                WHERE id = %s
            """, (cid, title, username, existing["id"]))
        else:
            _execute("""
                INSERT INTO vc_channels (channel_id, channel_title, channel_username, channel_type, is_active)
                VALUES (%s, %s, %s, %s, 1)
            """, (cid, title, username, channel_type))

        type_str = "সোর্স চ্যানেল" if channel_type == "source" else "ডেলিভারি চ্যানেল"
        flash(f"✅ সফলভাবে {type_str} ({title}) যুক্ত করা হয়েছে!", "success")
    except Exception as e:
        flash(f"❌ চ্যানেল যুক্ত করতে ব্যর্থ: {e}", "error")

    return redirect(url_for("video_collector"))


@app.route("/video-collector/delete/<int:channel_id_pk>", methods=["POST"])
@login_required
def video_collector_delete(channel_id_pk):
    try:
        _execute("DELETE FROM vc_channels WHERE id = %s", (channel_id_pk,))
        flash("✅ চ্যানেল ডিলিট করা হয়েছে।", "success")
    except Exception as e:
        flash(f"❌ ডিলিট করতে ব্যর্থ: {e}", "error")
    return redirect(url_for("video_collector"))


@app.route("/video-collector/send-now", methods=["POST"])
@login_required
def video_collector_send_now():
    try:
        _execute("""
            INSERT INTO vc_settings (key_name, value)
            VALUES ('trigger_immediate_send', '1')
            ON DUPLICATE KEY UPDATE value = '1'
        """)
        flash("⚡ অবিলম্বে পরবর্তী ১টি ভিডিও ডেলিভারি করার সিগন্যাল পাঠানো হয়েছে!", "success")
    except Exception as e:
        flash(f"❌ সিগন্যাল পাঠাতে ব্যর্থ: {e}", "error")
    return redirect(url_for("video_collector"))


@app.route("/video-collector/settings", methods=["POST"])
@login_required
def video_collector_settings():
    delete_source = "1" if request.form.get("delete_source_message") == "on" else "0"
    is_active = "1" if request.form.get("is_collector_active") == "on" else "0"
    collect_from_all = "1" if request.form.get("collect_from_all_joined") == "on" else "0"
    delivery_interval = request.form.get("delivery_interval_minutes", "15").strip()
    delivery_batch_size = request.form.get("delivery_batch_size", "3").strip()
    min_video_duration = request.form.get("min_video_duration", "20").strip()
    custom_caption = request.form.get("custom_caption", "").strip()
    bot_token = request.form.get("vc_bot_token", "").strip()
    bot_username = request.form.get("vc_bot_username", "").strip().lstrip("@")

    # Validate interval integer
    if not delivery_interval.isdigit() or int(delivery_interval) < 1:
        delivery_interval = "15"

    if not delivery_batch_size.isdigit() or int(delivery_batch_size) < 1:
        delivery_batch_size = "3"

    if not min_video_duration.isdigit() or int(min_video_duration) < 1:
        min_video_duration = "20"

    try:
        for k, v in [
            ("delete_source_message", delete_source),
            ("is_collector_active", is_active),
            ("collect_from_all_joined", collect_from_all),
            ("delivery_interval_minutes", delivery_interval),
            ("delivery_batch_size", delivery_batch_size),
            ("min_video_duration", min_video_duration),
            ("custom_caption", custom_caption),
            ("vc_bot_token", bot_token),
            ("vc_bot_username", bot_username)
        ]:
            _execute("""
                INSERT INTO vc_settings (key_name, value)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE value = VALUES(value)
            """, (k, v))
        flash("✅ সেটিংস সফলভাবে সংরক্ষণ করা হয়েছে।", "success")
    except Exception as e:
        flash(f"❌ সেটিংস সেভ করতে ব্যর্থ: {e}", "error")

    return redirect(url_for("video_collector"))


# ── Member Auto-Adder Helpers ──────────────────────────────────────

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


import time


def run_async(coro):
    """Run an async coroutine synchronously inside Flask request thread."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.close()
        except Exception:
            pass


def is_adder_running():
    """Check if auto_member_adder.py is currently running."""
    try:
        res = subprocess.run(["pgrep", "-f", "auto_member_adder.py"], stdout=subprocess.PIPE, text=True)
        pids = [p.strip() for p in res.stdout.strip().splitlines() if p.strip()]
        return len(pids) > 0, pids
    except Exception:
        return False, []


def start_adder_service():
    """Start or restart auto_member_adder.py daemon in background with process cooldown."""
    try:
        subprocess.run(["pkill", "-f", "auto_member_adder.py"])
        time.sleep(1)  # Allow previous process to cleanly exit and release SQLite session locks
    except Exception:
        pass

    python_bin = "/home/techandc/virtualenv/public_html/bot/3.11/bin/python"
    if not os.path.exists(python_bin):
        python_bin = sys.executable

    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(project_dir, "auto_member_adder.py")
    log_path = os.path.join(project_dir, "auto_adder.log")

    cmd = f"nohup {python_bin} {script_path} --all --daemon >> {log_path} 2>&1 &"
    subprocess.Popen(cmd, shell=True, cwd=project_dir, preexec_fn=getattr(os, "setpgrp", None))


def stop_adder_service():
    """Stop auto_member_adder.py daemon."""
    try:
        subprocess.run(["pkill", "-f", "auto_member_adder.py"])
        time.sleep(1)
    except Exception:
        pass


def init_adder_accounts_table():
    """Ensure member_adder_accounts table exists for tracking connected IDs."""
    try:
        _execute("""
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
    except Exception:
        pass


def get_connected_accounts_info():
    """
    High-performance account inspector optimized for 20-30+ accounts.
    Uses database caching to eliminate blocking MTProto network calls on every HTTP request.
    """
    sessions_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sessions")
    if not os.path.exists(sessions_dir):
        return []

    init_adder_accounts_table()

    # Discover all session files currently stored on disk
    session_files = {f[:-8] for f in os.listdir(sessions_dir) if f.endswith(".session")}
    if not session_files:
        return []

    # Clean up any removed session accounts from database
    try:
        db_rows = _query("SELECT * FROM member_adder_accounts", fetchall=True) or []
    except Exception:
        db_rows = []

    db_accounts = {r["account_name"]: r for r in db_rows}

    # Query today's added count and total added count per account in single aggregated queries
    today_map = {}
    total_map = {}
    try:
        today_stats = _query("""
            SELECT added_by_account, COUNT(*) as cnt 
            FROM member_add_history 
            WHERE status = 'added' AND DATE(attempted_at) = CURDATE()
            GROUP BY added_by_account
        """, fetchall=True) or []
        today_map = {r["added_by_account"]: r["cnt"] for r in today_stats if r.get("added_by_account")}

        total_stats = _query("""
            SELECT added_by_account, COUNT(*) as cnt 
            FROM member_add_history 
            WHERE status = 'added'
            GROUP BY added_by_account
        """, fetchall=True) or []
        total_map = {r["added_by_account"]: r["cnt"] for r in total_stats if r.get("added_by_account")}
    except Exception:
        pass

    accounts = []
    from video_collector.config import TG_API_ID, TG_API_HASH
    from telethon import TelegramClient

    for acc_name in session_files:
        rec = db_accounts.get(acc_name)
        if not rec or not rec.get("first_name"):
            # Uncached account: inspect once via Telethon and persist to database
            sess_base = os.path.join(sessions_dir, acc_name)
            first_name = acc_name
            last_name = ""
            username = ""
            tg_id = None
            status = "authorized"
            status_detail = "সক্রিয়"
            try:
                async def _inspect():
                    c = TelegramClient(sess_base, TG_API_ID, TG_API_HASH)
                    await c.connect()
                    if await c.is_user_authorized():
                        me = await c.get_me()
                        await c.disconnect()
                        return me
                    await c.disconnect()
                    return None

                me = run_async(_inspect())
                if me:
                    first_name = me.first_name or acc_name
                    last_name = me.last_name or ""
                    username = me.username or ""
                    tg_id = me.id
                    status = "authorized"
                else:
                    status = "unauthorized"
                    status_detail = "লগআউট"
            except Exception as e:
                status = "error"
                status_detail = str(e)[:100]

            try:
                _execute("""
                    INSERT INTO member_adder_accounts (account_name, telegram_id, first_name, last_name, username, status, status_detail)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        telegram_id = VALUES(telegram_id),
                        first_name = VALUES(first_name),
                        last_name = VALUES(last_name),
                        username = VALUES(username),
                        status = VALUES(status),
                        status_detail = VALUES(status_detail)
                """, (acc_name, tg_id, first_name, last_name, username, status, status_detail))
            except Exception:
                pass

            rec = {
                "account_name": acc_name,
                "first_name": first_name,
                "last_name": last_name,
                "username": username,
                "telegram_id": tg_id,
                "status": status,
                "status_detail": status_detail
            }

        acc_today = today_map.get(acc_name, 0)
        acc_total = total_map.get(acc_name, 0)

        accounts.append({
            "name": acc_name,
            "display_name": f"{rec.get('first_name', '')} {rec.get('last_name', '')}".strip() or acc_name,
            "username": rec.get("username", ""),
            "id": rec.get("telegram_id", ""),
            "status": rec.get("status", "authorized"),
            "status_detail": rec.get("status_detail", "সক্রিয়"),
            "added_today": acc_today,
            "total_added": acc_total
        })

    # Sort accounts by name for clean display
    accounts.sort(key=lambda x: x["name"])
    return accounts


# ── Member Auto-Adder Routes ───────────────────────────────────────

@app.route("/member-adder", methods=["GET"])
@login_required
def member_adder_page():
    try:
        _execute("""
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
        _execute("""
            CREATE TABLE IF NOT EXISTS member_adder_settings (
                setting_key VARCHAR(100) PRIMARY KEY,
                setting_val TEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        _execute("INSERT IGNORE INTO member_adder_settings VALUES ('daily_limit', '35')")
        _execute("INSERT IGNORE INTO member_adder_settings VALUES ('min_delay', '60')")
        _execute("INSERT IGNORE INTO member_adder_settings VALUES ('max_delay', '110')")
        _execute("INSERT IGNORE INTO member_adder_settings VALUES ('target_group', 'darkfantasyloverzone')")
        _execute("INSERT IGNORE INTO member_adder_settings VALUES ('active_account', 'nikita967')")
        
        # Ensure users table has created_at and updated_at
        try:
            _execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except Exception:
            pass
        try:
            _execute("ALTER TABLE users ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
        except Exception:
            pass
        try:
            _execute("ALTER TABLE users ADD INDEX idx_users_created (created_at)")
        except Exception:
            pass
        try:
            _execute("""
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
        except Exception:
            pass
    except Exception:
        pass

    # Total members in DB
    total_candidates_row = _query("SELECT COUNT(DISTINCT user_id) as cnt FROM users", fetchone=True)
    total_candidates = total_candidates_row["cnt"] if total_candidates_row else 0

    total_added_row = _query("SELECT COUNT(*) as cnt FROM member_add_history WHERE status='added'", fetchone=True)
    total_added = total_added_row["cnt"] if total_added_row else 0

    added_today_row = _query("SELECT COUNT(*) as cnt FROM member_add_history WHERE status='added' AND DATE(attempted_at) = CURDATE()", fetchone=True)
    added_today = added_today_row["cnt"] if added_today_row else 0

    privacy_row = _query("SELECT COUNT(*) as cnt FROM member_add_history WHERE status='privacy_restricted'", fetchone=True)
    total_privacy = privacy_row["cnt"] if privacy_row else 0

    recent_history = _query("SELECT * FROM member_add_history ORDER BY id DESC LIMIT 30", fetchall=True) or []

    settings_rows = _query("SELECT setting_key, setting_val FROM member_adder_settings", fetchall=True) or []
    settings = {
        "daily_limit": "35",
        "min_delay": "60",
        "max_delay": "110",
        "target_group": "darkfantasyloverzone",
        "active_account": "nikita967"
    }
    for r in settings_rows:
        settings[r["setting_key"]] = r["setting_val"]

    # Connected accounts info
    connected_accounts = get_connected_accounts_info()

    # Process running status
    is_running, running_pids = is_adder_running()

    # Pending web OTP login
    pending_login = session.get("adder_pending_login")

    return render_template(
        "member_adder.html",
        total_candidates=total_candidates,
        total_added=total_added,
        added_today=added_today,
        total_privacy=total_privacy,
        recent_history=recent_history,
        settings=settings,
        connected_accounts=connected_accounts,
        is_running=is_running,
        running_pids=running_pids,
        pending_login=pending_login,
        active="member_adder"
    )


@app.route("/member-adder/settings", methods=["POST"])
@login_required
def member_adder_settings():
    daily_limit = request.form.get("daily_limit", "35").strip()
    min_delay = request.form.get("min_delay", "60").strip()
    max_delay = request.form.get("max_delay", "110").strip()
    target_group = request.form.get("target_group", "darkfantasyloverzone").strip().lstrip("@")
    active_account = request.form.get("active_account", "nikita967").strip().lstrip("@")

    if not daily_limit.isdigit() or int(daily_limit) < 1 or int(daily_limit) > 50:
        daily_limit = "35"
    if not min_delay.isdigit() or int(min_delay) < 10:
        min_delay = "60"
    if not max_delay.isdigit() or int(max_delay) < int(min_delay):
        max_delay = "110"
    if not target_group:
        target_group = "darkfantasyloverzone"
    if not active_account:
        active_account = "nikita967"

    try:
        for k, v in [
            ("daily_limit", daily_limit),
            ("min_delay", min_delay),
            ("max_delay", max_delay),
            ("target_group", target_group),
            ("active_account", active_account)
        ]:
            _execute("""
                INSERT INTO member_adder_settings (setting_key, setting_val)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE setting_val = VALUES(setting_val)
            """, (k, v))
        flash("✅ মেম্বার অ্যাডার সেটিংস সফলভাবে সংরক্ষণ করা হয়েছে।", "success")
    except Exception as e:
        flash(f"❌ সেটিংস সেভ করতে ব্যর্থ: {e}", "error")

    return redirect(url_for("member_adder_page"))


@app.route("/member-adder/login-send-code", methods=["POST"])
@login_required
def member_adder_login_send_code():
    account_name = request.form.get("account_name", "").strip().lstrip("@")
    raw_phone = request.form.get("phone", "").strip()

    if not account_name:
        flash("❌ একাউন্টের একটি নাম দিন (যেমন: nikita2, acc3)", "error")
        return redirect(url_for("member_adder_page"))

    if not raw_phone:
        flash("❌ ফোন নাম্বার দিন", "error")
        return redirect(url_for("member_adder_page"))

    clean_name = re.sub(r"[^\w\-]", "_", account_name).lower()
    phone = format_phone_number(raw_phone)

    sessions_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    session_path = os.path.join(sessions_dir, clean_name)

    # Check if active session already exists with this name
    if os.path.exists(session_path + ".session"):
        existing = _query("SELECT status FROM member_adder_accounts WHERE account_name = %s", (clean_name,), fetchone=True)
        if existing and existing.get("status") == "authorized":
            flash(f"⚠️ '{clean_name}' নামের একটি একাউন্ট ইতিমধ্যে যুক্ত আছে! অনুগ্রহ করে ভিন্ন একটি নাম দিন (যেমন: {clean_name}_2)।", "error")
            return redirect(url_for("member_adder_page"))

    from video_collector.config import TG_API_ID, TG_API_HASH
    from telethon import TelegramClient
    from telethon.errors import (
        PhoneNumberBannedError,
        PhoneNumberInvalidError,
        FloodWaitError
    )

    try:
        async def _send():
            client = TelegramClient(session_path, TG_API_ID, TG_API_HASH)
            await client.connect()
            sent_code = await client.send_code_request(phone)
            await client.disconnect()
            return sent_code.phone_code_hash

        code_hash = run_async(_send())
        session["adder_pending_login"] = {
            "account_name": clean_name,
            "phone": phone,
            "phone_code_hash": code_hash
        }
        flash(f"📩 টেলিগ্রামে ৫ ডিজিটের কোড পাঠানো হয়েছে: {phone}। নিচে কোডটি দিয়ে লগইন সম্পন্ন করুন।", "success")
    except PhoneNumberBannedError:
        flash(f"❌ টেলিগ্রাম জানিয়েছে এই ফোন নাম্বারটি ({phone}) ব্যান করা আছে। অন্য সচল নাম্বার ব্যবহার করুন।", "error")
    except PhoneNumberInvalidError:
        flash(f"❌ ফোন নাম্বারটি ({phone}) সঠিক নয়। কান্ট্রি কোডসহ নাম্বার দিন (যেমন: +88017...)।", "error")
    except FloodWaitError as e:
        flash(f"⏳ টেলিগ্রাম নিরাপত্তা কারণে এই নাম্বারে {e.seconds} সেকেন্ড অপেক্ষা করতে বলা হয়েছে।", "error")
    except Exception as e:
        flash(f"❌ কোড পাঠাতে ব্যর্থ: {e}", "error")

    return redirect(url_for("member_adder_page"))


@app.route("/member-adder/login-verify-code", methods=["POST"])
@login_required
def member_adder_login_verify_code():
    pending = session.get("adder_pending_login")
    if not pending:
        flash("❌ কোনো পেন্ডিং লগইন পাওয়া যায়নি। পুনরায় চেষ্টা করুন।", "error")
        return redirect(url_for("member_adder_page"))

    raw_code = request.form.get("code", "").strip()
    two_fa_password = request.form.get("password", "").strip()

    # Clean code of non-digits
    code = re.sub(r"\D", "", raw_code)

    if not code:
        flash("❌ টেলিগ্রাম থেকে পাওয়া ৫ ডিজিটের কোডটি লিখুন", "error")
        return redirect(url_for("member_adder_page"))

    account_name = pending["account_name"]
    phone = pending["phone"]
    phone_code_hash = pending["phone_code_hash"]

    sessions_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sessions")
    session_path = os.path.join(sessions_dir, account_name)

    from video_collector.config import TG_API_ID, TG_API_HASH
    from telethon import TelegramClient
    from telethon.errors import (
        SessionPasswordNeededError,
        PhoneCodeInvalidError,
        PhoneCodeExpiredError,
        PasswordHashInvalidError,
        FloodWaitError
    )

    try:
        async def _verify():
            client = TelegramClient(session_path, TG_API_ID, TG_API_HASH)
            await client.connect()
            try:
                await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                if not two_fa_password:
                    raise SessionPasswordNeededError("এই একাউন্টে Two-Step Verification পাসওয়ার্ড চালু আছে। দয়া করে পাসওয়ার্ড দিন।")
                await client.sign_in(password=two_fa_password)
            me = await client.get_me()
            await client.disconnect()
            return me

        me = run_async(_verify())
        session.pop("adder_pending_login", None)

        # Register/update directly in member_adder_accounts DB table
        init_adder_accounts_table()
        _execute("""
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
        """, (account_name, phone, me.id, me.first_name, me.last_name or "", me.username or ""))

        # Auto-restart adder service in background so new account starts adding immediately!
        running, _ = is_adder_running()
        if running:
            start_adder_service()

        flash(f"🎉 একাউন্ট সফলভাবে যুক্ত হয়েছে: {me.first_name} (@{me.username or me.id})! ব্যাকগ্রাউন্ড সার্ভিস আপডেট হয়েছে।", "success")
    except SessionPasswordNeededError as e:
        flash(f"🔐 {e}", "error")
    except PhoneCodeInvalidError:
        flash("❌ আপনার দেওয়া ৫-ডিজিটের লগইন কোডটি সঠিক নয়। টেলিগ্রাম অ্যাপ দেখে সঠিক কোড দিন।", "error")
    except PhoneCodeExpiredError:
        flash("❌ কোডের মেয়াদ শেষ হয়ে গেছে। দয়া করে আবার নতুন কোড পাঠান।", "error")
    except PasswordHashInvalidError:
        flash("❌ আপনার দেওয়া Two-Step Verification পাসওয়ার্ডটি সঠিক নয়।", "error")
    except FloodWaitError as e:
        flash(f"⏳ অতিরিক্ত চেষ্টার কারণে টেলিগ্রাম {e.seconds} সেকেন্ড অপেক্ষা করতে বলেছে।", "error")
    except Exception as e:
        flash(f"❌ লগইন সম্পন্ন করতে ব্যর্থ: {e}", "error")

    return redirect(url_for("member_adder_page"))


@app.route("/member-adder/login-cancel", methods=["POST"])
@login_required
def member_adder_login_cancel():
    session.pop("adder_pending_login", None)
    flash("লগইন প্রক্রিয়া বাতিল করা হয়েছে।", "info")
    return redirect(url_for("member_adder_page"))


@app.route("/member-adder/delete-account/<account_name>", methods=["POST"])
@login_required
def member_adder_delete_account(account_name):
    clean_name = re.sub(r"[^\w\-]", "_", account_name).lower()
    sessions_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sessions")
    session_file = os.path.join(sessions_dir, clean_name + ".session")

    # Remove database record
    try:
        _execute("DELETE FROM member_adder_accounts WHERE account_name = %s", (clean_name,))
    except Exception:
        pass

    if os.path.exists(session_file):
        try:
            os.remove(session_file)
            flash(f"🗑️ একাউন্ট '{clean_name}' সফলভাবে ডিলিট করা হয়েছে।", "success")
            running, _ = is_adder_running()
            if running:
                start_adder_service()
        except Exception as e:
            flash(f"❌ সেশন ফাইল ডিলিট করতে ব্যর্থ: {e}", "error")
    else:
        flash(f"🗑️ একাউন্ট '{clean_name}' সফলভাবে রিমুভ করা হয়েছে।", "success")

    return redirect(url_for("member_adder_page"))


@app.route("/member-adder/service/<action>", methods=["POST"])
@login_required
def member_adder_service_action(action):
    if action == "start":
        start_adder_service()
        flash("▶️ মেম্বার অটো-অ্যাডার ব্যাকগ্রাউন্ডে সফলভাবে চালু করা হয়েছে!", "success")
    elif action == "stop":
        stop_adder_service()
        flash("⏹️ মেম্বার অটো-অ্যাডার সার্ভিস বন্ধ করা হয়েছে।", "success")
    elif action == "restart":
        start_adder_service()
        flash("🔄 মেম্বার অটো-অ্যাডার সার্ভিস রিস্টার্ট দেওয়া হয়েছে।", "success")
    return redirect(url_for("member_adder_page"))


@app.route("/api/member-adder/status", methods=["GET"])
@login_required
def api_member_adder_status():
    running, pids = is_adder_running()
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_file = os.path.join(project_dir, "auto_adder.log")
    logs = ""
    if os.path.exists(log_file):
        try:
            file_size = os.path.getsize(log_file)
            bytes_to_read = min(file_size, 32768)  # Read up to last 32 KB
            with open(log_file, "rb") as f:
                if file_size > bytes_to_read:
                    f.seek(file_size - bytes_to_read)
                tail_bytes = f.read()
            tail_text = tail_bytes.decode("utf-8", errors="ignore")
            lines = tail_text.splitlines(keepends=True)
            logs = "".join(lines[-45:])
        except Exception as e:
            logs = f"Error reading log: {e}"
    else:
        logs = "এখনো কোনো লগ তৈরি হয়নি।"
    return jsonify({
        "running": running,
        "pids": pids,
        "logs": logs
    })



# ── Portal & Video Management Routes ────────────────

UPLOAD_VIDEO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", "videos")
os.makedirs(UPLOAD_VIDEO_DIR, exist_ok=True)
ALLOWED_VIDEO_EXT = {"mp4", "webm", "ogg", "mov", "m4v"}


def get_portal_settings():
    try:
        rows = _query("SELECT setting_key, setting_val FROM portal_settings", fetchall=True)
        return {r["setting_key"]: r["setting_val"] for r in (rows or [])}
    except Exception:
        return {}


@app.route("/portal_admin", methods=["GET"])
@login_required
def portal_admin():
    # Load categories with video count
    try:
        categories = _query("""
            SELECT c.*, COUNT(v.id) AS video_count 
            FROM portal_categories c 
            LEFT JOIN portal_videos v ON c.slug = v.category_slug 
            GROUP BY c.id 
            ORDER BY c.order_num ASC, c.id ASC
        """, fetchall=True) or []
    except Exception:
        categories = []

    # Load videos
    try:
        videos = _query("SELECT * FROM portal_videos ORDER BY id DESC", fetchall=True) or []
    except Exception:
        videos = []

    settings = get_portal_settings()
    active_videos_count = sum(1 for v in videos if v.get("is_active") == 1)

    return render_template(
        "portal_admin.html",
        active="portal_admin",
        categories=categories,
        videos=videos,
        settings=settings,
        active_videos_count=active_videos_count
    )


@app.route("/portal/add_category", methods=["POST"])
@login_required
def portal_add_category():
    name = request.form.get("name", "").strip()
    slug = request.form.get("slug", "").strip().lower()
    icon = request.form.get("icon", "fa-fire").strip()
    try:
        order_num = int(request.form.get("order_num", 0))
    except (ValueError, TypeError):
        order_num = 0

    if not name or not slug:
        flash("❌ ক্যাটেগরির নাম এবং স্লাগ অবশ্যই পূরণ করতে হবে।", "error")
        return redirect(url_for("portal_admin"))

    # sanitize slug
    slug = re.sub(r"[^a-z0-9_-]", "", slug)

    try:
        _execute(
            "INSERT INTO portal_categories (name, slug, icon, order_num) VALUES (%s, %s, %s, %s)",
            (name, slug, icon, order_num)
        )
        flash(f"✅ ক্যাটেগরি '{name}' সফলভাবে যুক্ত হয়েছে।", "success")
    except Exception as e:
        flash(f"❌ ক্যাটেগরি যোগ করতে সমস্যা হয়েছে: {e}", "error")

    return redirect(url_for("portal_admin"))


@app.route("/portal/delete_category/<int:cat_id>", methods=["GET", "POST"])
@login_required
def portal_delete_category(cat_id: int):
    try:
        _execute("DELETE FROM portal_categories WHERE id=%s", (cat_id,))
        flash("🗑️ ক্যাটেগরি সফলভাবে মুছে ফেলা হয়েছে।", "success")
    except Exception as e:
        flash(f"❌ ক্যাটেগরি ডিলিট ব্যর্থ: {e}", "error")
    return redirect(url_for("portal_admin"))


@app.route("/portal/add_video", methods=["POST"])
@login_required
def portal_add_video():
    title = request.form.get("title", "").strip()
    category_slug = request.form.get("category_slug", "").strip()
    duration = request.form.get("duration", "04:15").strip()
    direct_url = request.form.get("video_url", "").strip()
    thumb_url = request.form.get("thumb_url", "").strip()
    keywords = request.form.get("keywords", "").strip()

    if not title or not category_slug:
        flash("❌ টাইটেল এবং ক্যাটেগরি প্রদান করুন।", "error")
        return redirect(url_for("portal_admin"))

    video_url = ""
    # Check if a file was uploaded
    if "video_file" in request.files:
        file = request.files["video_file"]
        if file and file.filename:
            fname = file.filename
            ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
            if ext in ALLOWED_VIDEO_EXT:
                import time
                safe_name = f"vid_{int(time.time())}_{re.sub(r'[^a-zA-Z0-9_]', '', fname.rsplit('.', 1)[0])[:20]}.{ext}"
                dest_path = os.path.join(UPLOAD_VIDEO_DIR, safe_name)
                file.save(dest_path)
                video_url = f"uploads/videos/{safe_name}"
            else:
                flash("❌ শুধুমাত্র .mp4, .webm, .ogg বা .mov ফাইল সাপোর্টেড।", "error")
                return redirect(url_for("portal_admin"))

    if not video_url and direct_url:
        video_url = direct_url

    if not video_url:
        flash("❌ একটি ভিডিও ফাইল আপলোড করুন অথবা ভিডিওর ডিরেক্ট URL প্রদান করুন।", "error")
        return redirect(url_for("portal_admin"))

    import random
    initial_views = random.randint(1200, 9800)

    try:
        _execute("""
            INSERT INTO portal_videos (title, category_slug, video_url, thumb_url, duration, views, is_active, keywords)
            VALUES (%s, %s, %s, %s, %s, %s, 1, %s)
        """, (title, category_slug, video_url, thumb_url, duration, initial_views, keywords))

        # Enforce FIFO rotation: keep only latest 10 videos on portal
        _execute("""
            DELETE FROM portal_videos 
            WHERE id NOT IN (
                SELECT id FROM (
                    SELECT id FROM portal_videos ORDER BY id DESC LIMIT 10
                ) AS keep_rows
            )
        """)
        flash(f"✅ ভিডিও '{title}' সফলভাবে যোগ করা হয়েছে (সর্বশেষ ১০টি ভিডিও পোর্টাল রোটেট হচ্ছে)।", "success")
    except Exception as e:
        flash(f"❌ ভিডিও সংরক্ষণে সমস্যা হয়েছে: {e}", "error")

    return redirect(url_for("portal_admin"))


@app.route("/portal/toggle_video/<int:video_id>")
@login_required
def portal_toggle_video(video_id: int):
    try:
        vid = _query("SELECT is_active FROM portal_videos WHERE id=%s", (video_id,), fetchone=True)
        if vid:
            new_status = 0 if vid.get("is_active") == 1 else 1
            _execute("UPDATE portal_videos SET is_active=%s WHERE id=%s", (new_status, video_id))
            flash(f"🔄 ভিডিও স্ট্যাটাস আপডেট হয়েছে ({'একটিভ' if new_status==1 else 'বন্ধ'})।", "success")
    except Exception as e:
        flash(f"❌ স্ট্যাটাস পরিবর্তন ব্যর্থ: {e}", "error")
    return redirect(url_for("portal_admin"))


@app.route("/portal/delete_video/<int:video_id>")
@login_required
def portal_delete_video(video_id: int):
    try:
        vid = _query("SELECT video_url FROM portal_videos WHERE id=%s", (video_id,), fetchone=True)
        if vid and vid.get("video_url"):
            vurl = vid["video_url"]
            if vurl.startswith("uploads/videos/"):
                local_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), vurl)
                if os.path.exists(local_path):
                    try:
                        os.remove(local_path)
                    except Exception:
                        pass
        _execute("DELETE FROM portal_videos WHERE id=%s", (video_id,))
        flash("🗑️ ভিডিও সফলভাবে ডিলিট করা হয়েছে।", "success")
    except Exception as e:
        flash(f"❌ ভিডিও ডিলিট ব্যর্থ: {e}", "error")
    return redirect(url_for("portal_admin"))


@app.route("/portal/save_settings", methods=["POST"])
@login_required
def portal_save_settings():
    settings_to_update = {
        "portal_title": request.form.get("portal_title", "EXCLUSIVE DESI & VIRAL VAULT").strip(),
        "portal_blur": request.form.get("portal_blur", "15").strip(),
        "telegram_group_url": request.form.get("telegram_group_url", "https://t.me/darkfantasyloverzone").strip(),
        "popunder_enabled": "1" if request.form.get("popunder_enabled") == "1" else "0",
        "popunder_url": request.form.get("popunder_url", "").strip(),
        "popunder_script": request.form.get("popunder_script", "").strip(),
        "social_ad_enabled": "1" if request.form.get("social_ad_enabled") == "1" else "0",
        "social_ad_script": request.form.get("social_ad_script", "").strip()
    }

    try:
        for k, v in settings_to_update.items():
            _execute("INSERT INTO portal_settings (setting_key, setting_val) VALUES (%s, %s) ON DUPLICATE KEY UPDATE setting_val=%s", (k, v, v))
        flash("✅ পোর্টাল, পোপান্ডার ও সোশ্যাল অ্যাড সেটিংস সফলভাবে সংরক্ষিত হয়েছে।", "success")
    except Exception as e:
        flash(f"❌ সেটিংস সংরক্ষণে সমস্যা হয়েছে: {e}", "error")

    return redirect(url_for("portal_admin"))


@app.route("/api/portal-data", methods=["GET"])
def api_portal_data():
    try:
        categories = _query("SELECT name, slug, icon FROM portal_categories ORDER BY order_num ASC, id ASC", fetchall=True) or []
        videos = _query("SELECT id, title, category_slug, video_url, thumb_url, duration, views FROM portal_videos WHERE is_active=1 ORDER BY order_num ASC, id DESC LIMIT 25", fetchall=True) or []
        settings = get_portal_settings()
        return jsonify({
            "status": "success",
            "categories": categories,
            "videos": videos,
            "settings": settings
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/portal-view", methods=["POST"])
def api_portal_view():
    try:
        vid_id = request.form.get("video_id") or (request.get_json(silent=True) or {}).get("video_id")
        if vid_id:
            _execute("UPDATE portal_videos SET views = views + 1 WHERE id=%s", (int(vid_id),))
        return jsonify({"status": "success"})
    except Exception:
        return jsonify({"status": "error"}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)



