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
      accessToken.value = response.access
      refreshToken.value = response.refresh
      localStorage.setItem('access_token', response.access)
      localStorage.setItem('refresh_token', response.refresh)
      user.value = response.user || {
        id: response.id,
        username: response.username,
        role: response.role,
        email: response.email,
      }
      localStorage.setItem('user', JSON.stringify(user.value))
      ElMessage.success('登录成功')
      await router.push('/workbench')
    } catch (error) {
      ElMessage.error('登录失败，请检查用户名和密码')
      throw error
    }
  }

  const logout = () => {
    accessToken.value = ''
    refreshToken.value = ''
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
    router.push('/login')
    ElMessage.success('已退出登录')
  }

  const fetchProfile = async () => {
    try {
      const profile = await authAPI.getProfile()
      // 后端 /auth/profile 返回 { user: {...} }，需解包
      user.value = profile?.user || profile || null
      if (user.value) localStorage.setItem('user', JSON.stringify(user.value))
    } catch (error) {
      console.error('Failed to fetch profile:', error)
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
  }
})
