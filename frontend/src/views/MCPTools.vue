<template>
  <div class="mcp-tools-page">
    <div class="page-header">
      <h2>MCP 工具市场</h2>
      <p class="subtitle">Model Context Protocol — Agent 可调用的标准化工具集</p>
      <div class="header-actions">
        <el-button type="primary" @click="refreshTools" :loading="loading">
          <el-icon><Refresh /></el-icon> 刷新工具列表
        </el-button>
        <el-button @click="showServerInfo = true">服务器信息</el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-statistic title="已注册工具" :value="tools.length">
          <template #suffix>
            <el-tag size="small" type="success">个</el-tag>
          </template>
        </el-statistic>
      </el-col>
      <el-col :span="6">
        <el-statistic :value="toolsByCategory.length">
          <template #title><span>工具分类</span></template>
        </el-statistic>
      </el-col>
      <el-col :span="6">
        <el-statistic :value="toolCallStats.total">
          <template #title><span>总调用次数</span></template>
        </el-statistic>
      </el-col>
      <el-col :span="6">
        <el-statistic :value="toolCallStats.errors">
          <template #title><span style="color:#f56c6c">调用失败</span></template>
        </el-statistic>
      </el-col>
    </el-row>

    <!-- 分类筛选 -->
    <div class="filter-bar">
      <el-radio-group v-model="activeCategory" size="small">
        <el-radio-button label="all">全部</el-radio-button>
        <el-radio-button
          v-for="cat in toolsByCategory"
          :key="cat.name"
          :label="cat.name"
        >
          {{ cat.label }} ({{ cat.count }})
        </el-radio-button>
      </el-radio-group>
      <el-input
        v-model="searchKeyword"
        placeholder="搜索工具..."
        prefix-icon="Search"
        clearable
        style="width: 240px; margin-left: 16px"
      />
    </div>

    <!-- 工具卡片网格 -->
    <el-row :gutter="20">
      <el-col
        v-for="tool in filteredTools"
        :key="tool.name"
        :xs="24" :sm="12" :md="8" :lg="6"
      >
        <el-card class="tool-card" :body-style="{ padding: '20px' }" shadow="hover">
          <div class="tool-header">
            <el-tag :type="categoryType(tool.category)" size="small" effect="plain">
              {{ tool.category }}
            </el-tag>
            <el-tooltip content="查看 Schema" placement="top">
              <el-button link type="primary" @click="viewSchema(tool)">
                <el-icon><InfoFilled /></el-icon>
              </el-button>
            </el-tooltip>
          </div>

          <h4 class="tool-name">{{ tool.name }}</h4>
          <p class="tool-desc">{{ tool.description }}</p>

          <div class="tool-params" v-if="tool.inputSchema?.properties">
            <p class="params-label">参数:</p>
            <el-tag
              v-for="(prop, key) in tool.inputSchema.properties"
              :key="key"
              size="small"
              effect="plain"
              style="margin: 2px"
            >
              {{ key }}
              <el-tooltip :content="prop.description || prop.type" placement="top">
                <span style="color: #909399"> : {{ prop.type }}</span>
              </el-tooltip>
            </el-tag>
          </div>

          <div class="tool-actions">
            <el-button type="primary" size="small" @click="openTestDialog(tool)" plain>
              测试调用
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 空状态 -->
    <el-empty v-if="filteredTools.length === 0 && !loading" description="没有匹配的工具" />

    <!-- 测试调用对话框 -->
    <el-dialog v-model="testDialog.visible" :title="`测试: ${testDialog.toolName}`" width="600px">
      <p class="dialog-desc">{{ testDialog.toolDesc }}</p>
      <el-form label-width="80px">
        <el-form-item label="参数 (JSON)">
          <el-input
            v-model="testDialog.argsJson"
            type="textarea"
            :rows="6"
            placeholder='{"query": "登录", "limit": 10}'
          />
        </el-form-item>
      </el-form>
      <div v-if="testDialog.result" class="call-result">
        <el-alert
          :type="testDialog.result.is_error ? 'error' : 'success'"
          :title="testDialog.result.is_error ? '调用失败' : '调用成功'"
          show-icon
          :closable="false"
        />
        <pre class="result-json">{{ JSON.stringify(testDialog.result, null, 2) }}</pre>
      </div>
      <template #footer>
        <el-button @click="testDialog.visible = false">关闭</el-button>
        <el-button type="primary" @click="callToolTest" :loading="testDialog.calling">
          发送调用
        </el-button>
      </template>
    </el-dialog>

    <!-- Schema 查看对话框 -->
    <el-dialog v-model="schemaDialog.visible" title="工具 Schema" width="500px">
      <pre class="schema-json">{{ JSON.stringify(schemaDialog.schema, null, 2) }}</pre>
    </el-dialog>

    <!-- 服务器信息对话框 -->
    <el-dialog v-model="showServerInfo" title="MCP 服务器信息" width="400px">
      <el-descriptions :column="1" border v-if="serverInfo">
        <el-descriptions-item label="名称">{{ serverInfo.name }}</el-descriptions-item>
        <el-descriptions-item label="版本">{{ serverInfo.version }}</el-descriptions-item>
        <el-descriptions-item label="已注册工具">{{ serverInfo.stats?.tools_registered || 0 }}</el-descriptions-item>
        <el-descriptions-item label="总调用">{{ serverInfo.stats?.total_calls || 0 }}</el-descriptions-item>
        <el-descriptions-item label="错误调用">{{ serverInfo.stats?.error_calls || 0 }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, InfoFilled } from '@element-plus/icons-vue'

const loading = ref(false)
const tools = ref([])
const activeCategory = ref('all')
const searchKeyword = ref('')
const showServerInfo = ref(false)
const serverInfo = ref(null)

const toolCallStats = ref({ total: 0, errors: 0 })

const testDialog = ref({
  visible: false, toolName: '', toolDesc: '',
  argsJson: '{}', result: null, calling: false,
})

const schemaDialog = ref({
  visible: false, schema: {},
})

const categoryLabels = {
  testcase: '测试用例', execution: '执行', data: '数据工厂',
  knowledge: '知识库', report: '报告', system: '系统', general: '通用',
}

const categoryTypes = {
  testcase: 'primary', execution: 'warning', data: 'success',
  knowledge: 'info', report: 'danger', system: '',
}

const toolsByCategory = computed(() => {
  const map = {}
  tools.value.forEach(t => {
    if (!map[t.category]) map[t.category] = { name: t.category, label: categoryLabels[t.category] || t.category, count: 0 }
    map[t.category].count++
  })
  return Object.values(map)
})

const filteredTools = computed(() => {
  let list = tools.value
  if (activeCategory.value !== 'all') {
    list = list.filter(t => t.category === activeCategory.value)
  }
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    list = list.filter(t => t.name.includes(kw) || t.description.includes(kw))
  }
  return list
})

const categoryType = (cat) => categoryTypes[cat] || 'info'

const refreshTools = async () => {
  loading.value = true
  try {
    const res = await fetch('/api/mcp/tools/', {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
    })
    const data = await res.json()
    tools.value = data.tools || []
    ElMessage.success(`已加载 ${tools.value.length} 个工具`)
  } catch (e) {
    ElMessage.error('加载工具列表失败')
  } finally {
    loading.value = false
  }
}

const viewSchema = (tool) => {
  schemaDialog.value.schema = { name: tool.name, description: tool.description, inputSchema: tool.inputSchema }
  schemaDialog.value.visible = true
}

const openTestDialog = (tool) => {
  testDialog.value = {
    visible: true, toolName: tool.name, toolDesc: tool.description,
    argsJson: JSON.stringify(
      Object.fromEntries(
        Object.entries(tool.inputSchema?.properties || {}).map(([k, v]) => {
          if (v.type === 'integer') return [k, 1]
          if (v.type === 'array') return [k, []]
          return [k, '']
        })
      ),
      null, 2
    ),
    result: null, calling: false,
  }
}

const callToolTest = async () => {
  testDialog.value.calling = true
  testDialog.value.result = null
  try {
    let args
    try {
      args = JSON.parse(testDialog.value.argsJson)
    } catch {
      ElMessage.error('JSON 格式错误')
      testDialog.value.calling = false
      return
    }
    const res = await fetch('/api/mcp/tools/call/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('token')}`,
      },
      body: JSON.stringify({ tool: testDialog.value.toolName, arguments: args }),
    })
    const data = await res.json()
    testDialog.value.result = { is_error: data.is_error, ...data.result }
    toolCallStats.value.total++
    if (data.is_error) toolCallStats.value.errors++
  } catch (e) {
    testDialog.value.result = { is_error: true, content: [{ type: 'text', text: String(e) }] }
    toolCallStats.value.errors++
  } finally {
    testDialog.value.calling = false
  }
}

const loadServerInfo = async () => {
  try {
    const res = await fetch('/api/mcp/server/info/', {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
    })
    serverInfo.value = await res.json()
  } catch { /* ignore */ }
}

onMounted(() => {
  refreshTools()
  loadServerInfo()
})
</script>

<style scoped>
.mcp-tools-page { padding: 20px; max-width: 1400px; margin: 0 auto; }
.page-header { margin-bottom: 24px; }
.page-header h2 { margin: 0 0 4px; font-size: 24px; }
.subtitle { color: #909399; font-size: 14px; margin: 0 0 12px; }
.header-actions { display: flex; gap: 8px; }
.stats-row { margin-bottom: 20px; }
.filter-bar { display: flex; align-items: center; margin-bottom: 20px; }
.tool-card { margin-bottom: 16px; cursor: pointer; transition: transform .2s; height: 100%; }
.tool-card:hover { transform: translateY(-2px); }
.tool-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.tool-name { font-size: 16px; margin: 0 0 8px; font-family: monospace; color: #409eff; }
.tool-desc { color: #606266; font-size: 13px; line-height: 1.5; margin-bottom: 12px; min-height: 40px; }
.tool-params { margin-bottom: 12px; }
.params-label { font-size: 12px; color: #909399; margin: 0 0 4px; }
.tool-actions { text-align: right; }
.dialog-desc { color: #909399; margin: 0 0 12px; }
.call-result { margin-top: 16px; }
.result-json { background: #f5f7fa; padding: 12px; border-radius: 4px; font-size: 12px; max-height: 300px; overflow: auto; }
.schema-json { background: #f5f7fa; padding: 16px; border-radius: 4px; font-size: 13px; overflow: auto; }
</style>
