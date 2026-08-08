<template>
  <div class="ai-evaluator">
    <!-- 顶部操作栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <h2>🤖 AI 测评师</h2>
        <el-tag type="info" size="small">给 AI 做体检、打分、找 bug</el-tag>
      </div>
      <div class="toolbar-right">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索任务名称..."
          :prefix-icon="Search"
          clearable
          style="width: 220px; margin-right: 12px"
        />
        <el-button type="primary" :icon="Plus" @click="openCreateDialog">
          新建测评任务
        </el-button>
        <el-button
          type="danger"
          :icon="Delete"
          :disabled="selectedTasks.length === 0"
          @click="batchDelete"
        >
          批量删除
        </el-button>
      </div>
    </div>

    <!-- 任务列表 -->
    <div class="task-list-section">
      <!-- 筛选栏 -->
      <div class="filter-bar">
        <el-radio-group v-model="statusFilter" size="small" @change="currentPage = 1">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="pending">待执行</el-radio-button>
          <el-radio-button value="running">执行中</el-radio-button>
          <el-radio-button value="completed">已完成</el-radio-button>
          <el-radio-button value="failed">失败</el-radio-button>
        </el-radio-group>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          size="small"
          value-format="YYYY-MM-DD"
          style="width: 240px"
          @change="currentPage = 1"
        />
      </div>

      <el-table
        :data="pagedTasks"
        v-loading="loading"
        @selection-change="handleSelectionChange"
        ref="tableRef"
        stripe
        style="width: 100%"
        :header-cell-style="{ background: '#f5f7fa', color: '#303133' }"
        :empty-text="''"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="name" label="任务名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="target_config.mode" label="问答模式" min-width="110">
          <template #default="{ row }">
            <el-tag :type="(row.target_config?.mode || 'chat') === 'knowledge' ? 'success' : ''" size="small">
              {{ (row.target_config?.mode || 'chat') === 'knowledge' ? '知识库问答' : '通用对话' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" min-width="85">
          <template #default="{ row }">
            <el-tag :type="statusTagType(runningTasks[row.id] ? 'running' : row.status)" size="small" effect="dark">
              {{ runningTasks[row.id] ? '执行中' : statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_questions" label="问题数" min-width="70" align="center" />
        <el-table-column label="正确/错误" min-width="95" align="center">
          <template #default="{ row }">
            <span class="stat-correct">{{ row.correct_count }}</span>
            <span style="color: #909399; margin: 0 2px">/</span>
            <span class="stat-wrong">{{ row.incorrect_count }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="accuracy" label="准确率" min-width="80" align="center">
          <template #default="{ row }">
            <el-tooltip
              v-if="row.status === 'completed'"
              :content="`正确回答数 ${row.correct_count || 0} / 总问题数 ${row.total_questions} × 100%`"
              placement="top"
            >
              <span :style="{ color: accuracyColor(row.accuracy), cursor: 'help' }">
                {{ row.accuracy }}%
              </span>
            </el-tooltip>
            <span v-else style="color: #909399">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="avg_response_time" label="平均响应" min-width="90" align="center">
          <template #default="{ row }">
            <el-tooltip content="所有问题的平均响应时间（秒）" placement="top">
              <span :style="{ color: row.avg_response_time > 5 ? '#f56c6c' : '#67c23a', cursor: 'help' }">
                {{ row.avg_response_time }}s
              </span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="overall_score" label="综合评分" min-width="100" align="center">
          <template #default="{ row }">
            <template v-if="row.status === 'completed'">
              <el-tooltip content="综合评分 = 准确率×40% + 速度分×20% + 安全分×20% + 质量分×20%" placement="top">
                <el-progress
                  :percentage="row.overall_score"
                  :color="scoreColor(row.overall_score)"
                  :stroke-width="6"
                  style="width: 90px; display: inline-block; cursor: help"
                />
              </el-tooltip>
            </template>
            <span v-else style="color: #909399">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="security_issues_found" label="安全风险" min-width="80" align="center">
          <template #default="{ row }">
            <template v-if="row.security_issues_found > 0">
              <el-tooltip :content="`发现 ${row.security_issues_found} 条涉及违规/敏感内容的风险`" placement="top">
                <el-tag type="danger" size="small" effect="dark" style="cursor: help">
                  {{ row.security_issues_found }}个
                </el-tag>
              </el-tooltip>
            </template>
            <template v-else>
              <el-tooltip content="未检测到安全风险" placement="top">
                <el-tag type="success" size="small" effect="plain" style="cursor: help">无</el-tag>
              </el-tooltip>
            </template>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="150">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="310" fixed="right">
          <template #default="{ row }">
            <!-- 待执行：[执行] [编辑] [题目] [删除] -->
            <template v-if="row.status === 'pending'">
              <el-button type="primary" size="small" @click="runEval(row)" :loading="runningTasks[row.id]">执行</el-button>
              <el-button size="small" @click="editTask(row)">编辑</el-button>
              <el-button size="small" @click="viewQuestions(row)">题目</el-button>
              <el-button size="small" type="danger" :icon="Delete" @click="deleteTask(row)"></el-button>
            </template>

            <!-- 执行中：[重试] [题目] [详情] [删除] -->
            <template v-else-if="row.status === 'running'">
              <el-button type="success" size="small" @click="retryTask(row)" :loading="retryingTasks[row.id]">重试</el-button>
              <el-button size="small" @click="viewQuestions(row)">题目</el-button>
              <el-button size="small" @click="viewResults(row)">详情</el-button>
              <el-button size="small" type="danger" :icon="Delete" @click="deleteTask(row)"></el-button>
            </template>

            <!-- 已完成：[重试] [报告] [详情] [删除] -->
            <template v-else-if="row.status === 'completed'">
              <el-button type="success" size="small" @click="retryTask(row)" :loading="retryingTasks[row.id]">重试</el-button>
              <el-button size="small" @click="viewReport(row)">报告</el-button>
              <el-button size="small" @click="viewResults(row)">详情</el-button>
              <el-button size="small" type="danger" :icon="Delete" @click="deleteTask(row)"></el-button>
            </template>

            <!-- 失败/取消：[重试] [执行] [编辑] [删除] -->
            <template v-else-if="row.status === 'failed' || row.status === 'cancelled'">
              <el-button type="success" size="small" @click="retryTask(row)" :loading="retryingTasks[row.id]">重试</el-button>
              <el-button type="primary" size="small" @click="runEval(row)" :loading="runningTasks[row.id]">执行</el-button>
              <el-button size="small" @click="editTask(row)">编辑</el-button>
              <el-button size="small" type="danger" :icon="Delete" @click="deleteTask(row)"></el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>

      <!-- 自定义空状态 -->
      <div v-if="!loading && filteredTasks.length === 0" class="custom-empty">
        <el-empty description="">
          <template #description>
            <div class="empty-desc">
              <p style="font-size: 16px; color: #606266; margin-bottom: 8px">还没有测评任务</p>
              <p style="font-size: 13px; color: #909399">点击右上角【新建测评任务】，创建你的第一个 AI 测评任务吧！</p>
            </div>
          </template>
          <el-button type="primary" :icon="Plus" @click="openCreateDialog">
            新建测评任务
          </el-button>
        </el-empty>
      </div>

      <!-- 分页 -->
      <div v-if="filteredTasks.length > 0" class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="filteredTasks.length"
          layout="total, prev, pager, next"
          background
        />
      </div>
    </div>

    <!-- ==================== 创建/编辑任务对话框 ==================== -->
    <el-dialog v-model="showCreateDialog" :title="editing ? '编辑 AI 测评任务' : '新建 AI 测评任务'" width="780px" destroy-on-close>
      <el-form :model="createForm" label-width="110px" ref="createFormRef" :rules="createRules">
        <!-- 基础信息 -->
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="任务名称" prop="task_name" required>
              <el-input v-model="createForm.task_name" placeholder="例如：大模型通用对话能力测评" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="问答模式" required>
              <el-radio-group v-model="createForm.target_config.mode">
                <el-radio value="knowledge">
                  <el-tooltip content="基于知识库文档检索 + AI 大模型生成回答，适合测评 RAG 效果" placement="top">
                    <span>知识库问答</span>
                  </el-tooltip>
                </el-radio>
                <el-radio value="chat">
                  <el-tooltip content="纯 AI 大模型对话能力，不依赖知识库，适合测评模型基础能力" placement="top">
                    <span>通用对话</span>
                  </el-tooltip>
                </el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="任务描述">
          <el-input v-model="createForm.task_description" type="textarea" :rows="2" placeholder="可选，描述本次测评的目的和范围" />
        </el-form-item>

        <!-- 知识库模式专属配置 -->
        <template v-if="createForm.target_config.mode === 'knowledge'">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="知识库ID" required>
                <el-input-number v-model="createForm.target_config.knowledge_base_id" :min="1" placeholder="1" style="width: 100%" />
                <el-link type="primary" :underline="false" style="font-size: 12px" @click="ElMessage.info('可在【数据看板 / 知识库管理】中查看你的知识库 ID')">
                  <el-icon><QuestionFilled /></el-icon> 如何获取？
                </el-link>
              </el-form-item>
            </el-col>
          </el-row>
        </template>

        <!-- 高级设置折叠 -->
        <el-collapse v-model="advancedActive" style="margin-bottom: 16px">
          <el-collapse-item title="高级设置" name="advanced">
            <el-row :gutter="16">
              <el-col :span="8">
                <el-form-item label="超时时间">
                  <el-input-number v-model="createForm.target_config.timeout" :min="5" :max="120" :step="5" style="width: 100%">
                    <template #suffix>秒</template>
                  </el-input-number>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="并发数">
                  <el-input-number v-model="createForm.target_config.concurrency" :min="1" :max="20" :step="1" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="重试次数">
                  <el-input-number v-model="createForm.target_config.retry_count" :min="0" :max="5" :step="1" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-collapse-item>
        </el-collapse>

        <el-divider content-position="left">
          <el-icon><Edit /></el-icon> 测评问题列表
        </el-divider>

        <!-- 批量导入 -->
        <div class="import-actions">
          <el-upload
            :auto-upload="false"
            :on-change="handleFileImport"
            accept=".xlsx,.csv"
            :show-file-list="false"
          >
            <el-button type="success" :icon="Upload">批量导入 Excel/CSV</el-button>
          </el-upload>
          <el-link type="primary" :underline="false" @click="downloadTemplate">
            <el-icon><Download /></el-icon> 下载导入模板
          </el-link>
          <el-button :icon="Plus" @click="addQuestionRow">手动添加</el-button>
          <el-button type="warning" :icon="MagicStick" :loading="generatingQuestions" @click="showGenDialog = true">
            AI 生成
          </el-button>
          <span class="import-hint">
            已添加 <b :class="{ 'text-danger': createForm.questions.length === 0 }">{{ createForm.questions.length }}</b> 个问题
          </span>
        </div>

        <!-- AI生成问题对话框 -->
        <el-dialog
          v-model="showGenDialog"
          title="AI 自动生成测评问题"
          width="520px"
          :append-to-body="true"
          destroy-on-close
        >
          <el-form :model="genForm" label-width="90px" ref="genFormRef">
            <el-form-item label="测评主题" required>
              <el-input
                v-model="genForm.topic"
                placeholder="例如：Redis缓存、用户登录流程、API安全性..."
              />
              <span style="font-size:12px;color:#909399">描述你想要测评的领域或主题</span>
            </el-form-item>
            <el-form-item label="生成数量" required>
              <el-input-number v-model="genForm.count" :min="1" :max="50" :step="5" style="width:100%" />
            </el-form-item>
            <el-form-item label="问题类型">
              <el-checkbox-group v-model="genForm.categories">
                <el-checkbox label="general">通用</el-checkbox>
                <el-checkbox label="knowledge">知识查询</el-checkbox>
                <el-checkbox label="procedure">流程指引</el-checkbox>
                <el-checkbox label="safety">安全边界</el-checkbox>
                <el-checkbox label="boundary">边界测试</el-checkbox>
              </el-checkbox-group>
              <span style="font-size:12px;color:#909399">不选则混合生成所有类型</span>
            </el-form-item>
          </el-form>

          <template #footer>
            <el-button @click="showGenDialog = false">取消</el-button>
            <el-button type="primary" :loading="generatingQuestions" @click="generateQuestionsByAI">
              {{ generatingQuestions ? 'AI 生成中...' : '开始生成' }}
            </el-button>
          </template>
        </el-dialog>

        <!-- 问题表格 -->
        <div class="question-table-wrapper" v-if="createForm.questions.length > 0">
          <el-table :data="createForm.questions" border size="small" max-height="300">
            <el-table-column label="序号" type="index" width="55" />
            <el-table-column label="问题" min-width="200">
              <template #default="{ row, $index }">
                <el-input v-model="row.question" size="small" placeholder="输入问题..." />
              </template>
            </el-table-column>
            <el-table-column label="期望答案/关键词" min-width="150">
              <template #default="{ row, $index }">
                <el-input v-model="row.expected_answer" size="small" placeholder="可选，留空则做通用评估" />
              </template>
            </el-table-column>
            <el-table-column label="分类" width="120">
              <template #default="{ row, $index }">
                <el-select v-model="row.category" size="small">
                  <el-option label="通用" value="general" />
                  <el-option label="知识查询" value="knowledge" />
                  <el-option label="流程指引" value="procedure" />
                  <el-option label="安全边界" value="safety" />
                  <el-option label="边界测试" value="boundary" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="60">
              <template #default="{ $index }">
                <el-button type="danger" size="small" :icon="Delete" circle @click="removeQuestionRow($index)" />
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 无问题时的提示 -->
        <el-alert
          v-if="createForm.questions.length === 0"
          title="请至少添加 1 个测评问题"
          type="warning"
          :closable="false"
          show-icon
          style="margin-top: 12px"
        />
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createTask" :loading="creating">
          {{ editing ? '保存修改' : '创建任务' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ==================== 测评结果对话框 ==================== -->
    <el-dialog v-model="showResultsDialog" :title="`测评详情 - ${currentTask?.name || ''}`" width="90%" destroy-on-close>
      <div class="results-toolbar">
        <el-radio-group v-model="resultFilter" size="small" @change="loadResults">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="correct">✅ 正确</el-radio-button>
          <el-radio-button value="incorrect">❌ 错误</el-radio-button>
          <el-radio-button value="partial">⚠️ 部分正确</el-radio-button>
          <el-radio-button value="error">🔴 异常</el-radio-button>
        </el-radio-group>
      </div>

      <el-table :data="resultsData" v-loading="resultsLoading" max-height="500" stripe border>
        <el-table-column type="index" width="55" label="序号" />
        <el-table-column prop="question_text" label="问题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="expected_answer" label="期望答案" min-width="120" show-overflow-tooltip />
        <el-table-column prop="actual_answer" label="实际回答" min-width="250" show-overflow-tooltip />
        <el-table-column label="判定" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="levelTagType(row.level)" size="small">
              {{ levelText(row.level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="score" label="得分" width="70" align="center">
          <template #default="{ row }">
            <span :style="{ color: scoreColor(row.score), fontWeight: 'bold' }">{{ row.score }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="response_time" label="响应时间" width="90" align="center">
          <template #default="{ row }">
            <span :style="{ color: row.response_time > 10 ? '#f56c6c' : '#67c23a' }">
              {{ row.response_time }}s
            </span>
          </template>
        </el-table-column>
        <el-table-column label="安全风险" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.has_security_risk" type="danger" size="small">
              {{ row.security_risk_type || '有风险' }}
            </el-tag>
            <span v-else style="color: #67c23a">安全</span>
          </template>
        </el-table-column>
        <el-table-column prop="ai_evaluation" label="AI评估" min-width="150" show-overflow-tooltip />
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="resultPage"
          :page-size="resultPageSize"
          :total="resultTotal"
          layout="total, prev, pager, next"
          background
          small
          @current-change="loadResults"
        />
      </div>
    </el-dialog>

    <!-- ==================== 测评报告对话框 ==================== -->
    <el-dialog v-model="showReportDialog" :title="`测评报告 - ${currentTask?.name || ''}`" width="850px" destroy-on-close>
      <div v-if="reportData" class="report-container">
        <!-- 总览卡片 -->
        <div class="report-summary-cards">
          <div class="report-card">
            <div class="card-value" :style="{ color: accuracyColor(reportData.accuracy_score) }">
              {{ reportData.accuracy_score }}%
            </div>
            <div class="card-label">准确率</div>
          </div>
          <div class="report-card">
            <div class="card-value" :style="{ color: scoreColor(currentTask?.overall_score) }">
              {{ currentTask?.overall_score }}
            </div>
            <div class="card-label">综合评分</div>
          </div>
          <div class="report-card">
            <div class="card-value" :style="{ color: reportData.speed_score > 60 ? '#67c23a' : '#f56c6c' }">
              {{ reportData.speed_score }}
            </div>
            <div class="card-label">响应速度分</div>
          </div>
          <div class="report-card">
            <div class="card-value" :style="{ color: reportData.safety_score > 80 ? '#67c23a' : '#f56c6c' }">
              {{ reportData.safety_score }}
            </div>
            <div class="card-label">安全性分</div>
          </div>
          <div class="report-card">
            <div class="card-value">{{ reportData.quality_score }}</div>
            <div class="card-label">回答质量分</div>
          </div>
        </div>

        <!-- 摘要 -->
        <el-alert :title="reportData.summary" type="info" :closable="false" show-icon style="margin-bottom: 20px" />

        <!-- 问题分布 -->
        <el-row :gutter="16">
          <el-col :span="12">
            <div class="chart-card">
              <h4>📊 分数分布</h4>
              <div v-for="(count, range) in reportData.score_distribution" :key="range" class="dist-bar">
                <span class="dist-label">{{ range }}</span>
                <el-progress
                  :percentage="count / (currentTask?.total_questions || 1) * 100"
                  :color="range === '90-100' ? '#67c23a' : range === '0-59' ? '#f56c6c' : '#e6a23c'"
                  :stroke-width="12"
                  :show-text="false"
                  style="flex: 1; margin: 0 12px"
                />
                <span class="dist-count">{{ count }}题</span>
              </div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="chart-card">
              <h4>🏷️ 分类统计</h4>
              <div v-for="(stats, cat) in reportData.category_stats" :key="cat" class="dist-bar">
                <span class="dist-label">{{ cat }}</span>
                <span style="margin-left: auto; font-size: 13px">
                  ✅{{ stats.correct }} ❌{{ stats.incorrect }} ⚠️{{ stats.partial }}
                  ({{ ((stats.correct + stats.partial) / (stats.total || 1) * 100).toFixed(0) }}%)
                </span>
              </div>
            </div>
          </el-col>
        </el-row>

        <!-- 响应时间统计 -->
        <div class="chart-card" style="margin-top: 16px">
          <h4>⏱️ 响应时间</h4>
          <p>平均响应时间: <b>{{ reportData.response_time_stats?.avg || 0 }}s</b>
            | 慢响应(>10s): <b style="color: #f56c6c">{{ reportData.response_time_stats?.slow_count || 0 }}条</b>
          </p>
        </div>

        <!-- 问题清单 -->
        <div v-if="reportData.wrong_questions?.length" class="chart-card" style="margin-top: 16px">
          <h4>❌ 答错的问题 ({{ reportData.wrong_questions.length }}条)</h4>
          <div v-for="(q, i) in reportData.wrong_questions" :key="i" class="issue-item">
            <div><b>#{{ q.index }}</b> {{ q.question }}</div>
            <div style="color: #909399; font-size: 12px">期望: {{ q.expected || '无' }}</div>
            <div style="color: #f56c6c; font-size: 12px">{{ q.evaluation }}</div>
          </div>
        </div>

        <div v-if="reportData.risk_questions?.length" class="chart-card" style="margin-top: 16px">
          <h4>🛡️ 安全风险 ({{ reportData.risk_questions.length }}条)</h4>
          <div v-for="(q, i) in reportData.risk_questions" :key="i" class="issue-item" style="border-left-color: #f56c6c">
            <div><b>#{{ q.index }}</b> {{ q.question }}</div>
            <div style="color: #f56c6c; font-size: 12px">风险类型: {{ q.risk_types?.join(', ') }}</div>
            <div style="color: #909399; font-size: 12px">{{ q.detail }}</div>
          </div>
        </div>

        <div v-if="reportData.slow_questions?.length" class="chart-card" style="margin-top: 16px">
          <h4>🐢 响应慢的问题 ({{ reportData.slow_questions.length }}条)</h4>
          <div v-for="(q, i) in reportData.slow_questions" :key="i" class="issue-item" style="border-left-color: #e6a23c">
            <div><b>#{{ q.index }}</b> {{ q.question }}</div>
            <div style="color: #e6a23c; font-size: 12px">响应时间: {{ q.response_time }}s</div>
          </div>
        </div>

        <!-- 改进建议 -->
        <div v-if="reportData.suggestions?.length" class="chart-card" style="margin-top: 16px">
          <h4>💡 改进建议</h4>
          <el-alert
            v-for="(s, i) in reportData.suggestions"
            :key="i"
            :title="s.content"
            :type="s.level === 'critical' ? 'error' : 'warning'"
            :closable="false"
            show-icon
            style="margin-bottom: 8px"
          />
        </div>
      </div>
    </el-dialog>

    <!-- 题目查看对话框 -->
    <el-dialog v-model="showQuestionsDialog" :title="`题目列表 - ${questionTaskName}`" width="750px" destroy-on-close>
      <div style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px">
        <el-select v-model="questionCategoryFilter" placeholder="筛选分类" clearable size="small" style="width: 140px" @change="() => {}">
          <el-option v-for="(label, key) in { general: '通用', knowledge: '知识查询', procedure: '流程指引', safety: '安全边界', boundary: '边界异常' }" :key="key" :label="label" :value="key" />
        </el-select>
        <span style="font-size: 12px; color: #909399">共 {{ questionList.length }} 题</span>
      </div>
      <el-table :data="questionList.filter(q => !questionCategoryFilter || q.category === questionCategoryFilter)" v-loading="questionsLoading" max-height="400" stripe size="small">
        <el-table-column prop="index" label="#" width="55" align="center" />
        <el-table-column prop="content" label="问题内容" min-width="300" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="100" align="center">
          <template #default="{ row: q }">
            <el-tag :type="categoryTagType(q.category)" size="small">{{ categoryLabel(q.category) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="expected_answer" label="期望答案" min-width="200" show-overflow-tooltip />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onActivated, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, Delete, Search, VideoPlay, DataAnalysis, List,
  Download, Edit, Upload, QuestionFilled, ArrowDown, More, MagicStick,
  Loading, RefreshRight, Warning
} from '@element-plus/icons-vue'
import { evaluatorAPI } from '@/api/index'

// ========== 状态 ==========
const loading = ref(false)
const tasks = ref([])
const selectedTasks = ref([])
const searchKeyword = ref('')
const currentPage = ref(1)
const pageSize = ref(8)

// 创建/编辑任务
const showCreateDialog = ref(false)
const creating = ref(false)
const editing = ref(false)
const editTaskId = ref(null)
const createFormRef = ref(null)
const advancedActive = ref([])
const createForm = ref({
  task_name: '',
  task_description: '',
  target_config: {
    knowledge_base_id: 1,
    mode: 'chat',
    timeout: 30,
    concurrency: 3,
    retry_count: 1,
  },
  questions: [],
})

// AI生成问题
const showGenDialog = ref(false)
const generatingQuestions = ref(false)
const genFormRef = ref(null)
const genForm = ref({
  topic: '',
  count: 10,
  categories: [],
})

// 表单校验规则
const createRules = {
  task_name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
}

// 结果查看
const showResultsDialog = ref(false)
const resultsData = ref([])
const resultsLoading = ref(false)
const resultFilter = ref('')
const resultPage = ref(1)
const resultPageSize = ref(10)
const resultTotal = ref(0)

// 报告
const showReportDialog = ref(false)
const currentTask = ref(null)
const reportData = ref(null)

// 筛选状态
const statusFilter = ref('')
const dateRange = ref(null)

// 正在执行中的任务ID集合
// 正在执行的ID追踪（用对象代替Set，确保 Vue 3 响应式追踪）
const runningTasks = ref({})
const retryingTasks = ref({})

// 题目查看
const showQuestionsDialog = ref(false)
const questionList = ref([])
const questionsLoading = ref(false)
const questionTaskName = ref('')
const questionCategoryFilter = ref('')

// ========== 计算属性 ==========
const filteredTasks = computed(() => {
  let result = tasks.value

  // 关键词搜索
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    result = result.filter(t => t.name.toLowerCase().includes(kw))
  }

  // 状态筛选
  if (statusFilter.value) {
    result = result.filter(t => t.status === statusFilter.value)
  }

  // 日期范围筛选
  if (dateRange.value && dateRange.value.length === 2) {
    const [start, end] = dateRange.value
    result = result.filter(t => {
      const d = t.created_at ? new Date(t.created_at).toISOString().slice(0, 10) : null
      return d && d >= start && d <= end
    })
  }

  return result
})

const pagedTasks = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredTasks.value.slice(start, start + pageSize.value)
})

watch(searchKeyword, () => { currentPage.value = 1 })
watch(() => tasks.value.length, () => { currentPage.value = 1 })

// ========== 方法 ==========
const loadTasks = async () => {
  loading.value = true
  try {
    const res = await evaluatorAPI.list()
    tasks.value = Array.isArray(res) ? res : (res.results || [])
    // 同步清理已完成/失败任务的 loading 状态，避免按钮卡在转圈
    tasks.value.forEach(t => {
      if (t.status === 'completed' || t.status === 'failed') {
        delete runningTasks.value[t.id]
        delete retryingTasks.value[t.id]
      }
    })
  } catch (e) {
    console.error('加载任务列表失败', e)
  } finally {
    loading.value = false
  }
}

const handleSelectionChange = (val) => {
  selectedTasks.value = val
}

const createTask = async () => {
  // 表单校验
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return

  if (!createForm.value.task_name.trim()) {
    ElMessage.warning('请输入任务名称')
    return
  }
  if (!createForm.value.questions.length) {
    ElMessage.warning('请添加至少 1 个测评问题')
    return
  }
  // 检查空问题
  const emptyQuestions = createForm.value.questions.filter((q, i) => !q.question.trim())
  if (emptyQuestions.length > 0) {
    ElMessage.warning(`第 ${createForm.value.questions.findIndex(q => !q.question.trim()) + 1} 行问题为空，请检查`)
    return
  }

  creating.value = true
  try {
    const payload = {
      task_name: createForm.value.task_name,
      task_description: createForm.value.task_description,
      target_type: 'knowledge_bot',
      target_config: { ...createForm.value.target_config },
      questions: createForm.value.questions.map(q => ({
        question: q.question,
        expected_answer: q.expected_answer || '',
        category: q.category || 'general',
      })),
    }

    if (editing.value && editTaskId.value) {
      await evaluatorAPI.updateTask(editTaskId.value, payload)
      ElMessage.success('测评任务更新成功！')
    } else {
      await evaluatorAPI.createTask(payload)
      ElMessage.success('测评任务创建成功！')
    }
    showCreateDialog.value = false
    resetCreateForm()
    loadTasks()
  } catch (e) {
    console.error(editing.value ? '更新任务失败' : '创建任务失败', e)
    const detail = e?.response?.data?.detail || e?.message || ''
    if (detail.includes('knowledge_base')) {
      ElMessage.error('保存失败：知识库 ID 不存在，请检查后重试')
    } else {
      ElMessage.error(`保存失败：${detail || '请检查网络或联系管理员'}`)
    }
  } finally {
    creating.value = false
  }
}

const openCreateDialog = () => {
  resetCreateForm()
  showCreateDialog.value = true
}

const editTask = (task) => {
  editing.value = true
  editTaskId.value = task.id

  const config = task.target_config || {}

  createForm.value = {
    task_name: task.name || '',
    task_description: task.description || '',
    target_config: {
      knowledge_base_id: config.knowledge_base_id || 1,
      mode: config.mode || 'chat',
      timeout: config.timeout || 30,
      concurrency: config.concurrency || 3,
      retry_count: config.retry_count || 1,
    },
    questions: (task.questions || []).map(q => ({
      question: q.question || '',
      expected_answer: q.expected_answer || '',
      category: q.category || 'general',
    })),
  }
  showCreateDialog.value = true
}

const resetCreateForm = () => {
  createForm.value = {
    task_name: '',
    task_description: '',
    target_config: {
      knowledge_base_id: 1,
      mode: 'chat',
      timeout: 30,
      concurrency: 3,
      retry_count: 1,
    },
    questions: [],
  }
  editing.value = false
  editTaskId.value = null
  advancedActive.value = []
  createFormRef.value?.resetFields?.()
}

// 下载导入模板
const downloadTemplate = () => {
  const headers = ['问题', '期望答案', '分类']
  const example = ['公司的年假制度是什么？', '年假 10 天', '知识查询']
  const csvContent = '\uFEFF' + [headers.join(','), example.join(',')].join('\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8-sig' })
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'ai_evaluator_import_template.csv'
  a.click()
  window.URL.revokeObjectURL(url)
  ElMessage.success('模板下载成功，请按模板格式填写后导入')
}

const addQuestionRow = () => {
  createForm.value.questions.push({
    question: '',
    expected_answer: '',
    category: 'general',
  })
}

const generateQuestionsByAI = async () => {
  if (!genForm.value.topic.trim()) {
    ElMessage.warning('请输入测评主题')
    return
  }

  const totalCount = genForm.value.count
  generatingQuestions.value = true
  const startTime = Date.now()

  // 根据数量显示不同提示
  if (totalCount > 5) {
    ElMessage.info(`正在并发生成 ${totalCount} 个问题，请稍候...`)
  }

  try {
    const res = await evaluatorAPI.generateQuestions({
      topic: genForm.value.topic.trim(),
      count: totalCount,
      categories: genForm.value.categories,
    })

    if (res.questions && res.questions.length > 0) {
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1)
      // 将AI生成的问题追加到列表
      createForm.value.questions.push(...res.questions)
      ElMessage.success(
        `AI 成功生成 ${res.questions.length} 个问题！耗时 ${elapsed} 秒` +
        (totalCount > 5 ? '（并发加速）' : '')
      )
      showGenDialog.value = false
      // 重置生成表单
      genForm.value = { topic: '', count: 10, categories: [] }
    } else {
      ElMessage.warning('AI 未生成有效问题，请调整主题后重试')
    }
  } catch (e) {
    console.error('AI生成问题失败', e)
    const detail = e?.response?.data?.error || e?.message || ''
    ElMessage.error(`AI生成失败：${detail || '请检查网络或稍后重试'}`)
  } finally {
    generatingQuestions.value = false
  }
}

const removeQuestionRow = (index) => {
  createForm.value.questions.splice(index, 1)
}

const handleFileImport = async (file) => {
  try {
    const XLSX = await import('xlsx')
    const reader = new FileReader()
    reader.onload = (e) => {
      const data = new Uint8Array(e.target.result)
      const workbook = XLSX.read(data, { type: 'array' })
      const sheet = workbook.Sheets[workbook.SheetNames[0]]
      const jsonData = XLSX.utils.sheet_to_json(sheet)

      if (!jsonData.length) {
        ElMessage.warning('导入失败：文件中没有数据，请检查文件内容')
        return
      }

      const questions = []
      const errors = []
      jsonData.forEach((row, idx) => {
        const q = row['问题'] || row['question'] || ''
        if (!q || !q.toString().trim()) {
          errors.push(`第 ${idx + 2} 行问题为空`)
          return
        }
        questions.push({
          question: q.toString().trim(),
          expected_answer: (row['期望答案'] || row['expected_answer'] || row['expectedAnswer'] || '').toString().trim(),
          category: row['分类'] || row['category'] || 'general',
        })
      })

      if (errors.length > 0) {
        ElMessage.warning(`导入完成，但 ${errors.length} 行数据有问题：${errors.slice(0, 3).join('；')}${errors.length > 3 ? '...' : ''}。请检查文件格式（可下载模板参考）`)
      }

      if (!questions.length) {
        ElMessage.error('未找到有效问题列，请确保文件包含"问题"列，可下载模板参考')
        return
      }

      createForm.value.questions = questions
      ElMessage.success(`成功导入 ${questions.length} 个问题`)
    }
    reader.readAsArrayBuffer(file.raw)
  } catch (e) {
    console.error('导入失败', e)
    ElMessage.error('导入失败：文件格式不正确，请使用 .xlsx 或 .csv 格式，可下载模板参考')
  }
}

const runEval = async (task) => {
  try {
    await ElMessageBox.confirm(
      `即将对"${task.name}"执行AI测评，共${task.total_questions}个问题。确认执行？`,
      '确认执行',
      { confirmButtonText: '开始测评', cancelButtonText: '取消', type: 'info' }
    )
  } catch {
    return
  }

  runningTasks.value[task.id] = true
  // 立即乐观更新本地状态，不等轮询
  const localTask = tasks.value.find(t => t.id === task.id)
  if (localTask) localTask.status = 'running'
  try {
    await evaluatorAPI.runEval({ task_id: task.id })
    ElMessage.success('测评已开始，正在后台执行...')
    pollTaskStatus(task.id)
  } catch (e) {
    delete runningTasks.value[task.id]
    // 回滚状态
    if (localTask) localTask.status = task.status
    ElMessage.error('执行失败')
  }
}

// 重试任务（重置后重新执行）
const retryTask = async (task) => {
  try {
    await ElMessageBox.confirm(
      `将重新执行"${task.name}"的AI测评，之前的结果会被覆盖。确认重试？`,
      '确认重试',
      { confirmButtonText: '开始重试', cancelButtonText: '取消', type: 'info' }
    )
  } catch { return }

  retryingTasks.value[task.id] = true
  // 立即乐观更新本地状态为"执行中"，清空旧统计数据
  const localTask = tasks.value.find(t => t.id === task.id)
  if (localTask) {
    localTask.status = 'running'
    localTask.correct_count = 0
    localTask.incorrect_count = 0
    localTask.partial_count = 0
    localTask.error_count = 0
    localTask.accuracy = 0
    localTask.avg_response_time = 0
    localTask.overall_score = 0
    localTask.security_issues_found = 0
  }
  try {
    // 尝试重置状态（允许失败：如果任务已在执行中则跳过重置）
    try {
      await evaluatorAPI.resetStuck(task.id)
    } catch (resetErr) {
      const msg = resetErr?.response?.data?.error || ''
      if (msg.includes('正常执行') || msg.includes('无需重置')) {
        // 任务还在跑，不需要重置，继续尝试执行
        console.log('reset_stuck 跳过:', msg)
      } else {
        throw resetErr  // 其他错误继续抛出
      }
    }

    await evaluatorAPI.runEval({ task_id: task.id })
    ElMessage.success('任务已重新开始测评')
    pollTaskStatus(task.id, () => {
      delete retryingTasks.value[task.id]
    })
  } catch (e) {
    delete retryingTasks.value[task.id]
    // 回滚状态
    if (localTask) localTask.status = task.status
    const detail = e?.response?.data?.error || e.message || ''
    if (detail.includes('正在执行中')) {
      ElMessage.warning('任务正在执行中，请等待完成')
    } else {
      ElMessage.error('重试失败: ' + detail)
    }
  }
}

const pollTaskStatus = (taskId, onComplete) => {
  const interval = setInterval(async () => {
    try {
      const res = await evaluatorAPI.list()
      const tasks_ = Array.isArray(res) ? res : (res.results || [])
      const t = tasks_.find(t => t.id === taskId)
      if (t && (t.status === 'completed' || t.status === 'failed')) {
        clearInterval(interval)
        delete runningTasks.value[taskId]
        if (onComplete) onComplete()
        loadTasks()
        if (t.status === 'completed') {
          ElMessage.success(`测评完成！综合评分: ${t.overall_score}分`)
        } else {
          ElMessage.error('测评执行失败')
        }
      }
    } catch {
      clearInterval(interval)
      delete runningTasks.value[taskId]
      if (onComplete) onComplete()
    }
  }, 3000)
}

const viewQuestions = async (task) => {
  questionTaskName.value = task.name
  showQuestionsDialog.value = true
  questionCategoryFilter.value = ''
  questionsLoading.value = true
  questionList.value = []
  try {
    const res = await evaluatorAPI.getQuestions(task.id)
    questionList.value = Array.isArray(res) ? res : (res.results || [])
  } catch (e) {
    console.error('加载题目失败', e)
    ElMessage.error('加载题目失败')
  } finally {
    questionsLoading.value = false
  }
}

const viewResults = async (task) => {
  currentTask.value = task
  showResultsDialog.value = true
  resultFilter.value = ''
  resultPage.value = 1
  await loadResults()
}

const loadResults = async () => {
  if (!currentTask.value) return
  resultsLoading.value = true
  try {
    const params = { ordering: 'question__index' }
    if (resultFilter.value) params.level = resultFilter.value

    const res = await evaluatorAPI.getResults(currentTask.value.id, params)
    resultsData.value = Array.isArray(res) ? res : (res.results || [])
    resultTotal.value = resultsData.value.length
  } catch (e) {
    console.error('加载结果失败', e)
  } finally {
    resultsLoading.value = false
  }
}

const viewReport = async (task) => {
  currentTask.value = task
  showReportDialog.value = true
  try {
    const res = await evaluatorAPI.getReport(task.id)
    reportData.value = res
  } catch (e) {
    ElMessage.error('获取报告失败')
  }
}

const exportCSV = async (task) => {
  try {
    const res = await evaluatorAPI.exportCSV(task.id)
    const blob = new Blob([res], { type: 'text/csv;charset=utf-8-sig' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `eval_report_${task.id}.csv`
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    ElMessage.error('导出失败')
  }
}

const deleteTask = async (task) => {
  try {
    await ElMessageBox.confirm(`确认删除任务"${task.name}"？`, '确认删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await evaluatorAPI.deleteTask(task.id)
    ElMessage.success('已删除')
    loadTasks()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const handleCommand = (cmd, task) => {
  if (cmd === 'detail') viewResults(task)
  else if (cmd === 'export') exportCSV(task)
  else if (cmd === 'delete') deleteTask(task)
}

const batchDelete = async () => {
  try {
    await ElMessageBox.confirm(`确认删除选中的 ${selectedTasks.value.length} 个任务？`, '批量删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    const ids = selectedTasks.value.map(t => t.id)
    await evaluatorAPI.batchDelete(ids)
    ElMessage.success('批量删除成功')
    loadTasks()
  } catch (e) {
    ElMessage.error('批量删除失败')
  }
}

// ========== 工具函数 ==========
const statusTagType = (s) => {
  return { pending: 'info', running: 'warning', completed: 'success', failed: 'danger' }[s] || 'info'
}
const statusText = (s) => {
  return { pending: '待执行', running: '执行中', completed: '已完成', failed: '失败' }[s] || s
}
const categoryLabel = (c) => {
  return { general: '通用', knowledge: '知识查询', procedure: '流程指引', safety: '安全边界', boundary: '边界异常' }[c] || c
}
const categoryTagType = (c) => {
  return { general: '', knowledge: 'success', procedure: 'warning', safety: 'danger', boundary: 'info' }[c] || ''
}
const accuracyColor = (v) => {
  if (v >= 90) return '#67c23a'
  if (v >= 70) return '#e6a23c'
  return '#f56c6c'
}
const scoreColor = (v) => {
  if (v >= 80) return '#67c23a'
  if (v >= 60) return '#e6a23c'
  return '#f56c6c'
}
const levelTagType = (l) => {
  return { correct: 'success', incorrect: 'danger', partial: 'warning', error: 'danger' }[l] || 'info'
}
const levelText = (l) => {
  return { correct: '✅ 正确', incorrect: '❌ 错误', partial: '⚠️ 部分', error: '🔴 异常' }[l] || l
}
const formatTime = (t) => {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
}

onMounted(() => {
  loadTasks()
})

// 切换回此页面时，恢复运行中的任务状态
onActivated(() => {
  if (Object.keys(runningTasks.value).length === 0 && tasks.value.length > 0) {
    tasks.value.forEach(t => {
      if (t.status === 'running') {
        runningTasks.value[t.id] = true
        pollTaskStatus(t.id)
      }
    })
  }
})
</script>

<style scoped>
.ai-evaluator {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
  box-sizing: border-box;
}

.task-list-section {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.toolbar-left h2 {
  margin: 0;
  font-size: 20px;
}
.toolbar-right {
  display: flex;
  align-items: center;
}



.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.custom-empty {
  padding: 40px 0;
}

.empty-desc {
  text-align: center;
}

.text-danger {
  color: #f56c6c;
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  padding: 24px 0 8px;
  flex-shrink: 0;
}

/* 响应式适配 */
@media (max-width: 768px) {
  .toolbar {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  .toolbar-right {
    flex-wrap: wrap;
    gap: 8px;
  }
  .filter-bar {
    flex-direction: column;
    align-items: flex-start;
  }
}

.stat-correct { color: #67c23a; font-weight: bold; }
.stat-wrong { color: #f56c6c; font-weight: bold; }

.import-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.import-hint {
  font-size: 13px;
  color: #909399;
}
.question-table-wrapper {
  max-height: 350px;
  overflow-y: auto;
}

.results-toolbar {
  margin-bottom: 16px;
}

/* 报告样式 */
.report-container {
  max-height: 65vh;
  overflow-y: auto;
}
.report-summary-cards {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}
.report-card {
  flex: 1;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}
.report-card .card-value {
  font-size: 28px;
  font-weight: bold;
}
.report-card .card-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.chart-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
}
.chart-card h4 {
  margin: 0 0 12px 0;
  font-size: 15px;
}
.dist-bar {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
}
.dist-label {
  width: 60px;
  color: #606266;
}
.dist-count {
  width: 40px;
  text-align: right;
  color: #909399;
}

.issue-item {
  background: #fafafa;
  border-left: 3px solid #f56c6c;
  padding: 8px 12px;
  margin-bottom: 8px;
  border-radius: 4px;
  font-size: 13px;
}
.issue-item > div {
  margin-bottom: 4px;
}
</style>
