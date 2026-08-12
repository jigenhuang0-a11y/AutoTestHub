<template>
  <div class="login-container">
    <!-- 神经网络背景 -->
    <canvas ref="neuralCanvas" class="neural-network-bg"></canvas>

    <!-- 粒子效果 -->
    <div class="particles">
      <div class="particle" v-for="n in 24" :key="n" :style="getParticleStyle(n)"></div>
    </div>

    <!-- 主内容区 -->
    <div class="login-wrapper">
      <!-- 左侧品牌区 -->
      <div class="brand-section">
        <div class="brand-content">
          <!-- 品牌标识 -->
          <div class="brand-hero">
            <div class="brand-mark">
              <div class="mark-core">
                <svg viewBox="0 0 48 48" class="mark-svg">
                  <circle cx="24" cy="24" r="4" fill="currentColor" />
                  <circle cx="12" cy="16" r="3" fill="currentColor" opacity="0.7" />
                  <circle cx="36" cy="16" r="3" fill="currentColor" opacity="0.7" />
                  <circle cx="12" cy="32" r="3" fill="currentColor" opacity="0.7" />
                  <circle cx="36" cy="32" r="3" fill="currentColor" opacity="0.7" />
                  <path d="M24 24 L12 16 M24 24 L36 16 M24 24 L12 32 M24 24 L36 32" stroke="currentColor" stroke-width="1.5" opacity="0.5" />
                  <circle cx="24" cy="24" r="18" fill="none" stroke="currentColor" stroke-width="1" opacity="0.25" />
                </svg>
                <div class="mark-orbit"></div>
              </div>
            </div>

            <h1 class="brand-title">
              AI<span class="title-accent">效能中台</span>
            </h1>
            <p class="brand-subtitle">企业大模型应用质量管控与研发效能一体化平台</p>
          </div>

          <!-- 打字机效果标语 -->
          <div class="ai-typing">
            <span class="typing-text">{{ typingText }}</span>
            <span class="typing-cursor">|</span>
          </div>

          <!-- 动态拓扑可视化 -->
          <div class="topology-panel">
            <div class="topology-header">
              <span class="topology-dot"></span>
              <span class="topology-title">实时编排拓扑</span>
              <span class="topology-status">运行中</span>
            </div>
            <canvas ref="topologyCanvas" class="topology-canvas"></canvas>
            <div class="topology-metrics">
              <div class="metric">
                <span class="metric-value">{{ topoMetrics.nodes }}</span>
                <span class="metric-label">活跃节点</span>
              </div>
              <div class="metric">
                <span class="metric-value">{{ topoMetrics.links }}</span>
                <span class="metric-label">链路连接</span>
              </div>
              <div class="metric">
                <span class="metric-value">{{ topoMetrics.tps }}</span>
                <span class="metric-label">调用/s</span>
              </div>
            </div>
          </div>

          <!-- 核心能力 Bento 网格 -->
          <div class="capability-grid">
            <div class="capability-card">
              <div class="capability-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <circle cx="12" cy="12" r="3"/>
                  <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
                </svg>
              </div>
              <div class="capability-body">
                <span class="capability-title">AI 底座</span>
                <span class="capability-desc">模型管理 / 权限控制 / 配额分配</span>
              </div>
            </div>

            <div class="capability-card">
              <div class="capability-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                  <path d="M8 7h8M8 11h5" opacity="0.5"/>
                </svg>
              </div>
              <div class="capability-body">
                <span class="capability-title">知识中枢</span>
                <span class="capability-desc">RAG 检索增强 / 答案溯源 / 多轮记忆</span>
              </div>
            </div>

            <div class="capability-card">
              <div class="capability-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
                  <rect x="9" y="3" width="6" height="4" rx="1"/>
                  <path d="M9 14l2 2 4-4"/>
                </svg>
              </div>
              <div class="capability-body">
                <span class="capability-title">全链路评测</span>
                <span class="capability-desc">Golden Dataset / Judge LLM / 多维度评分</span>
              </div>
            </div>

            <div class="capability-card">
              <div class="capability-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <circle cx="12" cy="12" r="3"/>
                  <circle cx="5" cy="8" r="2" opacity="0.7"/>
                  <circle cx="19" cy="8" r="2" opacity="0.7"/>
                  <circle cx="5" cy="16" r="2" opacity="0.7"/>
                  <circle cx="19" cy="16" r="2" opacity="0.7"/>
                  <path d="M12 12L5 8M12 12l7-4M12 12l-7 4M12 12l7 4" opacity="0.5"/>
                </svg>
              </div>
              <div class="capability-body">
                <span class="capability-title">需求评审师</span>
                <span class="capability-desc">智能问答 / 测试报告 / 质量洞察</span>
              </div>
            </div>

            <div class="capability-card">
              <div class="capability-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                  <line x1="12" y1="18" x2="12" y2="12"/>
                  <line x1="9" y1="15" x2="15" y2="15"/>
                </svg>
              </div>
              <div class="capability-body">
                <span class="capability-title">用例生成</span>
                <span class="capability-desc">AI 用例生成 / 测试数据工厂 / MCP 自动化</span>
              </div>
            </div>

            <div class="capability-card">
              <div class="capability-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
                  <path d="M9 3v9M15 12V3" opacity="0.4"/>
                </svg>
              </div>
              <div class="capability-body">
                <span class="capability-title">可观测 Trace</span>
                <span class="capability-desc">全链路追踪 / 耗时分析 / Token 成本监控</span>
              </div>
            </div>
          </div>

          <!-- 技术关键词云（装饰性） -->
          <div class="tech-cloud">
            <span class="tech-tag">Harness</span>
            <span class="tech-tag">RAG</span>
            <span class="tech-tag">Judge</span>
            <span class="tech-tag">Trace</span>
            <span class="tech-tag">Sandbox</span>
            <span class="tech-tag">Observability</span>
            <span class="tech-tag">Eval</span>
            <span class="tech-tag">Golden Dataset</span>
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
              <el-link type="primary" :underline="false" @click="forgotPassword">忘记密码？</el-link>
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
            <div class="test-accounts-title">演示账号（点击快速填入）</div>
            <div class="account-cards">
              <div
                v-for="acc in testAccounts"
                :key="acc.username"
                class="account-card"
                :class="{ 'account-card-disabled': acc.disabled }"
                @click="fillAccount(acc)"
              >
                <div class="account-role" :class="'role-' + acc.role">
                  {{ acc.roleLabel }}
                  <span v-if="acc.disabled" class="disabled-badge">暂时关闭</span>
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
import { User, Lock } from '@element-plus/icons-vue'
import { storage } from '@/utils/storage'

const authStore = useAuthStore()
const formRef = ref(null)
const loading = ref(false)
const neuralCanvas = ref(null)
const topologyCanvas = ref(null)

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
const fullText = '统一底座 · 评测闭环 · 测试协同 · 可观测治理'
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
      }, 2500)
    }
  }, 100)
}

// 粒子样式
const getParticleStyle = (index) => {
  const size = Math.random() * 3 + 1
  const left = Math.random() * 100
  const top = Math.random() * 100
  const delay = Math.random() * 6
  const duration = Math.random() * 12 + 12
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
  const nodeCount = 40

  for (let i = 0; i < nodeCount; i++) {
    nodes.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.35,
      vy: (Math.random() - 0.5) * 0.35,
      radius: Math.random() * 1.5 + 0.5,
    })
  }

  const animate = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    nodes.forEach(node => {
      node.x += node.vx
      node.y += node.vy

      if (node.x < 0 || node.x > canvas.width) node.vx *= -1
      if (node.y < 0 || node.y > canvas.height) node.vy *= -1
    })

    nodes.forEach((node, i) => {
      nodes.slice(i + 1).forEach(otherNode => {
        const dx = node.x - otherNode.x
        const dy = node.y - otherNode.y
        const distance = Math.sqrt(dx * dx + dy * dy)

        if (distance < 150) {
          const opacity = (1 - distance / 150) * 0.14
          ctx.beginPath()
          ctx.moveTo(node.x, node.y)
          ctx.lineTo(otherNode.x, otherNode.y)
          ctx.strokeStyle = `rgba(167, 139, 250, ${opacity})`
          ctx.lineWidth = 1
          ctx.stroke()
        }
      })
    })

    nodes.forEach(node => {
      ctx.beginPath()
      ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2)
      ctx.fillStyle = 'rgba(167, 139, 250, 0.4)'
      ctx.fill()
    })

    animationId = requestAnimationFrame(animate)
  }

  animate()
}

// 拓扑可视化
const topoMetrics = reactive({ nodes: 8, links: 20, tps: '—' })
let topologyAnimationId = null
let topologyMetricsInterval = null

const drawTopology = () => {
  if (!topologyCanvas.value) return

  const canvas = topologyCanvas.value
  const ctx = canvas.getContext('2d')
  const panel = canvas.parentElement

  let width = 0
  let height = 0
  let cx = 0
  let cy = 0
  let nodes = []
  let links = []
  let centerNode = null
  const packets = []

  const resize = () => {
    const rect = canvas.getBoundingClientRect()
    const dpr = window.devicePixelRatio || 1
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  }

  const buildTopology = () => {
    width = canvas.clientWidth
    height = canvas.clientHeight
    cx = width / 2
    cy = height / 2

    const nodesPerLayer = [3, 5, 4]
    const layerRadius = [height * 0.18, height * 0.32, height * 0.46]
    nodes = []
    let id = 0

    for (let l = 0; l < 3; l++) {
      const count = nodesPerLayer[l]
      const radius = layerRadius[l]
      for (let i = 0; i < count; i++) {
        const angle = (i / count) * Math.PI * 2 - Math.PI / 2 + l * 0.35
        nodes.push({
          id: id++,
          x: cx + Math.cos(angle) * radius,
          y: cy + Math.sin(angle) * radius,
          radius: l === 1 ? 5 : 4,
          layer: l,
          angle,
          speed: 0.002 + Math.random() * 0.003,
          pulse: Math.random() * Math.PI * 2,
        })
      }
    }

    centerNode = { id: id++, x: cx, y: cy, radius: 7, layer: -1, pulse: 0 }
    nodes.push(centerNode)

    links = []
    nodes.forEach(a => {
      if (a.layer === -1) return
      nodes.forEach(b => {
        if (a.id >= b.id) return
        if (a.layer === b.layer) {
          const diff = Math.abs(a.angle - b.angle)
          if (diff < 1.2 || diff > Math.PI * 2 - 1.2) {
            links.push({ from: a, to: b, opacity: 0.15 })
          }
        } else if (Math.abs(a.layer - b.layer) === 1) {
          const dx = a.x - b.x
          const dy = a.y - b.y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < height * 0.35) {
            links.push({ from: a, to: b, opacity: 0.22 })
          }
        }
      })
    })
  }

  resize()
  buildTopology()
  window.addEventListener('resize', () => {
    resize()
    buildTopology()
  })

  const spawnPacket = () => {
    const link = links[Math.floor(Math.random() * links.length)]
    packets.push({
      link,
      t: 0,
      speed: 0.01 + Math.random() * 0.015,
    })
  }

  const animate = () => {
    const rect = canvas.getBoundingClientRect()
    if (rect.width !== width || rect.height !== height) {
      resize()
      buildTopology()
    }

    ctx.clearRect(0, 0, width, height)

    // 旋转节点
    nodes.forEach(node => {
      if (node.layer === -1) return
      node.angle += node.speed
      const r = [height * 0.18, height * 0.32, height * 0.46][node.layer]
      node.x = cx + Math.cos(node.angle) * r
      node.y = cy + Math.sin(node.angle) * r
      node.pulse += 0.06
    })
    centerNode.pulse += 0.08

    // 连线
    links.forEach(link => {
      ctx.beginPath()
      ctx.moveTo(link.from.x, link.from.y)
      ctx.lineTo(link.to.x, link.to.y)
      ctx.strokeStyle = `rgba(167, 139, 250, ${link.opacity})`
      ctx.lineWidth = 1.2
      ctx.stroke()
    })

    // 数据包
    if (Math.random() < 0.08) spawnPacket()
    for (let i = packets.length - 1; i >= 0; i--) {
      const p = packets[i]
      p.t += p.speed
      const x = p.link.from.x + (p.link.to.x - p.link.from.x) * p.t
      const y = p.link.from.y + (p.link.to.y - p.link.from.y) * p.t
      ctx.beginPath()
      ctx.arc(x, y, 2, 0, Math.PI * 2)
      ctx.fillStyle = 'rgba(216, 180, 254, 0.9)'
      ctx.shadowColor = 'rgba(216, 180, 254, 0.8)'
      ctx.shadowBlur = 6
      ctx.fill()
      ctx.shadowBlur = 0
      if (p.t >= 1) packets.splice(i, 1)
    }

    // 节点
    nodes.forEach(node => {
      const pulse = Math.sin(node.pulse) * 0.5 + 0.5
      const pulseRadius = node.radius + pulse * 4

      ctx.beginPath()
      ctx.arc(node.x, node.y, pulseRadius, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(167, 139, 250, ${0.12 + pulse * 0.1})`
      ctx.fill()

      ctx.beginPath()
      ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2)
      ctx.fillStyle = node.layer === -1 ? '#d8b4fe' : '#a78bfa'
      ctx.fill()
    })

    topologyAnimationId = requestAnimationFrame(animate)
  }

  animate()
}

onMounted(() => {
  // 记住密码：自动填入用户名
  const remembered = storage.get('login_remembered', null)
  if (remembered) {
    loginForm.username = remembered
    loginForm.remember = true
  }

  startTyping()
  drawNeuralNetwork()
  drawTopology()

  // topology metrics 使用静态值，不再模拟随机数据
  // topologyMetricsInterval 保留以备未来接入真实数据
})

onUnmounted(() => {
  if (typingInterval) clearInterval(typingInterval)
  if (animationId) cancelAnimationFrame(animationId)
  if (topologyAnimationId) cancelAnimationFrame(topologyAnimationId)
  if (topologyMetricsInterval) clearInterval(topologyMetricsInterval)
})

const testAccounts = [
  { username: 'admin', password: 'admin123456', role: 'admin', roleLabel: '管理员', desc: '全部数据、管理用户' },
  { username: 'debug_user', password: 'admin123456', role: 'tester', roleLabel: '测试工程师', desc: 'AI 测试功能、执行任务、查看报告', disabled: true },
  { username: 'demo', password: 'demo123456', role: 'viewer', roleLabel: '访客', desc: '仅可查看效果，无管理权限' },
]

const fillAccount = (acc) => {
  if (acc.disabled) return
  loginForm.username = acc.username
  loginForm.password = acc.password
}

const handleLogin = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch (e) {
    return
  }

  loading.value = true
  try {
    // 记住密码：保存用户名到 localStorage
    if (loginForm.remember) {
      storage.set('login_remembered', loginForm.username)
    } else {
      storage.remove('login_remembered')
    }

    await authStore.login(loginForm.username, loginForm.password)
  } catch (error) {
    console.error('Login error:', error)
    // authStore.login 内部已弹出 ElMessage，避免重复提示
    if (!error?.handled) {
      ElMessage.error(error?.message || '登录失败')
    }
  } finally {
    loading.value = false
  }
}

const forgotPassword = () => {
  ElMessage({
    message: '演示环境，密码均为您设置的固定值。如遗忘请联系管理员重置。',
    type: 'info',
    duration: 5000,
    showClose: true,
  })
}
</script>

<style scoped>
.login-container {
  position: relative;
  width: 100%;
  min-height: 100dvh;
  overflow: hidden;
  background:
    radial-gradient(ellipse at 15% 10%, rgba(124, 58, 237, 0.14) 0%, transparent 50%),
    radial-gradient(ellipse at 85% 90%, rgba(99, 102, 241, 0.12) 0%, transparent 55%),
    linear-gradient(145deg, #0a0f1c 0%, #111827 45%, #0b0f1d 100%);
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
  background: rgba(167, 139, 250, 0.32);
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
    transform: translateY(-100dvh) translateX(20px);
    opacity: 0;
  }
}

/* 主内容区 */
.login-wrapper {
  position: relative;
  z-index: 2;
  display: flex;
  width: 100%;
  height: 100dvh;
  overflow: hidden;
}

/* 左侧品牌区 */
.brand-section {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px 28px;
  color: white;
  height: 100dvh;
  overflow: hidden;
}

.brand-content {
  max-width: 720px;
  width: 100%;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 品牌标识 */
.brand-hero {
  text-align: center;
  margin-bottom: 0;
  flex-shrink: 0;
}

.brand-mark {
  display: flex;
  justify-content: center;
  margin-bottom: 14px;
}

.mark-core {
  position: relative;
  width: 88px;
  height: 88px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #a78bfa;
  background: rgba(167, 139, 250, 0.08);
  border-radius: 24px;
  border: 1px solid rgba(167, 139, 250, 0.25);
  box-shadow: 0 0 40px rgba(167, 139, 250, 0.15), inset 0 0 24px rgba(167, 139, 250, 0.08);
}

.mark-svg {
  width: 44px;
  height: 44px;
  z-index: 2;
}

.mark-orbit {
  position: absolute;
  inset: 6px;
  border-radius: 18px;
  border: 1px solid rgba(167, 139, 250, 0.15);
  animation: orbit-rotate 14s linear infinite;
}

.brand-title {
  font-size: 44px;
  font-weight: 600;
  margin: 0 0 10px 0;
  letter-spacing: -1px;
  text-align: center;
  color: #f8fafc;
}

.brand-subtitle {
  font-size: 14px;
  opacity: 0.65;
  margin: 0;
  letter-spacing: 2px;
  text-align: center;
  text-transform: uppercase;
  font-weight: 500;
  color: #cbd5e1;
}

/* 打字机效果 */
.ai-typing {
  text-align: center;
  height: 24px;
  flex-shrink: 0;
}

.typing-text {
  font-size: 16px;
  color: #c4b5fd;
  font-weight: 500;
  letter-spacing: 1px;
}

.typing-cursor {
  font-size: 16px;
  color: #c4b5fd;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

/* 拓扑可视化 */
.topology-panel {
  background: rgba(255, 255, 255, 0.035);
  backdrop-filter: blur(16px);
  border-radius: 16px;
  border: 1px solid rgba(167, 139, 250, 0.18);
  padding: 16px;
  height: 340px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.25), inset 0 0 0 1px rgba(255, 255, 255, 0.04);
}

.topology-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  font-size: 14px;
  color: #cbd5e1;
  flex-shrink: 0;
}

.topology-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #22d3ee;
  box-shadow: 0 0 8px #22d3ee;
  animation: pulse-dot 2s infinite;
}

.topology-title {
  font-weight: 600;
  color: #f8fafc;
}

.topology-status {
  margin-left: auto;
  padding: 3px 12px;
  border-radius: 999px;
  background: rgba(34, 211, 238, 0.12);
  color: #22d3ee;
  font-size: 12px;
  font-weight: 600;
}

.topology-canvas {
  width: 100%;
  flex: 1;
  min-height: 0;
  border-radius: 12px;
  background:
    radial-gradient(circle at 50% 50%, rgba(99, 102, 241, 0.08) 0%, transparent 70%),
    rgba(2, 6, 23, 0.35);
  border: 1px solid rgba(148, 163, 184, 0.08);
}

.topology-metrics {
  display: flex;
  justify-content: space-around;
  margin-top: 12px;
  flex-shrink: 0;
}

.metric {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
}

.metric-value {
  font-size: 18px;
  font-weight: 700;
  color: #f8fafc;
  font-variant-numeric: tabular-nums;
}

.metric-label {
  font-size: 12px;
  color: #94a3b8;
}

/* 核心能力 Bento 网格 */
.capability-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  flex-shrink: 0;
}

.capability-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 20px 14px;
  text-align: center;
  background: rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(16px);
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.15);
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.capability-card:hover {
  background: rgba(167, 139, 250, 0.06);
  border-color: rgba(167, 139, 250, 0.35);
  transform: translateY(-2px);
  box-shadow: 0 12px 32px rgba(2, 8, 20, 0.25);
}

.capability-icon {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(167, 139, 250, 0.12);
  border-radius: 12px;
  color: #c4b5fd;
}

.capability-icon svg {
  width: 24px;
  height: 24px;
}

.capability-body {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.capability-title {
  font-size: 15px;
  font-weight: 600;
  color: #f8fafc;
}

.capability-desc {
  font-size: 12px;
  opacity: 0.6;
  color: #cbd5e1;
}

/* 技术关键词云 */
.tech-cloud {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  flex-shrink: 0;
}

.tech-tag {
  padding: 6px 13px;
  font-size: 12px;
  font-weight: 500;
  color: rgba(203, 213, 225, 0.85);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 999px;
  transition: all 0.25s ease;
  cursor: default;
}

.tech-tag:hover {
  color: #c4b5fd;
  border-color: rgba(167, 139, 250, 0.35);
  background: rgba(167, 139, 250, 0.08);
  transform: translateY(-1px);
}

/* 右侧登录区 */
.login-section {
  width: 640px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
  height: 100dvh;
  overflow-y: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.login-section::-webkit-scrollbar {
  display: none;
}

.login-box {
  width: 100%;
  max-width: 540px;
  background: rgba(248, 250, 252, 0.97);
  backdrop-filter: blur(24px);
  border-radius: 24px;
  padding: 40px 36px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.35);
  border: 1px solid rgba(167, 139, 250, 0.18);
}

.login-header {
  margin-bottom: 26px;
}

.login-header h2 {
  font-size: 28px;
  font-weight: 600;
  color: #0f172a;
  margin: 0 0 10px 0;
}

.login-header p {
  font-size: 15px;
  color: #64748b;
  margin: 0;
}

.login-form {
  margin-bottom: 0;
}

.login-form :deep(.el-input__wrapper) {
  padding: 12px 16px;
  border-radius: 14px;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
}

.login-form :deep(.el-input__inner) {
  font-size: 15px;
}

.login-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #a78bfa inset, 0 0 0 3px rgba(167, 139, 250, 0.15);
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  font-size: 14px;
}

.login-btn {
  background: linear-gradient(135deg, #7c3aed 0%, #6366f1 100%);
  border: none;
  border-radius: 14px;
  height: 46px;
  font-size: 16px;
  font-weight: 600;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.login-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(124, 58, 237, 0.35);
}

.test-accounts {
  margin-top: 22px;
  padding-top: 20px;
  border-top: 1px solid #e2e8f0;
}

.test-accounts-title {
  font-size: 13px;
  color: #94a3b8;
  text-align: center;
  margin-bottom: 12px;
}

.account-cards {
  display: flex;
  gap: 14px;
}

.account-card {
  flex: 1;
  padding: 14px 12px;
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  text-align: center;
}

.account-card:hover {
  background: #f5f3ff;
  border-color: #c4b5fd;
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(124, 58, 237, 0.12);
}

.account-card-disabled {
  opacity: 0.45;
  cursor: not-allowed;
  pointer-events: none;
}

.account-card-disabled:hover {
  background: #f8fafc;
  border-color: #e2e8f0;
  transform: none;
  box-shadow: none;
}

.disabled-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  color: #9ca3af;
  background: #f3f4f6;
  vertical-align: middle;
}

.account-role {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 8px;
}

.role-admin {
  background: #fef3c7;
  color: #b45309;
}

.role-tester {
  background: #ede9fe;
  color: #6d28d9;
}

.role-viewer {
  background: #e0f2fe;
  color: #0369a1;
}

.account-cred {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 5px;
}

.account-desc {
  font-size: 12px;
  color: #94a3b8;
}

/* 响应式设计 */
@media (max-width: 1100px) {
  .login-section {
    width: 560px;
    padding: 36px;
  }

  .login-box {
    padding: 36px 30px;
  }
}

@media (max-width: 1024px) {
  .brand-section {
    display: none;
  }

  .login-section {
    width: 100%;
  }

  .login-box {
    padding: 32px 28px;
  }
}

@media (max-width: 480px) {
  .login-section {
    padding: 20px;
  }

  .login-box {
    padding: 24px 20px;
  }

  .login-header h2 {
    font-size: 24px;
  }

  .account-cards {
    flex-direction: column;
  }
}
</style>
