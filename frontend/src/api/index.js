import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000, // 增加到2分钟，给AI更多思考时间
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
    if (error.response) {
      switch (error.response.status) {
        case 401:
          ElMessage.error('未授权，请重新登录')
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          window.location.href = '/login'
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
          ElMessage.error(error.response.data?.error || '请求失败')
      }
    } else {
      ElMessage.error('网络错误，请检查网络连接')
    }
    return Promise.reject(error)
  }
)

// 认证API
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

// 测试套件API - 简化版:用例的集合/文件夹
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
  // 知识库管理
  list: (params) => api.get('/knowledge/knowledge-bases/', { params }),
  get: (id) => api.get(`/knowledge/knowledge-bases/${id}/`),
  create: (data) => api.post('/knowledge/knowledge-bases/', data),
  update: (id, data) => api.put(`/knowledge/knowledge-bases/${id}/`, data),
  delete: (id) => api.delete(`/knowledge/knowledge-bases/${id}/`),
  
  // 文档上传
  uploadDocument: (kbId, file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`/knowledge/knowledge-bases/${kbId}/upload_document/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  
  // 删除文档
  deleteDocument: (kbId, documentId) => api.delete(`/knowledge/knowledge-bases/${kbId}/delete_document/`, {
    data: { document_id: documentId },
  }),
  
  // 问答 - 支持session_id、mode和图片
  ask: (kbId, question, sessionId, mode, systemPrompt, images) => {
    const data = { question }
    if (sessionId) {
      data.session_id = sessionId
    }
    if (mode) {
      data.mode = mode
    }
    if (systemPrompt) {
      data.system_prompt = systemPrompt
    }
    if (images && images.length > 0) {
      data.images = images
    }
    return api.post(`/knowledge/knowledge-bases/${kbId}/ask/`, data)
  },
  
  // 流式问答 - SSE 流式输出
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
  
  // 对话历史（所有消息）
  chatHistory: (kbId) => api.get(`/knowledge/knowledge-bases/${kbId}/chat_history/`),
  
  // 获取会话列表
  getSessionList: (kbId) => api.get(`/knowledge/knowledge-bases/${kbId}/session_list/`),
  
  // 获取指定会话的所有消息
  getSessionMessages: (kbId, sessionId) => api.get(`/knowledge/knowledge-bases/${kbId}/session_messages/`, {
    params: { session_id: sessionId }
  }),
  
  // 删除对话历史消息
  deleteMessage: (kbId, messageId) => api.delete(`/knowledge/knowledge-bases/${kbId}/delete_message/`, {
    data: { message_id: messageId }
  }),
  
  // 批量删除对话历史消息
  batchDeleteMessages: (kbId, messageIds) => api.delete(`/knowledge/knowledge-bases/${kbId}/batch_delete_messages/`, {
    data: { message_ids: messageIds }
  }),
  
  // 删除整个会话
  deleteSession: (kbId, sessionId) => api.delete(`/knowledge/knowledge-bases/${kbId}/delete_session/`, {
    data: { session_id: sessionId }
  }),
  
  // 文档列表
  documents: (params) => api.get('/knowledge/documents/', { params }),
  
  // 获取知识库的文档列表
  getDocuments: (kbId) => api.get('/knowledge/documents/', { 
    params: { knowledge_base: kbId } 
  }),
  
  // 删除文档
  deleteDocument: (docId) => api.delete(`/knowledge/documents/${docId}/`),
}

// AI测评师API
export const evaluatorAPI = {
  // 任务列表
  list: (params) => api.get('/ai-evaluator/tasks/', { params }),
  // 创建任务（含问题列表）
  createTask: (data) => api.post('/ai-evaluator/tasks/create_task/', data),
  // 执行测评
  runEval: (data) => api.post('/ai-evaluator/tasks/run_eval/', data),
  // 获取结果列表
  getResults: (taskId, params) => api.get(`/ai-evaluator/tasks/${taskId}/results/`, { params }),
  // 获取题目列表
  getQuestions: (taskId) => api.get(`/ai-evaluator/tasks/${taskId}/questions/`),
  // 获取统计
  getStatistics: (taskId) => api.get(`/ai-evaluator/tasks/${taskId}/statistics/`),
  // 获取报告
  getReport: (taskId) => api.get(`/ai-evaluator/tasks/${taskId}/report/`),
  // 导出CSV
  exportCSV: (taskId) => api.get(`/ai-evaluator/tasks/${taskId}/export_csv/`, { responseType: 'blob' }),
  // 删除任务
  deleteTask: (taskId) => api.post(`/ai-evaluator/tasks/${taskId}/delete_task/`),
  // 批量删除
  batchDelete: (taskIds) => api.post('/ai-evaluator/tasks/batch_delete/', { task_ids: taskIds }),
  // 更新任务
  updateTask: (taskId, data) => api.put(`/ai-evaluator/tasks/${taskId}/`, data),
  // 汇总
  summary: () => api.get('/ai-evaluator/tasks/summary/'),
  // AI自动生成测评问题
  generateQuestions: (data) => api.post('/ai-evaluator/tasks/generate_questions/', data),
  // 重置卡死的执行中任务
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
  // 获取可用（启用）的模型列表 — 供创建任务下拉用
  active: () => api.get('/ai-evaluator/models/active/'),
  // 测试连接
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
  // 用例 CRUD
  listTestCases: (params) => api.get('/performance/', { params }),
  getTestCase: (id) => api.get(`/performance/${id}/`),
  createTestCase: (data) => api.post('/performance/', data),
  updateTestCase: (id, data) => api.put(`/performance/${id}/`, data),
  deleteTestCase: (id) => api.delete(`/performance/${id}/`),
  getTestCaseExecutions: (id) => api.get(`/performance/${id}/executions/`),

  // 执行
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

export default api
