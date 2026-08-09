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
    component: () => import('@/views/KnowledgeChat.vue'),
    meta: { requiresAuth: true, title: '知识中枢', group: 'test' },
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
    meta: { requiresAuth: true, title: '质量数字人', group: 'test' },
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
    component: () => import('@/views/TestCaseList.vue'),
    meta: { requiresAuth: true, title: '接口测试', group: 'test' },
  },
  {
    path: '/web-testcases',
    name: 'WebTestCaseList',
    component: () => import('@/views/WebTestCaseList.vue'),
    meta: { requiresAuth: true, title: 'UI 自动化', group: 'test' },
  },
  {
    path: '/perf-testcases',
    name: 'PerfTestCaseList',
    component: () => import('@/views/PerfTestCaseList.vue'),
    meta: { requiresAuth: true, title: '性能测试', group: 'test' },
  },
  {
    path: '/testsuites',
    name: 'TestSuiteList',
    component: () => import('@/views/TestSuiteList.vue'),
    meta: { requiresAuth: true, title: '测试套件', group: 'test' },
  },
  {
    path: '/history',
    name: 'ExecutionHistory',
    component: () => import('@/views/ExecutionHistory.vue'),
    meta: { requiresAuth: true, title: '执行历史', group: 'test' },
  },
  {
    path: '/reports',
    name: 'ReportView',
    component: () => import('@/views/ReportView.vue'),
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

let profileFetched = false
router.beforeEach(async (to, from) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return '/login'
  }
  // 已登录但 user 尚未加载（如刷新后从 token 恢复），先拉取 profile 再判定权限
  if (authStore.isAuthenticated && !authStore.user && !profileFetched) {
    profileFetched = true
    try { await authStore.fetchProfile() } catch { /* 失败不阻断导航 */ }
  }
  // 访客（非 admin）禁止访问管理类路由
  if (to.meta.adminOnly && authStore.user?.role !== 'admin') {
    ElMessage.warning('演示账号仅可查看效果，无权访问此页面')
    return '/workbench'
  }
  if (to.path === '/login' && authStore.isAuthenticated) {
    return '/workbench'
  }
})

export default router
