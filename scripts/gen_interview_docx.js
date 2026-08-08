const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, PageNumber, PageBreak, LevelFormat,
  ExternalHyperlink, TableOfContents
} = require('docx');

// Helper functions
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 60, bottom: 60, left: 100, right: 100 };

function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text, bold: true, size: 32, font: "Microsoft YaHei" })] });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text, bold: true, size: 28, font: "Microsoft YaHei" })] });
}
function h3(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun({ text, bold: true, size: 26, font: "Microsoft YaHei" })] });
}
function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 120, line: 360 },
    children: [new TextRun({ text, size: 22, font: "Microsoft YaHei", ...opts })]
  });
}
function bold(text) {
  return new TextRun({ text, bold: true, size: 22, font: "Microsoft YaHei" });
}
function normal(text) {
  return new TextRun({ text, size: 22, font: "Microsoft YaHei" });
}
function bullet(text) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    spacing: { after: 60, line: 340 },
    children: [new TextRun({ text, size: 22, font: "Microsoft YaHei" })]
  });
}
function numbered(text, ref = "numbers") {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { after: 60, line: 340 },
    children: [new TextRun({ text, size: 22, font: "Microsoft YaHei" })]
  });
}
function qaRow(question, answer) {
  return new TableRow({
    children: [
      new TableCell({
        borders, width: { size: 2800, type: WidthType.DXA }, margins: cellMargins,
        shading: { fill: "E8F0FE", type: ShadingType.CLEAR },
        children: [new Paragraph({ children: [new TextRun({ text: question, bold: true, size: 20, font: "Microsoft YaHei" })], spacing: { after: 0 } })]
      }),
      new TableCell({
        borders, width: { size: 6560, type: WidthType.DXA }, margins: cellMargins,
        children: [new Paragraph({ children: [new TextRun({ text: answer, size: 20, font: "Microsoft YaHei" })], spacing: { after: 0, line: 320 } })]
      })
    ]
  });
}

function makeTable(headers, rows, colWidths) {
  const headerRow = new TableRow({
    children: headers.map((h, i) => new TableCell({
      borders, width: { size: colWidths[i], type: WidthType.DXA }, margins: cellMargins,
      shading: { fill: "1A5276", type: ShadingType.CLEAR },
      children: [new Paragraph({ children: [new TextRun({ text: h, bold: true, size: 20, font: "Microsoft YaHei", color: "FFFFFF" })], spacing: { after: 0 } })]
    }))
  });
  const dataRows = rows.map(row => new TableRow({
    children: row.map((cell, i) => new TableCell({
      borders, width: { size: colWidths[i], type: WidthType.DXA }, margins: cellMargins,
      shading: i === 0 ? { fill: "F5F8FA", type: ShadingType.CLEAR } : undefined,
      children: [new Paragraph({ children: [new TextRun({ text: cell, size: 20, font: "Microsoft YaHei" })], spacing: { after: 0, line: 320 } })]
    }))
  }));
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [headerRow, ...dataRows]
  });
}

// Section 1: Cover
const cover = [
  new Paragraph({ spacing: { before: 3000 } }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: "面试准备文档", bold: true, size: 56, font: "Microsoft YaHei", color: "1A5276" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 }, children: [new TextRun({ text: "AI 软件测试开发工程师", size: 36, font: "Microsoft YaHei", color: "2E86C1" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: "目标公司：深圳市爱思软件技术有限公司", size: 24, font: "Microsoft YaHei", color: "666666" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: "薪资范围：25-35K·14薪", size: 24, font: "Microsoft YaHei", color: "666666" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [new TextRun({ text: "准备人：黄继根  |  2025年6月25日", size: 24, font: "Microsoft YaHei", color: "999999" })] }),
  new Paragraph({ children: [new PageBreak()] }),
];

// Section 2: TOC
const toc = [
  h1("目录"),
  new TableOfContents("目录", { hyperlink: true, headingStyleRange: "1-3" }),
  new Paragraph({ children: [new PageBreak()] }),
];

// Section 3: Quick Reference
const quickRef = [
  h1("核心要点速记卡"),
  p("面试前 5 分钟快速过一遍"),
  new Paragraph({ spacing: { after: 120 } }),
  makeTable(
    ["关键词", "一句话"],
    [
      ["AutoTestHub", "独立全栈研发的 AI 测试平台，4 大模块，已开源"],
      ["架构", "Django+Vue+ChromaDB+通义千问，插件化原子架构"],
      ["AI 测评师", "元评估模式，4 维度评测，双层次安全检测"],
      ["测试左移", "用例生成即自动评审，卡住质量入口"],
      ["测试右移", "AI 测评师追踪模型输出，上线后持续巡检"],
      ["RAG", "LangChain+ChromaDB，分块调优+阈值调优"],
      ["量化数据", "效率提升 60%/70%/90%，安全检出率提升 65%"],
      ["外包转型", "看到痛点 → 主动解决 → 产品化落地"],
      ["Java", "能阅读调试，主力 Python，学习成本低"],
      ["薪资", "期望 32K，底线 28K，14 薪"],
    ],
    [2500, 6860]
  ),
  new Paragraph({ children: [new PageBreak()] }),
];

// Section 4: 面试流程推演
const flow = [
  h1("面试流程推演"),
  p("投递日期：2025年6月25日（周四）"),
  new Paragraph({ spacing: { after: 120 } }),
  makeTable(
    ["日期", "节点", "内容"],
    [
      ["6.25 周四", "投递简历", "今天投"],
      ["6.29 周一", "HR 初筛电话", "10-15分钟，聊基本情况、薪资期望"],
      ["7.1-3", "技术一面", "测试 Leader，45-60分钟，深挖 AutoTestHub"],
      ["7.6-8", "技术二面", "技术总监/交叉面，30-45分钟"],
      ["7.8-10", "HR 谈薪", "技术面通过后1-2天"],
      ["7.10-14", "发 Offer", "谈完薪资2-3天"],
    ],
    [1500, 2500, 5360]
  ),
  new Paragraph({ spacing: { after: 120 } }),
  p("大概率 7 月中旬拿 Offer。成功率：75-80%"),
  new Paragraph({ spacing: { after: 120 } }),
  makeTable(
    ["轮次", "面试官", "难度", "核心内容"],
    [
      ["HR 初筛", "HR", "⭐", "离职原因、薪资期望、基本情况"],
      ["技术一面", "测试 Leader", "⭐⭐⭐⭐⭐", "AutoTestHub 深挖、AI 测试思路"],
      ["技术二面", "技术总监", "⭐⭐⭐", "架构能力、工程素养、团队协作"],
      ["HR 终面", "HR", "⭐⭐", "薪资谈判、入职时间"],
    ],
    [1500, 2000, 1500, 4360]
  ),
  p(""),
  p("最难的是技术一面。AutoTestHub 讲透了，Offer 就是你的。"),
  new Paragraph({ children: [new PageBreak()] }),
];

// Section 5: AutoTestHub 核心问题
const atQuestions = [
  h1("一、AutoTestHub 平台核心问题（权重 50%）"),
  p("面试官心理：这是你简历最亮眼的部分，他会深挖确认平台是否真的是你独立做的。这关过了，后面就顺了。"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q1: 介绍一下你的 AutoTestHub 平台，整体架构是怎样的？"),
  p("AutoTestHub 是我独立全栈研发的一站式 AI 智能测试平台，采用前后端分离架构："),
  bullet("前端：Vue 3.5 + Element Plus，可视化操作界面，支持低代码配置评测规则"),
  bullet("后端：Django 4.2 + Django REST Framework，插件化原子架构设计"),
  bullet("数据层：SQLite（开发）/ PostgreSQL（生产）+ ChromaDB 向量数据库"),
  bullet("AI 引擎：接入通义千问大模型，结合 LangChain + ChromaDB 实现 RAG 检索增强生成"),
  bullet("部署：支持 Docker 容器化部署"),
  p("核心四大模块："),
  bullet("AI 测评师——大模型质量评测引擎，支持多模式测评、安全扫描、结构化报告输出"),
  bullet("质量数字人——用例批量质检，四维度自动评分，内置 3 套行业模板"),
  bullet("Agent 技能系统——7 个可插拔技能，自然语言输入秒出结构化用例"),
  bullet("数据工厂——多场景测试数据智能生成，支持正负样本与边界案例"),
  p("平台遵循「测试左移 + 测试右移」双闭环质量兜底策略。已落地 19 项测评任务与 15 项用例自检任务的实战验证。"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q2: AI 测评师是怎么评估大模型输出的？"),
  p("AI 测评师采用「AI 评估 AI」的元评估模式。具体流程分五步："),
  numbered("构建评测集：支持 AI 自动生成、手动录入、批量导入三种方式"),
  numbered("调用被评测模型：将评测集中的问题逐一发送给目标大模型，获取原始输出"),
  numbered("四维度评测打分：准确率（正确/错误/部分正确三级判定）、响应时延、综合质量、安全风险"),
  numbered("安全检测（双层机制）：关键词规则匹配 + AI 深度分析（Prompt注入、数据泄露、有害内容）"),
  numbered("输出结构化评测报告：包含单题详情、维度分布、风险点汇总、改进建议"),
  p("核心价值：把 AI 大模型的线上质量从「拍脑袋感觉」变成「可量化、可巡检、可持续优化」的工程化体系。"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q3: 为什么选择 ChromaDB 而不是其他向量数据库？"),
  bullet("轻量化部署：嵌入式向量库，不需要单独部署服务，降低运维复杂度"),
  bullet("开发效率：Python API 简洁，和 LangChain 集成成熟，适合独立开发者快速验证"),
  bullet("场景匹配：知识库规模在万级文档以内，ChromaDB 性能完全够用"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q4: RAG 知识库怎么做的？检索效果怎么保证？"),
  p("基于 LangChain + ChromaDB 搭建："),
  bullet("文档处理：支持 PDF/DOCX/TXT 上传 → 自动分段（chunk_size=500, chunk_overlap=50）→ 向量化 → 存入 ChromaDB"),
  bullet("检索流程：用户提问 → 向量化 → 相似度搜索（阈值 0.7）→ Top-K 文档拼接上下文 → 大模型生成回答"),
  bullet("调优方法：调整分块策略、召回阈值测试、Rerank 后处理"),
  bullet("评测指标：召回率、精确率、MRR（平均倒数排名）"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q5: Agent 技能系统是什么原理？"),
  p("核心原理：Prompt Engineering + RAG 增强 + 结构化输出"),
  bullet("用户输入自然语言需求 → 系统加载对应技能的 System Prompt"),
  bullet("拼接 RAG 知识库中的项目上下文（业务规则、历史用例）"),
  bullet("发送给大模型，要求按指定 JSON Schema 输出"),
  bullet("前端解析 JSON → 渲染为表格 → 支持导出 Excel/JSON"),
  p("7 个可插拔技能覆盖：功能测试、安全测试、API 测试、边界测试、性能测试、兼容性测试、UI 测试"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q6: 质量数字人的四维度自动评分是哪四个维度？"),
  bullet("完整性：必要字段是否齐全（编号、标题、前置条件、步骤、预期结果）"),
  bullet("规范性：格式是否符合标准（步骤是否可执行、预期结果是否可验证）"),
  bullet("内容质量：业务覆盖度、逻辑合理性、是否有歧义"),
  bullet("可执行性：步骤是否具体可操作、前置条件是否充分"),
  p("内置 3 套行业模板（功能/接口/金融），150 条用例批量评审，输出等级分布与逐条缺陷定位。"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q7: 数据工厂和直接问 AI 有什么区别？"),
  bullet("预置业务模板：金融科技、跨境电商等行业模板，一键生成"),
  bullet("正负样本 + 边界案例：不只生成正常数据，还覆盖异常值和边界值"),
  bullet("结构化输出：JSON/CSV/Excel 多种格式，直接对接测试流程"),
  bullet("核心区别：模板化复用 + 格式固定 + 可直接导入自动化脚本，效率提升 80%"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q8: 你做 AutoTestHub 踩过最大的坑是什么？"),
  p("ChromaDB 向量检索的召回效果不稳定。"),
  p("排查过程：准备标注问答对 → 用不同分块参数测试召回率和精确率 → 发现 chunk_size 太大导致主题混杂。"),
  p("解决方案：调整为 chunk_size=500, chunk_overlap=50，相似度阈值从 0.5 提高到 0.7，增加 rerank 后处理。"),
  p("经验教训：RAG 不是「搭起来就能用」，需要持续调优。"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q9: 一个人做全栈，时间怎么分配？"),
  bullet("前期（30%）：需求梳理 + 架构设计，基于中行一线痛点确定核心功能"),
  bullet("中期（40%）：核心模块开发（AI 测评师 → 质量数字人 → Agent 技能 → 数据工厂）"),
  bullet("后期（30%）：测试验证 + 文档 + 开源准备"),
  p("最大挑战不是技术，是功能取舍——什么先做、什么后做、什么不做。"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q10: 平台从开发到现在的迭代过程是怎样的？"),
  bullet("V1.0（MVP）：核心验证——AI 测评师单题评测，验证「AI 评估 AI」可行性"),
  bullet("V2.0（功能完善）：批量评测、多维度打分、安全扫描、质量数字人、Agent 技能"),
  bullet("V3.0（效率提升）：数据工厂、接口智能解析、可视化编排、全链路执行度量"),
  bullet("V4.0（生态建设）：开源、文档完善、Docker 部署、插件化架构重构"),
  new Paragraph({ children: [new PageBreak()] }),
];

// Section 6: AI测试与评测
const aiQuestions = [
  h1("二、AI 测试与评测体系（权重 25%）"),

  h2("Q11: 大模型测试和传统软件测试最大的区别？"),
  p("核心区别在于确定性与不确定性："),
  makeTable(
    ["维度", "传统软件测试", "大模型测试"],
    [
      ["输入", "确定", "确定"],
      ["输出", "确定（可精确断言）", "不确定（语义级评估）"],
      ["验证方式", "assert == expected", "语义相似度 / 人工+AI评估"],
      ["质量维度", "功能正确性", "准确性+安全性+流畅性+合规性"],
      ["缺陷类型", "Bug（代码逻辑错误）", "幻觉、偏见、越狱、不当输出"],
    ],
    [1800, 3780, 3780]
  ),
  p("最大的难点：没法写 assert response == 标准答案，因为大模型的回答没有唯一标准答案。"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q12: 大模型的安全测试你做过哪些？"),
  p("四大类安全测试，单任务最高检出 4 个风险点："),
  bullet("Prompt 注入攻击：在用户输入中注入指令，试图覆盖系统提示词"),
  bullet("越狱攻击（Jailbreak）：通过角色扮演、多轮递进等方式绕过安全限制"),
  bullet("有害内容生成：检测模型是否输出歧视性、暴力、色情等内容"),
  bullet("数据泄露：测试模型是否在回答中泄露训练数据中的个人信息"),
  p("检测机制：关键词规则 + AI 深度分析双层次检测，安全风险检出率较人工提升 65%。"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q13: RAG 评测体系具体怎么搭建？"),
  p("核心指标："),
  makeTable(
    ["指标", "含义", "目标"],
    [
      ["召回率（Recall）", "相关文档有多少被检索到", ">0.8"],
      ["精确率（Precision）", "检索到的文档有多少相关", ">0.8"],
      ["MRR", "第一个相关文档的平均排名倒数", "越高越好"],
      ["答案准确率", "生成答案与标准答案的一致性", ">0.85"],
    ],
    [2200, 4360, 2800]
  ),
  p("搭建流程：准备标注数据集 → 不同参数跑检索测试 → 计算指标找最优参数 → 定期更新评测集。"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q14: 「测试左移 + 测试右移」怎么落地？"),
  p("测试左移（前置质量防护）：用例生成阶段启动自动质检，用例产出即评审，卡住质量入口。"),
  p("测试右移（上线后持续监测）：AI 测评师追踪模型上线后的输出质量，从幻觉检测到安全扫描全维度巡检。"),
  p("双闭环价值：把测试从点状验证升级为覆盖需求入口到模型输出端的全链路质量闭环。"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q15: 你怎么判断一个大模型的「能力边界」？"),
  bullet("知识边界：通过知识库问答评测，测试模型对特定领域的掌握程度"),
  bullet("推理边界：通过多步推理题、逻辑题测试，看模型能处理多复杂的推理链"),
  bullet("安全边界：通过安全测试用例集，找出模型在什么输入下会突破安全限制"),
  new Paragraph({ children: [new PageBreak()] }),
];

// Section 7: 自动化与工程
const engQuestions = [
  h1("三、自动化与工程能力（权重 15%）"),

  h2("Q16: Playwright 自动化怎么做的？遇到什么难点？"),
  bullet("OPPO 项目中用 Python+Playwright 写了 150+ 条 UI 自动化用例"),
  bullet("难点1：动态元素定位 → 推动开发加 data-testid 属性"),
  bullet("难点2：异步加载等待 → 用 Playwright 的 wait_for_selector 等智能等待"),
  bullet("难点3：多租户切换 → 封装租户切换 fixture，复用登录状态"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q17: CI/CD 流水线中测试怎么嵌入？"),
  p("流水线位置：代码提交 → 代码扫描 → 单元测试 → 构建 → 自动化测试 → 安全扫描 → 性能测试 → 部署"),
  bullet("测试用例要能在流水线中稳定运行——处理好环境依赖"),
  bullet("测试数据隔离——每次运行用独立的测试数据集"),
  bullet("失败快速反馈——测试失败立即通知，不等到全跑完"),
  p("效果：流水线构建失败率从 12% 优化至 3% 以内。"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q18: 你会 Java 吗？到什么程度？"),
  p("主力语言是 Python。Java 能阅读业务代码、简单调试，但没有用 Java 做过完整项目。"),
  p("AutoTestHub 全栈是用 Python（Django）+ JavaScript（Vue）完成的。"),
  p("核心能力不在语言层面，在于测试体系设计、AI 评测方法论、从 0 到 1 搭建质量工具体系。"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q19: 你做过的性能测试具体有哪些？"),
  bullet("JMeter 和 Locust 都熟练使用"),
  bullet("中行 AI Coding 项目中做 AI 全链路压测：模拟多用户并发调用大模型接口"),
  bullet("核心指标：QPS、响应时延（P50/P95/P99）、错误率"),
  bullet("效果：核心接口平均延迟下降 25%"),
  bullet("了解的进阶方向：全链路压测（SkyWalking）、ELK 日志体系、流量录制回放、JVM 监控"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q20: 熟悉的安全测试有哪些？"),
  bullet("漏洞类型：XSS、CSRF、SQL 注入、权限越权、路径遍历"),
  bullet("中行实践：120+ 条安全合规用例，验证多租户数据隔离"),
  bullet("累计闭环 250+ 有效缺陷"),
  bullet("工具：了解 OWASP ZAP，可完成基础站点扫描与报告输出"),
  new Paragraph({ children: [new PageBreak()] }),
];

// Section 8: 行为面试
const behaviorQuestions = [
  h1("四、行为面试与软技能（权重 10%）"),

  h2("Q21: 为什么从外包转到 AI 测试开发？"),
  p("在中行做 AI Coding 项目时，我发现外包团队普遍依赖人工逐条完成大模型评测，效率极低，每次新项目都要从零梳理测试规则。"),
  p("我意识到这个问题可以通过产品化来解决——做一个 AI 测试平台，把重复性工作自动化。"),
  p("于是我在工作之余独立研发了 AutoTestHub，把一线痛点转化为产品功能。这个过程让我确认了真正的方向：做 AI 测试开发的工具和体系建设。"),
  p("注意：不要说「外包不好」，要说「看到了行业痛点，主动去解决」。"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q22: 独立研发一个平台，遇到的最大困难是什么？"),
  p("不是技术，是一个人要做所有决策。技术问题有文档和社区，但「做什么、不做什么、先做什么」这些产品决策，没人帮你拍板。"),
  p("方法：基于一线业务痛点确定优先级 → 每个功能先做 MVP → 定期复盘砍掉低使用率功能。"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q23: 怎么看待加班？"),
  p("不排斥必要的加班（版本上线、紧急修复），但更倾向于通过提升效率来减少不必要的加班。AutoTestHub 的设计初衷之一就是把人从重复性工作中解放出来。"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q24: 职业规划是什么？"),
  bullet("短期（1-2年）：在 AI 测试开发方向上深耕，把经验应用到企业级场景"),
  bullet("中期（3-5年）：成为 AI 质量架构方向专家，设计覆盖多业务线的统一质量保障体系"),
  bullet("长期：推动 AI 测试的标准化和工程化，让质量保障可量化、可复制"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q25: 和 Leader 有分歧怎么处理？"),
  bullet("先理解再表达：搞清楚 Leader 为什么有不同想法"),
  bullet("用数据说话：准备对比分析，让讨论基于事实"),
  bullet("尊重最终决策：讨论完坚决执行，用结果验证"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q26: 之前都是外包，适应自研团队吗？"),
  p("完全适应。虽然之前是外包驻场，但做的事情和正式员工没有本质区别。"),
  p("最大的不同是所有权感——自研团队对产品的长期质量更有责任感。这也是我想要的——AutoTestHub 就是我自己「拥有」的产品，我习惯了为长期质量负责。"),
  new Paragraph({ spacing: { after: 200 } }),

  h2("Q27: 对 AI 测试这个方向的未来怎么看？"),
  bullet("辅助阶段（现在）：AI 帮人写用例、生成测试数据，人还是测试的主体"),
  bullet("自动化阶段（1-3年）：AI 独立完成大部分测试任务，人主要负责审核和决策"),
  bullet("自适应阶段（3-5年）：AI 自动感知系统变化、自适应调整测试策略"),
  p("先入场的人会有巨大的先发优势。"),
  new Paragraph({ children: [new PageBreak()] }),
];

// Section 9: 反问 + 薪资
const finalSection = [
  h1("五、反问面试官的问题"),

  h2("技术面反问："),
  bullet("「团队目前 AI 测试这块处于什么阶段？是从 0 开始搭建，还是有基础框架了？」"),
  bullet("「目前团队在 AI 质量保障方面遇到的最大挑战是什么？」"),
  bullet("「技术栈方面，团队主要用什么语言和框架？AI 方面用的是哪些模型？」"),
  bullet("「这个岗位的日常工作大概是怎样的？代码开发、评测设计、问题排查各占多少？」"),

  h2("HR 面反问："),
  bullet("「14 薪是固定还是浮动的？年终奖的考核标准是什么？」"),
  bullet("「试用期多久？薪资打几折？」"),
  bullet("「五险一金的缴纳基数和比例是怎样的？」"),
  bullet("「团队规模和分工是怎样的？」"),

  new Paragraph({ spacing: { after: 300 } }),

  h1("六、薪资谈判话术"),

  h2("简历期望：30K"),
  h2("HR 初筛问期望："),
  p("「我看贵司岗位预算是 25-35K，结合我的经验——独立全栈研发 AI 测试平台并已开源落地，6 年从传统测试进阶到 AI 测试开发——我的期望在 30-35K 区间，具体可以根据面试情况再沟通。」"),

  h2("技术面后 HR 谈薪："),
  p("「聊下来感觉方向非常匹配，我也很感兴趣。结合我的经验——独立全栈研发 AI 测试平台并已开源落地——我的期望是 32K 左右。」"),

  h2("被压价到 28-29K 时："),
  p("「28K 和我预期有一点差距。我带来的不只是一个测试工程师的工时，是一套可复用的 AI 质量保障体系。30K 的话我这边没问题，你看能争取一下吗？」"),

  makeTable(
    ["你报", "HR 大概率还", "你接受"],
    [
      ["32K", "30K", "✅ 接受"],
      ["32K", "28-29K", "争取到 30K"],
      ["32K", "27K 以下", "慎重，了解试用期和调薪机制"],
    ],
    [2500, 2500, 4360]
  ),

  new Paragraph({ spacing: { after: 300 } }),

  h1("七、面试前检查清单"),

  h2("🔴 必做（今晚完成）"),
  bullet("AutoTestHub 架构口述：能 2-3 分钟讲清楚（练 3 遍）"),
  bullet("AI 测评师四维度评测流程：能不看文档讲出来"),
  bullet("每个项目经历一句话总结：中行/OPPO/华为/富泰华"),
  bullet("准备好 GitHub 仓库：确保代码可见、README 完整"),

  h2("🟡 建议做（面试前一天）"),
  bullet("Java 基础快速过一遍：语法、集合、多线程"),
  bullet("准备一个 Demo：打开 GitHub 展示代码结构"),
  bullet("了解目标公司业务：技术栈、产品方向"),
  bullet("准备 2 个反问问题"),

  h2("🟢 加分项"),
  bullet("打印一份简历（线下面试用）"),
  bullet("准备一个成功案例：你解决过的最难的技术问题"),
  bullet("准备一个失败案例：你犯过的最大错误 + 学到了什么"),

  new Paragraph({ spacing: { after: 300 } }),

  p("AutoTestHub 是你最大的差异化武器。面试官最想听的就是这个。讲透了，Offer 就是你的。", { bold: true, size: 24, color: "1A5276" }),
];

// Build document
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Microsoft YaHei", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Microsoft YaHei", color: "1A5276" },
        paragraph: { spacing: { before: 360, after: 240 }, outlineLevel: 0, border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "2E86C1", space: 4 } } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Microsoft YaHei", color: "2E86C1" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Microsoft YaHei", color: "34495E" },
        paragraph: { spacing: { before: 180, after: 60 }, outlineLevel: 2 } },
    ]
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 }, // A4
        margin: { top: 1200, right: 1200, bottom: 1200, left: 1200 }
      }
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({ text: "面试准备文档 - AI 软件测试开发工程师", size: 18, font: "Microsoft YaHei", color: "999999", italics: true })]
        })]
      })
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "第 ", size: 18, font: "Microsoft YaHei", color: "999999" }), new TextRun({ children: [PageNumber.CURRENT], size: 18, font: "Microsoft YaHei", color: "999999" }), new TextRun({ text: " 页", size: 18, font: "Microsoft YaHei", color: "999999" })]
        })]
      })
    },
    children: [
      ...cover,
      ...toc,
      ...quickRef,
      ...flow,
      ...atQuestions,
      ...aiQuestions,
      ...engQuestions,
      ...behaviorQuestions,
      ...finalSection,
    ]
  }]
});

// Generate
const outputPath = "d:/AI_Project/ai-test-platform/docs/面试准备-AI软件测试开发工程师-爱思软件.docx";
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outputPath, buffer);
  console.log("Word 文档已生成：" + outputPath);
});
