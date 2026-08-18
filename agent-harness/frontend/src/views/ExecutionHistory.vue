<template>
  <div class="execution-history-container">
    <el-card class="glass-card" shadow="never">
      <template #header>
        <div class="page-hero">
          <div class="hero-main">
            <div class="hero-title">
              <div class="hero-icon-wrap">
                <el-icon :size="26"><Histogram /></el-icon>
              </div>
              <div>
                <h2 class="page-title">执行历史</h2>
                <p class="page-desc">查看 API、Web、性能测试的执行记录与结果</p>
              </div>
            </div>
          </div>
          <div class="hero-stats" v-if="executions.length">
            <div class="stat-item">
              <span class="stat-value">{{ stats.total }}</span>
              <span class="stat-label">总记录</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <span class="stat-value running">{{ stats.running }}</span>
              <span class="stat-label">执行中</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <span class="stat-value passed">{{ stats.passed }}</span>
              <span class="stat-label">已通过</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <span class="stat-value failed">{{ stats.failed }}</span>
              <span class="stat-label">已失败</span>
            </div>
          </div>
        </div>
      </template>

      <!-- 搜索筛选区域 -->
      <div class="page-toolbar">
        <el-form :model="filters" inline>
          <el-form-item label="套件名称">
            <el-input
              v-model="filters.search"
              placeholder="搜索套件名称或日志"
              clearable
              style="width: 200px"
              @clear="handleSearch"
              @keyup.enter="handleSearch"
            >
              <template #suffix>
                <el-icon @click="handleSearch" style="cursor:pointer"><Search /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="filters.execType" placeholder="全部" style="width: 130px" clearable @change="handleSearch">
              <el-option label="全部" value="" />
              <el-option label="API 测试" value="api">
                <span style="display:flex;align-items:center;gap:4px"><el-icon color="#409EFF"><Link /></el-icon> API 测试</span>
              </el-option>
              <el-option label="Web 自动化" value="web">
                <span style="display:flex;align-items:center;gap:4px"><el-icon color="#67C23A"><Monitor /></el-icon> Web 自动化</span>
              </el-option>
              <el-option label="性能测试" value="perf">
                <span style="display:flex;align-items:center;gap:4px"><el-icon color="#E6A23C"><Odometer /></el-icon> 性能测试</span>
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="执行时间">
            <el-select v-model="filters.timeRange" style="width: 130px" @change="handleSearch">
              <el-option label="今天" value="today" />
              <el-option label="近7天" value="7days" />
              <el-option label="近30天" value="30days" />
              <el-option label="自定义" value="custom" />
            </el-select>
            <el-date-picker
              v-if="filters.timeRange === 'custom'"
              v-model="filters.dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              style="width: 240px; margin-left: 8px"
              @change="handleSearch"
            />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="filters.status" placeholder="全部" style="width: 120px" clearable @change="handleSearch">
              <el-option label="已完成" value="completed" />
              <el-option label="执行中" value="running" />
              <el-option label="部分通过" value="partial" />
              <el-option label="失败" value="failed" />
            </el-select>
          </el-form-item>
          <el-form-item label="执行人">
            <el-select v-model="filters.started_by" placeholder="全部" style="width: 120px" clearable @change="handleSearch">
              <el-option v-for="user in users" :key="user.id" :label="user.username" :value="user.id" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">查询</el-button>
            <el-button @click="resetFilters">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 执行历史列表 -->
      <div class="page-content" v-loading="loading" element-loading-text="加载中..." element-loading-background="rgba(255,255,255,0.85)">
        <!-- 工具栏：批量操作 -->
        <div v-if="selectedRows.length > 0" style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px">
          <el-button
            type="danger" size="small"
            :disabled="selectedRows.length === 0"
            @click="batchDeleteExecutions"
          >
            批量删除 ({{ selectedRows.length }})
          </el-button>
          <span style="color: #909399; font-size: 12px">
            已选择 {{ selectedRows.length }} 条记录
          </span>
        </div>

        <!-- 空状态 -->
        <div v-if="!loading && !executions.length" class="empty-state-glass">
          <div class="empty-icon-wrap">
            <el-icon :size="42"><Histogram /></el-icon>
          </div>
          <h3 class="empty-title">暂无执行记录</h3>
          <p class="empty-desc">执行接口测试、Web 自动化或性能测试后，结果将展示在这里</p>
        </div>

        <!-- 表格 -->
        <template v-if="executions.length">
          <div class="table-wrapper">
            <el-table
              :data="executions"
              stripe
              border
              table-layout="auto"
              class="data-table"
              style="min-width: 1400px"
              @row-click="handleRowClick"
              @selection-change="handleSelectionChange"
            >
        <el-table-column type="selection" width="45" />
        <el-table-column prop="id" label="ID" width="160" align="center" show-overflow-tooltip />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.__type === 'web'" size="small" type="success">
              <el-icon style="margin-right:3px;vertical-align:-1px"><Monitor /></el-icon> Web
            </el-tag>
            <el-tag v-else-if="row.__type === 'perf'" size="small" type="warning">
              <el-icon style="margin-right:3px;vertical-align:-1px"><Odometer /></el-icon> 性能
            </el-tag>
            <el-tag v-else size="small">
              <el-icon style="margin-right:3px;vertical-align:-1px"><Link /></el-icon> API
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="执行名称" min-width="160">
          <template #default="{ row }">
            <el-link type="primary" @click.stop="viewDetail(row.id)">
              {{ row.name || `执行 #${row.id}` }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="关联用例/套件" min-width="110">
          <template #default="{ row }">
            <template v-if="row.__type === 'web'">
              <el-link v-if="row.test_case_title" type="primary" @click.stop="goToWebTestCase(row)">
                {{ row.test_case_title }}
              </el-link>
              <span v-else style="color:#999">-</span>
            </template>
            <template v-else-if="row.__type === 'perf'">
              <span style="font-size:12px;color:#606266">{{ row.test_case_name || '-' }}</span>
            </template>
            <template v-else>
              <el-link
                v-if="row.suite_id && row.suite_name"
                type="primary"
                @click.stop="goToSuite(row.suite_id)"
              >
                {{ row.suite_name }}
              </el-link>
              <span v-else-if="row.trigger_type === 'manual_case'" style="color: #999">单用例执行</span>
              <span v-else style="color: #999">-</span>
            </template>
          </template>
        </el-table-column>
        <el-table-column label="触发方式" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="getTriggerTypeColor(row.trigger_type)">
              {{ row.trigger_type_display || row.trigger_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="环境" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.__type === 'web'" size="small" type="info">浏览器</el-tag>
            <el-tag v-else-if="row.__type === 'perf'" size="small" type="info">压测</el-tag>
            <el-tag v-else-if="row.environment" size="small" :type="getEnvType(row.environment)">
              {{ row.environment_display || row.environment }}
            </el-tag>
            <span v-else style="color:#c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column label="执行人" width="100">
          <template #default="{ row }">
            {{ row.__type === 'web' ? (row.executed_by_username || '-') : (row.started_by_name || '-') }}
          </template>
        </el-table-column>
        <el-table-column label="结果" min-width="190">
          <template #default="{ row }">
            <!-- Web 自动化结果 -->
            <template v-if="row.__type === 'web'">
              <el-tag v-if="row.status === 'running'" size="small" type="info" effect="plain">
                <el-icon class="is-loading" style="margin-right:4px;vertical-align:-2px"><Loading /></el-icon>
                执行中
              </el-tag>
              <template v-if="row.status !== 'running'">
                <el-tag size="small" :type="row.status === 'passed' ? 'success' : 'danger'" effect="plain">
                  {{ row.status === 'passed' ? '通过' : '失败' }}
                </el-tag>
              </template>
              <el-tag v-if="row.screenshot_url" size="small" type="info" effect="plain" style="margin-left:4px">有截图</el-tag>
            </template>
            <!-- 性能测试结果 -->
            <template v-else-if="row.__type === 'perf'">
              <template v-if="row.status === 'running' || row.status === 'pending'">
                <el-tag size="small" type="info" effect="plain">
                  <el-icon class="is-loading" style="margin-right:4px;vertical-align:-2px"><Loading /></el-icon>
                  执行中
                </el-tag>
              </template>
              <div v-else class="result-badges">
                <el-tag size="small" effect="plain">QPS {{ row.requests_per_second || 0 }}</el-tag>
                <el-tag size="small" type="warning" effect="plain">P95 {{ row.p95_response_time || 0 }}ms</el-tag>
                <el-tag size="small" :type="(row.failure_rate || 0) > 0.01 ? 'danger' : 'success'" effect="plain">
                  失败{{ ((row.failure_rate || 0) * 100).toFixed(1) }}%
                </el-tag>
                <el-tag
                  v-if="row.ai_score != null"
                  size="small"
                  :type="row.ai_score >= 85 ? 'success' : row.ai_score >= 70 ? 'warning' : 'danger'"
                  effect="dark"
                >
                  AI {{ row.ai_score }}分
                </el-tag>
              </div>
            </template>
            <!-- API 测试结果 -->
            <template v-else>
              <template v-if="row.status === 'running' || row.status === 'pending'">
                <el-tag size="small" type="info" effect="plain">
                  <el-icon class="is-loading" style="margin-right:4px;vertical-align:-2px"><Loading /></el-icon>
                  执行中
                </el-tag>
              </template>
              <div v-else class="result-badges">
                <el-tag size="small" effect="plain">总 {{ row.total_cases || 0 }}</el-tag>
                <el-tag size="small" type="success" effect="plain">{{ row.passed_cases || 0 }}</el-tag>
                <el-tag size="small" type="danger" effect="plain">{{ row.failed_cases || 0 }}</el-tag>
                <el-tag size="small" type="warning" effect="plain">{{ row.skipped_cases || 0 }}</el-tag>
              </div>
            </template>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ row.status_display || getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="执行时间" width="150">
          <template #default="{ row }">{{ formatDate(row.__type === 'web' ? row.executed_at : row.started_at) }}</template>
        </el-table-column>
        <el-table-column label="耗时" width="90">
          <template #default="{ row }">{{ row.duration ? row.duration + 's' : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click.stop="viewDetail(row)">
              {{ row.__type === 'web' ? '详情' : '详情' }}
            </el-button>
            <el-button size="small" link type="warning" :loading="rerunningIds.has(row.id)" @click.stop="handleRerun(row)">重跑</el-button>
            <el-button size="small" link type="danger" @click.stop="deleteExecution(row)">删除</el-button>
          </template>
        </el-table-column>
            </el-table>
          </div>

          <!-- 分页 -->
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :total="pagination.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next, jumper"
            class="page-pagination"
            @current-change="loadExecutions"
            @size-change="onSizeChange"
          />
        </template>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onActivated, onUnmounted, onDeactivated } from 'vue'
import { useRouter } from 'vue-router'
import { executionAPI, webTestcaseAPI, perfAPI } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Monitor, Link, Loading, Odometer, Histogram } from '@element-plus/icons-vue'

const router = useRouter()

// 状态
const loading = ref(false)
const rerunningIds = ref(new Set())  // 正在重跑中的记录 ID 集合（含源行 + 新记录）
const executions = ref([])
const users = ref([])
const selectedRows = ref([])

// 页面统计指标
const stats = computed(() => {
  const total = executions.value.length
  const running = executions.value.filter(e => e.status === 'running' || e.status === 'pending').length
  const passed = executions.value.filter(e => e.status === 'passed' || e.status === 'completed').length
  const failed = executions.value.filter(e => e.status === 'failed' || e.status === 'error').length
  return { total, running, passed, failed }
})

let pollingTimer = null  // 自动轮询 timer，用于刷新 running 状态

// 筛选
const filters = reactive({
  search: '',
  timeRange: '7days',
  dateRange: null,
  status: '',
  started_by: '',
  execType: '', // 'api' | 'web' | ''
})

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
})

// 加载执行历史（支持 API + Web + Perf 三类型）
const loadExecutions = async (silent = false) => {
  if (!silent) loading.value = true
  try {
    const execType = filters.execType

    // 全部：并行加载三种执行记录，避免串行等待
    if (!execType) {
      const params = {
        page: pagination.page,
        page_size: pagination.pageSize,
        ordering: '-started_at',
      }
      if (filters.search) params.search = filters.search
      if (filters.status) params.status = filters.status
      if (filters.started_by) params.started_by = filters.started_by

      console.log('[ExecutionHistory] 并行加载全部执行记录，参数:', params)
      const [apiRes, webItems, perfItems] = await Promise.all([
        executionAPI.list(params),
        _loadWebExecutions(params.page, params.page_size),
        _loadPerfExecutions(params.page, params.page_size),
      ])
      console.log('[ExecutionHistory] API 返回:', apiRes)
      const apiItems = (apiRes.results || []).map(item => ({ ...item, __type: 'api' }))
      console.log('[ExecutionHistory] API items 数量:', apiItems.length)

      const allItems = [...apiItems, ...webItems, ...perfItems].sort((a, b) => {
        const ta = new Date(a.__type === 'web' ? a.executed_at : a.started_at).getTime()
        const tb = new Date(b.__type === 'web' ? b.executed_at : b.started_at).getTime()
        return tb - ta
      })
      executions.value = allItems.slice(0, pagination.pageSize)
      pagination.total = (apiRes.count || 0) + webItems.length + perfItems.length
      return
    }

    // 只查性能测试执行记录
    if (execType === 'perf') {
      const perfItems = await _loadPerfExecutions()
      executions.value = perfItems
      pagination.total = perfItems.length
      return
    }

    // 只查 API 测试执行记录
    if (execType === 'api') {
      const params = {
        page: pagination.page,
        page_size: pagination.pageSize,
        ordering: '-started_at',
      }
      if (filters.search) params.search = filters.search
      if (filters.status) params.status = filters.status
      if (filters.started_by) params.started_by = filters.started_by

      console.log('[ExecutionHistory] 加载 API 执行记录，参数:', params)
      const apiRes = await executionAPI.list(params)
      console.log('[ExecutionHistory] API 返回:', apiRes)
      const apiItems = (apiRes.results || []).map(item => ({ ...item, __type: 'api' }))
      console.log('[ExecutionHistory] API items 数量:', apiItems.length)

      executions.value = apiItems
      pagination.total = apiRes.count || apiItems.length
      return
    }

    // 只查 Web 自动化执行记录
    if (execType === 'web') {
      const webItems = await _loadWebExecutions()
      executions.value = webItems
      pagination.total = webItems.length
    }
  } catch (error) {
    console.error('Load executions error:', error)
  } finally {
    if (!silent) loading.value = false
    // 如果列表中有 running/pending 记录，自动启动轮询刷新
    const hasRunning = executions.value.some(e => e.status === 'running' || e.status === 'pending')
    if (hasRunning && !pollingTimer) {
      pollingTimer = setInterval(() => {
        loadExecutions(true)  // silent 刷新，不显示 loading 闪烁
      }, 2000)
    } else if (!hasRunning && pollingTimer) {
      clearInterval(pollingTimer)
      pollingTimer = null
    }
  }
}

// 加载性能测试执行记录
const _loadPerfExecutions = async (page = 1, pageSize = 10) => {
  try {
    const params = { page, page_size: pageSize, exclude_suite: true }
    if (filters.status) params.status = filters.status
    if (filters.started_by) params.started_by = filters.started_by
    const res = await perfAPI.getExecutions(params)
    const statusMap = { pending: '等待中', running: '执行中', completed: '已完成', failed: '失败', stopped: '已停止' }
  return (res.results || []).map(item => {
      // 后端有时返回状态未正确更新：有结果数据但 status 还是 running
      let status = item.status
      if (status === 'running' && (item.requests_per_second != null || item.duration > 0)) {
        status = 'completed'
      }
      return {
        ...item,
        __type: 'perf',
        name: item.test_case_name || `执行 #${item.id}`,
        started_at: item.started_at,
        started_by_name: item.started_by_name,
        trigger_type: 'manual_perf',
        trigger_type_display: '性能手动',
        status,
        status_display: statusMap[status] || status,
        test_case_title: item.test_case_name,
        test_case_id: item.test_case,
        duration: item.duration,
        failure_rate: item.total_requests > 0 ? (item.failures || 0) / item.total_requests : 0,
        ai_score: item.exec_summary?.score ?? null,
      }
    })
  } catch (e) {
    console.error('[ExecutionHistory] Load perf executions error:', e)
    return []
  }
}

// 加载 Web 执行记录
const _loadWebExecutions = async (page = 1, pageSize = 10) => {
  try {
    const params = {
      page,
      page_size: pageSize,
    }
    console.log('[ExecutionHistory] 正在加载 Web 执行记录...')
    const res = await webTestcaseAPI.allExecutions(params)
    console.log('[ExecutionHistory] Web API 返回:', res)
    const statusMap = { passed: '通过', failed: '失败', error: '异常', running: '执行中', pending: '执行中' }
    const items = (res.results || []).map(item => ({
      ...item,
      __type: 'web',
      name: item.test_case_title || `用例 #${item.test_case}`,
      test_case_title: item.test_case_title || `#${item.test_case}`,
      started_at: item.executed_at,
      started_by_name: item.executed_by_username,
      screenshot_url: item.screenshot ? `/media/${item.screenshot}` : null,
      trigger_type: 'manual_web',
      trigger_type_display: 'Web手动',
      status_display: statusMap[item.status] || item.status,
    }))
    console.log('[ExecutionHistory] Web 映射后记录数:', items.length)
    return items
  } catch (e) {
    console.error('[ExecutionHistory] Load web executions error:', e)
    return []
  }
}

const onSizeChange = () => {
  pagination.page = 1
  loadExecutions()
}

// 搜索
const handleSearch = () => {
  pagination.page = 1
  loadExecutions()
}

// 重置筛选
const resetFilters = () => {
  filters.search = ''
  filters.timeRange = '7days'
  filters.dateRange = null
  filters.status = ''
  filters.started_by = ''
  filters.execType = ''
  pagination.page = 1
  loadExecutions()
}

// 查看详情（兼容 API / Web / Perf）
const viewDetail = (row) => {
  if (row.__type === 'web') {
    router.push({ name: 'WebExecutionDetail', params: { id: row.id } })
  } else if (row.__type === 'perf') {
    router.push(`/perf-execution/${row.id}`)
  } else {
    router.push({ name: 'ExecutionDetail', params: { id: row.id } })
  }
}

// 跳转到 Web 用例
const goToWebTestCase = (row) => {
  router.push({ name: 'WebTestCaseList', query: { showHistory: row.test_case } })
}

// 跳转到套件
const goToSuite = (id) => {
  router.push({ name: 'TestSuiteList' })
}

// 表格选择变化
const handleSelectionChange = (rows) => {
  selectedRows.value = rows
}

// 批量删除执行记录
const batchDeleteExecutions = async () => {
  if (selectedRows.value.length === 0) return

  const webIds = selectedRows.value.filter(r => r.__type === 'web').map(r => r.id)
  const perfIds = selectedRows.value.filter(r => r.__type === 'perf').map(r => r.id)
  const apiIds = selectedRows.value.filter(r => r.__type !== 'web' && r.__type !== 'perf').map(r => r.id)

  try {
    await ElMessageBox.confirm(`确认删除选中的 ${selectedRows.value.length} 条执行记录？`, '批量删除确认', {
      type: 'warning',
    })

    // 分类型调用对应 API
    if (webIds.length > 0) {
      await webTestcaseAPI.batchDelete(webIds)
    }
    for (const id of perfIds) {
      await perfAPI.deleteExecution(id)
    }
    // API 类型逐个删除（后端暂无批量接口，复用单条）
    for (const id of apiIds) {
      await executionAPI.delete(id)
    }

    ElMessage.success(`成功删除 ${selectedRows.value.length} 条记录`)
    selectedRows.value = []
    loadExecutions()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Batch delete error:', error)
    }
  }
}

// 行点击
const handleRowClick = (row) => {
  viewDetail(row)
}

// 重新执行
const rerunExecution = async (row) => {
  try {
    await ElMessageBox.confirm('确认重新执行此测试？', '重跑确认', { type: 'warning' })
    ElMessage.info('正在重新执行...')
    const response = await executionAPI.rerun(row.id)
    const exec = response.execution || response || {}
    ElMessage.success(`重新执行完成: ${exec.passed_cases || 0} 通过, ${exec.failed_cases || 0} 失败`)
    loadExecutions()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Rerun error:', error)
    }
  }
}

// 重新执行（兼容 API / Web）
const handleRerun = async (row) => {
  try {
    await ElMessageBox.confirm(`确认重新执行"${row.name || row.test_case_title || '此测试'}"？`, '重跑确认', { type: 'warning' })
  } catch {
    return // 取消
  }

  // 防止重复点击同一行（源行或新记录）
  if (rerunningIds.value.has(row.id)) {
    ElMessage.warning('该用例正在重跑中，请稍候')
    return
  }

  rerunningIds.value.add(row.id)
  // 先本地更新状态为 running，让用户立即看到"执行中"
  const idx = executions.value.findIndex(e => e.id === row.id)
  if (idx !== -1) {
    executions.value[idx].status = 'running'
    executions.value[idx].status_display = '执行中'
    // 更新时间戳，让最新重跑置顶
    const now = new Date().toISOString()
    if (executions.value[idx].__type === 'web') {
      executions.value[idx].executed_at = now
    } else {
      executions.value[idx].started_at = now
    }
    // 触发重新排序，让最新重跑置顶
    executions.value.sort((a, b) => {
      const ta = new Date(a.__type === 'web' ? a.executed_at : a.started_at).getTime()
      const tb = new Date(b.__type === 'web' ? b.executed_at : b.started_at).getTime()
      return tb - ta
    })
  }

  try {
    if (row.__type === 'web') {
      const response = await webTestcaseAPI.rerun(row.id)
      // 源行移除，新记录加入（后端已改为原记录更新，所以 id 不变）
      rerunningIds.value.delete(row.id)
      rerunningIds.value.add(response.execution_id)
      ElMessage.success('Web 测试已提交后台执行')
      _pollRerunStatus(response.execution_id)
      return
    }
    if (row.__type === 'perf') {
      const res = await perfAPI.execute({ test_case_id: row.test_case_id || row.id, execution_id: row.id })
      rerunningIds.value.delete(row.id)
      rerunningIds.value.add(res.id)
      ElMessage.success('性能测试已提交后台执行')
      _pollPerfStatus(res.id)
      return
    }
    // API 测试
    const response = await executionAPI.rerun(row.id)
    const exec = response.execution || response || {}
    rerunningIds.value.delete(row.id)
    ElMessage.success(`重跑完成: ${exec.passed_cases || 0} 通过, ${exec.failed_cases || 0} 失败`)
    loadExecutions()
  } catch (error) {
    rerunningIds.value.delete(row.id)
    console.error('Rerun error:', error)
    const msg = error?.response?.data?.error || error?.response?.data?.message || error?.message || '重跑失败'
    ElMessage.error(msg)
  }
}

// 轮询 Web 重跑结果
const _pollRerunStatus = (executionId) => {
  let attempts = 0
  const maxAttempts = 60  // 最多等 2 分钟
  const timer = setInterval(async () => {
    attempts++
    try {
      const detail = await webTestcaseAPI.getExecution(executionId)
      // 只更新列表中该记录，避免全量刷新闪烁
      const idx = executions.value.findIndex(e => e.id === executionId && e.__type === 'web')
      if (idx !== -1) {
        executions.value[idx] = { ...executions.value[idx], ...detail }
        // 后端可能不返回 status_display，前端补齐
        if (!executions.value[idx].status_display) {
          executions.value[idx].status_display = getStatusText(executions.value[idx].status) || executions.value[idx].status
        }
        // 后端可能更新了时间戳，重新排序确保位置正确
        executions.value.sort((a, b) => {
          const ta = new Date(a.__type === 'web' ? a.executed_at : a.started_at).getTime()
          const tb = new Date(b.__type === 'web' ? b.executed_at : b.started_at).getTime()
          return tb - ta
        })
      }
      if (detail.status !== 'running') {
        clearInterval(timer)
        rerunningIds.value.delete(executionId)
        ElMessage.success(`重跑完成 - 结果：${detail.status === 'passed' ? '通过' : '失败'}，耗时 ${detail.duration || '-'}s`)
        loadExecutions()
      }
    } catch {
      // 忽略轮询错误
    }
    if (attempts >= maxAttempts) {
      clearInterval(timer)
      rerunningIds.value.delete(executionId)
      ElMessage.warning('重跑超时，请手动刷新查看结果')
    }
  }, 2000)
}

// 轮询性能测试重跑结果
const _pollPerfStatus = (executionId) => {
  let attempts = 0
  const maxAttempts = 60  // 最多等 3 分钟
  const timer = setInterval(async () => {
    attempts++
    try {
      const detail = await perfAPI.getExecution(executionId)
      let idx = executions.value.findIndex(e => e.id === executionId && e.__type === 'perf')
      // 新建记录可能还未出现在列表中，先全量刷新
      if (idx === -1) {
        await loadExecutions(true)
        idx = executions.value.findIndex(e => e.id === executionId && e.__type === 'perf')
      }
      if (idx !== -1) {
        // 更新结果字段
        executions.value[idx].requests_per_second = detail.requests_per_second
        executions.value[idx].p95_response_time = detail.p95_response_time
        executions.value[idx].total_requests = detail.total_requests
        executions.value[idx].failures = detail.failures
        executions.value[idx].duration = detail.duration
        executions.value[idx].failure_rate = detail.total_requests > 0 ? (detail.failures || 0) / detail.total_requests : 0
        executions.value[idx].ai_score = detail.exec_summary?.score ?? null
        executions.value[idx].status = detail.status
        executions.value[idx].status_display = getStatusText(detail.status) || detail.status
        // 重新排序
        executions.value.sort((a, b) => {
          const ta = new Date(a.__type === 'web' ? a.executed_at : a.started_at).getTime()
          const tb = new Date(b.__type === 'web' ? b.executed_at : b.started_at).getTime()
          return tb - ta
        })
      }
      if (detail.status !== 'running' && detail.status !== 'pending') {
        clearInterval(timer)
        rerunningIds.value.delete(executionId)
        ElMessage.success('性能测试执行完成')
        loadExecutions()
      }
    } catch {
      // 忽略轮询错误
    }
    if (attempts >= maxAttempts) {
      clearInterval(timer)
      rerunningIds.value.delete(executionId)
      ElMessage.warning('性能测试执行超时，请手动刷新查看结果')
    }
  }, 3000)
}

// 删除执行记录（兼容 API / Web）
const deleteExecution = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除执行记录 "${row.name || '执行 #' + row.id}"？`, '删除确认', {
      type: 'warning',
    })
    if (row.__type === 'web') {
      await webTestcaseAPI.deleteExecution(row.id)
    } else if (row.__type === 'perf') {
      await perfAPI.deleteExecution(row.id)
    } else {
      await executionAPI.delete(row.id)
    }
    ElMessage.success('删除成功')
    loadExecutions()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Delete error:', error)
    }
  }
}

// 辅助函数
const getStatusType = (status) => {
  const types = {
    pending: 'info',
    running: 'info',
    completed: 'success',
    partial: 'warning',
    failed: 'danger',
    passed: 'success',
    error: 'warning',
    stopped: 'warning',
  }
  return types[status] || 'info'
}

const getStatusText = (status) => {
  const texts = {
    pending: '等待中',
    running: '执行中',
    completed: '已完成',
    partial: '部分通过',
    failed: '失败',
  }
  return texts[status] || status
}

const getTriggerTypeColor = (type) => {
  const colors = {
    manual_suite: '',
    manual_case: 'success',
    manual_web: 'success',
    debug: 'info',
    scheduled: 'warning',
    ci: 'danger',
  }
  return colors[type] || ''
}

const getEnvType = (env) => {
  const types = { dev: 'info', test: '', prod: 'danger' }
  return types[env] || ''
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadExecutions()
})

// keep-alive 缓存激活时刷新数据（解决从其他页面回来数据不更新的问题）
onActivated(() => {
  loadExecutions()
})

// keep-alive 缓存停用时停止轮询
onDeactivated(() => {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
})

// 组件销毁时停止轮询
onUnmounted(() => {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
})
</script>

<style scoped>
.execution-history-container {
  padding: 20px;
  flex: 1;
  min-height: 0;
  background: #f5f7fa;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.glass-card {
  background: #ffffff !important;
  border: 1px solid #e4e7ed !important;
  border-radius: 12px !important;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06) !important;
  color: #303133;
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

.glass-card :deep(.el-card__header) {
  padding: 0 !important;
  border-bottom: 1px solid #e4e7ed !important;
  background: linear-gradient(135deg, #f0f7ff 0%, #ffffff 100%);
}

.glass-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  padding: 20px;
}

.page-hero {
  padding: 24px 28px;
}

.hero-main {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.hero-title {
  display: flex;
  align-items: center;
  gap: 16px;
}

.hero-icon-wrap {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  background: linear-gradient(135deg, #409eff 0%, #67b1ff 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.25);
}

.page-hero .page-title {
  font-size: 22px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 6px 0;
  line-height: 1.3;
}

.page-hero .page-desc {
  font-size: 14px;
  color: #606266;
  margin: 0;
}

.hero-stats {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hero-stats .stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 18px;
  background: #fff;
  border-radius: 10px;
  border: 1px solid #ebeef5;
  min-width: 88px;
}

.hero-stats .stat-value {
  font-size: 22px;
  font-weight: 700;
  color: #409eff;
  line-height: 1.1;
}

.hero-stats .stat-value.running {
  color: #909399;
}

.hero-stats .stat-value.passed {
  color: #67c23a;
}

.hero-stats .stat-value.failed {
  color: #f56c6c;
}

.hero-stats .stat-label {
  font-size: 12px;
  color: #909399;
}

.hero-stats .stat-divider {
  width: 1px;
  height: 32px;
  background: #e4e7ed;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 16px 20px;
  background: #fafbfc;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.page-toolbar :deep(.el-form-item) {
  margin-bottom: 12px;
  margin-right: 16px;
}

.page-toolbar :deep(.el-form-item__label) {
  color: #606266;
  font-weight: 500;
}

.page-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
  min-width: 0;
}

.table-wrapper {
  flex: 1;
  overflow-y: auto;
  overflow-x: auto;
  min-height: 0;
  min-width: 0;
}

.table-wrapper::-webkit-scrollbar {
  height: 8px;
  width: 8px;
}

.table-wrapper::-webkit-scrollbar-thumb {
  background: #c0c4cc;
  border-radius: 4px;
}

.data-table {
  width: auto;
  min-width: 1400px;
  border-radius: 8px;
  overflow: hidden;
}

.data-table :deep(.el-table__header-wrapper th.el-table__cell) {
  background-color: #fafbfc !important;
  color: #606266;
  font-weight: 600;
  border-bottom: 1px solid #d9dce0;
  white-space: nowrap;
}

.data-table :deep(.el-table__body-wrapper td.el-table__cell) {
  border-bottom: 1px solid #eef0f4;
  white-space: nowrap;
}

.data-table :deep(.el-table__body-wrapper tr.el-table__row:hover td.el-table__cell) {
  background-color: #f5f7fa;
}

.data-table :deep(.el-loading-mask) {
  background-color: rgba(255, 255, 255, 0.85) !important;
  backdrop-filter: blur(2px);
}

/* 隐藏 el-table 内部可能产生的滚动条 */
.data-table :deep(.el-table__body-wrapper) {
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.data-table :deep(.el-table__body-wrapper::-webkit-scrollbar) {
  display: none;
}
.data-table :deep(.el-table__header-wrapper) {
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.data-table :deep(.el-table__header-wrapper::-webkit-scrollbar) {
  display: none;
}

.page-pagination {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-top: 20px;
  flex-shrink: 0;
  padding: 0 4px;
  color: #606266;
  font-size: 14px;
}

/* 每页条数选择框 */
.page-pagination :deep(.el-pagination__sizes) {
  margin: 0 12px;
}

.page-pagination :deep(.el-pagination__sizes .el-select .el-input__wrapper) {
  box-shadow: 0 0 0 1px #dcdfe6 inset;
  border-radius: 4px;
  height: 30px;
  padding: 0 8px;
  line-height: 30px;
}

/* 翻页按钮和页码 */
.page-pagination :deep(.btn-prev),
.page-pagination :deep(.btn-next),
.page-pagination :deep(.number) {
  min-width: 30px;
  height: 30px;
  background: transparent;
  color: #606266;
  border-radius: 4px;
  font-size: 14px;
}

.page-pagination :deep(.number.active) {
  color: #409eff;
  background: transparent;
  font-weight: 600;
}

.page-pagination :deep(.btn-prev.is-disabled),
.page-pagination :deep(.btn-next.is-disabled) {
  color: #c0c4cc;
}

/* 前往 X 页 */
.page-pagination :deep(.el-pagination__jump) {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-left: 12px;
  color: #606266;
}

.page-pagination :deep(.el-pagination__jump .el-input) {
  width: 44px;
  margin: 0;
}

.page-pagination :deep(.el-pagination__jump .el-input__wrapper) {
  box-shadow: none;
  border: none;
  background: transparent;
  padding: 0;
}

.page-pagination :deep(.el-pagination__jump .el-input__inner) {
  width: 44px;
  height: 28px;
  line-height: 28px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 0 4px;
  text-align: center;
  background: #fff;
}

.page-pagination :deep(.el-pagination__jump .el-input__inner:focus) {
  border-color: #409eff;
}

.empty-state-glass {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px 20px;
  text-align: center;
  background: #ffffff;
  border: 1px dashed #dcdfe6;
  border-radius: 12px;
}

.empty-state-glass .empty-icon-wrap {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: #f0f7ff;
  color: #409eff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.empty-state-glass .empty-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 8px 0;
}

.empty-state-glass .empty-desc {
  font-size: 14px;
  color: #909399;
  margin: 0;
  max-width: 420px;
  line-height: 1.6;
}

.result-badges {
  display: flex;
  gap: 4px;
  align-items: center;
  flex-wrap: wrap;
  row-gap: 2px;
}

.result-badges .el-tag {
  min-width: 40px;
  justify-content: center;
}
</style>
