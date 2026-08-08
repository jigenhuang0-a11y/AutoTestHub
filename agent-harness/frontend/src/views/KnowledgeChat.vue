<template>
  <div class="knowledge-chat-container">
    <!-- 顶部导航 -->
    <div class="chat-header">
      <div class="header-actions" style="margin-left: auto; display: flex; gap: 8px;">
        <el-button 
          v-if="qaMode === 'knowledge'"
          size="small" 
          @click="showDocumentDialog"
        >
          <el-icon><Document /></el-icon> 文档管理
        </el-button>
        <el-upload
          v-if="qaMode === 'knowledge'"
          :show-file-list="false"
          :before-upload="handleUpload"
          accept=".pdf,.docx,.txt"
        >
          <el-button size="small" type="primary">
            <el-icon><Upload /></el-icon> 上传文档
          </el-button>
        </el-upload>
      </div>
    </div>

    <div class="chat-content">
      <!-- 左侧：历史对话列表 -->
      <div class="history-panel-wrapper" :class="{ collapsed: historyCollapsed }">
        <div v-if="historyCollapsed" class="history-collapsed-bar" @click="toggleHistoryPanel">
          <el-icon :size="18"><ArrowLeft /></el-icon>
        </div>
        <div v-else class="history-panel-expanded">
          <div class="history-panel-header-compact">
            <span class="history-panel-title">历史记录</span>
            <el-button size="small" text @click="toggleHistoryPanel">
              <el-icon><ArrowLeft /></el-icon>
            </el-button>
          </div>
          <ChatHistoryPanel
            :groups="groupedHistory"
            :active-id="currentMessageId"
            :selected-ids="selectedMessages"
            :loading="historyLoading"
            :error="historyLoadError"
            :mode="qaMode"
            @select-message="selectMessage"
            @toggle-select="toggleSelect"
            @toggle-select-all="toggleSelectAll"
            @delete-message="deleteMessage"
            @batch-delete="batchDelete"
            @retry="loadChatHistory"
          />
        </div>
      </div>

      <!-- 右侧：对话区域 -->
      <div class="chat-panel">
        <!-- 消息列表 -->
        <div class="message-list" ref="messageListRef">
          <!-- 工作流实时进度面板 -->
          <WorkflowTimeline
            v-if="qaMode === 'workflow' && (answering || workflowSteps.length > 0)"
            :steps="workflowSteps"
            :running="answering"
            :done="workflowDone"
            :has-error="workflowError"
            :result="workflowDone && workflowResult ? formatMessage(workflowResult) : ''"
            :elapsed-seconds="elapsedTime"
            :completed-count="workflowCompletedCount"
            @stop="stopWorkflow"
          />

          <div v-if="kbNotFound" class="welcome-message">
            <div class="welcome-content">
              <div class="welcome-icon icon-knowledge">
                <el-icon :size="60"><Reading /></el-icon>
              </div>
              <h3>暂无可用知识库</h3>
              <p>您当前没有可访问的知识库</p>
              <el-button type="primary" size="default" style="margin-top: 12px;" @click="createNewKB">
                <el-icon><Plus /></el-icon> 创建知识库
              </el-button>
            </div>
          </div>
          <div v-else-if="messages.length === 0 && !answering" class="welcome-message">
            <div class="welcome-content">
              <div class="welcome-icon" :class="qaMode === 'chat' ? 'icon-chat' : 'icon-knowledge'">
                <el-icon v-if="qaMode === 'chat'" :size="60"><ChatDotRound /></el-icon>
                <el-icon v-else :size="60"><Reading /></el-icon>
              </div>
              <h3>{{ qaMode === 'chat' ? '欢迎使用 AI 问答' : '欢迎使用知识库问答' }}</h3>
              <p>{{ qaMode === 'chat' ? '我是您的AI助手，可以帮您解答问题、编写代码、分析数据等' : '请先上传测试文档，然后可以开始提问' }}</p>
            </div>
          </div>
          
          <div v-for="(msg, index) in messages" :key="index" class="message-item" :class="{ 'user-message': msg.isUser }">
            <div class="message-avatar">
              <!-- AI助手头像 - 科技感渐变圆形 -->
              <div v-if="!msg.isUser" class="avatar-ai">
                <el-icon :size="24"><Reading /></el-icon>
              </div>
              <!-- 用户头像 - 柴犬形象 -->
              <div v-else class="avatar-user">
                🐕
              </div>
            </div>
            <div class="message-content">
              <!-- AI 回答元信息行：Skill + 响应耗时 -->
              <div v-if="!msg.isUser && (msg.skill || msg.responseTime)" class="message-meta-row">
                <el-tag v-if="msg.skill" size="small" type="success" effect="light">
                  <el-icon><SetUp /></el-icon> {{ msg.skill }}
                </el-tag>
                <span v-if="msg.responseTime" class="message-meta-time">
                  <el-icon><Timer /></el-icon> {{ formatResponseTime(msg.responseTime) }}
                </span>
              </div>
              <div v-if="msg.isUser" class="message-text">
                <div v-if="msg.images && msg.images.length > 0" class="message-images">
                  <img v-for="(img, i) in msg.images" :key="i" :src="img" class="message-image" />
                </div>
                {{ msg.content }}
              </div>
              <!-- 用户消息操作栏：复制 -->
              <div v-if="msg.isUser" class="message-user-actions">
                <el-button
                  size="small"
                  text
                  class="copy-msg-btn"
                  @click="copyMessageContent(msg.content)"
                >
                  <el-icon><CopyDocument /></el-icon>
                  <span class="copy-btn-text">复制</span>
                </el-button>
              </div>
              <div v-else class="message-text ai-message-bubble" v-html="formatMessage(msg.content)"></div>
              <!-- AI 思考过程折叠面板（历史消息中可展开查看） -->
              <div v-if="!msg.isUser && (msg.thinkingProcess?.length || msg.reasoningText)" class="message-thinking-collapse">
                <el-collapse>
                  <el-collapse-item>
                    <template #title>
                      <span class="thinking-collapse-title">
                        深度思考 {{ msg.thinkingProcess?.length ? '(' + msg.thinkingProcess.length + ' 步)' : '' }}
                        <el-tag size="small" type="success" class="thinking-response-tag">{{ formatDuration(msg.responseTime / 1000) }}</el-tag>
                      </span>
                    </template>
                    <div v-if="msg.reasoningText" class="thinking-history-steps">
                      <div class="reasoning-text-area reasoning-done" style="margin-top: 0;">
                        <div class="reasoning-text-content" v-html="formatMessage(msg.reasoningText)"></div>
                      </div>
                    </div>
                    <div v-else class="thinking-history-steps">
                      <div 
                        v-for="(step, idx) in msg.thinkingProcess" 
                        :key="idx" 
                        class="thinking-history-item"
                      >
                        <span class="step-check-done">✓</span>
                        <span class="step-text-done">{{ step }}</span>
                      </div>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>
              <!-- AI 消息底部操作栏：下载按钮 -->
              <div v-if="!msg.isUser && hasExtractableData(msg.content)" class="message-download-bar">
                <el-dropdown split-button size="small" type="primary" @click="downloadTestData(msg, 'json')">
                  <el-icon><Download /></el-icon> 测试数据 (JSON)
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item @click="downloadTestData(msg, 'json')">
                        <el-icon><Document /></el-icon> 导出为 JSON
                      </el-dropdown-item>
                      <el-dropdown-item @click="downloadTestData(msg, 'csv')">
                        <el-icon><Document /></el-icon> 导出为 CSV
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <el-dropdown split-button size="small" type="success" @click="downloadFullDocument(msg, 'excel')">
                  <el-icon><Download /></el-icon> 完整文档 (Excel)
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item @click="downloadFullDocument(msg, 'excel')">
                        <el-icon><Document /></el-icon> 导出为 Excel
                      </el-dropdown-item>
                      <el-dropdown-item @click="downloadFullDocument(msg, 'word')">
                        <el-icon><Document /></el-icon> 导出为 Word
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
              <div v-if="msg.contextDocs && msg.contextDocs.length > 0" class="message-context">
                <el-collapse>
                  <el-collapse-item title="参考文档片段">
                    <div v-for="(ctx, i) in msg.contextDocs" :key="i" class="context-item">
                      <el-tag size="small" type="info">片段 {{ i + 1 }}</el-tag>
                      <p>{{ ctx.content }}</p>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </div>
          </div>
          
          <!-- 流式输出中：实时显示AI回答 + 思考过程 + 计时器 + 停止按钮 -->
          <div v-if="answering && streamingText.length > 0" class="message-item">
            <div class="message-avatar">
              <div class="avatar-ai">
                <el-icon :size="24"><Reading /></el-icon>
              </div>
            </div>
            <div class="message-content">
              <!-- 思考过程面板：状态步骤 + 真实推理文本（始终在流式文字上方） -->
              <div v-if="thinkingSteps.length > 0 || streamingReasoning" class="thinking-steps-panel streaming-thinking-panel">
                <div class="thinking-panel-header">
                  <span class="thinking-panel-title">深度思考</span>
                  <span class="thinking-panel-timer">{{ formatDuration(elapsedTime) }}</span>
                </div>
                <div 
                  v-for="(step, idx) in thinkingSteps" 
                  :key="idx" 
                  class="thinking-step-item step-completed"
                >
                  <span class="step-icon">
                    <span class="step-check">✓</span>
                  </span>
                  <span class="step-text">{{ step }}</span>
                </div>
                <div v-if="streamingReasoning" class="reasoning-text-area reasoning-done">
                  <div class="reasoning-text-content" v-html="formatMessage(streamingReasoning)"></div>
                </div>
              </div>
              <!-- AI 回答正文 -->
              <div class="message-text ai-message-bubble" v-html="formatMessage(streamingText)"></div>
              <div class="streaming-footer">
                <span class="streaming-timer">
                  <span class="timer-dot"></span>
                  {{ formatDuration(elapsedTime) }}
                </span>
                <span class="streaming-cursor">▊</span>
              </div>
              <div class="streaming-actions">
                <el-button 
                  size="small" 
                  type="danger" 
                  plain
                  @click="stopStreaming"
                  class="stop-stream-btn"
                >
                  <el-icon><Close /></el-icon>
                  停止生成
                </el-button>
              </div>
            </div>
          </div>
          
          <!-- 思考过程 / 加载中提示（尚未收到任何 token）+ 停止按钮 -->
          <div v-if="answering && streamingText.length === 0" class="message-item" role="status" aria-live="polite" aria-label="AI正在思考">
            <div class="message-avatar">
              <div class="avatar-ai">
                <el-icon :size="24" aria-hidden="true"><Reading /></el-icon>
              </div>
            </div>
            <div class="message-content">
              <!-- 思考过程面板（加载中）：状态步骤 + 真实推理文本流式输出 -->
              <div v-if="thinkingSteps.length > 0" class="thinking-steps-panel loading-thinking-panel">
                <div class="thinking-panel-header">
                  <span class="thinking-panel-title">深度思考</span>
                  <span class="thinking-panel-timer">{{ formatDuration(elapsedTime) }}</span>
                </div>
                <!-- 状态步骤列表 -->
                <div 
                  v-for="(step, idx) in thinkingSteps" 
                  :key="idx" 
                  class="thinking-step-item"
                  :class="{ 'step-completed': idx < thinkingSteps.length - 1, 'step-active': idx === thinkingSteps.length - 1 }"
                >
                  <span class="step-icon">
                    <span v-if="idx < thinkingSteps.length - 1" class="step-check">✓</span>
                    <span v-else class="step-spinner"></span>
                  </span>
                  <span class="step-text">{{ step }}</span>
                </div>
                <!-- 真实推理文本（模型输出） -->
                <div v-if="streamingReasoning" class="reasoning-text-area">
                  <div class="reasoning-text-content" v-html="formatMessage(streamingReasoning)"></div>
                  <span v-if="!streamingText" class="reasoning-cursor">▊</span>
                </div>
              </div>
              <!-- 无思考步骤时的回退显示 -->
              <div v-else class="thinking-indicator">
                <div class="thinking-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <span class="thinking-text">{{ currentThinkingStatus }}</span>
                <span class="thinking-timer">{{ formatDuration(elapsedTime) }}</span>
              </div>
              <div class="streaming-actions" style="margin-top: 8px;">
                <el-button 
                  size="small" 
                  type="danger" 
                  plain
                  @click="stopStreaming"
                  class="stop-stream-btn"
                >
                  <el-icon><Close /></el-icon>
                  停止生成
                </el-button>
              </div>
            </div>
          </div>
        </div>

        <!-- 输入框 -->
        <div class="input-area">
          <div class="input-toolbar">
            <!-- 左侧按钮组：模式切换 + 新对话 -->
            <div class="toolbar-left">
              <ModeSwitcher :active="qaMode" @switch="switchMode" />
              
              <!-- 深度思考 / 快速模式切换：仅在日常对话模式下显示 -->
              <el-button
                v-if="qaMode === 'chat'"
                :class="['reasoning-toggle-btn', reasoningMode === 'reasoning' ? 'is-reasoning' : '']"
                size="small"
                :type="reasoningMode === 'reasoning' ? 'warning' : ''"
                @click="toggleReasoningMode"
                :title="reasoningMode === 'reasoning' ? '当前为深度思考模式（较慢）' : '当前为快速模式'"
              >
                <el-icon><Opportunity /></el-icon>
                {{ reasoningMode === 'reasoning' ? '深度思考' : '快速' }}
              </el-button>
              
              <!-- 新对话按钮 - 扁平化设计 -->
              <el-button 
                class="new-chat-btn-flat" 
                size="small"
                @click="startNewChat"
              >
                <el-icon><Plus /></el-icon> 新对话
              </el-button>
            </div>
            
            <!-- 右侧：Skill 选择器，仅在日常对话模式下显示 -->
            <div v-if="qaMode === 'chat'" class="toolbar-right">
              <el-dropdown
                trigger="click"
                placement="top-end"
                :disabled="skills.length === 0"
                @visible-change="(visible) => { showSkillSelector = visible }"
              >
                <el-button
                  size="small"
                  :type="activeSkill ? 'success' : ''"
                  class="skill-selector-btn"
                  :disabled="skills.length === 0"
                >
                  <el-icon><SetUp /></el-icon>
                  {{ activeSkill ? activeSkill.name : (skills.length > 0 ? '选择 Skill' : '加载中...') }}
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu class="skill-dropdown-menu">
                    <div class="skill-dropdown-header">
                      <span class="skill-dropdown-title">选择 Agent Skill</span>
                      <el-button v-if="activeSkill" size="small" text @click="clearSkill">
                        清除
                      </el-button>
                    </div>
                    <el-dropdown-item
                      v-for="skill in skills"
                      :key="skill.id"
                      :class="{ 'is-active': activeSkill?.id === skill.id }"
                      @click="selectSkill(skill)"
                    >
                      <div class="skill-dropdown-item">
                        <div class="skill-dropdown-name">
                          {{ skill.name }}
                          <el-tag v-if="skill.isBuiltIn" type="warning" size="small" effect="plain" class="builtin-tag">内置</el-tag>
                        </div>
                        <div class="skill-dropdown-desc">{{ skill.description }}</div>
                        <div class="skill-dropdown-keywords">
                          <el-tag
                            v-for="kw in skill.keywords.slice(0, 3)"
                            :key="kw"
                            size="small"
                            effect="plain"
                          >
                            {{ kw }}
                          </el-tag>
                        </div>
                      </div>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
          <!-- 当前激活的 Skill 提示：仅在日常对话模式下显示 -->
          <div v-if="qaMode === 'chat' && activeSkill" class="active-skill-bar-compact">
            <el-tag type="success" size="small" closable @close="clearSkill">
              <el-icon><SetUp /></el-icon> {{ activeSkill.name }}
            </el-tag>
          </div>
          
          <!-- 输入框主容器 -->
          <div class="chat-input-wrapper">
            <!-- 图片预览：在输入框内部上方 -->
            <div v-if="pendingImages.length > 0" class="image-preview-area">
              <div
                v-for="(img, idx) in pendingImages"
                :key="idx"
                class="image-preview-tag"
                @click="openImagePreview(idx)"
              >
                <img :src="img" alt="" />
                <span class="image-tag-name">图片 {{ idx + 1 }}</span>
                <el-icon class="image-tag-close" @click.stop="removeImage(idx)"><Close /></el-icon>
              </div>
            </div>
            <el-input
              v-model="question"
              type="textarea"
              :rows="4"
              :placeholder="qaMode === 'chat' ? '请输入您的问题...' : (kbNotFound ? '请先创建知识库后再提问...' : '基于知识库提问...')"
              :disabled="qaMode === 'knowledge' && kbNotFound"
              @keydown.enter.prevent="handleKeyDown"
              @input="handleQuestionInput"
              @paste="handlePaste"
            />
            <div class="input-actions">
              <div class="input-actions-left">
                <el-button
                  size="small"
                  text
                  @click="triggerImageUpload"
                  :disabled="qaMode !== 'chat'"
                  :title="qaMode === 'chat' ? '上传图片' : '图片问答仅支持日常对话模式'"
                >
                  <el-icon><Picture /></el-icon>
                  图片
                </el-button>
                <input
                  ref="imageInputRef"
                  type="file"
                  accept="image/*"
                  style="display: none"
                  @change="handleImageSelect"
                />
              </div>
              <el-button 
                type="primary" 
                @click="sendMessage" 
                :loading="answering" 
                :disabled="(!question.trim() && pendingImages.length === 0) || (qaMode === 'knowledge' && kbNotFound)"
              >
                <el-icon v-if="!answering"><Promotion /></el-icon>
                <span>{{ answering ? '生成中...' : '发送' }}</span>
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 文档管理对话框 -->
    <el-dialog
      v-model="documentDialogVisible"
      title="文档管理"
      width="700px"
    >
      <div class="document-list" v-loading="documentsLoading">
        <el-empty 
          v-if="documents.length === 0" 
          description="暂无上传的文档"
          :image-size="80"
        />
        <el-table 
          v-else
          :data="documents" 
          style="width: 100%"
          max-height="400"
        >
          <el-table-column prop="title" label="文档名称" min-width="200" show-overflow-tooltip />
          <el-table-column prop="file_type" label="类型" width="80">
            <template #default="{ row }">
              <el-tag size="small">{{ row.file_type.toUpperCase() }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="file_size" label="大小" width="100">
            <template #default="{ row }">
              {{ formatFileSize(row.file_size) }}
            </template>
          </el-table-column>
          <el-table-column prop="uploaded_at" label="上传时间" width="160">
            <template #default="{ row }">
              {{ formatDate(row.uploaded_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button 
                size="small" 
                type="success" 
                link 
                @click="downloadDocument(row)"
              >
                下载
              </el-button>
              <el-button 
                size="small" 
                type="danger" 
                link 
                @click="deleteDocument(row.id)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <template #footer>
        <el-button @click="documentDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
    <!-- 图片放大预览对话框 -->
    <el-dialog
      v-model="imagePreviewVisible"
      width="auto"
      :show-close="false"
      align-center
      destroy-on-close
      class="image-preview-dialog"
    >
      <div class="image-preview-container">
        <img :src="pendingImages[previewImageIndex]" alt="预览" />
        <div v-if="pendingImages.length > 1" class="image-preview-nav">
          <el-button circle @click="prevPreviewImage">
            <el-icon><ArrowLeft /></el-icon>
          </el-button>
          <span class="image-preview-counter">{{ previewImageIndex + 1 }} / {{ pendingImages.length }}</span>
          <el-button circle @click="nextPreviewImage">
            <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import { knowledgeBaseAPI } from '@/api/index'
import api from '@/api/index'
import { ArrowLeft, Upload, Reading, User, Promotion, Plus, Delete, ChatDotRound, Document, SetUp, Picture, Close, Download, Timer, Loading, CircleCheckFilled, CircleCloseFilled, CopyDocument, Opportunity } from '@element-plus/icons-vue'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import * as XLSX from 'xlsx'

// 子组件
import ChatHistoryPanel from '@/components/chat/ChatHistoryPanel.vue'
import WorkflowTimeline from '@/components/chat/WorkflowTimeline.vue'
import ModeSwitcher from '@/components/chat/ModeSwitcher.vue'

const router = useRouter()
const route = useRoute()

// 状态
const kbId = ref(route.params.id)
const knowledgeBase = ref(null)
const kbNotFound = ref(false)  // 知识库不存在或无权限
const kbLoading = ref(true)    // 加载状态
const historyLoading = ref(false)
const historyLoadError = ref(false)
const answering = ref(false)
const chatHistory = ref([])
const messages = ref([])
const question = ref('')
const messageListRef = ref(null)
const currentMessageId = ref(null)
const selectedMessages = ref(new Set()) // 选中的消息ID集合
const currentSessionId = ref('') // 当前选中的会话ID
const pendingImages = ref([]) // 待发送的图片列表（base64）
const imagePreviewVisible = ref(false)
const previewImageIndex = ref(0)

const openImagePreview = (idx) => {
  previewImageIndex.value = idx
  imagePreviewVisible.value = true
}
const prevPreviewImage = () => {
  if (previewImageIndex.value > 0) {
    previewImageIndex.value--
  } else {
    previewImageIndex.value = pendingImages.value.length - 1
  }
}
const nextPreviewImage = () => {
  if (previewImageIndex.value < pendingImages.value.length - 1) {
    previewImageIndex.value++
  } else {
    previewImageIndex.value = 0
  }
}

// 流式输出相关
const streamingText = ref('') // 流式输出的文本（当前实际显示的）
const fullStreamingText = ref('') // 流式输出收到的完整文本
const elapsedTime = ref(0) // 计时器（秒）
const thinkingSteps = ref([]) // 思考过程步骤累积列表
const currentThinkingStatus = ref('') // 当前（最新）状态文字
const streamingReasoning = ref('') // 模型真正的推理文本（reasoning 事件流式累积）
let streamTimer = null // 计时器 interval
let streamAbortController = null // 用于取消请求
let typewriterTimer = null // 打字机效果 timer
let typewriterIndex = 0 // 打字机当前显示到的位置
let streamReader = null // 当前流式读取器（用于手动取消）

// 问答模式：'chat' - 日常对话，'knowledge' - 知识库问答
const qaMode = ref('chat')

// 推理模式：'fast' - 直接回答，'reasoning' - 深度思考
const reasoningMode = ref('fast')
const toggleReasoningMode = () => {
  reasoningMode.value = reasoningMode.value === 'fast' ? 'reasoning' : 'fast'
}

// 历史面板折叠状态
const historyCollapsed = ref(false)
const toggleHistoryPanel = () => { historyCollapsed.value = !historyCollapsed.value }

// ========== Skill 相关状态 ==========
const skills = ref([])
const activeSkill = ref(null) // 当前激活的 Skill
const showSkillSelector = ref(false) // 是否显示 Skill 选择器

// ========== 多Agent工作流相关状态 ==========
const workflowSteps = ref([])       // 工作流步骤列表
const workflowDone = ref(false)     // 工作流是否完成
const workflowError = ref(false)    // 工作流是否有错误
const workflowResult = ref('')      // 工作流最终结果文本
let workflowAbortController = null  // 工作流请求取消控制器
let workflowReader = null           // 工作流 SSE reader

// 工作流步骤完成数（computed）
const workflowCompletedCount = computed(() => {
  return workflowSteps.value.filter(s => s.status === 'done').length
})

// 加载已启用的 Skills
const loadSkills = () => {
  try {
    const saved = localStorage.getItem('agent_skills')
    const customSkills = saved ? JSON.parse(saved) : []
    
    // 内置技能（与 AgentSkills.vue 保持一致）
    const builtInSkills = [
      {
        id: 'builtin-1',
        name: 'api-testcase-generator',
        description: 'Generate structured API test cases from Postman Collection v2.1 JSON, Apipost export JSON, or Swagger/OpenAPI 2.0 & 3.0 JSON.',
        keywords: ['接口测试用例', 'Postman用例生成', 'Apipost用例生成', 'Swagger用例生成', 'OpenAPI用例生成', 'generate API test cases', '接口边界值用例', 'API', '接口', 'postman', 'swagger', 'openapi', '生成用例', '测试用例生成', '接口测试', 'API测试', '写用例', '帮我生成', '生成测试'],
        systemPrompt: 'You are an API testing expert. When given API documentation or requirements, generate comprehensive test cases covering: 1) Normal cases with valid inputs, 2) Boundary value analysis, 3) Error cases with invalid inputs, 4) Authentication and authorization scenarios, 5) Cross-field validation. Output in structured format with test case ID, description, steps, expected results, and priority.',
        enabled: true,
        isBuiltIn: true,
      },
      {
        id: 'builtin-2',
        name: 'browser-use',
        description: 'Automates browser interactions for web testing, form filling, screenshots, and data extraction.',
        keywords: ['浏览器自动化', 'web测试', '页面截图', '表单填写', 'browser', 'playwright', 'selenium', 'cypress', '自动化测试', 'UI测试', '网页测试', 'Web自动化', '前端测试', '页面测试', '浏览器'],
        systemPrompt: 'You are a browser automation expert using Playwright. Help users write automation scripts for: web testing, form filling, taking screenshots, data extraction, and web page interaction. Provide complete, runnable code examples with explanations.',
        enabled: true,
        isBuiltIn: true,
      },
      {
        id: 'builtin-3',
        name: 'e2e-testing-patterns',
        description: 'Build reliable, fast E2E test suites with Playwright and Cypress.',
        keywords: ['e2e测试', 'Playwright', 'Cypress', '端到端测试', 'E2E', 'end-to-end', '端到端', '回归测试', '冒烟测试', '集成测试场景'],
        systemPrompt: 'You are an E2E testing specialist. Help design reliable test suites covering critical user journeys, eliminate flaky tests, and integrate with CI/CD. Provide best practices for Playwright and Cypress.',
        enabled: true,
        isBuiltIn: true,
      },
      {
        id: 'builtin-4',
        name: 'requirement-reviewer',
        description: '对需求文档/PRD进行逻辑审查+完整性评估+100分制打分。',
        keywords: ['testing', 'qa', 'review', 'prd', 'requirement', '需求评审', '需求', 'PRD', '评审', '需求文档', '需求审查', '打分'],
        systemPrompt: 'You are a requirements analyst. Review PRDs and requirement documents for: logical consistency, completeness, clarity, and testability. Score out of 100. Below 60 is fail. Output structured Markdown review report with sections: Summary, Strengths, Issues (with severity), Recommendations, and Score.',
        enabled: true,
        isBuiltIn: true,
      },
      {
        id: 'builtin-5',
        name: 'testcase-reviewer',
        description: '对测试用例进行逻辑审查 + PRD 对齐检查 + 100分制打分。',
        keywords: ['testing', 'qa', 'review', 'testcase', '用例评审', '测试用例', '用例', '审查用例', '检查用例', '用例质量'],
        systemPrompt: 'You are a test case reviewer. Check test cases against requirements for: coverage, correctness, clarity, and traceability. Score out of 100. Below 60 is fail. Output Markdown table report with test case ID, review result, issues, and score.',
        enabled: true,
        isBuiltIn: true,
      },
      {
        id: 'builtin-6',
        name: 'universal-testcase-generator',
        description: '全能测试用例生成器 - 根据各类文档生成测试用例。',
        keywords: ['生成测试用例', '测试用例思维导图', '接口测试用例', 'PRD转测试用例', 'test case generation', '测试用例', '用例生成', '写测试', '写用例', '帮我生成', '生成', '测试', '用例', 'testcase'],
        systemPrompt: 'You are a universal test case generator. Generate comprehensive test cases from any input: PRD, API docs, design screenshots, or online documents. Support multiple output formats: Markdown tables, mind maps, JSON. Cover functional, boundary, error, compatibility, performance, and security testing.',
        enabled: true,
        isBuiltIn: true,
      },
    ]
    
    // 合并并只保留启用的技能
    const allSkills = [...builtInSkills, ...customSkills]
    skills.value = allSkills.filter(s => s.enabled !== false)
    console.log('[Skill] Loaded', skills.value.length, 'enabled skills')
  } catch (error) {
    console.error('[Skill] Load skills error:', error)
    skills.value = []
  }
}

// 根据用户问题匹配 Skill（改进版：意图识别 + 精确匹配）
const matchSkill = (question) => {
  if (!question || skills.value.length === 0) return null
  
  const q = question.toLowerCase()
  let bestMatch = null
  let bestScore = 0
  
  // 意图检测：判断用户是想"生成/创建"还是"审查/评审"
  const intentKeywords = {
    generate: ['生成', '创建', '写', '编写', '制作', '新建', '产生', 'build', 'create', 'generate', 'make'],
    review: ['审查', '评审', '检查', 'review', '打分', '评估', '审计', '检查一下', '看一下'],
    automate: ['自动', '自动化', 'auto', 'automate', '浏览器', 'browser', '页面', '截图', '填写'],
    e2e: ['端到端', 'e2e', 'end-to-end', '回归', '冒烟'],
  }
  
  for (const skill of skills.value) {
    let score = 0
    // 关键词匹配
    for (const kw of skill.keywords || []) {
      if (q.includes(kw.toLowerCase())) {
        score += kw.length >= 4 ? 3 : 2 // 长关键词权重更高
      }
    }
    // 名称匹配
    if (q.includes(skill.name.toLowerCase())) {
      score += 5
    }
    // 描述匹配
    if (skill.description && q.includes(skill.description.toLowerCase().substring(0, 20))) {
      score += 2
    }
    
    // 意图加权：根据用户意图调整分数
    const skillId = skill.id
    const hasIntent = (intents) => intents.some(kw => q.includes(kw.toLowerCase()))
    
    if (skillId === 'builtin-6') { // universal-testcase-generator
      if (hasIntent(intentKeywords.generate)) score += 6  // 生成意图，加权
      if (hasIntent(intentKeywords.review)) score -= 3    // 审查意图，降权（用户想审查时不要匹配生成器）
    }
    if (skillId === 'builtin-5') { // testcase-reviewer
      if (hasIntent(intentKeywords.review)) score += 6     // 审查意图，加权
      if (hasIntent(intentKeywords.generate)) score -= 3   // 生成意图，降权
    }
    if (skillId === 'builtin-4') { // requirement-reviewer
      if (hasIntent(intentKeywords.review)) score += 5
    }
    if (skillId === 'builtin-2') { // browser-use
      if (hasIntent(intentKeywords.automate)) score += 5
    }
    if (skillId === 'builtin-3') { // e2e-testing-patterns
      if (hasIntent(intentKeywords.e2e)) score += 5
    }
    
    if (score > bestScore) {
      bestScore = score
      bestMatch = skill
    }
  }
  
  // 阈值：至少匹配到关键词且得分>=3才激活（降低误触发）
  return bestScore >= 3 ? bestMatch : null
}

// 手动选择 Skill
const selectSkill = (skill) => {
  activeSkill.value = skill
  showSkillSelector.value = false
  ElMessage.success(`已激活 Skill: ${skill.name}`)
}

// 清除 Skill
const clearSkill = () => {
  activeSkill.value = null
  ElMessage.info('已清除 Skill 选择')
}

// 监听问题输入，自动匹配 Skill（仅日常对话模式）
const handleQuestionInput = () => {
  if (!question.value.trim() || activeSkill.value || qaMode.value !== 'chat') return
  const matched = matchSkill(question.value)
  if (matched && matched.id !== activeSkill.value?.id) {
    activeSkill.value = matched
    console.log('[Skill] Auto-matched:', matched.name)
  }
}

// ========== 图片上传相关 ==========
const imageInputRef = ref(null)

const triggerImageUpload = () => {
  imageInputRef.value?.click()
}

const handleImageSelect = (e) => {
  const files = e.target.files
  if (!files || files.length === 0) return
  processImageFiles(files)
  e.target.value = '' // 清空input，允许重复选择同一文件
}

const handlePaste = (e) => {
  const items = e.clipboardData?.items
  if (!items) return
  const imageFiles = []
  for (let i = 0; i < items.length; i++) {
    if (items[i].type.startsWith('image/')) {
      const file = items[i].getAsFile()
      if (file) imageFiles.push(file)
    }
  }
  if (imageFiles.length > 0) {
    e.preventDefault()
    processImageFiles(imageFiles)
  }
}

const processImageFiles = (files) => {
  for (const file of files) {
    if (!file.type.startsWith('image/')) continue
    // 限制单张图片不超过 5MB
    if (file.size > 5 * 1024 * 1024) {
      ElMessage.warning('单张图片不能超过 5MB')
      continue
    }
    const reader = new FileReader()
    reader.onload = (e) => {
      pendingImages.value.push(e.target.result)
    }
    reader.readAsDataURL(file)
  }
}

const removeImage = (idx) => {
  pendingImages.value.splice(idx, 1)
}

// 文档管理
const documentDialogVisible = ref(false)
const documentsLoading = ref(false)
const documents = ref([])

// 加载知识库详情
const loadKnowledgeBase = async () => {
  kbLoading.value = true
  kbNotFound.value = false

  // 日常对话模式也尝试加载知识库（后端接口需要 kbId）
  if (qaMode.value === 'chat') {
    try {
      const listRes = await knowledgeBaseAPI.list({ page_size: 100 })
      const kbs = listRes.results || listRes || []
      if (kbs.length > 0) {
        const firstKb = kbs[0]
        kbId.value = firstKb.id
        knowledgeBase.value = firstKb
        kbNotFound.value = false
        window.history.replaceState(null, '', `/knowledge/${firstKb.id}`)
        console.log('[KB] Chat mode auto-selected KB:', firstKb.id, firstKb.name)
      } else {
        kbNotFound.value = true
        knowledgeBase.value = null
      }
    } catch (err) {
      console.error('Failed to list KBs in chat mode:', err)
      kbNotFound.value = true
      knowledgeBase.value = null
    } finally {
      kbLoading.value = false
    }
    return
  }

  // 如果kbId是无效值（如 "0"、"undefined"、空字符串），直接查找可用知识库
  const invalidIds = ['0', 'undefined', 'null', '', 'chat', 'select']
  if (!kbId.value || invalidIds.includes(String(kbId.value))) {
    console.log('[KB] Invalid kbId:', kbId.value, '- skipping direct fetch, listing available KBs')
    try {
      const listRes = await knowledgeBaseAPI.list({ page_size: 100 })
      const kbs = listRes.results || listRes || []
      if (kbs.length > 0) {
        const firstKb = kbs[0]
        kbId.value = firstKb.id
        knowledgeBase.value = firstKb
        window.history.replaceState(null, '', `/knowledge/${firstKb.id}`)
        console.log('[KB] Auto-selected KB:', firstKb.id, firstKb.name)
      } else {
        kbNotFound.value = true
        knowledgeBase.value = null
      }
    } catch (listErr) {
      console.error('Failed to list KBs:', listErr)
      kbNotFound.value = true
    } finally {
      kbLoading.value = false
    }
    return
  }

  try {
    const res = await knowledgeBaseAPI.get(kbId.value)
    knowledgeBase.value = res
    kbNotFound.value = false
  } catch (error) {
    // 知识库不存在或无权限 → 自动查找用户可用的知识库
    console.warn('KB not found, trying to find available KB:', error)
    try {
      const listRes = await knowledgeBaseAPI.list({ page_size: 100 })
      const kbs = listRes.results || listRes || []
      if (kbs.length > 0) {
        // 跳转到第一个可用的知识库
        const firstKb = kbs[0]
        kbId.value = firstKb.id
        knowledgeBase.value = firstKb
        // 更新URL但不触发导航（避免死循环）
        window.history.replaceState(null, '', `/knowledge/${firstKb.id}`)
      } else {
        kbNotFound.value = true
        knowledgeBase.value = null
      }
    } catch (listErr) {
      console.error('Failed to list KBs:', listErr)
      kbNotFound.value = true
    }
  } finally {
    kbLoading.value = false
  }
}

// 创建新知识库
const createNewKB = async () => {
  try {
    const { value } = await ElMessageBox.prompt('请输入知识库名称', '创建知识库', {
      confirmButtonText: '创建',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：产品文档库',
      inputPattern: /^.{1,50}$/,
      inputErrorMessage: '名称长度为1-50个字符'
    })
    if (!value) return
    const res = await knowledgeBaseAPI.create({ name: value, description: '' })
    kbId.value = res.id
    knowledgeBase.value = res
    kbNotFound.value = false
    window.history.replaceState(null, '', `/knowledge/${res.id}`)
    ElMessage.success('知识库创建成功')
  } catch (e) {
    if (e !== 'cancel') console.error('Create KB error:', e)
  }
}

// 加载对话历史（按会话分组）
const loadChatHistory = async () => {
  // 如果 kbId 无效，直接跳过（避免请求 undefined/字符串 导致 404）
  if (!kbId.value || !Number.isFinite(Number(kbId.value)) || Number(kbId.value) <= 0) {
    chatHistory.value = []
    return
  }
  historyLoading.value = true
  historyLoadError.value = false
  try {
    const res = await knowledgeBaseAPI.getSessionList(kbId.value)
    // 将会话列表转换为消息格式，用于显示在历史列表中
    chatHistory.value = res.map(session => ({
      id: session.session_id, // 使用session_id作为id
      session_id: session.session_id,
      question: session.title,
      answer: '', // 会话列表不需要显示答案
      created_at: session.last_message_time,
      message_count: session.message_count,
      is_session: true, // 标记这是会话而不是单条消息
      mode: session.mode || 'knowledge' // 添加模式标识，默认为知识库模式
    }))
  } catch (error) {
    console.error('Load history error:', error)
    historyLoadError.value = true
  } finally {
    historyLoading.value = false
  }
}

// 按日期分组对话历史（根据当前模式过滤）
const groupedHistory = computed(() => {
  const groups = []
  const today = new Date().toDateString()
  const yesterday = new Date(Date.now() - 86400000).toDateString()
  
  // 根据当前模式过滤历史记录
  const filteredHistory = chatHistory.value.filter(msg => msg.mode === qaMode.value)
  
  filteredHistory.forEach(msg => {
    const msgDate = new Date(msg.created_at).toDateString()
    let label = ''
    
    if (msgDate === today) {
      label = '今天'
    } else if (msgDate === yesterday) {
      label = '昨天'
    } else {
      label = new Date(msg.created_at).toLocaleDateString('zh-CN')
    }
    
    let group = groups.find(g => g.label === label)
    if (!group) {
      group = { date: msgDate, label, messages: [] }
      groups.push(group)
    }
    group.messages.push(msg)
  })
  
  return groups
})

// 选择历史消息（会话）
const selectMessage = async (msg) => {
  currentMessageId.value = msg.id
  currentSessionId.value = msg.session_id || '' // 保存会话ID
  
  console.log('选中会话，session_id:', currentSessionId.value)
  
  // 如果是会话，加载该会话的所有消息
  if (msg.is_session && msg.session_id) {
    try {
      const res = await knowledgeBaseAPI.getSessionMessages(kbId.value, msg.session_id)
      // 将后端返回的消息转换为前端格式
      messages.value = res.map(m => ({
        content: m.question,
        isUser: true,
        images: m.images || []  // 保留用户消息中的图片
      })).flatMap((userMsg, index) => {
        // 每个用户消息后面跟着AI回复
        const aiMsg = res[index]
        return [
          userMsg,
          {
            content: aiMsg.answer,
            isUser: false,
            contextDocs: aiMsg.context_docs || []
          }
        ]
      })
    } catch (error) {
      console.error('Load session messages error:', error)
      // 如果加载失败，只显示第一条消息
      messages.value = [
        { content: msg.question, isUser: true },
        { content: msg.answer, isUser: false, contextDocs: msg.context_docs || [] },
      ]
    }
  } else {
    // 显示该条消息的问答
    messages.value = [
      { content: msg.question, isUser: true },
      { content: msg.answer, isUser: false, contextDocs: msg.context_docs || [] },
    ]
  }
  
  scrollToBottom()
}

// ========== 模式独立状态（仅保留输入框内容、工作流UI状态；对话消息全局共享） ==========
const modeState = reactive({
  chat: { question: '' },
  knowledge: { question: '' },
  workflow: { question: '', workflowSteps: [], workflowDone: false, workflowError: false, workflowResult: '' },
})

// 切换问答模式
const switchMode = (mode) => {
  // 同一模式，不切换
  if (qaMode.value === mode) return
  
  // 如果正在执行中，先取消所有请求（防止切换模式后状态残留）
  if (answering.value) {
    if (workflowReader) {
      try { workflowReader.cancel() } catch (e) { /* ignore */ }
      workflowReader = null
    }
    if (workflowAbortController) {
      workflowAbortController.abort()
      workflowAbortController = null
    }
    if (streamReader) {
      try { streamReader.cancel() } catch (e) { /* ignore */ }
      streamReader = null
    }
    if (streamAbortController) {
      streamAbortController.abort()
      streamAbortController = null
    }
    stopTimer()
    stopTypewriter()
  }
  
  // 保存当前模式的输入框内容和工作流专属状态
  // 对话消息和 sessionId 全局共享，切换模式时不清空
  modeState[qaMode.value].question = question.value
  
  // 保存工作流专属状态
  if (qaMode.value === 'workflow') {
    modeState.workflow.workflowSteps = [...workflowSteps.value]
    modeState.workflow.workflowDone = workflowDone.value
    modeState.workflow.workflowError = workflowError.value
    modeState.workflow.workflowResult = workflowResult.value
  }
  
  // 清理所有流式状态
  answering.value = false
  streamingText.value = ''
  fullStreamingText.value = ''
  elapsedTime.value = 0
  workflowSteps.value = []
  workflowDone.value = false
  workflowError.value = false
  workflowResult.value = ''
  
  // 切换到新模式
  qaMode.value = mode
  
  // 切换到日常对话时，根据 kbId 有效性更新知识库状态
  if (mode === 'chat') {
    kbNotFound.value = !kbId.value || !Number.isFinite(Number(kbId.value)) || Number(kbId.value) <= 0
  }

  // 恢复目标模式的输入框内容；对话消息全局共享，不随模式切换清空
  currentMessageId.value = null
  question.value = modeState[mode].question || ''
  
  // 恢复工作流专属状态
  if (mode === 'workflow') {
    workflowSteps.value = [...(modeState.workflow.workflowSteps || [])]
    workflowDone.value = modeState.workflow.workflowDone || false
    workflowError.value = modeState.workflow.workflowError || false
    workflowResult.value = modeState.workflow.workflowResult || ''
  }
  
  // 重新加载历史（确保切换到新模式后左侧历史正确显示）
  if (kbId.value && !kbNotFound.value) {
    loadChatHistory()
  }
  
  // 简洁模式切换提示
  const modeNames = { chat: '日常对话', knowledge: '知识库问答', workflow: '多Agent工作流' }
  ElMessage.success(`已切换到${modeNames[mode]}模式`)
}

// 开始新对话（仅清空当前模式）
const startNewChat = () => {
  currentMessageId.value = null
  currentSessionId.value = ''
  messages.value = []
  question.value = ''
  // 同步保存到模式状态
  modeState[qaMode.value].question = ''
  if (qaMode.value === 'workflow') {
    modeState.workflow.workflowSteps = []
    modeState.workflow.workflowDone = false
    modeState.workflow.workflowError = false
    modeState.workflow.workflowResult = ''
  }
}

// 删除历史消息（会话）
const deleteMessage = async (msgId) => {
  // 找到对应的消息，获取其session_id
  const msg = chatHistory.value.find(m => m.id === msgId)
  if (!msg || !msg.session_id) {
    ElMessage.error('无法找到对应的会话')
    return
  }
  
  try {
    await ElMessageBox.confirm('确定要删除这个对话会话吗？这将删除该会话中的所有消息。', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    const res = await knowledgeBaseAPI.deleteSession(kbId.value, msg.session_id)
    if (res.success) {
      ElMessage.success(`删除成功，共删除 ${res.deleted_count} 条消息`)
      // 刷新历史列表
      await loadChatHistory()
      // 如果删除的是当前选中的会话，清空右侧对话区域
      if (currentSessionId.value === msg.session_id) {
        currentMessageId.value = null
        currentSessionId.value = ''
        messages.value = []
      }
    } else {
      ElMessage.error('删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Delete error:', error)
      ElMessage.error('删除失败')
    }
  }
}

// 切换消息选中状态
const toggleSelect = (msgId) => {
  if (selectedMessages.value.has(msgId)) {
    selectedMessages.value.delete(msgId)
  } else {
    selectedMessages.value.add(msgId)
  }
}

// 全选/取消全选
const toggleSelectAll = () => {
  if (selectedMessages.value.size === chatHistory.value.length) {
    // 已全选，取消全选
    selectedMessages.value.clear()
  } else {
    // 全选
    chatHistory.value.forEach(msg => {
      selectedMessages.value.add(msg.id)
    })
  }
}

// 批量删除（会话）
const batchDelete = async () => {
  if (selectedMessages.value.size === 0) {
    ElMessage.warning('请先选择要删除的会话')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedMessages.value.size} 个对话会话吗？这将删除这些会话中的所有消息。`,
      '提示',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    // 获取选中会话的session_id列表
    const selectedSessionIds = []
    Array.from(selectedMessages.value).forEach(msgId => {
      const msg = chatHistory.value.find(m => m.id === msgId)
      if (msg && msg.session_id) {
        selectedSessionIds.push(msg.session_id)
      }
    })
    
    // 逐个删除会话
    let totalDeleted = 0
    for (const sessionId of selectedSessionIds) {
      try {
        const res = await knowledgeBaseAPI.deleteSession(kbId.value, sessionId)
        if (res.success) {
          totalDeleted += res.deleted_count || 0
        }
      } catch (error) {
        console.error(`删除会话 ${sessionId} 失败:`, error)
      }
    }
    
    ElMessage.success(`成功删除 ${selectedSessionIds.length} 个会话，共 ${totalDeleted} 条消息`)
    selectedMessages.value.clear()
    // 刷新历史列表
    await loadChatHistory()
    // 如果删除的是当前选中的会话，清空右侧对话区域
    if (currentSessionId.value && selectedSessionIds.includes(currentSessionId.value)) {
      currentMessageId.value = null
      currentSessionId.value = ''
      messages.value = []
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Batch delete error:', error)
      ElMessage.error('批量删除失败')
    }
  }
}

// 上传文档 loading 消息实例（组件级别，防止重复创建）
let uploadLoadingMsg = null

// 上传文档
const handleUpload = async (file) => {
  // 关闭之前的 loading 消息（防止重复调用时消息卡住）
  if (uploadLoadingMsg) {
    try { uploadLoadingMsg.close() } catch (e) {}
    uploadLoadingMsg = null
  }
  
  uploadLoadingMsg = ElMessage.info({
    message: `正在处理 "${file.name}"，向量化入库中请稍候...`,
    duration: 0,
  })
  
  try {
    const res = await knowledgeBaseAPI.uploadDocument(kbId.value, file)
    
    if (uploadLoadingMsg) {
      uploadLoadingMsg.close()
      uploadLoadingMsg = null
    }
    
    // 使用 Notification 显示更明显的成功提示
    ElNotification({
      title: '文档上传成功',
      message: `✓ "${file.name}" 已上传，正在后台向量化处理中，请稍候...`,
      type: 'success',
      duration: 5000,
      position: 'top-right',
    })
    
    // 如果文档管理对话框是打开的，刷新文档列表
    if (documentDialogVisible.value) {
      await loadDocuments()
    }
  } catch (error) {
    if (uploadLoadingMsg) {
      uploadLoadingMsg.close()
      uploadLoadingMsg = null
    }
    console.error('Upload error:', error)
    ElNotification({
      title: '文档上传失败',
      message: `✗ "${file.name}" 上传失败，请检查文件格式或网络连接`,
      type: 'error',
      duration: 5000,
      position: 'top-right',
    })
  }
  return false // 阻止默认上传行为
}

// 格式化消息内容（解析Markdown）
const formatMessage = (content) => {
  if (!content) return ''
  if (typeof content !== 'string') {
    // 如果内容不是字符串，尝试转换为字符串
    try {
      content = String(content)
    } catch {
      return ''
    }
  }

  // 先解析转义字符（\n -> 换行，\t -> 制表符等）
  content = content
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
    .replace(/\\r/g, '')
    .replace(/\\"/g, '"')
    .replace(/\\'/g, "'")
    .replace(/\\\\/g, '\\')

  let formatted = content
  
  // 1. 转换Markdown代码块为HTML（优先处理，避免内部内容被其他规则影响）
  const codeBlocks = []
  formatted = formatted.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
    const language = lang || 'text'
    const placeholder = `__CODE_BLOCK_${codeBlocks.length}__`
    codeBlocks.push(`<pre class="code-block" data-language="${language}"><code class="language-${language}">${escapeHtml(code.trim())}</code></pre>`)
    return placeholder
  })
  
  // 2. 行内代码
  formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>')
  
  // 3. 标题（支持多级）
  formatted = formatted.replace(/^#### (.+)$/gm, '<h4>$1</h4>')
  formatted = formatted.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  formatted = formatted.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  formatted = formatted.replace(/^# (.+)$/gm, '<h1>$1</h1>')
  
  // 4. 分隔线
  formatted = formatted.replace(/^---+$/gm, '<hr/>')
  formatted = formatted.replace(/^\*\*\*+$/gm, '<hr/>')
  
  // 5. 引用块（多行支持）
  formatted = formatted.replace(/(^&gt; .+\n?)+/gm, (match) => {
    const lines = match.split('\n').filter(l => l.startsWith('&gt; '))
    const content = lines.map(l => l.replace(/^&gt; /, '')).join('<br/>')
    return `<blockquote>${content}</blockquote>`
  })
  
  // 6. 有序列表
  formatted = formatted.replace(/(^\d+\. .+\n?)+/gm, (match) => {
    const items = match.split('\n').filter(l => /^\d+\. /.test(l))
    const lis = items.map(l => `<li>${l.replace(/^\d+\. /, '')}</li>`).join('')
    return `<ol>${lis}</ol>`
  })
  
  // 7. 无序列表（支持多层级）
  formatted = formatted.replace(/(^[-*] .+\n?)+/gm, (match) => {
    const items = match.split('\n').filter(l => /^[-*] /.test(l))
    const lis = items.map(l => `<li>${l.replace(/^[-*] /, '')}</li>`).join('')
    return `<ul>${lis}</ul>`
  })
  
  // 8. 任务列表
  formatted = formatted.replace(/^- \[([ x])\] (.+)$/gm, (match, checked, text) => {
    const isChecked = checked === 'x' ? 'checked' : ''
    return `<li><input type="checkbox" ${isChecked} disabled/> ${text}</li>`
  })
  
  // 9. 表格（自动检测测试用例表 + 优先级徽章）
  const tableRegex = /(\|.+\|\n)(\|[\s\-:|]+\|\n)((\|.+\|\n?)+)/g
  formatted = formatted.replace(tableRegex, (match, header, separator, rows) => {
    // 检测是否为测试用例表格
    const hdrStr = header.toLowerCase()
    const isTC = hdrStr.includes('用例') || hdrStr.includes('优先级') || hdrStr.includes('priority')
      || hdrStr.includes('测试场景') || hdrStr.includes('预期结果') || hdrStr.includes('前置条件')
      || hdrStr.includes('测试步骤') || hdrStr.includes('用例id') || hdrStr.includes('case')

    // 提取表头文本用于定位优先级列
    const hdrTexts = header.split('|').filter(c => c.trim()).map(c => c.trim().toLowerCase())

    const headerCells = header.split('|').filter(c => c.trim()).map(c => `<th>${c.trim()}</th>`).join('')
    const bodyRows = rows.trim().split('\n').map(row => {
      const rowCells = row.split('|').filter(c => c.trim())
      const cells = rowCells.map((c, ci) => {
        const txt = c.trim()
        // 优先级列渲染为彩色徽章
        if (isTC && hdrTexts[ci] && (hdrTexts[ci].includes('优先级') || hdrTexts[ci].includes('priority'))) {
          let lvl = 'p2'
          if (/p0|最高|critical|紧急|blocker/i.test(txt)) lvl = 'p0'
          else if (/p1|高|high/i.test(txt)) lvl = 'p1'
          else if (/p3|低|low|minor/i.test(txt)) lvl = 'p3'
          return `<td><span class="tc-priority ${lvl}">${txt}</span></td>`
        }
        return `<td>${txt}</td>`
      }).join('')
      return `<tr>${cells}</tr>`
    }).join('')

    if (isTC) {
      return `<div class="tc-table-wrap"><table><thead><tr>${headerCells}</tr></thead><tbody>${bodyRows}</tbody></table></div>`
    }
    return `<table><thead><tr>${headerCells}</tr></thead><tbody>${bodyRows}</tbody></table>`
  })
  
  // 10. 加粗和斜体
  formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  formatted = formatted.replace(/\*(.+?)\*/g, '<em>$1</em>')
  
  // 11. 链接
  formatted = formatted.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
  
  // 12. 图片
  formatted = formatted.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" loading="lazy"/>')
  
  // 13. 换行处理：先处理段落，再处理剩余换行
  const paragraphs = formatted.split(/\n{2,}/)
  formatted = paragraphs.map(p => {
    p = p.trim()
    if (!p) return ''
    // 如果已经是块级元素，不包裹
    if (/^<(h[1-6]|ul|ol|blockquote|pre|table|hr|li)/.test(p)) {
      return p
    }
    // 将单个换行转为 <br/>
    p = p.replace(/\n/g, '<br/>')
    return `<p>${p}</p>`
  }).filter(Boolean).join('')
  
  // 14. 恢复代码块
  codeBlocks.forEach((code, index) => {
    formatted = formatted.replace(`__CODE_BLOCK_${index}__`, code)
  })
  
  return formatted
}

// HTML转义（防止XSS）
const escapeHtml = (text) => {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

// 绑定代码块事件
const bindCodeBlockEvents = () => {
  const codeBlocks = document.querySelectorAll('.ai-message-bubble pre')
  
  codeBlocks.forEach(pre => {
    // 如果已经绑定过，跳过
    if (pre.dataset.toolbarBound === 'true') return
    
    pre.dataset.toolbarBound = 'true'
    
    // 创建工具栏（顶部）
    const toolbar = document.createElement('div')
    toolbar.className = 'code-block-toolbar'
    
    // 语言标签（左侧）
    const language = pre.dataset.language || 'CODE'
    const langLabel = document.createElement('span')
    langLabel.className = 'toolbar-lang'
    langLabel.textContent = language.toUpperCase()
    
    // 右侧按钮组容器
    const btnGroup = document.createElement('div')
    btnGroup.className = 'toolbar-btn-group'
    
    // 复制按钮（豆包风格：纯图标小按钮）
    const copyBtn = document.createElement('button')
    copyBtn.className = 'toolbar-btn toolbar-btn-copy'
    copyBtn.title = '复制'
    copyBtn.innerHTML = `
      <svg viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>
    `
    
    // 放大查看按钮（纯图标小按钮）
    const zoomBtn = document.createElement('button')
    zoomBtn.className = 'toolbar-btn toolbar-btn-zoom'
    zoomBtn.title = '全屏'
    zoomBtn.innerHTML = `
      <svg viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/></svg>
    `
    
    btnGroup.appendChild(copyBtn)
    btnGroup.appendChild(zoomBtn)
    
    toolbar.appendChild(langLabel)
    toolbar.appendChild(btnGroup)
    
    // 插入工具栏到pre元素开头
    pre.insertBefore(toolbar, pre.firstChild)
    
    // 获取代码内容（排除工具栏文字）
    const getCodeContent = () => {
      const codeEl = pre.querySelector('code')
      return codeEl?.textContent || ''
    }
    
    // 复制功能
    copyBtn.addEventListener('click', async (e) => {
      e.stopPropagation()
      const code = getCodeContent().trim()
      
      try {
        await navigator.clipboard.writeText(code)
        // 临时显示已复制状态（绿色对勾）
        const originalHTML = copyBtn.innerHTML
        copyBtn.innerHTML = `<svg viewBox="0 0 24 24" width="14" height="14"><path fill="#52c41a" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>`
        copyBtn.style.color = '#52c41a'
        
        ElMessage({
          message: '已复制',
          type: 'success',
          duration: 1200
        })
        
        setTimeout(() => {
          copyBtn.innerHTML = originalHTML
          copyBtn.style.color = ''
        }, 2000)
      } catch (err) {
        console.error('复制失败:', err)
        ElMessage({
          message: '复制失败',
          type: 'error',
          duration: 1500
        })
      }
    })
    
    // 放大查看功能 - 打开模态框
    zoomBtn.addEventListener('click', (e) => {
      e.stopPropagation()
      showCodeModal(getCodeContent().trim(), language)
    })
  })
}

// 显示代码放大查看模态框（豆包风格：右侧滑出全屏面板 + 语法高亮 + 行号）
const showCodeModal = (code, language) => {
  // 创建遮罩层
  const overlay = document.createElement('div')
  overlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.45);
    z-index: 9998;
    opacity: 0;
    transition: opacity 0.3s ease;
  `

  // 创建右侧滑出面板
  const panel = document.createElement('div')
  panel.style.cssText = `
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: 65vw;
    min-width: 500px;
    max-width: 900px;
    background: #ffffff;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    box-shadow: -4px 0 24px rgba(0, 0, 0, 0.15);
    transform: translateX(100%);
    transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
  `

  // 顶部工具栏
  const headerDiv = document.createElement('div')
  headerDiv.style.cssText = `
    padding: 14px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #f0f0f0;
    flex-shrink: 0;
  `

  // 左侧：语言标签 + 复制按钮
  const leftGroup = document.createElement('div')
  leftGroup.style.cssText = `display: flex; align-items: center; gap: 12px;`

  const langSpan = document.createElement('span')
  langSpan.style.cssText = `
    color: #262626;
    font-size: 15px;
    font-weight: 600;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  `
  langSpan.textContent = language.toUpperCase()

  // 复制按钮
  const copyBtn = document.createElement('button')
  copyBtn.innerHTML = `
    <svg viewBox="0 0 24 24" width="14" height="14" style="margin-right: 4px; vertical-align: -2px;"><path fill="currentColor" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>
    <span>复制</span>
  `
  copyBtn.style.cssText = `
    background: #f5f5f5;
    border: 1px solid #e8e8e8;
    color: #595959;
    cursor: pointer;
    padding: 6px 14px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    transition: all 0.2s;
  `
  copyBtn.onmouseover = () => {
    copyBtn.style.background = '#f6ffed'
    copyBtn.style.borderColor = '#52c41a'
    copyBtn.style.color = '#389e0d'
  }
  copyBtn.onmouseout = () => {
    copyBtn.style.background = '#f5f5f5'
    copyBtn.style.borderColor = '#e8e8e8'
    copyBtn.style.color = '#595959'
  }
  copyBtn.onclick = async () => {
    try {
      await navigator.clipboard.writeText(code)
      copyBtn.innerHTML = `<svg viewBox="0 0 24 24" width="14" height="14" style="margin-right: 4px; vertical-align: -2px;"><path fill="#52c41a" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg><span>已复制</span>`
      copyBtn.style.color = '#52c41a'
      copyBtn.style.borderColor = '#52c41a'
      copyBtn.style.background = '#f6ffed'
      setTimeout(() => {
        copyBtn.innerHTML = `<svg viewBox="0 0 24 24" width="14" height="14" style="margin-right: 4px; vertical-align: -2px;"><path fill="currentColor" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg><span>复制</span>`
        copyBtn.style.color = ''
        copyBtn.style.borderColor = ''
        copyBtn.style.background = ''
      }, 2000)
      ElMessage({ message: '已复制', type: 'success', duration: 1200 })
    } catch (err) {
      ElMessage({ message: '复制失败', type: 'error', duration: 1500 })
    }
  }

  leftGroup.appendChild(langSpan)
  leftGroup.appendChild(copyBtn)

  // 关闭按钮
  const closeBtn = document.createElement('button')
  closeBtn.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20"><path fill="#8c8c8c" d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>'
  closeBtn.style.cssText = `
    background: none; border: none; cursor: pointer; padding: 6px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 6px; transition: all 0.2s;
  `
  closeBtn.onmouseover = () => closeBtn.style.background = '#f5f5f5'
  closeBtn.onmouseout = () => closeBtn.style.background = 'none'

  headerDiv.appendChild(leftGroup)
  headerDiv.appendChild(closeBtn)

  // 代码内容区域（白色背景）
  const codeContainer = document.createElement('div')
  codeContainer.style.cssText = `
    flex: 1;
    overflow: auto;
    padding: 20px 0;
    background: #ffffff;
  `

  // 语法高亮处理
  const langMap = {
    'js': 'javascript', 'ts': 'typescript', 'py': 'python',
    'bash': 'bash', 'sh': 'bash', 'shell': 'bash',
    'html': 'xml', 'xml': 'xml',
    'css': 'css', 'scss': 'scss', 'less': 'less',
    'json': 'json', 'yaml': 'yaml', 'yml': 'yaml',
    'sql': 'sql', 'java': 'java', 'go': 'go',
    'rust': 'rust', 'c': 'c', 'cpp': 'cpp',
    'php': 'php', 'ruby': 'ruby'
  }
  const hlLang = langMap[language.toLowerCase()] || language.toLowerCase()
  let highlighted = code
  try {
    if (hljs.getLanguage(hlLang)) {
      highlighted = hljs.highlight(code, { language: hlLang }).value
    }
  } catch (e) { /* 高亮失败则保持原样 */ }

  // 生成行号 + 代码
  const lines = code.split('\n')
  const lineCount = lines.length
  const lineHeightPx = 24  // 固定像素高度，确保对齐

  const wrapper = document.createElement('div')
  wrapper.style.cssText = `
    display: flex;
    font-family: 'SF Mono', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    padding: 0 24px;
  `

  // 行号列：独立 div，每行固定高度
  const lineNumbersDiv = document.createElement('div')
  lineNumbersDiv.style.cssText = `
    flex-shrink: 0;
    border-right: 1px solid #f0f0f0;
    margin-right: 16px;
    padding-top: 4px;
    user-select: none;
  `
  const numEls = []
  for (let i = 0; i < lineCount; i++) {
    const numEl = document.createElement('div')
    numEl.textContent = i + 1
    numEl.style.cssText = `
      color: #c4c4c4;
      text-align: right;
      padding-right: 16px;
      height: ${lineHeightPx}px;
      line-height: ${lineHeightPx}px;
      cursor: pointer;
      transition: background 0.15s;
      font-size: 14px;
    `
    numEls.push(numEl)
    lineNumbersDiv.appendChild(numEl)
  }

  // 代码列：整体放入 pre>code，让浏览器按 white-space: pre 自然换行
  const codeContentDiv = document.createElement('div')
  codeContentDiv.style.cssText = `
    flex: 1;
    overflow-x: auto;
    padding-top: 4px;
  `
  const preEl = document.createElement('pre')
  preEl.style.cssText = `
    margin: 0;
    padding: 0;
    background: transparent;
    line-height: ${lineHeightPx}px;
    font-size: 14px;
  `
  const codeEl = document.createElement('code')
  codeEl.style.cssText = `
    background: transparent;
    padding: 0;
    display: block;
    white-space: pre;
    line-height: ${lineHeightPx}px;
    font-size: 14px;
  `
  codeEl.innerHTML = highlighted
  preEl.appendChild(codeEl)
  codeContentDiv.appendChild(preEl)

  wrapper.appendChild(lineNumbersDiv)
  wrapper.appendChild(codeContentDiv)

  // hover 高亮效果：通过计算行索引来同步高亮
  const highlightLine = (idx) => {
    if (numEls[idx]) numEls[idx].style.background = '#f5f5f5'
  }
  const unhighlightLine = (idx) => {
    if (numEls[idx]) numEls[idx].style.background = 'transparent'
  }

  numEls.forEach((el, idx) => {
    el.addEventListener('mouseenter', () => highlightLine(idx))
    el.addEventListener('mouseleave', () => unhighlightLine(idx))
  })

  // 代码区域的 hover：通过鼠标位置计算行号
  codeContentDiv.addEventListener('mousemove', (e) => {
    const rect = codeContentDiv.getBoundingClientRect()
    const relativeY = e.clientY - rect.top - 4 + codeContentDiv.scrollTop
    const idx = Math.floor(relativeY / lineHeightPx)
    if (idx >= 0 && idx < lineCount) {
      codeContentDiv.querySelectorAll('.code-line-hover').forEach(el => el.classList.remove('code-line-hover'))
      highlightLine(idx)
      codeContentDiv.dataset.hoverIdx = String(idx)
    }
  })
  codeContentDiv.addEventListener('mouseleave', () => {
    const idx = parseInt(codeContentDiv.dataset.hoverIdx || '-1')
    if (idx >= 0) unhighlightLine(idx)
    codeContentDiv.dataset.hoverIdx = '-1'
  })

  codeContainer.appendChild(wrapper)
  panel.appendChild(headerDiv)
  panel.appendChild(codeContainer)

  document.body.appendChild(overlay)
  document.body.appendChild(panel)

  // 触发动画
  requestAnimationFrame(() => {
    overlay.style.opacity = '1'
    panel.style.transform = 'translateX(0)'
  })

  // 关闭函数
  const closeModal = () => {
    overlay.style.opacity = '0'
    panel.style.transform = 'translateX(100%)'
    setTimeout(() => {
      if (overlay.parentNode) document.body.removeChild(overlay)
      if (panel.parentNode) document.body.removeChild(panel)
    }, 350)
    document.removeEventListener('keydown', handleEsc)
  }

  closeBtn.onclick = closeModal
  overlay.onclick = closeModal

  const handleEsc = (e) => {
    if (e.key === 'Escape') closeModal()
  }
  document.addEventListener('keydown', handleEsc)
}

// 设置代码块复制功能（使用MutationObserver监听DOM变化）
const setupCodeBlockCopy = () => {
  const observer = new MutationObserver(() => {
    bindCodeBlockEvents()
  })
  
  observer.observe(document.querySelector('.message-list'), {
    childList: true,
    subtree: true
  })
  
  // 初始绑定
  bindCodeBlockEvents()
}

// 处理键盘事件（Enter发送，Shift+Enter换行）
const handleKeyDown = (e) => {
  // 如果按下的是 Enter 键且没有按住 Shift
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault() // 阻止默认的换行行为
    sendMessage() // 发送消息
  }
  // 如果按下的是 Shift + Enter，允许默认换行行为
}

// 格式化耗时
const formatDuration = (seconds) => {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m${s}s`
}

// 格式化响应耗时（毫秒）
const formatResponseTime = (ms) => {
  if (!ms || ms <= 0) return '0ms'
  if (ms < 1000) return `${ms}ms`
  const s = (ms / 1000).toFixed(1)
  return `${s}s`
}

// 复制消息内容到剪贴板
const copyMessageContent = async (content) => {
  try {
    await navigator.clipboard.writeText(content || '')
    ElMessage({ message: '已复制', type: 'success', duration: 1200 })
  } catch (err) {
    ElMessage({ message: '复制失败', type: 'error', duration: 1500 })
  }
}

// 开始计时器
const startTimer = () => {
  elapsedTime.value = 0
  streamTimer = setInterval(() => {
    elapsedTime.value++
  }, 1000)
}

// 停止计时器
const stopTimer = () => {
  if (streamTimer) {
    clearInterval(streamTimer)
    streamTimer = null
  }
}

// 打字机效果：逐字显示
let typewriterDone = false // 标记后端是否已完成
const startTypewriter = () => {
  stopTypewriter()
  // 如果已有内容，立即显示第一个字符，让用户看到响应开始了
  if (fullStreamingText.value.length > 0 && streamingText.value.length === 0) {
    typewriterIndex = 1
    streamingText.value = fullStreamingText.value.substring(0, 1)
    scrollToBottom()
  }
  
  typewriterTimer = setInterval(() => {
    // 如果已完成且打字机已追上全部文本，停止
    if (typewriterDone && typewriterIndex >= fullStreamingText.value.length) {
      stopTypewriter()
      return
    }
    
    // 每次显示若干字符
    const speed = typewriterDone ? 5 : 15 // done后加速：5ms间隔
    const batchSize = typewriterDone ? 3 : 1 // done后每次追加3个字符
    const target = Math.min(typewriterIndex + batchSize, fullStreamingText.value.length)
    
    if (typewriterIndex < target) {
      typewriterIndex = target
      streamingText.value = fullStreamingText.value.substring(0, typewriterIndex)
      scrollToBottom()
    }
  }, typewriterDone ? 5 : 15)
}

// 加速打字机（done 后调用），完成后执行回调
const speedUpTypewriter = (onComplete) => {
  typewriterDone = true
  // 重新启动打字机以应用加速
  stopTypewriter()
  typewriterTimer = setInterval(() => {
    if (typewriterIndex >= fullStreamingText.value.length) {
      stopTypewriter()
      if (onComplete) onComplete()
      return
    }
    const batchSize = 3
    const target = Math.min(typewriterIndex + batchSize, fullStreamingText.value.length)
    typewriterIndex = target
    streamingText.value = fullStreamingText.value.substring(0, typewriterIndex)
    scrollToBottom()
  }, 5)
}

// 停止打字机效果
const stopTypewriter = () => {
  if (typewriterTimer) {
    clearInterval(typewriterTimer)
    typewriterTimer = null
  }
}

// 强制完成打字机效果（立即显示全部文本）
const flushTypewriter = () => {
  stopTypewriter()
  typewriterIndex = fullStreamingText.value.length
  streamingText.value = fullStreamingText.value
  scrollToBottom()
}

// 完成流式输出：添加消息、清理状态、刷新历史
const finishStreaming = (fullAnswer, contextDocs, skillName, responseTimeMs) => {
  stopTimer()
  answering.value = false
  
  // 将完成的 AI 回复添加到消息列表（附带思考过程和真实推理）
  if (fullAnswer) {
    const thinkingSnapshot = [...thinkingSteps.value]
    const reasoningSnapshot = streamingReasoning.value || ''
    messages.value.push({
      content: fullAnswer,
      isUser: false,
      contextDocs: contextDocs || [],
      skill: skillName || null,
      responseTime: responseTimeMs,
      thinkingProcess: thinkingSnapshot.length > 0 ? thinkingSnapshot : undefined,
      reasoningText: reasoningSnapshot || undefined,
    })
    scrollToBottom()
    // 刷新历史列表
    loadChatHistory()
  }
  
  // 清理流式状态
  streamingText.value = ''
  streamingReasoning.value = ''
  thinkingSteps.value = []
  currentThinkingStatus.value = ''
}

// ========== 多Agent工作流 ==========

// Agent 名称映射
const getAgentLabel = (agent) => {
  const map = {
    'plan': '规划Agent',
    'planner': '规划Agent', 
    'generate': '用例生成Agent',
    'testcase_gen': '用例生成Agent',
    'executor': '执行Agent',
    'execution': '执行Agent',
    'verify': '验证Agent',
    'verification': '验证Agent',
    'evaluator': '评估Agent',
    'report': '报告Agent',
  }
  return map[agent] || agent || 'Agent'
}

// 发送工作流请求（SSE流式）
const sendWorkflowMessage = async (userQuestion) => {
  // 添加用户消息
  messages.value.push({ content: userQuestion, isUser: true })
  scrollToBottom()

  // 初始化工作流状态
  answering.value = true
  workflowSteps.value = []
  workflowDone.value = false
  workflowError.value = false
  workflowResult.value = ''
  startTimer()
  workflowAbortController = new AbortController()

  try {
    const token = localStorage.getItem('access_token')
    const response = await fetch(`${api.defaults.baseURL}/agent/tasks/workflow_stream/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        user_request: userQuestion,
        knowledge_base_id: kbId.value || null,
      }),
      signal: workflowAbortController.signal,
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    workflowReader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let resultText = ''

    while (true) {
      const { done, value } = await workflowReader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = ''

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim()
        if (!line || !line.startsWith('data: ')) {
          if (i === lines.length - 1 && !line.startsWith('data: ')) {
            buffer = line
          }
          continue
        }

        try {
          const raw = line.substring(6)
          const event = JSON.parse(raw)
          handleWorkflowEvent(event, resultText)
          
          // 累积结果文本
          if (event.event === 'workflow_complete' && event.data?.result) {
            resultText = typeof event.data.result === 'string' 
              ? event.data.result 
              : JSON.stringify(event.data.result, null, 2)
          }
        } catch (parseError) {
          if (parseError.message?.startsWith('data.')) {
            console.warn('Workflow SSE parse error:', parseError)
          } else {
            throw parseError
          }
        }
      }
    }

    // 流结束，标记完成
    if (!workflowAbortController) {
      // 切换模式或停止时，已在 switchMode/stopWorkflow 中保存了状态，不要覆盖
      answering.value = false
      stopTimer()
      return
    }
    workflowDone.value = true
    answering.value = false
    stopTimer()

    // 保存到消息列表
    const finalText = workflowResult.value || '工作流执行完成'
    messages.value.push({
      content: finalText,
      isUser: false,
      skill: '多Agent工作流',
      responseTime: elapsedTime.value * 1000,
    })
    scrollToBottom()
    loadChatHistory()

    // 同步保存到 modeState
    modeState.workflow.workflowSteps = [...workflowSteps.value]
    modeState.workflow.workflowDone = true
    modeState.workflow.workflowError = false
    modeState.workflow.workflowResult = finalText

  } catch (error) {
    if (error.name === 'AbortError') {
      console.log('用户停止了工作流')
      return
    }
    console.error('Workflow error:', error)
    workflowError.value = true
    answering.value = false
    stopTimer()

    const errorStep = {
      label: '错误',
      agent: '系统',
      description: error.message || '工作流执行失败',
      status: 'failed',
      error: error.message || '未知错误',
    }
    workflowSteps.value = [...workflowSteps.value, errorStep]
    
    messages.value.push({
      content: '工作流执行失败: ' + (error.message || '未知错误'),
      isUser: false,
    })
    scrollToBottom()

    // 同步保存到 modeState
    modeState.workflow.workflowSteps = [...workflowSteps.value]
    modeState.workflow.workflowDone = false
    modeState.workflow.workflowError = true
    modeState.workflow.workflowResult = error.message || '未知错误'
  } finally {
    workflowReader = null
    workflowAbortController = null
  }
}

// 处理工作流 SSE 事件
const handleWorkflowEvent = (event, _resultText) => {
  const type = event.event || event.type || ''
  const data = event.data || event

  switch (type) {
    case 'plan_start':
      workflowSteps.value = [...workflowSteps.value, {
        label: '制定计划',
        agent: '规划Agent',
        description: data.message || '正在分析需求，制定测试计划...',
        status: 'running',
      }]
      break

    case 'plan_complete':
      // 更新规划步骤为完成
      workflowSteps.value = workflowSteps.value.map(s =>
        s.agent === '规划Agent' && s.status === 'running' ? { ...s, status: 'done', detail: data.plan || data.message } : s
      )
      break

    case 'step_start':
      workflowSteps.value = [...workflowSteps.value, {
        label: data.label || data.name || '执行步骤',
        agent: data.agent || data.name || 'Agent',
        description: data.message || data.description || '正在执行...',
        status: 'running',
      }]
      break

    case 'step_progress':
      // 更新当前运行步骤
      workflowSteps.value = workflowSteps.value.map(s =>
        s.status === 'running' ? { ...s, description: data.message || s.description, detail: data.detail || s.detail } : s
      )
      break

    case 'step_complete':
      workflowSteps.value = workflowSteps.value.map(s =>
        s.status === 'running' ? { ...s, status: 'done', description: data.message || s.description, detail: data.result || s.detail, duration: data.duration } : s
      )
      break

    case 'step_failed':
      workflowSteps.value = workflowSteps.value.map(s =>
        s.status === 'running' ? { ...s, status: 'failed', error: data.error || data.message } : s
      )
      break

    case 'workflow_complete':
      workflowDone.value = true
      workflowResult.value = data.summary || data.result || data.message || '工作流执行完成'
      // 将所有 running 步骤标记为完成
      workflowSteps.value = workflowSteps.value.map(s =>
        s.status === 'running' ? { ...s, status: 'done' } : s
      )
      break

    case 'final_result':
      // 后端推送完整执行结果
      {
        const resultData = event.data || data
        let displayText = ''
        if (typeof resultData === 'string') {
          displayText = resultData
        } else if (resultData.summary) {
          displayText = resultData.summary
          if (resultData.results && resultData.results.length > 0) {
            displayText += '\n\n---\n'
            resultData.results.forEach((r, idx) => {
              const agentName = r.agent || `步骤${idx + 1}`
              const status = r.status === 'completed' ? '✅' : '❌'
              const result = r.result ? (typeof r.result === 'string' ? r.result : JSON.stringify(r.result, null, 2)) : ''
              displayText += `\n${status} ${agentName}\n${result ? result.substring(0, 500) : '无输出'}\n`
            })
          }
        } else {
          displayText = JSON.stringify(resultData, null, 2)
        }
        workflowResult.value = displayText
      }
      break

    case 'workflow_error':
    case 'error':
      workflowError.value = true
      workflowSteps.value = [...workflowSteps.value, {
        label: '错误',
        agent: '系统',
        description: data.message || '执行出错',
        status: 'failed',
        error: data.message || '',
      }]
      break

    default:
      // 未知事件类型，记录但继续
      if (event.event && event.data) {
        console.log('[Workflow] Unhandled event:', type, data)
      }
      break
  }

  scrollToBottom()
}

// 停止工作流
const stopWorkflow = () => {
  if (workflowReader) {
    try { workflowReader.cancel() } catch (e) { /* ignore */ }
    workflowReader = null
  }
  if (workflowAbortController) {
    workflowAbortController.abort()
    workflowAbortController = null
  }
  answering.value = false
  stopTimer()
  // 同步保存到 modeState
  modeState.workflow.workflowSteps = [...workflowSteps.value]
  ElMessage.info('已停止工作流')
}

// 停止流式输出
const stopStreaming = () => {
  if (!answering.value) return
  
  // 1. 取消 reader
  if (streamReader) {
    try { streamReader.cancel() } catch (e) { /* ignore */ }
    streamReader = null
  }
  
  // 2. Abort fetch
  if (streamAbortController) {
    streamAbortController.abort()
    streamAbortController = null
  }
  
  // 3. 保存当前已显示的内容作为完整回答
  const currentAnswer = streamingText.value || fullStreamingText.value
  if (currentAnswer) {
    const thinkingSnapshot = [...thinkingSteps.value]
    const reasoningSnapshot = streamingReasoning.value || ''
    messages.value.push({
      content: currentAnswer,
      isUser: false,
      contextDocs: [],
      skill: activeSkill.value?.name || null,
      responseTime: elapsedTime.value * 1000,
      thinkingProcess: thinkingSnapshot.length > 0 ? thinkingSnapshot : undefined,
      reasoningText: reasoningSnapshot || undefined,
    })
    scrollToBottom()
    // 延迟刷新历史列表，等待后端保存完成（GeneratorExit 处理需要时间）
    setTimeout(() => loadChatHistory(), 500)
  }
  
  // 4. 清理流式状态
  stopTimer()
  stopTypewriter()
  answering.value = false
  streamingText.value = ''
  fullStreamingText.value = ''
  streamingReasoning.value = ''
  thinkingSteps.value = []
  currentThinkingStatus.value = ''
  
  ElMessage.info('已停止生成')
}

// 发送问题
const sendMessage = async () => {
  if ((!question.value.trim() && pendingImages.value.length === 0) || answering.value) return

  // 没有可用知识库（kbId 无效），阻止发送并提示
  if (kbNotFound.value || !kbId.value || !Number.isFinite(Number(kbId.value)) || Number(kbId.value) <= 0) {
    ElMessage.warning('请先创建或选择一个知识库，才能进行对话')
    return
  }

  const userQuestion = question.value.trim()
  const userImages = [...pendingImages.value]
  question.value = ''
  pendingImages.value = []

  // 工作流模式：走多Agent工作流
  if (qaMode.value === 'workflow') {
    await sendWorkflowMessage(userQuestion)
    return
  }

  // 添加用户消息（包含图片）
  messages.value.push({ content: userQuestion, isUser: true, images: userImages })
  scrollToBottom()

    // 初始化流式状态：不再伪造“AI 正在连接”步骤，等后端推送真实状态
    answering.value = true
    streamingText.value = ''
    streamingReasoning.value = ''
    thinkingSteps.value = []
    currentThinkingStatus.value = '思考中...'
    startTimer()
    streamAbortController = new AbortController()

  let streamDone = false

  try {
    // 只在对话模式下使用 Skill，知识库模式不需要角色设定
    const isChatMode = qaMode.value === 'chat'
    const systemPrompt = isChatMode ? (activeSkill.value?.systemPrompt || undefined) : undefined
    const skillName = isChatMode ? (activeSkill.value?.name || undefined) : undefined

    // 使用流式 SSE API（带 AbortController）
    const response = await fetch(
      `${api.defaults.baseURL}/knowledge/knowledge-bases/${kbId.value}/ask_stream/`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify({
          question: userQuestion,
          session_id: currentSessionId.value || undefined,
          mode: qaMode.value,
          system_prompt: systemPrompt,
          skill_name: skillName,
          enable_reasoning: reasoningMode.value === 'reasoning',
          images: userImages.length > 0 ? userImages : undefined,
        }),
        signal: streamAbortController.signal,
      }
    )

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    streamReader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let fullAnswer = ''
    let contextDocs = []
    let responseTimeMs = 0
    let aiMessageIndex = -1

    while (true) {
      const { done, value } = await streamReader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // 按 SSE 事件块分隔符 \n\n 切分，只处理完整的事件块
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop() || ''

      for (const block of blocks) {
        processSSEBlock(block)
      }
    }

    // 流结束时，处理最后可能未以 \n\n 结尾的残留块
    if (buffer.trim()) {
      processSSEBlock(buffer.trim())
    }

    function processSSEBlock(block) {
      const lines = block.split('\n')
      for (const rawLine of lines) {
        const line = rawLine.trim()
        if (!line || !line.startsWith('data: ')) continue

        const payload = line.substring(6)
        if (payload === '[DONE]') continue

        try {
          const data = JSON.parse(payload)

          switch (data.type) {
            case 'meta':
              // 接收 session_id 和 skill 信息
              if (data.session_id && !currentSessionId.value) {
                currentSessionId.value = data.session_id
              }
              break

            case 'status':
              // 后端推送的进度提示（检索中、生成中）—— 累积为思考步骤
              if (data.content) {
                currentThinkingStatus.value = data.content
                thinkingSteps.value = [...thinkingSteps.value, data.content]
              }
              break
            
            case 'reasoning':
              // 模型真正的链式推理文本 —— 流式累积显示在深度思考面板
              if (data.content) {
                streamingReasoning.value += data.content
              }
              break
            
            case 'token':
              // 直接追加显示（不再使用打字机延迟）
              fullAnswer += data.content
              streamingText.value = fullAnswer
              scrollToBottom()
              break
            
            case 'done':
              // 流式完成
              streamDone = true
              fullAnswer = data.full_answer || fullAnswer
              contextDocs = data.context_docs || []
              // 记录后端计算的响应耗时（毫秒）
              if (data.response_time) {
                responseTimeMs = data.response_time
              }
              // 直接完成流式输出
              finishStreaming(fullAnswer, contextDocs, skillName, responseTimeMs)
              break
            
            case 'error':
              throw new Error(data.message || '未知错误')
          }
        } catch (parseError) {
          // JSON 解析失败，跳过该条消息，避免整流失败
          console.warn('SSE parse error:', parseError, 'payload:', payload)
        }
      }
    }

    // 如果流结束但没有收到 done 事件（异常情况），也完成
    if (!streamDone) {
      finishStreaming(fullAnswer, contextDocs, skillName, responseTimeMs)
    }
  } catch (error) {
    // 用户主动取消不算错误
    if (error.name === 'AbortError') {
      console.log('用户停止了流式输出')
      return
    }
    console.error('Ask stream error:', error)
    messages.value.push({
      content: '抱歉，回答失败，请稍后重试。',
      isUser: false,
    })
  } finally {
    stopTimer()
    if (!streamDone) {
      answering.value = false
      streamingText.value = ''
      thinkingSteps.value = []
      currentThinkingStatus.value = ''
    }
    streamReader = null
    streamAbortController = null
  }
}

// 滚动到底部
const scrollToBottom = async () => {
  await nextTick()
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

// 显示文档管理对话框
const showDocumentDialog = async () => {
  documentDialogVisible.value = true
  await loadDocuments()
}

// 加载文档列表
const loadDocuments = async () => {
  documentsLoading.value = true
  try {
    const res = await knowledgeBaseAPI.getDocuments(kbId.value)
    documents.value = res.results || []
  } catch (error) {
    console.error('Load documents error:', error)
    ElMessage.error('加载文档列表失败')
  } finally {
    documentsLoading.value = false
  }
}

// 删除文档
const deleteDocument = async (docId) => {
  try {
    await ElMessageBox.confirm('确定要删除该文档吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await knowledgeBaseAPI.deleteDocument(docId)
    ElMessage.success('删除成功')
    // 刷新文档列表
    await loadDocuments()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Delete document error:', error)
      ElMessage.error('删除失败')
    }
  }
}

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

// 下载文档
const downloadDocument = async (doc) => {
  try {
    ElMessage.info('正在准备下载...')
    
    // 使用axios获取文件，自动携带token
    const response = await api.get(`/knowledge/documents/${doc.id}/download/`, {
      responseType: 'blob'
    })
    
    // 创建Blob URL
    const blob = new Blob([response])
    const url = window.URL.createObjectURL(blob)
    
    // 创建隐藏的a标签进行下载
    const link = document.createElement('a')
    link.href = url
    link.download = doc.title || `document.${doc.file_type}`
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    
    // 释放Blob URL
    window.URL.revokeObjectURL(url)
    
    ElMessage.success(`文档 "${doc.title}" 下载成功`)
  } catch (error) {
    console.error('Download error:', error)
    ElMessage.error('下载失败，请重试')
  }
}

// ========== 测试用例数据提取与下载 ==========

// 判断消息内容是否包含可提取的测试用例数据
const hasExtractableData = (content) => {
  if (!content) return false
  // 快速预检：包含 Markdown 表格 或 JSON 代码块
  const hasTable = /\|.+\|/.test(content)
  const hasJsonBlock = /```(?:json)?\s*\n[\s\S]*?```/.test(content)
  return hasTable || hasJsonBlock
}

// 从AI回复内容中提取测试用例（Markdown表格或JSON代码块）
const extractTestCases = (content) => {
  if (!content || typeof content !== 'string') return []
  
  const testCases = []
  
  // 策略1：尝试从 Markdown 代码块中提取 JSON
  const jsonBlockRegex = /```(?:json)?\s*\n([\s\S]*?)```/g
  let match
  while ((match = jsonBlockRegex.exec(content)) !== null) {
    try {
      const parsed = JSON.parse(match[1].trim())
      if (Array.isArray(parsed)) {
        testCases.push(...parsed)
      } else if (parsed.test_cases || parsed.testcases || parsed.cases) {
        const arr = parsed.test_cases || parsed.testcases || parsed.cases
        if (Array.isArray(arr)) testCases.push(...arr)
      }
    } catch {
      // 不是有效JSON，跳过
    }
  }
  
  // 策略2：尝试从 Markdown 表格中提取（放宽条件，只要包含表格就提取）
  const tableRegex = /\|(.+)\|\n\|[\s\-:|]+\|\n((?:\|.+\|\n?)+)/g
  while ((match = tableRegex.exec(content)) !== null) {
    const headerRow = match[1]
    const bodyRows = match[2]
    
    // 解析表头
    const headers = headerRow.split('|')
      .map(h => h.trim().toLowerCase())
      .filter(h => h)
    
    // 只要是一个有效的表格（有表头有数据行），就提取
    if (headers.length > 0) {
      const rows = bodyRows.trim().split('\n')
      for (const row of rows) {
        const cells = row.split('|')
          .map(c => c.trim())
          .filter(c => c !== '')
        if (cells.length > 0) {
          const testCase = {}
          headers.forEach((header, i) => {
            if (i < cells.length) {
              testCase[header] = cells[i]
            }
          })
          // 补全缺失的列
          if (cells.length > headers.length) {
            for (let i = headers.length; i < cells.length; i++) {
              testCase[`col_${i}`] = cells[i]
            }
          }
          testCases.push(testCase)
        }
      }
    }
  }
  
  return testCases
}

// 触发下载文件
const triggerDownload = (content, filename, mimeType) => {
  const blob = new Blob([content], { type: mimeType })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

// ========== 场景1：下载测试数据（JSON/CSV）—— 导入测试管理平台用 ==========
const downloadTestData = (msg, format = 'json') => {
  try {
    const testCases = extractTestCases(msg.content)
    if (testCases.length === 0) {
      ElMessage.warning('未检测到可导出的测试用例数据')
      return
    }
    
    // 收集所有字段，并按常见优先级排序
    const priorityOrder = ['id', 'title', 'name', 'description', 'precondition', 
      'steps', 'expected', 'expected_result', 'priority', 'severity', 'type', 
      'category', 'tag', 'status', 'url', 'method', 'request_params', 
      'request_body', 'expected_response', 'author', 'module']
    const allKeys = new Set()
    testCases.forEach(tc => Object.keys(tc).forEach(k => allKeys.add(k)))
    const headers = [
      ...priorityOrder.filter(k => allKeys.has(k)),
      ...Array.from(allKeys).filter(k => !priorityOrder.includes(k))
    ]
    
    const dateStr = new Date().toISOString().slice(0, 10)
    
    if (format === 'json') {
      const exportData = {
        generated_at: new Date().toISOString(),
        tool: 'AI Test Platform',
        skill: msg.skill || 'AI Generated',
        total: testCases.length,
        test_cases: testCases.map(tc => {
          const ordered = {}
          headers.forEach(h => { ordered[h] = tc[h] !== undefined ? tc[h] : '' })
          return ordered
        }),
      }
      const jsonStr = JSON.stringify(exportData, null, 2)
      triggerDownload(jsonStr, `testcases_${dateStr}.json`, 'application/json')
      ElMessage.success(`已导出 ${testCases.length} 条测试数据 → testcases_${dateStr}.json（可导入禅道/Jira/Xray）`)
    } else if (format === 'csv') {
      // CSV 格式（兼容中文 BOM）
      const csvHeaders = headers.join(',')
      const csvRows = testCases.map(tc => 
        headers.map(h => {
          const val = tc[h] !== undefined ? String(tc[h]) : ''
          // 包含逗号或换行时用引号包裹
          return val.includes(',') || val.includes('\n') || val.includes('"') 
            ? `"${val.replace(/"/g, '""')}"` 
            : val
        }).join(',')
      )
      const csvContent = '\uFEFF' + csvHeaders + '\n' + csvRows.join('\n')
      triggerDownload(csvContent, `testcases_${dateStr}.csv`, 'text/csv;charset=utf-8')
      ElMessage.success(`已导出 ${testCases.length} 条测试数据 → testcases_${dateStr}.csv（可导入禅道/Jira/Xray）`)
    }
  } catch (error) {
    console.error('Test data download error:', error)
    ElMessage.error('导出测试数据失败')
  }
}

// ========== 场景2：下载完整文档（Excel/Word）—— 人工评审用 ==========
const downloadFullDocument = (msg, format = 'excel') => {
  try {
    const testCases = extractTestCases(msg.content)
    if (testCases.length === 0) {
      ElMessage.warning('未检测到可导出的测试用例数据')
      return
    }
    
    // 提取AI回复中的纯文本（去掉Markdown标记，保留内容）
    const rawContent = msg.content || ''
    // 提取概述/总结部分（表格之前的内容）
    const summaryMatch = rawContent.match(/^([\s\S]*?)(?=\|)/)
    const summary = summaryMatch ? summaryMatch[1].trim() : ''
    // 提取表格后的补充说明
    const afterTable = rawContent.replace(/[\s\S]*?\n((?:\|.+\|\n)+)/, '').trim()
    
    const dateStr = new Date().toISOString().slice(0, 10)
    const timeStr = new Date().toLocaleString('zh-CN')
    
    if (format === 'excel') {
      downloadFullExcel(testCases, summary, afterTable, msg, dateStr, timeStr)
    } else if (format === 'word') {
      downloadFullWord(testCases, summary, afterTable, msg, dateStr, timeStr)
    }
  } catch (error) {
    console.error('Full document download error:', error)
    ElMessage.error('导出完整文档失败')
  }
}

// Excel 完整文档（多Sheet：测试思路 + 用例明细 + 生成说明）
const downloadFullExcel = (testCases, summary, afterTable, msg, dateStr, timeStr) => {
  // 规范化列名
  const normalizeHeader = (key) => {
    const map = {
      'id': '用例编号', 'title': '用例名称', 'name': '用例名称',
      'steps': '测试步骤', 'expected': '预期结果', 'expected_result': '预期结果',
      'priority': '优先级', 'precondition': '前置条件', 'description': '描述',
      'status': '状态', 'type': '类型', 'url': '接口地址', 'method': '请求方法',
      'request_params': '请求参数', 'request_body': '请求体',
      'expected_response': '预期响应', 'severity': '严重程度',
      'category': '分类', 'tag': '标签', 'author': '作者', 'module': '模块',
    }
    return map[key] || key
  }
  
  // 收集所有字段
  const allKeys = new Set()
  testCases.forEach(tc => Object.keys(tc).forEach(k => allKeys.add(k)))
  const headers = Array.from(allKeys)
  
  const dataRows = testCases.map(tc => {
    const row = {}
    headers.forEach(h => { row[normalizeHeader(h)] = tc[h] !== undefined ? tc[h] : '' })
    return row
  })
  
  const wb = XLSX.utils.book_new()
  
  // Sheet 1: 用例明细
  const ws1 = XLSX.utils.json_to_sheet(dataRows, { header: headers.map(normalizeHeader) })
  ws1['!cols'] = headers.map(h => ({
    wch: Math.min(Math.max(normalizeHeader(h).length, ...testCases.map(tc => {
      const v = tc[h]; return v ? String(v).length : 0
    })) + 4, 60)
  }))
  XLSX.utils.book_append_sheet(wb, ws1, '用例明细')
  
  // Sheet 2: 测试思路总结
  const summaryRows = []
  if (summary) {
    summary.split('\n').filter(l => l.trim()).forEach(line => {
      summaryRows.push({ '测试思路': line.replace(/^[#*-]+\s*/, '') })
    })
  } else {
    summaryRows.push({ '测试思路': '（由AI自动生成）' })
  }
  const ws2 = XLSX.utils.json_to_sheet(summaryRows)
  ws2['!cols'] = [{ wch: 80 }]
  XLSX.utils.book_append_sheet(wb, ws2, '测试思路')
  
  // Sheet 3: 生成说明
  const infoRows = [
    { '项目': '生成工具', '内容': 'AI Test Platform' },
    { '项目': '使用技能', '内容': msg.skill || 'AI Generated' },
    { '项目': '生成时间', '内容': timeStr },
    { '项目': '用例总数', '内容': String(testCases.length) },
    { '项目': '备注', '内容': afterTable || '本文件由AI自动生成，供人工评审使用' },
  ]
  const ws3 = XLSX.utils.json_to_sheet(infoRows)
  ws3['!cols'] = [{ wch: 15 }, { wch: 60 }]
  XLSX.utils.book_append_sheet(wb, ws3, '生成说明')
  
  const filename = `测试用例完整文档_${dateStr}.xlsx`
  XLSX.writeFile(wb, filename)
  ElMessage.success(`已导出完整文档 → ${filename}（含用例明细+测试思路+生成说明）`)
}

// Word 完整文档（HTML格式转 .doc，Word 可直接打开）
const downloadFullWord = (testCases, summary, afterTable, msg, dateStr, timeStr) => {
  // 构建HTML内容
  const caseRows = testCases.map((tc, i) => {
    const cells = []
    if (tc.id) cells.push(`<td>${escapeHtml(String(tc.id))}</td>`)
    else cells.push(`<td>${i + 1}</td>`)
    if (tc.title || tc.name) cells.push(`<td>${escapeHtml(String(tc.title || tc.name))}</td>`)
    if (tc.steps) cells.push(`<td>${escapeHtml(String(tc.steps))}</td>`)
    if (tc.expected || tc.expected_result) cells.push(`<td>${escapeHtml(String(tc.expected || tc.expected_result))}</td>`)
    if (tc.priority) cells.push(`<td>${escapeHtml(String(tc.priority))}</td>`)
    return `<tr>${cells.join('')}</tr>`
  }).join('\n')
  
  // 动态生成表头
  const sampleTc = testCases[0] || {}
  const colHeaders = []
  if (sampleTc.id) colHeaders.push('用例编号')
  else colHeaders.push('序号')
  if (sampleTc.title || sampleTc.name) colHeaders.push('用例名称')
  if (sampleTc.steps) colHeaders.push('测试步骤')
  if (sampleTc.expected || sampleTc.expected_result) colHeaders.push('预期结果')
  if (sampleTc.priority) colHeaders.push('优先级')
  
  const htmlContent = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>测试用例完整文档</title>
  <style>
    body { font-family: 'Microsoft YaHei', sans-serif; padding: 20px; color: #333; }
    h1 { color: #409eff; border-bottom: 2px solid #409eff; padding-bottom: 10px; }
    h2 { color: #67c23a; margin-top: 24px; }
    table { border-collapse: collapse; width: 100%; margin: 16px 0; }
    th { background: #409eff; color: white; padding: 10px 8px; text-align: left; font-size: 14px; }
    td { border: 1px solid #dcdfe6; padding: 8px; font-size: 13px; }
    tr:nth-child(even) td { background: #f5f7fa; }
    .summary { background: #ecf5ff; padding: 16px; border-radius: 8px; margin: 16px 0; white-space: pre-wrap; }
    .meta { color: #909399; font-size: 12px; margin-top: 20px; }
  </style>
</head>
<body>
  <h1>测试用例完整文档</h1>
  <div class="meta">生成时间：${escapeHtml(timeStr)} &nbsp;|&nbsp; 使用技能：${escapeHtml(msg.skill || 'AI Generated')} &nbsp;|&nbsp; 共 ${testCases.length} 条</div>
  
  <h2>一、测试思路</h2>
  <div class="summary">${escapeHtml(summary || '（由AI自动生成）')}</div>
  
  <h2>二、用例明细</h2>
  <table>
    <thead><tr>${colHeaders.map(h => `<th>${h}</th>`).join('')}</tr></thead>
    <tbody>${caseRows}</tbody>
  </table>
  
  ${afterTable ? `<h2>三、补充说明</h2><div class="summary">${escapeHtml(afterTable)}</div>` : ''}
  
  <div class="meta">本文件由 AI Test Platform 自动生成，供人工评审使用。</div>
</body>
</html>`
  
  triggerDownload(htmlContent, `测试用例完整文档_${dateStr}.doc`, 'application/msword')
  ElMessage.success(`已导出完整文档 → 测试用例完整文档_${dateStr}.doc（可用Word打开）`)
}

// 格式化时间（时分）
const formatTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

// 格式化日期（完整时间）
const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(async () => {
  await loadKnowledgeBase()  // 先加载知识库，确保kbId就绪
  if (kbId.value && !kbNotFound.value && Number.isFinite(Number(kbId.value))) {
    loadChatHistory()       // kbId有效才加载对话历史
  }
  setupCodeBlockCopy()
  loadSkills() // 加载 Skills
})

onUnmounted(() => {
  stopTimer()
  stopTypewriter()
  if (streamReader) {
    try { streamReader.cancel() } catch (e) { /* ignore */ }
    streamReader = null
  }
  if (streamAbortController) {
    streamAbortController.abort()
    streamAbortController = null
  }
  // 清理工作流资源
  if (workflowReader) {
    try { workflowReader.cancel() } catch (e) { /* ignore */ }
    workflowReader = null
  }
  if (workflowAbortController) {
    workflowAbortController.abort()
    workflowAbortController = null
  }
})
</script>

<style scoped>
.knowledge-chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: white;
}

.chat-header {
  display: flex;
  align-items: center;
  padding: 15px 20px;
  border-bottom: 1px solid #e4e7ed;
}

.chat-header h3 {
  margin-left: 10px;
  font-size: 18px;
  font-weight: 500;
}

.chat-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.history-panel-wrapper {
  display: flex;
  flex-direction: column;
  width: 280px;
  min-width: 280px;
  border-right: 1px solid #e4e7ed;
  background: #f5f7fa;
  transition: width 0.25s ease, min-width 0.25s ease;
  overflow: hidden;
}

.history-panel-wrapper.collapsed {
  width: 40px;
  min-width: 40px;
}

.history-collapsed-bar {
  width: 40px;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #909399;
  transition: background 0.2s, color 0.2s;
  border-right: 1px solid #e4e7ed;
}

.history-collapsed-bar:hover {
  background: #e4e7ed;
  color: #409eff;
}

.history-panel-expanded {
  display: flex;
  flex-direction: column;
  width: 280px;
  flex: 1;
  overflow: hidden;
}

.history-panel-header-compact {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #e4e7ed;
  background: #f5f7fa;
  flex-shrink: 0;
}

.history-panel-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.history-panel-wrapper .history-panel {
  flex: 1;
  border-right: none;
  background: transparent;
}

.history-panel-wrapper :deep(.history-header) {
  display: none; /* 使用新的 compact header */
}

/* .history-panel 旧样式兼容 */
.history-panel {
  width: 280px;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  background: #e5e7eb; /* 更深的灰色背景，与气泡形成更好对比 */
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e4e7ed;
  font-weight: 500;
  background: #e5e7eb; /* 与面板背景一致 */
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}

.empty-history {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

/* 各模式专属空状态 */
.empty-mode-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 24px 16px;
  text-align: center;
}

.empty-mode-icon {
  color: #909399;
  margin-bottom: 4px;
}

.empty-mode-text {
  font-size: 14px;
  color: #606266;
  margin: 0;
  font-weight: 500;
}

.empty-mode-hint {
  font-size: 12px;
  color: #909399;
  margin: 0;
  line-height: 1.5;
}

/* 骨架屏加载态 */
.skeleton-list {
  width: 100%;
  padding: 8px 0;
}

.skeleton-item {
  padding: 10px 0;
}

.skeleton-line {
  display: block;
  height: 14px;
  background: linear-gradient(90deg, #e8e8e8 25%, #f5f5f5 50%, #e8e8e8 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
  border-radius: 4px;
  width: 80%;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 模式徽章 */
.history-mode-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
  white-space: nowrap;
}

.history-mode-badge.badge-chat {
  background: #ecf5ff;
  color: #409eff;
}

.history-mode-badge.badge-knowledge {
  background: #f0f9eb;
  color: #67c23a;
}

.history-mode-badge.badge-workflow {
  background: #fef0f0;
  color: #e6a23c;
}

/* 历史项无障碍焦点 */
.history-item:focus-visible {
  outline: 2px solid #409eff;
  outline-offset: -1px;
  border-radius: 6px;
}

.history-group {
  margin-bottom: 28px;
}

.group-title {
  font-size: 12px;
  color: #4a4e57; /* 更深的灰色，与更深的背景形成更好对比 */
  padding: 8px 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* 历史项目 - 气泡式设计 */
.history-item {
  padding: 12px 16px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: all 0.2s;
  background: #dcdfe6; /* 更深的灰色底色，增强对比度 */
  border-radius: 20px; /* 圆角气泡效果 */
  display: flex;
  align-items: flex-start; /* 改为顶部对齐，适应多行文本 */
  gap: 8px;
  min-height: 48px; /* 最小高度，确保单行时也有足够空间 */
}

.history-item:hover {
  background: #c0c4cc; /* 悬停时更深 */
}

/* 激活状态（当前选中的对话） */
.history-item.active {
  background: #409eff; /* 蓝色气泡 */
  color: white;
}

.history-item.active:hover {
  background: #409eff;
}

/* 批量选择模式下的样式 */
.history-item.selected {
  background: #ffe0b2; /* 橙色气泡，更深一些 */
}

.history-item.selected:hover {
  background: #ffcc80;
}

.item-title {
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2; /* 最多显示2行 */
  -webkit-box-orient: vertical;
  flex: 1;
  min-width: 0;
  line-height: 1.4;
  word-break: break-all;
}

.item-time {
  font-size: 12px;
  color: #4a4e57; /* 更深的灰色，与更深的背景形成更好对比 */
  flex-shrink: 0;
}

.history-item.active .item-time {
  color: rgba(255, 255, 255, 0.8);
}

.history-item.selected .item-time {
  color: #e6a23c; /* 更深的橙色 */
}

/* 删除按钮 - 只在悬停时显示 */
.delete-btn {
  opacity: 0;
  transition: opacity 0.2s ease;
  padding: 4px;
  flex-shrink: 0;
  color: #f56c6c !important;
}

.history-item:hover .delete-btn {
  opacity: 1;
}

/* 激活状态下的删除按钮使用白色背景增强对比度 */
.history-item.active .delete-btn {
  background: rgba(255, 255, 255, 0.9);
  border-radius: 4px;
}

.history-item.active .delete-btn:hover {
  background: #ffffff;
}

.delete-btn:hover {
  background: #fef0f0 !important;
}

/* 复选框样式 - 简洁设计 */
.item-checkbox {
  flex-shrink: 0;
  margin-right: 4px;
}

.history-item .el-checkbox__inner {
  width: 16px !important;
  height: 16px !important;
  border-color: #909399 !important; /* 更深的边框颜色，与更深的背景形成更好对比 */
  border-width: 2px !important;
}

.history-item .el-checkbox__inner:hover {
  border-color: #409eff !important;
}

.history-item.active .el-checkbox__inner,
.history-item.selected .el-checkbox__inner {
  background-color: #409eff !important;
  border-color: #409eff !important;
}

.history-item .el-checkbox__input {
  padding: 4px;
  margin: -4px;
}

.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0; /* 防止flex子元素溢出 */
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
  min-height: 0; /* 允许正确滚动 */
  background: #fafafa;
}

.welcome-message {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 200px; /* 确保有足够的高度 */
}

/* 自定义欢迎内容样式 */
.welcome-content {
  text-align: center;
  padding: 40px;
}

.welcome-icon {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
  transition: all 0.3s ease;
}

/* 日常对话模式 - 蓝色渐变 */
.welcome-icon.icon-chat {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.3);
}

.welcome-icon.icon-chat .el-icon {
  color: white;
}

/* 知识库问答模式 - 绿色渐变 */
.welcome-icon.icon-knowledge {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  box-shadow: 0 8px 24px rgba(245, 87, 108, 0.3);
}

.welcome-icon.icon-knowledge .el-icon {
  color: white;
}

.welcome-content h3 {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
}

.welcome-content p {
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
  max-width: 500px;
  margin: 0 auto;
}

.message-item {
  display: flex;
  gap: 16px;
  margin-bottom: 28px;
  align-items: flex-start;
}

.user-message {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
}

/* AI助手头像 - 科技感渐变圆形 */
.avatar-ai {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
  transition: all 0.3s ease;
}

.avatar-ai .el-icon {
  color: white;
}

.avatar-ai:hover {
  transform: scale(1.1);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

/* 用户头像 - 柴犬形象 */
.avatar-user {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  box-shadow: 0 2px 8px rgba(245, 87, 108, 0.3);
  transition: all 0.3s ease;
}

.avatar-user:hover {
  transform: scale(1.1);
  box-shadow: 0 4px 12px rgba(245, 87, 108, 0.4);
}

.message-content {
  max-width: 75%;
  min-width: 0;
}

.user-message .message-content {
  text-align: right;
}

/* AI思考状态指示器 */
.thinking-indicator {
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.thinking-dots {
  display: flex;
  gap: 4px;
}

.thinking-dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #409eff;
  animation: bounce 1.4s infinite ease-in-out both;
}

.thinking-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.thinking-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.thinking-text {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

/* 思考中的计时器 */
.thinking-timer {
  font-size: 12px;
  color: #909399;
  margin-left: 8px;
  font-variant-numeric: tabular-nums;
  font-family: 'SF Mono', 'JetBrains Mono', 'Consolas', monospace;
}

/* 思考过程步骤面板 —— 深度思考风格 */
.thinking-steps-panel {
  margin-top: 10px;
  padding: 12px 14px;
  background: #f5f7fa;
  border-radius: 8px;
  border-left: 3px solid #409eff;
  max-height: 320px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
}

.thinking-step-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 5px 0;
  font-size: 13px;
  color: #909399;
  transition: color 0.3s;
}

.thinking-step-item.step-active {
  color: #303133;
  font-weight: 500;
}

.thinking-step-item.step-completed {
  color: #67c23a;
}

.step-icon {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 1px;
}

.step-check {
  font-size: 13px;
  color: #67c23a;
  font-weight: bold;
}

.step-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid #409eff;
  border-top-color: transparent;
  border-radius: 50%;
  animation: step-spin 0.8s linear infinite;
}

@keyframes step-spin {
  to { transform: rotate(360deg); }
}

.step-text {
  line-height: 1.5;
}

/* 暗色模式 */
html.dark .thinking-steps-panel {
  background: #1e1f23;
  border-left-color: #5b9bd5;
  color: #b0b3b8;
}

html.dark .thinking-step-item.step-active {
  color: #e0e0e0;
}

html.dark .thinking-panel-header {
  border-bottom-color: rgba(91, 155, 213, 0.2);
}

html.dark .thinking-panel-title {
  color: #79c0ff;
}

html.dark .thinking-history-steps {
  background: #1e1f23;
  border-left-color: #5b9bd5;
}

html.dark .message-thinking-collapse .el-collapse-item__header {
  color: #79c0ff;
}

html.dark .thinking-collapse-title {
  color: #79c0ff;
}

/* 加载中：思考面板是主要内容，去掉顶部 margin */
.loading-thinking-panel {
  margin-top: 0;
}

/* 流式输出中，思考面板内嵌在消息中 */
.streaming-thinking-panel {
  margin: 0 0 12px 0;
}

/* 思考面板头部 */
.thinking-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.12);
}

.thinking-panel-title {
  font-size: 13px;
  font-weight: 600;
  color: #409eff;
  letter-spacing: 0.3px;
}

.thinking-panel-timer {
  font-size: 11px;
  color: #909399;
  font-family: 'SF Mono', 'JetBrains Mono', 'Consolas', monospace;
}

/* 历史消息中思考过程可折叠区域 */
.message-thinking-collapse {
  margin-top: 10px;
}

.message-thinking-collapse .el-collapse {
  border: none;
}

.message-thinking-collapse .el-collapse-item__header {
  height: 32px;
  line-height: 32px;
  border: none;
  background: transparent;
  padding-left: 0;
  font-size: 13px;
  color: #409eff;
}

.message-thinking-collapse .el-collapse-item__wrap {
  border: none;
  background: transparent;
}

.message-thinking-collapse .el-collapse-item__content {
  padding: 0;
}

.thinking-collapse-title {
  display: flex;
  align-items: center;
  font-size: 13px;
  color: #409eff;
  font-weight: 500;
}

.thinking-response-tag {
  margin-left: 8px;
}

.thinking-history-steps {
  padding: 10px 14px;
  background: #f5f7fa;
  border-radius: 8px;
  border-left: 3px solid #409eff;
}

.thinking-history-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 5px 0;
  font-size: 13px;
  color: #67c23a;
}

.step-check-done {
  font-size: 13px;
  font-weight: bold;
  flex-shrink: 0;
  margin-top: 1px;
}

.step-text-done {
  line-height: 1.5;
}

/* 真实推理文本区域 */
.reasoning-text-area {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed rgba(64, 158, 255, 0.2);
}

.reasoning-text-content {
  font-size: 13px;
  line-height: 1.7;
  color: #4a5568;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
}

.reasoning-text-content p {
  margin: 4px 0;
}

.reasoning-text-content ul, .reasoning-text-content ol {
  margin: 4px 0;
  padding-left: 18px;
}

.reasoning-text-content li {
  margin: 2px 0;
}

.reasoning-text-content strong {
  color: #303133;
}

/* 推理光标闪烁 */
.reasoning-cursor {
  display: inline-block;
  color: #409eff;
  font-size: 14px;
  animation: blink 0.8s infinite;
  margin-left: 2px;
}

/* 推理完成后的样式（不再有光标） */
.reasoning-done {
  border-top-style: solid;
}

/* 暗色模式适配 */
html.dark .reasoning-text-area {
  border-top-color: rgba(91, 155, 213, 0.2);
}

html.dark .reasoning-text-content {
  color: #b0b3b8;
}

html.dark .reasoning-text-content strong {
  color: #e0e0e0;
}

/* 流式输出底部状态栏 */
.streaming-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  margin-top: -4px;
}

.streaming-timer {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #909399;
  font-family: 'SF Mono', 'JetBrains Mono', 'Consolas', monospace;
  font-variant-numeric: tabular-nums;
}

.timer-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #52c41a;
  animation: timer-pulse 2s infinite;
}

@keyframes timer-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* 流式光标闪烁 */
.streaming-cursor {
  font-size: 18px;
  color: #409eff;
  animation: blink-cursor 0.8s infinite;
  line-height: 1;
}

/* 流式输出操作按钮 */
.streaming-actions {
  margin-top: 8px;
}

.stop-stream-btn {
  border-radius: 16px;
  padding: 4px 16px;
  font-size: 12px;
  transition: all 0.2s ease;
}

.stop-stream-btn:hover {
  transform: scale(1.05);
  box-shadow: 0 2px 8px rgba(245, 108, 108, 0.3);
}

@keyframes blink-cursor {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.message-text {
  padding: 16px 20px;
  border-radius: 12px;
  background: #ffffff;
  line-height: 1.7;
  word-wrap: break-word;
  overflow-wrap: break-word;
  word-break: break-word;
  overflow-x: auto;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08), 0 0 1px rgba(0, 0, 0, 0.1);
  border: 1px solid #f0f0f0;
}

.user-message .message-text {
  background: #409eff;
  color: white;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.3);
  border: none;
}

/* 用户消息操作栏：复制按钮 */
.message-user-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 4px;
  padding-right: 4px;
}

.copy-msg-btn {
  height: 24px;
  padding: 0 8px;
  font-size: 12px;
  color: #909399;
  transition: color 0.2s ease;
}

.copy-msg-btn:hover {
  color: #409eff;
}

.copy-msg-btn .el-icon {
  margin-right: 4px;
  font-size: 13px;
}

.copy-btn-text {
  margin-left: 2px;
}

/* ========== AI 消息 Markdown 渲染优化 ========== */
.ai-message-bubble {
  font-size: 14.5px;
  color: #1d1f23;
  line-height: 1.72;
  overflow-wrap: break-word;
  word-break: break-word;
  letter-spacing: -0.005em;
  overflow-x: auto; /* 表格溢出时支持横向滚动 */
}

/* 表格样式（必须用 :deep 穿透 v-html 渲染的 DOM） */
:deep(.ai-message-bubble) table {
  table-layout: auto;
  width: 100%;
  border-collapse: collapse;
  margin: 14px 0;
  font-size: 14px;
  border: 1px solid #e3e6ea;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  min-width: 600px;
}
:deep(.ai-message-bubble) td,
:deep(.ai-message-bubble) th {
  word-break: break-word;
  overflow-wrap: break-word;
  vertical-align: middle;
  padding: 14px 16px;
  line-height: 1.6;
  border-right: 1px solid #e3e6ea; /* 竖向分隔线 */
}
:deep(.ai-message-bubble) td:last-child,
:deep(.ai-message-bubble) th:last-child {
  border-right: none; /* 最后一列不需要右边框 */
}
:deep(.ai-message-bubble) th {
  background: #f5f7fa;
  text-align: left;
  font-weight: 700;
  color: #1a1d23;
  border-bottom: 1px solid #dcdfe6;
  font-size: 14px;
  white-space: nowrap;
  position: sticky;
  top: 0;
  z-index: 1;
  letter-spacing: 0.01em;
}
:deep(.ai-message-bubble) td {
  color: #2c3038;
  border-bottom: 1px solid #eff0f2; /* 横向分隔线 */
  max-width: 320px;
}
:deep(.ai-message-bubble) tr:last-child td {
  border-bottom: none; /* 最后一行不需要底部边框，表格外边框已有 */
}
:deep(.ai-message-bubble) tr:hover {
  background: #f5f7fa;
}

/* 段落间距 */
.ai-message-bubble p {
  margin: 0 0 12px 0;
  line-height: 1.72;
  color: #2c3038;
}
.ai-message-bubble p:last-child {
  margin-bottom: 0;
}

/* 标题样式 */
.ai-message-bubble h1,
.ai-message-bubble h2,
.ai-message-bubble h3,
.ai-message-bubble h4 {
  margin: 26px 0 12px 0;
  font-weight: 650;
  color: #0f1115;
  line-height: 1.35;
  letter-spacing: -0.02em;
}
.ai-message-bubble h1 { font-size: 21px; font-weight: 700; }
.ai-message-bubble h2 { font-size: 18px; }
.ai-message-bubble h3 { font-size: 16px; }
.ai-message-bubble h4 { font-size: 14.5px; text-transform: uppercase; letter-spacing: 0.04em; color: #5d626d; }

/* 列表样式 */
.ai-message-bubble ul,
.ai-message-bubble ol { margin: 10px 0; padding-left: 24px; }
.ai-message-bubble li { margin: 6px 0; line-height: 1.7; color: #2c3038; }
.ai-message-bubble ul li::marker { color: #9199a6; }
.ai-message-bubble ol li::marker { color: #9199a6; font-weight: 500; }

/* 任务列表 */
.ai-message-bubble ul li input[type="checkbox"] {
  margin-right: 8px; vertical-align: middle; width: 16px; height: 16px;
  accent-color: #3b82f6;
}

/* 引用块 */
.ai-message-bubble blockquote {
  margin: 14px 0; padding: 13px 18px;
  border-left: 2.5px solid #c8cdd4; background: #f6f7f9;
  border-radius: 0 6px 6px 0; color: #595d66;
}
.ai-message-bubble blockquote p { margin: 0; color: #595d66; }

/* 代码块 */
:deep(.ai-message-bubble pre) {
  position: relative; margin: 14px 0; padding: 36px 14px 12px 14px;
  background: #f4f5f7; border-radius: 8px; overflow-x: auto;
  font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 13px; line-height: 1.65; border: 1px solid #e1e4e8;
}
:deep(.ai-message-bubble pre code) {
  background: transparent; padding: 0; border-radius: 0;
  color: #24292f; font-family: inherit; font-size: inherit; line-height: inherit;
}

/* 行内代码 */
.ai-message-bubble code {
  background: #eef0f3; padding: 2px 7px; border-radius: 5px;
  font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12.5px; color: #cf3a4e; font-weight: 500;
}

/* ========== 测试用例专用表格 ========== */
.ai-message-bubble .tc-table-wrap {
  margin: 18px 0; border: 1px solid #e3e6ea; border-radius: 12px;
  overflow: hidden; background: #fff;
}
.ai-message-bubble .tc-table-wrap table {
  display: table; width: 100%; border-collapse: collapse; border-spacing: 0;
  font-size: 13.5px; border-radius: 0; box-shadow: none; margin: 0;
  overflow: visible; background: transparent;
}
.ai-message-bubble .tc-table-wrap thead th {
  background: #f8f9fb; padding: 12px 16px; text-align: left;
  font-weight: 650; font-size: 12px; color: #4a4f5a;
  text-transform: uppercase; letter-spacing: 0.04em;
  border-bottom: 2px solid #e3e6ea; white-space: nowrap;
}
.ai-message-bubble .tc-table-wrap tbody td {
  padding: 11px 16px; color: #2c3038; line-height: 1.55;
  vertical-align: top; font-size: 13.5px;
}
.ai-message-bubble .tc-table-wrap tbody tr {
  transition: background 0.12s ease; border-bottom: 1px solid #eff0f2;
}
.ai-message-bubble .tc-table-wrap tbody tr:last-child { border-bottom: none; }
.ai-message-bubble .tc-table-wrap tbody tr:hover { background: #f5f7fa; }
.ai-message-bubble .tc-table-wrap td:first-child {
  font-family: 'JetBrains Mono', 'SF Mono', 'Consolas', monospace;
  font-size: 12.5px; color: #545a66; white-space: nowrap;
}

/* 优先级徽章 */
.ai-message-bubble .tc-priority {
  display: inline-block; padding: 2px 10px; border-radius: 100px;
  font-size: 11.5px; font-weight: 650; text-transform: uppercase;
  letter-spacing: 0.03em; white-space: nowrap;
}
.ai-message-bubble .tc-priority.p0 { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
.ai-message-bubble .tc-priority.p1 { background: #fff7ed; color: #ea580c; border: 1px solid #fed7aa; }
.ai-message-bubble .tc-priority.p2 { background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }
.ai-message-bubble .tc-priority.p3 { background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; }

/* 分隔线 */
.ai-message-bubble hr { margin: 20px 0; border: none; border-top: 1px solid #e3e6ea; }

/* 链接 */
.ai-message-bubble a {
  color: #1d4ed8; text-decoration: none;
  border-bottom: 1px solid #c7d2fe; transition: border-color 0.15s, color 0.15s;
}
.ai-message-bubble a:hover { color: #1e40af; border-bottom-color: #1d4ed8; }

/* 图片 */
.ai-message-bubble img { max-width: 100%; border-radius: 8px; margin: 10px 0; }

/* 强调 */
.ai-message-bubble strong { font-weight: 650; color: #0f1115; }
.ai-message-bubble em { font-style: italic; color: #4a4f5a; }

.message-context {
  margin-top: 10px;
}

/* AI 消息底部下载按钮栏 */
.message-download-bar {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed #e0e0e0;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.message-download-bar .el-button {
  font-size: 12px;
  padding: 4px 12px;
}

/* AI 回答使用的 Skill 标签 */
/* AI 回答元信息行：Skill + 耗时 */
.message-meta-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.message-meta-time {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #909399;
}

.message-meta-time .el-icon {
  font-size: 13px;
}

.context-item {
  margin-bottom: 10px;
}

.context-item p {
  margin-top: 5px;
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}

/* 文档列表样式 */
.document-list {
  min-height: 200px;
}

.input-area {
  padding: 16px 20px;
  border-top: 1px solid #e4e7ed;
  background: #fafafa;
  flex-shrink: 0; /* 防止被压缩 */
}

.input-toolbar {
  display: flex;
  justify-content: space-between; /* 两端对齐 */
  align-items: center;
  margin-bottom: 12px;
}

/* 模式切换按钮组 */
.mode-switcher {
  display: flex;
  gap: 8px;
}

/* 左侧工具栏区域 */
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 右侧工具栏区域 */
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Skill 选择器按钮 */
.skill-selector-btn {
  transition: all 0.3s ease;
}

.skill-selector-btn:hover {
  transform: translateY(-1px);
}

/* 当前激活的 Skill 紧凑提示 */
.active-skill-bar-compact {
  display: flex;
  align-items: center;
  padding: 4px 0 8px;
}

/* 旧的 active-skill-bar 兼容隐藏 */
.active-skill-bar, .active-skill-desc {
  display: none;
}

/* Skill 下拉菜单样式 */
.skill-dropdown-menu {
  max-height: 450px;
  overflow-y: auto;
  padding: 0 !important;
}

.skill-dropdown-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid #e4e7ed;
  background: #f5f7fa;
}

.skill-dropdown-title {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}

.skill-dropdown-menu .el-dropdown-menu__item {
  padding: 12px 16px !important;
  line-height: 1.4 !important;
  border-bottom: 1px solid #f0f0f0;
}

.skill-dropdown-menu .el-dropdown-menu__item:last-child {
  border-bottom: none;
}

.skill-dropdown-menu .el-dropdown-menu__item:hover {
  background: #ecf5ff !important;
}

.skill-dropdown-menu .el-dropdown-menu__item.is-active {
  background: #ecf5ff !important;
  color: #409eff !important;
}

.skill-dropdown-item {
  width: 280px;
}

.skill-dropdown-name {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.skill-dropdown-name .builtin-tag {
  font-size: 11px;
  padding: 0 4px;
  height: 18px;
}

.skill-dropdown-desc {
  font-size: 12px;
  color: #606266;
  line-height: 1.4;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.skill-dropdown-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.mode-switcher .el-button-group {
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
}

.mode-switcher .el-button {
  padding: 8px 16px;
  font-size: 13px;
  transition: all 0.3s ease;
}

.mode-switcher .el-button--primary {
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
  border-color: transparent;
}

/* 新对话按钮 - 精致渐变设计 */
.new-chat-btn-flat {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 20px;
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 500;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.25);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.new-chat-btn-flat::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
  transition: left 0.5s ease;
}

.new-chat-btn-flat:hover::before {
  left: 100%;
}

.new-chat-btn-flat:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.35);
}

.new-chat-btn-flat:active {
  transform: translateY(0) scale(0.98);
  box-shadow: 0 2px 6px rgba(102, 126, 234, 0.2);
}

.new-chat-btn-flat .el-icon {
  margin-right: 4px;
}

/* 深度思考模式切换按钮 */
.reasoning-toggle-btn {
  border-radius: 20px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.3s ease;
}

.reasoning-toggle-btn.is-reasoning {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  border-color: transparent;
  color: white;
  box-shadow: 0 2px 8px rgba(245, 87, 108, 0.25);
}

.reasoning-toggle-btn.is-reasoning:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(245, 87, 108, 0.35);
}

.reasoning-toggle-btn .el-icon {
  margin-right: 4px;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.input-actions-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.hint-text {
  display: none;
}

.chat-input-wrapper {
  background: #fff;
  border: 1px solid #dcdfe6;
  border-radius: 12px;
  padding: 12px 14px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.chat-input-wrapper .el-textarea__inner {
  border: none;
  box-shadow: none;
  padding: 0;
  resize: none;
  font-size: 14px;
  line-height: 1.6;
  background: transparent;
}

/* 图片预览：在输入框内部上方，小标签形式 */
.image-preview-area {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0f0f0;
}
.image-preview-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: #f0f2f5;
  border-radius: 6px;
  font-size: 12px;
  color: #606266;
  cursor: default;
}
.image-preview-tag img {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  object-fit: cover;
  flex-shrink: 0;
}
.image-tag-name {
  white-space: nowrap;
}
.image-tag-close {
  cursor: pointer;
  font-size: 12px;
  color: #909399;
  transition: color 0.15s;
}
.image-tag-close:hover {
  color: #f56c6c;
}

/* 旧的图片预览样式已废弃 */
.image-preview-item,
.image-remove-btn {
  display: none;
}

/* 图片预览对话框 */
.image-preview-dialog .el-dialog__header {
  display: none;
}
.image-preview-dialog .el-dialog__body {
  padding: 0;
}
.image-preview-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  min-width: 300px;
}
.image-preview-container img {
  max-width: 80vw;
  max-height: 70vh;
  border-radius: 8px;
  object-fit: contain;
}
.image-preview-nav {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 16px;
}
.image-preview-counter {
  font-size: 14px;
  color: #606266;
  min-width: 60px;
  text-align: center;
}

/* 消息中的图片 */
.message-images {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.message-image {
  max-width: 200px;
  max-height: 200px;
  border-radius: 8px;
  object-fit: cover;
  border: 1px solid #e4e7ed;
}

/* 代码块工具栏样式（动态插入的DOM元素） */
/* 代码块工具栏 - 豆包风格：极简小图标 */
:deep(.ai-message-bubble pre .code-block-toolbar) {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: #f5f5f5;
  border-radius: 8px 8px 0 0;
  border-bottom: 1px solid #e4e7ed;
  z-index: 10;
  box-sizing: border-box;
  height: 32px;
}

:deep(.ai-message-bubble .toolbar-lang) {
  color: #8c8c8c;
  font-size: 12px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  text-transform: uppercase;
  user-select: none;
  font-weight: 500;
  letter-spacing: 0.5px;
}

/* 按钮组容器 */
:deep(.ai-message-bubble .toolbar-btn-group) {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 豆包风格：纯图标小按钮 */
:deep(.ai-message-bubble .toolbar-btn) {
  background: transparent;
  border: none;
  color: #8c8c8c;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  transition: all 0.2s ease;
}

:deep(.ai-message-bubble .toolbar-btn:hover) {
  background: rgba(0, 0, 0, 0.06);
  color: #595959;
}

:deep(.ai-message-bubble .toolbar-btn:active) {
  transform: scale(0.92);
}

/* 复制按钮 */
:deep(.ai-message-bubble .toolbar-btn-copy:hover) {
  color: #389e0d;
}

/* 全屏按钮 */
:deep(.ai-message-bubble .toolbar-btn-zoom:hover) {
  color: #096dd9;
}

/* ========== 多Agent工作流样式 ========== */

/* 工作流模式按钮高亮 */
.workflow-mode-btn.el-button--primary {
  background: linear-gradient(135deg, #e040fb 0%, #7c4dff 100%) !important;
  border-color: transparent !important;
}

/* 工作流欢迎图标 */
.welcome-icon.icon-workflow {
  background: linear-gradient(135deg, #e040fb 0%, #7c4dff 100%);
  box-shadow: 0 8px 24px rgba(124, 77, 255, 0.3);
}
.welcome-icon.icon-workflow .el-icon {
  color: white;
}

/* 工作流进度面板 */
.workflow-progress-panel {
  background: #ffffff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.workflow-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.workflow-panel-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.workflow-panel-title .el-icon {
  font-size: 20px;
  color: #7c4dff;
}

.workflow-panel-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.workflow-timer {
  font-size: 13px;
  color: #909399;
  font-family: 'SF Mono', 'Consolas', monospace;
  font-variant-numeric: tabular-nums;
}

.stop-wf-btn {
  border-radius: 16px;
  font-size: 12px;
  padding: 4px 14px;
}

.workflow-overall-progress {
  margin-bottom: 20px;
}

.workflow-timeline {
  position: relative;
  padding-left: 32px;
}

.wf-step {
  position: relative;
  padding-bottom: 24px;
}

.wf-step:last-child {
  padding-bottom: 0;
}

.wf-step-dot {
  position: absolute;
  left: -32px;
  top: 2px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
}

.wf-step-done .wf-step-dot {
  background: #f6ffed;
  color: #52c41a;
}

.wf-step-running .wf-step-dot {
  background: #fff7e6;
  color: #fa8c16;
}

.wf-step-fail .wf-step-dot {
  background: #fff2f0;
  color: #ff4d4f;
}

.wf-dot-pending {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #d9d9d9;
}

.wf-step-line {
  position: absolute;
  left: -19px;
  top: 32px;
  bottom: 0;
  width: 2px;
  background: #e8e8e8;
}

.wf-step-done .wf-step-line {
  background: #b7eb8f;
}

.wf-step-content {
  background: #fafafa;
  border-radius: 8px;
  padding: 12px 16px;
}

.wf-step-running .wf-step-content {
  background: #fffbe6;
  border: 1px solid #ffe58f;
}

.wf-step-done .wf-step-content {
  background: #f6ffed;
}

.wf-step-fail .wf-step-content {
  background: #fff2f0;
  border: 1px solid #ffccc7;
}

.wf-step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.wf-step-agent {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.wf-step-duration {
  font-size: 12px;
  color: #8c8c8c;
  font-family: 'SF Mono', 'Consolas', monospace;
}

.wf-step-desc {
  font-size: 13px;
  color: #595959;
  line-height: 1.5;
}

.wf-step-detail {
  margin-top: 8px;
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.5;
  max-height: 120px;
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.03);
  border-radius: 4px;
  padding: 8px;
}

.wf-step-error {
  margin-top: 8px;
}

/* 工作流最终结果 */
.workflow-result {
  margin-top: 16px;
  padding: 16px;
  background: linear-gradient(135deg, #f0f5ff 0%, #e6f7ff 100%);
  border-radius: 8px;
  border: 1px solid #91d5ff;
}

.wf-result-text {
  font-size: 14px;
  line-height: 1.7;
  color: #262626;
}
</style>

<style>
/* ========== 暗色模式全局覆盖 ========== */
html.dark .knowledge-chat-container {
  background: #141414;
  color: #e0e0e0;
}

html.dark .chat-header {
  border-bottom-color: #333333;
}

html.dark .chat-header h3 {
  color: #e0e0e0;
}

html.dark .history-panel-wrapper {
  background: #1d1e1f;
  border-right-color: #333333;
}

html.dark .history-collapsed-bar {
  color: #909399;
  border-right-color: #333333;
}

html.dark .history-collapsed-bar:hover {
  background: #2c2c2c;
}

html.dark .history-panel-header-compact {
  background: #1d1e1f;
  border-bottom-color: #333333;
}

html.dark .history-panel-title {
  color: #e0e0e0;
}

html.dark .history-panel {
  background: #1d1e1f;
  border-right-color: #333333;
}

html.dark .history-header {
  background: #1d1e1f;
  border-bottom-color: #333333;
}

html.dark .history-list {
  background: transparent;
}

html.dark .empty-history {
  color: #909399;
}

html.dark .empty-mode-text {
  color: #e0e0e0;
}

html.dark .empty-mode-hint {
  color: #909399;
}

html.dark .empty-mode-icon {
  color: #909399;
}

html.dark .group-title {
  color: #a0a0a0;
}

html.dark .history-item {
  background: #2a2a2a;
  color: #e0e0e0;
}

html.dark .history-item:hover {
  background: #3a3a3a;
}

html.dark .history-item.active {
  background: #409eff;
  color: #ffffff;
}

html.dark .history-item.active:hover {
  background: #409eff;
}

html.dark .item-time {
  color: #a0a0a0;
}

html.dark .history-item.active .item-time {
  color: rgba(255, 255, 255, 0.8);
}

html.dark .skeleton-line {
  background: linear-gradient(90deg, #2a2a2a 25%, #3a3a3a 50%, #2a2a2a 75%);
}

html.dark .chat-panel {
  background: #0a0a0a;
}

html.dark .message-list {
  background: #0a0a0a;
}

html.dark .welcome-content h3 {
  color: #e0e0e0;
}

html.dark .welcome-content p {
  color: #a0a0a0;
}

html.dark .thinking-indicator {
  background: #1d1e1f;
}

html.dark .thinking-text {
  color: #e0e0e0;
}

html.dark .thinking-timer,
html.dark .streaming-timer {
  color: #909399;
}

html.dark .message-text {
  background: #1d1e1f;
  color: #e0e0e0;
  border-color: #333333;
}

html.dark .user-message .message-text {
  background: #1677ff;
  color: #ffffff;
}

html.dark .ai-message-bubble {
  color: #e0e0e0;
}

html.dark .ai-message-bubble p,
html.dark .ai-message-bubble li {
  color: #d0d0d0;
}

html.dark .ai-message-bubble h1,
html.dark .ai-message-bubble h2,
html.dark .ai-message-bubble h3 {
  color: #ffffff;
}

html.dark .ai-message-bubble h4 {
  color: #a0a0a0;
}

html.dark .ai-message-bubble strong {
  color: #ffffff;
}

html.dark .ai-message-bubble em {
  color: #a0a0a0;
}

html.dark .ai-message-bubble blockquote {
  background: #1d1e1f;
  border-left-color: #555555;
  color: #a0a0a0;
}

html.dark .ai-message-bubble blockquote p {
  color: #a0a0a0;
}

html.dark .ai-message-bubble code {
  background: #2a2a2a;
  color: #ff6b81;
}

html.dark .ai-message-bubble pre {
  background: #161b22;
  border-color: #333333;
}

html.dark .ai-message-bubble pre code {
  color: #d0d0d0;
}

html.dark .ai-message-bubble table,
html.dark .ai-message-bubble th,
html.dark .ai-message-bubble td {
  border-color: #333333;
}

html.dark .ai-message-bubble th {
  background: #1d1e1f;
  color: #e0e0e0;
}

html.dark .ai-message-bubble tr:hover {
  background: #2a2a2a;
}

html.dark .ai-message-bubble hr {
  border-top-color: #333333;
}

html.dark .ai-message-bubble a {
  color: #58a6ff;
  border-bottom-color: #555555;
}

html.dark .ai-message-bubble a:hover {
  color: #79c0ff;
  border-bottom-color: #58a6ff;
}

html.dark .message-download-bar {
  border-top-color: #333333;
}

html.dark .message-meta-time {
  color: #909399;
}

html.dark .copy-msg-btn {
  color: #a0a0a0;
}

html.dark .copy-msg-btn:hover {
  color: #79c0ff;
}

html.dark .context-item p {
  color: #a0a0a0;
}

html.dark .input-area {
  background: #141414;
  border-top-color: #333333;
}

html.dark .chat-input-wrapper {
  background: #1d1e1f;
  border-color: #333333;
}

html.dark .chat-input-wrapper .el-textarea__inner {
  color: #e0e0e0;
}

html.dark .image-preview-area {
  border-bottom-color: #333333;
}

html.dark .image-preview-tag {
  background: #2a2a2a;
  color: #a0a0a0;
}

html.dark .image-tag-close {
  color: #909399;
}

html.dark .skill-dropdown-header {
  background: #1d1e1f;
  border-bottom-color: #333333;
}

html.dark .skill-dropdown-title,
html.dark .skill-dropdown-name {
  color: #e0e0e0;
}

html.dark .skill-dropdown-desc {
  color: #a0a0a0;
}

html.dark .skill-dropdown-menu .el-dropdown-menu__item:hover {
  background: #2a2a2a !important;
}

html.dark .workflow-progress-panel {
  background: #1d1e1f;
  border-color: #333333;
}

html.dark .workflow-panel-title,
html.dark .wf-step-agent {
  color: #e0e0e0;
}

html.dark .wf-step-content {
  background: #1d1e1f;
}

html.dark .wf-step-detail {
  background: rgba(255, 255, 255, 0.05);
  color: #a0a0a0;
}

html.dark .workflow-result {
  background: linear-gradient(135deg, #162040 0%, #0e2a3a 100%);
  border-color: #1f4e79;
}

html.dark .wf-result-text {
  color: #d0d0d0;
}
</style>
