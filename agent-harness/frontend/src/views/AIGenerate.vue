<template>
  <div class="aigen">
    <!-- 顶部标题 + 阶段步骤条 -->
    <header class="aigen-top">
      <div class="top-row">
        <div class="top-left">
          <div class="mode-select">
            <el-icon class="mode-icon"><Collection /></el-icon>
            <label>生成用例类型</label>
            <el-select
              v-model="caseType"
              size="default"
              :disabled="streaming || messages.length > 0"
              popper-class="mode-popper"
              style="width: 150px"
            >
              <template #prefix>
                <el-icon class="select-prefix-icon"><component :is="currentModeIcon" /></el-icon>
              </template>
              <el-option
                v-for="opt in modeOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              >
                <span class="mode-option" :class="{ active: caseType === opt.value }">
                  <span class="mode-option-icon"><el-icon><component :is="opt.icon" /></el-icon></span>
                  <span class="mode-option-label">{{ opt.label }}</span>
                </span>
              </el-option>
            </el-select>
            <el-tooltip content="会话开始后不可切换，避免需求上下文混淆" placement="bottom">
              <el-icon class="info-icon"><InfoFilled /></el-icon>
            </el-tooltip>
          </div>

          <span class="model-tag">
            <el-icon><Cpu /></el-icon>
            AI 底座自动分配模型
          </span>
        </div>

        <div class="title-block">
          <h2>AI 用例共创</h2>
          <p>与 AI 对话澄清用户故事 → 实时生成用例草稿 → 确认保存入库</p>
        </div>
      </div>

      <div class="steps">
        <div class="step" :class="{ active: phase === 'field', done: fieldSchemaConfirmed }">
          <span class="dot">1</span><span class="label">确认字段</span>
        </div>
        <div class="step-line" :class="{ on: fieldSchemaConfirmed }" />
        <div class="step" :class="{ active: phase === 'clarify', done: phase === 'draft' }">
          <span class="dot">2</span><span class="label">澄清需求</span>
        </div>
        <div class="step-line" :class="{ on: phase === 'draft' }" />
        <div class="step" :class="{ active: phase === 'draft', done: saved }">
          <span class="dot">3</span><span class="label">生成&amp;保存</span>
        </div>
      </div>
    </header>

    <div class="aigen-body">
      <!-- 左侧：对话 -->
      <section class="panel chat-panel">
        <div class="panel-head">
          <span class="ph-icon">💬</span>
          <span>需求澄清 · AI 对话</span>
        </div>

        <div class="chat-body" ref="chatBody">
          <div v-if="!messages.length && !streamingText" class="chat-empty">
            <div class="empty-emoji">✨</div>
            <p>{{ fieldSchemaConfirmed ? `先描述你的${modeHint.title}` : '请先完成右侧步骤一：确认用例字段方案' }}</p>
            <p class="hint">
              {{ fieldSchemaConfirmed ? modeHint.hint : '勾选需要的字段、调整名称/类型/示例，点击“确认字段”后即可开始 AI 对话' }}
            </p>
          </div>

          <div v-for="(msg, i) in messages" :key="i" class="chat-msg" :class="msg.role">
            <div class="avatar" :class="msg.role">{{ msg.role === 'user' ? '我' : 'AI' }}</div>
            <div class="bubble-col">
              <div
                class="bubble"
                :class="{ 'md-bubble': msg.role === 'assistant' }"
                v-html="msg.role === 'assistant' ? formatMessage(msg.content) : escapeHtml(msg.content)"
              />
              <div v-if="msg.role === 'assistant' && resolveOptions(msg).length" class="msg-options">
                <template v-for="(opt, idx) in resolveOptions(msg)" :key="idx">
                  <el-button
                    v-if="!String(opt).startsWith('以上都不是')"
                    size="small"
                    type="primary"
                    plain
                    :disabled="streaming"
                    @click="sendMessage(opt)"
                  >
                    {{ opt }}
                  </el-button>
                  <el-button
                    v-else
                    size="small"
                    type="info"
                    plain
                    :disabled="streaming"
                    @click="promptCustomInput"
                  >
                    {{ opt }}
                  </el-button>
                </template>
              </div>
            </div>
          </div>

          <div ref="bottomAnchor" />

          <!-- 深度思考提示：仅展示，不进入消息记录 -->
          <div v-if="reasoningVisible" class="reasoning-bar">
            <div class="reasoning-card">
              <span class="reasoning-pulse" />
              <span class="reasoning-title">深度思考</span>
              <span class="reasoning-text">{{ reasoningText }}</span>
            </div>
          </div>
        </div>

        <div class="chat-input">
          <el-input
            v-model="chatInput"
            type="textarea"
            :rows="3"
            :disabled="streaming || !fieldSchemaConfirmed"
            :placeholder="fieldSchemaConfirmed ? modeHint.placeholder : '请先确认右侧用例字段方案，再开始对话'"
            @compositionstart="isComposing = true"
            @compositionend="isComposing = false; compositionJustEndedAt = Date.now()"
            @keydown.enter.exact.prevent="handleEnter($event)"
          />
          <div class="chat-actions">
            <el-button @click="resetSession" :disabled="streaming" plain>重置会话</el-button>
            <el-tooltip v-if="!fieldSchemaConfirmed" content="请先确认右侧的用例字段方案">
              <el-button type="primary" :disabled="true">发送</el-button>
            </el-tooltip>
            <el-button v-else type="primary" native-type="button" @click="sendMessage()" :loading="streaming" :disabled="streaming">
              {{ streaming ? '生成中…' : '发送' }}
            </el-button>
          </div>
        </div>
      </section>

      <!-- 右侧：草稿 -->
      <section class="panel draft-panel">
        <div class="panel-head">
          <span class="ph-icon">📝</span>
          <span>{{ modeHint.draftTitle }}</span>
          <span class="count-badge">{{ draftCases.length }}</span>
          <el-tag v-if="draftCases.length" type="warning" effect="plain" size="small" round>待确认 / 可编辑</el-tag>
          <div class="head-actions" v-if="draftCases.length">
            <el-button size="small" text @click="selectAll">{{ allSelected ? '取消全选' : '全选' }}</el-button>
            <el-button size="small" type="primary" @click="saveSelected" :loading="saving">保存选中到{{ modeHint.saveTarget }}</el-button>
          </div>
        </div>

        <!-- 字段确认面板 -->
        <div v-if="!fieldSchemaConfirmed" class="field-confirm-panel">
          <div class="field-confirm-head">
            <span class="field-confirm-icon">🛠️</span>
            <div>
              <div class="field-confirm-title">步骤一：用例字段方案确认</div>
              <div class="field-confirm-sub">完成本步后，才能开始左侧 AI 对话澄清需求</div>
            </div>
          </div>

          <div class="field-step-bar">
            <div class="field-step active"><span class="field-step-num">1</span>确认字段</div>
            <div class="field-step-arrow">→</div>
            <div class="field-step"><span class="field-step-num">2</span>AI 澄清需求</div>
            <div class="field-step-arrow">→</div>
            <div class="field-step"><span class="field-step-num">3</span>生成草稿</div>
          </div>

          <el-table :data="fieldSchema" size="small" class="field-table" border>
            <el-table-column width="65" align="center" label="启用">
              <template #default="{ row }">
                <el-checkbox v-model="row.enabled" :disabled="row.fixed" />
              </template>
            </el-table-column>
            <el-table-column label="字段名" width="130">
              <template #default="{ row }">
                <el-input v-model="row.label" size="small" placeholder="显示名称" />
              </template>
            </el-table-column>
            <el-table-column label="类型" width="118">
              <template #default="{ row }">
                <el-select v-model="row.type" size="small" style="width: 100px" popper-class="field-type-popper">
                  <el-option v-for="t in typeOptions" :key="t.value" :label="t.label" :value="t.value" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="必填" width="60" align="center">
              <template #default="{ row }">
                <el-checkbox v-model="row.required" :disabled="row.fixed" />
              </template>
            </el-table-column>
            <el-table-column label="示例 / 默认值">
              <template #default="{ row }">
                <el-input v-model="row.example" size="small" placeholder="示例值，AI 会参考此格式生成" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="70" align="center">
              <template #default="{ $index, row }">
                <el-button v-if="!row.fixed" size="small" type="danger" text @click="removeField($index)">删除</el-button>
                <span v-else class="fixed-tag">固定</span>
              </template>
            </el-table-column>
          </el-table>
          <div class="field-confirm-actions">
            <el-button size="small" plain @click="addField">+ 添加字段</el-button>
            <div class="field-confirm-actions-right">
              <el-button size="small" text @click="initFieldSchema">恢复默认</el-button>
              <el-button size="small" type="primary" @click="confirmFieldSchema">确认字段，开始 AI 对话</el-button>
            </div>
          </div>
        </div>

        <div v-else-if="!draftCases.length" class="draft-empty">
          <el-empty :description="modeHint.emptyDesc" />
        </div>

        <div v-else class="draft-grid">
          <div
            v-for="(tc, index) in draftCases"
            :key="index"
            class="case-card"
            :class="{ checked: tc.selected }"
          >
            <div class="case-card-head">
              <el-checkbox v-model="tc.selected" />
              <span v-if="caseType === 'api'" class="method" :class="tc.method?.toLowerCase()">{{ tc.method }}</span>
              <span v-if="caseType === 'web'" class="method web">Web</span>
              <span v-if="caseType === 'performance'" class="method perf">Perf</span>
              <span v-if="caseType === 'manual'" class="method manual">手工</span>
              <el-tag size="small" :type="getPriorityType(tc.priority)" effect="dark" round>{{ tc.priority }}</el-tag>
              <el-button size="small" type="danger" link class="del" @click="removeCase(index)">删除</el-button>
            </div>

            <el-input v-model="tc.title" size="small" class="case-title" :placeholder="modeHint.titlePlaceholder" />

            <!-- API 字段 -->
            <el-descriptions v-if="caseType === 'api'" :column="1" size="small" border class="case-desc">
              <el-descriptions-item label="接口地址">
                <el-input v-model="tc.api_endpoint" size="small" />
              </el-descriptions-item>
              <el-descriptions-item label="方法">
                <el-select v-model="tc.method" size="small">
                  <el-option v-for="m in ['GET','POST','PUT','DELETE','PATCH']" :key="m" :label="m" :value="m" />
                </el-select>
              </el-descriptions-item>
              <el-descriptions-item label="优先级">
                <el-select v-model="tc.priority" size="small">
                  <el-option v-for="p in ['P0','P1','P2','P3','P4']" :key="p" :label="p" :value="p" />
                </el-select>
              </el-descriptions-item>
              <el-descriptions-item label="请求体">
                <el-input v-model="tc.request_body" type="textarea" :rows="2" size="small" />
              </el-descriptions-item>
              <el-descriptions-item label="预期响应">
                <el-input v-model="tc.expected_response" type="textarea" :rows="2" size="small" />
              </el-descriptions-item>
              <el-descriptions-item label="断言规则">
                <el-input v-model="tc.assertions" type="textarea" :rows="2" size="small" />
              </el-descriptions-item>
            </el-descriptions>

            <!-- Web 字段 -->
            <el-descriptions v-if="caseType === 'web'" :column="1" size="small" border class="case-desc">
              <el-descriptions-item label="页面 URL">
                <el-input v-model="tc.page_url" size="small" />
              </el-descriptions-item>
              <el-descriptions-item label="优先级">
                <el-select v-model="tc.priority" size="small">
                  <el-option v-for="p in ['P0','P1','P2','P3','P4']" :key="p" :label="p" :value="p" />
                </el-select>
              </el-descriptions-item>
              <el-descriptions-item label="操作步骤">
                <el-input v-model="tc.stepsText" type="textarea" :rows="3" size="small" placeholder="JSON 数组：action/selector/target/value/description" />
              </el-descriptions-item>
              <el-descriptions-item label="断言规则">
                <el-input v-model="tc.assertions" type="textarea" :rows="2" size="small" />
              </el-descriptions-item>
            </el-descriptions>

            <!-- 性能字段 -->
            <el-descriptions v-if="caseType === 'performance'" :column="1" size="small" border class="case-desc">
              <el-descriptions-item label="压测目标">
                <el-input v-model="tc.target_url" size="small" />
              </el-descriptions-item>
              <el-descriptions-item label="并发数">
                <el-input-number v-model="tc.concurrency" :min="1" :max="10000" size="small" />
              </el-descriptions-item>
              <el-descriptions-item label="持续时间(s)">
                <el-input-number v-model="tc.duration" :min="1" :max="3600" size="small" />
              </el-descriptions-item>
              <el-descriptions-item label="预热时间(s)">
                <el-input-number v-model="tc.ramp_up" :min="0" :max="600" size="small" />
              </el-descriptions-item>
              <el-descriptions-item label="场景脚本">
                <el-input v-model="tc.scenarioText" type="textarea" :rows="3" size="small" placeholder="JSON 数组：name/method/path/body" />
              </el-descriptions-item>
              <el-descriptions-item label="优先级">
                <el-select v-model="tc.priority" size="small">
                  <el-option v-for="p in ['P0','P1','P2','P3','P4']" :key="p" :label="p" :value="p" />
                </el-select>
              </el-descriptions-item>
            </el-descriptions>

            <!-- 手工字段 -->
            <div v-if="caseType === 'manual'" class="case-desc-grid">
              <div class="case-field">
                <label>前置条件</label>
                <el-input v-model="tc.preconditions" type="textarea" :rows="2" size="small" />
              </div>
              <div class="case-field">
                <label>预期结果</label>
                <el-input v-model="tc.expected_result" type="textarea" :rows="2" size="small" />
              </div>
              <div class="case-field span-2">
                <label>测试步骤</label>
                <el-input v-model="tc.stepsText" type="textarea" :rows="3" size="small" placeholder="JSON 数组：step/expected" />
              </div>
              <div class="case-field">
                <label>优先级</label>
                <el-select v-model="tc.priority" size="small" style="width: 100%;">
                  <el-option v-for="p in ['P0','P1','P2','P3','P4']" :key="p" :label="p" :value="p" />
                </el-select>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch } from 'vue'
import { testcaseAPI, webTestcaseAPI, perfAPI } from '@/api'
import { ElMessage } from 'element-plus'
import { Collection, InfoFilled, Cpu, Link, Monitor, Lightning, SetUp } from '@element-plus/icons-vue'

const modeOptions = [
  { value: 'manual', label: '手工测试', icon: SetUp },
  { value: 'api', label: '接口测试', icon: Link },
  { value: 'web', label: 'Web 自动化', icon: Monitor },
  { value: 'performance', label: '性能测试', icon: Lightning },
]

const caseType = ref('manual')
const currentModeIcon = computed(() => modeOptions.find(o => o.value === caseType.value)?.icon || Collection)

const modeHint = computed(() => {
  const map = {
    api: {
      title: '接口需求',
      hint: '描述接口地址、请求方法、参数与预期响应，AI 会帮你澄清边界与异常场景。',
      placeholder: '回车发送（Shift+Enter 换行）。例如：登录失败返回 401，需覆盖账号锁定场景',
      draftTitle: '接口用例草稿',
      saveTarget: '接口用例库',
      titlePlaceholder: '接口用例标题',
      emptyDesc: 'AI 正在澄清需求，生成的接口用例会显示在这里，供你选择/修改',
    },
    web: {
      title: 'Web 测试场景',
      hint: '描述页面 URL、操作路径、校验点，AI 会生成操作步骤与断言。',
      placeholder: '例如：在登录页输入错误密码 5 次后，页面应提示账号锁定',
      draftTitle: 'Web 用例草稿',
      saveTarget: 'Web 用例库',
      titlePlaceholder: 'Web 用例标题',
      emptyDesc: 'AI 正在澄清需求，生成的 Web 用例会显示在这里，供你选择/修改',
    },
    performance: {
      title: '性能压测目标',
      hint: '描述压测接口、并发、持续时长、关注指标，AI 会生成压测方案。',
      placeholder: '例如：对 /api/v1/orders 做 100 并发、持续 60 秒压测，观察 P95 与错误率',
      draftTitle: '性能方案草稿',
      saveTarget: '性能测试库',
      titlePlaceholder: '压测方案名称',
      emptyDesc: 'AI 正在澄清需求，生成的性能方案会显示在这里，供你选择/修改',
    },
    manual: {
      title: '业务手工测试场景',
      hint: '描述业务操作、前置条件、操作步骤、预期结果，AI 会生成手工用例。',
      placeholder: '例如：用户下单后取消订单，库存应回滚，订单状态变为已取消',
      draftTitle: '手工用例草稿',
      saveTarget: '用例库（手工）',
      titlePlaceholder: '手工用例标题',
      emptyDesc: 'AI 正在澄清需求，生成的手工用例会显示这里，供你选择/修改',
    },
  }
  return map[caseType.value] || map.api
})

// 用例字段方案
const defaultFieldSchemas = {
  manual: [
    { name: 'title', label: '用例标题', type: 'string', required: true, example: '用户下单后取消订单', enabled: true, fixed: true },
    { name: 'preconditions', label: '前置条件', type: 'text', required: false, example: '用户已登录，商品库存充足', enabled: true },
    { name: 'steps', label: '测试步骤', type: 'json', required: true, example: '1. 进入商品详情页\\n2. 点击立即购买\\n3. 提交订单', enabled: true },
    { name: 'expected_result', label: '预期结果', type: 'text', required: true, example: '订单状态变为已取消，库存回滚', enabled: true },
    { name: 'priority', label: '优先级', type: 'enum', required: true, example: 'P0/P1/P2/P3/P4', enabled: true, fixed: true },
  ],
  api: [
    { name: 'title', label: '用例标题', type: 'string', required: true, example: '登录接口-密码错误', enabled: true, fixed: true },
    { name: 'api_endpoint', label: '接口地址', type: 'string', required: true, example: '/api/v1/auth/login', enabled: true },
    { name: 'method', label: '请求方法', type: 'enum', required: true, example: 'POST', enabled: true },
    { name: 'headers', label: '请求头', type: 'json', required: false, example: '{"Content-Type":"application/json"}', enabled: true },
    { name: 'request_body', label: '请求体', type: 'json', required: false, example: '{"username":"test"}', enabled: true },
    { name: 'expected_response', label: '预期响应', type: 'json', required: true, example: '{"code":401}', enabled: true },
    { name: 'assertions', label: '断言规则', type: 'json', required: true, example: '["状态码=401"]', enabled: true },
    { name: 'priority', label: '优先级', type: 'enum', required: true, example: 'P0-P4', enabled: true, fixed: true },
  ],
  web: [
    { name: 'title', label: '用例标题', type: 'string', required: true, example: '登录页-错误密码锁定', enabled: true, fixed: true },
    { name: 'page_url', label: '页面 URL', type: 'string', required: true, example: '/login', enabled: true },
    { name: 'steps', label: '操作步骤', type: 'json', required: true, example: '[{"action":"input","selector":"#username","target":"test"}]', enabled: true },
    { name: 'assertions', label: '断言规则', type: 'json', required: true, example: '["页面提示账号锁定"]', enabled: true },
    { name: 'priority', label: '优先级', type: 'enum', required: true, example: 'P0-P4', enabled: true, fixed: true },
  ],
  performance: [
    { name: 'title', label: '方案名称', type: 'string', required: true, example: '下单接口压测', enabled: true, fixed: true },
    { name: 'target_url', label: '压测目标', type: 'string', required: true, example: '/api/v1/orders', enabled: true },
    { name: 'concurrency', label: '并发数', type: 'number', required: true, example: '100', enabled: true },
    { name: 'duration', label: '持续时间(s)', type: 'number', required: true, example: '60', enabled: true },
    { name: 'ramp_up', label: '预热时间(s)', type: 'number', required: false, example: '10', enabled: true },
    { name: 'scenario', label: '场景脚本', type: 'json', required: true, example: '[{"name":"下单","method":"POST","path":"/orders"}]', enabled: true },
    { name: 'priority', label: '优先级', type: 'enum', required: true, example: 'P0-P4', enabled: true, fixed: true },
  ],
}
const typeOptions = [
  { value: 'string', label: '文本' },
  { value: 'text', label: '长文本' },
  { value: 'json', label: 'JSON' },
  { value: 'number', label: '数字' },
  { value: 'enum', label: '枚举' },
  { value: 'boolean', label: '布尔' },
]

const fieldSchema = ref([])
const fieldSchemaConfirmed = ref(false)
const initFieldSchema = () => {
  fieldSchema.value = JSON.parse(JSON.stringify(defaultFieldSchemas[caseType.value] || defaultFieldSchemas.manual))
  fieldSchemaConfirmed.value = false
}
watch(caseType, initFieldSchema, { immediate: true })

const addField = () => {
  fieldSchema.value.push({
    name: `custom_${Date.now()}`,
    label: '',
    type: 'string',
    required: false,
    example: '',
    enabled: true,
    fixed: false,
  })
}
const removeField = (index) => {
  fieldSchema.value.splice(index, 1)
}

const confirmFieldSchema = () => {
  const enabled = fieldSchema.value.filter(f => f.enabled)
  if (!enabled.length) {
    ElMessage.warning('请至少启用一个字段')
    return
  }
  const emptyLabel = enabled.find(f => !f.label?.trim())
  if (emptyLabel) {
    ElMessage.warning('已启用字段的“字段名”不能为空')
    return
  }
  fieldSchemaConfirmed.value = true
  // 字段方案已通过 payload.field_schema 传给后端，不需要在聊天区展示这条系统消息
  sendMessage('__AUTO__')
}

// 对话状态
const messages = ref([])
const chatInput = ref('')
const streaming = ref(false)
const streamingText = ref('')
// 防止快速双击/回车+点击导致 sendMessage 并发执行
let sendMessageLock = false
let isComposing = false
let compositionJustEndedAt = 0
let lastSentText = ''
let lastSentAt = 0
const chatBody = ref(null)

// 深度思考提示（仅展示，不进入消息记录）
const reasoningVisible = ref(false)
const reasoningText = ref('')
const reasoningSteps = computed(() => [
  '理解需求背景与测试目标…',
  `分析${modeHint.value.title}的关键字段与约束…`,
  '枚举正例、边界与反例场景…',
  '组织用例结构并生成草稿…',
])
let reasoningTimer = null
const startReasoning = () => {
  if (reasoningTimer) clearInterval(reasoningTimer)
  reasoningVisible.value = true
  let i = 0
  reasoningText.value = reasoningSteps.value[i]
  reasoningTimer = setInterval(() => {
    i = (i + 1) % reasoningSteps.value.length
    reasoningText.value = reasoningSteps.value[i]
  }, 1400)
}
const stopReasoning = () => {
  reasoningVisible.value = false
  if (reasoningTimer) {
    clearInterval(reasoningTimer)
    reasoningTimer = null
  }
}

// 草稿
const draftCases = ref([])
const saving = ref(false)
const saved = ref(false)

const allSelected = computed(() => draftCases.value.length > 0 && draftCases.value.every(tc => tc.selected))
const sessionId = ref('')
const requirementStored = ref('')

const phase = computed(() => {
  if (!fieldSchemaConfirmed.value) return 'field'
  return draftCases.value.length ? 'draft' : 'clarify'
})

async function scrollChat() {
  nextTick(() => {
    if (chatBody.value) chatBody.value.scrollTop = chatBody.value.scrollHeight
  })
}

function escapeHtml(text) {
  if (typeof text !== 'string') return String(text)
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function formatMessage(content) {
  if (!content) return ''
  let text = String(content)
  text = text.replace(/\\n/g, '\n').replace(/\\t/g, '\t').replace(/\\r/g, '').replace(/\\"/g, '"')
  const codeBlocks = []
  text = text.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
    const placeholder = `__CODE_${codeBlocks.length}__`
    codeBlocks.push(`<pre class="md-code" data-lang="${lang || 'text'}"><code>${escapeHtml(code.trim())}</code></pre>`)
    return placeholder
  })
  text = text.replace(/`([^`]+)`/g, '<code>$1</code>')
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  text = text.replace(/^### (.+)$/gm, '<h5>$1</h5>')
  text = text.replace(/^## (.+)$/gm, '<h4>$1</h4>')
  text = text.replace(/^# (.+)$/gm, '<h3>$1</h3>')
  text = text.replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>')
  text = text.replace(/(<li>[\s\S]*?<\/li>\n?)+/g, m => '<ol>' + m.replace(/\n/g, '') + '</ol>')
  text = text.replace(/\n/g, '<br/>')
  codeBlocks.forEach((block, i) => { text = text.replace(`__CODE_${i}__`, block) })
  return text
}

// 兜底选项常量：用于引导用户在业务内容不在列表中时自行输入
const OTHER_OPTION = '以上都不是，请描述'

// 根据 AI 回复文本推导可点击选项（后端未返回 options 时的兜底）
function deriveOptions(reply) {
  if (!reply || typeof reply !== 'string') return []
  const r = reply
  // 1. 核心目标/测试目标
  if (/核心目标|核心场景|测试目标|业务目标|验证.*功能|验证.*场景/.test(r)) {
    return ['验证正常搜索功能', '验证筛选条件组合', '验证搜索结果排序', '验证空结果/无匹配', '验证搜索性能与边界', OTHER_OPTION]
  }
  // 2. 业务流程/场景
  if (/业务流程|业务场景|支付流程|下单流程|订单.*流程|退款流程|搜索流程|登录流程|注册流程|核心流程/.test(r)) {
    return ['用户下单流程', '订单取消流程', '商品搜索与筛选', '用户注册/登录', '支付流程', '退款流程', OTHER_OPTION]
  }
  // 3. 是否类
  if (/是否|要不要|需要吗|可以吗/.test(r)) {
    return ['是', '否', OTHER_OPTION]
  }
  // 4. 若 AI 追问极简流程之外的额外细节，不推选项
  if (/支付方式|支付渠道|验证.*环节|优先.*验证|哪个环节|用例标题|前置条件|测试步骤|预期结果|输入数据|操作步骤|执行步骤|筛选条件|组合方式|请确认以下信息|请补充以下信息/.test(r)) {
    return []
  }
  return []
}

// 选择最终展示的选项：如果后端返回的 options 与当前 reply 明显不匹配，
// 优先使用前端推导的选项，避免 AI 把比例选项错误绑定到流程问题上。
function resolveOptions(msg) {
  const backend = Array.isArray(msg.options) ? msg.options : []
  const derived = deriveOptions(msg.content)
  if (!backend.length) return derived
  if (!derived.length) return backend
  const backendSet = new Set(backend.map(String))
  const overlap = derived.some(opt => backendSet.has(String(opt)))
  if (!overlap) return derived
  return backend
}

// 当用户点击"以上都不是"时，聚焦输入框并给出输入引导
function promptCustomInput() {
  ElMessage.info('请在下方输入框中描述你的具体需求')
  nextTick(() => {
    const textarea = document.querySelector('.chat-input textarea')
    if (textarea) textarea.focus()
  })
}

// 映射 AI 返回的用例为本地草稿
function mapCases(list) {
  if (!Array.isArray(list)) return []
  const type = caseType.value
  return list.map(tc => {
    const base = {
      title: tc.title || tc.name || '',
      priority: tc.priority || 'P2',
      tags: Array.isArray(tc.tags) ? tc.tags : (tc.tags ? [tc.tags] : []),
      selected: true,
    }
    if (type === 'api') {
      return {
        ...base,
        api_endpoint: tc.api_endpoint || '',
        method: tc.method || 'GET',
        headers: typeof tc.headers === 'string' ? tc.headers : JSON.stringify(tc.headers || {}, null, 2),
        request_body: typeof tc.request_body === 'string' ? tc.request_body : JSON.stringify(tc.request_body || {}, null, 2),
        expected_response: typeof tc.expected_response === 'string' ? tc.expected_response : JSON.stringify(tc.expected_response || {}, null, 2),
        assertions: Array.isArray(tc.assertion_rules) ? JSON.stringify(tc.assertion_rules, null, 2) : (tc.assertion_rules || ''),
      }
    }
    if (type === 'web') {
      return {
        ...base,
        page_url: tc.page_url || '',
        project: tc.project || '',
        module: tc.module || '',
        stepsText: typeof tc.steps === 'string' ? tc.steps : JSON.stringify(tc.steps || [], null, 2),
        assertions: Array.isArray(tc.assertion_rules) ? JSON.stringify(tc.assertion_rules, null, 2) : (tc.assertion_rules || ''),
      }
    }
    if (type === 'performance') {
      return {
        ...base,
        name: tc.name || tc.title || '',
        target_url: tc.target_url || '',
        concurrency: Number(tc.concurrency) || 10,
        duration: Number(tc.duration) || 60,
        ramp_up: Number(tc.ramp_up) || 0,
        scenarioText: typeof tc.scenario === 'string' ? tc.scenario : JSON.stringify(tc.scenario || [], null, 2),
      }
    }
    if (type === 'manual') {
      return {
        ...base,
        project: tc.project || '',
        module: tc.module || '',
        preconditions: tc.preconditions || '',
        stepsText: typeof tc.steps === 'string' ? tc.steps : JSON.stringify(tc.steps || [], null, 2),
        expected_result: tc.expected_result || '',
      }
    }
    return base
  })
}

// 包装 enter 事件，避免中文输入法选词时重复触发
const handleEnter = (e) => {
  if (!e || e.key !== 'Enter') return
  // 输入法组合期间或刚结束 300ms 内忽略回车，防止 compositionend 后补发一次
  if (isComposing || Date.now() - compositionJustEndedAt < 300) return
  sendMessage()
}

// 发送消息
const sendMessage = async (overrideText = '') => {
  // 防止事件对象被当作消息文本传入（Vue 事件绑定误传 PointerEvent/KeyboardEvent）
  const safeOverride = typeof overrideText === 'string' ? overrideText : ''
  const isAuto = safeOverride === '__AUTO__'
  const text = isAuto ? '' : (safeOverride || chatInput.value.trim())
  if ((!isAuto && !text) || streaming.value || sendMessageLock) return

  // 最近 500ms 内已发送过相同内容，视为重复触发
  const now = Date.now()
  if (!isAuto && text === lastSentText && now - lastSentAt < 500) return

  sendMessageLock = true
  if (!isAuto && text) {
    lastSentText = text
    lastSentAt = now
    messages.value.push({ role: 'user', content: text })
    chatInput.value = ''
    if (!requirementStored.value) requirementStored.value = text
    await nextTick()
  }
  streaming.value = true
  streamingText.value = ''
  saved.value = false
  scrollChat()

  const payload = {
    session_id: sessionId.value,
    messages: messages.value,
    requirement: String(requirementStored.value ?? '').trim(),
    project: '',
    current_draft: draftCases.value.map(stripUI),
    instruction: String(isAuto ? '请基于已确认的字段方案，开始逐步澄清需求。' : text ?? '').trim(),
    model_id: '',
    case_type: caseType.value,
    field_schema: fieldSchemaConfirmed.value
      ? fieldSchema.value.filter(f => f.enabled).map(({ name, label, type, required, example }) => ({ name, label, type, required, example }))
      : [],
  }

  try {
    startReasoning()
    const res = await testcaseAPI.aiGenerateConversation(payload)
    if (!res.ok) {
      const errText = await res.text()
      throw new Error(errText || `请求失败：${res.status}`)
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buf = ''
    let doneEvent = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const parts = buf.split('\n\n')
      buf = parts.pop()
      for (const part of parts) {
        const line = part.replace(/^data:\s*/, '').trim()
        if (!line || line === '[DONE]') continue
        let evt
        try { evt = JSON.parse(line) } catch { continue }
        if (evt.type === 'meta') {
          sessionId.value = evt.session_id
        } else if (evt.type === 'token') {
          if (reasoningVisible.value) stopReasoning()
          streamingText.value += evt.content
          scrollChat()
        } else if (evt.type === 'done') {
          doneEvent = evt
        }
      }
    }

    if (doneEvent) {
      const reply = doneEvent.reply || ''
      const options = Array.isArray(doneEvent.options) ? doneEvent.options : undefined
      // 如果最后一条已经是相同内容的 assistant，则去重（防止 SSE 偶发重复 done）
      const lastMsg = messages.value[messages.value.length - 1]
      if (!lastMsg || lastMsg.role !== 'assistant' || lastMsg.content !== reply) {
        messages.value.push({ role: 'assistant', content: reply, options })
      } else if (options) {
        // 仅 options 有更新时也补上
        lastMsg.options = options
      }
      const incoming = Array.isArray(doneEvent.test_cases) ? doneEvent.test_cases : []
      if (incoming.length) {
        draftCases.value = mapCases(incoming)
        if (doneEvent.phase === 'draft') {
          ElMessage.success(`已生成/更新 ${draftCases.value.length} 条${modeHint.value.draftTitle.replace('草稿', '')}`)
        } else {
          ElMessage.info(`AI 返回 ${draftCases.value.length} 条试探性草稿，可右侧选择/修改`)
        }
      } else {
        ElMessage.info('AI 正在澄清需求，请继续补充')
      }
    }
  } catch (error) {
    console.error('Conversation error:', error)
    ElMessage.error('对话失败：' + (error.response?.data?.detail || error.message))
  } finally {
    stopReasoning()
    streaming.value = false
    streamingText.value = ''
    sendMessageLock = false
    scrollChat()
  }
}

function stringify(v) {
  if (typeof v === 'string') return v
  try { return JSON.stringify(v, null, 2) } catch { return String(v) }
}
function safeParse(v, fallback) {
  if (typeof v !== 'string') return v
  try { return JSON.parse(v) } catch { return fallback }
}

// 去掉 UI 字段，按模式转回后端结构
function stripUI(tc) {
  const type = caseType.value
  if (type === 'api') {
    return {
      title: tc.title,
      api_endpoint: tc.api_endpoint,
      method: tc.method,
      headers: safeParse(tc.headers, tc.headers),
      request_body: tc.request_body,
      expected_response: tc.expected_response,
      assertion_rules: safeParse(tc.assertions, tc.assertions),
      priority: tc.priority,
      tags: tc.tags,
    }
  }
  if (type === 'web') {
    return {
      title: tc.title,
      page_url: tc.page_url,
      project: tc.project || '',
      module: tc.module || '',
      steps: safeParse(tc.stepsText, []),
      assertion_rules: safeParse(tc.assertions, []),
      priority: tc.priority,
      tags: tc.tags,
    }
  }
  if (type === 'performance') {
    return {
      name: tc.name || tc.title,
      description: requirementStored.value,
      target_url: tc.target_url,
      concurrency: Number(tc.concurrency) || 10,
      duration: Number(tc.duration) || 60,
      ramp_up: Number(tc.ramp_up) || 0,
      scenario: safeParse(tc.scenarioText, []),
      status: 'draft',
      creator: '',
    }
  }
  if (type === 'manual') {
    return {
      title: tc.title,
      description: requirementStored.value,
      page_url: '',
      project: tc.project || '',
      module: tc.module || '',
      steps: safeParse(tc.stepsText, []),
      assertion_rules: [{ type: 'check_result', expected: tc.expected_result || '通过' }],
      priority: tc.priority,
      tags: tc.tags,
    }
  }
  return tc
}

const selectAll = () => {
  const next = !allSelected.value
  draftCases.value.forEach(tc => { tc.selected = next })
}

const removeCase = (i) => {
  draftCases.value.splice(i, 1)
}

const saveSelected = async () => {
  const selected = draftCases.value.filter(tc => tc.selected)
  if (!selected.length) {
    ElMessage.warning('请至少选择一个')
    return
  }
  saving.value = true
  try {
    let savedCount = 0
    for (const tc of selected) {
      const payload = stripUI(tc)
      if (caseType.value === 'api') {
        await testcaseAPI.create({
          title: payload.title,
          description: '',
          api_endpoint: payload.api_endpoint || '',
          method: payload.method || 'GET',
          headers: payload.headers || { 'Content-Type': 'application/json' },
          request_body: payload.request_body || '',
          expected_response: payload.expected_response || '',
          assertions: stringify(payload.assertion_rules) || '',
          priority: payload.priority || 'P2',
          status: 'draft',
          tags: payload.tags || [],
        })
      } else if (caseType.value === 'web') {
        await webTestcaseAPI.create({
          title: payload.title,
          description: '',
          page_url: payload.page_url || '',
          project: payload.project || '',
          module: payload.module || '',
          steps: payload.steps,
          assertion_rules: payload.assertion_rules,
          priority: payload.priority || 'P2',
          status: 'draft',
          tags: payload.tags || ['web', 'ai-generated'],
        })
      } else if (caseType.value === 'performance') {
        await perfAPI.createTestCase({
          name: payload.name,
          description: '',
          target_url: payload.target_url || '',
          concurrency: Number(payload.concurrency) || 10,
          duration: Number(payload.duration) || 60,
          ramp_up: Number(payload.ramp_up) || 0,
          scenario: payload.scenario,
          status: 'draft',
        })
      } else if (caseType.value === 'manual') {
        // 手工用例复用 web_testcases 表结构，标签标记 manual
        await webTestcaseAPI.create({
          title: payload.title,
          description: '',
          page_url: '',
          project: payload.project || '',
          module: payload.module || '',
          steps: payload.steps,
          assertion_rules: payload.assertion_rules,
          priority: payload.priority || 'P2',
          status: 'draft',
          tags: ['manual', 'ai-generated'],
        })
      }
      savedCount++
    }
    saved.value = true
    ElMessage.success(`成功保存 ${savedCount} 个到${modeHint.value.saveTarget}`)
  } catch (error) {
    console.error('Save error:', error)
    ElMessage.error('保存失败：' + (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
}

const resetSession = () => {
  sessionId.value = ''
  messages.value = []
  chatInput.value = ''
  draftCases.value = []
  requirementStored.value = ''
  saved.value = false
  fieldSchemaConfirmed.value = false
  initFieldSchema()
  ElMessage.info('会话已重置')
}

const getPriorityType = (priority) => {
  const types = { P0: 'danger', P1: 'warning', P2: '', P3: 'info', P4: 'info' }
  return types[priority] || ''
}
</script>

<style scoped>
.aigen {
  height: calc(100vh - 84px);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 4px 0;
}

.aigen-top {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 22px;
  background: linear-gradient(120deg, #4f46e5 0%, #7c3aed 100%);
  border-radius: 14px;
  color: #fff;
  box-shadow: 0 8px 24px rgba(79, 70, 229, 0.25);
}
.top-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.top-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.title-block h2 { margin: 0; font-size: 18px; font-weight: 700; }
.title-block p { margin: 4px 0 0; font-size: 12px; opacity: 0.85; }

.mode-select {
  display: flex; align-items: center; gap: 8px;
  background: rgba(255,255,255,0.18);
  padding: 6px 14px; border-radius: 12px;
}
.mode-select label { font-size: 12px; font-weight: 600; white-space: nowrap; }
.mode-icon { font-size: 15px; }
.info-icon { font-size: 14px; opacity: 0.8; cursor: pointer; }
.info-icon:hover { opacity: 1; }
.mode-select :deep(.el-input__wrapper) { background: #fff; }
.select-prefix-icon { color: #4f46e5; font-size: 15px; }

.mode-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 2px;
  border-radius: 6px;
  transition: background 0.15s;
}
.mode-option-icon {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  display: grid;
  place-items: center;
  background: #f3f4f6;
  color: #4b5563;
  font-size: 14px;
}
.mode-option-label { font-size: 13px; color: #1f2937; font-weight: 500; }
.mode-option.active .mode-option-icon { background: #eef2ff; color: #4f46e5; }
.mode-option.active .mode-option-label { color: #4f46e5; font-weight: 700; }

:global(.mode-popper) { border-radius: 10px !important; padding: 4px !important; }
:global(.mode-popper .el-select-dropdown__item) { padding: 6px 10px !important; border-radius: 6px; }
:global(.mode-popper .el-select-dropdown__item.selected) { background: #f5f3ff !important; font-weight: 700; }
:global(.mode-popper .el-select-dropdown__item.hover:not(.selected)) { background: #f9fafb !important; }

.steps { display: flex; align-items: center; justify-content: center; gap: 8px; }
.step { display: flex; align-items: center; gap: 8px; opacity: 0.6; transition: opacity 0.3s; }
.step.active, .step.done { opacity: 1; }
.dot {
  width: 26px; height: 26px; border-radius: 50%;
  display: grid; place-items: center;
  background: rgba(255, 255, 255, 0.25);
  font-size: 13px; font-weight: 700;
}
.step.active .dot { background: #fff; color: #4f46e5; }
.step.done .dot { background: #22c55e; color: #fff; }
.label { font-size: 13px; font-weight: 600; }
.step-line { flex: 0 0 36px; height: 2px; background: rgba(255,255,255,0.3); border-radius: 2px; }
.step-line.on { background: #22c55e; }

.model-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: rgba(255, 255, 255, 0.22);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 12px;
  border-radius: 20px;
}
.model-tag .el-icon { font-size: 13px; }

.aigen-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 14px;
}

@media (min-width: 1440px) {
  .aigen-body {
    grid-template-columns: 0.75fr 1.25fr;
  }
}

.panel {
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}
.panel-head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px;
  font-weight: 700;
  font-size: 14px;
  color: #1f2937;
  border-bottom: 1px solid #f0f0f3;
}
.ph-icon { font-size: 16px; }
.count-badge {
  background: #eef2ff; color: #4f46e5;
  font-size: 12px; font-weight: 700;
  border-radius: 10px; padding: 1px 9px;
}
.head-actions { margin-left: auto; display: flex; gap: 6px; }

.chat-panel { background: #fbfbfd; }
.chat-body {
  flex: 1; min-height: 0;
  overflow-y: auto;
  padding: 16px 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.chat-empty { margin: auto; text-align: center; color: #9ca3af; }
.chat-empty .empty-emoji { font-size: 34px; margin-bottom: 8px; }
.chat-empty p { margin: 4px 0; font-size: 13px; }
.chat-empty .hint { font-size: 12px; opacity: 0.8; max-width: 260px; }

.chat-msg { display: flex; gap: 10px; align-items: flex-start; }
.chat-msg.user { flex-direction: row-reverse; }
.avatar {
  flex-shrink: 0;
  width: 30px; height: 30px; border-radius: 8px;
  display: grid; place-items: center;
  font-size: 12px; font-weight: 700; color: #fff;
}
.avatar.user { background: #4f46e5; }
.avatar.assistant { background: #7c3aed; }
.bubble {
  max-width: 78%;
  padding: 10px 13px;
  border-radius: 12px;
  font-size: 13px; line-height: 1.7;
  white-space: pre-wrap; word-break: break-all;
}
.chat-msg.user .bubble { background: #4f46e5; color: #fff; border-top-right-radius: 2px; display: inline-block; width: fit-content; max-width: 78%; word-break: keep-all; }
.chat-msg.assistant .bubble { background: #fff; border: 1px solid #ececf2; color: #374151; border-top-left-radius: 2px; }
.bubble-col { display: flex; flex-direction: column; gap: 8px; width: 100%; max-width: calc(100% - 46px); }
.chat-msg.user .bubble-col { align-items: flex-end; }
.msg-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-left: 6px;
}
.msg-options .el-button { border-radius: 16px; padding: 6px 14px; font-size: 12px; }
.md-bubble { line-height: 1.8; }
.md-bubble h3 { margin: 10px 0 6px; font-size: 15px; }
.md-bubble h4 { margin: 8px 0 4px; font-size: 14px; }
.md-bubble h5 { margin: 6px 0 4px; font-size: 13px; }
.md-bubble ol { margin: 6px 0; padding-left: 20px; }
.md-bubble li { margin: 3px 0; }
.md-bubble strong { color: #111827; }
.md-bubble code {
  background: #f3f4f6; color: #ef4444; padding: 1px 5px; border-radius: 4px; font-size: 12px;
}
.md-bubble .md-code {
  background: #1f2937; color: #e5e7eb; padding: 8px 10px; border-radius: 6px; overflow-x: auto; margin: 6px 0;
}
.md-bubble .md-code code { background: transparent; color: inherit; }
.cursor { animation: blink 1s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }

.typing-dot {
  display: inline-block;
  width: 6px; height: 6px; border-radius: 50%;
  background: #a78bfa; margin: 0 2px;
  animation: typing 1.4s infinite ease-in-out both;
}
.typing-dot:nth-child(1) { animation-delay: -0.32s; }
.typing-dot:nth-child(2) { animation-delay: -0.16s; }
@keyframes typing {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.reasoning-bar {
  display: flex;
  justify-content: flex-start;
  margin-top: 8px;
}
.reasoning-card {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  max-width: 88%;
  padding: 10px 14px;
  border-radius: 14px 14px 14px 4px;
  background: linear-gradient(135deg, #f5f3ff 0%, #eef2ff 100%);
  border: 1px solid #e0e7ff;
  box-shadow: 0 4px 14px rgba(79, 70, 229, 0.1);
}
.reasoning-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  flex-shrink: 0;
  animation: pulse 1.4s infinite ease-in-out;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.85); }
}
.reasoning-title {
  font-size: 12px;
  font-weight: 700;
  color: #4f46e5;
  letter-spacing: 0.3px;
  flex-shrink: 0;
}
.reasoning-text {
  font-size: 13px;
  color: #4b5563;
}

.chat-input { flex-shrink: 0; padding: 12px 14px; border-top: 1px solid #f0f0f3; background: #fff; }
.chat-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }

.draft-empty { flex: 1; display: grid; place-items: center; }
.field-confirm-panel {
  margin: 14px;
  padding: 14px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.04);
}
.field-confirm-head {
  display: flex; align-items: flex-start; gap: 10px;
  margin-bottom: 12px;
}
.field-confirm-icon { font-size: 20px; }
.field-confirm-title { font-size: 15px; font-weight: 700; color: #1f2937; }
.field-confirm-sub { font-size: 12px; color: #6b7280; margin-top: 2px; }
.field-table { margin-bottom: 12px; }
.field-confirm-actions { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.field-confirm-actions-right { display: flex; gap: 8px; }
.fixed-tag { font-size: 12px; color: #9ca3af; }

.field-step-bar {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 14px; padding: 10px 12px;
  background: #f9fafb; border-radius: 10px;
}
.field-step {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: #6b7280; font-weight: 600;
}
.field-step.active { color: #4f46e5; }
.field-step-num {
  width: 20px; height: 20px; border-radius: 50%;
  display: grid; place-items: center;
  background: #e5e7eb; color: #374151; font-size: 11px;
}
.field-step.active .field-step-num { background: #4f46e5; color: #fff; }
.field-step-arrow { color: #d1d5db; font-size: 12px; }

.field-type-popper { min-width: 100px !important; z-index: 9999 !important; }
.field-type-popper .el-select-dropdown__item { padding: 0 12px; font-size: 13px; }
.draft-grid {
  flex: 1; min-height: 0;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 14px;
  display: flex;
  gap: 14px;
  align-items: stretch;
}
.case-card {
  flex: 0 0 360px;
  max-width: 360px;
  border: 1px solid #eef0f4;
  border-radius: 12px;
  padding: 12px;
  background: #fff;
  transition: border-color 0.2s, box-shadow 0.2s;
  display: flex;
  flex-direction: column;
}
.case-card.checked { border-color: #4f46e5; box-shadow: 0 0 0 2px rgba(79,70,229,0.12); }
.case-card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.method {
  font-size: 11px; font-weight: 700; padding: 1px 7px; border-radius: 6px;
  background: #f3f4f6; color: #374151;
}
.method.get { background: #ecfdf5; color: #059669; }
.method.post { background: #eff6ff; color: #2563eb; }
.method.put { background: #fffbeb; color: #d97706; }
.method.delete { background: #fef2f2; color: #dc2626; }
.method.patch { background: #f5f3ff; color: #7c3aed; }
.method.web { background: #ede9fe; color: #7c3aed; }
.method.perf { background: #fff7ed; color: #ea580c; }
.method.manual { background: #ecfeff; color: #0891b8; }
.del { margin-left: auto; }
.case-title { margin-bottom: 10px; }
.case-desc :deep(.el-descriptions__label) { width: 70px; color: #6b7280; }

/* 横向双列字段网格 */
.case-desc-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px 12px;
}
.case-desc-grid .case-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.case-desc-grid .case-field.span-2 {
  grid-column: span 2;
}
.case-desc-grid .case-field > label {
  font-size: 12px;
  color: #6b7280;
  line-height: 1.2;
}
.case-desc-grid .case-field :deep(.el-textarea__inner) {
  min-height: 54px !important;
}
</style>
