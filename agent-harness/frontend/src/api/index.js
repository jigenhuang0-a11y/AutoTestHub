import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  async (error) => {
    if (error.config?.skipErrorHandler) {
      return Promise.reject(error)
    }

    // 打印错误，方便 F12 调试
    const url = error.config?.url || 'unknown'
    const status = error.response?.status || 'network'
    console.error(`[api] error ${status} on ${url}:`, error.response?.data || error.message)

    if (error.response) {
      switch (error.response.status) {
        case 401: {
          const auth = useAuthStore()
          // 已登录态下，尝试用 /auth/refresh 静默续期并重试一次原请求
          if (auth.accessToken && !error.config._retried) {
            const ok = await auth.refreshAccessToken()
            if (ok) {
              error.config._retried = true
              const newToken = localStorage.getItem('access_token')
              if (newToken) error.config.headers.Authorization = `Bearer ${newToken}`
              return api.request(error.config)
            }
          }
          // 打印关键调试信息，帮助定位是哪个请求触发 401
          console.error('[api] 401 触发跳转登录页:', {
            url: error.config?.url,
            method: error.config?.method,
            status: error.response?.status,
            data: error.response?.data,
          })
          // 避免在登录页本身触发无限跳转
          if (window.location.pathname !== '/login' && router.currentRoute.value.path !== '/login') {
            ElMessage.error('登录已过期，请重新登录')
            localStorage.removeItem('access_token')
            localStorage.removeItem('refresh_token')
            localStorage.removeItem('user')
            router.replace('/login')
          }
          break
        }
        case 403:
          ElMessage.error('禁止访问')
          break
        case 404:
          ElMessage.error('请求的资源不存在')
          break
        case 500:
          ElMessage.error('服务器错误')
          break
        default:
          ElMessage.error(error.response.data?.detail || error.response.data?.error || '请求失败')
      }
    } else if (error.code === 'ECONNABORTED') {
      ElMessage.error('请求超时，请检查后端服务是否启动')
    } else {
      ElMessage.error('网络错误，请检查后端服务是否启动')
    }
    return Promise.reject(error)
  }
)

// 认证API
// 注意：baseURL 已含 /api/v1，此处用相对路径即可（不要带尾部斜杠，避免 FastAPI 307 重定向丢 body）
export const authAPI = {
  login: (data) => api.post('/auth/login', data),
  register: (data) => api.post('/auth/register', data),
  refreshToken: (data) => api.post('/auth/refresh', data),
  getProfile: () => api.get('/auth/profile'),
  changePassword: (data) => api.put('/auth/change-password', data),
}

// 规范化列表响应：后端可能返回 {items,total} 或 {results,count}，统一成 {results,total}
export function normalizeList(res) {
  if (!res) return { results: [], total: 0 }
  if (Array.isArray(res)) return { results: res, total: res.length }
  const items = res.items ?? res.results ?? []
  const total = res.total ?? res.count ?? items.length
  return { results: items, total }
}

// 测试用例API
export const testcaseAPI = {
  list: async (params) => normalizeList(await api.get('/testcases/', { params })),
  get: (id) => api.get(`/testcases/${id}/`),
  create: (data) => api.post('/testcases/', data),
  update: (id, data) => api.put(`/testcases/${id}/`, data),
  patch: (id, data) => api.patch(`/testcases/${id}/`, data),
  delete: (id) => api.delete(`/testcases/${id}/`),
  aiGenerate: (data) => api.post('/testcases/ai-generate/', data),
  aiGenerateConversation: (data) => {
    const token = localStorage.getItem('access_token')
    return fetch(`${api.defaults.baseURL}/testcases/ai-generate-conversation/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    })
  },
  aiParseInterface: (data) => api.post('/testcases/ai-parse-interface/', data),
  debug: (id, data) => api.post(`/testcases/${id}/debug/`, data),
  debugTemp: (data) => api.post('/testcases/debug-temp/', data),
}

// AI 底座 / 模型配置（供测试模块选择真实 LLM）
export const aiBaseAPI = {
  listModels: (params) => api.get('/ai-base/models/', { params }),
  activeModel: () => api.get('/ai-base/models/active/'),
}

// 测试执行API
export const executionAPI = {
  list: async (params) => normalizeList(await api.get('/execution/', { params })),
  get: (id) => api.get(`/execution/${id}/`),
  execute: (data) => api.post('/execution/', data),
  rerun: (id) => api.post(`/execution/${id}/rerun/`),
  delete: (id) => api.delete(`/execution/${id}/`),
  stats: (params) => api.get('/execution/stats/', { params }),
  exportReport: (id, format = 'html') => api.post(`/execution/${id}/export_report/`, { format }, {
    responseType: 'blob',
  }),
}

// 报告API
export const reportAPI = {
  list: async (params) => normalizeList(await api.get('/reports/', { params })),
  get: (id) => api.get(`/reports/${id}/`),
  summary: () => api.get('/reports/summary/'),
  health: (data) => api.post('/reports/health/', data),
}

// 测试套件API
export const testsuiteAPI = {
  list: async (params) => normalizeList(await api.get('/testsuites/', { params })),
  get: (id) => api.get(`/testsuites/${id}/`),
  create: (data) => api.post('/testsuites/', data),
  update: (id, data) => api.put(`/testsuites/${id}/`, data),
  delete: (id) => api.delete(`/testsuites/${id}/`),
  execute: (suiteId) => api.post(`/testsuites/${suiteId}/execute/`),
  scheduleExecute: (suiteId, data) => api.post(`/testsuites/${suiteId}/schedule-execute/`, data),
  cancelSchedule: (suiteId, data) => api.post(`/testsuites/${suiteId}/cancel-schedule/`, data),
  toggleLock: (suiteId, data) => api.post(`/testsuites/${suiteId}/toggle-lock/`, data),
  addTestCases: (suiteId, testCaseIds) => api.post(`/testsuites/${suiteId}/add-test-cases/`, { test_case_ids: testCaseIds }),
}

// 知识库API
// 后端知识库对象使用 kb_id 作为主键，前端组件统一使用 id，这里做字段适配。
const _normalizeKB = (kb) => {
  if (!kb || typeof kb !== 'object') return kb
  // 兼容后端 stub/包装层可能把真实字段放在 _data 里的情况
  const inner = kb._data || kb
  const id = inner.kb_id || inner.id || inner._id || inner.kbId || inner.uuid || ''
  return { ...kb, id }
}

export const knowledgeBaseAPI = {
  list: async (params) => {
    const res = await api.get('/knowledge/knowledge-bases/', { params })
    const items = res.items || res.results || res || []
    return { results: items.map(_normalizeKB), total: res.total ?? items.length }
  },
  get: async (id) => {
    const res = await api.get(`/knowledge/knowledge-bases/${id}/`)
    return _normalizeKB(res)
  },
  create: async (data) => {
    const res = await api.post('/knowledge/knowledge-bases/', data)
    // 后端可能直接返回对象，也可能包在 data/result/results 字段里
    const kb = res?.data ?? res?.result ?? res?.results ?? res
    return _normalizeKB(kb)
  },
  update: (id, data) => api.put(`/knowledge/knowledge-bases/${id}/`, data),
  delete: (id) => api.delete(`/knowledge/knowledge-bases/${id}/`),
  
  uploadDocument: (kbId, file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`/knowledge/knowledge-bases/${kbId}/upload_document/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  
  deleteDocument: (kbId, documentId) => api.delete(`/knowledge/knowledge-bases/${kbId}/delete_document/`, {
    data: { document_id: documentId },
  }),
  
  ask: (kbId, question, sessionId, mode, systemPrompt, images) => {
    const data = { question }
    if (sessionId) data.session_id = sessionId
    if (mode) data.mode = mode
    if (systemPrompt) data.system_prompt = systemPrompt
    if (images && images.length > 0) data.images = images
    return api.post(`/knowledge/knowledge-bases/${kbId}/ask/`, data)
  },
  
  askStream: (kbId, question, sessionId, mode, systemPrompt, skillName, images) => {
    const data = { question }
    if (sessionId) data.session_id = sessionId
    if (mode) data.mode = mode
    if (systemPrompt) data.system_prompt = systemPrompt
    if (skillName) data.skill_name = skillName
    if (images && images.length > 0) data.images = images
    const token = localStorage.getItem('access_token')
    return fetch(`${api.defaults.baseURL}/knowledge/knowledge-bases/${kbId}/ask_stream/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    })
  },
  
  chatStream: (question, sessionId, systemPrompt, skillName, images) => {
    const data = { question }
    if (sessionId) data.session_id = sessionId
    if (systemPrompt) data.system_prompt = systemPrompt
    if (skillName) data.skill_name = skillName
    if (images && images.length > 0) data.images = images
    const token = localStorage.getItem('access_token')
    return fetch(`${api.defaults.baseURL}/knowledge/chat/stream/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    })
  },

  chatHistory: (kbId) => api.get(`/knowledge/knowledge-bases/${kbId}/chat_history/`),
  getSessionList: (kbId) => api.get(`/knowledge/knowledge-bases/${kbId}/session_list/`),
  getSessionMessages: (kbId, sessionId) => api.get(`/knowledge/knowledge-bases/${kbId}/session_messages/`, {
    params: { session_id: sessionId }
  }),
  deleteMessage: (kbId, messageId) => api.delete(`/knowledge/knowledge-bases/${kbId}/delete_message/`, {
    data: { message_id: messageId }
  }),
  batchDeleteMessages: (kbId, messageIds) => api.delete(`/knowledge/knowledge-bases/${kbId}/batch_delete_messages/`, {
    data: { message_ids: messageIds }
  }),
  deleteSession: (kbId, sessionId) => api.delete(`/knowledge/knowledge-bases/${kbId}/delete_session/`, {
    data: { session_id: sessionId },
    skipErrorHandler: true
  }),

  // 日常对话（无 kbId）
  chatHistoryChat: () => api.get('/knowledge/chat/history/'),
  chatSessionList: () => api.get('/knowledge/chat/sessions/'),
  chatSessionMessages: (sessionId) => api.get('/knowledge/chat/messages/', {
    params: { session_id: sessionId }
  }),
  deleteChatSession: (sessionId) => api.delete(`/knowledge/chat/sessions/${sessionId}/`, {
    skipErrorHandler: true
  }),
  documents: (params) => api.get('/knowledge/documents/', { params }),
  getDocuments: (kbId) => api.get('/knowledge/documents/', { 
    params: { knowledge_base: kbId },
    skipErrorHandler: true
  }),
  deleteDocument: (docId) => api.delete(`/knowledge/documents/${docId}/`, {
    skipErrorHandler: true
  }),
}

// AI测评师API
export const evaluatorAPI = {
  list: (params) => api.get('/ai-evaluator/tasks/', { params }),
  createTask: (data) => api.post('/ai-evaluator/tasks/create_task/', data),
  runEval: (data) => api.post('/ai-evaluator/tasks/run_eval/', data),
  getResults: (taskId, params) => api.get(`/ai-evaluator/tasks/${taskId}/results/`, { params }),
  getQuestions: (taskId) => api.get(`/ai-evaluator/tasks/${taskId}/questions/`),
  getStatistics: (taskId) => api.get(`/ai-evaluator/tasks/${taskId}/statistics/`),
  getReport: (taskId) => api.get(`/ai-evaluator/tasks/${taskId}/report/`),
  exportCSV: (taskId) => api.get(`/ai-evaluator/tasks/${taskId}/export_csv/`, { responseType: 'blob' }),
  deleteTask: (taskId) => api.post(`/ai-evaluator/tasks/${taskId}/delete_task/`),
  batchDelete: (taskIds) => api.post('/ai-evaluator/tasks/batch_delete/', { task_ids: taskIds }),
  updateTask: (taskId, data) => api.put(`/ai-evaluator/tasks/${taskId}/`, data),
  summary: () => api.get('/ai-evaluator/tasks/summary/'),
  generateQuestions: (data) => api.post('/ai-evaluator/tasks/generate_questions/', data),
  resetStuck: (taskId) => api.post(`/ai-evaluator/tasks/${taskId}/reset_stuck/`),
}

// AI 模型配置 API
export const modelConfigAPI = {
  list: (params) => api.get('/ai-base/models/', { params }),
  get: (id) => api.get(`/ai-base/models/${id}/`),
  create: (data) => api.post('/ai-base/models/', data),
  update: (id, data) => api.put(`/ai-base/models/${id}/`, data),
  patch: (id, data) => api.patch(`/ai-base/models/${id}/`, data),
  delete: (id) => api.delete(`/ai-base/models/${id}/`),
  active: () => api.get('/ai-base/models/active/'),
  testConnection: (id) => api.post(`/ai-base/models/${id}/test_connection/`),
}

// Web自动化测试用例API
export const webTestcaseAPI = {
  list: async (params) => normalizeList(await api.get('/web-testcases/', { params })),
  get: (id) => api.get(`/web-testcases/${id}/`),
  create: (data) => api.post('/web-testcases/', data),
  update: (id, data) => api.put(`/web-testcases/${id}/`, data),
  patch: (id, data) => api.patch(`/web-testcases/${id}/`, data),
  delete: (id) => api.delete(`/web-testcases/${id}/`),
  debug: (id) => api.post(`/web-testcases/${id}/debug/`),
  debugTemp: (data) => api.post('/web-testcases/debug-temp/', data),
  executions: (id) => api.get(`/web-testcases/${id}/executions/`),
  allExecutions: (params) => api.get('/web-testcases/executions/', { params }),
  deleteExecution: (id) => api.delete(`/web-testcases/executions/${id}/`),
  getExecution: (id) => api.get(`/web-testcases/executions/${id}/`),
  batchDelete: (ids) => api.post('/web-testcases/executions/', { ids }),
  rerun: (executionId) => api.post(`/web-testcases/executions/${executionId}/`),
}

// 性能测试API
export const perfAPI = {
  listTestCases: async (params) => normalizeList(await api.get('/performance/', { params })),
  getTestCase: (id) => api.get(`/performance/${id}/`),
  createTestCase: (data) => api.post('/performance/', data),
  updateTestCase: (id, data) => api.put(`/performance/${id}/`, data),
  deleteTestCase: (id) => api.delete(`/performance/${id}/`),
  getTestCaseExecutions: (id) => api.get(`/performance/${id}/executions/`),
  execute: (data) => api.post('/performance/execute/', data),
  getExecutions: (params) => api.get('/performance/executions/', { params }),
  getExecution: (id) => api.get(`/performance/executions/${id}/`),
  deleteExecution: (id) => api.delete(`/performance/executions/${id}/`),
  stopExecution: (id) => api.post(`/performance/executions/${id}/stop/`),
  getMetrics: (id) => api.get(`/performance/executions/${id}/metrics/`),
  diagnoseExecution: (id) => api.post(`/performance/executions/${id}/diagnose/`),
}

// 数据工厂API
export const dataFactoryAPI = {
  listDatasets: async (params) => normalizeList(await api.get('/data-factory/datasets/', { params })),
  getDataset: (id) => api.get(`/data-factory/${id}/`),
  createDataset: (data) => api.post('/data-factory/', data),
  deleteDataset: (id) => api.delete(`/data-factory/${id}/`),
  listTemplates: (params) => api.get('/data-factory/templates/', { params }),
  getTemplate: (id) => api.get(`/data-factory/templates/${id}/`),
  listPresets: (params) => api.get('/data-factory/preset/', { params }),
  generateLLMDataset: (data) => api.post('/data-factory/datasets/generate_llm_dataset/', data),
}

// 质量检查API
export const qualityCheckerAPI = {
  listTasks: async (params) => normalizeList(await api.get('/quality-checker/', { params })),
  getTask: (id) => api.get(`/quality-checker/${id}/`),
  createTask: (data) => api.post('/quality-checker/', data),
  listStandards: async (params) => normalizeList(await api.get('/quality-checker/standards/', { params })),
}

// Agent/MCP API
export const agentAPI = {
  listTasks: (params) => api.get('/agent/tasks/', { params }),
  getTask: (id) => api.get(`/agent/tasks/${id}/`),
  generateTestcases: (data) => api.post('/agent/tasks/generate_testcases/', data),
  mcpHealth: () => api.get('/mcp/health/'),
  mcpTools: (params) => api.get('/mcp/tools/', { params }),
}

// 记忆管理 API（对接后端 /api/v1/memory/manage/*，承载对话实际沉淀的长期记忆）
export const memoryAPI = {
  list: (userId, mode) => {
    const params = {}
    if (userId !== undefined && userId !== null) params.user_id = userId
    if (mode) params.mode = mode
    return api.get('/memory/manage/list', { params })
  },
  delete: (userId, memoryId, mode) => api.post('/memory/manage/delete', {
    user_id: userId ?? null,
    memory_id: memoryId,
    mode: mode ?? null,
  }),
  clear: (userId, mode) => api.post('/memory/manage/clear', {
    user_id: userId ?? null,
    mode: mode ?? null,
  }),
}

// 环境管理 API
export const environmentAPI = {
  list: (params) => api.get('/agent/environments/', { params }),
  create: (data) => api.post('/agent/environments/', data),
  update: (id, data) => api.put(`/agent/environments/${id}/`, data),
  delete: (id) => api.delete(`/agent/environments/${id}/`),
}

// 全链路评测中心 API（Langfuse 监控 + Judge LLM 幻觉率评分）
export const evalCenterAPI = {
  dashboard: (hours = 24, granularity = 'auto') => api.get('/eval-center/dashboard', { params: { hours, granularity } }),
  records: (params) => api.get('/eval-center/records', { params }),
  judge: (data) => api.post('/eval-center/judge', data),
  langfuseConfig: () => api.get('/eval-center/langfuse-config'),
}

// 多 Agent 团队编排 API（对接后端 /api/v1/team/team/tasks 任务生命周期）
export const teamAPI = {
  list: (params) => api.get('/team/team/tasks', { params }),
  get: (id) => api.get(`/team/team/tasks/${id}`),
  create: (data) => api.post('/team/team/tasks', { req: data }),
  update: (id, data) => api.patch(`/team/team/tasks/${id}`, { req: data }),
  next: (id) => api.post(`/team/team/tasks/${id}/next`),
  assign: (id, role, message) => api.post(`/team/team/tasks/${id}/assign`, null, { params: { role, message } }),
  execute: (id) => api.post(`/team/team/tasks/${id}/execute`),
  submitReview: (id) => api.post(`/team/team/tasks/${id}/submit-review`),
  review: (id, verdict) => api.post(`/team/team/tasks/${id}/review`, null, { params: { verdict } }),
  unblock: (id) => api.post(`/team/team/tasks/${id}/unblock`),
  orchestrate: (data) => api.post('/team/team/tasks/orchestrate', { req: data }),
}

export default api
