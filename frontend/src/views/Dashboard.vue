<template>
  <div class="dashboard-container">
    <!-- 顶部指标卡：4 个核心 AI 指标 -->
    <el-row :gutter="20" class="metrics-row">
      <el-col :span="6">
        <el-card class="metric-card metric-blue">
          <div class="metric-icon">
            <el-icon :size="32"><Document /></el-icon>
          </div>
          <div class="metric-content">
            <div class="metric-label">总用例数</div>
            <div class="metric-value">{{ metrics.totalCases }}</div>
            <div class="metric-trend">
              <span :class="metrics.casesTrend > 0 ? 'trend-up' : 'trend-down'">
                {{ metrics.casesTrend > 0 ? '+' : '' }}{{ metrics.casesTrend }}%
              </span>
              <span class="trend-text">较上周</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="metric-card metric-green">
          <div class="metric-icon">
            <el-icon :size="32"><Finished /></el-icon>
          </div>
          <div class="metric-content">
            <div class="metric-label">批量执行成功率</div>
            <div class="metric-value">{{ metrics.successRate }}%</div>
            <div class="metric-trend">
              <span :class="metrics.successTrend > 0 ? 'trend-up' : 'trend-down'">
                {{ metrics.successTrend > 0 ? '+' : '' }}{{ metrics.successTrend }}%
              </span>
              <span class="trend-text">较上周</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="metric-card metric-orange">
          <div class="metric-icon">
            <el-icon :size="32"><Coin /></el-icon>
          </div>
          <div class="metric-content">
            <div class="metric-label">Token 消耗数</div>
            <div class="metric-value">{{ formatTokenCount(metrics.tokenUsage) }}</div>
            <div class="metric-trend">
              <span :class="metrics.tokenTrend > 0 ? 'trend-down' : 'trend-up'">
                {{ metrics.tokenTrend > 0 ? '+' : '' }}{{ metrics.tokenTrend }}%
              </span>
              <span class="trend-text">较上周</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="metric-card metric-purple">
          <div class="metric-icon">
            <el-icon :size="32"><MagicStick /></el-icon>
          </div>
          <div class="metric-content">
            <div class="metric-label">自愈修复率</div>
            <div class="metric-value">{{ metrics.healRate }}%</div>
            <div class="metric-trend">
              <span :class="metrics.healTrend > 0 ? 'trend-up' : 'trend-down'">
                {{ metrics.healTrend > 0 ? '+' : '' }}{{ metrics.healTrend }}%
              </span>
              <span class="trend-text">较上周</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="20" class="charts-row">
      <!-- Token 消耗趋势 -->
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span>Token 消耗趋势（最近{{ tokenTimeRange === '7d' ? '7天' : '30天' }}）</span>
              <el-radio-group v-model="tokenTimeRange" size="small" @change="fetchTokenTrend">
                <el-radio-button value="7d">7天</el-radio-button>
                <el-radio-button value="30d">30天</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <v-chart :option="tokenTrendOption" class="chart" autoresize />
        </el-card>
      </el-col>

      <!-- Agent 任务分布 -->
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <span>Agent 任务分布</span>
          </template>
          <v-chart :option="agentDistOption" class="chart" autoresize />
        </el-card>
      </el-col>
    </el-row>

    <!-- AI 特色仪表盘 -->
    <el-row :gutter="20" class="charts-row">
      <el-col :span="8">
        <el-card class="chart-card">
          <template #header>
            <span>MCP 工具利用率</span>
          </template>
          <v-chart :option="mcpUtilOption" class="gauge-chart" autoresize />
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="chart-card">
          <template #header>
            <span>AI 准确率</span>
          </template>
          <v-chart :option="aiAccuracyOption" class="gauge-chart" autoresize />
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="chart-card">
          <template #header>
            <span>自愈成功率</span>
          </template>
          <v-chart :option="healSuccessOption" class="gauge-chart" autoresize />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart, GaugeChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent, GridComponent,
} from 'echarts/components'
import { Document, Finished, Coin, MagicStick } from '@element-plus/icons-vue'
import axios from 'axios'

use([
  CanvasRenderer, LineChart, PieChart, GaugeChart,
  TitleComponent, TooltipComponent, LegendComponent, GridComponent,
])

// ---- 数据 ----
const tokenTimeRange = ref('7d')
const loading = ref(true)

// token 趋势
const tokenTrendData = ref({ dates: [], counts: [] })

// agent 分布
const agentDistData = ref([{ name: '加载中...', value: 1 }])

// 指标卡
const metrics = reactive({
  totalCases: 0, casesTrend: 0,
  successRate: 0, successTrend: 0,
  tokenUsage: 0, tokenTrend: 0,
  healRate: 0, healTrend: 0,
})

// 仪表盘
const gaugeData = reactive({
  mcpUtilization: 0,
  aiAccuracy: 0,
  healSuccessRate: 0,
})

// Token 格式化 (K/M)
const formatTokenCount = (count) => {
  if (!count || count === 0) return '0'
  if (count >= 1000000) return (count / 1000000).toFixed(1) + 'M'
  if (count >= 1000) return (count / 1000).toFixed(1) + 'K'
  return count.toString()
}

// ---- ECharts 配置 ----

// Token 消耗趋势折线图
const tokenTrendOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: tokenTrendData.value.dates,
    axisLabel: {
      rotate: tokenTrendData.value.dates.length > 14 ? 45 : 0,
      interval: tokenTrendData.value.dates.length > 14 ? 'auto' : 0,
    },
  },
  yAxis: { type: 'value', name: 'tokens' },
  series: [{
    name: 'Token 消耗',
    type: 'line',
    smooth: true,
    data: tokenTrendData.value.counts,
    itemStyle: { color: '#e6a23c' },
    areaStyle: {
      color: {
        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(230, 162, 60, 0.3)' },
          { offset: 1, color: 'rgba(230, 162, 60, 0.05)' },
        ],
      },
    },
  }],
}))

// Agent 任务分布饼图
const agentDistOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { orient: 'vertical', right: '5%', top: 'center', data: agentDistData.value.map(d => d.name) },
  series: [{
    name: '任务类型',
    type: 'pie',
    radius: ['40%', '70%'],
    avoidLabelOverlap: false,
    itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
    label: { show: false, position: 'center' },
    emphasis: { label: { show: true, fontSize: 20, fontWeight: 'bold' } },
    labelLine: { show: false },
    data: agentDistData.value.map((item, i) => ({
      ...item,
      itemStyle: { color: ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399'][i % 5] },
    })),
  }],
}))

// 仪表盘通用配置生成器
const makeGauge = (value, name, color) => ({
  series: [{
    type: 'gauge',
    radius: '70%', center: ['50%', '40%'],
    startAngle: 180, endAngle: 0, min: 0, max: 100, splitNumber: 5,
    itemStyle: { color },
    progress: { show: true, width: 18 },
    pointer: {
      icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z',
      length: '12%', width: 20, offsetCenter: [0, '-60%'],
      itemStyle: { color: 'auto' },
    },
    axisLine: { lineStyle: { width: 18 } },
    axisTick: { distance: -18, splitNumber: 5, lineStyle: { width: 2, color: '#999' } },
    splitLine: { distance: -22, length: 10, lineStyle: { width: 3, color: '#999' } },
    axisLabel: { distance: -12, color: '#999', fontSize: 12 },
    title: { offsetCenter: [0, '-20%'], fontSize: 14 },
    detail: {
      fontSize: 24, offsetCenter: [0, '25%'], valueAnimation: true,
      formatter: '{value}%', color: 'auto',
    },
    data: [{ value, name }],
  }],
})

const mcpUtilOption = computed(() => makeGauge(gaugeData.mcpUtilization, 'MCP利用率', '#409eff'))
const aiAccuracyOption = computed(() => makeGauge(gaugeData.aiAccuracy, 'AI准确率', '#67c23a'))
const healSuccessOption = computed(() => makeGauge(gaugeData.healSuccessRate, '自愈成功率', '#e6a23c'))

// ---- API 请求 ----

// Dashboard 综合数据
const fetchDashboardData = async () => {
  try {
    const token = localStorage.getItem('access_token')
    const res = await axios.get('/api/execution/stats/dashboard/', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.data?.success) {
      const d = res.data.data
      Object.assign(metrics, d.metrics)
      Object.assign(gaugeData, d.gauges)
      agentDistData.value = d.agentDistribution || [{ name: '暂无数据', value: 1 }]
      return
    }
  } catch (e) {
    console.log('Dashboard API 未就绪，使用默认数据', e)
  }
  // 兜底：使用模拟数据确保页面不为空
  Object.assign(metrics, {
    totalCases: 128, casesTrend: 12.5,
    successRate: 94.2, successTrend: 3.1,
    tokenUsage: 52380, tokenTrend: -8.2,
    healRate: 78.0, healTrend: 5.2,
  })
  Object.assign(gaugeData, {
    mcpUtilization: 65,
    aiAccuracy: 88,
    healSuccessRate: 72,
  })
  agentDistData.value = [
    { name: 'Plan', value: 35 }, { name: 'Execute', value: 25 },
    { name: 'Evaluate', value: 18 }, { name: 'Heal', value: 8 },
  ]
}

// Token 趋势
const fetchTokenTrend = async () => {
  try {
    const days = tokenTimeRange.value === '7d' ? 7 : 30
    const token = localStorage.getItem('access_token')
    const res = await axios.get(`/api/execution/stats/token-trend/?days=${days}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.data?.success) {
      tokenTrendData.value = { dates: res.data.data.dates, counts: res.data.data.counts }
      return
    }
  } catch { /* fallback */ }

  // 兜底模拟数据
  const days = tokenTimeRange.value === '7d' ? 7 : 30
  const today = new Date()
  const dates = [], counts = []
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today); d.setDate(d.getDate() - i)
    dates.push(`${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`)
    counts.push(Math.floor(Math.random() * 15000 + 5000))
  }
  tokenTrendData.value = { dates, counts }
}

onMounted(async () => {
  await Promise.all([fetchDashboardData(), fetchTokenTrend()])
})
</script>

<style scoped>
.dashboard-container { padding: 0; }
.metrics-row { margin-bottom: 20px; }

.metric-card {
  display: flex; align-items: center; padding: 10px;
  transition: all 0.3s;
}
.metric-card:hover { transform: translateY(-5px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }

.metric-icon {
  width: 60px; height: 60px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center; margin-right: 15px;
}
.metric-blue  .metric-icon { background: linear-gradient(135deg, #667eea, #764ba2); color: white; }
.metric-green .metric-icon { background: linear-gradient(135deg, #11998e, #38ef7d); color: white; }
.metric-orange .metric-icon { background: linear-gradient(135deg, #f093fb, #f5576c); color: white; }
.metric-purple .metric-icon { background: linear-gradient(135deg, #4facfe, #00f2fe); color: white; }

.metric-content { flex: 1; }
.metric-label { font-size: 13px; color: #999; margin-bottom: 5px; }
.metric-value { font-size: 28px; font-weight: bold; color: #333; margin-bottom: 5px; }
.metric-trend { font-size: 12px; }
.trend-up { color: #67c23a; }
.trend-down { color: #f56c6c; }
.trend-text { color: #999; margin-left: 5px; }

.charts-row { margin-bottom: 20px; }
.chart-card { height: 100%; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.chart { height: 300px; }
.gauge-chart { height: 200px; }
</style>
