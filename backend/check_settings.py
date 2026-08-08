import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
import django; django.setup()
from django.conf import settings

print(f'provider: {getattr(settings, "MIDSCENE_AI_PROVIDER", "MISSING")}')
print(f'model:    {getattr(settings, "MIDSCENE_AI_MODEL", "MISSING")}')
k = getattr(settings, 'MIDSCENE_AI_API_KEY', 'MISSING')
print(f'api_key:  [{len(k) if isinstance(k,str) else 0} chars] {repr(k[:40]) if len(str(k)) > 5 else repr(k)}')
b = getattr(settings, 'MIDSCENE_AI_BASE_URL', 'MISSING')
print(f'base_url: {repr(b)}')
d = getattr(settings, 'DASHSCOPE_API_KEY', 'MISSING')
print(f'dashscope: [{len(d) if isinstance(d,str) else 0} chars] {repr(d[:40]) if len(str(d))>5 else repr(d)}')

# Also check env directly
print()
print('--- Direct os.getenv ---')
for name in ['MIDSCENE_AI_PROVIDER','MIDSCENE_AI_MODEL','MIDSCENE_AI_API_KEY','MIDSCENE_AI_BASE_URL']:
    v = os.getenv(name)
    print(f'{name}: [{len(v) if v else 0} chars] {repr((v or "")[:30])} ')
