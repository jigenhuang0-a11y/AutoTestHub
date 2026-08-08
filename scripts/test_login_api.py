"""诊断登录 API 返回数据"""
import requests
import json

r = requests.post('http://8.163.86.47:8000/api/auth/login/',
    json={'username': 'admin', 'password': 'admin123'}, timeout=10)

print(f'Status: {r.status_code}')
data = r.json()
print(f'Keys: {list(data.keys())}')
print(f'Has "access": {"access" in data}')
print(f'Has "refresh": {"refresh" in data}')
print(f'Has "user": {"user" in data}')

acc = data.get('access', 'MISSING')
print(f'access type/length: {type(acc).__name__} / {len(acc) if acc else 0}')
ref = data.get('refresh', 'MISSING')
print(f'refresh type/length: {type(ref).__name__} / {len(ref) if ref else 0}')

u = data.get('user')
if u:
    print(f'user keys: {list(u.keys())}')
    print(f'user.username: {u.get("username")}')
    print(f'user.role: {u.get("role")}')
    print(f'user.is_admin: {u.get("is_admin")}')

# 验证 token
if acc:
    r2 = requests.get('http://8.163.86.47:8000/api/auth/profile/',
        headers={'Authorization': f'Bearer {acc}'}, timeout=10)
    print(f'\nToken verify: {r2.status_code}')
    if r2.status_code == 200:
        print(f'Profile OK: {r2.json().get("username")}')
    else:
        print(f'Profile FAIL: {r2.text[:200]}')
