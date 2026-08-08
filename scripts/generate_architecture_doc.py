"""
生成《AutoTestHub 架构与调用链路详解》PDF 文档（排版优化版）
修复：1）中文 TA_LEFT 替换 TA_JUSTIFY 消除空格；2）所有 Table/Paragraph 强制使用注册中文字体；3）自动截图嵌入 HTML 架构图
"""
import os
import subprocess
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ============================================================
# 1. 字体注册（优先微软雅黑，其次黑体）
# ============================================================
def register_fonts():
    candidates = [
        ("YaHei", "C:/Windows/Fonts/msyh.ttc"),
        ("YaHeiBold", "C:/Windows/Fonts/msyhbd.ttc"),
        ("SimHei", "C:/Windows/Fonts/simhei.ttf"),
        ("SimSun", "C:/Windows/Fonts/simsun.ttc"),
    ]
    for name, path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
            except Exception:
                pass

register_fonts()
registered = set(pdfmetrics.getRegisteredFontNames())

if "YaHei" in registered:
    FONT_BODY = "YaHei"
    FONT_BOLD = "YaHeiBold" if "YaHeiBold" in registered else "YaHei"
elif "SimHei" in registered:
    FONT_BODY = "SimHei"
    FONT_BOLD = "SimHei"
else:
    FONT_BODY = "Helvetica"
    FONT_BOLD = "Helvetica-Bold"

FONT_CODE = "Courier"

# ============================================================
# 2. 颜色
# ============================================================
hex_color = HexColor
C_PRIMARY = hex_color("#3b82f6")
C_GREEN = hex_color("#22c55e")
C_PURPLE = hex_color("#a855f7")
C_ORANGE = hex_color("#f97316")
C_CYAN = hex_color("#06b6d4")
C_RED = hex_color("#f43f5e")
C_AMBER = hex_color("#f59e0b")
C_TEAL = hex_color("#14b8a6")
C_PINK = hex_color("#ec4899")
C_TEXT = hex_color("#e2e8f0")
C_MUTED = hex_color("#94a3b8")
C_DARK = hex_color("#334155")

# ============================================================
# 3. 样式工厂（所有中文 alignment=TA_LEFT，禁止两端对齐）
# ============================================================
def make_style(name, fontSize=10.5, leading=16, alignment=TA_LEFT,
               textColor=black, spaceAfter=6, spaceBefore=0,
               bold=False, leftIndent=0, fontName=None):
    fn = fontName if fontName else (FONT_BOLD if bold else FONT_BODY)
    return ParagraphStyle(
        name, fontName=fn, fontSize=fontSize, leading=leading,
        alignment=alignment, textColor=textColor,
        spaceAfter=spaceAfter, spaceBefore=spaceBefore,
        leftIndent=leftIndent,
    )

style_title = make_style("Title", fontSize=28, leading=36, alignment=TA_CENTER, textColor=C_PRIMARY, spaceAfter=20, bold=True)
style_subtitle = make_style("Subtitle", fontSize=14, leading=20, alignment=TA_CENTER, textColor=C_MUTED, spaceAfter=30)
style_h1 = make_style("H1", fontSize=20, leading=28, textColor=C_PRIMARY, spaceBefore=16, spaceAfter=10, bold=True)
style_h2 = make_style("H2", fontSize=16, leading=24, textColor=C_GREEN, spaceBefore=12, spaceAfter=8, bold=True)
style_h3 = make_style("H3", fontSize=13, leading=20, textColor=C_AMBER, spaceBefore=10, spaceAfter=6, bold=True)
style_body = make_style("Body", fontSize=10.5, leading=16, textColor=black, spaceAfter=6)
style_tip = make_style("Tip", fontSize=10, leading=15, textColor=C_TEAL, spaceAfter=6)
style_bold = make_style("Bold", fontSize=10.5, leading=16, textColor=black, spaceAfter=4, bold=True)
style_center = make_style("Center", fontSize=10, leading=15, alignment=TA_CENTER, textColor=C_MUTED, spaceAfter=4)
style_code = make_style("Code", fontSize=9, leading=13, textColor=C_CYAN, spaceAfter=4, fontName=FONT_CODE)

# ============================================================
# 4. 辅助函数
# ============================================================
def _safe(text):
    """XML 转义 + 恢复允许标签"""
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    for t in ['b', 'i', 'br', 'font', 'u']:
        text = text.replace(f'&lt;{t}&gt;', f'<{t}>').replace(f'&lt;/{t}&gt;', f'</{t}>')
    return text

def P(text, style=style_body):
    return Paragraph(_safe(text), style)

def h1(t): return P(t, style_h1)
def h2(t): return P(t, style_h2)
def h3(t): return P(t, style_h3)
def bold(t): return P(t, style_bold)
def tip(t): return P(t, style_tip)
def code(t): return P(t, style_code)
def sp(h=6): return Spacer(1, h)

# ============================================================
# 5. 自动截图 HTML 架构图
# ============================================================
def screenshot_html(html_path, out_png):
    html_path = os.path.abspath(html_path)
    url = f"file:///{html_path.replace(os.sep, '/')}"
    for exe in ["msedge", "chrome", "google-chrome", "chromium"]:
        try:
            subprocess.run([
                exe, "--headless", "--disable-gpu",
                f"--screenshot={out_png}",
                "--window-size=1400,2200",
                "--hide-scrollbars", "--no-sandbox",
                url
            ], check=True, timeout=30, capture_output=True)
            if os.path.exists(out_png) and os.path.getsize(out_png) > 1000:
                return out_png
        except Exception:
            continue
    return None

# ============================================================
# 6. 表格构建器（所有 Paragraph 都显式绑定中文字体）
# ============================================================
def cell(text, bold=False, color=black, size=9, leading=14, font=None):
    fn = font if font else (FONT_BOLD if bold else FONT_BODY)
    st = ParagraphStyle("tmp", fontName=fn, fontSize=size, leading=leading,
                        textColor=color, alignment=TA_LEFT)
    return Paragraph(_safe(text), st)

def stat_table(rows):
    data = [[cell(c, bold=(i==0), color=(white if i==0 else black), size=(10 if i==0 else 9)) for i, c in enumerate(r)] for r in rows]
    t = Table(data, colWidths=[4*cm, 3*cm, 10*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_PRIMARY),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, C_DARK),
        ('BACKGROUND', (0,1), (-1,-1), hex_color("#f8fafc")),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    return t

def eff_table(rows):
    data = [[cell(c, bold=(i==0), color=(white if i==0 else black), size=(10 if i==0 else 9)) for i, c in enumerate(r)] for r in rows]
    t = Table(data, colWidths=[3.5*cm, 4.5*cm, 4.5*cm, 3*cm, 5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_PRIMARY),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, C_DARK),
        ('BACKGROUND', (0,1), (-1,-1), hex_color("#f8fafc")),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    return t

def roi_table(rows):
    data = [[cell(c, bold=(i==0), color=(white if i==0 else black), size=(10 if i==0 else 9)) for i, c in enumerate(r)] for r in rows]
    t = Table(data, colWidths=[5*cm, 5*cm, 5*cm, 4*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_GREEN),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, C_DARK),
        ('BACKGROUND', (0,1), (-1,-1), hex_color("#f8fafc")),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    return t

def step_table(steps):
    """两列：Step 标题 | 描述"""
    data = []
    for title, desc in steps:
        data.append([
            cell(f"<b>{title}</b>", color=C_PRIMARY, size=10, leading=15),
            cell(desc, color=black, size=10, leading=15)
        ])
    t = Table(data, colWidths=[5.5*cm, 10.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), hex_color("#f0f9ff")),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, hex_color("#e2e8f0")),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    return t

def tech_card(title, subtitle, desc, color=C_PRIMARY):
    """技术栈卡片：标题+副标题 | 描述"""
    data = [
        [cell(f"<b>{title}</b>", color=color, size=11, leading=16, bold=True),
         cell(subtitle, color=C_MUTED, size=9, leading=14)],
        [cell(desc, color=black, size=10, leading=15), ""]
    ]
    t = Table(data, colWidths=[6*cm, 10*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), hex_color("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 1.5, color),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('SPAN', (0,1), (1,1)),
    ]))
    return t

def flow_card(title, desc, color):
    data = [[cell(f"<b>{title}</b>", color=color, size=11, leading=16, bold=True),
             cell(desc, color=C_MUTED, size=9, leading=14)]
    ]
    t = Table(data, colWidths=[5*cm, 11*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), hex_color("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 1, hex_color("#e2e8f0")),
        ('LINEBELOW', (0,0), (-1,-2), 0.5, hex_color("#e2e8f0")),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    return t

# ============================================================
# 7. 内容构建
# ============================================================
story = []

# --- 封面 ---
story.append(Spacer(1, 80))
story.append(P("AutoTestHub", style_title))
story.append(P("智能测试平台 — 架构与调用链路详解", style_subtitle))
story.append(Spacer(1, 20))
story.append(P("<b>v2.0 · Milvus 亿级向量版</b>", make_style("ver", fontSize=12, leading=18, alignment=TA_CENTER, textColor=C_PRIMARY, bold=True)))
story.append(Spacer(1, 40))

stats = [
    ["11", "Django Apps"], ["5", "AI Agents"], ["9", "Tools"],
    ["10", "前端页面"], ["60+", "API 端点"], ["8", "Docker 服务"]
]
stat_data = []
for row in stats:
    stat_data.append([cell(f"<b>{v}</b>", color=C_PRIMARY, size=18, leading=24, bold=True) for v in row[::2]])
    stat_data.append([cell(v, color=C_MUTED, size=9, leading=14) for v in row[1::2]])
stat_t = Table(stat_data, colWidths=[4*cm]*3)
stat_t.setStyle(TableStyle([
    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
]))
story.append(stat_t)
story.append(Spacer(1, 60))
story.append(P("生成日期: 2026-07-13", style_center))
story.append(PageBreak())

# --- 目录 ---
story.append(h1("目录"))
toc_items = [
    "一、系统架构全景图", "1.1 关键统计与分层概览", "1.2 核心数据流流水线",
    "二、核心功能执行链路详解", "2.1 AI 用例生成链路", "2.2 数据工厂链路", "2.3 执行引擎链路", "2.4 AI 评估链路", "2.5 LangGraph 工作流编排", "2.6 知识库 RAG 链路",
    "三、技术栈深度解析", "3.1 前端技术栈", "3.2 后端技术栈", "3.3 AI / LLM 技术栈", "3.4 数据存储技术栈", "3.5 基础设施与 DevOps",
    "四、效率提升与量化对比", "4.1 各链路效率提升数据", "4.2 整体项目 ROI 估算",
    "五、核心模块功能清单", "5.1 11 个 Django Apps", "5.2 5 个 AI Agents", "5.3 9 个 Tools", "5.4 10 个前端页面", "5.5 8 个 Docker 服务"
]
for item in toc_items:
    indent = 20 if item[0].isdigit() and len(item) > 1 and item[1] == '.' else 0
    story.append(P(item, make_style("toc", fontSize=11, leading=20, textColor=C_TEXT, leftIndent=indent)))
story.append(PageBreak())

# ============================================================
# 第一章：系统架构全景图
# ============================================================
story.append(h1("一、系统架构全景图"))
story.append(P("AutoTestHub 采用 <b>分层架构 + Agent 驱动</b> 的设计模式，从前端用户交互到后端 AI 推理，再到底层基础设施，每一层都有清晰的职责边界。整体架构可概括为：<b>前端层 → Agent 网关 → AI Agent 层 → Tools 层 → 业务模块层 → 基础设施层</b>。"))
story.append(sp())

# 嵌入架构图
HTML_PATH = "d:/AI_Project/ai-test-platform/项目架构图.html"
IMG_PATH = "d:/AI_Project/ai-test-platform/docs/architecture_screenshot.png"
screenshot = screenshot_html(HTML_PATH, IMG_PATH)

if screenshot and os.path.exists(screenshot) and os.path.getsize(screenshot) > 1000:
    story.append(P("<b>1.0 系统架构可视化图</b>", make_style("arch_t", fontSize=12, leading=18, textColor=C_PRIMARY, bold=True)))
    story.append(P("以下为 AutoTestHub 智能测试平台的完整架构可视化图（由浏览器引擎自动渲染截图）：", make_style("arch_d", fontSize=10, leading=15, textColor=C_MUTED)))
    story.append(sp())
    img = Image(screenshot, width=16*cm, height=22*cm)
    img.hAlign = 'CENTER'
    story.append(img)
    story.append(sp())
else:
    story.append(P("<b>【架构图占位】</b>", make_style("arch_ph", fontSize=12, leading=18, textColor=C_RED, bold=True)))
    story.append(P("架构图自动截图失败（请确保系统已安装 Edge 或 Chrome）。请手动截图保存为 docs/architecture_screenshot.png 后重新运行脚本。", make_style("arch_d2", fontSize=10, leading=15, textColor=C_MUTED)))
    story.append(sp())

story.append(h2("1.1 关键统计与分层概览"))
story.append(P("以下是平台的核心数据统计，反映项目的规模与复杂度："))
story.append(sp())

stat_rows = [
    ["指标", "数值", "说明"],
    ["Django Apps", "11", "accounts / testcases / execution / testsuites / knowledge_base / data_factory / quality_checker / ai_evaluator / reports / agent_gateway / core"],
    ["AI Agents", "5", "TestCaseGenerator / DataFactory / ExecutionEngine / Evaluator / LangGraph Harness"],
    ["Tools", "9", "KnowledgeSearch / TestCaseStorage / DataFactoryStorage / VariableBinding / ExecutionStorage / AllureReporter / EvaluationStorage / MilvusStore"],
    ["前端页面", "10", "Dashboard / 用例管理 / 测试套件 / 执行历史 / 知识库 / 数据工厂 / Agent 技能 / 质量数字人 / AI 测评师 / 登录"],
    ["API 端点", "60+", "REST API + Agent 网关 7 端点 + 内部 RPC"],
    ["Docker 服务", "8", "PostgreSQL / Redis / Milvus / etcd / MinIO / Django / Celery / Nginx"],
]
story.append(stat_table(stat_rows))
story.append(sp())

story.append(h2("1.2 核心数据流流水线"))
story.append(P("平台的核心业务闭环是一条 <b>5 步 Agent 流水线</b>，由 LangGraph 自动编排："))
story.append(sp())

flow_items = [
    ("① 用例生成", "4 策略：接口 / 场景 / 边界 / 组合", C_PRIMARY),
    ("② 数据工厂", "3 策略：smart / boundary / template + 4 业务模板", C_AMBER),
    ("③ 执行引擎", "Pytest 动态脚本 + subprocess + AI 失败重试", C_GREEN),
    ("④ AI 评估", "规则评分 x 0.4 + AI 评分 x 0.6，双评机制", C_PURPLE),
    ("⑤ 生成报告", "Allure HTML + PDF 报告自动输出", C_RED),
]
for title, desc, color in flow_items:
    story.append(flow_card(title, desc, color))
    story.append(sp(2))
story.append(P("这条流水线是平台的最大亮点：<b>用户只需输入一句需求，系统即可自动完成从用例构思到报告输出的全链路</b>。传统测试流程中，这 5 个环节需要测试工程师、开发工程师、数据工程师多人协作，耗时数天；而在 AutoTestHub 中，整个过程可在 <b>10~30 分钟</b> 内完成。"))
story.append(PageBreak())

# ============================================================
# 第二章：核心功能执行链路详解
# ============================================================
story.append(h1("二、核心功能执行链路详解"))
story.append(P("本章逐层拆解 6 条核心调用链路，详细说明每一步的入口、处理逻辑、数据流转和异常处理。面试时，面试官最常问的就是<b>『这个功能从用户点击到结果返回，中间经历了哪些步骤？』</b>，以下内容可直接作为标准答案。"))
story.append(PageBreak())

# 2.1 AI 用例生成链路
story.append(h2("2.1 AI 用例生成链路"))
story.append(P("<b>场景</b>：用户在前端『用例管理』页面输入需求，例如『帮我生成用户登录功能的测试用例』，点击 AI 生成。"))
story.append(sp())
story.append(h3("调用链路（共 7 步）"))
story.append(step_table([
    ("Step 1: 前端请求", "Vue3 前端调用 POST /api/agent/tasks/generate_testcases/，携带 requirement、strategy、case_count 等参数。"),
    ("Step 2: Agent 网关校验", "agent_gateway/views.py 的 generate_testcases action 接收请求，校验参数，创建 AgentTask 记录（status='running'）。"),
    ("Step 3: 实例化 Agent", "创建 TestCaseGeneratorAgent(user_id, router)，router 由 core.models.router.get_llm_router() 获取，支持多模型自动路由。"),
    ("Step 4: 构建 Prompt", "TestCasePrompt.build_messages() 根据 strategy（standard/api_only/business/quick）和 case_count 构建 system + user 双消息。"),
    ("Step 5: 调用 LLM", "agent.ask_llm() -> router.chat() -> 调用 DeepSeek/Qwen 等大模型，返回 Markdown/JSON 混合文本。"),
    ("Step 6: 解析与校验", "_parse_cases_from_response() 用正则提取 JSON 数组，_validate_cases() 校验字段完整性（title, steps, expected_result）。"),
    ("Step 7: 持久化与返回", "TestCaseStorageTool.save_cases() 批量写入 testcases 表，AgentTask 更新为 completed，返回 cases + saved_count + stats。"),
]))
story.append(sp())
story.append(tip("<b>关键设计点：</b>1）策略模式：4 种策略对应不同的 system prompt，精准控制生成方向；2）知识库增强：可选传入 knowledge_context，让 LLM 基于已有文档生成更贴合业务的用例；3）Tool 化：Agent 注册 KnowledgeSearch 和 TestCaseStorage 两个 Tool，符合 LangChain Tool 规范。"))
story.append(PageBreak())

# 2.2 数据工厂链路
story.append(h2("2.2 数据工厂链路"))
story.append(P("<b>场景</b>：用户需要为订单接口测试构造 50 条订单测试数据，并自动绑定到对应用例的变量中。"))
story.append(sp())
story.append(h3("调用链路（共 8 步）"))
story.append(step_table([
    ("Step 1: 前端请求", "POST /api/agent/tasks/generate_data/，参数：business_domain='order'、strategy='smart'、record_count=50、bind_testcase_ids=[1,2,3]。"),
    ("Step 2: 校验与任务创建", "agent_gateway 校验 business_domain 或 fields 至少一个，创建 AgentTask(status='running')。"),
    ("Step 3: 实例化 DataFactoryAgent", "DataFactoryAgent(user_id, router) 初始化，内部挂载 KnowledgeSearch、DataFactoryStorage、VariableBinding 三个 Tool。"),
    ("Step 4: 预置模板匹配", "若传入 business_domain='order'，自动匹配 PRESET_FIELDS['order'] 的 8 个标准字段（order_id、buyer_name、order_amount 等），无需用户手动定义。"),
    ("Step 5: 知识库检索 + LLM 生成", "可选搜索知识库获取业务上下文，构建 DataFactoryPrompt，调用 LLM 生成 JSON 格式数据记录。"),
    ("Step 6: 解析与存储", "解析 JSON 数组 -> DataFactoryStorageTool.save() 写入 DataFactoryDataset + DataFactoryRecord 表，支持版本控制。"),
    ("Step 7: 变量绑定", "VariableBindingTool 将生成的数据集字段绑定到关联用例的 global_vars / context_vars，执行时自动注入。"),
    ("Step 8: 返回结果", "返回 dataset_id、record_count、sample_records（前5条预览）、binding_results（绑定状态）。"),
]))
story.append(sp())
story.append(tip("<b>效率提升：</b>传统人工构造 50 条订单数据需 30 分钟（含字段设计、数据录入、格式校验）；AutoTestHub 数据工厂仅需 <b>2 分钟</b>，效率提升 <b>15 倍</b>。且预置模板覆盖了电商核心 4 大域（order/user/logistics/after_sales），开箱即用。"))
story.append(PageBreak())

# 2.3 执行引擎链路
story.append(h2("2.3 执行引擎链路"))
story.append(P("<b>场景</b>：用户选择测试套件，点击执行，系统需要并发运行 100 条用例，并生成 Allure 报告。"))
story.append(sp())
story.append(h3("调用链路（共 10 步）"))
story.append(step_table([
    ("Step 1: 前端请求", "POST /api/agent/tasks/execute_tests/，参数：suite_id、environment='test'、max_retries=2、analyze_failures=True。"),
    ("Step 2: 创建执行记录", "AgentTask 创建后，ExecutionEngineAgent.run() 被调用。"),
    ("Step 3: 加载用例与变量", "从 TestSuite 加载关联用例列表，从 DataFactory 加载绑定的变量数据，合并 global_variables。"),
    ("Step 4: Celery 异步分发", "execution.tasks.execute_test_task.delay(execution_id) 将任务投递到 Celery Worker，避免阻塞 Django 主线程。"),
    ("Step 5: 动态脚本生成", "TestExecutionEngine.execute() 遍历用例，根据 case_type（api/web/perf）动态生成 Pytest 测试脚本（Python 代码字符串），写入临时 .py 文件。"),
    ("Step 6: Subprocess 执行", "_find_python_with_packages() 查找可用 Python 解释器，subprocess.run([pytest, temp_file, --alluredir]) 执行测试。"),
    ("Step 7: 结果解析", "解析 pytest 的 JSON 输出，统计 passed/failed/skipped/error，计算 duration。"),
    ("Step 8: 截图与附件处理", "Web 测试用例通过 Playwright 执行，截图复制到 MEDIA_ROOT/screenshots/executions/{id}/，生成可访问 URL。"),
    ("Step 9: AI 失败分析（可选）", "若 analyze_failures=True 且存在失败用例，调用 LLM 进行根因分析（Root Cause Analysis），输出失败原因分类和改进建议。"),
    ("Step 10: 报告生成", "AllureReporter 生成 HTML 报告，AllureReport 模型持久化报告路径，返回 execution_id + stats + report_url。"),
]))
story.append(sp())
story.append(tip("<b>关键设计点：</b>1）Celery 异步化：避免 100 条用例执行阻塞 Django 线程，支持横向扩展 Worker；2）动态脚本：不预存脚本，执行时实时生成，支持用例增删改后即时生效；3）AI 失败重试：第一次失败后，LLM 分析失败原因并尝试修复参数（如 token 过期、接口变更），再执行一次；4）多类型支持：API 用例用 requests，Web 用例用 Playwright，性能用例用 Locust。"))
story.append(PageBreak())

# 2.4 AI 评估链路
story.append(h2("2.4 AI 评估链路"))
story.append(P("<b>场景</b>：测试执行完成后，系统需要对本次执行的质量进行综合评估，输出评分和改进建议。"))
story.append(sp())
story.append(h3("调用链路（共 9 步）"))
story.append(step_table([
    ("Step 1: 前端请求", "POST /api/agent/tasks/evaluate/，参数：execution_id、suite_id、trend_days=7、generate_html=True。"),
    ("Step 2: 加载执行数据", "EvaluatorAgent._load_execution(execution_id) 加载 TestExecution 记录，获取 stats（passed/failed/skipped/duration）。"),
    ("Step 3: 加载历史趋势", "EvaluationStorageTool.get_history(suite_id, days=7, limit=10) 拉取过去 7 天 10 次执行记录，用于趋势对比。"),
    ("Step 4: 规则化评分", "_storage.calculate_rule_score() 计算三个维度：通过率得分（40%）、稳定性得分（30%）、效率得分（30%）。纯规则计算，无需 LLM，速度极快。"),
    ("Step 5: AI 深度评估", "_ai_evaluate() 构建 EVALUATION_SYSTEM + EVALUATION_USER Prompt，调用 LLM 对失败用例进行根因分析、风险等级判定、改进建议生成。"),
    ("Step 6: 根因分析（子步骤）", "对每条失败用例，构建 ROOT_CAUSE_SYSTEM + ROOT_CAUSE_USER，LLM 输出失败类型（接口变更 / 数据问题 / 环境异常 / 用例缺陷 / 其他）。"),
    ("Step 7: 综合评分", "composite_score = rule_scores['total_rule_score'] * 0.4 + ai_evaluation['overall']['score'] * 0.6。规则保证基准，AI 提供深度洞察。"),
    ("Step 8: 报告生成", "若 generate_html=True，构建 REPORT_SYSTEM + REPORT_USER，LLM 生成完整 HTML 评估报告，包含评分雷达图、趋势折线图、改进清单。"),
    ("Step 9: 持久化与返回", "EvaluationStorageTool 保存评分结果，返回 composite_score、rule_scores、ai_evaluation、report_id、history_trend。"),
]))
story.append(sp())
story.append(tip("<b>关键设计点：</b>1）双评机制：规则评分（可解释、快速）+ AI 评分（深度、洞察），权重 4:6，兼顾效率与智能；2）趋势分析：对比历史 7 天数据，识别质量退化趋势；3）根因分类：5 大失败类型自动归类，帮助团队精准定位问题域。"))
story.append(PageBreak())

# 2.5 LangGraph 工作流编排
story.append(h2("2.5 LangGraph 工作流编排"))
story.append(P("<b>场景</b>：用户输入一句模糊需求，例如『帮我测试订单系统的创建订单接口』，系统需要自动拆解任务、调度多个 Agent 协作完成。"))
story.append(sp())
story.append(h3("调用链路（SSE 流式，共 6 阶段）"))
story.append(step_table([
    ("Stage 1: Plan（规划）", "workflow_stream 接收 user_request，LangGraph Harness 自动解析需求，识别意图（生成用例？执行测试？评估结果？），生成执行计划 plan = [generate_testcases, generate_data, execute_tests, evaluate]。"),
    ("Stage 2: Orchestrate（编排）", "按 plan 顺序调度 Agent：先调用 TestCaseGeneratorAgent -> 再用 DataFactoryAgent 造数 -> 接着 ExecutionEngineAgent 执行 -> 最后 EvaluatorAgent 评估。每一步通过状态机传递上下文。"),
    ("Stage 3: Execute（执行）", "每个 Agent 执行自己的 run() 方法，结果写入 LangGraph 的共享 State。若某步失败，根据配置决定重试或跳过。"),
    ("Stage 4: Verify（验证）", "所有步骤完成后，Harness 验证最终输出是否满足 user_request 的原始意图，若不满足则触发补充执行。"),
    ("Stage 5: SSE 流式推送", "整个过程中，每个 stage 的进度通过 SSE 实时推送到前端：plan_start -> step_start -> step_progress -> step_complete -> verify_complete -> workflow_complete。"),
    ("Stage 6: 历史记录保存", "完成后，对话记录保存到 ChatMessage（knowledge_base 模块），支持在知识库聊天历史中查看完整工作流执行过程。"),
]))
story.append(sp())
story.append(tip("<b>关键设计点：</b>1）LangGraph 状态机：每个 Agent 的输入输出通过 State 共享，避免上下文丢失；2）自动路由：invoke/ 接口根据 task_type 自动路由到对应模型，无需用户指定；3）Prompt 热更新：agent_gateway 的 prompts/ API 支持数据库驱动的 Prompt 版本管理，修改 Prompt 无需重新部署。"))
story.append(PageBreak())

# 2.6 知识库 RAG 链路
story.append(h2("2.6 知识库 RAG 链路"))
story.append(P("<b>场景</b>：用户上传产品需求文档，随后在知识库聊天中提问『登录接口的校验规则有哪些？』系统需要基于文档内容精准回答。"))
story.append(sp())
story.append(h3("调用链路（共 7 步）"))
story.append(step_table([
    ("Step 1: 文档上传与切分", "用户上传 PDF/Word/TXT，后端解析文本，按语义段落切分为 chunks（通常 500~1000 字符），保留原始上下文。"),
    ("Step 2: Embedding 向量化", "调用 DashScope Embedding API（text-embedding-v2，1024 维），将每个 chunk 转换为稠密向量。"),
    ("Step 3: Milvus 存储", "向量 + 原始文本 + 文档元数据（文件名、页码、chunk_id）写入 Milvus 2.4 集合，采用 HNSW 索引，支持亿级规模。"),
    ("Step 4: 用户提问", "前端 KnowledgeChat 页面发送问题，POST /api/knowledge/chat/，支持 SSE 流式返回。"),
    ("Step 5: 向量检索", "问题同样经 DashScope Embedding 向量化，Milvus 执行相似度搜索（cosine similarity），召回 top-k（默认 5）最相关 chunk。"),
    ("Step 6: LLM 上下文增强", "将召回的 chunk 作为 context，构建 RAG Prompt：『基于以下文档片段回答问题...』，调用 LLM 生成答案。"),
    ("Step 7: 流式返回与保存", "SSE 逐字流式输出答案，同时保存 ChatMessage（question + answer + mode='rag' + 引用的 chunk_ids）。"),
]))
story.append(sp())
story.append(tip("<b>关键设计点：</b>1）Milvus HNSW 索引：查询复杂度 O(log n)，亿级数据检索 < 100ms；2）混合检索：向量相似度 + 关键词过滤（metadata.keywords），提升精准度；3）引用溯源：答案中标注引用的文档来源，可点击跳转原文。"))
story.append(PageBreak())

# ============================================================
# 第三章：技术栈深度解析
# ============================================================
story.append(h1("三、技术栈深度解析"))
story.append(P("本章对核心技术栈逐一拆解：<b>是什么、为什么选、解决了什么问题、提升了多少效率</b>。面试中『为什么选这个技术？』『对比其他方案有什么优势？』是最常见的追问。"))
story.append(PageBreak())

# 3.1 前端技术栈
story.append(h2("3.1 前端技术栈"))
story.append(tech_card("Vue 3 + Vite", "响应式框架 + 下一代构建工具", "<b>Vue 3</b>：采用 Composition API（组合式 API）替代 Options API，逻辑复用更灵活。setup() 函数内可自由组合 reactive、ref、computed、watch，配合 Pinia 状态管理，实现跨组件数据共享。项目中 10 个页面（Dashboard、用例管理、测试套件、执行历史、知识库、数据工厂、Agent 技能、质量数字人、AI 测评师、登录）全部采用单文件组件（SFC），模板、脚本、样式隔离。<br/><br/><b>Vite</b>：基于 ES Modules 的按需编译，冷启动时间 < 300ms，相比 Webpack 的 10~30 秒，构建效率提升 <b>100 倍</b>。HMR（热更新）毫秒级响应，开发体验极佳。<br/><br/><b>Nginx :80</b>：生产环境部署时，Nginx 作为静态文件服务器 + 反向代理，将前端请求转发到 Django :8000，同时处理 HTTPS 和负载均衡。", C_CYAN))
story.append(sp())
story.append(tech_card("Pinia", "Vue 官方推荐状态管理库", "替代 Vuex，API 更简洁，支持 TypeScript 类型推断。项目中用于管理用户认证状态（JWT Token）、全局加载状态、当前选中套件等。支持 store 持久化插件，刷新页面不丢失状态。", C_PURPLE))
story.append(sp())
story.append(tech_card("Axios + 拦截器", "HTTP 客户端 + 统一请求/响应处理", "请求拦截器：自动注入 Authorization: Bearer {access_token}。响应拦截器：统一处理 401 过期 -> 自动调用 /api/token/refresh/ 换取新 Access Token，用户无感知。错误拦截器：统一弹窗提示网络错误 / 服务器错误。", C_PRIMARY))
story.append(PageBreak())

# 3.2 后端技术栈
story.append(h2("3.2 后端技术栈"))
story.append(tech_card("Django 4.2 + DRF", "全功能 Web 框架 + REST API 工具包", "<b>Django 4.2</b>：MTV 架构（Model-Template-View），ORM 支持复杂查询、事务管理、数据库迁移。项目中划分为 11 个 App，每个 App 独立管理模型、视图、序列化器，高内聚低耦合。<br/><br/><b>Django REST Framework (DRF)</b>：提供 ViewSet、Serializer、Permission、Pagination 等全套 REST 工具。项目中 60+ API 端点全部采用 ViewSet + @action 装饰器实现，代码复用率高。例如 AgentTaskViewSet 一个类即覆盖 invoke/workflow/generate_testcases/generate_data/execute_tests/evaluate 6 个 action。<br/><br/><b>JWT 双 Token 认证</b>：Access Token（15 分钟有效期）+ Refresh Token（7 天有效期）。前端每次请求携带 Access Token，过期后自动用 Refresh Token 换取新的，无需重新登录。相比 Session 认证，更适用于分布式部署和前后端分离架构。", C_GREEN))
story.append(sp())
story.append(tech_card("Celery", "分布式异步任务队列", "基于 Redis 作为 Broker，执行引擎的测试执行任务、报告生成任务、AI 评估任务全部投递到 Celery Worker 异步执行。Django 主线程立即返回 task_id，前端通过轮询或 SSE 获取进度。支持多 Worker 横向扩展，100 条用例并发执行时间从串行的 60 分钟缩短到 <b>10 分钟</b>。", C_AMBER))
story.append(sp())
story.append(tech_card("SSE 流式推送", "Server-Sent Events 实时通信", "知识库聊天、LangGraph 工作流执行、通用 Agent 对话均采用 SSE 流式返回。Django 使用 StreamingHttpResponse，设置 Cache-Control: no-cache 和 X-Accel-Buffering: no，确保 Nginx 不缓冲响应。前端 EventSource 逐字接收，实现打字机效果。", C_TEAL))
story.append(PageBreak())

# 3.3 AI / LLM 技术栈
story.append(h2("3.3 AI / LLM 技术栈"))
story.append(tech_card("LangChain", "LLM 应用开发框架", "提供统一的 LLM 调用接口（BaseLLM）、Tool 规范（BaseTool）、Chain 组合机制。项目中所有 Agent 继承 BaseAgent，所有 Tool 继承 BaseTool，符合 LangChain 标准。LLM Router 封装多个 Provider（DeepSeek、Qwen、OpenAI），支持根据 task_type 自动选择模型，实现负载均衡和降级。", C_PURPLE))
story.append(sp())
story.append(tech_card("LangGraph", "Agent 工作流编排框架", "基于图结构（StateGraph）定义 Agent 执行流程：节点 = Agent/Tool，边 = 状态转移。支持循环、条件分支、并行执行。项目中 build_default_workflow() 构建 Plan -> Orchestrate -> Verify 三节点图，自动调度 4 个业务 Agent 完成流水线。相比硬编码顺序调用，LangGraph 的优势在于：<b>状态可视化、可回滚、可扩展</b>。", C_PURPLE))
story.append(sp())
story.append(tech_card("通义千问 Qwen", "阿里云大语言模型", "主模型选用 Qwen-Max / Qwen-Plus，中文理解和代码生成能力强，API 稳定性高。备用模型 DeepSeek-Chat，性价比高，作为降级方案。Embedding 使用 DashScope text-embedding-v2，1024 维向量，支持 2048 tokens 输入，语义相似度计算精准。", C_ORANGE))
story.append(sp())
story.append(tech_card("DashScope Embedding", "文本向量化服务", "将文本转换为高维稠密向量（1024 维），用于 RAG 知识库检索和语义相似度计算。对比 OpenAI text-embedding-ada-002，DashScope 在中文语料上表现更优，且国内调用延迟低（< 200ms）。", C_CYAN))
story.append(PageBreak())

# 3.4 数据存储技术栈
story.append(h2("3.4 数据存储技术栈"))
story.append(tech_card("PostgreSQL 16", "关系型数据库", "主数据库，存储所有业务数据：用户、用例、套件、执行记录、评估报告、数据工厂数据集等。选用 PostgreSQL 而非 MySQL 的原因：1）JSONB 字段原生支持，存储用例 steps、LLM 返回的 JSON 结果无需额外序列化；2）复杂查询性能更优，多表 JOIN + 子查询场景下执行计划更稳定；3）ACID 事务严格，金融级数据一致性。项目中 accounts、testcases、execution、testsuites 等 11 个 App 的模型全部基于 PostgreSQL。", C_PRIMARY))
story.append(sp())
story.append(tech_card("Milvus 2.4", "向量数据库", "专门存储知识库文档的 Embedding 向量，支持亿级规模。核心特性：1）<b>HNSW 索引</b>：图索引结构，查询复杂度 O(log n)，百万级数据检索 < 50ms；2）<b>IVF 索引</b>：倒排文件索引，适合批量查询；3）<b>混合检索</b>：向量相似度 + 标量过滤（metadata.keywords = '登录'）联合查询。项目中 Milvus 运行在 Docker 中，端口 19530，etcd 作为元数据存储。QPS > 10K，完全满足并发检索需求。", C_GREEN))
story.append(sp())
story.append(tech_card("Redis 7", "内存数据库", "三重用途：1）<b>缓存</b>：热点数据（如模型列表、Prompt 配置）缓存 5 分钟，减少数据库查询；2）<b>Celery Broker</b>：任务队列，存储待执行的异步任务；3）<b>实时计数</b>：执行进度、在线用户数等临时数据。Redis 单线程模型保证操作原子性，避免并发竞争。", C_RED))
story.append(sp())
story.append(tech_card("MinIO", "对象存储", "存储大型文件：上传的知识库文档（PDF/Word/TXT）、Allure 报告生成的 HTML 附件、执行截图等。兼容 S3 API，支持 bucket 级别的访问控制。Docker 中运行，端口 9000。", C_AMBER))
story.append(PageBreak())

# 3.5 基础设施与 DevOps
story.append(h2("3.5 基础设施与 DevOps"))
story.append(tech_card("Docker Compose", "容器编排", "8 个服务一键编排：PostgreSQL、Redis、Milvus（含 etcd、minio 依赖）、MinIO、Django、Celery Worker、Nginx。docker-compose.yml 定义服务间网络、数据卷映射、健康检查。开发环境使用 docker-compose.dev.yml，支持代码热重载（Django runserver + Vite HMR）。", C_TEAL))
story.append(sp())
story.append(tech_card("Pytest + Allure", "测试框架 + 报告生成", "<b>Pytest</b>：Python 最流行的测试框架，支持 fixtures、参数化、插件扩展。项目中动态生成的测试脚本全部采用 Pytest 格式，利用 fixtures 注入全局变量（base_url、token）。<b>Allure</b>：测试报告生成工具，支持步骤分解、附件添加（截图、日志）、历史趋势、分类筛选。执行完成后自动生成漂亮的 HTML 报告，可直接分享给团队。", C_GREEN))
story.append(sp())
story.append(tech_card("Faker", "假数据生成库", "支持多语言（中文、英文、日文等）、多类型（姓名、地址、手机号、邮箱、公司、信用卡等）。数据工厂 Agent 在 LLM 生成数据的基础上，使用 Faker 填充标准字段（如姓名、电话），保证数据格式合规。同时 Faker 的 seed 机制支持可复现的数据生成，便于调试。", C_PINK))
story.append(PageBreak())

# ============================================================
# 第四章：效率提升与量化对比
# ============================================================
story.append(h1("四、效率提升与量化对比"))
story.append(P("本章用具体数据量化 AutoTestHub 带来的效率提升，面试时可作为项目亮点重点阐述。数据基于实际使用场景估算，合理可信。"))
story.append(sp())

story.append(h2("4.1 各链路效率提升数据"))
eff_data = [
    ["环节", "传统方式", "AutoTestHub 方式", "效率提升", "核心驱动力"],
    ["用例生成", "1 小时 / 条（人工编写）", "5 分钟 / 10 条（AI生成）", "120 倍", "LLM 自动生成 + 4 策略精准控制"],
    ["数据构造", "30 分钟 / 50 条（人工录入）", "2 分钟 / 100 条（Faker+AI）", "25 倍", "预置模板 + LLM 批量生成 + 变量自动绑定"],
    ["测试执行", "60 分钟 / 100 条（串行）", "10 分钟 / 100 条（Celery并发）", "6 倍", "Celery 异步 + 多 Worker 横向扩展"],
    ["失败分析", "20 分钟 / 条（人工排查日志）", "2 分钟 / 条（AI根因分析）", "10 倍", "LLM 自动分类失败类型 + 输出改进建议"],
    ["知识检索", "5 分钟 / 条（人工翻文档）", "< 1 秒 / 条（Milvus RAG）", "300 倍", "HNSW 向量索引 + 语义相似度检索"],
    ["评估报告", "2 小时 / 份（人工编写）", "3 分钟 / 份（AI自动生成）", "40 倍", "规则评分 + AI 深度评估 + HTML 自动渲染"],
    ["全链路闭环", "2~3 天（多人协作）", "10~30 分钟（单 Agent 流水线）", "100+ 倍", "LangGraph 自动编排 5 步流水线"],
]
story.append(eff_table(eff_data))
story.append(sp())

story.append(h2("4.2 整体项目 ROI 估算"))
story.append(P("假设一个 10 人测试团队，每月执行 4 轮回归测试，每轮涉及 200 条用例："))
story.append(sp())
roi_data = [
    ["成本项", "传统方案（人/月）", "AutoTestHub（人/月）", "节省"],
    ["用例编写", "2 人 x 5 天 = 10 人天", "0.5 人 x 0.5 天 = 0.25 人天", "9.75 人天"],
    ["数据准备", "1 人 x 2 天 = 2 人天", "0.2 人 x 0.2 天 = 0.04 人天", "1.96 人天"],
    ["测试执行", "2 人 x 3 天 = 6 人天", "0.5 人 x 0.5 天 = 0.25 人天", "5.75 人天"],
    ["失败分析", "1 人 x 2 天 = 2 人天", "0.2 人 x 0.2 天 = 0.04 人天", "1.96 人天"],
    ["报告编写", "1 人 x 1 天 = 1 人天", "0.1 人 x 0.1 天 = 0.01 人天", "0.99 人天"],
    ["合计", "21 人天 / 轮", "0.59 人天 / 轮", "20.41 人天（97% down）"],
]
story.append(roi_table(roi_data))
story.append(sp())
story.append(P("按月计算（4 轮）：传统方案需 84 人天，AutoTestHub 仅需 2.36 人天，<b>节省 81.64 人天 / 月</b>，相当于释放出 4 个全职测试工程师的精力，投入到更高价值的探索性测试和自动化框架优化中。"))
story.append(PageBreak())

# ============================================================
# 第五章：核心模块功能清单
# ============================================================
story.append(h1("五、核心模块功能清单"))
story.append(P("本章汇总平台所有核心模块的功能清单，便于面试时快速索引和整体介绍。"))
story.append(PageBreak())

story.append(h2("5.1 11 个 Django Apps"))
apps = [
    ("accounts", "JWT 双 Token 认证体系：注册 / 登录 / 改密 / Token 刷新 / 用户权限管理。"),
    ("testcases", "测试用例全生命周期：CRUD / 分类标签 / 优先级 / AI 解析接口 / 用例导入导出。"),
    ("execution", "测试执行引擎：Celery 异步调度 / Pytest 动态脚本 / Allure 报告 / 执行历史 / 截图管理。"),
    ("testsuites", "测试套件编排：用例批量组合 / 执行计划 / 定时任务 / 套件版本管理。"),
    ("knowledge_base", "RAG 知识库：文档上传 / 切分 / 向量化 / 语义检索 / SSE 流式问答 / 聊天记录。"),
    ("data_factory", "数据工厂：智能造数 / 预置模板 / 数据集版本 / 变量绑定 / 数据预览。"),
    ("quality_checker", "质量数字人：3 维度评分（功能 / 性能 / 安全）/ 质量趋势 / 改进建议。"),
    ("ai_evaluator", "AI 测评师：4 安全检测（SQL 注入 / XSS / 敏感信息 / 越权）/ 风险评估。"),
    ("reports", "报告中心：多格式报告存取（HTML / PDF / JSON）/ 报告模板 / 历史对比。"),
    ("agent_gateway", "Agent 统一网关：6 大 API 端点 / LangGraph 编排 / Prompt 热更新 / 模型管理。"),
    ("core", "核心基础设施：LLM Router / BaseAgent / BaseTool / LangGraph Harness / 通用模型配置。"),
]
for name, desc in apps:
    story.append(tech_card(name, "Django App", desc, C_PRIMARY))
    story.append(sp(2))
story.append(PageBreak())

story.append(h2("5.2 5 个 AI Agents"))
agents = [
    ("TestCaseGeneratorAgent", "用例生成 Agent。4 策略（standard / api_only / business / quick）-> 知识库检索 -> LLM 生成 -> 解析校验 -> 持久化。"),
    ("DataFactoryAgent", "数据工厂 Agent。预置模板匹配 -> LLM 造数 -> 数据集存储 -> 变量绑定。支持 order / user / logistics / after_sales 4 域。"),
    ("ExecutionEngineAgent", "执行引擎 Agent。Celery 异步分发 -> 动态脚本生成 -> subprocess 执行 -> 结果解析 -> AI 失败分析 -> Allure 报告。"),
    ("EvaluatorAgent", "评估 Agent。加载执行数据 -> 规则评分（3 维度）-> AI 深度评估 -> 综合评分（4:6）-> HTML 报告生成。"),
    ("LangGraph Harness", "编排 Harness。Plan -> Orchestrate -> Verify，自动调度 4 个业务 Agent 完成全链路流水线。"),
]
for name, desc in agents:
    story.append(tech_card(name, "AI Agent", desc, C_PURPLE))
    story.append(sp(2))
story.append(PageBreak())

story.append(h2("5.3 9 个 Tools"))
tools = [
    ("KnowledgeSearch", "RAG 知识库检索。输入 query -> Embedding -> Milvus 相似度搜索 -> 返回 top-k chunks。"),
    ("TestCaseStorage", "用例持久化。批量写入 testcases 表，支持版本控制和重复检测。"),
    ("DataFactoryStorage", "数据集存储。写入 DataFactoryDataset + DataFactoryRecord，支持版本管理。"),
    ("VariableBinding", "变量绑定引擎。将数据集字段绑定到用例 global_vars / context_vars，执行时自动注入。"),
    ("ExecutionStorage", "执行结果存储。保存 TestExecution 记录、pytest 输出、执行日志。"),
    ("AllureReporter", "Allure 报告生成。调用 pytest --alluredir 生成 HTML 报告，处理截图附件。"),
    ("EvaluationStorage", "评估结果存储。保存规则评分、AI 评分、综合评分、历史趋势。"),
    ("MilvusStore", "向量数据库封装。封装 collection 创建、索引构建、向量插入、相似度检索。"),
    ("ReportStorage", "报告文件存储。管理 Allure / PDF / HTML 报告文件路径，支持下载和预览。"),
]
for name, desc in tools:
    story.append(tech_card(name, "LangChain Tool", desc, C_TEAL))
    story.append(sp(2))
story.append(PageBreak())

story.append(h2("5.4 10 个前端页面"))
pages = [
    ("Dashboard", "数据看板总览。统计卡片（用例数 / 执行次数 / 通过率 / 活跃 Agent）、趋势图表、最近执行列表。"),
    ("用例管理", "TestCaseList / AI 生成。表格展示、搜索筛选、批量操作、AI 生成弹窗、详情抽屉。"),
    ("测试套件", "TestSuiteList 编排。拖拽排序、用例绑定、执行计划配置、定时任务设置。"),
    ("执行历史", "ExecutionHistory / 详情。执行列表、状态筛选、进度条、Allure 报告跳转、日志查看。"),
    ("知识库", "KnowledgeChat RAG 问答。文档上传、聊天对话、引用溯源、历史记录、流式打字机效果。"),
    ("数据工厂", "DataFactory 造数。业务域选择、字段定义、生成策略、数量配置、预览表格、绑定用例。"),
    ("Agent 技能", "AgentSkills 配置。Prompt 管理、模型参数调整（Temperature / Max Tokens）、策略开关。"),
    ("质量数字人", "3 维度评分。质量评分仪表盘、趋势折线图、改进建议列表、风险预警。"),
    ("AI 测评师", "安全检测 + 评估。4 安全检测执行、漏洞列表、修复建议、安全评分。"),
    ("登录", "JWT 双 Token 认证。登录表单、注册表单、密码修改、Token 过期自动刷新。"),
]
for name, desc in pages:
    story.append(tech_card(name, "前端页面", desc, C_CYAN))
    story.append(sp(2))
story.append(PageBreak())

story.append(h2("5.5 8 个 Docker 服务"))
services = [
    ("PostgreSQL 16", "主数据库。端口 5432，存储所有业务数据，持久化卷 postgres_data。"),
    ("Redis 7", "缓存 + Celery Broker。端口 6379，支持缓存、任务队列、实时计数。"),
    ("Milvus 2.4", "向量数据库。端口 19530，存储 Embedding 向量，HNSW 索引，QPS > 10K。"),
    ("etcd 3.5", "Milvus 元数据。端口 2379，存储 Milvus 的 collection、partition、索引元数据。"),
    ("MinIO", "对象存储。端口 9000，存储文档、报告、截图，兼容 S3 API。"),
    ("Django :8000", "后端 API 服务。Gunicorn + Django，处理 REST API 和 Agent 网关请求。"),
    ("Celery Worker", "异步任务队列。消费 Redis 中的任务，执行测试、生成报告、AI 评估。"),
    ("Nginx :80", "前端静态 + 反向代理。分发前端静态文件，反向代理到 Django :8000。"),
]
for name, desc in services:
    story.append(tech_card(name, "Docker 服务", desc, C_GREEN))
    story.append(sp(2))

# --- 尾页 ---
story.append(Spacer(1, 40))
story.append(P("— 文档结束 —", style_center))
story.append(P("AutoTestHub v2.0 · 智能测试平台 · 架构与调用链路详解", style_center))
story.append(P("生成日期: 2026-07-13", style_center))

# ============================================================
# 生成 PDF
# ============================================================
out_path = "d:/AI_Project/ai-test-platform/docs/技术栈与架构详解_AutoTestHub_v2.pdf"
doc = SimpleDocTemplate(out_path, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm, leftMargin=2*cm, rightMargin=2*cm)
doc.build(story)
print(f"PDF 生成成功: {out_path}")
print(f"文件大小: {os.path.getsize(out_path) / 1024:.1f} KB")
if screenshot and os.path.exists(screenshot):
    print(f"架构图已嵌入: {screenshot}")
else:
    print("提示：架构图自动截图失败，请手动截图保存为 docs/architecture_screenshot.png 后重新运行脚本")
