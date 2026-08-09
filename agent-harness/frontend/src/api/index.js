import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
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
  (error) => {
    if (error.config?.skipErrorHandler) {
      return Promise.reject(error)
    }

    // 打印错误，方便 F12 调试
    const url = error.config?.url || 'unknown'
    const status = error.response?.status || 'network'
    console.error(`[api] error ${status} on ${url}:`, error.response?.data || error.message)

    if (error.response) {
      switch (error.response.status) {
        case 401:
          // 避免在登录页本身触发无限跳转
          if (window.location.pathname !== '/login') {
            ElMessage.error('登录已过期，请重新登录')
            localStorage.removeItem('access_token')
            localStorage.removeItem('refresh_token')
            localStorage.removeItem('user')
            window.location.replace('/login')
          }
          break
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
// 注意：baseURL 已含 /api，此处用相对路径即可
export const authAPI = {
  login: (data) => api.post('/auth/login/', data),
  register: (data) => api.post('/auth/register/', data),
  refreshToken: (data) => api.post('/auth/refresh/', data),
  getProfile: () => api.get('/auth/profile/'),
  changePassword: (data) => api.put('/auth/change-password/', data),
}

// 测试用例API
export const testcaseAPI = {
  list: (params) => api.get('/testcases/', { params }),
  get: (id) => api.get(`/testcases/${id}/`),
  create: (data) => api.post('/testcases/', data),
  update: (id, data) => api.put(`/testcases/${id}/`, data),
  patch: (id, data) => api.patch(`/testcases/${id}/`, data),
  delete: (id) => api.delete(`/testcases/${id}/`),
  aiGenerate: (data) => api.post('/testcases/ai-generate/', data),
  aiParseInterface: (data) => api.post('/testcases/ai-parse-interface/', data),
  debug: (id, data) => api.post(`/testcases/${id}/debug/`, data),
  debugTemp: (data) => api.post('/testcases/debug-temp/', data),
}

// 测试执行API
export const executionAPI = {
  list: (params) => api.get('/execution/', { params }),
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
  list: (params) => api.get('/reports/', { params }),
  get: (id) => api.get(`/reports/${id}/`),
}

// 测试套件API
export const testsuiteAPI = {
  list: (params) => api.get('/testsuites/', { params }),
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
export const knowledgeBaseAPI = {
  list: (params) => api.get('/knowledge/knowledge-bases/', { params }),
  get: (id) => api.get(`/knowledge/knowledge-bases/${id}/`),
  create: (data) => api.post('/knowledge/knowledge-bases/', data),
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
    data: { session_id: sessionId }
  }),
  documents: (params) => api.get('/knowledge/documents/', { params }),
  getDocuments: (kbId) => api.get('/knowledge/documents/', { 
    params: { knowledge_base: kbId } 
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
  list: (params) => api.get('/ai-evaluator/models/', { params }),
  get: (id) => api.get(`/ai-evaluator/models/${id}/`),
  create: (data) => api.post('/ai-evaluator/models/', data),
  update: (id, data) => api.put(`/ai-evaluator/models/${id}/`, data),
  patch: (id, data) => api.patch(`/ai-evaluator/models/${id}/`, data),
  delete: (id) => api.delete(`/ai-evaluator/models/${id}/`),
  active: () => api.get('/ai-evaluator/models/active/'),
  testConnection: (id) => api.post(`/ai-evaluator/models/${id}/test_connection/`),
}

// Web自动化测试用例API
export const webTestcaseAPI = {
  list: (params) => api.get('/web-testcases/', { params }),
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
  listTestCases: (params) => api.get('/performance/', { params }),
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
  listDatasets: (params) => api.get('/data-factory/', { params }),
  getDataset: (id) => api.get(`/data-factory/${id}/`),
  createDataset: (data) => api.post('/data-factory/', data),
  deleteDataset: (id) => api.delete(`/data-factory/${id}/`),
  listTemplates: (params) => api.get('/data-factory/templates/', { params }),
  getTemplate: (id) => api.get(`/data-factory/templates/${id}/`),
  listPresets: (params) => api.get('/data-factory/preset/', { params }),
}

// 质量检查API
export const qualityCheckerAPI = {
  listTasks: (params) => api.get('/quality-checker/', { params }),
  getTask: (id) => api.get(`/quality-checker/${id}/`),
  createTask: (data) => api.post('/quality-checker/', data),
  listStandards: (params) => api.get('/quality-checker/standards/', { params }),
}

// Agent/MCP API
export const agentAPI = {
  listTasks: (params) => api.get('/agent/tasks/', { params }),
  getTask: (id) => api.get(`/agent/tasks/${id}/`),
  generateTestcases: (data) => api.post('/agent/tasks/generate_testcases/', data),
  mcpHealth: () => api.get('/mcp/health/'),
  mcpTools: (params) => api.get('/mcp/tools/', { params }),
}

// 环境管理 API
export const environmentAPI = {
  list: (params) => api.get('/agent/environments/', { params }),
  create: (data) => api.post('/agent/environments/', data),
  update: (id, data) => api.put(`/agent/environments/${id}/`, data),
  delete: (id) => api.delete(`/agent/environments/${id}/`),
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
