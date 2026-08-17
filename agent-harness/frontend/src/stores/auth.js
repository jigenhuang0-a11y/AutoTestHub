import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authAPI } from '@/api'
import { ElMessage } from 'element-plus'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  const accessToken = ref(localStorage.getItem('access_token') || '')
  const refreshToken = ref(localStorage.getItem('refresh_token') || '')

  const isAuthenticated = computed(() => !!accessToken.value)

  const login = async (username, password) => {
    try {
      const response = await authAPI.login({ username, password })
      const token = response.access || response.access_token
      const refresh = response.refresh || response.refresh_token || ''
      const userPayload = response.user || {
        id: response.id || response.user_id,
        user_id: response.user_id,
        username: response.username,
        role: response.role,
        email: response.email,
      }
      if (!token) {
        throw new Error('服务端未返回有效的访问令牌')
      }

      accessToken.value = token
      refreshToken.value = refresh
      user.value = userPayload
      localStorage.setItem('access_token', token)
      localStorage.setItem('refresh_token', refresh)
      localStorage.setItem('user', JSON.stringify(userPayload))
      ElMessage.success('登录成功')
      await router.push({ path: '/workbench', query: { domain: 'test' } })
    } catch (error) {
      const msg = error?.response?.data?.detail || error?.message || '登录失败，请检查用户名和密码'
      ElMessage.error(msg)
      throw error
    }
  }

  const logout = (silent = false) => {
    accessToken.value = ''
    refreshToken.value = ''
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
    router.push('/login')
    if (!silent) ElMessage.success('已退出登录')
  }

  const fetchProfile = async () => {
    try {
      const profile = await authAPI.getProfile()
      // 后端 /auth/profile 返回 { user: {...} }，需解包
      user.value = profile?.user || profile || null
      if (user.value) localStorage.setItem('user', JSON.stringify(user.value))
    } catch (error) {
      console.error('Failed to fetch profile:', error)
      throw error
    }
  }

  // 应用启动时调用：恢复持久化身份，并确保 user 至少包含 role
  const initialize = async () => {
    const token = localStorage.getItem('access_token')
    const storedUser = localStorage.getItem('user')
    if (token) {
      accessToken.value = token
      refreshToken.value = localStorage.getItem('refresh_token') || ''
    }
    if (storedUser) {
      try {
        const parsed = JSON.parse(storedUser)
        if (parsed && parsed.role) {
          user.value = parsed
          return
        }
      } catch (e) {
        console.warn('Failed to parse stored user:', e)
        localStorage.removeItem('user')
      }
    }
    // 有 token 但无有效 user 信息时，主动拉取 profile
    if (token) {
      try {
        await fetchProfile()
      } catch (error) {
        console.error('Initialize fetchProfile failed:', error)
      }
    }
  }

  return {
    user,
    accessToken,
    refreshToken,
    isAuthenticated,
    login,
    logout,
    fetchProfile,
    initialize,
  }
})
