# -*- coding: utf-8 -*-
"""凯迪仕 · AI测试工程师 · 定制题库 PDF生成器"""
import os, sys, datetime

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gen_kaadas_custom.py')
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
    '\u00b1': '+/-', '\u00b2': '^2', '\u00d7': 'x', '\u03b1': 'alpha',
    '\u03b2': 'beta', '\u03b3': 'gamma', '\u03b5': 'epsilon', '\u03b8': 'theta',
    '\u03ba': 'kappa', '\u03c3': 'sigma', '\u2191': '^', '\u2192': '->',
    '\u2193': 'v', '\u2202': 'd', '\u2248': '~', '\u2260': '!=', '\u2265': '>=',
    '\u2460': '(1)', '\u2461': '(2)', '\u2462': '(3)', '\u2463': '(4)',
    '\u2464': '(5)', '\u2465': '(6)', '\u2466': '(7)', '\u2467': '(8)',
    '\u2468': '(9)', '\u2469': '(10)', '\u2500': '-', '\u2514': '+', '\u251c': '+',
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
        self.set_auto_page_break(True, 20)

    def header(self):
        if self.page_no() > 2:
            self.set_font('MSYH', '', 8)
            self.set_text_color(150, 150, 150)
            left_w = (self.w - self.l_margin - self.r_margin) * 0.65
            self.cell(left_w, 5, safe_text(self.header_label), align='L')
            self.cell(0, 5, f'{self.page_no()}', align='R', new_x="LMARGIN", new_y="NEXT")
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.ln(3)

# ---- 封面 ----
pdf = PDF('凯迪仕 · AI测试工程师 · 定制面试题库')
pdf.set_title('凯迪仕-AI测试工程师-定制面试题库')
pdf.set_author('AI测试面试准备')

pdf.add_page()

# 顶部深绿色横幅（凯迪仕风格）
pdf.set_fill_color(10, 50, 40)  # 深绿色
pdf.rect(0, 0, 210, 55, 'F')
pdf.set_y(10)
pdf.set_font('MSYH', 'B', 28)
pdf.set_text_color(255, 255, 255)
pdf.cell(0, 14, safe_text('凯迪仕'), align='C', new_x="LMARGIN", new_y="NEXT")
pdf.set_font('MSYH', 'B', 20)
pdf.set_text_color(130, 220, 180)  # 浅绿色
pdf.cell(0, 12, safe_text('AI测试工程师 · 定制面试题库'), align='C', new_x="LMARGIN", new_y="NEXT")

# 绿色标识条
pdf.set_y(62)
pdf.set_fill_color(30, 120, 80)
pdf.rect(15, pdf.get_y(), 180, 28, 'F')
pdf.set_font('MSYH', 'B', 16)
pdf.set_text_color(255, 255, 255)
pdf.cell(0, 8, safe_text(f'L1-L2 深度递进 · {total_qa}道定制题 · 8大模块'), align='C', new_x="LMARGIN", new_y="NEXT")
pdf.set_font('MSYH', '', 12)
pdf.cell(0, 8, safe_text('结合AutoTestHub项目经验 · 精准匹配JD要求'), align='C', new_x="LMARGIN", new_y="NEXT")

# 核心覆盖区
pdf.set_y(105)
pdf.set_font('MSYH', 'B', 15)
pdf.set_text_color(10, 50, 40)
pdf.cell(0, 10, safe_text('定制模块覆盖'), align='C', new_x="LMARGIN", new_y="NEXT")
pdf.ln(4)

keywords = [
    ('项目经验深挖', 'AI测试方法论', '测试数据集建设'),
    ('LLM基础知识', '测试工具与自动化', 'AI安全与合规'),
    ('面试软技能', '测试方案设计', '嵌入式AI测试'),
]
pdf.set_font('MSYH', '', 11)
for row in keywords:
    pdf.set_x(15)
    cell_w = 180 / 3
    for kw in row:
        pdf.set_fill_color(230, 250, 240)
        pdf.set_text_color(20, 90, 60)
        pdf.set_draw_color(180, 220, 200)
        pdf.cell(cell_w, 9, safe_text(f'  {kw}'), border=1, fill=True, align='C')
    pdf.ln(11)

pdf.ln(6)
pdf.set_font('MSYH', '', 11)
pdf.set_text_color(80, 80, 80)
pdf.cell(0, 8, safe_text('针对凯迪仕JD定制：AI测试经验 + 测试方案设计 + 数据集建设'), align='C', new_x="LMARGIN", new_y="NEXT")

# 底部信息栏
pdf.set_y(240)
pdf.set_fill_color(245, 245, 245)
pdf.rect(15, pdf.get_y(), 180, 32, 'F')
pdf.set_y(244)
pdf.set_font('MSYH', '', 10)
pdf.set_text_color(100, 100, 100)
pdf.cell(0, 7, safe_text('适用岗位：AI测试工程师 / 薪资20-40K / 深圳·3-5年'), align='C', new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 7, safe_text(f'生成日期：{datetime.date.today().strftime("%Y年%m月%d日")}  |  {total_qa}道深度递进题  |  8大模块'), align='C', new_x="LMARGIN", new_y="NEXT")

# ---- 目录 ----
pdf.add_page()
pdf.set_font('MSYH', 'B', 18)
pdf.set_text_color(10, 50, 40)
pdf.cell(0, 12, '目  录', align='L', new_x="LMARGIN", new_y="NEXT")
pdf.ln(8)

sections = []
for item in DATA:
    if item[0] == '__SECTION__':
        sections.append(item[1])

for i, sec in enumerate(sections, 1):
    pdf.set_font('MSYH', 'B', 11)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 7, safe_text(f'{i}. {sec}'), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

# ---- 题目内容 ----
qa_count = 0
for item in DATA:
    if item[0] == '__SECTION__':
        pdf.add_page()
        pdf.set_font('MSYH', 'B', 14)
        pdf.set_text_color(10, 50, 40)
        pdf.multi_cell(0, 8, safe_text(item[1]), align='L', new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
    elif item[0] == '__QA__':
        qa_count += 1
        question, answer = item[1], item[2]

        pdf.set_font('MSYH', 'B', 11)
        pdf.set_text_color(30, 30, 30)
        pdf.multi_cell(0, 6, safe_text(question), align='L', new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        pdf.set_font('MSYH', '', 9)
        pdf.set_text_color(60, 60, 60)

        for line in answer.split('\n'):
            line = safe_text(line.strip())
            if not line:
                pdf.ln(1)
                continue
            try:
                if line.startswith('【L') and ('回答' in line or '追问' in line):
                    pdf.set_font('MSYH', 'B', 9.5)
                    pdf.set_text_color(20, 100, 70)
                    pdf.multi_cell(0, 5.5, line, align='L', new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font('MSYH', '', 9)
                    pdf.set_text_color(60, 60, 60)
                else:
                    pdf.multi_cell(0, 5, line, align='L', new_x="LMARGIN", new_y="NEXT")
            except Exception as e:
                print(f"ERROR at qa#{qa_count}: [{line[:100]}]")
                raise

        pdf.set_draw_color(220, 220, 220)
        pdf.set_line_width(0.2)
        pdf.line(pdf.l_margin + 5, pdf.get_y() + 2, pdf.w - pdf.r_margin - 5, pdf.get_y() + 2)
        pdf.ln(4)

# ---- 输出 ----
PDF_FILE = os.path.join(OUTDIR, '凯迪仕-AI测试工程师-定制面试题库.pdf')
pdf.output(PDF_FILE)
file_size = os.path.getsize(PDF_FILE) / 1024 / 1024
print(f"\n{'='*60}")
print(f"[OK] 凯迪仕定制题库 PDF生成成功！")
print(f"  文件: {PDF_FILE}")
print(f"  题目数: {qa_count} 道")
print(f"  页数: {pdf.page_no()} 页")
print(f"  文件大小: {file_size:.2f} MB")
print(f"{'='*60}")
