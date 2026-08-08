<template>
  <div class="quality-checker-page">
    <div class="page-inner">
    <!-- ===== 灵宠 NPC 区域 ===== -->
    <div class="npc-area" :class="npcMoodClass">
      <div class="npc-container" @click="npcClick" @mouseenter="npcHover = true" @mouseleave="npcHover = false">
        <!-- 气泡对话 -->
        <transition name="bubble">
          <div v-if="npcBubbleVisible" class="npc-bubble" :class="npcBubbleType">
            <div class="bubble-tail"></div>
            <div class="bubble-text">{{ npcBubbleText }}</div>
          </div>
        </transition>

        <!-- 灵宠角色 (纯CSS绘制) -->
        <div class="pet-body" :class="{ 'pet-bounce': npcAnimating, 'pet-shake': npcShaking }">
          <!-- 耳朵 -->
          <div class="pet-ear left"></div>
          <div class="pet-ear right"></div>
          <!-- 头部 -->
          <div class="pet-head">
            <!-- 眼睛 -->
            <div class="pet-eye left" :class="eyeClass">
              <div class="pet-pupil"></div>
              <div v-if="npcMood === 'sad' || npcMood === 'angry'" class="pet-tear"></div>
            </div>
            <div class="pet-eye right" :class="eyeClass">
              <div class="pet-pupil"></div>
              <div v-if="npcMood === 'sad' || npcMood === 'angry'" class="pet-tear"></div>
            </div>
            <!-- 腮红 -->
            <div class="pet-blush left"></div>
            <div class="pet-blush right"></div>
            <!-- 嘴巴 -->
            <div class="pet-mouth" :class="mouthClass"></div>
            <!-- 星星装饰 (开心时) -->
            <div v-if="npcMood === 'happy'" class="pet-sparkle s1">✨</div>
            <div v-if="npcMood === 'happy'" class="pet-sparkle s2">✨</div>
          </div>
          <!-- 身体 -->
          <div class="pet-torso">
            <!-- 领结/围巾 -->
            <div class="pet-scarf"></div>
            <!-- 手 -->
            <div class="pet-hand left" :class="{ 'hand-wave': npcAnimating }"></div>
            <div class="pet-hand right" :class="{ 'hand-wave': npcAnimating }"></div>
          </div>
          <!-- 脚 -->
          <div class="pet-foot left"></div>
          <div class="pet-foot right"></div>
          <!-- 悬浮光环 (优秀时) -->
          <div v-if="npcMood === 'happy'" class="pet-halo"></div>
          <!-- 乌云 (差时) -->
          <div v-if="npcMood === 'sad' || npcMood === 'angry'" class="pet-cloud"></div>
        </div>

        <!-- 名字标签 -->
        <div class="pet-name">质检灵宠 · 小Q</div>
      </div>

      <!-- 质检仪表盘 -->
      <div class="npc-dashboard" v-if="latestTask">
        <div class="dash-item">
          <div class="dash-value" :style="{ color: scoreColor(latestTask.overall_score) }">
            {{ latestTask.overall_score }}
          </div>
          <div class="dash-label">综合评分</div>
        </div>
        <div class="dash-divider"></div>
        <div class="dash-item">
          <div class="dash-value" :style="{ color: passRateColor(latestTask.pass_rate) }">
            {{ latestTask.pass_rate }}%
          </div>
          <div class="dash-label">通过率</div>
        </div>
        <div class="dash-divider"></div>
        <div class="dash-item">
          <div class="dash-value">{{ latestTask.total_cases }}</div>
          <div class="dash-label">用例数</div>
        </div>
        <div class="dash-divider"></div>
        <div class="dash-item">
          <div class="dash-value" :class="latestTask.level">
            {{ levelEmoji(latestTask.overall_score) }}
          </div>
          <div class="dash-label">评级</div>
        </div>
      </div>
    </div>

    <!-- ===== 工具栏 ===== -->
    <div class="toolbar">
      <el-radio-group v-model="scenario" @change="handleScenarioChange">
        <el-radio-button value="general">
          <el-icon><Document /></el-icon> 功能测试
        </el-radio-button>
        <el-radio-button value="api">
          <el-icon><Connection /></el-icon> 接口测试
        </el-radio-button>
      </el-radio-group>

      <el-divider direction="vertical" />

      <el-button type="primary" @click="showUploadDialog">
        <el-icon><Upload /></el-icon> 上传用例
      </el-button>

      <el-button @click="showManualInputDialog">
        <el-icon><Edit /></el-icon> 手动录入
      </el-button>

      <el-button @click="showConfigDialog">
        <el-icon><Setting /></el-icon> 质检配置
      </el-button>

      <div class="toolbar-right">
        <el-button @click="loadTasks" :loading="loading">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
        <el-button @click="showSummaryDialog" type="success" plain>
          <el-icon><DataLine /></el-icon> 数据汇总
        </el-button>
      </div>
    </div>

    <!-- 配置面板改为弹窗 -->

    <!-- 任务列表 -->
    <div class="task-list-section">
      <div class="section-header">
        <h3 class="section-title">
          <el-icon><List /></el-icon> 质检任务列表
          <el-tag v-if="tasks.length" size="small" type="info" class="section-count-tag">{{ tasks.length }}</el-tag>
        </h3>
        <el-input
          v-model="taskSearchKeyword"
          placeholder="搜索任务名称"
          size="small"
          clearable
          class="task-search-input"
          :prefix-icon="Search"
        />
      </div>

      <div v-if="!loading && !filteredTasks.length" class="table-empty-wrap">
        <el-empty description="暂无质检任务，请上传或手动录入用例" />
      </div>

      <template v-else>
        <!-- 表格+分页 放在同一个容器里 -->
        <div class="native-table-wrap">
          <!-- 独立的 loading 遮罩（只覆盖表格，不影响分页） -->
          <div v-if="loading" class="table-loading-overlay">
            <div class="table-loading-spinner">
              <span class="spinner-icon">&#9696;</span>
              <span>加载中...</span>
            </div>
          </div>

          <table class="native-table">
            <thead>
              <tr>
                <th class="col-cb"><input type="checkbox" @change="toggleAllTasks" :checked="allSelected" /></th>
                <th class="col-name">任务名称</th>
                <th class="col-scene">场景</th>
                <th class="col-cases">用例</th>
                <th class="col-rate">通过率</th>
                <th class="col-score">评分</th>
                <th class="col-result">合格/警告/不合格</th>
                <th class="col-status">状态</th>
                <th class="col-time">创建时间</th>
                <th class="col-action">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="task in pagedTasks"
                :key="task.id"
                :class="{ 'row-selected': selectedTask && selectedTask.id === task.id }"
                @click="selectTask(task)"
              >
                <td class="col-cb" @click.stop>
                  <el-checkbox
                    :model-value="selectedTasks.some(t => t.id === task.id)"
                    @change="(val) => toggleTaskSelection(task, val)"
                  />
                </td>
                <td class="col-name" :title="task.name">{{ task.name }}</td>
                <td class="col-scene">
                  <span class="tag" :class="'tag-' + (task.scenario === 'api' ? 'success' : 'info')">
                    {{ task.scenario === 'api' ? '接口' : '功能' }}
                  </span>
                </td>
                <td class="col-cases">{{ task.total_cases }}</td>
                <td class="col-rate">
                  <div class="mini-progress">
                    <div class="mini-progress-bar" :style="{ width: task.pass_rate + '%', background: passRateColor(task.pass_rate) }"></div>
                  </div>
                  <span class="mini-progress-text">{{ task.pass_rate }}%</span>
                </td>
                <td class="col-score">
                  <span class="score-num" :style="{ color: scoreColor(task.overall_score) }">{{ task.overall_score }}</span>
                </td>
                <td class="col-result">
                  <span class="tag tag-success">{{ task.passed_cases }}</span>
                  <span class="sep">/</span>
                  <span class="tag tag-warning">{{ task.warning_cases }}</span>
                  <span class="sep">/</span>
                  <span class="tag tag-danger">{{ task.failed_cases }}</span>
                </td>
                <td class="col-status">
                  <span class="tag" :class="'tag-' + statusType(task.status)">{{ statusText(task.status) }}</span>
                </td>
                <td class="col-time">{{ formatTime(task.created_at) }}</td>
                <td class="col-action" @click.stop>
                  <button class="btn-link btn-primary" @click="viewResults(task)">查看</button>
                  <button class="btn-link btn-danger" @click="deleteTask(task)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>

          <!-- 分页（居中显示在表格下方） -->
          <div class="table-pagination-bar" v-if="filteredTasks.length > pageSize">
            <div class="native-pager">
              <span class="pager-total">共 {{ filteredTasks.length }} 条</span>
              <button class="pager-btn" :disabled="currentPage <= 1" @click="currentPage--">上一页</button>
              <button
                v-for="p in totalPages"
                :key="p"
                class="pager-btn"
                :class="{ 'pager-active': p === currentPage }"
                @click="currentPage = p"
              >{{ p }}</button>
              <button class="pager-btn" :disabled="currentPage >= totalPages" @click="currentPage++">下一页</button>
              <span class="pager-jump">
                到第 <input v-model.number="jumpPage" class="pager-input" @keyup.enter="goToPage" /> 页
              </span>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- 上传用例对话框 -->
    <el-dialog v-model="uploadDialogVisible" title="上传测试用例" width="650px" destroy-on-close>
      <div class="upload-section">
        <div class="scenario-hint">
          <el-alert :title="scenario === 'api' ? '当前模式：接口测试质检 — 将校验URL、请求方法、参数、响应断言等' : '当前模式：功能测试质检 — 将校验步骤、预期结果、前置条件等'"
                    :type="scenario === 'api' ? 'success' : 'info'" :closable="false" show-icon />
        </div>
        <el-upload ref="uploadRef" drag :auto-upload="false" :on-change="handleFileChange"
                   :limit="1" accept=".json,.csv,.xlsx,.xls" style="margin-top: 16px">
          <el-icon class="el-icon--upload" :size="48"><UploadFilled /></el-icon>
          <div class="el-upload__text">拖拽文件到此处或<em>点击上传</em></div>
          <template #tip>
            <div class="el-upload__tip">
              <div>支持 JSON (.json)、CSV (.csv)、Excel (.xlsx/.xls) 格式</div>
              <div><strong>JSON 格式：</strong>用例对象数组，如 <code>{"title":"...","steps":"...","expected":"..."}</code></div>
              <div><strong>CSV / Excel 格式：</strong>第一行为表头，如 <code>标题,步骤,预期结果,优先级</code></div>
              <div v-if="scenario === 'api'"><strong>接口测试需包含：</strong>请求地址、请求方法、请求参数、预期响应</div>
            </div>
          </template>
        </el-upload>
      </div>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmUpload" :loading="running" :disabled="!pendingFile">
          开始质检
        </el-button>
      </template>
    </el-dialog>

    <!-- 手动录入对话框 -->
    <el-dialog v-model="manualDialogVisible" title="手动录入用例" width="700px" destroy-on-close>
      <div class="scenario-hint">
        <el-alert :title="scenario === 'api' ? '当前模式：接口测试' : '当前模式：功能测试'" :type="scenario === 'api' ? 'success' : 'info'"
                  :closable="false" show-icon />
      </div>
      <div class="manual-input-area">
        <div v-for="(tc, idx) in manualCases" :key="idx" class="manual-case-card">
          <div class="case-header">
            <span class="case-index">用例 {{ idx + 1 }}</span>
            <el-button link type="danger" size="small" @click="removeManualCase(idx)"
                       :disabled="manualCases.length <= 1">删除</el-button>
          </div>

          <el-form label-position="top" size="small">
            <el-form-item label="用例标题 *" required>
              <el-input v-model="tc.title" placeholder="请输入用例/接口标题" />
            </el-form-item>
            <el-form-item label="优先级">
              <el-select v-model="tc.priority" placeholder="请选择" clearable style="width: 100%">
                <el-option label="P0 - 最高" value="P0" />
                <el-option label="P1 - 高" value="P1" />
                <el-option label="P2 - 中" value="P2" />
                <el-option label="P3 - 低" value="P3" />
              </el-select>
            </el-form-item>

            <template v-if="scenario === 'general'">
              <el-form-item label="前置条件">
                <el-input v-model="tc.precondition" type="textarea" :rows="2"
                          placeholder="如：已登录管理员账号，系统中有测试数据" />
              </el-form-item>
              <el-form-item label="测试步骤 *" required>
                <el-input v-model="tc.steps" type="textarea" :rows="3"
                          placeholder="1. 打开XX页面&#10;2. 点击XX按钮&#10;3. 输入XX数据" />
              </el-form-item>
              <el-form-item label="预期结果 *" required>
                <el-input v-model="tc.expected" type="textarea" :rows="3"
                          placeholder="1. 页面跳转至XX&#10;2. 提示操作成功&#10;3. 数据保存到数据库" />
              </el-form-item>
            </template>

            <template v-if="scenario === 'api'">
              <el-row :gutter="12">
                <el-col :span="16">
                  <el-form-item label="请求地址 *" required>
                    <el-input v-model="tc.url" placeholder="如：/api/user/login" />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="请求方法 *" required>
                    <el-select v-model="tc.method" style="width: 100%">
                      <el-option label="GET" value="GET" />
                      <el-option label="POST" value="POST" />
                      <el-option label="PUT" value="PUT" />
                      <el-option label="DELETE" value="DELETE" />
                      <el-option label="PATCH" value="PATCH" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="请求参数">
                <el-input v-model="tc.request_params" type="textarea" :rows="3"
                          placeholder='{"username": "admin", "password": "123456"} 或用文字描述参数' />
              </el-form-item>
              <el-form-item label="预期响应/断言 *" required>
                <el-input v-model="tc.expected_response" type="textarea" :rows="3"
                          placeholder='status_code=200, body.code=0, body.data.token 不为空' />
              </el-form-item>
            </template>
          </el-form>
        </div>
        <el-button @click="addManualCase" type="primary" plain style="width: 100%; margin-top: 8px">
          <el-icon><Plus /></el-icon> 添加用例
        </el-button>
      </div>
      <template #footer>
        <el-button @click="manualDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmManualInput" :loading="running">
          提交质检
        </el-button>
      </template>
    </el-dialog>

    <!-- 质检规则配置弹窗 -->
    <el-dialog v-model="configDialogVisible" title="质检规则配置" width="750px" destroy-on-close top="5vh">
      <!-- 预设规则模板 -->
      <div class="config-section">
        <div class="config-section-title">
          <span>规则模板</span>
          <el-button size="small" text type="primary" @click="loadRuleTemplate('general')">功能测试模板</el-button>
          <el-button size="small" text type="primary" @click="loadRuleTemplate('api')">接口测试模板</el-button>
          <el-button size="small" text type="primary" @click="loadRuleTemplate('finance')">金融行业模板</el-button>
        </div>
      </div>

      <el-divider style="margin: 12px 0" />

      <!-- 自定义规则列表 -->
      <div class="config-section">
        <div class="config-section-title">
          <span>检查规则（{{ checkRules.length }} 条）</span>
          <el-button size="small" type="primary" @click="addRule">
            <el-icon><Plus /></el-icon> 添加规则
          </el-button>
        </div>

        <div class="rule-list">
          <div v-for="(rule, idx) in checkRules" :key="idx" class="rule-card" :class="{ 'rule-disabled': !rule.enabled }">
            <div class="rule-header">
              <el-switch v-model="rule.enabled" size="small" />
              <span class="rule-name">{{ rule.name || '未命名规则' }}</span>
              <span class="rule-category-tag" :class="'cat-' + rule.category">{{ categoryLabel(rule.category) }}</span>
              <div class="rule-actions">
                <el-button link size="small" type="primary" @click="editRule(idx)">编辑</el-button>
                <el-button link size="small" type="danger" @click="removeRule(idx)">删除</el-button>
              </div>
            </div>
            <div class="rule-detail" v-if="rule.description">
              <span class="rule-desc">{{ rule.description }}</span>
              <span v-if="rule.weight !== undefined" class="rule-weight">权重: {{ rule.weight }}</span>
            </div>
          </div>
        </div>

        <el-empty v-if="!checkRules.length" description="暂无规则，请添加或选择模板" :image-size="60" />
      </div>

      <el-divider style="margin: 12px 0" />

      <!-- 全局参数 -->
      <div class="config-section">
        <div class="config-section-title">全局参数</div>
        <el-row :gutter="16">
          <el-col :span="12">
            <div class="config-item">
              <span>相似度阈值：</span>
              <el-slider v-model="checkConfig.duplicate_threshold" :min="0.5" :max="1.0" :step="0.05"
                         style="flex: 1; margin-left: 12px" show-input />
            </div>
          </el-col>
          <el-col :span="12">
            <div class="config-item">
              <span>合格分数线：</span>
              <el-input-number v-model="checkConfig.pass_score" :min="0" :max="100" size="small" style="margin-left: 12px; width: 120px" />
            </div>
          </el-col>
        </el-row>
      </div>

      <!-- 规则编辑弹窗 -->
      <el-dialog v-model="ruleEditVisible" :title="editingRuleIdx >= 0 ? '编辑规则' : '添加规则'" width="550px"
                 append-to-body destroy-on-close>
        <el-form :model="editingRule" label-width="90px" label-position="left" size="small">
          <el-form-item label="规则名称 *" required>
            <el-input v-model="editingRule.name" placeholder="如：标题不能为空" />
          </el-form-item>
          <el-form-item label="规则分类 *" required>
            <el-select v-model="editingRule.category" style="width: 100%" placeholder="选择分类">
              <el-option label="完整性检查" value="completeness" />
              <el-option label="格式规范" value="format" />
              <el-option label="内容质量" value="content" />
              <el-option label="重复检测" value="duplicate" />
              <el-option label="接口规范" value="api" />
              <el-option label="自定义" value="custom" />
            </el-select>
          </el-form-item>
          <el-form-item label="权重">
            <el-input-number v-model="editingRule.weight" :min="0" :max="100" />
            <span style="margin-left: 8px; font-size: 12px; color: #909399;">0-100，影响最终评分占比</span>
          </el-form-item>
          <el-form-item label="规则描述">
            <el-input v-model="editingRule.description" type="textarea" :rows="2"
                      placeholder="描述此规则的检查目的和逻辑" />
          </el-form-item>
          <el-form-item label="检查字段">
            <el-select v-model="editingRule.target_fields" multiple filterable allow-create
                       placeholder="选择或输入要检查的字段名" style="width: 100%">
              <el-option label="标题 (title)" value="title" />
              <el-option label="步骤 (steps)" value="steps" />
              <el-option label="预期结果 (expected)" value="expected" />
              <el-option label="前置条件 (precondition)" value="precondition" />
              <el-option label="优先级 (priority)" value="priority" />
              <el-option label="请求地址 (url)" value="url" />
              <el-option label="请求方法 (method)" value="method" />
              <el-option label="请求参数 (request_params)" value="request_params" />
              <el-option label="预期响应 (expected_response)" value="expected_response" />
            </el-select>
          </el-form-item>
          <el-form-item label="检查类型">
            <el-select v-model="editingRule.check_type" style="width: 100%" placeholder="选择检查方式">
              <el-option label="非空检查" value="not_empty" />
              <el-option label="最小长度检查" value="min_length" />
              <el-option label="格式正则匹配" value="regex" />
              <el-option label="关键词包含" value="contains_keywords" />
              <el-option label="枚举值校验" value="enum_check" />
              <el-option label="语义质量评估" value="semantic_quality" />
              <el-option label="自定义逻辑" value="custom_logic" />
            </el-select>
          </el-form-item>
          <el-form-item label="检查参数" v-if="editingRule.check_type === 'min_length'">
            <el-input-number v-model="editingRule.check_params.min_length" :min="1" placeholder="最小字符数" />
          </el-form-item>
          <el-form-item label="正则表达式" v-if="editingRule.check_type === 'regex'">
            <el-input v-model="editingRule.check_params.pattern" placeholder="如：^\d{4}-\d{2}-\d{2}" />
          </el-form-item>
          <el-form-item label="关键词" v-if="editingRule.check_type === 'contains_keywords'">
            <el-select v-model="editingRule.check_params.keywords" multiple filterable allow-create
                       placeholder="输入关键词后回车" style="width: 100%" />
          </el-form-item>
          <el-form-item label="枚举值" v-if="editingRule.check_type === 'enum_check'">
            <el-select v-model="editingRule.check_params.allowed_values" multiple filterable allow-create
                       placeholder="输入允许的值后回车" style="width: 100%" />
          </el-form-item>
          <el-form-item label="严重级别">
            <el-radio-group v-model="editingRule.severity">
              <el-radio value="critical">严重</el-radio>
              <el-radio value="high">高</el-radio>
              <el-radio value="medium">中</el-radio>
              <el-radio value="low">低</el-radio>
            </el-radio-group>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="ruleEditVisible = false">取消</el-button>
          <el-button type="primary" @click="saveRule">保存规则</el-button>
        </template>
      </el-dialog>

      <template #footer>
        <el-button @click="configDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveConfig">保存配置</el-button>
      </template>
    </el-dialog>

    <!-- 质检结果详情对话框 -->
    <el-dialog v-model="resultDialogVisible" :title="`质检结果 - ${currentTask?.name || ''}`"
               width="1100px" destroy-on-close top="3vh">
      <!-- 统计概览 -->
      <div v-if="taskStats" class="result-stats">
        <el-row :gutter="16">
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-value" :style="{ color: scoreColor(taskStats.overall_score) }">
                {{ taskStats.overall_score }}
              </div>
              <div class="stat-label">综合评分</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-value" style="color: #67c23a">{{ taskStats.pass_rate }}%</div>
              <div class="stat-label">通过率</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-value" style="color: #409eff">{{ taskStats.total_cases }}</div>
              <div class="stat-label">用例总数</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-value" style="color: #e6a23c">{{ (taskStats.issue_type_distribution && Object.keys(taskStats.issue_type_distribution).length) || 0 }}</div>
              <div class="stat-label">问题类型数</div>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="16" style="margin-top: 16px">
          <el-col :span="12">
            <el-card shadow="never" class="chart-card">
              <template #header>等级分布</template>
              <div class="bar-chart">
                <div class="bar-item">
                  <span class="bar-label">合格</span>
                  <el-progress :percentage="levelPercent('pass')" :color="'#67c23a'" :stroke-width="20">
                    <span class="bar-text">{{ taskStats.level_distribution?.pass || 0 }}</span>
                  </el-progress>
                </div>
                <div class="bar-item">
                  <span class="bar-label">警告</span>
                  <el-progress :percentage="levelPercent('warning')" :color="'#e6a23c'" :stroke-width="20">
                    <span class="bar-text">{{ taskStats.level_distribution?.warning || 0 }}</span>
                  </el-progress>
                </div>
                <div class="bar-item">
                  <span class="bar-label">不合格</span>
                  <el-progress :percentage="levelPercent('fail')" :color="'#f56c6c'" :stroke-width="20">
                    <span class="bar-text">{{ taskStats.level_distribution?.fail || 0 }}</span>
                  </el-progress>
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="never" class="chart-card">
              <template #header>分数分布</template>
              <div class="bar-chart" v-if="taskStats.score_distribution">
                <div v-for="(count, range) in taskStats.score_distribution" :key="range" class="bar-item">
                  <span class="bar-label">{{ range }}</span>
                  <el-progress :percentage="count / taskStats.total_cases * 100"
                               :color="rangeColor(range)" :stroke-width="20">
                    <span class="bar-text">{{ count }}</span>
                  </el-progress>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <el-card v-if="taskStats.top_issues?.length" shadow="never" style="margin-top: 16px">
          <template #header><el-icon><WarningFilled /></el-icon> Top 问题类型</template>
          <div class="issue-tags">
            <el-tag v-for="(item, idx) in taskStats.top_issues.slice(0, 8)" :key="idx"
                    :type="idx < 3 ? 'danger' : 'warning'" size="large" effect="plain">
              {{ issueTypeLabel(item[0]) }} x {{ item[1] }}
            </el-tag>
          </div>
        </el-card>
      </div>

      <div class="result-list" style="margin-top: 16px">
        <div class="result-filters">
          <el-radio-group v-model="resultFilter" size="small" @change="loadTaskResults">
            <el-radio-button value="">全部</el-radio-button>
            <el-radio-button value="pass">合格</el-radio-button>
            <el-radio-button value="warning">警告</el-radio-button>
            <el-radio-button value="fail">不合格</el-radio-button>
          </el-radio-group>
          <el-button size="small" @click="exportCSV" style="margin-left: 8px">
            <el-icon><Download /></el-icon> 导出 CSV
          </el-button>
        </div>

        <el-table :data="taskResults" v-loading="resultsLoading" stripe style="width: 100%; margin-top: 8px"
                  max-height="400" row-key="id">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="case_title" label="用例标题" min-width="200" show-overflow-tooltip />
          <el-table-column label="评分" width="90" align="center" sortable prop="score">
            <template #default="{ row }">
              <span :style="{ color: scoreColor(row.score), fontWeight: 'bold' }">{{ row.score }}</span>
            </template>
          </el-table-column>
          <el-table-column label="等级" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="levelType(row.level)" size="small">{{ levelText(row.level) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="完整性" width="75" align="center">
            <template #default="{ row }">{{ row.completeness_score }}</template>
          </el-table-column>
          <el-table-column label="格式" width="60" align="center">
            <template #default="{ row }">{{ row.format_score }}</template>
          </el-table-column>
          <el-table-column label="内容" width="60" align="center">
            <template #default="{ row }">{{ row.content_score }}</template>
          </el-table-column>
          <el-table-column label="问题" min-width="220">
            <template #default="{ row }">
              <div v-if="row.issues?.length">
                <el-tag v-for="(iss, i) in row.issues.slice(0, 3)" :key="i"
                        size="small" :type="iss.severity === 'critical' ? 'danger' : iss.severity === 'high' ? 'warning' : 'info'"
                        effect="plain" style="margin: 2px">
                  {{ iss.message }}
                </el-tag>
                <el-tag v-if="row.issues.length > 3" size="small" type="info">+{{ row.issues.length - 3 }}</el-tag>
              </div>
              <span v-else style="color: #67c23a">无问题</span>
            </template>
          </el-table-column>
          <el-table-column label="疑似重复" width="120" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.duplicate_of" type="danger" size="small" effect="dark">
                {{ row.duplicate_of }} ({{ (row.duplicate_similarity * 100).toFixed(0) }}%)
              </el-tag>
              <span v-else style="color: #909399">-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" align="center" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="showCaseDetail(row)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>

    <!-- 单用例详情 -->
    <el-dialog v-model="caseDetailVisible" title="用例质检详情" width="700px" destroy-on-close>
      <template v-if="currentCase">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="用例标题" :span="2">{{ currentCase.case_title }}</el-descriptions-item>
          <el-descriptions-item label="综合评分">
            <span :style="{ color: scoreColor(currentCase.score), fontWeight: 'bold', fontSize: '18px' }">
              {{ currentCase.score }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="等级">
            <el-tag :type="levelType(currentCase.level)">{{ levelText(currentCase.level) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="完整性得分">{{ currentCase.completeness_score }}</el-descriptions-item>
          <el-descriptions-item label="格式规范得分">{{ currentCase.format_score }}</el-descriptions-item>
          <el-descriptions-item label="内容质量得分" :span="2">{{ currentCase.content_score }}</el-descriptions-item>
        </el-descriptions>

        <el-card v-if="currentCase.issues?.length" shadow="never" style="margin-top: 12px" class="detail-card">
          <template #header><el-icon><WarningFilled /></el-icon> 发现的问题</template>
          <div v-for="(iss, idx) in currentCase.issues" :key="idx" class="issue-item">
            <el-tag :type="iss.severity === 'critical' ? 'danger' : iss.severity === 'high' ? 'warning' : 'info'"
                    size="small" effect="dark">
              {{ severityLabel(iss.severity) }}
            </el-tag>
            <span class="issue-msg">{{ iss.message }}</span>
          </div>
        </el-card>

        <el-card v-if="currentCase.suggestions?.length" shadow="never" style="margin-top: 12px" class="detail-card">
          <template #header><el-icon><Opportunity /></el-icon> 优化建议</template>
          <div v-for="(sg, idx) in currentCase.suggestions" :key="idx" class="suggestion-item">
            <span class="sug-idx">{{ idx + 1 }}.</span>
            <span>{{ sg.message }}</span>
          </div>
        </el-card>

        <el-card shadow="never" style="margin-top: 12px">
          <template #header><el-icon><Document /></el-icon> 用例原始内容</template>
          <pre class="case-raw">{{ JSON.stringify(currentCase.case_content, null, 2) }}</pre>
        </el-card>
      </template>
    </el-dialog>

    <!-- 数据汇总 -->
    <el-dialog v-model="summaryDialogVisible" title="质检数据汇总" width="800px" destroy-on-close>
      <div v-if="summaryData" v-loading="summaryLoading">
        <el-row :gutter="16">
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-value" style="color: #409eff">{{ summaryData.total_tasks }}</div>
              <div class="stat-label">任务总数</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-value" style="color: #67c23a">{{ summaryData.total_cases_checked }}</div>
              <div class="stat-label">已检用例</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-value" :style="{ color: scoreColor(summaryData.average_score) }">
                {{ summaryData.average_score }}
              </div>
              <div class="stat-label">平均分</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-value" style="color: #67c23a">{{ summaryData.pass_rate }}%</div>
              <div class="stat-label">整体通过率</div>
            </div>
          </el-col>
        </el-row>
        <el-divider />
        <h4>最近任务</h4>
        <el-table :data="summaryData.recent_tasks" stripe size="small" style="margin-top: 8px">
          <el-table-column prop="name" label="任务名称" show-overflow-tooltip />
          <el-table-column prop="overall_score" label="评分" width="80" align="center" />
          <el-table-column prop="pass_rate" label="通过率" width="100" align="center">
            <template #default="{ row }">
              <el-progress :percentage="row.pass_rate" :stroke-width="6" style="width: 70px" />
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="时间" width="160" align="center">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Monitor, Upload, Edit, Setting, Refresh, DataLine, List,
  UploadFilled, Plus, Download, WarningFilled, Opportunity, Document, Connection, Search
} from '@element-plus/icons-vue'
import api from '@/api/index.js'
import * as XLSX from 'xlsx'

// ==================== NPC State ====================
const npcMood = ref('neutral') // neutral, happy, sad, angry, surprised
const npcBubbleVisible = ref(false)
const npcBubbleText = ref('你好呀！我是质检灵宠小Q，把用例交给我来质检吧~')
const npcBubbleType = ref('info')
const npcAnimating = ref(false)
const npcShaking = ref(false)
const npcHover = ref(false)
let npcBubbleTimer = null

const npcMoodClass = computed(() => `mood-${npcMood.value}`)
const eyeClass = computed(() => {
  const map = { neutral: '', happy: 'eye-happy', sad: 'eye-sad', angry: 'eye-angry', surprised: 'eye-surprised' }
  return map[npcMood.value] || ''
})
const mouthClass = computed(() => {
  const map = { neutral: '', happy: 'mouth-happy', sad: 'mouth-sad', angry: 'mouth-angry', surprised: 'mouth-surprised' }
  return map[npcMood.value] || ''
})

function calcMood(score, passRate) {
  // 综合评分和通过率判断情绪
  const weighted = score * 0.6 + passRate * 0.4
  if (score >= 85 && passRate >= 70) return 'happy'
  if (weighted >= 65) return 'neutral'
  if (weighted >= 40) return 'sad'
  return 'angry'
}

// 用户点击选中的任务（优先显示）
const selectedTask = ref(null)

// 用于模板中显示最新任务数据的 computed（在 tasks 声明后初始化）
let latestTaskRef = ref(null)
let unwatchLatestTask = null

function initNpcWatch() {
  latestTaskRef = computed(() => selectedTask.value || tasks.value[0] || null)
  unwatchLatestTask = watch(latestTaskRef, (task) => {
    if (!task) {
      setNpcMood('neutral', '你好呀！我是质检灵宠小Q，把用例交给我来质检吧~')
      return
    }
    const score = task.overall_score
    const passRate = task.pass_rate
    const mood = calcMood(score, passRate)
    setNpcMood(mood, randomQuote(mood, score, passRate))
  }, { immediate: true })
}

// 模板中使用的别名
const latestTask = computed(() => latestTaskRef.value)

function setNpcMood(mood, text, type = 'info') {
  npcMood.value = mood
  npcBubbleText.value = text
  npcBubbleType.value = type
  npcBubbleVisible.value = true
  clearTimeout(npcBubbleTimer)
  npcBubbleTimer = setTimeout(() => { npcBubbleVisible.value = false }, 6000)
}

function randomQuote(mood, score, passRate) {
  const quotes = {
    happy: [
      `太棒了！综合评分 ${score} 分，通过率 ${passRate}%，这批用例质量很高呢！🎉`,
      `哇哦~ 评分 ${score} 分！小Q为你点赞，继续保持！✨`,
      `优秀！${passRate}% 的用例都合格了，团队用例编写水平很棒！👏`,
      `小Q检测到高质量用例！评分 ${score}，可以当作标杆案例啦~ 🌟`,
    ],
    neutral: [
      `综合评分 ${score} 分，还有提升空间哦，让小Q帮你找找问题~ 🔍`,
      `通过率 ${passRate}%，整体还行，但部分用例需要优化一下。`,
      `评分 ${score} 分，处于中等水平，看看哪些用例可以改进吧。`,
      `小Q已完成质检，${passRate}% 通过，继续加油！💪`,
    ],
    sad: [
      `呜... 评分只有 ${score} 分，通过率 ${passRate}%，这批用例需要大改 😢`,
      `小Q有点难过，${passRate}% 的通过率偏低，建议重点检查完整性。`,
      `评分 ${score} 分，问题比较多，让小Q帮你逐条分析吧。`,
      `哎呀，这批用例质量不太理想，不过别担心，小Q会陪你一起改进！`,
    ],
    angry: [
      `生气！评分 ${score} 分？！大量用例不合格，必须整改！💢`,
      `小Q很生气！通过率才 ${passRate}%？基础规范都没达标！`,
      `这不行！${score} 分太低了，重复用例、缺步骤、没预期结果...问题一大堆！`,
      `严肃警告：这批用例质量极差，请立即查看问题清单并整改！`,
    ],
  }
  const list = quotes[mood] || quotes.neutral
  return list[Math.floor(Math.random() * list.length)]
}

function levelEmoji(score) {
  if (score >= 85) return '🌟'
  if (score >= 60) return '👍'
  if (score >= 40) return '⚠️'
  return '💢'
}

function npcClick() {
  npcAnimating.value = true
  setTimeout(() => { npcAnimating.value = false }, 800)
  const task = latestTask.value
  if (task) {
    const score = task.overall_score
    const passRate = task.pass_rate
    const mood = calcMood(score, passRate)
    if (mood === 'happy') {
      setNpcMood('happy', '点击我干嘛？是不是想夸我质检得准呀~ 😊', 'success')
    } else if (mood === 'neutral') {
      setNpcMood('surprised', '哎呀！别戳我啦，快去看看哪些用例需要优化吧！', 'warning')
    } else {
      setNpcMood('angry', '别戳了！快去改用例！小Q看着都着急！', 'danger')
    }
  } else {
    setNpcMood('surprised', '咦？还没有质检任务呢，快上传用例让我开工吧！', 'info')
  }
}

// ==================== Original State ====================
const scenario = ref('general')
const loading = ref(false)
const running = ref(false)
const tasks = ref([])
const configDialogVisible = ref(false)

// 搜索
const taskSearchKeyword = ref('')
const filteredTasks = computed(() => {
  if (!taskSearchKeyword.value) return tasks.value
  const kw = taskSearchKeyword.value.toLowerCase()
  return tasks.value.filter(t => t.name && t.name.toLowerCase().includes(kw))
})

// 多选（手动管理）
const selectedTasks = ref([])
function toggleTaskSelection(row, checked) {
  if (checked) {
    selectedTasks.value = [...selectedTasks.value, row]
  } else {
    selectedTasks.value = selectedTasks.value.filter(t => t.id !== row.id)
  }
}
const allSelected = computed(() => {
  return pagedTasks.value.length > 0 && pagedTasks.value.every(t => selectedTasks.value.some(s => s.id === t.id))
})
function toggleAllTasks(e) {
  const checked = e.target.checked
  if (checked) {
    const existing = new Set(selectedTasks.value.map(t => t.id))
    const toAdd = pagedTasks.value.filter(t => !existing.has(t.id))
    selectedTasks.value = [...selectedTasks.value, ...toAdd]
  } else {
    const pageIds = new Set(pagedTasks.value.map(t => t.id))
    selectedTasks.value = selectedTasks.value.filter(t => !pageIds.has(t.id))
  }
}

// 分页
const currentPage = ref(1)
const pageSize = ref(6)
const jumpPage = ref(1)
const pagedTasks = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredTasks.value.slice(start, start + pageSize.value)
})
const totalPages = computed(() => Math.max(1, Math.ceil(filteredTasks.value.length / pageSize.value)))
function goToPage() {
  const p = jumpPage.value
  if (p >= 1 && p <= totalPages.value) {
    currentPage.value = p
  }
  jumpPage.value = currentPage.value
}

// 搜索或数据变化时重置到第一页
watch([taskSearchKeyword, () => tasks.value.length], () => {
  currentPage.value = 1
})

// 初始化 NPC watch（必须在 tasks 声明后）
initNpcWatch()

const checkConfig = reactive({
  duplicate_threshold: 0.85,
  pass_score: 60,
})

// ==================== 自定义规则系统 ====================
const checkRules = ref([])
const ruleEditVisible = ref(false)
const editingRuleIdx = ref(-1)
const editingRule = ref(createEmptyRule())

function createEmptyRule() {
  return {
    name: '',
    category: 'custom',
    weight: 10,
    description: '',
    target_fields: [],
    check_type: 'not_empty',
    check_params: {},
    severity: 'medium',
    enabled: true,
  }
}

function categoryLabel(cat) {
  const map = {
    completeness: '完整性', format: '格式规范', content: '内容质量',
    duplicate: '重复检测', api: '接口规范', custom: '自定义',
  }
  return map[cat] || cat
}

// 预设规则模板
const ruleTemplates = {
  general: [
    { name: '标题非空检查', category: 'completeness', weight: 15, description: '用例标题不能为空', target_fields: ['title'], check_type: 'not_empty', severity: 'critical', enabled: true },
    { name: '步骤非空检查', category: 'completeness', weight: 15, description: '测试步骤不能为空', target_fields: ['steps'], check_type: 'not_empty', severity: 'critical', enabled: true },
    { name: '预期结果非空检查', category: 'completeness', weight: 15, description: '预期结果不能为空', target_fields: ['expected'], check_type: 'not_empty', severity: 'critical', enabled: true },
    { name: '优先级枚举校验', category: 'format', weight: 8, description: '优先级必须在 P0-P3 范围内', target_fields: ['priority'], check_type: 'enum_check', check_params: { allowed_values: ['P0', 'P1', 'P2', 'P3'] }, severity: 'medium', enabled: true },
    { name: '标题最小长度', category: 'format', weight: 5, description: '标题至少5个字符', target_fields: ['title'], check_type: 'min_length', check_params: { min_length: 5 }, severity: 'low', enabled: true },
    { name: '步骤描述质量', category: 'content', weight: 12, description: '步骤描述应包含具体操作动词', target_fields: ['steps'], check_type: 'semantic_quality', severity: 'high', enabled: true },
    { name: '预期结果可验证性', category: 'content', weight: 12, description: '预期结果应具体可验证', target_fields: ['expected'], check_type: 'semantic_quality', severity: 'high', enabled: true },
    { name: '前置条件合理性', category: 'content', weight: 8, description: '前置条件应清晰合理', target_fields: ['precondition'], check_type: 'semantic_quality', severity: 'medium', enabled: true },
    { name: '重复用例检测', category: 'duplicate', weight: 10, description: '检测标题或步骤高度相似的用例', target_fields: ['title', 'steps'], check_type: 'custom_logic', severity: 'high', enabled: true },
  ],
  api: [
    { name: '标题非空检查', category: 'completeness', weight: 15, description: '接口用例标题不能为空', target_fields: ['title'], check_type: 'not_empty', severity: 'critical', enabled: true },
    { name: '请求地址非空检查', category: 'completeness', weight: 15, description: '请求URL不能为空', target_fields: ['url'], check_type: 'not_empty', severity: 'critical', enabled: true },
    { name: '请求方法非空检查', category: 'completeness', weight: 10, description: '请求方法不能为空', target_fields: ['method'], check_type: 'not_empty', severity: 'critical', enabled: true },
    { name: '预期响应非空检查', category: 'completeness', weight: 15, description: '预期响应/断言不能为空', target_fields: ['expected_response'], check_type: 'not_empty', severity: 'critical', enabled: true },
    { name: '请求方法枚举校验', category: 'format', weight: 8, description: '请求方法必须在标准HTTP方法中', target_fields: ['method'], check_type: 'enum_check', check_params: { allowed_values: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'] }, severity: 'high', enabled: true },
    { name: 'URL格式检查', category: 'format', weight: 8, description: '请求地址应以 / 开头', target_fields: ['url'], check_type: 'regex', check_params: { pattern: '^/' }, severity: 'medium', enabled: true },
    { name: '请求参数规范性', category: 'content', weight: 8, description: '请求参数描述应清晰', target_fields: ['request_params'], check_type: 'semantic_quality', severity: 'medium', enabled: true },
    { name: '断言可验证性', category: 'content', weight: 12, description: '预期响应断言应具体可验证', target_fields: ['expected_response'], check_type: 'semantic_quality', severity: 'high', enabled: true },
    { name: '重复接口检测', category: 'duplicate', weight: 10, description: '检测URL和方法相同的重复接口', target_fields: ['url', 'method'], check_type: 'custom_logic', severity: 'high', enabled: true },
  ],
  finance: [
    { name: '标题非空检查', category: 'completeness', weight: 10, description: '用例标题不能为空', target_fields: ['title'], check_type: 'not_empty', severity: 'critical', enabled: true },
    { name: '步骤非空检查', category: 'completeness', weight: 10, description: '测试步骤不能为空', target_fields: ['steps'], check_type: 'not_empty', severity: 'critical', enabled: true },
    { name: '预期结果非空检查', category: 'completeness', weight: 10, description: '预期结果不能为空', target_fields: ['expected'], check_type: 'not_empty', severity: 'critical', enabled: true },
    { name: '金额字段校验', category: 'format', weight: 15, description: '金额字段格式校验（精确到分）', target_fields: ['expected', 'steps'], check_type: 'regex', check_params: { pattern: '\\d+\\.\\d{2}' }, severity: 'critical', enabled: true },
    { name: '数据脱敏检查', category: 'content', weight: 15, description: '检查是否包含敏感信息（身份证、银行卡号等）', target_fields: ['title', 'steps', 'expected'], check_type: 'custom_logic', severity: 'critical', enabled: true },
    { name: '交易状态覆盖', category: 'content', weight: 12, description: '检查是否覆盖成功/失败/超时等交易状态', target_fields: ['expected'], check_type: 'semantic_quality', severity: 'high', enabled: true },
    { name: '合规性检查', category: 'custom', weight: 15, description: '检查是否符合金融行业监管要求', target_fields: ['steps', 'expected'], check_type: 'semantic_quality', severity: 'critical', enabled: true },
    { name: '优先级枚举校验', category: 'format', weight: 5, description: '优先级必须在 P0-P3 范围内', target_fields: ['priority'], check_type: 'enum_check', check_params: { allowed_values: ['P0', 'P1', 'P2', 'P3'] }, severity: 'medium', enabled: true },
    { name: '重复用例检测', category: 'duplicate', weight: 8, description: '检测标题或步骤高度相似的用例', target_fields: ['title', 'steps'], check_type: 'custom_logic', severity: 'high', enabled: true },
  ],
}

function loadRuleTemplate(type) {
  const template = ruleTemplates[type]
  if (!template) return
  // 深度克隆模板数据
  checkRules.value = JSON.parse(JSON.stringify(template))
  ElMessage.success(`已加载「${type === 'general' ? '功能测试' : type === 'api' ? '接口测试' : '金融行业'}」规则模板`)
}

function addRule() {
  editingRuleIdx.value = -1
  editingRule.value = createEmptyRule()
  ruleEditVisible.value = true
}

function editRule(idx) {
  editingRuleIdx.value = idx
  editingRule.value = JSON.parse(JSON.stringify(checkRules.value[idx]))
  ruleEditVisible.value = true
}

function removeRule(idx) {
  checkRules.value.splice(idx, 1)
}

function saveRule() {
  if (!editingRule.value.name.trim()) {
    ElMessage.warning('请输入规则名称')
    return
  }
  if (editingRuleIdx.value >= 0) {
    checkRules.value[editingRuleIdx.value] = JSON.parse(JSON.stringify(editingRule.value))
  } else {
    checkRules.value.push(JSON.parse(JSON.stringify(editingRule.value)))
  }
  ruleEditVisible.value = false
  ElMessage.success('规则已保存')
}

function saveConfig() {
  // 将规则配置序列化保存
  const config = {
    rules: checkRules.value,
    duplicate_threshold: checkConfig.duplicate_threshold,
    pass_score: checkConfig.pass_score,
  }
  console.log('保存配置:', config)
  // TODO: 调用后端API保存配置
  // await api.post('/quality-checker/config/', config)
  ElMessage.success('质检配置已保存')
  configDialogVisible.value = false
}

// 初始化默认规则（功能测试模板）
onMounted(() => {
  loadTasks()
  if (!checkRules.value.length) {
    loadRuleTemplate('general')
  }
})

const uploadDialogVisible = ref(false)
const pendingFile = ref(null)
const pendingTestCases = ref(null)
const uploadRef = ref(null)

const manualDialogVisible = ref(false)
const manualCases = ref([createEmptyCase()])

const resultDialogVisible = ref(false)
const currentTask = ref(null)
const taskStats = ref(null)
const taskResults = ref([])
const resultsLoading = ref(false)
const resultFilter = ref('')

const caseDetailVisible = ref(false)
const currentCase = ref(null)

const summaryDialogVisible = ref(false)
const summaryData = ref(null)
const summaryLoading = ref(false)

// ==================== Methods ====================
function createEmptyCase() {
  return {
    title: '', priority: '',
    precondition: '', steps: '', expected: '',
    url: '', method: 'GET', request_params: '', expected_response: '',
  }
}

function handleScenarioChange() {
  manualCases.value = [createEmptyCase()]
}

function showUploadDialog() { uploadDialogVisible.value = true }
function showManualInputDialog() { manualDialogVisible.value = true }
function showConfigDialog() { configDialogVisible.value = true }

function handleFileChange(file) {
  pendingFile.value = file
  const isExcel = file.name.endsWith('.xlsx') || file.name.endsWith('.xls')

  if (isExcel) {
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target.result)
        const workbook = XLSX.read(data, { type: 'array' })
        const sheetName = workbook.SheetNames[0]
        const sheet = workbook.Sheets[sheetName]
        pendingTestCases.value = XLSX.utils.sheet_to_json(sheet, { header: 1 })
        if (pendingTestCases.value.length >= 2) {
          const headers = pendingTestCases.value[0]
          const rows = pendingTestCases.value.slice(1)
          pendingTestCases.value = rows.map(row => {
            const obj = {}
            headers.forEach((h, idx) => { obj[h] = row[idx] || '' })
            return obj
          })
          ElMessage.success(`已解析 ${pendingTestCases.value.length} 条用例`)
          setNpcMood('surprised', `收到 ${pendingTestCases.value.length} 条用例！小Q准备开始质检啦~`, 'info')
        } else {
          throw new Error('Excel 文件至少需要表头+1行数据')
        }
      } catch (err) {
        ElMessage.error('Excel 解析失败: ' + err.message)
        pendingTestCases.value = null
      }
    }
    reader.readAsArrayBuffer(file.raw)
    return
  }

  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const text = e.target.result
      if (file.name.endsWith('.json')) {
        pendingTestCases.value = JSON.parse(text)
        if (!Array.isArray(pendingTestCases.value)) {
          pendingTestCases.value = [pendingTestCases.value]
        }
        ElMessage.success(`已解析 ${pendingTestCases.value.length} 条用例`)
        setNpcMood('surprised', `收到 ${pendingTestCases.value.length} 条用例！小Q准备开始质检啦~`, 'info')
      } else if (file.name.endsWith('.csv')) {
        pendingTestCases.value = parseCSV(text)
        ElMessage.success(`已解析 ${pendingTestCases.value.length} 条用例`)
        setNpcMood('surprised', `收到 ${pendingTestCases.value.length} 条用例！小Q准备开始质检啦~`, 'info')
      }
    } catch (err) {
      ElMessage.error('文件解析失败: ' + err.message)
      pendingTestCases.value = null
    }
  }
  reader.readAsText(file.raw)
}

function parseCSV(text) {
  const lines = text.trim().split('\n')
  if (lines.length < 2) throw new Error('CSV 至少需要表头+1行数据')
  const headers = lines[0].split(',').map(h => h.trim())
  const result = []
  for (let i = 1; i < lines.length; i++) {
    const vals = lines[i].split(',').map(v => v.trim())
    const row = {}
    headers.forEach((h, idx) => { row[h] = vals[idx] || '' })
    result.push(row)
  }
  return result
}

async function confirmUpload() {
  if (!pendingTestCases.value?.length) {
    ElMessage.warning('请先选择文件')
    return
  }
  setNpcMood('neutral', '小Q正在努力质检中...请稍等 ⏳', 'info')
  const fileName = pendingFile.value?.name?.replace(/\.[^/.]+$/, '') || ''
  await runQualityCheck(pendingTestCases.value, fileName)
  uploadDialogVisible.value = false
  pendingFile.value = null
  pendingTestCases.value = null
}

function addManualCase() { manualCases.value.push(createEmptyCase()) }
function removeManualCase(idx) { manualCases.value.splice(idx, 1) }

async function confirmManualInput() {
  const cases = manualCases.value.map(tc => {
    if (scenario.value === 'api') {
      return {
        title: tc.title, priority: tc.priority,
        url: tc.url, method: tc.method,
        request_params: tc.request_params, expected_response: tc.expected_response,
      }
    }
    return {
      title: tc.title, priority: tc.priority,
      precondition: tc.precondition, steps: tc.steps, expected: tc.expected,
    }
  })
  const hasContent = cases.some(c => c.title.trim())
  if (!hasContent) {
    ElMessage.warning('请至少填写一个用例标题')
    return
  }
  setNpcMood('neutral', '小Q正在努力质检中...请稍等 ⏳', 'info')
  await runQualityCheck(cases)
  manualDialogVisible.value = false
  manualCases.value = [createEmptyCase()]
}

async function runQualityCheck(testcases, taskName) {
  running.value = true
  try {
    // 只发送启用的规则
    const enabledRules = checkRules.value.filter(r => r.enabled)
    await api.post('/quality-checker/tasks/run_check/', {
      testcases,
      scenario: scenario.value,
      rules: enabledRules,
      duplicate_threshold: checkConfig.duplicate_threshold,
      pass_score: checkConfig.pass_score,
      task_name: taskName || '',
    })
    ElMessage.success('质检完成！')
    await loadTasks()
  } catch (e) {
    const errMsg = e?.response?.data?.error || e?.message || '未知错误'
    ElMessage.error('质检失败: ' + errMsg)
    setNpcMood('sad', '质检出错了...' + errMsg + ' 😢', 'danger')
    console.error('质检失败详情:', e)
  } finally {
    running.value = false
  }
}

async function loadTasks() {
  loading.value = true
  try {
    const res = await api.get('/quality-checker/tasks/')
    tasks.value = Array.isArray(res) ? res : (res.results || [])
    // 如果当前选中的任务不在新列表中，清除选中
    if (selectedTask.value) {
      const stillExists = tasks.value.find(t => t.id === selectedTask.value.id)
      if (!stillExists) selectedTask.value = null
    }
  } catch (e) {
    ElMessage.error('加载任务失败')
  } finally {
    loading.value = false
  }
}

function selectTask(task) {
  currentTask.value = task
  selectedTask.value = task
}

async function viewResults(task) {
  currentTask.value = task
  selectedTask.value = task
  resultDialogVisible.value = true
  resultFilter.value = ''
  await Promise.all([loadTaskStats(task.id), loadTaskResults()])
}

async function loadTaskStats(taskId) {
  try {
    taskStats.value = await api.get(`/quality-checker/tasks/${taskId}/statistics/`)
  } catch { taskStats.value = null }
}

async function loadTaskResults() {
  if (!currentTask.value) return
  resultsLoading.value = true
  try {
    const params = resultFilter.value ? { level: resultFilter.value } : {}
    taskResults.value = await api.get(`/quality-checker/tasks/${currentTask.value.id}/results/`, { params })
  } catch {
    taskResults.value = []
  } finally {
    resultsLoading.value = false
  }
}

async function deleteTask(task) {
  try {
    await ElMessageBox.confirm(`确定删除任务"${task.name}"吗？此操作不可恢复`, '确认删除', { type: 'warning' })
    await api.delete(`/quality-checker/tasks/${task.id}/`)
    ElMessage.success('已删除')
    selectedTasks.value = selectedTasks.value.filter(t => t.id !== task.id)
    await loadTasks()
  } catch { /* cancelled */ }
}

async function batchDelete() {
  if (!selectedTasks.value.length) return
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${selectedTasks.value.length} 个任务吗？此操作不可恢复`, '确认批量删除', { type: 'warning' })
    for (const task of selectedTasks.value) {
      await api.delete(`/quality-checker/tasks/${task.id}/`)
    }
    ElMessage.success(`已删除 ${selectedTasks.value.length} 个任务`)
    selectedTasks.value = []
    await loadTasks()
  } catch { /* cancelled */ }
}

function showCaseDetail(row) {
  currentCase.value = row
  caseDetailVisible.value = true
}

async function showSummaryDialog() {
  summaryDialogVisible.value = true
  summaryLoading.value = true
  try {
    summaryData.value = await api.get('/quality-checker/tasks/summary/')
  } catch {
    summaryData.value = null
  } finally {
    summaryLoading.value = false
  }
}

async function exportCSV() {
  if (!currentTask.value) return
  try {
    const res = await api.post('/quality-checker/tasks/export_report/', {
      task_id: currentTask.value.id
    }, { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([res]))
    const a = document.createElement('a')
    a.href = url
    a.download = `quality_report_${currentTask.value.id}.csv`
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch {
    ElMessage.error('导出失败')
  }
}

// ==================== Helpers ====================
function formatTime(t) {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
}

function statusType(s) {
  const map = { pending: 'info', processing: 'warning', completed: 'success', failed: 'danger' }
  return map[s] || 'info'
}

function statusText(s) {
  const map = { pending: '待处理', processing: '处理中', completed: '已完成', failed: '失败' }
  return map[s] || s
}

function scoreColor(s) {
  if (s >= 80) return '#67c23a'
  if (s >= 60) return '#e6a23c'
  return '#f56c6c'
}

function passRateColor(r) {
  if (r >= 80) return '#67c23a'
  if (r >= 60) return '#e6a23c'
  return '#f56c6c'
}

function levelType(l) {
  const map = { pass: 'success', warning: 'warning', fail: 'danger' }
  return map[l] || 'info'
}

function levelText(l) {
  const map = { pass: '合格', warning: '警告', fail: '不合格' }
  return map[l] || l
}

function severityLabel(s) {
  const map = { critical: '严重', high: '高', medium: '中', low: '低' }
  return map[s] || s
}

function issueTypeLabel(t) {
  const map = {
    completeness: '完整性', format: '格式规范', content: '内容质量',
    duplicate: '重复内容', api: '接口规范',
  }
  return map[t] || t
}

function levelPercent(level) {
  if (!taskStats.value?.level_distribution) return 0
  const count = taskStats.value.level_distribution[level] || 0
  return taskStats.value.total_cases ? count / taskStats.value.total_cases * 100 : 0
}

function rangeColor(range) {
  const map = { '90-100': '#67c23a', '80-89': '#85ce61', '70-79': '#e6a23c', '60-69': '#f56c6c', '0-59': '#f56c6c' }
  return map[range] || '#909399'
}

initNpcWatch()
</script>

<style scoped>
/* ==================== 页面布局 ==================== */
.quality-checker-page {
  background: #f5f7fa;
  min-height: 100%;
  box-sizing: border-box;
}

.page-inner {
  padding: 20px;
  padding-bottom: 40px;
}

/* ==================== 灵宠 NPC ==================== */
.npc-area {
  display: flex;
  align-items: flex-start;
  gap: 20px;
  margin-bottom: 16px;
  padding: 20px;
  padding-top: 50px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  position: relative;
  overflow: hidden;
}

.npc-area::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: radial-gradient(circle at 30% 50%, rgba(64,158,255,0.04) 0%, transparent 50%);
  pointer-events: none;
  z-index: 0;
}

.npc-container {
  position: relative;
  cursor: pointer;
  user-select: none;
  flex-shrink: 0;
  transform: scale(0.7);
  transform-origin: top center;
  margin-top: 40px;
}

/* 气泡 */
.npc-bubble {
  position: absolute;
  bottom: 95%;
  left: 50%;
  transform: translateX(-50%);
  background: #fff;
  border: 2px solid #409eff;
  border-radius: 16px;
  padding: 12px 18px;
  min-width: 220px;
  max-width: 320px;
  box-shadow: 0 4px 16px rgba(64,158,255,0.2);
  z-index: 1000;
  animation: bubblePop 0.4s ease-out;
  pointer-events: none;
}

.npc-bubble.success { border-color: #67c23a; box-shadow: 0 4px 16px rgba(103,194,58,0.2); }
.npc-bubble.warning { border-color: #e6a23c; box-shadow: 0 4px 16px rgba(230,162,60,0.2); }
.npc-bubble.danger { border-color: #f56c6c; box-shadow: 0 4px 16px rgba(245,108,108,0.2); }

.bubble-tail {
  position: absolute;
  bottom: -10px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 10px solid transparent;
  border-right: 10px solid transparent;
  border-top: 10px solid #409eff;
}

.npc-bubble.success .bubble-tail { border-top-color: #67c23a; }
.npc-bubble.warning .bubble-tail { border-top-color: #e6a23c; }
.npc-bubble.danger .bubble-tail { border-top-color: #f56c6c; }

.bubble-text {
  font-size: 14px;
  color: #303133;
  line-height: 1.6;
  white-space: pre-wrap;
}

@keyframes bubblePop {
  0% { opacity: 0; transform: translateX(-50%) scale(0.7) translateY(10px); }
  100% { opacity: 1; transform: translateX(-50%) scale(1) translateY(0); }
}

.bubble-enter-active { animation: bubblePop 0.4s ease-out; }
.bubble-leave-active { animation: bubblePop 0.3s ease-in reverse; }

/* 灵宠身体 */
.pet-body {
  position: relative;
  width: 100px;
  height: 120px;
  margin: 0 auto;
  animation: breathe 2.5s ease-in-out infinite;
}

@keyframes breathe {
  0%, 100% { transform: translateY(0) scale(1); }
  50% { transform: translateY(-4px) scale(1.02); }
}

/* 耳朵 */
.pet-ear {
  position: absolute;
  width: 28px;
  height: 36px;
  background: #8cc5ff;
  border-radius: 50% 50% 0 0;
  top: 0;
  transition: all 0.3s ease;
  animation: earWiggle 3s ease-in-out infinite;
}
.pet-ear.left { left: 12px; transform: rotate(-20deg); animation-delay: 0s; }
.pet-ear.right { right: 12px; transform: rotate(20deg); animation-delay: 1.5s; }

@keyframes earWiggle {
  0%, 90%, 100% { transform: rotate(var(--rot, 0deg)); }
  92% { transform: rotate(calc(var(--rot, 0deg) + 8deg)); }
  96% { transform: rotate(calc(var(--rot, 0deg) - 5deg)); }
}
.pet-ear.left { --rot: -20deg; }
.pet-ear.right { --rot: 20deg; }
.pet-ear::after {
  content: '';
  position: absolute;
  width: 14px;
  height: 20px;
  background: #ffd1dc;
  border-radius: 50% 50% 0 0;
  bottom: 4px;
  left: 50%;
  transform: translateX(-50%);
}

/* 头部 */
.pet-head {
  position: absolute;
  width: 90px;
  height: 80px;
  background: #a8d4ff;
  border-radius: 45px 45px 40px 40px;
  top: 18px;
  left: 5px;
  z-index: 2;
  transition: all 0.3s ease;
}

/* 眼睛 */
.pet-eye {
  position: absolute;
  width: 14px;
  height: 14px;
  background: #2c3e50;
  border-radius: 50%;
  top: 28px;
  transition: all 0.3s ease;
  animation: blink 4s ease-in-out infinite;
}
.pet-eye.left { left: 22px; }
.pet-eye.right { right: 22px; }

.pet-pupil {
  position: absolute;
  width: 6px;
  height: 6px;
  background: #fff;
  border-radius: 50%;
  top: 2px;
  right: 2px;
}

@keyframes blink {
  0%, 45%, 55%, 100% { transform: scaleY(1); }
  50% { transform: scaleY(0.1); }
}

/* 眼睛状态 */
/* happy: 开心大眼 - 眼睛变圆变大，瞳孔闪亮 */
.eye-happy {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
  border: 2px solid #2c3e50;
}
.eye-happy .pet-pupil {
  width: 10px;
  height: 10px;
  background: #2c3e50;
  border-radius: 50%;
  top: 4px;
  left: 4px;
}
/* happy眼睛里的高光 */
.eye-happy .pet-pupil::after {
  content: '';
  position: absolute;
  width: 4px;
  height: 4px;
  background: #fff;
  border-radius: 50%;
  top: 1px;
  right: 1px;
}
.eye-sad { transform: rotate(15deg); }
.eye-sad.right { transform: rotate(-15deg); }
.eye-angry {
  height: 10px;
  border-radius: 50%;
  background: #2c3e50;
}
.eye-angry::before {
  content: '';
  position: absolute;
  width: 18px;
  height: 4px;
  background: #2c3e50;
  top: -6px;
  left: -2px;
  border-radius: 2px;
}
.eye-angry.left::before { transform: rotate(20deg); }
.eye-angry.right::before { transform: rotate(-20deg); left: -2px; }
.eye-surprised { width: 16px; height: 16px; }

/* 眼泪 */
.pet-tear {
  position: absolute;
  width: 6px;
  height: 10px;
  background: #74b9ff;
  border-radius: 0 50% 50% 50%;
  bottom: -12px;
  left: 4px;
  animation: tearDrop 1.5s ease-in infinite;
}
@keyframes tearDrop {
  0% { transform: translateY(0) scale(1); opacity: 1; }
  100% { transform: translateY(20px) scale(0.5); opacity: 0; }
}

/* 腮红 */
.pet-blush {
  position: absolute;
  width: 16px;
  height: 10px;
  background: #ffb6c1;
  border-radius: 50%;
  top: 42px;
  opacity: 0.6;
  transition: opacity 0.3s;
  animation: blushPulse 3s ease-in-out infinite;
}
.pet-blush.left { left: 10px; animation-delay: 0s; }
.pet-blush.right { right: 10px; animation-delay: 1.5s; }

@keyframes blushPulse {
  0%, 100% { opacity: 0.4; transform: scale(1); }
  50% { opacity: 0.7; transform: scale(1.15); }
}

/* 嘴巴 */
.pet-mouth {
  position: absolute;
  width: 20px;
  height: 10px;
  border: 2px solid #2c3e50;
  border-top: none;
  border-radius: 0 0 20px 20px;
  top: 48px;
  left: 50%;
  transform: translateX(-50%);
  transition: all 0.3s ease;
}

.mouth-happy {
  width: 24px;
  height: 14px;
  background: #ff6b81;
  border: 2px solid #2c3e50;
  border-radius: 0 0 24px 24px;
}
.mouth-sad {
  width: 20px;
  height: 10px;
  border: 2px solid #2c3e50;
  border-bottom: none;
  border-radius: 20px 20px 0 0;
  background: transparent;
}
.mouth-angry {
  width: 16px;
  height: 6px;
  background: #2c3e50;
  border: none;
  border-radius: 0 0 8px 8px;
}
.mouth-surprised {
  width: 14px;
  height: 16px;
  background: #2c3e50;
  border: none;
  border-radius: 50%;
}

/* 身体 */
.pet-torso {
  position: absolute;
  width: 70px;
  height: 50px;
  background: #a8d4ff;
  border-radius: 35px 35px 30px 30px;
  top: 70px;
  left: 15px;
  z-index: 1;
}

/* 围巾 */
.pet-scarf {
  position: absolute;
  width: 74px;
  height: 14px;
  background: #ff6b81;
  border-radius: 7px;
  top: -4px;
  left: -2px;
}
.pet-scarf::after {
  content: '';
  position: absolute;
  width: 20px;
  height: 24px;
  background: #ff6b81;
  border-radius: 0 0 10px 10px;
  right: 8px;
  top: 10px;
}

/* 手 */
.pet-hand {
  position: absolute;
  width: 18px;
  height: 28px;
  background: #a8d4ff;
  border-radius: 9px;
  top: 10px;
  transition: all 0.3s ease;
  animation: handIdle 2s ease-in-out infinite;
}
.pet-hand.left { left: -10px; transform: rotate(-20deg); animation-delay: 0s; }
.pet-hand.right { right: -10px; transform: rotate(20deg); animation-delay: 1s; }

@keyframes handIdle {
  0%, 100% { transform: rotate(var(--hand-rot, 0deg)) translateY(0); }
  50% { transform: rotate(var(--hand-rot, 0deg)) translateY(-3px); }
}
.pet-hand.left { --hand-rot: -20deg; }
.pet-hand.right { --hand-rot: 20deg; }

.hand-wave {
  animation: waveHand 0.6s ease-in-out 2 !important;
}
@keyframes waveHand {
  0%, 100% { transform: rotate(-20deg); }
  50% { transform: rotate(-50deg); }
}
.pet-hand.right.hand-wave {
  animation: waveHandRight 0.6s ease-in-out 2 !important;
}
@keyframes waveHandRight {
  0%, 100% { transform: rotate(20deg); }
  50% { transform: rotate(50deg); }
}

/* 脚 */
.pet-foot {
  position: absolute;
  width: 22px;
  height: 14px;
  background: #8cc5ff;
  border-radius: 11px 11px 4px 4px;
  bottom: -4px;
  z-index: 0;
}
.pet-foot.left { left: 18px; }
.pet-foot.right { right: 18px; }

/* 星星装饰 */
.pet-sparkle {
  position: absolute;
  font-size: 14px;
  animation: sparkle 1.5s ease-in-out infinite;
}
.pet-sparkle.s1 { top: -8px; left: -4px; animation-delay: 0s; }
.pet-sparkle.s2 { top: -4px; right: -2px; animation-delay: 0.7s; }
@keyframes sparkle {
  0%, 100% { opacity: 0; transform: scale(0.5) rotate(0deg); }
  50% { opacity: 1; transform: scale(1.2) rotate(180deg); }
}

/* 光环 */
.pet-halo {
  position: absolute;
  width: 110px;
  height: 110px;
  border: 3px solid rgba(255,215,0,0.4);
  border-radius: 50%;
  top: 10px;
  left: -5px;
  animation: haloRotate 3s linear infinite;
}
@keyframes haloRotate {
  0% { transform: rotate(0deg) scale(1); opacity: 0.6; }
  50% { transform: rotate(180deg) scale(1.05); opacity: 0.3; }
  100% { transform: rotate(360deg) scale(1); opacity: 0.6; }
}

/* 乌云 */
.pet-cloud {
  position: absolute;
  width: 80px;
  height: 30px;
  background: #bdc3c7;
  border-radius: 30px;
  top: -10px;
  left: 10px;
  opacity: 0.5;
  animation: cloudFloat 2s ease-in-out infinite;
}
.pet-cloud::before, .pet-cloud::after {
  content: '';
  position: absolute;
  background: #bdc3c7;
  border-radius: 50%;
}
.pet-cloud::before { width: 30px; height: 30px; top: -12px; left: 12px; }
.pet-cloud::after { width: 24px; height: 24px; top: -8px; right: 14px; }
@keyframes cloudFloat {
  0%, 100% { transform: translateX(0); }
  50% { transform: translateX(5px); }
}

/* 动画状态 */
.pet-bounce {
  animation: bounce 0.8s ease;
}
@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  30% { transform: translateY(-15px) scale(1.05); }
  60% { transform: translateY(5px) scale(0.95); }
}

.pet-shake {
  animation: shake 0.5s ease;
}
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-5px) rotate(-3deg); }
  75% { transform: translateX(5px) rotate(3deg); }
}

/* 名字 */
.pet-name {
  text-align: center;
  font-size: 13px;
  color: #606266;
  margin-top: 8px;
  font-weight: 600;
  animation: nameGlow 3s ease-in-out infinite;
}

@keyframes nameGlow {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}

/* 仪表盘 */
.npc-dashboard {
  display: flex;
  align-items: center;
  gap: 0;
  flex: 1;
  justify-content: space-around;
  padding: 16px 24px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  border-radius: 12px;
  margin-left: -20px;
}

.dash-item {
  text-align: center;
  padding: 8px 16px;
}

.dash-value {
  font-size: 32px;
  font-weight: 700;
  line-height: 1.2;
}

.dash-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.dash-divider {
  width: 1px;
  height: 50px;
  background: #dcdfe6;
}

/* 情绪主题色 */
.mood-happy .pet-head, .mood-happy .pet-torso, .mood-happy .pet-hand { background: #a8e6cf; }
.mood-happy .pet-ear { background: #88d8b0; }
.mood-happy .pet-foot { background: #88d8b0; }

.mood-sad .pet-head, .mood-sad .pet-torso, .mood-sad .pet-hand { background: #b8c5d6; }
.mood-sad .pet-ear { background: #a0b4cc; }
.mood-sad .pet-foot { background: #a0b4cc; }

.mood-angry .pet-head, .mood-angry .pet-torso, .mood-angry .pet-hand { background: #f4a4a4; }
.mood-angry .pet-ear { background: #e88888; }
.mood-angry .pet-foot { background: #e88888; }

.mood-surprised .pet-head, .mood-surprised .pet-torso, .mood-surprised .pet-hand { background: #ffeaa7; }
.mood-surprised .pet-ear { background: #fdcb6e; }
.mood-surprised .pet-foot { background: #fdcb6e; }

/* ==================== 原有样式 ==================== */
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #fff;
  border-radius: 8px;
  margin-bottom: 12px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  flex-wrap: wrap;
}

.toolbar-right {
  margin-left: auto;
  display: flex;
  gap: 8px;
}

.config-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.config-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
}

/* ==================== 规则配置样式 ==================== */
.config-section {
  margin-bottom: 4px;
}

.config-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.rule-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 320px;
  overflow-y: auto;
}

.rule-card {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 10px 12px;
  background: #fafafa;
  transition: all 0.2s;
}

.rule-card:hover {
  border-color: #c6e2ff;
  background: #ecf5ff;
}

.rule-card.rule-disabled {
  opacity: 0.5;
  background: #f5f5f5;
}

.rule-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.rule-name {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  flex: 1;
}

.rule-category-tag {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 10px;
  background: #e9e9eb;
  color: #909399;
}

.rule-category-tag.cat-completeness { background: #e1f3d8; color: #67c23a; }
.rule-category-tag.cat-format      { background: #d9ecff; color: #409eff; }
.rule-category-tag.cat-content     { background: #faecd8; color: #e6a23c; }
.rule-category-tag.cat-duplicate   { background: #fde2e2; color: #f56c6c; }
.rule-category-tag.cat-api         { background: #e8dff5; color: #9b59b6; }
.rule-category-tag.cat-custom      { background: #e9e9eb; color: #909399; }

.rule-actions {
  display: flex;
  gap: 4px;
}

.rule-detail {
  margin-top: 6px;
  padding-left: 42px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.rule-desc {
  font-size: 12px;
  color: #909399;
  flex: 1;
}

.rule-weight {
  font-size: 12px;
  color: #409eff;
  font-weight: 500;
  white-space: nowrap;
}

.task-list-section {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  margin-bottom: 0;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.section-count-tag {
  margin-left: 8px;
}

.task-search-input {
  width: 200px;
}

.table-empty-wrap {
  padding: 20px 0;
}

/* ==================== 原生表格 ==================== */
.native-table-wrap {
  border-radius: 6px;
  position: relative;
}

/* 自定义 loading 遮罩（只盖表格区域） */
.table-loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5;
  pointer-events: auto;
}
.table-loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #409eff;
  font-size: 14px;
}
.spinner-icon {
  display: inline-block;
  font-size: 24px;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

.native-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 13px;
  color: #303133;
  border: 1px solid #e4e7ed;
}

.native-table thead {
  background: #f5f7fa;
}

.native-table th,
.native-table td {
  border: 1px solid #ebeef5;
}

.native-table th {
  padding: 8px 6px;
  text-align: center;
  font-weight: 600;
  font-size: 12px;
  color: #909399;
  border-bottom: 2px solid #e4e7ed;
  white-space: nowrap;
  user-select: none;
  background: #f5f7fa;
}

.native-table tbody tr {
  transition: background 0.15s;
  cursor: pointer;
}
.native-table tbody tr:nth-child(even) {
  background: #fafafa;
}
.native-table tbody tr:hover {
  background: #ecf5ff;
}
.native-table tbody tr.row-selected {
  background: #d9ecff;
}

.native-table td {
  padding: 6px 4px;
  text-align: center;
  vertical-align: middle;
}

/* 列宽分配 (table-layout:fixed) - 紧凑版 */
.col-cb     { width: 36px; }
.col-name   { width: 220px; text-align: left !important; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-scene  { width: 56px; }
.col-cases  { width: 52px; }
.col-rate   { width: 90px; }
.col-score  { width: 56px; }
.col-result { width: 140px; }
.col-status { width: 64px; }
.col-time   { width: 140px; }
.col-action { width: 100px; }

/* 任务名称溢出处理 */
.native-table td.col-name {
  max-width: 0;
}

/* 标签 */
.tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.5;
}
.tag-success { background: #e1f3d8; color: #67c23a; }
.tag-warning { background: #faecd8; color: #e6a23c; }
.tag-danger  { background: #fde2e2; color: #f56c6c; }
.tag-info    { background: #e9e9eb; color: #909399; }
.sep {
  margin: 0 3px;
  color: #c0c4cc;
  font-size: 12px;
}

/* 迷你进度条 */
.mini-progress {
  display: inline-block;
  width: 50px;
  height: 5px;
  background: #ebeef5;
  border-radius: 3px;
  overflow: hidden;
  vertical-align: middle;
  margin-right: 4px;
}
.mini-progress-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s;
}
.mini-progress-text {
  font-size: 12px;
  color: #606266;
  vertical-align: middle;
}

/* 评分数字 */
.score-num {
  font-weight: 700;
  font-size: 16px;
}

/* 链接按钮 */
.btn-link {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 13px;
  padding: 2px 4px;
  border-radius: 2px;
  transition: color 0.15s;
}
.btn-link:hover {
  text-decoration: underline;
}
.btn-primary { color: #409eff; }
.btn-primary:hover { color: #66b1ff; }
.btn-danger  { color: #f56c6c; }
.btn-danger:hover  { color: #f89898; }

.table-pagination-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px 8px;
  border-top: 1px solid #ebeef5;
  background: #fff;
  position: relative;
  z-index: 10;
}

/* 原生分页器 */
.native-pager {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #606266;
}
.pager-total {
  margin-right: 8px;
  color: #909399;
}
.pager-btn {
  min-width: 32px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: #fff;
  color: #606266;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}
.pager-btn:hover:not(:disabled):not(.pager-active) {
  color: #409eff;
  border-color: #c6e2ff;
  background: #ecf5ff;
}
.pager-btn:disabled {
  color: #c0c4cc;
  cursor: not-allowed;
  background: #f5f7fa;
}
.pager-active {
  color: #fff !important;
  background: #409eff !important;
  border-color: #409eff !important;
}
.pager-jump {
  margin-left: 8px;
  color: #909399;
}
.pager-input {
  width: 40px;
  height: 28px;
  text-align: center;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  outline: none;
  margin: 0 4px;
}
.pager-input:focus {
  border-color: #409eff;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 12px;
  font-size: 16px;
  color: #303133;
}

.scenario-hint {
  margin-bottom: 8px;
}

.upload-section {
  min-height: 200px;
}

.manual-input-area {
  max-height: 500px;
  overflow-y: auto;
}

.manual-case-card {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 10px;
  background: #fafafa;
}

.case-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.case-index {
  font-weight: 600;
  font-size: 14px;
  color: #409eff;
}

/* Stats */
.result-stats {
  margin-bottom: 4px;
}

.stat-card {
  text-align: center;
  padding: 16px 8px;
  background: #f5f7fa;
  border-radius: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.chart-card {
  margin-bottom: 0;
}

.bar-chart {
  padding: 8px 0;
}

.bar-item {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.bar-label {
  width: 70px;
  font-size: 13px;
  color: #606266;
  text-align: right;
  flex-shrink: 0;
}

.bar-item :deep(.el-progress) {
  flex: 1;
}

.bar-text {
  font-size: 12px;
  font-weight: 600;
}

.result-filters {
  display: flex;
  align-items: center;
}

.issue-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* Detail */
.detail-card {
  margin-bottom: 0;
}

.issue-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid #f0f0f0;
}

.issue-item:last-child {
  border-bottom: none;
}

.issue-msg {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

.suggestion-item {
  display: flex;
  gap: 6px;
  padding: 6px 0;
  font-size: 13px;
  color: #409eff;
  border-bottom: 1px solid #f0f0f0;
}

.suggestion-item:last-child {
  border-bottom: none;
}

.sug-idx {
  font-weight: 600;
  flex-shrink: 0;
}

.case-raw {
  font-size: 12px;
  background: #f5f7fa;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  max-height: 300px;
  overflow-y: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
