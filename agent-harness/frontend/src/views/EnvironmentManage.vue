<template>
  <div class="harness-page env-manage">
    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-card">
        <span class="stat-value">{{ envSummary.total }}</span>
        <span class="stat-label">环境总数</span>
      </div>
      <div class="stat-card">
        <span class="stat-value running">{{ envSummary.active }}</span>
        <span class="stat-label">启用中</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ envSummary.test }}</span>
        <span class="stat-label">测试环境</span>
      </div>
      <div class="stat-card">
        <span class="stat-value terminated">{{ envSummary.prod }}</span>
        <span class="stat-label">生产环境</span>
      </div>
    </div>

    <!-- 环境列表 -->
    <div class="main-panel">
      <div class="panel-title">
        <span>测试环境</span>
        <div class="panel-actions">
          <el-select v-model="typeFilter" placeholder="类型筛选" clearable size="small" style="width:130px">
            <el-option label="全部" value="" />
            <el-option label="测试" value="test" />
            <el-option label="预发" value="staging" />
            <el-option label="生产" value="prod" />
          </el-select>
          <el-button type="primary" size="small" @click="openCreate">+ 新建环境</el-button>
        </div>
      </div>

      <el-table
        :data="filteredEnvs"
        class="grid-table"
        size="small"
        height="100%"
        row-key="id"
        border
        empty-text="暂无环境，点击右上角「新建环境」添加"
      >
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="env_type" label="类型" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="typeStyle(row.env_type)">{{ typeCN[row.env_type] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="base_url" label="Base URL" min-width="200">
          <template #default="{ row }">
            <span class="env-url">{{ row.base_url || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="owner" label="负责人" width="110">
          <template #default="{ row }">{{ row.owner || '-' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <span :class="'status-dot ' + (row.status === 'active' ? 'running' : 'terminated')">
              {{ row.status === 'active' ? '启用' : '停用' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" text type="danger" @click="removeEnv(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 创建 / 编辑弹窗 -->
    <el-dialog v-model="showDialog" :title="isEdit ? '编辑环境' : '新建环境'" width="480px">
      <el-form label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如：预发环境 / 生产环境" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.env_type" style="width:100%">
            <el-option label="测试" value="test" />
            <el-option label="预发" value="staging" />
            <el-option label="生产" value="prod" />
          </el-select>
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="form.base_url" placeholder="https://api.example.com" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="form.owner" placeholder="团队 / 负责人" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="环境说明" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="statusActive" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEnv">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { environmentAPI } from '@/api'

const typeCN = { test: '测试', staging: '预发', prod: '生产' }

const envs = ref([])
const typeFilter = ref('')
const envSummary = reactive({ total: 0, active: 0, test: 0, prod: 0 })

const filteredEnvs = computed(() => {
  if (!typeFilter.value) return envs.value
  return envs.value.filter(e => e.env_type === typeFilter.value)
})

const showDialog = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const editingId = ref('')
const statusActive = ref(true)
const form = reactive({ name: '', env_type: 'test', base_url: '', owner: '', description: '' })

function typeStyle(t) { return { test: '', staging: 'warning', prod: 'danger' }[t] || '' }

async function fetchEnvs() {
  try {
    const res = await environmentAPI.list()
    const data = res.data.data || res.data
    envs.value = data.items || data || []
    envSummary.total = envs.value.length
    envSummary.active = envs.value.filter(e => e.status === 'active').length
    envSummary.test = envs.value.filter(e => e.env_type === 'test').length
    envSummary.prod = envs.value.filter(e => e.env_type === 'prod').length
  } catch (e) {
    ElMessage.error('获取环境列表失败: ' + e.message)
  }
}

function openCreate() {
  isEdit.value = false
  editingId.value = ''
  Object.assign(form, { name: '', env_type: 'test', base_url: '', owner: '', description: '' })
  statusActive.value = true
  showDialog.value = true
}

function openEdit(row) {
  isEdit.value = true
  editingId.value = row.id
  Object.assign(form, {
    name: row.name, env_type: row.env_type, base_url: row.base_url,
    owner: row.owner, description: row.description,
  })
  statusActive.value = row.status === 'active'
  showDialog.value = true
}

async function saveEnv() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写环境名称')
    return
  }
  saving.value = true
  const payload = { ...form, status: statusActive.value ? 'active' : 'inactive' }
  try {
    if (isEdit.value) {
      await environmentAPI.update(editingId.value, payload)
      ElMessage.success('环境已更新')
    } else {
      await environmentAPI.create(payload)
      ElMessage.success('环境已创建')
    }
    showDialog.value = false
    await fetchEnvs()
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

async function removeEnv(row) {
  try {
    await ElMessageBox.confirm(`确认删除环境「${row.name}」？`, '提示', { type: 'warning' })
  } catch { return }
  try {
    await environmentAPI.delete(row.id)
    ElMessage.success('已删除')
    await fetchEnvs()
  } catch (e) {
    ElMessage.error('删除失败: ' + e.message)
  }
}

onMounted(fetchEnvs)
</script>

<style scoped>
.env-manage {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow: hidden;
}
.stats-row { display: flex; gap: 14px; flex-shrink: 0; }
.stat-card {
  flex: 1; background: rgba(12, 24, 46, 0.6); border: 1px solid rgba(80, 140, 210, 0.16);
  border-radius: 14px; padding: 14px 18px; display: flex; flex-direction: column; gap: 4px;
}
.stat-value { font-size: 26px; font-weight: 700; color: #e6eefc; }
.stat-value.running { color: #5ad19a; }
.stat-value.terminated { color: #f08a8a; }
.stat-label { font-size: 12px; color: #8fa6c4; }
.main-panel {
  flex: 1; min-height: 0; background: rgba(12, 24, 46, 0.6);
  border: 1px solid rgba(80, 140, 210, 0.16); border-radius: 14px; padding: 16px 18px;
  display: flex; flex-direction: column;
}
.panel-title {
  display: flex; justify-content: space-between; align-items: center; gap: 10px;
  font-size: 14px; font-weight: 600; color: #c9d4e3; margin-bottom: 12px;
}
.env-url { font-family: monospace; font-size: 12px; color: #9fc0f0; word-break: break-all; }
.status-dot { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; }
.status-dot::before { content: ''; width: 7px; height: 7px; border-radius: 50%; background: #5ad19a; }
.status-dot.terminated::before { background: #f08a8a; }
.status-dot.running::before { background: #5ad19a; }
.grid-table { flex: 1; min-height: 0; background: transparent; }
</style>
