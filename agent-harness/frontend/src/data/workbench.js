import {
  Setting, Cpu, Collection, DataAnalysis, ChatDotRound, MagicStick,
  Document, Connection, Monitor, Odometer, FolderAdd, Timer,
  DocumentChecked, TrendCharts, PieChart, Link, SetUp, Grid, Tools
} from '@element-plus/icons-vue'

export const categories = [
  {
    key: 'ai-core',
    title: 'AI 核心底座',
    cards: [
      { id: 'r1-1', title: 'AI底座配置', subtitle: '模型入、权限、配额', icon: Setting, route: '/settings', type: 'normal' },
      { id: 'r1-2', title: '模型配置', subtitle: '团队模型、参数调优', icon: Cpu, route: '/team-model-settings', type: 'normal' },
      { id: 'r1-3', title: '知识中枢', subtitle: 'RAG、检索、溯源', icon: Collection, route: '/knowledge/chat', type: 'normal' },
      { id: 'r1-4', title: '全链路评测中心', subtitle: '数据集、Judge、Trace', icon: DataAnalysis, route: '/eval-center', type: 'highlight' },
      { id: 'r1-5', title: '质量数字人', subtitle: '问答、报告、智能体', icon: ChatDotRound, route: '/quality-checker', type: 'normal' },
      { id: 'r1-6', title: '数据工厂', subtitle: 'AI生成用例、测试数据', icon: MagicStick, route: '/data-factory', type: 'normal' },
      { id: 'r1-7', title: '系统设置', subtitle: '配置中心、权限管理', icon: SetUp, route: '/settings', type: 'normal' }
    ]
  },
  {
    key: 'testing',
    title: '自动化测试工具链',
    cards: [
      { id: 'r2-1', title: '用例生成', subtitle: 'AI生成用例、测试数据', icon: Document, route: '/testcases/ai-generate', type: 'normal' },
      { id: 'r2-2', title: '接口测试', subtitle: '自动化、套件、报表', icon: Connection, route: '/testcases', type: 'focus' },
      { id: 'r2-3', title: 'UI自动化', subtitle: 'Web流程、回放', icon: Monitor, route: '/web-testcases', type: 'normal' },
      { id: 'r2-4', title: 'Web测试', subtitle: '接口、Web流程', icon: Link, route: '/web-testcases', type: 'normal' },
      { id: 'r2-5', title: '性能测试', subtitle: '压测、瓶颈、分析', icon: Odometer, route: '/perf-testcases', type: 'normal' },
      { id: 'r2-6', title: '测试套件', subtitle: '组合编排、批量执行', icon: FolderAdd, route: '/testsuites', type: 'normal' },
      { id: 'r2-7', title: '执行历史', subtitle: '运行记录、实时追踪', icon: Timer, route: '/history', type: 'normal' }
    ]
  },
  {
    key: 'ops',
    title: '运维观测底座',
    cards: [
      { id: 'r3-1', title: '测试报告', subtitle: '结果汇总、趋势分析', icon: DocumentChecked, route: '/reports', type: 'normal' },
      { id: 'r3-2', title: '任务监控', subtitle: 'Celery队列、状态看板', icon: TrendCharts, route: '/monitor', type: 'normal' },
      { id: 'r3-3', title: '审计大屏', subtitle: '操作日志、合规审计', icon: PieChart, route: '/audit', type: 'normal' },
      { id: 'r3-4', title: '链路追踪', subtitle: '分布式Trace、调用链', icon: Link, route: '/trace', type: 'normal' },
      { id: 'r3-5', title: 'MCP工具网关', subtitle: '工具注册、权限管控', icon: SetUp, route: '/mcp-gateway', type: 'normal' },
      { id: 'r3-6', title: '沙箱管控', subtitle: '隔离执行、资源配额', icon: Grid, route: '/sandbox', type: 'normal' },
      { id: 'r3-7', title: '环境管理', subtitle: '环境配置、部署管理', icon: Tools, route: '', type: 'normal' }
    ]
  }
]

export const allCards = categories.flatMap(c => c.cards)
export const categoryMap = Object.fromEntries(categories.map(c => [c.key, c]))
export const cardCategoryMap = new Map()
categories.forEach(c => {
  c.cards.forEach(card => cardCategoryMap.set(card.route, c.key))
})
