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
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/(?!v1\b)/, '/api/v1/').replace(/\/$/, ''),
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
