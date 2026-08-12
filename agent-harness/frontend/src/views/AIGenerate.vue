<template>
  <div class="ai-generate-container">
    <el-row :gutter="20">
      <!-- 左侧：输入区域 -->
      <el-col :span="10">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>接口需求输入</span>
              <el-button type="primary" @click="handleGenerate" :loading="generating">
                <el-icon><MagicStick /></el-icon>
                AI生成
              </el-button>
            </div>
          </template>

          <el-form label-width="80px">
            <el-form-item label="AI 模型">
              <el-select v-model="selectedModelId" placeholder="选择 AI 底座模型" style="width: 100%">
                <el-option v-for="m in aiModels" :key="m.id" :label="`${m.name}（${m.provider}）`" :value="String(m.id)" />
                <el-option v-if="!aiModels.length" label="未配置模型（将降级 mock）" value="" disabled />
              </el-select>
            </el-form-item>

            <el-form-item label="测试需求">
              <el-input
                v-model="requirement"
                type="textarea"
                :rows="10"
                placeholder="请描述接口测试需求，例如：&#10;为用户登录接口 /api/auth/login 生成正向/异常用例，覆盖用户名密码校验、错误码、超时等场景"
              />
            </el-form-item>

            <el-form-item label="项目名称">
              <el-input v-model="project" placeholder="如：用户中心" />
            </el-form-item>

            <el-form-item label="生成数量">
              <el-input-number v-model="count" :min="1" :max="20" />
            </el-form-item>

            <el-form-item label="保存选项">
              <el-switch v-model="saveToDb" active-text="生成后直接保存" />
            </el-form-item>
          </el-form>

          <el-alert
            title="提示"
            type="info"
            :closable="false"
            style="margin-top: 10px"
          >
            <p>AI 将基于需求真实调用「AI 底座」配置的模型生成用例；若未配置有效模型 Key，将自动降级为本地 mock。</p>
          </el-alert>
        </el-card>
      </el-col>

      <!-- 右侧：生成结果 -->
      <el-col :span="14">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>生成的测试用例 ({{ generatedCases.length }})</span>
              <div v-if="generatedCases.length > 0">
                <el-button size="small" @click="selectAll">全选</el-button>
                <el-button size="small" type="primary" @click="saveSelected" :loading="saving">
                  保存选中
                </el-button>
              </div>
            </div>
          </template>

          <div v-if="generating" style="text-align: center; padding: 50px">
            <el-icon class="is-loading" :size="40"><Loading /></el-icon>
            <p style="margin-top: 10px; color: #999">AI正在生成测试用例...</p>
          </div>

          <el-empty v-else-if="!generatedCases.length" description="暂无生成结果" />

          <div v-else class="result-list">
            <el-collapse v-model="activeNames">
              <el-collapse-item
                v-for="(testCase, index) in generatedCases"
                :key="index"
                :name="index"
              >
                <template #title>
                  <div style="display: flex; align-items: center; width: 100%">
                    <el-checkbox
                      v-model="testCase.selected"
                      @click.stop
                      style="margin-right: 10px"
                    />
                    <span style="flex: 1">{{ testCase.title }}</span>
                    <el-tag size="small" :type="getPriorityType(testCase.priority)">
                      {{ testCase.priority }}
                    </el-tag>
                    <el-tag size="small" style="margin-left: 10px">
                      {{ testCase.method }}
                    </el-tag>
                  </div>
                </template>

                <el-descriptions :column="1" border>
                  <el-descriptions-item label="描述">
                    {{ testCase.description }}
                  </el-descriptions-item>
                  <el-descriptions-item label="接口地址">
                    <code>{{ testCase.api_endpoint }}</code>
                  </el-descriptions-item>
                  <el-descriptions-item label="请求头">
                    <pre>{{ JSON.stringify(testCase.headers || {}, null, 2) }}</pre>
                  </el-descriptions-item>
                  <el-descriptions-item label="请求体">
                    <pre>{{ JSON.stringify(testCase.request_body || {}, null, 2) }}</pre>
                  </el-descriptions-item>
                  <el-descriptions-item label="预期响应">
                    <pre>{{ JSON.stringify(testCase.expected_response || {}, null, 2) }}</pre>
                  </el-descriptions-item>
                  <el-descriptions-item label="断言说明">
                    {{ testCase.assertions }}
                  </el-descriptions-item>
                </el-descriptions>
              </el-collapse-item>
            </el-collapse>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { testcaseAPI, aiBaseAPI } from '@/api'
import { ElMessage } from 'element-plus'
import { MagicStick, Loading } from '@element-plus/icons-vue'

const requirement = ref('')
const project = ref('')
const count = ref(5)
const selectedModelId = ref('')
const aiModels = ref([])

const generating = ref(false)
const saving = ref(false)
const generatedCases = ref([])
const activeNames = ref([])
const saveToDb = ref(false)

async function loadAiModels() {
  try {
    const res = await aiBaseAPI.listModels()
    aiModels.value = res.items || res.results || []
    if (aiModels.value.length) {
      const active = aiModels.value.find(m => m.is_enabled)
      selectedModelId.value = String(active ? active.id : aiModels.value[0].id)
    }
  } catch (e) {
    aiModels.value = []
  }
}
onMounted(loadAiModels)

// 生成测试用例
const handleGenerate = async () => {
  if (!requirement.value.trim()) {
    ElMessage.warning('请输入测试需求')
    return
  }

  generating.value = true
  try {
    const response = await testcaseAPI.aiGenerate({
      requirement: requirement.value,
      project: project.value,
      count: count.value,
      model_id: selectedModelId.value,
    })

    const cases = response.test_cases || []
    generatedCases.value = cases.map(tc => ({
      title: tc.title,
      description: tc.description || '',
      api_endpoint: tc.api_endpoint || '',
      method: tc.method || 'GET',
      headers: typeof tc.headers === 'string' ? {} : (tc.headers || {}),
      request_body: tc.request_body,
      expected_response: tc.expected_response,
      assertions: Array.isArray(tc.assertion_rules) ? JSON.stringify(tc.assertion_rules) : (tc.assertion_rules || ''),
      priority: tc.priority || 'P2',
      status: 'draft',
      tags: Array.isArray(tc.tags) ? tc.tags : (tc.tags ? [tc.tags] : []),
      selected: true,
    }))

    if (saveToDb.value) {
      await saveSelected(true)
      ElMessage.success(`已生成并保存 ${cases.length} 个测试用例${response.ai_enhanced ? '' : '（mock）'}`)
    } else {
      ElMessage.success(`成功生成 ${cases.length} 个测试用例${response.ai_enhanced ? '' : '（mock）'}`)
    }

    if (generatedCases.value.length > 0) {
      activeNames.value = [0]
    }
  } catch (error) {
    console.error('Generate error:', error)
    ElMessage.error('生成失败：' + (error.response?.data?.detail || error.message))
  } finally {
    generating.value = false
  }
}

// 全选
const selectAll = () => {
  const allSelected = generatedCases.value.every(tc => tc.selected)
  generatedCases.value.forEach(tc => {
    tc.selected = !allSelected
  })
}

// 保存选中的用例
const saveSelected = async (silent = false) => {
  const selected = generatedCases.value.filter(tc => tc.selected)
  if (selected.length === 0) {
    if (!silent) ElMessage.warning('请至少选择一个测试用例')
    return
  }

  saving.value = true
  try {
    let savedCount = 0
    for (const testCase of selected) {
      await testcaseAPI.create({
        title: testCase.title,
        description: testCase.description || '',
        api_endpoint: testCase.api_endpoint || '',
        method: testCase.method || 'GET',
        headers: testCase.headers || {},
        request_body: typeof testCase.request_body === 'string' ? testCase.request_body : JSON.stringify(testCase.request_body || {}),
        expected_response: typeof testCase.expected_response === 'string' ? testCase.expected_response : JSON.stringify(testCase.expected_response || {}),
        assertions: testCase.assertions || '',
        priority: testCase.priority || 'P2',
        status: 'draft',
        tags: testCase.tags || [],
      })
      savedCount++
    }
    if (!silent) ElMessage.success(`成功保存 ${savedCount} 个测试用例`)
  } catch (error) {
    console.error('Save error:', error)
    if (!silent) ElMessage.error('保存失败：' + (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
}

const getPriorityType = (priority) => {
  const types = { P0: 'danger', P1: 'warning', P2: '', P3: 'info' }
  return types[priority] || ''
}
</script>

<style scoped>
.ai-generate-container {
  padding: 0;
}

.result-list {
  max-height: 600px;
  overflow-y: auto;
}

pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
}

code {
  background-color: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
}
</style>
