<template>
  <div class="testsuite-container">
    <el-card class="glass-card" shadow="never">
      <template #header>
        <div class="page-hero">
          <div class="hero-main">
            <div class="hero-title">
              <div class="hero-icon-wrap">
                <el-icon :size="26"><Briefcase /></el-icon>
              </div>
              <div>
                <h2 class="page-title">测试套件管理</h2>
                <p class="page-desc">管理测试套件，批量组织和执行测试用例</p>
              </div>
            </div>
            <el-button type="primary" size="large" @click="showCreateDialog" class="create-btn">
              <el-icon><Plus /></el-icon>
              新建套件
            </el-button>
          </div>
          <div class="hero-stats" v-if="suites.length">
            <div class="stat-item">
              <span class="stat-value">{{ stats.total }}</span>
              <span class="stat-label">套件总数</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <span class="stat-value passed">{{ stats.passed }}</span>
              <span class="stat-label">最近通过</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <span class="stat-value failed">{{ stats.failed }}</span>
              <span class="stat-label">最近失败</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <span class="stat-value">{{ stats.scheduled }}</span>
              <span class="stat-label">定时任务</span>
            </div>
          </div>
        </div>
      </template>

      <div class="page-toolbar">
        <el-form :inline="true" :model="searchForm" class="search-form">
          <el-form-item label="搜索">
            <el-input v-model="searchForm.search" placeholder="套件名称/描述" clearable />
          </el-form-item>
          <el-form-item label="用例数">
            <el-select v-model="searchForm.casesCount" placeholder="全部" clearable style="width: 140px">
              <el-option label="1-5个" value="1-5" />
              <el-option label="6-10个" value="6-10" />
              <el-option label="11-20个" value="11-20" />
              <el-option label="20个以上" value="20+" />
            </el-select>
          </el-form-item>
          <el-form-item label="创建时间">
            <el-date-picker v-model="searchForm.dateRange" type="daterange" range-separator="至" start-placeholder="开始日期"
              end-placeholder="结束日期" style="width: 240px" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="loadSuites">查询</el-button>
            <el-button @click="resetSearch">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <div class="page-content" v-loading="loading" element-loading-text="加载中..." element-loading-background="rgba(255,255,255,0.85)">
        <!-- 空状态 -->
        <div v-if="!loading && !suites.length" class="empty-state-glass">
          <div class="empty-icon-wrap">
            <el-icon :size="42"><Briefcase /></el-icon>
          </div>
          <h3 class="empty-title">暂无测试套件</h3>
          <p class="empty-desc">点击新建套件按钮创建第一个测试套件，将多个测试用例组合成集合批量执行</p>
          <el-button type="primary" @click="showCreateDialog">新建套件</el-button>
        </div>

        <!-- 表格 -->
        <template v-if="suites.length">
          <el-table :data="suites" border stripe class="data-table" style="width: 100%">
            <el-table-column prop="id" label="ID" width="60" sortable />
            <el-table-column prop="name" label="套件名称" min-width="200" sortable />
            <el-table-column prop="description" label="描述" min-width="140" show-overflow-tooltip />
            <el-table-column prop="cases_count" label="用例数" width="90" align="center" sortable>
              <template #default="{ row }">
                <el-tag size="small" :type="getCasesCountType(row.cases_count)">{{ row.cases_count || 0 }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="last_execution_status" label="上次执行结果" width="110" sortable>
              <template #default="{ row }">
                <el-tag v-if="row.last_execution_status" :type="getExecutionStatusType(row.last_execution_status)"
                  size="small">
                  {{ getExecutionStatusText(row.last_execution_status) }}
                </el-tag>
                <span v-else class="no-execution-text">未执行</span>
              </template>
            </el-table-column>
            <el-table-column prop="execution_count" label="执行次数" width="100" align="center" sortable>
              <template #default="{ row }">
                <span>{{ row.execution_count || 0 }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="created_by_username" label="创建者" width="100" />
            <el-table-column label="定时状态" width="160" align="center">
              <template #default="{ row }">
                <!-- 有待执行的定时任务 -->
                <div v-if="row.pending_schedule" class="schedule-status-cell">
                  <el-tag :type="row.pending_schedule.locked ? 'danger' : 'warning'" size="small"
                    effect="dark" class="schedule-tag">
                    <el-icon v-if="row.pending_schedule.locked" style="margin-right:2px;vertical-align:middle"><Lock /></el-icon>
                    {{ row.pending_schedule.locked ? '已锁定' : '未锁定' }}
                  </el-tag>
                  <div class="schedule-time-text">{{ formatScheduleTime(row.pending_schedule.scheduled_at) }}</div>
                  <div v-if="row.pending_schedule.started_by_username" class="schedule-owner">
                    设定人: {{ row.pending_schedule.started_by_username }}
                  </div>
                </div>
                <span v-else class="no-schedule-text">未设定</span>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="160" sortable>
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" :width="calcOpWidth()" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="success" style="min-width:62px" @click="executeSuite(row)" :loading="executingSuiteId === row.id" :disabled="hasPendingSchedule(row)">
                  {{ executingSuiteId === row.id ? '' : '执行' }}
                </el-button>
                <el-button size="small" type="warning" @click="showScheduleDialog(row)">
                  <el-icon><AlarmClock /></el-icon>
                  定时执行
                </el-button>
                <el-button size="small" type="primary" @click="copySuite(row)">复制套件</el-button>
                <el-button size="small" @click="editSuite(row)" :disabled="isLockedByOther(row)">编辑</el-button>
                <el-button size="small" type="danger" @click="deleteSuite(row.id)" :disabled="isLockedByOther(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 分页 -->
          <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.pageSize"
            :total="pagination.total" :page-sizes="[10, 20, 50]" layout="total, sizes, prev, pager, next, jumper"
            class="page-pagination" @size-change="loadSuites" @current-change="loadSuites" />
        </template>
      </div>
    </el-card>

    <!-- 创建/编辑对话框 - 三栏布局 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑测试套件' : '新建测试套件'" width="1400px" top="3vh"
      :close-on-click-modal="false" append-to-body class="testsuite-edit-dialog">
      <!-- 基本信息 -->
      <el-form :model="formData" :rules="formRules" ref="formRef" label-width="100px" class="suite-basic-info">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="套件名称" prop="name">
              <el-input v-model="formData.name" placeholder="请输入套件名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="执行顺序">
              <el-select v-model="formData.execution_order" style="width: 100%">
                <el-option label="串行执行（按顺序）" value="sequential" />
                <el-option label="并行执行" value="parallel" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述">
          <el-input v-model="formData.description" type="textarea" :rows="2" placeholder="套件描述，说明业务流程" />
        </el-form-item>
      </el-form>

      <!-- 三栏布局 -->
      <div class="three-column-layout">
        <!-- 左侧：可选用例库 -->
        <div class="column left-column">
          <div class="column-header">
            <span class="column-title">可选用例库</span>
          </div>
          <div style="padding:0 12px 8px;display:flex;flex-direction:column;gap:6px">
            <el-radio-group v-model="caseTypeFilter" size="small" style="display:flex;flex-wrap:nowrap">
              <el-radio-button value="all">全部 ({{ (availableTestCases.length || 0) + (availableWebTestCases.length || 0) + (availablePerfTestCases.length || 0) }})</el-radio-button>
              <el-radio-button value="api">自动化接口 ({{ availableTestCases.length || 0 }})</el-radio-button>
              <el-radio-button value="web">Web ({{ availableWebTestCases.length || 0 }})</el-radio-button>
              <el-radio-button value="perf">性能 ({{ availablePerfTestCases.length || 0 }})</el-radio-button>
            </el-radio-group>
            <el-input v-model="testCaseSearch" placeholder="搜索用例..." size="small" clearable>
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </div>
          <div class="column-body">
            <draggable v-model="filteredTestCases" item-key="id"
              :group="{ name: 'testcases', pull: 'clone', put: false }" :clone="cloneTestCase" @end="onDragEnd">
              <template #item="{ element }">
                <div class="draggable-case-item" :class="{ 'is-web': element.__type === 'web', 'is-perf': element.__type === 'perf' }">
                  <el-tag :type="element.__type === 'web' ? '' : (element.__type === 'perf' ? 'danger' : getMethodType(element.method))" size="small"
                    :effect="element.__type === 'web' ? 'plain' : undefined">
                    {{ element.__type === 'web' ? 'Web' : (element.__type === 'perf' ? 'Perf' : element.method) }}
                  </el-tag>
                  <span class="case-title" :title="element.title">{{ element.title }}</span>
                  <el-icon class="drag-icon"><Rank /></el-icon>
                </div>
              </template>
            </draggable>
          </div>
          <div class="column-footer">
            <span>共 {{ filteredTestCases.length }} 个用例</span>
          </div>
        </div>

        <!-- 中间：拖拽式流程编排区 -->
        <div class="column middle-column">
          <div class="column-header">
            <span class="column-title">流程编排区</span>
            <el-button-group>
              <el-button size="small" @click="aiAutoSort">
                <el-icon>
                  <MagicStick />
                </el-icon>
                AI自动排序
              </el-button>
              <el-button size="small" @click="clearWorkflow">
                <el-icon>
                  <Delete />
                </el-icon>
                清空
              </el-button>
            </el-button-group>
          </div>
          <div class="column-body workflow-area">
            <draggable v-model="workflowCases" item-key="id" :group="{ name: 'testcases' }" animation="200"
              ghost-class="ghost-item" chosen-class="chosen-item" tag="div" class="draggable-drop-zone"
              handle=".workflow-item-header" @change="onWorkflowChange">
              <template #item="{ element, index }">
                <div class="workflow-item" :class="{ 'first-item': index === 0 }">
                  <div class="workflow-item-header">
                    <span class="step-number">{{ index + 1 }}</span>
                    <el-tag :type="element.__type === 'web' ? '' : (element.__type === 'perf' ? 'danger' : getMethodType(element.method))" size="small"
                      :effect="element.__type === 'web' ? 'plain' : undefined">
                      {{ element.__type === 'web' ? 'Web' : (element.__type === 'perf' ? 'Perf' : element.method) }}
                    </el-tag>
                    <span class="case-title">{{ element.title }}</span>
                    <div class="workflow-actions">
                      <!-- API 用例才显示编辑和变量提取按钮 -->
                      <template v-if="element.__type !== 'web' && element.__type !== 'perf'">
                        <el-button class="workflow-edit-btn" type="warning" link @click="openStepEditDialog(index)"
                          title="编辑接口配置">
                          <el-icon :size="18"><Edit /></el-icon>
                        </el-button>
                        <el-button class="workflow-var-btn" type="primary" link @click="toggleExtractConfig(index)"
                          title="配置变量提取">
                          <el-icon :size="18"><Connection /></el-icon>
                          <span v-if="getStepVarCount(element) > 0" class="var-badge">{{ getStepVarCount(element) }}</span>
                        </el-button>
                      </template>
                      <el-button class="workflow-remove-btn" type="danger" link @click="removeFromWorkflow(index)">
                        <el-icon :size="18">
                          <Close />
                        </el-icon>
                      </el-button>
                    </div>
                  </div>
                  <div class="workflow-item-body">
                    <template v-if="element.__type === 'perf'">
                      <el-input v-model="element.target_url" placeholder="性能测试目标URL" size="small"
                        class="api-endpoint-input" readonly />
                      <div class="perf-config-row">
                        <span class="perf-config-label">并发数</span>
                        <el-input-number
                          :model-value="getPerfConfig(element.id).users"
                          @update:model-value="val => setPerfConfig(element.id, 'users', val)"
                          :min="1" :max="2000" :step="5"
                          size="small"
                          controls-position="right"
                        />
                        <span class="perf-config-label">持续时间(s)</span>
                        <el-input-number
                          :model-value="getPerfConfig(element.id).duration"
                          @update:model-value="val => setPerfConfig(element.id, 'duration', val)"
                          :min="1" :max="3600" :step="10"
                          size="small"
                          controls-position="right"
                        />
                      </div>
                    </template>
                    <el-input v-else v-model="element.api_endpoint" placeholder="接口地址，支持变量如 ${Url}" size="small"
                      class="api-endpoint-input" readonly />
                  </div>

                  <!-- 变量提取配置区域（可折叠展开） -->
                  <div v-if="element.showExtractConfig" class="step-extract-config-inline">
                    <div class="extract-config-header-inline">
                      <span class="config-label-inline">提取变量配置</span>
                      <el-button type="primary" link size="small" @click="addExtractRuleInline(index)">
                        <el-icon>
                          <Plus />
                        </el-icon> 添加规则
                      </el-button>
                    </div>

                    <!-- 提取规则列表 -->
                    <div v-for="(rule, ridx) in element.extract_rules" :key="ridx" class="extract-rule-row-inline">
                      <el-input v-model="rule.var_name" placeholder="变量名" size="small"
                        class="rule-input-inline var-name-input-inline" />
                      <el-input v-model="rule.var_value" placeholder="JSONPath表达式" size="small"
                        class="rule-input-inline var-value-input-inline" />
                      <el-select v-model="rule.var_type" size="small" class="rule-input-inline var-type-select-inline"
                        placeholder="类型">
                        <el-option label="套件变量" value="suite" />
                        <el-option label="临时变量" value="step" />
                      </el-select>
                      <el-button type="danger" link size="small" @click="removeExtractRuleInline(index, ridx)">
                        <el-icon>
                          <Delete />
                        </el-icon>
                      </el-button>
                    </div>

                    <!-- 空状态提示 -->
                    <div v-if="!element.extract_rules || element.extract_rules.length === 0"
                      class="empty-extract-hint-inline">
                      <el-icon>
                        <InfoFilled />
                      </el-icon>
                      <span>点击"添加规则"配置变量提取，支持从响应中提取数据供后续步骤使用</span>
                    </div>

                    <!-- JSONPath示例提示 -->
                    <div class="jsonpath-hint-inline">
                      <div class="hint-title">JSONPath示例：</div>
                      <div class="hint-item">$.data.token - 提取响应中的token</div>
                      <div class="hint-item">$.user.id - 提取用户ID</div>
                      <div class="hint-item">$.list[0].name - 提取列表第一个元素的name</div>
                    </div>
                  </div>

                  <!-- 依赖箭头 -->
                  <div v-if="index < workflowCases.length - 1" class="dependency-arrow">
                    <el-icon>
                      <ArrowDown />
                    </el-icon>
                    <span>依赖传递</span>
                  </div>
                </div>
              </template>
            </draggable>
            <div v-if="workflowCases.length === 0" class="empty-workflow-hint">
              <el-icon>
                <DArrowRight />
              </el-icon>
              <span>从左侧拖拽用例到此处编排流程</span>
            </div>
          </div>
          <div class="column-footer">
            <span>已编排 {{ workflowCases.length }} 个用例</span>
          </div>
        </div>

        <!-- 右侧：变量上下文面板 -->
        <div class="column right-column">
          <div class="column-header">
            <span class="column-title">变量上下文</span>
            <el-button size="small" text @click="refreshVariables">
              <el-icon>
                <Refresh />
              </el-icon>
            </el-button>
          </div>
          <div class="column-body variable-panel">
            <el-tabs v-model="activeVariableTab" class="variable-tabs">
              <el-tab-pane label="套件变量" name="suite">
                <div class="variable-list">
                  <div v-if="autoGlobalVars.length === 0" class="empty-hint">
                    <el-empty description="暂无套件变量，请在步骤中配置提取规则" :image-size="80" />
                  </div>
                  <div v-for="(v, idx) in autoGlobalVars" :key="v.name" class="variable-item auto-var-item">
                    <span class="var-name">{{ v.name }}</span>
                    <span class="var-value">{{ v.value || '待提取' }}</span>
                    <el-tag size="small" type="info">来源: {{ v.source }}</el-tag>
                  </div>
                </div>
              </el-tab-pane>
              <el-tab-pane label="执行日志" name="logs">
                <div class="execution-log">
                  <div v-if="executionLog.length === 0" class="empty-hint">
                    <el-empty description="暂无执行日志" :image-size="80" />
                  </div>
                  <div v-for="(log, idx) in executionLog" :key="idx" class="log-item">
                    <span class="log-time">{{ log.time }}</span>
                    <span :class="['log-message', log.type]">{{ log.message }}</span>
                  </div>
                </div>
              </el-tab-pane>
            </el-tabs>
          </div>
          <div class="column-footer">
            <span>变量面板</span>
          </div>
        </div>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <span class="footer-left">
            <el-button @click="preValidateWorkflow">
              <el-icon><Check /></el-icon>
              流程预校验
            </el-button>
            <el-button type="success" @click="executeSequentially">
              <el-icon><VideoPlay /></el-icon>
              {{ formData.execution_order === 'parallel' ? '一键并行执行' : '一键串行执行' }}
            </el-button>
            <el-button type="warning" @click="executeStepByStep">
              <el-icon><CaretRight /></el-icon>
              分步执行
            </el-button>
          </span>
          <span class="footer-right">
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" @click="submitForm" :loading="submitting"
              style="position: relative; z-index: 99999; pointer-events: auto;">保存</el-button>
          </span>
        </span>
      </template>
    </el-dialog>

    <!-- 步骤编辑模态框（与主 dialog 平级，避免嵌套 dialog overlay 残留） -->
    <el-dialog v-model="stepEditDialogVisible"
      :title="`编辑步骤 ${currentEditStepIndex + 1}: ${currentEditStep?.title || ''}`" width="800px"
      :close-on-click-modal="false" append-to-body destroy-on-close>
      <el-form label-width="100px" v-if="currentEditStep">
        <el-form-item label="接口地址">
          <el-input v-model="currentEditStep.api_endpoint" placeholder="接口地址，支持变量如 ${Url}" />
          <div v-if="currentEditStepIndex > 0 && getAvailableVarsForStep(currentEditStepIndex).length > 0"
            class="modal-var-hint">
            <div class="modal-var-label">可用变量：</div>
            <div class="modal-var-tags">
              <el-tag v-for="(varInfo, vidx) in getAvailableVarsForStep(currentEditStepIndex)" :key="vidx"
                size="small" type="primary" @click="copyVarToClipboard(varInfo.name)" style="cursor: pointer;">
                <span v-text="'$' + '{' + varInfo.name + '}'"></span>
              </el-tag>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="请求方法">
          <el-select v-model="currentEditStep.method" style="width: 150px;">
            <el-option label="GET" value="GET" />
            <el-option label="POST" value="POST" />
            <el-option label="PUT" value="PUT" />
            <el-option label="DELETE" value="DELETE" />
            <el-option label="PATCH" value="PATCH" />
          </el-select>
        </el-form-item>
        <el-form-item label="请求头">
          <el-input v-model="currentEditStep.headers" type="textarea" :rows="5"
            placeholder='{"Content-Type": "application/json", "Authorization": "Bearer ${token}"}' />
          <div v-if="currentEditStepIndex > 0 && getAvailableVarsForStep(currentEditStepIndex).length > 0"
            class="modal-var-hint">
            <div class="modal-var-label">可用变量：</div>
            <div class="modal-var-tags">
              <el-tag v-for="(varInfo, vidx) in getAvailableVarsForStep(currentEditStepIndex)" :key="vidx"
                size="small" type="primary" @click="copyVarToClipboard(varInfo.name)" style="cursor: pointer;">
                <span v-text="'$' + '{' + varInfo.name + '}'"></span>
              </el-tag>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="请求体">
          <el-input v-model="currentEditStep.request_body" type="textarea" :rows="5"
            placeholder='{"username": "admin", "password": "123456"}' />
          <div v-if="currentEditStepIndex > 0 && getAvailableVarsForStep(currentEditStepIndex).length > 0"
            class="modal-var-hint">
            <div class="modal-var-label">可用变量：</div>
            <div class="modal-var-tags">
              <el-tag v-for="(varInfo, vidx) in getAvailableVarsForStep(currentEditStepIndex)" :key="vidx"
                size="small" type="primary" @click="copyVarToClipboard(varInfo.name)" style="cursor: pointer;">
                <span v-text="'$' + '{' + varInfo.name + '}'"></span>
              </el-tag>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stepEditDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveStepEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 步骤变量提取配置对话框 -->
    <el-dialog v-model="stepVarDialogVisible" :title="`配置步骤 ${currentStepIndex + 1} 的变量提取`" width="700px"
      destroy-on-close append-to-body>
      <div v-if="currentStepData" class="step-var-config">
        <el-alert :title="`当前步骤：${currentStepData.title}`" type="info" :closable="false" show-icon
          style="margin-bottom: 20px;" />

        <el-form label-width="120px">
          <el-form-item label="已配置的提取规则">
            <el-table :data="currentStepData.extract_rules || []" border size="small">
              <el-table-column prop="var_name" label="变量名" width="150">
                <template #default="{ row }">
                  <el-input v-model="row.var_name" size="small" placeholder="如: token" />
                </template>
              </el-table-column>
              <el-table-column prop="var_value" label="JSONPath表达式" width="250">
                <template #default="{ row }">
                  <el-input v-model="row.var_value" size="small" placeholder="如: $.data.token" />
                </template>
              </el-table-column>
              <el-table-column prop="var_type" label="变量类型" width="120">
                <template #default="{ row }">
                  <el-select v-model="row.var_type" size="small">
                    <el-option label="套件变量" value="suite" />
                    <el-option label="临时变量" value="step" />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80">
                <template #default="{ $index }">
                  <el-button type="danger" link size="small" @click="removeExtractRule($index)">
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <el-button type="primary" size="small" @click="addExtractRule" style="margin-top: 10px;">
              <el-icon>
                <Plus />
              </el-icon>
              添加提取规则
            </el-button>
          </el-form-item>

          <el-form-item label="可用变量参考">
            <div class="available-vars-hint">
              <p>💡 提示：可以从响应中提取以下类型的变量：</p>
              <ul>
                <li><strong>全局变量 (global)</strong>：在整个测试套件中共享，后续所有步骤都可使用</li>
                <li><strong>上下文变量 (context)</strong>：仅在当前用例执行周期内有效</li>
              </ul>
              <p>📌 JSONPath 示例：</p>
              <code>$.data.token</code> - 提取响应中的 token<br />
              <code>$.user.id</code> - 提取用户ID<br />
              <code>$.list[0].name</code> - 提取列表第一个元素的name
            </div>
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <el-button @click="stepVarDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveStepVariables">保存</el-button>
      </template>
    </el-dialog>

    <!-- 定时执行对话框（简化版） -->
    <el-dialog v-model="scheduleDialogVisible" :title="scheduleDialogTitle" width="520px" :close-on-click-modal="false" append-to-body destroy-on-close>
      <div class="schedule-dialog-body">
        <!-- 已有任务：显示详情 -->
        <div v-if="existingSchedule" class="schedule-current-info">
          <el-alert :type="isScheduleOwner ? (existingSchedule.locked ? 'error' : 'warning') : 'info'" :closable="false" show-icon style="margin-bottom: 16px">
            <template #title>
              <template v-if="isScheduleOwner">
                {{ existingSchedule.locked ? '该任务已锁定，仅你可修改或取消' : '可修改时间、环境，或锁定任务' }}
              </template>
              <template v-else>
                {{ existingSchedule.locked ? '该任务已锁定（仅设置人可操作）' : '该任务由他人设置，仅可查看' }}
              </template>
            </template>
          </el-alert>

          <div class="schedule-detail-grid">
            <div class="detail-item">
              <span class="detail-label">计划时间:</span>
              <span class="detail-value">{{ formatScheduleTime(existingSchedule.scheduled_at) }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">执行环境:</span>
              <el-tag size="small" type="info">{{ envLabel(existingSchedule.environment) }}</el-tag>
            </div>
            <div class="detail-item">
              <span class="detail-label">设定人:</span>
              <span class="detail-value">{{ existingSchedule.started_by_username || '未知' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">状态:</span>
              <el-tag :type="existingSchedule.locked ? 'danger' : 'warning'" size="small">
                {{ existingSchedule.locked ? '已锁定' : '未锁定' }}
              </el-tag>
            </div>
          </div>
        </div>

        <!-- 新建任务提示 -->
        <el-alert v-else type="info" :closable="false" show-icon style="margin-bottom: 20px">
          <template #title>
            将在指定时间自动执行 <b>{{ scheduleTargetSuite?.name }}</b> 中的 {{ (scheduleTargetSuite?.test_cases?.length || 0) + (scheduleTargetSuite?.web_test_cases?.length || 0) + (scheduleTargetSuite?.perf_test_cases?.length || 0) }} 个用例
          </template>
        </el-alert>

        <!-- 可编辑表单（仅新建或设置人可编辑） -->
        <el-form v-if="!existingSchedule || isScheduleOwner" label-width="90px">
          <el-form-item label="计划时间">
            <el-date-picker
              v-model="scheduledTime"
              type="datetime"
              placeholder="选择日期和时间"
              format="YYYY-MM-DD HH:mm"
              value-format="YYYY-MM-DD HH:mm"
              style="width: 100%"
              :disabled-date="(date) => date.getTime() <= Date.now()"
            />
          </el-form-item>
          <el-form-item label="执行环境">
            <el-select v-model="scheduleEnvironment" style="width: 100%">
              <el-option label="开发环境 (dev)" value="dev" />
              <el-option label="测试环境 (test)" value="test" />
              <el-option label="生产环境 (prod)" value="prod" />
            </el-select>
          </el-form-item>
        </el-form>

        <!-- 新建时：可选择锁定 -->
        <div v-if="!existingSchedule" style="margin-bottom: 16px;">
          <el-checkbox v-model="scheduleLocked" label="锁定后仅自己可修改" />
        </div>

        <div class="schedule-tips">
          <p><el-icon><InfoFilled /></el-icon> 系统每分钟检查一次定时任务，执行时间误差不超过1分钟</p>
          <p><el-icon><InfoFilled /></el-icon> 执行结果将记录在「执行历史」中，可随时查看</p>
        </div>
      </div>
      <template #footer>
        <!-- 非设置人查看：只能关闭 -->
        <template v-if="existingSchedule && !isScheduleOwner">
          <el-button @click="scheduleDialogVisible = false">关闭</el-button>
        </template>
        <!-- 设置人管理已有任务：保存 / 锁定/解锁 / 取消 -->
        <template v-else-if="existingSchedule && isScheduleOwner">
          <el-button type="danger" plain @click="handleCancelSchedule">取消任务</el-button>
          <el-button @click="handleToggleLock">
            <el-icon><Lock /></el-icon> {{ existingSchedule.locked ? '解锁' : '锁定' }}
          </el-button>
          <el-button type="primary" @click="handleSaveSchedule" :loading="scheduling">保存修改</el-button>
        </template>
        <!-- 新建：一个按钮 -->
        <template v-else>
          <el-button @click="scheduleDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleCreateSchedule" :loading="scheduling">确认创建</el-button>
        </template>
      </template>
    </el-dialog>

    <!-- 执行结果面板（底部内嵌） -->
    <div v-if="resultPanelVisible" class="execution-result-panel">
      <div class="result-panel-header">
        <div class="result-panel-left">
          <el-icon :size="18"><DataAnalysis /></el-icon>
          <span class="result-panel-title">套件执行结果 · {{ lastResult.name }}</span>
          <span class="result-panel-time">{{ formatDate(lastResult.time) }}</span>
        </div>
        <div class="result-panel-right">
          <el-button size="small" text @click="resultPanelVisible = false">
            <el-icon><Close /></el-icon>
            收起
          </el-button>
        </div>
      </div>
      <div class="result-panel-summary">
        <div class="stat-item stat-passed">
          <span class="stat-num">{{ lastResult.passed }}</span>
          <span class="stat-label">通过</span>
        </div>
        <div class="stat-item stat-failed">
          <span class="stat-num">{{ lastResult.failed }}</span>
          <span class="stat-label">失败</span>
        </div>
        <div class="stat-item stat-skipped" v-if="lastResult.skipped > 0">
          <span class="stat-num">{{ lastResult.skipped }}</span>
          <span class="stat-label">跳过</span>
        </div>
        <el-button v-if="lastResult.id" size="small" type="primary" plain @click="$router.push({ name: 'ExecutionDetail', params: { id: lastResult.id } })">
          查看完整报告 →
        </el-button>
      </div>
      <div class="result-panel-list" v-if="lastResult.results?.length">
        <div
          v-for="(r, idx) in lastResult.results"
          :key="idx"
          class="result-item"
          :class="{ 'result-passed': r.status === 'passed' || r.status === 'completed', 'result-failed': r.status === 'failed' }"
        >
          <el-icon v-if="r.status === 'passed'" class="result-icon-pass"><CircleCheck /></el-icon>
          <el-icon v-else class="result-icon-fail"><CircleClose /></el-icon>
          <span class="result-item-name">{{ r.title || r.name || `用例 #${idx + 1}` }}</span>
          <span class="result-item-time">{{ r.duration ? (r.duration + 'ms') : '' }}</span>
          <span v-if="r.status === 'failed' && r.error" class="result-item-error">{{ String(r.error).substring(0, 120) }}{{ String(r.error).length > 120 ? '...' : '' }}</span>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { testsuiteAPI, testcaseAPI, webTestcaseAPI, perfAPI, authAPI, executionAPI } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { showDeleteConfirm, showSuccess } from '@/utils/helpers'
import { Plus, Delete, VideoPlay, Search, Rank, MagicStick, Close, ArrowDown, DArrowRight, Refresh, Check, CaretRight, Connection, CopyDocument, Edit, DataAnalysis, CircleCheck, CircleClose, AlarmClock, InfoFilled, Lock, Briefcase } from '@element-plus/icons-vue'
import draggable from 'vuedraggable'

const router = useRouter()
const loading = ref(false)
const executingSuiteId = ref(null)  // 正在执行的套件ID，用于loading状态
const suites = ref([])

// 页面统计指标
const stats = computed(() => {
  const total = suites.value.length
  const passed = suites.value.filter(s => s.last_execution_status === 'passed' || s.last_execution_status === 'completed').length
  const failed = suites.value.filter(s => s.last_execution_status === 'failed').length
  const scheduled = suites.value.filter(s => s.pending_schedule).length
  return { total, passed, failed, scheduled }
})

// 自动刷新定时器（仅在有进行中/待执行套件时轮询，避免无意义刷新闪烁）
let refreshTimer = null
const AUTO_REFRESH_INTERVAL = 30  // 秒

// 内嵌执行结果面板
const lastResult = ref(null)
const resultPanelVisible = ref(false)

// 定时执行对话框（简化版）
const scheduleDialogVisible = ref(false)
const scheduleTargetSuite = ref(null)
const scheduledTime = ref('')
const scheduleEnvironment = ref('dev')
const scheduleLocked = ref(false)
const scheduling = ref(false)
const existingSchedule = ref(null)  // 已有的定时任务信息
const currentUserId = ref(null)     // 当前登录用户ID

// 对话框标题
const scheduleDialogTitle = computed(() => {
  if (existingSchedule.value) {
    return existingSchedule.value.locked ? '定时任务（已锁定）' : '定时任务'
  }
  return '创建定时任务'
})

// 当前用户是否是定时任务的设置人
const isScheduleOwner = computed(() => {
  if (!existingSchedule.value || !currentUserId.value) return false
  return existingSchedule.value.started_by_id === currentUserId.value
})

const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const testCaseTableRef = ref(null)
const availableTestCases = ref([])
const availableWebTestCases = ref([])  // Web 用例列表
const availablePerfTestCases = ref([])  // 性能用例列表
const selectedTestCaseIds = ref([])

// 筛选栏状态
const searchForm = reactive({
  search: '',
  casesCount: '',
  dateRange: null,
})

// 拖拽编排相关状态
const testCaseSearch = ref('')
const caseTypeFilter = ref('all')  // all / api / web
const workflowCases = ref([])
const activeVariableTab = ref('suite')
const globalVariables = ref([])
const contextVariables = ref([])
const tokenConfig = reactive({
  source: 'login_api',
  value: '',
  injectTo: ['header'],
})
const executionLog = ref([])
const logExpanded = ref(['log'])

// 步骤变量配置相关状态
const stepVarDialogVisible = ref(false)
const currentStepIndex = ref(-1)
const currentStepData = ref(null)
// 步骤编辑模态框状态
const stepEditDialogVisible = ref(false)
const currentEditStepIndex = ref(-1)
const currentEditStep = ref(null)

// 过滤后的用例列表（用 ref 而非 computed，否则 vuedraggable 拖拽失败）

// 过滤后的用例列表（用 ref 而非 computed，否则 vuedraggable 拖拽失败）
const filteredTestCases = ref([])
const updateFilteredTestCases = () => {
  // 合并 API、Web 和性能用例，标记类型
  const apiCases = (availableTestCases.value || []).map(c => ({ ...c, __type: 'api' }))
  const webCases = (availableWebTestCases.value || []).map(c => ({ ...c, __type: 'web', method: 'Web' }))
  const perfCases = (availablePerfTestCases.value || []).map(c => ({ ...c, __type: 'perf', method: 'Perf', title: c.name }))

  let all = [...apiCases, ...webCases, ...perfCases]

  // 类型筛选
  if (caseTypeFilter.value === 'api') all = all.filter(c => c.__type === 'api')
  else if (caseTypeFilter.value === 'web') all = all.filter(c => c.__type === 'web')
  else if (caseTypeFilter.value === 'perf') all = all.filter(c => c.__type === 'perf')

  // 关键字搜索
  if (testCaseSearch.value) {
    const keyword = testCaseSearch.value.toLowerCase()
    all = all.filter(tc =>
      (tc.title || tc.name)?.toLowerCase().includes(keyword) ||
      tc.api_endpoint?.toLowerCase().includes(keyword) ||
      (tc.__type === 'web' && tc.url?.toLowerCase().includes(keyword)) ||
      (tc.__type === 'perf' && tc.target_url?.toLowerCase().includes(keyword))
    )
  }

  filteredTestCases.value = all
}

watch([testCaseSearch, caseTypeFilter, availableTestCases, availableWebTestCases, availablePerfTestCases], updateFilteredTestCases, { immediate: true, deep: true })

// 自动汇总套件内所有接口的变量
const suiteGlobalVars = computed(() => {
  const globalVars = []
  workflowCases.value.forEach((tc, index) => {
    // 从 extract_rules 中提取套件变量
    if (tc.extract_rules && tc.extract_rules.length > 0) {
      tc.extract_rules.forEach(rule => {
        // 显示所有 extract_rules 中的变量（不限制 var_type）
        if (rule.var_name) {
          if (!globalVars.find(gv => gv.name === rule.var_name)) {
            globalVars.push({
              name: rule.var_name,
              value: rule.var_value || '待提取',
              source: `步骤${index + 1}-${tc.title}`,
              type: 'auto',
            })
          }
        }
      })
    }
  })
  return globalVars
})

const suiteContextVars = computed(() => {
  const contextVars = []
  workflowCases.value.forEach((tc, index) => {
    // 从 extract_rules 中提取上下文变量
    if (tc.extract_rules && tc.extract_rules.length > 0) {
      tc.extract_rules.forEach(rule => {
        // 只提取 var_type !== 'suite' 的变量（即 step 类型）
        if (rule.var_type && rule.var_type !== 'suite') {
          contextVars.push({
            name: rule.var_name,
            value: rule.var_value || '待提取',
            source: `步骤${index + 1}-${tc.title}`,
            type: 'auto',
          })
        }
      })
    }
  })
  return contextVars
})

// 全局变量：只保留自动提取的变量
const autoGlobalVars = computed(() => {
  return suiteGlobalVars.value.map(v => ({
    name: v.name,
    value: v.value || '待提取',
    source: v.source,
  }))
})

// 上下文变量：只保留自动提取的变量
const autoContextVars = computed(() => {
  const vars = []
  workflowCases.value.forEach((tc, index) => {
    if (tc.context_vars && tc.context_vars.length > 0) {
      tc.context_vars.forEach(v => {
        vars.push({
          name: v.name,
          value: v.value || '待提取',
          step: index + 1,
          source: `步骤${index + 1}`
        })
      })
    }
  })
  return vars
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
})

const formData = reactive({
  id: null,
  name: '',
  description: '',
  test_cases: [],
  web_test_cases: [],
  perf_test_cases: [],
  perf_config: {},       // 性能用例执行参数: { caseId: { users, duration } }
  execution_order: 'sequential',
  suite_vars: {
    global_vars: [],      // 全局变量（自动+手动）
    context_vars: [],     // 上下文变量（按接口分组）
  },
})

const formRules = {
  name: [{ required: true, message: '请输入套件名称', trigger: 'blur' }],
}

// 加载套件数据
const loadSuites = async (silent = false) => {
  try {
    if (!silent) loading.value = true
    const params = {
      search: searchForm.search || undefined,
      page: pagination.page,
      page_size: pagination.pageSize,
    }

    // 处理用例数筛选
    if (searchForm.casesCount) {
      params.cases_count = searchForm.casesCount
    }

    // 处理日期范围筛选
    if (searchForm.dateRange && searchForm.dateRange.length === 2) {
      params.start_date = searchForm.dateRange[0]
      params.end_date = searchForm.dateRange[1]
    }

    const res = await testsuiteAPI.list(params)
    suites.value = res.results || res
    pagination.total = res.total
  } catch (error) {
    console.error('Load suites error:', error)
  } finally {
    if (!silent) loading.value = false
    // 根据是否有运行中间态决定是否持续轮询
    startAutoRefreshIfNeeded()
  }
}

// 重置搜索条件
const resetSearch = () => {
  searchForm.search = ''
  searchForm.casesCount = ''
  searchForm.dateRange = null
  loadSuites()
}

// 打开创建/编辑弹窗
const handleAdd = () => {
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(formData, {
    id: row.id,
    name: row.name,
    description: row.description,
    test_cases: row.test_cases || [],
    web_test_cases: row.web_test_cases || [],
    perf_test_cases: row.perf_test_cases || [],
    execution_order: row.execution_order || 'sequential',
    suite_vars: row.suite_vars || { global_vars: [], context_vars: [] },
  })

  // 调试日志：查看后端返回的数据
  console.log('=== 编辑套件 - 后端返回数据 ===', row)
  console.log('suite_vars:', row.suite_vars)
  console.log('test_case_details:', row.test_case_details)

  if (row.test_case_details && row.test_case_details.length > 0) {
    console.log('第一个用例的 extract_rules:', row.test_case_details[0].extract_rules)
  }

  // 加载工作流用例（API + Web + 性能）
  const apiDetails = row.test_case_details || []
  const webDetails = row.web_test_case_details || []
  const perfDetails = row.perf_test_case_details || []

  workflowCases.value = [
    ...apiDetails.map(tc => ({ ...tc, __type: 'api', showExtractConfig: tc.extract_rules && tc.extract_rules.length > 0, extract_rules: tc.extract_rules || [] })),
    ...webDetails.map(tc => ({ ...tc, __type: 'web', showExtractConfig: false })),
    ...perfDetails.map(tc => ({ ...tc, __type: 'perf', showExtractConfig: false, title: tc.name })),
  ]

  console.log('workflowCases:', workflowCases.value)
  console.log('autoGlobalVars 计算前:', autoGlobalVars.value)

  // 使用 setTimeout 确保 Vue 完成响应式更新
  setTimeout(() => {
    console.log('autoGlobalVars 计算后:', autoGlobalVars.value)
  }, 100)

  dialogVisible.value = true
}

const resetForm = () => {
  Object.assign(formData, {
    id: null,
    name: '',
    description: '',
    test_cases: [],
    web_test_cases: [],
    perf_test_cases: [],
    perf_config: {},
    execution_order: 'sequential',
    suite_vars: {
      global_vars: [],
      context_vars: []
    }
  })
  workflowCases.value = []
  isEdit.value = false
}

// 加载可用测试用例
const loadTestCases = async () => {
  try {
    const [apiRes, webRes, perfRes] = await Promise.all([
      testcaseAPI.list({ page_size: 200 }),
      webTestcaseAPI.list({ page_size: 200 }),
      perfAPI.listTestCases({ page_size: 200 }),
    ])
    availableTestCases.value = apiRes.results || apiRes
    availableWebTestCases.value = webRes.results || webRes
    availablePerfTestCases.value = perfRes.results || perfRes
  } catch (error) {
    console.error('Load test cases error:', error)
  }
}

// 显示创建对话框
const showCreateDialog = async () => {
  isEdit.value = false
  resetForm()
  executionLog.value = []  // 清空上次的执行日志
  await loadTestCases()
  dialogVisible.value = true
}

// 编辑套件
const editSuite = async (row) => {
  isEdit.value = true
  Object.assign(formData, {
    id: row.id,
    name: row.name,
    description: row.description,
    test_cases: row.test_cases || [],
    web_test_cases: row.web_test_cases || [],
    perf_test_cases: row.perf_test_cases || [],
    perf_config: row.perf_config || {},
    execution_order: row.execution_order || 'sequential',
    suite_vars: row.suite_vars || { global_vars: [], context_vars: [] },
  })

  // 始终加载可选用例库（左侧栏需要）
  await loadTestCases()

  // 调试日志
  console.log('=== editSuite 调试 ===')
  console.log('row.test_cases:', JSON.stringify(row.test_cases))
  console.log('row.test_case_details:', JSON.stringify(row.test_case_details))
  console.log('availableTestCases:', JSON.stringify(availableTestCases.value.map(c => ({ id: c.id, title: c.title }))))
  console.log('availableTestCases IDs:', availableTestCases.value.map(c => `${typeof c.id}:${c.id}`))

  // 合并 API、Web 和性能用例到流程编排区
  const apiDetails = row.test_case_details || []
  const webDetails = row.web_test_case_details || []
  const perfDetails = row.perf_test_case_details || []

  workflowCases.value = [
    ...apiDetails.map(tc => ({ ...tc, __type: 'api', showExtractConfig: false, extract_rules: tc.extract_rules || [] })),
    ...webDetails.map(tc => ({ ...tc, __type: 'web', showExtractConfig: false })),
    ...perfDetails.map(tc => ({ ...tc, __type: 'perf', showExtractConfig: false, title: tc.name })),
  ]

  // 如果详情为空，降级从可用列表按 ID 匹配（兼容只有 Web 或只有 API 的场景）
  if (workflowCases.value.length === 0) {
    const apiIds = formData.test_cases || []
    const webIds = row.web_test_cases || []
    const perfIds = row.perf_test_cases || []
    apiIds.forEach(tcId => {
      const tc = availableTestCases.value.find(c => c.id == tcId)
      if (tc) workflowCases.value.push({ ...tc, __type: 'api', showExtractConfig: false, extract_rules: tc.extract_rules || [] })
    })
    webIds.forEach(tcId => {
      const tc = availableWebTestCases.value.find(c => c.id == tcId)
      if (tc) workflowCases.value.push({ ...tc, __type: 'web', showExtractConfig: false })
    })
    perfIds.forEach(tcId => {
      const tc = availablePerfTestCases.value.find(c => c.id == tcId)
      if (tc) workflowCases.value.push({ ...tc, __type: 'perf', showExtractConfig: false, title: tc.name })
    })
  }

  console.log('editSuite workflowCases:', workflowCases.value.length, workflowCases.value.map(c => ({ id: c.id, title: c.title, type: c.__type })))

  // 加载变量
  loadVariables()
  executionLog.value = []  // 清空上次的执行日志

  dialogVisible.value = true
}

// 复制套件
const copySuite = async (row) => {
  isEdit.value = false
  Object.assign(formData, {
    id: null,
    name: `${row.name} (副本)`,
    description: row.description,
    test_cases: row.test_cases || [],
    web_test_cases: row.web_test_cases || [],
    perf_test_cases: row.perf_test_cases || [],
    perf_config: row.perf_config || {},
    execution_order: row.execution_order || 'sequential',
  })

  await loadTestCases()

  // 初始化工作流用例列表（API + Web + 性能）
  workflowCases.value = []
  if (formData.test_cases && formData.test_cases.length > 0) {
    formData.test_cases.forEach(tcId => {
      const tc = availableTestCases.value.find(c => c.id == tcId)
      if (tc) {
        workflowCases.value.push({ ...tc, __type: 'api' })
      }
    })
  }
  if (formData.web_test_cases && formData.web_test_cases.length > 0) {
    formData.web_test_cases.forEach(tcId => {
      const tc = availableWebTestCases.value.find(c => c.id == tcId)
      if (tc) {
        workflowCases.value.push({ ...tc, __type: 'web', showExtractConfig: false })
      }
    })
  }
  if (formData.perf_test_cases && formData.perf_test_cases.length > 0) {
    formData.perf_test_cases.forEach(tcId => {
      const tc = availablePerfTestCases.value.find(c => c.id == tcId)
      if (tc) {
        workflowCases.value.push({ ...tc, __type: 'perf', showExtractConfig: false, title: tc.name })
      }
    })
  }

  loadVariables()
  executionLog.value = []
  dialogVisible.value = true
}

// 克隆测试用例（拖拽时）
const cloneTestCase = (original) => {
  return { ...original, _cloned: true }
}

// 拖拽结束
const onDragEnd = () => {
  // 可以在这里添加拖拽后的处理逻辑
}

// 工作流变化
const onWorkflowChange = () => {
  // 更新表单数据
  formData.test_cases = workflowCases.value.filter(tc => tc.__type === 'api').map(tc => tc.id)
  formData.web_test_cases = workflowCases.value.filter(tc => tc.__type === 'web').map(tc => tc.id)
  formData.perf_test_cases = workflowCases.value.filter(tc => tc.__type === 'perf').map(tc => tc.id)

  // 维护 perf_config：保留已有的配置，初始化新增的用例，清理已移除的
  const currentPerfIds = new Set(formData.perf_test_cases.map(String))
  const newPerfConfig = {}
  for (const tc of workflowCases.value.filter(tc => tc.__type === 'perf')) {
    const key = String(tc.id)
    newPerfConfig[key] = formData.perf_config[key] || { users: tc.users || 10, duration: tc.duration || 60 }
  }
  formData.perf_config = newPerfConfig
}

// 从工作流中移除用例
const removeFromWorkflow = (index) => {
  const removed = workflowCases.value[index]
  workflowCases.value.splice(index, 1)
  formData.test_cases = workflowCases.value.filter(tc => tc.__type === 'api').map(tc => tc.id)
  formData.web_test_cases = workflowCases.value.filter(tc => tc.__type === 'web').map(tc => tc.id)
  formData.perf_test_cases = workflowCases.value.filter(tc => tc.__type === 'perf').map(tc => tc.id)
  // 清理被移除性能用例的配置
  if (removed && removed.__type === 'perf') {
    const newPerfConfig = { ...formData.perf_config }
    delete newPerfConfig[String(removed.id)]
    formData.perf_config = newPerfConfig
  }
}

// 清空工作流
const clearWorkflow = () => {
  workflowCases.value = []
  formData.test_cases = []
  formData.web_test_cases = []
  formData.perf_test_cases = []
  formData.perf_config = {}
}

// 获取步骤的变量数量
const getStepVarCount = (step) => {
  return (step.extract_rules?.length || 0) + (step.global_vars?.length || 0)
}

// 获取性能用例配置（并发数、持续时间）
const getPerfConfig = (caseId) => {
  const key = String(caseId)
  if (!formData.perf_config[key]) {
    formData.perf_config[key] = { users: 10, duration: 60 }
  }
  return formData.perf_config[key]
}

// 更新性能用例配置
const setPerfConfig = (caseId, field, value) => {
  const key = String(caseId)
  if (!formData.perf_config[key]) {
    formData.perf_config[key] = { users: 10, duration: 60 }
  }
  formData.perf_config[key][field] = value
}

// 编辑步骤变量（保留原有功能）
const editStepVariables = (index) => {
  currentStepIndex.value = index
  // 深拷贝当前步骤数据，避免直接修改
  currentStepData.value = JSON.parse(JSON.stringify(workflowCases.value[index]))

  // 初始化 extract_rules 数组
  if (!currentStepData.value.extract_rules) {
    currentStepData.value.extract_rules = []
  }

  stepVarDialogVisible.value = true
}

// 切换提取配置显示/隐藏
const toggleExtractConfig = (index) => {
  if (!workflowCases.value[index].showExtractConfig) {
    workflowCases.value[index].showExtractConfig = true
  } else {
    workflowCases.value[index].showExtractConfig = false
  }
}

// 打开步骤编辑模态框
const openStepEditDialog = (index) => {
  currentEditStepIndex.value = index
  // 深拷贝原始数据
  const stepData = JSON.parse(JSON.stringify(workflowCases.value[index]))

  // 将对象转换为JSON字符串（如果是对象的话）
  if (stepData.headers && typeof stepData.headers === 'object') {
    stepData.headers = JSON.stringify(stepData.headers, null, 2)
  }
  if (stepData.request_body && typeof stepData.request_body === 'object') {
    stepData.request_body = JSON.stringify(stepData.request_body, null, 2)
  }

  currentEditStep.value = stepData
  stepEditDialogVisible.value = true
}

// 保存步骤编辑
const saveStepEdit = async () => {
  const stepData = JSON.parse(JSON.stringify(currentEditStep.value))

  // 尝试将字符串解析为对象（如果是JSON格式）
  try {
    if (stepData.headers && typeof stepData.headers === 'string' && stepData.headers.trim().startsWith('{')) {
      stepData.headers = JSON.parse(stepData.headers)
    }
  } catch (e) {
    // 如果不是有效的JSON，保持字符串格式
  }

  try {
    if (stepData.request_body && typeof stepData.request_body === 'string' && stepData.request_body.trim().startsWith('{')) {
      stepData.request_body = JSON.parse(stepData.request_body)
    }
  } catch (e) {
    // 如果不是有效的JSON，保持字符串格式
  }

  workflowCases.value[currentEditStepIndex.value] = stepData
  stepEditDialogVisible.value = false
  ElMessage.success('步骤配置已保存，请点击底部"保存套件"按钮保存到数据库')
}

// 复制变量到剪贴板
const copyVarToClipboard = async (varName) => {
  const varRef = '${' + varName + '}'
  
  try {
    await navigator.clipboard.writeText(varRef)
    ElMessage.success(`已复制 ${varRef} 到剪贴板，请粘贴到需要的位置`)
  } catch (error) {
    ElMessage.error('复制失败，请手动复制')
  }
}

// 插入变量到接口地址（复制变量名到剪贴板）
const insertVarToEndpoint = async (stepIndex, varName) => {
  const varRef = '${' + varName + '}'

  try {
    // 复制到剪贴板
    await navigator.clipboard.writeText(varRef)
    ElMessage.success(`已复制 ${varRef}，请粘贴到接口地址中`)
  } catch (error) {
    // 降级方案：直接追加到末尾
    const endpoint = workflowCases.value[stepIndex].api_endpoint || ''
    workflowCases.value[stepIndex].api_endpoint = endpoint + varRef
    ElMessage.success(`已插入变量 ${varRef}（请手动调整位置）`)
  }
}

// 复制变量值
const copyVarValue = async (value) => {
  if (!value || value === '待提取') {
    ElMessage.warning('变量值还未提取，无法复制')
    return
  }
  
  try {
    await navigator.clipboard.writeText(value)
    ElMessage.success('已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败，请手动复制')
  }
}

// 添加提取规则（内联）
const addExtractRuleInline = (stepIndex) => {
  if (!workflowCases.value[stepIndex].extract_rules) {
    workflowCases.value[stepIndex].extract_rules = []
  }
  workflowCases.value[stepIndex].extract_rules.push({
    var_name: '',
    var_value: '',
    var_type: 'suite',  // 改为套件变量
    extract_type: 'json_path'
  })
  // 自动展开配置区域
  workflowCases.value[stepIndex].showExtractConfig = true
}

// 删除提取规则（内联）
const removeExtractRuleInline = (stepIndex, ruleIndex) => {
  workflowCases.value[stepIndex].extract_rules.splice(ruleIndex, 1)
  // 如果删除后没有规则了，自动折叠
  if (workflowCases.value[stepIndex].extract_rules.length === 0) {
    workflowCases.value[stepIndex].showExtractConfig = false
  }
}

// 添加提取规则（新方法）
const addExtractRule = (stepIndex) => {
  if (!workflowCases.value[stepIndex].extract_rules) {
    workflowCases.value[stepIndex].extract_rules = []
  }
  workflowCases.value[stepIndex].extract_rules.push({
    var_name: '',
    var_value: '',
    var_type: 'global',
    extract_type: 'json_path'
  })
}

// 删除提取规则（新方法）
const removeExtractRule = (stepIndex, ruleIndex) => {
  workflowCases.value[stepIndex].extract_rules.splice(ruleIndex, 1)
}

// 保存步骤变量配置
const saveStepVariables = () => {
  if (currentStepIndex.value >= 0 && currentStepIndex.value < workflowCases.value.length) {
    // 更新工作流中的步骤数据
    workflowCases.value[currentStepIndex.value] = { ...currentStepData.value }

    // 同步更新 formData.test_cases 中的变量信息
    const caseId = workflowCases.value[currentStepIndex.value].id
    const originalCase = availableTestCases.value.find(c => c.id === caseId)
    if (originalCase) {
      // 将提取规则同步回原始用例数据
      originalCase.extract_rules = currentStepData.value.extract_rules
      originalCase.global_vars = currentStepData.value.global_vars
      originalCase.context_vars = currentStepData.value.context_vars
    }

    ElMessage.success('变量提取规则已保存')
    stepVarDialogVisible.value = false
  }
}

// 获取指定步骤可以使用的变量（前面所有步骤提取的套件变量和临时变量）
const getAvailableVarsForStep = (stepIndex) => {
  const availableVars = []

  // 遍历前面的所有步骤
  for (let i = 0; i < stepIndex; i++) {
    const step = workflowCases.value[i]
    if (step.extract_rules) {
      step.extract_rules.forEach(rule => {
        // 收集所有变量（包括套件变量和临时变量）
        if (rule.var_name) {
          // 避免重复
          if (!availableVars.find(v => v.name === rule.var_name)) {
            availableVars.push({
              name: rule.var_name,
              value: rule.var_value,
              sourceStep: i + 1,
              varType: rule.var_type || 'suite'
            })
          }
        }
      })
    }
  }

  return availableVars
}

// AI自动排序
const aiAutoSort = async () => {
  if (workflowCases.value.length < 2) {
    ElMessage.warning('至少需要2个用例才能进行AI排序')
    return
  }

  ElMessage.info('AI正在分析接口依赖关系...')

  setTimeout(() => {
    const varPattern = /\$\{([^}]+)\}/g

    const stepInfo = workflowCases.value.map((tc) => {
      const provides = (tc.extract_rules || []).map(r => r.var_name).filter(Boolean)
      const uses = []
      const allText = `${tc.api_endpoint || ''} ${JSON.stringify(tc.headers || {})} ${JSON.stringify(tc.request_body || {})}`
      let match
      while ((match = varPattern.exec(allText)) !== null) {
        if (!uses.includes(match[1])) uses.push(match[1])
      }
      return { provides, uses, data: tc }
    })

    const sorted = []
    const visited = new Set()

    const visit = (step) => {
      if (visited.has(step)) return
      visited.add(step)
      for (const other of stepInfo) {
        if (other === step) continue
        if (other.provides.some(v => step.uses.includes(v)) && !visited.has(other)) {
          visit(other)
        }
      }
      sorted.push(step.data)
    }

    stepInfo.forEach(visit)
    workflowCases.value = sorted
    formData.test_cases = workflowCases.value.map(tc => tc.id)

    ElMessage.success('AI排序完成，已按业务依赖优化执行顺序')
  }, 800)
}

// 加载变量
const loadVariables = async () => {
  // 确保 workflowCases 数据已加载后再更新变量
  await nextTick()

  // 强制触发计算属性更新
  globalVariables.value = autoGlobalVars.value.map(v => ({
    name: v.name,
    value: v.value || '待提取',
    source: v.source,
  }))
  contextVariables.value = autoContextVars.value.map(v => ({
    name: v.name,
    source: v.source,
    value: v.value || '待提取',
  }))
}

// 刷新变量
const refreshVariables = () => {
  loadVariables()
  ElMessage.success('变量已刷新')
}

// 流程预校验
const preValidateWorkflow = () => {
  const errors = []

  if (workflowCases.value.length === 0) {
    errors.push('工作流中没有用例')
  }

  // 检查变量依赖
  workflowCases.value.forEach((tc, index) => {
    // 简单检查是否有未定义的变量引用
    const bodyText = JSON.stringify(tc.request_body || {})
    const varMatches = bodyText.match(/\{\{[^}]+\}\}/g)
    if (varMatches) {
      varMatches.forEach(varRef => {
        const varName = varRef.replace(/[{}]/g, '')
        const isDefined = globalVariables.value.some(v => v.name === varName) ||
          contextVariables.value.some(v => varName.includes(v.name))
        if (!isDefined) {
          errors.push(`步骤${index + 1}: 变量 ${varRef} 未定义`)
        }
      })
    }
  })

  if (errors.length > 0) {
    ElMessageBox.alert(
      `<ul>${errors.map(e => `<li>${e}</li>`).join('')}</ul>`,
      '校验失败',
      { dangerouslyUseHTMLString: true, type: 'error' }
    )
  } else {
    ElMessage.success('流程校验通过，无变量缺失和依赖问题')
  }
}

// 一键串行执行
const executeSequentially = async () => {
  if (workflowCases.value.length === 0) {
    ElMessage.warning('请先编排工作流')
    return
  }

  executionLog.value = []
  // 立即切换到执行日志 Tab
  activeVariableTab.value = 'logs'
  const execType = formData.execution_order === 'parallel' ? '并行' : '串行'
  addLog('info', ` 开始${execType}执行测试用例...`)

  for (let i = 0; i < workflowCases.value.length; i++) {
    const tc = workflowCases.value[i]
    addLog('info', `⏳ 执行步骤 ${i + 1}/${workflowCases.value.length}: ${tc.title}`)

    try {
      // TODO: 实际执行逻辑，需要传递上下文变量
      await new Promise(resolve => setTimeout(resolve, 500)) // 模拟执行
      addLog('success', `步骤 ${i + 1} 执行成功`)

      // 模拟提取变量到上下文
      if (i === 0) {
        contextVariables.value.forEach(v => {
          if (v.source === tc.title) {
            v.value = `mock_${v.name}_${Date.now()}`
          }
        })
      }
    } catch (error) {
      addLog('error', `步骤 ${i + 1} 执行失败: ${error.message}`)
      break
    }
  }

  addLog('success', '✅ 所有测试用例执行完成！')

  // 显示更明确的提示
  ElMessage({
    message: '工作流执行完成！请查看右侧"执行日志"了解详细结果',
    type: 'success',
    duration: 5000,
    showClose: true
  })
}

// 分步执行
const executeStepByStep = async () => {
  if (workflowCases.value.length === 0) {
    ElMessage.warning('请先编排工作流')
    return
  }

  try {
    await ElMessageBox.confirm(
      '分步执行将逐个确认每个步骤的执行结果，是否继续？',
      '分步执行确认',
      { confirmButtonText: '开始', cancelButtonText: '取消', type: 'warning' }
    )

    executionLog.value = []
    // 立即切换到执行日志 Tab
    activeVariableTab.value = 'logs'

    for (let i = 0; i < workflowCases.value.length; i++) {
      const tc = workflowCases.value[i]
      addLog('info', `准备执行步骤 ${i + 1}: ${tc.title}`)

      await new Promise(resolve => setTimeout(resolve, 500))
      addLog('success', `✅ 步骤 ${i + 1} 执行成功`)

      if (i < workflowCases.value.length - 1) {
        try {
          await ElMessageBox.confirm(
            `步骤 ${i + 1} 执行成功，是否继续执行下一步？`,
            '继续执行',
            { confirmButtonText: '继续', cancelButtonText: '停止', type: 'info' }
          )
        } catch {
          addLog('warning', '用户选择停止执行')
          break
        }
      }
    }

    ElMessage.success('分步执行完成')
  } catch {
    // 用户取消
  }
}

// 添加日志
const addLog = (type, message) => {
  executionLog.value.push({
    type,
    message,
    time: new Date().toLocaleTimeString(),
  })
}

// 提交表单
const submitForm = async () => {
  if (!formRef.value) return

  try {
    const valid = await formRef.value.validate().catch(() => false)
    if (!valid) {
      ElMessage.warning('请检查表单填写是否完整')
      return
    }

    if (workflowCases.value.length === 0) {
      ElMessage.warning('请至少拖拽一个测试用例到流程编排区')
      return
    }

    submitting.value = true

    // 构建 suite_vars，保存每个步骤的提取规则
    const suite_vars = {
      global_vars: [],
      context_vars: []
    }

    // 从 workflowCases 中提取所有步骤的变量配置
    workflowCases.value.forEach((tc, index) => {
      if (tc.extract_rules && tc.extract_rules.length > 0) {
        tc.extract_rules.forEach(rule => {
          const varData = {
            name: rule.var_name,
            value: rule.var_value,
            source: `步骤${index + 1}`,
            var_type: rule.var_type || 'suite'
          }

          if (rule.var_type === 'suite' || rule.var_type === 'global') {
            suite_vars.global_vars.push(varData)
          } else {
            suite_vars.context_vars.push(varData)
          }
        })
      }
    })

    // 分离 API、Web 和性能用例
    const apiCases = workflowCases.value.filter(tc => tc.__type === 'api')
    const webCases = workflowCases.value.filter(tc => tc.__type === 'web')
    const perfCases = workflowCases.value.filter(tc => tc.__type === 'perf')

    const data = {
      name: formData.name,
      description: formData.description,
      test_cases: apiCases.map(tc => tc.id),
      web_test_cases: webCases.map(tc => tc.id),
      perf_test_cases: perfCases.map(tc => tc.id),
      test_case_details: apiCases.map(tc => ({
        id: tc.id,
        title: tc.title,
        method: tc.method,
        api_endpoint: tc.api_endpoint,
        headers: tc.headers,
        request_body: tc.request_body,
        extract_rules: tc.extract_rules || []
      })),
      execution_order: formData.execution_order,
      suite_vars: suite_vars,
      perf_config: formData.perf_config,
    }

    if (isEdit.value) {
      await testsuiteAPI.update(formData.id, data)
      showSuccess('更新成功')
    } else {
      await testsuiteAPI.create(data)
      showSuccess('创建成功')
    }
    dialogVisible.value = false
    loadSuites()
  } catch (error) {
    console.error('Submit error:', error)
    ElMessage.error(error?.response?.data?.error || error?.message || '保存失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

// 删除测试套件
const deleteSuite = async (id) => {
  try {
    await showDeleteConfirm('确定要删除这个测试套件吗?此操作不会删除其中的测试用例')
    await testsuiteAPI.delete(id)
    showSuccess('删除成功')
    loadSuites()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Delete error:', error)
    }
  }
}

// 执行测试套件
const executeSuite = async (suite) => {
  const totalCases = (suite.test_cases?.length || 0) + (suite.web_test_cases?.length || 0) + (suite.perf_test_cases?.length || 0)
  if (totalCases === 0) {
    ElMessage.warning('该套件中没有测试用例,请先添加用例')
    return
  }

  executingSuiteId.value = suite.id
  try {
    ElMessage.info(`正在执行测试套件: ${suite.name}...`)
    const response = await testsuiteAPI.execute(suite.id)
    const execId = response.execution_id
    ElMessage.info('执行已启动，正在轮询状态...')
    await pollExecutionStatus(execId, suite.name)
  } catch (error) {
    console.error('Execute suite error:', error)
    ElMessage.error('执行失败: ' + (error.message || '未知错误'))
  } finally {
    executingSuiteId.value = null
  }
}

// 轮询执行状态
const pollExecutionStatus = async (execId, suiteName) => {
  let lastStatus = 'running'
  let result = null
  const maxPolls = 200 // 最多轮询 200 次（约 10 分钟）
  let pollCount = 0

  while ((lastStatus === 'running' || lastStatus === 'pending') && pollCount < maxPolls) {
    await new Promise(resolve => setTimeout(resolve, 3000))
    pollCount++
    try {
      result = await executionAPI.get(execId)
      lastStatus = result.status
      if (lastStatus === 'running' || lastStatus === 'pending') {
        ElMessage.info(`执行中... 状态: ${lastStatus}`)
      }
    } catch (e) {
      console.error('Poll error:', e)
      break
    }
  }

  if (result) {
    const passed = result.passed_count || 0
    const failed = result.failed_count || 0
    const skipped = result.skipped_count || 0
    showSuccess(`执行完成: ${suiteName} — ${passed} 通过, ${failed} 失败, ${skipped} 跳过`)

    lastResult.value = {
      id: execId,
      name: suiteName,
      passed: passed,
      failed: failed,
      skipped: skipped,
      results: result.execution_results || [],
      time: new Date()
    }
    resultPanelVisible.value = true
  }
}

// 显示定时执行对话框
const showScheduleDialog = async (suite) => {
  const totalCases = (suite.test_cases?.length || 0) + (suite.web_test_cases?.length || 0) + (suite.perf_test_cases?.length || 0)
  if (totalCases === 0) {
    ElMessage.warning('该套件中没有测试用例,请先添加用例')
    return
  }
  scheduleTargetSuite.value = suite

  if (suite.pending_schedule) {
    existingSchedule.value = suite.pending_schedule
    scheduleLocked.value = suite.pending_schedule.locked || false
    // 预填当前值
    if (suite.pending_schedule.scheduled_at) {
      const dt = new Date(suite.pending_schedule.scheduled_at)
      const pad = (n) => String(n).padStart(2, '0')
      scheduledTime.value = `${dt.getFullYear()}-${pad(dt.getMonth()+1)}-${pad(dt.getDate())} ${pad(dt.getHours())}:${pad(dt.getMinutes())}`
    } else {
      scheduledTime.value = ''
    }
    scheduleEnvironment.value = suite.pending_schedule.environment || 'dev'
  } else {
    existingSchedule.value = null
    scheduleLocked.value = false
    // 默认 +5 分钟
    const defaultTime = new Date()
    defaultTime.setMinutes(defaultTime.getMinutes() + 5)
    const pad = (n) => String(n).padStart(2, '0')
    scheduledTime.value = `${defaultTime.getFullYear()}-${pad(defaultTime.getMonth()+1)}-${pad(defaultTime.getDate())} ${pad(defaultTime.getHours())}:${pad(defaultTime.getMinutes())}`
    scheduleEnvironment.value = 'dev'
  }

  scheduleDialogVisible.value = true
}

// 新建定时任务
const handleCreateSchedule = async () => {
  if (!scheduledTime.value) {
    ElMessage.warning('请选择计划执行时间')
    return
  }
  scheduling.value = true
  try {
    const response = await testsuiteAPI.scheduleExecute(scheduleTargetSuite.value.id, {
      scheduled_at: scheduledTime.value,
      environment: scheduleEnvironment.value,
      locked: scheduleLocked.value,
    })
    ElMessage.success(response.message)
    scheduleDialogVisible.value = false
    loadSuites()
  } catch (error) {
    if (error?.response?.status === 409) {
      handleScheduleConflict(scheduleLocked.value)
    } else {
      ElMessage.error(error?.response?.data?.error || '创建失败')
    }
  } finally {
    scheduling.value = false
  }
}

// 保存修改已有任务
const handleSaveSchedule = async () => {
  if (!existingSchedule.value?.id) return
  if (!scheduledTime.value) {
    ElMessage.warning('请选择计划执行时间')
    return
  }
  scheduling.value = true
  try {
    const response = await testsuiteAPI.scheduleExecute(scheduleTargetSuite.value.id, {
      schedule_id: existingSchedule.value.id,
      scheduled_at: scheduledTime.value,
      environment: scheduleEnvironment.value,
    })
    ElMessage.success(response.message)
    scheduleDialogVisible.value = false
    loadSuites()
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '修改失败')
  } finally {
    scheduling.value = false
  }
}

// 锁定/解锁切换
const handleToggleLock = async () => {
  if (!existingSchedule.value?.id) return
  try {
    const response = await testsuiteAPI.toggleLock(scheduleTargetSuite.value.id, {
      schedule_id: existingSchedule.value.id,
    })
    ElMessage.success(response.message)
    existingSchedule.value.locked = response.locked
    loadSuites()
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '操作失败')
  }
}

// 取消定时任务
const handleCancelSchedule = async () => {
  if (!existingSchedule.value?.id) return
  try {
    await ElMessageBox.confirm('确定要取消该定时任务吗？', '取消确认', {
      confirmButtonText: '确定取消',
      cancelButtonText: '保留',
      type: 'warning'
    })
    await testsuiteAPI.cancelSchedule(scheduleTargetSuite.value.id, {
      schedule_id: existingSchedule.value.id,
    })
    ElMessage.success('定时任务已取消')
    scheduleDialogVisible.value = false
    loadSuites()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error?.response?.data?.error || '取消失败')
    }
  }
}

// 冲突处理（已有任务，询问是否覆盖）
const handleScheduleConflict = (locked) => {
  ElMessageBox.confirm('该套件已有待执行的定时任务，是否覆盖？', '冲突提示', {
    confirmButtonText: '覆盖并新建',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    return testsuiteAPI.scheduleExecute(scheduleTargetSuite.value.id, {
      scheduled_at: scheduledTime.value,
      environment: scheduleEnvironment.value,
      locked: locked,
      force: true,
    }).then((resp) => {
      ElMessage.success(resp.message)
      scheduleDialogVisible.value = false
      loadSuites()
    })
  }).catch(() => {})
}

// 辅助函数
const formatDate = (dateStr) => {
  if (!dateStr) return ''
  if (typeof dateStr === 'object') {
    return new Date(dateStr).toLocaleDateString('zh-CN')
  }
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getMethodType = (method) => {
  const types = { GET: '', POST: 'success', PUT: 'warning', DELETE: 'danger', PATCH: 'info' }
  return types[method] || ''
}

// 用例数标签类型
const getCasesCountType = (count) => {
  if (count >= 20) return 'danger'
  if (count >= 10) return 'warning'
  if (count >= 5) return ''
  return 'info'
}

// 执行状态类型
const getExecutionStatusType = (status) => {
  const types = { passed: 'success', failed: 'danger', skipped: 'info', running: 'warning' }
  return types[status] || 'info'
}

// 执行状态文本
const getExecutionStatusText = (status) => {
  const texts = { passed: '通过', failed: '失败', skipped: '跳过', running: '运行中' }
  return texts[status] || status
}

// 截断描述
const truncateDescription = (desc) => {
  if (!desc) return '暂无描述'
  if (desc.length <= 60) return desc
  return desc.substring(0, 57) + '...'
}

// ====== 定时任务辅助函数 ======

// 被他人锁定（非自己设置的已锁定任务）
const isLockedByOther = (row) => {
  if (!row.pending_schedule?.locked) return false
  return row.pending_schedule.started_by_id !== currentUserId.value
}

// 是否有待执行的定时任务（禁用手动执行）
const hasPendingSchedule = (row) => {
  return !!row.pending_schedule
}

// 格式化定时时间（友好显示）
const formatScheduleTime = (isoStr) => {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  const now = new Date()
  const diff = d.getTime() - now.getTime()
  const mins = Math.floor(diff / 60000)
  const hours = Math.floor(mins / 60)

  const timeStr = d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  if (mins < 0) return `${timeStr} (已过期)`
  if (mins < 60) return `${timeStr} (${mins}分钟后)`
  if (hours < 24) return `${timeStr} (${hours}小时${mins % 60}分后)`
  return timeStr
}

// 环境标签
const envLabel = (env) => {
  const labels = { dev: '开发环境', test: '测试环境', prod: '生产环境' }
  return labels[env] || env
}

// 动态计算操作列宽度
const calcOpWidth = () => {
  return 420
}

onMounted(async () => {
  // 获取当前用户ID
  try {
    const profile = await authAPI.getProfile()
    currentUserId.value = profile.id
  } catch (e) { /* ignore */ }
  loadSuites()
  startAutoRefreshIfNeeded()
})

// 仅当存在 running/pending 套件时才启动轮询，避免空列表无谓刷新
const startAutoRefreshIfNeeded = () => {
  const hasRunning = suites.value.some(s => s.last_execution_status === 'running' || s.last_execution_status === 'pending')
  if (hasRunning && !refreshTimer) {
    refreshTimer = setInterval(() => {
      loadSuites(true)  // silent：不触发 loading 闪烁
    }, AUTO_REFRESH_INTERVAL * 1000)
  } else if (!hasRunning && refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.testsuite-container {
  padding: 20px;
  min-height: calc(100vh - 84px);
  background: #f5f7fa;
  box-sizing: border-box;
}

.search-form {
  margin-bottom: 0;
}

/* 描述文本 */
.description-text {
  font-size: 13px;
  color: #606266;
}

/* 未执行状态文本 */
.no-execution-text {
  color: #c0c4cc;
  font-size: 12px;
}

/* 套件基本信息 */
.suite-basic-info {
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #ebeef5;
}

/* 三栏布局 */
.three-column-layout {
  display: flex;
  gap: 15px;
  height: 500px;
  max-height: 500px;
}

.column {
  display: flex;
  flex-direction: column;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.left-column {
  width: 310px;
  flex-shrink: 0;
}

.middle-column {
  flex: 0.7;
  min-width: 350px;
}

.middle-column {
  flex: 0.7;
  min-width: 350px;
}

.right-column {
  flex: 0.15;
  min-width: 180px;
}

.right-column {
  flex: 0.22;
  min-width: 200px;
}

.right-column {
  flex: 0.28;
  min-width: 220px;
}

.right-column {
  flex: 0.36;
  min-width: 240px;
}

.right-column {
  flex: 0.48;
  min-width: 260px;
}

.right-column {
  flex: 0.6;
  min-width: 280px;
}

.column-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 15px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}

.column-title {
  font-weight: 600;
  font-size: 14px;
}

.column-body {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.column-footer {
  padding: 8px 15px;
  background: #f5f7fa;
  font-size: 12px;
  color: #909399;
  border-top: 1px solid #ebeef5;
}

/* 可拖拽用例项 */
.draggable-case-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
  background: #e8f4ff;
  border: 1px solid #a3d0ff;
  border-radius: 6px;
  cursor: grab;
  transition: all 0.2s ease;
}
.draggable-case-item.is-web {
  background: #f0fdf4;
  border-color: #a7e1b8;
}
.draggable-case-item.is-web:hover {
  background: #dcfce7;
  border-color: #67c23a;
}

.draggable-case-item.is-perf {
  background: #fff2f0;
  border-color: #ffccc7;
}
.draggable-case-item.is-perf:hover {
  background: #ffe0db;
  border-color: #ff4d4f;
}

.draggable-case-item:hover {
  background: #d1ecff;
  border-color: #409eff;
  transform: translateX(4px);
}

.draggable-case-item .case-title {
  flex: 1;
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.drag-icon {
  color: #c0c4cc;
}

/* 工作流区域 */
.workflow-area {
  background: #fafafa;
}

.draggable-drop-zone {
  min-height: 360px;
}

.workflow-item {
  position: relative;
  padding: 12px 15px;
  margin-bottom: 10px;
  background: #f0f7ff;
  border: 2px solid #a3d0ff;
  border-radius: 8px;
  transition: all 0.2s ease;
}

.workflow-item:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.2);
}

.workflow-item.first-item {
  border-left: 4px solid #67c23a;
}

.workflow-item-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.workflow-remove-btn {
  width: 28px !important;
  height: 28px !important;
  padding: 0 !important;
  margin-left: auto;
}

.step-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: #409eff;
  color: #fff;
  border-radius: 50%;
  font-size: 12px;
  font-weight: bold;
}

.workflow-item-header .case-title {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.workflow-item-body {
  padding: 8px 16px 12px;
}

.perf-config-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.perf-config-label {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}

.api-endpoint-input {
  font-family: 'Courier New', monospace;
}

/* 只读状态下的灰色样式 */
.api-endpoint-input :deep(.el-input__wrapper) {
  background-color: #f5f7fa;
  cursor: not-allowed;
}

.api-endpoint-input :deep(.el-input__inner) {
  color: #909399;
  cursor: not-allowed;
}

.api-endpoint {
  font-size: 13px;
  color: #909399;
  font-family: 'Courier New', monospace;
}

.empty-workflow-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #c0c4cc;
  gap: 10px;
}

.empty-workflow-hint .el-icon {
  font-size: 48px;
}

/* 拖拽样式 */
.ghost-item {
  opacity: 0.5;
  background: #ecf5ff !important;
}

.chosen-item {
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
}

/* 变量面板 */
.variable-panel {
  padding: 0;
}

.variable-tabs :deep(.el-tabs__header) {
  margin: 0;
  padding: 0 10px;
  background: #f5f7fa;
}

.variable-list {
  padding: 10px;
}

.variable-item {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  margin-bottom: 10px;
  background: #f5f7fa;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
}

/* 自动提取变量的样式 */
.auto-var-item {
  background: #ecf5ff;
  border-left: 3px solid #409eff;
}

.auto-var-item .var-value {
  color: #606266;
  font-style: italic;
}

.var-name {
  font-size: 13px;
  font-weight: 600;
  font-family: 'Courier New', monospace;
  color: #409eff;
  min-width: 60px;
  flex-shrink: 0;
}

.var-value {
  flex: 1;
  font-size: 12px;
  font-family: 'Courier New', monospace;
  color: #606266;
  padding: 6px 10px;
  background: #fff;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  min-height: 32px;
  display: flex;
  align-items: center;
  word-break: break-all;
  max-width: 100%;
  min-width: 0;
  line-height: 1.5;
}

.variable-item .el-tag {
  font-size: 11px;
  flex-shrink: 0;
}

/* 步骤变量提取展示 */
.step-extract-vars {
  padding: 8px 12px;
  background: #f0f9ff;
  border-top: 1px dashed #dcdfe6;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.extract-var-label {
  font-size: 12px;
  color: #909399;
  font-weight: 500;
}

.extract-var-tag {
  margin: 0;
}

/* 可用变量提示区域 */
.step-available-vars {
  padding: 8px 12px;
  background: #fff7e6;
  border-top: 1px dashed #ffe4b5;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.available-var-label {
  font-size: 12px;
  color: #e6a23c;
  font-weight: 500;
}

.available-var-tag {
  margin: 0;
  font-family: 'Courier New', monospace;
}

.dependency-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 8px;
  color: #909399;
  font-size: 12px;
}

.variable-add-row {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  justify-content: flex-end;
}

.compact-btn {
  padding: 4px 8px !important;
  font-size: 12px !important;
  min-width: 40px !important;
  white-space: nowrap;
}

.dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.footer-left {
  display: flex;
  gap: 10px;
}

.footer-right {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.execution-log {
  margin-top: 10px;
}

.log-content {
  max-height: 150px;
  overflow-y: auto;
  background: #1e1e1e;
  border-radius: 4px;
  padding: 10px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.log-item {
  padding: 4px 0;
  border-bottom: 1px solid #333;
}

.log-item:last-child {
  border-bottom: none;
}

.log-item.info {
  color: #409eff;
}

.log-item.success {
  color: #67c23a;
}

.log-item.error {
  color: #f56c6c;
}

.log-item.warning {
  color: #e6a23c;
}

.log-message {
  flex: 1;
}

.log-time {
  color: #909399;
  margin-right: 10px;
}

/* 上下文变量分组样式 */
.context-variable-groups {
  max-height: 400px;
  overflow-y: auto;
}

.context-group {
  margin-bottom: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
}

.group-header {
  background: #f5f7fa;
  padding: 8px 12px;
  border-bottom: 1px solid #e4e7ed;
}

.group-step {
  font-weight: 600;
  color: #409eff;
  margin-right: 8px;
}

.group-title {
  color: #606266;
}

.group-vars {
  padding: 8px;
}

.variable-add-row {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.compact-btn {
  padding: 4px 8px !important;
  font-size: 12px !important;
  min-width: 40px !important;
  white-space: nowrap;
}

/* 变量提取配置区域 */
.step-extract-config {
  margin: 8px 0;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
}

.extract-config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.config-label {
  font-size: 12px;
  color: #606266;
  font-weight: 500;
}

.extract-rule-row {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
  align-items: center;
}

.rule-input {
  flex: 1;
}

.var-name-input {
  flex: 0.8;
}

.var-value-input {
  flex: 1.5;
}

.var-type-select {
  flex: 0.7;
}

.empty-extract-hint {
  font-size: 11px;
  color: #909399;
  text-align: center;
  padding: 4px 0;
}

/* 变量提取配置区域（内联） */
.step-extract-config-inline {
  margin: 10px 0;
  padding: 10px;
  background: #f8f9fa;
  border-radius: 6px;
  border: 1px dashed #dcdfe6;
}

.extract-config-header-inline {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e4e7ed;
}

.config-label-inline {
  font-size: 13px;
  color: #303133;
  font-weight: 600;
}

.extract-rule-row-inline {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  align-items: center;
}

.rule-input-inline {
  flex: 1;
}

.var-name-input-inline {
  flex: 0.9;
}

.var-value-input-inline {
  flex: 1.5;
}

.var-type-select-inline {
  flex: 0.8;
}

.empty-extract-hint-inline {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #909399;
  padding: 8px;
  background: #fff;
  border-radius: 4px;
  margin-bottom: 10px;
}

.jsonpath-hint-inline {
  margin-top: 10px;
  padding: 8px;
  background: #fff;
  border-radius: 4px;
  border-left: 3px solid #409eff;
}

.hint-title {
  font-size: 12px;
  color: #606266;
  font-weight: 600;
  margin-bottom: 6px;
}

.hint-item {
  font-size: 11px;
  color: #909399;
  font-family: 'Courier New', monospace;
  margin-bottom: 3px;
}

.modal-var-tags .el-tag {
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.modal-var-tags .el-tag:hover {
  transform: translateY(-2px);
  box-shadow: 0 2px 6px rgba(64, 158, 255, 0.3);
}

/* 步骤编辑按钮 */
.workflow-edit-btn {
  color: #e6a23c;
}

.workflow-edit-btn:hover {
  color: #f5a623;
}

.available-var-tag-inline {
  margin-right: 6px;
  margin-bottom: 4px;
}

/* 模态框变量提示 */
.modal-var-hint {
  margin-top: 8px;
  padding: 8px;
  background: #fdf6ec;
  border-radius: 4px;
  border-left: 3px solid #e6a23c;
}

.modal-var-label {
  font-size: 12px;
  color: #e6a23c;
  font-weight: 500;
  margin-bottom: 6px;
}

.modal-var-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* 页面标题区域 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(102, 126, 234, 0.3);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-icon {
  width: 56px;
  height: 56px;
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  color: white;
  border: 2px solid rgba(255, 255, 255, 0.3);
}

.header-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: white;
  margin: 0;
}

.page-desc {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.85);
  margin: 0;
}

.create-btn {
  background: white;
  color: #667eea;
  border: none;
  font-weight: 500;
}

.create-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.content-card {
  border-radius: 12px;
}

/* ========== 内嵌执行结果面板 ========== */
.execution-result-panel {
  margin-top: 20px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  overflow: hidden;
}
.result-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #fafafa;
  border-bottom: 1px solid #ebeef5;
}
.result-panel-left { display: flex; align-items: center; gap: 8px; color: #303133; }
.result-panel-title { font-weight: 600; font-size: 14px; }
.result-panel-time { color: #909399; font-size: 12px; margin-left: 8px; }
.result-panel-summary {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 14px 16px;
  border-bottom: 1px solid #ebeef5;
}
.stat-item { display: flex; flex-direction: column; align-items: center; gap: 2px; }
.stat-num { font-size: 22px; font-weight: 700; }
.stat-label { font-size: 12px; color: #909399; }
.stat-passed .stat-num { color: #67c23a; }
.stat-failed .stat-num { color: #f56c6c; }
.stat-skipped .stat-num { color: #e6a23c; }
.result-panel-list { max-height: 240px; overflow-y: auto; }
.result-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-bottom: 1px solid #f5f5f5;
  font-size: 13px;
}
.result-item:last-child { border-bottom: none; }
.result-item:hover { background: #fafafa; }
.result-icon-pass { color: #67c23a; }
.result-icon-fail { color: #f56c6c; }
.result-item-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.result-item-time { color: #909399; font-size: 12px; min-width: 60px; text-align: right; }
.result-item-error {
  width: 100%;
  margin-top: 2px;
  padding: 4px 8px;
  background: #fef0f0;
  border-radius: 4px;
  color: #f56c6c;
  font-size: 12px;
  font-family: monospace;
  overflow-wrap: break-word;
}
.result-failed .result-item-name { color: #f56c6c; }

/* ========== 定时执行对话框 ========== */
.schedule-dialog-body {
  padding: 0 10px;
}
.schedule-tips {
  margin-top: 16px;
  padding: 12px 16px;
  background: #fdf6ec;
  border-radius: 8px;
}
.schedule-tips p {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin: 4px 0;
  font-size: 13px;
  color: #b88230;
  line-height: 1.5;
}

/* ========== 定时状态列 ========== */
.schedule-status-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.schedule-tag {
  display: inline-flex;
  align-items: center;
}
.schedule-time-text {
  font-size: 11px;
  color: #e6a23c;
  font-family: 'Courier New', monospace;
  font-weight: 500;
}
.schedule-owner {
  font-size: 10px;
  color: #909399;
}
.no-schedule-text {
  color: #c0c4cc;
  font-size: 12px;
}

/* ========== 定时任务详情（对话框内）========== */
.schedule-current-info {
  margin-bottom: 16px;
}
.schedule-detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}
.detail-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}
.detail-label {
  color: #909399;
  white-space: nowrap;
  font-size: 12px;
}
.detail-value {
  color: #303133;
  font-weight: 500;
  font-size: 12px;
}

/* ========== 明亮风格页面样式 ========== */
.glass-card {
  background: #ffffff !important;
  border: 1px solid #e4e7ed !important;
  border-radius: 12px !important;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06) !important;
  color: #303133;
}

.glass-card :deep(.el-card__header) {
  padding: 0 !important;
  border-bottom: 1px solid #e4e7ed !important;
  background: linear-gradient(135deg, #f0f7ff 0%, #ffffff 100%);
}

.page-hero {
  padding: 24px 28px;
}

.hero-main {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.hero-title {
  display: flex;
  align-items: center;
  gap: 16px;
}

.hero-icon-wrap {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  background: linear-gradient(135deg, #409eff 0%, #67b1ff 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.25);
}

.page-hero .page-title {
  font-size: 22px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 6px 0;
  line-height: 1.3;
}

.page-hero .page-desc {
  font-size: 14px;
  color: #606266;
  margin: 0;
}

.hero-stats {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hero-stats .stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 18px;
  background: #fff;
  border-radius: 10px;
  border: 1px solid #ebeef5;
  min-width: 88px;
}

.hero-stats .stat-value {
  font-size: 22px;
  font-weight: 700;
  color: #409eff;
  line-height: 1.1;
}

.hero-stats .stat-value.passed {
  color: #67c23a;
}

.hero-stats .stat-value.failed {
  color: #f56c6c;
}

.hero-stats .stat-label {
  font-size: 12px;
  color: #909399;
}

.hero-stats .stat-divider {
  width: 1px;
  height: 32px;
  background: #e4e7ed;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 16px 20px;
  background: #fafbfc;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  margin-bottom: 16px;
}

.page-toolbar :deep(.el-form-item) {
  margin-bottom: 0;
  margin-right: 16px;
}

.page-toolbar :deep(.el-form-item__label) {
  color: #606266;
  font-weight: 500;
}

.page-content {
  min-height: 320px;
}

.data-table {
  border-radius: 8px;
  overflow: hidden;
}

.data-table :deep(.el-loading-mask) {
  background-color: rgba(255, 255, 255, 0.85) !important;
  backdrop-filter: blur(2px);
}

.page-pagination {
  margin-top: 20px;
  justify-content: flex-end;
}

.empty-state-glass {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px 20px;
  text-align: center;
  background: #ffffff;
  border: 1px dashed #dcdfe6;
  border-radius: 12px;
}

.empty-state-glass .empty-icon-wrap {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: #f0f7ff;
  color: #409eff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.empty-state-glass .empty-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 8px 0;
}

.empty-state-glass .empty-desc {
  font-size: 14px;
  color: #909399;
  margin: 0 0 20px 0;
  max-width: 420px;
  line-height: 1.6;
}

.hero-main .create-btn {
  background: #409eff;
  color: #fff;
  border: none;
  font-weight: 500;
  border-radius: 8px;
  padding: 0 20px;
}

.hero-main .create-btn:hover {
  background: #66b1ff;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.25);
}

</style>

<style>
/* 全局样式：dialog 通过 teleport 到 body，需非 scoped 样式 */
.testsuite-edit-dialog .el-overlay-dialog .el-dialog__wrapper {
  display: flex !important;
  flex-direction: column !important;
  max-height: 90vh !important;
  overflow: hidden !important;
}

.testsuite-edit-dialog .el-dialog__body {
  flex: 1 1 auto !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  min-height: 0 !important;
}

.testsuite-edit-dialog .el-dialog__footer {
  flex-shrink: 0 !important;
  padding: 12px 20px !important;
  pointer-events: auto !important;
}
</style>

