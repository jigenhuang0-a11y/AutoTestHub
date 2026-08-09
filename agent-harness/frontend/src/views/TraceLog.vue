<template>
  <div class="harness-page trace-log">
    <!-- 顶部搜索 -->
    <div class="search-bar">
      <el-input v-model="searchQuery" placeholder="搜索任务（请求内容 / 任务ID）..." class="search-input" clearable @keyup.enter="searchTasks" />
      <el-select v-model="statusFilter" placeholder="状态筛选" clearable @change="searchTasks" style="width:130px; margin-left: 12px;">
        <el-option label="全部" value="" />
        <el-option label="执行中" value="running" />
        <el-option label="已完成" value="completed" />
        <el-option label="失败" value="failed" />
      </el-select>
      <el-button type="primary" @click="searchTasks" style="margin-left: 12px;">搜索</el-button>
      <span class="task-count">{{ taskList.length }} 条结果</span>
    </div>

    <div class="trace-layout">
      <!-- 左侧任务列表 -->
      <div class="task-list-panel">
        <div class="panel-title">任务链路</div>
        <div
          v-for="task in taskList"
          :key="task.id"
          :class="['task-item', { active: selectedTask?.id === task.id }]"
          @click="selectTask(task)"
        >
          <div class="task-item-header">
            <span :class="'status-dot ' + task.status" />
            <span class="task-type">{{ task.task_type }}</span>
            <span class="task-id">#{{ task.id }}</span>
          </div>
          <div class="task-item-body">{{ task.user_request?.slice(0, 60) }}</div>
          <div class="task-item-meta">{{ formatTime(task.created_at) }}</div>
        </div>
        <div v-if="taskList.length === 0" class="task-empty">
          <el-icon :size="32" color="#94a3b8"><Search /></el-icon>
          <p>暂无任务链路数据</p>
          <p class="task-empty-hint">在业务平台发起 AI 用例生成或工作流执行后，点击搜索即可查看</p>
        </div>
      </div>

      <!-- 右侧链路详情 -->
      <div class="trace-detail-panel">
        <template v-if="selectedTask">
          <div class="detail-header">
            <span>链路详情 #{{ selectedTask.id }}</span>
            <span class="detail-status">{{ STATS_MAP[selectedTask.status] }}</span>
          </div>

          <!-- 时间线 -->
          <div v-if="traceError" class="trace-error">{{ traceError }}</div>
          <div v-else class="timeline">
            <div v-for="step in traceData.steps" :key="step.step" class="timeline-item">
              <div class="timeline-dot" :class="step.status">
                <el-icon v-if="step.status === 'success'" color="#00ff88"><CircleCheckFilled /></el-icon>
                <el-icon v-else-if="step.status === 'error'" color="#f87171"><CircleCloseFilled /></el-icon>
                <el-icon v-else color="#7dd3fc"><Loading /></el-icon>
              </div>
              <div class="timeline-body">
                <div class="timeline-header">
                  <el-tag size="small" :type="phaseColor(step.phase)">{{ step.phase }}</el-tag>
                  <span class="step-title">{{ step.title }}</span>
                  <span class="step-duration">{{ step.duration_ms }}ms</span>
                </div>
                <!-- 思考内容 -->
                <div v-if="step.thinking" class="thinking-box">
                  <div class="thinking-label">THINKING</div>
                  <div class="thinking-content">{{ step.thinking }}</div>
                </div>
                <!-- 动作 -->
                <div v-if="step.action" class="action-box">
                  <div class="action-label">ACTION</div>
                  <code>{{ step.action }}</code>
                </div>
                <!-- 输出 -->
                <div v-if="step.output" class="output-box">
                  <div class="output-label">OUTPUT</div>
                  <pre>{{ JSON.stringify(step.output, null, 2) }}</pre>
                </div>
              </div>
            </div>
          </div>
        </template>
        <div v-else class="empty-trace">
          <el-icon :size="48" color="#94a3b8"><Search /></el-icon>
          <p>选择一个任务查看执行链路</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Search, CircleCheckFilled, CircleCloseFilled, Loading } from '@element-plus/icons-vue'
import api from '@/api'

const route = useRoute()
const STATS_MAP = { running: '执行中', pending: '等待中', completed: '已完成', failed: '失败' }

const searchQuery = ref('')
const statusFilter = ref('')
const taskList = ref([])
const selectedTask = ref(null)
const traceData = ref({ steps: [] })
const traceError = ref('')

function phaseColor(p) {
  return { Plan: 'warning', 'MCP Call': 'primary', Verify: 'success', Execute: '' }[p] || ''
}

function formatTime(t) {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function searchTasks() {
  try {
    const params = { page_size: 50 }
    if (searchQuery.value) params.q = searchQuery.value
    if (statusFilter.value) params.status = statusFilter.value
    const res = await api.get('/agent/tasks/trace/', { params })
    taskList.value = res.data?.items || res.items || res || []
  } catch (e) {
    console.error('搜索任务失败', e)
  }
}

async function selectTask(task) {
  selectedTask.value = task
  traceError.value = ''
  traceData.value = { steps: [] }
  try {
    const res = await api.get(`/agent/tasks/trace/${task.id}/`)
    traceData.value = res.data || res || { steps: [] }
  } catch (e) {
    traceData.value = { steps: [] }
    if (e.response?.status === 404) {
      traceError.value = '该任务的链路数据不存在（可能已被清理或任务执行失败）'
    } else {
      traceError.value = `链路数据获取失败: ${e.response?.data?.detail || e.message}`
    }
  }
}

onMounted(() => {
  searchTasks()
  // 如果 URL 带 taskId，自动选中
  const taskId = route.query.taskId
  if (taskId) {
    api.get(`/agent/tasks/trace/${taskId}/`).then(res => {
      const t = res.data || res
      taskList.value = [t]
      selectTask(t)
    }).catch(() => {})
  }
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

.search-bar, .trace-layout, .task-list-panel, .trace-detail-panel {
  position: relative;
  z-index: 1;
}

.search-bar {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  padding: 12px;
  background: rgba(30, 41, 59, 0.9);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 12px;
  flex: 0 0 auto;
  box-shadow: 0 2px 8px rgba(2, 8, 20, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.08);
  
  transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s;
  contain: layout paint;
}

.search-bar:hover {
  border-color: rgba(64, 158, 255, 0.45);
  box-shadow: 0 12px 40px rgba(2, 132, 199, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.search-bar::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, #409eff, #7dd3fc, transparent);
  border-radius: 12px 12px 0 0;
  opacity: 0.8;
}
.search-input { width: 360px; }
.task-count { color: #e2e8f0; font-size: 13px; margin-left: auto; }

.trace-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 12px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.task-list-panel, .trace-detail-panel {
  background: rgba(30, 41, 59, 0.9);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 16px;
  padding: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 2px 8px rgba(2, 8, 20, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.08);
  
  transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s;
  contain: layout paint;
}

.task-list-panel:hover, .trace-detail-panel:hover {
  border-color: rgba(64, 158, 255, 0.45);
  box-shadow: 0 12px 40px rgba(2, 132, 199, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.task-list-panel::before, .trace-detail-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, #409eff, #7dd3fc, transparent);
  border-radius: 16px 16px 0 0;
  opacity: 0.8;
}

.panel-title {
  font-size: 14px; font-weight: 600; color: #f8fafc;
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.15);
  flex: 0 0 auto;
}

.task-list-body, .trace-detail-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.task-item {
  padding: 10px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.08);
  cursor: pointer;
  border-radius: 6px;
  margin-bottom: 4px;
  transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s, background 0.2s;
}
.task-item:hover, .task-item.active {
  background: rgba(64, 158, 255, 0.12);
  border-color: rgba(64, 158, 255, 0.3);
}
.task-item-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.task-type { color: #7dd3fc; font-size: 12px; }
.task-id { color: #e2e8f0; font-size: 11px; }
.task-item-body { font-size: 12px; color: #e2e8f0; }
.task-item-meta { font-size: 11px; color: #cbd5e1; margin-top: 4px; }
.task-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 40px 16px;   color: #e2e8f0; text-align: center;
}
.task-empty-hint { font-size: 11px; color: #cbd5e1; margin-top: 4px; }

.status-dot {
  width: 8px; height: 8px; border-radius: 50%;
  display: inline-block;
}
.status-dot.running { background: #7dd3fc; box-shadow: 0 0 6px #7dd3fc; }
.status-dot.completed { background: #00ff88; }
.status-dot.failed { background: #f87171; }

/* 详情 */
.detail-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 20px; padding-bottom: 12px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.15);
  font-size: 15px; font-weight: 600; color: #f8fafc;
}
.detail-status { font-size: 13px; color: #7dd3fc; }

/* 时间线 */
.trace-error {
  text-align: center; padding: 32px 16px; color: #fbbf24; font-size: 13px;
  background: rgba(251, 191, 36, 0.1); border-radius: 8px; margin: 16px 0;
}
.timeline { position: relative; padding-left: 20px; }
.timeline::before {
  content: '';
  position: absolute; left: 8px; top: 0; bottom: 0;
  width: 2px; background: rgba(64, 158, 255, 0.2);
}
.timeline-item {
  position: relative;
  padding: 0 0 24px 24px;
}
.timeline-dot {
  position: absolute; left: -16px; top: 2px;
  width: 20px; height: 20px;
  background: rgba(30, 41, 59, 0.95); border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  border: 2px solid rgba(64, 158, 255, 0.3);
  z-index: 1;
}
.timeline-dot.success { border-color: #00ff88; }
.timeline-dot.error { border-color: #f87171; }
.timeline-dot.running { border-color: #7dd3fc; }

.timeline-header {
  display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
}
.step-title { font-size: 13px; color: #f1f5f9; }
.step-duration { font-size: 11px; color: #e2e8f0; margin-left: auto; }

.thinking-box, .action-box, .output-box {
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(64, 158, 255, 0.12);
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 8px;
}
.thinking-label { font-size: 10px; color: #fbbf24; font-weight: 600; margin-bottom: 4px; }
.thinking-content { font-size: 12px; color: #e2e8f0; line-height: 1.6; }
.action-label { font-size: 10px; color: #7dd3fc; font-weight: 600; margin-bottom: 4px; }
.action-box code { font-size: 11px; color: #34d399; }
.output-label { font-size: 10px; color: #00ff88; font-weight: 600; margin-bottom: 4px; }
.output-box pre {
  color: #e2e8f0; font-size: 11px; margin: 0; max-height: 200px; overflow: auto;
  white-space: pre-wrap; word-break: break-all;
}

.empty-trace {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 300px; color: #cbd5e1;
}

/* dark input */
:deep(.el-input__inner), :deep(.el-textarea__inner) {
  background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(64, 158, 255, 0.2); color: #f1f5f9;
}
</style>
