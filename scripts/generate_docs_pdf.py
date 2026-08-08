"""
面试复习资料生成脚本：生成技术栈文档 + 踩坑记录文档 (PDF)
"""
import os
import sys

# 确保正确编码
sys.stdout.reconfigure(encoding='utf-8')

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, white, grey
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ============================================================
# 字体注册（使用中文字体）
# ============================================================
FONT_REGULAR = "SimSun"
FONT_BOLD = "SimHei"
FONT_MONO = "SimHei"

try:
    pdfmetrics.registerFont(TTFont('SimSun', 'C:/Windows/Fonts/simsun.ttc', subfontIndex=0))
    pdfmetrics.registerFont(TTFont('SimHei', 'C:/Windows/Fonts/simhei.ttf'))
    pdfmetrics.registerFont(TTFont('SimSun-Bold', 'C:/Windows/Fonts/simsun.ttc', subfontIndex=0))
except:
    FONT_REGULAR = "Helvetica"
    FONT_BOLD = "Helvetica-Bold"
    FONT_MONO = "Courier"

pdfmetrics.registerFont(TTFont('ChineseFont', 'C:/Windows/Fonts/msyh.ttc', subfontIndex=0))
FONT_REGULAR = 'ChineseFont'

# ============================================================
# 样式定义
# ============================================================
COLOR_PRIMARY = HexColor('#1a56db')
COLOR_DARK = HexColor('#1e293b')
COLOR_TEXT = HexColor('#334155')
COLOR_LIGHT_BG = HexColor('#f1f5f9')
COLOR_CODE_BG = HexColor('#f8fafc')
COLOR_RED = HexColor('#dc2626')
COLOR_GREEN = HexColor('#16a34a')
COLOR_ORANGE = HexColor('#ea580c')
COLOR_BORDER = HexColor('#e2e8f0')

styles = getSampleStyleSheet()

style_title = ParagraphStyle('CNTitle', fontName=FONT_REGULAR, fontSize=22, leading=28,
    textColor=COLOR_DARK, spaceAfter=6*mm, alignment=TA_LEFT, bold=True)

style_h1 = ParagraphStyle('CNH1', fontName=FONT_REGULAR, fontSize=16, leading=22,
    textColor=COLOR_PRIMARY, spaceBefore=10*mm, spaceAfter=4*mm, bold=True)

style_h2 = ParagraphStyle('CNH2', fontName=FONT_REGULAR, fontSize=13, leading=18,
    textColor=COLOR_DARK, spaceBefore=6*mm, spaceAfter=3*mm, bold=True)

style_h3 = ParagraphStyle('CNH3', fontName=FONT_REGULAR, fontSize=11, leading=15,
    textColor=COLOR_DARK, spaceBefore=4*mm, spaceAfter=2*mm, bold=True)

style_body = ParagraphStyle('CNBody', fontName=FONT_REGULAR, fontSize=10, leading=16,
    textColor=COLOR_TEXT, spaceAfter=2*mm, alignment=TA_JUSTIFY)

style_code = ParagraphStyle('CNCode', fontName=FONT_REGULAR, fontSize=8.5, leading=13,
    textColor=COLOR_TEXT, backColor=COLOR_CODE_BG, leftIndent=8*mm,
    spaceBefore=1*mm, spaceAfter=2*mm)

style_subtitle = ParagraphStyle('CNSubtitle', fontName=FONT_REGULAR, fontSize=11, leading=16,
    textColor=HexColor('#64748b'), spaceAfter=8*mm, alignment=TA_LEFT)

style_bullet = ParagraphStyle('CNBullet', fontName=FONT_REGULAR, fontSize=10, leading=16,
    textColor=COLOR_TEXT, leftIndent=6*mm, spaceAfter=1*mm)

style_table_header = ParagraphStyle('THeader', fontName=FONT_REGULAR, fontSize=9, leading=13,
    textColor=white, alignment=TA_CENTER)

style_table_cell = ParagraphStyle('TCell', fontName=FONT_REGULAR, fontSize=9, leading=13,
    textColor=COLOR_TEXT, alignment=TA_LEFT)

style_footer = ParagraphStyle('Footer', fontName=FONT_REGULAR, fontSize=8, leading=12,
    textColor=HexColor('#94a3b8'), alignment=TA_CENTER)

# 表格样式
TABLE_HEADER_BG = COLOR_PRIMARY
TABLE_STRIPE = HexColor('#f8fafc')
TABLE_BORDER = COLOR_BORDER


def hr():
    return HRFlowable(width="100%", thickness=0.5, color=COLOR_BORDER, spaceAfter=3*mm, spaceBefore=1*mm)

def bullet(text):
    return Paragraph(u"\u2022 " + text, style_bullet)

def code_block(code_text):
    return Paragraph(code_text.replace('\n', '<br/>').replace(' ', '&nbsp;'), style_code)

def make_table(headers, rows, col_widths=None):
    """创建带样式的表格"""
    header_cells = [Paragraph(h, style_table_header) for h in headers]
    data = [header_cells]
    for row in rows:
        data.append([Paragraph(str(c), style_table_cell) for c in row])

    if col_widths is None:
        col_widths = [170]*len(headers)

    t = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, -1), FONT_REGULAR),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, TABLE_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), TABLE_STRIPE))
    t.setStyle(TableStyle(style_cmds))
    return t

def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT_REGULAR, 7)
    canvas.setFillColor(HexColor('#94a3b8'))
    canvas.drawString(20*mm, 12*mm, doc.title)
    canvas.drawRightString(A4[0] - 20*mm, 12*mm, f"Page {doc.page}")
    canvas.restoreState()

def build_doc(filename, title, subtitle, story):
    doc = SimpleDocTemplate(
        filename, pagesize=A4,
        topMargin=22*mm, bottomMargin=22*mm,
        leftMargin=22*mm, rightMargin=22*mm,
        title=title
    )
    doc.title = title
    full_story = [
        Paragraph(title, style_title),
        Paragraph(subtitle, style_subtitle),
        hr(),
    ] + story
    doc.build(full_story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"  [OK] {filename}")


# ============================================================
# PDF 1: 技术栈文档
# ============================================================
def generate_tech_stack():
    story = []

    # --- 项目概述 ---
    story.append(Paragraph("1. 项目概述", style_h1))
    story.append(Paragraph(
        "AutoTestHub 是一个 AI 驱动的全栈测试平台，支持接口测试、Web UI 自动化、性能测试三大测试类型。"
        "集成 DeepSeek、通义千问、智谱 GLM 等国产大模型，提供 AI 用例生成、RAG 知识库问答、AI 测评师等功能。"
        "采用 Django REST Framework + Vue 3 前后端分离架构，Docker Compose 一键部署。",
        style_body))

    # --- 后端框架 ---
    story.append(Paragraph("2. 后端技术栈", style_h1))
    story.append(Paragraph("2.1 Web 框架与 API", style_h2))
    story.append(make_table(
        ["技术", "版本", "用途"],
        [
            ["Django", "4.2.7", "Web 框架核心，ORM、中间件、管理后台"],
            ["Django REST Framework", "3.14.0", "REST API 构建，ViewSet + Serializer 模式"],
            ["djangorestframework-simplejwt", "5.5.1", "JWT 认证 (HS256, Access 24h / Refresh 7d)"],
            ["django-cors-headers", "4.3.0", "跨域请求处理"],
            ["django-filter", "23.5", "API 查询过滤"],
            ["Gunicorn", "21.2.0", "WSGI 生产服务器"],
        ],
        [65*mm, 35*mm, 70*mm]
    ))

    story.append(Paragraph("2.2 自定义用户模型", style_h2))
    story.append(Paragraph(
        "继承 Django AbstractUser，新增 <b>role</b> 字段。三级角色体系：<b>admin</b>（管理员，可管理模型配置）、"
        "<b>tester</b>（测试工程师，常规操作）、<b>viewer</b>（只读）。所有 API 通过 DRF 权限类进行角色校验。",
        style_body))

    story.append(Paragraph("2.3 异步任务 (Celery)", style_h2))
    story.append(make_table(
        ["组件", "技术", "说明"],
        [
            ["任务队列", "Celery >=5.4.0", "异步执行测试任务、AI 评测、知识库向量化"],
            ["消息代理", "Redis >=5.0.0", "Celery Broker"],
            ["结果存储", "django-celery-results", "任务结果持久化到 Django DB"],
            ["并发配置", "4 workers", "每个 worker 独立处理一个任务"],
            ["超时限制", "600 秒", "单任务最长执行时间"],
        ],
        [40*mm, 55*mm, 75*mm]
    ))

    # --- 数据库 ---
    story.append(Paragraph("3. 数据存储", style_h1))

    story.append(Paragraph("3.1 关系数据库", style_h2))
    story.append(make_table(
        ["环境", "数据库", "说明"],
        [
            ["生产环境", "PostgreSQL 16 (Docker)", "完整 SQL 特性，强类型校验"],
            ["开发环境", "SQLite3 (Django 默认)", "零配置启动，但需注意约束差异"],
            ["连接方式", "psycopg2-binary 2.9.9", "Python PostgreSQL 驱动"],
        ],
        [40*mm, 65*mm, 65*mm]
    ))
    story.append(Paragraph(
        "<b>注意：</b>SQLite 不会校验 VARCHAR 长度等约束，而 PostgreSQL 会严格校验。"
        "开发环境应尽量与生产环境保持一致。",
        style_body))

    story.append(Paragraph("3.2 向量数据库 (Milvus)", style_h2))
    story.append(make_table(
        ["组件", "技术", "说明"],
        [
            ["向量数据库", "Milvus v2.4.0", "分布式向量检索，支持亿级向量"],
            ["Python SDK", "pymilvus >=2.4.0", "Python 客户端"],
            ["本地模式", "milvus-lite >=2.4.0", "嵌入式模式，无需 Docker"],
            ["元数据存储", "etcd v3.5.5", "Milvus 集群元数据"],
            ["对象存储", "MinIO", "Milvus 数据持久化"],
        ],
        [40*mm, 55*mm, 75*mm]
    ))

    story.append(Paragraph("3.3 缓存", style_h2))
    story.append(make_table(
        ["组件", "技术", "用途"],
        [
            ["Redis", "7-alpine (Docker)", "缓存 + Celery Broker + 会话存储"],
        ],
        [50*mm, 60*mm, 60*mm]
    ))

    # --- AI/LLM ---
    story.append(Paragraph("4. AI/LLM 集成", style_h1))
    story.append(Paragraph("4.1 LLM Provider 抽象层", style_h2))
    story.append(Paragraph(
        "采用 <b>工厂模式 + 策略模式</b> 实现统一 LLM 接口：<br/>"
        "<b>LLMProviderFactory.create(provider_name) → BaseLLMProvider</b><br/><br/>"
        "所有 Provider 继承同一基类，实现统一接口：<br/>"
        "<b>chat(messages)</b> 同步对话<br/>"
        "<b>chat_stream(messages)</b> 流式输出 (SSE)<br/>"
        "<b>embed(texts)</b> 文本向量化<br/><br/>"
        "新增 Provider 只需：1) 继承 BaseLLMProvider  2) 实现三个方法  3) 注册到工厂类",
        style_body))

    story.append(make_table(
        ["Provider", "默认模型", "特点"],
        [
            ["通义千问 (DashScope)", "qwen-plus", "Chat + Streaming + Embedding (text-embedding-v3)"],
            ["DeepSeek", "deepseek-chat", "高性价比，擅长代码生成和推理"],
            ["智谱 GLM", "glm-4-flash", "轻量模型，快速响应"],
        ],
        [60*mm, 50*mm, 60*mm]
    ))

    story.append(Paragraph("4.2 LangChain/LangGraph 生态", style_h2))
    story.append(make_table(
        ["包", "版本", "用途"],
        [
            ["langchain", ">=0.3.0", "LLM/Tool 抽象层"],
            ["langchain-openai", ">=0.2.0", "OpenAI 兼容 Provider（DeepSeek 等）"],
            ["langchain-community", ">=0.3.0", "文档加载器 (PDF/TXT)"],
            ["langchain-text-splitters", ">=0.3.0", "文本语义分块"],
            ["langgraph", ">=0.2.0", "Agent 状态机编排"],
        ],
        [60*mm, 40*mm, 70*mm]
    ))

    story.append(Paragraph("4.3 RAG 知识库链路", style_h2))
    story.append(Paragraph(
        "<b>完整流程：</b>上传文档 → PDF/TXT/DOCX 解析 → 文本语义分块 → Embedding 向量化 → "
        "Milvus 向量存储 → 用户提问 → 语义检索相似文档 → 拼接 Prompt → LLM 生成回答<br/><br/>"
        "<b>Embedding 方案：</b>默认使用 DashScope text-embedding-v3（在线），"
        "也支持 sentence-transformers + BAAI/bge-small-zh-v1.5（本地离线）",
        style_body))

    story.append(Paragraph("4.4 AI 视觉 Web 自动化 (Midscene)", style_h2))
    story.append(make_table(
        ["组件", "技术", "说明"],
        [
            ["视觉 AI 引擎", "Midscene (字节跳动)", "AI 视觉驱动的页面元素识别与操作"],
            ["视觉模型", "qwen-vl-plus / qwen-vl-max", "多模态大模型理解页面截图"],
            ["浏览器引擎", "Playwright", "Chromium/Firefox/WebKit 跨浏览器支持"],
            ["双引擎模式", "Playwright 精确模式 + AI 模式", "常规操作用 Playwright，复杂场景用 AI"],
        ],
        [50*mm, 55*mm, 65*mm]
    ))

    # --- 前端 ---
    story.append(Paragraph("5. 前端技术栈", style_h1))
    story.append(make_table(
        ["技术", "版本", "用途"],
        [
            ["Vue 3", "^3.5.34", "渐进式前端框架，Composition API"],
            ["Vite", "^8.0.12", "极速构建工具"],
            ["Pinia", "^3.0.4", "状态管理"],
            ["Vue Router", "^5.0.7", "SPA 路由"],
            ["Element Plus", "^2.14.0", "企业级 UI 组件库"],
            ["Axios", "^1.16.1", "HTTP 请求封装，拦截器处理 Token"],
            ["ECharts", "^6.0.0", "数据可视化图表"],
            ["html2pdf.js", "^0.14.0", "前端 PDF 导出"],
        ],
        [60*mm, 40*mm, 70*mm]
    ))

    story.append(Paragraph(
        "前端共 <b>19 个路由页面</b>，覆盖六大核心场景：<br/>"
        "仪表盘、用例管理（接口/Web/性能）、执行监控、测试报告、"
        "AI 模块（测评师/知识库/技能库）、平台管理（模型配置/MCP工具）",
        style_body))

    # --- 测试工具 ---
    story.append(Paragraph("6. 测试引擎", style_h1))
    story.append(make_table(
        ["引擎", "技术", "说明"],
        [
            ["接口测试", "pytest 7.4.3 + allure 2.13.2", "HTTP API 测试，JSONPath 断言，Allure 报告"],
            ["Web UI 自动化", "Playwright + Midscene AI", "双引擎：精确选择器 + AI 视觉识别"],
            ["性能测试", "Locust", "支持 5 种测试类型，实时压测监控"],
        ],
        [45*mm, 65*mm, 60*mm]
    ))

    # --- 部署 ---
    story.append(Paragraph("7. 部署架构", style_h1))
    story.append(Paragraph(
        "<b>Docker Compose 一键部署</b>：<br/>"
        "PostgreSQL 16 + Redis 7 + etcd + MinIO + Milvus 2.4 + Django(Gunicorn) + Celery + Vue(Nginx)<br/><br/>"
        "<b>开发环境：</b>仅启动 PostgreSQL Docker 容器（15432 端口），其余本地运行<br/>"
        "<b>生产环境：</b>全部容器化，Nginx 统一入口，环境变量注入配置",
        style_body))

    # --- 模块架构 ---
    story.append(Paragraph("8. 模块清单", style_h1))
    story.append(make_table(
        ["Django App", "功能"],
        [
            ["accounts", "用户系统 (admin/tester/viewer 三级角色)"],
            ["testcases", "接口测试用例管理"],
            ["web_testcases", "Web 自动化测试 (Playwright + AI 双引擎)"],
            ["performance", "性能测试 (Locust 压测引擎)"],
            ["testsuites", "测试套件编排"],
            ["execution", "测试执行引擎"],
            ["reports", "测试报告生成"],
            ["knowledge_base", "RAG 知识库管理 + AI 问答"],
            ["data_factory", "测试数据工厂 (AI 生成 + 版本管理)"],
            ["quality_checker", "质量数字人 (用例质量检测)"],
            ["ai_evaluator", "AI 测评师 (知识库机器人/API 评测)"],
            ["agent_gateway", "Agent 网关 (统一 AI 入口, Prompt 管理)"],
        ],
        [55*mm, 115*mm]
    ))

    # --- 关键设计模式 ---
    story.append(Paragraph("9. 核心设计模式", style_h1))

    story.append(Paragraph("9.1 工厂模式 — LLM Provider", style_h2))
    story.append(Paragraph(
        "LLMProviderFactory.create('deepseek') 根据名称返回对应 Provider 实例。"
        "新增模型供应商只需注册，无需改动业务代码。",
        style_body))

    story.append(Paragraph("9.2 策略模式 — 测试执行引擎", style_h2))
    story.append(Paragraph(
        "抽象 TestExecutor 基线，API/Web/Performance 三种执行器各自实现。"
        "调度层统一调用 execute() 方法，不关心具体类型。",
        style_body))

    story.append(Paragraph("9.3 观察者模式 — Celery 任务回调", style_h2))
    story.append(Paragraph(
        "测试任务异步执行完成后，通过 django-celery-results 回调更新任务状态和数据。"
        "前端通过轮询获取实时进度。",
        style_body))

    build_doc(
        os.path.join(os.path.dirname(__file__), "..", "docs", "技术栈文档_面试复习.pdf"),
        "AutoTestHub 技术栈文档",
        "面试复习专用 · 完整技术栈清单",
        story
    )


# ============================================================
# PDF 2: 踩坑记录文档
# ============================================================
def generate_pitfalls():
    story = []

    story.append(Paragraph("1. 核心踩坑记录（按模块）", style_h1))

    # --- 坑 1: pypdf ---
    story.append(Paragraph("1.1 知识库 — pypdf 缺失导致异步向量化静默失败", style_h2))
    story.append(Paragraph("<b>现象：</b>上传 PDF 文档后，知识库搜索不到内容，但页面显示「上传成功」。", style_body))
    story.append(Paragraph("<b>根因：</b>", style_body))
    story.append(bullet("Celery 异步向量化任务因 pypdf 未安装而抛出 ImportError"))
    story.append(bullet("Celery 任务静默失败，没有回写错误状态到数据库"))
    story.append(bullet("前端轮询到的任务状态始终是 SUCCESS，但实际上文档内容为空白"))
    story.append(Paragraph("<b>解决方案：</b>", style_body))
    story.append(bullet("在 requirements.txt 中添加 pypdf>=3.0.0 依赖"))
    story.append(bullet("向量化任务增加 try-except 包裹，异常时回写 FAILED 状态"))
    story.append(bullet("前端展示任务失败原因，提示用户重新上传"))
    story.append(hr())

    # --- 坑 2: pymilvus 2.4 ---
    story.append(Paragraph("1.2 知识库 — pymilvus 2.4 Hit 对象 API 变更", style_h2))
    story.append(Paragraph("<b>现象：</b>升级到 pymilvus 2.4 后，搜索返回值类型不兼容，代码报 AttributeError。", style_body))
    story.append(Paragraph("<b>根因：</b>", style_body))
    story.append(bullet("pymilvus 2.3 中 hit.get('entity') 返回 dict 类型"))
    story.append(bullet("pymilvus 2.4 中 hit.get('entity') 返回 NamedTuple 类型"))
    story.append(bullet("代码用 dict['key'] 方式访问字段，在 2.4 中不再兼容"))
    story.append(Paragraph("<b>解决方案：</b>", style_body))
    story.append(code_block("entity = hit.get('entity')\nif isinstance(entity, dict):\n    value = entity.get('field')\nelse:\n    value = entity.field  # NamedTuple 方式访问"))
    story.append(bullet("用 isinstance 判断类型，兼容两种 API"))
    story.append(hr())

    # --- 坑 3: similarity_threshold ---
    story.append(Paragraph("1.3 知识库 — similarity_threshold=0.5 过滤过度", style_h2))
    story.append(Paragraph("<b>现象：</b>知识库问答对概括性问题（如「这个项目是做什么的」）回答质量差，找不到相关内容。", style_body))
    story.append(Paragraph("<b>根因：</b>", style_body))
    story.append(bullet("向量相似度阈值设为 0.5，概括性问题与具体文档内容天然余弦相似度低（0.3-0.4）"))
    story.append(bullet("阈值一刀切，概括性问题和精确查询无法区分对待"))
    story.append(Paragraph("<b>解决方案：</b>", style_body))
    story.append(bullet("将 similarity_threshold 从 0.5 降低到 0.0"))
    story.append(bullet("让 LLM 自行判断检索到的文档是否相关，而非在向量层面就过滤掉"))
    story.append(hr())

    # --- 坑 4: 前端路径不一致 ---
    story.append(Paragraph("1.4 API 路径不一致导致 404", style_h2))
    story.append(Paragraph("<b>现象：</b>前端某些页面偶尔报 404，同样的功能在另一个页面却正常。", style_body))
    story.append(Paragraph("<b>根因：</b>", style_body))
    story.append(bullet("前端 axios baseURL 和后端 URL 配置未统一管理"))
    story.append(bullet("有的 API 用 /api/knowledge-base/，有的用 /api/knowledge/knowledge-bases/"))
    story.append(bullet("前后端各自维护一套 URL，出现差异时难以发现"))
    story.append(Paragraph("<b>解决方案：</b>", style_body))
    story.append(bullet("在统一的 API 常量文件中定义所有接口路径"))
    story.append(bullet("后端 Django URL 配置和使用同一套命名规范"))
    story.append(bullet("新增兼容路由（如 /api/executions/ 同时映射到原有视图）"))
    story.append(hr())

    # --- 坑 5: business_domain ---
    story.append(Paragraph("1.5 数据库字段设计 — business_domain 容量不足", style_h2))
    story.append(Paragraph("<b>现象：</b>创建知识库时填入的场景描述（几十字）无法保存到 business_domain 字段。", style_body))
    story.append(Paragraph("<b>根因：</b>", style_body))
    story.append(bullet("business_domain 定义为 CharField(max_length=20)，只能存 20 个字符"))
    story.append(bullet("前端把完整场景描述（50+ 字符）塞进这个字段"))
    story.append(bullet("本地 SQLite 不校验长度，到了服务器 PostgreSQL 才报错"))
    story.append(Paragraph("<b>解决方案：</b>", style_body))
    story.append(bullet("business_domain 保持 varchar(20)，只存简短枚举值（如 'AI评测'）"))
    story.append(bullet("长文本描述放入 description 字段（TextField，无长度限制）"))
    story.append(hr())

    # --- 坑 6: SQLite vs PostgreSQL ---
    story.append(Paragraph("1.6 开发环境与生产环境数据库不一致", style_h2))
    story.append(Paragraph("<b>现象：</b>本地开发环境一切正常，部署到服务器后出现各种字段校验错误。", style_body))
    story.append(Paragraph("<b>根因：</b>", style_body))
    story.append(bullet("SQLite 是「宽容模式」，不校验 VARCHAR 长度、不校验约束"))
    story.append(bullet("PostgreSQL 是「严格模式」，所有约束都会强制校验"))
    story.append(bullet("开发阶段在 SQLite 上的操作没有触发约束检查"))
    story.append(Paragraph("<b>解决方案：</b>", style_body))
    story.append(bullet("开发环境使用 docker-compose.dev.yml 启动 PostgreSQL 容器"))
    story.append(bullet("所有开发操作都在 PostgreSQL 上进行，避免环境差异"))
    story.append(hr())

    # --- 坑 7: Windows 端口 ---
    story.append(Paragraph("1.7 Windows 端口冲突 (5432/5433)", style_h2))
    story.append(Paragraph("<b>现象：</b>Windows 上启动 PostgreSQL Docker 时端口冲突，无法绑定 5432。", style_body))
    story.append(Paragraph("<b>根因：</b>", style_body))
    story.append(bullet("Windows 系统预留了 5432-5433 端口给某些系统服务"))
    story.append(bullet("PostgreSQL 默认端口 5432 被占用，且不是已运行的 PostgreSQL 实例"))
    story.append(Paragraph("<b>解决方案：</b>", style_body))
    story.append(bullet("将 PostgreSQL 端口映射改为 15432:5432"))
    story.append(bullet("更新 .env 中 DB_PORT=15432"))
    story.append(hr())

    # --- 坑 8: .env 密钥泄露 ---
    story.append(Paragraph("1.8 安全意识 — .env 文件误提交 Git", style_h2))
    story.append(Paragraph("<b>现象：</b>检查 GitHub 仓库时发现历史 commit 中包含 .env 文件，内有 API 密钥。", style_body))
    story.append(Paragraph("<b>根因：</b>", style_body))
    story.append(bullet("项目初期 .env 没有被 .gitignore 忽略，直接提交到了 Git 仓库"))
    story.append(bullet("后期即使添加了 .gitignore，历史 commit 中的密钥仍然可被查阅"))
    story.append(bullet("代码中还存在硬编码的默认密钥值（seed_model_configs.py）"))
    story.append(bullet("HANDOFF.md 交接文档中记录了明文密钥"))
    story.append(Paragraph("<b>解决方案：</b>", style_body))
    story.append(bullet("立即去云平台控制台重置所有泄露的 API Key（DashScope / DeepSeek）"))
    story.append(bullet(".gitignore 添加 .env / .env.* 规则"))
    story.append(bullet("代码中所有 API Key 默认值改为空字符串：os.getenv('KEY', '')"))
    story.append(bullet("文档中所有密钥用 *** 占位符替代"))
    story.append(bullet("Git 历史无法撤回，只能通过重置密钥来补救"))
    story.append(hr())

    # --- 坑 9: 本地 vs 服务器 ---
    story.append(Paragraph("1.9 数据库操作对象混淆 — 本地 Django ORM vs 服务器数据库", style_h2))
    story.append(Paragraph("<b>现象：</b>用本地 Python 脚本创建的数据，服务器前端看不到。", style_body))
    story.append(Paragraph("<b>根因：</b>", style_body))
    story.append(bullet("本地 Django ORM 操作的是本地 PostgreSQL（或 SQLite）数据库"))
    story.append(bullet("服务器部署的是独立的 PostgreSQL 容器"))
    story.append(bullet("两个数据库完全隔离，数据不会自动同步"))
    story.append(Paragraph("<b>解决方案：</b>", style_body))
    story.append(bullet("数据操作统一通过 API 调用，而不是直接操作数据库"))
    story.append(bullet("如需批量操作，使用 Django Management Command，在服务器容器中运行："))
    story.append(code_block("docker exec <backend-container> python manage.py <command_name>"))
    story.append(hr())

    # --- 坑 10: Celery Windows ---
    story.append(Paragraph("1.10 Celery 在 Windows 上的兼容性", style_h2))
    story.append(Paragraph("<b>现象：</b>Windows 上启动 Celery worker 后任务不执行或报错。", style_body))
    story.append(Paragraph("<b>根因：</b>", style_body))
    story.append(bullet("Celery 4.x+ 默认使用 prefork pool，Windows 不支持 fork 系统调用"))
    story.append(bullet("某些依赖（如 sqlite3 扩展）在 Windows 上行为不同"))
    story.append(Paragraph("<b>解决方案：</b>", style_body))
    story.append(bullet("Windows 开发时使用 --pool=solo 启动：celery -A project worker -l info --pool=solo"))
    story.append(bullet("生产环境（Linux Docker）使用默认 prefork pool，性能最优"))
    story.append(hr())

    # --- 坑 11: embedding 下载 ---
    story.append(Paragraph("1.11 国内网络导致模型下载失败", style_h2))
    story.append(Paragraph("<b>现象：</b>首次运行时，sentence-transformers 下载模型 BAAI/bge-small-zh-v1.5 超时失败。", style_body))
    story.append(Paragraph("<b>根因：</b>", style_body))
    story.append(bullet("Hugging Face 在国内访问不稳定，模型文件下载超时"))
    story.append(bullet("没有配置镜像源或代理"))
    story.append(Paragraph("<b>解决方案：</b>", style_body))
    story.append(bullet("优先使用 DashScope 在线 Embedding API（不需要下载模型）"))
    story.append(bullet("如需本地 Embedding，设置 HF_ENDPOINT=https://hf-mirror.com 环境变量"))
    story.append(bullet("编写下载重试逻辑和降级方案"))
    story.append(hr())

    # --- 经验总结 ---
    story.append(Paragraph("2. 经验总结", style_h1))

    story.append(Paragraph("2.1 环境一致性原则", style_h2))
    story.append(Paragraph(
        "开发环境、测试环境、生产环境必须使用相同的数据库和服务。SQLite 的宽容性会掩盖大量问题。"
        "推荐使用 docker-compose.dev.yml 在本地启动与生产一致的 PostgreSQL。",
        style_body))

    story.append(Paragraph("2.2 密钥管理铁律", style_h2))
    story.append(make_table(
        ["规则", "说明"],
        [
            ["绝不硬编码", "os.getenv('KEY', '') 默认值为空，不给真值"],
            [".gitignore 先行", "项目初始化第一步就加 .env"],
            ["历史无法撤回", "一旦泄露必须重置密钥，Git filter-repo 太麻烦"],
            ["文档要脱敏", "交接文档、README 中的密钥用 *** 替代"],
        ],
        [45*mm, 125*mm]
    ))

    story.append(Paragraph("2.3 异步任务可靠性", style_h2))
    story.append(make_table(
        ["规则", "说明"],
        [
            ["显式异常捕获", "所有 Celery 任务必须 try-except，不能指望框架兜底"],
            ["状态回写", "任务成功/失败都要写回数据库，前端依赖状态判断"],
            ["超时配置", "根据任务类型设置合理的 CELERY_TASK_TIME_LIMIT"],
            ["幂等性", "任务设计要考虑重试场景，不能重复写入数据"],
        ],
        [45*mm, 125*mm]
    ))

    story.append(Paragraph("2.4 LLM 集成经验", style_h2))
    story.append(make_table(
        ["经验", "说明"],
        [
            ["阈值不宜过低", "向量相似度阈值设为 0.0，让 LLM 自己判断相关性"],
            ["兼容性检查", "第三方 SDK 升级后必须验证 API 兼容性"],
            ["降级方案", "LLM 调用失败时有默认回答/本地模型兜底"],
            ["模型管理化", "模型配置存数据库而非代码，支持前端动态切换"],
        ],
        [45*mm, 125*mm]
    ))

    build_doc(
        os.path.join(os.path.dirname(__file__), "..", "docs", "踩坑记录_面试复习.pdf"),
        "AutoTestHub 踩坑记录与解决方案",
        "面试复习专用 · 11 个真实踩坑案例 + 经验总结",
        story
    )


# ============================================================
# 执行生成
# ============================================================
if __name__ == '__main__':
    print("Generating interview prep PDFs...")
    docs_dir = os.path.join(os.path.dirname(__file__), "..", "docs")
    os.makedirs(docs_dir, exist_ok=True)

    print("\n[1/2] 技术栈文档...")
    generate_tech_stack()

    print("\n[2/2] 踩坑记录文档...")
    generate_pitfalls()

    print(f"\nDone! Files saved to: {docs_dir}")
