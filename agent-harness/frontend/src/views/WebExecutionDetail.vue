<template>
  <div class="web-exec-detail-container" v-loading="loading">
    <template v-if="execution">
      <!-- 顶部操作栏 -->
      <div class="action-bar">
        <el-page-header class="detail-page-header" @back="goBack" :title="'返回'" />
        <div class="action-buttons">
          <el-button type="danger" @click="handleDelete">
            <el-icon><Delete /></el-icon> 删除记录
          </el-button>
        </div>
      </div>

      <!-- 概览卡片 -->
      <el-card class="overview-card" shadow="never">
        <el-row :gutter="24" align="middle">
          <el-col :span="16">
            <h3 class="exec-title">
              <el-tag type="success" size="small" style="margin-right:8px"><el-icon style="vertical-align:-2px;margin-right:2px"><Monitor /></el-icon>Web</el-tag>
              {{ execution.test_case_title || `用例 #${execution.id}` }}
            </h3>
            <el-descriptions :column="3" border size="default">
              <el-descriptions-item label="关联用例">
                <el-link v-if="execution.test_case_title" type="primary" @click="goToTestCase">
                  {{ execution.test_case_title }}
                </el-link>
                <span v-else>-</span>
              </el-descriptions-item>
              <el-descriptions-item label="触发方式">
                <el-tag size="small" type="success">手动执行</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="执行人">{{ execution.executed_by_username || '-' }}</el-descriptions-item>
              <el-descriptions-item label="环境">
                <el-tag size="small" type="info">浏览器</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="执行时间">{{ formatDate(execution.executed_at) }}</el-descriptions-item>
              <el-descriptions-item label="耗时">{{ execution.duration ? Number(execution.duration).toFixed(2) + ' 秒' : '-' }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="statusType" size="small">
                  <el-icon v-if="execution.status === 'passed'"><CircleCheck /></el-icon>
                  <el-icon v-else-if="execution.status === 'failed'"><CircleClose /></el-icon>
                  <el-icon v-else><Warning /></el-icon>
                  {{ statusText }}
                </el-tag>
              </el-descriptions-item>
            </el-descriptions>
          </el-col>
          <el-col :span="8">
            <div class="stats-overview">
              <div class="stat-box" :class="execution.status">
                <div class="stat-number">
                  <el-icon v-if="execution.status === 'passed'" color="#67c23a" :size="32"><CircleCheckFilled /></el-icon>
                  <el-icon v-else-if="execution.status === 'failed'" color="#f56c6c" :size="32"><CircleCloseFilled /></el-icon>
                  <el-icon v-else color="#e6a23c" :size="32"><WarningFilled /></el-icon>
                </div>
                <div class="stat-label">{{ statusText }}</div>
              </div>
              <div class="stat-box duration-box">
                <div class="stat-number">{{ execution.duration ? Number(execution.duration).toFixed(1) + 's' : '-' }}</div>
                <div class="stat-label">执行耗时</div>
              </div>
              <div class="stat-box steps-box" v-if="totalSteps > 0">
                <div class="stat-number">{{ totalSteps }}</div>
                <div class="stat-label">执行步骤</div>
              </div>
            </div>
          </el-col>
        </el-row>
      </el-card>

      <!-- 步骤执行详情（平铺卡片列表 + 可折叠） -->
      <el-card shadow="never" class="steps-card">
        <el-collapse v-model="stepsExpanded">
          <el-collapse-item name="steps">
            <template #title>
              <div class="card-header">
                <span><el-icon><List /></el-icon> 执行步骤 ({{ displaySteps.length }})</span>
                <span class="collapse-hint">{{ stepsExpanded.length ? '点击收起' : '点击展开' }}</span>
              </div>
            </template>

            <div v-if="displaySteps.length === 0" class="empty-hint">暂无步骤记录</div>

        <!-- 平铺步骤卡片列表（固定高度 + 内部滚动） -->
        <div v-else class="step-scroll-container">
        <div class="step-list">
          <div
            v-for="(step, idx) in displaySteps"
            :key="idx"
            class="step-card"
            :class="{ 'step-failed': step.status === 'failed' || step.status === 'error' }"
          >
            <!-- 卡片头部 -->
            <div class="step-card-header">
              <el-tag :type="stepTagType(step)" size="small" effect="dark">
                {{ idx + 1 }}
              </el-tag>
              <span class="step-card-title">{{ getStepTitle(step) }}</span>
              <el-tag :type="step.status === 'completed' ? 'success' : step.status === 'failed' ? 'danger' : 'info'" size="small" style="margin-left:auto">
                {{ stepStatusLabel(step) }}
              </el-tag>
            </div>

            <!-- 卡片内容 -->
            <div class="step-card-body">
              <!-- AI 模式：显示原始指令 -->
              <div v-if="step.instruction" class="step-instruction-line">
                <span class="step-label-tag">指令</span>
                <code>{{ step.instruction }}</code>
              </div>

              <!-- 操作类型 -->
              <div v-if="step.action" class="step-meta-line">
                <span class="step-label-tag">类型</span>
                <code>{{ step.action }}</code>
              </div>

              <!-- 操作参数 -->
              <div v-if="step.params && Object.keys(step.params).length" class="step-params-wrap">
                <div class="step-params-header">操作参数</div>
                <pre class="step-params">{{ formatJson(step.params) }}</pre>
              </div>

              <!-- 错误信息 -->
              <div v-if="step.error" class="step-error-wrap">
                <span class="step-label-tag error-tag">错误</span>
                <span class="step-error-text">{{ step.error }}</span>
              </div>

              <!-- 步骤截图 -->
              <div v-if="getStepScreenshot(step, idx)" class="step-screenshot-inline">
                <img
                  :src="getStepScreenshot(step, idx)"
                  alt="步骤截图"
                  class="step-screenshot-img"
                  @click="previewScreenshot(getStepScreenshot(step, idx))"
                />
              </div>
            </div>
          </div>
        </div>
        </div>
          </el-collapse-item>
        </el-collapse>
      </el-card>

      <!-- 最终截图（无步骤或步骤中无截图时，单独以折叠卡片展示） -->
      <el-card shadow="never" class="final-screenshot-card" v-if="execution.screenshot_url && !anyStepHasScreenshot">
        <el-collapse v-model="expandedFinalScreenshot">
          <el-collapse-item name="final-shot">
            <template #title>
              <div class="step-title">
                <el-icon style="margin-right:6px;color:#409eff"><Picture /></el-icon>
                <span class="step-action-name">执行结果截图</span>
                <span class="step-desc-final" v-if="finalScreenshotDesc"> — {{ finalScreenshotDesc }}</span>
              </div>
            </template>
            <div class="step-detail-content">
              <!-- 步骤说明 -->
              <div class="step-header-bar" v-if="finalScreenshotStepDesc">
                <div class="step-header-left">
                  <span class="step-num-badge">{{ finalScreenshotStepDesc }}</span>
                </div>
              </div>
              <div class="step-screenshot-wrapper" @click="previewScreenshot(execution.screenshot_url)">
                <img :src="execution.screenshot_url" alt="执行截图" class="step-screenshot-img" />
              </div>
              <p class="img-hint">点击放大查看</p>
            </div>
          </el-collapse-item>
        </el-collapse>
      </el-card>

      <!-- 结果数据（result_data JSON） -->
      <el-card shadow="never" class="result-card" v-if="rawResultData && Object.keys(rawResultData).length > 0">
        <template #header>
          <div class="card-header">
            <span><el-icon><DataAnalysis /></el-icon> 执行结果数据</span>
            <el-switch v-model="showRawJson" active-text="展开" inactive-text="收起" size="small" />
          </div>
        </template>
        <pre v-show="showRawJson" class="json-block"><code>{{ formatJson(rawResultData) }}</code></pre>
      </el-card>

      <!-- 错误信息 -->
      <el-card shadow="never" class="error-card" v-if="errorInfo">
        <template #header>
          <span style="color:#f56c6c"><el-icon><WarningFilled /></el-icon> 错误信息</span>
        </template>
        <pre class="error-block">{{ errorInfo }}</pre>
      </el-card>

    </template>

    <!-- 图片预览 Dialog -->
    <el-dialog v-model="showPreview" title="截图预览" width="85%" destroy-on-close>
      <div style="text-align:center">
        <img :src="previewSrc" alt="截图大图" style="max-width:100%;max-height:80vh;object-fit:contain;border-radius:6px" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Delete, Monitor, CircleCheck, CircleClose, Warning,
  Picture, DataAnalysis, WarningFilled,
  CircleCheckFilled, CircleCloseFilled,
  List,
} from '@element-plus/icons-vue'
import { webTestcaseAPI } from '@/api/index'

const route = useRoute()
const router = useRouter()

// 状态
const loading = ref(true)
const execution = ref(null)
const showPreview = ref(false)
const previewSrc = ref('')
const expandedFinalScreenshot = ref([])
const showRawJson = ref(false)
const stepsExpanded = ref(['steps'])  // 默认展开

// 计算属性
const statusType = computed(() => {
  const map = { passed: 'success', failed: 'danger', error: 'warning' }
  return map[execution.value?.status] || ''
})

const statusText = computed(() => {
  const map = { passed: '通过', failed: '失败', error: '异常' }
  return map[execution.value?.status] || execution.value?.status || '-'
})

const rawResultData = computed(() => execution.value?.result_data || null)

const stepsResults = computed(() => (rawResultData.value?.steps_results) || [])
const testCaseSteps = computed(() => execution.value?.test_case_steps || [])

/** 合并用例步骤定义 + 执行结果，用于展示 */
const displaySteps = computed(() => {
  if (!stepsResults.value.length && !testCaseSteps.value.length) return []

  // 以执行结果为主，补充用例步骤的 description/params 等信息
  const results = stepsResults.value
  const caseSteps = testCaseSteps.value

  // 如果有执行结果，以执行结果的条数为准
  if (results.length > 0) {
    return results.map((r, idx) => ({
      ...r,
      description: caseSteps[idx]?.description || '',
      params: r.params || caseSteps[idx]?.params || {},
    }))
  }

  // 没有执行结果时，仅展示用例步骤定义（标记为 pending）
  return caseSteps.map(s => ({ ...s, status: 'pending' }))
})

const totalSteps = computed(() => displaySteps.value.length)

const anyStepHasScreenshot = computed(() => displaySteps.value.length > 0)

/** 最终截图的简短描述 */
const finalScreenshotDesc = computed(() => {
  if (displaySteps.value.length > 0) {
    const lastStep = displaySteps.value[displaySteps.value.length - 1]
    return getStepDescription(lastStep)
  }
  return execution.value?.test_case_title || ''
})

/** 最终截图的步骤标题 */
const finalScreenshotStepDesc = computed(() => {
  if (displaySteps.value.length > 0) {
    return `步骤 ${displaySteps.value.length}：${stepActionLabel(displaySteps.value[displaySteps.value.length - 1])}`
  }
  return ''
})

const errorInfo = computed(() => {
  const rd = rawResultData.value
  if (!rd) return null
  if (typeof rd === 'string') return rd.includes('error') ? rd : null
  if (typeof rd === 'object') {
    return rd.error || rd.error_message || rd.message || rd.traceback ||
      (rd.assertion_errors?.length ? JSON.stringify(rd.assertion_errors, null, 2) : null) || null
  }
  return null
})

// 加载数据：直接调详情接口，避免列表接口缓存/旧数据导致状态不一致
onMounted(async () => {
  const id = route.params.id
  try {
    execution.value = await webTestcaseAPI.getExecution(id)
    if (!execution.value) {
      ElMessage.error('未找到该执行记录')
    }
  } catch (e) {
    console.error('Load web execution error:', e)
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
})

// 操作方法
const goBack = () => router.push({ name: 'ExecutionHistory' })

const goToTestCase = () => {
  if (execution.value?.test_case) {
    router.push({ name: 'WebTestCaseList', query: { highlight: execution.value.test_case } })
  }
}

const handleDelete = async () => {
  try {
    await ElMessageBox.confirm(`确认删除此执行记录？`, '删除确认', { type: 'warning' })
    await webTestcaseAPI.deleteExecution(execution.value.id)
    ElMessage.success('删除成功')
    router.push({ name: 'ExecutionHistory' })
  } catch (e) {
    if (e !== 'cancel') console.error('Delete error:', e)
  }
}

const previewScreenshot = (src) => {
  previewSrc.value = src
  showPreview.value = true
}

/** 获取步骤标题：ai_action 用 instruction 文本，否则用映射名 */
const getStepTitle = (step) => {
  // AI 模式：直接用自然语言指令作为标题
  if (step.action === 'ai_action' && step.instruction) {
    // 截断过长文本
    const text = String(step.instruction)
    return text.length > 50 ? text.slice(0, 50) + '...' : text
  }
  return stepActionLabel(step)
}

/** 获取步骤对应的截图：优先用步骤自身截图，最后一步使用最终截图 */
const getStepScreenshot = (step, idx) => {
  if (step.screenshot) return step.screenshot
  // 最后一个步骤展示最终截图（这样截图就收纳在折叠面板内）
  const isLastStep = idx === displaySteps.value.length - 1
  if (isLastStep && execution.value?.screenshot_url) {
    return execution.value.screenshot_url
  }
  return null
}

// 步骤辅助函数
const stepActionLabel = (step) => {
  const actionMap = {
    navigate: '打开页面',
    click: '点击',
    fill: '填写',
    select: '选择',
    hover: '悬停',
    wait_for: '等待',
    screenshot: '截图',
    scroll: '滚动',
    assert_text: '文本断言',
    assert_visible: '可见断言',
    assert_url: 'URL 断言',
    assert_value: '值断言',
    press_key: '按键',
    upload_file: '上传文件',
    execute_js: '执行 JS',
    ai_action: 'AI 操作',
  }
  return actionMap[step.action] || step.action || '未知操作'
}

const stepTagType = (step) => {
  switch (step.status) {
    case 'completed': return 'success'
    case 'failed': return 'danger'
    case 'error': return 'warning'
    default: return 'info'
  }
}

const stepStatusLabel = (step) => {
  const map = { completed: '已完成', failed: '失败', error: '异常', pending: '待执行' }
  return map[step.status] || step.status || '-'
}

const getStepDescription = (step) => step.description || step.params?.selector || step.params?.url || ''

// 辅助函数
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const formatJson = (data) => JSON.stringify(data, null, 2)
</script>

<style scoped>
.web-exec-detail-container {
  padding: 16px 24px;
}

.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.action-bar .action-buttons { display: flex; gap: 10px; }

.detail-page-header {
  color: #ffffff;
}
.detail-page-header :deep(.el-page-header__left),
.detail-page-header :deep(.el-page-header__title),
.detail-page-header :deep(.el-page-header__icon) {
  color: #ffffff;
}
.detail-page-header :deep(.el-page-header__left:hover) {
  color: #e2e8f0;
}

.exec-title {
  margin: 0 0 14px 0;
  font-size: 18px;
  color: #303133;
  display: flex;
  align-items: center;
}

/* 状态概览 */
.stats-overview {
  display: flex;
  gap: 16px;
  justify-content: flex-end;
  padding: 8px 0;
}
.stat-box {
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 14px 20px;
  text-align: center;
  min-width: 80px;
}
.stat-box.passed { border-color: #e1f3d8; background: #f0f9eb; }
.stat-box.failed { border-color: #fde2e2; background: #fef0f0; }
.stat-box.error { border-color: #faecd8; background: #fdf6ec; }
.stat-box .stat-number { font-size: 26px; font-weight: 700; line-height: 1.4; }
.stat-box .stat-label { font-size: 12px; color: #909399; margin-top: 4px; }
.stat-box.steps-box .stat-number { color: #409eff; }

/* 卡片通用间距 */
.overview-card,
.steps-card,
.final-screenshot-card,
.result-card,
.error-card { margin-top: 16px; }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.collapse-hint {
  font-size: 12px;
  color: #909399;
}

.empty-hint {
  text-align: center;
  color: #909399;
  padding: 20px 0;
  font-size: 13px;
}

/* ===== 平铺步骤卡片列表（固定高度 + 内部滚动） ===== */
.step-scroll-container {
  height: 55vh;
  overflow-y: auto;
  padding-right: 6px;
}
.step-scroll-container::-webkit-scrollbar {
  width: 8px;
}
.step-scroll-container::-webkit-scrollbar-thumb {
  background-color: #c0c4cc;
  border-radius: 4px;
}

.step-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.step-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
  transition: box-shadow 0.2s;
}
.step-card:hover {
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}
.step-card.step-failed {
  border-color: #fde2e2;
}

.step-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: #fafbfc;
  border-bottom: 1px solid #ebeef5;
}
.step-failed .step-card-header {
  background: #fef0f0;
  border-bottom-color: #fde2e2;
}

.step-card-title {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}

.step-card-body {
  padding: 16px;
}

/* 指令行 */
.step-instruction-line {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 10px;
}
.step-instruction-line code {
  background: #f0f9eb;
  color: #67c23a;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.6;
  flex: 1;
}

/* 元数据行 */
.step-meta-line {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.step-meta-line code {
  background: #ecf5ff;
  color: #409eff;
  padding: 1px 8px;
  border-radius: 3px;
  font-size: 12px;
}

.step-label-tag {
  display: inline-block;
  min-width: 40px;
  font-size: 11px;
  font-weight: 600;
  color: #909399;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
  line-height: 1.8;
}
.step-label-tag.error-tag {
  color: #f56c6c;
}

/* 参数块 */
.step-params-wrap {
  margin: 10px 0;
}
.step-params-header {
  font-size: 11px;
  font-weight: 600;
  color: #909399;
  margin-bottom: 6px;
  letter-spacing: 0.5px;
}
.step-params {
  margin: 0;
  padding: 8px 10px;
  background: #f5f7fa;
  border-radius: 4px;
  font-family: 'Consolas', Monaco, monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.55;
  max-height: 180px;
  overflow-y: auto;
}

/* 错误提示 */
.step-error-wrap {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-top: 8px;
  padding: 10px 12px;
  background: #fef0f0;
  border-radius: 6px;
  border-left: 3px solid #f56c6c;
}
.step-error-text {
  color: #f56c6c;
  word-break: break-all;
  line-height: 1.6;
  font-size: 13px;
  flex: 1;
}

/* 步骤内嵌截图 */
.step-screenshot-inline {
  margin-top: 14px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  overflow: hidden;
  cursor: zoom-in;
  transition: box-shadow 0.25s;
}
.step-screenshot-inline:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
}
.step-screenshot-img {
  display: block;
  width: 100%;
  max-height: 480px;
  object-fit: contain;
  background: #fff;
}

/* 最终截图折叠卡片（保留兼容） */
.step-action-name {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}
.step-desc-final {
  font-size: 13px;
  color: #909399;
  margin-left: 4px;
}
.step-detail-content { padding: 4px 0 8px; }
.step-header-bar {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px;
  background: linear-gradient(135deg, #ecf5ff 0%, #f0f9eb 100%);
  border-left: 4px solid #409eff;
  border-radius: 6px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.step-header-left { display: flex; align-items: center; gap: 8px; }
.step-num-badge {
  background: #409eff; color: #fff;
  font-size: 12px; font-weight: 700;
  padding: 3px 10px; border-radius: 4px;
  white-space: nowrap;
}
.step-header-action { font-size: 14px; font-weight: 600; color: #303133; }
.step-header-desc { font-size: 13px; color: #606266; }
.step-screenshot-wrapper {
  cursor: zoom-in; display: block;
  border-radius: 8px; overflow: hidden;
  border: 1px solid #e4e7ed;
  transition: box-shadow 0.25s;
}
.step-screenshot-wrapper:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
}

/* JSON / 错误信息块 */
.json-block, .error-block {
  margin: 0; padding: 14px; border-radius: 6px;
  font-family: 'Consolas', Monaco, monospace; font-size: 13px;
  white-space: pre-wrap; word-break: break-all; line-height: 1.5;
  background: #f5f7fa; overflow-x: auto;
  max-height: 400px; overflow-y: auto;
}
.error-block { background: #fef0f0; color: #f56c6c; border: 1px solid #fde2e2; }

/* 折叠面板微调 */
:deep(.el-collapse-item__header) {
  height: auto !important;
  min-height: 46px;
  padding: 8px 0;
  line-height: 30px;
}
:deep(.el-collapse-item__content) { padding-bottom: 8px; }
</style>
