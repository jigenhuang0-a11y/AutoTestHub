<template>
  <div class="perf-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>性能测试用例</span>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            新建性能用例
          </el-button>
        </div>
      </template>

      <!-- 搜索栏 -->
      <el-form :inline="true" :model="searchForm" class="search-bar">
        <el-form-item label="关键词">
          <el-input v-model="searchForm.search" placeholder="名称/URL" clearable @clear="loadList" @keyup.enter="loadList" style="width: 220px" />
        </el-form-item>
        <el-form-item label="方法">
          <el-select v-model="searchForm.method" placeholder="全部" clearable @change="loadList" style="width: 120px">
            <el-option label="GET" value="GET" />
            <el-option label="POST" value="POST" />
            <el-option label="PUT" value="PUT" />
            <el-option label="DELETE" value="DELETE" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable @change="loadList" style="width: 110px">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadList">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 表格 -->
      <div class="table-wrapper">
        <el-table
          :data="testCases"
          border
          stripe
          :header-cell-style="{background:'#f5f7fa',color:'#606266',fontWeight:600}"
          style="width: 100%"
        >
          <el-table-column prop="id" label="ID" width="55" align="center" />
          <el-table-column prop="name" label="用例名称" min-width="120" show-overflow-tooltip />
          <el-table-column label="请求" min-width="200">

            <template #default="{ row }">
              <template v-if="row.test_type === 'mixed' && row.mixed_scenarios?.length">
                <div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap">
                  <el-tag size="small" type="info">混合{{ row.mixed_scenarios.length }}场景</el-tag>
                  <span v-for="(s, i) in row.mixed_scenarios.slice(0, 2)" :key="i" style="font-size:11px;color:#6366f1">
                    {{ s.weight }}%
                  </span>
                  <span v-if="row.mixed_scenarios.length > 2" style="font-size:11px;color:#909399">...</span>
                </div>
              </template>
              <template v-else>
                <div style="display:flex;align-items:center;gap:6px">
                  <el-tag size="small" :type="methodTagType(row.method)">{{ row.method }}</el-tag>
                  <span style="color:#606266;font-size:12px" class="url-ellipsis">{{ row.target_url }}</span>
                </div>
              </template>
            </template>
          </el-table-column>
          <el-table-column label="压测参数" min-width="160" align="center">

            <template #default="{ row }">
              <div style="font-size:12px;display:flex;align-items:center;justify-content:center;gap:4px">
                <el-tag v-if="row.test_type === 'ramp'" size="small" type="warning" effect="plain">梯度</el-tag>
                <el-tag v-else-if="row.test_type === 'mixed'" size="small" type="success" effect="plain">混合</el-tag>
                <el-tag v-else size="small" type="primary" effect="plain">基准</el-tag>
                <span>{{ row.users }}并发/{{ row.duration }}s</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="断言阈值" min-width="200">

            <template #default="{ row }">
              <div style="font-size:11px;color:#909399;white-space:nowrap">
                均值&lt;{{ row.max_avg_response_time }}ms | P95&lt;{{ row.max_p95_response_time }}ms | 失败率&lt;{{ (row.max_failure_rate * 100).toFixed(0) }}%
              </div>
            </template>
          </el-table-column>
          <el-table-column label="最近执行" width="90" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.last_execution_status" size="small" :type="statusTagType(row.last_execution_status.status)">
                {{ row.last_execution_status.status_display }}
              </el-tag>
              <span v-else style="color:#c0c4cc;font-size:12px">未执行</span>
            </template>
          </el-table-column>
          <el-table-column prop="status_display" label="状态" width="70" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.status === 'active' ? 'success' : 'info'">
                {{ row.status_display }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="320" align="center">
            <template #default="{ row }">
              <el-button size="small" type="success" @click="executeCase(row)" :loading="executingId === row.id || row.last_execution_status?.status === 'running'" :disabled="row.last_execution_status?.status === 'running'">
                <el-icon><VideoPlay /></el-icon> 执行
              </el-button>
              <el-button v-if="row.last_execution_status" size="small" @click="goDetail(row.last_execution_status.id)">
                <el-icon><View /></el-icon> 查看
              </el-button>
              <el-button size="small" type="primary" @click="showEditDialog(row)">
                <el-icon><Edit /></el-icon> 编辑
              </el-button>
              <el-button size="small" type="danger" @click="deleteCase(row)">
                <el-icon><Delete /></el-icon> 删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="testCases.length === 0 && !loading" style="text-align:center;padding:60px 0">
        <el-empty description="暂无性能测试用例">
          <el-button type="primary" @click="showCreateDialog">创建第一个性能用例</el-button>
        </el-empty>
      </div>

      <!-- 分页 -->
      <el-pagination
        v-if="total > 0"
        v-model:current-page="pagination.page"
        :page-size="pagination.pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadList"
        style="margin-top:20px;justify-content:flex-end"
      />
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑性能用例' : '新建性能用例'"
      width="900px"
      :close-on-click-modal="false"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="140px">
        <el-form-item label="用例名称" prop="name">
          <el-input v-model="formData.name" placeholder="例如：登录接口压测" />
        </el-form-item>
        <!-- 单接口配置（非混合模式） -->
        <template v-if="formData.test_type !== 'mixed'">
          <el-form-item label="目标URL" prop="target_url">
            <el-input v-model="formData.target_url" placeholder="https://api.example.com/v1/login" />
          </el-form-item>
          <el-form-item label="请求方法" prop="method">
            <el-select v-model="formData.method" style="width:140px">
              <el-option label="GET" value="GET" />
              <el-option label="POST" value="POST" />
              <el-option label="PUT" value="PUT" />
              <el-option label="DELETE" value="DELETE" />
            </el-select>
          </el-form-item>
          <el-form-item label="请求头 (JSON)">
            <el-input v-model="formData.headersText" type="textarea" :rows="3" placeholder='{"Content-Type": "application/json"}' />
          </el-form-item>
          <el-form-item label="请求体 (JSON)" v-if="formData.method !== 'GET'">
            <el-input v-model="formData.bodyText" type="textarea" :rows="4" placeholder='{"username": "test", "password": "123456"}' />
          </el-form-item>
        </template>

        <!-- 混合场景配置 -->
        <template v-if="formData.test_type === 'mixed'">
          <el-divider content-position="left">接口场景配置（按权重配比并发）</el-divider>
          <div v-for="(sc, idx) in formData.mixedScenarios" :key="idx" style="background:#f0f9ff;padding:14px 16px;border-radius:8px;margin-bottom:12px;border:1px solid #bae6fd;position:relative">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
              <span style="font-weight:600;color:#0369a1">场景 {{ idx + 1 }}</span>
              <el-button v-if="formData.mixedScenarios.length > 1" size="small" type="danger" plain @click="removeScenario(idx)" :icon="Delete">删除</el-button>
            </div>
            <el-row :gutter="10">
              <el-col :span="14">
                <el-input v-model="sc.url" placeholder="https://api.example.com/endpoint" size="small">
                  <template #prepend>
                    <el-select v-model="sc.method" style="width:90px" size="small">
                      <el-option label="GET" value="GET" />
                      <el-option label="POST" value="POST" />
                      <el-option label="PUT" value="PUT" />
                      <el-option label="DELETE" value="DELETE" />
                    </el-select>
                  </template>
                </el-input>
              </el-col>
              <el-col :span="4">
                <el-input-number v-model="sc.weight" :min="1" :max="100" size="small" style="width:100%" controls-position="right" />
              </el-col>
              <el-col :span="2" style="display:flex;align-items:center;justify-content:center">
                <span style="color:#6366f1;font-weight:600;font-size:13px">
                  {{ mixedWeightPercent(idx, formData.mixedScenarios) }}%
                </span>
              </el-col>
            </el-row>
            <el-row :gutter="10" style="margin-top:8px">
              <el-col :span="12">
                <el-input v-model="sc.headersText" type="textarea" :rows="2" size="small" placeholder='{"Content-Type":"application/json"}' />
              </el-col>
              <el-col :span="12" v-if="sc.method !== 'GET'">
                <el-input v-model="sc.bodyText" type="textarea" :rows="2" size="small" placeholder='{"key":"value"}' />
              </el-col>
            </el-row>
          </div>
          <el-button type="primary" plain size="small" @click="addScenario" style="margin-bottom:12px">
            <el-icon><Plus /></el-icon> 添加场景
          </el-button>
          <div style="font-size:12px;color:#909399;margin-bottom:12px;padding-left:4px">
            💡 权重决定各接口在总并发中的占比。例如：场景A权重70 + 场景B权重30 → A占70%并发、B占30%并发
          </div>
        </template>

        <el-divider content-position="left">压测参数</el-divider>

        <el-form-item label="并发模型" prop="test_type">
          <el-select v-model="formData.test_type" style="width:240px" @change="onTestTypeChange">
            <el-option label="固定并发（基准测试）" value="baseline" />
            <el-option label="阶梯递增（负载测试）" value="ramp" />
            <el-option label="混合场景（权重配比）" value="mixed" />
            <el-option label="尖峰测试（即将推出）" value="spike" disabled />
            <el-option label="压力测试（即将推出）" value="stress" disabled />
          </el-select>
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="并发用户数" prop="users" label-width="110px">
              <el-input-number v-model="formData.users" :min="1" :max="5000" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="启动速率/s" prop="spawn_rate" label-width="110px">
              <el-input-number v-model="formData.spawn_rate" :min="1" :max="500" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="持续时间(s)" prop="duration" label-width="110px">
              <el-input-number v-model="formData.duration" :min="5" :max="3600" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <div v-if="formData.test_type === 'ramp'" style="background:#f5f7fa;padding:16px;border-radius:8px;margin-bottom:18px">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="每步增加用户" label-width="120px">
                <el-input-number v-model="formData.ramp_step_users" :min="1" :max="500" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="每步持续(s)" label-width="120px">
                <el-input-number v-model="formData.ramp_step_duration" :min="10" :max="600" style="width:100%" />
              </el-form-item>
            </el-col>
          </el-row>
          <div style="font-size:12px;color:#909399;padding-left:12px">
            💡 从 1 并发开始，每 {{ formData.ramp_step_duration }}s 增加 {{ formData.ramp_step_users }} 个并发，直到 {{ formData.users }} 并发
          </div>
        </div>

        <el-divider content-position="left">断言阈值</el-divider>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="最大平均响应" prop="max_avg_response_time" label-width="120px">
              <el-input-number v-model="formData.max_avg_response_time" :min="10" :max="60000" style="width:100%" />
              <span style="margin-left:4px;font-size:12px;color:#909399">ms</span>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="最大P95" prop="max_p95_response_time" label-width="100px">
              <el-input-number v-model="formData.max_p95_response_time" :min="10" :max="60000" style="width:100%" />
              <span style="margin-left:4px;font-size:12px;color:#909399">ms</span>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="最大失败率" prop="max_failure_rate" label-width="110px">
              <el-input-number v-model="formData.max_failure_rate" :min="0" :max="1" :step="0.01" :precision="2" style="width:100%" />
              <span style="margin-left:4px;font-size:12px;color:#909399">(0~1)</span>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="状态">
          <el-switch v-model="formData.statusBool" active-text="启用" inactive-text="停用" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="formData.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">
          {{ isEdit ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, VideoPlay, View } from '@element-plus/icons-vue'
import { perfAPI } from '@/api'
import { formatDate, showSuccess } from '@/utils/helpers'

const router = useRouter()

// ---------- 列表 ----------
const loading = ref(false)
const testCases = ref([])
const total = ref(0)
const searchForm = reactive({ search: '', method: '', status: '' })
const pagination = reactive({ page: 1, pageSize: 10 })

const loadList = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      search: searchForm.search || undefined,
      method: searchForm.method || undefined,
      status: searchForm.status || undefined,
    }
    const res = await perfAPI.listTestCases(params)
    testCases.value = res.results || res
    total.value = res.count || res.length
  } catch (e) {
    console.error('Load perf cases error:', e)
  } finally {
    loading.value = false
  }
}

const resetSearch = () => {
  searchForm.search = ''
  searchForm.method = ''
  searchForm.status = ''
  pagination.page = 1
  loadList()
}



// 轮询刷新用例列表（仅当存在 running 状态时）
let pollTimer = null
const startPolling = () => {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    const hasRunning = testCases.value.some(tc => tc.last_execution_status?.status === 'running')
    if (!hasRunning) return
    await loadList()
  }, 3000)
}

onMounted(() => {
  loadList()
  startPolling()
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})

// ---------- 执行 ----------
const executingId = ref(null)

const executeCase = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要用 ${row.users} 个并发用户对 "${row.name}" 进行 ${row.duration} 秒压测吗？`,
      '确认执行',
      { confirmButtonText: '开始压测', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }

  executingId.value = row.id
  try {
    const res = await perfAPI.execute({ test_case_id: row.id })
    ElMessage.success(`压测已启动！执行ID: ${res.id}`)
    await loadList()
    // 留在列表页，自动轮询刷新状态
  } catch (e) {
    console.error('Execute error:', e)
  } finally {
    executingId.value = null
  }
}

const goDetail = (id) => {
  if (!id) {
    ElMessage.warning('暂无执行记录，请先执行测试')
    return
  }
  router.push(`/perf-execution/${id}`)
}

// ---------- CRUD ----------
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const currentId = ref(null)
const formRef = ref(null)

const initialForm = () => ({
  name: '',
  target_url: '',
  method: 'GET',
  headersText: '',
  bodyText: '',
  test_type: 'baseline',
  users: 10,
  spawn_rate: 1,
  duration: 60,
  ramp_step_users: 5,
  ramp_step_duration: 30,
  mixedScenarios: [
    { url: '', method: 'GET', headersText: '', bodyText: '', weight: 50 },
    { url: '', method: 'GET', headersText: '', bodyText: '', weight: 50 },
  ],
  max_avg_response_time: 1000,
  max_p95_response_time: 2000,
  max_failure_rate: 0.01,
  statusBool: true,
  description: '',
})

const formData = reactive(initialForm())

const formRules = {
  name: [{ required: true, message: '请输入用例名称', trigger: 'blur' }],
  target_url: [
    {
      validator: (rule, value, callback) => {
        if (formData.test_type !== 'mixed') {
          if (!value) return callback(new Error('请输入目标URL'))
          if (!/^https?:\/\/.+/.test(value)) return callback(new Error('URL 需要以 http:// 或 https:// 开头'))
        }
        callback()
      },
      trigger: 'blur'
    }
  ],
  method: [
    {
      validator: (rule, value, callback) => {
        if (formData.test_type !== 'mixed' && !value) return callback(new Error('请选择请求方法'))
        callback()
      },
      trigger: 'change'
    }
  ],
  users: [{ required: true, message: '请输入并发用户数', trigger: 'blur' }],
  duration: [{ required: true, message: '请输入持续时间', trigger: 'blur' }],
}

const showCreateDialog = () => {
  isEdit.value = false
  currentId.value = null
  resetForm()
  dialogVisible.value = true
}

const showEditDialog = (row) => {
  isEdit.value = true
  currentId.value = row.id
  // 加载混合场景数据
  let mixedScenarios = initialForm().mixedScenarios
  if (row.mixed_scenarios && Array.isArray(row.mixed_scenarios) && row.mixed_scenarios.length > 0) {
    mixedScenarios = row.mixed_scenarios.map(s => ({
      url: s.url || '',
      method: s.method || 'GET',
      headersText: typeof s.headers === 'object' && s.headers ? JSON.stringify(s.headers, null, 2) : (s.headers || ''),
      bodyText: s.body ? (typeof s.body === 'object' ? JSON.stringify(s.body, null, 2) : s.body) : '',
      weight: s.weight || 0,
    }))
  }
  Object.assign(formData, {
    name: row.name,
    target_url: row.target_url,
    method: row.method,
    headersText: typeof row.headers === 'object' ? JSON.stringify(row.headers, null, 2) : (row.headers || ''),
    bodyText: row.body ? (typeof row.body === 'object' ? JSON.stringify(row.body, null, 2) : row.body) : '',
    test_type: row.test_type || 'baseline',
    users: row.users,
    spawn_rate: row.spawn_rate,
    duration: row.duration,
    ramp_step_users: row.ramp_step_users || 5,
    ramp_step_duration: row.ramp_step_duration || 30,
    mixedScenarios,
    max_avg_response_time: row.max_avg_response_time,
    max_p95_response_time: row.max_p95_response_time,
    max_failure_rate: row.max_failure_rate,
    statusBool: row.status === 'active',
    description: row.description || '',
  })
  dialogVisible.value = true
}

const resetForm = () => {
  Object.assign(formData, initialForm())
  if (formRef.value) formRef.value.resetFields()
}

const submitForm = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      let headers = {}
      let body = null

      if (formData.test_type !== 'mixed') {
        try {
          if (formData.headersText.trim()) headers = JSON.parse(formData.headersText)
        } catch { ElMessage.warning('请求头 JSON 格式不正确'); submitting.value = false; return }
        try {
          if (formData.method !== 'GET' && formData.bodyText.trim()) body = JSON.parse(formData.bodyText)
        } catch { ElMessage.warning('请求体 JSON 格式不正确'); submitting.value = false; return }
      }

      // 混合场景数据
      let mixed_scenarios = []
      if (formData.test_type === 'mixed') {
        for (let i = 0; i < formData.mixedScenarios.length; i++) {
          const sc = formData.mixedScenarios[i]
          if (!sc.url.trim()) {
            ElMessage.warning(`场景 ${i + 1} 的 URL 不能为空`); submitting.value = false; return
          }
          let scHeaders = {}
          let scBody = null
          try {
            if (sc.headersText?.trim()) scHeaders = JSON.parse(sc.headersText)
          } catch { ElMessage.warning(`场景 ${i + 1} 的请求头 JSON 格式不正确`); submitting.value = false; return }
          try {
            if (sc.method !== 'GET' && sc.bodyText?.trim()) scBody = JSON.parse(sc.bodyText)
          } catch { ElMessage.warning(`场景 ${i + 1} 的请求体 JSON 格式不正确`); submitting.value = false; return }
          mixed_scenarios.push({
            url: sc.url.trim(),
            method: sc.method,
            headers: scHeaders,
            body: scBody,
            weight: sc.weight,
          })
        }
        if (mixed_scenarios.length === 0) {
          ElMessage.warning('至少需要一个混合场景'); submitting.value = false; return
        }
        const totalW = mixed_scenarios.reduce((s, sc) => s + sc.weight, 0)
        if (totalW <= 0) {
          ElMessage.warning('混合场景权重总和必须大于0'); submitting.value = false; return
        }
      }

      const data = {
        name: formData.name,
        target_url: formData.test_type === 'mixed' ? (mixed_scenarios[0]?.url || '') : formData.target_url,
        method: formData.test_type === 'mixed' ? (mixed_scenarios[0]?.method || 'GET') : formData.method,
        headers: formData.test_type === 'mixed' ? (mixed_scenarios[0]?.headers || {}) : headers,
        body: formData.test_type === 'mixed' ? (mixed_scenarios[0]?.body || null) : body,
        test_type: formData.test_type,
        users: formData.users,
        spawn_rate: formData.spawn_rate,
        duration: formData.duration,
        ramp_step_users: formData.ramp_step_users,
        ramp_step_duration: formData.ramp_step_duration,
        mixed_scenarios: formData.test_type === 'mixed' ? mixed_scenarios : [],
        max_avg_response_time: formData.max_avg_response_time,
        max_p95_response_time: formData.max_p95_response_time,
        max_failure_rate: formData.max_failure_rate,
        status: formData.statusBool ? 'active' : 'inactive',
        description: formData.description,
      }

      if (isEdit.value) {
        await perfAPI.updateTestCase(currentId.value, data)
        showSuccess('更新成功')
      } else {
        await perfAPI.createTestCase(data)
        showSuccess('创建成功')
      }
      dialogVisible.value = false
      loadList()
    } catch (e) {
      console.error('Submit error:', e)
    } finally {
      submitting.value = false
    }
  })
}

const deleteCase = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要删除用例"${row.name}"吗？`, '删除确认', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'error',
    })
  } catch { return }

  try {
    await perfAPI.deleteTestCase(row.id)
    showSuccess('删除成功')
    loadList()
  } catch (e) {
    console.error('Delete error:', e)
  }
}

// ---------- 工具 ----------
const methodTagType = (m) => {
  const map = { GET: 'success', POST: 'primary', PUT: 'warning', DELETE: 'danger' }
  return map[m] || 'info'
}

const statusTagType = (s) => {
  const map = { completed: 'success', running: '', failed: 'danger', stopped: 'warning', pending: 'info' }
  return map[s] || 'info'
}

// ---------- 混合场景辅助 ----------
const onTestTypeChange = (val) => {
  if (val === 'mixed') {
    formData.target_url = ''
    formData.method = 'GET'
    formData.headersText = ''
    formData.bodyText = ''
  }
}

const addScenario = () => {
  formData.mixedScenarios.push({ url: '', method: 'GET', headersText: '', bodyText: '', weight: 10 })
}

const removeScenario = (idx) => {
  formData.mixedScenarios.splice(idx, 1)
}

const mixedWeightPercent = (idx, scenarios) => {
  const total = scenarios.reduce((s, sc) => s + (sc.weight || 0), 0)
  if (total === 0) return 0
  return Math.round((scenarios[idx].weight || 0) / total * 100)
}
</script>

<style scoped>
.perf-container {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.search-bar {
  margin-bottom: 10px;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 6px;
}

/* 表格外层 */
.table-wrapper {
  overflow-x: auto;
}
.perf-container :deep(.el-table .cell) {
  padding-top: 12px;
  padding-bottom: 12px;
}
.url-ellipsis {
  display: inline-block;
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
}

/* 测试类型卡片 */
.test-type-cards {
  display: flex;
  gap: 24px;
  justify-content: center;
}
.type-card {
  width: 240px;
  padding: 48px 32px 36px;
  min-height: 260px;
  border: 2px solid #e4e7ed;
  border-radius: 12px;
  text-align: center;
  cursor: pointer;
  transition: all 0.25s;
  background: #fff;
}
.type-card:hover {
  border-color: #409EFF;
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.15);
  transform: translateY(-2px);
}
.type-card.active {
  border-color: #409EFF;
  background: #ecf5ff;
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.2);
}
.type-name {
  font-size: 18px;
  font-weight: 600;
  margin: 16px 0 10px;
  color: #303133;
}
.type-desc {
  font-size: 13px;
  color: #909399;
  line-height: 1.6;
  margin-bottom: 16px;
}
</style>
