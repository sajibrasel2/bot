import pymysql
import time

conn = pymysql.connect(host='localhost', user='root', password='', db='techandc_tlbot')
cur = conn.cursor()
for i in range(6, 11):
    cur.execute("INSERT IGNORE INTO user_invites (chat_id, inviter_id, invited_id, timestamp) VALUES (-100123456, 777888999, %s, %s)", (1000 + i, int(time.time())))
conn.commit()
print("Total 10 test invites reached for user 777888999 / @testuser")
