import os, sys
os.chdir('/app')
sys.path.insert(0, '/app')
os.environ['DJANGO_SETTINGS_MODULE'] = 'ai_test_platform.settings'
import django
django.setup()
from django.db import connection
cursor = connection.cursor()
cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE '%demo%'")
print("Demo tables:", cursor.fetchall())

cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='demo_products'")
print("demo_products exists:", bool(cursor.fetchall()))
