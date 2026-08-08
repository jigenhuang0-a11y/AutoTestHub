<template>
  <div class="execution-history-container">
    <!-- 搜索筛选区域 -->
    <el-card class="filter-card" shadow="never">
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
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 执行历史列表 -->
    <el-card shadow="never">
      <!-- 工具栏：批量操作 -->
      <div style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px">
        <el-button
          type="danger" size="small"
          :disabled="selectedRows.length === 0"
          @click="batchDeleteExecutions"
        >
          批量删除 ({{ selectedRows.length }})
        </el-button>
        <span v-if="selectedRows.length > 0" style="color: #909399; font-size: 12px">
          已选择 {{ selectedRows.length }} 条记录
        </span>
      </div>
      <el-table
        :data="executions"
        v-loading="loading"
        stripe
        border
        style="width: 100%"
        @row-click="handleRowClick"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="45" />
        <el-table-column prop="id" label="ID" width="70" />
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
        <el-table-column label="执行名称" min-width="200">
          <template #default="{ row }">
            <el-link type="primary" @click.stop="viewDetail(row.id)">
              {{ row.name || `执行 #${row.id}` }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="关联用例/套件" min-width="160">
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
        <el-table-column label="结果" min-width="240">
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
                <el-tag size="small" effect="plain">总 {{ row.total_count || 0 }}</el-tag>
                <el-tag size="small" type="success" effect="plain">{{ row.passed_count || 0 }}</el-tag>
                <el-tag size="small" type="danger" effect="plain">{{ row.failed_count || 0 }}</el-tag>
                <el-tag size="small" type="warning" effect="plain">{{ row.skipped_count || 0 }}</el-tag>
              </div>
            </template>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ row.status_display || getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="执行时间" width="160">
          <template #default="{ row }">{{ formatDate(row.__type === 'web' ? row.executed_at : row.started_at) }}</template>
        </el-table-column>
        <el-table-column label="耗时" width="80">
          <template #default="{ row }">{{ row.duration ? row.duration + 's' : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click.stop="viewDetail(row)">
              {{ row.__type === 'web' ? '详情' : '详情' }}
            </el-button>
            <el-button size="small" link type="warning" :loading="rerunningIds.has(row.id)" @click.stop="handleRerun(row)">重跑</el-button>
            <el-button size="small" link type="danger" @click.stop="deleteExecution(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        :total="pagination.total"
        :page-size="pagination.pageSize"
        layout="total, prev, pager, next"
        style="margin-top: 16px; justify-content: flex-end"
        @current-change="loadExecutions"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onActivated, onUnmounted, onDeactivated } from 'vue'
import { useRouter } from 'vue-router'
import { executionAPI, webTestcaseAPI, perfAPI } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Monitor, Link, Loading, Odometer } from '@element-plus/icons-vue'

const router = useRouter()

// 状态
const loading = ref(false)
const rerunningIds = ref(new Set())  // 正在重跑中的记录 ID 集合（含源行 + 新记录）
const executions = ref([])
const users = ref([])
const selectedRows = ref([])

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

    // 只查性能测试执行记录
    if (execType === 'perf') {
      const perfItems = await _loadPerfExecutions()
      executions.value = perfItems
      pagination.total = perfItems.length
      return
    }

    // 只查 API 测试执行记录
    if (execType === 'api' || !execType) {
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

      if (!execType) {
        // 全部：合并 Web + Perf 执行记录
        const webItems = await _loadWebExecutions()
        const perfItems = await _loadPerfExecutions()
        const allItems = [...apiItems, ...webItems, ...perfItems].sort((a, b) => {
          const ta = new Date(a.__type === 'web' ? a.executed_at : a.started_at).getTime()
          const tb = new Date(b.__type === 'web' ? b.executed_at : b.started_at).getTime()
          return tb - ta
        })
        executions.value = allItems.slice(0, pagination.pageSize)
        pagination.total = (apiRes.count || 0) + webItems.length + perfItems.length
      } else {
        executions.value = apiItems
        pagination.total = apiRes.count || apiItems.length
      }
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
const _loadPerfExecutions = async () => {
  try {
    const params = { page: 1, page_size: 100, exclude_suite: true }
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
const _loadWebExecutions = async () => {
  try {
    const params = {
      page: 1,
      page_size: 100, // 先拉最近一批
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
  viewDetail(row.id)
}

// 重新执行
const rerunExecution = async (row) => {
  try {
    await ElMessageBox.confirm('确认重新执行此测试？', '重跑确认', { type: 'warning' })
    ElMessage.info('正在重新执行...')
    const response = await executionAPI.rerun(row.id)
    ElMessage.success(`重新执行完成: ${response.passed_count || 0} 通过, ${response.failed_count || 0} 失败`)
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
    rerunningIds.value.delete(row.id)
    ElMessage.success(`重跑完成: ${response.passed_count || 0} 通过, ${response.failed_count || 0} 失败`)
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
    running: '',
    completed: 'success',
    partial: 'warning',
    failed: 'danger',
    passed: 'success',
    error: 'warning',
    stopped: 'warning',
  }
  return types[status] || ''
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
  padding: 0;
}

.filter-card {
  margin-bottom: 16px;
}

.filter-card :deep(.el-card__body) {
  padding-bottom: 8px;
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
