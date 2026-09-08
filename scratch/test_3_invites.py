import pymysql
import time

conn = pymysql.connect(host='localhost', user='root', password='', db='techandc_tlbot')
cur = conn.cursor()
cur.execute("INSERT IGNORE INTO users (user_id, chat_id, username, first_name) VALUES (555666777, -100123456, 'three_invites', 'User With 3')")
for i in range(1, 4):
    cur.execute("INSERT IGNORE INTO user_invites (chat_id, inviter_id, invited_id, timestamp) VALUES (-100123456, 555666777, %s, %s)", (2000 + i, int(time.time())))
conn.commit()
print("3 test invites inserted for user 555666777")
