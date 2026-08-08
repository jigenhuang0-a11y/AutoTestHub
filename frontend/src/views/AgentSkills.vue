<template>
  <div class="agent-skills-container">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">
          <el-icon><SetUp /></el-icon>
          技能库
        </h2>
        <el-tag type="info" class="skills-count">{{ filteredSkills.length }} 个技能</el-tag>
      </div>
      <div class="header-right">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索技能..."
          prefix-icon="Search"
          clearable
          style="width: 240px"
        />
        <el-button type="primary" @click="showAddDialog">
          <el-icon><Plus /></el-icon>
          添加 Skill
        </el-button>
      </div>
    </div>

    <!-- 技能卡片列表 -->
    <div class="skills-grid" v-loading="loading">
      <div v-if="filteredSkills.length === 0" class="empty-state">
        <el-empty description="暂无技能" :image-size="120">
          <el-button type="primary" @click="showAddDialog">添加第一个技能</el-button>
        </el-empty>
      </div>

      <div
        v-for="skill in filteredSkills"
        :key="skill.id"
        class="skill-card"
        :class="{ 'skill-disabled': !skill.enabled }"
      >
        <!-- 卡片头部 -->
        <div class="card-header">
          <div class="skill-name-section">
            <h3 class="skill-name">{{ skill.name }}</h3>
            <div class="skill-badges">
              <el-tag v-if="skill.enabled" type="success" size="small">已启用</el-tag>
              <el-tag v-else type="info" size="small">已停用</el-tag>
              <el-tag v-if="skill.isBuiltIn" type="warning" size="small" effect="plain">内置</el-tag>
            </div>
          </div>
        </div>

        <!-- 卡片内容 -->
        <div class="card-body">
          <p class="skill-description">{{ skill.description }}</p>

          <!-- 触发关键词 -->
          <div class="skill-keywords" v-if="skill.keywords && skill.keywords.length > 0">
            <el-tag
              v-for="kw in skill.keywords"
              :key="kw"
              size="small"
              effect="plain"
              class="keyword-tag"
            >
              {{ kw }}
            </el-tag>
          </div>

          <!-- 文件信息 -->
          <div class="skill-files" v-if="skill.files && skill.files.length > 0">
            <el-icon><Document /></el-icon>
            <span class="files-text">{{ skill.files.length }} 个文件</span>
            <span class="files-detail">({{ skill.files.join(', ') }})</span>
          </div>
        </div>

        <!-- 卡片底部操作栏 -->
        <div class="card-footer">
          <el-switch
            v-model="skill.enabled"
            @change="(val) => toggleSkill(skill, val)"
            :loading="skill.toggling"
          />
          <div class="card-actions">
            <el-button
              size="small"
              text
              @click="viewSkill(skill)"
            >
              <el-icon><View /></el-icon>
              查看
            </el-button>
            <el-button
              size="small"
              text
              @click="editSkill(skill)"
            >
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-button
              size="small"
              text
              @click="exportSkill(skill)"
            >
              <el-icon><Download /></el-icon>
              导出
            </el-button>
            <el-button
              size="small"
              text
              type="danger"
              @click="deleteSkill(skill)"
              :disabled="skill.isBuiltIn"
            >
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 查看技能详情对话框 -->
    <el-dialog
      v-model="viewDialogVisible"
      title="技能详情"
      width="600px"
      destroy-on-close
    >
      <div v-if="viewingSkill" class="skill-detail">
        <div class="detail-header">
          <h3 class="detail-name">{{ viewingSkill.name }}</h3>
          <div class="detail-badges">
            <el-tag v-if="viewingSkill.enabled" type="success" size="small">已启用</el-tag>
            <el-tag v-else type="info" size="small">已停用</el-tag>
            <el-tag v-if="viewingSkill.isBuiltIn" type="warning" size="small" effect="plain">内置</el-tag>
          </div>
        </div>

        <el-descriptions :column="1" border>
          <el-descriptions-item label="技能描述">
            {{ viewingSkill.description }}
          </el-descriptions-item>

          <el-descriptions-item label="触发关键词" v-if="viewingSkill.keywords && viewingSkill.keywords.length > 0">
            <el-tag
              v-for="kw in viewingSkill.keywords"
              :key="kw"
              size="small"
              effect="plain"
              class="keyword-tag"
            >
              {{ kw }}
            </el-tag>
          </el-descriptions-item>

          <el-descriptions-item label="关联文件" v-if="viewingSkill.files && viewingSkill.files.length > 0">
            <div class="file-list">
              <div v-for="f in viewingSkill.files" :key="f" class="file-item">
                <el-icon><Document /></el-icon>
                <span>{{ f }}</span>
              </div>
            </div>
          </el-descriptions-item>

          <el-descriptions-item label="系统提示词">
            <div class="system-prompt-box">
              <pre>{{ viewingSkill.systemPrompt }}</pre>
            </div>
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="editFromView">
          <el-icon><Edit /></el-icon>
          编辑
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量导入技能选择对话框 -->
    <el-dialog
      v-model="batchImportVisible"
      title="批量导入技能"
      width="650px"
      destroy-on-close
      :z-index="3000"
    >
      <div class="batch-import-header">
        <p>检测到 <strong>{{ batchImportSkills.length }}</strong> 个技能，请选择要导入的技能：</p>
        <el-button text size="small" @click="toggleSelectAll">
          {{ selectedImportIds.length === batchImportSkills.length ? '取消全选' : '全选' }}
        </el-button>
      </div>
      <el-checkbox-group v-model="selectedImportIds" class="batch-import-list">
        <div
          v-for="(skill, idx) in batchImportSkills"
          :key="idx"
          class="batch-import-item"
        >
          <el-checkbox :label="String(idx)" :value="String(idx)">
            <span class="import-skill-name">{{ skill.name }}</span>
          </el-checkbox>
          <p class="import-skill-desc">{{ skill.description }}</p>
          <div class="import-skill-tags" v-if="skill.keywords && skill.keywords.length > 0">
            <el-tag v-for="kw in skill.keywords.slice(0, 6)" :key="kw" size="small" effect="plain">
              {{ kw }}
            </el-tag>
            <span v-if="skill.keywords.length > 6" class="more-tags">+{{ skill.keywords.length - 6 }}</span>
          </div>
        </div>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="cancelBatchImport">取消</el-button>
        <el-button
          type="primary"
          @click="confirmBatchImport"
          :disabled="selectedImportIds.length === 0"
        >
          导入选中技能 ({{ selectedImportIds.length }})
        </el-button>
      </template>
    </el-dialog>

    <!-- 添加/编辑技能对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑 Skill' : '添加 Skill'"
      width="600px"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="100px"
      >
        <el-form-item label="技能名称" prop="name">
          <el-input v-model="form.name" placeholder="例如：api-testcase-generator" />
        </el-form-item>

        <el-form-item label="技能描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="描述该技能的功能和用途..."
          />
        </el-form-item>

        <el-form-item label="触发关键词">
          <div class="dynamic-tags">
            <el-tag
              v-for="(tag, index) in form.keywords"
              :key="index"
              closable
              @close="removeKeyword(index)"
              class="dynamic-tag"
            >
              {{ tag }}
            </el-tag>
            <el-input
              v-if="inputVisible"
              ref="keywordInputRef"
              v-model="inputValue"
              size="small"
              @keyup.enter="handleKeywordConfirm"
              @blur="handleKeywordConfirm"
              style="width: 100px"
            />
            <el-button v-else size="small" @click="showKeywordInput">
              <el-icon><Plus /></el-icon>
              添加关键词
            </el-button>
          </div>
        </el-form-item>

        <el-form-item label="关联文件">
          <el-upload
            action="#"
            :auto-upload="false"
            :on-change="handleFileChange"
            :file-list="fileList"
            multiple
          >
            <el-button size="small">
              <el-icon><Upload /></el-icon>
              选择文件
            </el-button>
            <template #tip>
              <div class="el-upload__tip">
                支持 .json, .md, .py, .txt 等文件。
                <strong>上传 .json 文件将自动识别并填充表单字段。</strong>
              </div>
            </template>
          </el-upload>
        </el-form-item>

        <el-form-item label="系统提示词" prop="systemPrompt">
          <el-input
            v-model="form.systemPrompt"
            type="textarea"
            :rows="6"
            placeholder="输入系统提示词，定义 AI 在该技能下的行为..."
          />
        </el-form-item>

        <el-form-item label="启用状态">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveSkill" :loading="saving">
          {{ isEditing ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  SetUp, Plus, Search, Edit, Delete, Download,
  Document, Upload, View
} from '@element-plus/icons-vue'

// 状态
const loading = ref(false)
const searchKeyword = ref('')
const dialogVisible = ref(false)
const viewDialogVisible = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const formRef = ref(null)
const keywordInputRef = ref(null)
const inputVisible = ref(false)
const inputValue = ref('')
const fileList = ref([])
const viewingSkill = ref(null)

// 批量导入相关状态
const batchImportVisible = ref(false)
const batchImportSkills = ref([])
const selectedImportIds = ref([])

// 表单数据
const form = ref({
  id: null,
  name: '',
  description: '',
  keywords: [],
  files: [],
  systemPrompt: '',
  enabled: true,
})

// 表单校验规则
const formRules = {
  name: [
    { required: true, message: '请输入技能名称', trigger: 'blur' },
    { pattern: /^[a-z0-9-]+$/, message: '只能包含小写字母、数字和连字符', trigger: 'blur' },
  ],
  description: [
    { required: true, message: '请输入技能描述', trigger: 'blur' },
  ],
  systemPrompt: [
    { required: true, message: '请输入系统提示词', trigger: 'blur' },
  ],
}

// 技能列表（模拟数据 + localStorage 持久化）
const skills = ref([])

// 内置技能模板
const builtInSkills = [
  {
    id: 'builtin-1',
    name: 'api-testcase-generator',
    description: 'Generate structured API test cases from Postman Collection v2.1 JSON, Apipost export JSON, or Swagger/OpenAPI 2.0 & 3.0 JSON. Covers normal cases, boundary values, error cases, authentication scenarios, and cross-field validation.',
    keywords: ['接口测试用例', 'Postman用例生成', 'Apipost用例生成', 'Swagger用例生成', 'OpenAPI用例生成', 'generate API test cases', '接口边界值用例'],
    files: ['references', 'scripts'],
    systemPrompt: 'You are an API testing expert. Generate comprehensive test cases...',
    enabled: true,
    isBuiltIn: true,
  },
  {
    id: 'builtin-2',
    name: 'browser-use',
    description: 'Automates browser interactions for web testing, form filling, screenshots, and data extraction. Use when the user needs to navigate websites, interact with web pages, fill forms, take screenshots, or extract information from web pages.',
    keywords: ['浏览器自动化', 'web测试', '页面截图', '表单填写'],
    files: ['_meta.json', '_references'],
    systemPrompt: 'You are a browser automation expert using Playwright...',
    enabled: true,
    isBuiltIn: true,
  },
  {
    id: 'builtin-3',
    name: 'e2e-testing-patterns',
    description: 'Build reliable, fast E2E test suites with Playwright and Cypress. Critical user journey coverage, flaky test elimination, CI/CD integration.',
    keywords: ['e2e测试', 'Playwright', 'Cypress', '端到端测试'],
    files: ['README.md', '_meta.json'],
    systemPrompt: 'You are an E2E testing specialist...',
    enabled: true,
    isBuiltIn: true,
  },
  {
    id: 'builtin-4',
    name: 'requirement-reviewer',
    description: '对需求文档/PRD进行逻辑审查+完整性评估+100分制打分，低于60分标记为不通过，输出Markdown结构化评审报告。专治需求写得烂、逻辑混乱、缺胳膊少腿的PRD。',
    keywords: ['testing', 'qa', 'review', 'prd', 'requirement', '需求评审'],
    files: [],
    systemPrompt: 'You are a requirements analyst. Review PRDs for completeness...',
    enabled: true,
    isBuiltIn: true,
  },
  {
    id: 'builtin-5',
    name: 'testcase-reviewer',
    description: '对测试用例进行逻辑审查 + PRD 对齐检查 + 100分制打分，低于 60 分的用例标记为不通过，输出 Markdown 表格报告。',
    keywords: ['testing', 'qa', 'review', 'prd', 'testcase'],
    files: [],
    systemPrompt: 'You are a test case reviewer. Check test cases against requirements...',
    enabled: true,
    isBuiltIn: true,
  },
  {
    id: 'builtin-6',
    name: 'universal-testcase-generator',
    description: '全能测试用例生成器 - 根据各类文档生成测试用例，并支持多种导出格式。支持多种文档类型：PRD、接口文档、设计截图、在线文档...',
    keywords: ['生成测试用例', '测试用例思维导图', '接口测试用例', 'PRD转测试用例', 'test case generation'],
    files: ['README.md', 'assets', 'input', 'references', 'scripts'],
    systemPrompt: 'You are a universal test case generator...',
    enabled: true,
    isBuiltIn: true,
  },
]

// 过滤后的技能列表
const filteredSkills = computed(() => {
  if (!searchKeyword.value) return skills.value
  const keyword = searchKeyword.value.toLowerCase()
  return skills.value.filter(skill =>
    skill.name.toLowerCase().includes(keyword) ||
    skill.description.toLowerCase().includes(keyword) ||
    skill.keywords.some(k => k.toLowerCase().includes(keyword))
  )
})

// 加载技能列表
const loadSkills = () => {
  loading.value = true
  try {
    const saved = localStorage.getItem('agent_skills')
    if (saved) {
      const customSkills = JSON.parse(saved)
      // 合并内置技能和自定义技能
      skills.value = [...builtInSkills, ...customSkills]
    } else {
      skills.value = [...builtInSkills]
    }
  } catch (error) {
    console.error('Load skills error:', error)
    skills.value = [...builtInSkills]
  } finally {
    loading.value = false
  }
}

// 保存自定义技能到 localStorage
const saveSkillsToStorage = () => {
  const customSkills = skills.value.filter(s => !s.isBuiltIn)
  localStorage.setItem('agent_skills', JSON.stringify(customSkills))
}

// 显示添加对话框
const showAddDialog = () => {
  isEditing.value = false
  form.value = {
    id: null,
    name: '',
    description: '',
    keywords: [],
    files: [],
    systemPrompt: '',
    enabled: true,
  }
  fileList.value = []
  dialogVisible.value = true
}

// 查看技能详情
const viewSkill = (skill) => {
  viewingSkill.value = { ...skill }
  viewDialogVisible.value = true
}

// 从查看页面进入编辑
const editFromView = () => {
  viewDialogVisible.value = false
  if (viewingSkill.value) {
    editSkill(viewingSkill.value)
  }
}

// 编辑技能
const editSkill = (skill) => {
  isEditing.value = true
  form.value = {
    id: skill.id,
    name: skill.name,
    description: skill.description,
    keywords: [...skill.keywords],
    files: [...(skill.files || [])],
    systemPrompt: skill.systemPrompt || '',
    enabled: skill.enabled,
  }
  fileList.value = skill.files.map(f => ({ name: f }))
  dialogVisible.value = true
}

// 保存技能
const saveSkill = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    if (isEditing.value) {
      // 更新现有技能
      const index = skills.value.findIndex(s => s.id === form.value.id)
      if (index !== -1) {
        skills.value[index] = {
          ...skills.value[index],
          ...form.value,
          files: fileList.value.map(f => f.name || f),
        }
        ElMessage.success('技能更新成功')
      }
    } else {
      // 创建新技能
      const newSkill = {
        id: 'skill-' + Date.now(),
        ...form.value,
        files: fileList.value.map(f => f.name || f),
        isBuiltIn: false,
        toggling: false,
      }
      skills.value.unshift(newSkill)
      ElMessage.success('技能创建成功')
    }
    saveSkillsToStorage()
    dialogVisible.value = false
  } finally {
    saving.value = false
  }
}

// 删除技能
const deleteSkill = async (skill) => {
  if (skill.isBuiltIn) {
    ElMessage.warning('内置技能不能删除')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定要删除技能 "${skill.name}" 吗？`,
      '确认删除',
      { type: 'warning' }
    )
    const index = skills.value.findIndex(s => s.id === skill.id)
    if (index !== -1) {
      skills.value.splice(index, 1)
      saveSkillsToStorage()
      ElMessage.success('删除成功')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Delete error:', error)
    }
  }
}

// 切换技能启用状态
const toggleSkill = async (skill, enabled) => {
  skill.toggling = true
  try {
    // 模拟 API 调用
    await new Promise(resolve => setTimeout(resolve, 300))
    skill.enabled = enabled
    if (!skill.isBuiltIn) {
      saveSkillsToStorage()
    }
    ElMessage.success(`${skill.name} 已${enabled ? '启用' : '停用'}`)
  } catch (error) {
    console.error('Toggle error:', error)
    skill.enabled = !enabled
    ElMessage.error('操作失败')
  } finally {
    skill.toggling = false
  }
}

// 导出技能
const exportSkill = (skill) => {
  const data = {
    name: skill.name,
    description: skill.description,
    keywords: skill.keywords,
    systemPrompt: skill.systemPrompt,
    files: skill.files,
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${skill.name}.skill.json`
  link.click()
  URL.revokeObjectURL(url)
  ElMessage.success(`已导出 ${skill.name}`)
}

// 关键词标签相关
const showKeywordInput = () => {
  inputVisible.value = true
  nextTick(() => {
    keywordInputRef.value?.focus()
  })
}

const handleKeywordConfirm = () => {
  if (inputValue.value) {
    if (!form.value.keywords.includes(inputValue.value)) {
      form.value.keywords.push(inputValue.value)
    }
  }
  inputVisible.value = false
  inputValue.value = ''
}

const removeKeyword = (index) => {
  form.value.keywords.splice(index, 1)
}

// 文件上传相关 - 自动解析 JSON 文件填充表单
const handleFileChange = (uploadFile, uploadFiles) => {
  fileList.value = uploadFiles
  
  // 如果是 JSON 文件，尝试解析并自动填充表单
  const file = uploadFile.raw
  if (file && file.name.toLowerCase().endsWith('.json')) {
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const content = JSON.parse(e.target.result)
        
        // 检测是否为技能数组（批量导入模式）
        if (Array.isArray(content) && content.length > 0) {
          // 提取技能配置字段（兼容多种命名风格）
          batchImportSkills.value = content.map(item => ({
            name: item.name || item.skill_name || '',
            description: item.description || item.desc || '',
            keywords: item.keywords || item.tags || item.trigger_keywords || [],
            systemPrompt: item.system_prompt || item.systemPrompt || item.prompt || item.system_prompt_template || '',
          })).filter(s => s.name) // 至少需要有名称
          
          selectedImportIds.value = batchImportSkills.value.map((_, idx) => String(idx))
          // 先关闭添加/编辑对话框，再打开批量导入对话框
          dialogVisible.value = false
          nextTick(() => {
            batchImportVisible.value = true
          })
          return
        }
        
        // 单技能对象模式（原有逻辑）
        const skillData = {
          name: content.name || content.skill_name || '',
          description: content.description || content.desc || '',
          keywords: content.keywords || content.tags || content.trigger_keywords || [],
          systemPrompt: content.system_prompt || content.systemPrompt || content.prompt || content.system_prompt_template || '',
        }
        
        // 自动填充（只填充空字段，避免覆盖已有内容）
        if (skillData.name && !form.value.name) {
          form.value.name = skillData.name
        }
        if (skillData.description && !form.value.description) {
          form.value.description = skillData.description
        }
        if (skillData.keywords.length > 0 && form.value.keywords.length === 0) {
          form.value.keywords = [...skillData.keywords]
        }
        if (skillData.systemPrompt && !form.value.systemPrompt) {
          form.value.systemPrompt = skillData.systemPrompt
        }
        
        ElMessage.success('已自动识别并填充技能字段')
      } catch (err) {
        console.warn('JSON 解析失败，仅作为文件关联:', err)
      }
    }
    reader.readAsText(file)
  }
}

// 批量导入 - 全选/取消全选
const toggleSelectAll = () => {
  if (selectedImportIds.value.length === batchImportSkills.value.length) {
    selectedImportIds.value = []
  } else {
    selectedImportIds.value = batchImportSkills.value.map((_, idx) => String(idx))
  }
}

// 批量导入 - 取消
const cancelBatchImport = () => {
  batchImportVisible.value = false
  batchImportSkills.value = []
  selectedImportIds.value = []
}

// 批量导入 - 确认导入
const confirmBatchImport = () => {
  const selectedSkills = selectedImportIds.value
    .map(idxStr => batchImportSkills.value[parseInt(idxStr)])
    .filter(Boolean)
  
  if (selectedSkills.length === 0) {
    ElMessage.warning('请至少选择一个技能')
    return
  }
  
  // 批量创建技能
  const newSkills = selectedSkills.map(skill => ({
    id: 'skill-' + Date.now() + '-' + Math.random().toString(36).substring(2, 8),
    name: skill.name,
    description: skill.description,
    keywords: [...skill.keywords],
    files: [],
    systemPrompt: skill.systemPrompt || '',
    enabled: true,
    isBuiltIn: false,
    toggling: false,
  }))
  
  skills.value.unshift(...newSkills)
  saveSkillsToStorage()
  
  ElMessage.success(`成功导入 ${newSkills.length} 个技能`)
  
  // 清理状态
  batchImportVisible.value = false
  batchImportSkills.value = []
  selectedImportIds.value = []
}

onMounted(() => {
  loadSkills()
})
</script>

<style scoped>
.agent-skills-container {
  padding: 24px;
  height: 100%;
  overflow-y: auto;
  box-sizing: border-box;
  background: #f5f7fa;
}

/* 页面头部 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-title .el-icon {
  font-size: 24px;
  color: #409eff;
}

.skills-count {
  font-size: 13px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 技能卡片网格 */
.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 20px;
}

.empty-state {
  grid-column: 1 / -1;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

/* 技能卡片 */
.skill-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  border: 1px solid #e4e7ed;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  min-height: 240px;
}

.skill-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.skill-disabled {
  opacity: 0.7;
  background: #fafafa;
}

/* 卡片头部 */
.card-header {
  margin-bottom: 12px;
}

.skill-name-section {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.skill-name {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin: 0;
  word-break: break-all;
  flex: 1;
}

.skill-badges {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

/* 卡片内容 */
.card-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skill-description {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.skill-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.keyword-tag {
  font-size: 12px;
}

.skill-files {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #909399;
}

.skill-files .el-icon {
  font-size: 14px;
}

.files-text {
  font-weight: 500;
}

.files-detail {
  color: #c0c4cc;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 卡片底部 */
.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

.card-actions {
  display: flex;
  gap: 4px;
}

.card-actions .el-button {
  padding: 4px 8px;
}

/* 动态标签 */
.dynamic-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.dynamic-tag {
  margin-right: 0;
}

/* 技能详情 */
.skill-detail {
  padding: 0 8px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  gap: 12px;
}

.detail-name {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin: 0;
  word-break: break-all;
}

.detail-badges {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #606266;
}

.system-prompt-box {
  background: #f5f7fa;
  border-radius: 6px;
  padding: 12px;
  max-height: 300px;
  overflow-y: auto;
}

.system-prompt-box pre {
  margin: 0;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 批量导入 */
.batch-import-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}

.batch-import-header p {
  margin: 0;
  font-size: 14px;
  color: #606266;
}

.batch-import-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.batch-import-item {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 12px;
  background: #fafafa;
  transition: border-color 0.2s;
}

.batch-import-item:hover {
  border-color: #409eff;
}

.import-skill-name {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  margin-left: 4px;
}

.import-skill-desc {
  margin: 6px 0 6px 24px;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.import-skill-tags {
  margin-left: 24px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.more-tags {
  font-size: 11px;
  color: #c0c4cc;
}

/* 响应式 */
@media (max-width: 768px) {
  .skills-grid {
    grid-template-columns: 1fr;
  }

  .page-header {
    flex-direction: column;
    gap: 16px;
    align-items: flex-start;
  }

  .header-right {
    width: 100%;
  }

  .header-right .el-input {
    flex: 1;
  }
}
</style>
