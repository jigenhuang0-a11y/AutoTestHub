<template>
  <div class="report-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>测试报告列表</span>
          <el-button size="small" @click="loadReports" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <!-- 空状态 -->
      <el-empty v-if="!loading && !reports.length" description="暂无测试报告">
        <el-button type="primary" @click="$router.push('/history')">查看执行历史</el-button>
      </el-empty>

      <!-- 报告列表 -->
      <el-table v-else :data="reports" border stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="title" label="报告标题" min-width="200" />
        <el-table-column prop="execution_name" label="执行名称" min-width="150" />
        <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="viewReport(row)">
              <el-icon><View /></el-icon>
              查看
            </el-button>
            <el-button size="small" type="success" @click="downloadPDF(row)" :loading="downloadingId === row.id">
              <el-icon><Download /></el-icon>
              PDF
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="reports.length > 0"
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 20px; justify-content: flex-end"
        @size-change="loadReports"
        @current-change="loadReports"
      />
    </el-card>

    <!-- 报告详情对话框 -->
    <el-dialog
      v-model="reportDialogVisible"
      :title="currentReport?.title || '报告详情'"
      width="90%"
      top="3vh"
      :close-on-click-modal="false"
    >
      <div v-if="currentReport" class="report-detail">
        <!-- 报告基本信息 -->
        <el-descriptions :column="3" border class="report-info">
          <el-descriptions-item label="执行名称">
            {{ currentReport.execution_name }}
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ formatDate(currentReport.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="报告ID">
            #{{ currentReport.id }}
          </el-descriptions-item>
          <el-descriptions-item label="摘要" :span="3">
            {{ currentReport.summary || '暂无摘要' }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- Allure报告HTML嵌入 -->
        <div v-if="currentReport.report_html" class="report-html-container">
          <div class="html-header">
            <span>Allure报告预览</span>
            <el-button size="small" @click="openInNewWindow">
              <el-icon><FullScreen /></el-icon>
              新窗口打开
            </el-button>
          </div>
          <iframe
            ref="reportFrameRef"
            :srcdoc="currentReport.report_html"
            class="report-iframe"
            sandbox="allow-scripts allow-same-origin"
          ></iframe>
        </div>

        <!-- 无报告内容时的空状态 -->
        <div v-else class="no-report">
          <el-empty description="暂无Allure报告内容">
            <template #image>
              <el-icon :size="100" color="#c0c4cc"><Document /></el-icon>
            </template>
          </el-empty>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { reportAPI } from '@/api'
import { ElMessage } from 'element-plus'
import html2pdf from 'html2pdf.js'
import { Refresh, View, Download, FullScreen, Document } from '@element-plus/icons-vue'

const loading = ref(false)
const downloadingId = ref(null)
const reports = ref([])
const reportDialogVisible = ref(false)
const currentReport = ref(null)
const reportFrameRef = ref(null)

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
})

// 加载报告列表
const loadReports = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
    }
    const response = await reportAPI.list(params)
    reports.value = response.results || response
    pagination.total = response.count || response.length
  } catch (error) {
    console.error('Load reports error:', error)
  } finally {
    loading.value = false
  }
}

// 查看报告
const viewReport = async (report) => {
  try {
    const detail = await reportAPI.get(report.id)
    currentReport.value = detail
    reportDialogVisible.value = true
  } catch (error) {
    console.error('View report error:', error)
  }
}

// 下载PDF报告
const downloadPDF = async (report) => {
  downloadingId.value = report.id
  try {
    // 获取报告详情
    const detail = await reportAPI.get(report.id)

    // 创建临时容器用于生成PDF
    const element = document.createElement('div')
    element.innerHTML = `
      <div style="padding: 20px; font-family: Arial, sans-serif;">
        <h1 style="color: #333; border-bottom: 2px solid #409eff; padding-bottom: 10px;">
          ${detail.title || '测试报告'}
        </h1>
        <div style="margin: 20px 0;">
          <p><strong>执行名称：</strong>${detail.execution_name || 'N/A'}</p>
          <p><strong>创建时间：</strong>${formatDate(detail.created_at)}</p>
          <p><strong>摘要：</strong>${detail.summary || '暂无摘要'}</p>
        </div>
        ${detail.report_html ? detail.report_html : '<p>暂无详细报告内容</p>'}
      </div>
    `
    document.body.appendChild(element)

    // 配置PDF选项
    const opt = {
      margin: [10, 10],
      filename: `${detail.title || 'test-report'}_${new Date().getTime()}.pdf`,
      image: { type: 'jpeg', quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true },
      jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
    }

    // 生成PDF
    await html2pdf().set(opt).from(element).save()

    ElMessage.success('PDF下载成功')
    document.body.removeChild(element)
  } catch (error) {
    console.error('Download PDF error:', error)
    ElMessage.error('PDF下载失败')
  } finally {
    downloadingId.value = null
  }
}

// 在新窗口打开报告
const openInNewWindow = () => {
  if (!currentReport.value?.report_html) return

  const newWindow = window.open('', '_blank')
  if (newWindow) {
    newWindow.document.write(currentReport.value.report_html)
    newWindow.document.close()
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadReports()
})
</script>

<style scoped>
.report-container {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.report-detail {
  max-height: 75vh;
  overflow-y: auto;
}

.report-info {
  margin-bottom: 20px;
}

.report-html-container {
  border: 1px solid #e6e6e6;
  border-radius: 4px;
  overflow: hidden;
}

.html-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background: #f5f7fa;
  border-bottom: 1px solid #e6e6e6;
  font-weight: bold;
}

.report-iframe {
  width: 100%;
  height: 600px;
  border: none;
}

.no-report {
  padding: 50px 0;
  text-align: center;
}
</style>
