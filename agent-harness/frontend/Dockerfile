# 多阶段构建：Vite 构建 + Nginx 托管
FROM node:20-alpine AS builder

WORKDIR /app

# 安装依赖（把 lockfile 里的 resolved URL 换成国内镜像，避免容器内 npm 超时）
COPY package.json package-lock.json ./
RUN npm install --no-audit --no-fund --platform=linux --arch=x64 --registry=https://registry.npmmirror.com

# 构建
COPY . .
# 强制清除 Vite/Rollup 缓存，确保源码修改一定进入构建产物
RUN rm -rf node_modules/.vite dist .vite
RUN npm run build

# 第二阶段：Nginx 托管静态资源
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
