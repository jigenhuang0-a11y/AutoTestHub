<template>
  <div class="ai-generate-container">
    <el-row :gutter="20">
      <!-- 左侧：输入区域 -->
      <el-col :span="10">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>接口文档输入</span>
              <el-button type="primary" @click="handleGenerate" :loading="generating">
                <el-icon><MagicStick /></el-icon>
                AI生成
              </el-button>
            </div>
          </template>

          <el-form label-width="80px">
            <el-form-item label="接口文档">
              <el-input
                v-model="apiDocument"
                type="textarea"
                :rows="25"
                placeholder="请粘贴接口文档内容，例如：&#10;&#10;接口名称：用户登录&#10;请求地址：POST /api/auth/login/&#10;请求参数：&#10;- username: 用户名（必填）&#10;- password: 密码（必填）&#10;&#10;响应示例：&#10;{&#10;  &quot;access&quot;: &quot;eyJ...&quot;,&#10;  &quot;refresh&quot;: &quot;eyJ...&quot;&#10;}"
              />
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
            <p>请输入详细的接口文档，包括：</p>
            <ul style="margin: 5px 0; padding-left: 20px">
              <li>接口名称和描述</li>
              <li>请求方法（GET/POST等）</li>
              <li>请求URL和参数</li>
              <li>响应格式和示例</li>
              <li>错误码说明</li>
            </ul>
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
import { ref } from 'vue'
import { testcaseAPI } from '@/api'
import { ElMessage } from 'element-plus'
import { MagicStick, Loading } from '@element-plus/icons-vue'

const apiDocument = ref('')
const generating = ref(false)
const saving = ref(false)
const generatedCases = ref([])
const activeNames = ref([])
const saveToDb = ref(false)

// 生成测试用例
const handleGenerate = async () => {
  if (!apiDocument.value.trim()) {
    ElMessage.warning('请输入接口文档')
    return
  }

  generating.value = true
  try {
    const response = await testcaseAPI.aiGenerate({
      api_document: apiDocument.value,
      save_to_db: saveToDb.value,
    })

    if (saveToDb.value) {
      generatedCases.value = (response.test_cases || []).map(tc => ({
        ...tc,
        selected: true,
      }))
      ElMessage.success(`已生成并保存 ${response.test_cases?.length || 0} 个测试用例`)
    } else {
      generatedCases.value = (response.test_cases || []).map(tc => ({
        ...tc,
        selected: true,
      }))
      ElMessage.success(`成功生成 ${response.count || 0} 个测试用例`)
    }

    // 默认展开第一个
    if (generatedCases.value.length > 0) {
      activeNames.value = [0]
    }
  } catch (error) {
    console.error('Generate error:', error)
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
const saveSelected = async () => {
  const selected = generatedCases.value.filter(tc => tc.selected)
  if (selected.length === 0) {
    ElMessage.warning('请至少选择一个测试用例')
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
        request_body: testCase.request_body || {},
        expected_response: testCase.expected_response || {},
        assertions: testCase.assertions || '',
        priority: testCase.priority || 'P2',
        status: 'draft',
        tags: testCase.tags || [],
      })
      savedCount++
    }
    ElMessage.success(`成功保存 ${savedCount} 个测试用例`)
  } catch (error) {
    console.error('Save error:', error)
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
