<template>
  <div class="harness-page mcp-gateway">
    <!-- 工具统计卡片 -->
    <div class="stats-row">
      <div class="stat-card">
        <span class="stat-value">{{ tools.length }}</span>
        <span class="stat-label">已注册工具</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ categories.length }}</span>
        <span class="stat-label">工具分类</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ tools.filter(t => t.enabled !== false).length }}</span>
        <span class="stat-label">启用中</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ auditTotal }}</span>
        <span class="stat-label">今日调用</span>
      </div>
    </div>

    <!-- 工具配置表 + 安全规则 -->
    <div class="main-row">
      <div class="tool-table-panel">
        <div class="panel-title">
          <span>工具配置</span>
          <el-button type="primary" size="small" @click="showAddTool = true">+ 新增工具</el-button>
        </div>
        <el-table :data="tools" size="small" height="380" row-key="name" empty-text="暂无工具，点击右上角「新增工具」注册 MCP 工具">
          <el-table-column prop="name" label="工具名称" width="180">
            <template #default="{ row }">
              <span class="tool-name">{{ row.name || row.tool }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="category" label="分类" width="100">
            <template #default="{ row }">
              <el-tag size="small">{{ row.category || 'general' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
          <el-table-column label="输入Schema" width="120">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="viewSchema(row)">查看</el-button>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-switch
                v-model="row.enabled"
                :active-value="true"
                :inactive-value="false"
                size="small"
                @change="handleToolStatusChange(row)"
              />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="testCall(row)">测试</el-button>
              <el-button link type="warning" size="small" @click="editTool(row)">编辑</el-button>
              <el-button link type="danger" size="small" @click="deleteTool(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 安全规则面板 -->
      <div class="rules-panel">
        <div class="panel-title">安全规则</div>
        <div class="rule-item">
          <div class="rule-header">
            <el-icon color="#00ff88"><CircleCheckFilled /></el-icon>
            <span>高危代码拦截</span>
            <el-tag size="small" type="success">启用</el-tag>
          </div>
          <p class="rule-desc">拦截 os.system / subprocess / eval / __import__ 等危险调用</p>
        </div>
        <div class="rule-item">
          <div class="rule-header">
            <el-icon color="#00ff88"><CircleCheckFilled /></el-icon>
            <span>外部接口白名单</span>
            <el-tag size="small" type="success">启用</el-tag>
          </div>
          <p class="rule-desc">仅允许白名单内的域名/IP 发起 HTTP 请求（*.api.example.com）</p>
        </div>
        <div class="rule-item">
          <div class="rule-header">
            <el-icon color="#fbbf24"><WarningFilled /></el-icon>
            <span>文件系统隔离</span>
            <el-tag size="small" type="warning">部分启用</el-tag>
          </div>
          <p class="rule-desc">沙箱内文件操作隔离到临时目录，禁止访问宿主机路径</p>
        </div>
        <div class="rule-item">
          <div class="rule-header">
            <el-icon color="#f87171"><CircleCloseFilled /></el-icon>
            <span>网络访问限制</span>
            <el-tag size="small" type="danger">未启用</el-tag>
          </div>
          <p class="rule-desc">限制工具对公网的出站连接（建议启用）</p>
        </div>
      </div>
    </div>

    <!-- 审计记录 -->
    <div class="audit-panel">
      <div class="panel-title">
        <span>审计记录</span>
        <el-button size="small" @click="fetchAudit">刷新</el-button>
      </div>
      <el-table :data="auditRecords" size="small" height="200" row-key="id" empty-text="暂无审计记录，执行工具调用后会自动生成">
        <el-table-column prop="tool_name" label="工具" width="150" />
        <el-table-column prop="team_id" label="团队" width="120" />
        <el-table-column prop="user_id" label="用户" width="80" />
        <el-table-column prop="status" label="结果" width="80">
          <template #default="{ row }">
            <span :class="'status-dot ' + row.status">{{ row.status }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="duration_ms" label="耗时" width="80">
          <template #default="{ row }">{{ row.duration_ms }}ms</template>
        </el-table-column>
        <el-table-column prop="timestamp" label="时间" min-width="160" />
      </el-table>
    </div>

    <!-- 测试调用对话框 -->
    <el-dialog v-model="showTestDialog" title="测试工具调用" width="600px" top="10vh" :close-on-click-modal="false">
      <el-form label-width="80px">
        <el-form-item label="工具">
          <el-input :value="testTarget?.name || testTarget?.tool" disabled />
        </el-form-item>
        <el-form-item label="参数 JSON">
          <el-input v-model="testArgs" type="textarea" rows="6" placeholder='{"key": "value"}' />
        </el-form-item>
      </el-form>
      <div v-if="testResult !== null" class="test-result">
        <div class="result-header">{{ testError ? '错误' : '成功' }}</div>
        <pre>{{ testResult }}</pre>
      </div>
      <template #footer>
        <el-button @click="showTestDialog = false">取消</el-button>
        <el-button type="primary" :loading="testLoading" @click="doTestCall">调用</el-button>
      </template>
    </el-dialog>

    <!-- Schema 查看 -->
    <el-dialog v-model="showSchemaDialog" title="工具 Schema" width="500px" top="10vh">
      <pre class="schema-pre">{{ schemaContent }}</pre>
    </el-dialog>
    <!-- 新增工具对话框 -->
    <el-dialog v-model="showAddTool" title="新增工具" width="600px" top="10vh" :close-on-click-modal="false">
      <el-form :model="addToolForm" label-width="90px">
        <el-form-item label="工具名称" required>
          <el-input v-model="addToolForm.name" placeholder="例如：python_repl" />
        </el-form-item>
        <el-form-item label="分类" required>
          <el-select v-model="addToolForm.category" placeholder="选择分类" style="width: 100%">
            <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="addToolForm.description" type="textarea" :rows="3" placeholder="工具用途说明" />
        </el-form-item>
        <el-form-item label="输入Schema">
          <el-input v-model="addToolForm.inputSchema" type="textarea" :rows="6" placeholder='{"type": "object", "properties": {}}' />
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch v-model="addToolForm.enabled" :active-value="true" :inactive-value="false" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddTool = false">取消</el-button>
        <el-button type="primary" :loading="addToolLoading" @click="submitAddTool">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CircleCheckFilled, WarningFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import api from '@/api'

const tools = ref([])
const categories = ref([])
const auditRecords = ref([])
const auditTotal = ref(0)

// 测试调用
const showTestDialog = ref(false)
const testTarget = ref(null)
const testArgs = ref('{}')
const testResult = ref(null)
const testError = ref(false)
const testLoading = ref(false)

// Schema
const showSchemaDialog = ref(false)
const schemaContent = ref('')

// 新增
const showAddTool = ref(false)
const addToolLoading = ref(false)
const addToolForm = reactive({
  name: '',
  category: '',
  description: '',
  inputSchema: '{\n  "type": "object",\n  "properties": {}\n}',
  enabled: true
})

async function fetchTools() {
  try {
    const res = await api.get('/mcp/tools/')
    // 响应拦截器已返回 response.data，res 即后端 JSON
    const data = res
    tools.value = (data.tools || data.results || []).map(t => ({
      ...t,
      enabled: t.enabled !== false,
      category: t.category || t.tool_type || '',
    }))
  } catch (e) {
    ElMessage.error('获取工具列表失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function fetchAudit() {
  try {
    const res = await api.get('/mcp/audit/', { params: { limit: 20 } })
    auditRecords.value = res.records || []
    auditTotal.value = res.stats?.today_calls || 0
  } catch (e) {
    auditRecords.value = []
    auditTotal.value = 0
  }
}

async function loadCategories() {
  try {
    const res = await api.get('/mcp/tools/categories/')
    categories.value = res.results || res || []
  } catch (e) {
    // 分类接口不可用时回退到从工具列表提取
    const cats = new Set()
    tools.value.forEach(t => { if (t.category) cats.add(t.category) })
    categories.value = Array.from(cats).map(name => ({ name, active: true, count: 0 }))
  }
}

async function handleToolStatusChange(row) {
  const toolName = row.name || row.tool
  const newStatus = row.enabled ? 'active' : 'disabled'
  try {
    await api.put(`/mcp/tools/${toolName}/`, { status: newStatus })
    ElMessage.success(`"${toolName}" 已${row.enabled ? '启用' : '禁用'}`)
    fetchAudit()
  } catch (e) {
    ElMessage.error('状态保存失败: ' + (e.response?.data?.detail || e.message))
    // 回滚开关
    row.enabled = !row.enabled
  }
}

function viewSchema(row) {
  schemaContent.value = JSON.stringify(row.input_schema || row.parameters || { type: 'object', properties: {} }, null, 2)
  showSchemaDialog.value = true
}

function testCall(row) {
  testTarget.value = row
  testArgs.value = '{}'
  testResult.value = null
  showTestDialog.value = true
}

async function doTestCall() {
  testLoading.value = true
  const toolName = testTarget.value.name || testTarget.value.tool
  try {
    let args
    try { args = JSON.parse(testArgs.value) } catch { args = {} }
    const res = await api.post('/mcp/tools/call/', {
      tool_name: toolName,
      arguments: args,
    })
    testResult.value = JSON.stringify(res, null, 2)
    testError.value = !res.ok
    fetchAudit()
  } catch (e) {
    testResult.value = e.response?.data || e.message
    testError.value = true
  } finally {
    testLoading.value = false
  }
}

function editTool(row) {
  // 将当前工具信息填入新增表单进行编辑
  addToolForm.name = row.name || row.tool
  addToolForm.category = row.category || 'general'
  addToolForm.description = row.description || ''
  addToolForm.inputSchema = JSON.stringify(row.input_schema || { type: 'object', properties: {} }, null, 2)
  addToolForm.enabled = row.enabled !== false
  showAddTool.value = true
}

function deleteTool(row) {
  const toolName = row.name || row.tool
  ElMessageBox.confirm(`确定删除工具 "${toolName}"？`, '确认', { type: 'warning' })
    .then(async () => {
      try {
        await api.delete(`/mcp/tools/${toolName}/`)
        ElMessage.success('已删除')
        fetchTools()
        fetchAudit()
      } catch (e) {
        ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
      }
    })
    .catch(() => {})
}

async function submitAddTool() {
  if (!addToolForm.name.trim()) {
    ElMessage.warning('请输入工具名称')
    return
  }
  if (!addToolForm.category) {
    ElMessage.warning('请选择工具分类')
    return
  }
  let inputSchema = { type: 'object', properties: {} }
  try {
    inputSchema = JSON.parse(addToolForm.inputSchema || '{}')
  } catch {
    ElMessage.warning('输入 Schema 不是合法 JSON')
    return
  }
  addToolLoading.value = true
  try {
    const payload = {
      name: addToolForm.name.trim(),
      category: addToolForm.category,
      description: addToolForm.description.trim(),
      input_schema: inputSchema,
      enabled: addToolForm.enabled,
      endpoint: `/mcp/${addToolForm.name.trim()}`
    }
    await api.post('/mcp/tools/', payload)
    ElMessage.success('工具保存成功')
    showAddTool.value = false
    resetAddToolForm()
    fetchTools()
    fetchAudit()
  } catch (e) {
    console.error('新增工具失败', e)
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    addToolLoading.value = false
  }
}

function resetAddToolForm() {
  addToolForm.name = ''
  addToolForm.category = ''
  addToolForm.description = ''
  addToolForm.inputSchema = '{\n  "type": "object",\n  "properties": {}\n}'
  addToolForm.enabled = true
}

onMounted(() => { fetchTools().then(loadCategories); fetchAudit() })
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

.stats-row, .main-row, .stat-card, .tool-table-panel, .rules-panel, .audit-panel {
  position: relative;
  z-index: 1;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 12px;
  flex: 0 0 auto;
}

.main-row {
  display: grid;
  grid-template-columns: 3fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.stat-card, .tool-table-panel, .rules-panel, .audit-panel {
  background: rgba(30, 41, 59, 0.9);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 16px !important;
  box-shadow: 0 2px 8px rgba(2, 8, 20, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
  
  contain: layout paint;
  transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s;
}

.stat-card {
  display: flex;
  flex-direction: column;
  padding: 12px;
}

.stat-value { font-size: 24px; font-weight: 700; color: #7dd3fc; }
.stat-label { font-size: 11px; color: #e2e8f0; margin-top: 4px; }

.stat-card:hover, .tool-table-panel:hover, .rules-panel:hover, .audit-panel:hover {
  border-color: rgba(64, 158, 255, 0.45) !important;
  box-shadow: 0 12px 40px rgba(2, 132, 199, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.1) !important;
}

.stat-card::before, .tool-table-panel::before, .rules-panel::before, .audit-panel::before {
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

.tool-table-panel, .rules-panel, .audit-panel {
  background: rgba(30, 41, 59, 0.9);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 8px;
  padding: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.audit-panel { flex: 0 0 220px; min-height: 0; }

.panel-title {
  font-size: 13px; font-weight: 600; color: #e2e8f0;
  margin-bottom: 8px;
  display: flex; align-items: center; justify-content: space-between;
}

.tool-name { color: #7dd3fc; font-weight: 500; }

/* 安全规则 */
.rule-item {
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(64, 158, 255, 0.2);
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 10px;
}
.rule-header {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; font-weight: 600; color: #f1f5f9;
  margin-bottom: 6px;
}
.rule-desc { font-size: 12px; color: #e2e8f0; margin: 0; }

/* 表格暗色 */
:deep(.el-table) {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: rgba(30, 41, 59, 0.95);
  --el-table-row-hover-bg-color: rgba(64, 158, 255, 0.08);
  --el-table-border-color: rgba(64, 158, 255, 0.15);
  --el-table-text-color: #e2e8f0;
  --el-table-header-text-color: #e2e8f0;
}
:deep(.el-table th) { border-bottom: 1px solid rgba(64, 158, 255, 0.15); padding: 10px 8px; }
:deep(.el-table td) { border-bottom: 1px solid rgba(64, 158, 255, 0.08); padding: 8px; }

.status-dot::before {
  content: ''; display: inline-block;
  width: 7px; height: 7px; border-radius: 50%; margin-right: 6px;
}
.status-dot.success::before { background: #00ff88; }
.status-dot.failure::before, .status-dot.error::before { background: #f87171; }

/* 测试对话框 */
.test-result {
  margin-top: 16px;
  background: rgba(15, 23, 42, 0.8);
  border-radius: 6px;
  padding: 12px;
  max-height: 200px; overflow: auto;
}
.test-result .result-header {
  font-size: 13px; font-weight: 600; margin-bottom: 8px;
}
.test-result pre {
  color: #e2e8f0; font-size: 12px; white-space: pre-wrap; word-break: break-all;
}

.schema-pre {
  background: rgba(15, 23, 42, 0.8); color: #e2e8f0; padding: 16px; border-radius: 6px;
  font-size: 12px; max-height: 400px; overflow: auto; white-space: pre-wrap;
}

/* el-dialog dark */
:deep(.el-dialog) { background: rgba(30, 41, 59, 0.9); border: 1px solid rgba(64, 158, 255, 0.3); }
:deep(.el-dialog__title) { color: #f1f5f9; }
:deep(.el-dialog__body) { color: #e2e8f0; }
:deep(.el-input__inner), :deep(.el-textarea__inner) {
  background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(64, 158, 255, 0.3); color: #e2e8f0;
}
:deep(.el-form-item__label) { color: #e2e8f0; }
</style>
