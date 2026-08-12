import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    name: 'Home',
    redirect: '/workbench',
  },
  {
    path: '/workbench',
    name: 'Workbench',
    component: () => import('@/views/Workbench.vue'),
    meta: { requiresAuth: true, title: '工作台' },
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { requiresAuth: true, title: '数据看板' },
  },
  {
    path: '/testcases',
    name: 'TestCaseList',
    component: () => import('@/views/TestCaseList.vue'),
    meta: { requiresAuth: true, title: '接口自动化' },
  },
  {
    path: '/testcases/ai-generate',
    name: 'AIGenerate',
    component: () => import('@/views/AIGenerate.vue'),
    meta: { requiresAuth: true, title: 'AI 生成用例' },
  },
  {
    path: '/web-testcases',
    name: 'WebTestCaseList',
    component: () => import('@/views/WebTestCaseList.vue'),
    meta: { requiresAuth: true, title: 'Web 自动化' },
  },
  {
    path: '/perf-testcases',
    name: 'PerfTestCaseList',
    component: () => import('@/views/PerfTestCaseList.vue'),
    meta: { requiresAuth: true, title: '性能测试' },
  },
  {
    path: '/perf-execution/:id',
    name: 'PerfExecutionDetail',
    component: () => import('@/views/PerfExecutionDetail.vue'),
    meta: { requiresAuth: true, title: '性能执行详情' },
  },
  {
    path: '/history',
    name: 'ExecutionHistory',
    component: () => import('@/views/ExecutionHistory.vue'),
    meta: { requiresAuth: true, title: '执行历史' },
  },
  {
    path: '/history/:id',
    name: 'ExecutionDetail',
    component: () => import('@/views/ExecutionDetail.vue'),
    meta: { requiresAuth: true, title: '执行详情' },
  },
  {
    path: '/web-execution/:id',
    name: 'WebExecutionDetail',
    component: () => import('@/views/WebExecutionDetail.vue'),
    meta: { requiresAuth: true, title: 'Web 执行详情' },
  },
  {
    path: '/reports',
    name: 'ReportList',
    component: () => import('@/views/ReportView.vue'),
    meta: { requiresAuth: true, title: '测试报告' },
  },
  {
    path: '/testsuites',
    name: 'TestSuiteList',
    component: () => import('@/views/TestSuiteList.vue'),
    meta: { requiresAuth: true, title: '测试套件管理' },
  },
  {
    path: '/knowledge',
    name: 'KnowledgeBaseList',
    redirect: '/knowledge/chat',
  },
  {
    path: '/knowledge/chat',
    name: 'KnowledgeChatSelect',
    component: () => import('@/views/KnowledgeChat.vue'),
    meta: { requiresAuth: true, title: 'AI问答' },
  },
  {
    path: '/knowledge/:id',
    name: 'KnowledgeChat',
    component: () => import('@/views/KnowledgeChat.vue'),
    meta: { requiresAuth: true, title: 'AI问答' },
  },
  {
    path: '/data-factory',
    name: 'DataFactory',
    component: () => import('@/views/DataFactory.vue'),
    meta: { requiresAuth: true, title: '数据工厂' },
  },
  {
    path: '/agent-skills',
    name: 'AgentSkills',
    component: () => import('@/views/AgentSkills.vue'),
    meta: { requiresAuth: true, title: '技能库' },
  },
  {
    path: '/quality-checker',
    name: 'QualityChecker',
    component: () => import('@/views/QualityChecker.vue'),
    meta: { requiresAuth: true, title: '需求评审师' },
  },
  {
    path: '/ai-evaluator',
    name: 'AIEvaluator',
    component: () => import('@/views/AIEvaluator.vue'),
    meta: { requiresAuth: true, title: 'AI 测评师' },
  },
  {
    path: '/model-manage',
    name: 'ModelManage',
    component: () => import('@/views/ModelManage.vue'),
    meta: { requiresAuth: true, title: '模型管理', adminOnly: true },
  },
  {
    path: '/self-healing',
    name: 'SelfHealingMonitor',
    component: () => import('@/views/SelfHealingMonitor.vue'),
    meta: { requiresAuth: true, title: '自主纠错监控' },
  },

]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫
let profileFetched = false
router.beforeEach(async (to, from) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return '/login'
  }
  if (to.path === '/login' && authStore.isAuthenticated) {
    return '/'
  }
  // 有 token 但没有用户信息（页面刷新场景）→ 自动获取 profile
  if (authStore.isAuthenticated && !authStore.user && !profileFetched) {
    profileFetched = true
    try { await authStore.fetchProfile() } catch { /* 失败不阻断导航 */ }
  }
})

export default router
