# 多阶段构建：Vite 构建 + Nginx 托管
FROM node:20-alpine AS builder

WORKDIR /app

# 安装依赖（把 lockfile 里的 resolved URL 换成国内镜像，避免容器内 npm 超时）
COPY package.json package-lock.json ./
RUN npm install --no-audit --no-fund --platform=linux --arch=x64

# 构建
COPY . .
RUN npm run build

# 第二阶段：Nginx 托管静态资源
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
