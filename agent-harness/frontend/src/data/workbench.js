import {
  Setting, Cpu, Collection, DataAnalysis, ChatDotRound, MagicStick,
  Document, Connection, Monitor, Odometer, FolderAdd, Timer,
  DocumentChecked, TrendCharts, PieChart, Link, SetUp, Grid, Tools,
  Tickets, Calendar
} from '@element-plus/icons-vue'

// 产品域工作台：把原本按能力维度的分组重构成按产品域维度
export const domains = [
  {
    key: 'base',
    label: 'AI 效能中台',
    desc: 'AI 底座 + 运维观测一体化',
    sections: [
      {
        key: 'ai-core',
        title: 'AI 核心底座',
        cards: [
          { id: 'r1-1', title: 'AI底座配置', subtitle: '模型入、权限、配额', icon: Setting, route: '/settings', type: 'normal' },
          { id: 'r1-2', title: '模型配置', subtitle: '团队模型、参数调优', icon: Cpu, route: '/team-model-settings', type: 'normal' },
          { id: 'r1-7', title: '系统设置', subtitle: '配置中心、权限管理', icon: SetUp, route: '/settings', type: 'normal' }
        ]
      },
      {
        key: 'ops',
        title: '运维观测管理',
        cards: [
          { id: 'r3-2', title: '任务监控', subtitle: 'Celery队列、状态看板', icon: TrendCharts, route: '/monitor', type: 'normal' },
          { id: 'r3-3', title: '审计大屏', subtitle: '操作日志、合规审计', icon: PieChart, route: '/audit', type: 'normal' },
          { id: 'r3-4', title: '链路追踪', subtitle: '分布式Trace、调用链', icon: Link, route: '/trace', type: 'normal' },
          { id: 'r3-5', title: 'MCP工具网关', subtitle: '工具注册、权限管控', icon: SetUp, route: '/mcp-gateway', type: 'normal' },
          { id: 'r3-6', title: '沙箱管控', subtitle: '隔离执行、资源配额', icon: Grid, route: '/sandbox', type: 'normal' },
          { id: 'r3-7', title: '环境管理', subtitle: '环境配置、部署管理', icon: Tools, route: '/env', type: 'normal' },
          { id: 'r3-8', title: 'Agent 编排中心', subtitle: '多 Agent 团队协作编排与监控', icon: Connection, route: '/agent-orchestrator', type: 'highlight' }
        ]
      }
    ]
  },
  {
    key: 'test',
    label: 'AI 测试平台',
    desc: '面向测试人员的智能测试工作台',
    sections: [
      {
        key: 'testing-ai',
        title: 'AI 增强测试',
        cards: [
          { id: 'r1-3', title: '测试知识库', subtitle: 'RAG 知识点加载与问答', icon: Collection, route: '/knowledge/chat', type: 'normal' },
          { id: 'r1-4', title: '全链路评测中心', subtitle: '基于AI底座的智能体评估追踪', icon: DataAnalysis, route: '/eval-center', type: 'highlight' },
          { id: 'r1-5', title: '需求评审师', subtitle: '评审需求、评估测试用例', icon: ChatDotRound, route: '/quality-checker', type: 'normal' },
          { id: 'r1-6', title: '数据工厂', subtitle: '测试数据构造与生成', icon: MagicStick, route: '/data-factory', type: 'normal' }
        ]
      },
      {
        key: 'testing',
        title: '自动化测试工具链',
        cards: [
          { id: 'r2-1', title: '用例生成', subtitle: 'AI生成用例、测试数据', icon: Document, route: '/testcases/ai-generate', type: 'normal' },
          { id: 'r2-2', title: '接口测试', subtitle: '自动化、套件、报表', icon: Connection, route: '/testcases', type: 'focus' },
          { id: 'r2-3', title: 'UI自动化', subtitle: 'Web流程、回放', icon: Monitor, route: '/web-testcases', type: 'normal' },
          { id: 'r2-4', title: '性能测试', subtitle: '压测、瓶颈、分析', icon: Odometer, route: '/perf-testcases', type: 'normal' },
          { id: 'r2-6', title: '测试套件', subtitle: '组合编排、批量执行', icon: FolderAdd, route: '/testsuites', type: 'normal' },
          { id: 'r2-7', title: '执行历史', subtitle: '运行记录、实时追踪', icon: Timer, route: '/history', type: 'normal' }
        ]
      },
      {
        key: 'testing-report',
        title: '质量报告',
        cards: [
          { id: 'r3-1', title: '测试报告', subtitle: '结果汇总、趋势分析', icon: DocumentChecked, route: '/reports', type: 'normal' }
        ]
      }
    ]
  },
  {
    key: 'case',
    label: '用例平台',
    desc: '下一代用例管理与协作',
    comingSoon: true,
    sections: [
      {
        key: 'case-lib',
        title: '规划中',
        cards: [
          { id: 'c1', title: '用例库', subtitle: '统一用例资产管理', icon: Tickets, route: '', type: 'normal', disabled: true },
          { id: 'c2', title: '协作评审', subtitle: '团队用例评审', icon: ChatDotRound, route: '', type: 'normal', disabled: true }
        ]
      }
    ]
  },
  {
    key: 'schedule',
    label: '团队排期',
    desc: '团队协作与排期管理',
    comingSoon: true,
    sections: [
      {
        key: 'schedule-plan',
        title: '规划中',
        cards: [
          { id: 's1', title: '迭代排期', subtitle: 'Sprint 规划与跟踪', icon: Calendar, route: '', type: 'normal', disabled: true },
          { id: 's2', title: '任务看板', subtitle: '团队任务协作', icon: Grid, route: '', type: 'normal', disabled: true }
        ]
      }
    ]
  }
]

// 兼容旧数据导出
export const categories = domains.flatMap(d => d.sections)
export const allCards = domains.flatMap(d => d.sections.flatMap(s => s.cards))
export const cardCategoryMap = new Map()
domains.forEach(d => {
  d.sections.forEach(s => {
    s.cards.forEach(card => {
      if (card.route) cardCategoryMap.set(card.route, s.key)
    })
  })
})

export const domainMap = Object.fromEntries(domains.map(d => [d.key, d]))
export const cardDomainMap = new Map()
domains.forEach(d => {
  d.sections.forEach(s => {
    s.cards.forEach(card => {
      if (card.route) cardDomainMap.set(card.route, d.key)
    })
  })
})
