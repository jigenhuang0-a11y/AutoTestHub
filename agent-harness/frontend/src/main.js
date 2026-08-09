import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'

// 导入全局组件
import TableSkeleton from './components/TableSkeleton.vue'
import EmptyState from './components/EmptyState.vue'

const app = createApp(App)
const pinia = createPinia()

// 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 注册全局组件
app.component('TableSkeleton', TableSkeleton)
app.component('EmptyState', EmptyState)

app.use(pinia)

// 在挂载前恢复登录态：防止刷新后 adminOnly 路由因 user 缺失被误拦截
const authStore = useAuthStore()
await authStore.initialize()

app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')
