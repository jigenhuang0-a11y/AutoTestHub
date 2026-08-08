import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'ai_test_platform.settings'
django.setup()
from testcases.models import TestCase
cases = TestCase.objects.all().values('id', 'title', 'status', 'api_endpoint', 'method')[:10]
for c in cases:
    print(f"ID={c['id']}, status={c['status']}, method={c['method']}, endpoint={c['api_endpoint'][:50]}")
print(f"Total: {TestCase.objects.count()}")
