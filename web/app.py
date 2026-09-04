"""
Web Admin Panel — Flask
Run : python web/app.py
URL : http://localhost:5000
Login: admin / (PANEL_PASSWORD from .env)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime as dt
import pymysql
import pymysql.cursors
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, flash
)
from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB

app = Flask(__name__)
# Fix #38: secret key from env, fallback to random bytes
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(24)

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
                    ("force_add_count", "INT DEFAULT 5")
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
    return _query("SELECT * FROM chat_settings WHERE chat_id=%s", (chat_id,), fetchone=True)


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
            return f.read()
    return "Landing page not found", 404


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
            "antilink_enabled":      1 if request.form.get("antilink_enabled")  else 0,
            "badwords_enabled":      1 if request.form.get("badwords_enabled")  else 0,
            "badwords_list":         request.form.get("badwords_list", "")[:2000],
            "antiforward_enabled":   1 if request.form.get("antiforward_enabled") else 0,
            "lock_media_msg":        1 if request.form.get("lock_media_msg") else 0,
            "lock_stickers":         1 if request.form.get("lock_stickers") else 0,
            "badword_strike_limit":  max(1, min(5, int(request.form.get("badword_strike_limit",  3) or 3))),
            "badword_mute_duration": max(60, int(request.form.get("badword_mute_duration", 60) or 60)),
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


# ── API ───────────────────────────────────────────

@app.route("/api/stats")
@login_required
def api_stats():
    return jsonify(get_stats())


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)


