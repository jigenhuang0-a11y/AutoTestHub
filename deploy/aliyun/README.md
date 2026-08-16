# 阿里云部署 AI 测试平台（含 Langfuse 可观测）

> 目标：把课程里讲的 **Langfuse 自托管 + 智能体评估** 落地到你的全链路评测中心。
> 你项目里 `docker-compose.yml` 已经集成了 Langfuse（2 核服务 `langfuse:3000`，复用 postgres + redis），所以上云 = 把这套 compose 跑在 ECS 上 + 配好公网地址 + 反代。

---

## 一、购买阿里云 ECS（第一步）

| 项 | 推荐配置 | 说明 |
|---|---|---|
| 实例规格 | **4 核 8G**（ecs.g7 或共享型）起步；预算紧可 2 核 4G 先跑通 | Langfuse + postgres + milvus 较吃内存 |
| 镜像 | Ubuntu 22.04 64 位 | |
| 系统盘 | 100G 高效云盘 | 镜像 + 向量数据 |
| 带宽 | 按量 3~5 Mbps 或固定 5M | 内网评估够用 |
| 安全组 | 放行 22/80/443/3000/8080/8001 | 脚本会自动配 ufw |
| 地域 | 选离你近的（如杭州） | 后续接 DashScope 同地域更稳 |

> 备注：如果只是本地验证，可以完全不买机器，直接在本地 `docker compose up -d` 即可。

---

## 二、一键部署

把整个仓库上传/克隆到 ECS，进入根目录执行：

```bash
cd ai-test-platform
sudo bash deploy/aliyun/deploy.sh
```

脚本会自动：
1. 安装 Docker + Compose（含阿里云镜像加速）
2. 配置 ufw 防火墙放行端口
3. 由 `.env.example` 生成 `.env`，并把 `LANGFUSE_NEXTAUTH_URL` / `LANGFUSE_BASE_URL` 改成你的**公网地址**（否则 Langfuse 登录回调失败）
4. `docker compose up -d --build` 拉起全部服务
5. 打印访问地址

### 手动指定公网地址（可选）
```bash
PUBLIC_URL=http://47.x.x.x:3000 sudo -E bash deploy/aliyun/deploy.sh
```

---

## 三、验证

```bash
docker compose ps            # 所有服务状态为 healthy/running
curl http://localhost:8001/api/v1/health   # 后端健康
# 浏览器打开 http://<公网IP>:3000  → Langfuse 登录页
```

Langfuse 默认管理员账号（首次启动创建）：
- 邮箱：`admin@langfuse.com`
- 密码：`password`
- **首次登录务必改密**

---

## 四、接入你的全链路评测中心

Langfuse 跑起来后，把评估链路接进去：

### 1. 在 Langfuse 后台建 Project，拿到 key
设置 → API Keys → 复制 `public_key` / `secret_key`。

### 2. 后端上报 trace（在 Eval Center 的评分逻辑里埋点）
```python
from langfuse import Langfuse
langfuse = Langfuse(
    public_key="pk-...",
    secret_key="sk-...",
    host="http://<你的公网IP>:3000",
)
trace = langfuse.trace(name="eval-case")
trace.generation(
    name="judge-llm",
    model="deepseek-chat",
    input=prompt,
    output=response,
    model_parameters={"temperature": 0},
)
langfuse.flush()
```

### 3. Judge LLM 评分写回
用另一个 LLM 对输出打"幻觉率/完整性/安全性"等维度分，调用 Langfuse SDK 的 `trace.score(...)` 写回，前端即可在 Eval Center 拉取趋势。

---

## 五、生产加固（上线前必做）

1. **改密钥**：`.env` 里所有 `change-me-*`、`LANGFUSE_SALT`、`LANGFUSE_NEXTAUTH_SECRET`、`LANGFUSE_ENCRYPTION_KEY` 都要换成 `openssl rand -hex 32` 强随机值。
2. **HTTPS**：部署 `deploy/aliyun/nginx-langfuse.conf`，用 Nginx 反代 + Let's Encrypt 证书，把 Langfuse 和主站都走 443。
3. **数据库不对外**：compose 里 postgres 映射 `5433` 仅容器内网，ECS 安全组不要放行 5432/5433。
4. **关掉遥测**：compose 已设 `TELEMETRY_ENABLED=false`。

---

## 六、目录说明

```
deploy/aliyun/
├── deploy.sh            # 一键部署脚本（ECS 上跑）
├── nginx-langfuse.conf  # Nginx 反代配置（主站 + Langfuse 子域名）
└── README.md            # 本文件
```
