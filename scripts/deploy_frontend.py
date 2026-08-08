#!/usr/bin/env python3
"""部署前端到阿里云服务器"""
import paramiko
import os
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HOST = '8.163.86.47'
USER = 'root'
PWD = 'Hjg123456'
LOCAL_ZIP = r'd:\AI_Project\ai-test-platform\frontend-dist.zip'
REMOTE_ZIP = '/tmp/frontend-dist.zip'
PROJECT_DIR = '/opt/ai-test-platform'

print('=== 1. 上传前端 zip ===')
transport = paramiko.Transport((HOST, 22))
transport.connect(username=USER, password=PWD)
sftp = paramiko.SFTPClient.from_transport(transport)
sftp.put(LOCAL_ZIP, REMOTE_ZIP)
sftp.close()
print('上传完成')

print('=== 2. 服务器端解压部署 ===')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=30)

cmds = [
    f'cd {PROJECT_DIR}',
    f'unzip -o {REMOTE_ZIP} -d frontend/dist/',
    f'rm -rf backend/static/frontend',
    f'mkdir -p backend/static',
    f'cp -r frontend/dist/* backend/static/',
    f'cd backend && python manage.py collectstatic --clear --noinput 2>&1 | tail -5',
    'pkill -f "gunicorn.*8000" || echo "no gunicorn running"',
    'sleep 2',
    'cd /opt/ai-test-platform/backend && nohup gunicorn ai_test_platform.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120 > gunicorn.log 2>&1 &',
    'echo "部署完成"',
]

for cmd in cmds:
    print(f'> {cmd[:80]}')
    _, out, err = ssh.exec_command(cmd, timeout=30)
    out_str = out.read().decode('utf-8', errors='replace')
    err_str = err.read().decode('utf-8', errors='replace')
    if out_str.strip():
        print(out_str.strip()[:500])
    if err_str.strip():
        print(f'[ERR] {err_str.strip()[:200]}')

ssh.close()
print('\n=== 部署完毕 ===')
print('请用 Ctrl+Shift+R 硬刷新: http://8.163.86.47:8000/knowledge/')
print('验证新文件: ls -lh /opt/ai-test-platform/backend/static/assets/KnowledgeChat-*.js')
