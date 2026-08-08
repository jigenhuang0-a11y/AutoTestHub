import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import TaskMonitor from '@/views/TaskMonitor.vue'
import AuditDashboard from '@/views/AuditDashboard.vue'
import MCPGateway from '@/views/MCPGateway.vue'
import SandboxManage from '@/views/SandboxManage.vue'
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
    meta: { requiresAuth: true, title: '配置中心', group: 'ai-core', adminOnly: true },
  },
  {
    path: '/team-model-settings',
    name: 'TeamModelSettings',
    component: TeamModelSettings,
    meta: { requiresAuth: true, title: '模型配置', group: 'admin', adminOnly: true },
  },
  {
    path: '/knowledge',
    redirect: '/knowledge/chat',
  },
  {
    path: '/knowledge/chat',
    name: 'KnowledgeChat',
    component: () => import('@/views/KnowledgeChat.vue'),
    meta: { requiresAuth: true, title: '知识中枢', group: 'ai-core' },
  },
  {
    path: '/eval-center',
    name: 'EvalCenter',
    component: () => import('@/views/EvalCenter.vue'),
    meta: { requiresAuth: true, title: '全链路评测中心', group: 'ai-core' },
  },
  {
    path: '/quality-checker',
    name: 'QualityChecker',
    component: () => import('@/views/QualityChecker.vue'),
    meta: { requiresAuth: true, title: '质量数字人', group: 'ai-core' },
  },
  {
    path: '/data-factory',
    name: 'DataFactory',
    component: () => import('@/views/DataFactory.vue'),
    meta: { requiresAuth: true, title: '数据工厂', group: 'ai-core' },
  },

  // ===== 测试工具 =====
  {
    path: '/testcases/ai-generate',
    name: 'AIGenerate',
    component: () => import('@/views/AIGenerate.vue'),
    meta: { requiresAuth: true, title: 'AI 用例生成', group: 'testing' },
  },
  {
    path: '/testcases',
    name: 'TestCaseList',
    component: () => import('@/views/TestCaseList.vue'),
    meta: { requiresAuth: true, title: '接口测试', group: 'testing' },
  },
  {
    path: '/web-testcases',
    name: 'WebTestCaseList',
    component: () => import('@/views/WebTestCaseList.vue'),
    meta: { requiresAuth: true, title: 'UI 自动化', group: 'testing' },
  },
  {
    path: '/perf-testcases',
    name: 'PerfTestCaseList',
    component: () => import('@/views/PerfTestCaseList.vue'),
    meta: { requiresAuth: true, title: '性能测试', group: 'testing' },
  },
  {
    path: '/testsuites',
    name: 'TestSuiteList',
    component: () => import('@/views/TestSuiteList.vue'),
    meta: { requiresAuth: true, title: '测试套件', group: 'testing' },
  },
  {
    path: '/history',
    name: 'ExecutionHistory',
    component: () => import('@/views/ExecutionHistory.vue'),
    meta: { requiresAuth: true, title: '执行历史', group: 'testing' },
  },
  {
    path: '/reports',
    name: 'ReportView',
    component: () => import('@/views/ReportView.vue'),
    meta: { requiresAuth: true, title: '测试报告', group: 'testing' },
  },

  // ===== 运维底座 =====
  {
    path: '/monitor',
    name: 'TaskMonitor',
    component: TaskMonitor,
    meta: { requiresAuth: true, title: '任务监控', group: 'ops' },
  },
  {
    path: '/audit',
    name: 'AuditDashboard',
    component: AuditDashboard,
    meta: { requiresAuth: true, title: '审计大屏', group: 'ops' },
  },
  {
    path: '/trace',
    name: 'TraceLog',
    component: TraceLog,
    meta: { requiresAuth: true, title: '链路追踪', group: 'ops' },
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
  // 访客（非 admin）禁止访问管理类路由
  if (to.meta.adminOnly && authStore.user?.role !== 'admin') {
    ElMessage.warning('演示账号仅可查看效果，无权访问此页面')
    return '/workbench'
  }
  if (to.path === '/login' && authStore.isAuthenticated) {
    return '/workbench'
  }
  if (authStore.isAuthenticated && !authStore.user && !profileFetched) {
    profileFetched = true
    try { await authStore.fetchProfile() } catch { /* 失败不阻断导航 */ }
  }
})

export default router
