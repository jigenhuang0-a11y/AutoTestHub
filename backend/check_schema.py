import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
import django
django.setup()

from django.db import connection
with connection.cursor() as c:
    c.execute("PRAGMA table_info(perf_test_cases)")
    print('=== perf_test_cases columns ===')
    for row in c.fetchall():
        print(row[1], row[2])
    
    c.execute("PRAGMA table_info(perf_executions)")
    print('\n=== perf_executions columns ===')
    for row in c.fetchall():
        print(row[1], row[2])
