<template>
  <div class="perf-detail-container">
    <!-- 顶部工具栏 -->
    <div class="top-bar">
      <div class="top-bar-left">
        <el-button class="back-btn" @click="$router.back()">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <span class="page-title">性能压测详情 #{{ execution.id }}</span>
        <!-- 历史执行下拉 -->
        <el-select
          v-if="historyExecutions.length > 0"
          v-model="selectedHistory"
          placeholder="历史执行"
          size="small"
          style="width:220px;margin-left:12px"
          @change="switchHistory"
        >
          <el-option
            v-for="h in historyExecutions"
            :key="h.id"
            :label="`#${h.id} ${h.status_display} ${formatDate(h.started_at)}`"
            :value="h.id"
          />
        </el-select>
      </div>
      <div>
        <el-button v-if="execution.status === 'running'" type="danger" @click="handleStop" :loading="stopping">
          <el-icon><VideoPause /></el-icon>
          停止压测
        </el-button>
        <el-button
          v-if="(execution.status === 'completed' || execution.status === 'failed') && execution.total_requests"
          type="warning"
          @click="handleDiagnose"
          :loading="diagnosing"
        >
          <el-icon><Aim /></el-icon>
          AI 诊断
        </el-button>
        <el-button @click="refreshData" :loading="refreshing">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 测试信息 -->
    <el-card class="info-card">
      <template #header>
        <span>测试信息</span>
        <el-tag :type="statusTagType(execution.status)" style="margin-left:12px">
          {{ execution.status_display || execution.status }}
        </el-tag>
      </template>
      <el-descriptions :column="4" border size="small">
        <el-descriptions-item label="用例名称">{{ execution.test_case_name }}</el-descriptions-item>
        <el-descriptions-item label="目标URL">{{ execution.test_case_url }}</el-descriptions-item>
        <el-descriptions-item label="请求方法">{{ execution.test_case_method }}</el-descriptions-item>
        <el-descriptions-item label="并发用户数">{{ execution.users }}</el-descriptions-item>
        <el-descriptions-item label="持续时间">{{ execution.duration }}s</el-descriptions-item>
        <el-descriptions-item label="执行人">{{ execution.started_by_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ formatDate(execution.started_at) }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ execution.completed_at ? formatDate(execution.completed_at) : '进行中...' }}</el-descriptions-item>
      </el-descriptions>
      <div style="margin-top:8px;display:flex;align-items:center;gap:12px">
        <span style="font-size:13px;color:#606266">阈值结果：</span>
        <el-tag :type="execution.thresholds_passed ? 'success' : 'danger'">
          {{ execution.thresholds_passed ? '全部通过' : '未通过' }}
        </el-tag>
        <el-alert
          v-if="execution.threshold_errors && execution.threshold_errors.length"
          v-for="(err, i) in execution.threshold_errors" :key="i"
          :title="err" type="error" :closable="false" show-icon style="margin:0"
        />
      </div>
    </el-card>

    <!-- 核心指标卡片 -->
    <el-row :gutter="12" style="margin-top:4px">
      <el-col :span="3" v-for="m in coreMetrics" :key="m.key">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-label">{{ m.label }}</div>
          <div class="metric-value" :class="m.cls">
            {{ m.value }}<span v-if="m.unit" class="unit">{{ m.unit }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- AI 性能分析（智能助手） -->
    <el-card v-if="hasMetricsTimeline" class="ai-analysis-card" style="margin-top:16px">
      <template #header>
        <div class="ai-header">
          <div class="ai-header-left">
            <el-icon size="20" color="#e65c00"><Aim /></el-icon>
            <span class="ai-title">AI 性能诊断</span>
            <el-tag v-if="aiAnalysis.fromAI" type="primary" effect="dark" round size="small" style="margin-right:4px">🤖 通义千问</el-tag>
            <el-tag v-if="aiAnalysis.score >= 80" type="success" effect="dark" round size="small">{{ aiAnalysis.score }}分</el-tag>
            <el-tag v-else-if="aiAnalysis.score >= 60" type="warning" effect="dark" round size="small">{{ aiAnalysis.score }}分</el-tag>
            <el-tag v-else type="danger" effect="dark" round size="small">{{ aiAnalysis.score }}分</el-tag>
          </div>
          <el-button type="primary" size="small" @click="aiDialogVisible = true">
            <el-icon><ChatDotRound /></el-icon> 查看详细诊断
          </el-button>
        </div>
      </template>

      <div class="ai-brief">
        <div class="ai-summary">
          <el-icon size="20" :color="aiSummaryIcon.color"><component :is="aiSummaryIcon.icon" /></el-icon>
          <span :class="aiSummaryIcon.textClass">{{ aiAnalysis.summary }}</span>
        </div>
        <div class="ai-tags">
          <el-tag v-for="(tag, i) in aiAnalysis.tags" :key="i" :type="tag.type" size="small" effect="plain">
            {{ tag.text }}
          </el-tag>
        </div>
      </div>

      <el-divider style="margin:12px 0" />

      <div class="ai-metrics-review">
        <div v-for="(review, i) in aiAnalysis.metricReviews" :key="i" class="metric-review-item">
          <div class="review-header">
            <span class="review-name">{{ review.name }}</span>
            <el-progress
              :percentage="review.score"
              :color="review.color"
              :stroke-width="8"
              :show-text="false"
              style="width:80px"
            />
            <span class="review-val" :style="{color: review.color}">{{ review.val }}</span>
            <span class="review-status" :style="{color: review.color}">{{ review.status }}</span>
          </div>
          <div class="review-desc">{{ review.desc }}</div>
        </div>
      </div>

      <div class="ai-footer">
        <el-icon size="12" color="#909399"><Timer /></el-icon>
        <span>基于 {{ execution.metrics_timeline?.length }} 个采样点，{{ execution.duration }}s 压测周期</span>
      </div>
    </el-card>

    <!-- 实时曲线图 -->
    <el-card style="margin-top:16px" v-if="hasMetricsTimeline">
      <template #header>
        <span>实时指标曲线</span>
        <el-tag v-if="execution.status === 'running'" type="warning" size="small" style="margin-left:8px">
          <el-icon class="is-loading"><Loading /></el-icon>
          实时更新中...
        </el-tag>
      </template>
      <div ref="chartRef" style="width:100%;height:360px"></div>
    </el-card>

    <!-- 图表下方：指标数据 + 日志 -->
    <el-row :gutter="16" style="margin-top:16px">
      <!-- 每秒指标数据 -->
      <el-col :span="12" v-if="hasMetricsTimeline">
        <el-card :body-style="{ padding: '0' }">
          <template #header>
            <div style="display:flex;align-items:center;gap:8px">
              <span style="font-weight:600">每秒指标数据</span>
              <el-tag size="small">{{ execution.metrics_timeline?.length }} 条</el-tag>
            </div>
          </template>
            <el-table :data="execution.metrics_timeline" size="small" max-height="340" stripe style="width:100%">
              <el-table-column prop="timestamp" label="时间(s)" min-width="90" />
              <el-table-column prop="rps" label="QPS" min-width="80" />
              <el-table-column prop="users" label="用户" min-width="80" />
              <el-table-column label="P50" min-width="90">
                <template #default="{ row }">{{ row.p50 }}ms</template>
              </el-table-column>
              <el-table-column label="P95" min-width="90">
                <template #default="{ row }">{{ row.p95 }}ms</template>
              </el-table-column>
              <el-table-column label="P99" min-width="90">
                <template #default="{ row }">{{ row.p99 }}ms</template>
              </el-table-column>
              <el-table-column label="平均" min-width="100">
                <template #default="{ row }">{{ row.avg }}ms</template>
              </el-table-column>
              <el-table-column prop="failures_per_sec" label="错误" min-width="80" />
            </el-table>
          </el-card>
      </el-col>

      <!-- 执行日志 -->
      <el-col :span="12">
        <el-card :body-style="{ padding: '0' }">
          <template #header>
            <div style="display:flex;align-items:center;gap:8px">
              <span style="font-weight:600">执行日志</span>
              <el-tag v-if="execution.execution_log" size="small" type="success">有记录</el-tag>
              <el-tag v-else size="small" type="info">暂无</el-tag>
            </div>
          </template>
          <pre v-if="execution.execution_log" class="log-box" style="height:340px;overflow-y:auto;margin:0">{{ execution.execution_log }}</pre>
          <el-empty v-else description="暂无执行日志，可能压测未产生详细输出或运行中未记录" :image-size="80" style="height:340px" />
        </el-card>
      </el-col>
    </el-row>

    <!-- AI 详细诊断对话框 -->
    <el-dialog v-model="aiDialogVisible" title="AI 性能诊断详情" width="780px" destroy-on-close>
      <div class="ai-dialog-content">
        <!-- 顶部评分 -->
        <div class="ai-dialog-score">
          <div class="score-circle" :class="scoreCircleClass">
            <span class="score-number">{{ aiAnalysis.score }}</span>
            <span class="score-label">{{ scoreLabel }}</span>
          </div>
          <div class="score-summary">
            <div class="score-title">{{ aiAnalysis.summary }}</div>
            <div class="score-desc">{{ aiAnalysis.fullSummary }}</div>
          </div>
        </div>

        <el-divider />

        <!-- 各维度诊断 -->
        <div class="ai-dimension-section">
          <div class="section-title">
            <el-icon><DataLine /></el-icon> 各维度诊断
          </div>
          <div v-for="(review, i) in aiAnalysis.metricReviews" :key="i" class="dimension-card">
            <div class="dimension-header">
              <span class="dimension-name">{{ review.name }}</span>
              <el-progress
                :percentage="review.score"
                :color="review.color"
                :stroke-width="10"
                :show-text="false"
                style="width:120px"
              />
              <span class="dimension-val" :style="{color: review.color}">{{ review.val }}</span>
              <el-tag :type="review.score >= 80 ? 'success' : review.score >= 60 ? 'warning' : 'danger'" size="small">
                {{ review.status }}
              </el-tag>
            </div>
            <div class="dimension-desc">{{ review.desc }}</div>
            <div class="dimension-suggestion">
              <el-icon color="#409eff"><ArrowRight /></el-icon>
              <span>{{ review.suggestion }}</span>
            </div>
          </div>
        </div>

        <el-divider />

        <!-- 问题列表 -->
        <div class="ai-issues-section" v-if="aiAnalysis.issues.length > 0">
          <div class="section-title">
            <el-icon><WarningFilled /></el-icon> 发现 {{ aiAnalysis.issues.length }} 个问题
          </div>
          <div v-for="(issue, idx) in aiAnalysis.issues" :key="idx" class="issue-card">
            <div class="issue-header">
              <el-icon :color="issue.severity === 'error' ? '#f56c6c' : '#e6a23c'" size="18">
                <WarningFilled v-if="issue.severity === 'error'" />
                <InfoFilled v-else />
              </el-icon>
              <span class="issue-title">{{ issue.title }}</span>
              <el-tag :type="issue.severity === 'error' ? 'danger' : 'warning'" size="small">
                {{ issue.severityText }}
              </el-tag>
            </div>
            <div class="issue-desc">{{ issue.desc }}</div>
            <div class="issue-suggestion">
              <el-icon color="#409eff"><ArrowRight /></el-icon>
              <span>{{ issue.suggestion }}</span>
            </div>
          </div>
        </div>

        <div v-else class="ai-issues-section">
          <div class="section-title">
            <el-icon color="#67c23a"><CircleCheck /></el-icon> 未发现问题
          </div>
          <div style="color:#67c23a;font-size:14px;padding:12px 0">
            本次压测各项指标均在正常范围内，系统表现良好，无明显性能瓶颈。
          </div>
        </div>

        <el-divider />

        <!-- 综合建议 -->
        <div class="ai-recommend-section">
          <div class="section-title">
            <el-icon><ChatDotRound /></el-icon> 综合建议
          </div>
          <div v-for="(rec, i) in aiAnalysis.recommendations" :key="i" class="recommend-item">
            <span class="rec-index">{{ i + 1 }}</span>
            <span class="rec-text">{{ rec }}</span>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, VideoPause, Refresh, Loading, Aim, CircleCheck, WarningFilled, InfoFilled, ArrowRight, Timer, ChatDotRound, DataLine } from '@element-plus/icons-vue'
import { perfAPI } from '@/api'
import { formatDate } from '@/utils/helpers'

const route = useRoute()
const router = useRouter()

const execution = ref({
  id: route.params.id,
  status: 'running',
  total_requests: 0,
  requests_per_second: 0,
  failures: 0,
  avg_response_time: 0,
  metrics_timeline: [],
  threshold_errors: [],
})

const refreshing = ref(false)
const stopping = ref(false)
const diagnosing = ref(false)
const activeCollapse = ref([]) // 折叠面板默认全部收起
const infoCollapse = ref([])   // 测试信息默认收起
const aiDialogVisible = ref(false) // AI 详细诊断对话框

// ---------- 历史执行 ----------
const historyExecutions = ref([])
const selectedHistory = ref(null)

const loadHistory = async () => {
  const testCaseId = execution.value.test_case
  if (!testCaseId) return
  try {
    const res = await perfAPI.getTestCaseExecutions(testCaseId)
    historyExecutions.value = res.results || res || []
    selectedHistory.value = Number(execution.value.id)
  } catch (e) {
    console.error('Load history error:', e)
  }
}

const switchHistory = (id) => {
  if (id && id !== Number(execution.value.id)) {
    router.push(`/perf-execution/${id}`)
  }
}



const coreMetrics = computed(() => {
  const fp = execution.value.total_requests
    ? (execution.value.failures / execution.value.total_requests * 100).toFixed(1)
    : '0.0'
  return [
    { key: 'total', label: '总请求数', value: (execution.value.total_requests || 0).toLocaleString(), cls: 'primary', unit: '' },
    { key: 'qps', label: 'QPS', value: execution.value.requests_per_second || 0, cls: 'success', unit: '' },
    { key: 'avg', label: '平均响应', value: execution.value.avg_response_time || 0, cls: (execution.value.avg_response_time || 0) > 500 ? 'danger' : 'success', unit: 'ms' },
    { key: 'fail', label: '失败率', value: fp, cls: parseFloat(fp) > 1 ? 'danger' : 'success', unit: '%' },
    { key: 'min', label: '最小响应', value: execution.value.min_response_time || 0, cls: 'warning', unit: 'ms' },
    { key: 'p50', label: 'P50', value: execution.value.p50_response_time || 0, cls: 'warning', unit: 'ms' },
    { key: 'p95', label: 'P95', value: execution.value.p95_response_time || 0, cls: 'warning', unit: 'ms' },
    { key: 'p99', label: 'P99', value: execution.value.p99_response_time || 0, cls: 'warning', unit: 'ms' },
  ]
})


// ---------- AI 分析 ----------
const emptyResult = () => ({ score: 0, issues: [], tags: [], metricReviews: [], summary: '', fullSummary: '', recommendations: [] })

// 将后端 AI exec_summary 转换为前端格式
const fromBackendAI = (summary) => {
  if (!summary || summary.score == null) return null
  const tags = []
  if (summary.score >= 85) tags.push({ text: 'AI 评估: 优秀', type: 'success' })
  else if (summary.score >= 70) tags.push({ text: 'AI 评估: 需关注', type: 'warning' })
  else tags.push({ text: 'AI 评估: 需优化', type: 'danger' })
  tags.push({ text: 'AI 诊断', type: 'info' })

  return {
    score: summary.score,
    summary: summary.summary || '',
    fullSummary: summary.fullSummary || '',
    issues: (summary.issues || []).map(i => ({
      severity: i.severity || 'warning',
      severityText: i.severity === 'error' ? '严重' : i.severity === 'warning' ? '警告' : '提示',
      title: i.title || '',
      desc: i.desc || '',
      suggestion: i.suggestion || '',
    })),
    tags,
    metricReviews: [],
    recommendations: summary.recommendations || [],
    fromAI: true,
  }
}

const aiAnalysis = computed(() => {
  // 优先使用后端 AI 诊断结果
  const aiData = execution.value.exec_summary
  if (aiData && aiData.score != null) {
    const result = fromBackendAI(aiData)
    if (result) return result
  }

  // 降级：使用前端算法分析
  const data = execution.value.metrics_timeline || []
  if (!data.length) return emptyResult()

  const type = execution.value.test_type || 'baseline'

  switch (type) {
    case 'ramp':  return analyzeRamp(data, execution.value)
    case 'mixed': return analyzeMixed(data, execution.value)
    default:      return analyzeBaseline(data, execution.value)
  }
})

// ===== 基准测试分析（当前逻辑，微调输出风格） =====
const analyzeBaseline = (data, execution) => {
  const issues = []
  let score = 100

  const rpsValues = data.map(d => d.rps || 0)
  const rpsAvg = rpsValues.reduce((a, b) => a + b, 0) / rpsValues.length
  const rpsMax = Math.max(...rpsValues)
  const rpsMin = Math.min(...rpsValues)
  const rpsCv = rpsAvg > 0 ? ((rpsMax - rpsMin) / rpsAvg) : 0

  const avgValues = data.map(d => d.avg || 0)
  const avgAll = avgValues.reduce((a, b) => a + b, 0) / avgValues.length

  const p95Values = data.map(d => d.p95 || 0)
  const p95Avg = p95Values.reduce((a, b) => a + b, 0) / p95Values.length
  const p95Max = Math.max(...p95Values)

  const p99Values = data.map(d => d.p99 || 0)
  const p99Avg = p99Values.reduce((a, b) => a + b, 0) / p99Values.length

  const failRate = execution.total_requests > 0
    ? (execution.failures / execution.total_requests * 100) : 0

  // 响应趋势
  let trendText = '稳定', trendScore = 100
  if (data.length > 10) {
    const half = Math.floor(data.length / 2)
    const firstAvg = data.slice(0, half).reduce((s, d) => s + (d.avg || 0), 0) / half
    const secondAvg = data.slice(half).reduce((s, d) => s + (d.avg || 0), 0) / half
    if (secondAvg > firstAvg * 1.5) {
      trendText = '持续恶化'; trendScore = 40; score -= 15
      issues.push({ severity: 'warning', severityText: '恶化', title: '响应时间持续恶化', desc: `后半程平均响应时间 ${secondAvg.toFixed(1)}ms，比前半程 ${firstAvg.toFixed(1)}ms 增长了 ${((secondAvg / firstAvg - 1) * 100).toFixed(0)}%。`, suggestion: '疑似内存泄漏或连接池资源耗尽，排查系统资源消耗。' })
    } else if (secondAvg > firstAvg * 1.2) {
      trendText = '轻微上升'; trendScore = 70; score -= 5
    }
  }

  // QPS 稳定性
  let qpsScore = 100, qpsStatus = '优秀', qpsColor = '#67C23A'
  let qpsDesc = `QPS 平均 ${rpsAvg.toFixed(1)}，吞吐量稳定。`
  let qpsSuggestion = '当前表现正常，可尝试加大并发验证极限。'
  if (rpsCv > 0.5) {
    qpsScore = 40; qpsStatus = '较差'; qpsColor = '#F56C6C'; score -= 15
    qpsDesc = `QPS 波动范围 ${rpsMin.toFixed(0)}~${rpsMax.toFixed(0)}，变异系数 ${(rpsCv * 100).toFixed(0)}%，不稳定。`
    qpsSuggestion = '检查 GC 停顿、连接池耗尽或负载不均。'
    issues.push({ severity: 'warning', severityText: '波动', title: 'QPS 波动大', desc: qpsDesc, suggestion: qpsSuggestion })
  } else if (rpsCv > 0.3) {
    qpsScore = 65; qpsStatus = '一般'; qpsColor = '#E6A23C'; score -= 8
    qpsDesc = `QPS 存在波动，变异系数 ${(rpsCv * 100).toFixed(0)}%。`
    qpsSuggestion = '排查间歇性性能抖动。'
  }

  // P95
  let p95Score = 100, p95Status = '优秀', p95Color = '#67C23A'
  let p95Desc = `P95 平均 ${p95Avg.toFixed(1)}ms，用户体验良好。`
  let p95Suggestion = '当前响应优秀，可作为基线参考。'
  if (p95Max > 1000) {
    p95Score = 30; p95Status = '严重'; p95Color = '#F56C6C'; score -= 25
    p95Desc = `P95 峰值 ${p95Max.toFixed(1)}ms，超过1秒红线。`
    p95Suggestion = '优化慢查询、加缓存、检查下游延迟。'
    issues.push({ severity: 'error', severityText: '严重', title: 'P95 过高', desc: p95Desc, suggestion: p95Suggestion })
  } else if (p95Avg > 500) {
    p95Score = 50; p95Status = '较差'; p95Color = '#F56C6C'; score -= 15
    p95Desc = `P95 平均 ${p95Avg.toFixed(1)}ms，超出 <500ms 理想范围。`
    p95Suggestion = '进行代码剖析，检查索引和慢查询。'
    issues.push({ severity: 'warning', severityText: '警告', title: 'P95 偏高', desc: p95Desc, suggestion: p95Suggestion })
  } else if (p95Avg > 200) {
    p95Score = 75; p95Status = '良好'; p95Color = '#E6A23C'; score -= 5
    p95Desc = `P95 平均 ${p95Avg.toFixed(1)}ms，可接受，有优化空间。`
    p95Suggestion = '关注长尾请求，优化边缘场景。'
  }

  // P99
  let p99Score = 100, p99Status = '优秀', p99Color = '#67C23A'
  let p99Desc = `P99 平均 ${p99Avg.toFixed(1)}ms，长尾控制良好。`
  if (p99Avg > 1000) { p99Score = 35; p99Status = '严重'; p99Color = '#F56C6C'; p99Desc = `P99 平均 ${p99Avg.toFixed(1)}ms，长尾严重。`; score -= 10 }
  else if (p99Avg > 500) { p99Score = 65; p99Status = '一般'; p99Color = '#E6A23C'; p99Desc = `P99 平均 ${p99Avg.toFixed(1)}ms，存在延迟。`; score -= 5 }

  // 失败率
  let failScore = 100, failStatus = '优秀', failColor = '#67C23A'
  let failDesc = `失败率 ${failRate.toFixed(2)}%，全部正常。`
  let failSuggestion = '继续保持，建议定期回归验证。'
  if (failRate > 1) {
    failScore = 20; failStatus = '严重'; failColor = '#F56C6C'; score -= 25
    failDesc = `失败率 ${failRate.toFixed(2)}%，${execution.failures || 0}个失败。`
    failSuggestion = '立即查错误日志、超时配置和连接池。'
    issues.push({ severity: 'error', severityText: '严重', title: '失败率过高', desc: failDesc, suggestion: failSuggestion })
  } else if (failRate > 0.1) {
    failScore = 55; failStatus = '较差'; failColor = '#F56C6C'; score -= 12
    failDesc = `失败率 ${failRate.toFixed(2)}%，存在失败请求。`
    failSuggestion = '排查偶发超时，考虑重试和熔断。'
    issues.push({ severity: 'warning', severityText: '注意', title: '存在失败', desc: failDesc, suggestion: failSuggestion })
  } else if (failRate > 0.01) {
    failScore = 80; failStatus = '良好'; failColor = '#E6A23C'; score -= 3
    failDesc = `失败率 ${failRate.toFixed(2)}%，极少量失败。`
  }

  // 平均响应
  let avgScore = 100, avgStatus = '优秀', avgColor = '#67C23A'
  let avgDesc = `平均响应 ${avgAll.toFixed(1)}ms，速度快。`
  if (avgAll > 500) { avgScore = 45; avgStatus = '较差'; avgColor = '#F56C6C'; avgDesc = `平均 ${avgAll.toFixed(1)}ms，较慢。` }
  else if (avgAll > 200) { avgScore = 75; avgStatus = '良好'; avgColor = '#E6A23C'; avgDesc = `平均 ${avgAll.toFixed(1)}ms，可接受。` }

  // 吞吐量匹配
  let tpScore = 100, tpStatus = '优秀', tpColor = '#67C23A'
  const expected = execution.users || 0
  const tpDesc = expected > 0 && rpsAvg < expected * 0.8
    ? `并发${expected}，QPS 仅${rpsAvg.toFixed(1)}，未达预期。`
    : `并发${expected}，QPS ${rpsAvg.toFixed(1)}，匹配良好。`
  const tpSuggestion = rpsAvg < expected * 0.8 ? '排查阻塞操作和线程池配置。' : '资源利用率合理。'
  if (expected > 0 && rpsAvg < expected * 0.5) {
    tpScore = 40; tpStatus = '较差'; tpColor = '#F56C6C'; score -= 10
    issues.push({ severity: 'warning', severityText: '瓶颈', title: '吞吐量不足', desc: tpDesc, suggestion: tpSuggestion })
  } else if (expected > 0 && rpsAvg < expected * 0.8) {
    tpScore = 70; tpStatus = '一般'; tpColor = '#E6A23C'; score -= 5
  }

  // 综合
  const finalScore = Math.max(0, Math.round(score))
  let summary, fullSummary
  if (finalScore >= 90) {
    summary = `这个接口在 ${execution.users || '?'} 个并发下表现优秀，响应快，零失败 ✅`
    fullSummary = `综合评分 ${finalScore} 分。在 ${execution.users} 个并发用户下，系统稳定运行，QPS、响应时间、错误率均达标。建议将此结果作为性能基线。`
  } else if (finalScore >= 70) {
    summary = `在 ${execution.users || '?'} 并发下表现良好，部分指标有优化空间 ⚠️`
    fullSummary = `综合评分 ${finalScore} 分。整体尚可，但存在波动或偶发延迟，建议针对性优化后再验证。`
  } else if (finalScore >= 50) {
    summary = `在 ${execution.users || '?'} 并发下存在明显性能问题，需要优化 ⚠️`
    fullSummary = `综合评分 ${finalScore} 分。存在响应时间偏高或失败率偏高的问题，建议优先处理后再测试。`
  } else {
    summary = `在 ${execution.users || '?'} 并发下性能严重不达标，需紧急修复 ❌`
    fullSummary = `综合评分 ${finalScore} 分。性能严重不达标，建议立即排查并修复后再上线。`
  }

  const tags = []
  if (finalScore >= 90) tags.push({ text: '可上线', type: 'success' })
  else if (finalScore >= 70) tags.push({ text: '需关注', type: 'warning' })
  else tags.push({ text: '需优化', type: 'danger' })
  if (failRate === 0) tags.push({ text: '零失败', type: 'success' })
  if (p95Avg < 100) tags.push({ text: '响应快', type: 'success' })
  if (rpsCv < 0.3) tags.push({ text: '高稳定', type: 'success' })

  const metricReviews = [
    { name: 'QPS 稳定性', score: qpsScore, val: `${rpsAvg.toFixed(1)} req/s`, status: qpsStatus, color: qpsColor, desc: qpsDesc, suggestion: qpsSuggestion },
    { name: '平均响应', score: avgScore, val: `${avgAll.toFixed(1)} ms`, status: avgStatus, color: avgColor, desc: avgDesc, suggestion: '继续监控' },
    { name: 'P95 响应', score: p95Score, val: `${p95Avg.toFixed(1)} ms`, status: p95Status, color: p95Color, desc: p95Desc, suggestion: p95Suggestion },
    { name: 'P99 响应', score: p99Score, val: `${p99Avg.toFixed(1)} ms`, status: p99Status, color: p99Color, desc: p99Desc, suggestion: '继续监控' },
    { name: '失败率', score: failScore, val: `${failRate.toFixed(2)}%`, status: failStatus, color: failColor, desc: failDesc, suggestion: failSuggestion },
    { name: '响应趋势', score: trendScore, val: trendText, status: trendText === '稳定' ? '优秀' : trendText, color: trendText === '稳定' ? '#67C23A' : '#E6A23C', desc: trendText === '稳定' ? '全程稳定' : trendText, suggestion: trendText === '稳定' ? '定期回归验证' : '检查资源变化' },
    { name: '吞吐量匹配', score: tpScore, val: `${rpsAvg.toFixed(1)} / ${execution.users || 0} req/s`, status: tpStatus, color: tpColor, desc: tpDesc, suggestion: tpSuggestion },
  ]

  const recommendations = []
  if (failRate > 0.1) recommendations.push('优先解决失败：查错误日志、超时配置、连接池。')
  if (p95Avg > 500) recommendations.push('优化响应：做 Profiling、优化慢查询、加缓存。')
  if (rpsCv > 0.3) recommendations.push('稳定波动：排查 GC、连接池、负载不均。')
  if (trendText !== '稳定') recommendations.push('关注趋势：监控 CPU/内存/连接数。')
  if (expected > 0 && rpsAvg < expected * 0.8) recommendations.push('提升吞吐：排查阻塞和线程池。')
  if (recommendations.length === 0) {
    recommendations.push('当前表现优秀，建议保存为基线，定期回归验证。')
    recommendations.push('建议试试"梯度增压"，找到系统极限在哪里。')
  }

  return { score: finalScore, issues, tags, metricReviews, summary, fullSummary, recommendations }
}

// ===== 梯度增压分析 =====
const analyzeRamp = (data, execution) => {
  const issues = []
  let score = 100

  // 按用户数分组找阶梯
  const steps = []
  let prevUsers = -1
  for (const point of data) {
    const u = point.users || 0
    if (u !== prevUsers) {
      prevUsers = u
      steps.push({ users: u, points: [], avgMs: 0, rps: 0, failRate: 0 })
    }
    if (steps.length) steps[steps.length - 1].points.push(point)
  }

  // 计算每步统计
  steps.forEach(step => {
    const pts = step.points
    step.avgMs = pts.reduce((s, p) => s + (p.avg || 0), 0) / pts.length
    step.rps = pts.reduce((s, p) => s + (p.rps || 0), 0) / pts.length
    const totalFail = pts.reduce((s, p) => s + (p.failures_per_sec || 0), 0)
    step.failRate = step.rps > 0 ? (totalFail / (step.rps * pts.length) * 100) : 0
  })

  // 找拐点：响应时间陡升的阶梯
  let turningPoint = null
  let maxQpsStep = steps.length > 0 ? steps[0] : null
  let peakQps = 0

  for (let i = 0; i < steps.length; i++) {
    const curr = steps[i]
    if (curr.rps > peakQps) { peakQps = curr.rps; maxQpsStep = curr }
    if (i > 0 && !turningPoint) {
      const prev = steps[i - 1]
      if (prev.avgMs > 0 && curr.avgMs > prev.avgMs * 2) {
        turningPoint = { fromUsers: prev.users, toUsers: curr.users, fromMs: prev.avgMs, toMs: curr.avgMs }
      }
    }
  }

  // 打分逻辑
  if (turningPoint) {
    score -= 20
    issues.push({
      severity: 'warning', severityText: '拐点',
      title: `性能拐点：并发 ${turningPoint.toUsers}`,
      desc: `并发 ${turningPoint.fromUsers}→${turningPoint.toUsers} 时，响应时间从 ${turningPoint.fromMs.toFixed(1)}ms 跳到 ${turningPoint.toMs.toFixed(1)}ms，系统进入拐点区域。`,
      suggestion: `建议日常承载 < ${turningPoint.toUsers} 并发。超过此值需扩容或优化。`
    })
  }

  if (steps.some(s => s.failRate > 1)) {
    score -= 15
    issues.push({
      severity: 'error', severityText: '雪崩',
      title: '高并发下出现失败',
      desc: '阶梯加压过程中出现请求失败，系统在高并发下不够稳定。',
      suggestion: '排查高并发下的连接池耗尽、超时或限流配置。'
    })
  }

  const finalScore = Math.max(0, Math.round(score))
  const bestUsers = maxQpsStep ? maxQpsStep.users : 0

  let summary, fullSummary
  if (turningPoint) {
    summary = `并发 ${turningPoint.toUsers} 是性能拐点，建议日常承载 ${turningPoint.fromUsers} 以内`
    fullSummary = `梯度增压发现：并发从 ${turningPoint.fromUsers} 增加到 ${turningPoint.toUsers} 时响应时间剧增。QPS 峰值出现在 ${bestUsers} 并发时(${peakQps.toFixed(1)} req/s)。${finalScore >= 70 ? '系统在中低并发下表现正常。' : '需密切关注高并发下的表现。'}`
  } else {
    summary = `从低到 ${steps[steps.length - 1]?.users || '?'} 并发全程稳定，暂未发现拐点 ✅`
    fullSummary = `本次梯度增压未发现明显拐点，最大 QPS 为 ${peakQps.toFixed(1)} req/s（${bestUsers} 并发）。可以继续加大最大并发送验证极限。`
  }

  const tags = []
  if (turningPoint) tags.push({ text: `拐点@${turningPoint.toUsers}并发`, type: 'warning' })
  if (!turningPoint) tags.push({ text: '全程稳定', type: 'success' })
  if (maxQpsStep) tags.push({ text: `峰值QPS ${peakQps.toFixed(0)}`, type: 'info' })
  if (steps.some(s => s.failRate > 0)) tags.push({ text: '有失败', type: 'danger' })

  const metricReviews = [
    { name: '性能拐点', score: turningPoint ? 50 : 90, val: turningPoint ? `并发 ${turningPoint.toUsers}` : '未发现', status: turningPoint ? '需关注' : '优秀', color: turningPoint ? '#E6A23C' : '#67C23A', desc: turningPoint ? `在并发${turningPoint.toUsers}处响应急剧恶化` : '全程未出现性能拐点', suggestion: turningPoint ? `建议日常承载 < ${turningPoint.toUsers}` : '可继续加大并发测试' },
    { name: '最佳QPS', score: peakQps > 0 ? 85 : 60, val: `${peakQps.toFixed(1)} @${bestUsers}并发`, status: peakQps > 10 ? '良好' : '偏低', color: peakQps > 10 ? '#67C23A' : '#E6A23C', desc: `${bestUsers}并发时QPS达到峰值`, suggestion: '可将此并发设为日常容量参考' },
    { name: '阶梯数', score: steps.length >= 3 ? 85 : 60, val: `${steps.length} 个阶梯`, status: steps.length >= 3 ? '充分' : '较少', color: steps.length >= 3 ? '#67C23A' : '#E6A23C', desc: `从 ${steps[0]?.users || 1} 到 ${steps[steps.length-1]?.users || '?'} 分成 ${steps.length} 个阶梯`, suggestion: steps.length < 3 ? '建议增加阶梯数以获得更精细的拐点定位' : '阶梯密度合理' },
  ]

  const recommendations = []
  if (turningPoint) {
    recommendations.push(`建议将日常并发限制在 ${turningPoint.fromUsers} 以内，超过此值需扩容或优化。`)
    recommendations.push(`优化后可再次梯度测试验证拐点是否后移。`)
  } else {
    recommendations.push('尝试更大的最大并发数，探索系统真正极限。')
  }
  if (steps.some(s => s.failRate > 0)) {
    recommendations.push('高并发下出现失败，排查连接池、超时和限流配置。')
  }

  return { score: finalScore, issues, tags, metricReviews, summary, fullSummary, recommendations }
}

// ===== 混合场景分析（占位） =====
const analyzeMixed = (data, execution) => {
  return {
    score: 75,
    issues: [{ severity: 'info', severityText: '预告', title: '混合场景分析即将上线', desc: '将支持多接口独立分析、瓶颈接口标注和优化优先级排序。', suggestion: '敬请期待' }],
    tags: [{ text: '多接口', type: 'info' }, { text: '场景化', type: 'info' }],
    metricReviews: [],
    summary: '混合场景分析功能正在开发中...',
    fullSummary: '混合场景将支持多接口权重配比的性能分析，对各接口独立指标计算和整体瓶颈识别。',
    recommendations: ['混合场景功能即将推出，当前可用基准或梯度测试']
  }
}

// AI 评分圆环样式
const scoreCircleClass = computed(() => {
  const s = aiAnalysis.value.score
  if (s >= 80) return 'score-excellent'
  if (s >= 60) return 'score-good'
  return 'score-bad'
})
const scoreLabel = computed(() => {
  const s = aiAnalysis.value.score
  if (s >= 90) return '优秀'
  if (s >= 80) return '良好'
  if (s >= 60) return '一般'
  if (s >= 40) return '较差'
  return '严重'
})

// AI 摘要图标
const aiSummaryIcon = computed(() => {
  const s = aiAnalysis.value.score
  if (s >= 80) return { icon: 'CircleCheck', color: '#67C23A', textClass: 'text-success' }
  if (s >= 60) return { icon: 'InfoFilled', color: '#E6A23C', textClass: 'text-warning' }
  return { icon: 'WarningFilled', color: '#F56C6C', textClass: 'text-danger' }
})


const hasMetricsTimeline = computed(() => {
  return execution.value.metrics_timeline && execution.value.metrics_timeline.length > 0
})

// ---------- ECharts 图表 ----------
const chartRef = ref(null)
let chartInstance = null
let echartsLoaded = false

const loadECharts = () => {
  return new Promise((resolve) => {
    if (window.echarts) { echartsLoaded = true; resolve(); return }

    const script = document.createElement('script')
    script.src = 'https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js'
    script.onload = () => { echartsLoaded = true; resolve() }
    script.onerror = () => resolve() // 静默失败
    document.head.appendChild(script)
  })
}

const renderChart = async () => {
  if (!hasMetricsTimeline.value || !chartRef.value) return

  await nextTick()
  if (!echartsLoaded) await loadECharts()
  if (!window.echarts) return

  const data = execution.value.metrics_timeline
  if (!data || !data.length) return

  if (!chartInstance) {
    chartInstance = window.echarts.init(chartRef.value)
  }

  const timestamps = data.map(d => d.timestamp + 's')

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: ['QPS', 'P95(ms)', 'P50(ms)', '错误/s'],
      top: 0
    },
    grid: {
      left: 60, right: 60, top: 40, bottom: 40
    },
    xAxis: {
      type: 'category',
      data: timestamps,
      axisLabel: { fontSize: 11 }
    },
    yAxis: [
      {
        type: 'value',
        name: 'QPS / 错误数',
        axisLabel: { fontSize: 11 }
      },
      {
        type: 'value',
        name: '响应时间 (ms)',
        axisLabel: { fontSize: 11 }
      }
    ],
    series: [
      {
        name: 'QPS',
        type: 'line',
        data: data.map(d => d.rps),
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#409EFF', width: 2 },
        areaStyle: { color: 'rgba(64,158,255,0.1)' }
      },
      {
        name: 'P95(ms)',
        type: 'line',
        yAxisIndex: 1,
        data: data.map(d => d.p95),
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#E6A23C', width: 2 }
      },
      {
        name: 'P50(ms)',
        type: 'line',
        yAxisIndex: 1,
        data: data.map(d => d.p50),
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#67C23A', width: 2 }
      },
      {
        name: '错误/s',
        type: 'line',
        data: data.map(d => d.failures_per_sec),
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#F56C6C', width: 1.5, type: 'dashed' }
      }
    ]
  }

  chartInstance.setOption(option, true)

  // 自适应
  window.addEventListener('resize', () => chartInstance?.resize())
}

// 监听数据更新后重新渲染图表
watch(() => execution.value.metrics_timeline, () => {
  nextTick(() => renderChart())
}, { deep: true })

// ---------- 数据加载 ----------
const refreshData = async () => {
  refreshing.value = true
  try {
    // 如果正在运行，用 metrics 接口获取最新数据
    if (execution.value.status === 'running') {
      const res = await perfAPI.getMetrics(execution.value.id)
      Object.assign(execution.value, res)
    } else {
      const res = await perfAPI.getExecution(execution.value.id)
      Object.assign(execution.value, res)
    }
    renderChart()
  } catch (e) {
    console.error('Refresh error:', e)
  } finally {
    refreshing.value = false
  }
}

let pollTimer = null

onMounted(async () => {
  // 首次加载：总是获取完整执行详情（包含用例名称、URL、执行人等）
  refreshing.value = true
  try {
    const res = await perfAPI.getExecution(execution.value.id)
    Object.assign(execution.value, res)
    renderChart()
  } catch (e) {
    console.error('Load detail error:', e)
  } finally {
    refreshing.value = false
  }

  // 加载同用例历史执行记录
  await loadHistory()

  // 如果执行中，每秒轮询一次（只拉实时指标）
  if (execution.value.status === 'running') {
    pollTimer = setInterval(async () => {
      try {
        const res = await perfAPI.getMetrics(execution.value.id)
        Object.assign(execution.value, res)
        renderChart()
        // 完成后停止轮询
        if (execution.value.status !== 'running') {
          clearInterval(pollTimer)
          pollTimer = null
          // 最终加载完整数据
          await refreshData()
        }
      } catch { /* 忽略轮询错误 */ }
    }, 2000)
  }
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

// ---------- 停止 ----------
const handleStop = async () => {
  try {
    await ElMessageBox.confirm('确定要停止当前压测吗？', '确认停止', { type: 'warning' })
  } catch { return }

  stopping.value = true
  try {
    await perfAPI.stopExecution(execution.value.id)
    ElMessage.success('停止指令已发送')
    execution.value.status = 'stopped'
  } catch (e) {
    console.error('Stop error:', e)
  } finally {
    stopping.value = false
  }
}

// ---------- AI 诊断 ----------
const handleDiagnose = async () => {
  diagnosing.value = true
  try {
    await perfAPI.diagnoseExecution(execution.value.id)
    ElMessage.success('AI 诊断已触发，分析中...')

    // 轮询等待 AI 诊断结果
    let retries = 0
    const maxRetries = 15
    const checkResult = setInterval(async () => {
      retries++
      try {
        const res = await perfAPI.getMetrics(execution.value.id)
        Object.assign(execution.value, res)
        if (res.exec_summary && res.exec_summary.score != null) {
          clearInterval(checkResult)
          ElMessage.success('AI 诊断完成！')
        } else if (retries >= maxRetries) {
          clearInterval(checkResult)
          ElMessage.warning('AI 诊断超时，请稍后刷新')
        }
      } catch {
        if (retries >= maxRetries) {
          clearInterval(checkResult)
        }
      }
    }, 3000)
  } catch (e) {
    ElMessage.error('触发诊断失败: ' + (e.response?.data?.error || e.message))
  } finally {
    diagnosing.value = false
  }
}

// ---------- 工具 ----------
const statusTagType = (s) => {
  const map = { completed: 'success', running: 'primary', failed: 'danger', stopped: 'warning', pending: 'info' }
  return map[s] || 'info'
}
</script>

<style scoped>
.top-bar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.perf-detail-container {
  padding: 20px;
}
.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-title {
  font-size: 18px;
  font-weight: 600;
  color: #ffffff;
}
.back-btn {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.25);
  color: #ffffff;
}
.back-btn:hover,
.back-btn:focus {
  background: rgba(255, 255, 255, 0.22);
  border-color: rgba(255, 255, 255, 0.35);
  color: #ffffff;
}
.back-btn :deep(.el-icon) {
  color: #ffffff;
}
.info-card {
  margin-bottom: 0;
}
.metric-card {
  text-align: center;
  cursor: default;
  padding: 10px;
}
.metric-card.small {
  padding: 8px;
}
.metric-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.metric-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}
.metric-value.small-val {
  font-size: 20px;
}
.metric-value .unit {
  font-size: 14px;
  font-weight: 400;
  margin-left: 2px;
  color: #909399;
}
.metric-value.primary { color: #409EFF; }
.metric-value.success { color: #67C23A; }
.metric-value.danger  { color: #F56C6C; }
.metric-value.warning { color: #E6A23C; }

.log-box {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.6;
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  margin: 0;
}

/* AI 性能诊断样式 */
.ai-analysis-card {
  border-left: 4px solid #e65c00;
}
.ai-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ai-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ai-title {
  font-weight: 600;
  font-size: 15px;
}
.ai-brief {
  padding: 8px 0;
}
.ai-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 500;
  margin-bottom: 10px;
}
.ai-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.ai-metrics-review {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  padding: 4px 0;
}
.metric-review-item {
  padding: 8px 10px;
  border-radius: 6px;
  background: #f8f9fa;
}
.review-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.review-name {
  font-size: 12px;
  color: #606266;
  flex-shrink: 0;
  width: 56px;
}
.review-val {
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}
.review-status {
  font-size: 11px;
}
.review-desc {
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}
.ai-footer {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}

/* AI 对话框样式 */
.ai-dialog-content {
  max-height: 600px;
  overflow-y: auto;
}
.ai-dialog-score {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 10px 0;
}
.score-circle {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 4px solid;
  flex-shrink: 0;
}
.score-circle.score-excellent { border-color: #67C23A; background: #f0f9eb; }
.score-circle.score-good { border-color: #E6A23C; background: #fdf6ec; }
.score-circle.score-bad { border-color: #F56C6C; background: #fef0f0; }
.score-number {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
}
.score-label {
  font-size: 12px;
  color: #606266;
}
.score-summary {
  flex: 1;
}
.score-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 6px;
}
.score-desc {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
}
.dimension-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 10px;
}
.dimension-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.dimension-name {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  width: 80px;
  flex-shrink: 0;
}
.dimension-val {
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}
.dimension-desc {
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
  line-height: 1.5;
}
.dimension-suggestion {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  font-size: 13px;
  color: #409eff;
  line-height: 1.5;
}
.issue-card {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 10px;
}
.issue-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.issue-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}
.issue-desc {
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
  line-height: 1.5;
  padding-left: 24px;
}
.issue-suggestion {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  font-size: 13px;
  color: #409eff;
  padding-left: 24px;
  line-height: 1.5;
}
.recommend-item {
  display: flex;
  gap: 8px;
  padding: 8px 0;
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  border-bottom: 1px solid #f0f2f5;
}
.recommend-item:last-child {
  border-bottom: none;
}
.rec-index {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.rec-text {
  flex: 1;
}
.text-success { color: #67C23A; }
.text-warning { color: #E6A23C; }
.text-danger { color: #F56C6C; }
</style>

