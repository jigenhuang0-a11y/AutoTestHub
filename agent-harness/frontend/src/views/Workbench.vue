<template>
  <div class="workbench">
    <!-- 多层背景 -->
    <div class="bg-base"></div>
    <div class="bg-grid"></div>
    <div class="bg-vignette"></div>

    <!-- 顶部栏 -->
    <header class="wb-header">
      <div class="header-brand" @click="router.push('/workbench')">
        <div class="brand-logo-ring">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="12" cy="12" r="3"/>
            <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
          </svg>
        </div>
        <div class="brand-text-group">
          <span class="brand-title-sm">Agent Harness</span>
        </div>
      </div>

      <div class="wb-nav-pills">
        <div
          v-for="item in domainTabs"
          :key="item.key"
          class="nav-pill"
          :class="{ active: activeDomain === item.key }"
          @click="switchDomain(item.key)"
        >
          <el-icon :size="14"><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
          <el-tag v-if="item.comingSoon" size="small" type="info" effect="plain" round class="domain-tag">规划中</el-tag>
        </div>
      </div>

      <div class="header-actions">
        <div class="action-icon"><el-icon :size="18"><ChatDotRound /></el-icon></div>
        <div class="action-icon"><el-icon :size="18"><Bell /></el-icon></div>
        <div class="action-icon"><el-icon :size="18"><Tools /></el-icon></div>
        <el-dropdown trigger="click" @command="handleUserCommand">
          <div class="user-dropdown-trigger">
            <el-avatar :size="32" class="user-avatar">{{ userInitial }}</el-avatar>
            <el-icon :size="14" class="user-dropdown-arrow"><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>
                <div class="user-dropdown-info">
                  <span class="user-dropdown-name">{{ authStore.user?.username || '用户' }}</span>
                  <span class="user-dropdown-role">{{ authStore.user?.role || '管理员' }}</span>
                </div>
              </el-dropdown-item>
              <el-dropdown-item divided command="logout">
                <el-icon :size="14"><SwitchButton /></el-icon>
                <span>退出登录</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <!-- 主内容区 -->
    <div class="wb-body">
      <!-- 顶部标题区 -->
      <div class="hero-section">
        <div class="hero-icon-wrap">
          <div class="hero-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M12 2L2 7l10 5 10-5-10-5z"/>
              <path d="M2 17l10 5 10-5"/>
              <path d="M2 12l10 5 10-5"/>
            </svg>
          </div>
        </div>
        <div class="hero-text">
          <h1 class="hero-title">{{ currentDomain.label }}</h1>
          <p class="hero-subtitle">{{ currentDomain.desc }}</p>
        </div>
      </div>

      <!-- 分类/卡片区域 -->
      <template v-for="section in displaySections" :key="section.key">
        <div class="row-label">{{ section.title }}</div>
        <div class="card-grid">
          <div
            v-for="card in section.cards"
            :key="card.id"
            class="wb-card"
            :class="['card-' + card.type, { disabled: card.disabled }]"
            @click="navigateCard(card)"
            @mousemove="!card.disabled && handleMouseMove($event)"
            @mouseleave="!card.disabled && handleMouseLeave($event)"
          >
            <div class="card-base"></div>
            <div class="card-shine"></div>
            <div class="card-spotlight"></div>
            <div class="card-border"></div>
            <div class="card-top-line"></div>
            <div class="card-inner">
              <div class="card-icon-box">
                <component :is="card.icon" :size="18" />
              </div>
              <div class="card-text">
                <h3 class="card-title">{{ card.title }}</h3>
                <p class="card-subtitle">{{ card.subtitle }}</p>
              </div>
              <div v-if="card.disabled" class="card-lock">规划中</div>
            </div>
          </div>
        </div>
      </template>

      <!-- 底部通栏 -->
      <div class="slogan-bar">
        <span>统一底座</span>
        <span class="slogan-dot">·</span>
        <span>评测闭环</span>
        <span class="slogan-dot">·</span>
        <span>测试协同</span>
        <span class="slogan-dot">·</span>
        <span>可观测治理</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  Setting, Cpu, Collection, DataAnalysis, ChatDotRound, MagicStick,
  Document, Connection, Monitor, Odometer, FolderAdd, Timer,
  DocumentChecked, TrendCharts, PieChart, Link, SetUp, Grid,
  ChatDotRound as MsgIcon, Bell, Tools, ArrowDown, SwitchButton,
  Cpu as DomainBase, DataLine as DomainTest, Tickets, Calendar
} from '@element-plus/icons-vue'
import { domains, domainMap } from '@/data/workbench'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const userInitial = computed(() => {
  return (authStore.user?.username?.[0] || 'U').toUpperCase()
})

// 当前选中的产品域，默认 AI 效能中台
const activeDomain = ref('base')
const currentDomain = computed(() => domainMap[activeDomain.value] || domains[0])
const displaySections = computed(() => currentDomain.value.sections)

const navigateCard = (card) => {
  if (card.disabled) return
  if (card.route) router.push(card.route)
}

const handleUserCommand = (command) => {
  if (command === 'logout') {
    authStore.logout()
  }
}

let rafId = null
let latestX = 0
let latestY = 0
let activeTarget = null

const handleMouseMove = (e) => {
  const target = e.currentTarget
  const rect = target.getBoundingClientRect()
  latestX = e.clientX - rect.left
  latestY = e.clientY - rect.top
  activeTarget = target

  if (!rafId) {
    rafId = requestAnimationFrame(() => {
      if (activeTarget) {
        activeTarget.style.setProperty('--mouse-x', `${latestX}px`)
        activeTarget.style.setProperty('--mouse-y', `${latestY}px`)
      }
      rafId = null
    })
  }
}

const handleMouseLeave = (e) => {
  if (rafId) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
  activeTarget = null
  e.currentTarget.style.removeProperty('--mouse-x')
  e.currentTarget.style.removeProperty('--mouse-y')
}

// 产品域顶部导航
const domainTabs = computed(() => [
  { key: 'base', label: 'AI 效能中台', icon: DomainBase },
  { key: 'test', label: 'AI 测试平台', icon: DomainTest },
  { key: 'case', label: '用例平台', icon: Tickets, comingSoon: true },
  { key: 'schedule', label: '团队排期', icon: Calendar, comingSoon: true },
])

const switchDomain = (key) => {
  activeDomain.value = key
}
</script>

<style scoped>
.workbench {
  position: relative;
  height: 100%;
  background: #112544;
  overflow-y: auto;
  overflow-x: hidden;
}

/* ====== 多层背景 ====== */
.bg-base {
  position: fixed;
  inset: 0;
  z-index: 0;
  background:
    radial-gradient(ellipse 120% 60% at 50% 0%, rgba(30, 80, 140, 0.5) 0%, transparent 55%),
    radial-gradient(ellipse 70% 40% at 50% 100%, rgba(25, 65, 115, 0.25) 0%, transparent 50%),
    #112544;
}

.bg-grid {
  position: fixed;
  inset: 0;
  z-index: 0;
  background-image:
    linear-gradient(rgba(80, 150, 230, 0.1) 1px, transparent 1px),
    linear-gradient(90deg, rgba(80, 150, 230, 0.1) 1px, transparent 1px);
  background-size: 28px 28px;
  pointer-events: none;
}

.bg-vignette {
  position: fixed;
  inset: 0;
  z-index: 0;
  background: radial-gradient(ellipse 85% 85% at 50% 50%, transparent 45%, rgba(8, 18, 35, 0.4) 100%);
  pointer-events: none;
}

/* ====== 顶部栏 ====== */
.wb-header {
  position: relative;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 28px;
  border-bottom: 1px solid rgba(80, 150, 230, 0.12);
  background: rgba(17, 37, 68, 0.45);
  backdrop-filter: blur(16px);
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}
.header-brand:hover { opacity: 0.85; }

.brand-logo-ring {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: 1.5px solid rgba(90, 160, 240, 0.35);
  background: rgba(90, 160, 240, 0.08);
  color: #5aa0e8;
  flex-shrink: 0;
}
.brand-logo-ring svg { width: 16px; height: 16px; }

.brand-text-group {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}
.brand-title-sm {
  font-size: 15px;
  font-weight: 700;
  color: #b0c8e8;
  letter-spacing: 0.3px;
}

/* 中间导航 - 胶囊容器 */
.wb-nav-pills {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 3px;
  padding: 3px;
  border-radius: 22px;
  background: rgba(12, 20, 38, 0.75);
  border: 1px solid rgba(50, 80, 140, 0.3);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.04),
    0 4px 20px rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(12px);
}
.nav-pill {
  padding: 6px 20px;
  border-radius: 18px;
  font-size: 13px;
  font-weight: 500;
  color: #7a9ab8;
  cursor: pointer;
  transition: all 0.3s;
  border: 1px solid transparent;
  text-decoration: none;
  white-space: nowrap;
  background: transparent;
}
.nav-pill:hover {
  color: #b0d0f0;
  background: rgba(255, 255, 255, 0.06);
}
.nav-pill.active {
  color: #ffffff;
  background: rgba(40, 100, 180, 0.5);
  border-color: rgba(60, 160, 250, 0.4);
  box-shadow:
    0 0 12px rgba(40, 140, 240, 0.25),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

/* 右侧图标组 */
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.action-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: #5a7a9e;
  cursor: pointer;
  transition: all 0.25s;
}
.action-icon:hover {
  color: #8ab0d8;
  background: rgba(255, 255, 255, 0.05);
}
.user-avatar {
  background: linear-gradient(135deg, #2563eb, #3b82f6);
  color: #fff;
  font-weight: 600;
  font-size: 12px;
}
.user-dropdown-trigger {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  padding: 2px 6px 2px 2px;
  border-radius: 18px;
  transition: background 0.2s;
}
.user-dropdown-trigger:hover {
  background: rgba(255, 255, 255, 0.06);
}
.user-dropdown-arrow {
  color: #5a7a9e;
}
.user-dropdown-info {
  display: flex;
  flex-direction: column;
  min-width: 120px;
  padding: 4px 8px;
}
.user-dropdown-name {
  font-weight: 600;
  color: #e2e8f0;
  font-size: 13px;
}
.user-dropdown-role {
  color: #64748b;
  font-size: 11px;
  margin-top: 2px;
}

/* ====== 主内容区 ====== */
.wb-body {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 32px 20px;
  min-height: calc(100vh - 56px);
  gap: 6px;
}

/* ====== Hero 标题区 ====== */
.hero-section {
  width: 100%;
  max-width: 1600px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 4px 16px;
}

.hero-icon-wrap {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(50, 120, 220, 0.18), rgba(100, 80, 200, 0.12));
  border: 1px solid rgba(80, 140, 220, 0.2);
  color: #5a90d8;
}
.hero-icon-wrap svg { width: 18px; height: 18px; }

.hero-title {
  font-size: 20px;
  font-weight: 800;
  color: #ffffff;
  letter-spacing: 0.5px;
  line-height: 1.2;
}

.hero-subtitle {
  font-size: 12px;
  color: #82a8d8;
  margin-top: 3px;
  letter-spacing: 0.5px;
}

/* 行标题 */
.row-label {
  width: 100%;
  max-width: 1600px;
  font-size: 11px;
  font-weight: 600;
  color: #5e8ab8;
  letter-spacing: 2px;
  text-transform: uppercase;
  padding: 14px 4px 8px;
}

/* ====== 卡片网格 7列 ====== */
.card-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 12px;
  width: 100%;
  max-width: 1600px;
}

/* ====== 卡片基础 ====== */
.wb-card {
  position: relative;
  border-radius: 12px;
  cursor: pointer;
  transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  min-height: 148px;
  contain: layout style paint;
}

/* 底层毛玻璃 */
.card-base {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  z-index: 1;
}

/* 顶部高光反射 */
.card-shine {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: radial-gradient(
    ellipse 95% 45% at 50% 0%,
    rgba(255, 255, 255, 0.12) 0%,
    transparent 55%
  );
  pointer-events: none;
  z-index: 2;
}

/* 鼠标跟随流光 - GPU 加速，避免重绘 */
.card-spotlight {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  z-index: 6;
  opacity: 0;
  transition: opacity 0.3s;
  overflow: hidden;
}
.card-spotlight::before {
  content: '';
  position: absolute;
  width: 400px;
  height: 400px;
  margin-left: -200px;
  margin-top: -200px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.1) 0%, transparent 60%);
  transform: translate3d(var(--mouse-x, 50%), var(--mouse-y, 50%), 0);
  will-change: transform;
}
.wb-card:hover .card-spotlight {
  opacity: 1;
}

/* 边框层 */
.card-border {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  transition: all 0.35s;
  pointer-events: none;
  z-index: 3;
}

/* 顶部亮线 */
.card-top-line {
  position: absolute;
  top: 0;
  left: 12%;
  right: 12%;
  height: 1.5px;
  z-index: 4;
  pointer-events: none;
}

/* ====== 普通卡片 ====== */
.card-normal .card-base {
  background:
    radial-gradient(ellipse 85% 45% at 50% 0%, rgba(220, 235, 255, 0.85) 0%, transparent 55%),
    linear-gradient(180deg, #f3eede 0%, #e8e0cb 100%);
}
.card-normal .card-border {
  border: 1px solid rgba(190, 165, 110, 0.4);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.55),
    0 0 28px rgba(180, 150, 90, 0.18);
}
.card-normal .card-top-line {
  background: linear-gradient(90deg, transparent, rgba(180, 150, 90, 0.7), transparent);
}
.card-normal .card-icon-box {
  color: #7a5a1a;
  background: rgba(210, 180, 120, 0.18);
  border: 1.5px solid rgba(190, 165, 110, 0.5);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.4),
    0 0 12px rgba(190, 160, 100, 0.22);
}
.card-normal .card-title {
  color: #3a2e12;
}
.card-normal .card-subtitle {
  color: #6a5630;
}

/* ====== 高亮卡片（紫色）- 霓虹发光 ====== */
.card-highlight {
  box-shadow:
    0 0 45px rgba(210, 160, 255, 0.5),
    0 0 90px rgba(210, 160, 255, 0.2),
    0 0 160px rgba(210, 160, 255, 0.1);
}
.card-highlight .card-base {
  background:
    radial-gradient(ellipse 85% 45% at 50% 0%, rgba(240, 215, 255, 0.9) 0%, transparent 55%),
    linear-gradient(180deg, #f3eede 0%, #e8e0cb 100%);
}
.card-highlight .card-border {
  border: 1.5px solid rgba(200, 165, 240, 0.62);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.55),
    0 0 45px rgba(200, 150, 255, 0.4);
}
.card-highlight .card-top-line {
  background: linear-gradient(90deg, transparent, rgba(210, 170, 255, 0.92), transparent);
}
.card-highlight .card-icon-box {
  color: #7a3ab8;
  background: rgba(210, 175, 255, 0.2);
  border: 1.5px solid rgba(190, 155, 235, 0.55);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.4),
    0 0 16px rgba(200, 150, 255, 0.3);
}
.card-highlight .card-title {
  color: #3a1a48;
}
.card-highlight .card-subtitle {
  color: #6a4a9a;
}

/* ====== 重点卡片（亮蓝）- 霓虹发光 ====== */
.card-focus {
  box-shadow:
    0 0 45px rgba(80, 180, 255, 0.5),
    0 0 90px rgba(80, 180, 255, 0.2),
    0 0 160px rgba(80, 180, 255, 0.1);
}
.card-focus .card-base {
  background:
    radial-gradient(ellipse 85% 45% at 50% 0%, rgba(185, 230, 255, 0.9) 0%, transparent 55%),
    linear-gradient(180deg, #f3eede 0%, #e8e0cb 100%);
}
.card-focus .card-border {
  border: 1.5px solid rgba(110, 190, 250, 0.62);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.55),
    0 0 45px rgba(70, 170, 255, 0.4);
}
.card-focus .card-top-line {
  background: linear-gradient(90deg, transparent, rgba(140, 210, 255, 0.92), transparent);
}
.card-focus .card-icon-box {
  color: #1a6ac8;
  background: rgba(140, 200, 255, 0.2);
  border: 1.5px solid rgba(120, 190, 245, 0.55);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.4),
    0 0 16px rgba(100, 190, 255, 0.3);
}
.card-focus .card-title {
  color: #1a2e48;
}
.card-focus .card-subtitle {
  color: #3a5a9a;
}

/* ====== 卡片内部布局 - 左上图标 + 右文 ====== */
.card-inner {
  position: relative;
  z-index: 5;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: flex-start;
  padding: 16px 18px;
  height: 100%;
  gap: 14px;
  text-align: left;
}

/* 图标盒子 - 大边框包裹，小图标居中 */
.card-icon-box {
  width: 56px;
  height: 56px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  transition: all 0.35s;
}

/* 文字区 */
.card-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-title {
  font-size: 16px;
  font-weight: 800;
  color: #1a2a48;
  letter-spacing: 0.4px;
  line-height: 1.2;
}

/* 功能说明 */
.card-subtitle {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
  text-align: left;
  letter-spacing: 0.6px;
  transition: color 0.3s;
}

.wb-card.disabled { cursor: not-allowed; opacity: 0.55; }
.wb-card.disabled:hover { transform: none; box-shadow: none; }
.card-lock {
  margin-left: auto;
  padding: 3px 8px;
  border: 1px solid rgba(58, 46, 18, 0.25);
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  color: rgba(58, 46, 18, 0.55);
  white-space: nowrap;
}
.domain-tag { margin-left: 4px; }

/* ====== hover 效果 ====== */
.wb-card:hover {
  transform: translateY(-2px);
}

/* 普通卡片 hover */
.card-normal:hover {
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.3),
    0 0 45px rgba(60, 150, 240, 0.4);
}
.card-normal:hover .card-border {
  border-color: rgba(100, 190, 255, 0.65);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.2),
    0 0 45px rgba(50, 130, 230, 0.4);
}
.card-normal:hover .card-top-line {
  background: linear-gradient(90deg, transparent, rgba(130, 220, 255, 1), transparent);
}
.card-normal:hover .card-icon-box {
  color: #d0ecff;
  border-color: rgba(120, 195, 255, 0.6);
  background: rgba(120, 190, 255, 0.2);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 0 20px rgba(60, 150, 240, 0.4);
}
.card-normal:hover .card-subtitle {
  color: #a0d4ff;
  text-shadow: 0 0 14px rgba(100, 190, 255, 0.5);
}

/* 高亮卡片 hover */
.card-highlight:hover {
  box-shadow:
    0 0 65px rgba(220, 170, 255, 0.7),
    0 0 130px rgba(220, 170, 255, 0.3),
    0 0 200px rgba(220, 170, 255, 0.15);
}
.card-highlight:hover .card-border {
  border-color: rgba(240, 215, 255, 0.85);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.28),
    0 0 60px rgba(210, 160, 255, 0.55);
}
.card-highlight:hover .card-top-line {
  background: linear-gradient(90deg, transparent, rgba(255, 245, 255, 1), transparent);
}
.card-highlight:hover .card-icon-box {
  color: #ffffff;
  border-color: rgba(230, 200, 255, 0.7);
  background: rgba(220, 180, 255, 0.24);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 0 24px rgba(210, 160, 255, 0.5);
}

/* 重点卡片 hover */
.card-focus:hover {
  box-shadow:
    0 0 65px rgba(100, 200, 255, 0.7),
    0 0 130px rgba(100, 200, 255, 0.3),
    0 0 200px rgba(100, 200, 255, 0.15);
}
.card-focus:hover .card-border {
  border-color: rgba(140, 225, 255, 0.85);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.28),
    0 0 60px rgba(80, 180, 255, 0.55);
}
.card-focus:hover .card-top-line {
  background: linear-gradient(90deg, transparent, rgba(180, 240, 255, 1), transparent);
}
.card-focus:hover .card-icon-box {
  color: #d8f2ff;
  border-color: rgba(140, 220, 255, 0.7);
  background: rgba(130, 205, 255, 0.24);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 0 24px rgba(90, 185, 255, 0.5);
}

/* ====== Slogan 栏 ====== */
.slogan-bar {
  width: 100%;
  max-width: 1600px;
  padding: 20px 32px;
  border-radius: 12px;
  background: linear-gradient(90deg, rgba(40, 70, 120, 0.6) 0%, rgba(35, 65, 115, 0.7) 50%, rgba(40, 70, 120, 0.6) 100%);
  border: 1px solid rgba(80, 140, 210, 0.45);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.1),
    0 4px 20px rgba(0, 0, 0, 0.2);
  text-align: center;
  font-size: 13px;
  font-weight: 600;
  color: #6c9ad0;
  letter-spacing: 3px;
  margin-top: auto;
  backdrop-filter: blur(12px);
}

.slogan-dot {
  margin: 0 14px;
  color: #3a5070;
}

/* ====== 响应式 ====== */
@media (max-width: 1400px) {
  .card-grid { grid-template-columns: repeat(4, 1fr); }
}
@media (max-width: 1000px) {
  .card-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 860px) {
  .wb-header { padding: 0 16px; }
  .wb-body { padding: 20px 16px; }
  .wb-nav-pills { position: static; transform: none; }
}
@media (max-width: 640px) {
  .card-grid { grid-template-columns: repeat(2, 1fr); }
  .header-actions .action-icon { display: none; }
}
</style>
