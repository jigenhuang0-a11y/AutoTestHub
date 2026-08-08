# -*- coding: utf-8 -*-
"""路特创新·深度版面试题库 PDF生成器 —— 80题 微信读书适配"""
import os, sys, datetime

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gen_lute_deep_dive.py')
print(f"加载: {DATA_FILE}")

DATA = []
def S(title): DATA.append(("__SECTION__", title, ""))
def Q(q, a): DATA.append(("__QA__", q, a))

with open(DATA_FILE, 'r', encoding='utf-8') as f:
    code = f.read()
exec(code)

total_qa = len([x for x in DATA if x[0] == '__QA__'])
print(f"加载完成: {total_qa} 题")

from fpdf import FPDF

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs')
os.makedirs(OUTDIR, exist_ok=True)

CHAR_MAP = {
    '\u00b1': '+/-', '\u00b2': '^2', '\u00d7': 'x',
    '\u2191': '^', '\u2192': '->', '\u2193': 'v',
    '\u2260': '!=', '\u2265': '>=', '\u2248': '~',
    '\u2460': '(1)','\u2461': '(2)','\u2462': '(3)','\u2463': '(4)',
    '\u2464': '(5)','\u2465': '(6)','\u2466': '(7)','\u2467': '(8)',
    '\u2468': '(9)','\u2469': '(10)',
    '\u2500': '-', '\u2514': '+', '\u251c': '+',
    '\u03b1': 'alpha','\u03b2': 'beta','\u03b8': 'theta',
}

def safe_text(text):
    for ch, repl in CHAR_MAP.items():
        text = text.replace(ch, repl)
    return text

class PDF(FPDF):
    def __init__(self, header_label):
        super().__init__('P', 'mm', 'A4')
        self.set_left_margin(15)
        self.set_right_margin(15)
        self.header_label = header_label
        font_dir = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
        msyh = os.path.join(font_dir, 'msyh.ttc')
        msyhbd = os.path.join(font_dir, 'msyhbd.ttc')
        if os.path.exists(msyh):
            self.add_font('MSYH', '', msyh)
        else:
            self.add_font('MSYH', '', os.path.join(font_dir, 'simhei.ttf'))
        if os.path.exists(msyhbd):
            self.add_font('MSYH', 'B', msyhbd)
        else:
            self.add_font('MSYH', 'B', msyh)
        self.set_auto_page_break(True, 18)

    def header(self):
        if self.page_no() > 1:
            self.set_font('MSYH', '', 7.5)
            self.set_text_color(140, 140, 140)
            label_short = self.header_label[:60]
            self.cell(0, 4, safe_text(label_short), align='L')
            self.ln(1)
            self.set_draw_color(210, 210, 210)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.ln(3)

# ==========================================
# 封面
# ==========================================
pdf = PDF('路特创新 · 测试工程师面试题库 · 深度版 (80题)')

pdf.set_title('路特创新-软件测试工程师面试题库-深度版')
pdf.set_author('黄继根 · 面试准备 · 深度版')

pdf.add_page()

# —— 顶部深蓝横幅 (放大) ——
pdf.set_fill_color(22, 48, 82)
pdf.rect(0, 0, 210, 78, 'F')

# 公司名 36pt 超大
pdf.set_y(15)
pdf.set_font('MSYH', 'B', 36)
pdf.set_text_color(255, 255, 255)
pdf.cell(0, 16, safe_text('路特创新'), align='C', new_x="LMARGIN", new_y="NEXT")

pdf.set_font('MSYH', '', 13)
pdf.set_text_color(180, 210, 245)
pdf.cell(0, 8, safe_text('Momcozy · 全球母婴科技品牌'), align='C', new_x="LMARGIN", new_y="NEXT")
pdf.ln(3)
pdf.set_font('MSYH', 'B', 14)
pdf.set_text_color(220, 235, 255)
pdf.cell(0, 8, safe_text('软件测试工程师 · 面试题库 · 深度版'), align='C', new_x="LMARGIN", new_y="NEXT")

# —— 题目概要条 ——
pdf.set_y(86)
pdf.set_fill_color(0, 128, 128)
pdf.rect(12, pdf.get_y(), 186, 30, 'F')
pdf.set_font('MSYH', 'B', 18)
pdf.set_text_color(255, 255, 255)
pdf.cell(0, 11, safe_text(f'{total_qa}道深度递进题 · L1+L2 双层次'), align='C', new_x="LMARGIN", new_y="NEXT")
pdf.set_font('MSYH', '', 11)
pdf.cell(0, 8, safe_text('AutoTestHub全源码拆解 + 方法论实战 + 业务场景覆盖'), align='C', new_x="LMARGIN", new_y="NEXT")

# —— 模块权重图 ——
pdf.set_y(130)
pdf.set_font('MSYH', 'B', 16)
pdf.set_text_color(22, 48, 82)
pdf.cell(0, 10, safe_text('五大模块 · 权重分布'), align='C', new_x="LMARGIN", new_y="NEXT")
pdf.ln(5)

modules = [
    ("AutoTestHub 深度拆解", "52题 · 65%", (22, 48, 82)),
    ("测试方法论与团队协作", "20题 · 25%", (0, 100, 120)),
    ("母婴智能硬件/App测试", "6题 · 7.5%", (120, 60, 30)),
    ("跨境电商/职业发展", "2题 · 2.5%", (80, 80, 80)),
]

bar_x = 30
bar_w = 150
bar_h = 9
bar_gap = 14

for i, (name, cnt, color) in enumerate(modules):
    y = pdf.get_y()
    pdf.set_font('MSYH', '', 11)
    pdf.set_text_color(50, 50, 50)
    pdf.set_xy(bar_x - 25, y + 1)
    pdf.cell(22, 7, safe_text(name[:8]), align='R')
    
    # 进度条背景
    pdf.set_fill_color(235, 235, 235)
    pdf.rect(bar_x, y, bar_w, bar_h, 'F')
    
    # 进度条填充 (按比例)
    fill_pcts = [0.65, 0.25, 0.075, 0.025]
    ratio = fill_pcts[i]
    pdf.set_fill_color(*color)
    pdf.rect(bar_x, y, bar_w * ratio, bar_h, 'F')
    
    # 百分比文字
    pdf.set_font('MSYH', 'B', 11)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(bar_x + 3, y + 1)
    pdf.cell(bar_w * ratio - 5, 6, safe_text(cnt), align='R')
    
    pdf.set_y(y + bar_gap)

# —— 关键模块标签 ——
pdf.set_y(pdf.get_y() + 5)
pdf.set_font('MSYH', 'B', 13)
pdf.set_text_color(22, 48, 82)
pdf.cell(0, 10, safe_text('核心拆解模块'), align='C', new_x="LMARGIN", new_y="NEXT")
pdf.ln(3)

tags = [
    ('架构设计', 22,48,82), ('AI用例生成', 0,128,128), ('执行引擎', 22,48,82),
    ('质量数字人', 0,128,128), ('RAG知识库', 22,48,82), ('AI测评师', 0,128,128),
    ('数据工厂', 22,48,82), ('反思改进', 0,128,128), ('左移右移', 120,60,30),
    ('团队协作', 120,60,30), ('质量体系', 120,60,30), ('母婴硬件', 80,80,80),
]
pdf.set_font('MSYH', '', 10)
start_x = 12
tag_y = pdf.get_y()
col_w = 47
for i, (tag, r, g, b) in enumerate(tags):
    col = i % 3
    row = i // 3
    x = start_x + col * 62
    y = tag_y + row * 10
    if y > 270:
        break
    pdf.set_xy(x, y)
    pdf.set_fill_color(r, g, b)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(58, 8, safe_text(tag), fill=True, align='C')

# —— 底部信息 ——
pdf.set_y(255)
pdf.set_fill_color(245, 245, 245)
pdf.rect(12, pdf.get_y(), 186, 28, 'F')
pdf.set_y(258)
pdf.set_font('MSYH', '', 10)
pdf.set_text_color(100, 100, 100)
pdf.cell(0, 7, safe_text('候选人：黄继根  |  岗位：软件测试工程师 / AI测试开发'), align='C', new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 7, safe_text(f'基于简历+AutoTestHub全源码+路特创新业务场景 · {total_qa}道深度题 · {datetime.date.today().strftime("%Y年%m月%d日")}'), align='C', new_x="LMARGIN", new_y="NEXT")

# ==========================================
# 目录
# ==========================================
pdf.add_page()
pdf.set_font('MSYH', 'B', 18)
pdf.set_text_color(22, 48, 82)
pdf.cell(0, 12, '目  录', align='L', new_x="LMARGIN", new_y="NEXT")
pdf.ln(6)

sections = []
qa_per_section = {}
current_sec = None
for item in DATA:
    if item[0] == '__SECTION__':
        current_sec = item[1]
        sections.append(current_sec)
        qa_per_section[current_sec] = 0
    elif item[0] == '__QA__' and current_sec:
        qa_per_section[current_sec] += 1

# Group sections with indent for sub-sections
main_chapters = ['第1章', '第2章', '第3章']
for sec in sections:
    cnt = qa_per_section.get(sec, 0)
    is_main = any(sec.startswith(ch) for ch in main_chapters)
    if is_main:
        pdf.ln(1)
        pdf.set_font('MSYH', 'B', 13)
        pdf.set_text_color(22, 48, 82)
    else:
        pdf.set_font('MSYH', '', 11)
        pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 7, safe_text(f'  {sec}  ({cnt}题)'), new_x="LMARGIN", new_y="NEXT")

pdf.ln(4)
pdf.set_font('MSYH', '', 11)
pdf.set_text_color(100, 100, 100)
pdf.cell(0, 7, safe_text(f'  共计 {total_qa} 题  |  L1 基础回答 + L2 深度追问'), new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 7, safe_text('  核心权重：AutoTestHub平台深度拆解 65% | 测试方法论 25% | 业务认知 10%'), new_x="LMARGIN", new_y="NEXT")

# ==========================================
# 题目内容
# ==========================================
qa_count = 0
for item in DATA:
    if item[0] == '__SECTION__':
        pdf.add_page()
        pdf.set_font('MSYH', 'B', 15)
        pdf.set_text_color(22, 48, 82)
        pdf.multi_cell(0, 9, safe_text(item[1]), align='L', new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
    elif item[0] == '__QA__':
        qa_count += 1
        question, answer = item[1], item[2]
        
        # Question header with number
        pdf.set_font('MSYH', 'B', 12)
        pdf.set_text_color(30, 30, 30)
        pdf.multi_cell(0, 6.5, safe_text(question), align='L', new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        pdf.set_font('MSYH', '', 10.5)
        pdf.set_text_color(55, 55, 55)

        for line in answer.split('\n'):
            line = safe_text(line.strip())
            if not line:
                pdf.ln(1)
                continue
            try:
                if line.startswith('【L') and ('回答' in line or '追问' in line):
                    pdf.set_font('MSYH', 'B', 11)
                    pdf.set_text_color(0, 115, 115)
                    pdf.multi_cell(0, 6, line, align='L', new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font('MSYH', '', 10.5)
                    pdf.set_text_color(55, 55, 55)
                else:
                    pdf.multi_cell(0, 5.8, line, align='L', new_x="LMARGIN", new_y="NEXT")
            except Exception as e:
                print(f"ERROR at qa#{qa_count}: [{line[:100]}]")
                raise

        # Light separator
        pdf.set_draw_color(225, 225, 225)
        pdf.set_line_width(0.15)
        pdf.line(pdf.l_margin + 5, pdf.get_y() + 2, pdf.w - pdf.r_margin - 5, pdf.get_y() + 2)
        pdf.ln(5)

# ==========================================
# 输出
# ==========================================
PDF_FILE = os.path.join(OUTDIR, '路特创新-面试题库-深度版-80题.pdf')
pdf.output(PDF_FILE)
file_size = os.path.getsize(PDF_FILE) / 1024 / 1024
print(f"\n{'='*60}")
print(f"[OK] 路特创新 · 深度版面试题库 PDF 生成成功！")
print(f"  文件: {PDF_FILE}")
print(f"  题目数: {qa_count} 道")
print(f"  页数: {pdf.page_no()} 页")
print(f"  文件大小: {file_size:.2f} MB")
print(f"{'='*60}")
