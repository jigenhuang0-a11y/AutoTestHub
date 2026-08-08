<template>
  <div
    class="workflow-progress-panel"
    role="status"
    aria-live="polite"
    :aria-label="statusLabel"
  >
    <!-- 面板头部 -->
    <div class="workflow-panel-header">
      <div class="workflow-panel-title">
        <el-icon v-if="running" class="is-loading" aria-hidden="true">
          <Loading />
        </el-icon>
        <el-icon v-else-if="done" style="color: var(--el-color-success)" aria-hidden="true">
          <CircleCheckFilled />
        </el-icon>
        <el-icon v-else-if="hasError" style="color: var(--el-color-danger)" aria-hidden="true">
          <CircleCloseFilled />
        </el-icon>
        <span>多Agent协作工作流</span>
      </div>
      <div class="workflow-panel-meta">
        <el-tag v-if="running" type="warning" size="small" effect="dark">执行中</el-tag>
        <el-tag v-else-if="done" type="success" size="small" effect="dark">完成</el-tag>
        <el-tag v-else-if="hasError" type="danger" size="small" effect="dark">出错</el-tag>
        <span class="workflow-timer" v-if="running" aria-live="off">{{ formattedTime }}</span>
        <el-button
          v-if="running"
          size="small"
          type="danger"
          plain
          @click="$emit('stop')"
          aria-label="停止工作流执行"
        >
          <el-icon><Close /></el-icon> 停止
        </el-button>
      </div>
    </div>

    <!-- 总进度条 -->
    <div class="workflow-overall-progress" v-if="steps.length > 0">
      <el-progress
        :percentage="progressPercent"
        :status="done ? 'success' : hasError ? 'exception' : ''"
        :stroke-width="8"
      />
    </div>

    <!-- 步骤时间线 -->
    <div class="workflow-timeline" v-if="steps.length > 0">
      <div
        v-for="(step, idx) in steps"
        :key="idx"
        class="wf-step"
        :class="{
          'wf-step-running': step.status === 'running',
          'wf-step-done': step.status === 'done',
          'wf-step-fail': step.status === 'failed',
        }"
      >
        <div class="wf-step-dot">
          <el-icon v-if="step.status === 'done'"><CircleCheckFilled /></el-icon>
          <el-icon v-else-if="step.status === 'failed'"><CircleCloseFilled /></el-icon>
          <el-icon v-else-if="step.status === 'running'" class="is-loading"><Loading /></el-icon>
          <span v-else class="wf-dot-pending"></span>
        </div>
        <div class="wf-step-line" v-if="idx < steps.length - 1"></div>
        <div class="wf-step-content">
          <div class="wf-step-header">
            <span class="wf-step-agent">{{ step.agent || step.label }}</span>
            <span class="wf-step-duration" v-if="step.duration">{{ step.duration }}</span>
          </div>
          <div class="wf-step-desc">{{ step.description }}</div>
          <div class="wf-step-detail" v-if="step.detail" v-html="step.detail"></div>
          <div class="wf-step-error" v-if="step.error">
            <el-alert :title="step.error" type="error" :closable="false" show-icon />
          </div>
        </div>
      </div>
    </div>

    <!-- 空步骤状态 -->
    <div v-else-if="running" class="workflow-empty-step">
      <div class="thinking-dots">
        <span></span><span></span><span></span>
      </div>
      <p class="thinking-text">正在初始化工作流...</p>
    </div>

    <!-- 最终结果 -->
    <div v-if="done && result" class="workflow-result">
      <div class="workflow-result-label">执行结果</div>
      <div class="wf-result-text" v-html="result"></div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  Loading,
  CircleCheckFilled,
  CircleCloseFilled,
  Close,
} from '@element-plus/icons-vue'

const props = defineProps({
  steps: { type: Array, default: () => [] },
  running: { type: Boolean, default: false },
  done: { type: Boolean, default: false },
  hasError: { type: Boolean, default: false },
  result: { type: String, default: '' },
  elapsedSeconds: { type: Number, default: 0 },
  completedCount: { type: Number, default: 0 },
})

defineEmits(['stop'])

const progressPercent = computed(() => {
  const total = Math.max(props.steps.length, 1)
  return Math.round((props.completedCount / total) * 100)
})

const formattedTime = computed(() => {
  const s = props.elapsedSeconds
  const mins = Math.floor(s / 60)
  const secs = s % 60
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
})

const statusLabel = computed(() => {
  if (props.running) return '多Agent工作流执行中'
  if (props.done) return '多Agent工作流已完成'
  if (props.hasError) return '多Agent工作流出错'
  return '多Agent工作流进度'
})
</script>

<style scoped>
.workflow-progress-panel {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.workflow-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.workflow-panel-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.workflow-panel-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.workflow-timer {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
}

.workflow-overall-progress {
  margin-bottom: 16px;
}

/* 步骤时间线 */
.workflow-timeline {
  position: relative;
  padding-left: 20px;
}

.wf-step {
  position: relative;
  padding-bottom: 16px;
}

.wf-step:last-child {
  padding-bottom: 0;
}

.wf-step-dot {
  position: absolute;
  left: -20px;
  top: 2px;
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}

.wf-step-done .wf-step-dot {
  color: var(--el-color-success);
}

.wf-step-fail .wf-step-dot {
  color: var(--el-color-danger);
}

.wf-step-running .wf-step-dot {
  color: var(--el-color-primary);
}

.wf-dot-pending {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--el-border-color);
}

.wf-step-line {
  position: absolute;
  left: -13px;
  top: 18px;
  bottom: 0;
  width: 2px;
  background: var(--el-border-color-light);
}

.wf-step-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}

.wf-step-agent {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.wf-step-duration {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}

.wf-step-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}

.wf-step-detail {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
  padding: 6px 8px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
}

.wf-step-error {
  margin-top: 6px;
}

/* 空步骤 */
.workflow-empty-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 0;
}

.thinking-dots {
  display: flex;
  gap: 4px;
}

.thinking-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--el-color-primary);
  animation: dot-bounce 1.2s ease-in-out infinite;
}

.thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.thinking-text {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin: 0;
}

/* 结果区域 */
.workflow-result {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.workflow-result-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}

.wf-result-text {
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.6;
}

.wf-result-text :deep(code) {
  background: var(--el-fill-color-light);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 12px;
}

.wf-result-text :deep(pre) {
  background: var(--el-fill-color-light);
  padding: 8px 12px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
}
</style>
