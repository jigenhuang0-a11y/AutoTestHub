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
          </el-select>
          <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadDashboard">刷新</el-button>
          <el-button type="success" :icon="VideoPlay" @click="demoJudge">触发样例评测</el-button>
          <el-button v-if="langfuse?.enabled" type="info" :icon="Link" @click="openLangfuse">打开 Langfuse</el-button>
          <el-button :icon="Download" @click="exportReport" :disabled="!dashboard.total_records">导出报告</el-button>
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
              <span>综合分趋势（近 {{ hours }}h）</span>
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
              <el-tag size="small" type="info">{{ dashboard.recent_records.length }} 条</el-tag>
            </div>
          </template>
          <el-table :data="dashboard.recent_records" size="default" max-height="100%" stripe>
            <el-table-column prop="overall" label="综合" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="scoreTag(row.overall)" size="small">{{ row.overall }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="hallucination" label="幻觉" width="80" align="center" />
            <el-table-column prop="reason" label="说明" show-overflow-tooltip />
            <el-table-column label="操作" width="90" align="center">
              <template #default="{ row }">
                <el-button v-if="row.trace_id && langfuse?.enabled" link type="primary" size="small" @click="openTrace(row.trace_id)">
                  Trace
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

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
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, VideoPlay, Link, Monitor, Collection, Medal, View, Grid, Download } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { evalCenterAPI } from '@/api'

const hours = ref(24)
const loading = ref(false)
const dashboard = ref({
  total_records: 0,
  avg_scores: { overall: 0, hallucination: 0, consistency: 0, completeness: 0, executability: 0, safety: 0 },
  by_feature: {},
  trend: [],
  recent_records: [],
})
const langfuse = ref({ enabled: false, host: '', traces_url: '' })

const isTrendEmpty = computed(() => !(dashboard.value.trend || []).length)
const isFeatureEmpty = computed(() => !Object.keys(dashboard.value.by_feature || {}).length)

const radarRef = ref(null)
const trendRef = ref(null)
const featureRef = ref(null)
let radarChart = null
let trendChart = null
let featureChart = null

const defaultScores = () => ({ overall: 0, hallucination: 0, consistency: 0, completeness: 0, executability: 0, safety: 0 })
const defaultDashboard = () => ({
  total_records: 0,
  avg_scores: defaultScores(),
  by_feature: {},
  trend: [],
  recent_records: [],
})

function normalizeDashboard(data) {
  const d = data || {}
  return {
    total_records: d.total_records ?? 0,
    avg_scores: { ...defaultScores(), ...(d.avg_scores || {}) },
    by_feature: d.by_feature || {},
    trend: Array.isArray(d.trend) ? d.trend : [],
    recent_records: Array.isArray(d.recent_records) ? d.recent_records : [],
  }
}

async function loadDashboard() {
  loading.value = true
  try {
    const { data } = await evalCenterAPI.dashboard(hours.value)
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
    const { data } = await evalCenterAPI.langfuseConfig()
    langfuse.value = data
  } catch {
    langfuse.value = { enabled: false }
  }
}

async function demoJudge() {
  try {
    const req = {
      input_text: '为电商订单系统生成 3 条测试用例，覆盖下单、取消、库存扣减。',
      output_text: '1. 用户选择商品并点击下单，系统应创建订单并扣减库存。\n2. 用户取消订单，系统应恢复库存。\n3. 库存不足时，系统应提示缺品并阻止下单。',
      reference: '订单系统需求：支持下单、取消、库存校验。',
      feature: 'ai_testcase',
    }
    const { data } = await evalCenterAPI.judge(req)
    if (data.success) {
      ElMessage.success('样例评测完成，综合分：' + data.data.overall)
      loadDashboard()
    } else {
      ElMessage.error(data.message || '评测失败')
    }
  } catch (e) {
    ElMessage.error('评测请求失败：' + (e.message || e))
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
    ...Object.entries(d.by_feature).map(([k, v]) => `  ${k}：样本 ${v.count} | 平均分 ${v.avg_overall}`),
    '',
    '【最近评测记录】',
    ...d.recent_records.map(r => `  [${r.overall}] ${r.feature} - ${r.reason || '（无说明）'}`),
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
  const option = {
    color: ['#818cf8'],
    radar: {
      indicator: [
        { name: '幻觉率', max: 100 },
        { name: '一致性', max: 100 },
        { name: '完整性', max: 100 },
        { name: '可执行性', max: 100 },
        { name: '安全性', max: 100 },
      ],
      radius: '60%',
      axisName: { color: '#94a3b8' },
      splitArea: { areaStyle: { color: ['rgba(148,163,184,0.06)', 'rgba(148,163,184,0.12)'] } },
      axisLine: { lineStyle: { color: 'rgba(148,163,184,0.25)' } },
      splitLine: { lineStyle: { color: 'rgba(148,163,184,0.2)' } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: [s.hallucination, s.consistency, s.completeness, s.executability, s.safety],
        name: '平均分',
      }],
      areaStyle: { opacity: 0.35, color: '#818cf8' },
      lineStyle: { width: 3 },
      symbol: 'circle',
      symbolSize: 6,
    }],
  }
  radarChart.setOption(option)
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
  const x = trend.map(t => t.hour?.replace('T', ' ') || '')
  const avg = trend.map(t => t.avg_overall)
  const count = trend.map(t => t.count)
  const option = {
    color: ['#60a5fa', '#34d399'],
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(15,23,42,0.95)', borderColor: 'rgba(148,163,184,0.2)', textStyle: { color: '#e2e8f0' } },
    legend: { data: ['平均综合分', '评测次数'], bottom: 0, textStyle: { color: '#94a3b8' } },
    grid: { top: 30, left: 40, right: 40, bottom: 40, containLabel: true },
    xAxis: { type: 'category', data: x, axisLabel: { rotate: 30, color: '#94a3b8' }, axisLine: { lineStyle: { color: 'rgba(148,163,184,0.25)' } } },
    yAxis: [
      { type: 'value', name: '分数', max: 100, axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: 'rgba(148,163,184,0.1)' } } },
      { type: 'value', name: '次数', axisLabel: { color: '#94a3b8' }, splitLine: { show: false } },
    ],
    series: [
      { name: '平均综合分', type: 'line', data: avg, smooth: true, lineStyle: { width: 3 }, areaStyle: { opacity: 0.15, color: '#60a5fa' }, symbol: 'circle', symbolSize: 6 },
      { name: '评测次数', type: 'bar', yAxisIndex: 1, data: count, itemStyle: { borderRadius: [4, 4, 0, 0] } },
    ],
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
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  radarChart?.dispose()
  trendChart?.dispose()
  featureChart?.dispose()
})
</script>

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

@media (max-width: 768px) {
  .eval-center { padding: 16px; }
  .page-header { flex-direction: column; align-items: flex-start; }
  .metric-card { margin-bottom: 12px; }
}
</style>
