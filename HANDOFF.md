# AutoTestHub 项目交接文档

> 生成日期：2026-08-08
> 维护人：AI 协作开发
> 适用对象：接手前端（agent-harness/frontend）后续 UI 调整 / 面试讲解 / 二次开发的同事

---

## 1. 项目概览

**AutoTestHub** — AI 驱动的全链路测试平台。技术栈：Django REST Framework + Vue 3 + PostgreSQL + Milvus + Celery + Docker。

核心四大能力：
- 接口自动化测试（Swagger/OpenAPI 文档 AI 解析生成用例）
- Web UI 自动化测试（Playwright + Midscene AI 感知）
- 性能压测（Locust 分布式）
- AI 智能评测（RAG 知识库 + Judge 评测引擎）

平台定位：企业大模型应用**质量管控**与**研发效能**一体化中台。

---

## 2. 仓库结构

```
ai-test-platform/
├── agent-harness/        # 独立的 Agent 编排服务（单一 Harness 大脑）
│   ├── app/              # FastAPI 服务 + 工作流编排核心
│   └── frontend/         # Vue 3 前端（含本交接重点的 Workbench 页面）
├── backend/              # Django REST Framework（工具/网关层，仅暴露 Agent 工具 API）
├── frontend/             # 另一套 Vue 前端（旧，逐步弃用）
├── docs/                 # 设计文档、截图、PDF
├── k8s/                  # Kubernetes 部署清单
├── scripts/              # 运维/数据脚本
├── docker-compose*.yml   # 多套 compose（dev/minimal/full）
├── ARCHITECTURE.md       # 架构设计文档
├── PLAN.md               # 迭代计划
└── INTERVIEW_PREP.md     # 面试准备（针对本项目）
```

### 架构关键决策（历史背景）
早期 Django 内和独立编排服务各写了一套 Harness，属于技术债务。
**最终决策**：不打通两套，统一以 `agent-harness` 为唯一 Agent Harness 大脑；Django 退化为工具/网关层，只暴露 Agent 工具 API。
SaaS 化方向：每个团队可有自己的工作流模板、私有工具注册、独立记忆命名空间（team_id/user_id）和模型偏好。
> 面试话术：早期为快速验证，两套 Harness 并存；后续统一成单一大脑，Django 当工具层，SaaS 化时团队可自定义模板/工具/记忆/模型。

---

## 3. 前端重点页面：Workbench 工作台

**文件**：`agent-harness/frontend/src/views/Workbench.vue`

这是工作台首页，采用「三行功能卡片网格 + Hero 标题 + 底部通栏」布局。

### 3.1 布局结构
- 顶部：Hero 标题区（平台名「AI效能中台」+ 副标题）+ 导航 pills（工作台/评测中心/监控中心/系统设置）+ 操作图标 + 用户头像
- 三行卡片网格（`card-grid`，7 列）：
  - 第 1 行：AI 核心底座（7 张卡片）
  - 第 2 行：自动化测试工具链（7 张卡片）
  - 第 3 行：运维观测底座（7 张卡片）
- 底部：slogan 通栏

### 3.2 卡片数据与渲染
卡片数据集中在 `<script setup>` 中，三组数据：`row1` / `row2` / `row3`，每组 7 个对象：

```js
{ id, title, subtitle, icon, route, type }
```

- `icon`：从 `@element-plus/icons-vue` 导入的图标组件
- `type`：决定卡片样式，三个取值：
  - `'normal'` → 普通卡片（蓝白边）
  - `'highlight'` → 高亮卡片（紫色霓虹，用于「全链路评测中心」）
  - `'focus'` → 重点卡片（亮蓝霓虹，用于「接口测试」）
- 渲染逻辑：`v-for` 遍历，`@click="navigate(card.route)"` 跳转路由。`type` 通过 `:class="['card-' + card.type]"` 绑定样式类。

### 3.3 卡片视觉规范（最新确认稿）

**布局**：左图右文（图标在左，标题+副标题在右，横向排列）。
**底色**：不透明奶白色实底（非透明玻璃态）。
- 普通卡片：`#f3eede` → `#e8e0cb` 渐变
- 高亮/重点卡片：奶白底 + 彩色霓虹边框（紫/蓝）

**关键尺寸**：
| 项 | 值 |
|----|----|
| 卡片 `min-height` | `148px` |
| 卡片 `border-radius` | `12px` |
| 网格 `gap` | `12px` |
| 卡片内 `padding` | `16px 18px` |
| 图标框尺寸 | `56px`（圆角 `14px`），内部图标 `:size="18"` |
| 标题 | `16px` / `800` / 深色 `#1a2a48` 系 |
| 副标题 | `12px` / `600` / 深色（如 `#6a5630`） |
| 行标题 `row-label` padding | `14px 4px 8px` |

**交互**：
- 鼠标 `mousemove` 通过 `requestAnimationFrame` 更新 `--mouse-x/--mouse-y` 变量，驱动 `.card-spotlight` 流光（GPU 加速，避免重绘卡顿）
- hover 时卡片上浮 `translateY(-2px)`，边框与图标发光增强

### 3.4 历史样式调整记录（避坑）
Workbench 卡片历经多次样式往返，最终确定的方向是：
1. **底色**：不透明奶白色实底（用户明确要求：卡片背景应是不透明的奶白色，而非透明玻璃态）
2. **文字**：深色文字（适配浅色底）
3. **布局**：左图右文（图标小、边框大、边框包裹小图标居中）
4. **尺寸**：放大 30% 后定稿（相对最初缩小版而言）

> ⚠️ 接手注意：若后续被要求「改回深色玻璃态」，只需把三种 `.card-base` 的 `background` 改回 `rgba(...)` 半透明 + 文字改回 `#ffffff` 即可，布局/尺寸无需动。

---

## 4. 开发与运行

### 4.1 前端（agent-harness/frontend）
```bash
cd agent-harness/frontend
npm install
npm run dev      # Vite 开发服务器，默认 5173 端口
```

### 4.2 后端
```bash
# Django 网关层
cd backend
pip install -r requirements.txt
python manage.py runserver

# Agent 编排服务（独立 FastAPI）
cd agent-harness
uvicorn app.main:app --reload
```

### 4.3 容器化
```bash
docker-compose up -d          # 全量
docker-compose.dev.yml        # 开发
docker-compose.minimal.yml    # 最小
```

---

## 5. 安全与脱敏（推送前必查）

1. `.env` 和 `backend/.env` 已在 `.gitignore` 排除，不会被提交
2. `.env.example` 是唯一放行的模板文件，已全是占位符
3. 旧 API Key（DeepSeek）已重置，Git 历史已通过 amend 清理
4. 推送前跑 `git status` 确认无敏感文件误加

---

## 6. 待办 / 已知问题

- [ ] `row1` 中「AI底座配置」与「系统设置」route 重复（均为 `/settings`），需确认是否合并
- [ ] `row3` 中「环境管理」route 为空（暂无页面）
- [ ] Workbench 与旧的 `frontend/` 目录存在功能重叠，长期应统一到 `agent-harness/frontend`
- [ ] 规划：先入职 → 换 MacBook 64GB → 本地跑 7B 模型 → SaaS 化

---

## 7. 关键文件索引

| 文件 | 说明 |
|------|------|
| `agent-harness/frontend/src/views/Workbench.vue` | 工作台首页（卡片网格） |
| `agent-harness/app/core/workflow.py` | Agent 工作流编排核心 |
| `backend/core/llm_provider.py` | LLM Provider（含 DeepSeekProvider） |
| `backend/seed_model_configs.py` | 模型配置种子数据 |
| `ARCHITECTURE.md` | 架构设计文档 |
| `INTERVIEW_PREP.md` | 面试准备（项目/原理/场景题） |
| `PLAN.md` | 迭代计划 |

---

*本文件由 AI 协作生成，如与实际情况不符，以代码为准。*
