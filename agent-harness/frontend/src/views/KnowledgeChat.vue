<template>
  <div class="knowledge-chat-container">
    <!-- 顶部导航 -->
    <div class="chat-header">
      <div class="header-actions" style="margin-left: auto; display: flex; gap: 8px; align-items: center;">
        <el-button
          :type="isDark ? 'default' : 'default'"
          size="small"
          text
          @click="toggleTheme"
          :title="isDark ? '当前深色主题，点击切换浅色' : '当前浅色主题，点击切换深色'"
        >
          <el-icon :size="18"><component :is="isDark ? Moon : Sunny" /></el-icon>
          <span style="margin-left: 4px;">{{ isDark ? '深色' : '浅色' }}</span>
        </el-button>
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
          accept=".txt,.md,.markdown,.pdf,.docx"
        >
          <el-button size="small" type="primary">
            <el-icon><Upload /></el-icon> 上传文档
          </el-button>
        </el-upload>
        <el-button size="small" text @click="openMemoryDrawer">
          <el-icon><Memo /></el-icon> 记忆管理
        </el-button>
      </div>
    </div>

    <!-- 记忆管理抽屉 -->
    <el-drawer
      v-model="memoryDrawerVisible"
      title="记忆管理"
      direction="rtl"
      size="420px"
      :append-to-body="true"
    >
      <div class="memory-manage">
        <div class="memory-manage-toolbar">
          <span class="memory-manage-count">共 {{ totalMemoryCount }} 条长期记忆</span>
          <el-button size="small" type="danger" plain :disabled="totalMemoryCount === 0" @click="clearAllMemories">清空全部</el-button>
        </div>
        <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px;">
          这里展示 AI 在对话 / 知识库问答中自动沉淀的长期记忆（用户偏好、决策、经验等），跨会话保留，用于让回答更贴合你的习惯。
        </el-alert>
        <div v-if="memoryLoading" class="memory-loading">
          <el-icon class="is-loading"><Loading /></el-icon> 加载中...
        </div>
        <div v-else-if="totalMemoryCount === 0" class="memory-empty">
          <el-empty description="暂无长期记忆" :image-size="80" />
        </div>
        <div v-else class="memory-groups">
          <div v-for="group in memoryGroups" :key="group.mode" class="memory-group">
            <div class="memory-group-header">
              <span class="memory-group-title">{{ group.mode === 'chat' ? '日常对话' : '知识库问答' }}</span>
              <span class="memory-group-count">{{ group.entries.length }} 条</span>
              <el-button
                v-if="group.entries.length"
                size="small" text type="danger"
                @click="clearMemoriesByMode(group.mode)"
              >清空</el-button>
            </div>
            <div
              v-for="item in group.entries"
              :key="item.id"
              class="memory-item"
            >
              <div class="memory-item-content">{{ item.content }}</div>
              <div class="memory-item-meta">
                <el-tag size="small" :type="memoryTypeTag(item.memory_type)">{{ memoryTypeName(item.memory_type) }}</el-tag>
                <span class="memory-item-time" v-if="item.created_at">{{ formatMemoryTime(item.created_at) }}</span>
                <el-button size="small" text type="danger" @click="deleteMemory(item)">删除</el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-drawer>

    <div class="chat-content">
      <!-- 左侧：历史对话列表 -->
      <div class="history-panel-wrapper" :class="{ collapsed: historyCollapsed }">
        <div v-if="historyCollapsed" class="history-collapsed-bar" @click="toggleHistoryPanel">
          <el-icon :size="18"><ArrowLeft /></el-icon>
        </div>
        <div v-else class="history-panel-expanded">
          <div class="history-panel-header-compact">
            <div class="history-panel-header-left">
              <span class="history-panel-title">历史记录</span>
              <el-checkbox
                v-if="chatHistory.length"
                :model-value="isAllSelected"
                @change="toggleSelectAll"
              >
                全选
              </el-checkbox>
              <el-button
                v-if="selectedMessages.size"
                size="small"
                type="danger"
                text
                @click="batchDelete"
              >
                删除({{ selectedMessages.size }})
              </el-button>
            </div>
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

          <div v-if="kbNotFound && qaMode === 'knowledge'" class="welcome-message">
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
          
          <div v-for="(msg, index) in messages" :key="msg._id || msg.tempId || index" class="message-item" :class="{ 'user-message': msg.isUser }">
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
              <!-- AI 回答元信息行：Skill + 响应耗时 + 质量评分 + 人工协同 -->
              <div v-if="!msg.isUser && (msg.skill || msg.responseTime || msg.evalScore !== undefined || msg.needsHuman || (msg.evalPending && showEvalMeta) || msg._interrupted)" class="message-meta-row">
                <el-tag v-if="msg._interrupted" size="small" type="danger" effect="dark">
                  生成已中断
                </el-tag>
                <el-tag v-if="msg.skill" size="small" type="success" effect="light">
                  <el-icon><SetUp /></el-icon> {{ msg.skill }}
                </el-tag>
                <span v-if="msg.responseTime" class="message-meta-time">
                  <el-icon><Timer /></el-icon> {{ formatResponseTime(msg.responseTime) }}
                </span>
                <el-tag v-if="msg.evalPending && showEvalMeta" size="small" type="info" effect="plain">
                  质量评估中...
                </el-tag>
                <el-tag v-else-if="msg.evalScore !== undefined" size="small" :type="msg.evalScore >= 0.7 ? 'success' : 'warning'" effect="plain">
                  质量评分 {{ Math.round(msg.evalScore * 100) }}%
                </el-tag>
                <el-tag v-if="!msg.evalPending && msg.evalIterations && msg.evalIterations > 1" size="small" type="info" effect="plain">
                  循环 {{ msg.evalIterations }} 轮
                </el-tag>
                <el-tag v-if="msg.needsHuman" size="small" type="danger" effect="dark">
                  已转人工协同
                </el-tag>
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
              <!-- 历史消息：折叠式思考过程，默认不展开，不抢正文视觉焦点 -->
              <div v-if="!msg.isUser && msg.isDeepThinking && msg.reasoningText" class="message-thinking-collapse">
                <el-collapse>
                  <el-collapse-item>
                    <template #title>
                      <span class="thinking-collapse-title">
                        <el-icon><Opportunity /></el-icon> 思考过程
                        <el-tag size="small" type="success" class="thinking-response-tag">{{ formatDuration(msg.responseTime / 1000) }}</el-tag>
                      </span>
                    </template>
                    <div class="thinking-history-steps">
                      <div class="reasoning-text-area reasoning-done" style="margin-top: 0;">
                        <div class="reasoning-text-content" v-html="formatMessage(msg.reasoningText)"></div>
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
                      <div class="context-header">
                        <el-tag size="small" type="info">片段 {{ i + 1 }}</el-tag>
                        <span class="context-filename" :title="ctx.filename">{{ ctx.filename }}</span>
                        <span v-if="ctx.chunk_index !== undefined" class="context-meta">chunk #{{ ctx.chunk_index }}</span>
                        <span v-if="ctx.score !== undefined" class="context-score">score {{ ctx.score }}</span>
                      </div>
                      <p class="context-content">{{ ctx.content }}</p>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </div>
          </div>
          
          <!-- 流式输出中：实时显示AI回答 + 可折叠思考过程 + 计时器 + 停止按钮 -->
          <div v-if="answering" class="message-item">
            <div class="message-avatar">
              <div class="avatar-ai">
                <el-icon :size="24"><Reading /></el-icon>
              </div>
            </div>
            <div class="message-content">
              <!-- 思考过程折叠面板：默认收起，不抢占正文视觉焦点 -->
              <el-collapse v-if="reasoningMode === 'reasoning' && (streamingReasoning || thinkingSteps.length > 0)" v-model="activeStreamingThinkingPanel">
                <el-collapse-item name="reasoning">
                  <template #title>
                    <span class="thinking-panel-title-inline">
                      <el-icon><Opportunity /></el-icon> 思考过程
                      <span class="thinking-panel-timer">{{ formatDuration(elapsedTime) }}</span>
                    </span>
                  </template>
                  <div v-if="thinkingSteps.length > 0" class="thinking-steps-panel streaming-thinking-panel">
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
                  </div>
                  <div v-if="streamingReasoning" class="reasoning-text-area reasoning-terminal">
                    <div ref="reasoningContentRef" class="reasoning-text-content" v-html="formatMessage(streamingReasoning)"></div>
                    <span v-if="!streamingText" class="reasoning-cursor">▊</span>
                  </div>
                </el-collapse-item>
              </el-collapse>
              <!-- 非深度思考模式或无推理内容时的加载提示 -->
              <div v-else-if="answering && streamingText.length === 0" class="thinking-indicator">
                <div class="thinking-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <span class="thinking-text">{{ currentThinkingStatus }}</span>
                <span class="thinking-timer">{{ formatDuration(elapsedTime) }}</span>
              </div>
              <!-- AI 回答正文：深度思考模式下先隐藏答案，思考结束后一次性完整显示 -->
              <div v-if="streamingText.length > 0 && !isReasoningPhase" class="message-text ai-message-bubble" v-html="formatMessage(streamingText)"></div>
              <div v-else-if="answering && reasoningMode === 'reasoning'" class="answer-placeholder">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>{{ isReasoningPhase ? '正在深度思考，请稍候…' : '正在整理最终答案…' }}</span>
              </div>
              <div v-if="streamingText.length > 0 && !isReasoningPhase" class="streaming-footer">
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
import { ref, reactive, onMounted, onUnmounted, nextTick, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import { knowledgeBaseAPI, memoryAPI, authAPI } from '@/api/index'
import api from '@/api/index'
import { useAuthStore } from '@/stores/auth'
import { ArrowLeft, Upload, Reading, User, Promotion, Plus, Delete, ChatDotRound, Document, SetUp, Picture, Close, Download, Timer, Loading, CircleCheckFilled, CircleCloseFilled, CopyDocument, Opportunity, Moon, Sunny, Memo } from '@element-plus/icons-vue'
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
const currentTaskId = ref('') // 后台生成任务 ID，用于切换页面后重连继续接收增量
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
const activeStreamingThinkingPanel = ref([]) // 流式思考过程折叠面板展开状态（默认收起）
const isReasoningPhase = ref(false) // 深度思考模式：是否仍处于思考阶段（未出答案）
const answerBuffer = ref('')      // 思考阶段缓存的首批答案 token
const reasoningContentRef = ref(null) // 流式思考文本容器，用于自动滚动
let streamTimer = null // 计时器 interval
let streamAbortController = null // 用于取消请求
let typewriterTimer = null // 打字机效果 timer
let typewriterIndex = 0 // 打字机当前显示到的位置
let streamReader = null // 当前流式读取器（用于手动取消）
let eventSeq = 0 // 已处理的 SSE 事件序号（用于重连 offset，不含 meta）
let messageKeySeed = 0 // 本地消息 key 自增种子，避免 v-for 用 index 闪烁
const nextMessageKey = () => `msg-${Date.now()}-${++messageKeySeed}`

// 问答模式：'chat' - 日常对话，'knowledge' - 知识库问答
// 默认先设为 chat，onMounted 中会根据持久化状态或 URL 再决定最终模式
const qaMode = ref('chat')

// 推理模式：'fast' - 直接回答，'reasoning' - 深度思考
const reasoningMode = ref('fast')

// 是否展示质量评估元信息（QualityChecker/多 Agent 测试任务才显示；
// 日常对话与知识库问答默认不展示，避免每次问答都出现"质量评估中"并误触飞书推送）
const showEvalMeta = computed(() => false)
const toggleReasoningMode = () => {
  reasoningMode.value = reasoningMode.value === 'fast' ? 'reasoning' : 'fast'
}

// 历史面板折叠状态
const historyCollapsed = ref(false)
const toggleHistoryPanel = () => { historyCollapsed.value = !historyCollapsed.value }

// ========== 记忆管理 ==========
const authStore = useAuthStore()
const currentUserId = computed(() => authStore.user?.id ?? null)

const memoryDrawerVisible = ref(false)
const memoryLoading = ref(false)
const memoryGroups = ref([]) // [{ mode, entries: [{id, content, memory_type, importance, created_at}] }]

const totalMemoryCount = computed(() =>
  memoryGroups.value.reduce((sum, g) => sum + g.entries.length, 0)
)

const memoryTypeName = (t) => {
  const map = { fact: '事实', decision: '决策', pattern: '模式', lesson: '经验' }
  return map[t] || t || '事实'
}
const memoryTypeTag = (t) => {
  const map = { fact: 'info', decision: 'warning', pattern: 'success', lesson: 'danger' }
  return map[t] || 'info'
}
const formatMemoryTime = (iso) => {
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch (e) {
    return ''
  }
}

const loadMemories = async () => {
  memoryLoading.value = true
  try {
    const res = await memoryAPI.list(currentUserId.value)
    memoryGroups.value = res.memories || []
  } catch (e) {
    console.error('[Memory] 加载失败:', e)
    if (e && e.status === 401) {
      ElMessage.error('登录已过期，请重新登录后再查看记忆')
    } else {
      ElMessage.error('记忆加载失败')
    }
  } finally {
    memoryLoading.value = false
  }
}

const openMemoryDrawer = () => {
  memoryDrawerVisible.value = true
  loadMemories()
}

const deleteMemory = async (item) => {
  try {
    await ElMessageBox.confirm(`确定删除这条记忆？\n\n「${item.content}」`, '删除记忆', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch (e) {
    return
  }
  try {
    await memoryAPI.delete(currentUserId.value, item.id, item.mode)
    ElMessage.success('已删除')
    await loadMemories()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const clearMemoriesByMode = async (mode) => {
  try {
    await ElMessageBox.confirm(`确定清空「${mode === 'chat' ? '日常对话' : '知识库问答'}」的全部记忆？`, '清空记忆', {
      confirmButtonText: '清空',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch (e) {
    return
  }
  try {
    await memoryAPI.clear(currentUserId.value, mode)
    ElMessage.success('已清空')
    await loadMemories()
  } catch (e) {
    ElMessage.error('清空失败')
  }
}

const clearAllMemories = async () => {
  try {
    await ElMessageBox.confirm('确定清空全部长期记忆（日常对话 + 知识库问答）？', '清空全部记忆', {
      confirmButtonText: '全部清空',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch (e) {
    return
  }
  try {
    await memoryAPI.clear(currentUserId.value)
    ElMessage.success('已清空全部记忆')
    await loadMemories()
  } catch (e) {
    ElMessage.error('清空失败')
  }
}

// 主题切换
const isDark = ref(false)
const applyTheme = () => {
  const html = document.documentElement
  if (isDark.value) {
    html.classList.add('dark')
  } else {
    html.classList.remove('dark')
  }
  localStorage.setItem('knowledge-theme', isDark.value ? 'dark' : 'light')
}
const toggleTheme = () => {
  isDark.value = !isDark.value
  applyTheme()
}

// 已处理完的 task_id 集合，防止页面重连/后端重放 done 事件导致重复追加同一条回答
const finishedTaskIds = new Set()

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
    const reader = new window.FileReader()
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
      let kbs = listRes.results || listRes || []
      if (kbs.length === 0) {
        try {
          const created = await knowledgeBaseAPI.create({ name: '默认知识库', description: '系统自动创建' })
          kbs = [created]
          console.log('[KB] Chat mode auto-created default KB:', created.id)
        } catch (createErr) {
          console.error('Failed to auto-create default KB in chat mode:', createErr)
        }
      }
      if (kbs.length > 0) {
        const firstKb = kbs[0]
        kbId.value = firstKb.id
        knowledgeBase.value = firstKb
        kbNotFound.value = false
        // 注意：不再 router.replace 到 /knowledge/{id}。
        // 否则路径变化会触发二次 remount，onMounted 再次运行时把 qaMode 误判为 knowledge，
        // 覆盖从 localStorage 恢复的 chat 模式，导致“切回变 knowledge / 消息被清空”。
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
      let kbs = listRes.results || listRes || []
      if (kbs.length === 0) {
        // 多租户下自动创建默认知识库，避免用户首次使用就弹创建框
        try {
          const created = await knowledgeBaseAPI.create({ name: '默认知识库', description: '系统自动创建' })
          kbs = [created]
          console.log('[KB] Auto-created default KB:', created.id)
        } catch (createErr) {
          console.error('Failed to auto-create default KB:', createErr)
        }
      }
      if (kbs.length > 0) {
        const firstKb = kbs[0]
        kbId.value = firstKb.id
        knowledgeBase.value = firstKb
        kbNotFound.value = false
        // 同上：不再 router.replace 改变路径，避免二次 remount 改写 qaMode。
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
      let kbs = listRes.results || listRes || []
      if (kbs.length === 0) {
        try {
          const created = await knowledgeBaseAPI.create({ name: '默认知识库', description: '系统自动创建' })
          kbs = [created]
          console.log('[KB] Auto-created default KB after not found:', created.id)
        } catch (createErr) {
          console.error('Failed to auto-create default KB:', createErr)
        }
      }
      if (kbs.length > 0) {
        // 跳转到第一个可用的知识库
        const firstKb = kbs[0]
        kbId.value = firstKb.id
        knowledgeBase.value = firstKb
        kbNotFound.value = false
        // 更新URL但不触发导航（避免死循环）
        router.replace( `/knowledge/${firstKb.id}`)
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

// 防御：当进入知识库模式但 kbId 仍为无效值（undefined/空）时，
// 兜底触发一次知识库加载，确保 URL 与 kbId 始终有效，避免停在 /knowledge/undefined
watch(
  () => [qaMode.value, kbId.value],
  async ([mode, id]) => {
    if (mode === 'knowledge') {
      const invalid = !id || ['0', 'undefined', 'null', '', 'chat', 'select'].includes(String(id))
      if (invalid) {
        console.warn('[KB] 检测到无效 kbId，触发兜底加载:', id)
        await loadKnowledgeBase()
      }
    }
  }
)

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
    router.replace( `/knowledge/${res.id}`)
    ElMessage.success('知识库创建成功')
  } catch (e) {
    if (e !== 'cancel') console.error('Create KB error:', e)
  }
}

// 加载对话历史（按会话分组）。采用增量合并，避免整表替换导致左侧列表闪烁。
// silent=true 时不在左侧显示骨架屏，用于模式切换后的后台刷新，避免切换过程卡顿。
const loadChatHistory = async (silent = false) => {
  if (!silent) historyLoading.value = true
  historyLoadError.value = false
  try {
    let items = []
    if (qaMode.value === 'chat') {
      const res = await knowledgeBaseAPI.chatSessionList()
      items = res.items || []
    } else if (qaMode.value === 'knowledge' && kbId.value && String(kbId.value).trim()) {
      const res = await knowledgeBaseAPI.getSessionList(kbId.value)
      items = res.items || []
    }

    // 增量合并：保留当前列表中尚在后端不存在的本地临时项（如刚刚创建的新会话），
    // 其余按后端数据更新，避免整表替换导致 v-for 闪烁。
    const newMap = new Map((items || []).map(session => {
      const mode = session.mode || (qaMode.value === 'chat' ? 'chat' : 'knowledge')
      const sid = session.session_id || session.id
      return [sid, {
        id: sid,
        session_id: sid,
        question: session.title,
        answer: '',
        created_at: session.updated_at || session.created_at,
        updated_at: session.updated_at,
        is_session: true,
        mode,
      }]
    }))

    // 保留当前列表中属于当前模式、且后端尚未返回的会话：
    // - 乐观插入 / 当前对话占位 必须保留
    // - 如果当前模式本地已有真实记录但后端返回空（生成中切走、后端未同步、切换页面 remount 等），
    //   也保留本地记录，防止历史被吞。清空历史应通过删除会话完成。
    const existingLocal = chatHistory.value.filter(
      h => h.mode === qaMode.value && !newMap.has(h.id)
    )
    const hasBackendItems = newMap.size > 0
    const preserved = existingLocal.filter(
      h => h._isOptimistic || h._isCurrent || !hasBackendItems
    )

    // 按 updated_at 倒序排列
    const merged = [...preserved, ...newMap.values()].sort(
      (a, b) => new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at)
    )

    // 保留其他模式已加载的历史，避免切换模式时 chat/knowledge 互相覆盖导致"切着切着就没了"
    const otherModeHistory = chatHistory.value.filter(h => h.mode !== qaMode.value)
    chatHistory.value = [...otherModeHistory, ...merged].sort(
      (a, b) => new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at)
    )
    // 标记当前模式历史已加载，切换回来时不再重复请求
    if (modeState[qaMode.value]) {
      modeState[qaMode.value].historyLoaded = true
      modeState[qaMode.value].historyLoadedAt = Date.now()
    }
  } catch (error) {
    console.error('Load history error:', error)
    historyLoadError.value = true
  } finally {
    if (!silent) historyLoading.value = false
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

// 当前模式可见的历史记录
const visibleHistory = computed(() => chatHistory.value.filter(msg => msg.mode === qaMode.value))

// 是否已全选当前模式可见记录
const isAllSelected = computed(() => {
  if (visibleHistory.value.length === 0) return false
  return visibleHistory.value.every(msg => selectedMessages.value.has(msg.id))
})

// 选择历史消息（会话）
const selectMessage = async (msg) => {
  currentMessageId.value = msg.id
  currentSessionId.value = msg.session_id || ''

  // 如果是会话，加载该会话的所有消息
  if (msg.is_session && msg.session_id) {
    // 本地当前对话的临时占位项 / 未落库的临时会话：不要请求后端
    if (msg._isCurrent || String(msg.session_id).startsWith('temp-')) {
      scrollToBottom()
      return
    }
    try {
      let items = []
      if (qaMode.value === 'chat') {
        const res = await knowledgeBaseAPI.chatSessionMessages(msg.session_id)
        items = res.items || []
      } else if (qaMode.value === 'knowledge' && kbId.value) {
        const res = await knowledgeBaseAPI.getSessionMessages(kbId.value, msg.session_id)
        items = res.items || []
      }
      // 后端消息字段：id / session_id / role / content / created_at
      messages.value = items.map(m => ({
        _id: m.id || nextMessageKey(),
        content: m.content || '',
        isUser: m.role === 'user',
        images: [],
        contextDocs: [],
        evalScore: m.eval_score !== undefined ? m.eval_score : undefined,
        evalIterations: m.eval_iterations || undefined,
        needsHuman: !!m.needs_human,
      }))
    } catch (error) {
      console.error('Load session messages error:', error)
      messages.value = [
        { _id: nextMessageKey(), content: msg.question, isUser: true },
        {
          _id: nextMessageKey(),
          content: msg.answer, isUser: false,
          contextDocs: msg.context_docs || [],
          evalScore: msg.eval_score !== undefined ? msg.eval_score : undefined,
          evalIterations: msg.eval_iterations || undefined,
          needsHuman: !!msg.needs_human,
        },
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

// ========== 模式独立状态（输入框、右侧消息、当前会话均按模式隔离） ==========
const HISTORY_REFRESH_COOLDOWN_MS = 15000
const modeState = reactive({
  chat: { question: '', messages: [], currentSessionId: '', historyLoaded: false, historyLoadedAt: 0, streamingSnapshot: null },
  knowledge: { question: '', messages: [], currentSessionId: '', historyLoaded: false, historyLoadedAt: 0, streamingSnapshot: null },
  workflow: { question: '', workflowSteps: [], workflowDone: false, workflowError: false, workflowResult: '', historyLoaded: false, historyLoadedAt: 0, streamingSnapshot: null },
})

// ========== 对话状态持久化（防止切换页面/组件 remount 后消息丢失） ==========
// 以 access_token 前缀隔离多用户；状态按 kbId 维度分别保存，避免 modeState 体积过大且跨知识库互相串。
const STORAGE_PREFIX = 'kc_state_v1'
const storageUserKey = () => {
  const t = localStorage.getItem('access_token') || ''
  // 取 token 前 12 位作为用户隔离标识
  return t ? t.slice(0, 12) : 'anon'
}
// 注意：不要使用 kbId 作为 key 的一部分——kbId 是动态值（进入时可能为 'chat'/'none'，
// loadKnowledgeBase 后会变成真实 id 并触发 replaceState + 路由名变化 → 组件 remount，
// 导致存储 key 漂移、恢复不到。统一用固定 per-user key 即可（多知识库场景后续可扩展）。
const storageKey = () => `${STORAGE_PREFIX}_${storageUserKey()}`

const persistState = () => {
  try {
    const payload = {
      modeState: JSON.parse(JSON.stringify(modeState)),
      chatHistory: chatHistory.value.map(h => ({ ...h })),
      qaMode: qaMode.value,
      // 额外保存全局流式状态，供 onUnmounted 后组件 remount 时恢复
      streamingSnapshot: {
        answering: answering.value,
        streamingText: streamingText.value,
        streamingReasoning: streamingReasoning.value,
        answerBuffer: answerBuffer.value,
        isReasoningPhase: isReasoningPhase.value,
        currentThinkingStatus: currentThinkingStatus.value,
        activeStreamingThinkingPanel: [...(activeStreamingThinkingPanel.value || [])],
        thinkingSteps: [...(thinkingSteps.value || [])],
        elapsedTime: elapsedTime.value,
        qaMode: qaMode.value,
      },
      savedAt: Date.now(),
    }
    localStorage.setItem(storageKey(), JSON.stringify(payload))
  } catch (e) {
    // 序列化失败（如超大/循环引用）时静默忽略，不影响主流程
    console.warn('[Persist] save failed:', e?.message || e)
  }
}

const restoreState = () => {
  try {
    const raw = localStorage.getItem(storageKey())
    if (!raw) return null
    const data = JSON.parse(raw)
    if (data?.modeState) {
      // 逐模式合并，避免缺字段；仅覆盖存在对应模式的属性
      for (const mode of Object.keys(modeState)) {
        const saved = data.modeState[mode]
        if (saved) {
          if (Array.isArray(saved.messages)) modeState[mode].messages = saved.messages
          if (typeof saved.currentSessionId === 'string') modeState[mode].currentSessionId = saved.currentSessionId
          if (typeof saved.question === 'string') modeState[mode].question = saved.question
          if (typeof saved.historyLoaded === 'boolean') modeState[mode].historyLoaded = saved.historyLoaded
          if (typeof saved.historyLoadedAt === 'number') modeState[mode].historyLoadedAt = saved.historyLoadedAt
          if (saved.streamingSnapshot && typeof saved.streamingSnapshot === 'object') {
            modeState[mode].streamingSnapshot = saved.streamingSnapshot
          }
          if (Array.isArray(saved.workflowSteps)) modeState[mode].workflowSteps = saved.workflowSteps
          if (typeof saved.workflowDone === 'boolean') modeState[mode].workflowDone = saved.workflowDone
          if (typeof saved.workflowError === 'boolean') modeState[mode].workflowError = saved.workflowError
          if (typeof saved.workflowResult === 'string') modeState[mode].workflowResult = saved.workflowResult
        }
      }
    }
    if (Array.isArray(data?.chatHistory)) chatHistory.value = data.chatHistory
    // 恢复全局流式快照
    const ss = data?.streamingSnapshot
    if (ss && ss.qaMode === qaMode.value) {
      answering.value = !!ss.answering
      streamingText.value = ss.streamingText || ''
      streamingReasoning.value = ss.streamingReasoning || ''
      answerBuffer.value = ss.answerBuffer || ''
      isReasoningPhase.value = !!ss.isReasoningPhase
      currentThinkingStatus.value = ss.currentThinkingStatus || ''
      activeStreamingThinkingPanel.value = Array.isArray(ss.activeStreamingThinkingPanel) ? [...ss.activeStreamingThinkingPanel] : []
      thinkingSteps.value = Array.isArray(ss.thinkingSteps) ? [...ss.thinkingSteps] : []
      elapsedTime.value = typeof ss.elapsedTime === 'number' ? ss.elapsedTime : 0
    }
    return data
  } catch (e) {
    console.warn('[Persist] restore failed:', e?.message || e)
    return null
  }
}

// 状态变化时自动落盘：deep 监听 messages，同步到 modeState 后再 debounce 落盘。
// 之前仅监听 messages.length，流式输出 content 变化时不会触发，导致刷新丢消息。
let persistTimer = null
const debouncedPersistState = () => {
  if (persistTimer) clearTimeout(persistTimer)
  persistTimer = setTimeout(() => {
    persistState()
    persistTimer = null
  }, 250)
}

watch(
  [() => messages.value, () => currentSessionId.value, qaMode],
  () => {
    const mode = qaMode.value
    if (mode !== 'workflow') {
      modeState[mode].messages = messages.value.map(m => ({ ...m }))
      modeState[mode].currentSessionId = currentSessionId.value || ''
    }
    debouncedPersistState()
  },
  { deep: true }
)
watch(chatHistory, debouncedPersistState, { deep: true })

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
  
  // 保存当前模式的输入框内容、右侧消息和当前会话
  const oldMode = qaMode.value
  modeState[oldMode].question = question.value
  modeState[oldMode].messages = messages.value.map(m => ({ ...m }))
  modeState[oldMode].currentSessionId = currentSessionId.value || ''
  
  // 保存工作流专属状态
  if (oldMode === 'workflow') {
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

  // 日常对话模式不依赖知识库，不设置 kbNotFound

  // 恢复目标模式的输入框内容、右侧消息和当前会话（按模式隔离）
  currentMessageId.value = null
  question.value = modeState[mode].question || ''
  if (mode !== 'workflow') {
    messages.value = (modeState[mode].messages || []).map(m => ({ ...m }))
    currentSessionId.value = modeState[mode].currentSessionId || ''
  }
  
  // 恢复工作流专属状态
  if (mode === 'workflow') {
    workflowSteps.value = [...(modeState.workflow.workflowSteps || [])]
    workflowDone.value = modeState.workflow.workflowDone || false
    workflowError.value = modeState.workflow.workflowError || false
    workflowResult.value = modeState.workflow.workflowResult || ''
  }
  
  // 切换模式时不再立即请求历史：chatHistory 已按 mode 字段聚合，
  // 直接过滤即可恢复目标模式列表，避免左侧骨架屏导致视觉卡顿。
  // 首次进入某模式在下一帧后台静默刷新；已加载过的模式超过冷却时间后也后台刷新，
  // 保持数据新鲜的同时不会阻塞切换动画。
  if (mode !== 'workflow') {
    const state = modeState[mode]
    const needRefresh = !state.historyLoaded ||
      (Date.now() - (state.historyLoadedAt || 0) > HISTORY_REFRESH_COOLDOWN_MS)
    if (needRefresh) {
      nextTick(() => loadChatHistory(true))
    }
  }

  // 简洁模式切换提示：延迟一点，等切换动画跑完再出现，减少干扰
  const modeNames = { chat: '日常对话', knowledge: '知识库问答', workflow: '多Agent工作流' }
  setTimeout(() => {
    ElMessage.success(`已切换到${modeNames[mode]}模式`)
  }, 120)
  debouncedPersistState() // 切换模式后立即落盘
}

// 强制停止当前生成并清空右侧对话状态（用于删除当前会话、切换页面等场景）
const resetCurrentChatState = () => {
  // 1. 取消网络请求和 reader，停止后台推流
  if (streamReader) {
    try { streamReader.cancel() } catch (e) { /* ignore */ }
    streamReader = null
  }
  if (streamAbortController) {
    try { streamAbortController.abort() } catch (e) { /* ignore */ }
    streamAbortController = null
  }

  // 2. 清掉后台任务 ID，避免卸载/重连时又把旧任务拉回来
  currentTaskId.value = ''
  try {
    localStorage.removeItem('kb_current_task_id')
  } catch (e) {}

  // 3. 清掉流式相关状态
  stopTimer()
  stopTypewriter()
  answering.value = false
  streamingText.value = ''
  fullStreamingText.value = ''
  streamingReasoning.value = ''
  thinkingSteps.value = []
  currentThinkingStatus.value = ''
  isReasoningPhase.value = false
  answerBuffer.value = ''

  // 4. 清掉当前会话的右侧消息
  currentMessageId.value = null
  currentSessionId.value = ''
  messages.value = []

  // 5. 同步清空当前模式状态，避免 persistState 又写回旧消息
  const mode = qaMode.value
  if (modeState[mode]) {
    modeState[mode].messages = []
    modeState[mode].currentSessionId = ''
    modeState[mode].question = ''
    if (mode === 'workflow') {
      modeState.workflow.workflowSteps = []
      modeState.workflow.workflowDone = false
      modeState.workflow.workflowError = false
      modeState.workflow.workflowResult = ''
    }
  }
}

// 开始新对话（仅清空当前模式）。聊天模式下乐观插入一个临时会话条目，
// 让左侧列表立即出现新项，避免发送第一条消息后才抖动刷新。
const startNewChat = () => {
  currentMessageId.value = null
  currentSessionId.value = ''
  messages.value = []
  question.value = ''
  // 同步保存到模式状态
  const mode = qaMode.value
  modeState[mode].question = ''
  modeState[mode].messages = []
  modeState[mode].currentSessionId = ''
  if (mode === 'workflow') {
    modeState.workflow.workflowSteps = []
    modeState.workflow.workflowDone = false
    modeState.workflow.workflowError = false
    modeState.workflow.workflowResult = ''
  }

  // 聊天/知识库模式：在左侧列表头部插入一个未命名的临时会话
  if (qaMode.value === 'chat' || qaMode.value === 'knowledge') {
    const tempId = `temp-${Date.now()}`
    const tempSession = {
      id: tempId,
      session_id: tempId,
      question: '新对话',
      answer: '',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      is_session: true,
      mode: qaMode.value,
      _isOptimistic: true,
    }
    chatHistory.value = [tempSession, ...chatHistory.value.filter(h => h.id !== tempId)]
  }
  persistState() // 新对话状态立即落盘
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

    let res
    let notFound = false
    // 临时会话（未落库）直接在前端移除，不调后端
    if (msg.session_id && String(msg.session_id).startsWith('temp-')) {
      res = { ok: true, success: true }
    } else if (qaMode.value === 'chat') {
      try {
        res = await knowledgeBaseAPI.deleteChatSession(msg.session_id)
      } catch (err) {
        if (err?.response?.status === 404 || err?.status === 404) {
          notFound = true
          res = { ok: true, success: true }
        } else {
          throw err
        }
      }
    } else {
      try {
        res = await knowledgeBaseAPI.deleteSession(kbId.value, msg.session_id)
      } catch (err) {
        if (err?.response?.status === 404 || err?.status === 404) {
          notFound = true
          res = { ok: true, success: true }
        } else {
          throw err
        }
      }
    }
    if (res.ok || res.success) {
      ElMessage.success('删除成功')
      // 直接从本地列表移除（包括后端不存在的幽灵会话）
      chatHistory.value = chatHistory.value.filter(h => h.id !== msg.id && h.session_id !== msg.session_id)
      selectedMessages.value.delete(msg.id)
      persistState()
      // 如果删除的是当前选中的会话，清空右侧对话区域
      if (currentSessionId.value === msg.session_id) {
        currentMessageId.value = null
        currentSessionId.value = ''
        messages.value = []
      }
      // 最后再拉一次后端列表兜底
      await loadChatHistory()
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
  if (isAllSelected.value) {
    // 已全选，取消全选（仅取消当前模式可见记录）
    visibleHistory.value.forEach(msg => selectedMessages.value.delete(msg.id))
  } else {
    // 全选当前模式可见记录
    visibleHistory.value.forEach(msg => selectedMessages.value.add(msg.id))
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
    
    // 逐个删除会话（根据当前模式选择对应接口）
    let totalDeleted = 0
    let successCount = 0
    for (const sessionId of selectedSessionIds) {
      try {
        // 临时会话（未落库）直接跳过，不调后端
        if (String(sessionId).startsWith('temp-')) {
          successCount += 1
          continue
        }
        const res = qaMode.value === 'chat'
          ? await knowledgeBaseAPI.deleteChatSession(sessionId)
          : await knowledgeBaseAPI.deleteSession(kbId.value, sessionId)
        if (res.success || res.ok) {
          successCount += 1
          totalDeleted += res.deleted_count || 0
        }
      } catch (error) {
        // 404 表示后端已无该会话，也视为删除成功，前端移除即可
        if (error?.response?.status === 404 || error?.status === 404) {
          successCount += 1
          console.log(`会话 ${sessionId} 在后端不存在，前端直接移除`)
        } else {
          console.error(`删除会话 ${sessionId} 失败:`, error)
        }
      }
    }
    
    ElMessage.success(`成功删除 ${successCount} 个会话，共 ${totalDeleted} 条消息`)
    // 如果删除的是当前选中的会话，先停止可能正在进行的生成任务并清空状态
    if (currentSessionId.value && selectedSessionIds.includes(currentSessionId.value)) {
      resetCurrentChatState()
    }

    // 直接从本地列表移除所有选中的会话（包括后端不存在的幽灵会话）
    chatHistory.value = chatHistory.value.filter(
      h => !selectedSessionIds.includes(h.session_id)
    )
    selectedMessages.value.clear()
    persistState()
    // 最后再拉一次后端列表兜底
    await loadChatHistory()
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
  
  // 6. 有序列表（支持模型输出多个 1. 时兜底重排为 1/2/3...，允许空行分隔）
  formatted = formatted.replace(/((?:^\d+\. .+(?:\n|$))(?:\n*^\d+\. .+(?:\n|$))*)/gm, (match) => {
    const items = match.split('\n').filter(l => /^\d+\. /.test(l.trim()))
    if (items.length === 0) return match
    const lis = items.map((l) => `<li>${l.trim().replace(/^\d+\. /, '')}</li>`).join('')
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
    background: var(--tech-card);
    z-index: 9999;
    display: flex;
    flex-direction: column;
    box-shadow: -4px 0 24px var(--tech-shadow);
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
    background: var(--tech-card);
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
const finishStreaming = (fullAnswer, contextDocs, skillName, responseTimeMs, { calledRef = null, evalInfo = null } = {}) => {
  // 用局部引用防重，避免 HMR/多事件导致重复写入
  if (calledRef && calledRef.value) return
  if (calledRef) calledRef.value = true

  stopTimer()
  answering.value = false

  // 深度思考模型可能把内容全输出在 reasoning 字段，content 为空；
  // 兜底：用已累积的推理内容作为最终答案，避免只显示占位符。
  if (!fullAnswer && reasoningMode.value === 'reasoning' && streamingReasoning.value) {
    fullAnswer = streamingReasoning.value
  }

  // 将完成的 AI 回复添加到消息列表（附带思考过程和真实推理）
  if (fullAnswer) {
    const isDeepThinking = reasoningMode.value === 'reasoning'
    const thinkingSnapshot = isDeepThinking ? [...thinkingSteps.value] : []
    const reasoningSnapshot = isDeepThinking ? (streamingReasoning.value || '') : ''
    const evalData = evalInfo || null
    messages.value.push({
      _id: nextMessageKey(),
      content: fullAnswer,
      isUser: false,
      contextDocs: contextDocs || [],
      skill: skillName || null,
      responseTime: responseTimeMs,
      isDeepThinking,
      thinkingProcess: thinkingSnapshot.length > 0 ? thinkingSnapshot : undefined,
      reasoningText: reasoningSnapshot || undefined,
      evalScore: evalData?.score ?? undefined,
      evalIterations: evalData?.iterations ?? undefined,
      needsHuman: evalData?.needsHuman ?? false,
      evalPending: evalData?.pending ?? false,
    })
    scrollToBottom()
    // 新会话首次发完消息后，延迟刷新一次历史列表以获取后端持久化的会话 id；
    // 后续同一会话内的消息不再触发整表刷新，避免左侧列表闪烁。
    if (!currentSessionId.value || !chatHistory.value.some(h => h.id === currentSessionId.value)) {
      setTimeout(() => loadChatHistory(), 500)
    }
  }

  // 清理流式状态
  streamingText.value = ''
  streamingReasoning.value = ''
  thinkingSteps.value = []
  currentThinkingStatus.value = ''
  activeStreamingThinkingPanel.value = []
  isReasoningPhase.value = false
  answerBuffer.value = ''
  persistState() // AI 回复完成后立即落盘
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
  messages.value.push({ _id: nextMessageKey(), content: userQuestion, isUser: true })
  scrollToBottom()
  persistState() // 工作流用户问题发出后立即落盘

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
      _id: nextMessageKey(),
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
      _id: nextMessageKey(),
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
  
  // 3. 保存当前已显示的内容作为完整回答（思考阶段被停止时，也包含缓存的答案 token）
  const currentAnswer = streamingText.value || answerBuffer.value || fullStreamingText.value
  if (currentAnswer) {
    const isDeepThinking = reasoningMode.value === 'reasoning'
    const thinkingSnapshot = isDeepThinking ? [...thinkingSteps.value] : []
    const reasoningSnapshot = isDeepThinking ? (streamingReasoning.value || '') : ''
    messages.value.push({
      _id: nextMessageKey(),
      content: currentAnswer,
      isUser: false,
      contextDocs: [],
      skill: activeSkill.value?.name || null,
      responseTime: elapsedTime.value * 1000,
      isDeepThinking,
      thinkingProcess: thinkingSnapshot.length > 0 ? thinkingSnapshot : undefined,
      reasoningText: reasoningSnapshot || undefined,
    })
    scrollToBottom()
    // 同一会话内后续消息不再刷新左侧历史，避免闪烁
    if (!currentSessionId.value || !chatHistory.value.some(h => h.id === currentSessionId.value)) {
      setTimeout(() => loadChatHistory(), 500)
    }
    persistState() // 停止流式后落盘已生成内容
  }

  // 4. 清理流式状态
  stopTimer()
  stopTypewriter()
  stopTaskPolling()
  currentTaskId.value = ''
  try { localStorage.removeItem('kb_current_task_id') } catch (e) {}
  answering.value = false
  streamingText.value = ''
  fullStreamingText.value = ''
  streamingReasoning.value = ''
  thinkingSteps.value = []
  currentThinkingStatus.value = ''
  isReasoningPhase.value = false
  answerBuffer.value = ''
  
  ElMessage.info('已停止生成')
}

// 发送问题
const sendMessage = async () => {
  if ((!question.value.trim() && pendingImages.value.length === 0) || answering.value) return

  // 知识库模式下，没有可用知识库时阻止发送并提示
  if (qaMode.value === 'knowledge' && (kbNotFound.value || !kbId.value || !String(kbId.value).trim())) {
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
  messages.value.push({ _id: nextMessageKey(), content: userQuestion, isUser: true, images: userImages })
  scrollToBottom()
  persistState() // 用户问题发出后立即落盘

  // 初始化流式状态：不再伪造“AI 正在连接”步骤，等后端推送真实状态
  answering.value = true
  streamingText.value = ''
  streamingReasoning.value = ''
  thinkingSteps.value = []
  isReasoningPhase.value = reasoningMode.value === 'reasoning'
  answerBuffer.value = ''
  currentThinkingStatus.value = reasoningMode.value === 'reasoning' ? '深度思考中...' : '生成中...'
  startTimer()
  streamAbortController = new AbortController()

  // 总超时 120s，防止后端挂起导致前端无限等待
  let totalTimeoutId = null
  let idleTimeoutId = null
  const clearStreamTimers = () => {
    if (totalTimeoutId) clearTimeout(totalTimeoutId)
    if (idleTimeoutId) clearTimeout(idleTimeoutId)
    totalTimeoutId = null
    idleTimeoutId = null
    stopContentIdleCheck()
  }
  const resetIdleTimeout = () => {
    if (idleTimeoutId) clearTimeout(idleTimeoutId)
    idleTimeoutId = setTimeout(() => {
      if (streamAbortController) {
        streamAbortController.abort(new Error('IDLE_TIMEOUT'))
      }
    }, 45000)
  }
  totalTimeoutId = setTimeout(() => {
    if (streamAbortController) {
      streamAbortController.abort(new Error('REQUEST_TIMEOUT'))
    }
  }, 120000)
  resetIdleTimeout()

  let streamDone = false
  const finishCalled = ref(false)
  let fullAnswer = ''
  let contextDocs = []
  let responseTimeMs = 0

  // 统一的流式内容静默兜底：只要 reasoning / answer / streamingText 任一
  // 超过 IDLE_MS 没增长，就认为模型已经停止输出，自动完成。
  let contentIdleTimer = null
  let lastContentLen = 0
  let lastContentTime = 0
  const CONTENT_IDLE_MS = 4000
  const startContentIdleCheck = () => {
    if (contentIdleTimer) return
    lastContentLen = (
      (streamingReasoning.value?.length || 0) +
      (answerBuffer.value?.length || 0) +
      (streamingText.value?.length || 0)
    )
    lastContentTime = Date.now()
    contentIdleTimer = setInterval(() => {
      if (streamDone || reasoningMode.value !== 'reasoning') return
      const reasoningLen = streamingReasoning.value?.length || 0
      const answerLen = answerBuffer.value?.length || 0
      const textLen = streamingText.value?.length || 0
      const totalLen = reasoningLen + answerLen + textLen
      const now = Date.now()
      if (totalLen > lastContentLen) {
        lastContentLen = totalLen
        lastContentTime = now
        return
      }
      if (totalLen === lastContentLen && now - lastContentTime > CONTENT_IDLE_MS) {
        const fallbackAnswer = answerBuffer.value || streamingReasoning.value || streamingText.value || ''
        console.log('[ContentIdle] 流式内容 4s 未增长，自动兜底完成', fallbackAnswer.length)
        streamDone = true
        resetIdleTimeout()
        clearStreamTimers()
        finishStreaming(fallbackAnswer, contextDocs, skillName, responseTimeMs, { calledRef: finishCalled })
      }
    }, 500)
  }
  const stopContentIdleCheck = () => {
    if (contentIdleTimer) {
      clearInterval(contentIdleTimer)
      contentIdleTimer = null
    }
  }

  try {
    // 只在对话模式下使用 Skill，知识库模式不需要角色设定
    const isChatMode = qaMode.value === 'chat'
    const systemPrompt = isChatMode ? (activeSkill.value?.systemPrompt || undefined) : undefined
    const skillName = isChatMode ? (activeSkill.value?.name || undefined) : undefined

    // 使用流式 SSE API（带 AbortController）
    // 日常对话不依赖知识库，使用独立接口
    const streamUrl = qaMode.value === 'chat'
      ? `/api/v1/knowledge/chat/stream/`
      : `/api/v1/knowledge/knowledge-bases/${kbId.value}/ask_stream/`
    const token = localStorage.getItem('access_token')
    const response = await fetch(
      streamUrl,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          question: userQuestion,
          session_id: currentSessionId.value || undefined,
          mode: qaMode.value,
          system_prompt: systemPrompt,
          skill_name: skillName,
          enable_reasoning: reasoningMode.value === 'reasoning',
          images: userImages.length > 0 ? userImages : undefined,
          user_id: currentUserId.value ?? undefined,
        }),
        signal: streamAbortController.signal,
      }
    )

    // 收到响应首包即重置空闲计时
    resetIdleTimeout()

    if (!response.ok) {
      const errText = await response.text().catch(() => '')
      console.error(`[KnowledgeChat] Ask stream failed status: ${response.status}`, errText.slice(0, 200))
      if (response.status === 401) {
        ElMessage.error('登录已过期，请重新登录')
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        localStorage.removeItem('user')
        router.replace('/login')
        return
      }
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    streamReader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await streamReader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop() || ''
      for (const block of blocks) {
        processSSEBlock(block)
      }
    }
    if (buffer.trim()) processSSEBlock(buffer.trim())

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
              // 接收 session_id 和 task_id（task_id 用于切换页面后重连）
              if (data.task_id) {
                currentTaskId.value = data.task_id
                try { localStorage.setItem('kb_current_task_id', data.task_id) } catch (e) {}
              }
              // 接收 session_id 和 skill 信息
              if (data.session_id && !currentSessionId.value) {
                currentSessionId.value = data.session_id
                // 新会话立即在左侧插入占位，标题先用问题前 8 字兜底，等 finishStreaming 刷新
                const placeholderTitle = (userQuestion || '新对话').slice(0, 8) || '新对话'
                // 移除同模式的乐观临时项，避免 temp-xxx 和真实 session_id 同时存在导致闪烁
                chatHistory.value = chatHistory.value.filter(
                  h => !(h.mode === qaMode.value && h._isOptimistic)
                )
                chatHistory.value.unshift({
                  id: data.session_id,
                  session_id: data.session_id,
                  question: placeholderTitle,
                  answer: '',
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                  is_session: true,
                  mode: qaMode.value,
                })
              }
              break

            case 'status':
              // 后端推送的进度提示（检索中、生成中）
              if (data.content) {
                currentThinkingStatus.value = data.content
                // 仅在深度思考模式下累积为思考步骤，避免快速模式也显示思考面板
                if (reasoningMode.value === 'reasoning') {
                  thinkingSteps.value = [...thinkingSteps.value, data.content]
                  // 进入深度思考即刻展开临时思考面板，让用户实时看到思考过程
                  activeStreamingThinkingPanel.value = ['reasoning']
                  scrollToBottom()
                }
              }
              break

            case 'reasoning':
              // 模型真正的链式推理文本 —— 仅在深度思考模式下流式累积显示
              if (data.content && reasoningMode.value === 'reasoning') {
                streamingReasoning.value += data.content
                isReasoningPhase.value = true
                // 思考阶段保持临时思考面板展开，让用户实时看到思考过程
                activeStreamingThinkingPanel.value = ['reasoning']
                // 思考过程不断变长时，自动向下滚动，避免用户手动下拉
                scrollToBottom()
                startContentIdleCheck()
              }
              break
            
            case 'token':
              // 深度思考模式：思考阶段（收到第一个 token 之前）不显示答案，
              // 让用户先完整看到黑框思考过程；一旦 reasoning 阶段结束（首个 token 到达），
              // 立即把已缓存的答案实时逐字流出，避免「思考完→答案空白等待」的卡顿感。
              if (reasoningMode.value === 'reasoning') {
                if (isReasoningPhase.value) {
                  isReasoningPhase.value = false
                  // reasoning 阶段结束，把已缓存的内容交接给实时显示区，无缝衔接
                  streamingText.value = answerBuffer.value || ''
                }
                answerBuffer.value += data.content
                streamingText.value += data.content
                scrollToBottom()
                startContentIdleCheck()
              } else {
                fullAnswer += data.content
                streamingText.value = fullAnswer
                scrollToBottom()
              }
              break
            
            case 'done':
              // 流式完成：若已处理过则忽略，避免后端/网络重发导致重复渲染
              stopContentIdleCheck()
              const doneTaskId = data.task_id || currentTaskId.value
              currentTaskId.value = ''
              try { localStorage.removeItem('kb_current_task_id') } catch (e) {}
              if (doneTaskId && finishedTaskIds.has(doneTaskId)) {
                console.log('[SSE] 忽略已处理过的 done 事件，task:', doneTaskId)
                break
              }
              if (doneTaskId) finishedTaskIds.add(doneTaskId)
              if (!streamDone) {
                streamDone = true
                fullAnswer = data.full_answer || answerBuffer.value || streamingText.value || fullAnswer
                // 深度思考模式下若答案仍为空，用累积的 reasoning 兜底，避免卡住
                if (!fullAnswer && reasoningMode.value === 'reasoning' && streamingReasoning.value) {
                  fullAnswer = streamingReasoning.value
                }
                contextDocs = data.context_docs || []
                // 记录后端计算的响应耗时（毫秒）
                if (data.response_time) {
                  responseTimeMs = data.response_time
                }
                // 评估闭环元数据（得分/轮次/人工协同/后台评估中）
                const evalInfo = (data.eval_score !== undefined || data.needs_human || data.eval_pending)
                  ? {
                      score: data.eval_score,
                      iterations: data.eval_iterations,
                      needsHuman: !!data.needs_human,
                      pending: !!data.eval_pending,
                    }
                  : null
                if (data.needs_human) {
                  ElMessage.warning('本次回答未通过质量评估，已转人工协同复核')
                }
                // 直接完成流式输出
                finishStreaming(fullAnswer, contextDocs, skillName, responseTimeMs, { calledRef: finishCalled, evalInfo })
              }
              break
            
            case 'error':
              throw new Error(data.message || '未知错误')
          }
          // 非 meta 事件计入序号，供重连 offset 使用
          if (data.type !== 'meta') eventSeq += 1
        } catch (parseError) {
          // JSON 解析失败，跳过该条消息，避免整流失败
          console.warn('SSE parse error:', parseError, 'payload:', payload)
        }
      }
    }

    // 如果流结束但没有收到 done 事件（异常情况），也完成
    if (!streamDone) {
      // 深度思考模式下，若 content 为空但有 reasoning 累积，用 reasoning 兜底
      if (!fullAnswer && reasoningMode.value === 'reasoning' && (answerBuffer.value || streamingReasoning.value)) {
        fullAnswer = answerBuffer.value || streamingReasoning.value
      }
      finishStreaming(fullAnswer, contextDocs, skillName, responseTimeMs, { calledRef: finishCalled })
    }
    // 保证流式显示已结束
    answering.value = false
    streamingText.value = ''
  } catch (error) {
    clearStreamTimers()
    // 用户主动取消不算错误
    if (error.name === 'AbortError') {
      const msg = error.message || ''
      if (msg === 'REQUEST_TIMEOUT') {
        ElMessage.error('请求总超时，已停止等待')
      } else if (msg === 'IDLE_TIMEOUT') {
        ElMessage.error('响应超时，已停止等待')
      } else {
        console.log('用户停止了流式输出')
      }
      // 超时情况下保存已有内容
      if ((msg === 'REQUEST_TIMEOUT' || msg === 'IDLE_TIMEOUT') && (streamingText.value || answerBuffer.value || streamingReasoning.value)) {
        // 深度思考模式下答案缓存在 answerBuffer；若 answerBuffer 也为空，用 reasoning 兜底
        const currentAnswer = answerBuffer.value || streamingText.value || streamingReasoning.value
        messages.value.push({
          _id: nextMessageKey(),
          content: currentAnswer,
          isUser: false,
          contextDocs: [],
          responseTime: elapsedTime.value * 1000,
          isDeepThinking: reasoningMode.value === 'reasoning',
          thinkingProcess: reasoningMode.value === 'reasoning' && thinkingSteps.value.length > 0 ? [...thinkingSteps.value] : undefined,
          reasoningText: reasoningMode.value === 'reasoning' && streamingReasoning.value ? streamingReasoning.value : undefined,
        })
        scrollToBottom()
      }
      return
    }
    console.error('Ask stream error:', error)
    messages.value.push({
      _id: nextMessageKey(),
      content: '抱歉，回答失败，请稍后重试。',
      isUser: false,
    })
  } finally {
    clearStreamTimers()
    stopTimer()
    // 兜底：任何情况下都要结束流式状态
    answering.value = false
    streamingText.value = ''
    streamingReasoning.value = ''
    thinkingSteps.value = []
    currentThinkingStatus.value = ''
    isReasoningPhase.value = false
    answerBuffer.value = ''
    streamReader = null
    streamAbortController = null
    // 兜底刷新历史：仅在可能是新会话时触发，避免同一会话重复刷新导致闪烁
    if (!currentSessionId.value || !chatHistory.value.some(h => h.id === currentSessionId.value)) {
      setTimeout(() => loadChatHistory(), 800)
    }
  }
}

// ── 切换页面后轮询后台任务结果（不重连 SSE，真正异步解耦页面生命周期） ──
let taskPollTimer = null

async function pollTaskResult() {
  const taskId = currentTaskId.value
  if (!taskId) return
  const token = localStorage.getItem('access_token')
  const url = `/api/v1/knowledge/chat/task/${taskId}/result`
  try {
    const resp = await fetch(url, {
      method: 'GET',
      headers: { 'Authorization': `Bearer ${token}` },
    })
    if (!resp.ok) {
      console.warn('[Poll] 任务查询失败 status', resp.status)
      return
    }
    const data = await resp.json()
    if (!data.exists) {
      // 任务已不存在（如已过期）：放弃轮询，回退到历史加载
      console.log('[Poll] 任务不存在，停止轮询', taskId)
      stopTaskPolling()
      currentTaskId.value = ''
      try { localStorage.removeItem('kb_current_task_id') } catch (e) {}
      return
    }
    if (data.error) {
      console.warn('[Poll] 后台任务出错', data.error)
      stopTaskPolling()
      currentTaskId.value = ''
      try { localStorage.removeItem('kb_current_task_id') } catch (e) {}
      ElMessage.error('生成任务失败：' + data.error)
      return
    }
    if (data.done && data.full_answer) {
      // 任务完成：直接渲染完整答案，无需再等 SSE 增量
      stopTaskPolling()
      const doneTaskId = taskId
      currentTaskId.value = ''
      try { localStorage.removeItem('kb_current_task_id') } catch (e) {}
      if (doneTaskId && finishedTaskIds.has(doneTaskId)) {
        console.log('[Poll] 忽略已处理过的任务', doneTaskId)
        return
      }
      if (doneTaskId) finishedTaskIds.add(doneTaskId)
      finishStreaming(data.full_answer, [], null, 0, {})
      return
    }
    // 未完成：保持“生成中”状态，继续轮询
    if (!answering.value) {
      answering.value = true
      currentThinkingStatus.value = reasoningMode.value === 'reasoning' ? '深度思考中...' : '生成中...'
    }
  } catch (e) {
    console.warn('[Poll] 轮询异常', e)
  }
}

function startTaskPolling() {
  stopTaskPolling()
  // 立即查一次，再每 2 秒轮询，彻底解耦页面生命周期
  pollTaskResult()
  taskPollTimer = setInterval(pollTaskResult, 2000)
}

function stopTaskPolling() {
  if (taskPollTimer) {
    clearInterval(taskPollTimer)
    taskPollTimer = null
  }
}

// 滚动到底部
const scrollToBottom = async () => {
  await nextTick()
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

// 滚动思考过程文本到底部，保持最新内容可见
const scrollReasoningToBottom = async () => {
  await nextTick()
  const el = reasoningContentRef.value
  if (el) {
    el.scrollTop = el.scrollHeight
  }
}

// 思考内容变化时自动滚动到底部，让最新文字始终出现在可视区域内
watch(streamingReasoning, () => {
  if (activeStreamingThinkingPanel.value.includes('reasoning')) {
    scrollReasoningToBottom()
  }
})

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
    const status = error?.response?.status
    // 404 多为后端未部署新接口或旧数据，静默处理，空文档由对话框自身展示
    if (status !== 404) {
      ElMessage.error(error?.response?.data?.detail || '加载文档列表失败，请稍后重试')
    }
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
    th { background: #409eff; color: var(--tech-text); padding: 10px 8px; text-align: left; font-size: 14px; }
    td { border: 1px solid var(--tech-border); padding: 8px; font-size: 13px; }
    tr:nth-child(even) td { background: var(--tech-card-deep); }
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

// 初始化时主动校验登录态，避免旧 token 残留导致挂载即 401 反复跳登录
const ensureValidToken = async () => {
  const token = localStorage.getItem('access_token')
  if (!token) {
    ElMessage.warning('请先登录')
    router.replace('/login')
    return false
  }
  try {
    // api/index.js 的响应拦截器已返回 response.data，所以 res 就是 profile 数据
    const res = await authAPI.getProfile()
    if (!res || (!res.user && !res.username)) {
      throw new Error('invalid token')
    }
    return true
  } catch (e) {
    const status = e?.response?.status || e?.status
    // 只有明确 401 才认定 token 过期并清理；其他错误可能是网络/代理抖动，不重定向
    if (status === 401) {
      console.warn('[Auth] token expired (401), redirect to login')
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('user')
      ElMessage.error('登录已过期，请重新登录')
      router.replace('/login')
    } else {
      console.warn('[Auth] profile check failed (non-401), keep session:', status, e?.message || e)
    }
    return false
  }
}

onMounted(async () => {
  // 兜底：确保全局 FileReader 在 window 上可用，避免某些 Vite HMR/编译场景下引用失败
  if (typeof window !== 'undefined' && typeof window.FileReader === 'undefined' && typeof FileReader !== 'undefined') {
    window.FileReader = FileReader
  }

  const savedTheme = localStorage.getItem('knowledge-theme')
  isDark.value = savedTheme === 'dark'
  applyTheme()

  const ok = await ensureValidToken()
  if (!ok) return  // token 失效，已跳登录页，停止后续初始化

  // 1. 先恢复本地持久化的对话状态（消息/历史/当前会话/上次模式），避免切换页面 remount 后丢失
  const restored = restoreState()
  // 2. 以持久化的模式为准；没有持久化时再由 URL 决定默认模式。
  // 注意：不能用 route.path.startsWith('/knowledge/') 判断是否 knowledge 模式，
  // 因为 chat 模式下 loadKnowledgeBase 也会把 kbId 写进路径（参见下方改动说明），
  // 导致 remount 后误判为 knowledge。改用 route.name 区分（KnowledgeChatDetail 才是显式知识库详情）。
  if (restored?.qaMode && ['chat', 'knowledge', 'workflow'].includes(restored.qaMode)) {
    qaMode.value = restored.qaMode
    console.log('[Restore] restored qaMode:', restored.qaMode)
  } else {
    qaMode.value = route.name === 'KnowledgeChatDetail' ? 'knowledge' : 'chat'
  }

  await loadKnowledgeBase()  // 先加载知识库，确保kbId就绪

  // 3. 恢复当前模式的输入框、workflow 步骤等非消息类 UI 状态
  const cur = qaMode.value
  if (modeState[cur]) {
    question.value = modeState[cur].question || ''
    // 消息/会话 id 先不恢复，由第 5 步统一决定（刷新保留，菜单进入新对话）
    if (cur === 'workflow') {
      workflowSteps.value = Array.isArray(modeState.workflow.workflowSteps) ? [...modeState.workflow.workflowSteps] : []
      workflowDone.value = !!modeState.workflow.workflowDone
      workflowError.value = !!modeState.workflow.workflowError
      workflowResult.value = modeState.workflow.workflowResult || ''
    }
  }
  // 4. 根据当前模式加载对应历史（知识库或日常对话）——会增量合并，不会覆盖本地会话内消息
  await loadChatHistory()
  // 5. 恢复当前进行中的对话：
  //    - 只要本地有未结束的消息，不管刷新还是从菜单切回，都恢复当前对话。
  //    - 只有本地没有任何消息时，才默认打开全新对话。
  const restoredMessages = modeState[cur]?.messages || []
  const restoredSessionId = modeState[cur]?.currentSessionId || ''
  console.log('[Restore] cur:', cur, 'restoredMessages:', restoredMessages.length, 'sessionId:', restoredSessionId)
  if (restoredMessages.length > 0) {
    // 恢复当前进行中的对话
    messages.value = restoredMessages.map(m => ({ ...m }))
    currentSessionId.value = restoredSessionId
    currentMessageId.value = null
    // 恢复未完成的后台任务 id，用于切回页面时异步轮询结果（不再依赖事件序号断点）
    const savedTaskId = localStorage.getItem('kb_current_task_id')
    if (savedTaskId) {
      currentTaskId.value = savedTaskId
    }
    // 若最后一条是离开页面时中断的 AI 消息（兼容旧版 localStorage 数据），清理流式占位状态
    const lastMsg = messages.value[messages.value.length - 1]
    if (lastMsg && !lastMsg.isUser && lastMsg._interrupted) {
      answering.value = false
      streamingText.value = ''
      streamingReasoning.value = ''
      answerBuffer.value = ''
      isReasoningPhase.value = false
      currentThinkingStatus.value = ''
      activeStreamingThinkingPanel.value = []
      thinkingSteps.value = []
      modeState[cur].streamingSnapshot = null
    }
    let matched = chatHistory.value.find(h => h.session_id === restoredSessionId)
    if (matched) {
      currentMessageId.value = matched.id
    } else if (restoredSessionId && !restoredSessionId.startsWith('temp-')) {
      // 后端历史列表里还没出现当前会话（可能尚未落库或列表接口未返回），
      // 临时补一个当前会话项到左侧，避免“右侧有消息、左侧找不到会话”
      const firstUserMsg = restoredMessages.find(m => m.role === 'user')
      const title = firstUserMsg?.content?.slice(0, 30) || '当前对话'
      const tempItem = {
        id: restoredSessionId,
        session_id: restoredSessionId,
        question: title,
        answer: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        is_session: true,
        mode: cur,
        _isCurrent: true,
      }
      chatHistory.value = [tempItem, ...chatHistory.value.filter(h => h.session_id !== restoredSessionId)]
      currentMessageId.value = restoredSessionId
    }
  } else {
    // 没有进行中的对话：优先定位到当前模式下最新的一条历史记录，
    // 避免每次进入页面都自动创建空的新对话；只有当前模式完全没有历史时才新建。
    const visible = chatHistory.value.filter(h => h.mode === cur && !h._isOptimistic)
    if (visible.length > 0) {
      const latest = visible[0] // 已按 updated_at 倒序，第一条即最新
      await selectMessage(latest)
    } else {
      startNewChat()
    }
  }
  setupCodeBlockCopy()
  loadSkills() // 加载 Skills

  // 6. 若离开页面时存在未完成的后台生成任务，切回后异步轮询结果（不重连 SSE）
  if (currentTaskId.value) {
    // 等待本轮初始化（历史/消息恢复）完成再轮询，避免与初次渲染竞争
    nextTick(async () => {
      try {
        startTaskPolling()
      } catch (e) {
        console.warn('[Poll] 自动轮询启动失败', e)
      }
    })
  }
})

// 同步当前模式的消息和会话 id，确保切换模式时状态最新。
// 注意：不要 immediate，否则 setup 阶段会清空 restoreState 之前已持久化的状态。
watch(
  [() => messages.value.length, () => currentSessionId.value, qaMode],
  () => {
    const mode = qaMode.value
    if (mode !== 'workflow') {
      modeState[mode].messages = messages.value.map(m => ({ ...m }))
      modeState[mode].currentSessionId = currentSessionId.value || ''
    }
  }
)

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
  // 兜底：组件销毁（路由切换 remount）前，把当前对话状态落盘，回来时可恢复
  if (persistTimer) {
    clearTimeout(persistTimer)
    persistTimer = null
  }
  // 后台生成任务不依赖前端连接：离开页面时只需保存 task_id，
  // 回来时通过轮询 result 接口获取结果（后端任务仍在跑，结果自动落库）。
  // 若本轮发送已结束或用户主动停止，则清理 task_id，避免回来后误轮询。
  stopTaskPolling()
  if (currentTaskId.value && answering.value) {
    try {
      localStorage.setItem('kb_current_task_id', currentTaskId.value)
    } catch (e) { /* ignore */ }
  } else {
    currentTaskId.value = ''
    try { localStorage.removeItem('kb_current_task_id') } catch (e) {}
  }
  persistState()
})
</script>

<style scoped>
.knowledge-chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background:
    radial-gradient(circle at 80% 10%, rgba(64, 158, 255, 0.06) 0%, transparent 35%),
    radial-gradient(circle at 20% 90%, rgba(168, 85, 247, 0.05) 0%, transparent 40%),
    linear-gradient(180deg, var(--tech-bg) 0%, var(--tech-bg-deep) 100%);
  color: var(--tech-text);
}

.chat-header {
  display: flex;
  align-items: center;
  padding: 15px 20px;
  border-bottom: 1px solid var(--tech-border);
  background: rgba(var(--tech-bg-rgb), 0.55);
  backdrop-filter: blur(10px);
}

.chat-header h3 {
  margin-left: 10px;
  font-size: 18px;
  font-weight: 600;
  color: var(--tech-text);
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
  border-right: 1px solid var(--tech-border);
  background:
    radial-gradient(circle at 0% 0%, rgba(64, 158, 255, 0.1) 0%, transparent 40%),
    radial-gradient(circle at 100% 100%, rgba(168, 85, 247, 0.08) 0%, transparent 45%),
    linear-gradient(180deg, var(--tech-bg) 0%, var(--tech-bg-deep) 100%);
  transition: width 0.25s ease, min-width 0.25s ease;
  overflow: hidden;
  color: var(--tech-text);
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
  color: var(--tech-text-dim);
  transition: background 0.2s, color 0.2s;
  border-right: 1px solid var(--tech-border);
  background: var(--tech-bg);
}

.history-collapsed-bar:hover {
  background: rgba(64, 158, 255, 0.12);
  color: var(--tech-cyan);
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
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--tech-border);
  background: rgba(var(--tech-bg-rgb), 0.7);
  backdrop-filter: blur(8px);
  flex-shrink: 0;
}

.history-panel-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.history-panel-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--tech-text);
  letter-spacing: 0.5px;
  white-space: nowrap;
  flex-shrink: 0;
}

.history-panel-header-left .el-checkbox {
  margin-right: 0;
  flex-shrink: 0;
  position: relative;
}

/* 用一个绝对定位的伪元素强制画出明显的外框，覆盖在 Element Plus 原框上方 */
.history-panel-header-left .el-checkbox .el-checkbox__input::after {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 24px;
  height: 24px;
  box-sizing: border-box;
  background-color: #ffffff;
  border: 3.5px solid #0d47a1;
  border-radius: 4px;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.95), 0 0 0 5px rgba(13, 71, 161, 0.35);
  pointer-events: none;
  z-index: 2;
}

.history-panel-header-left .el-checkbox.is-checked .el-checkbox__input::after {
  background-color: #0d47a1;
  border-color: #082d6b;
  box-shadow: 0 0 14px rgba(13, 71, 161, 0.65);
}

.history-panel-header-left .el-checkbox .el-checkbox__label {
  color: #141414 !important;
  font-weight: 700 !important;
  font-size: 15px !important;
  padding-left: 34px !important;
}

.history-panel-header-left .el-checkbox.is-checked .el-checkbox__label {
  color: #0d47a1 !important;
}

/* 让原生的 inner 变透明，只保留对勾 */
.history-panel-header-left .el-checkbox .el-checkbox__inner {
  background-color: transparent !important;
  border-color: transparent !important;
  box-shadow: none !important;
  width: 24px !important;
  height: 24px !important;
  z-index: 3;
}

.history-panel-header-left .el-checkbox.is-checked .el-checkbox__inner::after {
  border-color: #ffffff !important;
  border-width: 3px !important;
  width: 6px !important;
  height: 12px !important;
  left: 6px !important;
  top: 0 !important;
}

.history-panel-header-left .el-button {
  flex-shrink: 0;
  padding: 4px 8px;
  font-weight: 600;
}

.history-panel-header-left .el-button.is-text {
  color: #f56c6c;
}

.history-panel-header-left .el-button.is-text:hover {
  color: #ff8585;
  background: rgba(245, 108, 108, 0.12);
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
  border-right: 1px solid var(--tech-border);
  display: flex;
  flex-direction: column;
  background: transparent;
  overflow: hidden;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--tech-border);
  font-weight: 500;
  background: rgba(var(--tech-bg-rgb), 0.5); /* 与面板背景一致 */
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
  margin-bottom: 24px;
}

.group-title {
  font-size: 11px;
  color: var(--tech-cyan);
  padding: 8px 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.2px;
  text-shadow: 0 0 8px rgba(64, 158, 255, 0.35);
}

/* 历史项目 - 科技风毛玻璃卡片 */
.history-item {
  position: relative;
  padding: 12px 16px 12px 20px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--tech-card);
  border: 1px solid var(--tech-border);
  border-radius: 10px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  min-height: 48px;
  box-shadow: 0 2px 8px var(--tech-shadow), inset 0 1px 0 rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(6px);
  overflow: hidden;
}

.history-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 12%;
  bottom: 12%;
  width: 3px;
  border-radius: 0 2px 2px 0;
  background: linear-gradient(180deg, var(--tech-cyan), var(--tech-blue));
  opacity: 0.5;
  transition: opacity 0.2s ease, box-shadow 0.2s ease;
}

.history-item:hover {
  background: rgba(64, 158, 255, 0.12);
  border-color: var(--tech-border-hover);
  box-shadow: 0 6px 20px rgba(64, 158, 255, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.08);
  transform: translateY(-1px);
}

.history-item:hover::before {
  opacity: 1;
  box-shadow: 0 0 10px var(--tech-cyan);
}

/* 激活状态（当前选中的对话） */
.history-item.active {
  background: rgba(64, 158, 255, 0.18);
  border-color: var(--tech-cyan);
  color: var(--tech-text);
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.35), 0 0 20px rgba(64, 158, 255, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.history-item.active::before {
  opacity: 1;
  background: linear-gradient(180deg, var(--tech-cyan), var(--tech-purple));
  box-shadow: 0 0 14px var(--tech-cyan);
}

.history-item.active:hover {
  background: rgba(64, 158, 255, 0.22);
}

/* 批量选择模式下的样式 */
.history-item.selected {
  background: rgba(64, 158, 255, 0.22);
  border-color: var(--tech-blue);
}

.history-item.selected:hover {
  background: rgba(38, 70, 128, 0.95);
}

.item-title {
  font-size: 13px;
  color: var(--tech-text);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  flex: 1;
  min-width: 0;
  line-height: 1.4;
  word-break: break-all;
  font-weight: 500;
  letter-spacing: 0.2px;
}

.history-item:hover .item-title {
  color: var(--tech-text);
}

.item-time {
  font-size: 11px;
  color: var(--tech-text-dim);
  flex-shrink: 0;
}

.history-item.active .item-time {
  color: rgba(255, 255, 255, 0.8);
}

.history-item.selected .item-time {
  color: #79bbff;
}

/* 删除按钮 - 常显 */
.delete-btn {
  opacity: 1;
  transition: all 0.2s ease;
  padding: 5px 8px;
  flex-shrink: 0;
  color: #ff6b6b !important;
  background: rgba(255, 107, 107, 0.08);
  border: 1px solid rgba(255, 107, 107, 0.25);
  border-radius: 6px;
}

.history-item:hover .delete-btn {
  color: #ff9e9e !important;
  background: rgba(255, 107, 107, 0.18);
  border-color: rgba(255, 107, 107, 0.5);
  box-shadow: 0 0 10px rgba(255, 107, 107, 0.25);
}

/* 激活状态下的删除按钮 */
.history-item.active .delete-btn {
  background: rgba(255, 107, 107, 0.18);
  border-color: rgba(255, 107, 107, 0.5);
}

.history-item.active .delete-btn:hover {
  background: rgba(255, 107, 107, 0.28);
}

.delete-btn:hover {
  background: rgba(255, 107, 107, 0.25) !important;
}

/* 复选框样式 - 深色背景适配 */
.item-checkbox {
  flex-shrink: 0;
  margin-right: 4px;
}

.history-item .el-checkbox__inner {
  width: 16px !important;
  height: 16px !important;
  border-color: var(--tech-border-hover) !important;
  border-width: 1px !important;
  background: rgba(0, 0, 0, 0.25);
}

.history-item .el-checkbox__inner:hover {
  border-color: var(--tech-cyan) !important;
}

.history-item.active .el-checkbox__inner,
.history-item.selected .el-checkbox__inner {
  background-color: var(--tech-blue) !important;
  border-color: var(--tech-blue) !important;
}

.history-item .el-checkbox__input {
  padding: 4px;
  margin: -4px;
}

.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
  min-height: 0;
  background: transparent;
}

.message-list::-webkit-scrollbar {
  width: 6px;
}
.message-list::-webkit-scrollbar-track {
  background: transparent;
}
.message-list::-webkit-scrollbar-thumb {
  background: var(--tech-border);
  border-radius: 3px;
}
.message-list::-webkit-scrollbar-thumb:hover {
  background: rgba(64, 158, 255, 0.5);
}

.welcome-message {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 200px;
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

/* 日常对话模式 - 蓝紫渐变 */
.welcome-icon.icon-chat {
  background: linear-gradient(135deg, var(--tech-cyan) 0%, #667eea 50%, var(--tech-purple) 100%);
  box-shadow: 0 0 32px rgba(64, 158, 255, 0.35), 0 8px 24px rgba(102, 126, 234, 0.3);
}

.welcome-icon.icon-chat .el-icon {
  color: var(--tech-text);
}

/* 知识库问答模式 - 粉橙渐变 */
.welcome-icon.icon-knowledge {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 50%, #ff8c42 100%);
  box-shadow: 0 0 32px rgba(245, 87, 108, 0.3), 0 8px 24px rgba(245, 87, 108, 0.25);
}

.welcome-icon.icon-knowledge .el-icon {
  color: var(--tech-text);
}

.welcome-content h3 {
  font-size: 24px;
  font-weight: 600;
  color: var(--tech-text);
  margin-bottom: 12px;
  text-shadow: 0 0 16px rgba(64, 158, 255, 0.25);
}

.welcome-content p {
  font-size: 14px;
  color: var(--tech-text-dim);
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
  background: linear-gradient(135deg, var(--tech-cyan) 0%, #667eea 50%, var(--tech-purple) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 18px rgba(64, 158, 255, 0.35), 0 4px 12px rgba(102, 126, 234, 0.3);
  transition: all 0.3s ease;
}

.avatar-ai .el-icon {
  color: var(--tech-text);
}

.avatar-ai:hover {
  transform: scale(1.1);
  box-shadow: 0 0 28px rgba(64, 158, 255, 0.5), 0 6px 18px rgba(102, 126, 234, 0.4);
}

/* 用户头像 - 粉橙渐变 */
.avatar-user {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 50%, #ff8c42 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  box-shadow: 0 0 18px rgba(245, 87, 108, 0.3), 0 4px 12px rgba(245, 87, 108, 0.25);
  transition: all 0.3s ease;
}

.avatar-user:hover {
  transform: scale(1.1);
  box-shadow: 0 0 28px rgba(245, 87, 108, 0.45), 0 6px 18px rgba(245, 87, 108, 0.35);
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
  background: var(--tech-card);
  border: 1px solid var(--tech-border);
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 2px 10px var(--tech-shadow);
}

/* 深度思考模式：答案占位提示 */
.answer-placeholder {
  padding: 12px 16px;
  margin: 12px 0;
  background: var(--tech-card);
  border: 1px dashed var(--tech-border);
  border-radius: 12px;
  color: var(--tech-text-dim);
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  box-shadow: 0 2px 10px var(--tech-shadow);
}

.answer-placeholder .is-loading {
  animation: rotating 1.5s linear infinite;
}

.thinking-dots {
  display: flex;
  gap: 4px;
}

.thinking-dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--tech-cyan);
  box-shadow: 0 0 8px var(--tech-cyan);
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
  color: var(--tech-text);
  font-weight: 500;
}

/* 思考中的计时器 */
.thinking-timer {
  font-size: 12px;
  color: var(--tech-text-dim);
  margin-left: 8px;
  font-variant-numeric: tabular-nums;
  font-family: 'SF Mono', 'JetBrains Mono', 'Consolas', monospace;
}

/* 思考过程步骤面板 —— 固定高度、内部滚动、终端风格 */
.thinking-steps-panel {
  margin-top: 10px;
  padding: 12px 14px;
  background: linear-gradient(180deg, rgba(13, 24, 41, 0.95), rgba(8, 15, 28, 0.98));
  border-radius: 10px;
  border: 1px solid rgba(64, 158, 255, 0.35);
  border-left: 3px solid var(--tech-blue);
  max-height: 180px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.6;
  color: #a8c5ff;
  box-shadow: inset 0 0 20px rgba(64, 158, 255, 0.08), 0 4px 16px var(--tech-shadow);
}

/* 思考步骤面板滚动条 */
.thinking-steps-panel::-webkit-scrollbar {
  width: 4px;
}

.thinking-steps-panel::-webkit-scrollbar-track {
  background: rgba(64, 158, 255, 0.08);
  border-radius: 2px;
}

.thinking-steps-panel::-webkit-scrollbar-thumb {
  background: rgba(64, 158, 255, 0.45);
  border-radius: 2px;
}

.thinking-steps-panel::-webkit-scrollbar-thumb:hover {
  background: rgba(64, 158, 255, 0.65);
}

.thinking-step-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 5px 0;
  font-size: 13px;
  color: var(--tech-text-dim);
  transition: color 0.3s;
}

.thinking-step-item.step-active {
  color: var(--tech-text);
  font-weight: 500;
}

.thinking-step-item.step-completed {
  color: #95d475;
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
  color: #95d475;
  font-weight: bold;
}

.step-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid var(--tech-cyan);
  border-top-color: transparent;
  border-radius: 50%;
  animation: step-spin 0.8s linear infinite;
  box-shadow: 0 0 6px var(--tech-cyan);
}

@keyframes step-spin {
  to { transform: rotate(360deg); }
}

.step-text {
  line-height: 1.5;
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
  border-bottom: 1px solid var(--tech-border);
}

.thinking-panel-title {
  font-size: 14px;
  font-weight: 700;
  color: #66b1ff;
  letter-spacing: 0.5px;
  text-shadow: 0 0 10px rgba(64, 158, 255, 0.25);
}

.thinking-panel-timer {
  font-size: 12px;
  color: var(--tech-text-dim);
  font-family: 'SF Mono', 'JetBrains Mono', 'Consolas', monospace;
  font-weight: 600;
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
  color: var(--tech-cyan);
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
  font-size: 14px;
  color: #66b1ff;
  font-weight: 700;
}

.thinking-response-tag {
  margin-left: 8px;
  font-weight: 600;
}

.thinking-history-steps {
  padding: 10px 14px;
  background: var(--tech-card);
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

/* 真实推理文本区域 —— 固定高度、内部滚动 */
.reasoning-text-area {
  position: relative;
  margin-top: 10px;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid rgba(64, 158, 255, 0.25);
  background: rgba(64, 158, 255, 0.05);
}

.reasoning-text-area.reasoning-terminal {
  background: linear-gradient(180deg, rgba(13, 24, 41, 0.95), rgba(8, 15, 28, 0.98));
  border: 1px solid rgba(64, 158, 255, 0.35);
  box-shadow: inset 0 0 20px rgba(64, 158, 255, 0.08), 0 2px 10px rgba(0, 0, 0, 0.1);
}

/* 顶部渐变遮罩，提示内容可滚动 */
.reasoning-text-area.reasoning-terminal::before {
  content: '';
  position: absolute;
  top: 12px;
  left: 12px;
  right: 12px;
  height: 24px;
  background: linear-gradient(180deg, rgba(13, 24, 41, 0.95), transparent);
  border-radius: 6px 6px 0 0;
  pointer-events: none;
  z-index: 2;
}

.reasoning-text-content {
  font-family: 'SF Mono', 'JetBrains Mono', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.75;
  color: #a8c5ff;
  white-space: pre-wrap;
  word-break: break-word;
  height: 180px;
  max-height: 180px;
  overflow-y: auto;
  padding: 8px 10px;
  border-radius: 6px;
  scroll-behavior: smooth;
}

/* 滚动条样式：科技蓝细条 */
.reasoning-text-content::-webkit-scrollbar {
  width: 4px;
}

.reasoning-text-content::-webkit-scrollbar-track {
  background: rgba(64, 158, 255, 0.08);
  border-radius: 2px;
}

.reasoning-text-content::-webkit-scrollbar-thumb {
  background: rgba(64, 158, 255, 0.45);
  border-radius: 2px;
}

.reasoning-text-content::-webkit-scrollbar-thumb:hover {
  background: rgba(64, 158, 255, 0.65);
}

/* 终端光标 */
.reasoning-cursor {
  color: #409eff;
  font-family: 'SF Mono', 'JetBrains Mono', 'Consolas', monospace;
  font-size: 13px;
  animation: blink-cursor 1s step-end infinite;
}

.reasoning-text-content p {
  margin: 6px 0;
}

/* 推理步骤：用卡片式有序列表，步骤号更醒目 */
.reasoning-text-content ol {
  margin: 10px 0;
  padding-left: 0;
  list-style: none;
  counter-reset: reasoning-step;
}

.reasoning-text-content ol li {
  position: relative;
  margin: 10px 0;
  padding: 10px 12px 10px 42px;
  border-radius: 8px;
  background: rgba(64, 158, 255, 0.06);
  border: 1px solid rgba(64, 158, 255, 0.15);
  color: var(--tech-text);
}

.reasoning-text-content ol li::before {
  counter-increment: reasoning-step;
  content: counter(reasoning-step);
  position: absolute;
  left: 10px;
  top: 9px;
  width: 22px;
  height: 22px;
  line-height: 22px;
  border-radius: 50%;
  text-align: center;
  font-size: 12px;
  font-weight: 700;
  color: #ffffff;
  background: linear-gradient(135deg, #409eff, #66b1ff);
  box-shadow: 0 0 8px rgba(64, 158, 255, 0.35);
}

.reasoning-text-content ul {
  margin: 6px 0;
  padding-left: 18px;
}

.reasoning-text-content ul li {
  margin: 3px 0;
  padding: 0;
  background: transparent;
  border: none;
}

.reasoning-text-content ul li::before {
  display: none;
}

.reasoning-text-content strong {
  color: var(--tech-cyan);
  font-weight: 600;
}

/* 推理光标闪烁 */
.reasoning-cursor {
  display: inline-block;
  color: var(--tech-cyan);
  font-size: 14px;
  animation: blink 0.8s infinite;
  margin-left: 2px;
}

/* 推理完成后的样式（不再有光标） */
.reasoning-done {
  border-top-style: solid;
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
  color: var(--tech-text-dim);
  font-family: 'SF Mono', 'JetBrains Mono', 'Consolas', monospace;
  font-variant-numeric: tabular-nums;
}

.timer-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #52c41a;
  box-shadow: 0 0 8px #52c41a;
  animation: timer-pulse 2s infinite;
}

@keyframes timer-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* 流式光标闪烁 */
.streaming-cursor {
  font-size: 18px;
  color: var(--tech-cyan);
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
  background: var(--tech-card);
  color: var(--tech-text);
  line-height: 1.7;
  word-wrap: break-word;
  overflow-wrap: break-word;
  word-break: break-word;
  overflow-x: auto;
  box-shadow: 0 2px 10px var(--tech-shadow);
  border: 1px solid var(--tech-border);
  text-align: left;
}

.user-message .message-text {
  background: linear-gradient(135deg, var(--tech-cyan) 0%, var(--tech-blue) 100%);
  color: var(--tech-user-msg-text);
  box-shadow: 0 0 20px rgba(64, 158, 255, 0.25), 0 4px 12px rgba(64, 158, 255, 0.3);
  border: none;
  font-weight: 500;
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
  color: var(--tech-text-dim);
  background: var(--tech-card);
  border: 1px solid var(--tech-border);
  border-radius: 4px;
  transition: all 0.2s ease;
}

.copy-msg-btn:hover {
  color: var(--tech-cyan);
  border-color: var(--tech-cyan);
  background: var(--tech-card-deep);
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
  color: var(--tech-text);
  line-height: 1.72;
  overflow-wrap: break-word;
  word-break: break-word;
  letter-spacing: -0.005em;
  overflow-x: auto;
}

/* 表格样式（必须用 :deep 穿透 v-html 渲染的 DOM） */
::deep(.ai-message-bubble) table {
  table-layout: auto;
  width: 100%;
  border-collapse: collapse;
  margin: 14px 0;
  font-size: 14px;
  border: 1px solid var(--tech-border);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 10px var(--tech-shadow);
  min-width: 600px;
}
::deep(.ai-message-bubble) td,
::deep(.ai-message-bubble) th {
  word-break: break-word;
  overflow-wrap: break-word;
  vertical-align: middle;
  padding: 14px 16px;
  line-height: 1.6;
  border-right: 1px solid var(--tech-border);
}
::deep(.ai-message-bubble) td:last-child,
::deep(.ai-message-bubble) th:last-child {
  border-right: none;
}
::deep(.ai-message-bubble) th {
  background: rgba(64, 158, 255, 0.18);
  text-align: left;
  font-weight: 700;
  color: var(--tech-text);
  border-bottom: 1px solid rgba(64, 158, 255, 0.3);
  font-size: 14px;
  white-space: nowrap;
  position: sticky;
  top: 0;
  z-index: 1;
  letter-spacing: 0.01em;
}
::deep(.ai-message-bubble) td {
  color: var(--tech-text);
  border-bottom: 1px solid rgba(64, 158, 255, 0.12);
  max-width: 320px;
}
::deep(.ai-message-bubble) tr:last-child td {
  border-bottom: none;
}
::deep(.ai-message-bubble) tr:hover {
  background: rgba(64, 158, 255, 0.08);
}

/* 段落间距 */
.ai-message-bubble p {
  margin: 0 0 12px 0;
  line-height: 1.72;
  color: var(--tech-text);
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
  color: var(--tech-text);
  line-height: 1.35;
  letter-spacing: -0.02em;
}
.ai-message-bubble h1 { font-size: 21px; font-weight: 700; }
.ai-message-bubble h2 { font-size: 18px; }
.ai-message-bubble h3 { font-size: 16px; }
.ai-message-bubble h4 { font-size: 14.5px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--tech-text-dim); }

/* 列表样式 */
.ai-message-bubble ul,
.ai-message-bubble ol { margin: 10px 0; padding-left: 24px; }
.ai-message-bubble li { margin: 6px 0; line-height: 1.7; color: var(--tech-text); }
.ai-message-bubble ul li::marker { color: var(--tech-cyan); }
.ai-message-bubble ol li::marker { color: var(--tech-cyan); font-weight: 500; }

/* 任务列表 */
.ai-message-bubble ul li input[type="checkbox"] {
  margin-right: 8px; vertical-align: middle; width: 16px; height: 16px;
  accent-color: var(--tech-blue);
}

/* 引用块 */
.ai-message-bubble blockquote {
  margin: 14px 0; padding: 13px 18px;
  border-left: 2.5px solid var(--tech-blue); background: rgba(64, 158, 255, 0.08);
  border-radius: 0 6px 6px 0; color: var(--tech-text-dim);
}
.ai-message-bubble blockquote p { margin: 0; color: var(--tech-text-dim); }

/* 代码块 */
::deep(.ai-message-bubble pre) {
  position: relative; margin: 14px 0; padding: 36px 14px 12px 14px;
  background: var(--tech-bg-deep); border-radius: 8px; overflow-x: auto;
  font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 13px; line-height: 1.65; border: 1px solid var(--tech-border);
}
::deep(.ai-message-bubble pre code) {
  background: transparent; padding: 0; border-radius: 0;
  color: var(--tech-text); font-family: inherit; font-size: inherit; line-height: inherit;
}

/* 行内代码 */
.ai-message-bubble code {
  background: rgba(64, 158, 255, 0.12); padding: 2px 7px; border-radius: 5px;
  font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12.5px; color: #ff8c9a; font-weight: 500;
}

.ai-message-bubble .tc-table-wrap {
  margin: 18px 0; border: 1px solid var(--tech-border); border-radius: 12px;
  overflow: hidden; background: rgba(var(--tech-bg-rgb), 0.6);
}
.ai-message-bubble .tc-table-wrap table {
  display: table; width: 100%; border-collapse: collapse; border-spacing: 0;
  font-size: 13.5px; border-radius: 0; box-shadow: none; margin: 0;
  overflow: visible; background: transparent;
}
.ai-message-bubble .tc-table-wrap thead th {
  background: rgba(64, 158, 255, 0.18); padding: 12px 16px; text-align: left;
  font-weight: 650; font-size: 12px; color: var(--tech-text);
  text-transform: uppercase; letter-spacing: 0.04em;
  border-bottom: 1px solid rgba(64, 158, 255, 0.3); white-space: nowrap;
}
.ai-message-bubble .tc-table-wrap tbody td {
  padding: 11px 16px; color: var(--tech-text); line-height: 1.55;
  vertical-align: top; font-size: 13.5px;
}
.ai-message-bubble .tc-table-wrap tbody tr {
  transition: background 0.12s ease; border-bottom: 1px solid rgba(64, 158, 255, 0.12);
}
.ai-message-bubble .tc-table-wrap tbody tr:last-child { border-bottom: none; }
.ai-message-bubble .tc-table-wrap tbody tr:hover { background: rgba(64, 158, 255, 0.08); }
.ai-message-bubble .tc-table-wrap td:first-child {
  font-family: 'JetBrains Mono', 'SF Mono', 'Consolas', monospace;
  font-size: 12.5px; color: var(--tech-text-dim); white-space: nowrap;
}

/* 优先级徽章 */
.ai-message-bubble .tc-priority {
  display: inline-block; padding: 2px 10px; border-radius: 100px;
  font-size: 11.5px; font-weight: 650; text-transform: uppercase;
  letter-spacing: 0.03em; white-space: nowrap;
}
.ai-message-bubble .tc-priority.p0 { background: rgba(255, 107, 107, 0.15); color: #ff6b6b; border: 1px solid rgba(255, 107, 107, 0.4); }
.ai-message-bubble .tc-priority.p1 { background: rgba(255, 140, 66, 0.15); color: #ff8c42; border: 1px solid rgba(255, 140, 66, 0.4); }
.ai-message-bubble .tc-priority.p2 { background: rgba(64, 158, 255, 0.15); color: #79bbff; border: 1px solid rgba(64, 158, 255, 0.4); }
.ai-message-bubble .tc-priority.p3 { background: rgba(149, 212, 117, 0.15); color: #95d475; border: 1px solid rgba(149, 212, 117, 0.4); }

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
  border-top: 1px dashed var(--tech-border);
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
  margin-bottom: 12px;
  padding: 10px 12px;
  background: #f8f9fb;
  border-radius: 6px;
  border-left: 3px solid #409eff;
}

.context-header {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.context-filename {
  font-weight: 500;
  color: #303133;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.context-meta {
  font-size: 12px;
  color: #606266;
}

.context-score {
  font-size: 12px;
  color: #67c23a;
  font-weight: 500;
  margin-left: auto;
}

.context-content {
  margin: 0;
  font-size: 13px;
  color: #4a4f5a;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: #606266;
  line-height: 1.5;
}

/* 文档列表样式 */
.document-list {
  min-height: 200px;
}

.input-area {
  padding: 16px 20px;
  border-top: 1px solid var(--tech-border);
  background: rgba(var(--tech-bg-rgb), 0.55);
  backdrop-filter: blur(10px);
  flex-shrink: 0;
}

.input-toolbar {
  display: flex;
  justify-content: space-between;
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
  background: rgba(var(--tech-bg-rgb), 0.95) !important;
  border: 1px solid rgba(64, 158, 255, 0.25) !important;
  box-shadow: 0 8px 24px var(--tech-shadow) !important;
}

.skill-dropdown-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid var(--tech-border);
  background: rgba(var(--tech-bg-rgb), 0.7);
}

.skill-dropdown-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--tech-text);
}

.skill-dropdown-menu .el-dropdown-menu__item {
  padding: 12px 16px !important;
  line-height: 1.4 !important;
  border-bottom: 1px solid rgba(64, 158, 255, 0.12);
}

.skill-dropdown-menu .el-dropdown-menu__item:last-child {
  border-bottom: none;
}

.skill-dropdown-menu .el-dropdown-menu__item:hover {
  background: rgba(64, 158, 255, 0.15) !important;
}

.skill-dropdown-menu .el-dropdown-menu__item.is-active {
  background: rgba(64, 158, 255, 0.2) !important;
  color: var(--tech-cyan) !important;
}

.skill-dropdown-item {
  width: 280px;
}

.skill-dropdown-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--tech-text);
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
  color: var(--tech-text-dim);
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
  box-shadow: 0 2px 10px var(--tech-shadow);
}

.mode-switcher .el-button {
  padding: 8px 16px;
  font-size: 13px;
  transition: all 0.3s ease;
  background: rgba(var(--tech-bg-rgb), 0.7);
  color: var(--tech-text);
  border-color: rgba(64, 158, 255, 0.25);
}

.mode-switcher .el-button--primary {
  background: linear-gradient(135deg, var(--tech-cyan) 0%, var(--tech-blue) 100%);
  border-color: transparent;
  color: var(--tech-user-msg-text);
  font-weight: 600;
}

/* 新对话按钮 - 科技渐变 */
.new-chat-btn-flat {
  background: linear-gradient(135deg, var(--tech-cyan) 0%, #667eea 50%, var(--tech-purple) 100%);
  color: var(--tech-text);
  border: none;
  border-radius: 20px;
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 0 16px rgba(64, 158, 255, 0.25);
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
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.35), transparent);
  transition: left 0.5s ease;
}

.new-chat-btn-flat:hover::before {
  left: 100%;
}

.new-chat-btn-flat:hover {
  transform: translateY(-2px);
  box-shadow: 0 0 24px rgba(64, 158, 255, 0.4);
}

.new-chat-btn-flat:active {
  transform: translateY(0) scale(0.98);
  box-shadow: 0 0 12px rgba(64, 158, 255, 0.25);
}

.new-chat-btn-flat .el-icon {
  margin-right: 4px;
}

/* 深度思考模式切换按钮 */
.reasoning-toggle-btn {
  border-radius: 20px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.3s ease;
  background: rgba(64, 158, 255, 0.16);
  color: #66b1ff;
  border-color: rgba(64, 158, 255, 0.6);
}

.reasoning-toggle-btn:hover {
  background: rgba(64, 158, 255, 0.28);
  color: #8cc5ff;
  border-color: rgba(64, 158, 255, 0.85);
}

.reasoning-toggle-btn.is-reasoning {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 50%, #ff8c42 100%);
  border-color: transparent;
  color: #ffffff;
  font-weight: 700;
  box-shadow: 0 0 18px rgba(245, 87, 108, 0.4);
}

.reasoning-toggle-btn.is-reasoning:hover {
  transform: translateY(-1px);
  box-shadow: 0 0 24px rgba(245, 87, 108, 0.4);
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
  background: rgba(var(--tech-bg-rgb), 0.7);
  border: 1px solid var(--tech-border);
  border-radius: 12px;
  padding: 12px 14px;
  box-shadow: 0 2px 12px var(--tech-shadow);
}

.chat-input-wrapper .el-textarea__inner {
  border: none;
  box-shadow: none;
  padding: 0;
  resize: none;
  font-size: 14px;
  line-height: 1.6;
  background: transparent;
  color: var(--tech-text);
}

.chat-input-wrapper .el-textarea__inner::placeholder {
  color: var(--tech-text-dim);
}

/* 图片预览：在输入框内部上方，小标签形式 */
.image-preview-area {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--tech-border);
}
.image-preview-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: rgba(64, 158, 255, 0.12);
  border-radius: 6px;
  font-size: 12px;
  color: var(--tech-text);
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
  color: var(--tech-text-dim);
  transition: color 0.15s;
}
.image-tag-close:hover {
  color: #ff6b6b;
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
  color: var(--tech-text-dim);
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
  border: 1px solid var(--tech-border);
}

/* 代码块工具栏样式（动态插入的DOM元素） */
::deep(.ai-message-bubble pre .code-block-toolbar) {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: rgba(64, 158, 255, 0.12);
  border-radius: 8px 8px 0 0;
  border-bottom: 1px solid var(--tech-border);
  z-index: 10;
  box-sizing: border-box;
  height: 32px;
}

::deep(.ai-message-bubble .toolbar-lang) {
  color: var(--tech-cyan);
  font-size: 12px;
  font-family: 'JetBrains Mono', 'SF Mono', 'Consolas', monospace;
  text-transform: uppercase;
  user-select: none;
  font-weight: 600;
  letter-spacing: 0.5px;
}

/* 按钮组容器 */
::deep(.ai-message-bubble .toolbar-btn-group) {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 科技风代码块工具栏按钮 */
::deep(.ai-message-bubble .toolbar-btn) {
  background: transparent;
  border: none;
  color: var(--tech-text-dim);
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

::deep(.ai-message-bubble .toolbar-btn:hover) {
  background: rgba(64, 158, 255, 0.18);
  color: var(--tech-cyan);
}

::deep(.ai-message-bubble .toolbar-btn:active) {
  transform: scale(0.92);
}

/* 复制按钮 */
::deep(.ai-message-bubble .toolbar-btn-copy:hover) {
  color: #95d475;
}

/* 全屏按钮 */
::deep(.ai-message-bubble .toolbar-btn-zoom:hover) {
  color: var(--tech-cyan);
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
  color: var(--tech-text);
}

/* 工作流进度面板 */
.workflow-progress-panel {
  background: var(--tech-card);
  border: 1px solid var(--tech-border);
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 24px;
  box-shadow: 0 2px 12px var(--tech-shadow);
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
  color: var(--tech-text-dim);
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
  color: var(--tech-text-dim);
  line-height: 1.5;
  max-height: 120px;
  overflow-y: auto;
  background: rgba(var(--tech-bg-rgb), 0.05);
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
  background: linear-gradient(135deg, var(--tech-card-deep) 0%, rgba(64, 158, 255, 0.08) 100%);
  border-radius: 8px;
  border: 1px solid var(--tech-border-hover);
}

.wf-result-text {
  font-size: 14px;
  line-height: 1.7;
  color: var(--tech-text);
}
</style>

<style>
/* ================= 主题变量 ================= */
:root {
  --tech-bg: #f5f7fa;
  --tech-bg-deep: #e4e7ed;
  --tech-bg-rgb: 245, 247, 250;
  --tech-card: #ffffff;
  --tech-card-solid: #ffffff;
  --tech-card-deep: #f5f7fa;
  --tech-border: #dcdfe6;
  --tech-border-hover: #409eff;
  --tech-text: #303133;
  --tech-text-dim: #606266;
  --tech-cyan: #1677ff;
  --tech-blue: #409eff;
  --tech-purple: #a855f7;
  --tech-user-msg-text: #ffffff;
  --tech-shadow: rgba(0, 0, 0, 0.08);
}

html.dark {
  --tech-bg: #0b1220;
  --tech-bg-deep: #070c16;
  --tech-bg-rgb: 11, 18, 32;
  --tech-card: rgba(24, 38, 62, 0.95);
  --tech-card-solid: #16233a;
  --tech-card-deep: #0d1525;
  --tech-border: rgba(64, 158, 255, 0.45);
  --tech-border-hover: rgba(64, 158, 255, 0.85);
  --tech-text: #c9d8f0;
  --tech-text-dim: #9fb3d8;
  --tech-cyan: #00f2ff;
  --tech-blue: #409eff;
  --tech-purple: #a855f7;
  --tech-user-msg-text: #0b1220;
  --tech-shadow: rgba(0, 0, 0, 0.45);
}

html.dark .el-button--default {
  --el-button-bg-color: rgba(18, 28, 48, 0.78);
  --el-button-text-color: #c9d8f0;
  --el-button-border-color: rgba(64, 158, 255, 0.35);
}
html.dark .el-button--default:hover {
  --el-button-hover-bg-color: rgba(26, 42, 72, 0.88);
  --el-button-hover-text-color: #00f2ff;
  --el-button-hover-border-color: rgba(64, 158, 255, 0.5);
}
html.dark .el-button--primary {
  --el-button-bg-color: #409eff;
  --el-button-border-color: #409eff;
  --el-button-text-color: #0b1220;
}
html.dark .el-button--primary:hover {
  --el-button-hover-bg-color: #66b1ff;
  --el-button-hover-border-color: #66b1ff;
}
html.dark .el-input__wrapper {
  background-color: rgba(18, 28, 48, 0.78) !important;
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.35) inset !important;
}
html.dark .el-input__inner {
  color: #c9d8f0 !important;
}
html.dark .el-textarea__inner {
  background-color: transparent !important;
  color: #c9d8f0 !important;
}
html.dark .el-dropdown-menu {
  background-color: #121c30 !important;
  border-color: rgba(64, 158, 255, 0.35) !important;
}
html.dark .el-dropdown-menu__item {
  color: #c9d8f0 !important;
}
html.dark .el-dropdown-menu__item:hover {
  background-color: rgba(0, 242, 255, 0.1) !important;
  color: #00f2ff !important;
}
html.dark .el-checkbox__label {
  color: #e6f0ff !important;
}
html.dark .el-checkbox__inner {
  background-color: rgba(255, 255, 255, 0.92) !important;
  border-color: rgba(64, 158, 255, 0.9) !important;
  border-width: 1.5px !important;
}
html.dark .el-checkbox__inner::after {
  border-color: #0b1220 !important;
}
html.dark .el-checkbox__input.is-checked .el-checkbox__inner {
  background-color: #409eff !important;
  border-color: #66b1ff !important;
  box-shadow: 0 0 10px rgba(64, 158, 255, 0.6) !important;
}
html.dark .el-checkbox__input.is-checked .el-checkbox__inner::after {
  border-color: #ffffff !important;
}
html.dark .el-checkbox__input:hover .el-checkbox__inner {
  border-color: #00f2ff !important;
}
html.dark .el-tag {
  background-color: rgba(64, 158, 255, 0.15) !important;
  border-color: rgba(64, 158, 255, 0.35) !important;
  color: #c9d8f0 !important;
}
html.dark .el-tag--success {
  background-color: rgba(103, 194, 58, 0.15) !important;
  border-color: rgba(103, 194, 58, 0.35) !important;
  color: #95d475 !important;
}
html.dark .el-empty__description {
  color: #7a8caf !important;
}

/* 深色模式下增强思考区域和复制按钮可读性 */
html.dark .message-thinking-collapse .el-collapse-item__header {
  background: rgba(64, 158, 255, 0.12) !important;
  border-radius: 6px;
  padding: 0 10px;
  color: #00f2ff !important;
}
html.dark .message-thinking-collapse .el-collapse-item__header:hover {
  background: rgba(64, 158, 255, 0.2) !important;
}
html.dark .thinking-history-steps {
  background: rgba(11, 18, 32, 0.85);
  border-left-color: #00f2ff;
}
html.dark .thinking-step-item {
  color: #9fb3d8;
}
html.dark .thinking-steps-panel {
  background: linear-gradient(180deg, rgba(13, 24, 41, 0.95), rgba(8, 15, 28, 0.98));
  border-color: rgba(64, 158, 255, 0.5);
}
html.dark .reasoning-text-content {
  color: #a8c5ff;
}
html.dark .copy-msg-btn {
  color: #9fb3d8;
  background: rgba(22, 35, 58, 0.8);
  border-color: rgba(64, 158, 255, 0.4);
}
html.dark .copy-msg-btn:hover {
  color: #00f2ff;
  border-color: #00f2ff;
  background: rgba(22, 35, 58, 1);
}

/* ================= 记忆管理面板 ================= */
.memory-manage { padding: 4px 0; }
.memory-manage-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.memory-manage-count { color: var(--tech-text-dim); font-size: 13px; }
.memory-loading { text-align: center; color: var(--tech-text-dim); padding: 40px 0; }
.memory-loading .is-loading { animation: rotating 1.5s linear infinite; margin-right: 6px; }
@keyframes rotating { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.memory-empty { padding: 20px 0; }
.memory-groups { display: flex; flex-direction: column; gap: 20px; }
.memory-group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--tech-border);
}
.memory-group-title { font-weight: 600; color: var(--tech-text); }
.memory-group-count {
  font-size: 12px;
  color: var(--tech-text-dim);
  background: var(--tech-card-deep);
  border-radius: 10px;
  padding: 1px 8px;
}
.memory-group-header .el-button { margin-left: auto; }
.memory-item {
  background: var(--tech-card);
  border: 1px solid var(--tech-border);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 10px;
  transition: border-color 0.2s ease;
}
.memory-item:hover { border-color: var(--tech-border-hover); }
.memory-item-content {
  color: var(--tech-text);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.memory-item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}
.memory-item-time { font-size: 12px; color: var(--tech-text-dim); margin-left: auto; }
.memory-item-meta .el-button { margin-left: auto; }
.memory-item-meta .el-button + .el-button { margin-left: 4px; }
</style>
