<template>
  <div class="self-healing-monitor">
    <div class="page-header">
      <h2>自主纠错监控</h2>
      <p class="subtitle">AI 驱动的错误自动诊断与修复</p>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="总修复次数" :value="stats.total_heals">
            <template #prefix><el-icon><MagicStick /></el-icon></template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-success">
          <el-statistic title="修复成功" :value="stats.successful_heals">
            <template #prefix><el-icon><CircleCheck /></el-icon></template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-danger">
          <el-statistic title="修复失败" :value="stats.failed_heals">
            <template #prefix><el-icon><CircleClose /></el-icon></template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-info">
          <el-statistic title="成功率" :value="successRate" suffix="%">
            <template #prefix><el-icon><TrendCharts /></el-icon></template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>

    <!-- 工具区 -->
    <el-row :gutter="20">
      <!-- 左侧：错误分类测试 -->
      <el-col :span="12">
        <el-card header="错误分类分析器" class="analyzer-card">
          <el-form label-width="80px">
            <el-form-item label="错误消息">
              <el-input
                v-model="errorInput"
                type="textarea"
                :rows="4"
                placeholder="粘贴错误消息...如: ConnectionError: 无法连接 API 服务器"
              />
            </el-form-item>
            <el-form-item label="上下文">
              <el-input
                v-model="contextInput"
                type="textarea"
                :rows="2"
                placeholder='{"step_name": "testcase_generation", "agent": "generator"}'
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="analyzeError" :loading="analyzing">
                <el-icon><Search /></el-icon> 智能分析
              </el-button>
              <el-button @click="loadPreset">使用示例</el-button>
            </el-form-item>
          </el-form>

          <!-- 分析结果 -->
          <div v-if="analysisResult" class="analysis-result">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="类别">
                <el-tag :type="severityType(analysisResult.severity)" size="small">
                  {{ analysisResult.category }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="严重程度">
                <el-tag :type="severityType(analysisResult.severity)" size="small">
                  {{ analysisResult.severity }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="可修复" :span="2">
                <el-tag :type="analysisResult.fixable ? 'success' : 'danger'" size="small">
                  {{ analysisResult.fixable ? '✅ 可自动修复' : '❌ 需人工介入' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="摘要" :span="2">
                {{ analysisResult.summary }}
              </el-descriptions-item>
              <el-descriptions-item label="根因" :span="2">
                {{ analysisResult.root_cause }}
              </el-descriptions-item>
              <el-descriptions-item label="建议策略" :span="2">
                <el-tag v-for="s in analysisResult.suggested_strategies" :key="s" size="small" style="margin:2px">
                  {{ s }}
                </el-tag>
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：批量分析 + 修复历史 -->
      <el-col :span="12">
        <el-card header="批量错误分析" class="batch-card">
          <el-input
            v-model="batchErrors"
            type="textarea"
            :rows="5"
            placeholder="每行一个错误消息..."
          />
          <div style="margin-top: 12px">
            <el-button type="primary" @click="analyzeBatch" :loading="batchAnalyzing">
              批量分析 ({{ batchErrorList.length }}条)
            </el-button>
          </div>

          <div v-if="batchResults.length" class="batch-results" style="margin-top: 16px">
            <el-collapse>
              <el-collapse-item
                v-for="(r, i) in batchResults" :key="i"
                :title="`#${i+1} ${r.analysis.category} — ${r.error.substring(0, 40)}...`"
              >
                <el-tag :type="r.analysis.fixable ? 'success' : 'danger'" size="small">
                  {{ r.analysis.fixable ? '可修复' : '不可修复' }}
                </el-tag>
                <el-tag size="small" style="margin-left:8px">{{ r.analysis.summary }}</el-tag>
                <p style="font-size:12px;color:#909399;margin-top:8px">策略: {{ r.analysis.suggested_strategies.join(', ') }}</p>
              </el-collapse-item>
            </el-collapse>
          </div>
        </el-card>

        <!-- 修复历史 -->
        <el-card header="修复历史记录" class="history-card" style="margin-top: 16px">
          <el-timeline v-if="healingHistory.length">
            <el-timeline-item
              v-for="record in healingHistory" :key="record.id"
              :timestamp="record.timestamp"
              :type="record.success ? 'success' : 'danger'"
              :icon="record.success ? CircleCheck : CircleClose"
            >
              <p><strong>{{ record.step_name }}</strong> — {{ record.strategy_used }}</p>
              <p style="font-size:12px;color:#909399">
                尝试 {{ record.attempts }} 次 · {{ record.duration_ms }}ms · {{ record.notes }}
              </p>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无修复记录" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, CircleCheck, CircleClose, TrendCharts, Search } from '@element-plus/icons-vue'

const errorInput = ref('')
const contextInput = ref('')
const analyzing = ref(false)
const batchAnalysing = ref(false)
const batchErrors = ref('')
const analysisResult = ref(null)
const batchResults = ref([])
const healingHistory = ref([])
const stats = ref({ total_heals: 0, successful_heals: 0, failed_heals: 0 })

const successRate = computed(() => {
  if (stats.value.total_heals === 0) return 0
  return Math.round((stats.value.successful_heals / stats.value.total_heals) * 100)
})

const batchErrorList = computed(() => {
  return batchErrors.value.split('\n').filter(l => l.trim())
})

const severityType = (s) => {
  const map = { low: 'info', medium: 'warning', high: 'danger', critical: 'danger' }
  return map[s] || 'info'
}

const apiHeaders = () => ({
  'Content-Type': 'application/json',
  Authorization: `Bearer ${localStorage.getItem('token')}`,
})

const analyzeError = async () => {
  if (!errorInput.value.trim()) {
    ElMessage.warning('请输入错误消息')
    return
  }
  analyzing.value = true
  let ctx = {}
  try { ctx = JSON.parse(contextInput.value) } catch { /* ignore */ }
  try {
    const res = await fetch('/api/agent/self-healing/analyze/', {
      method: 'POST', headers: apiHeaders(),
      body: JSON.stringify({ error: errorInput.value, context: ctx }),
    })
    const data = await res.json()
    analysisResult.value = data.analysis
  } catch (e) {
    ElMessage.error('分析失败: ' + e.message)
  } finally {
    analyzing.value = false
  }
}

const analyzeBatch = async () => {
  if (!batchErrorList.value.length) {
    ElMessage.warning('请至少输入一条错误')
    return
  }
  batchAnalyzing.value = true
  try {
    const res = await fetch('/api/agent/self-healing/classify-batch/', {
      method: 'POST', headers: apiHeaders(),
      body: JSON.stringify({ errors: batchErrorList.value.map(e => ({ error: e })) }),
    })
    const data = await res.json()
    batchResults.value = data.results || []
    ElMessage.success(`已分析 ${data.count} 条错误`)
  } catch (e) {
    ElMessage.error('批量分析失败')
  } finally {
    batchAnalyzing.value = false
  }
}

const loadPreset = () => {
  errorInput.value = 'ConnectionError: Failed to connect to API server at https://api.example.com: ETIMEDOUT'
  contextInput.value = '{"step_name": "execution", "agent": "execution"}'
}

const loadStats = async () => {
  try {
    const [sRes, hRes] = await Promise.all([
      fetch('/api/agent/self-healing/stats/', { headers: apiHeaders() }),
      fetch('/api/agent/self-healing/history/?limit=10', { headers: apiHeaders() }),
    ])
    const sData = await sRes.json()
    const hData = await hRes.json()
    stats.value = sData.stats || stats.value
    healingHistory.value = hData.history || []
  } catch { /* ignore */ }
}

onMounted(() => {
  loadStats()
})
</script>

<style scoped>
.self-healing-monitor { padding: 20px; max-width: 1400px; margin: 0 auto; }
.page-header { margin-bottom: 20px; }
.page-header h2 { margin: 0 0 4px; font-size: 24px; }
.subtitle { color: #909399; font-size: 14px; margin: 0; }
.stats-row { margin-bottom: 20px; }
.stat-card { text-align: center; }
.stat-success :deep(.el-statistic__number) { color: #67c23a; }
.stat-danger :deep(.el-statistic__number) { color: #f56c6c; }
.stat-info :deep(.el-statistic__number) { color: #409eff; }
.analyzer-card, .batch-card, .history-card { margin-bottom: 0; }
.analysis-result { margin-top: 16px; }
</style>
