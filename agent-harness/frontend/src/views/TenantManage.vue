<template>
  <div class="harness-page tenant-manage">
    <div class="main-panel">
      <div class="panel-title">
        <span>业务接入方</span>
        <el-button type="primary" size="small" @click="resetForm(); dialogVisible = true">+ 新增接入方</el-button>
      </div>
      <el-table :data="tenants" size="small" height="100%" row-key="id" empty-text="暂无接入方，点击右上角「新增接入方」开始使用">
        <el-table-column prop="name" label="业务名称" width="140">
          <template #default="{ row }"><span class="t-name">{{ row.name }}</span></template>
        </el-table-column>
        <el-table-column prop="team" label="所属团队" width="110" />
        <el-table-column prop="api_key" label="API Key" width="170">
          <template #default="{ row }">
            <el-input :model-value="row.api_key" size="small" readonly class="key-input">
              <template #suffix>
                <el-button link size="small" @click="copyKey(row.api_key)">复制</el-button>
              </template>
            </el-input>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <span :class="'status-dot ' + row.status">{{ row.status === 'active' ? '启用' : '已禁用' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="限流" width="130">
          <template #default="{ row }">
            <span class="rate-limit">QPS: {{ row.rate_limit?.qps }} | 日上限: {{ row.rate_limit?.daily_cap }}</span>
          </template>
        </el-table-column>
        <el-table-column label="工具白名单" min-width="280">
          <template #default="{ row }">
            <el-tag v-for="t in (row.tools_whitelist || [])" :key="t" size="small" class="tool-tag">{{ t }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="调用统计" min-width="200">
          <template #default="{ row }">
            <span class="call-stats">
              总计{{ row.stats?.total_calls?.toLocaleString() }}
              | 今日{{ row.stats?.today_calls }}
              | 均{{ row.stats?.avg_latency_ms }}ms
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="editTenant(row)">编辑</el-button>
            <el-button link type="warning" size="small" @click="resetKey(row)">重置Key</el-button>
            <el-button link type="danger" size="small" @click="disableTenant(row)">
              {{ row.status === 'active' ? '禁用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="editingTenant ? '编辑接入方' : '新增接入方'" width="550px" top="10vh" :close-on-click-modal="false">
      <el-form label-width="100px">
        <el-form-item label="业务名称" required>
          <el-input v-model="form.name" placeholder="如：电商平台核心业务" />
        </el-form-item>
        <el-form-item label="所属团队" required>
          <el-input v-model="form.team" placeholder="如：电商事业部" />
        </el-form-item>
        <el-form-item label="QPS 限制">
          <el-input-number v-model="form.qps" :min="1" :max="1000" />
        </el-form-item>
        <el-form-item label="日调用上限">
          <el-input-number v-model="form.dailyCap" :min="100" :max="1000000" :step="1000" />
        </el-form-item>
        <el-form-item label="工具白名单">
          <el-checkbox-group v-model="form.whitelist">
            <el-checkbox
              v-for="tool in availableTools"
              :key="tool.value"
              :label="tool.value"
              :value="tool.value"
            >
              {{ tool.label }}
            </el-checkbox>
          </el-checkbox-group>
          <div v-if="!availableTools.length" style="color:#e2e8f0;font-size:12px">
            工具列表加载中...
          </div>
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="form.contact" placeholder="邮箱" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveTenant">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

const tenants = ref([])
const availableTools = ref([])
const dialogVisible = ref(false)
const saving = ref(false)
const editingTenant = ref(null)
const showAdd = ref(false)

const form = reactive({ name: '', team: '', qps: 50, dailyCap: 5000, whitelist: [], contact: '' })

async function fetchTenants() {
  try {
    const res = await api.get('/agent/tenants/')
    tenants.value = res.results || res.tenants || res || []
  } catch (e) {
    ElMessage.error('获取接入方列表失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function fetchAvailableTools() {
  try {
    const res = await api.get('/mcp/tools/')
    const tools = res.results || res.tools || []
    availableTools.value = tools.map(t => ({
      label: t.name,
      value: t.name,
      category: t.category,
    }))
  } catch (e) {
    // 工具列表不可用时不影响主流程
    availableTools.value = []
  }
}

function resetForm() {
  form.name = ''; form.team = ''; form.qps = 50; form.dailyCap = 5000
  form.whitelist = []; form.contact = ''
  editingTenant.value = null
}

function editTenant(row) {
  editingTenant.value = row
  form.name = row.name
  form.team = row.team
  form.qps = row.rate_limit?.qps || 50
  form.dailyCap = row.rate_limit?.daily_cap || 5000
  form.whitelist = [...(row.tools_whitelist || [])]
  form.contact = row.contact || ''
  dialogVisible.value = true
}

async function saveTenant() {
  if (!form.name || !form.team) { ElMessage.warning('请填写必填项'); return }
  saving.value = true
  try {
    const payload = {
      name: form.name, team: form.team,
      rate_limit: { qps: form.qps, daily_cap: form.dailyCap },
      tools_whitelist: form.whitelist,
      contact: form.contact,
    }
    if (editingTenant.value) {
      await api.put(`/agent/tenants/${editingTenant.value.id}/`, payload)
    } else {
      await api.post('/agent/tenants/', payload)
    }
    ElMessage.success(editingTenant.value ? '更新成功' : '创建成功')
    dialogVisible.value = false
    fetchTenants()
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

function resetKey(row) {
  ElMessageBox.confirm('重置密钥后旧 Key 将立即失效，确认？', '重置密钥', { type: 'warning' })
    .then(async () => {
      try {
        await api.post(`/agent/tenants/${row.id}/reset-key/`)
        ElMessage.success('密钥已重置')
        fetchTenants()
      } catch (e) {
        ElMessage.error('重置失败: ' + (e.response?.data?.detail || e.message))
      }
    })
    .catch(() => {})
}

function disableTenant(row) {
  const action = row.status === 'active' ? '禁用' : '启用'
  ElMessageBox.confirm(`确认${action}接入方 "${row.name}"？`, '确认', { type: 'warning' })
    .then(async () => {
      try {
        if (row.status === 'active') {
          await api.delete(`/agent/tenants/${row.id}/`)
        } else {
          await api.put(`/agent/tenants/${row.id}/`, { status: 'active' })
        }
        ElMessage.success(`${action}成功`)
        fetchTenants()
      } catch (e) {
        ElMessage.error(`${action}失败: ` + (e.response?.data?.detail || e.message))
      }
    })
    .catch(() => {})
}

function copyKey(key) {
  navigator.clipboard.writeText(key).then(() => ElMessage.success('已复制'))
    .catch(() => ElMessage.info(key))
}

onMounted(() => { fetchTenants(); fetchAvailableTools() })
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

.main-panel,
.harness-page > * {
  position: relative;
  z-index: 1;
}

.main-panel {
  background: rgba(30, 41, 59, 0.9);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 16px;
  padding: 12px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 2px 8px rgba(2, 8, 20, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.08);
  
  transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s;
  contain: layout paint;
}

.main-panel:hover {
  border-color: rgba(64, 158, 255, 0.45);
  box-shadow: 0 12px 40px rgba(2, 132, 199, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.1);
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
  font-size: 14px; font-weight: 600; color: #f8fafc;
  margin-bottom: 8px;
  display: flex; align-items: center; justify-content: space-between;
}

.t-name { color: #7dd3fc; font-weight: 500; }

.key-input { width: 180px; }

.rate-limit { font-size: 12px; color: #e2e8f0; }

.tool-tag { margin-right: 6px; margin-bottom: 4px; }

.call-stats { font-size: 12px; color: #e2e8f0; }

.status-dot { color: #f1f5f9; }
.status-dot::before {
  content: ''; display: inline-block;
  width: 7px; height: 7px; border-radius: 50%; margin-right: 6px;
}
.status-dot.active::before { background: #00ff88; box-shadow: 0 0 6px #00ff88; }
.status-dot.disabled::before { background: #f87171; }

/* 表格 */
:deep(.el-table) {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: rgba(30, 41, 59, 0.95);
  --el-table-row-hover-bg-color: rgba(64, 158, 255, 0.12);
  --el-table-border-color: rgba(64, 158, 255, 0.15);
  --el-table-text-color: #f1f5f9;
  --el-table-header-text-color: #cbd5e1;
}
:deep(.el-table th) { border-bottom: 1px solid rgba(64, 158, 255, 0.15); padding: 10px 8px; }
:deep(.el-table td) { border-bottom: 1px solid rgba(64, 158, 255, 0.08); padding: 8px; }

/* 对话框 */
:deep(.el-dialog) { background: rgba(22, 32, 50, 0.98); border: 1px solid rgba(64, 158, 255, 0.3); border-radius: 12px; }
:deep(.el-dialog__title) { color: #f8fafc; }
:deep(.el-dialog__body) { color: #e2e8f0; }
:deep(.el-input__inner), :deep(.el-textarea__inner) {
  background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(64, 158, 255, 0.3); color: #e2e8f0;
}
:deep(.el-form-item__label) { color: #cbd5e1; }
:deep(.el-checkbox__label) { color: #e2e8f0; }
</style>
