<template>
  <div class="workflow-monitor">
    <!-- 顶部标题栏 -->
    <div class="header">
      <h2>Agent 工作流监控</h2>
      <div class="header-actions">
        <el-tag v-if="isRunning" type="warning" effect="dark">执行中</el-tag>
        <el-tag v-else-if="isComplete" type="success" effect="dark">完成</el-tag>
        <el-tag v-else-if="hasError" type="danger" effect="dark">错误</el-tag>
        <el-tag v-else type="info">就绪</el-tag>
        <el-button type="primary" size="small" @click="executeWorkflow" :loading="isRunning">
          <el-icon><VideoPlay /></el-icon> 执行工作流
        </el-button>
      </div>
    </div>

    <!-- 总进度条 -->
    <div class="overall-progress" v-if="totalSteps > 0">
      <div class="progress-label">
        <span>总进度</span>
        <span class="progress-text">{{ completedSteps }}/{{ totalSteps }} 步骤</span>
      </div>
      <el-progress
        :percentage="Math.round((completedSteps / totalSteps) * 100)"
        :status="isComplete ? 'success' : hasError ? 'exception' : ''"
        :stroke-width="12"
      />
    </div>

    <!-- 当前阶段 + 步骤时间线 -->
    <div class="content-area">
      <el-row :gutter="20">
        <!-- 左侧：步骤流 -->
        <el-col :span="14">
          <el-card class="step-card">
            <template #header>
              <span>执行步骤</span>
            </template>

            <!-- 需求输入 -->
            <div class="input-section">
              <el-input
                v-model="userRequest"
                type="textarea"
                :rows="3"
                placeholder="输入测试需求，例如：帮我生成订单模块的测试用例，并用边界值策略生成测试数据，然后执行并评估结果"
                :disabled="isRunning"
              />
            </div>

            <!-- 步骤列表 -->
            <div class="steps-timeline" v-if="steps.length > 0">
              <div
                v-for="(step, index) in steps"
                :key="index"
                class="step-item"
                :class="{
                  'step-running': step.status === 'running',
                  'step-completed': step.status === 'completed',
                  'step-failed': step.status === 'failed',
                }"
              >
                <div class="step-indicator">
                  <el-icon v-if="step.status === 'completed'" class="step-icon-done"><CircleCheckFilled /></el-icon>
                  <el-icon v-else-if="step.status === 'failed'" class="step-icon-fail"><CircleCloseFilled /></el-icon>
                  <el-icon v-else-if="step.status === 'running'" class="step-icon-running is-loading"><Loading /></el-icon>
                  <span v-else class="step-icon-pending"></span>
                </div>

                <div class="step-body">
                  <div class="step-header">
                    <span class="step-agent">{{ getAgentLabel(step.agent) }}</span>
                    <span class="step-duration" v-if="step.duration_ms">
                      {{ (step.duration_ms / 1000).toFixed(1) }}s
                    </span>
                  </div>
                  <div class="step-desc">{{ step.description }}</div>
                  <div class="step-status" v-if="step.status">
                    <el-tag v-if="step.status === 'running'" type="warning" size="small" effect="plain">执行中</el-tag>
                    <el-tag v-else-if="step.status === 'completed'" type="success" size="small" effect="plain">完成</el-tag>
                    <el-tag v-else-if="step.status === 'failed'" type="danger" size="small" effect="plain">失败</el-tag>
                    <el-tag v-else type="info" size="small">等待</el-tag>
                  </div>
                  <div class="step-error" v-if="step.error">
                    <el-alert :title="step.error" type="error" :closable="false" show-icon />
                  </div>
                </div>
              </div>
            </div>

            <!-- 空状态 -->
            <el-empty v-else description="输入需求后点击「执行工作流」" :image-size="80" />
          </el-card>
        </el-col>

        <!-- 右侧：事件日志 + 结果 -->
        <el-col :span="10">
          <!-- 事件日志 -->
          <el-card class="log-card">
            <template #header>
              <span>实时事件日志</span>
              <el-button size="small" text @click="logs.length = 0">清空</el-button>
            </template>
            <div class="log-container" ref="logContainer">
              <div v-for="(log, idx) in logs" :key="idx" class="log-entry" :class="'log-' + log.type">
                <span class="log-time">{{ log.time }}</span>
                <span class="log-icon">{{ log.icon }}</span>
                <span class="log-msg">{{ log.msg }}</span>
              </div>
              <div v-if="logs.length === 0" class="log-empty">
                日志将在此实时显示...
              </div>
            </div>
          </el-card>

          <!-- 验证结果 -->
          <el-card class="result-card" v-if="verification">
            <template #header>
              <span>验证结果</span>
            </template>
            <div class="verification-summary">
              <el-statistic title="总得分" :value="verification.score * 100" suffix="%">
                <template #prefix>
                  <el-icon :color="verification.passed ? '#67c23a' : '#f56c6c'">
                    <CircleCheckFilled v-if="verification.passed" />
                    <WarningFilled v-else />
                  </el-icon>
                </template>
              </el-statistic>
              <div class="verification-details">
                <div><span>总步骤:</span> {{ verification.total_steps }}</div>
                <div><span>成功:</span> <span style="color:#67c23a">{{ verification.completed_steps }}</span></div>
                <div><span>失败:</span> <span style="color:#f56c6c">{{ verification.failed_steps }}</span></div>
              </div>
            </div>
            <div class="issues-list" v-if="verification.issues && verification.issues.length > 0">
              <el-alert
                v-for="(issue, idx) in verification.issues"
                :key="idx"
                :title="issue"
                type="warning"
                :closable="false"
                show-icon
                style="margin-bottom: 6px"
              />
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, onBeforeUnmount } from 'vue'
import { VideoPlay, Loading, CircleCheckFilled, CircleCloseFilled, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

// ================ 状态 ================
const userRequest = ref('')
const isRunning = ref(false)
const isComplete = ref(false)
const hasError = ref(false)
const totalSteps = ref(0)
const completedSteps = ref(0)
const steps = reactive([])
const logs = reactive([])
const verification = ref(null)
const logContainer = ref(null)

let eventSource = null

// ================ Agent 标签映射 ================
const agentLabels = {
  generator: '用例生成',
  data_factory: '数据工厂',
  execution: '执行引擎',
  evaluator: 'AI 评估',
  knowledge: '知识检索',
  unknown: '未知',
}

function getAgentLabel(name) {
  return agentLabels[name] || name
}

// ================ 日志记录 ================
function addLog(type, msg, icon = '') {
  const icons = {
    info: '🔵',
    success: '✅',
    warning: '⚠️',
    error: '❌',
    plan: '🧠',
    execute: '⚡',
    verify: '🔍',
  }
  const now = new Date()
  logs.push({
    time: `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`,
    type,
    msg,
    icon: icon || icons[type] || '',
  })
  // 自动滚动
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
}

// ================ 核心：SSE 工作流执行 ================
async function executeWorkflow() {
  const request = userRequest.value.trim()
  if (!request) {
    ElMessage.warning('请输入测试需求')
    return
  }

  // 重置状态
  steps.splice(0, steps.length)
  logs.splice(0, logs.length)
  verification.value = null
  isRunning.value = true
  isComplete.value = false
  hasError.value = false
  totalSteps.value = 0
  completedSteps.value = 0

  addLog('info', `开始执行: ${request.slice(0, 60)}...`)

  const token = localStorage.getItem('access_token')

  try {
    // 用 fetch + ReadableStream 消费 SSE
    const response = await fetch('/api/agent/tasks/workflow_stream/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ user_request: request }),
    })

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6))
            handleSSEEvent(event)
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
    }

    // 处理剩余 buffer
    if (buffer.startsWith('data: ')) {
      try {
        const event = JSON.parse(buffer.slice(6))
        handleSSEEvent(event)
      } catch (e) {}
    }
  } catch (error) {
    addLog('error', `连接错误: ${error.message}`)
    hasError.value = true
  } finally {
    isRunning.value = false
    if (verification.value) {
      isComplete.value = true
    }
  }
}

// ================ SSE 事件分发 ================
function handleSSEEvent(event) {
  const { event: eventType, data } = event

  switch (eventType) {
    case 'plan_start':
      addLog('plan', '🧠 开始规划...')
      break

    case 'plan_complete':
      totalSteps.value = data.steps.length
      // 初始化步骤列表
      steps.splice(0, steps.length)
      data.steps.forEach((s, i) => {
        steps.push({
          agent: s.agent,
          description: s.description,
          status: 'pending',
          duration_ms: null,
          error: null,
        })
      })
      addLog('plan', `规划完成: ${data.steps.length} 步 (${data.reasoning || ''})`)
      break

    case 'step_start':
      if (data.step_index !== undefined && steps[data.step_index]) {
        steps[data.step_index].status = 'running'
      }
      addLog('execute', `${getAgentLabel(data.agent)} - ${data.description || '开始执行...'}`)
      break

    case 'step_complete':
      if (data.step_index !== undefined && steps[data.step_index]) {
        steps[data.step_index].status = 'completed'
        steps[data.step_index].duration_ms = data.duration_ms
      }
      completedSteps.value++
      addLog('success', `${getAgentLabel(data.agent)} 完成 (${(data.duration_ms / 1000).toFixed(1)}s)`)
      break

    case 'step_failed':
      if (data.step_index !== undefined && steps[data.step_index]) {
        steps[data.step_index].status = 'failed'
        steps[data.step_index].duration_ms = data.duration_ms
        steps[data.step_index].error = data.error
      }
      completedSteps.value++
      addLog('error', `${getAgentLabel(data.agent)} 失败: ${data.error}`)
      break

    case 'verify_start':
      addLog('verify', '🔍 开始验证...')
      break

    case 'verify_complete':
      verification.value = data
      addLog(data.passed ? 'success' : 'warning',
             data.passed ? '验证通过!' : `验证未通过 (得分: ${data.score})`)
      break

    case 'workflow_complete':
      isComplete.value = true
      addLog('success', `工作流完成 ${data.passed ? '✓' : '✗'}`)
      break

    case 'workflow_error':
      hasError.value = true
      addLog('error', `工作流错误: ${data.error}`)
      break

    case 'final_result':
      // 最终结果已通过 verify_complete 处理
      break

    case 'error':
      hasError.value = true
      addLog('error', `错误: ${data.message}`)
      break
  }
}

// ================ 清理 ================
onBeforeUnmount(() => {
  if (eventSource) {
    eventSource.close()
  }
})
</script>

<style scoped>
.workflow-monitor {
  padding: 0;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* ====== 总进度条 ====== */
.overall-progress {
  margin-bottom: 20px;
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.progress-label {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
  color: #666;
}

.progress-text {
  font-weight: 600;
  color: #409eff;
}

/* ====== 内容区 ====== */
.content-area {
  margin-top: 0;
}

.step-card, .log-card, .result-card {
  height: 100%;
}

.input-section {
  margin-bottom: 20px;
}

/* ====== 步骤时间线 ====== */
.steps-timeline {
  position: relative;
  padding-left: 8px;
}

.step-item {
  display: flex;
  padding: 12px 0;
  border-left: 2px solid #e4e7ed;
  padding-left: 20px;
  position: relative;
  transition: all 0.3s;
}

.step-item.step-running {
  border-left-color: #e6a23c;
  background: linear-gradient(90deg, rgba(230, 162, 60, 0.05), transparent);
}

.step-item.step-completed {
  border-left-color: #67c23a;
}

.step-item.step-failed {
  border-left-color: #f56c6c;
  background: linear-gradient(90deg, rgba(245, 108, 108, 0.05), transparent);
}

.step-indicator {
  position: absolute;
  left: -12px;
  top: 14px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid #e4e7ed;
}

.step-running .step-indicator {
  border-color: #e6a23c;
}

.step-completed .step-indicator {
  border-color: #67c23a;
}

.step-failed .step-indicator {
  border-color: #f56c6c;
}

.step-icon-done {
  color: #67c23a;
  font-size: 14px;
}

.step-icon-fail {
  color: #f56c6c;
  font-size: 14px;
}

.step-icon-running {
  color: #e6a23c;
  font-size: 14px;
}

.step-icon-pending {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #c0c4cc;
}

.step-body {
  flex: 1;
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.step-agent {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}

.step-duration {
  font-size: 12px;
  color: #909399;
}

.step-desc {
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
}

.step-status {
  margin-top: 4px;
}

.step-error {
  margin-top: 8px;
}

/* ====== 日志区 ====== */
.log-container {
  max-height: 350px;
  overflow-y: auto;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
}

.log-entry {
  padding: 4px 0;
  border-bottom: 1px solid #f5f5f5;
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.log-time {
  color: #909399;
  flex-shrink: 0;
  font-size: 12px;
}

.log-icon {
  flex-shrink: 0;
}

.log-msg {
  color: #303133;
  word-break: break-all;
}

.log-error .log-msg {
  color: #f56c6c;
}

.log-success .log-msg {
  color: #67c23a;
}

.log-empty {
  color: #c0c4cc;
  text-align: center;
  padding: 30px 0;
}

/* ====== 结果区 ====== */
.result-card {
  margin-top: 20px;
}

.verification-summary {
  display: flex;
  gap: 30px;
  align-items: center;
  margin-bottom: 12px;
}

.verification-details {
  font-size: 13px;
  color: #606266;
}

.verification-details div {
  margin-bottom: 4px;
}

.verification-details span {
  font-weight: 600;
  color: #303133;
}

/* ====== Element Plus icon spin ====== */
.is-loading {
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
