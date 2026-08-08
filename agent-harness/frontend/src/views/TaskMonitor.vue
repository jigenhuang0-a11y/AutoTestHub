<template>
  <div class="harness-page task-monitor">
    <!-- 顶部统计卡片 -->
    <div class="stats-row">
      <div class="stat-card running">
        <div class="stat-icon"><el-icon><Loading /></el-icon></div>
        <div class="stat-body">
          <span class="stat-value">{{ stats.running }}</span>
          <span class="stat-label">运行中</span>
        </div>
      </div>
      <div class="stat-card pending">
        <div class="stat-icon"><el-icon><Clock /></el-icon></div>
        <div class="stat-body">
          <span class="stat-value">{{ stats.pending }}</span>
          <span class="stat-label">排队中</span>
        </div>
      </div>
      <div class="stat-card failed">
        <div class="stat-icon"><el-icon><CircleCloseFilled /></el-icon></div>
        <div class="stat-body">
          <span class="stat-value">{{ stats.failed }}</span>
          <span class="stat-label">失败</span>
        </div>
      </div>
      <div class="stat-card calls">
        <div class="stat-icon"><el-icon><TrendCharts /></el-icon></div>
        <div class="stat-body">
          <span class="stat-value">{{ stats.today_calls }}</span>
          <span class="stat-label">今日调用</span>
        </div>
      </div>
      <div class="stat-card latency">
        <div class="stat-icon"><el-icon><Timer /></el-icon></div>
        <div class="stat-body">
          <span class="stat-value">{{ stats.avg_latency }}<small>ms</small></span>
          <span class="stat-label">平均耗时</span>
        </div>
      </div>
      <div class="stat-card success">
        <div class="stat-icon"><el-icon><CircleCheckFilled /></el-icon></div>
        <div class="stat-body">
          <span class="stat-value">{{ stats.success_rate }}<small>%</small></span>
          <span class="stat-label">成功率</span>
        </div>
      </div>
    </div>

    <!-- 图表行 -->
    <div class="charts-row">
      <div class="chart-panel">
        <div class="panel-title">任务并发趋势（近7天）</div>
        <div ref="trendChart" class="chart-box"></div>
      </div>
      <div class="chart-panel">
        <div class="panel-title">沙箱资源占用</div>
        <div ref="sandboxChart" class="chart-box"></div>
      </div>
    </div>

    <!-- 任务列表 + 实时日志 -->
    <div class="bottom-row">
      <div class="table-panel">
        <div class="panel-title">
          <span>任务列表</span>
          <el-select v-model="taskFilter" size="small" class="filter-select" @change="fetchTasks">
            <el-option label="全部" value="" />
            <el-option label="执行中" value="running" />
            <el-option label="等待中" value="pending" />
            <el-option label="已完成" value="completed" />
            <el-option label="失败" value="failed" />
          </el-select>
        </div>
        <el-table :data="tasks" size="small" height="100%" row-key="id" @row-click="showTrace" empty-text="暂无任务，在业务平台发起 AI 用例生成或工具调用即可看到">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="task_type" label="类型" width="100">
            <template #default="{ row }">
              <el-tag :type="typeColor(row.task_type)" size="small">{{ row.task_type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="user_request" label="请求" min-width="200" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <span :class="'status-dot ' + row.status">
                {{ STATUS_MAP[row.status] || row.status }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="steps_count" label="步骤" width="70" />
          <el-table-column prop="duration_ms" label="耗时" width="90">
            <template #default="{ row }">{{ formatMs(row.duration_ms) }}</template>
          </el-table-column>
          <el-table-column prop="created_at" label="时间" width="160">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
        </el-table>
      </div>
      <div class="log-panel">
        <div class="panel-title">
          <span>实时日志</span>
          <el-tag size="small" type="success" effect="dark">审计事件驱动</el-tag>
        </div>
        <div class="log-area" ref="logArea">
          <div v-for="(log, i) in logs" :key="i" class="log-line">
            <span class="log-time">{{ log.time }}</span>
            <span :class="'log-level ' + log.level">[{{ log.level }}]</span>
            <span class="log-msg">{{ log.msg }}</span>
          </div>
          <div v-if="logs.length === 0" class="log-empty">
            <p>等待审计事件产生日志...</p>
            <p class="log-hint">去沙箱管控执行代码、MCP 工具网关测试工具即可看到日志</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { Loading, Clock, CircleCloseFilled, TrendCharts, Timer, CircleCheckFilled } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import api from '@/api'
import { useAuditStore } from '@/stores/audit'
import { formatTime, formatMs } from '@/utils/helpers'

const router = useRouter()
const auditStore = useAuditStore()
const pollTimer = ref(null)
const STATUS_MAP = { running: '执行中', pending: '等待中', completed: '已完成', failed: '失败' }

const stats = reactive({
  running: 0, pending: 0, failed: 0, completed: 0,
  today_calls: 0, avg_latency: 0, success_rate: 100,
})

const tasks = ref([])
const taskFilter = ref('')
const logs = ref([])

const trendChart = ref(null)
const sandboxChart = ref(null)
const logArea = ref(null)
let trendInstance = null
let sandboxInstance = null

function typeColor(t) {
  const m = { code_generation: 'success', testcase: 'warning', data_factory: 'info', evaluator: '' }
  return m[t] || ''
}

// ---- 审计事件 → 实时日志 ----
const severityLevel = { safe: 'INFO', warning: 'WARN', dangerous: 'ERROR' }

function auditToLog(event) {
  const timestamp = event.timestamp || event.created_at || event.time
  const t = timestamp ? new Date(timestamp) : new Date()
  const timeStr = t.toTimeString().slice(0, 8) + '.' + String(t.getMilliseconds()).padStart(3, '0')
  const severity = event.severity || event.risk_level || 'info'
  const summary = event.summary || event.description || event.event_type || 'Unknown'
  return {
    time: timeStr,
    level: severityLevel[severity] || 'INFO',
    msg: summary,
  }
}

// 初始化已有审计事件为日志
function syncLogsFromAudit() {
  logs.value = auditStore.events.slice(0, 80).map(auditToLog)
}

// 监听新审计事件
let unwatchAudit = null

// ---- API ----
async function fetchStats() {
  try {
    const res = await api.get('/agent/tasks/stats/')
    const data = res?.data || {}
    const d = data.data || data
    Object.assign(stats, d.summary || {})
    stats.today_calls = d.today_calls || 0
    stats.avg_latency = Math.round(d.avg_duration_ms || 0)
    stats.success_rate = d.success_rate || 100
    renderCharts(d.trend || [], d.sandbox_usage || [])
  } catch (e) {
    // 后端不可用，保持上次数据
    console.error('fetchStats error:', e)
    ElMessage.warning('获取统计数据失败，使用缓存数据')
  }
}

async function fetchTasks() {
  try {
    const params = { page_size: 50 }
    if (taskFilter.value) params.status = taskFilter.value
    const res = await api.get('/agent/tasks/', { params })
    const data = res?.data || {}
    const list = data.results || data.data?.items || data.items || []
    tasks.value = Array.isArray(list) ? list : []
  } catch (e) {
    console.error('fetchTasks error:', e)
    ElMessage.error('获取任务列表失败: ' + (e.response?.data?.detail || e.message))
    tasks.value = []
  }
}

function renderCharts(trendData, sandboxData) {
  nextTick(() => {
    if (trendInstance) trendInstance.dispose()
    if (trendChart.value) {
      trendInstance = echarts.init(trendChart.value)
      const labels = trendData.length > 0
        ? trendData.map(t => t.date)
        : auditStore.trendData.labels
      const totalSeries = trendData.length > 0
        ? trendData.map(t => t.total)
        : auditStore.trendData.passed.map((v, i) => v + auditStore.trendData.blocked[i])
      const successSeries = trendData.length > 0
        ? trendData.map(t => t.success)
        : auditStore.trendData.passed
      const failedSeries = trendData.length > 0
        ? trendData.map(t => t.failed)
        : auditStore.trendData.blocked

      trendInstance.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['总量', '成功', '失败'], textStyle: { color: '#e2e8f0' }, top: 0 },
        grid: { left: 40, right: 20, top: 40, bottom: 30 },
        xAxis: { type: 'category', data: labels, axisLine: { lineStyle: { color: 'rgba(64, 158, 255, 0.15)' } } },
        yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(64, 158, 255, 0.08)' } } },
        series: [
          { name: '总量', type: 'line', data: totalSeries, smooth: true, lineStyle: { color: '#7dd3fc' }, itemStyle: { color: '#7dd3fc' } },
          { name: '成功', type: 'line', data: successSeries, smooth: true, lineStyle: { color: '#00ff88' }, itemStyle: { color: '#00ff88' } },
          { name: '失败', type: 'line', data: failedSeries, smooth: true, lineStyle: { color: '#f87171' }, itemStyle: { color: '#f87171' } },
        ]
      })
    }
    if (sandboxInstance) sandboxInstance.dispose()
    if (sandboxChart.value) {
      sandboxInstance = echarts.init(sandboxChart.value)
      const sData = sandboxData.length > 0 ? sandboxData : []
      sandboxInstance.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['已用', '可用'], textStyle: { color: '#e2e8f0' }, top: 0 },
        grid: { left: 40, right: 20, top: 40, bottom: 30 },
        xAxis: { type: 'category', data: sData.map(s => s.name), axisLine: { lineStyle: { color: 'rgba(64, 158, 255, 0.15)' } } },
        yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(64, 158, 255, 0.08)' } } },
        series: [
          { name: '已用', type: 'bar', stack: 'total', data: sData.map(s => s.used), itemStyle: { color: '#7dd3fc' }, barWidth: 24 },
          { name: '可用', type: 'bar', stack: 'total', data: sData.map(s => s.total - s.used), itemStyle: { color: 'rgba(64, 158, 255, 0.08)' }, barWidth: 24 },
        ]
      })
    }
  })
}

function showTrace(row) {
  if (row && row.id) router.push(`/trace?taskId=${row.id}`)
}

onMounted(async () => {
  // 先从后端拉取真实审计事件
  await auditStore.fetchEvents()
  
  fetchStats()
  fetchTasks()
  syncLogsFromAudit()

  // 每10秒拉取新审计事件
  pollTimer.value = setInterval(async () => {
    await auditStore.fetchEvents()
    syncLogsFromAudit()
    fetchStats()
  }, 10000)

  // 实时监听新审计事件 → 日志
  unwatchAudit = watch(
    () => auditStore.events.length,
    (newLen, oldLen) => {
      if (newLen > oldLen) {
        // 有新事件
        const newEvents = auditStore.events.slice(0, newLen - oldLen)
        newEvents.forEach(e => {
          logs.value.unshift(auditToLog(e))
        })
        if (logs.value.length > 200) logs.value = logs.value.slice(0, 200)
        nextTick(() => {
          if (logArea.value) logArea.value.scrollTop = 0
        })
      }
    }
  )
})

onUnmounted(() => {
  if (pollTimer.value) clearInterval(pollTimer.value)
  if (trendInstance) trendInstance.dispose()
  if (sandboxInstance) sandboxInstance.dispose()
  if (unwatchAudit) unwatchAudit()
})
</script>

<style scoped>
.harness-page {
  background: #1a2d45;
  height: calc(100vh - 56px);
  min-height: 0;
  padding: 16px;
  color: #f1f5f9;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: relative;
}

.harness-page::before {
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

.stats-row, .charts-row, .bottom-row, .stat-card, .chart-panel, .table-panel, .log-panel {
  position: relative;
  z-index: 1;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-bottom: 12px;
  flex: 0 0 auto;
}

.stat-card, .chart-panel, .table-panel, .log-panel {
  background: rgba(30, 41, 59, 0.9);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 16px !important;
  box-shadow: 0 2px 8px rgba(2, 8, 20, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
  
  contain: layout paint;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
}

.stat-card::before, .chart-panel::before, .table-panel::before, .log-panel::before {
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

.stat-card:hover, .chart-panel:hover, .table-panel:hover, .log-panel:hover {
  border-color: rgba(64, 158, 255, 0.45) !important;
  box-shadow: 0 12px 40px rgba(2, 132, 199, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.1) !important;
}

.panel-title { color: #f8fafc !important; }

.stat-card .stat-icon {
  width: 38px; height: 38px;
  border-radius: 9px;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px;
}
.stat-card.running .stat-icon { background: rgba(64, 158, 255, 0.15); color: #7dd3fc; }
.stat-card.pending .stat-icon { background: rgba(251, 191, 36, 0.15); color: #fbbf24; }
.stat-card.failed .stat-icon { background: rgba(248, 113, 113, 0.15); color: #f87171; }
.stat-card.calls .stat-icon { background: rgba(52, 211, 153, 0.15); color: #34d399; }
.stat-card.latency .stat-icon { background: rgba(144, 147, 153, 0.15); color: #e2e8f0; }
.stat-card.success .stat-icon { background: rgba(0, 255, 136, 0.15); color: #00ff88; }

.stat-body { display: flex; flex-direction: column; }
.stat-value { font-size: 20px; font-weight: 700; color: #fff; }
.stat-value small { font-size: 12px; font-weight: 400; color: #e2e8f0; margin-left: 2px; }
.stat-label { font-size: 11px; color: #e2e8f0; margin-top: 2px; }

.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
  flex: 0 0 auto;
}

.chart-panel {
  background: rgba(30, 41, 59, 0.9);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
}
.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;
  margin-bottom: 8px;
  display: flex; align-items: center; justify-content: space-between;
}
.chart-box { height: 200px; }

.bottom-row {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: 12px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.table-panel, .log-panel {
  background: rgba(30, 41, 59, 0.9);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 8px;
  padding: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.filter-select { width: 110px; }

:deep(.el-table) {
  flex: 1;
  min-height: 0;
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: rgba(30, 41, 59, 0.95);
  --el-table-row-hover-bg-color: rgba(64, 158, 255, 0.08);
  --el-table-border-color: rgba(64, 158, 255, 0.15);
  --el-table-text-color: #e2e8f0;
  --el-table-header-text-color: #e2e8f0;
}
:deep(.el-table th) { border-bottom: 1px solid rgba(64, 158, 255, 0.15); padding: 10px 8px; }
:deep(.el-table td) { border-bottom: 1px solid rgba(64, 158, 255, 0.08); padding: 8px; cursor: pointer; }

.status-dot::before {
  content: '';
  display: inline-block;
  width: 7px; height: 7px;
  border-radius: 50%;
  margin-right: 6px;
}
.status-dot.running::before { background: #7dd3fc; box-shadow: 0 0 6px #7dd3fc; }
.status-dot.pending::before { background: #fbbf24; }
.status-dot.completed::before { background: #00ff88; }
.status-dot.failed::before { background: #f87171; }

.log-area {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  font-size: 12px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  background: rgba(15, 23, 42, 0.8);
  border-radius: 6px;
  padding: 10px;
}
.log-line {
  padding: 3px 0;
  border-bottom: 1px solid rgba(64, 158, 255, 0.08);
  display: flex; gap: 8px;
  white-space: nowrap;
}
.log-time { color: #94a3b8; }
.log-level.INFO { color: #00ff88; }
.log-level.WARN { color: #fbbf24; }
.log-level.ERROR { color: #f87171; }
.log-msg { color: #e2e8f0; }
.log-empty {
  text-align: center;
  color: #94a3b8;
  padding: 40px 16px;
}
.log-hint { font-size: 11px; color: #64748b; margin-top: 8px; }
.log-area::-webkit-scrollbar { width: 4px; }
.log-area::-webkit-scrollbar-thumb { background: rgba(64, 158, 255, 0.2); border-radius: 2px; }
</style>
