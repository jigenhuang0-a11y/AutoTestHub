import sqlite3, sys
conn = sqlite3.connect('db.sqlite3')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'perf_%'")
for row in c.fetchall():
    print(row[0])
conn.close()
