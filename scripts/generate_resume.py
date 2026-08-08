"""
生成针对 深圳市爱思软件技术有限公司 - AI 软件测试开发工程师 的优化简历
"""
from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os

doc = Document()

# ============ 页面设置 ============
sections = doc.sections
for section in sections:
    section.top_margin = Cm(1.5)
    section.bottom_margin = Cm(1.5)
    section.left_margin = Cm(2)
    section.right_margin = Cm(2)

# ============ 样式设置 ============
style = doc.styles['Normal']
font = style.font
font.name = '微软雅黑'
font.size = Pt(10.5)
style.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

# ============ 辅助函数 ============
def add_heading_text(text, size=14, bold=True, color=None, alignment=None):
    """添加标题段落"""
    p = doc.add_paragraph()
    if alignment:
        p.alignment = alignment
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.bold = bold
    run.font.name = '微软雅黑'
    run.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    if color:
        run.font.color.rgb = RGBColor(*color)
    return p

def add_line():
    """添加分隔线"""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    pPr = p._element.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '6')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), '2E75B6')
    pBdr.append(bottom)
    pPr.append(pBdr)
    return p

def add_section_title(text):
    """添加区块标题"""
    add_line()
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    run.font.size = Pt(13)
    run.bold = True
    run.font.color.rgb = RGBColor(0x2E, 0x75, 0xB6)
    run.font.name = '微软雅黑'
    run.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    return p

def add_body(text, indent=True, size=10.5):
    """添加正文段落"""
    p = doc.add_paragraph()
    if indent:
        p.paragraph_format.first_line_indent = Pt(21)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.3
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.font.name = '微软雅黑'
    run.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    return p

def add_bullet(text, bold_prefix=None):
    """添加要点"""
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.6)
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.line_spacing = 1.2
    if bold_prefix:
        r = p.add_run('● ' + bold_prefix)
        r.bold = True
        r.font.size = Pt(10)
        r.font.name = '微软雅黑'
        r.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        r2 = p.add_run(text)
        r2.font.size = Pt(10)
        r2.font.name = '微软雅黑'
        r2.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    else:
        r = p.add_run('● ' + text)
        r.font.size = Pt(10)
        r.font.name = '微软雅黑'
        r.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    return p

def add_tag(text, color=None):
    """添加小标签"""
    run = doc.add_paragraph().add_run(text)
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(*(color or (0x66, 0x66, 0x66)))
    run.font.name = '微软雅黑'
    run.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

def add_info_row(label, value):
    """个人信息行"""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(1)
    r1 = p.add_run(label)
    r1.bold = True
    r1.font.size = Pt(10.5)
    r1.font.name = '微软雅黑'
    r1.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    r2 = p.add_run(value)
    r2.font.size = Pt(10.5)
    r2.font.name = '微软雅黑'
    r2.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    return p

# =============================================
# 正文开始
# =============================================

# 姓名
add_heading_text('黄 继 根', size=22, bold=True, alignment=WD_ALIGN_PARAGRAPH.CENTER)

# 求职意向
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(4)
r = p.add_run('AI 软件测试开发工程师')
r.font.size = Pt(13)
r.font.color.rgb = RGBColor(0x2E, 0x75, 0xB6)
r.bold = True
r.font.name = '微软雅黑'
r.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

# 联系方式（一行紧凑排列）
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(2)
info_text = '男 · 29岁 · 全日制本科 · 深圳南山区 | 13249894029 | hjg19960220@163.com'
r = p.add_run(info_text)
r.font.size = Pt(9.5)
r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
r.font.name = '微软雅黑'
r.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(4)
r = p.add_run('期望薪资 30K · 一周内到岗 · GitHub: github.com/jigenhuang0-a11y/AutoTestHub')
r.font.size = Pt(9.5)
r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
r.font.name = '微软雅黑'
r.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

# ============ 核心亮点 ============
add_section_title('▎核心亮点')

add_bullet(
    '独立全栈研发 AutoTestHub AI 测试平台并已开源，覆盖「AI出题→技能调度→批量测评→质检打分→安全扫描→报告导出」全链路，'
    '已落地 19 项测评任务与 15 项用例自检任务实战验证，测试交付效率提升 50% 以上，AI 评测效率提升 90%+。',
    bold_prefix='自研 AI 测试平台：'
)
add_bullet(
    '6 年测试经验，从传统 B 端测试逐步进阶至 AI 测试开发方向，具备银行（中国银行）、消费电子（华为/OPPO）、'
    '制造业多行业项目落地经验，熟悉企业级质量保障体系全流程。',
    bold_prefix='全栈测试经验：'
)
add_bullet(
    '落地测试左移+右移双闭环质量兜底策略：左移将质检前置至用例生成环节，右移通过 AI 测评师追踪模型输出质量，'
    '从幻觉检测到安全扫描实现上线后兜底，将测试从点状验证升级为全链路质量闭环。',
    bold_prefix='测试左右移体系：'
)

# ============ IT技能 ============
add_section_title('▎专业技能')

add_bullet(
    '熟练 Python，具备全栈开发基础——使用 Django/DRF 独立完成 AI 测试平台后端搭建与接口开发；熟悉 Vue3 前端开发；'
    '掌握 Requests、Pytest、Allure 等测试库，可编写自动化脚本、Mock 数据工厂及数据处理工具；了解异步编程与流式输出。',
    bold_prefix='Python 全栈开发：'
)
add_bullet(
    '熟悉 RAG 评测体系（召回率/精确率/相似度调优）、Agent 安全测试（Prompt注入/越狱/角色提权/记忆污染）、'
    'AI 输出合规检测（歧视性输出/不当建议），具备从零构建 AI 质量保障体系的能力。',
    bold_prefix='AI 测试与评测：'
)
add_bullet(
    '熟练 Playwright/Cypress UI 自动化框架，熟悉 Postman/Apifox 接口测试与自动化断言；了解 Docker 容器化、'
    'Kubernetes 集群架构，熟悉 KubeSphere/Jenkins/GitLab CI 流水线搭建与持续集成流程。',
    bold_prefix='自动化与 DevOps：'
)
add_bullet(
    '熟练 JMeter/Locust 性能测试工具，了解 MySQL 调优、JVM 监控、全链路压测（SkyWalking/ELK）；'
    '熟悉 XSS/CSRF/SQL注入/权限越权等 Web 安全漏洞原理，了解 OWASP ZAP 扫描工具。',
    bold_prefix='性能与安全：'
)

# ============ 工作经历 ============
add_section_title('▎工作经历')

# 经历1
p = doc.add_paragraph()
p.paragraph_format.space_after = Pt(1)
r1 = p.add_run('2026.03 - 至今    AI 测试平台 AutoTestHub（独立研发）    AI 测试开发工程师')
r1.bold = True
r1.font.size = Pt(10.5)
r1.font.name = '微软雅黑'
r1.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

add_body('基于中国银行金融大模型项目一线业务痛点，独立从零研发一站式 AI 智能测试平台，通过 RAG 知识库、大模型测评引擎、自动化调度能力，解决测试用例重复编写、人工评审低效、大模型线上批量评测难等行业难题。基于 Django4.2+Vue3.5 全栈架构，集成 ChromaDB 向量库，支持 Docker 容器化部署。', size=10)

add_bullet(
    '依托大模型+RAG 知识库，自然语言解析业务需求，自动生成功能/边界/安全/性能结构化测试用例，支持多格式导出，'
    '单接口用例编写效率提升 60%，用例人工评审周期缩短 70%。',
    bold_prefix='智能用例生成：'
)
add_bullet(
    '内置 3 类行业质检规则，从完整性、规范性、内容维度自动批量评审用例，'
    '支持自定义规则配置，用例场景覆盖率提升 40%，重复用例检出率达 95% 以上。',
    bold_prefix='用例批量质检：'
)
add_bullet(
    '打造 AI 测评师引擎，支持通用对话、知识库问答两类评测模式，覆盖准确率/响应时延/综合质量/安全风险四维度，'
    '单轮百题评测从人工 1-2 天缩短至分钟级，安全风险检出率较人工提升 65%。',
    bold_prefix='大模型质量评测：'
)
add_bullet(
    '7 个可插拔 Agent 技能，自然语言输入即秒出结构化用例；预置金融科技、跨境电商多套业务模板，'
    '一键生成正负样本与边界数据；沉淀标准化 AI 测试方法论与可复用测试资产。',
    bold_prefix='Agent 技能与数据引擎：'
)

# 经历2
p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(8)
p.paragraph_format.space_after = Pt(1)
r1 = p.add_run('2025.02 - 2026.01    京北方（驻中国银行）    软件测试工程师')
r1.bold = True
r1.font.size = Pt(10.5)
r1.font.name = '微软雅黑'
r1.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

add_body('参与中国银行企业级 DevOps 云平台、AI Coding 两大金融核心项目全流程质量保障。独立负责 DevOps 流水线插件需求评审与测试设计，累计编写 350+ 功能用例、200+ 插件用例，完成麒麟/x86/ARM 信创多架构兼容性专项测试，累计闭环 250+ 有效缺陷，流水线构建失败率从 12% 优化至 3% 以内。负责 AI Coding 平台大模型模块专项测试，主导 RAG 检索效果调优与 AI 全链路性能压测，将业务问答准确率提升 40%，核心接口平均延迟下降 25%。', size=10)

# 经历3
p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(8)
p.paragraph_format.space_after = Pt(1)
r1 = p.add_run('2024.10 - 2025.01    东莞亿达（驻 OPPO）    /    2023.06 - 2024.03    中软国际（驻华为）')
r1.bold = True
r1.font.size = Pt(10.5)
r1.font.name = '微软雅黑'
r1.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

add_body('OPPO 效能协作 SaaS 平台迭代测试，基于 Python+Playwright 编写 UI 自动化用例 150+ 条，覆盖版本主回归。华为应用内支付服务全球聚合支付平台测试，独立负责欧洲/俄罗斯站点版本测试与发布验证，参与 A/B 测试分流、蓝绿集群部署、金丝雀发布验证，保障海外站点支付业务稳定运行。', size=10)

# 更早经历简写
p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(4)
r1 = p.add_run('2021.06 - 2023.03    富泰华工业（深圳）    /    2020.12 - 2021.05    东莞景丰    软件测试工程师')
r1.font.size = Pt(9.5)
r1.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
r1.font.name = '微软雅黑'
r1.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

# ============ 项目成果 ============
add_section_title('▎项目成果')

add_bullet('左移提效：单接口用例编写效率提升 60%，用例人工评审周期缩短 70%，测试数据构造效率提升 80%，整体测试交付效率提升 50%+。')
add_bullet('右移提质：AI 大模型质量评估效率提升 90%+，单轮百题评测从人工 1-2 天缩短至分钟级；安全风险检出率较人工提升 65%。')
add_bullet('能力沉淀：沉淀 7 项可复用测试技能插件、3 套行业质检规则模板，形成标准化 AI 测试方法论，可直接复用于不同业务线。')
add_bullet('开源贡献：平台前后端完整源码、AI 评测引擎、部署文档均已开源，GitHub 可查看从架构设计到业务落地的全流程实现。')

# ============ 教育背景 ============
add_section_title('▎教育背景')

p = doc.add_paragraph()
p.paragraph_format.space_after = Pt(2)
r = p.add_run('2016.09 - 2020.06    桂林电子科技大学    网络工程    全日制本科')
r.font.size = Pt(10.5)
r.font.name = '微软雅黑'
r.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

# ============ 自我评价（适配岗位） ============
add_section_title('▎自我评价')

add_body(
    '6 年软件测试从业经验，从传统 B 端测试逐步进阶至 AI 测试开发方向，具备银行、消费电子、制造业多行业项目落地经验。'
    '独立全栈研发 AI 智能测试平台并已开源，精通测试左右移质量体系、RAG 大模型评测、Agent 智能测试能力落地，'
    '具备从 0 到 1 搭建 AI 测试工具体系的能力。熟练掌握自动化、DevOps 云原生、性能安全全栈测试技术，'
    '擅长从业务痛点出发设计质量方案、落地工程化测试流程。注重测试资产沉淀与效率提升，'
    '具备较强的问题分析与技术攻坚能力，能够快速适配不同业务场景的质量保障需求。',
    size=10
)

# ============ 保存 ============
output_dir = os.path.join(os.path.dirname(__file__), '..', 'docs')
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, '黄继根-简历-AI软件测试开发工程师-爱思软件.docx')
doc.save(output_path)
print(f'简历已生成: {output_path}')
