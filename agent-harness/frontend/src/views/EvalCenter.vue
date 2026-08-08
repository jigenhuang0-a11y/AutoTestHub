<template>
  <div class="eval-center">
    <div class="page-placeholder">
      <el-icon class="placeholder-icon"><DataAnalysis /></el-icon>
      <h2 class="placeholder-title">全链路评测中心</h2>
      <p class="placeholder-desc">Golden Dataset + Judge LLM + 多维度评分</p>
      <p class="placeholder-sub">评测中心正在建设中，此页面将承载：</p>
      <div class="features-grid">
        <div class="feature-item">
          <el-icon><Collection /></el-icon>
          <span>评测数据集管理</span>
        </div>
        <div class="feature-item">
          <el-icon><Checked /></el-icon>
          <span>多维度 Judge 评分</span>
        </div>
        <div class="feature-item">
          <el-icon><TrendCharts /></el-icon>
          <span>综合评分雷达图</span>
        </div>
        <div class="feature-item">
          <el-icon><Link /></el-icon>
          <span>评测结果下钻 Trace</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { DataAnalysis, Collection, Checked, TrendCharts, Link } from '@element-plus/icons-vue'
</script>

<style scoped>
.eval-center {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1a2d45;
}

.page-placeholder {
  text-align: center;
  max-width: 520px;
  padding: 48px;
}

.placeholder-icon {
  font-size: 64px;
  color: #64748b;
  margin-bottom: 24px;
}

.placeholder-title {
  font-size: 28px;
  font-weight: 700;
  color: #f1f5f9;
  margin-bottom: 12px;
  letter-spacing: 1px;
}

.placeholder-desc {
  font-size: 15px;
  color: #94a3b8;
  margin-bottom: 8px;
}

.placeholder-sub {
  font-size: 13px;
  color: #475569;
  margin-bottom: 32px;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  text-align: left;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: rgba(139, 92, 246, 0.08);
  border: 1px solid rgba(139, 92, 246, 0.15);
  border-radius: 10px;
  color: #c4b5fd;
  font-size: 13px;
}
</style>
