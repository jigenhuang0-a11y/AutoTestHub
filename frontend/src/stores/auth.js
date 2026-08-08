import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authAPI } from '@/api'
import { ElMessage } from 'element-plus'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const accessToken = ref(localStorage.getItem('access_token') || '')
  const refreshToken = ref(localStorage.getItem('refresh_token') || '')

  const isAuthenticated = computed(() => !!accessToken.value)

  // 登录
  const login = async (username, password) => {
    try {
      const response = await authAPI.login({ username, password })
      accessToken.value = response.access
      refreshToken.value = response.refresh
      localStorage.setItem('access_token', response.access)
      localStorage.setItem('refresh_token', response.refresh)
      // 后端返回的用户字段在顶层，直接构造 user 对象
      user.value = response.user || {
        id: response.id,
        username: response.username,
        role: response.role,
        email: response.email,
      }
      ElMessage.success('登录成功')
      await router.push('/')
    } catch (error) {
      ElMessage.error('登录失败，请检查用户名和密码')
      throw error
    }
  }

  // 登出
  const logout = () => {
    accessToken.value = ''
    refreshToken.value = ''
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    router.push('/login')
    ElMessage.success('已退出登录')
  }

  // 获取用户信息
  const fetchProfile = async () => {
    try {
      const profile = await authAPI.getProfile()
      user.value = profile
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
