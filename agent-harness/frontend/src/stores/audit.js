/**
 * 审计事件 Store
 * 
 * 从后端 /api/v1/audit/events 拉取真实审计数据，
 * 并提供 computed 统计数据供 AuditDashboard 和 TaskMonitor 使用
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/api'

export const useAuditStore = defineStore('audit', () => {
  const events = ref([])
  const loading = ref(false)
  const error = ref(null)

  // 从后端获取审计事件
  async function fetchEvents(limit = 200) {
    loading.value = true
    error.value = null
    try {
      const { data } = await api.get('/audit/events', { params: { limit } })
      // 后端返回格式: { success: true, data: { events: [...] } }
      const raw = data.data?.events || data.events || data.results || data
      events.value = Array.isArray(raw) ? raw : []
    } catch (e) {
      console.error('获取审计事件失败:', e)
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  // ---- 统计指标 ----
  const totalEvents = computed(() => events.value.length)

  const todayEvents = computed(() => {
    const today = new Date().toISOString().slice(0, 10)
    return events.value.filter(e => {
      const t = e.timestamp || e.created_at || e.time
      return t && t.startsWith(today)
    }).length
  })

  const riskDist = computed(() => {
    let safe = 0, warning = 0, dangerous = 0
    for (const e of events.value) {
      const s = (e.safety_level || e.severity || e.risk_level || '').toLowerCase()
      if (s === 'dangerous' || s === 'high' || s === 'error' || s === 'critical') dangerous++
      else if (s === 'warning' || s === 'warn' || s === 'medium') warning++
      else safe++
    }
    return { safe, warning, dangerous }
  })

  // 7天趋势
  const trendData = computed(() => {
    const labels = []
    const passed = []
    const blocked = []
    const now = new Date()
    for (let i = 6; i >= 0; i--) {
      const d = new Date(now)
      d.setDate(d.getDate() - i)
      const key = d.toISOString().slice(0, 10)
      labels.push(key.slice(5)) // MM-DD
      const dayEvents = events.value.filter(e => {
        const t = e.timestamp || e.created_at || e.time || ''
        return t.startsWith(key)
      })
      passed.push(dayEvents.filter(e => (e.severity || '') !== 'dangerous').length)
      blocked.push(dayEvents.filter(e => (e.severity || '') === 'dangerous').length)
    }
    return { labels, passed, blocked }
  })

  // 状态分布
  const statusDist = computed(() => {
    let success = 0, failed = 0, blocked = 0
    for (const e of events.value) {
      const s = (e.status || '').toLowerCase()
      if (s === 'success' || s === 'ok' || s === 'passed') success++
      else if (s === 'blocked' || s === 'dangerous') blocked++
      else failed++
    }
    return { success, failed, blocked }
  })

  return {
    events, loading, error,
    fetchEvents,
    totalEvents, todayEvents, riskDist, trendData, statusDist,
  }
})
