<template>
  <el-button-group class="mode-switcher" role="tablist" aria-label="问答模式切换">
    <el-button
      v-for="item in modes"
      :key="item.value"
      role="tab"
      :aria-selected="active === item.value"
      :type="active === item.value ? 'primary' : ''"
      size="small"
      @click="$emit('switch', item.value)"
      :aria-label="'切换到' + item.label + '模式'"
    >
      <el-icon aria-hidden="true">
        <component :is="item.icon" />
      </el-icon>
      {{ item.label }}
    </el-button>
  </el-button-group>
</template>

<script setup>
import { ChatDotRound, Reading } from '@element-plus/icons-vue'

defineProps({
  active: { type: String, default: 'knowledge' },
})

defineEmits(['switch'])

const modes = [
  { value: 'chat', label: '日常对话', icon: ChatDotRound },
  { value: 'knowledge', label: '知识库问答', icon: Reading },
]
</script>

<style scoped>
.mode-switcher {
  flex-shrink: 0;
}

.mode-switcher :deep(.el-button) {
  font-size: 12px;
  padding: 5px 10px;
}

.mode-switcher :deep(.el-button .el-icon) {
  margin-right: 3px;
}
</style>
