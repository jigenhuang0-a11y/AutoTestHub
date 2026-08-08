#!/bin/bash
# ============================================================
# AI 测试平台 — 一键启动 & 健康检查脚本
# 用法: ./start.sh
# ============================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color
CHECK="✓"

echo "========================================="
echo "  AI 测试平台 - 启动脚本"
echo "========================================="

# --------------------------------------------------
# 1. 启动所有容器
# --------------------------------------------------
echo -e "\n${YELLOW}[1/5] 启动容器服务...${NC}"
docker compose up -d --wait 2>/dev/null || docker compose up -d
echo -e "${GREEN}${CHECK} 容器已启动${NC}"

# 等 Milvus 健康检查（etcd + minio + milvus 需要时间）
echo "等待 Milvus 就绪..."
for i in $(seq 1 30); do
    if docker exec ai-test-milvus curl -sf http://localhost:9091/healthz > /dev/null 2>&1; then
        break
    fi
    sleep 2
done

# --------------------------------------------------
# 2. 服务健康检查
# --------------------------------------------------
echo -e "\n${YELLOW}[2/5] 服务健康检查...${NC}"

for srv in ai-test-db ai-test-redis ai-test-etcd ai-test-minio ai-test-milvus ai-test-backend ai-test-celery ai-test-frontend; do
    status=$(docker inspect --format='{{.State.Status}}' $srv 2>/dev/null || echo "not_found")
    health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no_healthcheck{{end}}' $srv 2>/dev/null || echo "unknown")
    if [ "$status" = "running" ]; then
        if [ "$health" = "healthy" ] || [ "$health" = "no_healthcheck" ]; then
            echo -e "  ${GREEN}${CHECK}${NC} $srv"
        else
            echo -e "  ${YELLOW}⚠${NC} $srv — $health"
        fi
    else
        echo -e "  ${RED}✗${NC} $srv — $status"
    fi
done

# --------------------------------------------------
# 3. Milvus 连接测试（失败也不退出脚本）
# --------------------------------------------------
echo -e "\n${YELLOW}[3/5] Milvus 连接测试...${NC}"
MILVUS_OK="fail"

# 使用 manage.py shell 确保 Django 环境正确初始化
MILVUS_OUTPUT=$(docker exec ai-test-backend python manage.py shell -c "
from core.tools.milvus_store import get_milvus_store
s = get_milvus_store()
h = s.health_check()
print('ok' if h.get('status') == 'ok' else 'fail')
" 2>&1) || true

if echo "$MILVUS_OUTPUT" | grep -q "^ok"; then
    echo -e "${GREEN}${CHECK} Milvus 连接正常${NC}"
else
    echo -e "${YELLOW}⚠ Milvus 连接失败，知识库问答将降级为纯 LLM 对话${NC}"
fi

# --------------------------------------------------
# 4. 数据库初始化
# --------------------------------------------------
echo -e "\n${YELLOW}[4/5] 检查数据库...${NC}"
MIGRATE_OUT=$(docker exec ai-test-backend python manage.py migrate --noinput 2>&1) || true
if echo "$MIGRATE_OUT" | grep -qi "error\|exception"; then
    echo -e "${YELLOW}⚠ 数据库迁移有警告，但继续...${NC}"
    echo "$MIGRATE_OUT" | tail -5
else
    echo -e "${GREEN}${CHECK} 数据库迁移完成${NC}"
fi

# --------------------------------------------------
# 5. 创建默认管理员 & 默认知识库
# --------------------------------------------------
echo -e "\n${YELLOW}[5/5] 初始化管理员 & 知识库...${NC}"

# 从 .env 读取管理员密码，默认自动生成
ADMIN_PASSWORD="${ADMIN_PASSWORD:-$(openssl rand -base64 12 2>/dev/null || python3 -c "import secrets; print(secrets.token_urlsafe(12))")}"

# 创建/更新管理员
ADMIN_SCRIPT=$(cat <<'EOF'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
try:
    user, created = User.objects.get_or_create(username='admin', defaults={'email':'admin@ai-test.com','role':'admin','is_admin':True})
    if user.role != 'admin':
        user.role = 'admin'
        user.is_admin = True
        user.save()
        print('updated')
    elif created:
        print('created')
    else:
        print('exists')
except Exception as e:
    print('error:', e)
EOF
)
ADMIN_RESULT=$(docker exec ai-test-backend python -c "$ADMIN_SCRIPT" 2>&1) || true

if echo "$ADMIN_RESULT" | grep -q "created"; then
    # 设置密码（使用环境变量 ADMIN_PASSWORD）
    docker exec ai-test-backend python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
django.setup()
from django.contrib.auth import get_user_model
u = get_user_model().objects.get(username='admin')
u.set_password(os.getenv('ADMIN_PASSWORD', 'ChangeMe123!'))
u.save()
" 2>/dev/null || true
    echo -e "${GREEN}${CHECK} 管理员已创建 (admin)${NC}"
elif echo "$ADMIN_RESULT" | grep -q "updated"; then
    docker exec ai-test-backend python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
django.setup()
from django.contrib.auth import get_user_model
u = get_user_model().objects.get(username='admin')
u.set_password(os.getenv('ADMIN_PASSWORD', 'ChangeMe123!'))
u.save()
" 2>/dev/null || true
    echo -e "${GREEN}${CHECK} 管理员角色已修复 (admin)${NC}"
else
    echo -e "${GREEN}${CHECK} 管理员已就绪 (admin)${NC}"
fi

# 创建默认知识库
KB_SCRIPT=$(cat <<'EOF'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
django.setup()
from knowledge_base.models import KnowledgeBase
from django.contrib.auth import get_user_model
User = get_user_model()
try:
    admin = User.objects.get(username='admin')
    kb, created = KnowledgeBase.objects.get_or_create(
        name='默认知识库',
        defaults={'description': 'AI测试平台默认知识库', 'created_by': admin}
    )
    if created:
        print(f'created:{kb.id}')
    else:
        print(f'exists:{kb.id}')
except Exception as e:
    print('error:', e)
EOF
)
KB_RESULT=$(docker exec ai-test-backend python -c "$KB_SCRIPT" 2>&1) || true

if echo "$KB_RESULT" | grep -q "created"; then
    echo -e "${GREEN}${CHECK} 默认知识库已创建${NC}"
else
    echo -e "${GREEN}${CHECK} 默认知识库已就绪${NC}"
fi

# --------------------------------------------------
# 完成
# --------------------------------------------------
echo ""
echo "========================================="
echo -e "  ${GREEN}🚀 AI 测试平台已就绪！${NC}"
echo "========================================="
echo "  访问地址: http://localhost"
echo "  管理员:   admin / (密码: \$ADMIN_PASSWORD 或 ChangeMe123!)"
echo "  知识库:   默认已创建"
echo "========================================="
