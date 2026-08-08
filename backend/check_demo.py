import os, sys, time
os.chdir('/app')
sys.path.insert(0, '/app')
os.environ['DJANGO_SETTINGS_MODULE'] = 'ai_test_platform.settings'

print("Starting Django setup...", flush=True)
start = time.time()

import django
try:
    django.setup()
except Exception as e:
    print(f"Setup failed after {time.time()-start:.1f}s: {type(e).__name__}: {e}", flush=True)
    raise

elapsed = time.time() - start
print(f"Django setup OK ({elapsed:.1f}s)", flush=True)

from django.db import connection
cursor = connection.cursor()
cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE '%demo%'")
print("Demo tables:", cursor.fetchall(), flush=True)

cursor.execute("SELECT COUNT(*) FROM demo_products")
print("Products count:", cursor.fetchone()[0], flush=True)
