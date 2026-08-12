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
  background:
    radial-gradient(circle at 10% 0%, rgba(64, 158, 255, 0.12) 0%, transparent 35%),
    radial-gradient(circle at 90% 100%, rgba(168, 85, 247, 0.1) 0%, transparent 40%),
    linear-gradient(180deg, var(--tech-bg) 0%, var(--tech-bg-deep) 100%);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  color: var(--tech-text);
  border-right: 1px solid var(--tech-border);
  box-shadow: inset -8px 0 24px var(--tech-shadow);
}

.history-header {
  padding: 14px 16px;
  border-bottom: 1px solid var(--tech-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  background: rgba(var(--tech-bg-rgb), 0.6);
  backdrop-filter: blur(8px);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--tech-text);
  font-weight: 600;
  font-size: 13px;
}

.header-right {
  font-size: 12px;
  font-weight: 600;
  color: var(--tech-cyan);
  letter-spacing: 0.5px;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 0;
}

.history-list::-webkit-scrollbar {
  width: 5px;
}
.history-list::-webkit-scrollbar-track {
  background: transparent;
}
.history-list::-webkit-scrollbar-thumb {
  background: var(--tech-border);
  border-radius: 3px;
}
.history-list::-webkit-scrollbar-thumb:hover {
  background: var(--tech-border-hover);
}

.history-group {
  margin-bottom: 6px;
}

.group-title {
  padding: 8px 16px 6px;
  font-size: 10px;
  color: var(--tech-cyan);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.2px;
  text-shadow: 0 0 8px rgba(64, 158, 255, 0.35);
}

.history-item {
  position: relative;
  padding: 12px 14px 12px 18px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  border-radius: 10px;
  margin: 0 12px 10px;
  border: 1px solid var(--tech-border);
  background: var(--tech-card);
  box-shadow:
    0 2px 8px rgba(0, 0, 0, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(6px);
  overflow: hidden;
}

/* 左侧霓虹指示条 */
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
  box-shadow:
    0 6px 20px rgba(64, 158, 255, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  transform: translateY(-1px);
}

.history-item:hover::before {
  opacity: 1;
  box-shadow: 0 0 10px var(--tech-cyan);
}

.history-item.active {
  background: rgba(64, 158, 255, 0.18);
  border-color: var(--tech-cyan);
  box-shadow:
    0 0 0 1px rgba(64, 158, 255, 0.35),
    0 0 20px rgba(64, 158, 255, 0.15),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.history-item.active::before {
  opacity: 1;
  background: linear-gradient(180deg, var(--tech-cyan), var(--tech-purple));
  box-shadow: 0 0 14px var(--tech-cyan);
}

.history-item.selected {
  background: rgba(64, 158, 255, 0.22);
  border-color: var(--tech-blue);
}

.history-item:focus-visible {
  outline: 1px solid var(--tech-cyan);
  outline-offset: 2px;
}

.item-checkbox {
  flex-shrink: 0;
}

.item-title {
  flex: 1;
  font-size: 13px;
  color: var(--tech-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 500;
  letter-spacing: 0.2px;
}

.history-item:hover .item-title {
  color: var(--tech-text);
}

.delete-btn {
  opacity: 1;
  flex-shrink: 0;
  color: #ff6b6b;
  padding: 5px 8px;
  border-radius: 6px;
  transition: all 0.2s ease;
  background: rgba(255, 107, 107, 0.08);
  border: 1px solid rgba(255, 107, 107, 0.25);
}

.history-item:hover .delete-btn {
  color: #ff9e9e;
  background: rgba(255, 107, 107, 0.18);
  border-color: rgba(255, 107, 107, 0.5);
  box-shadow: 0 0 10px rgba(255, 107, 107, 0.25);
}

.delete-btn .el-icon {
  font-size: 15px;
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
  gap: 10px;
  padding: 36px 18px;
  text-align: center;
  background: rgba(var(--tech-bg-rgb), 0.7);
  border-radius: 12px;
  margin: 12px;
  border: 1px dashed var(--tech-border);
  box-shadow: inset 0 0 24px rgba(64, 158, 255, 0.08);
}

.empty-mode-icon {
  color: var(--tech-cyan);
  margin-bottom: 4px;
  opacity: 0.8;
  filter: drop-shadow(0 0 8px rgba(64, 158, 255, 0.4));
}

.empty-mode-text {
  font-size: 14px;
  color: var(--tech-text);
  margin: 0;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.empty-mode-hint {
  font-size: 12px;
  color: var(--tech-text-dim);
  margin: 0;
  line-height: 1.5;
  max-width: 200px;
}

/* 错误状态 */
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 28px 16px;
  text-align: center;
  color: var(--tech-text);
}

.error-text {
  font-size: 13px;
  color: #f56c6c;
  margin: 0;
}

/* 骨架屏 */
.skeleton-list {
  width: 100%;
  padding: 12px 0;
}

.skeleton-item {
  padding: 12px 16px;
}

.skeleton-line {
  display: block;
  height: 14px;
  background: linear-gradient(
    90deg,
    rgba(64, 158, 255, 0.08) 25%,
    rgba(64, 158, 255, 0.18) 50%,
    rgba(64, 158, 255, 0.08) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.6s ease-in-out infinite;
  border-radius: 6px;
  width: 80%;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 模式徽章 */
.history-mode-badge {
  font-size: 10px;
  padding: 3px 10px;
  border-radius: 20px;
  font-weight: 700;
  white-space: nowrap;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  border: 1px solid;
  background: rgba(0, 0, 0, 0.25);
}

.badge-chat {
  color: #79bbff;
  border-color: rgba(121, 187, 255, 0.5);
  box-shadow: 0 0 10px rgba(121, 187, 255, 0.2);
}

.badge-knowledge {
  color: #95d475;
  border-color: rgba(149, 212, 117, 0.5);
  box-shadow: 0 0 10px rgba(149, 212, 117, 0.2);
}

.badge-workflow {
  color: #eebe77;
  border-color: rgba(238, 190, 119, 0.5);
  box-shadow: 0 0 10px rgba(238, 190, 119, 0.2);
}

/* Element Plus 复选框在深色背景下的颜色覆盖 */
:deep(.el-checkbox__input + .el-checkbox__label) {
  color: #e6f0ff;
  font-weight: 600;
}
:deep(.el-checkbox__inner) {
  background-color: rgba(255, 255, 255, 0.92);
  border-color: rgba(64, 158, 255, 0.9);
  border-width: 1.5px;
}
:deep(.el-checkbox__input.is-checked + .el-checkbox__label) {
  color: var(--tech-cyan);
}
:deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
  background-color: var(--tech-blue);
  border-color: #66b1ff;
  box-shadow: 0 0 10px rgba(64, 158, 255, 0.6);
}
:deep(.el-checkbox__input.is-checked .el-checkbox__inner::after) {
  border-color: #ffffff;
}
:deep(.el-checkbox__input:hover .el-checkbox__inner) {
  border-color: var(--tech-cyan);
}
</style>
