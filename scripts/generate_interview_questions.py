"""
面试题生成脚本：根据 AutoTestHub 平台技术栈生成 50 道面试题 (PDF)
"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ============================================================
# 字体
# ============================================================
FONT_REGULAR = 'ChineseFont'
pdfmetrics.registerFont(TTFont('ChineseFont', 'C:/Windows/Fonts/msyh.ttc', subfontIndex=0))

# ============================================================
# 颜色
# ============================================================
C_PRIMARY = HexColor('#1a56db')
C_DARK = HexColor('#1e293b')
C_TEXT = HexColor('#334155')
C_LIGHT_BG = HexColor('#eff6ff')
C_GREEN = HexColor('#16a34a')
C_ORANGE = HexColor('#ea580c')
C_RED = HexColor('#dc2626')
C_BORDER = HexColor('#e2e8f0')
C_CODE_BG = HexColor('#f1f5f9')
C_GREY = HexColor('#64748b')

# ============================================================
# 样式
# ============================================================
style_title = ParagraphStyle('T', fontName=FONT_REGULAR, fontSize=22, leading=30,
    textColor=C_DARK, spaceAfter=4*mm, alignment=TA_LEFT)
style_subtitle = ParagraphStyle('ST', fontName=FONT_REGULAR, fontSize=10, leading=14,
    textColor=C_GREY, spaceAfter=8*mm)
style_h1 = ParagraphStyle('H1', fontName=FONT_REGULAR, fontSize=16, leading=22,
    textColor=C_PRIMARY, spaceBefore=10*mm, spaceAfter=4*mm)
style_h2 = ParagraphStyle('H2', fontName=FONT_REGULAR, fontSize=13, leading=18,
    textColor=C_DARK, spaceBefore=5*mm, spaceAfter=2*mm)
style_q = ParagraphStyle('Q', fontName=FONT_REGULAR, fontSize=11, leading=17,
    textColor=HexColor('#0f172a'), spaceBefore=3*mm, spaceAfter=1*mm, leftIndent=2*mm)
style_a = ParagraphStyle('A', fontName=FONT_REGULAR, fontSize=9.5, leading=15,
    textColor=C_TEXT, leftIndent=6*mm, spaceBefore=0.5*mm, spaceAfter=2*mm,
    borderPadding=4, backColor=C_LIGHT_BG)
style_a_label = ParagraphStyle('AL', fontName=FONT_REGULAR, fontSize=9.5, leading=15,
    textColor=C_GREEN)
style_code = ParagraphStyle('CD', fontName=FONT_REGULAR, fontSize=8.5, leading=13,
    textColor=C_TEXT, backColor=C_CODE_BG, leftIndent=10*mm, spaceBefore=0.5*mm, spaceAfter=0.5*mm)
style_footer = ParagraphStyle('FT', fontName=FONT_REGULAR, fontSize=8, leading=12,
    textColor=C_GREY, alignment=TA_CENTER)
style_cat_note = ParagraphStyle('CN', fontName=FONT_REGULAR, fontSize=9, leading=13,
    textColor=C_GREY, spaceBefore=1*mm, spaceAfter=4*mm)


def hr():
    return HRFlowable(width="100%", thickness=0.5, color=C_BORDER, spaceAfter=2*mm, spaceBefore=1*mm)

def q(idx, text):
    return Paragraph(f"<b>Q{idx}.</b> {text}", style_q)

def a(text):
    # 转义所有 HTML 标签，再恢复允许的 <b> </b> <br/>
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = text.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>').replace('&lt;br/&gt;', '<br/>')
    return Paragraph(text, style_a)

def code(text):
    return Paragraph(text.replace('\n', '<br/>').replace(' ', '&nbsp;'), style_code)

def cat_header(name, note=""):
    return [
        Paragraph(name, style_h1),
        Paragraph(note, style_cat_note) if note else Spacer(1, 0),
    ]

def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT_REGULAR, 7)
    canvas.setFillColor(C_GREY)
    canvas.drawString(20*mm, 12*mm, "AutoTestHub 面试题 · 50题完整版")
    canvas.drawRightString(A4[0] - 20*mm, 12*mm, f"第 {doc.page} 页")
    canvas.restoreState()


# ============================================================
# 面试题数据
# ============================================================
questions = [
    # ========== 一、项目深挖（你自己的平台）==========
    ("一、项目深挖 — 你的 AutoTestHub 平台", "面试官最爱问：你做的这个项目到底是怎么回事？每道题都要能说满2分钟。"),

    (1, "请用2分钟介绍一下你的 AutoTestHub 平台，包括它解决了什么问题、你的角色是什么。",
     "【答题框架】<br/>"
     "1. <b>一句话定位</b>：AI驱动的全栈自动化测试平台，覆盖接口/Web/性能三大测试类型。<br/>"
     "2. <b>解决什么问题</b>：传统测试团队面临用例编写效率低、知识分散（文档难查）、AI应用质量缺乏系统化评测手段。<br/>"
     "3. <b>我的角色</b>：从0到1独立完成——需求分析→技术选型→前后端开发→AI能力集成→Docker部署。<br/>"
     "4. <b>技术栈亮点</b>：Django+DRF（后端）、Vue3（前端）、Milvus（向量库）、多LLM Provider切换。<br/>"
     "5. <b>核心功能亮点</b>：AI用例生成、RAG知识库问答、多模型编排的AI测评师。<br/>"
     "6. <b>一句话收尾</b>：平台已通过Docker Compose一键部署运行，GitHub开源。"),

    (2, "你平台的 AI 用例生成是怎么实现的？从用户输入到生成用例的完整链路是什么？",
     "【完整链路】<br/>"
     "① 用户在前端填写接口信息（URL、Method、参数说明）或直接粘贴接口文档。<br/>"
     "② 后端接收请求后构造Prompt，包含角色指令（你是一个测试工程师）、输出格式要求（JSON格式、包含用例标题/步骤/断言规则/数据模板）、接口上下文。<br/>"
     "③ 通过LLMProviderFactory选择配置的模型（默认通义千问），调用chat()方法。<br/>"
     "④ LLM返回结构化的JSON，后端解析并填充到TestCase模型字段（api_endpoint、method、headers、assertion_rules等）。<br/>"
     "⑤ 保存到数据库，前端展示生成的用例列表，用户可直接编辑或执行。<br/>"
     "⑥ 关键设计：extract_rules（从响应提取变量）和context_vars（上下文传递）实现接口串联。"),

    (3, "平台里多个LLM提供商（千问/DeepSeek/智谱）是怎么切换的？说说你的设计。",
     "【工厂模式 + 策略模式】<br/>"
     "LLMProviderFactory.create('deepseek') 根据传入名称返回对应的Provider实例。<br/>"
     "所有Provider继承BaseLLMProvider抽象基类，统一实现chat()、chat_stream()、embed()三个接口。<br/>"
     "新增Provider只需：①继承基类 ②实现三个方法 ③注册到工厂的PROVIDERS字典。<br/>"
     "PROVIDERS = { 'dashscope': DashScopeProvider, 'deepseek': DeepSeekProvider, 'glm': GLMProvider }<br/>"
     "业务代码不关心具体是哪个Provider，只调用统一的chat(messages)接口。<br/>"
     "<b>加分点</b>：GLM不支持Embedding，所以它的embed()方法兜底调用DashScopeProvider。"),

    (4, "你的RAG知识库是怎么工作的？从文档上传到AI回答的完整流程。",
     "【六步RAG链路】<br/>"
     "① 文档上传 → 后端保存到服务器并记录Document模型。<br/>"
     "② 文档解析 → 支持PDF(PyPDFLoader)、DOCX(docx2txt)、TXT三种格式，统一转为纯文本。<br/>"
     "③ 文本分块 → RecursiveCharacterTextSplitter(chunk_size=500, overlap=50)做语义分块。<br/>"
     "④ 向量化 → 每批10条，调用DashScope text-embedding-v3（1024维），生成向量列表。<br/>"
     "⑤ 存入Milvus → pymilvus upsert写入Collection。<br/>"
     "⑥ 问答检索 → 用户问题向量化 → Milvus Top-5相似检索 → 拼接Prompt(系统指令+上下文+问题) → LLM生成回答。<br/>"
     "支持knowledge(知识库检索)和chat(纯对话)两种模式切换，流式SSE输出。"),

    (5, "AI测评师模块做了哪些事情？双模型工作流是怎么设计的？",
     "【五步LangGraph工作流】<br/>"
     "① 答案准备：被测AI并行回答所有题目（ThreadPoolExecutor，5线程）。<br/>"
     "② 主模型初评：千问/DeepSeek 并行评分所有题目。<br/>"
     "③ 复核模型评分（条件节点）：当score在40-75分的模糊区间时触发第二模型独立评分。<br/>"
     "④ 仲裁融合：主模型60%权重 + 复核模型40%权重，差异>20分时改为各50%。<br/>"
     "⑤ 综合汇总：准确率(50%) + 平均分(20%) + 速度(15%) + 安全(15%)。<br/>"
     "安全检测四维度：prompt注入/有害内容/数据泄露/偏见毒性。<br/>"
     "<b>降级策略</b>：LangGraph不可用时自动降级为单模型Legacy模式。"),

    (6, "平台中测试执行引擎是怎么设计的？Pytest脚本是如何动态生成的？",
     "【三大引擎并行】<br/>"
     "接口测试：动态生成pytest脚本→subprocess执行→解析JSON结果。<br/>"
     "Web测试：Playwright(精确选择器) + Midscene AI(视觉识别) 双引擎。<br/>"
     "性能测试：Locust压测引擎，实时指标采集。<br/><br/>"
     "【Pytest动态生成流程】<br/>"
     "① 读取Execution记录的测试用例ID列表。<br/>"
     "② 将用例信息、断言规则、提取规则、全局变量分别写入JSON元数据文件。<br/>"
     "③ 用字符串拼接方式生成test_generated.py，内含：变量替换函数、JSONPath提取函数、9种断言操作符、主测试函数(遍历用例→替换变量→发请求→提取变量→断言→保存结果)。<br/>"
     "④ compile()做语法检查。<br/>"
     "⑤ subprocess.run('python -m pytest --alluredir=...')执行。"),

    (7, "你的数据工厂模块是怎么设计的？怎么生成测试数据？",
     "【三层设计】<br/>"
     "Dataset（数据集）→ Template（字段模板）→ Record（具体数据行）。<br/>"
     "支持两种生成方式：<br/>"
     "① Faker规则造数：预设姓名/邮箱/手机号/地址/日期等规则，批量生成。<br/>"
     "② AI智能生成：将业务场景描述发给LLM，生成符合逻辑的真实数据（如订单含商品/金额/地址完整信息）。<br/>"
     "版本管理：Version快照 + 引用追踪，可回滚到历史版本。<br/>"
     "预置业务模板：订单/物流/售后/商家四套模板可直接使用。"),

    (8, "质量数字人模块做了什么事情？评分体系是怎样的？",
     "【三维度评分引擎】<br/>"
     "① 完整性评分(40分)：必填字段是否齐全、用例步骤是否连贯、预期结果是否明确。<br/>"
     "② 格式规范(20分)：命名规范、描述清晰度、是否符合团队模板。<br/>"
     "③ 内容质量(40分)：边界条件覆盖、异常场景考虑、断言有效性。<br/>"
     "重复检测：SequenceMatcher计算文本相似度≥85%标记为重复并警告。<br/>"
     "等级：pass(≥80) / warning(60-79) / fail(<60)。<br/>"
     "支持功能测试和接口测试两种场景的差异化评分。"),

    (9, "你的平台开发过程中，遇到的最大技术难点是什么？怎么解决的？",
     "【选1-2个深入讲】<br/>"
     "① pymilvus 2.3→2.4升级API不兼容 → hit.entity从dict变成NamedTuple，用isinstance做类型兼容。<br/>"
     "② Celery异步任务静默失败 → pypdf缺失导致向量化任务报ImportError但不写错误状态，加try-except+数据库状态回写。<br/>"
     "③ similarity_threshold=0.5过滤过度 → 概括性问题和文档相似度天然低，降为0.0交给LLM自己判断相关性。<br/>"
     "④ SQLite开发→PostgreSQL生产环境差异 → CharField max_length在SQLite不校验，上生产就崩，统一用PostgreSQL开发。"),

    (10, "你的平台是如何处理安全问题的？比如密钥管理、认证授权？",
     "【多层安全】<br/>"
     "① JWT双Token认证：Access Token(24h) + Refresh Token(7d)，simplejwt实现。<br/>"
     "② 三级角色体系：admin/tester/viewer，通过DRF权限类校验。<br/>"
     "③ 密钥管理 ：所有API Key走os.getenv()，.gitignore忽略.env，默认值为空字符串。<br/>"
     "④ 安全检测：AI测评师内置四维安全检测（prompt注入/有害内容/数据泄露/偏见毒性）。<br/>"
     "⑤ CORS限制 + NGINX统一入口防绕过。<br/>"
     "⑥ 踩坑案例：早期.env误提交Git历史→事后全部重置密钥。"),


    # ========== 二、Django / 后端技术 ==========
    ("二、Django & 后端核心技术", "路由、中间件、ORM、序列化——测试开发岗必问基础"),

    (11, "Django的请求处理流程是怎样的？从浏览器输入URL到返回响应的完整链路。",
     "浏览器 → NGINX(反向代理) → Gunicorn(WSGI) → Django Middleware层 → URL路由匹配 → View处理 → Serializer序列化/数据库ORM → Response → Middleware反向处理 → 浏览器。<br/>"
     "中间件执行顺序：请求从上到下（CORS→Security→Session→Common→CSRF→Auth→Message），响应从下到上。<br/>"
     "中间件是洋葱模型：每个中间件的process_request和process_response对称执行。"),

    (12, "Django中间件（Middleware）是什么？你的项目里用了哪些？",
     "Middleware是Django请求/响应处理的钩子链。你的项目用了：<br/>"
     "① corsheaders.middleware.CorsMiddleware：处理跨域请求（需放在最前面）。<br/>"
     "② SecurityMiddleware：HTTPS重定向、XSS防护等安全头。<br/>"
     "③ SessionMiddleware：Session支持。<br/>"
     "④ CommonMiddleware：URL标准化、禁止特定User-Agent。<br/>"
     "⑤ CsrfViewMiddleware：CSRF防护（前后端分离用Token方式）。<br/>"
     "⑥ AuthenticationMiddleware：将用户绑定到request.user。<br/>"
     "⑦ MessageMiddleware：消息框架。<br/>"
     "⑧ XFrameOptionsMiddleware：防点击劫持。"),

    (13, "Django REST Framework 中 ViewSet 和 APIView 的区别？你项目里怎么选的？",
     "【ViewSet】封装了CRUD常用操作（list/create/retrieve/update/destroy），搭配Router自动生成URL。<br/>"
     "【APIView】更底层，需要手动定义get/post/put/delete方法，URL手动配置。<br/>"
     "你的项目：标准CRUD场景用ModelViewSet（如TestCaseViewSet），特殊场景用APIView+@action（如流式问答ask_stream用原生Django View实现SSE）。<br/>"
     "ViewSet配合@action装饰器可实现自定义路由（如 testcases/{id}/debug/）。"),

    (14, "Django ORM 中 select_related 和 prefetch_related 的区别？什么时候用哪个？",
     "select_related：SQL JOIN，一次性查询关联表，适用于ForeignKey/OneToOne关系，底层是INNER JOIN/LEFT JOIN。<br/>"
     "prefetch_related：两次查询+Python拼接，适用于ManyToMany/反向ForeignKey，底层是WHERE id IN (...)。<br/>"
     "规则：一对一或多对一用select_related，多对多用prefetch_related。<br/>"
     "在你项目中：查TestCase列表关联执行记录用select_related，查TestSuite下的TestCase列表(ManyToMany)用prefetch_related。"),

    (15, "JWT 认证的原理是什么？你的双 Token 机制是怎么实现的？",
     "JWT(JSON Web Token)由三部分组成：Header(算法) + Payload(用户ID+过期时间) + Signature(签名)。<br/>"
     "你的实现：djangorestframework-simplejwt，HS256签名。<br/>"
     "双Token：Access Token(短期24小时，明文携带权限) + Refresh Token(长期7天，仅用于刷新)。<br/>"
     "流程：登录→返回双Token→前端每次请求带Access Token→过期后用Refresh Token换取新Access Token→Refresh也过期则重新登录。<br/>"
     "优点：无状态(服务器不存Session)、适合分布式。缺点：无法主动失效(除非加黑名单)。"),

    (16, "Django 的 QuerySet 是惰性求值的，这是什么意思？有什么好处？",
     "QuerySet对象在被创建时不执行数据库查询，只有在实际需要数据时才执行SQL（如遍历、切片、list()、len()）。<br/>"
     "好处：①链式过滤不会重复查库——TestCase.objects.filter(method='POST').filter(priority='P0')只执行1次SQL。<br/>"
     "②分页时不会加载全部数据——queryset[0:20]只查20条。<br/>"
     "③配合缓存避免重复查询。<br/>"
     "注意：print(queryset)会立即执行查询。"),

    (17, "Celery 异步任务的原理是什么？你的项目里 Celery 怎么配置和使用的？",
     "Celery是一个分布式任务队列。架构：Producer(你的Django应用) → Broker(Redis) → Worker(Celery进程) → Result Backend(数据库)。<br/>"
     "配置：BROKER_URL=redis://...，CELERY_TASK_TIME_LIMIT=600秒，4个worker处理不同任务。<br/>"
     "使用场景：知识库文档向量化(耗时操作)、AI测评批量评测(并行5线程)、数据工厂批量造数。<br/>"
     "Windows兼容：开发环境加--pool=solo，生产环境(Docker Linux)默认prefork。<br/>"
     "踩坑经验：Celery任务必须try-except并回写错误状态到数据库。"),

    (18, "什么是 SSE (Server-Sent Events)？你的流式回答是怎么实现的？",
     "SSE是HTTP长连接，服务器向浏览器单向推送数据流，适合AI流式输出场景。<br/>"
     "你的实现：<br/>"
     "① 后端Django原生View返回StreamingHttpResponse，content_type='text/event-stream'。<br/>"
     "② 手动JWT认证（从请求头提取Token）。<br/>"
     "③ 逐token yield输出SSE格式：data: {token}\\n\\n。<br/>"
     "④ 前端用EventSource或fetch+ReadableStream接收，逐字渲染。<br/>"
     "⑤ 断开时保存部分回答到数据库。<br/>"
     "vs WebSocket：SSE单向(服务器→浏览器)、更轻量、HTTP协议原生支持，WebSocket双向但更复杂。"),

    (19, "Django的transaction.atomic()有什么用？什么场景下需要事务？",
     "atomic()将代码块包装为数据库事务，要么全部成功提交，要么全部回滚。<br/>"
     "场景：创建TestCase同时需要关联更新TestSuite中的用例数量——两个操作必须在同一个事务中，否则会出现数据不一致。<br/>"
     "用法：with transaction.atomic(): 或 @transaction.atomic装饰器。<br/>"
     "注意：Django默认是自动提交模式，每条SQL都隐式提交。atomic()会改为手动提交。<br/>"
     "嵌套atomic()会创建保存点(Savepoint)。"),

    (20, "你项目中 DRF 的 Serializer 和 ModelSerializer 的区别？验证逻辑写在哪里？",
     "Serializer：手动定义每个字段，灵活但代码多。<br/>"
     "ModelSerializer：基于Django Model自动生成字段和create/update方法，代码少。<br/>"
     "你的项目：大部分用ModelSerializer（如TestCaseSerializer），复杂验证写在validate()方法或自定义validate_<field>()中。<br/>"
     "验证顺序：字段级validate_<field>() → 对象级validate() → Model的clean()。<br/>"
     "嵌套序列化：用SerializerMethodField处理关联对象的自定义展示。"),


    # ========== 三、数据库 & 存储 ==========
    ("三、数据库 & 存储", "PostgreSQL、Milvus、Redis——数据库是测试开发的必修课"),

    (21, "SQLite 和 PostgreSQL 的区别？你为什么选择 PostgreSQL 作为生产数据库？",
     "类型校验：SQLite不校验VARCHAR(max_length)，PostgreSQL严格校验（你的business_domain问题就是例子）。<br/>"
     "并发能力：SQLite仅支持单写者(WAL模式有限改善)，PostgreSQL支持高并发读写(MVCC机制)。<br/>"
     "功能：PostgreSQL支持JSONB、全文搜索、窗口函数、CTE递归查询等高级特性。<br/>"
     "你的项目需要：多用户并发操作(JWT无状态)、JSON字段高效查询(assertion_rules)、复杂统计SQL。这些SQLite难以胜任。"),

    (22, "数据库索引的原理是什么？什么字段应该建索引？",
     "索引本质是B+树数据结构，将无序数据组织为有序结构，把O(n)全表扫描降为O(log n)。<br/>"
     "应该建索引的字段：①WHERE条件常用字段 ②ORDER BY字段 ③外键字段 ④唯一性约束字段。<br/>"
     "不应该建索引：①频繁更新的字段(维护索引有开销) ②区分度低的字段(如性别只有男女) ③小表(<1000行)。<br/>"
     "你项目中：TestCase的priority+status复合索引、Execution的created_at时间索引。"),

    (23, "Milvus 是什么？为什么选择 Milvus 而不是 Faiss？",
     "Milvus是云原生分布式向量数据库。选择Milvus的理由：<br/>"
     "① 企业级特性：亿级向量、HNSW索引、QPS>10K、数据持久化。<br/>"
     "② 分布式架构：支持水平扩展，元数据(etcd)+对象存储(MinIO)分离。<br/>"
     "③ milvus-lite嵌入式模式：开发环境零依赖。<br/>"
     "Faiss是向量检索库(不是数据库)：不持久化、无分布式、无元数据管理。适合离线批量检索，不适合生产服务。<br/>"
     "HNSW索引原理：分层可导航小世界图，近似最近邻搜索，复杂度O(log n)。"),

    (24, "向量相似度检索的原理是什么？为什么相似度阈值设置需要谨慎？",
     "将文本转为高维空间中的向量(如1024维)，通过余弦相似度或欧氏距离衡量语义相似度。<br/>"
     "阈值的坑：概括性问题(如'这个项目是做什么的')和具体文档的向量距离天然较大(0.3-0.4)，设置0.5阈值会过滤掉正确结果。<br/>"
     "你的经验：将similarity_threshold从0.5降到0.0，让LLM自己判断检索结果是否相关，而不是在向量层就截断。<br/>"
     "Embedding模型选择：DashScope text-embedding-v3(1024维在线)或BAAI/bge-small-zh-v1.5(本地离线)。"),

    (25, "Redis 在你的项目中有哪些用途？",
     "三重角色：<br/>"
     "① Celery Broker：消息队列中间件，存储待执行的任务。<br/>"
     "② 缓存层：缓存热点数据(如模型配置列表)，减少数据库查询。<br/>"
     "③ 会话存储(可选)：分布式Session。<br/>"
     "淘汰策略：LRU(Least Recently Used)，单线程事件驱动模型确保原子性。<br/>"
     "持久化：RDB快照(定期保存全量数据) + AOF日志(每条写命令记录)双保险。"),


    # ========== 四、AI / LLM ==========
    ("四、AI / LLM 技术", "RAG、Embedding、多模型编排——你的核心竞争力"),

    (26, "RAG(检索增强生成)的核心原理是什么？解决了什么问题？",
     "RAG = Retrieval(检索) + Augmented(增强) + Generation(生成)。<br/>"
     "解决的问题：①LLM训练数据时效性不足 ②缺乏特定领域知识 ③'幻觉'问题。<br/>"
     "流程：用户提问→向量检索找到相关私有文档→将文档作为上下文注入Prompt→LLM基于上下文生成准确回答。<br/>"
     "你项目中的RAG：文档→Chunking→Embedding→Milvus→Top-K检索→拼接Prompt→LLM生成。<br/>"
     "vs 微调：RAG成本低、可实时更新知识、可溯源；微调需要GPU训练、不能实时更新。"),

    (27, "什么是 Embedding？text-embedding-v3 和 BGE 的区别？",
     "Embedding(向量化)将文本映射到高维向量空间，语义相近的文本向量距离也近。<br/>"
     "text-embedding-v3(DashScope在线API)：1024维、中文优化、无需本地GPU、但有API延迟和费用。<br/>"
     "BAAI/bge-small-zh-v1.5(本地开源)：512维、需本地下载约400MB、无网络延迟、无API费用。<br/>"
     "你的项目：默认用DashScope在线API，本地离线模式用sentence-transformers+bge。<br/>"
     "选择标准：在线API方便但依赖网络；本地模型自主但吃GPU。"),

    (28, "Prompt Engineering 有哪些技巧？你项目中怎么构造Prompt的？",
     "核心技巧：①角色设定('你是一个资深测试工程师') ②明确输出格式(JSON Schema约束) ③提供Few-shot示例(附带2-3个好用例) ④分步引导(先分析接口→再设计用例)。<br/>"
     "你项目中的Prompt设计：<br/>"
     "用例生成Prompt包含角色指令+输出格式要求+接口上下文+设计约束。<br/>"
     "RAG问答Prompt包含系统指令+检索到的文档内容+用户问题。<br/>"
     "测评Prompt包含评估标准(正确性/完整性)+答案+期望答案。<br/>"
     "关键：越具体的Prompt越稳定，不要依赖LLM'猜'你的意图。"),

    (29, "GPT、Claude、千问这些大模型，各自的优缺点是什么？",
     "通义千问(Qwen)：中文能力强、API国内稳定、价格适中、支持Embedding和多模态。<br/>"
     "DeepSeek：性价比极高(1/10价格)、擅长代码和推理、支持128K上下文、开源可私有化。<br/>"
     "智谱GLM：GLM-4综合能力强、Flash版快速便宜、不支持Embedding。<br/>"
     "你的多模型策略：用例生成用千问(中文最好)，代码生成用DeepSeek(便宜且代码能力好)，日常对话/测评用GLM Flash(快速)。"),

    (30, "Streaming(流式输出) 和 非流式输出 的区别？各自适用什么场景？",
     "非流式(chat)：等LLM生成完所有内容后一次性返回，适合批处理的AI用例生成。<br/>"
     "流式(chat_stream)：LLM逐token返回，前端逐字渲染，用户体验好(像ChatGPT打字效果)。<br/>"
     "你项目中的实现：RAG问答和AI对话用SSE流式输出（text/event-stream），AI用例生成用非流式（需要完整JSON解析）。<br/>"
     "流式难点：需要处理JSON不完整的情况、断连时保存部分回答。"),

    (31, "LangChain 和 LangGraph 分别解决了什么问题？你项目中怎么用的？",
     "LangChain：LLM应用开发框架，提供文档加载器(PyPDFLoader)、文本分割器(RecursiveCharacterTextSplitter)、LLM抽象层(ChatOpenAI)。<br/>"
     "LangGraph：有状态、多步骤Agent工作流编排框架，核心是图(节点+边)。<br/>"
     "你项目：RAG链条用LangChain工具链(文档加载→分割→向量库)。AI测评双模型工作流用LangGraph(答案准备→初评→条件复核→仲裁→汇总)。<br/>"
     "LangGraph优势：条件边(should_review)、并行节点(ThreadPoolExecutor)、状态持久化。"),

    (32, "多模型并行评测中，仲裁融合的权重是怎么设计的？",
     "主模型初评权重60%，复核模型权重40%。<br/>"
     "动态调整：当两个模型评分差异>20分时，改为各50%权重（避免主模型明显误判）。<br/>"
     "阈值选择理由：40-75分是模糊区间，此范围外的结果主模型置信度高(极高或极低分)。<br/>"
     "为什么不用简单平均？主模型通常比你评估的模型更强，应占主导权，但需要复核兜底。"),

    (33, "LLM 的 Temperature 参数有什么作用？你项目里怎么设置的？",
     "Temperature控制LLM输出的随机性/创造性：0→确定性最高(相同输入总得相同输出)，1→最随机，>1→胡言乱语。<br/>"
     "你项目的选择：用例生成设0.3(需要结构化输出的一致性)，AI对话设0.7(需要自然的多样性)，代码生成设0.1(需要精确)。<br/>"
     "与Top-p的区别：Temperature调整概率分布的锐度(温度越高分布越平)，Top-p限制候选token范围。两者常配合使用。"),

    (34, "如何处理LLM API调用失败的情况？（超时/限流/返回异常）",
     "① 超时处理：requests.post(timeout=120)，超时后捕获异常返回默认回答或友好提示。<br/>"
     "② 重试机制：指数退避重试(1s→2s→4s)，最多3次。<br/>"
     "③ 限流处理：检查HTTP 429状态码，读取Retry-After响应头。<br/>"
     "④ 降级方案：主模型失败→切换备用模型(如千问挂了降级DeepSeek)。<br/>"
     "⑤ 前端提示：返回标准错误格式{'error': True, 'message': '...'}，前端展示可理解的错误信息。"),

    (35, "什么是Token？为什么LLM有上下文长度限制？",
     "Token是LLM处理文本的最小单位，中文大约1个汉字≈1.5-2个Token。<br/>"
     "上下文长度限制原因：Attention机制计算复杂度O(n²)，8K→128K上下文，计算量增256倍。<br/>"
     "你项目的应对：RAG模式只注入Top-5相关文档片段(而非全量文档)、Prompt精简不冗余。<br/>"
     "DeepSeek支持128K上下文但响应慢且贵，千问qwen-plus默认8K。按需选择模型能省费用。"),


    # ========== 五、前端 & 全栈 ==========
    ("五、Vue3 前端 & 全栈", "前后端分离、组件通信，全栈岗必考"),

    (36, "Vue 3 Composition API 和 Options API 的区别？为什么选择 Composition API？",
     "Options API：按选项分类(data/methods/computed/watch)，代码分散在不同选项中。<br/>"
     "Composition API：按逻辑功能组织(setup函数)，用ref/reactive管理响应式，用computed/watch做计算和监听。<br/>"
     "选择理由：逻辑复用更灵活(自定义hooks提取公共逻辑)、TypeScript支持更好、代码可读性更高(一个功能的代码在一起)。<br/>"
     "你在项目中的使用：用<script setup>语法糖写组件，用Pinia做状态管理。"),

    (37, "Vue 组件之间有哪些通信方式？你的项目里主要用哪些？",
     "① 父子组件：props(父传子) + emit(子传父)。<br/>"
     "② 兄弟组件：通过共同父组件中转，或Pinia共享状态。<br/>"
     "③ 跨层级：provide/inject(祖先向后代注入)。<br/>"
     "④ 全局状态：Pinia Store(你项目的主要方式)——跨组件共享用户信息、模型配置、知识库状态。<br/>"
     "⑤ 路由参数：query/params传参。<br/>"
     "选择建议：简单父子传值用props/emit，跨组件共享状态用Pinia。"),

    (38, "Pinia 状态管理的核心概念是什么？和 Vuex 的区别？",
     "Pinia核心：Store(defineStore创建) → state(响应式数据) → getters(计算属性) → actions(修改state的方法，同步异步都行)。<br/>"
     "vs Vuex：①Pinia没有mutations(actions直接改state) ②TypeScript类型推断原生支持 ③模块化更自然(无需嵌套modules) ④更轻量。<br/>"
     "你项目中的Store：userStore(用户信息+登录状态)、modelStore(当前选中的LLM配置)、knowledgeStore(知识库列表+会话)等。"),

    (39, "axios 拦截器是怎么用的？你的项目怎么处理 401 未授权的？",
     "请求拦截器：在config.headers.Authorization中添加Bearer Token。<br/>"
     "响应拦截器：检查response.status，401时清除token并跳转登录页。<br/>"
     "你的实现：30秒响应超时设置，baseURL='/api'。<br/>"
     "Token刷新：拦截器中检测401→调用Refresh Token接口获取新Access Token→重试原请求。<br/>"
     "注意：防止多个请求同时触发刷新(加刷新pending锁)。"),

    (40, "Vue Router 的路由守卫是什么？你的项目怎么做权限控制的？",
     "全局前置守卫router.beforeEach((to, from, next)=>)在每个路由跳转前执行。<br/>"
     "你的权限控制：①检查是否有token→没有则跳转/login。②检查用户角色(admin/tester/viewer)→如模型管理页仅admin可访问。<br/>"
     "路由meta定义权限：meta: { requiresAuth: true, roles: ['admin'] }。<br/>"
     "菜单权限：根据角色动态生成侧边栏菜单，viewer只显示查看类页面。"),


    # ========== 六、测试领域 ==========
    ("六、测试领域知识", "测试方法论、接口测试、自动化框架——测试开发岗核心"),

    (41, "什么是接口测试？你们平台是怎么做自动化接口测试的？",
     "接口测试是验证API的功能、性能、安全性的测试方法，位于测试金字塔中间层。<br/>"
     "平台实现：①用例管理(TestCase CRUD)→②AI辅助生成(或者手动编写)→③加入测试套件→④触发执行(Pytest动态脚本)→⑤断言验证(9种操作符)→⑥Allure报告生成。<br/>"
     "核心能力：接口串联编排(extract_rules提取上一个接口的返回值作为下一个的入参)、变量替换(支持{{var}}和${var}两种语法)、多维度断言(JSONPath/状态码/字段存在性)。"),

    (42, "Pytest 相比 Unittest 有什么优势？用过哪些 Pytest 高级特性？",
     "优势：①断言简洁(pytest assert代替self.assertEqual) ②fixture机制(依赖注入优于setUp/tearDown) ③参数化(单用例多数据) ④插件生态丰富(Allure/coverage/xdist)。<br/>"
     "你项目中的使用：①conftest.py定义共享fixture ②pytest.mark.parametrize做数据驱动 ③pytest-xdist分布式执行(可选) ④allure-pytest生成可视化报告。<br/>"
     "fixture的scope：function(默认，每个测试函数)、class、module、session。"),

    (43, "Web UI 自动化中，Playwright 相比 Selenium 有什么优势？Midscene AI 解决了什么问题？",
     "Playwright优势：①自动等待(无需sleep) ②多浏览器(Chromium/Firefox/WebKit) ③网络拦截(route拦截请求mock数据) ④比Selenium快、API更现代。<br/>"
     "Midscene AI解决的问题：传统选择器依赖DOM结构(XPath/CSS Selector)，页面改版就失效。Midscene用AI视觉理解页面——'点击登录按钮'→AI识别页面截图中的登录按钮→点击，更语义化、更鲁棒。<br/>"
     "你的双引擎策略：常规操作用Playwright精确选择器(稳定快速)，复杂/易变场景用AI模式(容错高)。"),

    (44, "性能测试怎么做？Locust 的核心原理是什么？",
     "Locust是Python编写的性能测试工具，核心原理：①定义用户行为类(HttpUser+@task装饰器) ②用协程(greenlet/gevent)模拟数千个并发虚拟用户 ③实时Web UI展示QPS/响应时间/失败率。<br/>"
     "5种测试类型：负载测试(逐步加压)、压力测试(找极限)、稳定性测试(长时间跑)、并发测试、峰值测试。<br/>"
     "关键指标：QPS、P50/P95/P99延迟、错误率、吞吐量。<br/>"
     "你的平台：前端配置测试场景→后端生成Locust脚本→docker exec启动Locust→实时推送指标到前端。"),

    (45, "你在项目中写过单元测试吗？Mock 是什么？",
     "单元测试验证最小可测单元(函数/方法)的正确性。你项目使用Django TestCase+DRF APITestCase。<br/>"
     "Mock：替代真实依赖(外部API/数据库)的模拟对象，隔离测试环境。场景：测试LLM调用逻辑但不真实调用API(省费用)→mock LLMProviderFactory的返回。<br/>"
     "Python的unittest.mock：@patch装饰器、MagicMock对象。<br/>"
     "测试原则：每个测试独立(不依赖执行顺序)、快速(不调用外部API)、覆盖正常+异常+边界。"),


    # ========== 七、场景设计 ==========
    ("七、场景设计题", "考察架构思维和问题解决能力——决定薪资档次的关键"),

    (46, "如果平台日活从100人增长到10000人，哪些地方会成为瓶颈？你会怎么优化？",
     "【瓶颈分析】<br/>"
     "① 数据库：单PostgreSQL并发不足→读写分离(主从复制)+连接池(PgBouncer)。<br/>"
     "② API层：Gunicorn worker有限(默认4个)→横向扩展(Docker多实例)+负载均衡。<br/>"
     "③ LLM API：千问/DeepSeek有QPS限制→多Provider轮询+本地模型(7B)兜底。<br/>"
     "④ Celery：任务堆积→增加worker数量+优先级队列。<br/>"
     "⑤ 静态资源：ECharts大量渲染→图表懒加载+Web Worker。<br/>"
     "⑥ 向量检索：Milvus单实例→Milvus集群分片。<br/>"
     "⑦ 缓存：热点查询(如Dashboard统计)加Redis缓存，避免每次实时算。"),

    (47, "如果要给平台加上测试结果自动分析功能（比如失败原因归类），你怎么设计？",
     "【方案设计】<br/>"
     "① 数据收集：Execution模型已有case_results(JSON)，内含每个用例的error_message+assertion_results。<br/>"
     "② 错误分类引擎：基于规则匹配(HTTP状态码→网络/后端问题、连接超时→服务不可用、JSONPath失败→数据结构变更)做粗分类。<br/>"
     "③ AI辅助分析：将失败用例信息+screenshot+console log喂给LLM，生成人类可读的失败原因和修复建议。<br/>"
     "④ 统计面板：Dashboard新增'失败原因分布'饼图 + '高频失败接口'排行榜。<br/>"
     "⑤ 趋势分析：记录每个接口的历史通过率，波动时主动告警。"),

    (48, "如果要实现分布式测试执行（多台机器并行跑用例），你会怎么设计？",
     "【架构设计】<br/>"
     "① 任务分发：主节点接收执行请求→拆解用例→通过Celery将子任务分发到不同worker节点。<br/>"
     "② 执行节点：每台机器运行Celery worker+Docker(内含Playwright/Pytest/Locust环境)。<br/>"
     "③ 结果聚合：每个节点执行完后回写结果到共享PostgreSQL→主节点汇总。<br/>"
     "④ 调度策略：按用例类型分配(API→轻量节点、Web UI→GPU节点、性能→高配节点)。<br/>"
     "⑤ 通信：Celery+RabbitMQ(比Redis更适合分布式)做消息队列。<br/>"
     "⑥ 监控：Prometheus采集各节点指标+Grafana看板。"),

    (49, "面试官问：你的平台安全性怎么保证？SQL注入、XSS、CSRF分别怎么防护？",
     "SQL注入：Django ORM自动参数化查询(用%s占位符)，杜绝字符串拼接SQL。RAW SQL必须用params参数。<br/>"
     "XSS：Django模板自动转义HTML({{ text }}默认转义<>&)。前后端分离时前端Vue的{{ }}也自动转义，v-html需谨慎。<br/>"
     "CSRF：前后端分离场景用Token方式(Axios头里带X-CSRFToken)替代Cookie认证(用JWT)。Django CsrfViewMiddleware只保护Cookie认证的请求。<br/>"
     "额外防护：①CORS白名单②NGINX限流(limit_req)防DDoS③API Key全加密存储(os.getenv)④JWT定期刷新。"),


    # ========== 八、行为面试 ==========
    ("八、行为面试 & 综合素质", "软技能同样重要，这些题决定HR给不给过"),

    (50, "你的平台技术方案中，有哪些是你不满意的？如果重做会怎么改进？",
     "【坦诚+有思考】<br/>"
     "① 测试执行引擎：当前用subprocess+动态生成.py文件，太耦合→重做会用Docker容器隔离每个执行环境(安全性+并行度都好)。<br/>"
     "② 前端状态管理：早期没有规范用Pinia，有些组件直接axios→重做会统一Store管理所有API调用。<br/>"
     "③ 错误处理：Celery任务早期静默失败→已修复try-except+状态回写。<br/>"
     "④ 数据库：初期用SQLite开发→已改为开发也用PostgreSQL Docker。<br/>"
     "⑤ 如果完全重来：引入微服务架构(Celery独立服务+AI服务独立部署+K8s编排)，而不是单体Django。"),
]

# ============================================================
# 生成 PDF
# ============================================================
def build():
    filename = os.path.join(os.path.dirname(__file__), "..", "docs", "面试题50题_AutoTestHub.pdf")
    doc = SimpleDocTemplate(
        filename, pagesize=A4,
        topMargin=20*mm, bottomMargin=18*mm,
        leftMargin=20*mm, rightMargin=20*mm,
        title="AutoTestHub 面试题 50 题"
    )

    story = []
    story.append(Paragraph("AutoTestHub 平台面试题 50 题", style_title))
    story.append(Paragraph("基于项目技术栈的完整面试题库 · 含参考答案要点", style_subtitle))
    story.append(hr())

    current_cat = None
    for item in questions:
        if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str):
            # 分类标题
            story.extend(cat_header(item[0], item[1]))
            current_cat = item[0]
            continue

        idx, qtext, atext = item
        story.append(q(idx, qtext))
        story.append(a(atext))

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"  [OK] 面试题 PDF 已生成: {filename}")
    print(f"  共 50 道题，覆盖 8 大类别")

if __name__ == '__main__':
    build()
