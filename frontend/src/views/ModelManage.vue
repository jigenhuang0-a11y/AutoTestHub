<template>
  <div class="model-manage">
    <!-- 页头 -->
    <div class="page-header">
      <h2>AI 模型管理</h2>
      <p>统一配置 AI 模型的 API 地址、密钥等参数，用户创建测评任务时直接选择模型即可。</p>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <el-button type="primary" :icon="Plus" @click="openCreate">新增模型</el-button>
      <el-button :icon="RefreshRight" @click="loadModels" :loading="loading">刷新</el-button>
    </div>

    <!-- 模型卡片列表 -->
    <el-row :gutter="16" v-loading="loading">
      <el-col :xs="24" :sm="12" :lg="8" v-for="model in models" :key="model.id" style="margin-bottom: 16px;">
        <el-card shadow="hover" class="model-card" :class="{ 'is-disabled': !model.is_active }">
          <template #header>
            <div class="card-header">
              <span class="model-name">{{ model.name }}</span>
              <el-tag :type="model.is_active ? 'success' : 'info'" size="small">
                {{ model.is_active ? '启用' : '停用' }}
              </el-tag>
            </div>
          </template>

          <div class="card-body">
            <div class="info-row">
              <span class="label">提供商:</span>
              <el-tag size="small">{{ model.provider_display || model.provider }}</el-tag>
            </div>
            <div class="info-row">
              <span class="label">模型 ID:</span>
              <code>{{ model.model_id }}</code>
            </div>
            <div class="info-row">
              <span class="label">API 地址:</span>
              <span class="url-text">{{ model.api_url?.replace('https://', '')?.substring(0, 35) }}...</span>
            </div>
            <div class="info-row">
              <span class="label">超时:</span>
              <span>{{ model.timeout }}s</span>
              <span style="margin-left: 12px; color: #909399;">温度: {{ model.temperature }}</span>
            </div>
            <div class="info-row" v-if="model.description">
              <span class="label">描述:</span>
              <span>{{ model.description }}</span>
            </div>
          </div>

          <div class="card-actions">
            <el-button size="small" type="primary" link @click="testConn(model)" :loading="testingId === model.id">
              测试连接
            </el-button>
            <el-button size="small" link @click="openEdit(model)">编辑</el-button>
            <el-popconfirm title="确定删除此模型配置？" @confirm="deleteModel(model.id)">
              <template #reference>
                <el-button size="small" type="danger" link>删除</el-button>
              </template>
            </el-popconfirm>
            <el-switch
              v-model="model.is_active"
              active-text=""
              inactive-text=""
              style="margin-left: auto"
              @change="toggleActive(model)"
            />
          </div>
        </el-card>
      </el-col>

      <!-- 空状态 -->
      <el-col :span="24" v-if="!loading && models.length === 0">
        <el-empty description="暂无模型配置">
          <el-button type="primary" @click="openCreate">添加第一个模型</el-button>
        </el-empty>
      </el-col>
    </el-row>

    <!-- 创建/编辑弹窗 -->
    <el-dialog
      v-model="showDialog"
      :title="editing ? '编辑模型' : '新增模型'"
      width="600px"
      destroy-on-close
    >
      <el-form :model="form" label-width="100px" ref="formRef" :rules="rules">
        <el-form-item label="模型名称" prop="name" required>
          <el-input v-model="form.name" placeholder="如：DeepSeek Chat V3" />
        </el-form-item>
        <el-form-item label="提供商" prop="provider">
          <el-select v-model="form.provider" placeholder="选择提供商" style="width: 100%">
            <el-option label="DeepSeek" value="deepseek" />
            <el-option label="OpenAI" value="openai" />
            <el-option label="Anthropic Claude" value="anthropic" />
            <el-option label="智谱 GLM" value="zhipu" />
            <el-option label="通义千问" value="qwen" />
            <el-option label="百度文心" value="baidu" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型 ID" prop="model_id" required>
          <el-input v-model="form.model_id" placeholder="如 deepseek-chat, gpt-4o, claude-3-5-sonnet" />
        </el-form-item>
        <el-form-item label="API 地址" prop="api_url" required>
          <el-input v-model="form.api_url" placeholder="https://api.deepseek.com/v1/chat/completions" />
        </el-form-item>
        <el-form-item label="API Key" prop="api_key" required>
          <el-input v-model="form.api_key" type="password" show-password placeholder="sk-..." />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="可选，描述此模型的用途和特点" />
        </el-form-item>
        <el-divider content-position="left">执行参数</el-divider>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="超时(秒)">
              <el-input-number v-model="form.timeout" :min="5" :max="120" :step="5" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="最大Token">
              <el-input-number v-model="form.max_tokens" :min="256" :max="128000" :step="1024" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="温度">
              <el-slider v-model="form.temperature" :min="0" :max="2" :step="0.1" show-input input-size="small" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :icon="Check" @click="saveModel" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, RefreshRight, Check } from '@element-plus/icons-vue'
import { modelConfigAPI } from '@/api/index'

const loading = ref(false)
const saving = ref(false)
const testingId = ref(null)
const models = ref([])
const showDialog = ref(false)
const editing = ref(false)
const editId = ref(null)
const formRef = ref(null)

const form = ref({
  name: '',
  provider: 'deepseek',
  model_id: '',
  api_url: '',
  api_key: '',
  description: '',
  timeout: 30,
  max_tokens: 4096,
  temperature: 0.7,
  is_active: true,
})

const rules = {
  name: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  model_id: [{ required: true, message: '请输入模型 ID', trigger: 'blur' }],
  api_url: [{ required: true, message: '请输入 API 地址', trigger: 'blur' }],
  api_key: [{ required: true, message: '请输入 API Key', trigger: 'blur' }],
}

// 加载模型列表
const loadModels = async () => {
  loading.value = true
  try {
    const res = await modelConfigAPI.list()
    models.value = Array.isArray(res) ? res : (res.results || [])
  } catch {
    models.value = []
  } finally {
    loading.value = false
  }
}

// 打开新增弹窗
const openCreate = () => {
  editing.value = false
  editId.value = null
  form.value = {
    name: '',
    provider: 'deepseek',
    model_id: '',
    api_url: '',
    api_key: '',
    description: '',
    timeout: 30,
    max_tokens: 4096,
    temperature: 0.7,
    is_active: true,
  }
  showDialog.value = true
}

// 打开编辑弹窗
const openEdit = (model) => {
  editing.value = true
  editId.value = model.id
  // 编辑时需要获取完整信息（含 api_key）
  modelConfigAPI.get(model.id).then(full => {
    form.value = {
      name: full.name || model.name,
      provider: full.provider || model.provider,
      model_id: full.model_id || model.model_id,
      api_url: full.api_url || model.api_url,
      api_key: full.api_key || '',
      description: full.description || model.description,
      timeout: full.timeout ?? 30,
      max_tokens: full.max_tokens ?? 4096,
      temperature: full.temperature ?? 0.7,
      is_active: full.is_active !== false,
    }
    showDialog.value = true
  })
}

// 保存
const saveModel = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    if (editing.value && editId.value) {
      await modelConfigAPI.update(editId.value, form.value)
      ElMessage.success('模型已更新')
    } else {
      await modelConfigAPI.create(form.value)
      ElMessage.success('模型已添加')
    }
    showDialog.value = false
    loadModels()
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

// 删除
const deleteModel = async (id) => {
  try {
    await modelConfigAPI.delete(id)
    ElMessage.success('已删除')
    loadModels()
  } catch {
    ElMessage.error('删除失败')
  }
}

// 切换启用/停用
const toggleActive = async (model) => {
  try {
    await modelConfigAPI.patch(model.id, { is_active: model.is_active })
    ElMessage.success(model.is_active ? '已启用' : '已停用')
  } catch {
    model.is_active = !model.is_active // 回滚
    ElMessage.error('操作失败')
  }
}

// 测试连接
const testConn = async (model) => {
  testingId.value = model.id
  try {
    const res = await modelConfigAPI.testConnection(model.id)
    if (res.success) {
      ElMessage.success(res.message)
    } else {
      ElMessage.warning(res.message)
    }
  } catch (e) {
    ElMessage.error('连接失败: ' + (e.response?.data?.message || e.message))
  } finally {
    testingId.value = null
  }
}

onMounted(() => {
  loadModels()
})
</script>

<style scoped>
.model-manage {
  padding: 20px;
}
.page-header h2 {
  margin: 0 0 8px;
  font-size: 20px;
}
.page-header p {
  color: #909399;
  margin: 0 0 20px;
  font-size: 14px;
}
.toolbar {
  margin-bottom: 20px;
}
.model-card {
  transition: transform 0.2s;
}
.model-card:hover {
  transform: translateY(-2px);
}
.model-card.is-disabled {
  opacity: 0.65;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.model-name {
  font-weight: 600;
  font-size: 15px;
}
.card-body {
  font-size: 13px;
}
.info-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}
.info-row .label {
  color: #909399;
  width: 60px;
  flex-shrink: 0;
}
.info-row code {
  background: #f5f7fa;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 12px;
}
.url-text {
  color: #606266;
  font-size: 12px;
}
.card-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  padding-top: 10px;
  border-top: 1px solid #ebeef5;
}
</style>
