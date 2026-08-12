import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5174,
    strictPort: false,
    proxy: {
      '/api/knowledge': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        // 保留末尾斜杠，避免 FastAPI 307 重定向导致 fetch 丢失 Authorization header
        rewrite: (path) => path.replace(/^\/api\/(?!v1\b)/, '/api/v1/'),
      },
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        // 保留原路径末尾斜杠，避免后端 307 重定向导致 axios 跨重定向丢失 Authorization
        rewrite: (path) => path.replace(/^\/api\/(?!v1\b)/, '/api/v1/'),
      },
      '/agent': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/agent/, '/api/v1/agent'),
      },
      '/mcp': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/mcp/, '/api/v1/mcp'),
      },
      '/media': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/internal': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
})
