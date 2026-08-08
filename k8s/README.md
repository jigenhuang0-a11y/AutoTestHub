# AI测试平台 K8s 部署指南

## 文件清单

```
k8s/
├── README.md                    # 本文件
├── 00-namespace.yaml            # 命名空间
├── 01-configmap.yaml            # 非敏感配置 + Nginx 配置（含 SSE 缓冲关闭）
├── 02-secrets.yaml              # 敏感信息（API Keys、密码）
├── 03-persistent-volumes.yaml   # PVC 持久化存储声明
├── 10-postgres.yaml             # PostgreSQL 16 StatefulSet
├── 11-redis.yaml                # Redis 7 Deployment
├── 12-etcd.yaml                 # etcd v3.5.5（Milvus 依赖）
├── 13-minio.yaml                # MinIO（Milvus 依赖）
├── 14-milvus.yaml               # Milvus 2.4 向量数据库
├── 20-backend.yaml              # Django Backend（Gunicorn, 2 replicas）
├── 21-celery.yaml               # Celery Worker（2 replicas）
├── 22-orchestrator.yaml         # AI 编排服务 FastAPI（2 replicas + Prometheus annotations）
├── 23-frontend.yaml             # Vue 3 前端（Nginx, 2 replicas）
├── 30-monitoring.yaml           # Prometheus + Grafana + OTEL Collector
├── 40-hpa.yaml                  # HPA 自动伸缩（backend/orchestrator/frontend/celery）
└── 50-ingress.yaml              # Ingress 统一入口路由
```

## 架构说明

```
                    ┌──────────────┐
                    │   Ingress    │  (TLS + 域名路由)
                    └──────┬───────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌──────────┐   ┌──────────┐   ┌──────────────┐
    │ Frontend │   │ Backend  │   │ Orchestrator │
    │  (Nginx) │   │ (Django) │   │  (FastAPI)   │
    │  2 pods  │   │  2 pods  │   │   2 pods     │
    └──────────┘   └────┬─────┘   └──────┬───────┘
                        │               │
        ┌───────────────┼───────┬───────┤
        ▼               ▼       ▼       ▼
   ┌─────────┐   ┌─────────┐ ┌──────┐ ┌──────────┐
   │Postgres │   │  Redis  │ │Milvus│ │Monitor   │
   │Stateful │   │  1 pod  │ │ 1 pod│ │Prom+Graf │
   └─────────┘   └─────────┘ └──────┘ │+OTEL Col │
                                      └──────────┘
```

## 快速部署

### 前提条件

- Kubernetes 集群 v1.26+（minikube / k3s / 云厂商托管集群）
- 已安装 Ingress Controller（nginx-ingress）
- 已安装 Metrics Server（HPA 依赖）
- kubectl 已配置连接到目标集群

### 1. 构建镜像

```bash
# Backend（Django + Playwright）
cd backend
docker build -t ai-test-platform-backend:latest .

# Frontend（Vue 3 + Nginx）
cd frontend
docker build -t ai-test-platform-frontend:latest .

# AI 编排服务
cd ai-orchestration-service
docker build -t ai-test-platform-orchestrator:latest .
```

### 2. 修改 Secrets

```bash
# 编辑 k8s/02-secrets.yaml，填入真实 API Key 和密码
vim k8s/02-secrets.yaml
```

### 3. 一键部署

```bash
# 按编号顺序 apply（基础设施 → 应用 → 监控 → 伸缩 → 路由）
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-configmap.yaml
kubectl apply -f k8s/02-secrets.yaml
kubectl apply -f k8s/03-persistent-volumes.yaml

# 等待 PVC 绑定（如使用 StorageClass，会自动创建 PV）
kubectl wait --for=jsonpath='{.status.phase}'=Bound pvc --all -n ai-test-platform --timeout=60s

# 部署基础设施
kubectl apply -f k8s/10-postgres.yaml
kubectl apply -f k8s/11-redis.yaml
kubectl apply -f k8s/12-etcd.yaml
kubectl apply -f k8s/13-minio.yaml
kubectl apply -f k8s/14-milvus.yaml

# 等待基础设施就绪
kubectl wait --for=condition=ready pod -l app=postgres -n ai-test-platform --timeout=120s
kubectl wait --for=condition=ready pod -l app=redis -n ai-test-platform --timeout=60s
kubectl wait --for=condition=ready pod -l app=milvus -n ai-test-platform --timeout=180s

# 部署应用服务
kubectl apply -f k8s/20-backend.yaml
kubectl apply -f k8s/21-celery.yaml
kubectl apply -f k8s/22-orchestrator.yaml
kubectl apply -f k8s/23-frontend.yaml

# 部署监控 + HPA + Ingress
kubectl apply -f k8s/30-monitoring.yaml
kubectl apply -f k8s/40-hpa.yaml
kubectl apply -f k8s/50-ingress.yaml

# 查看部署状态
kubectl get all -n ai-test-platform
```

### 4. 验证

```bash
# 健康检查
kubectl port-forward -n ai-test-platform svc/frontend 8080:80
curl http://localhost:8080/

# 编排服务
kubectl port-forward -n ai-test-platform svc/ai-orchestrator 8001:8001
curl http://localhost:8001/api/v1/health/live

# Prometheus
kubectl port-forward -n ai-test-platform svc/prometheus 9090:9090
# 浏览器打开 http://localhost:9090

# Grafana（默认 admin/admin）
kubectl port-forward -n ai-test-platform svc/grafana 3000:3000
# 浏览器打开 http://localhost:3000
```

## 关键配置说明

| 配置项 | 文件 | 说明 |
|--------|------|------|
| SSE 缓冲关闭 | `01-configmap.yaml` → nginx.conf | `/api/v1/workflow/stream` 和 `/resume` 路径关闭 `proxy_buffering` |
| Prometheus 抓取 | `22-orchestrator.yaml` → annotations | 编排服务 Pod 带 `prometheus.io/scrape: "true"` 注解 |
| HPA 阈值 | `40-hpa.yaml` | 编排服务 CPU 60% 触发扩容（最高 8 副本），后端 70% |
| OTEL 链路追踪 | `30-monitoring.yaml` → otel-collector | 编排服务的 OTLP 数据 → Collector → 日志输出（可接 Jaeger） |
| TLS | `50-ingress.yaml` | 默认注释掉，生产环境取消注释并配置 cert-manager |

## 面试话术

> "平台的 K8s 部署清单覆盖了 9 个核心服务，包括 PostgreSQL、Redis、Milvus 等有状态服务用 StatefulSet + PVC，
> 无状态服务（backend/orchestrator/frontend/celery）用 Deployment + HPA 自动伸缩。
> Nginx Ingress 做统一入口，SSE 流式端点的 proxy_buffering 已关闭。
> Prometheus + Grafana + OpenTelemetry Collector 构成完整的可观测三件套。"

## 常见问题

### Q: 本地如何测试 K8s 部署？
```bash
# 使用 minikube
minikube start --cpus=4 --memory=8192
kubectl apply -f k8s/

# 使用 k3s（轻量，推荐）
curl -sfL https://get.k3s.io | sh -
kubectl apply -f k8s/
```

### Q: StorageClass 不存在导致 PVC 挂起？
```bash
# minikube 默认有 standard StorageClass
kubectl get storageclass

# k3s 使用 local-path
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml
```

### Q: 镜像拉取策略？
清单中默认 `imagePullPolicy: IfNotPresent`（本地开发）。
推送到镜像仓库后改为 `Always` 或指定 tag。
