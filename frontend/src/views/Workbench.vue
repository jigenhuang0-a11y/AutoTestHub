<template>
  <div class="workbench">
    <!-- 产品域 Tab -->
    <div class="domain-tabs">
      <div
        v-for="domain in domains"
        :key="domain.key"
        class="domain-tab"
        :class="{ active: activeDomain === domain.key }"
        @click="switchDomain(domain.key)"
      >
        <el-icon :size="18"><component :is="domain.icon" /></el-icon>
        <span>{{ domain.label }}</span>
        <el-tag v-if="domain.comingSoon" size="small" type="info" effect="plain" round>规划中</el-tag>
      </div>
    </div>

    <!-- 工作台内容 -->
    <div class="workbench-body">
      <div class="domain-header">
        <div>
          <h2 class="domain-title">{{ currentDomain.label }}</h2>
          <p class="domain-desc">{{ currentDomain.desc }}</p>
        </div>
      </div>

      <!-- 卡片网格 -->
      <div class="card-grid">
        <div
          v-for="group in currentDomain.groups"
          :key="group.title"
          class="card-group"
        >
          <div class="group-title">
            <el-icon><component :is="group.icon" /></el-icon>
            <span>{{ group.title }}</span>
          </div>
          <div class="group-cards">
            <div
              v-for="item in group.items"
              :key="item.title"
              class="entry-card"
              :class="{ disabled: item.disabled }"
              @click="goTo(item)"
            >
              <div class="entry-icon" :style="{ background: item.color }">
                <el-icon :size="22"><component :is="item.icon" /></el-icon>
              </div>
              <div class="entry-text">
                <div class="entry-title">{{ item.title }}</div>
                <div class="entry-sub">{{ item.desc }}</div>
              </div>
              <el-icon v-if="item.disabled" class="entry-lock"><Lock /></el-icon>
              <el-icon v-else class="entry-arrow"><ArrowRight /></el-icon>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Cpu, DataLine, SetUp, Monitor, MagicStick, Reading, Connection,
  VideoPlay, Link, Timer, DataAnalysis, Coin, ChatDotRound,
  Histogram, Search, Box, Operation, Tickets, Calendar, Lock, ArrowRight,
} from '@element-plus/icons-vue'

const router = useRouter()

const activeDomain = ref('base')

const domains = [
  { key: 'base', label: 'AI 效能中台', icon: Cpu, desc: 'AI 底座能力与运维观测一体化' },
  { key: 'test', label: 'AI 测试平台', icon: DataLine, desc: '智能化测试业务全流程' },
  { key: 'case', label: '用例平台', icon: Tickets, desc: '下一代用例管理与协作', comingSoon: true },
  { key: 'schedule', label: '团队排期', icon: Calendar, desc: '团队协作与排期管理', comingSoon: true },
]

// 各产品域的功能分组
const domainConfig = {
  base: {
    label: 'AI 效能中台',
    desc: 'AI 底座能力与运维观测一体化',
    groups: [
      {
        title: 'AI 核心底座',
        icon: Cpu,
        items: [
          { title: '模型管理', desc: 'LLM 模型配置与路由', icon: SetUp, color: 'linear-gradient(135deg,#667eea,#764ba2)', to: '/model-manage' },
          { title: '技能库', desc: 'Agent 技能与工具注册', icon: MagicStick, color: 'linear-gradient(135deg,#f093fb,#f5576c)', to: '/agent-skills' },
          { title: '知识中枢', desc: 'RAG 知识库问答', icon: Reading, color: 'linear-gradient(135deg,#4facfe,#00f2fe)', to: '/knowledge/chat' },
          { title: 'Agent 编排', desc: '多 Agent 团队协作', icon: Connection, color: 'linear-gradient(135deg,#11998e,#38ef7d)', to: '/team', disabled: true },
        ],
      },
      {
        title: '运维观测管理',
        icon: Monitor,
        items: [
          { title: '任务监控', desc: '编排任务实时观测', icon: VideoPlay, color: 'linear-gradient(135deg,#fa709a,#fee140)', to: '/self-healing' },
          { title: '审计大屏', desc: '全链路审计与统计', icon: Histogram, color: 'linear-gradient(135deg,#30cfd0,#330867)', to: '/dashboard' },
          { title: '链路追踪', desc: '调用链与性能分析', icon: Search, color: 'linear-gradient(135deg,#a8edea,#fed6e3)', to: '/dashboard', disabled: true },
          { title: 'MCP 工具网关', desc: '工具接入与治理', icon: Box, color: 'linear-gradient(135deg,#ff9a9e,#fecfef)', to: '/agent-skills', disabled: true },
          { title: '沙箱管控', desc: '执行环境与隔离', icon: Operation, color: 'linear-gradient(135deg,#5ee7df,#b490ca)', to: '/self-healing', disabled: true },
          { title: '环境管理', desc: '多环境配置', icon: Coin, color: 'linear-gradient(135deg,#d299c2,#fef9d7)', to: '/dashboard', disabled: true },
        ],
      },
    ],
  },
  test: {
    label: 'AI 测试平台',
    desc: '智能化测试业务全流程',
    groups: [
      {
        title: '自动化测试工具链',
        icon: DataLine,
        items: [
          { title: 'AI 用例生成', desc: '自然语言生成测试用例', icon: MagicStick, color: 'linear-gradient(135deg,#667eea,#764ba2)', to: '/testcases/ai-generate' },
          { title: '接口自动化', desc: 'API 用例与执行', icon: Link, color: 'linear-gradient(135deg,#11998e,#38ef7d)', to: '/testcases' },
          { title: '性能测试', desc: '压测与性能分析', icon: Timer, color: 'linear-gradient(135deg,#4facfe,#00f2fe)', to: '/perf-testcases' },
          { title: '测试套件', desc: '用例集与编排', icon: Connection, color: 'linear-gradient(135deg,#fa709a,#fee140)', to: '/testsuites' },
          { title: '执行历史', desc: '历次执行记录', icon: VideoPlay, color: 'linear-gradient(135deg,#30cfd0,#330867)', to: '/history' },
          { title: '测试报告', desc: '可视化报告', icon: DataAnalysis, color: 'linear-gradient(135deg,#a8edea,#fed6e3)', to: '/reports' },
        ],
      },
      {
        title: 'AI 增强能力',
        icon: ChatDotRound,
        items: [
          { title: '数据工厂', desc: '测试数据生成', icon: Coin, color: 'linear-gradient(135deg,#ff9a9e,#fecfef)', to: '/data-factory' },
          { title: '需求评审师', desc: '评审需求、评估测试用例', icon: Monitor, color: 'linear-gradient(135deg,#5ee7df,#b490ca)', to: '/quality-checker' },
          { title: 'AI 测评师', desc: '模型与用例评测', icon: Cpu, color: 'linear-gradient(135deg,#d299c2,#fef9d7)', to: '/ai-evaluator' },
        ],
      },
    ],
  },
  case: {
    label: '用例平台',
    desc: '下一代用例管理与协作',
    groups: [
      {
        title: '规划中',
        icon: Tickets,
        items: [
          { title: '用例库', desc: '统一用例资产管理', icon: Tickets, color: 'linear-gradient(135deg,#667eea,#764ba2)', disabled: true },
          { title: '协作评审', desc: '团队用例评审', icon: ChatDotRound, color: 'linear-gradient(135deg,#11998e,#38ef7d)', disabled: true },
        ],
      },
    ],
  },
  schedule: {
    label: '团队排期',
    desc: '团队协作与排期管理',
    groups: [
      {
        title: '规划中',
        icon: Calendar,
        items: [
          { title: '迭代排期', desc: 'Sprint 规划与跟踪', icon: Calendar, color: 'linear-gradient(135deg,#f093fb,#f5576c)', disabled: true },
          { title: '任务看板', desc: '团队任务协作', icon: Operation, color: 'linear-gradient(135deg,#4facfe,#00f2fe)', disabled: true },
        ],
      },
    ],
  },
}

const currentDomain = computed(() => domainConfig[activeDomain.value])

const switchDomain = (key) => {
  activeDomain.value = key
}

const goTo = (item) => {
  if (item.disabled || !item.to) return
  router.push(item.to)
}
</script>

<style scoped>
.workbench { padding: 24px; max-width: 1400px; margin: 0 auto; }

.domain-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--app-border);
  padding-bottom: 0;
}
.domain-tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  color: var(--app-text-secondary);
  font-weight: 500;
  transition: all 0.2s;
}
.domain-tab:hover { color: var(--app-text); }
.domain-tab.active {
  color: #409eff;
  border-bottom-color: #409eff;
}

.domain-header { margin-bottom: 24px; }
.domain-title { font-size: 24px; font-weight: 700; margin: 0 0 4px; color: var(--app-text); }
.domain-desc { font-size: 14px; color: var(--app-text-secondary); margin: 0; }

.card-grid { display: flex; flex-direction: column; gap: 24px; }
.card-group {
  background: var(--el-bg-color);
  border: 1px solid var(--app-border);
  border-radius: 12px;
  padding: 20px;
}
.group-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--app-text);
  margin-bottom: 16px;
}
.group-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.entry-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--app-border);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--app-bg);
}
.entry-card:hover:not(.disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  border-color: #409eff;
}
.entry-card.disabled { opacity: 0.5; cursor: not-allowed; }
.entry-icon {
  width: 44px; height: 44px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  color: white; flex-shrink: 0;
}
.entry-text { flex: 1; min-width: 0; }
.entry-title { font-size: 14px; font-weight: 600; color: var(--app-text); }
.entry-sub { font-size: 12px; color: var(--app-text-secondary); margin-top: 2px; }
.entry-arrow { color: var(--app-text-secondary); }
.entry-lock { color: var(--app-text-secondary); }
</style>
