<template>
  <aside class="history-panel" aria-label="对话历史侧栏">
    <div class="history-header">
      <div class="header-left">
        <el-checkbox
          v-if="hasHistory"
          :model-value="allSelected"
          @change="$emit('toggle-select-all', $event)"
          size="small"
          aria-label="全选历史记录"
        >
          全选
        </el-checkbox>
        <el-button
          v-if="selectedCount > 0"
          size="small"
          type="danger"
          @click="$emit('batch-delete')"
          style="margin-left: 8px;"
          aria-label="批量删除选中记录"
        >
          批量删除 ({{ selectedCount }})
        </el-button>
      </div>
      <div class="header-right">
        <span class="history-mode-badge" :class="'badge-' + mode">
          {{ modeLabel }}
        </span>
      </div>
    </div>

    <div
      class="history-list"
      v-loading="loading"
      aria-busy="loading"
      aria-label="历史对话列表"
    >
      <!-- 骨架屏加载态 -->
      <div v-if="loading" class="empty-history">
        <div class="skeleton-list" role="status" aria-label="加载历史记录">
          <div class="skeleton-item" v-for="n in 3" :key="n">
            <span class="skeleton-line"></span>
          </div>
        </div>
      </div>

      <!-- 各模式专属空状态 -->
      <div v-else-if="!hasHistory" class="empty-history">
        <div class="empty-mode-content">
          <el-icon :size="36" class="empty-mode-icon">
            <ChatDotRound v-if="mode === 'chat'" />
            <Connection v-else-if="mode === 'workflow'" />
            <Reading v-else />
          </el-icon>
          <p class="empty-mode-text">{{ emptyTitle }}</p>
          <p class="empty-mode-hint">{{ emptyHint }}</p>
        </div>
      </div>

      <!-- 错误状态 -->
      <div v-else-if="error" class="empty-history">
        <div class="error-state">
          <el-icon :size="28" style="color: var(--el-color-danger)"><WarningFilled /></el-icon>
          <p class="error-text">加载失败</p>
          <el-button size="small" @click="$emit('retry')">重试</el-button>
        </div>
      </div>

      <!-- 历史分组列表 -->
      <div v-for="group in groups" :key="group.date" class="history-group">
        <div class="group-title">{{ group.label }}</div>
        <div
          v-for="msg in group.messages"
          :key="msg.id"
          class="history-item"
          role="button"
          tabindex="0"
          :class="{
            active: activeId === msg.id,
            selected: selectedIds.has(msg.id),
          }"
          @click="$emit('select-message', msg)"
          @keydown.enter.prevent="$emit('select-message', msg)"
          @keydown.space.prevent="$emit('select-message', msg)"
          :title="msg.question"
          :aria-label="'会话: ' + msg.question"
        >
          <el-checkbox
            :model-value="selectedIds.has(msg.id)"
            @update:model-value="(val) => $emit('toggle-select', msg.id)"
            @click.stop
            class="item-checkbox"
            :aria-label="'选择: ' + msg.question"
          />
          <div class="item-title">{{ msg.question }}</div>
          <el-button
            size="small"
            type="danger"
            link
            @click.stop="$emit('delete-message', msg.id)"
            class="delete-btn"
            aria-label="删除这条记录"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import {
  ChatDotRound,
  Connection,
  Reading,
  Delete,
  WarningFilled,
} from '@element-plus/icons-vue'

const props = defineProps({
  groups: { type: Array, default: () => [] },
  activeId: { type: [Number, String], default: null },
  selectedIds: { type: Set, default: () => new Set() },
  loading: { type: Boolean, default: false },
  error: { type: Boolean, default: false },
  mode: { type: String, default: 'knowledge' },
})

defineEmits([
  'select-message',
  'toggle-select',
  'toggle-select-all',
  'delete-message',
  'batch-delete',
  'retry',
])

const MODE_LABELS = {
  chat: '日常对话',
  knowledge: '知识库问答',
  workflow: '多Agent工作流',
}

const MODE_EMPTY = {
  chat: { title: '暂无对话记录', hint: '开始一段新对话吧' },
  knowledge: { title: '暂无问答记录', hint: '上传文档后开始知识库问答' },
  workflow: { title: '暂无工作流记录', hint: '输入测试需求，启动多Agent工作流' },
}

const hasHistory = computed(() => props.groups.length > 0)
const selectedCount = computed(() => props.selectedIds?.size || 0)
const modeLabel = computed(() => MODE_LABELS[props.mode] || '知识库问答')
const emptyTitle = computed(() => MODE_EMPTY[props.mode]?.title || '暂无记录')
const emptyHint = computed(() => MODE_EMPTY[props.mode]?.hint || '')

const allSelected = computed(() => {
  const total = props.groups.reduce((sum, g) => sum + g.messages.length, 0)
  return total > 0 && selectedCount.value === total
})
</script>

<style scoped>
.history-panel {
  width: 100%;
  min-width: 0;
  background: transparent;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.history-header {
  padding: 12px 14px;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--el-text-color-primary);
  font-weight: 500;
}

.header-right {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.history-group {
  margin-bottom: 2px;
}

.group-title {
  padding: 6px 14px 4px;
  font-size: 11px;
  color: #303133;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.history-item {
  padding: 10px 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: background 0.15s ease, box-shadow 0.15s ease;
  border-radius: 6px;
  margin: 0 8px 2px;
  border: 1px solid #ebeef5;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}

.history-item:hover {
  background: #f5f7fa;
  box-shadow: 0 2px 4px rgba(0,0,0,0.06);
}

.history-item.active {
  background: #e6f2ff;
  border-color: #a0cfff;
}

.history-item.selected {
  background: #e6f2ff;
  border-color: #b3d8ff;
}

.history-item:focus-visible {
  outline: 2px solid #409eff;
  outline-offset: -2px;
}

.item-checkbox {
  flex-shrink: 0;
}

.item-title {
  flex: 1;
  font-size: 13px;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 500;
}

.delete-btn {
  opacity: 0;
  transition: opacity 0.15s ease;
  flex-shrink: 0;
}

.history-item:hover .delete-btn {
  opacity: 1;
}

/* 空状态 */
.empty-history {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 200px;
}

.empty-mode-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 32px 16px;
  text-align: center;
  background: #fafbfc;
  border-radius: 8px;
  margin: 8px;
  border: 1px dashed #d9dde3;
}

.empty-mode-icon {
  color: #909399;
  margin-bottom: 4px;
  opacity: 0.6;
}

.empty-mode-text {
  font-size: 14px;
  color: #303133;
  margin: 0;
  font-weight: 600;
}

.empty-mode-hint {
  font-size: 12px;
  color: #606266;
  margin: 0;
  line-height: 1.5;
  max-width: 200px;
}

/* 错误状态 */
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 24px 16px;
  text-align: center;
}

.error-text {
  font-size: 13px;
  color: #303133;
  margin: 0;
}

/* 骨架屏 */
.skeleton-list {
  width: 100%;
  padding: 8px 0;
}

.skeleton-item {
  padding: 10px 14px;
}

.skeleton-line {
  display: block;
  height: 14px;
  background: linear-gradient(
    90deg,
    #f5f7fa 25%,
    #e4e7ed 50%,
    #f5f7fa 75%
  );
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

.badge-chat {
  background: #d9ecff;
  color: #337ecc;
  border: 1px solid #b3d8ff;
}

.badge-knowledge {
  background: #d1edc4;
  color: #529b2e;
  border: 1px solid #b3e19d;
}

.badge-workflow {
  background: #faecd8;
  color: #b88230;
  border: 1px solid #f0c78a;
}
</style>
