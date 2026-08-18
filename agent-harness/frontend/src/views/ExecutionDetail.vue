<template>
  <div class="execution-detail-container" v-loading="loading">
    <template v-if="execution">
      <!-- 顶部操作栏 -->
      <div class="action-bar">
        <el-page-header @back="goBack" :title="'返回'" />
        <div class="action-buttons">
          <el-button type="primary" @click="rerunExecution">
            <el-icon><Refresh /></el-icon> 重新执行
          </el-button>
          <el-dropdown @command="handleExport" :disabled="exporting">
            <el-button :loading="exporting">
              <el-icon><Download /></el-icon> 导出报告<el-icon><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="pdf">
                  <el-icon><Document /></el-icon> 导出 PDF
                </el-dropdown-item>
                <el-dropdown-item command="html">
                  <el-icon><Notebook /></el-icon> 导出 Allure 报告
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <!-- 概览卡片 -->
      <el-card class="overview-card" shadow="never">
        <el-row :gutter="20">
          <el-col :span="16">
            <h3 class="exec-title">{{ execution.name || `执行 #${execution.id}` }}</h3>
            <el-descriptions :column="2" border size="default">
              <el-descriptions-item label="关联套件">
                <el-link v-if="execution.suite_id && execution.suite_name" type="primary" @click="goToSuite">
                  {{ execution.suite_name }}
                </el-link>
                <span v-else>-</span>
              </el-descriptions-item>
              <el-descriptions-item label="触发方式">
                <el-tag size="small">{{ execution.trigger_type_display || execution.trigger_type }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="执行人">{{ execution.started_by_name || '-' }}</el-descriptions-item>
              <el-descriptions-item label="环境">
                <el-tag size="small" :type="getEnvType(execution.environment)">
                  {{ execution.environment_display || execution.environment }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="开始时间">{{ formatDate(execution.started_at) }}</el-descriptions-item>
              <el-descriptions-item label="总耗时">{{ execution.duration ? execution.duration + ' 秒' : '-' }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="getStatusType(execution.status)" size="small">
                  {{ execution.status_display || getStatusText(execution.status) }}
                </el-tag>
              </el-descriptions-item>
            </el-descriptions>
          </el-col>
          <el-col :span="8">
            <div class="stats-overview">
              <div class="stat-box total">
                <div class="stat-number">{{ execution.total_cases }}</div>
                <div class="stat-label">总数</div>
              </div>
              <div class="stat-box passed">
                <div class="stat-number">{{ execution.passed_cases }}</div>
                <div class="stat-label">通过</div>
              </div>
              <div class="stat-box failed">
                <div class="stat-number">{{ execution.failed_cases }}</div>
                <div class="stat-label">失败</div>
              </div>
              <div class="stat-box skipped">
                <div class="stat-number">{{ execution.skipped_cases }}</div>
                <div class="stat-label">跳过</div>
              </div>
            </div>
          </el-col>
        </el-row>
      </el-card>

      <!-- 执行总结 -->
      <el-card class="summary-card" shadow="never" style="margin-top: 16px" v-if="execution.summary">
        <template #header>
          <span>执行总结</span>
        </template>
        <div class="summary-body">{{ execution.summary }}</div>
      </el-card>

      <!-- 失败详情抽屉（API用例） -->
      <el-drawer
        v-model="failureDrawerVisible"
        title="失败详情"
        size="50%"
        destroy-on-close
      >
        <template v-if="selectedCase && selectedCase.type !== 'web'">
          <h4>请求信息</h4>
          <el-descriptions :column="1" border size="small" style="margin-bottom: 16px">
            <el-descriptions-item label="URL">{{ selectedCase.request_url || selectedCase.api_endpoint }}</el-descriptions-item>
            <el-descriptions-item label="方法">{{ selectedCase.request_method || selectedCase.method }}</el-descriptions-item>
            <el-descriptions-item label="Headers">
              <pre class="json-block">{{ formatJSON(selectedCase.request_headers) }}</pre>
            </el-descriptions-item>
            <el-descriptions-item label="Body">
              <pre class="json-block">{{ formatJSON(selectedCase.request_body) }}</pre>
            </el-descriptions-item>
          </el-descriptions>

          <h4>响应信息</h4>
          <el-descriptions :column="1" border size="small" style="margin-bottom: 16px">
            <el-descriptions-item label="状态码">{{ selectedCase.response_status_code || '-' }}</el-descriptions-item>
            <el-descriptions-item label="响应体">
              <pre class="json-block">{{ formatJSON(selectedCase.response_body) }}</pre>
            </el-descriptions-item>
          </el-descriptions>

          <h4 style="color: #f56c6c">失败原因</h4>
          <el-alert type="error" :closable="false" style="margin-top: 8px">
            {{ selectedCase.error || '未知错误' }}
          </el-alert>
        </template>
        <!-- Web 用例失败时也复用此抽屉 -->
        <template v-else-if="selectedCase && selectedCase.type === 'web'">
          <h4>Web 用例信息</h4>
          <el-descriptions :column="1" border size="small" style="margin-bottom: 16px">
            <el-descriptions-item label="目标 URL">
              <el-link :href="selectedCase.target_url" target="_blank" type="primary">{{ selectedCase.target_url }}</el-link>
            </el-descriptions-item>
            <el-descriptions-item label="引擎类型">
              <el-tag :type="selectedCase.engine === 'ai' ? 'danger' : 'success'" size="small">
                {{ selectedCase.engine === 'ai' ? 'AI(Midscene)' : (selectedCase.engine || 'Playwright') }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="执行状态">
              <el-tag :type="getCaseStatusType(selectedCase.status)" size="small">{{ getCaseStatusText(selectedCase.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="耗时">{{ selectedCase.duration ? selectedCase.duration + 's' : '-' }}</el-descriptions-item>
          </el-descriptions>
          <!-- 截图 -->
          <template v-if="selectedCase.screenshot_path">
            <h4>执行截图</h4>
            <div style="text-align: center; margin-bottom: 16px;">
              <img
                :src="selectedCase.screenshot_path"
                style="max-width: 100%; border: 1px solid #eee; border-radius: 4px;"
                alt="执行截图"
              />
            </div>
          </template>
          <!-- 步骤结果 -->
          <template v-if="selectedCase.steps_results && selectedCase.steps_results.length">
            <h4>执行步骤</h4>
            <el-timeline style="padding-left: 10px; margin-top: 12px;">
              <el-timeline-item
                v-for="(step, idx) in selectedCase.steps_results"
                :key="idx"
                :type="step.status === 'completed' ? 'primary' : 'danger'"
                :timestamp="'Step ' + step.step"
                placement="top"
              >
                <div>{{ step.action || step.instruction || step.description || '操作步骤' }}</div>
              </el-timeline-item>
            </el-timeline>
          </template>
          <!-- 断言错误 -->
          <template v-if="selectedCase.assertion_errors && selectedCase.assertion_errors.length">
            <h4 style="color: #f56c6c; margin-top: 16px;">断言错误</h4>
            <el-alert type="error" :closable="false" v-for="(err, i) in selectedCase.assertion_errors" :key="i" style="margin-bottom: 8px;">
              {{ err }}
            </el-alert>
          </template>
          <!-- 错误信息 -->
          <template v-if="selectedCase.error">
            <h4 style="color: #f56c6c; margin-top: 16px;">错误信息</h4>
            <el-alert type="error" :closable="false">{{ selectedCase.error }}</el-alert>
          </template>
        </template>
      </el-drawer>

      <!-- Web 用例详情抽屉 -->
      <el-drawer
        v-model="webDetailVisible"
        title="Web 用例详情"
        size="50%"
        destroy-on-close
      >
        <template v-if="selectedWebCase">
          <h4>基本信息</h4>
          <el-descriptions :column="2" border size="small" style="margin-bottom: 16px">
            <el-descriptions-item label="用例名称">{{ selectedWebCase.title }}</el-descriptions-item>
            <el-descriptions-item label="引擎">
              <el-tag :type="selectedWebCase.engine === 'ai' ? 'danger' : 'success'" size="small">
                {{ selectedWebCase.engine === 'ai' ? 'AI(Midscene)' : (selectedWebCase.engine || 'Playwright') }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="目标 URL" :span="2">
              <el-link :href="selectedWebCase.target_url" target="_blank" type="primary">{{ selectedWebCase.target_url }}</el-link>
            </el-descriptions-item>
            <el-descriptions-item label="执行状态">
              <el-tag :type="getCaseStatusType(selectedWebCase.status)" size="small">{{ getCaseStatusText(selectedWebCase.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="耗时">{{ selectedWebCase.duration != null ? selectedWebCase.duration + 's' : '-' }}</el-descriptions-item>
          </el-descriptions>

          <!-- 截图 -->
          <template v-if="selectedWebCase.screenshot_path">
            <h4>执行截图</h4>
            <div style="text-align: center; margin-bottom: 16px;">
              <img
                :src="selectedWebCase.screenshot_path"
                style="max-width: 100%; border: 1px solid #eee; border-radius: 4px;"
                alt="执行截图"
              />
            </div>
          </template>

          <!-- 步骤结果 -->
          <template v-if="selectedWebCase.steps_results && selectedWebCase.steps_results.length">
            <h4>执行步骤</h4>
            <el-table :data="selectedWebCase.steps_results" stripe border size="small" style="margin-top: 8px;">
              <el-table-column prop="step" label="步骤" width="70" />
              <el-table-column prop="action" label="操作" width="120" show-overflow-tooltip />
              <el-table-column prop="status" label="状态" width="90">
                <template #default="{ row }">
                  <el-tag :type="row.status === 'completed' ? 'success' : 'danger'" size="small">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="instruction" label="指令/描述" show-overflow-tooltip>
                <template #default="{ row }">{{ row.instruction || row.description || '-' }}</template>
              </el-table-column>
            </el-table>
          </template>

          <!-- 断言信息 -->
          <template v-if="selectedWebCase.assertion_errors && selectedWebCase.assertion_errors.length">
            <h4 style="color: #f56c6c; margin-top: 16px;">断言错误</h4>
            <div v-for="(err, i) in selectedWebCase.assertion_errors" :key="i" style="margin-bottom: 8px;">
              <el-alert type="error" :closable="false">{{ err }}</el-alert>
            </div>
          </template>

          <!-- 错误信息 -->
          <template v-if="selectedWebCase.error">
            <h4 style="color: #f56c6c; margin-top: 16px;">错误信息</h4>
            <el-alert type="error" :closable="false" style="white-space: pre-wrap;">{{ selectedWebCase.error }}</el-alert>
          </template>
        </template>
      </el-drawer>

      <!-- 执行日志 -->
      <el-card class="log-card" shadow="never" style="margin-top: 16px">
        <template #header>
          <div class="card-header-with-action">
            <span>执行日志</span>
            <el-button size="small" @click="copyLog">
              <el-icon><CopyDocument /></el-icon> 复制日志
            </el-button>
          </div>
        </template>
        <div class="log-timeline">
          <div v-for="(log, idx) in executionLog" :key="idx" class="log-entry" :class="`log-level-${log.level}`">
            <span class="log-time">{{ formatDate(log.time) }}</span>
            <el-tag size="small" :type="log.level === 'error' ? 'danger' : log.level === 'warning' ? 'warning' : log.level === 'success' ? 'success' : 'info'" class="log-level">
              {{ log.level.toUpperCase() }}
            </el-tag>
            <span class="log-message">{{ log.message }}</span>
          </div>
          <el-empty v-if="!executionLog.length" description="暂无日志" />
        </div>
      </el-card>

      <!-- 用例明细（默认折叠） -->
      <el-collapse v-model="activeCollapse" style="margin-top: 16px">
        <el-collapse-item title="查看用例执行明细" name="cases">
          <el-card class="cases-card" shadow="never" v-if="caseResults.length">
            <el-table :data="caseResults" stripe border max-height="500">
              <el-table-column label="用例名称" min-width="180" show-overflow-tooltip>
                <template #default="{ row }">
                  {{ row.title || row.case_title || row.case_id || '-' }}
                </template>
              </el-table-column>
              <el-table-column label="类型" width="70">
                <template #default="{ row }">
                  <el-tag size="small" :type="row.type === 'web' ? 'warning' : ''">
                    {{ row.type === 'web' ? 'Web' : 'API' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column v-if="hasApiCases" label="方法" width="80">
                <template #default="{ row }">
                  <template v-if="row.type !== 'web'">
                    <el-tag size="small" :type="getMethodType(row.method)">{{ row.method || '-' }}</el-tag>
                  </template>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column v-if="hasWebCases" label="目标URL" min-width="160" show-overflow-tooltip>
                <template #default="{ row }">
                  <template v-if="row.type === 'web'">
                    <el-link v-if="row.target_url" :href="row.target_url" target="_blank" type="primary" :underline="false">
                      {{ row.target_url.length > 40 ? row.target_url.substring(0, 40) + '...' : row.target_url }}
                    </el-link>
                    <span v-else>-</span>
                  </template>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column v-if="hasWebCases" label="引擎" width="90">
                <template #default="{ row }">
                  <template v-if="row.type === 'web'">
                    <el-tag size="small" :type="row.engine === 'ai' ? 'danger' : 'success'">
                      {{ row.engine === 'ai' ? 'AI(Midscene)' : (row.engine || 'Playwright') }}
                    </el-tag>
                  </template>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column v-if="hasApiCases" label="状态码" width="100">
                <template #default="{ row }">
                  <template v-if="row.type !== 'web'">
                    <span :style="{ color: row.response_status_code === row.expected_status ? '#67c23a' : '#f56c6c' }">
                      {{ row.response_status_code || '-' }}
                    </span>
                  </template>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="85">
                <template #default="{ row }">
                  <el-tag :type="getCaseStatusType(row.status)" size="small">
                    {{ getCaseStatusText(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="耗时" width="75">
                <template #default="{ row }">{{ row.duration != null ? row.duration + 's' : '-' }}</template>
              </el-table-column>
              <el-table-column label="操作" width="100" fixed="right">
                <template #default="{ row }">
                  <el-button
                    v-if="row.type !== 'web' && row.status === 'failed'"
                    size="small"
                    link
                    type="danger"
                    @click="expandFailure(row)"
                  >
                    失败详情
                  </el-button>
                  <el-button
                    v-if="row.type === 'web'"
                    size="small"
                    link
                    @click="showWebDetail(row)"
                  >
                    详情
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
          <el-empty v-else description="暂无用例执行结果" />
        </el-collapse-item>
      </el-collapse>
    </template>

    <el-empty v-else-if="!loading" description="未找到执行记录" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { executionAPI } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Download, CopyDocument, ArrowDown, Document, Notebook } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const execution = ref(null)
const exporting = ref(false)
const failureDrawerVisible = ref(false)
const selectedCase = ref(null)

// Web 详情相关
const webDetailVisible = ref(false)
const selectedWebCase = ref(null)

// 折叠面板：用例明细默认收起
const activeCollapse = ref([])

// 用例执行结果
const caseResults = computed(() => {
  if (!execution.value || !execution.value.execution_results) return []
  return execution.value.execution_results
})

// 根据执行结果生成执行日志
const executionLog = computed(() => {
  if (!execution.value) return []
  const logs = []
  const started = execution.value.started_at || execution.value.created_at
  logs.push({ time: started, level: 'info', message: `开始执行：${execution.value.name || execution.value.id}` })
  if (execution.value.summary) {
    logs.push({ time: started, level: 'info', message: `执行摘要：${execution.value.summary}` })
  }
  caseResults.value.forEach((r, idx) => {
    const name = r.title || r.case_title || r.case_id || `用例 #${idx + 1}`
    const statusText = getCaseStatusText(r.status)
    const duration = r.duration != null ? `${r.duration}s` : (r.duration_ms != null ? `${(r.duration_ms / 1000).toFixed(1)}s` : '-')
    const level = r.status === 'failed' ? 'error' : r.status === 'skipped' ? 'warning' : 'success'
    logs.push({ time: r.created_at || started, level, message: `[${statusText}] ${name}（耗时 ${duration}）` })
    if (r.error_message) {
      logs.push({ time: r.created_at || started, level: 'error', message: `失败原因：${r.error_message}` })
    }
  })
  const ended = execution.value.ended_at || execution.value.created_at
  logs.push({ time: ended, level: 'info', message: `执行结束：共 ${execution.value.total_cases || caseResults.value.length} 条，通过 ${execution.value.passed_cases || 0}，失败 ${execution.value.failed_cases || 0}，跳过 ${execution.value.skipped_cases || 0}` })
  return logs
})

// 加载执行详情
const loadDetail = async () => {
  loading.value = true
  try {
    const response = await executionAPI.get(route.params.id)
    execution.value = response
  } catch (error) {
    console.error('Load detail error:', error)
  } finally {
    loading.value = false
  }
}

// 展开失败详情
const expandFailure = (caseResult) => {
  selectedCase.value = caseResult
  failureDrawerVisible.value = true
}

// 预览 Web 截图（截图路径已转为 /media/ 开头的可访问 URL）
const previewScreenshot = (caseResult) => {
  if (!caseResult.screenshot_path) return
  // 直接新窗口打开图片 URL
  window.open(caseResult.screenshot_path, '_blank')
}

// 显示 Web 用例详情
const showWebDetail = (caseResult) => {
  selectedWebCase.value = caseResult
  webDetailVisible.value = true
}

// 返回
const goBack = () => {
  router.back()
}

// 跳转到套件
const goToSuite = () => {
  if (execution.value?.suite_id) {
    router.push({ name: 'TestSuiteList' })
  }
}

// 重新执行
const rerunExecution = async () => {
  try {
    await ElMessageBox.confirm('确认重新执行此测试？', '重跑确认', { type: 'warning' })
    ElMessage.info('正在重新执行...')
    const response = await executionAPI.rerun(execution.value.id)
    const exec = response.execution || response || {}
    ElMessage.success(`重新执行完成: ${exec.passed_cases || 0} 通过, ${exec.failed_cases || 0} 失败`)
    loadDetail()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Rerun error:', error)
    }
  }
}

// 导出报告：支持 PDF 和 HTML 格式下载
const handleExport = async (format) => {
  try {
    exporting.value = true
    const reportName = format === 'pdf' ? 'PDF' : 'Allure'
    ElMessage.info(`正在生成 ${reportName} 报告，请稍候...`)

    const blob = await executionAPI.exportReport(execution.value.id, format)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const extension = format === 'pdf' ? 'pdf' : 'zip'
    link.download = `report_exec_${execution.value.id}.${extension}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success(`${reportName} 报告已下载`)
  } catch (error) {
    if (error.response) {
      try {
        const text = await error.response.data.text()
        const data = JSON.parse(text)
        ElMessage.error(data.error || '导出失败')
      } catch {
        ElMessage.error('导出失败')
      }
    } else if (error !== 'cancel') {
      console.error('Export error:', error)
      ElMessage.error('导出失败，请检查网络连接')
    }
  } finally {
    exporting.value = false
  }
}

// 复制日志
const copyLog = () => {
  const text = executionLog.value.map(l => `${formatDate(l.time)} [${l.level.toUpperCase()}] ${l.message}`).join('\n')
  navigator.clipboard.writeText(text || '暂无日志').then(() => {
    ElMessage.success('日志已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

// 辅助函数
const getStatusType = (status) => {
  const types = {
    pending: 'info',
    running: '',
    completed: 'success',
    partial: 'warning',
    failed: 'danger',
  }
  return types[status] || ''
}

const getStatusText = (status) => {
  const texts = {
    pending: '等待中',
    running: '执行中',
    completed: '已完成',
    partial: '部分通过',
    failed: '失败',
  }
  return texts[status] || status
}

const getCaseStatusType = (status) => {
  const types = { passed: 'success', failed: 'danger', skipped: 'info' }
  return types[status] || ''
}

const getCaseStatusText = (status) => {
  const texts = { passed: '通过', failed: '失败', skipped: '跳过' }
  return texts[status] || status
}

const getMethodType = (method) => {
  const types = { GET: '', POST: 'success', PUT: 'warning', DELETE: 'danger', PATCH: 'info' }
  return types[method] || ''
}

const getEnvType = (env) => {
  const types = { dev: 'info', test: '', prod: 'danger' }
  return types[env] || ''
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const formatJSON = (data) => {
  if (!data) return '无'
  if (typeof data === 'string') {
    try {
      return JSON.stringify(JSON.parse(data), null, 2)
    } catch {
      return data
    }
  }
  return JSON.stringify(data, null, 2)
}

onMounted(() => {
  loadDetail()
})
</script>

<style scoped>
.execution-detail-container {
  padding: 0;
}

.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.overview-card :deep(.el-card__body) {
  padding: 20px;
}

.exec-title {
  margin: 0 0 16px 0;
  font-size: 18px;
}

.stats-overview {
  display: flex;
  gap: 12px;
  height: 100%;
  align-items: center;
  justify-content: center;
}

.stat-box {
  text-align: center;
  padding: 16px 20px;
  border-radius: 8px;
  min-width: 80px;
}

.stat-box.total {
  background: #f5f7fa;
}

.stat-box.passed {
  background: #f0f9eb;
  color: #67c23a;
}

.stat-box.failed {
  background: #fef0f0;
  color: #f56c6c;
}

.stat-box.skipped {
  background: #fdf6ec;
  color: #e6a23c;
}

.stat-number {
  font-size: 28px;
  font-weight: bold;
}

.stat-label {
  font-size: 12px;
  margin-top: 4px;
  color: #999;
}

.card-header-with-action {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.json-block {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
  max-height: 300px;
  overflow-y: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

.summary-body {
  font-size: 14px;
  line-height: 1.8;
  color: #475569;
  white-space: pre-wrap;
  word-break: break-all;
}

.log-timeline {
  max-height: 520px;
  overflow-y: auto;
  padding: 8px 0;
}

.log-entry {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 6px;
  font-size: 13px;
  line-height: 1.6;
}

.log-entry:nth-child(odd) {
  background: #f8fafc;
}

.log-time {
  color: #64748b;
  font-family: monospace;
  font-size: 12px;
  min-width: 140px;
  flex-shrink: 0;
}

.log-level {
  flex-shrink: 0;
  min-width: 50px;
  text-align: center;
}

.log-message {
  color: #334155;
  word-break: break-all;
}

.log-level-error .log-message {
  color: #dc2626;
}
</style>
