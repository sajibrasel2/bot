"""
Automated 3-Hour Diagnostic & Activity Analyzer for Telegram Bot
Analyzes bot.log, Database settings, User activities, and System health.
"""

import os
import re
import sys
from datetime import datetime, timedelta

def main():
    log_file = "bot.log"
    if not os.path.exists(log_file):
        log_file = "/home/techandc/public_html/bot/bot.log"

    print("=" * 65)
    print(" 🚀 TELEGRAM BOT 3-HOUR COMPREHENSIVE ACTIVITY & LOG AUDIT")
    print("=" * 65)

    # 1. Parse log file
    if not os.path.exists(log_file):
        print(f"⚠️ Log file not found at: {log_file}")
        lines = []
    else:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

    total_lines = len(lines)
    print(f"📁 Log File: {log_file} (Total lines: {total_lines:,})")

    # Metrics counters
    conflicts = 0
    http_200 = 0
    bad_requests = []
    delete_messages = 0
    send_messages = 0
    send_stickers = 0
    forceadd_checks = 0
    forceadd_enabled_checks = 0
    forceadd_disabled_checks = 0
    forceadd_locks = []
    new_invites_tracked = []
    callback_queries = 0
    promo_tags = 0
    all_errors = []
    unique_users_active = set()
    chats_active = set()

    # Grab the recent lines (last 3000)
    analyzed_lines = lines[-3500:] if len(lines) > 3500 else lines

    for idx, line in enumerate(analyzed_lines):
        line_str = line.strip()

        if "409 Conflict" in line_str:
            conflicts += 1
        if "HTTP/1.1 200 OK" in line_str:
            http_200 += 1
        if "HTTP/1.1 400 Bad Request" in line_str:
            bad_requests.append(line_str)
        if "/deleteMessage" in line_str:
            delete_messages += 1
        if "/sendMessage" in line_str:
            send_messages += 1
        if "/sendSticker" in line_str:
            send_stickers += 1
        if "/answerCallbackQuery" in line_str:
            callback_queries += 1

        if " | ERROR | " in line_str:
            all_errors.append(line_str)

        # Extract ForceAdd details
        if "ForceAdd check:" in line_str:
            forceadd_checks += 1
            if "enabled=1" in line_str:
                forceadd_enabled_checks += 1
            else:
                forceadd_disabled_checks += 1
            
            # Extract user & chat
            m = re.search(r"user=(\d+).*?chat=(-?\d+)", line_str)
            if m:
                unique_users_active.add(m.group(1))
                chats_active.add(m.group(2))

        if "⛔ ForceAdd Locking" in line_str:
            forceadd_locks.append(line_str)

    print("\n" + "─" * 65)
    print(" 📊 [1] LOG & TELEGRAM API ACTIVITY SUMMARY")
    print("─" * 65)
    print(f" • Total API Success (200 OK)  : {http_200:,} calls")
    print(f" • Messages Deleted (Mod/Lock) : {delete_messages:,} times")
    print(f" • Messages Sent (Bot alerts)  : {send_messages:,} times")
    print(f" • Stickers Sent (Promo)       : {send_stickers:,} times")
    print(f" • Inline Buttons Clicked      : {callback_queries:,} interactions")
    print(f" • Active Group Chats Recorded : {len(chats_active)}")
    print(f" • Active Unique Members Seen  : {len(unique_users_active)}")
    print(f" • 409 Conflicts in Log Period : {conflicts} (Duplicate background process)")
    if bad_requests:
        print(f" • 400 Bad Requests Encountered: {len(bad_requests)}")
        for br in bad_requests[-3:]:
            print(f"    └─ {br}")

    print("\n" + "─" * 65)
    print(" 🔒 [2] FORCE ADD & CHAT UNLOCK ACTIVITY")
    print("─" * 65)
    print(f" • Total Message Checks        : {forceadd_checks}")
    print(f"   ├─ Checked when Enabled (1) : {forceadd_enabled_checks}")
    print(f"   └─ Checked when Disabled (0): {forceadd_disabled_checks}")
    print(f" • Total Users Locked (0/target): {len(forceadd_locks)}")
    if forceadd_locks:
        print("   Recent Lock Events:")
        for lk in forceadd_locks[-3:]:
            print(f"    - {lk}")

    # 3. Database Check
    print("\n" + "─" * 65)
    print(" 🗄️ [3] DATABASE & DASHBOARD SETTINGS STATE")
    print("─" * 65)
    try:
        import pymysql
        from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB

        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB,
            cursorclass=pymysql.cursors.DictCursor
        )
        cur = conn.cursor()

        # Chat Settings
        cur.execute("SELECT chat_id, chat_title, force_add_enabled, force_add_count, promo_sticker, antiflood_enabled, antilink_enabled, welcome_enabled FROM chat_settings")
        groups = cur.fetchall()
        print(f" • Total Connected Groups in DB: {len(groups)}")
        for g in groups:
            fa_st = "✅ ON" if g.get("force_add_enabled") == 1 else "❌ OFF"
            fa_cnt = g.get("force_add_count", 0)
            stk = "Custom ✅" if g.get("promo_sticker") else "None (Default)"
            w_st = "ON" if g.get("welcome_enabled") else "OFF"
            fl_st = "ON" if g.get("antiflood_enabled") else "OFF"
            ln_st = "ON" if g.get("antilink_enabled") else "OFF"
            print(f"   📌 Group: '{g.get('chat_title') or 'Untitled'}' (ID: {g['chat_id']})")
            print(f"      ├─ ForceAdd    : {fa_st} (Req: {fa_cnt} friends)")
            print(f"      ├─ PromoSticker: {stk}")
            print(f"      └─ Welcome: {w_st} | AntiFlood: {fl_st} | AntiLink: {ln_st}")

        # Top Inviters
        cur.execute("""
            SELECT ui.chat_id, ui.inviter_id, COUNT(*) as invite_count, u.first_name, u.username
            FROM user_invites ui
            LEFT JOIN users u ON ui.inviter_id = u.user_id
            GROUP BY ui.chat_id, ui.inviter_id
            ORDER BY invite_count DESC
            LIMIT 5
        """)
        top_invs = cur.fetchall()
        print("\n • 🏆 Top Inviters in Database:")
        if top_invs:
            for i, row in enumerate(top_invs, 1):
                name = row.get("first_name") or f"User {row['inviter_id']}"
                uname = f" (@{row['username']})" if row.get("username") else ""
                print(f"   {i}. {name}{uname} ─ {row['invite_count']} invites (Chat: {row['chat_id']})")
        else:
            print("   (No invites recorded yet)")

        # Total Users
        cur.execute("SELECT COUNT(*) as total_users FROM users")
        u_cnt = cur.fetchone()["total_users"]
        print(f"\n • Total Registered Users in DB: {u_cnt:,}")

        # Active Warns
        cur.execute("SELECT COUNT(*) as total_warns FROM warns")
        w_cnt = cur.fetchone()["total_warns"]
        print(f" • Total Active Warnings: {w_cnt}")

        conn.close()
    except Exception as db_err:
        print(f"⚠️ Could not query database: {db_err}")

    print("\n" + "─" * 65)
    print(" 📋 [4] RECENT 10 SIGNIFICANT LOG ACTIONS")
    print("─" * 65)
    sig_lines = [l.strip() for l in analyzed_lines if any(k in l for k in ["ForceAdd", "sendSticker", "Locked", "Bad Request"])]
    for sl in sig_lines[-10:]:
        print(f" • {sl}")

    print("\n" + "=" * 65)
    print(" ✅ AUDIT REPORT COMPLETE")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    main()
