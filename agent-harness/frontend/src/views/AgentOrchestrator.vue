<template>
  <div class="harness-page agent-orchestrator">
    <div class="ao-body">
      <!-- Hero 标题区（卡片式，融入中台框架） -->
      <div class="hero-card">
        <div class="hero-section">
          <div class="hero-icon-wrap">
            <el-icon :size="20"><Connection /></el-icon>
          </div>
          <div class="hero-text">
            <h1 class="hero-title">Agent 编排中心</h1>
            <p class="hero-subtitle">多 Agent 团队协作编排 · 工作树拆解 · 自动化调度执行</p>
          </div>
          <el-button class="hero-new" type="primary" @click="openCreate">
            <el-icon><Plus /></el-icon> 新建编排任务
          </el-button>
        </div>
      </div>

      <!-- 统计胶囊 -->
      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-icon total"><Document /></span>
          <div class="stat-text"><span class="stat-value">{{ tasks.length }}</span><span class="stat-label">编排任务</span></div>
        </div>
        <div class="stat-card">
          <span class="stat-icon active"><Clock /></span>
          <div class="stat-text"><span class="stat-value">{{ activeCount }}</span><span class="stat-label">进行中</span></div>
        </div>
        <div class="stat-card">
          <span class="stat-icon done"><Select /></span>
          <div class="stat-text"><span class="stat-value">{{ doneCount }}</span><span class="stat-label">已完成</span></div>
        </div>
        <div class="stat-card">
          <span class="stat-icon blocked"><WarningFilled /></span>
          <div class="stat-text"><span class="stat-value">{{ blockedCount }}</span><span class="stat-label">阻塞</span></div>
        </div>
      </div>

      <div class="main-row">
        <!-- 左：任务列表 -->
        <div class="task-list-panel">
          <div class="panel-title">
            <span><el-icon><List /></el-icon> 编排任务</span>
            <el-input v-model="filterText" size="small" placeholder="搜索任务" class="list-search" clearable />
          </div>
          <div v-if="loadingTasks" class="panel-loading">
            <el-icon class="is-loading"><Loading /></el-icon> 加载中…
          </div>
          <div v-else-if="filteredTasks.length === 0" class="empty-hint">
            <div class="ao-empty small">
              <el-icon :size="40"><Connection /></el-icon>
              <p>{{ tasks.length ? '无匹配任务' : '暂无任务，点击右上角新建' }}</p>
            </div>
          </div>
          <div class="task-scroll">
            <div
              v-for="t in filteredTasks"
              :key="t.id"
              class="task-item"
              :class="[{ active: selectedId === t.id }, 's-' + t.status]"
              @click="selectTask(t)"
            >
              <div class="task-item-head">
                <span class="task-title">{{ t.title }}</span>
                <el-tag size="small" :type="statusTagType(t.status)" effect="dark">{{ statusText(t.status) }}</el-tag>
              </div>
              <div class="task-item-desc">{{ t.description || '未填写描述' }}</div>
              <div class="task-item-meta">
                <span class="ti-roles"><el-icon><User /></el-icon> {{ (t.required_roles || []).join('/') || '—' }}</span>
                <span class="prio-pill" :class="'p-' + (t.priority || 3)">{{ prioText(t.priority) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 右：任务详情 / 编排 -->
        <div class="task-detail-panel">
          <template v-if="selected">
            <div class="detail-head">
              <div class="detail-head-info">
                <div class="detail-title-row">
                  <h3 class="detail-title">{{ selected.title }}</h3>
                  <el-tag size="small" :type="statusTagType(selected.status)" effect="dark">{{ statusText(selected.status) }}</el-tag>
                </div>
                <p class="detail-sub">{{ selected.description || '未填写描述' }}</p>
                <div class="meta-chips">
                  <span class="chip"><el-icon><Avatar /></el-icon> 角色 {{ (selected.required_roles || []).join(' / ') || '—' }}</span>
                  <span class="chip"><el-icon><Cpu /></el-icon> 模型 {{ selected.model || '—' }}</span>
                  <span class="chip"><el-icon><Flag /></el-icon> 优先级 {{ prioText(selected.priority) }}</span>
                  <span v-if="selected.assigned_role" class="chip on"><el-icon><Pointer /></el-icon> 当前 {{ selected.assigned_role }}</span>
                </div>
              </div>
              <div class="detail-actions">
                <el-button size="small" type="warning" :loading="acting" @click="doAction('next')">推进下一步</el-button>
                <el-button size="small" type="success" :disabled="selected.status === 'done'" @click="openAssign">派单</el-button>
                <el-button size="small" type="primary" :disabled="selected.status === 'done' || selected.status === 'blocked'" @click="doAction('execute')">执行</el-button>
                <el-button size="small" :disabled="selected.status !== 'in_progress'" @click="doAction('submit-review')">提交评审</el-button>
                <el-button size="small" type="success" :disabled="selected.status !== 'review'" @click="doAction('review', 'accept')">通过评审</el-button>
                <el-button size="small" type="danger" :disabled="selected.status !== 'blocked'" @click="doAction('unblock')">解除阻塞</el-button>
              </div>
            </div>

            <!-- 状态进度 -->
            <div class="flow-bar">
              <el-steps :active="stepIndex(selected.status)" finish-status="success" size="small">
                <el-step title="已创建" />
                <el-step title="已分配" />
                <el-step title="进行中" />
                <el-step title="评审中" />
                <el-step title="已完成" />
              </el-steps>
            </div>

            <!-- 编排执行轨迹（时间线） -->
            <div class="hist-block">
              <div class="panel-title"><span><el-icon><Histogram /></el-icon> 编排执行轨迹</span></div>
              <el-timeline class="hist-timeline">
                <el-timeline-item
                  v-for="(h, i) in hist"
                  :key="i"
                  :timestamp="fmt(h.timestamp)"
                  placement="top"
                  :color="actionColor(h.action)"
                  :hollow="i !== hist.length - 1"
                >
                  <div class="tl-card">
                    <div class="tl-head">
                      <el-tag size="small" effect="dark" :type="actionTag(h.action)">{{ h.action }}</el-tag>
                      <span v-if="h.role" class="tl-role">[{{ h.role }}]</span>
                      <span v-if="h.handoff_to" class="tl-handoff">→ 交接 {{ h.handoff_to }}</span>
                      <span v-if="h.verdict" class="tl-verdict">裁决：{{ h.verdict }}</span>
                    </div>
                    <div class="tl-msg">{{ h.message }}</div>
                  </div>
                </el-timeline-item>
                <el-timeline-item v-if="!hist.length" :hollow="true" color="#3a5070">
                  <div class="tl-empty">暂无轨迹，点击「推进下一步」开始编排</div>
                </el-timeline-item>
              </el-timeline>
            </div>

            <!-- 产物 -->
            <div v-if="artifacts.length" class="artifacts-block">
              <div class="panel-title"><span><el-icon><Files /></el-icon> 产物</span></div>
              <div class="art-grid">
                <div v-for="(a, i) in artifacts" :key="i" class="art-card">
                  <div class="art-card-head">
                    <span class="art-name">{{ a.name }}</span>
                    <el-tag size="small" effect="plain" type="info">{{ a.type }}</el-tag>
                  </div>
                  <div class="art-content" :title="a.content">{{ a.content }}</div>
                  <div class="art-owner">产出方：{{ a.owner || '—' }}</div>
                </div>
              </div>
            </div>

            <!-- 人工消息 -->
            <div v-if="humanMessages.length" class="human-block">
              <div class="panel-title"><span><el-icon><ChatDotRound /></el-icon> 人工消息</span></div>
              <div class="hist-box small">
                <div v-for="(m, i) in humanMessages" :key="i" class="hist-line">
                  <span class="hist-role">[{{ m.from_role }}]</span>
                  <span class="hist-msg">{{ m.message }}</span>
                </div>
              </div>
            </div>
          </template>

          <div v-else class="detail-empty">
            <div class="ao-empty">
              <el-icon :size="64"><Connection /></el-icon>
              <p>选择左侧任务，查看编排详情</p>
              <p class="ao-empty-sub">或点击右上角新建一个编排任务</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 新建任务弹窗 -->
    <el-dialog v-model="createVisible" title="新建编排任务" width="540px" class="ao-dialog">
      <el-form label-width="84px">
        <el-form-item label="任务标题" required>
          <el-input v-model="form.title" placeholder="如 生成登录模块测试用例" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="任务详细说明" />
        </el-form-item>
        <el-form-item label="所需角色">
          <el-select v-model="form.required_roles" multiple placeholder="选择参与角色" style="width: 100%">
            <el-option v-for="r in roleOptions" :key="r" :label="r" :value="r" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型">
          <el-select v-model="form.model" placeholder="选择模型" style="width: 100%">
            <el-option label="deepseek-chat" value="deepseek-chat" />
            <el-option label="gpt-4o" value="gpt-4o" />
            <el-option label="claude-3.5" value="claude-3.5-sonnet" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="form.priority" style="width: 100%">
            <el-option label="最低" :value="1" />
            <el-option label="低" :value="2" />
            <el-option label="中" :value="3" />
            <el-option label="高" :value="4" />
            <el-option label="紧急" :value="5" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 派单弹窗 -->
    <el-dialog v-model="assignVisible" title="派单给角色" width="460px" class="ao-dialog">
      <el-form label-width="70px">
        <el-form-item label="角色" required>
          <el-select v-model="assignForm.role" placeholder="选择角色" style="width: 100%">
            <el-option v-for="r in roleOptions" :key="r" :label="r" :value="r" />
          </el-select>
        </el-form-item>
        <el-form-item label="指令">
          <el-input v-model="assignForm.message" type="textarea" :rows="3" placeholder="给该角色的指令" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitAssign">派单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Clock } from '@element-plus/icons-vue'
import { teamAPI } from '@/api'

const roleOptions = ['orchestrator', 'planner', 'builder', 'reviewer', 'ops']

const tasks = ref([])
const loadingTasks = ref(false)
const filterText = ref('')
const selectedId = ref(null)
const selected = ref(null)
const acting = ref(false)

const activeCount = computed(() => tasks.value.filter(t => ['assigned', 'in_progress', 'review'].includes(t.status)).length)
const doneCount = computed(() => tasks.value.filter(t => t.status === 'done').length)
const blockedCount = computed(() => tasks.value.filter(t => t.status === 'blocked').length)

const filteredTasks = computed(() => {
  const kw = filterText.value.trim().toLowerCase()
  if (!kw) return tasks.value
  return tasks.value.filter(t =>
    (t.title || '').toLowerCase().includes(kw) ||
    (t.description || '').toLowerCase().includes(kw) ||
    (t.required_roles || []).join('/').toLowerCase().includes(kw)
  )
})

const hist = computed(() => selected.value?.orchestration_history || [])
const artifacts = computed(() => selected.value?.artifacts || [])
const humanMessages = computed(() => selected.value?.human_messages || [])

function statusText(s) {
  return { inbox: '待分配', assigned: '已分配', in_progress: '进行中', review: '评审中', done: '已完成', blocked: '阻塞', failed: '失败' }[s] || (s || '待分配')
}
function statusTagType(s) {
  return { inbox: 'info', assigned: '', in_progress: 'warning', review: 'warning', done: 'success', blocked: 'danger', failed: 'danger' }[s] || 'info'
}
function actionTag(a) {
  const m = { create: 'success', assign: 'primary', execute: 'warning', advance: 'info', handoff: 'warning', review: 'primary', unblock: 'danger', message: 'info' }
  return m[a] || 'info'
}
function actionColor(a) {
  const m = { create: '#22c55e', assign: '#3b82f6', execute: '#f59e0b', advance: '#5aa0e8', handoff: '#f59e0b', review: '#3b82f6', unblock: '#ef4444', message: '#5aa0e8' }
  return m[a] || '#5aa0e8'
}
function stepIndex(s) {
  return { inbox: 0, assigned: 1, in_progress: 2, review: 3, done: 4 }[s] ?? 0
}
function prioText(p) {
  return { 1: '最低', 2: '低', 3: '中', 4: '高', 5: '紧急' }[p] || '中'
}
function fmt(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN', { hour12: false })
}

async function loadTasks() {
  loadingTasks.value = true
  try {
    const data = await teamAPI.list()
    tasks.value = data.items || []
    if (selectedId.value) {
      selected.value = tasks.value.find(t => t.id === selectedId.value) || null
    }
  } catch (e) {
    ElMessage.error('加载任务失败')
  } finally {
    loadingTasks.value = false
  }
}

function selectTask(t) {
  selectedId.value = t.id
  selected.value = t
}

async function doAction(action, verdict) {
  acting.value = true
  try {
    let res
    if (action === 'review') res = await teamAPI.review(selectedId.value, verdict)
    else if (action === 'next') res = await teamAPI.next(selectedId.value)
    else if (action === 'execute') res = await teamAPI.execute(selectedId.value)
    else if (action === 'submit-review') res = await teamAPI.submitReview(selectedId.value)
    else if (action === 'unblock') res = await teamAPI.unblock(selectedId.value)
    ElMessage.success(res?.message || '操作成功')
    await refresh()
  } catch (e) {
    ElMessage.error('操作失败：' + (e.response?.data?.detail || e.message))
  } finally {
    acting.value = false
  }
}

async function refresh() {
  await loadTasks()
}

// 新建
const createVisible = ref(false)
const creating = ref(false)
const form = ref({ title: '', description: '', required_roles: ['planner', 'builder', 'reviewer'], model: 'deepseek-chat', priority: 3 })
function openCreate() {
  form.value = { title: '', description: '', required_roles: ['planner', 'builder', 'reviewer'], model: 'deepseek-chat', priority: 3 }
  createVisible.value = true
}
async function submitCreate() {
  if (!form.value.title.trim()) {
    ElMessage.warning('请填写任务标题')
    return
  }
  creating.value = true
  try {
    const res = await teamAPI.create(form.value)
    ElMessage.success('任务已创建')
    createVisible.value = false
    await loadTasks()
    if (res.id) selectTask({ id: res.id })
  } catch (e) {
    ElMessage.error('创建失败：' + (e.response?.data?.detail || e.message))
  } finally {
    creating.value = false
  }
}

// 派单
const assignVisible = ref(false)
const assignForm = ref({ role: '', message: '' })
function openAssign() {
  if (selected.value?.status === 'done') return
  assignForm.value = { role: '', message: '' }
  assignVisible.value = true
}
async function submitAssign() {
  if (!assignForm.value.role) {
    ElMessage.warning('请选择角色')
    return
  }
  acting.value = true
  try {
    const res = await teamAPI.assign(selectedId.value, assignForm.value.role, assignForm.value.message)
    ElMessage.success(res?.message || '派单成功')
    assignVisible.value = false
    await refresh()
  } catch (e) {
    ElMessage.error('派单失败：' + (e.response?.data?.detail || e.message))
  } finally {
    acting.value = false
  }
}

onUnmounted(() => {})

loadTasks()
</script>

<style scoped>
.agent-orchestrator {
  position: relative;
  height: 100%;
  background: #112544;
  overflow-y: auto;
  overflow-x: hidden;
}

.ao-body {
  position: relative;
  z-index: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 18px 24px 22px;
}

/* Hero 卡片（融入中台框架） */
.hero-card {
  flex-shrink: 0;
  background: rgba(12, 26, 50, 0.65);
  border: 1px solid rgba(80, 140, 210, 0.16);
  border-radius: 14px;
  padding: 14px 18px;
  margin-bottom: 16px;
  backdrop-filter: blur(8px);
  box-shadow: 0 4px 18px rgba(8, 20, 40, 0.18);
}

/* Hero 卡片（融入中台框架） */
.hero-card {
  background: rgba(16, 32, 56, 0.55);
  border: 1px solid rgba(80, 140, 210, 0.16);
  border-radius: 16px;
  padding: 16px 20px;
  margin-bottom: 18px;
  backdrop-filter: blur(8px);
  box-shadow: 0 4px 18px rgba(8, 20, 40, 0.18);
}

/* ===== Hero 区 ===== */
.hero-section {
  display: flex;
  align-items: center;
  gap: 14px;
}
.hero-icon-wrap {
  width: 44px; height: 44px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(50, 120, 220, 0.18), rgba(100, 80, 200, 0.12));
  border: 1px solid rgba(80, 140, 220, 0.2);
  color: #5a90d8;
}
.hero-text { flex: 1; }
.hero-title { margin: 0; font-size: 20px; font-weight: 800; color: #fff; letter-spacing: 0.5px; }
.hero-subtitle { margin: 4px 0 0; font-size: 12px; color: #82a8d8; letter-spacing: 0.5px; }
.hero-new { background: linear-gradient(135deg, #2563eb, #3b82f6); border: none; box-shadow: 0 4px 16px rgba(40, 110, 220, 0.35); }

/* ===== 统计胶囊 ===== */
.stats-row { display: flex; gap: 14px; margin-bottom: 18px; }
.stat-card {
  flex: 1; display: flex; align-items: center; gap: 10px;
  background: rgba(12, 24, 46, 0.55); border: 1px solid rgba(80, 140, 210, 0.16);
  border-radius: 12px; padding: 12px 14px;
  backdrop-filter: blur(8px);
  transition: border-color .25s, transform .25s, box-shadow .25s;
}
.stat-card:hover {
  transform: translateY(-2px);
  border-color: rgba(90, 160, 240, 0.35);
  box-shadow: 0 8px 22px rgba(20, 60, 120, 0.25);
}
.stat-icon {
  width: 30px; height: 30px; border-radius: 9px;
  display: flex; align-items: center; justify-content: center; font-size: 15px;
}
.stat-icon.total { color: #7ab0f0; background: rgba(90, 160, 240, 0.12); border: 1px solid rgba(90,160,240,.25); }
.stat-icon.active { color: #fbbf24; background: rgba(251, 191, 36, 0.12); border: 1px solid rgba(251,191,36,.25); }
.stat-icon.done { color: #22c55e; background: rgba(34, 197, 94, 0.12); border: 1px solid rgba(34,197,94,.25); }
.stat-icon.blocked { color: #ef4444; background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239,68,68,.25); }
.stat-text { display: flex; flex-direction: column; line-height: 1.1; gap: 2px; }
.stat-value { font-size: 20px; font-weight: 800; color: #e8f1ff; }
.stat-label { font-size: 11px; color: #7a9ab8; }

/* ===== 主布局 ===== */
.main-row {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 16px;
  align-items: stretch;
}
.panel-title {
  display: flex; justify-content: space-between; align-items: center; gap: 10px;
  font-size: 14px; font-weight: 600; color: #c9d4e3; margin-bottom: 12px;
}
.panel-title .el-icon { margin-right: 4px; vertical-align: -2px; color: #6fa0e0; }

.task-list-panel, .task-detail-panel {
  background: rgba(12, 24, 46, 0.6); border: 1px solid rgba(80, 140, 210, 0.16);
  border-radius: 14px; padding: 18px;
  backdrop-filter: blur(8px);
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}
.panel-loading { color: #8a94a6; font-size: 13px; padding: 20px; }

.list-search { width: 150px; }
.list-search :deep(.el-input__wrapper) { background: rgba(8, 18, 35, 0.6); border-radius: 9px; }

.task-scroll { flex: 1; min-height: 0; overflow-y: auto; padding-right: 4px; }

/* 任务列表项 */
.task-item {
  border: 1px solid rgba(80, 140, 210, 0.14); border-radius: 12px; padding: 12px 14px;
  margin-bottom: 10px; cursor: pointer; transition: all .2s;
  background: rgba(255, 255, 255, 0.02);
  position: relative; overflow: hidden;
}
.task-item::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
  background: transparent; transition: background .2s;
}
.task-item:hover { border-color: rgba(90, 160, 240, 0.4); transform: translateX(2px); }
.task-item.active { border-color: rgba(90, 160, 240, 0.6); background: rgba(40, 90, 170, 0.16); }
.task-item.active::before { background: linear-gradient(180deg, #5aa0e8, #3b82f6); }
.task-item.s-blocked.active::before { background: linear-gradient(180deg, #ef4444, #b91c1c); }
.task-item.s-done.active::before { background: linear-gradient(180deg, #22c55e, #15803d); }

.task-item-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.task-title { font-weight: 600; color: #e6edf5; font-size: 14px; }
.task-item-desc {
  font-size: 12px; color: #8a9bb4; margin: 6px 0; line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.task-item-meta { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: #7a9ab8; }
.ti-roles { display: inline-flex; align-items: center; gap: 4px; }
.prio-pill {
  padding: 1px 9px; border-radius: 999px; font-size: 11px; font-weight: 600;
  border: 1px solid transparent;
}
.p-1, .p-2 { color: #7a9ab8; background: rgba(120, 150, 190, 0.14); border-color: rgba(120,150,190,.25); }
.p-3 { color: #7ab0f0; background: rgba(90, 160, 240, 0.14); border-color: rgba(90,160,240,.3); }
.p-4 { color: #fbbf24; background: rgba(251, 191, 36, 0.14); border-color: rgba(251,191,36,.3); }
.p-5 { color: #ef4444; background: rgba(239, 68, 68, 0.14); border-color: rgba(239,68,68,.3); }

/* ===== 详情头部 ===== */
.detail-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 16px; margin-bottom: 16px; flex-wrap: wrap;
}
.detail-head-info { flex: 1; min-width: 280px; }
.detail-title-row { display: flex; align-items: center; gap: 10px; }
.detail-title { margin: 0; font-size: 19px; color: #eaf2ff; font-weight: 800; }
.detail-sub { margin: 6px 0 10px; font-size: 12px; color: #8a9bb4; line-height: 1.5; }
.meta-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 12px; color: #9fb4d0; padding: 4px 10px; border-radius: 8px;
  background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(80, 140, 210, 0.16);
}
.chip.on { color: #7ab0f0; border-color: rgba(90, 160, 240, 0.35); background: rgba(40, 90, 170, 0.16); }
.chip .el-icon { font-size: 13px; }
.detail-actions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }

/* 进度条 */
.flow-bar {
  margin: 8px 0 18px; padding: 16px 12px 4px;
  background: rgba(8, 18, 35, 0.4); border-radius: 12px; border: 1px solid rgba(80, 140, 210, 0.12);
}

/* ===== 轨迹时间线 ===== */
.hist-timeline { padding: 4px 2px 0; }
.hist-timeline :deep(.el-timeline-item__timestamp) {
  color: #6c84a8; font-size: 11px; font-family: 'JetBrains Mono', Consolas, monospace;
}
.tl-card {
  background: rgba(8, 18, 35, 0.5); border: 1px solid rgba(80, 140, 210, 0.14);
  border-radius: 10px; padding: 10px 12px;
}
.tl-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 6px; }
.tl-role { color: #7ab0f0; font-weight: 600; font-size: 12px; }
.tl-handoff { color: #fbbf24; font-size: 12px; }
.tl-verdict { color: #9fb4d0; font-size: 12px; }
.tl-msg { color: #aebfd4; font-size: 12px; line-height: 1.6; }
.tl-empty { color: #5a6473; font-style: italic; font-size: 12px; }

/* ===== 产物卡片 ===== */
.art-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.art-card {
  background: rgba(8, 18, 35, 0.5); border: 1px solid rgba(80, 140, 210, 0.16);
  border-radius: 12px; padding: 12px;
}
.art-card-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 8px; }
.art-name { font-weight: 600; color: #dce7f5; font-size: 13px; }
.art-content {
  font-size: 12px; color: #9fb0c3; line-height: 1.6; min-height: 36px;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.art-owner { font-size: 11px; color: #6c84a8; margin-top: 6px; }

.hist-box.small {
  background: rgba(8, 18, 35, 0.5); border: 1px solid rgba(80, 140, 210, 0.14);
  border-radius: 10px; height: 140px; overflow-y: auto; padding: 12px; font-size: 12px; line-height: 1.7;
}
.hist-line { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px; padding: 3px 0; border-bottom: 1px dashed rgba(255, 255, 255, 0.05); }
.hist-role { color: #7ab0f0; font-weight: 600; }
.hist-msg { color: #aebfd4; }

.hist-block, .artifacts-block, .human-block { margin-bottom: 18px; }

.detail-empty, .empty-hint { flex: 1; display: flex; align-items: center; justify-content: center; min-height: 0; }

.ao-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; color: #7a9ab8; gap: 10px;
}
.ao-empty .el-icon { color: rgba(90, 140, 210, 0.45); filter: drop-shadow(0 0 8px rgba(90,140,210,.25)); }
.ao-empty p { margin: 0; font-size: 14px; color: #9fb4d0; }
.ao-empty .ao-empty-sub { font-size: 12px; color: #6c84a8; }
.ao-empty.small { gap: 8px; }
.ao-empty.small .el-icon { color: rgba(90, 140, 210, 0.35); filter: none; }
.ao-empty.small p { font-size: 13px; }

/* 弹窗 */
.ao-dialog :deep(.el-dialog) {
  background: #13243f; border: 1px solid rgba(80, 140, 210, 0.2); border-radius: 16px;
}
.ao-dialog :deep(.el-dialog__title) { color: #eaf2ff; }
.ao-dialog :deep(.el-dialog__body) { color: #c9d4e3; }

/* 滚动条 */
.task-scroll::-webkit-scrollbar, .hist-box.small::-webkit-scrollbar { width: 6px; }
.task-scroll::-webkit-scrollbar-thumb, .hist-box.small::-webkit-scrollbar-thumb {
  background: rgba(90, 140, 200, 0.3); border-radius: 3px;
}

@media (max-width: 1000px) {
  .main-row { grid-template-columns: 1fr; }
  .ao-body { padding: 18px 16px; }
}
</style>
