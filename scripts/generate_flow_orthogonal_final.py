#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高清流程图 - 直角折线版，无斜线，充分利用右侧空间
"""

from PIL import Image, ImageDraw, ImageFont
import os

W, H = 2000, 1500

# 字体
font_title = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 48)
font_sub   = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 22)
font_node  = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 28)
font_ns    = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
font_lbl   = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 17)
font_leg   = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 19)

# 颜色
C_BG     = '#FAFBFC'
C_BORDER = '#DADCE0'
C_TITLE  = '#202124'
C_SUB    = '#5F6368'
C_LINE   = '#5F6368'  # 统一深灰线，不抢节点风头

LAYERS = [
    ('#E8F0FE', '#4285F4', '数据准备'),
    ('#F3E5F5', '#9C27B0', 'AI生成'),
    ('#E8F5E9', '#34A853', '用例管理与质检'),
    ('#FFF3E0', '#FF9800', '编排与执行'),
    ('#FCE4EC', '#EC407A', '报告'),
]

NODE_W, NODE_H = 260, 110
LANE_X, LANE_Y, LANE_H, N_LAYER = 80, 115, 240, 5
LANE_W = W - 220

img = Image.new('RGB', (W, H), C_BG)
d   = ImageDraw.Draw(img)

# ===== 标题 =====
d.text((W//2, 32), "AI测试平台 全局联动业务流程图", fill=C_TITLE, font=font_title, anchor="mt")
d.text((W//2, 76), "数据工厂→AI生成→API用例→质检→手动编排→执行→报告", fill=C_SUB, font=font_sub, anchor="mt")

# ===== 泳道 =====
for i, (bg, accent, lbl) in enumerate(LAYERS):
    y = LANE_Y + i * LANE_H
    d.rectangle([LANE_X, y, LANE_X + LANE_W, y + LANE_H - 10], fill=bg, outline=C_BORDER, width=1)
    d.text((LANE_X + 15, y + LANE_H//2 - 15), lbl, fill=accent, font=font_lbl, anchor="lm")

# ===== 左侧用户条 =====
UX, UW = LANE_X - 55, 40
d.rectangle([UX, LANE_Y, UX + UW, LANE_Y + N_LAYER * LANE_H - 10], fill='#1565C0')
for i, c in enumerate("用户入口"):
    d.text((UX + UW//2, LANE_Y + 50 + i * 24), c, fill='white', font=font_lbl, anchor="mm")

# ===== 右侧 AI问答评测 =====
EX, EW = LANE_X + LANE_W + 20, 60
d.rectangle([EX, LANE_Y, EX + EW, LANE_Y + N_LAYER * LANE_H - 10], fill='#D84315')
for i, c in enumerate("AI问答评测"):
    d.text((EX + EW//2, LANE_Y + 60 + i * 24), c, fill='white', font=font_lbl, anchor="mm")

# ===== 节点绘制 =====
def node(x, y, title, sub, color):
    r = 8
    d.rounded_rectangle([x, y, x+NODE_W, y+NODE_H], radius=r, fill='white', outline=color, width=3)
    d.text((x+NODE_W//2, y+NODE_H//2-13), title, fill=color, font=font_node, anchor="mm")
    d.text((x+NODE_W//2, y+NODE_H//2+16), sub,   fill=C_SUB, font=font_ns, anchor="mm")
    return {
        'cx': x+NODE_W//2, 'cy': y+NODE_H//2,
        't': (x+NODE_W//2, y),      'b': (x+NODE_W//2, y+NODE_H),
        'l': (x, y+NODE_H//2),      'r': (x+NODE_W, y+NODE_H//2),
        'x': x, 'y': y, 'w': NODE_W, 'h': NODE_H,
    }

# 第1层
Y1 = LANE_Y + (LANE_H - NODE_H)//2
DF  = node(200, Y1, "数据工厂", "Faker造数·模板·版本", LAYERS[0][1])
KB  = node(520, Y1, "知识库(RAG)", "文档上传→向量化→检索", LAYERS[0][1])

# 第2层
Y2 = LANE_Y + LANE_H + (LANE_H-NODE_H)//2
AG = node(200, Y2, "AI用例生成", "Agent工作流→API功能用例", LAYERS[1][1])

# 第3层
Y3 = LANE_Y + LANE_H*2 + (LANE_H-NODE_H)//2
API  = node(200,  Y3, "API功能用例", "HTTP接口·JSONPath断言", LAYERS[2][1])
WEB  = node(520,  Y3, "Web自动化用例", "Playwright·MidsceneAI", LAYERS[2][1])
PERF = node(840,  Y3, "性能测试用例", "Locust压测·实时指标", LAYERS[2][1])
QC   = node(1160, Y3, "质量数字人", "入库前质检·三维度评分", LAYERS[2][1])

# 第4层
Y4 = LANE_Y + LANE_H*3 + (LANE_H-NODE_H)//2
SUITE = node(200, Y4, "测试套件", "手动选择·聚合3类用例", LAYERS[3][1])
EXEC  = node(600, Y4, "测试执行引擎", "Pytest动态生成·多触发", LAYERS[4][1])

# 第5层
Y5 = LANE_Y + LANE_H*4 + (LANE_H-NODE_H)//2
RPT = node(600, Y5, "报告中心", "Allure·HTML·AI评估", LAYERS[4][1])

# ===== 连线工具 =====
def v_arrow(x, y1, y2, color, w=2):
    """垂直向下箭头"""
    if y2 < y1: return
    d.line([(x,y1),(x,y2)], fill=color, width=w)
    d.polygon([(x,y2),(x-6,y2-8),(x+6,y2-8)], fill=color)

def h_arrow(x1, y, x2, color, w=2):
    """水平箭头"""
    d.line([(x1,y),(x2,y)], fill=color, width=w)
    if x2 > x1:
        d.polygon([(x2,y),(x2-8,y-6),(x2-8,y+6)], fill=color)
    else:
        d.polygon([(x2,y),(x2+8,y-6),(x2+8,y+6)], fill=color)

def corner_L(x1, y1, x2, y2, color, w=2):
    """直角折线：先向下再向右/向左"""
    d.line([(x1,y1),(x1,y2)], fill=color, width=w)
    d.line([(x1,y2),(x2,y2)], fill=color, width=w)
    if x2 > x1:
        d.polygon([(x2,y2),(x2-8,y2-6),(x2-8,y2+6)], fill=color)
    else:
        d.polygon([(x2,y2),(x2+8,y2-6),(x2+8,y2+6)], fill=color)

def corner_7(x1, y1, x2, y2, color, w=2):
    """直角折线：先向右/向左再向下"""
    d.line([(x1,y1),(x2,y1)], fill=color, width=w)
    d.line([(x2,y1),(x2,y2)], fill=color, width=w)
    d.polygon([(x2,y2),(x2-6,y2-8),(x2+6,y2-8)], fill=color)

def dash_h(x1, x2, y, color, w=2):
    for xx in range(min(x1,x2), max(x1,x2), 12):
        d.line([(xx,y),(xx+6,y)], fill=color, width=w)

def dash_v(x, y1, y2, color, w=2):
    for yy in range(min(y1,y2), max(y1,y2), 12):
        d.line([(x,yy),(x,yy+6)], fill=color, width=w)

# ===== 核心数据流（实线） =====

# 1. 数据工厂 → AI用例生成：垂直向下（X=200，短）
v_arrow(DF['cx'], DF['b'][1], AG['t'][1], C_LINE, 2)

# 2. 知识库 → AI用例生成：先向下到第2层中间，再向左
# 从知识库底部中心向下到第2层顶部上方20px，再向左到AI用例生成顶部，再向下
corner_L(KB['cx'], KB['b'][1], AG['cx'], AG['t'][1], C_LINE, 2)

# 3. AI用例生成 → API功能用例：垂直向下（X=200）
v_arrow(AG['cx'], AG['b'][1], API['t'][1], C_LINE, 2)

# 4. 数据工厂 → API功能用例：从数据工厂右边缘垂直向下，绕过AI用例生成右侧，到第3层再向左
# 从数据工厂右边缘（x=460）向下到第3层顶部，再向左到API顶部中心
lane2_bottom = Y2 + NODE_H  # 第2层底部Y
d.line([(DF['r'][0], DF['b'][1]), (DF['r'][0], Y3 - 10)], fill='#FF9800', width=2)  # 垂直向下
h_arrow(DF['r'][0], Y3 - 10, API['cx'], '#FF9800', 2)  # 向左到API

# 5. API功能用例 → 质量数字人：第3层内水平（实线：入库前质检）
h_arrow(API['r'][0], API['cy'], QC['l'][0], LAYERS[2][1], 2)

# 6. 测试套件 → 测试执行引擎：第4层内水平
h_arrow(SUITE['r'][0], SUITE['cy'], EXEC['l'][0], LAYERS[3][1], 3)

# 7. 测试执行引擎 → 报告中心：垂直向下（X=600）
v_arrow(EXEC['cx'], EXEC['b'][1], RPT['t'][1], LAYERS[4][1], 3)

# 8. 知识库 → AI问答评测：水平向右（第1层）
h_arrow(KB['r'][0], KB['cy'], EX, LANE_Y+120, '#D84315', 2)

# ===== 手动加入（虚线标注） =====
# 在第3层底部和第4层顶部之间画一条横虚线，标注"手动加入"
dash_h(API['cx'], PERF['cx'], Y3 + NODE_H + 25, '#9AA0A6')
d.text((PERF['cx'] + 40, Y3 + NODE_H + 18), "手动加入", fill=C_SUB, font=font_lbl)
# 向下的短虚线
for n in [API, WEB, PERF]:
    dash_v(n['cx'], n['b'][1], Y3 + NODE_H + 25, '#9AA0A6')
# 从虚线到测试套件顶部的短虚线
dash_v(SUITE['cx'], Y3 + NODE_H + 25, SUITE['t'][1], '#9AA0A6')

# ===== 用户虚线（灰色，只到关键节点） =====
user_targets = [DF, AG, API, EXEC, RPT]
for tgt in user_targets:
    dash_h(UX + UW, tgt['l'][0], tgt['l'][1], '#9AA0A6')

# ===== 图例 =====
LY = H - 55
v_arrow(85, LY-8, 85, LY+8, C_LINE, 2)
d.text((100, LY-8), "实线: 核心数据流", fill=C_TITLE, font=font_leg)

for xx in range(310, 345, 12):
    d.line([(xx,LY),(xx+6,LY)], fill='#9AA0A6', width=2)
d.text((355, LY-8), "虚线: 用户交互 / 手动加入", fill=C_TITLE, font=font_leg)

h_arrow(660, LY, 690, LY, '#FF9800', 2)
d.text((700, LY-8), "橙色: 数据供给", fill=C_TITLE, font=font_leg)

# ===== 保存 =====
os.makedirs("项目演示", exist_ok=True)
p = "项目演示/全局联动业务流程图.png"
img.save(p, "PNG", dpi=(300,300))
print(f"已保存: {p}")
