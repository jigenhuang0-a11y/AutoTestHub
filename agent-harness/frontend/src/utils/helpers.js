import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'

export const showSuccess = (message = '操作成功') => {
  ElMessage.success(message)
}

export const showError = (message = '操作失败') => {
  ElMessage.error(message)
}

export const showWarning = (message = '请注意') => {
  ElMessage.warning(message)
}

export const showConfirm = (message = '确定要执行此操作吗？', title = '提示') => {
  return ElMessageBox.confirm(message, title, {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
}

export const showDeleteConfirm = (message = '确定要删除吗？此操作不可恢复') => {
  return ElMessageBox.confirm(message, '删除确认', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'error',
    confirmButtonClass: 'el-button--danger',
  })
}

export const createLoading = (options = {}) => {
  return ElLoading.service({
    lock: true,
    text: options.text || '加载中...',
    background: 'rgba(255, 255, 255, 0.7)',
    ...options,
  })
}

export const formatDate = (dateStr, format = 'YYYY-MM-DD HH:mm:ss') => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return format
    .replace('YYYY', year)
    .replace('MM', month)
    .replace('DD', day)
    .replace('HH', hours)
    .replace('mm', minutes)
    .replace('ss', seconds)
}

export const debounce = (func, delay = 300) => {
  let timer = null
  return function (...args) {
    clearTimeout(timer)
    timer = setTimeout(() => { func.apply(this, args) }, delay)
  }
}

export const throttle = (func, delay = 300) => {
  let lastTime = 0
  return function (...args) {
    const now = Date.now()
    if (now - lastTime >= delay) {
      func.apply(this, args)
      lastTime = now
    }
  }
}

export const deepClone = (obj) => {
  if (obj === null || typeof obj !== 'object') return obj
  if (obj instanceof Date) return new Date(obj.getTime())
  if (obj instanceof Array) return obj.map(item => deepClone(item))
  if (obj instanceof Object) {
    const clonedObj = {}
    for (const key in obj) {
      if (obj.hasOwnProperty(key)) {
        clonedObj[key] = deepClone(obj[key])
      }
    }
    return clonedObj
  }
}

// 保留原有函数，确保兼容性
export function formatTime(t) {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  })
}

export function formatMs(ms) {
  if (!ms) return '-'
  if (ms < 1000) return ms + 'ms'
  return (ms / 1000).toFixed(1) + 's'
}

export function formatUptime(s) {
  if (!s) return '-'
  if (s < 60) return Math.floor(s) + '秒'
  if (s < 3600) return Math.floor(s / 60) + '分' + (s % 60) + '秒'
  if (s < 86400) return Math.floor(s / 3600) + '小时'
  return Math.floor(s / 86400) + '天'
}
