#!/usr/bin/env bash
# ============================================================
# AI 测试平台 — 阿里云 ECS 一键部署脚本
# 适用：Ubuntu 22.04 / 20.04 全新 ECS
# 用法：
#   chmod +x deploy.sh
#   sudo ./deploy.sh
# 部署完成后访问：
#   主站      http://<你的公网IP>/
#   Langfuse  http://<你的公网IP>:3000   （或绑域名 langfuse.your-domain.com）
# ============================================================
set -euo pipefail

# ====================== 可配置项 ======================
# 改成你的 ECS 公网 IP 或域名（含 http:// 前缀、端口）。Langfuse 必须可达此地址才能登录。
PUBLIC_URL="${PUBLIC_URL:-http://$(curl -s ifconfig.me 2>/dev/null || echo localhost):3000}"
# Docker 镜像源（国内拉取加速，按需留空）
DOCKER_MIRROR="https://registry.cn-hangzhou.aliyuncs.com"
# =======================================================

echo "==> [1/6] 安装 Docker & Docker Compose"
if ! command -v docker >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg lsb-release
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  # 国内镜像加速
  mkdir -p /etc/docker
  cat > /etc/docker/daemon.json <<EOF
{ "registry-mirrors": ["${DOCKER_MIRROR}"] }
EOF
  systemctl daemon-reload && systemctl restart docker
fi
systemctl enable docker

echo "==> [2/6] 配置防火墙（放行端口）"
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 3000/tcp   # Langfuse Web
ufw allow 8080/tcp   # 前端（Nginx 未启用时备用）
ufw allow 8001/tcp   # 后端 API（Nginx 未启用时备用）
ufw --force enable || true

echo "==> [3/6] 生成生产 .env（覆盖 Langfuse 公网地址）"
# 在项目根目录执行；若从 git clone 拉取，请先 cd 到仓库根
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
echo "项目根目录: $ROOT"

if [ ! -f .env ]; then
  cp .env.example .env
fi

# 用 Python 安全替换/追加 Langfuse 公网地址（避免重复写入）
python3 - <<PY
import re, os
path = ".env"
s = open(path, encoding="utf-8").read()
url = os.environ.get("PUBLIC_URL", "${PUBLIC_URL}")
pairs = {
  "LANGFUSE_NEXTAUTH_URL": url,
  "LANGFUSE_BASE_URL": url,
}
for k, v in pairs.items():
    if re.search(rf"^{re.escape(k)}=.*", s, re.M):
        s = re.sub(rf"^{re.escape(k)}=.*", f"{k}={v}", s, flags=re.M)
    else:
        s += f"\n{k}={v}\n"
open(path, "w", encoding="utf-8").write(s)
print("已写入 LANGFUSE_NEXTAUTH_URL / LANGFUSE_BASE_URL =", url)
PY

echo "==> [4/6] 构建并启动全部服务（含 Langfuse）"
docker compose up -d --build

echo "==> [5/6] 等待服务健康"
sleep 20
docker compose ps

echo "==> [6/6] 部署完成"
cat <<EOF

========================================================
  部署完成 ✅
  主站 API:    http://<你的公网IP>:8001/api/v1/health
  前端:        http://<你的公网IP>:8080
  Langfuse:    ${PUBLIC_URL}   （默认账号 admin@langfuse.com / password，首次登录请改密）
  数据库/向量: 见 docker-compose.yml（postgres:5433 仅容器内，未对外暴露）
========================================================
  下一步建议：
  1. 进入 Langfuse 创建 Project，拿到 public/secret key
  2. 把 key 配到后端 .env 的 LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY
  3. 在 Eval Center 调用 Langfuse SDK 上报 trace + Judge LLM 评分
  4. （可选）部署 nginx-langfuse.conf 用域名反向代理 + HTTPS
========================================================
EOF
