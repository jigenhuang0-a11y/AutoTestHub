<template>
  <el-container v-if="$route.path !== '/login'" style="height: 100vh">
    <!-- 侧边栏 -->
    <el-aside width="200px" style="background-color: #304156; position: relative; z-index: 10;">
      <div class="logo">
        <h2 style="color: white; text-align: center; padding: 20px 0">AI测试平台</h2>
      </div>
      <el-menu
        :default-active="$route.path"
        :default-openeds="alwaysOpenedMenus"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        router
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataLine /></el-icon>
          <span>数据看板</span>
        </el-menu-item>
        <el-sub-menu index="/case-group">
          <template #title>
            <el-icon><Collection /></el-icon>
            <span>用例管理</span>
          </template>
          <el-menu-item index="/testcases">
            <el-icon><Link /></el-icon>
            <span>接口自动化</span>
          </el-menu-item>
          <el-menu-item index="/web-testcases">
            <el-icon><Monitor /></el-icon>
            <span>Web 自动化</span>
          </el-menu-item>
          <el-menu-item index="/perf-testcases" class="dev-menu-item">
            <el-icon><Timer /></el-icon>
            <span>性能测试</span>
          </el-menu-item>
        </el-sub-menu>
        <el-menu-item index="/testsuites">
          <el-icon><Connection /></el-icon>
          <span>测试套件</span>
        </el-menu-item>
        <el-menu-item index="/history">
          <el-icon><VideoPlay /></el-icon>
          <span>执行历史</span>
        </el-menu-item>
        <el-menu-item index="/knowledge">
          <el-icon><Reading /></el-icon>
          <span>AI问答</span>
        </el-menu-item>
        <el-menu-item index="/data-factory">
          <el-icon><MagicStick /></el-icon>
          <span>数据工厂</span>
        </el-menu-item>
        <el-menu-item index="/agent-skills">
          <el-icon><SetUp /></el-icon>
          <span>技能库</span>
        </el-menu-item>
        <el-menu-item index="/quality-checker">
          <el-icon><Monitor /></el-icon>
          <span>质量数字人</span>
        </el-menu-item>
        <el-menu-item index="/ai-evaluator">
          <el-icon><Cpu /></el-icon>
          <span>AI 测评师</span>
        </el-menu-item>
        <el-menu-item index="/reports">
          <el-icon><DataAnalysis /></el-icon>
          <span>测试报告</span>
        </el-menu-item>
        <el-menu-item index="/model-manage" v-if="isAdmin">
          <el-icon><SetUp /></el-icon>
          <span>模型管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container style="flex: 1; min-height: 0;">
      <!-- 顶部导航 -->
      <el-header class="top-header">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-button
            circle
            text
            class="theme-toggle"
            :icon="isDark ? Sunny : Moon"
            @click="toggleTheme"
            :title="isDark ? '切换到亮色模式' : '切换到暗色模式'"
          />
          <el-dropdown @command="handleCommand" trigger="click">
            <div class="user-info">
              <div class="user-avatar">
                <svg viewBox="0 0 36 36" class="shiba-icon-nav">
                  <!-- 柴犬头像SVG -->
                  <defs>
                    <linearGradient id="shibaGradNav" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" style="stop-color:#f4a460;stop-opacity:1" />
                      <stop offset="100%" style="stop-color:#d2691e;stop-opacity:1" />
                    </linearGradient>
                  </defs>
                  <!-- 头部背景 -->
                  <circle cx="18" cy="18" r="16" fill="url(#shibaGradNav)" />
                  <!-- 耳朵 -->
                  <path d="M 7 10 L 10 3 L 14 8 Z" fill="#d2691e" />
                  <path d="M 29 10 L 26 3 L 22 8 Z" fill="#d2691e" />
                  <!-- 脸部 -->
                  <ellipse cx="18" cy="20" rx="10" ry="8" fill="#fff8dc" />
                  <!-- 眼睛 -->
                  <circle cx="13.5" cy="18" r="2" fill="#333" />
                  <circle cx="22.5" cy="18" r="2" fill="#333" />
                  <circle cx="14" cy="17.5" r="0.8" fill="white" />
                  <circle cx="23" cy="17.5" r="0.8" fill="white" />
                  <!-- 眼镜 -->
                  <circle cx="13.5" cy="18" r="3.5" fill="none" stroke="#333" stroke-width="1.2" />
                  <circle cx="22.5" cy="18" r="3.5" fill="none" stroke="#333" stroke-width="1.2" />
                  <line x1="17" y1="18" x2="19" y2="18" stroke="#333" stroke-width="1.2" />
                  <!-- 鼻子 -->
                  <ellipse cx="18" cy="22" rx="1.5" ry="1.2" fill="#333" />
                  <!-- 嘴巴 -->
                  <path d="M 15 24 Q 18 26 21 24" fill="none" stroke="#333" stroke-width="0.8" />
                  <!-- 程序员文字 -->
                  <text x="18" y="31" text-anchor="middle" fill="white" font-size="5" font-weight="bold">DEV</text>
                </svg>
              </div>
              <div class="user-detail">
                <span class="user-name">{{ authStore.user?.username || '用户' }}</span>
                <el-tag
                  size="small"
                  :type="roleTagType"
                  :effect="'dark'"
                  round
                >
                  {{ roleLabel }}
                </el-tag>
              </div>
              <el-icon class="dropdown-icon"><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu class="user-dropdown">
                <div class="dropdown-user-info">
                  <span class="dropdown-username">{{ authStore.user?.username }}</span>
                  <el-tag size="small" :type="roleTagType" effect="plain" round>{{ roleLabel }}</el-tag>
                </div>
                <el-dropdown-item divided command="logout" class="logout-item">
                  <el-icon><SwitchButton /></el-icon>
                  <span>退出登录</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 主内容区 -->
      <el-main class="main-content">
        <router-view v-slot="{ Component }">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </el-main>
    </el-container>
  </el-container>

  <router-view v-else />
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ArrowDown, User, Document, VideoPlay, DataLine, Connection, SwitchButton, Reading, MagicStick, SetUp, Monitor, Cpu, Collection, Link, Timer, DataAnalysis, Moon, Sunny } from '@element-plus/icons-vue'

const route = useRoute()
const authStore = useAuthStore()

const isDark = ref(false)

const applyTheme = (dark) => {
  const html = document.documentElement
  if (dark) {
    html.classList.add('dark')
  } else {
    html.classList.remove('dark')
  }
}

const toggleTheme = () => {
  isDark.value = !isDark.value
  applyTheme(isDark.value)
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

onMounted(() => {
  const saved = localStorage.getItem('theme')
  if (saved) {
    isDark.value = saved === 'dark'
  } else {
    isDark.value = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
  }
  applyTheme(isDark.value)
})

const currentTitle = computed(() => route.meta.title || '')
const isAdmin = computed(() => authStore.user?.role === 'admin')

// 用例管理子菜单始终展开
const alwaysOpenedMenus = ['/case-group']

const roleConfig = {
  admin:   { label: '管理员', tagType: 'danger' },
  tester:  { label: '测试工程师', tagType: '' },
  viewer:  { label: '查看者', tagType: 'info' },
}

const roleLabel = computed(() => {
  const r = authStore.user?.role
  return (r && roleConfig[r]?.label) || '未知'
})

const roleTagType = computed(() => {
  const r = authStore.user?.role
  return (r && roleConfig[r]?.tagType) || 'info'
})

const handleCommand = (command) => {
  if (command === 'logout') {
    authStore.logout()
  }
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --app-bg: #f5f7fa;
  --app-header-bg: #ffffff;
  --app-text: #303133;
  --app-text-secondary: #606266;
  --app-border: #e4e7ed;
  --app-hover: #f5f7fa;
  --el-bg-color: #ffffff;
  --el-bg-color-page: #f2f3f5;
}

html.dark {
  --app-bg: #0a0a0a;
  --app-header-bg: #1d1e1f;
  --app-text: #e0e0e0;
  --app-text-secondary: #a0a0a0;
  --app-border: #414243;
  --app-hover: #2c2c2c;
  color-scheme: dark;
}

html, body, #app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background-color: var(--app-bg);
  color: var(--app-text);
}

.el-aside .el-menu {
  border-right: none;
}

.theme-toggle {
  margin-right: 12px;
  font-size: 18px;
  color: var(--app-text-secondary);
}
</style>

<style scoped>
.top-header {
  background: var(--app-header-bg);
  border-bottom: 1px solid var(--app-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
  transition: background 0.3s ease, border-color 0.3s ease;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 16px;
  border-radius: 20px;
  background: transparent;
  cursor: pointer;
  transition: all 0.3s ease;
}

.user-info:hover {
  background: var(--app-hover);
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  overflow: hidden;
  background: linear-gradient(135deg, #f4a460 0%, #d2691e 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 6px rgba(244, 164, 96, 0.3);
}

.shiba-icon-nav {
  width: 100%;
  height: 100%;
}

.user-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--app-text);
}

.user-detail {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dropdown-user-info {
  padding: 12px 16px 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.dropdown-username {
  font-size: 14px;
  font-weight: 600;
  color: var(--app-text);
}

.dropdown-icon {
  font-size: 12px;
  color: var(--app-text-secondary);
  transition: transform 0.3s ease;
}

.user-info:hover .dropdown-icon {
  transform: rotate(180deg);
}

/* 下拉菜单样式 */
::deep(.user-dropdown) {
  padding: 8px 0;
  min-width: 160px;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  border: 1px solid var(--app-border);
}

::deep(.logout-item) {
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #f56c6c;
  font-weight: 500;
  font-size: 14px;
}

::deep(.logout-item:hover) {
  background: #fef0f0;
  color: #f56c6c;
}

::deep(.logout-item .el-icon) {
  font-size: 16px;
}

.main-content {
  padding: 0 !important;
  overflow-y: auto;
  overflow-x: hidden;
  flex: 1;
  min-height: 0;
  background-color: var(--app-bg);
}
</style>
