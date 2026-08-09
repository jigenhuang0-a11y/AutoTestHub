<template>
  <div class="harness-page team-model-settings">
    <div class="main-panel">
      <div class="panel-title">
        <span>团队模型偏好</span>
        <span class="panel-hint">不同团队可按任务类型选择不同模型，留空则继承全局默认</span>
      </div>

      <div class="settings-layout">
        <!-- 左侧：团队列表 -->
        <div class="team-list-panel">
          <div class="team-list-header">
            <span>团队列表</span>
            <el-button type="primary" size="small" @click="showAddTeamDialog">
              <el-icon><Plus /></el-icon> 添加团队
            </el-button>
          </div>

          <div v-if="loadingTeams" class="team-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>加载中...</span>
          </div>

          <div v-else class="team-list">
            <div
              v-for="team in teamList"
              :key="team"
              class="team-item"
              :class="{ active: selectedTeam === team }"
              @click="selectTeam(team)"
            >
              <div class="team-row">
                <span class="team-name">{{ team }}</span>
                <div class="team-actions">
                  <el-tag v-if="team === 'global'" type="info" size="small" effect="plain">全局</el-tag>
                  <el-tooltip v-if="isCustomTeam(team)" content="删除团队" placement="top">
                    <el-button
                      type="danger"
                      link
                      size="small"
                      :icon="Delete"
                      @click.stop="deleteTeam(team)"
                    />
                  </el-tooltip>
                </div>
              </div>
              <div class="team-overrides">
                <el-tag v-if="getTeamOverrideCount(team) > 0" type="warning" size="small" effect="dark">
                  {{ getTeamOverrideCount(team) }} 项覆盖
                </el-tag>
                <span v-else class="no-override">继承全局默认</span>
              </div>
            </div>

            <div v-if="teamList.length === 0" class="empty-team-list">
              暂无团队，点击右上角添加
            </div>
          </div>
        </div>

        <!-- 右侧：配置表单 -->
        <div class="form-panel">
          <div v-if="selectedTeam" class="form-header">
            <div class="current-team">
              <span class="label">当前团队：</span>
              <strong>{{ selectedTeam }}</strong>
              <el-tag v-if="getTeamOverrideCount(selectedTeam) > 0" type="warning" size="small" style="margin-left: 8px">
                {{ getTeamOverrideCount(selectedTeam) }} 项覆盖
              </el-tag>
              <el-tag v-else type="info" size="small" style="margin-left: 8px">继承全局默认</el-tag>
            </div>
            <div class="form-actions">
              <el-button type="success" :loading="saving" @click="savePrefs">
                <el-icon><Check /></el-icon> 保存配置
              </el-button>
              <el-button :loading="saving" @click="resetPrefs">
                <el-icon><RefreshLeft /></el-icon> 恢复全局默认
              </el-button>
            </div>
          </div>

          <div v-if="selectedTeam" class="prefs-form-container">
            <el-alert
              v-if="selectedTeam === 'global'"
              title="global 为全局默认团队，所有未单独配置的团队都会继承此配置"
              type="info"
              :closable="false"
              style="margin-bottom: 16px"
            />

            <el-form label-width="180px" class="prefs-form">
              <el-form-item
                v-for="field in modelFields"
                :key="field.key"
                :label="field.label"
              >
                <el-select
                  v-model="form[field.key]"
                  clearable
                  :placeholder="'留空使用全局默认'"
                  style="width: 340px"
                >
                  <el-option
                    v-for="m in availableModels"
                    :key="m.name"
                    :label="`${m.name}  (${m.provider})`"
                    :value="m.name"
                  >
                    <span style="float:left">{{ m.name }}</span>
                    <span style="float:right;color:#94a3b8;font-size:12px">{{ m.provider }}</span>
                  </el-option>
                </el-select>
                <span class="field-cap">{{ field.cap }}</span>
              </el-form-item>
            </el-form>
          </div>

          <div v-else class="empty-hint">
            <el-icon :size="48" color="#475569"><Setting /></el-icon>
            <p>请从左侧选择一个团队进行配置</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加团队弹窗 -->
    <el-dialog
      v-model="addTeamDialogVisible"
      title="添加团队配置"
      width="420px"
      :close-on-click-modal="false"
    >
      <el-form @submit.prevent>
        <el-form-item label="团队ID">
          <el-input
            v-model="newTeamId"
            placeholder="输入团队唯一标识，例如 trade-team"
            clearable
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addTeamDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!newTeamId.trim()" @click="addTeam">
          确认添加
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Check, RefreshLeft, Setting, Loading, Delete } from '@element-plus/icons-vue'
import api from '@/api'

// ── 状态 ──
const selectedTeam = ref('')
const teamList = ref([])
const teamPrefs = ref({})
const availableModels = ref([])
const loadingTeams = ref(false)
const prefsLoaded = ref(false)
const saving = ref(false)
const addTeamDialogVisible = ref(false)
const newTeamId = ref('')
const tenantTeams = ref([])
const customTeams = ref([])

const form = ref({
  planning_model: '',
  code_generation_model: '',
  evaluation_model: '',
  agent_model: '',
  fast_chat_model: '',
  data_generation_model: '',
  rag_query_model: '',
  fallback_model: '',
})

// ── 字段定义 ──
const modelFields = [
  { key: 'planning_model', label: '规划模型 (Planning)', cap: '任务分解、用例生成规划' },
  { key: 'code_generation_model', label: '代码生成模型', cap: '测试脚本、自动化代码' },
  { key: 'evaluation_model', label: '评测模型 (Evaluation)', cap: '问答评测、结果打分' },
  { key: 'agent_model', label: 'Agent 模型', cap: '工具调用、多步推理' },
  { key: 'fast_chat_model', label: '快速对话模型', cap: '日常问答、快速响应' },
  { key: 'data_generation_model', label: '数据生成模型', cap: '测试数据、Mock 数据' },
  { key: 'rag_query_model', label: 'RAG 检索模型', cap: '知识库检索 & 增强生成' },
  { key: 'fallback_model', label: '兜底模型 (Fallback)', cap: '主模型不可用时的降级方案' },
]

// ── 计算属性 ──
const activeOverrides = computed(() => {
  return modelFields
    .filter(f => form.value[f.key] && form.value[f.key].length > 0)
    .map(f => ({ key: f.key, label: f.label.split(' ')[0], value: form.value[f.key] }))
})

// ── 方法 ──
async function fetchTeams() {
  try {
    const res = await api.get('/agent/tenants/', { skipErrorHandler: true })
    const tenants = res.results || res.tenants || res || []
    const teams = [...new Set(tenants.map(t => t.team).filter(Boolean))]
    tenantTeams.value = teams.sort()
  } catch (e) {
    tenantTeams.value = []
  }
  updateTeamList()
}

function updateTeamList() {
  teamList.value = [...new Set([...tenantTeams.value, ...customTeams.value])].sort()
}

async function fetchModels() {
  try {
    const res = await api.get('/llm/models', { skipErrorHandler: true })
    const models = res.models || []
    if (models.length > 0) {
      availableModels.value = models.sort((a, b) => (b.priority || 0) - (a.priority || 0))
    } else {
      throw new Error('empty')
    }
  } catch (e) {
    availableModels.value = []
  }
}

async function loadAllTeamPrefs() {
  const prefs = {}
  for (const team of teamList.value) {
    try {
      const res = await api.get(`/llm/team/${encodeURIComponent(team)}/model-prefs`, { skipErrorHandler: true })
      prefs[team] = res.data?.prefs || {}
    } catch (e) {
      prefs[team] = {}
    }
  }
  teamPrefs.value = prefs
}

function selectTeam(team) {
  selectedTeam.value = team
  const prefs = teamPrefs.value[team] || {}
  modelFields.forEach(f => { form.value[f.key] = prefs[f.key] || '' })
  prefsLoaded.value = true
}

function getTeamOverrideCount(team) {
  const prefs = teamPrefs.value[team] || {}
  return modelFields.filter(f => prefs[f.key] && prefs[f.key].length > 0).length
}

function showAddTeamDialog() {
  newTeamId.value = ''
  addTeamDialogVisible.value = true
}

async function addTeam() {
  const id = newTeamId.value.trim()
  if (!id) return
  if (teamList.value.includes(id)) {
    ElMessage.warning('该团队已存在')
    addTeamDialogVisible.value = false
    selectTeam(id)
    return
  }
  customTeams.value = [...customTeams.value, id]
  updateTeamList()
  teamPrefs.value[id] = {}
  addTeamDialogVisible.value = false
  selectTeam(id)
  ElMessage.success(`已添加团队 ${id}，配置后请保存`)
}

function isCustomTeam(team) {
  return customTeams.value.includes(team)
}

async function deleteTeam(team) {
  try {
    await ElMessageBox.confirm(
      `确定删除团队「${team}」的模型偏好配置？`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch (e) {
    return
  }

  try {
    await api.delete(`/llm/team/${encodeURIComponent(team)}/model-prefs`, { skipErrorHandler: true })
  } catch (e) {
    // 忽略后端已不存在的情况
  }

  customTeams.value = customTeams.value.filter(t => t !== team)
  updateTeamList()
  delete teamPrefs.value[team]

  if (selectedTeam.value === team) {
    selectedTeam.value = ''
    prefsLoaded.value = false
    modelFields.forEach(f => { form.value[f.key] = '' })
  }

  ElMessage.success(`团队「${team}」已删除`)
}

async function savePrefs() {
  if (!selectedTeam.value) return
  saving.value = true
  try {
    const payload = {}
    modelFields.forEach(f => { payload[f.key] = form.value[f.key] || '' })
    const res = await api.put(
      `/llm/team/${encodeURIComponent(selectedTeam.value)}/model-prefs`,
      { config: payload },
      { skipErrorHandler: true }
    )
    teamPrefs.value[selectedTeam.value] = res?.prefs || payload
    ElMessage.success(`团队「${selectedTeam.value}」配置已保存！偏好即时生效`)
  } catch (e) {
    const detail = e.response?.data?.detail || e.response?.data?.error || e.message
    ElMessage.error(`保存失败: ${typeof detail === 'object' ? JSON.stringify(detail) : detail}`)
  } finally {
    saving.value = false
  }
}

async function resetPrefs() {
  try {
    await ElMessageBox.confirm(
      `将清除团队「${selectedTeam.value}」的所有模型偏好，恢复为全局默认配置。`,
      '确认恢复默认',
      { type: 'warning', confirmButtonText: '确认恢复', cancelButtonText: '取消' }
    )
    saving.value = true
    await api.delete(`/llm/team/${encodeURIComponent(selectedTeam.value)}/model-prefs`, { skipErrorHandler: true })
    teamPrefs.value[selectedTeam.value] = {}
    modelFields.forEach(f => { form.value[f.key] = '' })
    prefsLoaded.value = true
    ElMessage.success(`团队「${selectedTeam.value}」已恢复为全局默认配置`)
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      const detail = e.response?.data?.detail || e.response?.data?.error || e.message
      ElMessage.error(`恢复失败: ${typeof detail === 'object' ? JSON.stringify(detail) : detail}`)
    }
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  loadingTeams.value = true
  await fetchTeams()
  await fetchModels()
  await loadAllTeamPrefs()
  if (teamList.value.includes('global')) {
    selectTeam('global')
  } else if (teamList.value.length > 0) {
    selectTeam(teamList.value[0])
  }
  loadingTeams.value = false
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
  overflow: auto;
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

.main-panel {
  position: relative;
  z-index: 1;
  background: rgba(30, 41, 59, 0.9);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 16px;
  padding: 20px 24px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  box-shadow: 0 2px 8px rgba(2, 8, 20, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.main-panel::before {
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
  font-size: 15px;
  font-weight: 600;
  color: #f8fafc;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-hint {
  font-size: 12px;
  font-weight: 400;
  color: #94a3b8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* 两列布局 */
.settings-layout {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* 左侧团队列表 */
.team-list-panel {
  width: 260px;
  min-width: 260px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(64, 158, 255, 0.2);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.team-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.15);
  font-size: 14px;
  font-weight: 600;
  color: #e2e8f0;
}

.team-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #64748b;
  font-size: 13px;
}

.team-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.team-item {
  padding: 12px 14px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid transparent;
  margin-bottom: 6px;
}

.team-item:hover {
  background: rgba(64, 158, 255, 0.1);
  border-color: rgba(64, 158, 255, 0.25);
}

.team-item.active {
  background: rgba(64, 158, 255, 0.18);
  border-color: rgba(64, 158, 255, 0.5);
}

.team-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.team-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.team-name {
  font-size: 14px;
  color: #e2e8f0;
  word-break: break-all;
  font-weight: 500;
}

.team-overrides {
  font-size: 12px;
}

.no-override {
  color: #64748b;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.empty-team-list {
  padding: 40px 16px;
  text-align: center;
  color: #64748b;
  font-size: 13px;
}

/* 右侧表单 */
.form-panel {
  flex: 1;
  min-width: 0;
  background: rgba(15, 23, 42, 0.4);
  border: 1px solid rgba(64, 158, 255, 0.2);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.form-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.15);
  background: rgba(15, 23, 42, 0.4);
}

.current-team .label {
  color: #94a3b8;
  font-size: 13px;
}

.current-team strong {
  color: #f8fafc;
  font-size: 15px;
  font-weight: 600;
}

.form-actions {
  display: flex;
  gap: 10px;
}

.prefs-form-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.prefs-form {
  padding: 0;
}

.field-cap {
  margin-left: 12px;
  font-size: 12px;
  color: #64748b;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* 空状态 & 加载 */
.empty-hint, .loading-hint {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #64748b;
  font-size: 14px;
}

/* Element 覆盖 */
:deep(.el-select) {
  --el-select-border-color-hover: rgba(64, 158, 255, 0.5);
  --el-select-input-focus-border-color: #409eff;
}

:deep(.el-input__wrapper) {
  background: rgba(15, 23, 42, 0.8);
  border-color: rgba(64, 158, 255, 0.3);
  box-shadow: none;
}

:deep(.el-input__inner) {
  color: #e2e8f0;
}

:deep(.el-form-item__label) {
  color: #cbd5e1;
  font-size: 13px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

:deep(.el-input__wrapper:hover) {
  border-color: rgba(64, 158, 255, 0.5);
}

:deep(.el-select__popper) {
  background: #1e293b;
  border: 1px solid rgba(64, 158, 255, 0.3);
}

:deep(.el-select-dropdown__item) {
  color: #e2e8f0;
}

:deep(.el-select-dropdown__item.hover) {
  background: rgba(64, 158, 255, 0.15);
}

:deep(.el-select-dropdown__item.selected) {
  color: #7dd3fc;
}

:deep(.el-dialog) {
  background: #1e293b;
  border: 1px solid rgba(64, 158, 255, 0.3);
}

:deep(.el-dialog__title) {
  color: #f1f5f9;
}

:deep(.el-dialog__body label) {
  color: #cbd5e1;
}
</style>
