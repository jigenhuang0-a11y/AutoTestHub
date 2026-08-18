<template>
  <div class="report-container">
    <!-- 英雄区 -->
    <div class="hero">
      <div class="hero-left">
        <div class="title-icon">
          <el-icon :size="26"><DocumentChecked /></el-icon>
        </div>
        <div>
          <h1>测试报告体检中心</h1>
          <p class="subtitle">汇总执行结果、生成质量评分、输出改进建议</p>
        </div>
      </div>
      <div class="hero-actions">
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
        <el-button type="success" :icon="Plus" @click="goExecute">新建执行</el-button>
      </div>
    </div>

    <!-- 空状态 -->
    <el-card v-if="!loading && !reports.length" shadow="never" class="empty-card">
      <el-empty description="暂无测试报告">
        <template #image>
          <el-icon :size="80" color="#64748b"><Document /></el-icon>
        </template>
        <el-button type="primary" @click="goExecute">新建执行</el-button>
      </el-empty>
    </el-card>

    <template v-else>
      <!-- 核心指标：排在测试报告列表上方 -->
      <el-row :gutter="16" class="metric-row">
        <el-col :xs="24" :sm="12" :md="6">
          <div class="metric-card">
            <div class="metric-icon blue"><el-icon :size="24"><Document /></el-icon></div>
            <div class="metric-body">
              <div class="metric-value">{{ summary.total_executions }}</div>
              <div class="metric-label">累计报告数</div>
            </div>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <div class="metric-card">
            <div class="metric-icon green"><el-icon :size="24"><CircleCheck /></el-icon></div>
            <div class="metric-body">
              <div class="metric-value score-good">{{ summary.pass_rate }}%</div>
              <div class="metric-label">平均通过率</div>
            </div>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <div class="metric-card">
            <div class="metric-icon red"><el-icon :size="24"><CircleClose /></el-icon></div>
            <div class="metric-body">
              <div class="metric-value score-poor">{{ summary.fail_rate }}%</div>
              <div class="metric-label">平均失败率</div>
            </div>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <div class="metric-card">
            <div class="metric-icon purple"><el-icon :size="24"><Timer /></el-icon></div>
            <div class="metric-body">
              <div class="metric-value">{{ summary.avg_duration }}s</div>
              <div class="metric-label">平均执行时长</div>
            </div>
          </div>
        </el-col>
      </el-row>

      <!-- 测试报告列表：卡片式全宽独占 -->
      <el-card shadow="never" class="list-card">
        <template #header>
          <div class="card-header">
            <span class="section-title">测试报告列表</span>
            <el-button size="small" @click="loadReports" :loading="loading">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
          </div>
        </template>
        <div class="report-list">
          <div
            v-for="row in reports"
            :key="row.exec_id"
            class="report-item"
          >
            <div class="report-main">
              <div class="report-title-block">
                <div class="report-id">#{{ row.exec_id }}</div>
                <div class="report-name">{{ row.name }}</div>
              </div>
              <div class="result-stack">
                <div class="result-bar">
                  <div class="bar-pass" :style="{ width: passPct(row) + '%' }"></div>
                  <div class="bar-fail" :style="{ width: failPct(row) + '%' }"></div>
                  <div class="bar-skip" :style="{ width: skipPct(row) + '%' }"></div>
                </div>
                <div class="result-legend">
                  <span class="rl-pass">{{ row.passed_cases }} 通过</span>
                  <span class="rl-fail">{{ row.failed_cases }} 失败</span>
                  <span class="rl-skip">{{ row.skipped_cases }} 跳过</span>
                </div>
              </div>
            </div>
            <div class="report-meta">
              <div class="status-pill" :class="'status-' + row.status">
                <el-icon v-if="row.status === 'completed'" :size="14"><CircleCheck /></el-icon>
                <el-icon v-else-if="row.status === 'failed'" :size="14"><CircleClose /></el-icon>
                <el-icon v-else :size="14"><Timer /></el-icon>
                <span>{{ statusText(row.status) }}</span>
              </div>
              <div class="meta-item">
                <el-icon :size="14"><Timer /></el-icon>
                <span>{{ row.duration }}s</span>
              </div>
              <div class="meta-item time-block">{{ formatDate(row.created_at) }}</div>
            </div>
            <div class="report-actions">
              <el-button size="small" type="primary" plain @click="viewReport(row)">
                <el-icon><View /></el-icon> 查看
              </el-button>
              <el-button size="small" type="warning" plain @click="checkHealth(row)">
                <el-icon><FirstAidKit /></el-icon> 体检
              </el-button>
              <el-button size="small" type="success" plain @click="downloadPDF(row)" :loading="downloadingId === row.exec_id">
                <el-icon><Download /></el-icon> PDF
              </el-button>
            </div>
          </div>
        </div>
        <div class="pagination-wrapper">
          <span class="page-total">共 {{ pagination.total }} 条</span>
          <el-select v-model="pagination.pageSize" size="small" class="page-size" @change="pagination.page = 1; loadReports()">
            <el-option label="10 条/页" :value="10" />
            <el-option label="20 条/页" :value="20" />
            <el-option label="50 条/页" :value="50" />
          </el-select>
          <div class="page-pager">
            <button
              class="page-btn"
              :disabled="pagination.page <= 1"
              @click="pagination.page--; loadReports()"
            >上一页</button>
            <span class="page-current">{{ pagination.page }}</span>
            <button
              class="page-btn"
              :disabled="pagination.page * pagination.pageSize >= pagination.total"
              @click="pagination.page++; loadReports()"
            >下一页</button>
          </div>
          <div class="page-jumper">
            <span>前往</span>
            <input
              v-model.number="jumpPage"
              type="number"
              min="1"
              :max="Math.max(1, Math.ceil(pagination.total / pagination.pageSize))"
              class="jump-input"
              @keyup.enter="goJumpPage"
            />
            <span>页</span>
          </div>
        </div>
      </el-card>
    </template>

    <!-- 报告详情对话框 -->
    <el-dialog v-model="reportDialogVisible" :title="currentReport?.name || '报告详情'" width="90%" top="3vh" :close-on-click-modal="false">
      <div v-if="currentReport" class="report-detail">
        <el-descriptions :column="3" border class="report-info">
          <el-descriptions-item label="报告 ID">#{{ currentReport.exec_id }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTag(currentReport.status)" size="small">{{ currentReport.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(currentReport.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="用例数" :span="1">{{ currentReport.total_cases }}</el-descriptions-item>
          <el-descriptions-item label="通过/失败/跳过" :span="1">
            <div class="result-badges">
              <el-tag type="success" size="small">{{ currentReport.passed_cases }}</el-tag>
              <el-tag type="danger" size="small">{{ currentReport.failed_cases }}</el-tag>
              <el-tag type="info" size="small">{{ currentReport.skipped_cases || 0 }}</el-tag>
            </div>
          </el-descriptions-item>
          <el-descriptions-item label="执行耗时" :span="1">{{ currentReport.duration }}s</el-descriptions-item>
          <el-descriptions-item label="摘要" :span="3">{{ currentReport.summary || '暂无摘要' }}</el-descriptions-item>
        </el-descriptions>
        <div class="detail-chart-row">
          <div ref="detailPieRef" class="detail-chart" />
          <div ref="detailBarRef" class="detail-chart" />
        </div>
        <el-table :data="currentReport.results || []" border stripe size="default" style="margin-top: 20px" max-height="400">
          <el-table-column prop="case_id" label="用例 ID" width="120" />
          <el-table-column prop="case_title" label="用例标题" min-width="200" />
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="statusTag(row.status)" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="duration_ms" label="耗时(ms)" width="100" align="center" />
          <el-table-column prop="error_message" label="错误信息" min-width="220" show-overflow-tooltip />
        </el-table>
      </div>
    </el-dialog>

    <!-- 体检对话框 -->
    <el-dialog
      v-model="healthDialogVisible"
      title="测试报告体检"
      width="520px"
      :close-on-click-modal="false"
      class="health-dialog"
      align-center
    >
      <div v-if="health" class="health-body">
        <div class="health-score">
          <div class="score-circle" :style="scoreStyle(health.score)">
            <span class="score-number">{{ health.grade }}</span>
            <span class="score-sub">{{ health.score }} 分</span>
          </div>
          <div class="score-meta">
            <div class="meta-line"><span class="meta-label">通过率</span><span class="meta-value score-good">{{ health.pass_rate }}%</span></div>
            <div class="meta-line"><span class="meta-label">失败率</span><span class="meta-value score-poor">{{ health.fail_rate }}%</span></div>
            <div class="meta-line"><span class="meta-label">跳过率</span><span class="meta-value">{{ health.skip_rate }}%</span></div>
            <div class="meta-line"><span class="meta-label">耗时</span><span class="meta-value">{{ health.duration }}s</span></div>
          </div>
        </div>
        <div class="suggestion-box">
          <div class="suggestion-title">改进建议</div>
          <ul>
            <li v-for="(s, i) in health.suggestions" :key="i">{{ s }}</li>
          </ul>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { reportAPI } from '@/api'
import { ElMessage } from 'element-plus'
import html2pdf from 'html2pdf.js'
import * as echarts from 'echarts'
import {
  Refresh, View, Download, FullScreen, Document,
  DocumentChecked, CircleCheck, CircleClose, Timer,
  Plus, FirstAidKit,
} from '@element-plus/icons-vue'

const router = useRouter()
const loading = ref(false)
const downloadingId = ref(null)
const reports = ref([])
const summary = reactive({
  total_executions: 0,
  total_cases: 0,
  pass_rate: 0,
  fail_rate: 0,
  skip_rate: 0,
  avg_duration: 0,
})
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })
const jumpPage = ref(1)

const goJumpPage = () => {
  const maxPage = Math.max(1, Math.ceil(pagination.total / pagination.pageSize))
  const target = Math.min(maxPage, Math.max(1, jumpPage.value || 1))
  pagination.page = target
  jumpPage.value = target
  loadReports()
}

const reportDialogVisible = ref(false)
const healthDialogVisible = ref(false)
const currentReport = ref(null)
const health = ref(null)
const detailPieRef = ref(null)
const detailBarRef = ref(null)
let detailPieChart = null
let detailBarChart = null

const loadReports = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize }
    const response = await reportAPI.list(params)
    reports.value = response.results || response
    pagination.total = response.total || response.count || 0
  } catch (error) {
    console.error('Load reports error:', error)
    ElMessage.error('加载报告列表失败')
  } finally {
    loading.value = false
  }
}

const loadSummary = async () => {
  try {
    const data = await reportAPI.summary()
    Object.assign(summary, data)
  } catch (error) {
    console.error('Load summary error:', error)
  }
}

const loadAll = async () => {
  await loadSummary()
  await loadReports()
}

const goExecute = async () => {
  try {
    loading.value = true
    await reportAPI.generate()
    ElMessage.success('报告生成成功')
    await loadAll()
  } catch (error) {
    console.error('Generate report error:', error)
    ElMessage.error(error?.response?.data?.detail || '生成报告失败')
  } finally {
    loading.value = false
  }
}

const statusTag = (status) => {
  if (!status) return 'info'
  const s = String(status).toLowerCase()
  if (s === 'passed' || s === 'completed' || s === 'success') return 'success'
  if (s === 'failed' || s === 'error' || s === 'failure') return 'danger'
  if (s === 'skipped' || s === 'pending') return 'info'
  return 'warning'
}

const statusText = (status) => {
  const map = { completed: '已完成', failed: '失败', running: '执行中', pending: '排队中', skipped: '跳过', passed: '已通过' }
  return map[status] || status
}

const passPct = (row) => (row.total_cases ? Math.round((row.passed_cases / row.total_cases) * 100) : 0)
const failPct = (row) => (row.total_cases ? Math.round((row.failed_cases / row.total_cases) * 100) : 0)
const skipPct = (row) => (row.total_cases ? Math.round((row.skipped_cases / row.total_cases) * 100) : 0)
const rowClassName = ({ rowIndex }) => (rowIndex % 2 === 0 ? 'row-even' : 'row-odd')

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const viewReport = async (report) => {
  try {
    const detail = await reportAPI.get(report.exec_id)
    currentReport.value = detail
    reportDialogVisible.value = true
    nextTick(initDetailCharts)
  } catch (error) {
    console.error('View report error:', error)
    ElMessage.error('加载报告详情失败')
  }
}

const checkHealth = async (report) => {
  try {
    health.value = await reportAPI.health({ report_id: report.exec_id })
    healthDialogVisible.value = true
  } catch (error) {
    console.error('Health check error:', error)
    ElMessage.error('体检失败')
  }
}

const scoreStyle = (score) => {
  let color = '#f87171'
  if (score >= 90) color = '#4ade80'
  else if (score >= 75) color = '#fbbf24'
  else if (score >= 60) color = '#fb923c'
  return { borderColor: color, color }
}

const downloadPDF = async (report) => {
  downloadingId.value = report.exec_id
  try {
    const detail = await reportAPI.get(report.exec_id)
    const element = document.createElement('div')
    element.className = 'pdf-body'
    element.innerHTML = `
      <div style="padding: 20px; font-family: Arial, sans-serif; color: #1f2937;">
        <h1 style="color: #1f2937; border-bottom: 2px solid #409eff; padding-bottom: 10px;">
          ${detail.name || '测试报告'}
        </h1>
        <div style="margin: 20px 0; line-height: 1.8;">
          <p><strong>报告 ID：</strong>${detail.exec_id}</p>
          <p><strong>状态：</strong>${detail.status}</p>
          <p><strong>创建时间：</strong>${formatDate(detail.created_at)}</p>
          <p><strong>用例数：</strong>${detail.total_cases}</p>
          <p><strong>通过/失败/跳过：</strong>${detail.passed_cases} / ${detail.failed_cases} / ${detail.skipped_cases || 0}</p>
          <p><strong>摘要：</strong>${detail.summary || '暂无摘要'}</p>
        </div>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
          <thead><tr style="background: #f3f4f6;"><th>用例 ID</th><th>用例标题</th><th>状态</th><th>耗时(ms)</th><th>错误信息</th></tr></thead>
          <tbody>
            ${(detail.results || []).map(r => `<tr><td>${r.case_id}</td><td>${r.case_title}</td><td>${r.status}</td><td>${r.duration_ms}</td><td>${r.error_message || ''}</td></tr>`).join('')}
          </tbody>
        </table>
      </div>
    `
    document.body.appendChild(element)
    const opt = {
      margin: [10, 10],
      filename: `${detail.name || 'test-report'}_${Date.now()}.pdf`,
      image: { type: 'jpeg', quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true },
      jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
    }
    await html2pdf().set(opt).from(element).save()
    ElMessage.success('PDF 下载成功')
    document.body.removeChild(element)
  } catch (error) {
    console.error('Download PDF error:', error)
    ElMessage.error('PDF 下载失败')
  } finally {
    downloadingId.value = null
  }
}

const initDetailCharts = () => {
  const r = currentReport.value
  if (!r) return
  nextTick(() => {
    if (detailPieRef.value) {
      detailPieChart?.dispose()
      detailPieChart = echarts.init(detailPieRef.value, null, { renderer: 'canvas' })
      detailPieChart.setOption({
        color: ['#4ade80', '#f87171', '#94a3b8'],
        tooltip: { trigger: 'item' },
        legend: { bottom: 0, textStyle: { color: '#94a3b8' } },
        series: [{
          type: 'pie',
          radius: ['45%', '70%'],
          center: ['50%', '45%'],
          itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
          label: { show: false },
          data: [
            { value: r.passed_cases, name: '通过' },
            { value: r.failed_cases, name: '失败' },
            { value: r.skipped_cases || 0, name: '跳过' },
          ].filter(d => d.value > 0),
        }],
      })
    }
    if (detailBarRef.value) {
      detailBarChart?.dispose()
      detailBarChart = echarts.init(detailBarRef.value, null, { renderer: 'canvas' })
      detailBarChart.setOption({
        color: ['#60a5fa'],
        tooltip: { trigger: 'axis' },
        grid: { top: 24, left: 40, right: 20, bottom: 24, containLabel: true },
        xAxis: { type: 'category', data: (r.results || []).map(x => x.case_id.slice(-6)), axisLabel: { color: '#64748b', rotate: 30 } },
        yAxis: { type: 'value', name: 'ms', axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: '#e2e8f0' } } },
        series: [{ type: 'bar', data: (r.results || []).map(x => x.duration_ms), itemStyle: { borderRadius: [4, 4, 0, 0] } }],
      })
    }
  })
}

const onResize = () => {
  detailPieChart?.resize()
  detailBarChart?.resize()
}

onMounted(() => {
  loadAll()
  window.addEventListener('resize', onResize)
})
</script>

<style scoped>
.report-container {
  padding: 24px;
  min-height: 100vh;
  height: 100vh;
  background: radial-gradient(1200px 600px at 80% -10%, #243049 0%, #1e293b 55%);
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

.report-container > .hero,
.report-container > .metric-row {
  flex-shrink: 0;
}

.report-container > .list-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.report-container > .list-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding-bottom: 16px;
  position: relative;
}

.pagination-wrapper {
  flex-shrink: 0;
  margin-top: 16px;
  margin-bottom: 20px;
  padding: 12px 18px;
  background: #27354d;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: 0 4px 12px rgba(2, 6, 23, 0.2);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
}

.page-total {
  font-size: 13px;
  color: #94a3b8;
}

.page-size {
  width: 100px;
}

.page-size :deep(.el-input__wrapper) {
  background: #1e293b;
  box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.25) inset;
}

.page-size :deep(.el-input__inner) {
  color: #e2e8f0;
}

.page-pager {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-btn {
  padding: 7px 14px;
  font-size: 13px;
  color: #e2e8f0;
  background: #1e293b;
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.page-btn:hover:not(:disabled) {
  border-color: #60a5fa;
  color: #60a5fa;
}

.page-btn:disabled {
  color: #64748b;
  border-color: rgba(148, 163, 184, 0.12);
  cursor: not-allowed;
}

.page-current {
  min-width: 30px;
  text-align: center;
  padding: 7px 0;
  font-size: 14px;
  font-weight: 700;
  color: #f8fafc;
  background: #3b82f6;
  border-radius: 8px;
}

.page-jumper {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #94a3b8;
}

.jump-input {
  width: 44px;
  height: 30px;
  padding: 0 6px;
  text-align: center;
  font-size: 13px;
  color: #f8fafc;
  background: #1e293b;
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 8px;
  outline: none;
}

.jump-input:focus {
  border-color: #60a5fa;
}

/* 报告卡片列表 */
.report-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
}

.report-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 18px 22px;
  background: #1e293b;
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 12px;
  transition: all 0.2s ease;
}

.report-item:hover {
  border-color: rgba(59, 130, 246, 0.35);
  background: rgba(59, 130, 246, 0.06);
  box-shadow: 0 6px 18px rgba(2, 6, 23, 0.18);
}

.report-main {
  display: flex;
  align-items: center;
  gap: 48px;
  flex: 1;
  min-width: 0;
}

.report-title-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 220px;
}

.report-id {
  font-size: 12px;
  color: #64748b;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.report-name {
  font-size: 15px;
  font-weight: 600;
  color: #f8fafc;
}

.result-stack {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  width: 160px;
}

.result-bar {
  width: 100%;
  height: 8px;
  display: flex;
  border-radius: 4px;
  overflow: hidden;
  background: rgba(148, 163, 184, 0.12);
}

.bar-pass { background: #4ade80; }
.bar-fail { background: #f87171; }
.bar-skip { background: #94a3b8; }

.result-legend {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #94a3b8;
}

.result-legend .rl-pass { color: #4ade80; }
.result-legend .rl-fail { color: #f87171; }
.result-legend .rl-skip { color: #94a3b8; }

.report-meta {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-shrink: 0;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
}

.status-completed { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
.status-failed { background: rgba(239, 68, 68, 0.15); color: #f87171; }
.status-running { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.status-pending { background: rgba(148, 163, 184, 0.15); color: #cbd5e1; }
.status-skipped { background: rgba(168, 85, 247, 0.15); color: #c084fc; }

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #cbd5e1;
}

.time-block {
  font-size: 13px;
  color: #94a3b8;
}

.report-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.hero {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 24px 28px;
  margin-bottom: 20px;
  background: linear-gradient(120deg, rgba(59,130,246,0.18) 0%, rgba(45,212,191,0.10) 100%);
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
  background: linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%);
  color: #fff;
  box-shadow: 0 8px 20px rgba(59, 130, 246, 0.35);
}

.hero-left h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #f8fafc;
  letter-spacing: 0.5px;
}

.subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: #cbd5e1;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.empty-card {
  background: #27354d;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  color: #e2e8f0;
}

.metric-row {
  margin-bottom: 16px;
}

.metric-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  background: #27354d;
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 12px;
  color: #e2e8f0;
  box-shadow: 0 4px 12px rgba(2, 6, 23, 0.15);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(2, 6, 23, 0.22);
}

.metric-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  border-radius: 12px;
  color: #fff;
  flex-shrink: 0;
}

.metric-icon.blue { background: linear-gradient(135deg, #3b82f6, #60a5fa); }
.metric-icon.green { background: linear-gradient(135deg, #22c55e, #4ade80); }
.metric-icon.red { background: linear-gradient(135deg, #ef4444, #f87171); }
.metric-icon.purple { background: linear-gradient(135deg, #8b5cf6, #a78bfa); }

.metric-value {
  font-size: 24px;
  font-weight: 700;
  color: #f8fafc;
  line-height: 1.2;
}

.metric-label {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}

.score-good { color: #4ade80 !important; }
.score-poor { color: #f87171 !important; }

.section-title {
  font-size: 17px;
  font-weight: 700;
  color: #f8fafc;
}

.metric-row {
  margin-bottom: 20px;
}

.metric-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px 20px;
  background: #27354d;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  color: #e2e8f0;
  box-shadow: 0 4px 12px rgba(2, 6, 23, 0.2);
}

.metric-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 12px;
  flex-shrink: 0;
}

.metric-icon.blue { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
.metric-icon.green { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
.metric-icon.red { background: rgba(239, 68, 68, 0.2); color: #f87171; }
.metric-icon.purple { background: rgba(168, 85, 247, 0.2); color: #c084fc; }

.metric-body {
  flex: 1;
  min-width: 0;
}

.metric-value {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.2;
  color: #f8fafc;
}

.metric-label {
  font-size: 13px;
  color: #94a3b8;
  margin-top: 4px;
}

.list-card {
  background: #27354d;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  color: #e2e8f0;
  box-shadow: 0 4px 12px rgba(2, 6, 23, 0.2);
}

.list-card :deep(.el-card__header) {
  padding: 20px 24px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.list-card :deep(.el-card__body) {
  padding: 20px 24px;
  color: #e2e8f0;
}

.list-card :deep(.el-table) {
  font-size: 14px;
  background: transparent;
}

.list-card :deep(.el-table th.el-table__cell) {
  height: 54px;
  font-size: 14px;
  font-weight: 700;
  color: #f8fafc;
  background: rgba(148, 163, 184, 0.12);
}

.list-card :deep(.el-table td.el-table__cell) {
  height: 58px;
  padding: 10px 0;
}

.list-card :deep(.el-table .cell) {
  padding: 0 14px;
}

.list-card :deep(.el-tag) {
  font-size: 13px;
  padding: 0 10px;
  height: 26px;
}

.list-card :deep(.el-button--small) {
  padding: 8px 14px;
  font-size: 13px;
}

.list-card :deep(.el-pagination) {
  margin-top: 24px;
  font-size: 14px;
}

.list-card :deep(.el-pagination .el-select .el-input) {
  font-size: 14px;
}

.case-count {
  font-weight: 700;
  font-size: 15px;
  color: #f8fafc;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  color: #f8fafc;
}

.result-badges {
  display: inline-flex;
  gap: 6px;
  justify-content: center;
}

.report-detail {
  max-height: 75vh;
  overflow-y: auto;
}

.report-info {
  margin-bottom: 20px;
}

.detail-chart-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
  margin-bottom: 10px;
}

.detail-chart {
  height: 240px;
  background: #f8fafc;
  border-radius: 8px;
}

.health-body {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.health-score {
  display: flex;
  align-items: center;
  gap: 24px;
}

.score-circle {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 110px;
  height: 110px;
  border-radius: 50%;
  border: 6px solid;
  background: #1e293b;
}

.score-number {
  font-size: 36px;
  font-weight: 800;
  line-height: 1;
}

.score-sub {
  font-size: 12px;
  margin-top: 4px;
  color: #e2e8f0;
}

.score-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 24px;
  flex: 1;
}

.meta-line {
  display: flex;
  justify-content: space-between;
  font-size: 16px;
  color: #f8fafc;
  font-weight: 500;
}

.meta-value {
  font-weight: 700;
  color: #f8fafc;
}

.suggestion-box {
  padding: 16px 18px;
  background: rgba(30, 41, 59, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 10px;
}

.suggestion-title {
  font-weight: 700;
  color: #f8fafc;
  margin-bottom: 10px;
}

.suggestion-box ul {
  margin: 0;
  padding-left: 18px;
  color: #e2e8f0;
  line-height: 1.8;
}

/* 体检对话框深色主题 */
.health-dialog .el-dialog {
  background: #0f172a;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 16px;
  box-shadow: 0 20px 50px rgba(2, 6, 23, 0.6);
}

.health-dialog .el-dialog__header {
  padding: 18px 24px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.15);
  margin-right: 0;
}

.health-dialog .el-dialog__title {
  color: #f8fafc;
  font-weight: 700;
  font-size: 17px;
}

.health-dialog .el-dialog__headerbtn {
  top: 50%;
  transform: translateY(-50%);
  right: 18px;
}

.health-dialog .el-dialog__headerbtn .el-dialog__close {
  color: #94a3b8;
}

.health-dialog .el-dialog__headerbtn .el-dialog__close:hover {
  color: #f8fafc;
}

.health-dialog .el-dialog__body {
  padding: 24px;
  color: #e2e8f0;
}
</style>
