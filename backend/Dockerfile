# ============================================
# 后端 Dockerfile - Django REST API + Playwright + Chromium
# ============================================
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖 + Chromium 浏览器（用于 Web 自动化）
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Python 环境配置
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium \
    PLAYWRIGHT_BROWSERS_PATH=/usr/bin

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建必要目录
RUN mkdir -p /app/allure-results /app/media /app/static

# 暴露端口
EXPOSE 8000

# 启动：迁移数据库 → 初始化模型配置 → 启动服务
CMD ["sh", "-c", "\
    python manage.py migrate && \
    python seed_model_configs.py && \
    gunicorn ai_test_platform.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 4 \
        --timeout 120 \
        --access-logfile - \
        --error-logfile - \
    "]
