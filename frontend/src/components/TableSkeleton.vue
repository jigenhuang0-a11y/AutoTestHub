<template>
  <div class="table-skeleton">
    <div v-for="i in rows" :key="i" class="skeleton-row">
      <div
        v-for="j in cols"
        :key="j"
        class="skeleton-cell"
        :style="{ width: colWidths[j - 1] || '100px' }"
      >
        <div class="skeleton-placeholder"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  rows: {
    type: Number,
    default: 5,
  },
  cols: {
    type: Number,
    default: 4,
  },
  colWidths: {
    type: Array,
    default: () => [],
  },
})
</script>

<style scoped>
.table-skeleton {
  width: 100%;
}

.skeleton-row {
  display: flex;
  border-bottom: 1px solid #f0f0f0;
  padding: 12px 0;
}

.skeleton-cell {
  padding: 0 12px;
}

.skeleton-placeholder {
  height: 16px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: 4px;
}

@keyframes skeleton-loading {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
