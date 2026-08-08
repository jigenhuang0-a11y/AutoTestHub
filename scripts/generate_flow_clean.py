#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高清流程图 - 优化连线，减少交叉，指向明确
画布: 2000x1500，节点不变，只优化连线
"""

from PIL import Image, ImageDraw, ImageFont
import os, math

W, H = 2000, 1500

# ---- 字体 ----
font_title = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 50)
font_sub = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 24)
font_node = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 30)
font_node_small = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 19)
font_label = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
font_legend = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)

# ---- 颜色 ----
C_BG = '#FAFBFC'
C_BORDER = '#DADCE0'
C_TITLE = '#202124'
C_SUB = '#5F6368'

LAYER_COLORS = [
    ('#E8F0FE', '#4285F4', '数据准备'),
    ('#F3E5F5', '#9C27B0', 'AI生成'),
    ('#E8F5E9', '#34A853', '用例管理'),
    ('#FFF3E0', '#FF9800', '质检与编排'),
    ('#FCE4EC', '#EC407A', '执行与报告'),
]

NODE_W, NODE_H = 280, 115
ARROW_COLOR = '#5F6368'  # 统一箭头颜色更低调

def arrow_vert(draw, x1, y1, x2, y2, color, width=2):
    """垂直向下箭头（x相同）"""
    draw.line([(x1, y1), (x2, y2)], fill=color, width=width)
    # 箭头
    draw.polygon([(x2, y2), (x2-6, y2-8), (x2+6, y2-8)], fill=color)

def arrow_h(draw, x1, y1, x2, y2, color, width=2):
    """水平箭头"""
    draw.line([(x1, y1), (x2, y2)], fill=color, width=width)
    # 箭头
    if x2 > x1:
        draw.polygon([(x2, y2), (x2-8, y2-6), (x2-8, y2+6)], fill=color)
    else:
        draw.polygon([(x2, y2), (x2+8, y2-6), (x2+8, y2+6)], fill=color)

def arrow_orth(draw, x1, y1, x2, y2, color, width=2):
    """直角折线箭头：先垂直再水平或先水平再垂直"""
    if abs(x1 - x2) < 10:
        arrow_vert(draw, x1, y1, x2, y2, color, width)
        return
    if abs(y1 - y2) < 10:
        arrow_h(draw, x1, y1, x2, y2, color, width)
        return
    # 先垂直再水平
    mid_y = y2
    draw.line([(x1, y1), (x1, mid_y)], fill=color, width=width)
    draw.line([(x1, mid_y), (x2, mid_y)], fill=color, width=width)
    # 箭头
    if x2 > x1:
        draw.polygon([(x2, mid_y), (x2-8, mid_y-6), (x2-8, mid_y+6)], fill=color)
    else:
        draw.polygon([(x2, mid_y), (x2+8, mid_y-6), (x2+8, mid_y+6)], fill=color)

def dash_line(draw, x1, y1, x2, y2, color, width=2):
    dx = x2 - x1
    dy = y2 - y2
    if abs(x2 - x1) > abs(y2 - y1):
        # 水平虚线
        for xx in range(x1, x2, 12):
            draw.line([(xx, y1), (xx+6, y1)], fill=color, width=width)
    else:
        # 垂直虚线
        for yy in range(y1, y2, 12):
            draw.line([(x1, yy), (x1, yy+6)], fill=color, width=width)

def draw_node(draw, x, y, w, h, title, subtitle, color, font_title, font_sub):
    r = 10
    draw.rounded_rectangle([x, y, x + w, y + h], radius=r, fill='white', outline=color, width=3)
    draw.text((x + w//2, y + h//2 - 14), title, fill=color, font=font_title, anchor="mm")
    draw.text((x + w//2, y + h//2 + 16), subtitle, fill=C_SUB, font=font_sub, anchor="mm")
    # 返回连接点
    return {
        'top': (x + w//2, y),
        'bottom': (x + w//2, y + h),
        'left': (x, y + h//2),
        'right': (x + w, y + h//2)
    }

# ---- 创建画布 ----
img = Image.new('RGB', (W, H), C_BG)
draw = ImageDraw.Draw(img)

# ---- 标题 ----
draw.text((W//2, 35), "AI测试平台 全局联动业务流程图", fill=C_TITLE, font=font_title, anchor="mt")
draw.text((W//2, 80), "核心主链路：数据准备 → AI生成 → 用例管理 → 质检与编排 → 执行与报告", fill=C_SUB, font=font_sub, anchor="mt")

# ---- 泳道 ----
LANE_X = 80
LANE_W = W - 210
LANE_Y = 115
LANE_H = 240
LAYERS = 5

for i, (bg_c, accent_c, label) in enumerate(LAYER_COLORS):
    y = LANE_Y + i * LANE_H
    draw.rectangle([LANE_X, y, LANE_X + LANE_W, y + LANE_H - 10], fill=bg_c, outline=C_BORDER, width=1)
    draw.text((LANE_X + 15, y + LANE_H//2 - 15), label, fill=accent_c, font=font_label, anchor="lm")

# ---- 左侧用户条 ----
USER_X = LANE_X - 55
USER_W = 40
draw.rectangle([USER_X, LANE_Y, USER_X + USER_W, LANE_Y + LAYERS * LANE_H - 10], fill='#1565C0')
for i, c in enumerate("用户入口"):
    draw.text((USER_X + USER_W//2, LANE_Y + 50 + i * 24), c, fill='white', font=font_label, anchor="mm")

# ---- 右侧 AI问答评测 ----
EVAL_X = LANE_X + LANE_W + 20
EVAL_W = 60
draw.rectangle([EVAL_X, LANE_Y, EVAL_X + EVAL_W, LANE_Y + LAYERS * LANE_H - 10], fill='#D84315')
for i, c in enumerate("AI问答评测"):
    draw.text((EVAL_X + EVAL_W//2, LANE_Y + 60 + i * 24), c, fill='white', font=font_label, anchor="mm")

# ---- 绘制节点 ----
# 第1层
Y1 = LANE_Y + (LANE_H - NODE_H) // 2
KB_X = 220
DF_X = 520
KB = draw_node(draw, KB_X, Y1, NODE_W, NODE_H, "知识库 (RAG)", "文档上传 · 向量检索 · Milvus", LAYER_COLORS[0][1], font_node, font_node_small)
DF = draw_node(draw, DF_X, Y1, NODE_W, NODE_H, "数据工厂", "Faker造数 · 模板管理 · 版本快照", LAYER_COLORS[0][1], font_node, font_node_small)

# 第2层
Y2 = LANE_Y + LANE_H + (LANE_H - NODE_H) // 2
AGENT_X = 390
AGENT = draw_node(draw, AGENT_X, Y2, NODE_W, NODE_H, "AI用例生成", "Agent工作流 · 自然语言→结构化用例", LAYER_COLORS[1][1], font_node, font_node_small)

# 第3层
Y3 = LANE_Y + LANE_H * 2 + (LANE_H - NODE_H)//2
API_X = 120
WEB_X = API_X + NODE_W + 60
PERF_X = WEB_X + NODE_W + 60
QC_X = PERF_X + NODE_W + 80

API = draw_node(draw, API_X, Y3, NODE_W, NODE_H, "API用例管理", "HTTP接口 · JSONPath断言", LAYER_COLORS[2][1], font_node, font_node_small)
WEB = draw_node(draw, WEB_X, Y3, NODE_W, NODE_H, "Web自动化用例", "Playwright · Midscene AI", LAYER_COLORS[2][1], font_node, font_node_small)
PERF = draw_node(draw, PERF_X, Y3, NODE_W, NODE_H, "性能测试用例", "Locust压测 · 实时指标", LAYER_COLORS[2][1], font_node, font_node_small)
QC = draw_node(draw, QC_X, Y3, NODE_W, NODE_H, "质量数字人", "三维度评分 · 重复检测", LAYER_COLORS[3][1], font_node, font_node_small)

# 第4层
Y4 = LANE_Y + LANE_H * 3 + (LANE_H - NODE_H)//2
SUITE_X = 390
EXEC_X = SUITE_X + NODE_W + 100
SUITE = draw_node(draw, SUITE_X, Y4, NODE_W, NODE_H, "测试套件", "聚合API+Web+性能用例", LAYER_COLORS[3][1], font_node, font_node_small)
EXEC = draw_node(draw, EXEC_X, Y4, NODE_W, NODE_H, "测试执行引擎", "Pytest脚本 · 多触发方式", LAYER_COLORS[4][1], font_node, font_node_small)

# 第5层
Y5 = LANE_Y + LANE_H * 4 + (LANE_H - NODE_H)//2
REPORT_X = 390
REPORT = draw_node(draw, REPORT_X, Y5, NODE_W, NODE_H, "报告中心", "Allure · HTML · AI评估", LAYER_COLORS[4][1], font_node, font_node_small)

# ---- 连线 - 核心数据流（实线，带箭头，垂直为主） ----

# 1. 知识库 → AI用例生成（垂直向下）
arrow_vert(draw, KB['bottom'][0], KB['bottom'][1], AGENT['top'][0], AGENT['top'][1], LAYER_COLORS[0][1], 2)

# 2. 数据工厂 → AI用例生成（垂直向下）
arrow_vert(draw, DF['bottom'][0], DF['bottom'][1], AGENT['top'][0], AGENT['top'][1], LAYER_COLORS[0][1], 2)

# 3. AI用例生成 → 3种用例（分别向下）
arrow_vert(draw, AGENT['bottom'][0] - 80, AGENT['bottom'][1], API['top'][0], API['top'][1], LAYER_COLORS[1][1], 2)
arrow_vert(draw, AGENT['bottom'][0], AGENT['bottom'][1], WEB['top'][0], WEB['top'][1], LAYER_COLORS[1][1], 2)
arrow_vert(draw, AGENT['bottom'][0] + 80, AGENT['bottom'][1], PERF['top'][0], PERF['top'][1], LAYER_COLORS[1][1], 2)

# 4. 3种用例 → 测试套件（各自向下）
arrow_vert(draw, API['bottom'][0], API['bottom'][1], SUITE['top'][0], SUITE['top'][1], LAYER_COLORS[2][1], 2)
arrow_vert(draw, WEB['bottom'][0], WEB['bottom'][1], SUITE['top'][0], SUITE['top'][1], LAYER_COLORS[2][1], 2)
arrow_vert(draw, PERF['bottom'][0], PERF['bottom'][1], SUITE['top'][0], SUITE['top'][1], LAYER_COLORS[2][1], 2)

# 5. 质量数字人 → 测试套件（向左再向下）
arrow_orth(draw, QC['left'][0], QC['left'][1], SUITE['top'][0] + 60, SUITE['top'][1], LAYER_COLORS[3][1], 2)

# 6. 测试套件 → 测试执行引擎（水平向右）
arrow_h(draw, SUITE['right'][0], SUITE['right'][1], EXEC['left'][0], EXEC['left'][1], LAYER_COLORS[3][1], 3)

# 7. 测试执行引擎 → 报告中心（垂直向下）
arrow_vert(draw, EXEC['bottom'][0], EXEC['bottom'][1], REPORT['top'][0] + 100, REPORT['top'][1], LAYER_COLORS[4][1], 3)

# 8. 数据工厂 → API用例（水平供给数据）
arrow_orth(draw, DF['right'][0], DF['right'][1], API['right'][0] + 20, API['right'][1], '#FF9800', 2)

# 9. 知识库 → AI问答评测（水平向右）
arrow_h(draw, KB['right'][0], KB['right'][1], EVAL_X, LANE_Y + 100, '#D84315', 2)

# ---- 用户虚线（灰色虚线） ----
for y, node in [(Y1, KB), (Y2, AGENT), (Y3, API), (Y4, EXEC), (Y5, REPORT)]:
    dash_line(draw, USER_X + USER_W, node['left'][1], node['left'][0], node['left'][1], '#9AA0A6', 2)

# ---- 图例 ----
LEGEND_Y = H - 50
arrow_vert(draw, 80, LEGEND_Y - 8, 80, LEGEND_Y + 8, LAYER_COLORS[0][1], 2)
draw.text((95, LEGEND_Y - 8), "实线: 核心数据流", fill=C_TITLE, font=font_legend)

for xx in range(340, 370, 12):
    draw.line([(xx, LEGEND_Y), (xx+6, LEGEND_Y)], fill='#9AA0A6', width=2)
draw.text((380, LEGEND_Y - 8), "虚线: 用户交互/触发", fill=C_TITLE, font=font_legend)

arrow_h(draw, 660, LEGEND_Y, 690, LEGEND_Y, '#D84315', 2)
draw.text((700, LEGEND_Y - 8), "橙色: 数据供给 / AI问答评测", fill=C_TITLE, font=font_legend)

# ---- 保存 ----
os.makedirs("项目演示", exist_ok=True)
path = "项目演示/全局联动业务流程图.png"
img.save(path, "PNG", dpi=(300, 300))
print(f"已保存: {path}")
