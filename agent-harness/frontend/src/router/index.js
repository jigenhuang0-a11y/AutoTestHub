import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import TaskMonitor from '@/views/TaskMonitor.vue'
import AuditDashboard from '@/views/AuditDashboard.vue'
import MCPGateway from '@/views/MCPGateway.vue'
import SandboxManage from '@/views/SandboxManage.vue'
import EnvironmentManage from '@/views/EnvironmentManage.vue'
import TenantManage from '@/views/TenantManage.vue'
import TraceLog from '@/views/TraceLog.vue'
import SystemSettings from '@/views/SystemSettings.vue'
import TeamModelSettings from '@/views/TeamModelSettings.vue'
import Login from '@/views/Login.vue'
import Workbench from '@/views/Workbench.vue'
import KnowledgeChat from '@/views/KnowledgeChat.vue'
import TestCaseList from '@/views/TestCaseList.vue'
import WebTestCaseList from '@/views/WebTestCaseList.vue'
import PerfTestCaseList from '@/views/PerfTestCaseList.vue'
import TestSuiteList from '@/views/TestSuiteList.vue'
import ExecutionHistory from '@/views/ExecutionHistory.vue'
import ReportView from '@/views/ReportView.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false, title: '登录' },
  },
  // 工作台首页
  {
    path: '/',
    name: 'Home',
    redirect: '/workbench',
  },
  {
    path: '/workbench',
    name: 'Workbench',
    component: Workbench,
    meta: { requiresAuth: true, title: '工作台', fullscreen: true },
  },

  // ===== AI 核心能力 =====
  {
    path: '/settings',
    name: 'SystemSettings',
    component: SystemSettings,
    meta: { requiresAuth: true, title: '配置中心', group: 'base', adminOnly: true },
  },
  {
    path: '/team-model-settings',
    name: 'TeamModelSettings',
    component: TeamModelSettings,
    meta: { requiresAuth: true, title: '模型配置', group: 'base', adminOnly: true },
  },
  {
    path: '/knowledge',
    redirect: '/knowledge/chat',
  },
  {
    path: '/knowledge/chat',
    name: 'KnowledgeChat',
    component: KnowledgeChat,
    meta: { requiresAuth: true, title: '测试知识库', group: 'test' },
  },
  {
    path: '/knowledge/:id',
    name: 'KnowledgeChatDetail',
    component: KnowledgeChat,
    meta: { requiresAuth: true, title: '测试知识库', group: 'test' },
  },
  {
    path: '/eval-center',
    name: 'EvalCenter',
    component: () => import('@/views/EvalCenter.vue'),
    meta: { requiresAuth: true, title: '全链路评测中心', group: 'test' },
  },
  {
    path: '/quality-checker',
    name: 'QualityChecker',
    component: () => import('@/views/QualityChecker.vue'),
    meta: { requiresAuth: true, title: '需求评审师', group: 'test' },
  },
  {
    path: '/data-factory',
    name: 'DataFactory',
    component: () => import('@/views/DataFactory.vue'),
    meta: { requiresAuth: true, title: '数据工厂', group: 'test' },
  },
  {
    path: '/monitor',
    name: 'TaskMonitor',
    component: TaskMonitor,
    meta: { requiresAuth: true, title: '任务监控', group: 'base' },
  },
  {
    path: '/audit',
    name: 'AuditDashboard',
    component: AuditDashboard,
    meta: { requiresAuth: true, title: '审计大屏', group: 'base' },
  },
  {
    path: '/trace',
    name: 'TraceLog',
    component: TraceLog,
    meta: { requiresAuth: true, title: '链路追踪', group: 'base' },
  },

  // ===== AI 测试平台 =====
  {
    path: '/testcases/ai-generate',
    name: 'AIGenerate',
    component: () => import('@/views/AIGenerate.vue'),
    meta: { requiresAuth: true, title: 'AI 用例生成', group: 'test' },
  },
  {
    path: '/testcases',
    name: 'TestCaseList',
    component: TestCaseList,
    meta: { requiresAuth: true, title: '接口测试', group: 'test' },
  },
  {
    path: '/web-testcases',
    name: 'WebTestCaseList',
    component: WebTestCaseList,
    meta: { requiresAuth: true, title: 'UI 自动化', group: 'test' },
  },
  {
    path: '/perf-testcases',
    name: 'PerfTestCaseList',
    component: PerfTestCaseList,
    meta: { requiresAuth: true, title: '性能测试', group: 'test' },
  },
  {
    path: '/testsuites',
    name: 'TestSuiteList',
    component: TestSuiteList,
    meta: { requiresAuth: true, title: '测试套件', group: 'test' },
  },
  {
    path: '/history',
    name: 'ExecutionHistory',
    component: ExecutionHistory,
    meta: { requiresAuth: true, title: '执行历史', group: 'test' },
  },
  {
    path: '/executions/:id',
    name: 'ExecutionDetail',
    component: () => import('@/views/ExecutionDetail.vue'),
    meta: { requiresAuth: true, title: '执行详情', group: 'test' },
  },
  {
    path: '/web-execution/:id',
    name: 'WebExecutionDetail',
    component: () => import('@/views/WebExecutionDetail.vue'),
    meta: { requiresAuth: true, title: 'Web 执行详情', group: 'test' },
  },
  {
    path: '/perf-execution/:id',
    name: 'PerfExecutionDetail',
    component: () => import('@/views/PerfExecutionDetail.vue'),
    meta: { requiresAuth: true, title: '性能执行详情', group: 'test' },
  },
  {
    path: '/reports',
    name: 'ReportView',
    component: ReportView,
    meta: { requiresAuth: true, title: '测试报告', group: 'test' },
  },

  // ===== 系统管理 (admin) =====
  {
    path: '/mcp-gateway',
    name: 'MCPGateway',
    component: MCPGateway,
    meta: { requiresAuth: true, title: 'MCP 工具网关', group: 'admin', adminOnly: true },
  },
  {
    path: '/sandbox',
    name: 'SandboxManage',
    component: SandboxManage,
    meta: { requiresAuth: true, title: '沙箱管控', group: 'admin', adminOnly: true },
  },
  {
    path: '/env',
    name: 'EnvironmentManage',
    component: EnvironmentManage,
    meta: { requiresAuth: true, title: '环境管理', group: 'admin', adminOnly: true },
  },
  {
    path: '/agent-orchestrator',
    name: 'AgentOrchestrator',
    component: () => import('@/views/AgentOrchestrator.vue'),
    meta: { requiresAuth: true, title: 'Agent 编排中心', group: 'base' },
  },
  {
    path: '/tenants',
    name: 'TenantManage',
    component: TenantManage,
    meta: { requiresAuth: true, title: '业务接入', group: 'admin', adminOnly: true },
  },

  // 兼容旧路径
  {
    path: '/dashboard',
    redirect: '/workbench',
  },
  {
    path: '/ai-evaluator',
    redirect: '/eval-center',
  },
  {
    path: '/agent-harness/:pathMatch(.*)*',
    redirect: (to) => {
      const map = {
        monitor: '/monitor',
        'mcp-gateway': '/mcp-gateway',
        sandbox: '/sandbox',
        tenants: '/tenants',
        trace: '/trace',
        audit: '/audit',
        settings: '/settings',
        'team-model-settings': '/team-model-settings',
        'quality-checker': '/quality-checker',
        'knowledge/chat': '/knowledge/chat',
      }
      const match = Array.isArray(to.params.pathMatch) ? to.params.pathMatch[0] : to.params.pathMatch
      return map[match] || '/workbench'
    },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 导航守卫
// 注意：在 Pinia store 中 access_token / user 已从 localStorage 恢复。
// 若已登录但 user 缺失（例如旧数据未持久化），访问 adminOnly 路由前会重新拉取 profile。
router.beforeEach(async (to, from) => {
  const authStore = useAuthStore()

  // 1. 已登录用户不应再看到登录页
  if (to.path === '/login' && authStore.isAuthenticated) {
    return { path: '/workbench', replace: true }
  }

  // 2. 需要登录但未登录 -> 引导登录
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // 3. 已登录但 user 信息缺失：在进入 adminOnly 页面前拉取 profile
  // 使用 to.meta 上的标记避免同一次导航链中重复拉取
  if (authStore.isAuthenticated && !authStore.user && to.meta.adminOnly && !to.meta._profileFetched) {
    to.meta._profileFetched = true
    try {
      await authStore.fetchProfile()
    } catch (err) {
      console.error('fetchProfile failed:', err)
    }
  }

  // 4. adminOnly 权限判定
  if (to.meta.adminOnly && authStore.user?.role !== 'admin') {
    // 如果 user 仍未获取到，为避免误拦截，给出明确提示
    const tip = authStore.user
      ? '演示账号仅可查看效果，无权访问此页面'
      : '用户身份信息未加载，无法访问此页面'
    ElMessage.warning(tip)
    return { path: '/workbench', replace: true }
  }
})

export default router
