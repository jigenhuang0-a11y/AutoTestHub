# ============================================
# 前端 Dockerfile - Vue3 + Vite
# ============================================
# 作用：把 Vue3 前端打包成静态文件，用 Nginx 托管
# 面试话术："前端用多阶段构建，npm build 后只保留 dist 产物，Nginx 做静态服务和反向代理"
# ============================================

# ---------- 阶段1：构建 ----------
FROM node:20-alpine AS builder

WORKDIR /app

# 先复制 package.json（利用缓存层）
COPY package.json package-lock.json ./

# 安装依赖（使用国内镜像加速）
RUN npm ci --registry=https://registry.npmmirror.com

# 复制源码并构建
COPY . .
RUN npm run build

# ---------- 阶段2：Nginx 托管 ----------
FROM nginx:alpine

# 复制构建产物到 Nginx 静态目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 Nginx 配置（含 API 反向代理）
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
