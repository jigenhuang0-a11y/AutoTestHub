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
          </el-select>
          <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadDashboard">刷新</el-button>
          <el-button :type="isTracking ? 'warning' : 'success'" :icon="isTracking ? RefreshLeft : VideoPlay" :loading="demoLoading" @click="toggleTracking">链路追踪回放</el-button>
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

    <!-- 顶部指标卡 -->
    <el-row :gutter="16" class="metric-row">
      <el-col :xs="24" :sm="12" :md="6">
        <div class="metric-card">
          <div class="metric-icon blue">
            <el-icon :size="24"><Collection /></el-icon>
          </div>
          <div class="metric-body">
            <div class="metric-value">{{ dashboard.total_records }}</div>
            <div class="metric-label">近 {{ hours }}h 评测样本</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <div class="metric-card">
          <div class="metric-icon purple">
            <el-icon :size="24"><Medal /></el-icon>
          </div>
          <div class="metric-body">
            <div class="metric-value" :class="scoreClass(dashboard.avg_scores.overall)">
              {{ dashboard.avg_scores.overall }}
            </div>
            <div class="metric-label">平均综合分</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <div class="metric-card">
          <div class="metric-icon orange">
            <el-icon :size="24"><View /></el-icon>
          </div>
          <div class="metric-body">
            <div class="metric-value" :class="scoreClass(dashboard.avg_scores.hallucination)">
              {{ dashboard.avg_scores.hallucination }}
            </div>
            <div class="metric-label">平均幻觉率得分</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <div class="metric-card">
          <div class="metric-icon teal">
            <el-icon :size="24"><Grid /></el-icon>
          </div>
          <div class="metric-body">
            <div class="metric-value">{{ Object.keys(dashboard.by_feature).length }}</div>
            <div class="metric-label">覆盖业务模块</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 维度评分条 -->
    <el-card shadow="never" class="dim-card">
      <template #header>
        <div class="card-header">
          <span>多维度质量评分</span>
          <el-tag size="small" :type="scoreTag(dashboard.avg_scores.overall)">
            综合 {{ dashboard.avg_scores.overall }}
          </el-tag>
        </div>
      </template>
      <div class="dim-grid">
        <div v-for="d in dimList" :key="d.key" class="dim-item">
          <div class="dim-top">
            <span class="dim-name">{{ d.label }}</span>
            <span class="dim-score" :class="scoreClass(scoreOf(d.key))">{{ scoreOf(d.key) }}</span>
          </div>
          <el-progress
            :percentage="scoreOf(d.key)"
            :stroke-width="10"
            :show-text="false"
            :color="barColor(scoreOf(d.key))"
          />
        </div>
      </div>
    </el-card>

    <!-- 图表区 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :xs="24" :lg="8">
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
      <el-col :xs="24" :lg="16">
        <el-card shadow="never" class="chart-card trend-card">
          <template #header>
            <div class="card-header">
              <span>综合分趋势（近 {{ hours }}h · {{ dashboard.granularity === 'day' ? '按天' : '按小时' }}）</span>
              <el-tag size="small" type="info">{{ dashboard.trend.length }} 个时间点</el-tag>
            </div>
          </template>
          <div ref="trendRef" class="chart-box">
            <div v-if="isTrendEmpty" class="chart-empty">暂无评测数据</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="chart-row bottom-row">
      <el-col :xs="24" :lg="12" class="bottom-left">
        <el-card shadow="never" class="chart-card feature-card">
          <template #header>
            <div class="card-header">
              <span>模块覆盖 & 平均分</span>
              <el-tag size="small" type="info">{{ Object.keys(dashboard.by_feature).length }} 个模块</el-tag>
            </div>
          </template>
          <div ref="featureRef" class="chart-box">
            <div v-if="isFeatureEmpty" class="chart-empty">暂无模块数据</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12" class="bottom-right">
        <el-card shadow="never" class="chart-card records-card">
          <template #header>
            <div class="card-header">
              <span>最近评测记录</span>
              <div class="header-actions">
                <el-tag size="small" type="info">{{ records.length }} 条</el-tag>
                <el-button size="small" link type="primary" @click="loadRecords">刷新</el-button>
              </div>
            </div>
          </template>
          <el-table :data="records" size="default" max-height="340" stripe @row-click="openDetail">
            <el-table-column prop="feature" label="模块" width="120" show-overflow-tooltip>
              <template #default="{ row }">
                <el-tag size="small" effect="plain">{{ featureLabel(row.feature) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="综合" width="70" align="center">
              <template #default="{ row }">
                <el-tag :type="scoreTag(row.overall)" size="small">{{ row.overall }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="幻觉" width="70" align="center">
              <template #default="{ row }">
                <span :class="scoreClass(row.hallucination)">{{ row.hallucination }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="Judge 结论" show-overflow-tooltip />
            <el-table-column label="操作" width="140" align="center">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click.stop="openDetail(row)">详情</el-button>
                <el-button v-if="row.trace_id && langfuse?.enabled" link type="info" size="small" @click.stop="openTrace(row.trace_id)">Trace</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 待优化样本队列 -->
    <el-card shadow="never" class="queue-card">
      <template #header>
        <div class="card-header">
          <span>🎯 待优化样本队列（低分自动归集）</span>
          <el-tag size="small" type="danger">{{ lowScoreRecords.length }} 条待复核</el-tag>
        </div>
      </template>
      <el-table :data="lowScoreRecords" size="default" max-height="320" stripe empty-text="暂无低分样本，质量良好 🎉">
        <el-table-column prop="feature" label="模块" width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ featureLabel(row.feature) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="综合" width="70" align="center">
          <template #default="{ row }"><el-tag :type="scoreTag(row.overall)" size="small">{{ row.overall }}</el-tag></template>
        </el-table-column>
        <el-table-column label="幻觉" width="70" align="center">
          <template #default="{ row }"><span :class="scoreClass(row.hallucination)">{{ row.hallucination }}</span></template>
        </el-table-column>
        <el-table-column prop="reason" label="Judge 结论" show-overflow-tooltip />
        <el-table-column label="问题归类" width="180">
          <template #default="{ row }">
            <el-select v-model="row.annotation" size="small" placeholder="标记问题" @change="onAnnotate(row)" @click.stop>
              <el-option label="检索片段缺失" value="retrieval_missing" />
              <el-option label="模型幻觉" value="hallucination" />
              <el-option label="问题模糊" value="ambiguous_input" />
              <el-option label="参考答案错误" value="bad_reference" />
              <el-option label="已修复" value="resolved" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click.stop="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 说明 -->
    <el-card shadow="never" class="info-card">
      <div class="info-grid">
        <div class="info-item">
          <div class="info-title">评测机制</div>
          <p>每次 LLM 调用自动上报 Langfuse trace；Judge LLM 基于幻觉率、一致性、完整性、可执行性、安全性五个维度打分，分数同步写入 Langfuse Score。</p>
        </div>
        <div class="info-item">
          <div class="info-title">部署位置</div>
          <p>Langfuse 服务运行在阿里云 ECS Docker 中，本页面读取后端聚合数据，可直接下钻到原始 Trace 进行人工复核。</p>
        </div>
      </div>
    </el-card>

    <!-- 评测详情抽屉：RAG 链路回放 -->
    <el-drawer v-model="detailVisible" title="链路追踪回放" size="46%" :destroy-on-close="true">
      <div v-if="detail" class="detail-wrap">
        <div class="detail-head">
          <el-tag effect="plain">{{ featureLabel(detail.feature) }}</el-tag>
          <el-tag :type="scoreTag(detail.overall)">综合 {{ detail.overall }}</el-tag>
          <el-tag type="info">{{ formatTime(detail.created_at) }}</el-tag>
          <el-button v-if="detail.trace_id && langfuse?.enabled" size="small" type="info" @click="openTrace(detail.trace_id)">在 Langfuse 打开</el-button>
        </div>

        <el-divider>执行链路</el-divider>
        <el-steps :active="3" align-center finish-status="success" class="trace-steps">
          <el-step title="用户提问" :description="truncate(detail.input_text, 60)" />
          <el-step title="RAG 检索" :description="(detail.retrieved_docs || []).length + ' 个片段'" />
          <el-step title="Judge 评分" :description="'综合 ' + detail.overall" />
        </el-steps>

        <el-divider>检索上下文（RAG 引用）</el-divider>
        <div v-if="(detail.retrieved_docs || []).length" class="doc-list">
          <div v-for="(doc, i) in detail.retrieved_docs" :key="i" class="doc-item">
            <div class="doc-meta">
              <span class="doc-idx">#{{ i + 1 }}</span>
              <span class="doc-src">{{ doc.source || '知识库' }}</span>
              <span class="doc-score">相关度 {{ doc.score ?? '—' }}</span>
            </div>
            <div class="doc-content">{{ doc.content }}</div>
          </div>
        </div>
        <el-empty v-else description="该记录无检索上下文（非 RAG 路径）" :image-size="60" />

        <el-divider>Judge 评分明细</el-divider>
        <div class="dim-bars">
          <div v-for="d in dimList" :key="d.key" class="dim-bar-item">
            <span class="dim-bar-name">{{ d.label }}</span>
            <el-progress :percentage="detail[d.key] || 0" :stroke-width="12" :show-text="false" :color="barColor(detail[d.key] || 0)" />
            <span class="dim-bar-val" :class="scoreClass(detail[d.key] || 0)">{{ detail[d.key] }}</span>
          </div>
        </div>
        <div class="reason-box">
          <div class="reason-title">Judge 结论</div>
          <p>{{ detail.reason || '（无说明）' }}</p>
        </div>

        <!-- 实时流水线记录仪：幻觉根因定位 + 修改建议 -->
        <template v-if="(detail.issues && detail.issues.length) || (detail.retrieval_gaps && detail.retrieval_gaps.length) || (detail.recommendations && detail.recommendations.length)">
          <el-divider content-position="left">
            <span class="recorder-title">🔍 幻觉/问题定位记录仪</span>
          </el-divider>

          <div v-if="detail.issues && detail.issues.length" class="issue-list">
            <div class="recorder-subtitle">问题定位清单（{{ detail.issues.length }}）</div>
            <div v-for="(iss, i) in detail.issues" :key="i" class="issue-card" :class="'sev-' + (iss.severity || 'medium')">
              <div class="issue-head">
                <el-tag :type="sevTag(iss.severity)" size="small">{{ sevLabel(iss.severity) }}</el-tag>
                <el-tag size="small" effect="plain">{{ dimLabel(iss.dimension) }}</el-tag>
                <span class="issue-loc">{{ iss.location || '未标注位置' }}</span>
              </div>
              <div class="issue-row"><span class="issue-key">问题陈述</span><span class="issue-claim">{{ iss.claim }}</span></div>
              <div class="issue-row"><span class="issue-key">事实依据</span><span class="issue-evi">{{ iss.evidence || '—' }}</span></div>
              <div class="issue-row issue-fix"><span class="issue-key">修改建议</span><span class="issue-sug">{{ iss.suggestion || '—' }}</span></div>
            </div>
          </div>

          <div v-if="detail.retrieval_gaps && detail.retrieval_gaps.length" class="gap-block">
            <div class="recorder-subtitle">检索缺口（RAG 漏召回）</div>
            <ul class="gap-list">
              <li v-for="(g, i) in detail.retrieval_gaps" :key="i">{{ g }}</li>
            </ul>
          </div>

          <div v-if="detail.recommendations && detail.recommendations.length" class="rec-block">
            <div class="recorder-subtitle">工程优化建议</div>
            <ul class="rec-list">
              <li v-for="(r, i) in detail.recommendations" :key="i">{{ r }}</li>
            </ul>
          </div>
        </template>

        <el-divider>输入输出原文</el-divider>
        <div class="io-block">
          <div class="io-label">用户提问</div>
          <pre class="io-text">{{ detail.input_text || '—' }}</pre>
        </div>
        <div class="io-block">
          <div class="io-label">AI 回答</div>
          <pre class="io-text">{{ detail.output_text || '—' }}</pre>
        </div>
        <div v-if="detail.model || detail.latency_ms || detail.token_usage" class="meta-line">
          <el-tag size="small" v-if="detail.model">模型 {{ detail.model }}</el-tag>
          <el-tag size="small" v-if="detail.latency_ms">耗时 {{ detail.latency_ms }}ms</el-tag>
          <el-tag size="small" v-if="detail.token_usage">Tokens {{ detail.token_usage }}</el-tag>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, RefreshLeft, VideoPlay, Link, Monitor, Collection, Medal, View, Grid, Download } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { evalCenterAPI } from '@/api'

const featureLabels = {
  ai_testcase: 'AI 用例生成',
  data_factory: '数据工厂',
  knowledge_chat: 'RAG 知识问答',
  chat: '智能对话',
  agent_loop: 'Agent 循环',
  unknown: '未分类',
}
const featureLabel = (f) => featureLabels[f] || f || '未分类'
const truncate = (s, n) => (s && s.length > n ? s.slice(0, n) + '…' : (s || ''))
function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z')
  if (isNaN(d.getTime())) return iso
  const pad = (x) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const hours = ref(24)
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
const detailVisible = ref(false)
const detail = ref(null)
const demoLoading = ref(false)
const isTracking = ref(false)
let trackingTimer = null
const LOW_OVERALL = 70
const LOW_HALLUCINATION = 60

const lowScoreRecords = computed(() =>
  records.value.filter(r =>
    (r.overall !== undefined && r.overall < LOW_OVERALL) ||
    (r.hallucination !== undefined && r.hallucination < LOW_HALLUCINATION)
  )
)

async function loadRecords() {
  recordsLoading.value = true
  try {
    const data = await evalCenterAPI.records({ hours: 720, limit: 100 })
    records.value = Array.isArray(data) ? data : (data.records || [])
  } catch (e) {
    ElMessage.error('记录加载失败：' + (e.message || e))
  } finally {
    recordsLoading.value = false
  }
}

function openDetail(row) {
  detail.value = row
  detailVisible.value = true
}

const annotations = ref({})  // trace_id -> 标注
function onAnnotate(row) {
  if (row.trace_id) {
    annotations.value[row.trace_id] = row.annotation
  }
  ElMessage.success('已标记：' + (row.annotation || ''))
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
    ...Object.entries(d.by_feature).map(([k, v]) => `  ${featureLabel(k)}：样本 ${v.count} | 平均分 ${v.avg_overall}`),
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

const isTrendEmpty = computed(() => !(dashboard.value.trend || []).length)
const isFeatureEmpty = computed(() => !Object.keys(dashboard.value.by_feature || {}).length)
// 单点兜底：趋势只有 1 个时间点时，隐藏柱状图、放大圆点并提示
const isSinglePoint = computed(() => (dashboard.value.trend || []).length === 1)

const radarRef = ref(null)
const trendRef = ref(null)
const featureRef = ref(null)
let radarChart = null
let trendChart = null
let featureChart = null

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
    // axios 拦截器已返回 response.data，无需再解构 { data }
    const data = await evalCenterAPI.dashboard(hours.value, 'auto')
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
    detail.value = {
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

function toggleTracking() {
  if (isTracking.value) {
    stopTracking()
  } else {
    startTracking()
  }
}

function startTracking() {
  isTracking.value = true
  detailVisible.value = true
  ElMessage.success('已开启链路追踪回放，每 8 秒自动刷新一次')
  // 立即执行一次
  demoJudge()
  // 循环追踪
  trackingTimer = setInterval(() => {
    if (!isTracking.value) return
    demoJudge()
  }, 8000)
}

function stopTracking() {
  isTracking.value = false
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

function sevLabel(sev) {
  return { high: '严重', medium: '中等', low: '轻微' }[sev] || '中等'
}
function sevTag(sev) {
  return { high: 'danger', medium: 'warning', low: 'info' }[sev] || 'warning'
}
function dimLabel(dim) {
  return {
    hallucination: '幻觉', consistency: '一致性', completeness: '完整性',
    executability: '可执行性', safety: '安全性',
  }[dim] || dim || '其他'
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
  const refs = [radarRef.value, trendRef.value, featureRef.value]
  const ready = refs.every(el => el && el.offsetHeight > 0 && el.offsetWidth > 0)
  if (!ready) {
    setTimeout(initCharts, 300)
    return
  }
  initRadar()
  initTrend()
  initFeature()
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
      radius: '60%',
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
function formatTrendLabel(hour) {
  if (!hour) return ''
  const hasTime = hour.includes('T')
  const iso = hasTime ? `${hour}:00:00Z` : `${hour}T00:00:00Z`
  const d = new Date(iso)
  if (isNaN(d.getTime())) return hour
  const pad = n => String(n).padStart(2, '0')
  const md = `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  return hasTime ? `${md} ${pad(d.getHours())}:00` : md
}

function initTrend() {
  if (!trendRef.value) return
  trendChart?.dispose()
  if (isTrendEmpty.value) {
    trendChart = null
    return
  }
  trendChart = echarts.init(trendRef.value, null, { renderer: 'canvas' })
  const trend = dashboard.value.trend || []
  const x = trend.map(t => formatTrendLabel(t.hour))
  const avg = trend.map(t => Number(t.avg_overall) || 0)
  const count = trend.map(t => Number(t.count) || 0)
  const maxCount = Math.max(...count, 1)

  const series = [
    {
      name: '平均综合分',
      type: 'line',
      data: avg,
      smooth: true,
      lineStyle: { width: isSinglePoint.value ? 0 : 3 },
      symbol: 'circle',
      symbolSize: isSinglePoint.value ? 22 : 8,
      itemStyle: { color: '#60a5fa', borderColor: '#fff', borderWidth: isSinglePoint.value ? 3 : 0 },
      label: { show: true, position: 'top', color: '#e2e8f0', fontSize: isSinglePoint.value ? 14 : 12, formatter: '{c}' },
    },
  ]
  // 单点时不画柱状图，避免遮挡折线；多点时才叠加评测次数柱状
  if (!isSinglePoint.value) {
    series.push({
      name: '评测次数',
      type: 'bar',
      yAxisIndex: 1,
      data: count,
      itemStyle: { borderRadius: [4, 4, 0, 0], color: 'rgba(52,211,153,0.55)' },
      barMaxWidth: 24,
      label: { show: true, position: 'top', color: '#e2e8f0', formatter: '{c}' },
    })
  }

  const option = {
    color: ['#60a5fa', '#34d399'],
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15,23,42,0.95)',
      borderColor: 'rgba(148,163,184,0.2)',
      textStyle: { color: '#e2e8f0' },
    },
    legend: { data: isSinglePoint.value ? ['平均综合分'] : ['平均综合分', '评测次数'], bottom: 0, textStyle: { color: '#94a3b8' } },
    grid: { top: 30, left: 40, right: 50, bottom: 40, containLabel: true },
    xAxis: { type: 'category', data: x, axisLabel: { rotate: 0, color: '#94a3b8' }, axisLine: { lineStyle: { color: 'rgba(148,163,184,0.25)' } } },
    yAxis: [
      { type: 'value', name: '分数', min: 0, max: 100, axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: 'rgba(148,163,184,0.1)' } } },
      { type: 'value', name: '次数', min: 0, max: Math.ceil(maxCount * 1.2), axisLabel: { color: '#94a3b8' }, splitLine: { show: false }, show: !isSinglePoint.value },
    ],
    series,
  }
  trendChart.setOption(option)
}

function initFeature() {
  if (!featureRef.value) return
  featureChart?.dispose()
  if (isFeatureEmpty.value) {
    featureChart = null
    return
  }
  featureChart = echarts.init(featureRef.value, null, { renderer: 'canvas' })
  const byFeature = dashboard.value.by_feature || {}
  const names = Object.keys(byFeature)
  const counts = names.map(n => byFeature[n].count)
  const avgs = names.map(n => byFeature[n].avg_overall)
  const option = {
    color: ['#fbbf24', '#2dd4bf'],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: 'rgba(15,23,42,0.95)', borderColor: 'rgba(148,163,184,0.2)', textStyle: { color: '#e2e8f0' } },
    legend: { data: ['评测次数', '平均综合分'], bottom: 0, textStyle: { color: '#94a3b8' } },
    grid: { top: 20, left: 40, right: 40, bottom: 40, containLabel: true },
    xAxis: { type: 'category', data: names, axisLabel: { interval: 0, rotate: 20, color: '#94a3b8' }, axisLine: { lineStyle: { color: 'rgba(148,163,184,0.25)' } } },
    yAxis: [
      { type: 'value', name: '次数', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: 'rgba(148,163,184,0.1)' } } },
      { type: 'value', name: '分数', max: 100, axisLabel: { color: '#94a3b8' }, splitLine: { show: false } },
    ],
    series: [
      { name: '评测次数', type: 'bar', data: counts, itemStyle: { borderRadius: [4, 4, 0, 0] } },
      { name: '平均综合分', type: 'line', yAxisIndex: 1, data: avgs, lineStyle: { width: 3 }, symbol: 'circle', symbolSize: 6 },
    ],
  }
  featureChart.setOption(option)
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
  featureChart?.resize()
}

onMounted(() => {
  loadDashboard()
  loadLangfuseConfig()
  loadRecords()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  radarChart?.dispose()
  trendChart?.dispose()
  featureChart?.dispose()
  stopTracking()
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

.metric-row {
  margin-bottom: 20px;
}

.metric-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: #27354d;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(2, 6, 23, 0.2);
  transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
}

.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(2, 6, 23, 0.3);
  border-color: rgba(148, 163, 184, 0.32);
}

.metric-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: 12px;
  flex-shrink: 0;
}

.metric-icon.blue { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.metric-icon.purple { background: rgba(139, 92, 246, 0.15); color: #a78bfa; }
.metric-icon.orange { background: rgba(249, 115, 22, 0.15); color: #fb923c; }
.metric-icon.teal { background: rgba(20, 184, 166, 0.15); color: #2dd4bf; }

.metric-body {
  flex: 1;
  min-width: 0;
}

.metric-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  color: #f8fafc;
}

.metric-label {
  margin-top: 4px;
  font-size: 13px;
  color: #94a3b8;
}

.score-excellent { color: #4ade80; }
.score-good { color: #fbbf24; }
.score-poor { color: #f87171; }

.dim-card {
  background: #27354d;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(2, 6, 23, 0.2);
  color: #e2e8f0;
  margin-bottom: 16px;
}

.dim-card :deep(.el-card__header) {
  padding: 16px 20px;
  font-weight: 600;
  color: #f8fafc;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.dim-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px 28px;
  padding: 8px 4px 4px;
}

.dim-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dim-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.dim-name {
  font-size: 13px;
  color: #cbd5e1;
}

.dim-score {
  font-size: 16px;
  font-weight: 700;
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
  height: 260px;
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

.info-card {
  background: #27354d;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(2, 6, 23, 0.2);
  color: #cbd5e1;
  margin-top: 16px;
}

.info-card :deep(.el-card__body) {
  padding: 20px 24px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
}

.info-title {
  font-size: 14px;
  font-weight: 600;
  color: #f8fafc;
  margin-bottom: 8px;
}

.info-item p {
  margin: 0;
  font-size: 13px;
  color: #94a3b8;
  line-height: 1.7;
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
  .metric-card { margin-bottom: 12px; }
}
</style>
