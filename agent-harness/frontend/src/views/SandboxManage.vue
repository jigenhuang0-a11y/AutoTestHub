<template>
  <div class="harness-page sandbox-manage">
    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-card">
        <span class="stat-value">{{ sandboxSummary.total }}</span>
        <span class="stat-label">总实例</span>
      </div>
      <div class="stat-card">
        <span class="stat-value running">{{ sandboxSummary.running }}</span>
        <span class="stat-label">运行中</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ sandboxSummary.idle }}</span>
        <span class="stat-label">空闲</span>
      </div>
      <div class="stat-card">
        <span class="stat-value terminated">{{ sandboxSummary.terminated }}</span>
        <span class="stat-label">已销毁</span>
      </div>
    </div>

    <!-- 沙箱列表 + 操作 -->
    <div class="main-panel">
      <div class="panel-title">
        <span>沙箱实例</span>
        <div class="panel-actions">
          <el-select v-model="typeFilter" placeholder="类型筛选" clearable size="small" style="width:120px">
            <el-option label="全部" value="" />
            <el-option label="Python" value="python" />
            <el-option label="Node.js" value="node" />
            <el-option label="Browser" value="browser" />
          </el-select>
          <el-button type="primary" size="small" @click="createSandbox">+ 创建沙箱</el-button>
        </div>
      </div>
      <el-table :data="filteredSandboxes" class="grid-table" size="small" height="100%" row-key="id" border empty-text="暂无沙箱实例，点击右上角「创建沙箱」新建一个">
        <el-table-column prop="name" label="名称" width="180">
          <template #default="{ row }"><span class="sbx-name">{{ row.name }}</span></template>
        </el-table-column>
        <el-table-column prop="type" label="类型" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="typeStyle(row.type)">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <span :class="'status-dot ' + row.status">{{ STATUS_CN[row.status] }}</span>
          </template>
        </el-table-column>
        <el-table-column label="内存配额" width="140">
          <template #default="{ row }">
            <div class="mem-bar">
              <div class="mem-fill" :style="{ width: (row.memory_used_mb / row.memory_mb * 100) + '%' }" />
              <span class="mem-text">{{ row.memory_used_mb }}/{{ row.memory_mb }} MB</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="cpu_percent" label="CPU" width="80">
          <template #default="{ row }">{{ row.cpu_percent }}%</template>
        </el-table-column>
        <el-table-column label="运行时长" width="110">
          <template #default="{ row }">{{ formatUptime(row.uptime_seconds) }}</template>
        </el-table-column>
        <el-table-column prop="host" label="主机" width="140" />
        <el-table-column prop="created_at" label="创建时间" min-width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small"
              :disabled="row.status !== 'running'"
              @click="openExecute(row)">
              执行
            </el-button>
            <el-button link type="danger" size="small"
              :disabled="row.status === 'terminated'"
              @click="destroySandbox(row)">
              销毁
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 创建沙箱对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建沙箱" width="450px" top="15vh" :close-on-click-modal="false">
      <el-form label-width="80px">
        <el-form-item label="类型">
          <el-select v-model="newSandbox.type" style="width:100%">
            <el-option label="Python" value="python" />
            <el-option label="Node.js" value="node" />
            <el-option label="Browser" value="browser" />
          </el-select>
        </el-form-item>
        <el-form-item label="内存(MB)">
          <el-input-number v-model="newSandbox.memory" :min="256" :max="4096" :step="256" style="width:100%" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="newSandbox.name" placeholder="可选，留空自动生成" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="doCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 执行代码对话框 -->
    <el-dialog v-model="showExecuteDialog" :title="`在沙箱中执行代码 - ${currentSandbox?.name || ''}`" width="750px" top="8vh" :close-on-click-modal="false">
      <div class="exec-meta">
        <span>类型：<el-tag size="small" :type="typeStyle(currentSandbox?.type)">{{ currentSandbox?.type }}</el-tag></span>
        <span>内存配额：{{ currentSandbox?.memory_mb }} MB</span>
        <span>状态：<span :class="'status-dot ' + currentSandbox?.status">{{ STATUS_CN[currentSandbox?.status] }}</span></span>
      </div>

      <!-- 执行模式切换 -->
      <div class="exec-mode-bar">
        <el-radio-group v-model="execMode" size="small">
          <el-radio-button value="code">手写代码</el-radio-button>
          <el-radio-button value="git">Git 仓库 + 分支</el-radio-button>
        </el-radio-group>
      </div>

      <!-- Git 模式：项目地址 + 分支 -->
      <div v-if="execMode === 'git'" class="git-section">
        <el-form label-width="80px" size="small">
          <el-form-item label="仓库地址">
            <el-input
              v-model="repoUrl"
              placeholder="https://github.com/user/repo.git"
              clearable
            />
          </el-form-item>
          <el-form-item label="分支">
            <el-input
              v-model="repoBranch"
              placeholder="main"
              clearable
              style="width: 200px"
            />
          </el-form-item>
        </el-form>
        <p class="git-hint">仓库将被克隆到沙箱临时目录，你的测试脚本可在其上下文中运行。</p>
      </div>

      <el-form label-width="0">
        <el-form-item>
          <el-input
            v-model="executeCode"
            type="textarea"
            :rows="execMode === 'git' ? 10 : 12"
            :placeholder="codePlaceholder"
            class="code-editor"
          />
        </el-form-item>
      </el-form>

      <div v-if="executeResult.status" class="exec-result">
        <div class="exec-result-header">
          <span>执行结果</span>
          <el-tag size="small" :type="executeResult.ok ? 'success' : 'danger'">{{ executeResult.status }}</el-tag>
          <span class="exec-duration">耗时 {{ executeResult.duration_ms }} ms</span>
        </div>
        <pre v-if="executeResult.stdout" class="exec-stdout">{{ executeResult.stdout }}</pre>
        <pre v-if="executeResult.stderr" class="exec-stderr">{{ executeResult.stderr }}</pre>
        <pre v-if="executeResult.error_message" class="exec-stderr">{{ executeResult.error_message }}</pre>
      </div>

      <template #footer>
        <el-button @click="showExecuteDialog = false">关闭</el-button>
        <el-button type="primary" :loading="executing" @click="doExecute">运行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

const STATUS_CN = { running: '运行中', idle: '空闲', terminated: '已销毁' }

const sandboxes = ref([])
const typeFilter = ref('')
const sandboxSummary = reactive({ total: 0, running: 0, idle: 0, terminated: 0 })

const filteredSandboxes = computed(() => {
  if (!typeFilter.value) return sandboxes.value
  return sandboxes.value.filter(s => s.type === typeFilter.value)
})

const showCreateDialog = ref(false)
const creating = ref(false)
const newSandbox = reactive({ type: 'python', memory: 512, name: '' })

const showExecuteDialog = ref(false)
const currentSandbox = ref(null)
const execMode = ref('code')           // 'code' | 'git'
const repoUrl = ref('')
const repoBranch = ref('main')
const executeCode = ref('')
const executing = ref(false)
const executeResult = reactive({
  ok: false,
  status: '',
  stdout: '',
  stderr: '',
  error_message: '',
  duration_ms: 0
})

const codePlaceholder = computed(() => {
  if (execMode.value === 'git') {
    return currentSandbox.value?.type === 'node'
      ? "// 测试脚本：仓库已克隆到工作目录，可直接 require('./src/...')\nconsole.log('Hello from cloned repo')"
      : "# 测试脚本：仓库已克隆到工作目录，可直接 import 或 subprocess 跑测试\nprint('Hello from cloned repo')"
  }
  return currentSandbox.value?.type === 'node' ? '输入 Node.js 代码...' : '输入 Python 代码...'
})

function formatTime(t) {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
}

function typeStyle(t) { return { python: '', node: 'success', browser: 'warning' }[t] || '' }

function formatUptime(s) {
  if (!s) return '-'
  if (s < 3600) return Math.floor(s / 60) + '分钟'
  if (s < 86400) return Math.floor(s / 3600) + '小时'
  return Math.floor(s / 86400) + '天'
}

async function fetchSandboxes() {
  try {
    const res = await api.get('/agent/sandbox/')
    const data = res.data.data || res.data
    sandboxes.value = data.items || data || []
    sandboxSummary.total = sandboxes.value.length
    sandboxSummary.running = sandboxes.value.filter(s => s.status === 'running').length
    sandboxSummary.idle = sandboxes.value.filter(s => s.status === 'idle').length
    sandboxSummary.terminated = sandboxes.value.filter(s => s.status === 'terminated').length
  } catch (e) {
    ElMessage.error('获取沙箱列表失败: ' + e.message)
  }
}



async function createSandbox() {
  showCreateDialog.value = true
}

async function doCreate() {
  creating.value = true
  try {
    await api.post('/agent/sandbox/', {
      type: newSandbox.type,
      memory_mb: newSandbox.memory,
      name: newSandbox.name || undefined,
    })
    ElMessage.success('沙箱创建成功')
    showCreateDialog.value = false
    fetchSandboxes()
  } catch (e) {
    ElMessage.error('创建失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    creating.value = false
  }
}

function destroySandbox(row) {
  ElMessageBox.confirm(`确定销毁沙箱 "${row.name}"？此操作不可恢复。`, '确认销毁', { type: 'warning', confirmButtonText: '销毁' })
    .then(async () => {
      try {
        await api.delete(`/agent/sandbox/${row.id}/`)
        ElMessage.success('已销毁')
        fetchSandboxes()
      } catch (e) {
        ElMessage.error('销毁失败: ' + (e.response?.data?.detail || e.message))
      }
    })
    .catch(() => {})
}

function openExecute(row) {
  currentSandbox.value = row
  execMode.value = 'code'
  repoUrl.value = ''
  repoBranch.value = 'main'
  executeCode.value = row.type === 'node'
    ? "console.log('Hello from Node sandbox')"
    : "print('Hello from Python sandbox')"
  Object.assign(executeResult, {
    ok: false,
    status: '',
    stdout: '',
    stderr: '',
    error_message: '',
    duration_ms: 0
  })
  showExecuteDialog.value = true
}

async function doExecute() {
  if (!executeCode.value.trim()) {
    ElMessage.warning('请输入要执行的代码')
    return
  }
  if (execMode.value === 'git' && !repoUrl.value.trim()) {
    ElMessage.warning('Git 模式下请填写仓库地址')
    return
  }
  executing.value = true
  try {
    const payload = {
      code: executeCode.value,
      timeout: 300
    }
    if (execMode.value === 'git') {
      payload.repo_url = repoUrl.value.trim()
      payload.branch = repoBranch.value.trim() || 'main'
    }
    const res = await api.post(`/agent/sandbox/${currentSandbox.value.id}/execute`, payload)
    Object.assign(executeResult, {
      ok: res.data.status === 'success',
      status: res.data.status,
      stdout: res.data.stdout || '',
      stderr: res.data.stderr || '',
      error_message: res.data.error_message || '',
      duration_ms: res.data.duration_ms || 0,
    })
    if (res.data.status === 'success') {
      ElMessage.success(`执行完成 (${res.data.duration_ms}ms)`)
    } else {
      ElMessage.warning('执行异常: ' + (res.data.error_message || res.data.stderr || '未知错误'))
    }
    fetchSandboxes()
  } catch (e) {
    ElMessage.error('沙箱执行失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    executing.value = false
  }
}

onMounted(() => { fetchSandboxes() })
</script>

<style scoped>
.harness-page {
  background: #1a2d45;
  height: calc(100vh - 56px);
  min-height: 0;
  padding: 16px;
  color: #f1f5f9;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  display: flex;
  flex-direction: column;
  overflow: hidden;
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

.stats-row, .main-panel, .audit-panel, .stat-card {
  position: relative;
  z-index: 1;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 12px;
  flex: 0 0 auto;
}

.stat-card, .main-panel, .audit-panel {
  background: rgba(30, 41, 59, 0.95);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 16px !important;
  box-shadow: 0 2px 8px rgba(2, 8, 20, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
  contain: layout paint;
  transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s;
}

.stat-card {
  display: flex;
  flex-direction: column;
  padding: 16px;
}

.main-panel {
  display: flex;
  flex-direction: column;
  padding: 16px;
  flex: 1;
  min-height: 0;
  margin-bottom: 12px;
}

.audit-panel {
  display: flex;
  flex-direction: column;
  padding: 16px;
  flex: 0 0 220px;
  min-height: 0;
}

.stat-value { font-size: 28px; font-weight: 700; color: #7dd3fc; }
.stat-value.running { color: #00ff88; }
.stat-value.terminated { color: #f87171; }
.stat-label { font-size: 12px; color: #e2e8f0; margin-top: 4px; }

.stat-card:hover, .main-panel:hover, .audit-panel:hover {
  border-color: rgba(64, 158, 255, 0.45) !important;
  box-shadow: 0 12px 40px rgba(2, 132, 199, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.1) !important;
}

.stat-card::before, .main-panel::before, .audit-panel::before {
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

.panel-title { color: #f8fafc !important; }

.sbx-name { color: #7dd3fc; font-weight: 500; }

.mem-bar {
  position: relative;
  background: rgba(15, 23, 42, 0.8);
  border-radius: 4px;
  height: 22px;
  overflow: hidden;
}
.mem-fill {
  position: absolute; left: 0; top: 0; bottom: 0;
  background: linear-gradient(90deg, #7dd3fc, #00ff88);
  transition: width 0.5s;
  border-radius: 4px;
}
.mem-text {
  position: relative; z-index: 1;
  font-size: 11px; color: #e2e8f0;
  display: flex; align-items: center; justify-content: center;
  height: 100%;
}

.status-dot::before {
  content: ''; display: inline-block;
  width: 7px; height: 7px; border-radius: 50%; margin-right: 6px;
}
.status-dot.running::before { background: #00ff88; box-shadow: 0 0 6px #00ff88; }
.status-dot.idle::before { background: #fbbf24; }
.status-dot.terminated::before { background: #94a3b8; }

.event-HIGH { color: #f87171; font-weight: 500; }

/* 表格暗色 */
:deep(.grid-table.el-table) {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: rgba(30, 41, 59, 0.95);
  --el-table-row-hover-bg-color: rgba(64, 158, 255, 0.12);
  --el-table-border-color: rgba(64, 158, 255, 0.18);
  --el-table-text-color: #e2e8f0;
  --el-table-header-text-color: #e2e8f0;
}
:deep(.grid-table.el-table .el-table__cell) { border: 1px solid rgba(64, 158, 255, 0.12) !important; }
:deep(.grid-table.el-table th.el-table__cell) {
  background: rgba(30, 41, 59, 0.95);
  border-bottom: 1px solid rgba(64, 158, 255, 0.25) !important;
  padding: 10px 8px;
  font-weight: 600;
}
:deep(.grid-table.el-table td.el-table__cell) { border-bottom: 1px solid rgba(64, 158, 255, 0.12) !important; padding: 8px; }
:deep(.grid-table.el-table tr.el-table__row--striped td.el-table__cell) { background: rgba(255, 255, 255, 0.03); }
:deep(.grid-table.el-table::before) { display: none; }
:deep(.grid-table.el-table--border::after) { display: none; }

/* 对话框暗色 */
:deep(.el-dialog) { background: rgba(30, 41, 59, 0.9); border: 1px solid rgba(64, 158, 255, 0.3); }
:deep(.el-dialog__title) { color: #f1f5f9; }
:deep(.el-dialog__body) { color: #e2e8f0; }
:deep(.el-input__inner) { background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(64, 158, 255, 0.3); color: #e2e8f0; }
:deep(.el-form-item__label) { color: #e2e8f0; }
/* 执行对话框 */
.exec-meta {
  display: flex;
  gap: 20px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #e2e8f0;
}
.exec-meta span {
  display: flex;
  align-items: center;
  gap: 6px;
}
/* ------- 执行模式切换 ------- */
.exec-mode-bar {
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.15);
}

.git-section {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(64, 158, 255, 0.2);
  border-radius: 8px;
  padding: 14px 16px 6px;
  margin-bottom: 14px;
}

.git-hint {
  font-size: 12px;
  color: #94a3b8;
  margin: 4px 0 0 0;
  line-height: 1.5;
}

:deep(.code-editor .el-textarea__inner) {
  background: rgba(15, 23, 42, 0.8) !important;
  border: 1px solid rgba(64, 158, 255, 0.2) !important;
  color: #00ff88 !important;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 13px;
}
.exec-result {
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 6px;
  padding: 12px;
  margin-top: 12px;
}
.exec-result-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  font-weight: 600;
  color: #f1f5f9;
}
.exec-duration {
  margin-left: auto;
  font-size: 12px;
  color: #e2e8f0;
  font-weight: normal;
}
.exec-result pre {
  margin: 0 0 8px 0;
  padding: 8px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}
.exec-stdout {
  background: rgba(15, 23, 42, 0.8);
  color: #00ff88;
}
.exec-stderr {
  background: rgba(248, 113, 113, 0.1);
  color: #f87171;
}
</style>

