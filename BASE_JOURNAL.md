# 底座建设日记：从零到服务间认证打通

> 项目核心卖点——不是代码，是"为什么这么做、踩了什么坑、怎么解决的"
> 适合于：面试讲项目难点、技术方案设计题、架构演进故事
>
> **⚠️ 本文档为本地保留，不推 GitHub**

**目录**
1. [起点：两套大脑的混乱](#一起点两套大脑的混乱)
2. [测试方法论](#二测试方法论用接口测试的思路验证底座)
3. [实战踩坑记录](#三实战踩坑记录)
4. [关键设计决策速查表](#四关键设计决策速查表)
5. [当前状态总览](#五当前状态总览)
6. [面试怎么讲这些](#六面试怎么讲这些)
7. [🆕 附加：GitHub 仓库安全教训](#七github-仓库安全教训)

---

## 一、起点：两套大脑的混乱

### 问题

项目早期快速验证阶段，AI Agent 能力分在两个地方各自实现：

- **Django 侧**：`backend/core/agents/harness/workflow.py` — 一套简单的 Agent Harness
- **编排服务侧**：`ai-orchestration-service/app/core/workflow.py` — 另一套更完整的 Workflow Harness

两套各写了一部分，互相不知道对方存在。典型的技术债。

### 为什么不能"打通两套"

如果硬对接，每一套都要写适配层，以后任何改动都要两边同步改。维护成本翻倍，出 bug 概率翻倍。

### 决策：统一为单一大脑

**一刀切**：以 `ai-orchestration-service` 为唯一 Agent 大脑，Django 只做工具层。

理由不仅是消除重复，更是为 SaaS 化铺路：
- 平台提供通用工作流原语（Plan/Orchestrate/Verify/ReAct/Checkpoint）
- 每个团队可以有自己的工作流模板、私有工具注册、独立记忆命名空间
- **平台适配团队风格，而不是团队削足适履适配平台** ← 这句话面试时值得讲

### 面试叙述方式

> "早期为了快速出原型，Django 里和独立编排服务各写了一套 Agent Harness。后来统一以编排服务为唯一大脑，Django 只做工具暴露层。这样既消除了重复，也为多租户 SaaS 化奠定了基础——每个团队可以有自己风格的 Agent。"

---

## 二、测试方法论：用接口测试的思路验证底座

### 我们的验证节奏

```
单元测试       → 每个模块独立能用
   ↓
接口测试       → 模块之间能通信（现在做的）
   ↓
集成测试       → 完整业务流程跑得通
   ↓
系统测试       → 加上前端，用户可操作
   ↓
验收测试       → 面试官 clone 一键跑通
```

### 为什么是这个顺序

- 接口不稳就去搞集成，报错时根本不知道是谁的问题
- 每个阶段只验证一件事，出问题范围可控
- 跟企业测试流程完全一致，面试时可以直接类比

---

## 三、实战踩坑记录

### 坑 1：Docker 健康检查失败

**现象**：`docker ps` 显示 orchestrator 容器 `unhealthy`

**排查过程**：
1. 看容器日志 → 没报错，服务本身正常运行
2. 手动调 `/api/v1/health/live` → 返回 `{"status":"alive"}`，接口正常
3. 检查 docker-compose.yml 健康检查命令 → `curl -f http://localhost:8001/...`
4. 进入容器 `docker exec` 执行 curl → **command not found**

**根因**：`python:3.11-slim` 基础镜像极简，连 curl 都没装。Docker 健康检查用 curl 但镜像里没有，永远失败。

**解决**：Dockerfile 里 `apt-get install -y curl`

**经验**：slim/alpine 镜像为了小，砍掉了大量常用工具。健康检查命令要用镜像里一定存在的工具，或者自己装上。

---

### 坑 2：服务间认证 401 — 三重排查

**现象**：编排服务调 Django MCP 工具返回 `{"detail":"身份认证信息未提供"}`，HTTP 401。

这个坑踩了三层才找到根因。

#### 第一层：文件是空的

**排查**：读 `backend/core/auth/service_auth.py` → 文件存在但内容为空（之前 `write_to_file` 写入失败但没报错）

**修复**：重写完整认证类

**结果**：还是 401 ✓（继续排查）

#### 第二层：认证类返回 AnonymousUser，被 IsAuthenticated 拒绝

**排查**：
- `ServiceTokenAuthentication` 验证 token 后返回了 `AnonymousUser()`
- Django REST 的 `IsAuthenticated` 权限类检查 `user.is_authenticated` → False → 拒绝
- MCP views 用了 `@permission_classes([IsAuthenticated])`，认证通过但权限不通过

**修复**：认证成功时返回一个自定义 ServiceAccount 对象，其 `is_authenticated = True`

```python
class ServiceAccount:
    is_authenticated = True
    is_service = True
```

**结果**：还是 401？！ ✓（继续排查）

#### 第三层：容器里跑的还是旧代码

**排查**：
1. 本地代码已经改了 → 测试还是 401
2. 检查 docker-compose.yml → **backend 没有挂载代码目录**
3. 只挂载了 `media_data` 和 `allure_data`
4. 容器里是构建镜像时拷贝进去的旧代码，本地改了什么它根本看不到

**修复**：
```yaml
volumes:
  - ./backend:/app           # ← 新增，热更新
  - media_data:/app/media
  - allure_data:/app/allure-results
```

加上这行后，改 Django 代码只需重启容器，不用重建镜像。

**最终结果**：`curl ... -H "X-Service-Token: xxxx"` → 返回完整 MCP 工具列表 ✅

### 这次排查的教训

| 层次 | 问题 | 怎么发现的 | 怎么修的 |
|------|------|-----------|---------|
| 代码层 | 文件是空的 | read_file 读内容 | 重写 |
| 框架层 | AnonymousUser 通不过 IsAuthenticated | 读 DRF 源码逻辑 | 返回 ServiceAccount |
| 部署层 | 容器没挂载代码 | 读 docker-compose.yml | 加 volume 挂载 |

三层问题叠加，每一层拆开看都不难，但摞在一起就容易"修了但没生效 → 怀疑自己 → 重复排查"。

**核心经验**：改完代码验证不生效时，别急着怀疑逻辑，先确认容器里跑的是不是你改的代码。

---

### 坑 3：backend 代码每次改动都要重建镜像

**问题**：backend 容器没有挂载本地代码，每次改 Python 文件都必须 `docker compose build backend`，太慢。

**解决**：`volumes: - ./backend:/app`，从此改代码只需重启容器。

**经验**：开发阶段一定要把代码目录 mount 进容器。生产部署才用镜像内置。

---

## 四、关键设计决策速查表

| 决策 | 方案 | 为什么 |
|------|------|--------|
| Agent 大脑 | 单一编排服务，Django 只做工具 | 消除重复，为 SaaS 铺路 |
| 服务间认证 | X-Service-Token + 用户 token fallback | 编排服务可独立工作，不依赖用户登录 |
| MCP 协议 | Django 暴露工具，编排服务通过 HTTP 调用 | 解耦，工具可独立扩展 |
| LLM 调度 | LLMRouter 统一路由 | team 级别模型偏好 + fallback |
| 断点续跑 | Checkpoint Store | 工作流中断后从断点继续，不从头跑 |
| 多租户 | team_id 命名空间 | 预留，企业落地时天然支持 |
| 开发部署 | volumes 挂载代码 | 改代码即生效，快速迭代 |

---

## 五、当前状态总览

```
第一阶段（地基浇筑）
├── ✅ 服务间认证代码完成
├── ✅ orchestrator 健康检查修复
├── ✅ backend 代码挂载（热更新）
├── ✅ 全容器 healthy
├── ✅ MCP 工具列表通过服务 token 可访问
├── ⏳ ReAct act_node → 真实 ToolGateway 联通验证
├── ⏳ 不带用户 token 全链路跑通
└── ⏳ 错误处理（LLM超时、工具失败、异常返回）

第二阶段（核心链路）     ░░░░░░░░░░  0%
第三阶段（前端界面）     ░░░░░░░░░░  0%
第四阶段（面试准备）     ░░░░░░░░░░  0%
```

---

## 六、面试怎么讲这些

### 30 秒版本（电梯演讲）

> "我做一个 AI 测试平台，核心是一个 LLM 编排底座。用 ReAct Agent 做思考循环，MCP 协议集成测试工具。踩过最大的坑是服务间认证——容器没挂载代码导致改了不生效，还有就是 DRF 的认证类返回 AnonymousUser 被权限检查拒绝。通过这个项目，我对 Agent 架构设计、服务间通信、从原型到生产的演进路径有了完整理解。"

### 3 分钟版本（项目难点）

1. **Agent 架构统一**：早期两套 Harness 并存，决策统一为单一大脑，为 SaaS 化铺路
2. **服务间认证**：编排服务调工具层，需要无用户登录也能工作。设计了 X-Service-Token + user token fallback 双层认证
3. **Docker 开发体验**：slim 镜像缺工具导致健康检查失败、代码没挂载导致改了不生效——这些坑教会我区分开发和生产部署的最优实践
4. **测试节奏**：接口测试→集成测试→系统测试，先验证模块间通信再跑全链路

### 关键词提醒

- **不要背**：理解逻辑后用自己的话讲
- **带例子**：每个结论后面跟一个小例子（比如 401 排查三层）
- **说为什么**：不只说做了什么，要解释决策理由
- **主动提坑**：面试官喜欢听"遇到过什么问题+怎么解决"，这比平铺直叙强 10 倍

---

## 七、GitHub 仓库安全教训

### 怎么发现的

在验证完 MCP 服务间认证后复盘时，检查了向 GitHub 推送的内容，发现公开仓库 `jigenhuang0-a11y/AutoTestHub` 里包含了不该公开的一切：

```
推上去的内容：
├── ai-orchestration-service/    ← 全部编排核心源码
├── .venv/                       ← 连虚拟环境二进制都推了
├── INTERVIEW_PREP.md            ← 面试准备文档
├── HANDOFF.md / PLAN.md         ← 内部规划
├── scripts/generate_resume.py   ← 简历生成脚本！
├── 项目演示/                     ← 项目截图
├── scripts/ (50+ 后台脚本)       ← 业务逻辑全暴露
└── .codebuddy/teams/            ← 团队协作配置
```

### 风险

如果面试官 clone 了这个仓库，会看到：
- 这个项目的核心技术（编排引擎）源码
- 求职准备材料（面试题、简历脚本）—— 会被认为"这就是你面试准备的作弊材料"
- 内部规划文档

**结论**：面试官看到这个仓库的一瞬间，你就被刷了。

### 修复步骤

1. **立即改私有**：GitHub Settings → Change visibility → Make private
2. **检查历史**：即使最新 commit 删了敏感文件，历史版本仍可见 → 需要 `git filter-branch` 彻底清除
3. **重建公开仓库**：只放测试平台业务代码 + 架构文档 + README。编排核心代码永远不放公开仓库
4. **未来策略**：
   - 公开仓库 = 门面层（前端 + Django 业务）
   - 私有仓库 = 核心引擎（编排服务）
   - 本地保留 = 面试材料、日记、脚本

### 面试怎么聊

> "项目分两层，仓库也是分开管理的。公开的是测试平台业务层和架构文档，核心编排引擎在私有仓库里。我可以详细讲解架构原理、ReAct 循环、多模型调度这些设计，但出于知识产权保护，核心源码不便对外。"

**记住：技术可以讲，源码不能给。代码是焚诀，教出去了就拿不到 offer。**
