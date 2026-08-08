<template>
  <div class="login-container">
    <!-- AI神经网络背景 -->
    <canvas ref="neuralCanvas" class="neural-network-bg"></canvas>
    
    <!-- 粒子效果 -->
    <div class="particles">
      <div class="particle" v-for="n in 20" :key="n" :style="getParticleStyle(n)"></div>
    </div>

    <!-- 主内容区 -->
    <div class="login-wrapper">
      <!-- 左侧品牌区 -->
      <div class="brand-section">
        <div class="brand-content">
          <!-- AI大脑图标 -->
          <div class="ai-brain-wrapper">
            <div class="ai-brain">
              <svg viewBox="0 0 120 120" class="brain-svg">
                <!-- 神经网络连接 -->
                <g class="neural-connections">
                  <line x1="30" y1="30" x2="60" y2="40" stroke="#4ade80" stroke-width="2" opacity="0.6"/>
                  <line x1="60" y1="40" x2="90" y2="30" stroke="#4ade80" stroke-width="2" opacity="0.6"/>
                  <line x1="30" y1="70" x2="60" y2="60" stroke="#4ade80" stroke-width="2" opacity="0.6"/>
                  <line x1="60" y1="60" x2="90" y2="70" stroke="#4ade80" stroke-width="2" opacity="0.6"/>
                  <line x1="60" y1="40" x2="60" y2="60" stroke="#4ade80" stroke-width="2" opacity="0.6"/>
                  <line x1="30" y1="30" x2="30" y2="70" stroke="#4ade80" stroke-width="2" opacity="0.6"/>
                  <line x1="90" y1="30" x2="90" y2="70" stroke="#4ade80" stroke-width="2" opacity="0.6"/>
                </g>
                <!-- 节点 -->
                <circle cx="30" cy="30" r="6" fill="#4ade80" class="node node-1"/>
                <circle cx="60" cy="40" r="6" fill="#4ade80" class="node node-2"/>
                <circle cx="90" cy="30" r="6" fill="#4ade80" class="node node-3"/>
                <circle cx="30" cy="70" r="6" fill="#4ade80" class="node node-4"/>
                <circle cx="60" cy="60" r="6" fill="#4ade80" class="node node-5"/>
                <circle cx="90" cy="70" r="6" fill="#4ade80" class="node node-6"/>
                <!-- AI标识 -->
                <text x="60" y="58" text-anchor="middle" fill="white" font-size="16" font-weight="bold">AI</text>
              </svg>
              <!-- 脉冲环 -->
              <div class="pulse-ring"></div>
              <div class="pulse-ring pulse-ring-2"></div>
            </div>
          </div>
          
          <h1 class="brand-title">
            <span class="title-ai">AI</span>测试平台
          </h1>
          <p class="brand-subtitle">AI-Driven Testing Platform</p>
          
          <!-- 打字机效果标语 -->
          <div class="ai-typing">
            <span class="typing-text">{{ typingText }}</span>
            <span class="typing-cursor">|</span>
          </div>
          
          <div class="brand-features">
            <div class="feature-item">
              <div class="feature-icon ai-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.071 0l-.354.354a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-.354-.354z"/>
                </svg>
              </div>
              <div class="feature-content">
                <span class="feature-title">AI 用例生成</span>
                <span class="feature-desc">需求解析 + 接口分析，智能生成测试用例</span>
              </div>
            </div>
            <div class="feature-item">
              <div class="feature-icon ai-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <ellipse cx="12" cy="5" rx="8" ry="3"/>
                  <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/>
                  <path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>
                </svg>
              </div>
              <div class="feature-content">
                <span class="feature-title">数据工厂</span>
                <span class="feature-desc">测试数据生成、脱敏、版本与复用管理</span>
              </div>
            </div>
            <div class="feature-item">
              <div class="feature-icon ai-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="3"/>
                  <path d="M12 2v2M12 20v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M2 12h2M20 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
                </svg>
              </div>
              <div class="feature-content">
                <span class="feature-title">AI 测评师</span>
                <span class="feature-desc">大模型问答评测、效果打分与回归验证</span>
              </div>
            </div>
            <div class="feature-item">
              <div class="feature-icon ai-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="2" y="4" width="20" height="16" rx="3"/>
                  <path d="M6 8h4M6 12h8M6 16h5" opacity="0.6"/>
                  <circle cx="18" cy="10" r="1" fill="currentColor"/>
                </svg>
              </div>
              <div class="feature-content">
                <span class="feature-title">Web 测试</span>
                <span class="feature-desc">UI 自动化、元素定位与端到端回归</span>
              </div>
            </div>
            <div class="feature-item">
              <div class="feature-icon ai-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
                  <circle cx="12" cy="12" r="2" fill="currentColor"/>
                </svg>
              </div>
              <div class="feature-content">
                <span class="feature-title">性能测试</span>
                <span class="feature-desc">压测编排、指标采集与瓶颈定位</span>
              </div>
            </div>
            <div class="feature-item">
              <div class="feature-icon ai-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                  <circle cx="12" cy="7" r="4"/>
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" opacity="0.5"/>
                </svg>
              </div>
              <div class="feature-content">
                <span class="feature-title">质量数字人</span>
                <span class="feature-desc">7×24 值守、风险播报与质量报告</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧登录区 -->
      <div class="login-section">
        <div class="login-box">
          <div class="login-header">
            <h2>欢迎登录</h2>
            <p>请输入您的账号信息</p>
          </div>

          <el-form :model="loginForm" :rules="rules" ref="formRef" class="login-form">
            <el-form-item prop="username">
              <el-input
                v-model="loginForm.username"
                placeholder="请输入用户名"
                size="large"
                :prefix-icon="User"
                @keyup.enter="handleLogin"
              />
            </el-form-item>

            <el-form-item prop="password">
              <el-input
                v-model="loginForm.password"
                type="password"
                placeholder="请输入密码"
                size="large"
                :prefix-icon="Lock"
                show-password
                @keyup.enter="handleLogin"
              />
            </el-form-item>

            <div class="form-options">
              <el-checkbox v-model="loginForm.remember">记住密码</el-checkbox>
              <el-link type="primary" :underline="false">忘记密码？</el-link>
            </div>

            <el-form-item>
              <el-button
                type="primary"
                size="large"
                style="width: 100%"
                :loading="loading"
                @click="handleLogin"
                class="login-btn"
              >
                <span v-if="!loading">登 录</span>
                <span v-else>登录中...</span>
              </el-button>
            </el-form-item>
          </el-form>

          <div class="test-accounts">
            <div class="test-accounts-title">测试账号（点击快速填入）</div>
            <div class="account-cards">
              <div
                v-for="acc in testAccounts"
                :key="acc.username"
                class="account-card"
                @click="fillAccount(acc)"
              >
                <div class="account-role" :class="'role-' + acc.role">
                  {{ acc.roleLabel }}
                </div>
                <div class="account-cred">{{ acc.username }} / {{ acc.password }}</div>
                <div class="account-desc">{{ acc.desc }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { User, Lock, Check } from '@element-plus/icons-vue'

const authStore = useAuthStore()
const formRef = ref(null)
const loading = ref(false)
const neuralCanvas = ref(null)

const loginForm = reactive({
  username: '',
  password: '',
  remember: false,
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6位', trigger: 'blur' },
  ],
}

// 打字机效果
const typingText = ref('')
const fullText = '让AI赋能测试，提升质量保障效率'
let typingIndex = 0
let typingInterval = null

const startTyping = () => {
  typingInterval = setInterval(() => {
    if (typingIndex < fullText.length) {
      typingText.value += fullText[typingIndex]
      typingIndex++
    } else {
      clearInterval(typingInterval)
      setTimeout(() => {
        typingText.value = ''
        typingIndex = 0
        startTyping()
      }, 2000)
    }
  }, 100)
}

// 粒子样式
const getParticleStyle = (index) => {
  const size = Math.random() * 4 + 2
  const left = Math.random() * 100
  const top = Math.random() * 100
  const delay = Math.random() * 5
  const duration = Math.random() * 10 + 10
  return {
    width: `${size}px`,
    height: `${size}px`,
    left: `${left}%`,
    top: `${top}%`,
    animationDelay: `${delay}s`,
    animationDuration: `${duration}s`,
  }
}

// 神经网络背景动画
let animationId = null
const drawNeuralNetwork = () => {
  if (!neuralCanvas.value) return
  
  const canvas = neuralCanvas.value
  const ctx = canvas.getContext('2d')
  
  const resize = () => {
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight
  }
  resize()
  window.addEventListener('resize', resize)
  
  const nodes = []
  const nodeCount = 50
  
  for (let i = 0; i < nodeCount; i++) {
    nodes.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.5,
      vy: (Math.random() - 0.5) * 0.5,
      radius: Math.random() * 2 + 1,
    })
  }
  
  const animate = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    
    // 更新节点位置
    nodes.forEach(node => {
      node.x += node.vx
      node.y += node.vy
      
      if (node.x < 0 || node.x > canvas.width) node.vx *= -1
      if (node.y < 0 || node.y > canvas.height) node.vy *= -1
    })
    
    // 绘制连接线
    nodes.forEach((node, i) => {
      nodes.slice(i + 1).forEach(otherNode => {
        const dx = node.x - otherNode.x
        const dy = node.y - otherNode.y
        const distance = Math.sqrt(dx * dx + dy * dy)
        
        if (distance < 150) {
          const opacity = (1 - distance / 150) * 0.3
          ctx.beginPath()
          ctx.moveTo(node.x, node.y)
          ctx.lineTo(otherNode.x, otherNode.y)
          ctx.strokeStyle = `rgba(74, 222, 128, ${opacity})`
          ctx.lineWidth = 1
          ctx.stroke()
        }
      })
    })
    
    // 绘制节点
    nodes.forEach(node => {
      ctx.beginPath()
      ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2)
      ctx.fillStyle = 'rgba(74, 222, 128, 0.6)'
      ctx.fill()
    })
    
    animationId = requestAnimationFrame(animate)
  }
  
  animate()
}

onMounted(() => {
  startTyping()
  drawNeuralNetwork()
})

onUnmounted(() => {
  if (typingInterval) clearInterval(typingInterval)
  if (animationId) cancelAnimationFrame(animationId)
})

const testAccounts = [
  { username: 'admin', password: 'admin123456', role: 'admin', roleLabel: '管理员', desc: '全部数据、管理用户' },
  { username: 'debug_user', password: 'admin123456', role: 'tester', roleLabel: '测试工程师', desc: '仅自己的数据（隔离验证）' },
]

const fillAccount = (acc) => {
  loginForm.username = acc.username
  loginForm.password = acc.password
}

const handleLogin = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        await authStore.login(loginForm.username, loginForm.password)
      } catch (error) {
        console.error('Login error:', error)
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style scoped>
.login-container {
  position: relative;
  width: 100%;
  height: 100vh;
  overflow: hidden;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
}

/* 神经网络画布 */
.neural-network-bg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
}

/* 粒子效果 */
.particles {
  position: absolute;
  width: 100%;
  height: 100%;
  z-index: 1;
  pointer-events: none;
}

.particle {
  position: absolute;
  background: rgba(74, 222, 128, 0.4);
  border-radius: 50%;
  animation: float-particle infinite linear;
}

@keyframes float-particle {
  0% {
    transform: translateY(0) translateX(0);
    opacity: 0;
  }
  10% {
    opacity: 1;
  }
  90% {
    opacity: 1;
  }
  100% {
    transform: translateY(-100vh) translateX(20px);
    opacity: 0;
  }
}

/* 主内容区 */
.login-wrapper {
  position: relative;
  z-index: 2;
  display: flex;
  width: 100%;
  height: 100%;
}

/* 左侧品牌区 */
.brand-section {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px;
  color: white;
}

.brand-content {
  max-width: 500px;
}

/* AI大脑图标 */
.ai-brain-wrapper {
  margin-bottom: 40px;
}

.ai-brain {
  position: relative;
  width: 120px;
  height: 120px;
  margin: 0 auto;
}

.brain-svg {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 0 20px rgba(74, 222, 128, 0.5));
}

.neural-connections line {
  animation: pulse-line 2s infinite;
}

.node {
  animation: pulse-node 2s infinite;
}

.node-1 { animation-delay: 0s; }
.node-2 { animation-delay: 0.2s; }
.node-3 { animation-delay: 0.4s; }
.node-4 { animation-delay: 0.6s; }
.node-5 { animation-delay: 0.8s; }
.node-6 { animation-delay: 1s; }

@keyframes pulse-line {
  0%, 100% {
    opacity: 0.3;
  }
  50% {
    opacity: 0.8;
  }
}

@keyframes pulse-node {
  0%, 100% {
    r: 6;
    opacity: 0.6;
  }
  50% {
    r: 8;
    opacity: 1;
  }
}

.pulse-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100%;
  height: 100%;
  border: 2px solid rgba(74, 222, 128, 0.4);
  border-radius: 50%;
  animation: pulse-expand 2s infinite;
}

.pulse-ring-2 {
  animation-delay: 1s;
}

@keyframes pulse-expand {
  0% {
    width: 100%;
    height: 100%;
    opacity: 1;
  }
  100% {
    width: 200%;
    height: 200%;
    opacity: 0;
  }
}

.brand-title {
  font-size: 42px;
  font-weight: 700;
  margin: 0 0 12px 0;
  letter-spacing: 2px;
  text-align: center;
}

.title-ai {
  background: linear-gradient(135deg, #4ade80 0%, #22d3ee 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.brand-subtitle {
  font-size: 16px;
  opacity: 0.7;
  margin: 0 0 20px 0;
  letter-spacing: 1px;
  text-align: center;
}

/* 打字机效果 */
.ai-typing {
  text-align: center;
  margin-bottom: 40px;
  height: 24px;
}

.typing-text {
  font-size: 18px;
  color: #4ade80;
  font-weight: 500;
}

.typing-cursor {
  font-size: 18px;
  color: #4ade80;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% {
    opacity: 1;
  }
  51%, 100% {
    opacity: 0;
  }
}

.brand-features {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
  max-width: 560px;
  width: 100%;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  border: 1px solid rgba(74, 222, 128, 0.2);
  transition: all 0.3s ease;
}

.feature-item:hover {
  background: rgba(74, 222, 128, 0.1);
  border-color: rgba(74, 222, 128, 0.4);
  transform: translateY(-3px);
}

.feature-icon {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
}

.ai-icon {
  background: rgba(74, 222, 128, 0.2);
  border-radius: 9px;
  padding: 7px;
  color: #4ade80;
}

.ai-icon svg {
  width: 100%;
  height: 100%;
}

.feature-content {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.feature-title {
  font-size: 14px;
  font-weight: 600;
}

.feature-desc {
  font-size: 12px;
  opacity: 0.7;
}

/* 右侧登录区 */
.login-section {
  width: 560px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.login-box {
  width: 100%;
  max-width: 480px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border-radius: 16px;
  padding: 48px 40px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(74, 222, 128, 0.3);
}

.login-header {
  margin-bottom: 36px;
}

.login-header h2 {
  font-size: 28px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 8px 0;
}

.login-header p {
  font-size: 14px;
  color: #666;
  margin: 0;
}

.login-form {
  margin-bottom: 0;
}

.login-form :deep(.el-input__wrapper) {
  padding: 12px 16px;
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  font-size: 14px;
}

.login-btn {
  background: linear-gradient(135deg, #4ade80 0%, #22d3ee 100%);
  border: none;
  transition: all 0.3s ease;
}

.login-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 30px rgba(74, 222, 128, 0.4);
}

.test-accounts {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #e8e8e8;
}

.test-accounts-title {
  font-size: 12px;
  color: #999;
  text-align: center;
  margin-bottom: 14px;
}

.account-cards {
  display: flex;
  gap: 10px;
}

.account-card {
  flex: 1;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  text-align: center;
}

.account-card:hover {
  background: #f0fdf4;
  border-color: #86efac;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(74, 222, 128, 0.15);
}

.account-role {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 5px;
}

.role-admin {
  background: #fef3c7;
  color: #b45309;
}

.role-tester {
  background: #dbeafe;
  color: #1d4ed8;
}

.account-cred {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 3px;
}

.account-desc {
  font-size: 11px;
  color: #94a3b8;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .brand-section {
    display: none;
  }
  
  .login-section {
    width: 100%;
  }
  
  .login-box {
    padding: 36px 32px;
  }
}

@media (max-width: 480px) {
  .login-section {
    padding: 20px;
  }
  
  .login-box {
    padding: 32px 24px;
  }
  
  .login-header h2 {
    font-size: 24px;
  }
}
</style>