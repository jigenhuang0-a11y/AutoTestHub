<template>
  <div class="eval-center">
    <!-- 渐变英雄区 -->
    <div class="hero">
      <div class="hero-left">
        <div class="title-icon">
          <el-icon :size="26"><Monitor /></el-icon>
        </div>
        <div>
          <h1>全链路评测中心</h1>
          <p class="subtitle">Golden Dataset + Judge LLM + 多维度评分 · 实时幻觉率与质量监控</p>
        </div>
      </div>
      <div class="hero-right">
        <div class="health-ring">
          <el-progress
            type="dashboard"
            :percentage="Math.round(dashboard.avg_scores.overall)"
            :width="92"
            :stroke-width="9"
            :color="ringColor"
          >
            <template #default="{ percentage }">
              <span class="ring-value">{{ percentage }}</span>
              <span class="ring-label">综合健康度</span>
            </template>
          </el-progress>
        </div>
        <div class="hero-actions">
          <el-select v-model="hours" size="default" style="width: 130px" @change="loadDashboard">
            <el-option label="近 24 小时" :value="24" />
            <el-option label="近 7 天" :value="168" />
            <el-option label="近 30 天" :value="720" />
            <el-option label="近 90 天" :value="2160" />
          </el-select>
          <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadDashboard">刷新</el-button>
          <el-button type="success" :icon="VideoPlay" :loading="demoLoading" @click="openLatestReplay">查看最新结果</el-button>
          <el-tooltip content="开启后按设定周期自动刷新面板数据，持续追踪最新链路">
            <span class="track-wrap">
              <el-switch v-model="autoRefresh" class="track-switch" active-text="自动追踪" inline-prompt inactive-text="自动追踪" style="margin-left: 8px;" @change="toggleAutoRefresh" />
              <span v-if="isTracking" class="track-dot" :title="'自动追踪中，每 ' + (refreshInterval < 60 ? refreshInterval + ' 秒' : Math.round(refreshInterval / 60) + ' 分钟')"></span>
            </span>
          </el-tooltip>
          <el-select v-if="autoRefresh" v-model="refreshInterval" size="default" style="width: 120px; margin-left: 8px;" @change="restartAutoRefresh">
            <el-option label="10 秒" :value="10" />
            <el-option label="30 秒" :value="30" />
            <el-option label="1 分钟" :value="60" />
            <el-option label="5 分钟" :value="300" />
          </el-select>
          <el-button v-if="langfuse?.enabled" type="info" :icon="Link" @click="openLangfuse">打开 Langfuse</el-button>
          <el-dropdown @command="onExport" :disabled="!records.length">
            <el-button :icon="Download">导出</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="txt">文本报告</el-dropdown-item>
                <el-dropdown-item command="csv">CSV 明细</el-dropdown-item>
                <el-dropdown-item command="json">JSON 原始</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </div>

    <!-- 维度评分条 -->
    <el-card shadow="never" class="dim-card compact">
      <template #header>
        <div class="card-header">
          <span>多维度质量评分</span>
          <el-tag size="small" :type="scoreTag(dashboard.avg_scores.overall)">
            综合 {{ dashboard.avg_scores.overall }}
          </el-tag>
        </div>
      </template>
      <div class="dim-grid compact">
        <div v-for="d in dimList" :key="d.key" class="dim-item compact">
          <div class="dim-top compact">
            <span class="dim-name">{{ d.label }}</span>
            <span class="dim-score" :class="scoreClass(scoreOf(d.key))">{{ scoreOf(d.key) }}</span>
          </div>
          <el-progress
            :percentage="scoreOf(d.key)"
            :stroke-width="6"
            :show-text="false"
            :color="barColor(scoreOf(d.key))"
          />
        </div>
      </div>
    </el-card>

    <!-- 功能流水线概览：一眼看清哪个功能出问题（幻觉率/Token/耗时） -->
    <el-card shadow="never" class="feat-card">
      <template #header>
        <div class="card-header">
          <span>AI 功能 & 底座链路概览</span>
          <span class="card-sub">上层=业务功能 · 下层=AI 底座链路 · 红色=异常需关注</span>
        </div>
      </template>
      <div class="feat-grid">
        <div
          v-for="f in featureStatsList"
          :key="f.feature"
          class="feat-item"
          :class="{ 'feat-warn': f.avg_hallucination > 60, 'feat-active': f.feature === activeFeature }"
          @click="onFeatureCardClick(f.feature)"
        >
          <div class="feat-top">
            <span class="feat-name">{{ f.label }}</span>
            <span class="feat-count">{{ f.count }} 次</span>
          </div>
          <div class="feat-metrics">
            <div class="feat-metric">
              <span class="fm-label">幻觉率</span>
              <span class="fm-value" :class="scoreClass(f.avg_hallucination)">{{ f.avg_hallucination || '—' }}</span>
            </div>
            <div class="feat-metric">
              <span class="fm-label">综合分</span>
              <span class="fm-value" :class="scoreClass(f.avg_score)">{{ f.avg_score || '—' }}</span>
            </div>
          </div>
          <!-- AI 底座链路支撑标签 -->
          <div class="feat-infra">
            <el-tag
              v-for="infra in infraChainOf(f.feature)"
              :key="infra"
              size="small"
              effect="dark"
              type="warning"
              class="infra-chip"
            >{{ featureLabel(infra) }}</el-tag>
          </div>
          <el-progress :percentage="Math.min(100, f.avg_hallucination || 0)" :stroke-width="4" :show-text="false" :color="f.avg_hallucination > 60 ? '#f56c6c' : '#67c23a'" />
        </div>
      </div>

      <div class="infra-layer-title">AI 底座链路层</div>
      <div class="feat-grid infra">
        <div
          v-for="f in infraStatsList"
          :key="f.feature"
          class="feat-item infra-item"
          :class="{ 'feat-warn': f.error_count > 0, 'feat-active': f.feature === activeFeature }"
          @click="toggleFeatureFilter(f.feature)"
        >
          <div class="feat-top">
            <span class="feat-name">{{ f.label }}</span>
            <span class="feat-count">{{ f.count }} 次</span>
          </div>
          <div class="feat-metrics">
            <div class="feat-metric">
              <span class="fm-label">失败</span>
              <span class="fm-value" :class="f.error_count > 0 ? 'score-bad' : ''">{{ f.error_count || '—' }}</span>
            </div>
            <div class="feat-metric">
              <span class="fm-label">均耗时</span>
              <span class="fm-value">{{ f.avg_latency_ms ? (f.avg_latency_ms / 1000).toFixed(1) + 's' : '—' }}</span>
            </div>
          </div>
          <div class="feat-infra">
            <el-tag size="small" effect="dark" type="warning" class="infra-chip">底座</el-tag>
            <el-tag v-if="f.avg_tokens" size="small" effect="dark" type="info" class="infra-chip">{{ f.avg_tokens }} token</el-tag>
          </div>
          <el-progress :percentage="Math.min(100, (f.error_count / Math.max(f.count, 1)) * 100 || 0)" :stroke-width="4" :show-text="false" :color="f.error_count > 0 ? '#f56c6c' : '#3b82f6'" />
        </div>
      </div>
    </el-card>

    <!-- 图表区 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="chart-card radar-card">
          <template #header>
            <div class="card-header">
              <span>多维度评分雷达图</span>
              <el-tag size="small" type="info">平均分</el-tag>
            </div>
          </template>
          <div ref="radarRef" class="chart-box" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="chart-card trend-card">
          <template #header>
            <div class="card-header">
              <span>综合分趋势（近 {{ hours }}h · {{ granularityText }}）</span>
              <div class="trend-header-actions">
                <el-radio-group v-model="granularity" size="small" @change="loadDashboard">
                  <el-radio-button label="按小时" value="hour" />
                  <el-radio-button label="按周" value="week" />
                  <el-radio-button label="按月" value="month" />
                </el-radio-group>
                <el-tag size="small" type="info">{{ dashboard.trend.length }} 个时间点</el-tag>
              </div>
            </div>
          </template>
          <div ref="trendRef" class="chart-box">
            <div v-if="isTrendEmpty" class="chart-empty">暂无评测数据</div>
          </div>
        </el-card>
      </el-col>
    </el-row>


  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, RefreshLeft, VideoPlay, Link, Monitor, Download } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { evalCenterAPI } from '@/api'

const router = useRouter()

const featureLabels = {
  // ── 业务功能层（对应左侧菜单真实功能） ──
  requirement_review: '需求评审师',
  ai_testcase: 'AI 用例生成',
  generation: 'AI 用例生成',
  data_factory: '数据工厂',
  data_generation: '数据工厂',
  api_test: '接口测试',
  ui_auto: 'UI 自动化',
  perf_test: '性能测试',
  test_execution: '测试执行',
  quality_eval: 'AI 评测',
  evaluate: 'AI 评测',
  evaluation: 'AI 评测',
  knowledge_chat: '测试知识库',
  chat: '智能对话',
  fast_chat: 'AI 快速问答',
  reasoning: 'AI 深度思考',
  rag_query: 'RAG 问答',
  rag_search: 'RAG 检索',
  agent_loop: 'Agent 循环',
  quality_check: '质量检查',
  // ── AI 底座链路层（用于事件列表底座标签，不在功能链路概览展示） ──
  llm_router: 'LLM 路由',
  llm_call: 'LLM 生成',
  tool_call: '工具调用',
  tool_gateway: '工具网关',
  vector_search: '向量检索',
  db_query: '数据库操作',
  memory: '长短期记忆',
  judge: 'Judge 评分',
  unknown: '未分类',
}
// 业务功能层（EvalCenter「AI 功能链路概览」只展示这些）
const BUSINESS_FEATURES = [
  'knowledge_chat',
  'requirement_review',
  'ai_testcase',
  'data_factory',
  'api_test',
  'ui_auto',
  'perf_test',
  'test_execution',
  'quality_eval',
]
// AI 底座链路层标识（用于事件列表的底座标签）
const INFRA_FEATURES = ['llm_router', 'llm_call', 'tool_call', 'tool_gateway', 'vector_search', 'db_query', 'memory', 'judge']
const isInfraFeature = (f) => INFRA_FEATURES.includes(f)
const featureLabel = (f) => featureLabels[f] || f || '未分类'
// 把后端可能的 task_type 别名归并到标准业务功能名，用于统一展示与筛选
function normalizeFeature(f) {
  const aliasMap = {
    generation: 'ai_testcase',
    data_generation: 'data_factory',
    evaluation: 'quality_eval',
    evaluate: 'quality_eval',
  }
  return aliasMap[f] || f
}
const truncate = (s, n) => (s && s.length > n ? s.slice(0, n) + '…' : (s || ''))
// 各业务功能典型的 AI 底座链路支撑（用于功能卡片展示）
const FEATURE_INFRA_CHAIN = {
  requirement_review: ['llm_router', 'llm_call'],
  ai_testcase: ['llm_router', 'llm_call', 'tool_call'],
  data_factory: ['llm_router', 'llm_call', 'db_query'],
  api_test: ['llm_router', 'tool_call'],
  ui_auto: ['llm_router', 'tool_call'],
  perf_test: ['llm_router', 'tool_call'],
  test_execution: ['llm_router', 'tool_call', 'db_query'],
  quality_eval: ['llm_router', 'llm_call', 'judge'],
  knowledge_chat: ['llm_router', 'vector_search', 'llm_call'],
}
const infraChainOf = (feature) => FEATURE_INFRA_CHAIN[feature] || []
function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z')
  if (isNaN(d.getTime())) return iso
  const pad = (x) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const hours = ref(24)
const granularity = ref('hour')
const loading = ref(false)
const dashboard = ref({
  total_records: 0,
  granularity: 'hour',
  avg_scores: { overall: 0, hallucination: 0, consistency: 0, completeness: 0, executability: 0, safety: 0 },
  by_feature: {},
  trend: [],
  recent_records: [],
})
const langfuse = ref({ enabled: false, host: '', traces_url: '' })
const records = ref([])
const recordsLoading = ref(false)
const featureStats = ref({})  // feature -> {count, avg_hallucination, avg_score, avg_tokens, avg_latency_ms}
const activeFeature = ref('')  // 点击功能卡筛选记录表
const demoLoading = ref(false)
const demoTrace = ref(null)
const isTracking = ref(false)
const autoRefresh = ref(localStorage.getItem('eval-center-auto-refresh') === 'true')
const refreshInterval = ref(Number(localStorage.getItem('eval-center-refresh-interval')) || 30)
let trackingTimer = null
// 用户手动改间隔时立即持久化，并重启定时器
watch(refreshInterval, (val) => {
  localStorage.setItem('eval-center-refresh-interval', String(val))
  if (isTracking.value) restartAutoRefresh()
})
const lastEventMs = ref(0)
const pollLoading = ref(false)
const showInfraEvents = ref(false)  // 默认只看业务功能事件，避免底座事件淹没列表

async function loadRecords() {
  recordsLoading.value = true
  try {
    // 事件驱动：优先读取真实 AI 调用事件；为空时 fallback 到历史 Judge 记录
    let list = []
    try {
      const data = await evalCenterAPI.events({ limit: 100, since_ms: 0 })
      list = Array.isArray(data) ? data : (data.events || [])
      lastEventMs.value = (data.latest_ms || lastEventMs.value)
    } catch (_) {}
    if (!list.length) {
      const data = await evalCenterAPI.records({ hours: 720, limit: 100 })
      const rows = Array.isArray(data) ? data : (data.records || [])
      list = rows.map(normalizeRecordToEvent)
    }
    records.value = list.map(normalizeEventToRecord)
    loadFeatureStats()
  } catch (e) {
    ElMessage.error('记录加载失败：' + (e.message || e))
  } finally {
    recordsLoading.value = false
  }
}

const filteredRecords = computed(() => {
  let list = records.value
  if (!showInfraEvents.value) {
    // 关闭底座事件时，只保留业务功能记录（过滤掉所有 AI 底座链路层）
    list = list.filter(r => BUSINESS_FEATURES.includes(normalizeFeature(r.feature)))
  }
  if (activeFeature.value) {
    list = list.filter(r => normalizeFeature(r.feature) === activeFeature.value)
  }
  return list
})

// 按功能聚合的流水线概览（幻觉率 / Token / 耗时），只展示业务功能并补零
const featureStatsList = computed(() => {
  const safeStats = featureStats.value && typeof featureStats.value === 'object' && !Array.isArray(featureStats.value)
    ? featureStats.value
    : {}
  // 先归并后端返回的别名数据
  const merged = {}
  Object.entries(safeStats).forEach(([rawKey, val]) => {
    const key = normalizeFeature(rawKey)
    if (!BUSINESS_FEATURES.includes(key)) return
    const cur = merged[key]
    if (!cur) {
      merged[key] = { ...val, feature: key, label: featureLabel(key) }
      return
    }
    const total = (cur.count || 0) + (val.count || 0)
    const weightA = cur.count || 0
    const weightB = val.count || 0
    merged[key] = {
      feature: key,
      label: featureLabel(key),
      count: total,
      avg_hallucination: total ? Math.round(((cur.avg_hallucination || 0) * weightA + (val.avg_hallucination || 0) * weightB) / total) : 0,
      avg_score: total ? Math.round(((cur.avg_score || 0) * weightA + (val.avg_score || 0) * weightB) / total) : 0,
      avg_tokens: total ? Math.round(((cur.avg_tokens || 0) * weightA + (val.avg_tokens || 0) * weightB) / total) : 0,
      avg_latency_ms: total ? Math.round(((cur.avg_latency_ms || 0) * weightA + (val.avg_latency_ms || 0) * weightB) / total) : 0,
    }
  })
  // 对未调用的业务功能补零展示，确保即使后端无数据也始终有卡片
  BUSINESS_FEATURES.forEach((key) => {
    if (!merged[key]) {
      merged[key] = { feature: key, label: featureLabel(key), count: 0, avg_hallucination: 0, avg_score: 0, avg_tokens: 0, avg_latency_ms: 0 }
    }
  })
  return Object.values(merged).sort((a, b) => {
    const idxA = BUSINESS_FEATURES.indexOf(a.feature)
    const idxB = BUSINESS_FEATURES.indexOf(b.feature)
    if (idxA !== idxB) return idxA - idxB
    return (b.avg_hallucination || 0) - (a.avg_hallucination || 0)
  })
})

// AI 底座链路层聚合统计（LLM 路由 / LLM 生成 / 向量检索 / 工具调用 / 数据库 / Judge）
const infraStatsList = computed(() => {
  const safeStats = featureStats.value && typeof featureStats.value === 'object' && !Array.isArray(featureStats.value)
    ? featureStats.value
    : {}
  const merged = {}
  // 优先从后端聚合数据取
  Object.entries(safeStats).forEach(([rawKey, val]) => {
    const key = normalizeFeature(rawKey)
    if (!INFRA_FEATURES.includes(key)) return
    const cur = merged[key]
    if (!cur) {
      merged[key] = { ...val, feature: key, label: featureLabel(key), error_count: 0 }
      return
    }
    const total = (cur.count || 0) + (val.count || 0)
    const weightA = cur.count || 0
    const weightB = val.count || 0
    merged[key] = {
      feature: key,
      label: featureLabel(key),
      count: total,
      avg_hallucination: total ? Math.round(((cur.avg_hallucination || 0) * weightA + (val.avg_hallucination || 0) * weightB) / total) : 0,
      avg_score: total ? Math.round(((cur.avg_score || 0) * weightA + (val.avg_score || 0) * weightB) / total) : 0,
      avg_tokens: total ? Math.round(((cur.avg_tokens || 0) * weightA + (val.avg_tokens || 0) * weightB) / total) : 0,
      avg_latency_ms: total ? Math.round(((cur.avg_latency_ms || 0) * weightA + (val.avg_latency_ms || 0) * weightB) / total) : 0,
      error_count: (cur.error_count || 0) + (val.error_count || 0),
    }
  })
  // 兜底从 records 里实时统计
  if (!Object.keys(merged).length && records.value.length) {
    records.value.forEach((r) => {
      const key = normalizeFeature(r.feature)
      if (!INFRA_FEATURES.includes(key)) return
      if (!merged[key]) {
        merged[key] = { feature: key, label: featureLabel(key), count: 0, avg_hallucination: 0, avg_score: 0, avg_tokens: 0, avg_latency_ms: 0, error_count: 0 }
      }
      const m = merged[key]
      m.count += 1
      const total = m.count
      m.avg_latency_ms = Math.round(((m.avg_latency_ms || 0) * (total - 1) + (r.latency_ms || 0)) / total)
      m.avg_tokens = Math.round(((m.avg_tokens || 0) * (total - 1) + (r.tokens || 0)) / total)
      if (r.status === 'error') m.error_count += 1
    })
  }
  // 补零展示，确保始终能看到全部 AI 底座链路
  INFRA_FEATURES.forEach((key) => {
    if (!merged[key]) {
      merged[key] = { feature: key, label: featureLabel(key), count: 0, avg_hallucination: 0, avg_score: 0, avg_tokens: 0, avg_latency_ms: 0, error_count: 0 }
    }
  })
  return Object.values(merged).sort((a, b) => (b.count || 0) - (a.count || 0))
})

async function loadFeatureStats() {
  try {
    const data = await evalCenterAPI.featureStats(hours.value)
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      featureStats.value = data
    }
  } catch (e) {
    // 后端接口未就绪时，保底展示空业务功能卡片，不阻塞界面
    console.warn('feature-stats load failed:', e.message)
  }
}

function toggleFeatureFilter(f) {
  activeFeature.value = activeFeature.value === f ? '' : f
  loadRecords()
}

async function onFeatureCardClick(f) {
  // 测试知识库 / AI 对话：直接打开最新追踪详情（重点链路亮点）
  if (f === 'knowledge_chat' || f === 'chat') {
    try {
      const res = await evalCenterAPI.latestByFeature(f)
      if (res.found && res.event?.trace_id) {
        router.push({
          name: 'TraceReplay',
          params: { traceId: res.event.trace_id },
          query: { event_id: res.event.event_id || '' },
        })
        return
      }
      ElMessage.info(`「${featureLabel(f)}」暂无追踪记录，请先在对应功能发起一次对话`)
    } catch (e) {
      ElMessage.warning('打开追踪详情失败：' + (e.message || e))
    }
    return
  }
  // 其余功能维持原有筛选行为
  toggleFeatureFilter(f)
}

// 把旧 EvalStore 记录统一成 EvalEvent 样式，保证前端只处理一种结构
function normalizeRecordToEvent(rec) {
  return {
    event_id: rec.record_id || rec.trace_id || ('rec-' + Date.now()),
    feature: rec.feature,
    input_summary: rec.input_text,
    output_summary: rec.output_text,
    model: rec.model,
    provider: rec.provider || '—',
    latency_ms: rec.latency_ms,
    token_usage: rec.token_usage,
    trace_id: rec.trace_id,
    retrieved_docs: rec.retrieved_docs,
    status: 'completed',
    judge: rec.judge,
    dimension_scores: rec.dimension_scores || (rec.judge || {}).dimension_scores,
    issues: rec.issues,
    timestamp: rec.created_at,
    created_at_ms: rec.created_at ? new Date(rec.created_at).getTime() : Date.now(),
  }
}

// 把 EvalEvent 统一成记录表可用的行结构
function normalizeEventToRecord(ev) {
  const judge = ev.judge_output || ev.judge || {}
  const dims = judge.dimension_scores || ev.dimension_scores || {}
  const overall = judge.overall ?? dims['综合分'] ?? dims.overall ?? 0
  const hasScore = overall > 0 || Object.values(dims).some(v => Number(v) > 0)
  return {
    event_id: ev.event_id,
    feature: ev.feature,
    input_text: ev.input_summary,
    output_text: ev.output_summary,
    model: ev.model,
    provider: ev.provider,
    latency_ms: ev.latency_ms,
    token_usage: ev.token_usage,
    trace_id: ev.trace_id,
    retrieved_docs: ev.retrieved_docs,
    overall,
    hallucination: dims['幻觉率'] ?? dims.hallucination ?? 0,
    consistency: dims['一致性'] ?? dims.consistency ?? 0,
    completeness: dims['完整性'] ?? dims.completeness ?? 0,
    executability: dims['可执行性'] ?? dims.executability ?? 0,
    safety: dims['安全性'] ?? dims.safety ?? 0,
    reason: judge.summary || judge.reason || (ev.status === 'judging' ? 'Judge 中…' : ''),
    issues: judge.issues || ev.issues || [],
    created_at: ev.timestamp,
    status: ev.status,
    trace_steps: ev.trace_steps || [],
    metadata: { ...(ev.metadata || {}), hasScore },
    _raw: ev,
  }
}

function isLegacyRecordId(id) {
  return id && (id.startsWith('local-') || id.startsWith('rec-'))
}

async function openDetail(row) {
  if (!row.trace_id) {
    ElMessage.warning('该记录没有 trace_id，无法回放')
    return
  }
  router.push({ name: 'TraceReplay', params: { traceId: row.trace_id }, query: { event_id: row.event_id || '' } })
}

function exportReport() {
  const d = dashboard.value
  const lines = [
    '全链路评测中心 · 测试报告',
    `统计周期：近 ${hours.value} 小时`,
    `生成时间：${new Date().toLocaleString()}`,
    '',
    `评测样本总数：${d.total_records}`,
    `覆盖业务模块：${Object.keys(d.by_feature).length}`,
    '',
    '【多维度平均分】',
    ...dimList.map(x => `  ${x.label}：${scoreOf(x.key)}`),
    '',
    '【各模块评测分布】',
    ...Object.entries(d.by_feature).map(([k, v]) => `  ${featureLabel(k)}：样本 ${v.count} | 平均分 ${v.avg_overall == null ? 'N/A（底座链路）' : v.avg_overall}`),
    '',
    '【最近评测记录】',
    ...records.value.slice(0, 50).map(r => `  [${r.overall}] ${featureLabel(r.feature)} - ${r.reason || '（无说明）'}`),
  ]
  const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `eval-report-${new Date().toISOString().slice(0, 10)}.txt`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('报告已导出')
}

function exportCSV() {
  const header = ['时间', '模块', '综合', '幻觉率', '一致性', '完整性', '可执行性', '安全性', 'Trace', 'Judge结论']
  const rows = records.value.map(r => [
    formatTime(r.created_at), featureLabel(r.feature), r.overall, r.hallucination,
    r.consistency, r.completeness, r.executability, r.safety, r.trace_id || '', (r.reason || '').replace(/[\n,]/g, ' '),
  ])
  const csv = [header, ...rows].map(row => row.map(c => `"${c}"`).join(',')).join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `eval-records-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('CSV 已导出')
}

function exportJSON() {
  const blob = new Blob([JSON.stringify(records.value, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `eval-records-${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('JSON 已导出')
}

const isTrendEmpty = computed(() => !(dashboard.value.trend || []).some(t => (t.count || 0) > 0))
const isFeatureEmpty = computed(() => !Object.keys(dashboard.value.by_feature || {}).length)
// 单点兜底：非空趋势点只有 1 个时，放大圆点并特殊显示
const isSinglePoint = computed(() => (dashboard.value.trend || []).filter(t => (t.count || 0) > 0).length === 1)
const granularityText = computed(() => {
  const map = { hour: '按小时', week: '按周', month: '按月' }
  return map[dashboard.value.granularity] || map[granularity.value] || '按小时'
})

const radarRef = ref(null)
const trendRef = ref(null)
let radarChart = null
let trendChart = null

const defaultScores = () => ({ overall: 0, hallucination: 0, consistency: 0, completeness: 0, executability: 0, safety: 0 })
const defaultDashboard = () => ({
  total_records: 0,
  granularity: 'hour',
  avg_scores: defaultScores(),
  by_feature: {},
  trend: [],
  recent_records: [],
})

function normalizeDashboard(data) {
  const d = data || {}
  return {
    total_records: d.total_records ?? 0,
    granularity: d.granularity || 'hour',
    avg_scores: { ...defaultScores(), ...(d.avg_scores || {}) },
    by_feature: d.by_feature || {},
    trend: Array.isArray(d.trend) ? d.trend : [],
    recent_records: Array.isArray(d.recent_records) ? d.recent_records : [],
  }
}

async function loadDashboard() {
  loading.value = true
  try {
    // 刷新面板时同步刷新功能链路概览数据
    await loadFeatureStats()
    // axios 拦截器已返回 response.data，无需再解构 { data }
    const data = await evalCenterAPI.dashboard(hours.value, granularity.value)
    dashboard.value = normalizeDashboard(data)
    nextTick(() => setTimeout(initCharts, 100))
  } catch (e) {
    ElMessage.error('仪表盘加载失败：' + (e.message || e))
  } finally {
    loading.value = false
  }
}

async function loadLangfuseConfig() {
  try {
    const data = await evalCenterAPI.langfuseConfig()
    langfuse.value = data || { enabled: false }
  } catch {
    langfuse.value = { enabled: false }
  }
}

// 离线演示用的结构化根因样例（后端不可达时也能展示"问题定位记录仪"）
function buildOfflineDemo() {
  return {
    hallucination: 20, consistency: 70, completeness: 60, executability: 70, safety: 90, overall: 62,
    reason: '生成内容包含多处与参考材料不符的幻觉信息，如到账时间、无理由秒退和优惠券补偿。',
    dimension_scores: { 幻觉率: 20, 一致性: 70, 完整性: 60, 可执行性: 70, 安全性: 90 },
    issues: [
      { severity: 'high', dimension: 'hallucination', location: '答案第2条',
        claim: '退款将在 24 小时内到账',
        evidence: "参考材料明确说明'审核通过后 1-3 个工作日到账'，24 小时与 1-3 个工作日不符。",
        suggestion: "改为'审核通过后 1-3 个工作日到账'。" },
      { severity: 'high', dimension: 'hallucination', location: '答案第3条',
        claim: '平台还支持无理由秒退——用户无需任何理由可在 7 天内一键全额退款',
        evidence: "参考材料明确说明'不支持无理由秒退'，且不应编造 7 天无理由退货政策。",
        suggestion: "删除该句，或改为'平台不支持无理由秒退'。" },
      { severity: 'medium', dimension: 'hallucination', location: '答案第3条',
        claim: '退款会额外赠送 5% 的优惠券作为补偿',
        evidence: '参考材料中无任何关于优惠券补偿的信息。',
        suggestion: '删除该句，或补充相关事实依据。' },
    ],
    retrieval_gaps: [
      '未检索到关于退款到账时间的准确表述（1-3 个工作日）',
      '未检索到关于无理由秒退的限制条款',
    ],
    recommendations: [
      '在知识库中补充退款政策的详细说明，包括到账时间、无理由退货限制等。',
      '在生成流程中增加事实校验步骤，确保输出与检索内容一致。',
      '在 prompt 中强制要求模型引用参考材料的具体条款，避免编造。',
    ],
  }
}

// 手动触发：用固定样例跑一遍 Judge（用于离线演示或验证渲染）
async function demoJudge() {
  demoLoading.value = true
  const req = {
    input_text: '我们的会员系统支持哪些退款方式？退款多久到账？',
    output_text: '根据知识库：本平台支持原路退回和余额退回两种方式。退款将在 24 小时内到账。' +
      '此外，平台还支持"无理由秒退"——用户无需任何理由可在 7 天内一键全额退款，' +
      '并且退款会额外赠送 5% 的优惠券作为补偿。',
    reference: '会员退款规则：支持原路退回、余额退回。审核通过后 1-3 个工作日到账。不支持无理由秒退。',
    feature: 'rag_qa',
  }
  let payload = null
  try {
    const data = await evalCenterAPI.judge(req)
    payload = data.success === true ? data.data : data
  } catch (e) {
    // 后端不可达（如未登录/无 token）→ 用离线样例展示渲染效果
    payload = buildOfflineDemo()
  } finally {
    demoLoading.value = false
  }
  if (payload && payload.overall !== undefined) {
    demoTrace.value = {
      ...payload,
      input_text: req.input_text,
      output_text: req.output_text,
      retrieved_docs: [{ source: '会员退款规则.md', score: 0.91, content: req.reference }],
      feature: req.feature,
      created_at: new Date().toISOString(),
      trace_id: payload.trace_id || ('demo-' + Date.now()),
      model: 'deepseek-chat',
      latency_ms: 0,
      token_usage: 0,
    }
    loadDashboard()
    if (!isTracking.value) {
      ElMessage.success('样例评测完成，综合分：' + payload.overall + '（含幻觉定位）')
    }
  } else if (!isTracking.value) {
    ElMessage.error('评测失败')
  }
}

// 自动追踪核心：轮询后端真实 AI 调用事件，只有用户使用 AI 功能才刷新
async function pollEvents() {
  if (pollLoading.value) return
  pollLoading.value = true
  try {
    const data = await evalCenterAPI.poll(lastEventMs.value)
    if (data.new) {
      lastEventMs.value = data.latest_ms || lastEventMs.value
      // 有新事件时刷新面板和记录列表
      await loadDashboard()
      await loadRecords()
      // 静默模式下不弹 toast，避免短周期刷屏
      if (!isTracking.value && data.count) {
        ElMessage.info(`检测到 ${data.count} 条新的 AI 调用，已刷新看板`)
      }
    }
  } catch (e) {
    // 自动追踪失败时不弹窗刷屏，只打印日志
    console.warn('[EvalCenter] 轮询失败', e)
  } finally {
    pollLoading.value = false
  }
}

function openLatestReplay() {
  // 优先打开最新真实事件；没有事件时 fallback 到手动样例
  if (records.value.length) {
    openDetail(records.value[0])
    return
  }
  demoLoading.value = true
  demoJudge().then(() => {
    demoLoading.value = false
    if (demoTrace.value?.trace_id) {
      router.push({ name: 'TraceReplay', params: { traceId: demoTrace.value.trace_id } })
    }
  })
}

function restartAutoRefresh() {
  if (isTracking.value) {
    if (trackingTimer) {
      clearInterval(trackingTimer)
      trackingTimer = null
    }
    pollEvents()
    trackingTimer = setInterval(() => {
      if (!isTracking.value) return
      pollEvents()
    }, refreshInterval.value * 1000)
  }
}

function toggleAutoRefresh() {
  if (autoRefresh.value) {
    startTracking()
  } else {
    stopTracking()
  }
}

function startTracking() {
  isTracking.value = true
  autoRefresh.value = true
  localStorage.setItem('eval-center-auto-refresh', 'true')
  localStorage.setItem('eval-center-refresh-interval', String(refreshInterval.value))
  const sec = refreshInterval.value
  const label = sec < 60 ? `${sec} 秒` : `${Math.round(sec / 60)} 分钟`
  ElMessage({ type: 'info', message: `已开启自动追踪，每 ${label} 静默刷新一次（仅在使用 AI 功能时更新）`, duration: 2000 })
  // 立即执行一次轮询，并启动定时器
  pollEvents()
  trackingTimer = setInterval(() => {
    if (!isTracking.value) return
    pollEvents()
  }, refreshInterval.value * 1000)
}

function stopTracking() {
  isTracking.value = false
  autoRefresh.value = false
  localStorage.setItem('eval-center-auto-refresh', 'false')
  if (trackingTimer) {
    clearInterval(trackingTimer)
    trackingTimer = null
  }
}

function scoreClass(score) {
  if (score >= 85) return 'score-excellent'
  if (score >= 60) return 'score-good'
  return 'score-poor'
}

function scoreTag(score) {
  if (score >= 85) return 'success'
  if (score >= 60) return 'warning'
  return 'danger'
}


function barColor(score) {
  if (score >= 85) return '#4ade80'
  if (score >= 60) return '#fbbf24'
  return '#f87171'
}

function ringColor(percentage) {
  return barColor(percentage)
}

const dimList = [
  { key: 'overall', label: '综合分' },
  { key: 'hallucination', label: '幻觉率' },
  { key: 'consistency', label: '一致性' },
  { key: 'completeness', label: '完整性' },
  { key: 'executability', label: '可执行性' },
  { key: 'safety', label: '安全性' },
]

function scoreOf(key) {
  const v = dashboard.value.avg_scores[key]
  return typeof v === 'number' ? v : 0
}

function initCharts() {
  const refs = [radarRef.value, trendRef.value]
  const ready = refs.every(el => el && el.offsetHeight > 0 && el.offsetWidth > 0)
  if (!ready) {
    setTimeout(initCharts, 300)
    return
  }
  initRadar()
  initTrend()
}

function initRadar() {
  if (!radarRef.value) return
  radarChart?.dispose()
  radarChart = echarts.init(radarRef.value, null, { renderer: 'canvas' })
  const s = dashboard.value.avg_scores
  const dims = ['幻觉率', '一致性', '完整性', '可执行性', '安全性']
  const values = [s.hallucination, s.consistency, s.completeness, s.executability, s.safety]
  const option = {
    color: ['#818cf8'],
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(15,23,42,0.95)',
      borderColor: 'rgba(148,163,184,0.2)',
      textStyle: { color: '#e2e8f0' },
      formatter: () => {
        return dims.map((name, i) => `${name}: <strong>${values[i] ?? 0}</strong>`).join('<br/>')
      },
    },
    radar: {
      indicator: dims.map(name => ({ name, max: 100 })),
      radius: '35%',
      axisName: {
        color: '#94a3b8',
        formatter: (name, indicator) => {
          const idx = dims.indexOf(name)
          return `{name|${name}}\n{score|${values[idx] ?? 0}}`
        },
        rich: {
          name: { color: '#94a3b8', fontSize: 12, lineHeight: 16 },
          score: { color: '#e2e8f0', fontSize: 14, fontWeight: 'bold', lineHeight: 18 },
        },
      },
      splitArea: { areaStyle: { color: ['rgba(148,163,184,0.06)', 'rgba(148,163,184,0.12)'] } },
      axisLine: { lineStyle: { color: 'rgba(148,163,184,0.25)' } },
      splitLine: { lineStyle: { color: 'rgba(148,163,184,0.2)' } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: values,
        name: '平均分',
      }],
      areaStyle: { opacity: 0.25, color: '#818cf8' },
      lineStyle: { width: 3 },
      symbol: 'circle',
      symbolSize: 6,
      label: { show: false },
    }],
  }
  radarChart.setOption(option)
}

// 后端 hour 字段是 UTC（day 聚合: "2026-08-18"；hour 聚合: "2026-08-18T13"）。
// 这里按浏览器本地时区解析并格式化为短标签。
function formatTrendLabel(item) {
  const hour = typeof item === 'string' ? item : (item?.hour || '')
  const latestAt = typeof item === 'string' ? null : item?.latest_at
  if (!hour) return ''
  function toLocalLabel(iso) {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return null
    const pad = n => String(n).padStart(2, '0')
    return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:00`
  }
  // 月度聚合："2026-08"
  if (/^\d{4}-\d{2}$/.test(hour)) {
    return hour
  }
  // 优先用 latest_at（完整 ISO 时间），按本地时区解析
  if (latestAt) {
    const label = toLocalLabel(latestAt)
    if (label) return label
  }
  // 小时聚合：hour 形如 "2026-08-19T00"
  if (/^\d{4}-\d{2}-\d{2}T\d{2}$/.test(hour)) {
    const label = toLocalLabel(`${hour}:00:00Z`)
    if (label) return label
  }
  return hour
}

function initTrend() {
  if (!trendRef.value) return
  trendChart?.dispose()
  // 只保留有数据的坐标点，让标签正好落在数据正下方
  const trend = (dashboard.value.trend || []).filter(t => (t.count || 0) > 0)
  if (trend.length === 0) {
    trendChart = null
    return
  }
  trendChart = echarts.init(trendRef.value, null, { renderer: 'canvas' })
  const x = trend.map(t => formatTrendLabel(t))
  const rawHours = trend.map(t => t.latest_at || t.hour)
  const avg = trend.map(t => (t.avg_overall == null ? null : Number(t.avg_overall)))
  const count = trend.map(t => Number(t.count) || 0)
  const maxCount = Math.max(...count, 1)
  const single = trend.length === 1
  const rotate = x.length > 6 ? 35 : 0

  const series = [
    {
      name: '平均综合分',
      type: 'line',
      data: avg,
      smooth: true,
      lineStyle: { width: single ? 0 : 3 },
      symbol: 'circle',
      symbolSize: single ? 14 : 4,
      itemStyle: { color: '#60a5fa', borderColor: '#fff', borderWidth: single ? 2 : 0 },
      label: {
        show: true,
        position: 'top',
        color: '#e2e8f0',
        fontSize: single ? 12 : 10,
        formatter: p => (p.value == null ? '' : p.value),
        distance: 8,
      },
    },
    {
      name: '评测次数',
      type: 'scatter',
      yAxisIndex: 1,
      data: count,
      symbol: 'circle',
      symbolSize: value => Math.min(12, Math.max(5, Math.sqrt(value || 0) * 2)),
      itemStyle: { color: 'rgba(52,211,153,0.85)', shadowBlur: 3, shadowColor: 'rgba(52,211,153,0.25)' },
      label: {
        show: true,
        position: 'top',
        color: '#e2e8f0',
        fontSize: 10,
        formatter: p => (p.value > 0 ? p.value : ''),
        distance: 5,
      },
    },
  ]

  const option = {
    color: ['#60a5fa', '#34d399'],
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15,23,42,0.95)',
      borderColor: 'rgba(148,163,184,0.2)',
      textStyle: { color: '#e2e8f0' },
      formatter: params => {
        const idx = params[0].dataIndex
        const time = rawHours[idx] || params[0].name
        let html = `<div style="font-weight:600;margin-bottom:4px">${time}</div>`
        params.forEach(p => {
          if (p.value == null) return
          html += `<div style="display:flex;align-items:center;gap:6px">
            <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color}"></span>
            <span>${p.seriesName}：${p.value}</span>
          </div>`
        })
        return html
      },
    },
    legend: { data: ['平均综合分', '评测次数'], bottom: 0, textStyle: { color: '#94a3b8' } },
    grid: { top: 12, left: 32, right: 40, bottom: 18, containLabel: true },
    xAxis: {
      type: 'category',
      data: x,
      axisTick: { alignWithLabel: true },
      axisLabel: { interval: 0, rotate, color: '#94a3b8' },
      axisLine: { lineStyle: { color: 'rgba(148,163,184,0.25)' } },
    },
    yAxis: [
      { type: 'value', name: '分数', min: 0, max: 100, axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: 'rgba(148,163,184,0.1)' } } },
      { type: 'value', name: '次数', min: 0, max: Math.ceil(maxCount * 1.2), axisLabel: { color: '#94a3b8' }, splitLine: { show: false } },
    ],
    series,
  }
  trendChart.setOption(option)
}

function openLangfuse() {
  if (langfuse.value.traces_url) {
    window.open(langfuse.value.traces_url, '_blank')
  }
}

function onExport(cmd) {
  if (cmd === 'csv') return exportCSV()
  if (cmd === 'json') return exportJSON()
  return exportReport()
}

function openTrace(traceId) {
  if (langfuse.value.host) {
    window.open(`${langfuse.value.host}/traces/${traceId}`, '_blank')
  }
}

function onResize() {
  radarChart?.resize()
  trendChart?.resize()
}

onMounted(() => {
  loadDashboard()
  loadLangfuseConfig()
  loadRecords()
  window.addEventListener('resize', onResize)
  if (autoRefresh.value) {
    startTracking()
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  radarChart?.dispose()
  trendChart?.dispose()
  // 只清 timer，不重置 autoRefresh：状态由 localStorage 持久化，切回页面可恢复
  if (trackingTimer) {
    clearInterval(trackingTimer)
    trackingTimer = null
  }
  isTracking.value = false
})
</script>

<style scoped>
.detail-wrap { color: #e2e8f0; }
.detail-head { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 4px; }
.trace-steps { margin: 8px 0 4px; }
.doc-list { display: flex; flex-direction: column; gap: 10px; }
.doc-item { background: rgba(148,163,184,0.08); border: 1px solid rgba(148,163,184,0.18); border-radius: 10px; padding: 10px 12px; }
.doc-meta { display: flex; gap: 10px; align-items: center; font-size: 12px; color: #94a3b8; margin-bottom: 6px; }
.doc-idx { background: #6366f1; color: #fff; border-radius: 6px; padding: 0 6px; font-weight: 700; }
.doc-score { color: #34d399; }
.doc-content { font-size: 13px; line-height: 1.6; white-space: pre-wrap; color: #cbd5e1; }
.dim-bars { display: flex; flex-direction: column; gap: 10px; }
.dim-bar-item { display: flex; align-items: center; gap: 12px; }
.dim-bar-name { width: 80px; font-size: 13px; color: #cbd5e1; flex-shrink: 0; }
.dim-bar-item :deep(.el-progress) { flex: 1; }
.dim-bar-val { width: 40px; text-align: right; font-weight: 700; }
.reason-box { margin-top: 14px; background: rgba(99,102,241,0.10); border-left: 3px solid #6366f1; border-radius: 8px; padding: 10px 12px; }
.reason-title { font-size: 13px; color: #a5b4fc; margin-bottom: 6px; font-weight: 600; }
.reason-box p { margin: 0; font-size: 13px; line-height: 1.6; color: #e2e8f0; white-space: pre-wrap; }
.io-block { margin-bottom: 12px; }
.io-label { font-size: 12px; color: #94a3b8; margin-bottom: 4px; }
.io-text { background: rgba(15,23,42,0.6); border: 1px solid rgba(148,163,184,0.15); border-radius: 8px; padding: 10px 12px; font-size: 12px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; max-height: 200px; overflow: auto; margin: 0; }
.meta-line { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
.header-actions { display: flex; align-items: center; gap: 8px; }
.record-model { font-size: 12px; color: #e2e8f0; line-height: 1.4; }
.record-meta { font-size: 11px; color: #94a3b8; line-height: 1.3; }
.score-excellent { color: #4ade80; }
.score-good { color: #fbbf24; }
.score-poor { color: #f87171; }
.recorder-title { color: #f0abfc; font-weight: 600; }
.recorder-subtitle { font-size: 12px; color: #c4b5fd; margin: 10px 0 6px; font-weight: 600; }
.issue-list { display: flex; flex-direction: column; gap: 8px; }
.issue-card { background: rgba(15,23,42,0.55); border: 1px solid rgba(148,163,184,0.18); border-left-width: 4px; border-radius: 8px; padding: 10px 12px; }
.issue-card.sev-high { border-left-color: #f87171; }
.issue-card.sev-medium { border-left-color: #fbbf24; }
.issue-card.sev-low { border-left-color: #60a5fa; }
.issue-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.issue-loc { font-size: 12px; color: #94a3b8; }
.issue-row { display: flex; gap: 8px; font-size: 12.5px; line-height: 1.6; margin-bottom: 4px; }
.issue-key { flex: 0 0 64px; color: #818cf8; font-weight: 600; }
.issue-claim { color: #fca5a5; flex: 1; }
.issue-evi { color: #e2e8f0; flex: 1; }
.issue-fix .issue-sug { color: #86efac; flex: 1; }
.gap-block, .rec-block { margin-top: 6px; }
.gap-list, .rec-list { margin: 0; padding-left: 18px; }
.gap-list li, .rec-list li { font-size: 12.5px; line-height: 1.7; color: #e2e8f0; }
.gap-list li { color: #fcd34d; }
.rec-list li { color: #a5f3fc; }

/* 横向执行链路流程图 */
.trace-flow {
  display: flex;
  align-items: stretch;
  gap: 0;
  padding: 12px 4px 24px;
  overflow-x: auto;
}

.trace-flow-item {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 160px;
  max-width: 260px;
  cursor: pointer;
  position: relative;
  padding-top: 10px;
}

.trace-flow-card {
  flex: 1;
  min-height: 130px;
  padding: 14px 12px 12px;
  border-radius: 12px;
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.15);
  box-shadow: 0 4px 12px rgba(2, 6, 23, 0.2);
  transition: all 0.2s ease;
}

.trace-flow-item:hover .trace-flow-card {
  transform: translateY(-2px);
  border-color: rgba(56, 189, 248, 0.4);
  box-shadow: 0 8px 24px rgba(2, 6, 23, 0.35);
}

.trace-flow-item.is-problem .trace-flow-card {
  border-color: rgba(248, 113, 113, 0.55);
  background: rgba(69, 26, 26, 0.35);
  box-shadow: 0 0 16px rgba(248, 113, 113, 0.18);
}

.trace-flow-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.trace-flow-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  color: #fff;
}

.trace-flow-icon.success { background: linear-gradient(135deg, #22c55e, #16a34a); }
.trace-flow-icon.primary { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.trace-flow-icon.danger { background: linear-gradient(135deg, #ef4444, #dc2626); }

.trace-flow-title-block {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.trace-flow-title {
  font-weight: 600;
  font-size: 14px;
  color: #e2e8f0;
}

.trace-flow-subtitle {
  font-size: 11.5px;
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.workstation-no {
  position: absolute;
  top: -9px;
  left: 8px;
  z-index: 2;
  padding: 1px 7px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 600;
  color: #0f172a;
  background: linear-gradient(135deg, #38bdf8, #22d3ee);
  box-shadow: 0 2px 6px rgba(56, 189, 248, 0.25);
}

.trace-flow-warn {
  flex-shrink: 0;
}

/* 按底座工位类型着色边框，像工厂流水线区分不同工位 */
.trace-flow-item.trace-type-route .trace-flow-card { border-top: 3px solid #3b82f6; }
.trace-flow-item.trace-type-llm .trace-flow-card { border-top: 3px solid #22c55e; }
.trace-flow-item.trace-type-tool .trace-flow-card { border-top: 3px solid #f59e0b; }
.trace-flow-item.trace-type-retrieve .trace-flow-card { border-top: 3px solid #a855f7; }
.trace-flow-item.trace-type-db .trace-flow-card { border-top: 3px solid #ec4899; }
.trace-flow-item.trace-type-judge .trace-flow-card { border-top: 3px solid #eab308; }
.trace-flow-item.trace-type-input .trace-flow-card { border-top: 3px solid #64748b; }

.trace-flow-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 10px;
}

.trace-flow-line {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.45);
  font-size: 12px;
  line-height: 1.5;
}

.trace-flow-line.trace-flow-input-line {
  border-left: 2px solid rgba(56, 189, 248, 0.5);
}

.trace-flow-line.trace-flow-output-line {
  border-left: 2px solid rgba(34, 197, 94, 0.5);
}

.trace-flow-line.trace-flow-empty {
  color: #64748b;
  font-style: italic;
  justify-content: center;
  padding: 14px;
  background: rgba(15, 23, 42, 0.25);
}

.trace-flow-label {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  min-width: 30px;
  margin-top: 1px;
}

.trace-flow-text {
  flex: 1;
  color: #cbd5e1;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.trace-flow-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.trace-flow-meta .el-tag {
  margin: 0;
}

.trace-flow-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  flex-shrink: 0;
  color: #64748b;
}

.trace-flow-item.is-problem .trace-flow-arrow {
  color: #f87171;
}

/* AI 底座工位全景 */
.trace-panorama {
  padding: 8px 4px 20px;
}

.panorama-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 14px;
}

.panorama-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px;
  border-radius: 12px;
  background: rgba(30, 41, 59, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.12);
  transition: all 0.2s ease;
}

.panorama-card.is-used {
  border-color: rgba(34, 197, 94, 0.35);
  background: rgba(20, 83, 45, 0.12);
}

.panorama-card.is-unused {
  opacity: 0.65;
}

.panorama-card.is-unused .panorama-icon {
  filter: grayscale(0.5);
}

.panorama-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  color: #fff;
  flex-shrink: 0;
}

.panorama-info {
  flex: 1;
  min-width: 0;
}

.panorama-title {
  font-weight: 600;
  font-size: 14px;
  color: #e2e8f0;
  margin-bottom: 6px;
}

.panorama-desc {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.panorama-count,
.panorama-latency {
  font-size: 12px;
  color: #cbd5e1;
}

.panorama-detail {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  font-size: 11px;
  color: #94a3b8;
}

.panorama-detail span {
  background: rgba(15, 23, 42, 0.5);
  padding: 2px 6px;
  border-radius: 4px;
}

.panorama-hint {
  font-size: 11px;
  color: #64748b;
}

/* 节点诊断弹窗 */
:global(.el-dialog.step-detail-dialog),
:global(.step-detail-dialog .el-dialog) {
  background: #0f172a !important;
  border: 1px solid rgba(148, 163, 184, 0.2) !important;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.6) !important;
}
:global(.step-detail-dialog .el-dialog__header) {
  background: transparent !important;
  border-bottom: 1px solid rgba(148, 163, 184, 0.15) !important;
  padding-bottom: 14px !important;
}
:global(.step-detail-dialog .el-dialog__title) {
  color: #f8fafc !important;
  font-weight: 600 !important;
}
:global(.step-detail-dialog .el-dialog__body) {
  background: #0f172a !important;
  color: #e2e8f0 !important;
  padding-top: 10px !important;
}
:global(.step-detail-dialog .el-dialog__headerbtn .el-dialog__close) {
  color: #94a3b8 !important;
}
:global(.step-detail-dialog .el-dialog__headerbtn .el-dialog__close:hover) {
  color: #f8fafc !important;
}

.step-detail-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-detail-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  color: #fff;
}

.step-detail-icon.success { background: linear-gradient(135deg, #22c55e, #16a34a); }
.step-detail-icon.primary { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.step-detail-icon.danger { background: linear-gradient(135deg, #ef4444, #dc2626); }

.step-detail-title {
  font-weight: 600;
  font-size: 16px;
  color: #e2e8f0;
  margin-bottom: 6px;
}

.step-detail-status {
  display: flex;
  gap: 8px;
}

.step-detail-section {
  margin-bottom: 18px;
}

.step-detail-label {
  font-size: 13px;
  font-weight: 600;
  color: #94a3b8;
  margin-bottom: 8px;
}

.step-detail-output {
  margin: 0;
  padding: 10px;
  border-radius: 8px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 12.5px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 220px;
  overflow: auto;
}

.step-detail-metrics {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.step-detail-metric {
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(30, 41, 59, 0.5);
  font-size: 12px;
}

.step-detail-key {
  display: block;
  color: #94a3b8;
  margin-bottom: 4px;
}

.step-detail-val {
  color: #e2e8f0;
  word-break: break-all;
}

.step-detail-diagnosis,
.step-detail-solution {
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.7;
}

.step-detail-diagnosis {
  background: rgba(69, 26, 26, 0.55);
  border: 1px solid rgba(248, 113, 113, 0.35);
  color: #fecaca;
}

.step-detail-solution {
  background: rgba(12, 74, 110, 0.45);
  border: 1px solid rgba(56, 189, 248, 0.35);
  color: #bae6fd;
}

.ml-2 { margin-left: 8px; }

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.5; }
  100% { opacity: 1; }
}

.feat-cell { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.infra-badge { font-size: 10px; padding: 0 5px; line-height: 16px; height: 18px; }
</style>

<style scoped>
.eval-center {
  padding: 24px;
  min-height: 100vh;
  background: radial-gradient(1200px 600px at 80% -10%, #243049 0%, #1e293b 55%);
  color: #e2e8f0;
}

.hero {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 24px 28px;
  margin-bottom: 20px;
  background: linear-gradient(120deg, rgba(99,102,241,0.18) 0%, rgba(45,212,191,0.10) 100%);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 16px;
  box-shadow: 0 10px 30px rgba(2, 6, 23, 0.25);
}

.hero-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.title-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #fff;
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.35);
  flex-shrink: 0;
}

.hero-left h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #f8fafc;
  line-height: 1.3;
  letter-spacing: 0.5px;
}

.subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: #cbd5e1;
}

.hero-right {
  display: flex;
  align-items: center;
  gap: 24px;
}

.hero-right .health-ring {
  display: flex;
  align-items: center;
}

.ring-value {
  display: block;
  font-size: 26px;
  font-weight: 700;
  color: #f8fafc;
  line-height: 1;
}

.ring-label {
  display: block;
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.track-wrap {
  display: inline-flex;
  align-items: center;
  margin-left: 2px;
}

/* 自动追踪 switch：未开启时提高对比度，避免在深色背景下太暗 */
:deep(.track-switch .el-switch__core) {
  border-color: rgba(148, 163, 184, 0.5);
  background-color: rgba(30, 41, 59, 0.8);
}
:deep(.track-switch .el-switch__label) {
  color: #e2e8f0;
}
:deep(.track-switch.is-checked .el-switch__core) {
  border-color: #22c55e;
  background-color: #22c55e;
}
:deep(.track-switch.is-checked .el-switch__label) {
  color: #fff;
}

.track-dot {
  width: 9px;
  height: 9px;
  margin-left: 7px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7);
  animation: track-pulse 1.4s infinite;
}

@keyframes track-pulse {
  0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
  70% { box-shadow: 0 0 0 7px rgba(34, 197, 94, 0); }
  100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
}

.trend-header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.score-excellent { color: #4ade80; }
.score-good { color: #fbbf24; }
.score-poor { color: #f87171; }

.feat-card {
  background: #27354d;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(2, 6, 23, 0.2);
  color: #e2e8f0;
  margin-bottom: 16px;
}

.feat-card :deep(.el-card__header) {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.feat-card :deep(.el-card__body) {
  padding: 10px 14px 12px;
}

.card-sub {
  font-size: 12px;
  font-weight: 400;
  color: #94a3b8;
  margin-left: 10px;
}

.infra-layer-title {
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
  margin: 14px 0 6px;
  padding-left: 2px;
}

.feat-grid {
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
  padding: 8px 2px 2px;
  overflow-x: auto;
  scrollbar-width: thin;
}

.feat-grid::-webkit-scrollbar {
  height: 6px;
}

.feat-grid::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.3);
  border-radius: 3px;
}

.feat-grid.infra {
  padding-top: 4px;
}

.feat-item {
  flex: 1 1 0;
  min-width: 126px;
  max-width: 160px;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 10px;
  padding: 8px 10px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.feat-item:hover {
  transform: translateY(-2px);
  border-color: rgba(96, 165, 250, 0.55);
}

.feat-item.feat-active {
  border-color: #60a5fa;
  box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.25);
}

.feat-item.feat-warn {
  border-color: rgba(245, 108, 108, 0.6);
  background: rgba(127, 29, 29, 0.18);
}

.feat-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.feat-name {
  font-size: 12px;
  font-weight: 600;
  color: #f1f5f9;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.feat-count {
  font-size: 10px;
  color: #94a3b8;
  flex-shrink: 0;
  margin-left: 4px;
}

.feat-metrics {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
}

.feat-metric {
  display: flex;
  flex-direction: column;
}

.fm-label {
  font-size: 9px;
  color: #94a3b8;
}

.fm-value {
  font-size: 13px;
  font-weight: 700;
  color: #e2e8f0;
  line-height: 1.2;
}

.feat-infra {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-bottom: 4px;
  max-height: 36px;
  overflow: hidden;
}

.infra-chip {
  font-size: 9px !important;
  padding: 0 4px;
  height: 15px;
}

.dim-card {
  background: #27354d;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(2, 6, 23, 0.2);
  color: #e2e8f0;
  margin-bottom: 16px;
}

.dim-card.compact {
  margin-bottom: 14px;
}

.dim-card :deep(.el-card__header) {
  padding: 16px 20px;
  font-weight: 600;
  color: #f8fafc;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.dim-card.compact :deep(.el-card__header) {
  padding: 10px 16px;
}

.dim-card.compact :deep(.el-card__body) {
  padding: 10px 16px 12px;
}

.dim-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px 28px;
  padding: 8px 4px 4px;
}

.dim-grid.compact {
  gap: 8px 20px;
  padding: 0;
}

.dim-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dim-item.compact {
  gap: 4px;
}

.dim-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.dim-top.compact {
  line-height: 1.2;
}

.dim-name {
  font-size: 13px;
  color: #cbd5e1;
}

.dim-score {
  font-size: 16px;
  font-weight: 700;
}

.dim-top.compact .dim-score {
  font-size: 14px;
}

.chart-row {
  margin-bottom: 16px;
}

.chart-row.bottom-row {
  margin-top: 0;
  align-items: stretch;
}

.chart-row.bottom-row .el-col {
  display: flex;
}

.chart-row.bottom-row .chart-card {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.chart-row.bottom-row .chart-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.records-card :deep(.el-table) {
  flex: 1;
}

.records-card :deep(.el-table__body-wrapper) {
  max-height: none !important;
}

.chart-card {
  background: #27354d;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(2, 6, 23, 0.2);
  color: #e2e8f0;
}

.chart-card :deep(.el-card__header) {
  padding: 16px 20px;
  font-weight: 600;
  color: #f8fafc;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chart-box {
  position: relative;
  width: 100%;
  height: 170px;
  overflow: visible;
  min-width: 260px;
}

.trend-card .chart-box {
  height: 140px;
}

.chart-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  font-size: 15px;
  font-weight: 500;
  pointer-events: none;
}

.feature-card .chart-box,
.chart-card:has(.el-table) .chart-box {
  height: 240px;
}

.bottom-row {
  margin-top: 0;
}



.chart-card :deep(.el-table),
.chart-card :deep(.el-table__expanded-cell),
.chart-card :deep(.el-table th.el-table__cell),
.chart-card :deep(.el-table tr),
.chart-card :deep(.el-table td.el-table__cell) {
  background: transparent;
  color: #e2e8f0;
}

.chart-card :deep(.el-table th.el-table__cell) {
  background: rgba(15, 23, 42, 0.25);
  font-weight: 600;
  color: #f8fafc;
}

.chart-card :deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background: rgba(15, 23, 42, 0.15);
}

.chart-card :deep(.el-table__body tr:hover > td.el-table__cell) {
  background: rgba(99, 102, 241, 0.12);
}

.chart-card :deep(.el-table__empty-text) {
  color: #64748b;
}

/* 抽屉：减少遮罩雾化，增加内容对比度 */
:global(.el-overlay) {
  background-color: rgba(0, 0, 0, 0.55) !important;
}
:global(.el-drawer) {
  background: #0f172a !important;
  box-shadow: -12px 0 40px rgba(0, 0, 0, 0.55);
}
:global(.el-drawer__header) {
  color: #f8fafc !important;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  margin-bottom: 0;
  padding: 18px 20px;
  font-weight: 600;
}
:global(.el-drawer__body) {
  padding: 20px;
  color: #e2e8f0;
}
:global(.el-drawer__close-btn) {
  color: #94a3b8;
}
:global(.el-drawer__close-btn:hover) {
  color: #f8fafc;
}

@media (max-width: 768px) {
  .eval-center { padding: 16px; }
  .page-header { flex-direction: column; align-items: flex-start; }
}
</style>
