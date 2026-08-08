#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 测试开发 + AI 持续交付架构 - 学习与发展计划
基准时间：2026年10月开始投简历，11月入职
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# ================================================================
# 字体注册
# ================================================================
font_candidates = {
    "SimHei": ["C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/SimHei.ttf"],
    "MicrosoftYaHei": ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyh.ttf"],
}
registered_fonts = set()
for fn, paths in font_candidates.items():
    for p in paths:
        if os.path.exists(p):
            try:
                pdfmetrics.registerFont(TTFont(fn, p))
                registered_fonts.add(fn)
                break
            except Exception:
                pass

def gf(preferred):
    """get first available font from preferred list"""
    for f in preferred:
        if f in registered_fonts:
            return f
    return "Helvetica"

FONT_BODY = gf(["MicrosoftYaHei", "SimHei"])
FONT_HEAD = gf(["SimHei", "MicrosoftYaHei"])

# ================================================================
# 颜色
# ================================================================
CP = HexColor("#1a5276")       # primary
CS = HexColor("#2e86c1")       # secondary
CA = HexColor("#e74c3c")       # accent
CBG = HexColor("#f8f9fa")      # bg light
CPH = HexColor("#e8f6f3")      # phase bg
CTD = HexColor("#2c3e50")      # text dark
CTM = HexColor("#5d6d7e")      # text medium
CTL = HexColor("#95a5a6")      # text light
CGR = HexColor("#27ae60")      # green
CWA = HexColor("#f39c12")      # warning

# ================================================================
# 样式（自定义名避免与 reportlab 内置冲突）
# ================================================================
def mks():
    ss = getSampleStyleSheet()
    def add(**kw):
        ss.add(ParagraphStyle(**kw))
    add(name="Z_Title", fontName=FONT_HEAD, fontSize=26, leading=36, textColor=CP, alignment=TA_CENTER, spaceAfter=6)
    add(name="Z_Subtitle", fontName=FONT_BODY, fontSize=14, leading=22, textColor=CTM, alignment=TA_CENTER, spaceAfter=8)
    add(name="Z_Date", fontName=FONT_BODY, fontSize=10, leading=14, textColor=CTL, alignment=TA_CENTER, spaceAfter=24)
    add(name="Z_H1", fontName=FONT_HEAD, fontSize=16, leading=26, textColor=CP, spaceBefore=18, spaceAfter=10)
    add(name="Z_H2", fontName=FONT_HEAD, fontSize=13, leading=22, textColor=CS, spaceBefore=14, spaceAfter=6)
    add(name="Z_Body", fontName=FONT_BODY, fontSize=10.5, leading=18, textColor=CTD, spaceBefore=4, spaceAfter=4)
    add(name="Z_Highlight", fontName=FONT_HEAD, fontSize=11, leading=18, textColor=CA, backColor=HexColor("#fadbd8"), leftIndent=10, rightIndent=10, borderPadding=6, spaceBefore=8, spaceAfter=8)
    add(name="Z_Phase", fontName=FONT_HEAD, fontSize=12, leading=22, textColor=CP, backColor=CPH, leftIndent=6, rightIndent=6, borderPadding=4, spaceBefore=10, spaceAfter=4)
    add(name="Z_Month", fontName=FONT_HEAD, fontSize=11, leading=18, textColor=CTD, spaceBefore=6, spaceAfter=2)
    add(name="Z_TH", fontName=FONT_HEAD, fontSize=10, leading=16, textColor=white, alignment=TA_CENTER)
    add(name="Z_TC", fontName=FONT_BODY, fontSize=9, leading=14, textColor=CTD)
    return ss

S = mks()

# ================================================================
# 工具
# ================================================================
def section(story, title, level="Z_H1"):
    story.append(Spacer(1, 4))
    story.append(Paragraph(title, S[level]))

def tbl(data, col_widths):
    """做表格，固定表头样式"""
    t = Table(data, colWidths=col_widths, repeatRows=1)
    ts = [
        ("FONTNAME", (0, 0), (-1, 0), FONT_HEAD),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("BACKGROUND", (0, 0), (-1, 0), CP),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 1), (-1, -1), FONT_BODY),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("TEXTCOLOR", (0, 1), (-1, -1), CTD),
        ("ALIGN", (0, 1), (-1, -1), "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#d5d8dc")),
        ("BACKGROUND", (0, 1), (-1, -1), white),
    ]
    t.setStyle(TableStyle(ts))
    return t

def H(text):
    return Paragraph(f"<b>{text}</b>", S["Z_TH"])
def C(text):
    return Paragraph(text, S["Z_TC"])

# ================================================================
# 构建 PDF
# ================================================================
def build():
    doc = []

    # ── 封面 ──
    doc.append(Spacer(1, 60))
    doc.append(Paragraph("AI 测试开发 + 持续交付架构", S["Z_Title"]))
    doc.append(Paragraph("学习与发展路线图", S["Z_Subtitle"]))
    doc.append(Paragraph("2026.10 — 2028.03 | 18 个月规划", S["Z_Date"]))

    info = [
        [C("<b>当前时间</b>"), C("2026年7月（准备期）")],
        [C("<b>计划启动</b>"), C("2026年10月 — 开始投简历")],
        [C("<b>目标入职</b>"), C("2026年11月（AI 测试开发）")],
        [C("<b>身份定位</b>"), C("AI 研发效能工程师（LLM-Native DX Engineer）")],
        [C("<b>硬件目标</b>"), C("MacBook Pro 16\" M4 Max 64GB（2027年2月购入）")],
        [C("<b>跳槽目标</b>"), C("2028年Q1（35-50K）")],
    ]
    tinfo = Table(info, colWidths=[40*mm, 110*mm])
    tinfo.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_BODY), ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), CTD), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (0, -1), CPH), ("BACKGROUND", (1, 0), (1, -1), white),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#d5d8dc")),
    ]))
    doc.append(tinfo)
    doc.append(Spacer(1, 16))

    doc.append(Paragraph(
        "核心原则：保住试用期 → 周末产出可展示成果（GitHub + CSDN）→ 每天学 1-2h",
        S["Z_Highlight"]))

    # ===============================================================
    # 一、学习计划（按优先级）
    # ===============================================================
    section(doc, "一、学习计划（按优先级）")

    section(doc, "P0 — 入职必备（2026.10-12）", "Z_H2")
    p0 = [
        [H("技能"), H("为什么"), H("学习资源"), H("周期")],
        [C("Go 语言基础"), C("云原生生态全用 Go（K8s/Docker）"), C("《Go 语言圣经》前 8 章"), C("3 周")],
        [C("Docker 进阶"), C("多阶段构建、网络、卷管理"), C("Docker 官方文档 + 公司 CI"), C("1 周")],
        [C("Git CI/CD"), C("GitHub Actions / GitLab CI"), C("AutoTestHub 接入 CI"), C("1 周")],
    ]
    doc.append(tbl(p0, [32*mm, 55*mm, 55*mm, 18*mm]))
    doc.append(Spacer(1, 10))

    section(doc, "P1 — 入职 3 个月内（2027.1-3）", "Z_H2")
    p1 = [
        [H("技能"), H("为什么"), H("学习资源"), H("周期")],
        [C("Kubernetes 核心"), C("云原生心脏"), C("《Kubernetes in Action》+ Minikube"), C("4 周")],
        [C("Helm + Kustomize"), C("K8s 应用打包管理"), C("把 AutoTestHub 写成 Helm Chart"), C("1 周")],
        [C("Prometheus + Grafana"), C("AI 流水线可观测性"), C("官网 QuickStart"), C("2 周")],
    ]
    doc.append(tbl(p1, [32*mm, 55*mm, 55*mm, 18*mm]))
    doc.append(Spacer(1, 10))

    section(doc, "P2 — 入职 6 个月内（需 MacBook，2027.3-6）", "Z_H2")
    p2 = [
        [H("技能"), H("为什么"), H("学习资源"), H("周期")],
        [C("tree-sitter AST"), C("代码评审核心"), C("官方文档 + 解析 Python/JS"), C("1 周")],
        [C("代码评审 Prompt"), C("对标人类 Code Review"), C("研究 50 份 PR + 迭代"), C("2 周")],
        [C("LLM 微调 LoRA"), C("用评审数据集微调 7B"), C("Hugging Face PEFT"), C("4 周")],
    ]
    doc.append(tbl(p2, [32*mm, 55*mm, 55*mm, 18*mm]))
    doc.append(Spacer(1, 10))

    section(doc, "P3 — 入职 12 个月内（高阶，2027.7-11）", "Z_H2")
    p3 = [
        [H("技能"), H("为什么"), H("学习资源"), H("周期")],
        [C("模型量化 GGUF/AWQ"), C("本地跑 14B"), C("llama.cpp + Ollama"), C("2 周")],
        [C("vLLM 推理加速"), C("高并发评审"), C("官方文档"), C("2 周")],
        [C("Argo Workflows"), C("云原生 CI/CD 引擎"), C("搭 Demo"), C("2 周")],
    ]
    doc.append(tbl(p3, [32*mm, 55*mm, 55*mm, 18*mm]))
    doc.append(PageBreak())

    # ===============================================================
    # 二、综合时间计划表
    # ===============================================================
    section(doc, "二、综合时间计划表（2026.10 — 2028.03）")

    doc.append(Paragraph("2026 年", S["Z_Phase"]))
    for m, d, emoji in [
        ("10月", "完善简历 + AutoTestHub v1.0 + 投简历 + 准备面试 + Go 语言入门", "🚀"),
        ("11月", "面试密集期 + 入职！活下来 + 熟悉公司 CI/CD 流程", "🔥"),
        ("12月", "Docker 进阶 + GitHub Actions + 开始发 CSDN 第一篇文章", "📝"),
    ]:
        doc.append(Paragraph(f"<b>{m}</b>  {emoji} {d}", S["Z_Month"]))

    doc.append(Spacer(1, 14))
    doc.append(Paragraph("2027 年", S["Z_Phase"]))
    for m, d in [
        ("1月", "K8s 基础学习 + 在公司试点 AI 测试（用例生成/数据构造）"),
        ("2月", "转正！买 MacBook 64GB！+ K8s 完成 + 第 1 个短视频"),
        ("3月", "AI 代码评审 Agent MVP（API 版）+ Helm 学习 + tree-sitter"),
        ("4月", "代码切分 + 评审 Prompt 迭代 + Prometheus + Grafana 监控"),
        ("5月", "本地 7B 模型微调 LoRA + 双体系联调（测试 → 评审）"),
        ("6月", "基准数据集 + A/B 评测 + GitHub 开源 AI 代码评审 Agent"),
        ("7月", "Argo Workflows + vLLM 推理加速 + 全链路打通"),
        ("8月", "录视频 + 写 3 篇重量级技术文章"),
        ("9月", "集中推广月：CSDN + B站 + 知乎 + 掘金"),
        ("10月", "GitHub 冲刺 200 Star + 开始接猎头 / 内推消息"),
        ("11月", "看机会，面试猎头推的岗位（不主动投简历）"),
        ("12月", "谈 offer（目标 35-50K）+ 准备离职"),
    ]:
        doc.append(Paragraph(f"<b>{m}</b>  {d}", S["Z_Month"]))

    doc.append(Spacer(1, 14))
    doc.append(Paragraph("2028 年", S["Z_Phase"]))
    for m, d in [
        ("1-2月", "拿完年终 → 跳槽入职新公司"),
        ("3月", "新环境站稳脚跟，身份正式切换为 AI 研发效能工程师"),
    ]:
        doc.append(Paragraph(f"<b>{m}</b>  {d}", S["Z_Month"]))

    doc.append(PageBreak())

    # ===============================================================
    # 三、推广策略
    # ===============================================================
    section(doc, "三、CSDN + 短视频推广策略")

    doc.append(Paragraph("推广不是做网红，是做技术名片。", S["Z_Body"]))
    doc.append(Spacer(1, 6))

    section(doc, "CSDN 策略（目标：一年 5000+ 粉丝）", "Z_H2")
    csdn = [
        [H("内容类型"), H("频率"), H("示例")],
        [C("效率对比实战"), C("每周 1 篇"), C("「我用 AI 把 XX 效率提升了 100 倍」— 有数据有截图")],
        [C("项目开源 + 架构"), C("每月 1 篇"), C("「独立研发 AI 测试平台，架构设计如下」")],
        [C("踩坑实录"), C("不定时"), C("「Milvus 检索踩了 3 个坑」— 真实内容流量最高")],
        [C("不要发"), C("—"), C("「Python 入门第 X 讲」— 没人看，浪费时间")],
    ]
    doc.append(tbl(csdn, [35*mm, 25*mm, 90*mm]))
    doc.append(Spacer(1, 10))

    section(doc, "短视频策略（抖音 / B站）", "Z_H2")
    vdo = [
        [H("类型"), H("示例"), H("频率")],
        [C("效率对比"), C("录屏：传统 30 分钟 vs AI 15 秒"), C("每周 1 条")],
        [C("架构讲解"), C("白板讲 RAG 原理、Agent 编排"), C("2 周 1 条")],
        [C("项目预览"), C("平台跑起来真实演示"), C("每月 1 条")],
    ]
    doc.append(tbl(vdo, [30*mm, 95*mm, 25*mm]))
    doc.append(Spacer(1, 10))

    section(doc, "推广 → 内推 → 被挖路径", "Z_H2")
    path = [
        [H("阶段"), H("里程碑"), H("预期效果")],
        [C("1-3 月"), C("默默发内容，0 粉丝也发"), C("积累作品池")],
        [C("3-6 月"), C("1-2 篇爆款（踩坑类最易爆）"), C("500 粉丝 + 评论互动")],
        [C("6-9 月"), C("GitHub 100 Star + CSDN 1000 粉"), C("有人私信「你哪个公司」")],
        [C("9-12 月"), C("GitHub 200 Star + CSDN 2000 粉"), C("猎头主动搜到你")],
        [C("12-15 月"), C("双体系各 200+ Star"), C("不投简历，等猎头来挖")],
    ]
    doc.append(tbl(path, [22*mm, 68*mm, 60*mm]))
    doc.append(PageBreak())

    # ===============================================================
    # 四、MacBook 购买
    # ===============================================================
    section(doc, "四、MacBook 购买方案")

    doc.append(Paragraph("推荐：MacBook Pro 16\" M4 Max | 64GB 统一内存 | 1TB SSD", S["Z_Body"]))
    doc.append(Paragraph("参考价格：约 ¥27,999 - 32,999", S["Z_Body"]))
    doc.append(Spacer(1, 8))

    mac = [
        [H("方案"), H("时机"), H("方式"), H("优点"), H("风险")],
        [C("A 激进"), C("入职第一月工资"), C("分期 24 期月供 ~1200"), C("早买早用"), C("试用期不稳定有压力")],
        [C("B 稳妥 ⭐"), C("转正后（2027.2）"), C("一次性或分期"), C("稳了再投入"), C("前 3 月用 API（日均 < ¥1）")],
        [C("C 保守"), C("入职 6 个月后"), C("一次性"), C("资金最宽裕"), C("太慢，时间比钱贵")],
    ]
    doc.append(tbl(mac, [22*mm, 35*mm, 35*mm, 35*mm, 35*mm]))
    doc.append(Spacer(1, 10))
    doc.append(Paragraph("建议方案 B（转正后购买）。2027.2 买 MacBook，到 2027.8 还有 6 个月黄金期把双体系全打通。", S["Z_Body"]))
    doc.append(PageBreak())

    # ===============================================================
    # 五、核心结论
    # ===============================================================
    section(doc, "五、核心结论")

    for title, body in [
        ("1. 身份定位",
         "完成 AI 测试 + AI 代码评审后，你不再是「软件测试工程师」，而是 <b>AI 研发效能工程师（LLM-Native DX Engineer）</b>。目标薪资 35-60K+。"),
        ("2. 时间预估",
         "上班状态下（工作日 3h + 周末 8h），<b>12-15 个月</b>可以把两个体系做到可展示水平。前 3 个月专心保试用期，后 12 个月周末发力。"),
        ("3. 护城河",
         "护城河不是技术壁垒，而是 <b>全链路打通的稀有性</b>。你既做了测试端又做了评审端，大厂这两个团队是割裂的——你拥有全链路视角。"),
        ("4. 推广策略",
         "CSDN + 短视频不是做网红，是 <b>技术名片</b>。目标不是粉丝数，而是让猎头和面试官搜到你名字时，看到一堆硬核成果。"),
        ("5. 现在就能开始",
         "本周就能：安装 Go 环境试水、AutoTestHub 接入 GitHub Actions、写第一篇 CSDN 踩坑文章。不需要换电脑，不花钱。"),
        ("6. 最重要的事",
         "核心就 3 件事：<b>保住试用期</b> → <b>周末产出可展示成果</b> → <b>每天学 1-2h</b>。别贪多。"),
    ]:
        doc.append(Paragraph(f"<b>{title}</b>", S["Z_H2"]))
        doc.append(Paragraph(body, S["Z_Body"]))
        doc.append(Spacer(1, 4))

    doc.append(Spacer(1, 20))
    doc.append(Paragraph("— 本计划基准时间 2026年7月制定｜10月启动｜建议每 3 个月回顾调整 —", S["Z_Date"]))

    return doc


# ================================================================
# 主函数
# ================================================================
def main():
    out_dir = "d:/AI_Project/ai-test-platform/docs"
    out_path = os.path.join(out_dir, "AI测试开发+持续交付架构_学习发展路线图_2026.pdf")
    os.makedirs(out_dir, exist_ok=True)

    pdoc = SimpleDocTemplate(
        out_path, pagesize=A4,
        rightMargin=18*mm, leftMargin=18*mm,
        topMargin=16*mm, bottomMargin=16*mm,
    )
    story = build()
    pdoc.build(story)

    sz = os.path.getsize(out_path)
    print(f"[OK] PDF: {out_path}")
    print(f"[*] Size: {sz/1024:.0f} KB")

if __name__ == "__main__":
    main()
