<template>
  <div class="harness-page audit-dashboard">
    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-card" v-for="card in summaryCards" :key="card.label">
        <span class="stat-value" :style="{ color: card.color }">{{ card.value }}</span>
        <span class="stat-label">{{ card.label }}</span>
      </div>
    </div>

    <!-- 图表行 -->
    <div class="charts-row">
  <div class="chart-panel">
    <div class="panel-title">安全扫描趋势（近7天）</div>
    <div v-once ref="trendChartRef" class="chart"></div>
  </div>
  <div class="chart-panel">
    <div class="panel-title">风险等级分布</div>
    <div v-once ref="riskChartRef" class="chart"></div>
  </div>
    </div>

    <!-- 审计事件流 -->
    <div class="events-panel">
      <div class="panel-title">
        <span>审计事件流（最近 {{ displayEvents.length }} 条）</span>
        <div class="panel-actions">
          <el-tag size="small" type="info" style="margin-right:8px">
            实时 · 自动刷新
          </el-tag>
          <el-button size="small" @click="loadAll">刷新</el-button>
        </div>
      </div>
      <div v-if="displayEvents.length > 0" class="table-wrapper">
        <el-table :data="displayEvents" size="small" height="100%" row-key="id">
          <el-table-column prop="time" label="时间" width="150">
            <template #default="{ row }">{{ formatTime(row.time) }}</template>
          </el-table-column>
          <el-table-column prop="type" label="类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="typeTag(row.type)">{{ row.type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="severity" label="安全等级" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="row.severity === 'dangerous' ? 'danger' : row.severity === 'warning' ? 'warning' : 'success'">
                {{ severityLabel[row.severity] || row.severity || '-' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="user" label="用户" width="80" />
          <el-table-column prop="taskId" label="任务ID" width="130" />
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="row.status === 'error' || row.status === 'failed' ? 'danger' : 'success'">
                {{ row.status || '-' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="summary" label="摘要" show-overflow-tooltip />
        </el-table>
      </div>
      <div v-else class="empty-state">
        <el-icon :size="48" color="#94a3b8"><DataAnalysis /></el-icon>
        <p>暂无审计事件</p>
        <p class="empty-hint">去沙箱管控执行代码、MCP 工具网关测试工具、业务接入创建租户<br/>——每个操作都会自动生成审计事件</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { DataAnalysis } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { useAuditStore } from '@/stores/audit'
import { formatTime } from '@/utils/helpers'

const auditStore = useAuditStore()
const pollTimer = ref(null)

// ---- 统计卡片（响应式） ----
const summaryCards = computed(() => [
  { label: '总审计事件', value: auditStore.totalEvents, color: '#7dd3fc' },
  { label: '今日事件', value: auditStore.todayEvents, color: '#00ff88' },
  { label: '危险操作', value: auditStore.riskDist.dangerous, color: '#f87171' },
  { label: '警告', value: auditStore.riskDist.warning, color: '#fbbf24' },
  { label: '安全', value: auditStore.riskDist.safe, color: '#22d3ee' },
])

// 后端字段 → 前端展示字段 兼容映射
const displayEvents = computed(() => auditStore.events.map(e => ({
  ...e,
  time: e.created_at || e.timestamp || e.time,
  type: e.event_type || e.type,
  user: e.user_id || e.user,
  taskId: e.task_id || e.taskId,
  summary: e.message || e.summary,
  status: e.safety_passed === 1 ? '安全通过'
    : e.safety_passed === 0 ? '未通过'
    : (e.sandbox_status || '完成'),
})))

const severityLabel = { safe: '安全', warning: '警告', dangerous: '危险', info: '提示' }

function typeTag(type) {
  const t = (type || '').toString().toLowerCase()
  if (t.includes('sandbox') || t.includes('沙箱')) return ''
  if (t.includes('mcp') || t.includes('tool') || t.includes('工具')) return 'success'
  if (t.includes('tenant') || t.includes('接入')) return 'warning'
  if (t.includes('model') || t.includes('prompt') || t.includes('模型')) return 'info'
  if (t.includes('workflow') || t.includes('工作流')) return 'primary'
  if (t.includes('safety') || t.includes('安全')) return 'danger'
  return ''
}

// ---- 图表 ----
const trendChartRef = ref(null)
const riskChartRef = ref(null)
let trendChart = null
let riskChart = null
let resizeHandler = null

function renderTrend() {
  if (!trendChart) return
  const d = auditStore.trendData
  trendChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { data: ['通过', '拦截'], textStyle: { color: '#e2e8f0' }, top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '40px', containLabel: true },
    xAxis: {
      type: 'category', boundaryGap: false, data: d.labels,
      axisLine: { lineStyle: { color: 'rgba(64, 158, 255, 0.15)' } },
      axisLabel: { color: '#e2e8f0' },
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: 'rgba(64, 158, 255, 0.15)' } },
      axisLabel: { color: '#e2e8f0' },
      splitLine: { lineStyle: { color: 'rgba(64, 158, 255, 0.08)' } },
    },
    series: [
      { name: '通过', type: 'line', smooth: true, data: d.passed, itemStyle: { color: '#00ff88' }, areaStyle: { color: 'rgba(0,255,136,0.08)' } },
      { name: '拦截', type: 'line', smooth: true, data: d.blocked, itemStyle: { color: '#f87171' }, areaStyle: { color: 'rgba(248, 113, 113, 0.08)' } },
    ],
  }, true)
}

function renderRisk() {
  if (!riskChart) return
  const d = auditStore.riskDist
  riskChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    legend: { textStyle: { color: '#e2e8f0' }, bottom: 0 },
    series: [{
      type: 'pie', radius: ['40%', '70%'], center: ['50%', '45%'],
      data: [
        { value: d.safe, name: '安全', itemStyle: { color: '#00ff88' } },
        { value: d.warning, name: '警告', itemStyle: { color: '#fbbf24' } },
        { value: d.dangerous, name: '危险', itemStyle: { color: '#f87171' } },
      ],
      label: { color: '#e2e8f0' },
    }],
  }, true)
}

function loadAll() {
  renderTrend()
  renderRisk()
}

function initCharts() {
  if (trendChartRef.value) trendChart = echarts.init(trendChartRef.value)
  if (riskChartRef.value) riskChart = echarts.init(riskChartRef.value)
}

// 监听审计事件变化，自动刷新图表
watch(auditStore.events, () => {
  nextTick(() => { renderTrend(); renderRisk() })
}, { deep: true })

onMounted(async () => {
  await nextTick()
  initCharts()
  // 从后端拉取真实审计数据
  await auditStore.fetchEvents()
  loadAll()
  resizeHandler = () => { trendChart?.resize(); riskChart?.resize() }
  window.addEventListener('resize', resizeHandler)
  // 每 30 秒自动刷新
  pollTimer.value = setInterval(async () => {
    await auditStore.fetchEvents()
    renderTrend()
    renderRisk()
  }, 30000)
})

onBeforeUnmount(() => {
  if (pollTimer.value) clearInterval(pollTimer.value)
  trendChart?.dispose()
  riskChart?.dispose()
  trendChart = null
  riskChart = null
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
})
</script>

<style scoped>
.audit-dashboard {
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: relative;
  z-index: 1;
  height: calc(100vh - 56px - 32px); /* viewport - topbar - padding */
}

.audit-dashboard::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(64, 158, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(64, 158, 255, 0.03) 1px, transparent 1px);
  background-size: 40px 40px;
  z-index: 0;
  opacity: 0.4;
}

.stats-row, .charts-row, .events-panel, .stat-card, .chart-panel {
  position: relative;
  z-index: 1;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  flex: 0 0 auto;
}

.charts-row {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: 12px;
  flex: 0 0 auto;
}

.stat-card, .chart-panel, .events-panel {
  background: rgba(30, 41, 59, 0.9);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 16px !important;
  box-shadow: 0 2px 8px rgba(2, 8, 20, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
  
  contain: layout paint;
  transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s;
}

.stat-card {
  display: flex;
  flex-direction: column;
  padding: 16px;
}

.chart-panel {
  padding: 16px;
  min-height: 280px;
  display: flex;
  flex-direction: column;
}

.events-panel {
  padding: 16px;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.stat-value { font-size: 28px; font-weight: 700; }
.stat-label { font-size: 12px; color: #e2e8f0; margin-top: 4px; }
.panel-actions { display: flex; align-items: center; }
.chart { width: 100%; height: 220px; }
.table-wrapper { flex: 1; min-height: 0; overflow: hidden; display: flex; flex-direction: column; }

.stat-card:hover, .chart-panel:hover, .events-panel:hover {
  border-color: rgba(64, 158, 255, 0.45) !important;
  box-shadow: 0 12px 40px rgba(2, 132, 199, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.1) !important;
}

.stat-card::before, .chart-panel::before, .events-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, #409eff, #7dd3fc, transparent);
  border-radius: 16px 16px 0 0;
  opacity: 0.8;
  pointer-events: none;
}

.panel-title { color: #f8fafc !important; }

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #e2e8f0;
  gap: 8px;
  font-size: 13px;
}
.empty-hint {
  font-size: 12px;
  color: #94a3b8;
  text-align: center;
  line-height: 1.8;
}

:deep(.el-table) {
  flex: 1;
  min-height: 0;
  height: 100% !important;
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: rgba(30, 41, 59, 0.95);
  --el-table-row-hover-bg-color: rgba(64, 158, 255, 0.08);
  --el-table-border-color: rgba(64, 158, 255, 0.15);
  --el-table-text-color: #e2e8f0;
  --el-table-header-text-color: #e2e8f0;
  background-color: transparent !important;
}
:deep(.el-table tr) { background-color: transparent !important; }
:deep(.el-table th.el-table__cell),
:deep(.el-table td.el-table__cell) {
  background-color: transparent !important;
  border-bottom: 1px solid rgba(64, 158, 255, 0.08) !important;
}
:deep(.el-table th) { border-bottom: 1px solid rgba(64, 158, 255, 0.15); padding: 10px 8px; }
:deep(.el-table td) { border-bottom: 1px solid rgba(64, 158, 255, 0.08); padding: 8px; }
:deep(.el-table .el-table__empty-block) { background-color: transparent; color: #e2e8f0; }

@media (max-width: 1200px) {
  .stats-row { grid-template-columns: repeat(3, 1fr); }
  .charts-row { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .stats-row { grid-template-columns: repeat(2, 1fr); }
}
</style>
