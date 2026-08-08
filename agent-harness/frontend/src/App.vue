<template>
  <!-- 工作台全屏模式：无侧边栏 -->
  <template v-if="isWorkspace">
    <router-view />
  </template>

  <!-- 登录页：纯展示 -->
  <template v-else-if="isLoginPage">
    <router-view />
  </template>

  <!-- 其他页面：带分组侧边栏 -->
  <template v-else>
    <div class="app-layout">
      <!-- 侧边栏 -->
      <aside class="sidebar">
        <div class="logo" @click="$router.push('/workbench')" title="回到工作台">
          <div class="logo-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="logo-svg">
              <circle cx="12" cy="12" r="3"/>
              <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
            </svg>
          </div>
          <h2 class="logo-title">AI 效能中台</h2>
          <el-icon class="logo-home" :size="16"><HomeFilled /></el-icon>
        </div>

        <nav class="sidebar-nav">
          <!-- 工作台快捷入口 -->
          <router-link to="/workbench" class="nav-item" :class="{ active: isActive('/workbench') }">
            <el-icon :size="18"><HomeFilled /></el-icon>
            <span>工作台</span>
          </router-link>

          <div class="nav-divider"></div>

          <!-- 分组导航：默认展开当前路由所在分组 -->
          <div v-for="(group, index) in visibleGroups" :key="group.key" class="nav-group">
            <div
              class="nav-group-title"
              :class="{ active: currentGroup === group.key }"
              @click="toggleGroup(group.key)"
            >
              {{ group.title }}
              <el-icon class="group-arrow" :class="{ 'is-expanded': isExpanded(group.key) }">
                <ArrowDown />
              </el-icon>
            </div>
            <div v-show="isExpanded(group.key)" class="nav-group-items">
              <router-link
                v-for="item in group.items"
                :key="item.to"
                :to="item.to"
                class="nav-item"
                :class="{ active: isActive(item.to) }"
              >
                <el-icon :size="18"><component :is="iconMap[item.icon]" /></el-icon>
                <span>{{ item.label }}</span>
              </router-link>
            </div>
            <div v-if="index < visibleGroups.length - 1" class="nav-divider"></div>
          </div>
        </nav>

        <div class="sidebar-footer">
          <div class="user-card">
            <el-avatar :size="32" class="user-avatar">{{ userInitial }}</el-avatar>
            <div class="user-info">
              <span class="user-name">{{ authStore.user?.username || '用户' }}</span>
              <span class="user-role">{{ roleLabel }}</span>
            </div>
            <el-icon class="logout-icon" @click="handleLogout"><SwitchButton /></el-icon>
          </div>
        </div>
      </aside>

      <!-- 主内容区 -->
      <div class="main-layout">
        <header class="top-header">
          <div class="header-left">
            <h3 class="page-title">{{ route.meta.title || '' }}</h3>
          </div>
          <div class="header-right">
            <el-tag type="info" effect="plain" class="env-tag">AI 效能中台</el-tag>
          </div>
        </header>
        <main class="main-content">
          <router-view />
        </main>
      </div>
    </div>
  </template>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  HomeFilled, Setting, Collection, DataAnalysis, User, Coin,
  MagicStick, Connection, Monitor, Lightning, Briefcase, Timer, TrendCharts,
  Odometer, PieChart, Link,
  Platform, Box, UserFilled, SetUp, SwitchButton, ArrowDown
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const isAdmin = computed(() => authStore.user?.role === 'admin')
const isWorkspace = computed(() => route.meta.fullscreen === true)
const isLoginPage = computed(() => route.path === '/login')

const iconMap = {
  HomeFilled, Setting, Collection, DataAnalysis, User, Coin,
  MagicStick, Connection, Monitor, Lightning, Briefcase, Timer, TrendCharts,
  Odometer, PieChart, Link,
  Platform, Box, UserFilled, SetUp, SwitchButton, ArrowDown
}

const menuGroups = [
  {
    key: 'ai-core',
    title: 'AI 核心能力',
    items: [
      { to: '/settings', icon: 'Setting', label: '配置中心', adminOnly: true },
      { to: '/knowledge/chat', icon: 'Collection', label: '知识中枢' },
      { to: '/eval-center', icon: 'DataAnalysis', label: '全链路评测中心' },
      { to: '/quality-checker', icon: 'User', label: '质量数字人' },
      { to: '/data-factory', icon: 'Coin', label: '数据工厂' }
    ]
  },
  {
    key: 'testing',
    title: '测试工具',
    items: [
      { to: '/testcases/ai-generate', icon: 'MagicStick', label: 'AI 用例生成' },
      { to: '/testcases', icon: 'Connection', label: '接口测试' },
      { to: '/web-testcases', icon: 'Monitor', label: 'UI 自动化' },
      { to: '/perf-testcases', icon: 'Lightning', label: '性能测试' },
      { to: '/testsuites', icon: 'Briefcase', label: '测试套件' },
      { to: '/history', icon: 'Timer', label: '执行历史' },
      { to: '/reports', icon: 'TrendCharts', label: '测试报告' }
    ]
  },
  {
    key: 'ops',
    title: '运维底座',
    items: [
      { to: '/monitor', icon: 'Odometer', label: '任务监控' },
      { to: '/audit', icon: 'PieChart', label: '审计大屏' },
      { to: '/trace', icon: 'Link', label: '链路追踪' }
    ]
  },
  {
    key: 'admin',
    title: '系统管理',
    adminOnly: true,
    items: [
      { to: '/mcp-gateway', icon: 'Platform', label: 'MCP 网关' },
      { to: '/sandbox', icon: 'Box', label: '沙箱管控' },
      { to: '/tenants', icon: 'UserFilled', label: '业务接入' },
      { to: '/team-model-settings', icon: 'SetUp', label: '模型配置' }
    ]
  }
]

const isHubRoute = computed(() => route.path === '/workbench')

const visibleGroups = computed(() => {
  let groups = menuGroups
    .map(g => ({ ...g, items: g.items.filter(i => !i.adminOnly || isAdmin.value) }))
    .filter(g => !g.adminOnly || isAdmin.value)
    .filter(g => g.items.length > 0)

  // 工作台/分类入口页显示全部分组；具体功能页只显示当前所属分组
  if (!isHubRoute.value && currentGroup.value) {
    groups = groups.filter(g => g.key === currentGroup.value)
  }
  return groups
})

const currentGroup = computed(() => route.params?.group || route.meta?.group || null)
const expandedGroups = ref(new Set())

watch(currentGroup, (group) => {
  if (group) expandedGroups.value.add(group)
}, { immediate: true })

const isExpanded = (key) => expandedGroups.value.has(key)
const toggleGroup = (key) => {
  if (expandedGroups.value.has(key)) {
    expandedGroups.value.delete(key)
  } else {
    expandedGroups.value.add(key)
  }
}

const isActive = (to) => {
  if (to === '/workbench') return route.path === '/workbench'
  if (to === '/testcases') return route.path === '/testcases'
  return route.path.startsWith(to)
}

const roleConfig = {
  admin: { label: '管理员' },
  tester: { label: '测试工程师' },
  viewer: { label: '查看者' },
}

const roleLabel = computed(() => {
  const r = authStore.user?.role
  return (r && roleConfig[r]?.label) || '未知'
})

const userInitial = computed(() => {
  return (authStore.user?.username?.[0] || 'U').toUpperCase()
})

const handleLogout = () => {
  authStore.logout()
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}
</style>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
}

.main-layout {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #1a2d45;
}

/* ====== 侧边栏 ====== */
.sidebar {
  width: 220px;
  flex-shrink: 0;
  background: #0f1923;
  border-right: 1px solid rgba(64, 158, 255, 0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.logo {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.1);
  cursor: pointer;
  transition: background 0.2s;
}

.logo:hover {
  background: rgba(64, 158, 255, 0.05);
}

.logo-icon {
  color: #409eff;
  display: flex;
  align-items: center;
}

.logo-svg {
  width: 24px;
  height: 24px;
}

.logo-title {
  color: #f1f5f9;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.5px;
  flex: 1;
}

.logo-home {
  margin-left: auto;
  color: #7aa8d8;
  opacity: 0.6;
  transition: opacity 0.2s, color 0.2s;
}

.logo:hover .logo-home {
  opacity: 1;
  color: #b8d8f8;
}

/* 导航区 */
.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.nav-group-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 12px 6px;
  font-size: 11px;
  font-weight: 600;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  cursor: pointer;
  user-select: none;
  transition: color 0.2s;
}

.nav-group-title:hover {
  color: #94a3b8;
}

.nav-group-title.active {
  color: #7dd3fc;
}

.group-arrow {
  transition: transform 0.2s;
  color: #475569;
}

.group-arrow.is-expanded {
  transform: rotate(180deg);
}

.nav-group-items {
  overflow: hidden;
}

.nav-divider {
  height: 1px;
  margin: 6px 12px;
  background: rgba(255, 255, 255, 0.05);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 8px;
  color: #94a3b8;
  font-size: 13px;
  text-decoration: none;
  transition: all 0.2s;
  margin-bottom: 2px;
  cursor: pointer;
}

.nav-item:hover {
  background: rgba(64, 158, 255, 0.08);
  color: #cbd5e1;
}

.nav-item.active {
  background: rgba(64, 158, 255, 0.15);
  color: #7dd3fc;
  font-weight: 500;
}

.nav-item .el-icon {
  flex-shrink: 0;
}

.nav-item span {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 侧边栏底部 */
.sidebar-footer {
  padding: 8px;
  border-top: 1px solid rgba(64, 158, 255, 0.1);
}

.user-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(15, 25, 35, 0.8);
  border: 1px solid rgba(64, 158, 255, 0.1);
}

.user-avatar {
  background: #409eff;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
}

.user-info {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.user-name {
  color: #e2e8f0;
  font-size: 13px;
  font-weight: 500;
}

.user-role {
  color: #64748b;
  font-size: 11px;
}

.logout-icon {
  color: #64748b;
  cursor: pointer;
  font-size: 16px;
  transition: color 0.2s;
}

.logout-icon:hover {
  color: #f87171;
}

/* ====== 主区域 ====== */
.top-header {
  height: 56px;
  flex-shrink: 0;
  background: #162032;
  border-bottom: 1px solid rgba(64, 158, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.page-title {
  color: #f8fafc;
  font-size: 15px;
  font-weight: 600;
}

.env-tag {
  background: rgba(64, 158, 255, 0.1) !important;
  color: #7dd3fc !important;
  border-color: rgba(64, 158, 255, 0.2) !important;
  font-size: 12px;
}

.main-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  background: #1a2d45;
}
</style>
