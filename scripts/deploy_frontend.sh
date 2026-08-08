#!/usr/bin/env bash
# ============================================================
# 部署脚本 - 更新阿里云服务器前端
# 服务器: 8.163.86.47 (Ubuntu 22.04)
# ============================================================
# 用法：在本地 PowerShell 中执行以下命令
# ============================================================

# ---------- 1. 本地打包 dist 目录 ----------
# 已在本地完成: npm run build

# ---------- 2. 上传到服务器 ----------
# 方式A: 直接 scp (需要密码)
# scp -r D:\AI_Project\ai-test-platform\frontend\dist\ root@8.163.86.47:/opt/ai-test-platform/frontend/

# 方式B: 先压缩再上传 (推荐，更快)
# 本地 PowerShell:
#   Compress-Archive -Path D:\AI_Project\ai-test-platform\frontend\dist\* -DestinationPath D:\AI_Project\frontend-dist.zip -Force
#   scp D:\AI_Project\frontend-dist.zip root@8.163.86.47:/tmp/
# 服务器上:
#   unzip -o /tmp/frontend-dist.zip -d /opt/ai-test-platform/frontend/dist/

# ---------- 3. 服务器端更新 ----------
# 如果前端用 Docker (nginx 容器):
#   docker cp /opt/ai-test-platform/frontend/dist/. ai-test-frontend:/usr/share/nginx/html/
#   docker exec ai-test-frontend nginx -s reload

# 如果前端用 Django 静态文件:
#   cp -r /opt/ai-test-platform/frontend/dist/* /opt/ai-test-platform/backend/static/frontend/
#   cd /opt/ai-test-platform/backend && python manage.py collectstatic --noinput
#   systemctl restart gunicorn  # 或 supervisorctl restart gunicorn

# 如果前端用 Nginx 直接托管:
#   rsync -av --delete /opt/ai-test-platform/frontend/dist/ /var/www/ai-test-platform/
#   nginx -s reload

echo "部署脚本参考完成，请根据实际部署方式选择对应命令"
