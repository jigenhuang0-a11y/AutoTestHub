<template>
  <div class="trace-replay">
    <div class="replay-header">
      <div class="replay-title">
        <el-button class="back-btn" text @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          返回评测中心
        </el-button>
        <div class="title-block">
          <h1>
            <el-icon><Connection /></el-icon>
            链路追踪回放
          </h1>
          <p class="subtitle">Trace ID: {{ traceId || '—' }}</p>
        </div>
      </div>
      <div class="replay-actions">
        <el-tag v-if="detail?.feature" effect="dark" round>
          {{ featureLabel(detail.feature) }}
        </el-tag>
        <el-tag v-if="detail?.status" :type="statusType(detail.status)" effect="plain" round>
          {{ detail.status }}
        </el-tag>
        <el-button v-if="langfuseHost" text type="primary" @click="openLangfuse">
          <el-icon><TopRight /></el-icon>
          Langfuse 打开
        </el-button>
      </div>
    </div>

    <div v-loading="loading" class="replay-body">
      <template v-if="detail">
        <!-- 顶部概览卡片 -->
        <div class="overview-row">
          <div class="overview-card">
            <div class="overview-label">模型</div>
            <div class="overview-value">{{ detail.model || '—' }}</div>
            <div v-if="detail.provider" class="overview-sub">{{ detail.provider }}</div>
          </div>
          <div class="overview-card">
            <div class="overview-label">耗时</div>
            <div class="overview-value">{{ detail.latency_ms }}ms</div>
          </div>
          <div class="overview-card">
            <div class="overview-label">Token 消耗</div>
            <div class="overview-value">{{ detail.metrics?.total_tokens || detail.token_usage || 0 }}</div>
            <div class="overview-sub">
              <span v-if="detail.metrics?.input_tokens != null">in {{ detail.metrics.input_tokens }}</span>
              <span v-if="detail.metrics?.output_tokens != null"> / out {{ detail.metrics.output_tokens }}</span>
              <span v-if="detail.metrics?.cost_usd"> · ${{ detail.metrics.cost_usd }}</span>
            </div>
          </div>
          <div class="overview-card">
            <div class="overview-label">综合分 / 幻觉率</div>
            <div class="overview-value">
              <span :class="scoreClass(detail.overall)">{{ detail.overall ?? 0 }}</span>
              <span class="sep">/</span>
              <span :class="scoreClass(100 - (detail.hallucination || 0))">{{ detail.hallucination ?? 0 }}</span>
            </div>
          </div>
          <div class="overview-card">
            <div class="overview-label">发生时间</div>
            <div class="overview-value">{{ formatTime(detail.created_at) }}</div>
          </div>
        </div>

        <!-- 输入输出原文 -->
        <el-card class="replay-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span><el-icon><Document /></el-icon> 输入输出原文</span>
            </div>
          </template>
          <div class="io-grid">
            <div class="io-block">
              <div class="io-label">输入</div>
              <pre class="io-text">{{ detail.input_text || detail.input_summary || '（无）' }}</pre>
            </div>
            <div class="io-block">
              <div class="io-label">输出</div>
              <pre class="io-text">{{ detail.output_text || detail.output_summary || '（无）' }}</pre>
            </div>
          </div>
        </el-card>

        <!-- 执行链路（横向流水线） -->
        <el-card class="replay-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span><el-icon><Link /></el-icon> 执行链路</span>
              <span class="card-sub">点击工位卡片查看节点诊断</span>
            </div>
          </template>
          <div class="trace-flow">
            <template v-for="(step, idx) in detail.trace_steps" :key="step.step_id || idx">
              <div
                class="trace-flow-item"
                :class="[
                  `trace-type-${step.type || 'input'}`,
                  { 'is-problem': isProblemStep(step, detail) }
                ]"
                @click="openStepDetail(step)"
              >
                <div class="workstation-no">工位 {{ idx + 1 }}</div>
                <div class="trace-flow-card">
                  <div class="trace-flow-header">
                    <div class="trace-flow-icon" :class="stepIconClass(step)">
                      <el-icon size="16"><component :is="stepIcon(step)" /></el-icon>
                    </div>
                    <div class="trace-flow-title-block">
                      <div class="trace-flow-title">{{ stepWorkstationName(step) }}</div>
                      <div class="trace-flow-subtitle">{{ step.title || stepTypeLabel(step.type) }}</div>
                    </div>
                    <el-icon v-if="isProblemStep(step, detail)" class="trace-flow-warn" color="#f87171" size="18"><WarningFilled /></el-icon>
                  </div>
                  <div class="trace-flow-body">
                    <div v-if="stepInputText(step)" class="trace-flow-line trace-flow-input-line">
                      <span class="trace-flow-label">IN</span>
                      <span class="trace-flow-text">{{ stepInputText(step) }}</span>
                    </div>
                    <div v-if="stepOutputText(step)" class="trace-flow-line trace-flow-output-line">
                      <span class="trace-flow-label">OUT</span>
                      <span class="trace-flow-text">{{ stepOutputText(step) }}</span>
                    </div>
                    <div v-if="!stepInputText(step) && !stepOutputText(step)" class="trace-flow-line trace-flow-empty">
                      该节点暂无输入输出摘要
                    </div>
                  </div>
                  <div class="trace-flow-meta">
                    <el-tag v-for="(tag, tIdx) in stepTags(step)" :key="tIdx" :type="tag.type" size="small" effect="plain">
                      {{ tag.label }}
                    </el-tag>
                  </div>
                </div>
              </div>
              <div v-if="idx < (detail.trace_steps || []).length - 1" class="trace-flow-arrow">
                <el-icon><ArrowRight /></el-icon>
              </div>
            </template>
            <el-empty v-if="!(detail.trace_steps || []).length" description="暂无执行链路数据" />
          </div>
        </el-card>

        <!-- AI 底座工位全景 -->
        <el-card class="replay-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span><el-icon><Grid /></el-icon> AI 底座工位全景</span>
            </div>
          </template>
          <div v-loading="panoramaLoading" class="trace-panorama">
            <div v-if="(tracePanorama || []).length" class="panorama-grid">
              <div
                v-for="item in tracePanorama"
                :key="item.feature"
                class="panorama-card"
                :class="item.used ? 'is-used' : 'is-unused'"
              >
                <div class="panorama-icon" :style="{ background: panoramaColor(item.feature) + '25', color: panoramaColor(item.feature) }">
                  <el-icon size="22"><component :is="panoramaIcon(item.feature)" /></el-icon>
                </div>
                <div class="panorama-info">
                  <div class="panorama-title">{{ item.label || panoramaLabel(item.feature) }}</div>
                  <div class="panorama-desc">
                    <el-tag v-if="item.used" type="success" size="small" effect="dark">已参与</el-tag>
                    <el-tag v-else type="info" size="small" effect="plain">未参与</el-tag>
                    <span v-if="item.used" class="panorama-count">调用 {{ item.count || 0 }} 次</span>
                    <span v-if="item.latency_ms" class="panorama-latency">{{ item.latency_ms }}ms</span>
                  </div>
                  <div class="panorama-detail">
                    <span v-if="item.model">模型: {{ item.model }}</span>
                    <span v-if="item.tool">工具: {{ item.tool }}</span>
                    <span v-if="item.tables">表: {{ Array.isArray(item.tables) ? item.tables.join(', ') : item.tables }}</span>
                    <span v-if="item.kb_id">KB: {{ item.kb_id }}</span>
                  </div>
                  <div v-if="!item.used" class="panorama-hint">本次追踪未调用该底座能力</div>
                </div>
              </div>
            </div>
            <el-empty v-else description="暂无底座工位数据" />
          </div>
        </el-card>

        <!-- 检索片段 / RAG Evidence -->
        <el-card v-if="(detail.retrieved_docs || []).length" class="replay-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span><el-icon><Files /></el-icon> 检索片段</span>
            </div>
          </template>
          <div class="doc-list">
            <div v-for="(doc, idx) in detail.retrieved_docs" :key="idx" class="doc-item">
              <div class="doc-meta">
                <span class="doc-idx">{{ idx + 1 }}</span>
                <span>{{ doc.source || doc.collection || '未知来源' }}</span>
                <span v-if="doc.score != null" class="doc-score">score: {{ Number(doc.score).toFixed(3) }}</span>
              </div>
              <div class="doc-content">{{ doc.content || doc.text || '（无内容）' }}</div>
            </div>
          </div>
        </el-card>

        <!-- Judge 维度评分 -->
        <el-card v-if="hasJudge(detail)" class="replay-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span><el-icon><Medal /></el-icon> Judge 多维度评分</span>
            </div>
          </template>
          <div class="dim-bars">
            <div v-for="dim in dimList" :key="dim.key" class="dim-bar-item">
              <span class="dim-bar-name">{{ dim.label }}</span>
              <el-progress
                :percentage="Math.round(detail[dim.key] || 0)"
                :color="barColor"
                :stroke-width="10"
                :show-text="false"
              />
              <span class="dim-bar-val" :class="scoreClass(detail[dim.key] || 0)">{{ detail[dim.key] || 0 }}</span>
            </div>
          </div>
          <div v-if="detail.reason" class="reason-box">
            <div class="reason-title">评分结论</div>
            <p>{{ detail.reason }}</p>
          </div>
        </el-card>

        <!-- 问题定位记录仪 -->
        <el-card v-if="(detail.issues || []).length" class="replay-card" shadow="never">
          <template #header>
            <div class="card-header recorder-title">
              <span><el-icon><WarningFilled /></el-icon> 问题定位记录仪</span>
            </div>
          </template>
          <div class="issue-list">
            <div v-for="(issue, idx) in detail.issues" :key="idx" class="issue-card" :class="`sev-${issue.severity || 'medium'}`">
              <div class="issue-head">
                <el-tag :type="sevTag(issue.severity)" size="small">{{ sevLabel(issue.severity) }}</el-tag>
                <span class="issue-loc">{{ issue.location || issue.dimension || '全局' }}</span>
              </div>
              <div class="issue-row"><span class="issue-key">Claim</span><span class="issue-claim">{{ issue.claim }}</span></div>
              <div class="issue-row"><span class="issue-key">Evidence</span><span class="issue-evi">{{ issue.evidence }}</span></div>
              <div class="issue-row"><span class="issue-key">Fix</span><span class="issue-sug">{{ issue.suggestion }}</span></div>
            </div>
          </div>
        </el-card>
      </template>

      <el-empty v-else-if="!loading" description="未找到该追踪记录" />
    </div>

    <!-- 节点诊断弹窗 -->
    <el-dialog
      v-model="stepDetailVisible"
      title="节点诊断"
      width="700px"
      align-center
      destroy-on-close
      class="step-detail-dialog"
      :close-on-click-modal="true"
    >
      <div v-if="selectedStep" class="step-detail">
        <div class="step-detail-head">
          <div class="step-detail-icon" :class="stepIconClass(selectedStep)">
            <el-icon size="22"><component :is="stepIcon(selectedStep)" /></el-icon>
          </div>
          <div>
            <div class="step-detail-title">{{ stepWorkstationName(selectedStep) }}</div>
            <div class="step-detail-status">
              <el-tag :type="stepStatusType(selectedStep)" effect="dark" round>
                {{ selectedStep.status || 'completed' }}
              </el-tag>
              <el-tag v-if="isProblemStep(selectedStep, detail)" type="danger" effect="plain" round>疑似异常</el-tag>
            </div>
          </div>
        </div>

        <div class="step-detail-section">
          <div class="step-detail-label">节点输入</div>
          <pre class="step-detail-output">{{ stepInputText(selectedStep) || '（无输入）' }}</pre>
        </div>
        <div class="step-detail-section">
          <div class="step-detail-label">节点输出</div>
          <pre class="step-detail-output">{{ stepOutputText(selectedStep) || '（无输出）' }}</pre>
        </div>

        <div class="step-detail-section">
          <div class="step-detail-label">关键指标</div>
          <div class="step-detail-metrics">
            <div v-for="(val, key) in stepMetrics(selectedStep)" :key="key" class="step-detail-metric">
              <span class="step-detail-key">{{ key }}</span>
              <span class="step-detail-val">{{ val }}</span>
            </div>
          </div>
        </div>

        <div class="step-detail-section">
          <div class="step-detail-label">为什么出问题？</div>
          <div class="step-detail-diagnosis">{{ stepDiagnosis(selectedStep, detail) }}</div>
        </div>
        <div class="step-detail-section">
          <div class="step-detail-label">建议方案</div>
          <div class="step-detail-solution">{{ stepSolution(selectedStep, detail) }}</div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { evalCenterAPI } from '@/api'
import {
  ArrowLeft, Connection, TopRight, Document, Link, Grid, Files, Medal, WarningFilled,
  User, Switch, Search, Cpu, Tools, Coin, CircleCheck, ArrowRight,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const traceId = ref('')
const eventId = ref('')
const loading = ref(false)
const detail = ref(null)
const tracePanorama = ref([])
const panoramaLoading = ref(false)
const selectedStep = ref(null)
const stepDetailVisible = ref(false)
const langfuseHost = ref('')

const stepIconMap = {
  input: User,
  route: Switch,
  retrieve: Search,
  prompt: Document,
  llm: Cpu,
  judge: Medal,
  tool: Tools,
  db: Coin,
}

const panoramaTypeMap = {
  llm_router: { icon: Switch, color: '#3b82f6', label: 'LLM 路由' },
  llm_call: { icon: Cpu, color: '#22c55e', label: 'LLM 生成' },
  tool_call: { icon: Tools, color: '#f59e0b', label: '工具调用' },
  tool_gateway: { icon: Link, color: '#f97316', label: 'MCP 网关' },
  vector_search: { icon: Search, color: '#a855f7', label: '向量检索' },
  db_query: { icon: Coin, color: '#ec4899', label: '数据库' },
  rag_query: { icon: Search, color: '#8b5cf6', label: 'RAG 检索' },
  memory: { icon: Files, color: '#14b8a6', label: '长短期记忆' },
  judge: { icon: Medal, color: '#eab308', label: 'Judge 评分' },
  knowledge_chat: { icon: Document, color: '#6366f1', label: 'AI 知识库问答' },
  requirement_review: { icon: User, color: '#f472b6', label: '需求评审' },
  ai_testcase: { icon: Document, color: '#38bdf8', label: 'AI 用例生成' },
  data_factory: { icon: Grid, color: '#fbbf24', label: '数据工厂' },
  api_test: { icon: Link, color: '#60a5fa', label: '接口测试' },
  ui_auto: { icon: Cpu, color: '#a78bfa', label: 'UI 自动化' },
  perf_test: { icon: WarningFilled, color: '#fb923c', label: '性能测试' },
}

const dimList = [
  { key: 'overall', label: '综合分' },
  { key: 'hallucination', label: '幻觉率' },
  { key: 'consistency', label: '一致性' },
  { key: 'completeness', label: '完整性' },
  { key: 'executability', label: '可执行性' },
  { key: 'safety', label: '安全性' },
]

function goBack() {
  router.push('/eval-center')
}

function featureLabel(feature) {
  const map = {
    knowledge_chat: 'AI 知识库问答',
    chat: 'AI 日常问答',
    fast_chat: 'AI 快速问答',
    rag_query: 'RAG 问答',
    ai_testcase: 'AI 用例生成',
    data_factory: '数据工厂',
    requirement_review: '需求评审',
    api_test: '接口测试',
    ui_auto: 'UI 自动化',
    perf_test: '性能测试',
    llm_router: 'LLM 路由决策',
    llm_call: 'LLM 生成',
    vector_search: '向量检索',
    tool_call: '工具调用',
    tool_gateway: 'MCP 网关',
    db_query: '数据库操作',
  }
  return map[feature] || feature || '未知'
}

function statusType(status) {
  if (status === 'failed' || status === 'error') return 'danger'
  if (status === 'judging') return 'warning'
  return 'success'
}

function scoreClass(score) {
  if (score >= 85) return 'score-excellent'
  if (score >= 60) return 'score-good'
  return 'score-poor'
}

function barColor(score) {
  if (score >= 85) return '#4ade80'
  if (score >= 60) return '#fbbf24'
  return '#f87171'
}

function formatTime(t) {
  if (!t) return '—'
  const d = new Date(t)
  if (isNaN(d.getTime())) return t
  return d.toLocaleString()
}

function hasJudge(row) {
  if (!row) return false
  return row.overall > 0 || Object.values({
    hallucination: row.hallucination,
    consistency: row.consistency,
    completeness: row.completeness,
    executability: row.executability,
    safety: row.safety,
  }).some(v => Number(v) > 0)
}

function sevLabel(sev) {
  return { high: '严重', medium: '中等', low: '轻微' }[sev] || '中等'
}
function sevTag(sev) {
  return { high: 'danger', medium: 'warning', low: 'info' }[sev] || 'warning'
}

function stepTypeLabel(type) {
  return {
    input: '用户输入', route: '路由决策', retrieve: '向量检索', prompt: 'Prompt 组装',
    llm: 'LLM 生成', judge: 'Judge 评分', tool: '工具调用', db: '数据库操作',
  }[type] || type || '节点'
}

function stepStatusType(step) {
  if (step.status === 'failed' || step.status === 'error') return 'danger'
  if (step.status === 'running') return 'primary'
  return 'success'
}

function stepIcon(step) {
  return stepIconMap[step.type] || CircleCheck
}

function stepIconClass(step) {
  const type = step.type || 'input'
  if (type === 'llm' || type === 'retrieve') return 'success'
  if (type === 'judge') return 'primary'
  if (type === 'route' || type === 'tool' || type === 'db') return 'primary'
  return 'success'
}

function isProblemStep(step, detailRow) {
  if (step.status === 'failed' || step.status === 'error') return true
  const m = step.metadata || {}
  if (step.type === 'judge' && (m.overall === 0 || m.overall === undefined)) return true
  if (step.type === 'llm' && (!m.token_usage || m.token_usage === 0)) return true
  if (step.type === 'llm' && m.latency_ms > 10000) return true
  if (step.type === 'retrieve' && (m.hit_count === 0 || m.hit_count === undefined)) return true
  if (step.type === 'route' && m.fallback) return true
  if (['tool', 'db'].includes(step.type) && (m.error || m.status === 'failed')) return true
  const needsJudge = detailRow && (detailRow.feature || detailRow.task_type) &&
    !['fast_chat'].includes(detailRow.feature || detailRow.task_type)
  if (needsJudge && detailRow.overall === 0 && ['llm', 'judge', 'route'].includes(step.type)) return true
  return false
}

function stepWorkstationName(step) {
  const m = step.metadata || {}
  if (step.type === 'route') return m.model || m.provider || 'LLM 路由'
  if (step.type === 'llm') return `${m.provider || 'LLM'} · ${m.model || 'unknown'}`
  if (step.type === 'tool') {
    if (m.tool) return `工具 · ${m.tool}`
    if (m.tool_name) return `工具 · ${m.tool_name}`
    if (m.gateway) return `网关 · ${m.gateway}`
    return '工具/MCP 调用'
  }
  if (step.type === 'retrieve') {
    if (m.kb_id) return `知识库 · ${m.kb_id}`
    if (m.collection) return `向量索引 · ${m.collection}`
    return '向量检索'
  }
  if (step.type === 'db') {
    const tables = Array.isArray(m.tables) ? m.tables.join(', ') : (m.table || 'sqlite')
    return `DB · ${tables}`
  }
  if (step.type === 'judge') return m.model ? `Judge · ${m.model}` : 'Judge 评分'
  return step.title || '节点'
}

function stepTags(step) {
  const m = step.metadata || {}
  const tags = []
  if (m.task_type && step.type === 'route') tags.push({ label: m.task_type, type: 'info' })
  if (m.model) tags.push({ label: m.model, type: 'success' })
  if (m.provider && !m.model) tags.push({ label: m.provider, type: 'success' })
  if (m.tool) tags.push({ label: m.tool, type: 'warning' })
  if (m.tool_name && !m.tool) tags.push({ label: m.tool_name, type: 'warning' })
  if (Array.isArray(m.tables) && m.tables.length) tags.push({ label: m.tables.join(','), type: 'danger' })
  if (m.kb_id) tags.push({ label: `KB:${m.kb_id}`, type: 'warning' })
  if (m.collection) tags.push({ label: m.collection, type: 'warning' })
  if (m.latency_ms) tags.push({ label: `${m.latency_ms}ms`, type: 'info' })
  if (m.token_usage) tags.push({ label: `${m.token_usage} token`, type: 'primary' })
  if (m.hit_count != null) tags.push({ label: `命中 ${m.hit_count}`, type: 'success' })
  if (m.fallback) tags.push({ label: 'fallback', type: 'danger' })
  return tags
}

function stepInputText(step) {
  if (step.input) return step.input
  if (step.type === 'input') return step.detail || ''
  if (step.type === 'route') return (step.metadata?.task_type) || ''
  if (step.type === 'tool') return step.metadata?.tool || step.metadata?.tool_name || ''
  if (step.type === 'retrieve') return step.metadata?.query || step.metadata?.kb_id || ''
  if (step.type === 'db') {
    const ops = step.metadata?.ops
    return ops ? `INSERT=${ops.insert} UPDATE=${ops.update} DELETE=${ops.delete}` : ''
  }
  return ''
}

function stepOutputText(step) {
  if (step.output) return step.output
  if (step.type === 'input') return step.detail || ''
  if (step.type === 'route') return (step.metadata?.reason) || (step.metadata?.model) || ''
  if (step.type === 'llm') return step.detail || (step.metadata?.route_reason) || ''
  if (step.type === 'tool') return step.metadata?.result || step.metadata?.status || ''
  if (step.type === 'retrieve') {
    const hit = step.metadata?.hit_count || 0
    const top = step.metadata?.top_score
    return `命中 ${hit} 条${top != null ? '，最高分 ' + top.toFixed(3) : ''}`
  }
  if (step.type === 'db') {
    const tables = Array.isArray(step.metadata?.tables) ? step.metadata.tables.join(', ') : ''
    return tables ? `涉及表: ${tables}` : '数据库写操作'
  }
  if (step.type === 'judge') return `综合 ${step.metadata?.overall || 0}`
  return step.detail || ''
}

function stepMetrics(step) {
  const m = step.metadata || {}
  const out = {}
  if (m.model) out['模型'] = m.model
  if (m.provider) out['供应商'] = m.provider
  if (m.latency_ms) out['耗时'] = `${m.latency_ms}ms`
  if (m.token_usage) out['Token'] = m.token_usage
  if (m.input_tokens != null) out['Input Tokens'] = m.input_tokens
  if (m.output_tokens != null) out['Output Tokens'] = m.output_tokens
  if (m.hit_count != null) out['命中数'] = m.hit_count
  if (m.top_score != null) out['最高相似分'] = m.top_score.toFixed(3)
  if (m.kb_id) out['知识库'] = m.kb_id
  if (m.collection) out['向量索引'] = m.collection
  if (m.tool) out['工具'] = m.tool
  if (m.tool_name) out['工具名'] = m.tool_name
  if (m.gateway) out['网关'] = m.gateway
  if (Array.isArray(m.tables) && m.tables.length) out['数据表'] = m.tables.join(', ')
  if (m.fallback) out['Fallback'] = '是'
  if (m.task_type) out['任务类型'] = m.task_type
  if (m.status) out['状态'] = m.status
  return out
}

function openStepDetail(step) {
  selectedStep.value = step
  stepDetailVisible.value = true
}

function stepDiagnosis(step, detailRow) {
  const m = step.metadata || {}
  if (step.status === 'failed' || step.status === 'error') {
    return `该步骤执行失败（status=${step.status}）。可能是模型接口异常、超时或依赖服务（如向量库、路由配置）不可用。`
  }
  if (step.type === 'judge' && (m.overall === 0 || m.overall === undefined)) {
    return 'Judge 评分返回 0 或未生成评分。常见原因：Judge LLM 未被触发、Judge prompt 未命中输出格式、或评分维度字段缺失。'
  }
  if (step.type === 'llm' && m.token_usage === 1) {
    return 'LLM 生成 token 数极少，疑似输出被截断、模型拒绝回答、或 max_tokens/temperature 设置过严。'
  }
  if (step.type === 'llm' && m.latency_ms > 10000) {
    return 'LLM 调用耗时超过 10 秒，存在明显延迟。可能当前模型负载高、网络抖动，或提示词过长导致首 token 时间增加。'
  }
  if (step.type === 'retrieve' && (m.hit_count === 0 || m.hit_count === undefined)) {
    return '检索未命中任何上下文片段。可能是知识库为空、向量相似度阈值过高、query 与文档差异大，或未走 RAG 路径。'
  }
  if (step.type === 'route' && m.fallback) {
    return '路由命中 fallback 模型。说明首选模型不可用、配额耗尽，或路由规则未覆盖当前 task_type。'
  }
  const needsJudge = detailRow && (detailRow.feature || detailRow.task_type) &&
    !['fast_chat'].includes(detailRow.feature || detailRow.task_type)
  if (needsJudge && detailRow.overall === 0 && ['llm', 'judge', 'route'].includes(step.type)) {
    return '本记录综合评分为 0，该步骤可能是导致未评分的环节，建议检查 Judge 执行链路或模型输出完整性。'
  }
  return '该步骤暂未发现明显异常。点击可查看详细指标与输出内容。'
}

function stepSolution(step, detailRow) {
  const m = step.metadata || {}
  if (step.status === 'failed' || step.status === 'error') {
    return '查看 ai-orchestrator 容器日志，定位模型/RAG/路由层的异常栈；确认 API Key、网络与依赖服务状态。'
  }
  if (step.type === 'judge' && (m.overall === 0 || m.overall === undefined)) {
    return '1) 检查 eval_loop.py 是否被触发；2) 确认 Judge prompt 要求返回 JSON 维度分数；3) 在日志中搜索 "Judge" 查看解析失败原因。'
  }
  if (step.type === 'llm' && m.token_usage === 1) {
    return '1) 提高 max_tokens；2) 检查 temperature/top_p 是否过低；3) 查看原始输出是否为空/截断；4) 必要时换模型重试。'
  }
  if (step.type === 'llm' && m.latency_ms > 10000) {
    return '1) 启用流式响应以提升首 token 体验；2) 缩短 prompt；3) 切换更低延迟模型；4) 检查网络与模型服务端负载。'
  }
  if (step.type === 'retrieve' && (m.hit_count === 0 || m.hit_count === undefined)) {
    return '1) 确认知识库已上传并建立索引；2) 调低向量检索阈值；3) 检查 query 编码器是否与索引一致；4) 如无需 RAG，可明确关闭 RAG 开关。'
  }
  if (step.type === 'route' && m.fallback) {
    return '1) 检查 model_configs 中首选模型配置是否生效；2) 查看路由表是否覆盖 task_type；3) 确认首选模型配额/网络正常。'
  }
  const needsJudge = detailRow && (detailRow.feature || detailRow.task_type) &&
    !['fast_chat'].includes(detailRow.feature || detailRow.task_type)
  if (needsJudge && detailRow.overall === 0 && ['llm', 'judge', 'route'].includes(step.type)) {
    return '从 LLM 生成输出、Judge 评分结果、路由选择三个方向排查，确保每个步骤都有有效输出且 Judge 能正确解析。'
  }
  return '保持当前配置，定期观察该步骤指标趋势。'
}

function panoramaIcon(feature) {
  return (panoramaTypeMap[feature] || {}).icon || CircleCheck
}
function panoramaColor(feature) {
  return (panoramaTypeMap[feature] || {}).color || '#64748b'
}
function panoramaLabel(feature) {
  return (panoramaTypeMap[feature] || {}).label || feature
}

async function loadLangfuseConfig() {
  try {
    const data = await evalCenterAPI.langfuseConfig()
    langfuseHost.value = data?.host || ''
  } catch {
    langfuseHost.value = ''
  }
}

function openLangfuse() {
  if (langfuseHost.value && traceId.value) {
    window.open(`${langfuseHost.value}/traces/${traceId.value}`, '_blank')
  }
}

function normalizeEventToRecord(ev) {
  const judge = ev.judge_output || ev.judge || {}
  const dims = judge.dimension_scores || ev.dimension_scores || {}
  const overall = judge.overall ?? dims['综合分'] ?? dims.overall ?? 0
  return {
    event_id: ev.event_id,
    feature: ev.feature,
    task_type: ev.task_type,
    input_text: ev.input_summary,
    output_text: ev.output_summary,
    input_summary: ev.input_summary,
    output_summary: ev.output_summary,
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
    reason: judge.summary || judge.reason || '',
    issues: judge.issues || ev.issues || [],
    created_at: ev.timestamp,
    status: ev.status,
    trace_steps: ev.trace_steps || [],
    metrics: ev.metrics || {},
  }
}

function isLegacyRecordId(id) {
  return id && (id.startsWith('local-') || id.startsWith('rec-'))
}

async function loadDetail() {
  loading.value = true
  detail.value = null
  tracePanorama.value = []
  try {
    let row = null
    // 优先用 event_id 加载
    if (eventId.value && !isLegacyRecordId(eventId.value)) {
      const ev = await evalCenterAPI.event(eventId.value)
      row = normalizeEventToRecord(ev)
    } else if (traceId.value) {
      // 只有 trace_id 时：先查事件列表，匹配 trace_id
      try {
        const data = await evalCenterAPI.events({ limit: 200, since_ms: 0 })
        const list = Array.isArray(data) ? data : (data.events || [])
        const ev = list.find(e => e.trace_id === traceId.value)
        if (ev) {
          row = normalizeEventToRecord(ev)
        }
      } catch (_) {}
    }
    detail.value = row
  } catch (e) {
    ElMessage.error('详情加载失败：' + (e.message || e))
  } finally {
    loading.value = false
  }
}

async function loadPanorama() {
  if (!traceId.value) return
  panoramaLoading.value = true
  try {
    const data = await evalCenterAPI.tracePanorama(traceId.value)
    tracePanorama.value = data?.components || []
  } catch (_) {
    tracePanorama.value = []
  } finally {
    panoramaLoading.value = false
  }
}

onMounted(async () => {
  traceId.value = route.params.traceId || route.query.trace_id || ''
  eventId.value = route.query.event_id || ''
  await loadLangfuseConfig()
  await loadDetail()
  await loadPanorama()
})
</script>

<style scoped>
.trace-replay {
  min-height: 100vh;
  background: radial-gradient(1200px 600px at 80% -10%, #243049 0%, #1e293b 55%);
  color: #e2e8f0;
  padding: 24px;
}

.replay-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
  padding: 20px 24px;
  background: linear-gradient(120deg, rgba(99,102,241,0.18) 0%, rgba(45,212,191,0.10) 100%);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 16px;
}

.replay-title {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  color: #cbd5e1;
  font-size: 14px;
}
.back-btn:hover { color: #fff; }

.title-block h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #f8fafc;
  display: flex;
  align-items: center;
  gap: 10px;
}

.subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  color: #94a3b8;
  font-family: monospace;
}

.replay-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.replay-body {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.overview-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.overview-card {
  background: #27354d;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  padding: 18px;
}

.overview-label {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 8px;
}

.overview-value {
  font-size: 20px;
  font-weight: 700;
  color: #f8fafc;
}

.overview-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #94a3b8;
}

.sep { margin: 0 6px; color: #64748b; }

.replay-card {
  background: #27354d;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  color: #e2e8f0;
}
.replay-card :deep(.el-card__header) {
  padding: 16px 20px;
  font-weight: 600;
  color: #f8fafc;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.card-sub {
  margin-left: auto;
  font-size: 12px;
  color: #94a3b8;
  font-weight: normal;
}

.io-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}
.io-label {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 6px;
}
.io-text {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 8px;
  padding: 12px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 260px;
  overflow: auto;
  margin: 0;
  color: #e2e8f0;
}

/* 执行链路 */
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
  min-width: 180px;
  max-width: 280px;
  cursor: pointer;
  position: relative;
  padding-top: 10px;
}

.trace-flow-card {
  flex: 1;
  min-height: 150px;
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

.trace-flow-title-block { flex: 1; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.trace-flow-title { font-weight: 600; font-size: 14px; color: #e2e8f0; }
.trace-flow-subtitle { font-size: 11.5px; color: #94a3b8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

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

.trace-flow-warn { flex-shrink: 0; }

.trace-type-route .trace-flow-card { border-top: 3px solid #3b82f6; }
.trace-type-llm .trace-flow-card { border-top: 3px solid #22c55e; }
.trace-type-tool .trace-flow-card { border-top: 3px solid #f59e0b; }
.trace-type-retrieve .trace-flow-card { border-top: 3px solid #a855f7; }
.trace-type-db .trace-flow-card { border-top: 3px solid #ec4899; }
.trace-type-judge .trace-flow-card { border-top: 3px solid #eab308; }
.trace-type-input .trace-flow-card { border-top: 3px solid #64748b; }

.trace-flow-body { display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px; }
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
.trace-flow-input-line { border-left: 2px solid rgba(56, 189, 248, 0.5); }
.trace-flow-output-line { border-left: 2px solid rgba(34, 197, 94, 0.5); }
.trace-flow-empty { color: #64748b; font-style: italic; justify-content: center; padding: 14px; background: rgba(15, 23, 42, 0.25); }
.trace-flow-label { flex-shrink: 0; font-size: 11px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; min-width: 30px; margin-top: 1px; }
.trace-flow-text { flex: 1; color: #cbd5e1; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.trace-flow-meta { display: flex; flex-wrap: wrap; gap: 6px; }
.trace-flow-meta .el-tag { margin: 0; }
.trace-flow-arrow { display: flex; align-items: center; justify-content: center; width: 28px; flex-shrink: 0; color: #64748b; }
.trace-flow-item.is-problem .trace-flow-arrow { color: #f87171; }

/* 底座工位全景 */
.trace-panorama { padding: 8px 4px 20px; }
.panorama-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
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
.panorama-card.is-used { border-color: rgba(34, 197, 94, 0.35); background: rgba(20, 83, 45, 0.12); }
.panorama-card.is-unused { opacity: 0.65; }
.panorama-card.is-unused .panorama-icon { filter: grayscale(0.5); }
.panorama-icon {
  display: flex; align-items: center; justify-content: center;
  width: 38px; height: 38px; border-radius: 10px; color: #fff; flex-shrink: 0;
}
.panorama-info { flex: 1; min-width: 0; }
.panorama-title { font-weight: 600; font-size: 14px; color: #e2e8f0; margin-bottom: 6px; }
.panorama-desc { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.panorama-count, .panorama-latency { font-size: 12px; color: #cbd5e1; }
.panorama-detail { display: flex; flex-wrap: wrap; gap: 4px; font-size: 11px; color: #94a3b8; }
.panorama-detail span { background: rgba(15, 23, 42, 0.5); padding: 2px 6px; border-radius: 4px; }
.panorama-hint { font-size: 11px; color: #64748b; }

/* 检索片段 */
.doc-list { display: flex; flex-direction: column; gap: 10px; }
.doc-item { background: rgba(148,163,184,0.08); border: 1px solid rgba(148,163,184,0.18); border-radius: 10px; padding: 10px 12px; }
.doc-meta { display: flex; gap: 10px; align-items: center; font-size: 12px; color: #94a3b8; margin-bottom: 6px; }
.doc-idx { background: #6366f1; color: #fff; border-radius: 6px; padding: 0 6px; font-weight: 700; }
.doc-score { color: #34d399; }
.doc-content { font-size: 13px; line-height: 1.6; white-space: pre-wrap; color: #cbd5e1; }

/* 维度评分 */
.dim-bars { display: flex; flex-direction: column; gap: 10px; }
.dim-bar-item { display: flex; align-items: center; gap: 12px; }
.dim-bar-name { width: 80px; font-size: 13px; color: #cbd5e1; flex-shrink: 0; }
.dim-bar-item :deep(.el-progress) { flex: 1; }
.dim-bar-val { width: 40px; text-align: right; font-weight: 700; }
.reason-box { margin-top: 14px; background: rgba(99,102,241,0.10); border-left: 3px solid #6366f1; border-radius: 8px; padding: 10px 12px; }
.reason-title { font-size: 13px; color: #a5b4fc; margin-bottom: 6px; font-weight: 600; }
.reason-box p { margin: 0; font-size: 13px; line-height: 1.6; color: #e2e8f0; white-space: pre-wrap; }

/* 问题定位 */
.recorder-title { color: #f0abfc; font-weight: 600; }
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
.issue-sug { color: #86efac; flex: 1; }

/* 节点诊断弹窗 */
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
:global(.step-detail-dialog .el-dialog__title) { color: #f8fafc !important; font-weight: 600 !important; }
:global(.step-detail-dialog .el-dialog__body) { background: #0f172a !important; color: #e2e8f0 !important; padding-top: 10px !important; }
:global(.step-detail-dialog .el-dialog__headerbtn .el-dialog__close) { color: #94a3b8 !important; }
:global(.step-detail-dialog .el-dialog__headerbtn .el-dialog__close:hover) { color: #f8fafc !important; }

.step-detail-head { display: flex; align-items: center; gap: 12px; }
.step-detail-icon { display: flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 10px; color: #fff; }
.step-detail-icon.success { background: linear-gradient(135deg, #22c55e, #16a34a); }
.step-detail-icon.primary { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.step-detail-icon.danger { background: linear-gradient(135deg, #ef4444, #dc2626); }
.step-detail-title { font-weight: 600; font-size: 16px; color: #e2e8f0; margin-bottom: 6px; }
.step-detail-status { display: flex; gap: 8px; }
.step-detail-section { margin-bottom: 18px; }
.step-detail-label { font-size: 13px; font-weight: 600; color: #94a3b8; margin-bottom: 8px; }
.step-detail-output { margin: 0; padding: 10px; border-radius: 8px; background: #0f172a; color: #e2e8f0; font-size: 12.5px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; max-height: 220px; overflow: auto; }
.step-detail-metrics { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.step-detail-metric { padding: 8px 10px; border-radius: 6px; background: rgba(30, 41, 59, 0.5); font-size: 12px; }
.step-detail-key { display: block; color: #94a3b8; margin-bottom: 4px; }
.step-detail-val { color: #e2e8f0; word-break: break-all; }
.step-detail-diagnosis, .step-detail-solution { padding: 10px 12px; border-radius: 8px; font-size: 13px; line-height: 1.7; }
.step-detail-diagnosis { background: rgba(69, 26, 26, 0.55); border: 1px solid rgba(248, 113, 113, 0.35); color: #fecaca; }
.step-detail-solution { background: rgba(12, 74, 110, 0.45); border: 1px solid rgba(56, 189, 248, 0.35); color: #bae6fd; }

.score-excellent { color: #4ade80; }
.score-good { color: #fbbf24; }
.score-poor { color: #f87171; }

@media (max-width: 900px) {
  .io-grid { grid-template-columns: 1fr; }
  .overview-row { grid-template-columns: repeat(2, 1fr); }
}
</style>
