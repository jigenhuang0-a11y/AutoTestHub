<template>
  <div class="harness-page system-settings">
    <!-- 动态背景 -->
    <div class="bg-grid"></div>
    <div class="bg-glow bg-glow-1"></div>
    <div class="bg-glow bg-glow-2"></div>

    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-title">
        <span class="title-icon">
          <el-icon><Setting /></el-icon>
        </span>
        <div>
          <h1 class="page-title">AI 测试平台 · 控制中心</h1>
          <p class="page-subtitle">模型编排 · Prompt 热更新 · RAG 知识库 · 用户权限 · 系统监控 · 通知集成</p>
        </div>
      </div>
      <div class="header-actions">
        <el-button class="tech-btn" :icon="Refresh" @click="refreshAll" :loading="loadingHealth">
          刷新状态
        </el-button>
      </div>
    </div>

    <!-- ═══════ 核心指标 Card ═══════ -->
    <div class="stats-banner">
      <div class="stat-card" v-for="(stat, idx) in platformStats" :key="idx" :style="{ '--delay': idx * 0.1 + 's' }">
        <div class="stat-glow"></div>
        <div class="stat-icon-wrap">
          <el-icon class="stat-icon"><component :is="stat.icon" /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">
            <span class="stat-num" ref="statNums">{{ stat.value }}</span>
            <span class="stat-unit">{{ stat.unit }}</span>
          </div>
          <div class="stat-label">{{ stat.label }}</div>
          <div class="stat-trend" :class="stat.trend > 0 ? 'up' : 'down'">
            <el-icon><component :is="stat.trend > 0 ? 'Top' : 'Bottom'" /></el-icon>
            {{ Math.abs(stat.trend) }}% vs 昨日
          </div>
        </div>
      </div>
    </div>

    <!-- 标签页 -->
    <el-tabs v-model="activeTab" class="settings-tabs">
      <!-- ═══════ Tab 1: 引擎配置 ═══════ -->
      <el-tab-pane label="引擎配置" name="engine">
        <div class="config-grid config-grid-3">
          <!-- 模型配置 -->
          <div class="tech-card model-card">
            <div class="card-header">
              <div class="header-left">
                <span class="card-icon"><el-icon><Cpu /></el-icon></span>
                <span class="card-title">模型引擎</span>
              </div>
              <div class="header-right-row">
                <el-tag size="small" class="count-tag">{{ models.length }} 个模型</el-tag>
                <el-button size="small" class="mini-add-btn" :icon="Plus" circle @click="addModel" />
              </div>
            </div>
            <div class="card-body">
              <el-table :data="models" size="small" row-key="name" empty-text="暂无模型配置" class="tech-table">
                <el-table-column prop="name" label="模型" width="160">
                  <template #default="{ row }">
                    <div class="model-name">
                      <span class="model-dot" :class="row.active ? 'active' : 'inactive'"></span>
                      {{ row.name }}
                    </div>
                  </template>
                </el-table-column>
                <el-table-column prop="provider" label="提供商" width="130">
                  <template #default="{ row }">
                    <span class="provider-tag">{{ row.provider }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="70">
                  <template #default="{ row }">
                    <el-switch v-model="row.active" size="small" class="tech-switch" />
                  </template>
                </el-table-column>
                <el-table-column label="Token" width="90">
                  <template #default="{ row }">
                    <span class="token-bar-wrap">
                      <span class="token-bar" :style="{ width: (row.usage_pct || 0) + '%' }"></span>
                      <span class="token-text">{{ row.usage_pct || 0 }}%</span>
                    </span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </div>

          <!-- Prompt 热更新 -->
          <div class="tech-card prompt-card">
            <div class="card-header">
              <div class="header-left">
                <span class="card-icon"><el-icon><ChatDotRound /></el-icon></span>
                <span class="card-title">Prompt 模板 · 热更新</span>
              </div>
              <el-tag size="small" class="count-tag">{{ prompts.length }} 条</el-tag>
            </div>
            <div class="card-body">
              <el-table :data="prompts" size="small" row-key="id" empty-text="暂无 Prompt 配置" class="tech-table">
                <el-table-column prop="agent_name" label="Agent" width="140">
                  <template #default="{ row }">
                    <span class="agent-name">{{ row.agent_name }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="prompt_subtype" label="场景" width="90" />
                <el-table-column label="类型" width="70">
                  <template #default="{ row }">
                    <el-tag size="small" :type="row.prompt_type === 'system' ? 'primary' : 'info'" class="type-tag">
                      {{ row.prompt_type === 'system' ? 'SYS' : 'USR' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="system_prompt" label="System Prompt" min-width="220" show-overflow-tooltip />
                <el-table-column prop="version" label="版本" width="60">
                  <template #default="{ row }">
                    <span class="version-badge">v{{ row.version }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="启用" width="65">
                  <template #default="{ row }">
                    <el-switch v-model="row.is_active" size="small" class="tech-switch" />
                  </template>
                </el-table-column>
                <el-table-column label="" width="60" fixed="right">
                  <template #default="{ row }">
                    <el-button link type="primary" size="small" class="edit-link" @click="editPrompt(row)">
                      <el-icon><Edit /></el-icon>
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </div>

          <!-- RAG 知识库 -->
          <div class="tech-card knowledge-card">
            <div class="card-header">
              <div class="header-left">
                <span class="card-icon"><el-icon><Collection /></el-icon></span>
                <span class="card-title">RAG 知识库</span>
              </div>
              <el-tag size="small" class="count-tag">{{ knowledgeBases.length }} 个库</el-tag>
            </div>
            <div class="card-body">
              <div class="kb-list" v-if="knowledgeBases.length > 0">
                <div v-for="kb in knowledgeBases" :key="kb.name" class="kb-item">
                  <div class="kb-item-left">
                    <el-icon class="kb-icon"><Document /></el-icon>
                    <div class="kb-info">
                      <div class="kb-name">{{ kb.name }}</div>
                      <div class="kb-meta">{{ kb.docs }} 文档 · {{ kb.chunks }} 片段 · {{ kb.embedding_model }}</div>
                    </div>
                  </div>
                  <div class="kb-item-right">
                    <el-tag size="small" :type="kb.status === 'ready' ? 'success' : 'warning'" class="kb-status-tag">
                      <span class="kb-dot" :class="kb.status"></span>
                      {{ kb.status === 'ready' ? '就绪' : '索引中' }}
                    </el-tag>
                    <el-progress :percentage="kb.sync_pct" :stroke-width="4" :show-text="false" class="kb-progress" />
                  </div>
                </div>
              </div>
              <div v-else class="kb-empty">
                <el-icon><FolderOpened /></el-icon>
                <span>暂无知识库，点击上方 + 新建</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 底座连接状态 -->
        <div class="tech-card status-card">
          <div class="card-header">
            <div class="header-left">
              <span class="card-icon"><el-icon><Monitor /></el-icon></span>
              <span class="card-title">底座连接状态</span>
            </div>
            <el-tag size="small" :type="healthError ? 'danger' : 'success'" class="health-tag">
              {{ healthError ? '异常' : '监控中' }}
            </el-tag>
          </div>
          <div class="card-body" v-loading="loadingHealth">
            <div class="status-grid" v-if="healthServices.length > 0">
              <div v-for="(svc, index) in healthServices" :key="svc.name" class="status-item" :class="svc.status" :style="{ '--delay': index * 0.1 + 's' }">
                <div class="status-glow"></div>
                <div class="status-icon-wrap">
                  <el-icon class="status-icon" :class="svc.status">
                    <CircleCheckFilled v-if="svc.status === 'ok'" />
                    <WarningFilled v-else />
                  </el-icon>
                  <span class="status-pulse" :class="svc.status"></span>
                </div>
                <div class="status-content">
                  <div class="status-name">{{ svc.name }}</div>
                  <div class="status-detail">{{ svc.detail }}</div>
                </div>
                <div class="status-arrow">
                  <el-icon><ArrowRight /></el-icon>
                </div>
              </div>
            </div>
            <div v-else-if="!loadingHealth && !healthError" class="health-empty">
              <el-icon><InfoFilled /></el-icon>
              <span>点击刷新检查底座服务连接状态</span>
            </div>
            <div v-if="healthError" class="health-error">
              <el-icon><WarningFilled /></el-icon>
              <span>{{ healthError }}</span>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- ═══════ Tab 2: 平台监控 ═══════ -->
      <el-tab-pane label="平台监控" name="monitor">
        <div class="monitor-grid">
          <!-- 资源使用 -->
          <div class="tech-card resource-card">
            <div class="card-header">
              <div class="header-left">
                <span class="card-icon"><el-icon><Odometer /></el-icon></span>
                <span class="card-title">系统资源</span>
              </div>
              <span class="header-live">LIVE</span>
            </div>
            <div class="card-body">
              <div class="resource-bars">
                <div class="res-item" v-for="r in resources" :key="r.label">
                  <div class="res-header">
                    <span class="res-label">{{ r.label }}</span>
                    <span class="res-value" :class="r.pct > 80 ? 'danger' : r.pct > 60 ? 'warn' : ''">{{ r.pct }}%</span>
                  </div>
                  <div class="res-bar-track">
                    <div class="res-bar-fill" :class="r.pct > 80 ? 'danger' : r.pct > 60 ? 'warn' : 'ok'"
                      :style="{ width: r.pct + '%' }">

                    </div>
                  </div>
                  <div class="res-detail">{{ r.detail }}</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 任务队列 -->
          <div class="tech-card queue-card">
            <div class="card-header">
              <div class="header-left">
                <span class="card-icon"><el-icon><List /></el-icon></span>
                <span class="card-title">任务队列 · Celery</span>
              </div>
            </div>
            <div class="card-body">
              <div class="queue-grid">
                <div class="queue-item" v-for="q in taskQueues" :key="q.name">
                  <div class="queue-header">
                    <span class="queue-name">{{ q.name }}</span>
                    <span class="queue-badge" :class="q.status">{{ q.status }}</span>
                  </div>
                  <div class="queue-metrics">
                    <div class="queue-metric">
                      <span class="qm-label">等待中</span>
                      <span class="qm-value">{{ q.pending }}</span>
                    </div>
                    <div class="queue-metric">
                      <span class="qm-label">执行中</span>
                      <span class="qm-value running">{{ q.running }}</span>
                    </div>
                    <div class="queue-metric">
                      <span class="qm-label">已完成</span>
                      <span class="qm-value done">{{ q.completed }}</span>
                    </div>
                  </div>
                  <div class="queue-workers">
                    <el-icon><Avatar /></el-icon>
                    <span>{{ q.workers }} Workers</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 最近30天调用量 -->
          <div class="tech-card chart-card">
            <div class="card-header">
              <div class="header-left">
                <span class="card-icon"><el-icon><TrendCharts /></el-icon></span>
                <span class="card-title">API 调用趋势 (30天)</span>
              </div>
              <el-tag size="small" class="count-tag">今日 {{ dailyCallCount }} 次</el-tag>
            </div>
            <div class="card-body chart-body">
              <div class="mini-chart">
                <div class="chart-bars">
                  <div v-for="(day, idx) in chartData" :key="idx" class="chart-col">
                    <div class="chart-bar-wrap">
                      <div class="chart-bar" :style="{ height: day.pct + '%' }">
                        <div class="chart-bar-glow"></div>
                      </div>
                    </div>
                    <span class="chart-label">{{ day.label }}</span>
                  </div>
                </div>
              </div>
              <div class="chart-legend">
                <span class="legend-item"><span class="legend-dot call"></span> API 调用</span>
                <span class="legend-item"><span class="legend-dot success"></span> 成功率 {{ successRate }}%</span>
                <span class="legend-item"><span class="legend-dot latency"></span> P99 {{ p99Latency }}ms</span>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- ═══════ Tab 3: 用户与权限 ═══════ -->
      <el-tab-pane label="用户与权限" name="rbac">
        <div class="rbac-grid">
          <!-- 用户管理 -->
          <div class="tech-card rbac-card users-card">
            <div class="card-header">
              <div class="header-left">
                <span class="card-icon"><el-icon><User /></el-icon></span>
                <span class="card-title">用户管理</span>
              </div>
              <el-button type="primary" size="small" class="add-btn" @click="openUserDialog()">
                <el-icon><Plus /></el-icon> 新增用户
              </el-button>
            </div>
            <div class="card-body">
              <el-table :data="rbacUsers" size="small" row-key="id" v-loading="loadingUsers" empty-text="暂无用户" class="tech-table">
                <el-table-column prop="username" label="用户名" width="120">
                  <template #default="{ row }">
                    <div class="user-cell">
                      <el-avatar :size="24" class="mini-avatar">{{ (row.username?.[0] || 'U').toUpperCase() }}</el-avatar>
                      <span>{{ row.username }}</span>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column prop="email" label="邮箱" min-width="150" />
                <el-table-column label="角色" width="180">
                  <template #default="{ row }">
                    <el-tag v-for="r in row.roles" :key="r" size="small" :type="r === 'admin' ? 'danger' : r === 'tester' ? 'warning' : 'info'" class="role-tag">
                      {{ roleLabel[r] || r }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="80">
                  <template #default="{ row }">
                    <el-tag :type="row.is_active ? 'success' : 'info'" size="small" class="state-tag">
                      <span class="state-dot" :class="row.is_active ? 'active' : 'inactive'"></span>
                      {{ row.is_active ? '启用' : '禁用' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="130" fixed="right">
                  <template #default="{ row }">
                    <el-button link type="primary" size="small" class="edit-link" @click="openUserDialog(row)">
                      <el-icon><Edit /></el-icon>
                    </el-button>
                    <el-button link type="danger" size="small" class="delete-link" @click="deleteUser(row)">
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </div>

          <!-- 角色管理 + 权限 -->
          <div class="tech-card rbac-card roles-card">
            <div class="card-header">
              <div class="header-left">
                <span class="card-icon"><el-icon><Key /></el-icon></span>
                <span class="card-title">角色与权限</span>
              </div>
              <el-button type="primary" size="small" class="add-btn" @click="openRoleDialog()">
                <el-icon><Plus /></el-icon> 新增角色
              </el-button>
            </div>
            <div class="card-body">
              <el-table :data="rbacRoles" size="small" row-key="id" v-loading="loadingRoles" empty-text="暂无角色" class="tech-table">
                <el-table-column prop="name" label="角色" width="100">
                  <template #default="{ row }">
                    <el-tag size="small" :type="row.name === 'admin' ? 'danger' : row.name === 'tester' ? 'warning' : 'info'" class="role-name-tag">
                      {{ roleLabel[row.name] || row.name }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="description" label="说明" min-width="150" show-overflow-tooltip />
                <el-table-column label="用户数" width="70">
                  <template #default="{ row }">
                    <span class="user-count">{{ row.user_count || 0 }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="" width="110" fixed="right">
                  <template #default="{ row }">
                    <el-button link type="primary" size="small" class="edit-link" @click="openRoleDialog(row)">
                      <el-icon><Edit /></el-icon>
                    </el-button>
                    <el-button link type="danger" size="small" class="delete-link" @click="deleteRole(row)"
                      :disabled="['admin','tester','viewer'].includes(row.name)">
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </div>

          <!-- 可用权限说明 -->
          <div class="tech-card perm-card">
            <div class="card-header">
              <div class="header-left">
                <span class="card-icon"><el-icon><InfoFilled /></el-icon></span>
                <span class="card-title">可用权限说明</span>
              </div>
              <el-tag size="small" class="count-tag">共 {{ allPermissions.length }} 项</el-tag>
            </div>
            <div class="card-body perm-body">
              <div class="perm-grid" v-if="allPermissions.length > 0">
                <div v-for="p in allPermissions" :key="p.code" class="perm-tag" :title="p.description">
                  <span class="perm-name">{{ p.name }}</span>
                  <span class="perm-code">{{ p.code }}</span>
                </div>
              </div>
              <div v-else class="perm-empty">权限列表加载中...</div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- ═══════ Tab 4: 通知与集成 ═══════ -->
      <el-tab-pane label="通知与集成" name="integrations">
        <div class="integration-grid">
          <!-- Webhook 配置 -->
          <div class="tech-card webhook-card">
            <div class="card-header">
              <div class="header-left">
                <span class="card-icon"><el-icon><Link /></el-icon></span>
                <span class="card-title">Webhook 通知</span>
              </div>
              <div class="header-actions">
                <el-tag size="small" class="count-tag">{{ webhooks.length }} 个钩子</el-tag>
                <el-button size="small" type="primary" plain @click="openWebhookDialog()">
                  <el-icon><Plus /></el-icon> 添加
                </el-button>
              </div>
            </div>
            <div class="card-body">
              <div class="webhook-list" v-if="webhooks.length > 0">
                <div v-for="wh in webhooks" :key="wh.id" class="wh-item">
                  <div class="wh-left">
                    <span class="wh-dot" :class="wh.active ? 'active' : 'inactive'"></span>
                    <div>
                      <div class="wh-name">
                        {{ wh.name }}
                        <el-tag size="small" :type="platformType(wh.platform)" class="wh-platform-tag">{{ wh.platform }}</el-tag>
                      </div>
                      <div class="wh-url">{{ wh.url }}</div>
                    </div>
                  </div>
                  <div class="wh-right">
                    <el-switch v-model="wh.active" size="small" class="tech-switch" @change="toggleWebhook(wh)" />
                    <el-button size="small" text :loading="wh._testing" @click="testWebhook(wh)" title="发送测试通知">
                      <el-icon><Right /></el-icon>
                    </el-button>
                    <el-button size="small" text type="primary" @click="openWebhookDialog(wh)">
                      <el-icon><Edit /></el-icon>
                    </el-button>
                    <el-button size="small" text type="danger" @click="deleteWebhookConfirm(wh)">
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </div>
                </div>
              </div>
              <div v-else class="wh-empty">
                <el-icon><Connection /></el-icon>
                <span>暂无 Webhook，添加钉钉/飞书/企微通知</span>
              </div>
            </div>
          </div>

          <!-- 第三方集成 -->
          <div class="tech-card third-party-card">
            <div class="card-header">
              <div class="header-left">
                <span class="card-icon"><el-icon><Connection /></el-icon></span>
                <span class="card-title">第三方集成</span>
              </div>
            </div>
            <div class="card-body">
              <div class="tp-grid">
                <div class="tp-item" v-for="tp in thirdParties" :key="tp.name">
                  <div class="tp-icon" :style="{ background: tp.color }">
                    <el-icon><component :is="tp.icon" /></el-icon>
                  </div>
                  <div class="tp-info">
                    <div class="tp-name">{{ tp.name }}</div>
                    <div class="tp-desc">{{ tp.desc }}</div>
                  </div>
                  <el-switch v-model="tp.connected" size="small" class="tech-switch" />
                </div>
              </div>
            </div>
          </div>


        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- ═══ 对话框 ═══ -->
    <el-dialog v-model="showUserDialog" :title="editingUserId ? '编辑用户' : '新增用户'" width="480px" top="8vh" :close-on-click-modal="false" class="tech-dialog">
      <el-form label-width="80px">
        <el-form-item label="用户名" required>
          <el-input v-model="userForm.username" placeholder="登录用户名" :disabled="!!editingUserId" />
        </el-form-item>
        <el-form-item :label="editingUserId ? '新密码' : '密码'" :required="!editingUserId">
          <el-input v-model="userForm.password" type="password" show-password :placeholder="editingUserId ? '留空则不修改' : '至少6位'" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="userForm.email" placeholder="user@example.com" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="userForm.roles" multiple placeholder="选择角色" style="width: 100%">
            <el-option v-for="r in rbacRoles" :key="r.name" :label="roleLabel[r.name] || r.name" :value="r.name" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editingUserId" label="状态">
          <el-switch v-model="userForm.is_active" active-text="启用" inactive-text="禁用" class="tech-switch" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUserDialog = false">取消</el-button>
        <el-button type="primary" :loading="savingUser" @click="saveUser">
          {{ editingUserId ? '更新' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showRoleDialog" :title="editingRoleId ? '编辑角色' : '新增角色'" width="560px" top="8vh" :close-on-click-modal="false" class="tech-dialog">
      <el-form label-width="80px">
        <el-form-item label="角色名" required>
          <el-input v-model="roleForm.name" placeholder="角色标识名" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="roleForm.description" placeholder="角色描述" />
        </el-form-item>
        <el-form-item label="权限">
          <el-checkbox-group v-model="roleForm.permissions">
            <div class="perm-check-grid">
              <el-checkbox v-for="p in allPermissions" :key="p.code" :value="p.code" :label="p.code">
                <span class="perm-check-label">{{ p.name }}</span>
              </el-checkbox>
            </div>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRoleDialog = false">取消</el-button>
        <el-button type="primary" :loading="savingRole" @click="saveRole">
          {{ editingRoleId ? '更新' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showPromptDialog" title="编辑 Prompt" width="700px" top="5vh" :close-on-click-modal="false" class="tech-dialog">
      <el-form label-width="100px">
        <el-form-item label="Agent">
          <el-input :model-value="editingPrompt?.agent_name" disabled />
        </el-form-item>
        <el-form-item label="System Prompt">
          <el-input v-model="promptForm.system_prompt" type="textarea" :rows="12" />
        </el-form-item>
        <el-form-item label="User Prompt 模板">
          <el-input v-model="promptForm.user_template" type="textarea" :rows="6" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPromptDialog = false">取消</el-button>
        <el-button type="primary" :loading="savingPrompt" @click="savePrompt">保存</el-button>
      </template>
    </el-dialog>

    <!-- Webhook 编辑对话框 -->
    <el-dialog v-model="showWebhookDialog" :title="editingWebhook ? '编辑 Webhook' : '添加 Webhook'" width="520px" top="8vh" :close-on-click-modal="false" class="tech-dialog">
      <el-form label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="webhookForm.name" placeholder="例如：测试团队飞书通知" maxlength="100" />
        </el-form-item>
        <el-form-item label="平台" required>
          <el-select v-model="webhookForm.platform" placeholder="选择平台" style="width:100%">
            <el-option label="飞书 (Feishu/Lark)" value="feishu" />
            <el-option label="钉钉 (DingTalk)" value="dingtalk" />
            <el-option label="企业微信 (WeCom)" value="wecom" />
          </el-select>
          <div class="platform-hint">
            <span v-if="webhookForm.platform === 'feishu'">飞书群聊 → 设置 → 机器人 → 添加自定义机器人 → 复制 Webhook URL</span>
            <span v-else-if="webhookForm.platform === 'dingtalk'">钉钉群 → 群设置 → 智能群助手 → 添加机器人 → 自定义 → 复制 Webhook URL</span>
            <span v-else-if="webhookForm.platform === 'wecom'">企业微信群 → 群设置 → 群机器人 → 添加 → 复制 Webhook URL</span>
          </div>
        </el-form-item>
        <el-form-item label="Webhook URL" required>
          <el-input v-model="webhookForm.url" placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="webhookForm.active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showWebhookDialog = false">取消</el-button>
        <el-button type="primary" :loading="savingWebhook" @click="saveWebhook">
          {{ editingWebhook ? '更新' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  CircleCheckFilled, WarningFilled, Plus, Setting, Cpu, ChatDotRound,
  Monitor, ArrowRight, User, Key, Edit, Delete, Refresh, InfoFilled,
  Collection, Document, FolderOpened, Connection, Link, Files, Avatar,
  Odometer, List, TrendCharts, Top, Bottom, Right
} from '@element-plus/icons-vue'
import api from '@/api'

// ── 全局状态 ──
const activeTab = ref('engine')

// ── 平台统计 ──
const platformStats = ref([
  { label: '今日 API 调用', value: '1,283', unit: '次', trend: 12.5, icon: 'TrendCharts' },
  { label: '活跃 Agent', value: '5', unit: '个', trend: 0, icon: 'Cpu' },
  { label: '知识库文档', value: '3,842', unit: '篇', trend: 8.3, icon: 'Collection' },
  { label: '平均响应', value: '320', unit: 'ms', trend: -15.2, icon: 'Odometer' },
])

// ── 系统监控 ──
const resources = ref([
  { label: 'CPU', pct: 34, detail: '4 Core · 3.4 GHz' },
  { label: '内存', pct: 62, detail: '7.4 GB / 12 GB' },
  { label: '磁盘', pct: 48, detail: '120 GB / 250 GB' },
  { label: 'GPU', pct: 71, detail: 'NVIDIA A10 · 16 GB' },
])

const taskQueues = ref([
  { name: 'celery@default', status: 'active', pending: 3, running: 2, completed: 12847, workers: 4 },
  { name: 'celery@agent', status: 'active', pending: 7, running: 4, completed: 3921, workers: 4 },
  { name: 'celery@beat', status: 'active', pending: 0, running: 0, completed: 562, workers: 1 },
])

const dailyCallCount = ref(1283)
const successRate = ref(98.7)
const p99Latency = ref(850)
const chartData = ref(
  Array.from({ length: 30 }, (_, i) => ({
    label: `${i + 1}`,
    pct: Math.floor(Math.random() * 60 + 20)
  }))
)

// ── 知识库 ──
const knowledgeBases = ref([
  { name: 'API 文档库', docs: 128, chunks: 3824, embedding_model: 'text2vec-large-chinese', sync_pct: 100, status: 'ready' },
  { name: '测试用例库', docs: 3560, chunks: 28000, embedding_model: 'bge-large-zh', sync_pct: 100, status: 'ready' },
  { name: '业务知识库', docs: 154, chunks: 4600, embedding_model: 'text2vec-large-chinese', sync_pct: 72, status: 'indexing' },
])

// ── 集成 ──
// Webhook 通知（Phase 2.5）：从后端 API 加载
const webhooks = ref([])
const showWebhookDialog = ref(false)
const editingWebhook = ref(null)
const savingWebhook = ref(false)
const webhookForm = reactive({ name: '', platform: '', url: '', active: true })

function platformType(p) { return { feishu: 'success', dingtalk: 'info', wecom: 'info' }[p.toLowerCase()] || 'info' }

async function fetchWebhooks() {
  try {
    const res = await api.get('/api/v1/webhooks/', { skipErrorHandler: true })
    const data = res.data.results || []
    if (data.length > 0) {
      webhooks.value = data.map(wh => ({ ...wh, active: !!wh.active }))
    } else { throw new Error('empty') }
  } catch (e) { /* 后端不可用时留空 */ webhooks.value = [] }
}

function openWebhookDialog(wh = null) {
  editingWebhook.value = wh
  if (wh) {
    webhookForm.name = wh.name
    webhookForm.platform = wh.platform
    webhookForm.url = wh.url
    webhookForm.active = wh.active
  } else {
    webhookForm.name = ''
    webhookForm.platform = ''
    webhookForm.url = ''
    webhookForm.active = true
  }
  showWebhookDialog.value = true
}

async function saveWebhook() {
  if (!webhookForm.name || !webhookForm.platform || !webhookForm.url) {
    ElMessage.warning('请填写名称、平台和 Webhook URL')
    return
  }
  savingWebhook.value = true
  try {
    if (editingWebhook.value) {
      await api.patch(`/api/v1/webhooks/${editingWebhook.value.id}`, { ...webhookForm })
      ElMessage.success('Webhook 已更新')
    } else {
      await api.post('/api/v1/webhooks/', { ...webhookForm })
      ElMessage.success('Webhook 已添加')
    }
    showWebhookDialog.value = false
    await fetchWebhooks()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally { savingWebhook.value = false }
}

async function toggleWebhook(wh) {
  try {
    await api.patch(`/api/v1/webhooks/${wh.id}`, { active: wh.active })
  } catch (e) {
    wh.active = !wh.active
    ElMessage.error('切换失败')
  }
}

async function testWebhook(wh) {
  wh._testing = true
  try {
    const res = await api.post(`/api/v1/webhooks/${wh.id}/test`, {
      message: '这是一条来自 AI 测试平台的测试通知 🚀'
    })
    ElMessage.success(res.data.message || '测试通知发送成功')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '发送失败，请检查 URL 是否正确')
  } finally { wh._testing = false }
}

async function deleteWebhookConfirm(wh) {
  try {
    await ElMessageBox.confirm(`确定删除「${wh.name}」？`, '删除确认', { type: 'warning' })
    await api.delete(`/api/v1/webhooks/${wh.id}`)
    ElMessage.success('已删除')
    await fetchWebhooks()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

const thirdParties = ref([
  { name: 'GitLab CI', desc: '代码仓库 & CI/CD 集成', icon: 'Connection', color: 'linear-gradient(135deg, #fc6d26, #e24329)', connected: true },
  { name: 'Jenkins', desc: '构建与部署管道', icon: 'Link', color: 'linear-gradient(135deg, #d33833, #335061)', connected: true },
  { name: 'Jira', desc: '缺陷与需求追踪', icon: 'Link', color: 'linear-gradient(135deg, #0052cc, #2684ff)', connected: false },
  { name: 'Prometheus', desc: '指标采集与告警', icon: 'TrendCharts', color: 'linear-gradient(135deg, #e6522c, #f0a040)', connected: true },
])

const auditLogs = ref([
  { id: 1, time: '10:32:15', user: 'admin', action: '更新配置', actionType: 'warning', detail: '修改了 deepseek-chat 模型参数' },
  { id: 2, time: '10:28:41', user: 'zhangsan', action: '创建任务', actionType: 'primary', detail: '创建了 API 测试任务 "登录接口压测"' },
  { id: 3, time: '10:15:03', user: 'admin', action: '删除用户', actionType: 'danger', detail: '删除了用户 test_old_account' },
  { id: 4, time: '09:58:22', user: 'lisi', action: '导出报告', actionType: 'info', detail: '导出了回归测试报告 v2.3.1' },
  { id: 5, time: '09:32:10', user: 'admin', action: '热更新', actionType: 'success', detail: '热更新了 plan_agent 的 System Prompt' },
])

// ── 系统配置（已有）──
const models = ref([])
const prompts = ref([])
const healthServices = ref([])
const loadingHealth = ref(false)
const healthError = ref('')
const showPromptDialog = ref(false)
const savingPrompt = ref(false)
const editingPrompt = ref(null)
const promptForm = reactive({ system_prompt: '', user_template: '' })

// ── RBAC ──
const rbacUsers = ref([])
const rbacRoles = ref([])
const allPermissions = ref([])
const loadingUsers = ref(false)
const loadingRoles = ref(false)
const showUserDialog = ref(false)
const showRoleDialog = ref(false)
const savingUser = ref(false)
const savingRole = ref(false)
const editingUserId = ref(null)
const editingRoleId = ref(null)

const roleLabel = { admin: '管理员', tester: '测试工程师', viewer: '访客' }

const userForm = reactive({ username: '', password: '', email: '', roles: [], is_active: true })
const roleForm = reactive({ name: '', description: '', permissions: [] })

// ── 粒子样式 ──


// ── 系统配置 API ──
async function fetchHealth() {
  loadingHealth.value = true
  healthError.value = ''
  try {
    const res = await api.get('/health/', { skipErrorHandler: true })
    healthServices.value = res.data.services || []
    if (healthServices.value.length === 0) throw new Error('empty')
  } catch (e) { healthError.value = '健康检查暂不可用' } finally {
    loadingHealth.value = false
  }
}

async function fetchModels() {
  try {
    const res = await api.get('/agent/tasks/models/', { skipErrorHandler: true })
    const data = res.data.models || res.data || []
    if (data.length > 0) {
      models.value = data.map(m => ({ ...m, active: true, usage_pct: Math.floor(Math.random() * 55 + 20) }))
    } else { throw new Error('empty') }
  } catch (e) { models.value = [] }
}

async function fetchPrompts() {
  try {
    const res = await api.get('/agent/tasks/prompts/', { skipErrorHandler: true })
    const data = res.data.results || res.data.data || res.data || []
    if (data.length > 0) {
      prompts.value = data.map(p => ({ ...p, is_active: !!p.is_active }))
    } else { throw new Error('empty') }
  } catch (e) { prompts.value = [] }
}

function editPrompt(row) {
  editingPrompt.value = row
  promptForm.system_prompt = row.system_prompt || ''
  promptForm.user_prompt_template = row.user_prompt_template || ''
  showPromptDialog.value = true
}

async function savePrompt() {
  savingPrompt.value = true
  try {
    await api.put(`/agent/tasks/prompts/${editingPrompt.value.id}/`, {
      system_prompt: promptForm.system_prompt,
      user_prompt_template: promptForm.user_template,
    })
    ElMessage.success('保存成功，Prompt 已热更新')
    showPromptDialog.value = false
    fetchPrompts()
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    savingPrompt.value = false
  }
}

function addModel() {
  ElMessage.info('模型管理功能开发中')
}

// ── RBAC ──
async function fetchUsers() {
  loadingUsers.value = true
  try {
    const res = await api.get('/auth/users', { skipErrorHandler: true })
    rbacUsers.value = res.data.users || []
    if (rbacUsers.value.length === 0) throw new Error('empty')
  } catch (e) { rbacUsers.value = [] } finally {
    loadingUsers.value = false
  }
}

async function fetchRoles() {
  loadingRoles.value = true
  try {
    const res = await api.get('/auth/roles', { skipErrorHandler: true })
    rbacRoles.value = res.data.roles || []
    if (rbacRoles.value.length === 0) throw new Error('empty')
  } catch (e) { rbacRoles.value = [] } finally {
    loadingRoles.value = false
  }
}

async function fetchPermissions() {
  try {
    const res = await api.get('/auth/permissions', { skipErrorHandler: true })
    allPermissions.value = res.data.permissions || []
    if (allPermissions.value.length === 0) throw new Error('empty')
  } catch (e) { allPermissions.value = [] }
}

function openUserDialog(row) {
  if (row) {
    editingUserId.value = row.id
    userForm.username = row.username
    userForm.password = ''
    userForm.email = row.email
    userForm.roles = [...(row.roles || [])]
    userForm.is_active = row.is_active !== false
  } else {
    editingUserId.value = null
    userForm.username = ''
    userForm.password = ''
    userForm.email = ''
    userForm.roles = []
    userForm.is_active = true
  }
  showUserDialog.value = true
}

async function saveUser() {
  if (!userForm.username) { ElMessage.warning('请输入用户名'); return }
  if (!editingUserId.value && !userForm.password) { ElMessage.warning('请输入密码'); return }
  if (!editingUserId.value && userForm.password.length < 6) { ElMessage.warning('密码至少6位'); return }
  savingUser.value = true
  try {
    if (editingUserId.value) {
      await api.put(`/auth/users/${editingUserId.value}`, {
        username: userForm.username,
        password: userForm.password || undefined,
        email: userForm.email,
        roles: userForm.roles,
        is_active: userForm.is_active,
      })
      ElMessage.success('用户已更新')
    } else {
      await api.post('/auth/users', {
        username: userForm.username,
        password: userForm.password,
        email: userForm.email,
        roles: userForm.roles,
      })
      ElMessage.success('用户创建成功')
    }
    showUserDialog.value = false
    fetchUsers()
  } catch (e) {
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    savingUser.value = false
  }
}

async function deleteUser(row) {
  try { await ElMessageBox.confirm(`确认删除用户 "${row.username}"？`, '删除用户', { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }) } catch { return }
  try {
    await api.delete(`/auth/users/${row.id}`)
    ElMessage.success('用户已删除')
    fetchUsers()
  } catch (e) {
    ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
  }
}

function openRoleDialog(row) {
  if (row) {
    editingRoleId.value = row.id
    roleForm.name = row.name
    roleForm.description = row.description
    roleForm.permissions = [...(row.permissions || [])]
  } else {
    editingRoleId.value = null
    roleForm.name = ''
    roleForm.description = ''
    roleForm.permissions = []
  }
  showRoleDialog.value = true
}

async function saveRole() {
  if (!roleForm.name) { ElMessage.warning('请输入角色名'); return }
  savingRole.value = true
  try {
    if (editingRoleId.value) {
      await api.put(`/auth/roles/${editingRoleId.value}`, { name: roleForm.name, description: roleForm.description, permissions: roleForm.permissions })
      ElMessage.success('角色已更新')
    } else {
      await api.post('/auth/roles', { name: roleForm.name, description: roleForm.description, permissions: roleForm.permissions })
      ElMessage.success('角色创建成功')
    }
    showRoleDialog.value = false
    fetchRoles()
  } catch (e) {
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    savingRole.value = false
  }
}

async function deleteRole(row) {
  try { await ElMessageBox.confirm(`确认删除角色 "${row.name}"？`, '删除角色', { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }) } catch { return }
  try {
    await api.delete(`/auth/roles/${row.id}`)
    ElMessage.success('角色已删除')
    fetchRoles()
  } catch (e) {
    ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
  }
}

function refreshAll() {
  fetchHealth(); fetchModels(); fetchPrompts()
}

onMounted(() => {
  fetchModels(); fetchPrompts(); fetchHealth()
  fetchUsers(); fetchRoles(); fetchPermissions()
  fetchWebhooks()
})
</script>

<!-- 全局样式：硬压 Element Plus 表格白色 -->
<style>
.tech-table.el-table {
  --el-table-bg-color: transparent !important;
  --el-table-tr-bg-color: transparent !important;
  --el-table-header-bg-color: transparent !important;
  --el-table-row-hover-bg-color: rgba(64, 158, 255, 0.15) !important;
  --el-table-border-color: rgba(64, 158, 255, 0.15) !important;
  --el-table-text-color: #e2e8f0 !important;
  --el-table-header-text-color: #e2e8f0 !important;
  --el-table-current-row-bg-color: rgba(64, 158, 255, 0.18) !important;
  background: transparent !important;
}
.tech-table.el-table .el-table__inner-wrapper,
.tech-table.el-table .el-table__header,
.tech-table.el-table .el-table__body { background: transparent !important; }
.tech-table.el-table .el-table__header th.el-table__cell {
  background: rgba(30, 41, 59, 0.95) !important;
  color: #f1f5f9 !important;
  border-bottom: 1px solid rgba(64, 158, 255, 0.15) !important;
  font-weight: 600 !important;
}
.tech-table.el-table .el-table__body tr { background: transparent !important; }
.tech-table.el-table .el-table__body tr.el-table__row--striped td.el-table__cell { background: rgba(255, 255, 255, 0.03) !important; }
.tech-table.el-table .el-table__body td.el-table__cell {
  background: transparent !important;
  color: #e2e8f0 !important;
  border-bottom: 1px solid rgba(64, 158, 255, 0.06) !important;
}
.tech-table.el-table .el-table__body tr:hover > td.el-table__cell {
  background: rgba(64, 158, 255, 0.18) !important;
  box-shadow: inset 0 0 20px rgba(64, 158, 255, 0.05);
}
.tech-table.el-table::before { display: none; }
.tech-table.el-table .el-table__empty-text { color: #e2e8f0; }
.tech-table.el-table .el-table__expanded-cell { background: transparent !important; }
</style>

<style scoped>
/* ── 基础 ── */
.harness-page {
  background: #1a2d45;
  height: calc(100vh - 56px);
  min-height: 0;
  padding: 24px;
  color: #f1f5f9;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  overflow: auto;
  position: relative;
}

/* ── 动态背景 ── */
.bg-grid {
  position: fixed; inset: 0;
  background-image:
    linear-gradient(rgba(64, 158, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(64, 158, 255, 0.06) 1px, transparent 1px);
  background-size: 50px 50px;
  pointer-events: none; z-index: 0;
}
.bg-glow {
  position: fixed; border-radius: 50%; filter: blur(100px);
  pointer-events: none; z-index: 0; opacity: 0.3;
}
.bg-glow-1 {
  width: 600px; height: 600px;
  background: radial-gradient(circle, rgba(64, 158, 255, 0.3), transparent 70%);
  top: -200px; right: -200px;
}
.bg-glow-2 {
  width: 500px; height: 500px;
  background: radial-gradient(circle, rgba(0, 255, 136, 0.2), transparent 70%);
  bottom: -150px; left: -150px;
}


/* ── 页面头部 ── */
.page-header {
  position: relative; z-index: 1;
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 20px; padding-bottom: 16px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.15);
}
.header-title { display: flex; align-items: center; gap: 16px; }
.title-icon {
  width: 48px; height: 48px; border-radius: 12px;
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.3), rgba(96, 165, 250, 0.1));
  border: 1px solid rgba(64, 158, 255, 0.45);
  display: flex; align-items: center; justify-content: center;
  color: #7dd3fc; font-size: 24px;
  box-shadow: 0 0 30px rgba(64, 158, 255, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.12);
}
.page-title { font-size: 22px; font-weight: 700; color: #f8fafc; letter-spacing: 0.5px; margin: 0 0 4px; text-shadow: 0 0 20px rgba(64, 158, 255, 0.3); }
.page-subtitle { font-size: 12px; color: #e2e8f0; margin: 0; }
.tech-btn {
  background: rgba(64, 158, 255, 0.2) !important; border: 1px solid rgba(64, 158, 255, 0.45) !important;
  color: #7dd3fc !important;
  box-shadow: 0 0 16px rgba(64, 158, 255, 0.15); transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s;
}
.tech-btn:hover { background: rgba(64, 158, 255, 0.3) !important; box-shadow: 0 0 24px rgba(64, 158, 255, 0.35); transform: translateY(-1px); }

/* ── 核心指标 Banner ── */
.stats-banner {
  position: relative; z-index: 1;
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;
  margin-bottom: 20px;
}
.stat-card {
  position: relative;
  background: rgba(30, 41, 59, 0.95);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 14px; padding: 18px 20px;
  display: flex; align-items: center; gap: 16px;
  overflow: hidden;
  transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s;
}

.stat-glow {
  position: absolute; top: -50%; right: -30%;
  width: 120px; height: 120px;
  background: radial-gradient(circle, rgba(64, 158, 255, 0.15), transparent);
  pointer-events: none;
}
.stat-icon-wrap {
  width: 48px; height: 48px; border-radius: 12px;
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.3), rgba(96, 165, 250, 0.05));
  border: 1px solid rgba(64, 158, 255, 0.25);
  display: flex; align-items: center; justify-content: center;
  color: #7dd3fc; font-size: 22px; flex-shrink: 0;
}
.stat-info { flex: 1; min-width: 0; }
.stat-value { display: flex; align-items: baseline; gap: 4px; }
.stat-num { font-size: 24px; font-weight: 700; color: #f8fafc; font-family: 'JetBrains Mono', monospace; }
.stat-unit { font-size: 13px; color: #e2e8f0; }
.stat-label { font-size: 12px; color: #e2e8f0; margin-top: 2px; }
.stat-trend { font-size: 12px; margin-top: 6px; display: flex; align-items: center; gap: 2px; }
.stat-trend.up { color: #00ff88; }
.stat-trend.down { color: #7dd3fc; }

/* ── Tabs ── */
.settings-tabs { position: relative; z-index: 1; }
.settings-tabs :deep(.el-tabs__header) { border: none; margin-bottom: 16px; }
.settings-tabs :deep(.el-tabs__nav-wrap::after) { display: none; }
.settings-tabs :deep(.el-tabs__active-bar) { background: linear-gradient(90deg, #409eff, #00ff88); height: 2px; box-shadow: 0 0 10px rgba(64, 158, 255, 0.5); transition: none !important; }
.settings-tabs :deep(.el-tabs__item) { color: #f1f5f9; font-size: 13px; font-weight: 500; padding: 0 18px !important; height: 38px; transition: color 0.2s; }
.settings-tabs :deep(.el-tabs__item.is-active) { color: #f8fafc; text-shadow: 0 0 12px rgba(96, 165, 250, 0.6); }
.settings-tabs :deep(.el-tabs__item:hover) { color: #f1f5f9; }
.settings-tabs :deep(.el-tabs__content) { padding: 0; transition: none !important; }

/* ── 科技卡片 ── */
.tech-card {
  position: relative; z-index: 1;
  background: rgba(30, 41, 59, 0.9);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 16px;
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.08);
  overflow: hidden; transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s;
  contain: layout paint;
}
.tech-card:hover { border-color: rgba(64, 158, 255, 0.45); box-shadow: 0 8px 40px rgba(0, 0, 0, 0.35), 0 0 40px rgba(64, 158, 255, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.1); }
.tech-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(64, 158, 255, 0.6), rgba(0, 255, 136, 0.4), transparent);
  z-index: 2;
}

.card-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px; border-bottom: 1px solid rgba(64, 158, 255, 0.15);
  background: rgba(64, 158, 255, 0.03); position: relative; z-index: 3;
}
.header-left { display: flex; align-items: center; gap: 10px; }
.header-right-row { display: flex; align-items: center; gap: 8px; }
.card-icon {
  width: 30px; height: 30px; border-radius: 8px;
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.3), rgba(96, 165, 250, 0.05));
  border: 1px solid rgba(64, 158, 255, 0.25);
  display: flex; align-items: center; justify-content: center;
  color: #7dd3fc; font-size: 15px;
}
.card-title { font-size: 14px; font-weight: 600; color: #f8fafc; }
.count-tag { background: rgba(64, 158, 255, 0.15) !important; border-color: rgba(64, 158, 255, 0.3) !important; color: #7dd3fc !important; }
.mini-add-btn {
  width: 24px; height: 24px;
  background: rgba(64, 158, 255, 0.18) !important; border: 1px solid rgba(64, 158, 255, 0.3) !important; color: #7dd3fc !important;
}
.mini-add-btn:hover { background: rgba(64, 158, 255, 0.3) !important; }
.header-live {
  font-size: 10px; font-weight: 700; letter-spacing: 2px;
  color: #00ff88; background: rgba(0, 255, 136, 0.1);
  padding: 3px 8px; border-radius: 4px;
}
.card-body { padding: 14px 18px; position: relative; z-index: 3; }

/* ── 布局 ── */
.config-grid { display: grid; gap: 16px; margin-bottom: 16px; }
.config-grid-3 { grid-template-columns: 1fr 1fr 1fr; }
.model-card, .prompt-card, .knowledge-card { min-height: 340px; }
.monitor-grid { display: grid; grid-template-columns: 1fr 1fr 2fr; gap: 16px; }
.resource-card, .queue-card { min-height: 340px; }
.chart-card { min-height: 340px; }

/* ── 表格内容 ── */
.model-name { display: flex; align-items: center; gap: 8px; font-weight: 500; color: #f8fafc; }
.model-dot { width: 8px; height: 8px; border-radius: 50%; background: #94a3b8; box-shadow: 0 0 6px currentColor; transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s; }
.model-dot.active { background: #00ff88; box-shadow: 0 0 10px #00ff88; }
.model-dot.inactive { background: #e2e8f0; box-shadow: none; }
@keyframes dotPulse { 0%, 100% { box-shadow: 0 0 10px #00ff88; } 50% { box-shadow: 0 0 18px #00ff88; } }
.provider-tag { color: #f1f5f9; font-size: 12px; background: rgba(64, 158, 255, 0.06); padding: 2px 8px; border-radius: 4px; }
.token-bar-wrap { display: flex; align-items: center; gap: 8px; }
.token-bar { height: 4px; border-radius: 2px; background: linear-gradient(90deg, #409eff, #00ff88); min-width: 0; transition: width 0.6s; }
.token-text { font-size: 11px; color: #e2e8f0; white-space: nowrap; font-family: 'JetBrains Mono', monospace; }
.agent-name { color: #f8fafc; font-weight: 500; }
.type-tag { background: rgba(64, 158, 255, 0.15) !important; border-color: rgba(64, 158, 255, 0.3) !important; color: #7dd3fc !important; font-size: 11px !important; }
.version-badge { background: rgba(100, 116, 139, 0.2); color: #e2e8f0; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-family: 'JetBrains Mono', monospace; }
.edit-link { color: #7dd3fc !important; }
.edit-link:hover { color: #93c5fd !important; }
.delete-link { color: #f87171 !important; }
.delete-link:hover { color: #fca5a5 !important; }

/* ── Switch ── */
.tech-switch :deep(.el-switch__core) { border-color: #64748b !important; background: #475569 !important; }
.tech-switch.is-checked :deep(.el-switch__core) { border-color: #409eff !important; background: #409eff !important; box-shadow: 0 0 10px rgba(64, 158, 255, 0.4); }

/* ── 知识库 ── */
.kb-list { display: flex; flex-direction: column; gap: 10px; }
.kb-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; border-radius: 10px; background: rgba(30, 41, 59, 0.75); border: 1px solid rgba(64, 158, 255, 0.18); transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s; }
.kb-item:hover { border-color: rgba(64, 158, 255, 0.25); background: rgba(64, 158, 255, 0.15); }
.kb-item-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
.kb-icon { font-size: 20px; color: #7dd3fc; flex-shrink: 0; }
.kb-info { min-width: 0; }
.kb-name { font-size: 13px; font-weight: 600; color: #f8fafc; }
.kb-meta { font-size: 11px; color: #e2e8f0; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.kb-item-right { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; flex-shrink: 0; }
.kb-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 4px; }
.kb-dot.ready { background: #00ff88; box-shadow: 0 0 6px #00ff88; }
.kb-dot.indexing { background: #fbbf24; box-shadow: 0 0 6px #fbbf24; }
.kb-progress { width: 80px; }
.kb-progress :deep(.el-progress-bar__outer) { background: rgba(64, 158, 255, 0.18) !important; }
.kb-progress :deep(.el-progress-bar__inner) { background: linear-gradient(90deg, #409eff, #00ff88) !important; }
.kb-status-tag { background: rgba(0, 255, 136, 0.08) !important; border-color: rgba(0, 255, 136, 0.2) !important; color: #00ff88 !important; }
.kb-status-tag.el-tag--warning { background: rgba(251, 191, 36, 0.08) !important; border-color: rgba(251, 191, 36, 0.2) !important; color: #fbbf24 !important; }
.kb-empty { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 40px 0; color: #e2e8f0; font-size: 13px; }

/* ── 系统资源 ── */
.resource-bars { display: flex; flex-direction: column; gap: 20px; }
.res-item { }
.res-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.res-label { font-size: 13px; font-weight: 500; color: #e2e8f0; }
.res-value { font-size: 14px; font-weight: 700; color: #00ff88; font-family: 'JetBrains Mono', monospace; }
.res-value.warn { color: #fbbf24; }
.res-value.danger { color: #f87171; }
.res-bar-track { height: 8px; border-radius: 4px; background: rgba(64, 158, 255, 0.15); overflow: hidden; }
.res-bar-fill { height: 100%; border-radius: 4px; position: relative; transition: width 0.8s ease; }
.res-bar-fill.ok { background: linear-gradient(90deg, #409eff, #00ff88); }
.res-bar-fill.warn { background: linear-gradient(90deg, #fbbf24, #f59e0b); }
.res-bar-fill.danger { background: linear-gradient(90deg, #f87171, #ef4444); }
.res-bar-shimmer {
  position: absolute; top: 0; left: -100%; width: 50%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  opacity: 0.3;
}
.res-detail { font-size: 11px; color: #e2e8f0; margin-top: 4px; }

/* ── 任务队列 ── */
.queue-grid { display: flex; flex-direction: column; gap: 12px; }
.queue-item { padding: 14px; border-radius: 10px; background: rgba(30, 41, 59, 0.75); border: 1px solid rgba(64, 158, 255, 0.18); }

.queue-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.queue-name { font-size: 13px; font-weight: 600; color: #f8fafc; font-family: 'JetBrains Mono', monospace; }
.queue-badge { font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 4px; }
.queue-badge.active { color: #00ff88; background: rgba(0, 255, 136, 0.08); }
.queue-metrics { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 10px; }
.queue-metric { text-align: center; }
.qm-label { font-size: 10px; color: #e2e8f0; display: block; }
.qm-value { font-size: 16px; font-weight: 700; color: #e2e8f0; font-family: 'JetBrains Mono', monospace; }
.qm-value.running { color: #fbbf24; }
.qm-value.done { color: #00ff88; }
.queue-workers { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #e2e8f0; }

/* ── Mini 图表 ── */
.chart-body { padding: 12px 18px 14px; }
.mini-chart { margin-bottom: 12px; }
.chart-bars { display: flex; align-items: flex-end; gap: 3px; height: 120px; }
.chart-col { flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end; }
.chart-bar-wrap { width: 100%; height: 100%; display: flex; align-items: flex-end; justify-content: center; }
.chart-bar {
  width: 80%; border-radius: 3px 3px 0 0;
  background: linear-gradient(0deg, rgba(64, 158, 255, 0.6), rgba(0, 255, 136, 0.5));
  position: relative; min-height: 3px; transition: height 0.5s;
}
.chart-bar:hover { background: linear-gradient(0deg, rgba(64, 158, 255, 0.9), rgba(0, 255, 136, 0.8)); }
.chart-bar-glow {
  position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: #00ff88; box-shadow: 0 0 8px rgba(0, 255, 136, 0.4);
}
.chart-label { font-size: 9px; color: #94a3b8; margin-top: 4px; font-family: 'JetBrains Mono', monospace; }
.chart-legend { display: flex; gap: 16px; margin-top: 8px; }
.legend-item { font-size: 11px; color: #e2e8f0; display: flex; align-items: center; gap: 6px; }
.legend-dot { width: 8px; height: 8px; border-radius: 2px; }
.legend-dot.call { background: rgba(64, 158, 255, 0.7); }
.legend-dot.success { background: #00ff88; }
.legend-dot.latency { background: #fbbf24; }

/* ── 状态网格 ── */
.status-card { margin-bottom: 16px; }
.status-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; }
.status-item {
  display: flex; align-items: center; gap: 14px; padding: 16px; border-radius: 12px;
  background: rgba(30, 41, 59, 0.75); border: 1px solid rgba(64, 158, 255, 0.18);
  position: relative; overflow: hidden; transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s; cursor: pointer;
}
.status-item:hover { border-color: rgba(64, 158, 255, 0.25); transform: translateY(-3px); box-shadow: 0 12px 30px rgba(0, 0, 0, 0.3), 0 0 30px rgba(64, 158, 255, 0.18); }
.status-item.ok { border-left: 3px solid #00ff88; }
.status-item.warn { border-left: 3px solid #fbbf24; }
.status-glow { position: absolute; top: -50%; right: -50%; width: 100%; height: 100%; background: radial-gradient(circle, rgba(64, 158, 255, 0.15), transparent 70%); pointer-events: none; }
.status-icon-wrap { position: relative; width: 42px; height: 42px; display: flex; align-items: center; justify-content: center; border-radius: 10px; background: rgba(30, 41, 59, 0.9); }
.status-icon { font-size: 20px; z-index: 1; }
.status-icon.ok { color: #00ff88; }
.status-icon.warn { color: #fbbf24; }
.status-pulse { position: absolute; width: 8px; height: 8px; border-radius: 50%; top: 7px; right: 7px; z-index: 2; }
.status-pulse.ok { background: #00ff88; box-shadow: 0 0 8px rgba(0, 255, 136, 0.7); }
.status-pulse.warn { background: #fbbf24; box-shadow: 0 0 8px rgba(251, 191, 36, 0.7); }
.status-content { flex: 1; min-width: 0; }
.status-name { font-size: 13px; font-weight: 600; color: #f8fafc; margin-bottom: 2px; }
.status-detail { font-size: 11px; color: #e2e8f0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.status-arrow { color: #94a3b8; font-size: 13px; transition: color 0.3s; }
.status-item:hover .status-arrow { color: #7dd3fc; }
.health-tag { background: rgba(0, 255, 136, 0.08) !important; border-color: rgba(0, 255, 136, 0.2) !important; color: #00ff88 !important; }
.health-tag.el-tag--danger { background: rgba(248, 113, 113, 0.08) !important; border-color: rgba(248, 113, 113, 0.2) !important; color: #f87171 !important; }
.health-empty { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 40px 0; color: #e2e8f0; font-size: 13px; }
.health-error { display: flex; align-items: center; gap: 8px; margin-top: 14px; padding: 12px 16px; background: rgba(248, 113, 113, 0.08); border: 1px solid rgba(248, 113, 113, 0.2); border-radius: 8px; color: #f87171; font-size: 12px; }

/* ── RBAC ── */
.rbac-grid { display: grid; grid-template-columns: 1.2fr 1fr; gap: 16px; }
.users-card, .roles-card { min-height: 480px; }
.add-btn { background: linear-gradient(135deg, #409eff, #00ff88) !important; border: none !important; box-shadow: 0 4px 16px rgba(64, 158, 255, 0.35); transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s; font-size: 12px !important; }
.add-btn:hover { box-shadow: 0 6px 24px rgba(64, 158, 255, 0.5); transform: translateY(-1px); }
.user-cell { display: flex; align-items: center; gap: 8px; }
.mini-avatar { background: linear-gradient(135deg, #409eff, #7dd3fc) !important; color: #fff !important; font-size: 11px; font-weight: 600; }
.role-tag { margin-right: 4px; background: rgba(64, 158, 255, 0.15) !important; border-color: rgba(64, 158, 255, 0.3) !important; color: #7dd3fc !important; }
.role-tag.el-tag--danger { background: rgba(248, 113, 113, 0.08) !important; border-color: rgba(248, 113, 113, 0.2) !important; color: #f87171 !important; }
.role-tag.el-tag--warning { background: rgba(251, 191, 36, 0.08) !important; border-color: rgba(251, 191, 36, 0.2) !important; color: #fbbf24 !important; }
.state-tag { display: inline-flex; align-items: center; gap: 5px; background: rgba(0, 255, 136, 0.08) !important; border-color: rgba(0, 255, 136, 0.2) !important; color: #00ff88 !important; font-size: 11px !important; }
.state-tag.el-tag--info { background: rgba(100, 116, 139, 0.15) !important; border-color: rgba(100, 116, 139, 0.25) !important; color: #e2e8f0 !important; }
.state-dot { width: 6px; height: 6px; border-radius: 50%; background: #00ff88; box-shadow: 0 0 6px #00ff88; }
.state-dot.inactive { background: #e2e8f0; box-shadow: none; }
.role-name-tag { background: rgba(64, 158, 255, 0.15) !important; border-color: rgba(64, 158, 255, 0.3) !important; color: #7dd3fc !important; }
.role-name-tag.el-tag--danger { background: rgba(248, 113, 113, 0.08) !important; border-color: rgba(248, 113, 113, 0.2) !important; color: #f87171 !important; }
.role-name-tag.el-tag--warning { background: rgba(251, 191, 36, 0.08) !important; border-color: rgba(251, 191, 36, 0.2) !important; color: #fbbf24 !important; }
.user-count { color: #e2e8f0; font-family: 'JetBrains Mono', monospace; }

/* ── 权限 ── */
.perm-card { grid-column: 1 / -1; }
.perm-body { padding: 14px 18px; }
.perm-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.perm-tag { display: inline-flex; align-items: center; gap: 5px; padding: 5px 10px; border-radius: 6px; background: rgba(30, 41, 59, 0.9); border: 1px solid rgba(64, 158, 255, 0.18); cursor: default; transition: transform 0.2s, border-color 0.2s, background 0.2s; }
.perm-tag:hover { border-color: rgba(64, 158, 255, 0.45); background: rgba(64, 158, 255, 0.18); transform: translateY(-1px); }
.perm-name { font-size: 11px; color: #f8fafc; }
.perm-code { font-size: 9px; color: #e2e8f0; font-family: 'JetBrains Mono', monospace; background: rgba(100, 116, 139, 0.2); padding: 2px 4px; border-radius: 3px; }
.perm-empty { color: #e2e8f0; font-size: 12px; padding: 10px 0; }
.perm-check-grid { display: flex; flex-wrap: wrap; gap: 6px; max-height: 220px; overflow-y: auto; padding: 10px; background: rgba(30, 41, 59, 0.75); border: 1px solid rgba(64, 158, 255, 0.18); border-radius: 8px; }
.perm-check-label { font-size: 11px; color: #e2e8f0; }

/* ── 集成 ── */
.integration-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }


.webhook-list { display: flex; flex-direction: column; gap: 8px; }
.wh-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-radius: 10px; background: rgba(30, 41, 59, 0.8); border: 1px solid rgba(64, 158, 255, 0.2); transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s; }
.wh-item:hover { border-color: rgba(64, 158, 255, 0.3); }
.wh-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
.wh-right { display: flex; align-items: center; flex-shrink: 0; gap: 6px; }
.wh-platform-tag { margin-left: 8px; vertical-align: middle; }

.header-actions { display: flex; align-items: center; gap: 12px; }

.platform-hint {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 6px;
  line-height: 1.5;
}
.wh-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.wh-dot.active { background: #00ff88; box-shadow: 0 0 8px #00ff88; }
.wh-dot.inactive { background: #e2e8f0; }
.wh-name { font-size: 13px; font-weight: 500; color: #f8fafc; }
.wh-url { font-size: 11px; color: #e2e8f0; font-family: 'JetBrains Mono', monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 240px; }
.wh-empty { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 40px 0; color: #e2e8f0; font-size: 13px; }

.tp-grid { display: flex; flex-direction: column; gap: 8px; }
.tp-item { display: flex; align-items: center; gap: 12px; padding: 12px; border-radius: 10px; background: rgba(30, 41, 59, 0.8); border: 1px solid rgba(64, 158, 255, 0.2); transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s; }
.tp-item:hover { border-color: rgba(64, 158, 255, 0.3); }
.tp-icon { width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 16px; flex-shrink: 0; }
.tp-info { flex: 1; min-width: 0; }
.tp-name { font-size: 13px; font-weight: 500; color: #f8fafc; }
.tp-desc { font-size: 11px; color: #e2e8f0; }

/* ── 对话框 ── */
.tech-dialog :deep(.el-dialog) { background: rgba(22, 32, 50, 0.98); border: 1px solid rgba(64, 158, 255, 0.3); border-radius: 16px; box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5); }
.tech-dialog :deep(.el-dialog__header) { border-bottom: 1px solid rgba(64, 158, 255, 0.15); padding: 16px 20px; margin-right: 0; }
.tech-dialog :deep(.el-dialog__title) { color: #f8fafc; font-weight: 600; }
.tech-dialog :deep(.el-dialog__body) { color: #e2e8f0; padding: 20px; }
.tech-dialog :deep(.el-form-item__label) { color: #e2e8f0; }
.tech-dialog :deep(.el-input__wrapper),
.tech-dialog :deep(.el-textarea__inner),
.tech-dialog :deep(.el-select .el-input__wrapper) { background: rgba(7, 9, 20, 0.6) !important; border: 1px solid rgba(64, 158, 255, 0.15) !important; box-shadow: none !important; color: #e0e6f0; }
.tech-dialog :deep(.el-input__wrapper:hover),
.tech-dialog :deep(.el-textarea__inner:hover) { border-color: rgba(64, 158, 255, 0.3) !important; }
.tech-dialog :deep(.el-input__wrapper.is-focus),
.tech-dialog :deep(.el-textarea__inner:focus) { border-color: #409eff !important; box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.18) !important; }
.tech-dialog :deep(.el-checkbox__label) { color: #e2e8f0 !important; }
.tech-dialog :deep(.el-checkbox__inner) { background: rgba(30, 41, 59, 0.9) !important; border-color: rgba(64, 158, 255, 0.3) !important; }

/* ── Loading ── */
.tech-card :deep(.el-loading-mask) { background: rgba(7, 9, 20, 0.7) !important; }

/* ── 响应式 ── */
@media (max-width: 1400px) {
  .config-grid-3 { grid-template-columns: 1fr 1fr; }
  .monitor-grid { grid-template-columns: 1fr 1fr; }
  .stats-banner { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 1100px) {
  .config-grid-3 { grid-template-columns: 1fr; }
  .monitor-grid { grid-template-columns: 1fr; }
  .stats-banner { grid-template-columns: 1fr 1fr; }
  .rbac-grid { grid-template-columns: 1fr; }
  .integration-grid { grid-template-columns: 1fr; }
}
@media (max-width: 700px) {
  .stats-banner { grid-template-columns: 1fr; }
}
</style>
