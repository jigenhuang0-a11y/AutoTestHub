import subprocess, time, sys, os

os.chdir(r'd:\AI_Project\ai-test-platform\backend')

# 先确认没有其他python进程
try:
    subprocess.run(['taskkill', '/F', '/IM', 'python.exe'], capture_output=True)
    time.sleep(1)
except:
    pass

# 启动 Django 服务器
p = subprocess.Popen(
    ['python', 'manage.py', 'runserver', '0.0.0.0:8000'],
    stdout=open('../backend_run.log', 'w'),
    stderr=open('../backend_error.log', 'w'),
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
)
print(f"Django started at PID {p.pid}")
time.sleep(3)
print("✅ 服务器已重启，请刷新 http://localhost:8000")
