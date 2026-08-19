<template>
  <div class="eval-center">
    <!-- 渐变英雄区 -->
    <div class="hero">
      <div class="hero-left">
        <div class="title-icon">
          <el-icon :size="26"><Monitor /></el-icon>
        </div>
        <div>
          <h1>全链路评测中心</h1>
          <p class="subtitle">Golden Dataset + Judge LLM + 多维度评分 · 实时幻觉率与质量监控</p>
        </div>
      </div>
      <div class="hero-right">
        <div class="health-ring">
          <el-progress
            type="dashboard"
            :percentage="Math.round(dashboard.avg_scores.overall)"
            :width="92"
            :stroke-width="9"
            :color="ringColor"
          >
            <template #default="{ percentage }">
              <span class="ring-value">{{ percentage }}</span>
              <span class="ring-label">综合健康度</span>
            </template>
          </el-progress>
        </div>
        <div class="hero-actions">
          <el-select v-model="hours" size="default" style="width: 130px" @change="loadDashboard">
            <el-option label="近 24 小时" :value="24" />
            <el-option label="近 7 天" :value="168" />
            <el-option label="近 30 天" :value="720" />
            <el-option label="近 90 天" :value="2160" />
          </el-select>
          <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadDashboard">刷新</el-button>
          <el-button type="success" :icon="VideoPlay" :loading="demoLoading" @click="openLatestReplay">查看最新结果</el-button>
          <el-tooltip content="开启后按设定周期自动刷新面板数据，持续追踪最新链路">
            <span class="track-wrap">
              <el-switch v-model="autoRefresh" class="track-switch" active-text="自动追踪" inline-prompt inactive-text="自动追踪" style="margin-left: 8px;" @change="toggleAutoRefresh" />
              <span v-if="isTracking" class="track-dot" :title="'自动追踪中，每 ' + (refreshInterval < 60 ? refreshInterval + ' 秒' : Math.round(refreshInterval / 60) + ' 分钟')"></span>
            </span>
          </el-tooltip>
          <el-select v-if="autoRefresh" v-model="refreshInterval" size="default" style="width: 120px; margin-left: 8px;" @change="restartAutoRefresh">
            <el-option label="10 秒" :value="10" />
            <el-option label="30 秒" :value="30" />
            <el-option label="1 分钟" :value="60" />
            <el-option label="5 分钟" :value="300" />
          </el-select>
          <el-button v-if="langfuse?.enabled" type="info" :icon="Link" @click="openLangfuse">打开 Langfuse</el-button>
          <el-dropdown @command="onExport" :disabled="!records.length">
            <el-button :icon="Download">导出</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="txt">文本报告</el-dropdown-item>
                <el-dropdown-item command="csv">CSV 明细</el-dropdown-item>
                <el-dropdown-item command="json">JSON 原始</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </div>

    <!-- 顶部指标卡 -->
    <el-row :gutter="16" class="metric-row">
      <el-col :xs="24" :sm="12" :md="6">
        <div class="metric-card">
          <div class="metric-icon blue">
            <el-icon :size="24"><Collection /></el-icon>
          </div>
          <div class="metric-body">
            <div class="metric-value">{{ dashboard.total_records }}</div>
            <div class="metric-label">近 {{ hours }}h 评测样本</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <div class="metric-card">
          <div class="metric-icon purple">
            <el-icon :size="24"><Medal /></el-icon>
          </div>
          <div class="metric-body">
            <div class="metric-value" :class="scoreClass(dashboard.avg_scores.overall)">
              {{ dashboard.avg_scores.overall }}
            </div>
            <div class="metric-label">平均综合分</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <div class="metric-card">
          <div class="metric-icon orange">
            <el-icon :size="24"><View /></el-icon>
          </div>
          <div class="metric-body">
            <div class="metric-value" :class="scoreClass(dashboard.avg_scores.hallucination)">
              {{ dashboard.avg_scores.hallucination }}
            </div>
            <div class="metric-label">平均幻觉率得分</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <div class="metric-card">
          <div class="metric-icon teal">
            <el-icon :size="24"><Grid /></el-icon>
          </div>
          <div class="metric-body">
            <div class="metric-value">{{ Object.keys(dashboard.by_feature).length }}</div>
            <div class="metric-label">覆盖业务模块</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 维度评分条 -->
    <el-card shadow="never" class="dim-card">
      <template #header>
        <div class="card-header">
          <span>多维度质量评分</span>
          <el-tag size="small" :type="scoreTag(dashboard.avg_scores.overall)">
            综合 {{ dashboard.avg_scores.overall }}
          </el-tag>
        </div>
      </template>
      <div class="dim-grid">
        <div v-for="d in dimList" :key="d.key" class="dim-item">
          <div class="dim-top">
            <span class="dim-name">{{ d.label }}</span>
            <span class="dim-score" :class="scoreClass(scoreOf(d.key))">{{ scoreOf(d.key) }}</span>
          </div>
          <el-progress
            :percentage="scoreOf(d.key)"
            :stroke-width="10"
            :show-text="false"
            :color="barColor(scoreOf(d.key))"
          />
        </div>
      </div>
    </el-card>

    <!-- 图表区 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="chart-card radar-card">
          <template #header>
            <div class="card-header">
              <span>多维度评分雷达图</span>
              <el-tag size="small" type="info">平均分</el-tag>
            </div>
          </template>
          <div ref="radarRef" class="chart-box" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="16">
        <el-card shadow="never" class="chart-card trend-card">
          <template #header>
            <div class="card-header">
              <span>综合分趋势（近 {{ hours }}h · {{ granularityText }}）</span>
              <div class="trend-header-actions">
                <el-radio-group v-model="granularity" size="small" @change="loadDashboard">
                  <el-radio-button label="按小时" value="hour" />
                  <el-radio-button label="按周" value="week" />
                  <el-radio-button label="按月" value="month" />
                </el-radio-group>
                <el-tag size="small" type="info">{{ dashboard.trend.length }} 个时间点</el-tag>
              </div>
            </div>
          </template>
          <div ref="trendRef" class="chart-box">
            <div v-if="isTrendEmpty" class="chart-empty">暂无评测数据</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="chart-row bottom-row">
      <el-col :xs="24" :lg="12" class="bottom-left">
        <el-card shadow="never" class="chart-card feature-card">
          <template #header>
            <div class="card-header">
              <span>模块覆盖 & 平均分</span>
              <el-tag size="small" type="info">{{ Object.keys(dashboard.by_feature).length }} 个模块</el-tag>
            </div>
          </template>
          <div ref="featureRef" class="chart-box">
            <div v-if="isFeatureEmpty" class="chart-empty">暂无模块数据</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12" class="bottom-right">
        <el-card shadow="never" class="chart-card records-card">
          <template #header>
            <div class="card-header">
              <span>最近评测记录</span>
              <div class="header-actions">
                <el-tag size="small" type="info">{{ records.length }} 条</el-tag>
                <el-button size="small" link type="primary" @click="loadRecords">刷新</el-button>
              </div>
            </div>
          </template>
          <el-table :data="records" size="default" max-height="340" stripe @row-click="openDetail">
            <el-table-column prop="feature" label="模块" width="130" show-overflow-tooltip>
              <template #default="{ row }">
                <el-tag size="small" effect="plain">{{ featureLabel(row.feature) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="模型 / 耗时" width="150" show-overflow-tooltip>
              <template #default="{ row }">
                <div class="record-model">{{ row.model || '—' }}</div>
                <div class="record-meta">{{ row.latency_ms ? row.latency_ms + 'ms' : '—' }} · {{ row.provider || '—' }}</div>
              </template>
            </el-table-column>
            <el-table-column label="综合" width="70" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.overall" :type="scoreTag(row.overall)" size="small">{{ row.overall }}</el-tag>
                <span v-else class="record-meta">—</span>
              </template>
            </el-table-column>
            <el-table-column label="幻觉" width="70" align="center">
              <template #default="{ row }">
                <span v-if="row.hallucination" :class="scoreClass(row.hallucination)">{{ row.hallucination }}</span>
                <span v-else class="record-meta">—</span>
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="状态 / Judge 结论" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.status === 'judging'" class="record-meta">Judge 中…</span>
                <span v-else>{{ row.reason || '已完成，暂无 Judge 结论' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" align="center">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click.stop="openDetail(row)">详情</el-button>
                <el-button v-if="row.trace_id && langfuse?.enabled" link type="info" size="small" @click.stop="openTrace(row.trace_id)">Trace</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 待优化样本队列 -->
    <el-card shadow="never" class="queue-card">
      <template #header>
        <div class="card-header">
          <span>🎯 待优化样本队列（低分自动归集）</span>
          <el-tag size="small" type="danger">{{ lowScoreRecords.length }} 条待复核</el-tag>
        </div>
      </template>
      <el-table :data="lowScoreRecords" size="default" max-height="320" stripe empty-text="暂无低分样本，质量良好 🎉">
        <el-table-column prop="feature" label="模块" width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ featureLabel(row.feature) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="综合" width="70" align="center">
          <template #default="{ row }"><el-tag :type="scoreTag(row.overall)" size="small">{{ row.overall }}</el-tag></template>
        </el-table-column>
        <el-table-column label="幻觉" width="70" align="center">
          <template #default="{ row }"><span :class="scoreClass(row.hallucination)">{{ row.hallucination }}</span></template>
        </el-table-column>
        <el-table-column prop="reason" label="Judge 结论" show-overflow-tooltip />
        <el-table-column label="问题归类" width="180">
          <template #default="{ row }">
            <el-select v-model="row.annotation" size="small" placeholder="标记问题" @change="onAnnotate(row)" @click.stop>
              <el-option label="检索片段缺失" value="retrieval_missing" />
              <el-option label="模型幻觉" value="hallucination" />
              <el-option label="问题模糊" value="ambiguous_input" />
              <el-option label="参考答案错误" value="bad_reference" />
              <el-option label="已修复" value="resolved" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click.stop="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 说明 -->
    <el-card shadow="never" class="info-card">
      <div class="info-grid">
        <div class="info-item">
          <div class="info-title">评测机制</div>
          <p>每次 LLM 调用自动上报 Langfuse trace；Judge LLM 基于幻觉率、一致性、完整性、可执行性、安全性五个维度打分，分数同步写入 Langfuse Score。</p>
        </div>
        <div class="info-item">
          <div class="info-title">部署位置</div>
          <p>Langfuse 服务运行在阿里云 ECS Docker 中，本页面读取后端聚合数据，可直接下钻到原始 Trace 进行人工复核。</p>
        </div>
      </div>
    </el-card>

    <!-- 评测详情抽屉：RAG 链路回放 -->
    <el-drawer v-model="detailVisible" title="链路追踪回放" size="46%" :destroy-on-close="true">
      <div v-if="detail" class="detail-wrap">
        <div class="detail-head">
          <el-tag effect="plain">{{ featureLabel(detail.feature) }}</el-tag>
          <el-tag v-if="detail.overall" :type="scoreTag(detail.overall)">综合 {{ detail.overall }}</el-tag>
          <el-tag v-if="detail.status" :type="detail.status === 'completed' ? 'success' : 'warning'">{{ detail.status === 'judging' ? 'Judge 中' : detail.status }}</el-tag>
          <el-tag type="info">{{ formatTime(detail.created_at) }}</el-tag>
          <el-button v-if="detail.trace_id && langfuse?.enabled" size="small" type="info" @click="openTrace(detail.trace_id)">在 Langfuse 打开</el-button>
        </div>

        <el-divider>执行链路</el-divider>
        <div v-if="detail.trace_steps && detail.trace_steps.length" class="trace-flow">
          <div
            v-for="(step, i) in detail.trace_steps"
            :key="step.step_id || i"
            class="trace-flow-item"
            :class="{
              'is-problem': isProblemStep(step, detail),
              'is-last': i === detail.trace_steps.length - 1,
              ['trace-type-' + step.type]: true,
            }"
            @click="openStepDetail(step)"
          >
            <div class="trace-flow-card">
              <div class="trace-flow-header">
                <div class="trace-flow-icon" :class="stepStatusType(step)">
                  <el-icon :size="16"><component :is="stepIcon(step)" /></el-icon>
                </div>
                <div class="trace-flow-title">{{ step.title }}</div>
                <el-tag v-if="isProblemStep(step, detail)" size="small" type="danger" effect="dark" class="trace-flow-warn">异常</el-tag>
              </div>
              <div class="trace-flow-output" :title="stepOutputText(step)">
                {{ truncate(stepOutputText(step), 90) }}
              </div>
              <div class="trace-flow-meta">
                <template v-if="step.type === 'route'">
                  <el-tag size="small" effect="dark" type="info">{{ step.metadata?.task_type }}</el-tag>
                  <el-tag size="small" effect="dark" type="success">{{ step.metadata?.model }}</el-tag>
                </template>
                <template v-else-if="step.type === 'retrieve'">
                  <el-tag size="small" effect="dark" type="info">{{ step.metadata?.hit_count || 0 }} chunk</el-tag>
                </template>
                <template v-else-if="step.type === 'llm'">
                  <el-tag size="small" effect="dark" type="info">{{ step.metadata?.model }}</el-tag>
                  <el-tag size="small" effect="dark" type="warning">{{ step.metadata?.latency_ms }}ms</el-tag>
                  <el-tag size="small" effect="dark" type="success">≈{{ step.metadata?.token_usage }} token</el-tag>
                </template>
                <template v-else-if="step.type === 'judge'">
                  <el-tag size="small" effect="dark" :type="scoreTag(step.metadata?.overall || 0)">综合 {{ step.metadata?.overall || 0 }}</el-tag>
                </template>
                <template v-else>
                  <el-tag size="small" effect="dark" type="info">{{ step.status || 'completed' }}</el-tag>
                </template>
              </div>
            </div>
            <div v-if="i < detail.trace_steps.length - 1" class="trace-flow-arrow">
              <el-icon :size="18"><ArrowRight /></el-icon>
            </div>
          </div>
        </div>
        <el-steps v-else :active="traceActiveStep(detail)" align-center finish-status="success" class="trace-steps">
          <el-step title="用户提问" :description="truncate(detail.input_text, 60)" />
          <el-step title="LLM 路由" :description="(detail.model || '—') + ' / ' + (detail.provider || '—')" />
          <el-step v-if="(detail.retrieved_docs || []).length" title="RAG 检索" :description="(detail.retrieved_docs || []).length + ' 个片段'" />
          <el-step title="LLM 生成" :description="(detail.latency_ms ? detail.latency_ms + 'ms' : '—') + (detail.token_usage ? ' · ' + detail.token_usage + ' tokens' : '')" />
          <el-step title="Judge 评分" :description="(detail.overall ? '综合 ' + detail.overall : '未评分')" />
        </el-steps>

        <!-- 链路节点诊断弹窗 -->
        <el-dialog v-model="stepDetailVisible" title="节点诊断" width="520px" :destroy-on-close="true" class="step-detail-dialog">
          <div v-if="selectedStep" class="step-detail-body">
            <div class="step-detail-head">
              <div class="step-detail-icon" :class="stepStatusType(selectedStep)">
                <el-icon :size="20"><component :is="stepIcon(selectedStep)" /></el-icon>
              </div>
              <div>
                <div class="step-detail-title">{{ selectedStep.title }}</div>
                <div class="step-detail-status">
                  <el-tag :type="stepStatusType(selectedStep)">{{ selectedStep.status || 'completed' }}</el-tag>
                  <el-tag v-if="isProblemStep(selectedStep, detail)" type="danger" class="ml-2">疑似异常</el-tag>
                </div>
              </div>
            </div>

            <el-divider />

            <div class="step-detail-section">
              <div class="step-detail-label">节点输出</div>
              <pre class="step-detail-output">{{ stepOutputText(selectedStep) || '（无输出）' }}</pre>
            </div>

            <div v-if="selectedStep.metadata && Object.keys(selectedStep.metadata).length" class="step-detail-section">
              <div class="step-detail-label">关键指标</div>
              <div class="step-detail-metrics">
                <div v-for="(v, k) in selectedStep.metadata" :key="k" class="step-detail-metric">
                  <span class="step-detail-key">{{ k }}</span>
                  <span class="step-detail-val">{{ typeof v === 'object' ? JSON.stringify(v).slice(0, 120) : v }}</span>
                </div>
              </div>
            </div>

            <div v-if="isProblemStep(selectedStep, detail)" class="step-detail-section">
              <div class="step-detail-label">为什么出问题？</div>
              <div class="step-detail-diagnosis">{{ stepDiagnosis(selectedStep, detail) }}</div>
            </div>

            <div v-if="isProblemStep(selectedStep, detail)" class="step-detail-section">
              <div class="step-detail-label">建议方案</div>
              <div class="step-detail-solution">{{ stepSolution(selectedStep, detail) }}</div>
            </div>
          </div>
        </el-dialog>

        <el-divider>检索上下文（RAG 引用）</el-divider>
        <div v-if="(detail.retrieved_docs || []).length" class="doc-list">
          <div v-for="(doc, i) in detail.retrieved_docs" :key="i" class="doc-item">
            <div class="doc-meta">
              <span class="doc-idx">#{{ i + 1 }}</span>
              <span class="doc-src">{{ doc.source || '知识库' }}</span>
              <span class="doc-score">相关度 {{ doc.score ?? '—' }}</span>
            </div>
            <div class="doc-content">{{ doc.content }}</div>
          </div>
        </div>
        <el-empty v-else description="该记录无检索上下文（非 RAG 路径）" :image-size="60" />

        <el-divider>Judge 评分明细</el-divider>
        <div class="dim-bars">
          <div v-for="d in dimList" :key="d.key" class="dim-bar-item">
            <span class="dim-bar-name">{{ d.label }}</span>
            <el-progress :percentage="detail[d.key] || 0" :stroke-width="12" :show-text="false" :color="barColor(detail[d.key] || 0)" />
            <span class="dim-bar-val" :class="scoreClass(detail[d.key] || 0)">{{ detail[d.key] }}</span>
          </div>
        </div>
        <div class="reason-box">
          <div class="reason-title">Judge 结论</div>
          <p>{{ detail.reason || '（无说明）' }}</p>
        </div>

        <!-- 实时流水线记录仪：幻觉根因定位 + 修改建议 -->
        <template v-if="(detail.issues && detail.issues.length) || (detail.retrieval_gaps && detail.retrieval_gaps.length) || (detail.recommendations && detail.recommendations.length)">
          <el-divider content-position="left">
            <span class="recorder-title">🔍 幻觉/问题定位记录仪</span>
          </el-divider>

          <div v-if="detail.issues && detail.issues.length" class="issue-list">
            <div class="recorder-subtitle">问题定位清单（{{ detail.issues.length }}）</div>
            <div v-for="(iss, i) in detail.issues" :key="i" class="issue-card" :class="'sev-' + (iss.severity || 'medium')">
              <div class="issue-head">
                <el-tag :type="sevTag(iss.severity)" size="small">{{ sevLabel(iss.severity) }}</el-tag>
                <el-tag size="small" effect="plain">{{ dimLabel(iss.dimension) }}</el-tag>
                <span class="issue-loc">{{ iss.location || '未标注位置' }}</span>
              </div>
              <div class="issue-row"><span class="issue-key">问题陈述</span><span class="issue-claim">{{ iss.claim }}</span></div>
              <div class="issue-row"><span class="issue-key">事实依据</span><span class="issue-evi">{{ iss.evidence || '—' }}</span></div>
              <div class="issue-row issue-fix"><span class="issue-key">修改建议</span><span class="issue-sug">{{ iss.suggestion || '—' }}</span></div>
            </div>
          </div>

          <div v-if="detail.retrieval_gaps && detail.retrieval_gaps.length" class="gap-block">
            <div class="recorder-subtitle">检索缺口（RAG 漏召回）</div>
            <ul class="gap-list">
              <li v-for="(g, i) in detail.retrieval_gaps" :key="i">{{ g }}</li>
            </ul>
          </div>

          <div v-if="detail.recommendations && detail.recommendations.length" class="rec-block">
            <div class="recorder-subtitle">工程优化建议</div>
            <ul class="rec-list">
              <li v-for="(r, i) in detail.recommendations" :key="i">{{ r }}</li>
            </ul>
          </div>
        </template>

        <el-divider>输入输出原文</el-divider>
        <div class="io-block">
          <div class="io-label">用户提问</div>
          <pre class="io-text">{{ detail.input_text || '—' }}</pre>
        </div>
        <div class="io-block">
          <div class="io-label">AI 回答</div>
          <pre class="io-text">{{ detail.output_text || '—' }}</pre>
        </div>
        <div v-if="detail.model || detail.latency_ms || detail.token_usage" class="meta-line">
          <el-tag size="small" v-if="detail.model">模型 {{ detail.model }}</el-tag>
          <el-tag size="small" v-if="detail.latency_ms">耗时 {{ detail.latency_ms }}ms</el-tag>
          <el-tag size="small" v-if="detail.token_usage">Tokens {{ detail.token_usage }}</el-tag>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, RefreshLeft, VideoPlay, Link, Monitor, Collection, Medal, View, Grid, Download, ArrowRight, User, Switch, Search, Document, Cpu, CircleCheck } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { evalCenterAPI } from '@/api'

const featureLabels = {
  ai_testcase: 'AI 用例生成',
  data_generation: '数据工厂',
  data_factory: '数据工厂',
  knowledge_chat: 'RAG 知识问答',
  chat: '智能对话',
  fast_chat: 'AI 快速问答',
  reasoning: 'AI 深度思考',
  rag_query: 'RAG 问答',
  rag_search: 'RAG 检索',
  agent_loop: 'Agent 循环',
  requirement_review: '需求评审',
  quality_check: '质量检查',
  evaluate: 'AI 评测',
  unknown: '未分类',
}
const featureLabel = (f) => featureLabels[f] || f || '未分类'
const truncate = (s, n) => (s && s.length > n ? s.slice(0, n) + '…' : (s || ''))
function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z')
  if (isNaN(d.getTime())) return iso
  const pad = (x) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const hours = ref(24)
const granularity = ref('hour')
const loading = ref(false)
const dashboard = ref({
  total_records: 0,
  granularity: 'hour',
  avg_scores: { overall: 0, hallucination: 0, consistency: 0, completeness: 0, executability: 0, safety: 0 },
  by_feature: {},
  trend: [],
  recent_records: [],
})
const langfuse = ref({ enabled: false, host: '', traces_url: '' })
const records = ref([])
const recordsLoading = ref(false)
const detailVisible = ref(false)
const detail = ref(null)
const stepDetailVisible = ref(false)
const selectedStep = ref(null)
const demoLoading = ref(false)
const isTracking = ref(false)
const autoRefresh = ref(localStorage.getItem('eval-center-auto-refresh') === 'true')
const refreshInterval = ref(30)
let trackingTimer = null
const LOW_OVERALL = 70
const LOW_HALLUCINATION = 60
const lastEventMs = ref(0)
const pollLoading = ref(false)

const lowScoreRecords = computed(() =>
  records.value.filter(r =>
    (r.overall !== undefined && r.overall < LOW_OVERALL) ||
    (r.hallucination !== undefined && r.hallucination < LOW_HALLUCINATION)
  )
)

async function loadRecords() {
  recordsLoading.value = true
  try {
    // 事件驱动：优先读取真实 AI 调用事件；为空时 fallback 到历史 Judge 记录
    let list = []
    try {
      const data = await evalCenterAPI.events({ limit: 100, since_ms: 0 })
      list = Array.isArray(data) ? data : (data.events || [])
      lastEventMs.value = (data.latest_ms || lastEventMs.value)
    } catch (_) {}
    if (!list.length) {
      const data = await evalCenterAPI.records({ hours: 720, limit: 100 })
      const rows = Array.isArray(data) ? data : (data.records || [])
      list = rows.map(normalizeRecordToEvent)
    }
    records.value = list.map(normalizeEventToRecord)
  } catch (e) {
    ElMessage.error('记录加载失败：' + (e.message || e))
  } finally {
    recordsLoading.value = false
  }
}

// 把旧 EvalStore 记录统一成 EvalEvent 样式，保证前端只处理一种结构
function normalizeRecordToEvent(rec) {
  return {
    event_id: rec.record_id || rec.trace_id || ('rec-' + Date.now()),
    feature: rec.feature,
    input_summary: rec.input_text,
    output_summary: rec.output_text,
    model: rec.model,
    provider: rec.provider || '—',
    latency_ms: rec.latency_ms,
    token_usage: rec.token_usage,
    trace_id: rec.trace_id,
    retrieved_docs: rec.retrieved_docs,
    status: 'completed',
    judge: rec.judge,
    dimension_scores: rec.dimension_scores || (rec.judge || {}).dimension_scores,
    issues: rec.issues,
    timestamp: rec.created_at,
    created_at_ms: rec.created_at ? new Date(rec.created_at).getTime() : Date.now(),
  }
}

// 把 EvalEvent 统一成记录表可用的行结构
function normalizeEventToRecord(ev) {
  const judge = ev.judge_output || ev.judge || {}
  const dims = judge.dimension_scores || ev.dimension_scores || {}
  const overall = judge.overall ?? dims['综合分'] ?? dims.overall ?? 0
  return {
    event_id: ev.event_id,
    feature: ev.feature,
    input_text: ev.input_summary,
    output_text: ev.output_summary,
    model: ev.model,
    provider: ev.provider,
    latency_ms: ev.latency_ms,
    token_usage: ev.token_usage,
    trace_id: ev.trace_id,
    retrieved_docs: ev.retrieved_docs,
    overall,
    hallucination: dims['幻觉率'] ?? dims.hallucination ?? 0,
    consistency: dims['一致性'] ?? dims.consistency ?? 0,
    completeness: dims['完整性'] ?? dims.completeness ?? 0,
    executability: dims['可执行性'] ?? dims.executability ?? 0,
    safety: dims['安全性'] ?? dims.safety ?? 0,
    reason: judge.summary || judge.reason || (ev.status === 'judging' ? 'Judge 中…' : ''),
    issues: judge.issues || ev.issues || [],
    created_at: ev.timestamp,
    status: ev.status,
    trace_steps: ev.trace_steps || [],
    metadata: ev.metadata || {},
    _raw: ev,
  }
}

function isLegacyRecordId(id) {
  return id && (id.startsWith('local-') || id.startsWith('rec-'))
}

async function openDetail(row) {
  // local-/rec- 开头的 ID 来自旧 EvalStore 记录，不是事件存储里的真实 AI 调用事件，直接展示本行数据
  if (row.event_id && !isLegacyRecordId(row.event_id)) {
    try {
      const ev = await evalCenterAPI.event(row.event_id)
      detail.value = normalizeEventToRecord(ev)
    } catch (e) {
      ElMessage.error('详情加载失败：' + (e.message || e))
      detail.value = row
    }
  } else {
    detail.value = row
  }
  detailVisible.value = true
}

const annotations = ref({})  // trace_id -> 标注
function onAnnotate(row) {
  if (row.trace_id) {
    annotations.value[row.trace_id] = row.annotation
  }
  ElMessage.success('已标记：' + (row.annotation || ''))
}

function exportReport() {
  const d = dashboard.value
  const lines = [
    '全链路评测中心 · 测试报告',
    `统计周期：近 ${hours.value} 小时`,
    `生成时间：${new Date().toLocaleString()}`,
    '',
    `评测样本总数：${d.total_records}`,
    `覆盖业务模块：${Object.keys(d.by_feature).length}`,
    '',
    '【多维度平均分】',
    ...dimList.map(x => `  ${x.label}：${scoreOf(x.key)}`),
    '',
    '【各模块评测分布】',
    ...Object.entries(d.by_feature).map(([k, v]) => `  ${featureLabel(k)}：样本 ${v.count} | 平均分 ${v.avg_overall}`),
    '',
    '【最近评测记录】',
    ...records.value.slice(0, 50).map(r => `  [${r.overall}] ${featureLabel(r.feature)} - ${r.reason || '（无说明）'}`),
  ]
  const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `eval-report-${new Date().toISOString().slice(0, 10)}.txt`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('报告已导出')
}

function exportCSV() {
  const header = ['时间', '模块', '综合', '幻觉率', '一致性', '完整性', '可执行性', '安全性', 'Trace', 'Judge结论']
  const rows = records.value.map(r => [
    formatTime(r.created_at), featureLabel(r.feature), r.overall, r.hallucination,
    r.consistency, r.completeness, r.executability, r.safety, r.trace_id || '', (r.reason || '').replace(/[\n,]/g, ' '),
  ])
  const csv = [header, ...rows].map(row => row.map(c => `"${c}"`).join(',')).join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `eval-records-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('CSV 已导出')
}

function exportJSON() {
  const blob = new Blob([JSON.stringify(records.value, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `eval-records-${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('JSON 已导出')
}

const isTrendEmpty = computed(() => !(dashboard.value.trend || []).some(t => (t.count || 0) > 0))
const isFeatureEmpty = computed(() => !Object.keys(dashboard.value.by_feature || {}).length)
// 单点兜底：非空趋势点只有 1 个时，放大圆点并特殊显示
const isSinglePoint = computed(() => (dashboard.value.trend || []).filter(t => (t.count || 0) > 0).length === 1)
const granularityText = computed(() => {
  const map = { hour: '按小时', week: '按周', month: '按月' }
  return map[dashboard.value.granularity] || map[granularity.value] || '按小时'
})

const radarRef = ref(null)
const trendRef = ref(null)
const featureRef = ref(null)
let radarChart = null
let trendChart = null
let featureChart = null

const defaultScores = () => ({ overall: 0, hallucination: 0, consistency: 0, completeness: 0, executability: 0, safety: 0 })
const defaultDashboard = () => ({
  total_records: 0,
  granularity: 'hour',
  avg_scores: defaultScores(),
  by_feature: {},
  trend: [],
  recent_records: [],
})

function normalizeDashboard(data) {
  const d = data || {}
  return {
    total_records: d.total_records ?? 0,
    granularity: d.granularity || 'hour',
    avg_scores: { ...defaultScores(), ...(d.avg_scores || {}) },
    by_feature: d.by_feature || {},
    trend: Array.isArray(d.trend) ? d.trend : [],
    recent_records: Array.isArray(d.recent_records) ? d.recent_records : [],
  }
}

async function loadDashboard() {
  loading.value = true
  try {
    // axios 拦截器已返回 response.data，无需再解构 { data }
    const data = await evalCenterAPI.dashboard(hours.value, granularity.value)
    dashboard.value = normalizeDashboard(data)
    nextTick(() => setTimeout(initCharts, 100))
  } catch (e) {
    ElMessage.error('仪表盘加载失败：' + (e.message || e))
  } finally {
    loading.value = false
  }
}

async function loadLangfuseConfig() {
  try {
    const data = await evalCenterAPI.langfuseConfig()
    langfuse.value = data || { enabled: false }
  } catch {
    langfuse.value = { enabled: false }
  }
}

// 离线演示用的结构化根因样例（后端不可达时也能展示"问题定位记录仪"）
function buildOfflineDemo() {
  return {
    hallucination: 20, consistency: 70, completeness: 60, executability: 70, safety: 90, overall: 62,
    reason: '生成内容包含多处与参考材料不符的幻觉信息，如到账时间、无理由秒退和优惠券补偿。',
    dimension_scores: { 幻觉率: 20, 一致性: 70, 完整性: 60, 可执行性: 70, 安全性: 90 },
    issues: [
      { severity: 'high', dimension: 'hallucination', location: '答案第2条',
        claim: '退款将在 24 小时内到账',
        evidence: "参考材料明确说明'审核通过后 1-3 个工作日到账'，24 小时与 1-3 个工作日不符。",
        suggestion: "改为'审核通过后 1-3 个工作日到账'。" },
      { severity: 'high', dimension: 'hallucination', location: '答案第3条',
        claim: '平台还支持无理由秒退——用户无需任何理由可在 7 天内一键全额退款',
        evidence: "参考材料明确说明'不支持无理由秒退'，且不应编造 7 天无理由退货政策。",
        suggestion: "删除该句，或改为'平台不支持无理由秒退'。" },
      { severity: 'medium', dimension: 'hallucination', location: '答案第3条',
        claim: '退款会额外赠送 5% 的优惠券作为补偿',
        evidence: '参考材料中无任何关于优惠券补偿的信息。',
        suggestion: '删除该句，或补充相关事实依据。' },
    ],
    retrieval_gaps: [
      '未检索到关于退款到账时间的准确表述（1-3 个工作日）',
      '未检索到关于无理由秒退的限制条款',
    ],
    recommendations: [
      '在知识库中补充退款政策的详细说明，包括到账时间、无理由退货限制等。',
      '在生成流程中增加事实校验步骤，确保输出与检索内容一致。',
      '在 prompt 中强制要求模型引用参考材料的具体条款，避免编造。',
    ],
  }
}

// 手动触发：用固定样例跑一遍 Judge（用于离线演示或验证渲染）
async function demoJudge() {
  demoLoading.value = true
  const req = {
    input_text: '我们的会员系统支持哪些退款方式？退款多久到账？',
    output_text: '根据知识库：本平台支持原路退回和余额退回两种方式。退款将在 24 小时内到账。' +
      '此外，平台还支持"无理由秒退"——用户无需任何理由可在 7 天内一键全额退款，' +
      '并且退款会额外赠送 5% 的优惠券作为补偿。',
    reference: '会员退款规则：支持原路退回、余额退回。审核通过后 1-3 个工作日到账。不支持无理由秒退。',
    feature: 'rag_qa',
  }
  let payload = null
  try {
    const data = await evalCenterAPI.judge(req)
    payload = data.success === true ? data.data : data
  } catch (e) {
    // 后端不可达（如未登录/无 token）→ 用离线样例展示渲染效果
    payload = buildOfflineDemo()
  } finally {
    demoLoading.value = false
  }
  if (payload && payload.overall !== undefined) {
    detail.value = {
      ...payload,
      input_text: req.input_text,
      output_text: req.output_text,
      retrieved_docs: [{ source: '会员退款规则.md', score: 0.91, content: req.reference }],
      feature: req.feature,
      created_at: new Date().toISOString(),
      trace_id: payload.trace_id || ('demo-' + Date.now()),
      model: 'deepseek-chat',
      latency_ms: 0,
      token_usage: 0,
    }
    loadDashboard()
    if (!isTracking.value) {
      ElMessage.success('样例评测完成，综合分：' + payload.overall + '（含幻觉定位）')
    }
  } else if (!isTracking.value) {
    ElMessage.error('评测失败')
  }
}

// 自动追踪核心：轮询后端真实 AI 调用事件，只有用户使用 AI 功能才刷新
async function pollEvents() {
  if (pollLoading.value) return
  pollLoading.value = true
  try {
    const data = await evalCenterAPI.poll(lastEventMs.value)
    if (data.new) {
      lastEventMs.value = data.latest_ms || lastEventMs.value
      // 有新事件时刷新面板和记录列表
      await loadDashboard()
      await loadRecords()
      // 静默模式下不弹 toast，避免短周期刷屏
      if (!isTracking.value && data.count) {
        ElMessage.info(`检测到 ${data.count} 条新的 AI 调用，已刷新看板`)
      }
    }
  } catch (e) {
    // 自动追踪失败时不弹窗刷屏，只打印日志
    console.warn('[EvalCenter] 轮询失败', e)
  } finally {
    pollLoading.value = false
  }
}

function openLatestReplay() {
  // 优先打开最新真实事件；没有事件时 fallback 到手动样例
  if (records.value.length) {
    openDetail(records.value[0])
    return
  }
  demoLoading.value = true
  demoJudge().then(() => {
    demoLoading.value = false
    if (detail.value && detail.value.overall !== undefined) {
      detailVisible.value = true
    }
  })
}

function restartAutoRefresh() {
  if (isTracking.value) {
    if (trackingTimer) {
      clearInterval(trackingTimer)
      trackingTimer = null
    }
    pollEvents()
    trackingTimer = setInterval(() => {
      if (!isTracking.value) return
      pollEvents()
    }, refreshInterval.value * 1000)
  }
}

function toggleAutoRefresh() {
  if (autoRefresh.value) {
    startTracking()
  } else {
    stopTracking()
  }
}

function startTracking() {
  isTracking.value = true
  autoRefresh.value = true
  localStorage.setItem('eval-center-auto-refresh', 'true')
  const sec = refreshInterval.value
  const label = sec < 60 ? `${sec} 秒` : `${Math.round(sec / 60)} 分钟`
  ElMessage({ type: 'info', message: `已开启自动追踪，每 ${label} 静默刷新一次（仅在使用 AI 功能时更新）`, duration: 2000 })
  // 立即执行一次轮询，并启动定时器
  pollEvents()
  trackingTimer = setInterval(() => {
    if (!isTracking.value) return
    pollEvents()
  }, refreshInterval.value * 1000)
}

function stopTracking() {
  isTracking.value = false
  autoRefresh.value = false
  localStorage.setItem('eval-center-auto-refresh', 'false')
  if (trackingTimer) {
    clearInterval(trackingTimer)
    trackingTimer = null
  }
}

function scoreClass(score) {
  if (score >= 85) return 'score-excellent'
  if (score >= 60) return 'score-good'
  return 'score-poor'
}

function scoreTag(score) {
  if (score >= 85) return 'success'
  if (score >= 60) return 'warning'
  return 'danger'
}

function sevLabel(sev) {
  return { high: '严重', medium: '中等', low: '轻微' }[sev] || '中等'
}
function sevTag(sev) {
  return { high: 'danger', medium: 'warning', low: 'info' }[sev] || 'warning'
}
function dimLabel(dim) {
  return {
    hallucination: '幻觉', consistency: '一致性', completeness: '完整性',
    executability: '可执行性', safety: '安全性',
  }[dim] || dim || '其他'
}

function traceActiveStep(row) {
  if (!row) return 0
  let step = 1
  if (row.model) step = 2
  if ((row.retrieved_docs || []).length) step = 3
  if (row.model && row.latency_ms) step = 4
  if (row.overall) step = 5
  return step
}

function stepStatusType(step) {
  if (step.status === 'failed' || step.status === 'error') return 'danger'
  if (step.status === 'running') return 'primary'
  return 'success'
}

function isProblemStep(step, detailRow) {
  if (step.status === 'failed' || step.status === 'error') return true
  const m = step.metadata || {}
  if (step.type === 'judge' && (m.overall === 0 || m.overall === undefined)) return true
  if (step.type === 'llm' && m.token_usage === 1) return true
  if (step.type === 'llm' && m.latency_ms > 10000) return true
  if (step.type === 'retrieve' && (m.hit_count === 0 || m.hit_count === undefined)) return true
  if (step.type === 'route' && m.fallback) return true
  // 若整条记录 judge 为 0，且该步骤是生成/评分相关，标红提示
  if (detailRow && detailRow.overall === 0 && ['llm', 'judge', 'route'].includes(step.type)) return true
  return false
}

const stepIconMap = {
  input: User,
  route: Switch,
  retrieve: Search,
  prompt: Document,
  llm: Cpu,
  judge: Medal,
}

function stepIcon(step) {
  return stepIconMap[step.type] || CircleCheck
}

function stepOutputText(step) {
  if (step.output) return step.output
  if (step.type === 'input') return step.detail || ''
  if (step.type === 'route') return (step.metadata?.model) || ''
  if (step.type === 'llm') return (step.metadata?.route_reason) || ''
  return step.detail || ''
}

function openStepDetail(step) {
  selectedStep.value = step
  stepDetailVisible.value = true
}

function stepDiagnosis(step, detailRow) {
  const m = step.metadata || {}
  if (step.status === 'failed' || step.status === 'error') {
    return `该步骤执行失败（status=${step.status}）。可能是模型接口异常、超时或依赖服务（如向量库、路由配置）不可用。`
  }
  if (step.type === 'judge' && (m.overall === 0 || m.overall === undefined)) {
    return 'Judge 评分返回 0 或未生成评分。常见原因：Judge LLM 未被触发、Judge prompt 未命中输出格式、或评分维度字段缺失。'
  }
  if (step.type === 'llm' && m.token_usage === 1) {
    return 'LLM 生成 token 数极少，疑似输出被截断、模型拒绝回答、或 max_tokens/temperature 设置过严。'
  }
  if (step.type === 'llm' && m.latency_ms > 10000) {
    return 'LLM 调用耗时超过 10 秒，存在明显延迟。可能当前模型负载高、网络抖动，或提示词过长导致首 token 时间增加。'
  }
  if (step.type === 'retrieve' && (m.hit_count === 0 || m.hit_count === undefined)) {
    return '检索未命中任何上下文片段。可能是知识库为空、向量相似度阈值过高、query 与文档差异大，或未走 RAG 路径。'
  }
  if (step.type === 'route' && m.fallback) {
    return '路由命中 fallback 模型。说明首选模型不可用、配额耗尽，或路由规则未覆盖当前 task_type。'
  }
  if (detailRow && detailRow.overall === 0 && ['llm', 'judge', 'route'].includes(step.type)) {
    return '本记录综合评分为 0，该步骤可能是导致未评分的环节，建议检查 Judge 执行链路或模型输出完整性。'
  }
  return '该步骤暂未发现明显异常。点击可查看详细指标与输出内容。'
}

function stepSolution(step, detailRow) {
  const m = step.metadata || {}
  if (step.status === 'failed' || step.status === 'error') {
    return '查看 ai-orchestrator 容器日志，定位模型/RAG/路由层的异常栈；确认 API Key、网络与依赖服务状态。'
  }
  if (step.type === 'judge' && (m.overall === 0 || m.overall === undefined)) {
    return '1) 检查 eval_loop.py 是否被触发；2) 确认 Judge prompt 要求返回 JSON 维度分数；3) 在日志中搜索 "Judge" 查看解析失败原因。'
  }
  if (step.type === 'llm' && m.token_usage === 1) {
    return '1) 提高 max_tokens；2) 检查 temperature/top_p 是否过低；3) 查看原始输出是否为空/截断；4) 必要时换模型重试。'
  }
  if (step.type === 'llm' && m.latency_ms > 10000) {
    return '1) 启用流式响应以提升首 token 体验；2) 缩短 prompt；3) 切换更低延迟模型；4) 检查网络与模型服务端负载。'
  }
  if (step.type === 'retrieve' && (m.hit_count === 0 || m.hit_count === undefined)) {
    return '1) 确认知识库已上传并建立索引；2) 调低向量检索阈值；3) 检查 query 编码器是否与索引一致；4) 如无需 RAG，可明确关闭 RAG 开关。'
  }
  if (step.type === 'route' && m.fallback) {
    return '1) 检查 model_configs 中首选模型配置是否生效；2) 查看路由表是否覆盖 task_type；3) 确认首选模型配额/网络正常。'
  }
  if (detailRow && detailRow.overall === 0 && ['llm', 'judge', 'route'].includes(step.type)) {
    return '从 LLM 生成输出、Judge 评分结果、路由选择三个方向排查，确保每个步骤都有有效输出且 Judge 能正确解析。'
  }
  return '保持当前配置，定期观察该步骤指标趋势。'
}

function barColor(score) {
  if (score >= 85) return '#4ade80'
  if (score >= 60) return '#fbbf24'
  return '#f87171'
}

function ringColor(percentage) {
  return barColor(percentage)
}

const dimList = [
  { key: 'overall', label: '综合分' },
  { key: 'hallucination', label: '幻觉率' },
  { key: 'consistency', label: '一致性' },
  { key: 'completeness', label: '完整性' },
  { key: 'executability', label: '可执行性' },
  { key: 'safety', label: '安全性' },
]

function scoreOf(key) {
  const v = dashboard.value.avg_scores[key]
  return typeof v === 'number' ? v : 0
}

function initCharts() {
  const refs = [radarRef.value, trendRef.value, featureRef.value]
  const ready = refs.every(el => el && el.offsetHeight > 0 && el.offsetWidth > 0)
  if (!ready) {
    setTimeout(initCharts, 300)
    return
  }
  initRadar()
  initTrend()
  initFeature()
}

function initRadar() {
  if (!radarRef.value) return
  radarChart?.dispose()
  radarChart = echarts.init(radarRef.value, null, { renderer: 'canvas' })
  const s = dashboard.value.avg_scores
  const dims = ['幻觉率', '一致性', '完整性', '可执行性', '安全性']
  const values = [s.hallucination, s.consistency, s.completeness, s.executability, s.safety]
  const option = {
    color: ['#818cf8'],
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(15,23,42,0.95)',
      borderColor: 'rgba(148,163,184,0.2)',
      textStyle: { color: '#e2e8f0' },
      formatter: () => {
        return dims.map((name, i) => `${name}: <strong>${values[i] ?? 0}</strong>`).join('<br/>')
      },
    },
    radar: {
      indicator: dims.map(name => ({ name, max: 100 })),
      radius: '60%',
      axisName: {
        color: '#94a3b8',
        formatter: (name, indicator) => {
          const idx = dims.indexOf(name)
          return `{name|${name}}\n{score|${values[idx] ?? 0}}`
        },
        rich: {
          name: { color: '#94a3b8', fontSize: 12, lineHeight: 16 },
          score: { color: '#e2e8f0', fontSize: 14, fontWeight: 'bold', lineHeight: 18 },
        },
      },
      splitArea: { areaStyle: { color: ['rgba(148,163,184,0.06)', 'rgba(148,163,184,0.12)'] } },
      axisLine: { lineStyle: { color: 'rgba(148,163,184,0.25)' } },
      splitLine: { lineStyle: { color: 'rgba(148,163,184,0.2)' } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: values,
        name: '平均分',
      }],
      areaStyle: { opacity: 0.25, color: '#818cf8' },
      lineStyle: { width: 3 },
      symbol: 'circle',
      symbolSize: 6,
      label: { show: false },
    }],
  }
  radarChart.setOption(option)
}

// 后端 hour 字段是 UTC（day 聚合: "2026-08-18"；hour 聚合: "2026-08-18T13"）。
// 这里按浏览器本地时区解析并格式化为短标签。
function formatTrendLabel(item) {
  const hour = typeof item === 'string' ? item : (item?.hour || '')
  const latestAt = typeof item === 'string' ? null : item?.latest_at
  if (!hour) return ''
  // 月度聚合："2026-08"
  if (/^\d{4}-\d{2}$/.test(hour)) {
    return hour
  }
  // 周/月聚合：用桶内最新记录时间的本地日期做标签
  const useLocalDate = dashboard.value.granularity === 'week' || dashboard.value.granularity === 'month'
  if (useLocalDate && latestAt) {
    const d = new Date(latestAt)
    if (!isNaN(d.getTime())) {
      const pad = n => String(n).padStart(2, '0')
      return `${pad(d.getMonth() + 1)}.${pad(d.getDate())}`
    }
  }
  // 小时聚合：hour 形如 "2026-08-19T00"
  if (/^\d{4}-\d{2}-\d{2}T\d{2}$/.test(hour)) {
    const d = new Date(`${hour}:00:00Z`)
    if (!isNaN(d.getTime())) {
      const pad = n => String(n).padStart(2, '0')
      return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:00`
    }
  }
  return hour
}

function initTrend() {
  if (!trendRef.value) return
  trendChart?.dispose()
  // 只保留有数据的坐标点，让标签正好落在数据正下方
  const trend = (dashboard.value.trend || []).filter(t => (t.count || 0) > 0)
  if (trend.length === 0) {
    trendChart = null
    return
  }
  trendChart = echarts.init(trendRef.value, null, { renderer: 'canvas' })
  const x = trend.map(t => formatTrendLabel(t))
  const rawHours = trend.map(t => t.latest_at || t.hour)
  const avg = trend.map(t => (t.avg_overall == null ? null : Number(t.avg_overall)))
  const count = trend.map(t => Number(t.count) || 0)
  const maxCount = Math.max(...count, 1)
  const single = trend.length === 1
  const rotate = x.length > 6 ? 35 : 0

  const series = [
    {
      name: '平均综合分',
      type: 'line',
      data: avg,
      smooth: true,
      lineStyle: { width: single ? 0 : 3 },
      symbol: 'circle',
      symbolSize: single ? 14 : 4,
      itemStyle: { color: '#60a5fa', borderColor: '#fff', borderWidth: single ? 2 : 0 },
      label: {
        show: true,
        position: 'top',
        color: '#e2e8f0',
        fontSize: single ? 12 : 10,
        formatter: p => (p.value == null ? '' : p.value),
        distance: 8,
      },
    },
    {
      name: '评测次数',
      type: 'scatter',
      yAxisIndex: 1,
      data: count,
      symbol: 'circle',
      symbolSize: value => Math.min(12, Math.max(5, Math.sqrt(value || 0) * 2)),
      itemStyle: { color: 'rgba(52,211,153,0.85)', shadowBlur: 3, shadowColor: 'rgba(52,211,153,0.25)' },
      label: {
        show: true,
        position: 'top',
        color: '#e2e8f0',
        fontSize: 10,
        formatter: p => (p.value > 0 ? p.value : ''),
        distance: 5,
      },
    },
  ]

  const option = {
    color: ['#60a5fa', '#34d399'],
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15,23,42,0.95)',
      borderColor: 'rgba(148,163,184,0.2)',
      textStyle: { color: '#e2e8f0' },
      formatter: params => {
        const idx = params[0].dataIndex
        const time = rawHours[idx] || params[0].name
        let html = `<div style="font-weight:600;margin-bottom:4px">${time}</div>`
        params.forEach(p => {
          if (p.value == null) return
          html += `<div style="display:flex;align-items:center;gap:6px">
            <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color}"></span>
            <span>${p.seriesName}：${p.value}</span>
          </div>`
        })
        return html
      },
    },
    legend: { data: ['平均综合分', '评测次数'], bottom: 0, textStyle: { color: '#94a3b8' } },
    grid: { top: 36, left: 40, right: 50, bottom: 42, containLabel: true },
    xAxis: {
      type: 'category',
      data: x,
      axisTick: { alignWithLabel: true },
      axisLabel: { interval: 0, rotate, color: '#94a3b8' },
      axisLine: { lineStyle: { color: 'rgba(148,163,184,0.25)' } },
    },
    yAxis: [
      { type: 'value', name: '分数', min: 0, max: 100, axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: 'rgba(148,163,184,0.1)' } } },
      { type: 'value', name: '次数', min: 0, max: Math.ceil(maxCount * 1.2), axisLabel: { color: '#94a3b8' }, splitLine: { show: false } },
    ],
    series,
  }
  trendChart.setOption(option)
}

function initFeature() {
  if (!featureRef.value) return
  featureChart?.dispose()
  if (isFeatureEmpty.value) {
    featureChart = null
    return
  }
  featureChart = echarts.init(featureRef.value, null, { renderer: 'canvas' })
  const byFeature = dashboard.value.by_feature || {}
  const names = Object.keys(byFeature)
  const counts = names.map(n => byFeature[n].count)
  const avgs = names.map(n => byFeature[n].avg_overall)
  const option = {
    color: ['#fbbf24', '#2dd4bf'],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: 'rgba(15,23,42,0.95)', borderColor: 'rgba(148,163,184,0.2)', textStyle: { color: '#e2e8f0' } },
    legend: { data: ['评测次数', '平均综合分'], bottom: 0, textStyle: { color: '#94a3b8' } },
    grid: { top: 20, left: 40, right: 40, bottom: 40, containLabel: true },
    xAxis: { type: 'category', data: names, axisLabel: { interval: 0, rotate: 20, color: '#94a3b8' }, axisLine: { lineStyle: { color: 'rgba(148,163,184,0.25)' } } },
    yAxis: [
      { type: 'value', name: '次数', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: 'rgba(148,163,184,0.1)' } } },
      { type: 'value', name: '分数', max: 100, axisLabel: { color: '#94a3b8' }, splitLine: { show: false } },
    ],
    series: [
      { name: '评测次数', type: 'bar', data: counts, itemStyle: { borderRadius: [4, 4, 0, 0] } },
      { name: '平均综合分', type: 'line', yAxisIndex: 1, data: avgs, lineStyle: { width: 3 }, symbol: 'circle', symbolSize: 6 },
    ],
  }
  featureChart.setOption(option)
}

function openLangfuse() {
  if (langfuse.value.traces_url) {
    window.open(langfuse.value.traces_url, '_blank')
  }
}

function onExport(cmd) {
  if (cmd === 'csv') return exportCSV()
  if (cmd === 'json') return exportJSON()
  return exportReport()
}

function openTrace(traceId) {
  if (langfuse.value.host) {
    window.open(`${langfuse.value.host}/traces/${traceId}`, '_blank')
  }
}

function onResize() {
  radarChart?.resize()
  trendChart?.resize()
  featureChart?.resize()
}

onMounted(() => {
  loadDashboard()
  loadLangfuseConfig()
  loadRecords()
  window.addEventListener('resize', onResize)
  if (autoRefresh.value) {
    startTracking()
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  radarChart?.dispose()
  trendChart?.dispose()
  featureChart?.dispose()
  // 只清 timer，不重置 autoRefresh：状态由 localStorage 持久化，切回页面可恢复
  if (trackingTimer) {
    clearInterval(trackingTimer)
    trackingTimer = null
  }
  isTracking.value = false
})
</script>

<style scoped>
.detail-wrap { color: #e2e8f0; }
.detail-head { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 4px; }
.trace-steps { margin: 8px 0 4px; }
.doc-list { display: flex; flex-direction: column; gap: 10px; }
.doc-item { background: rgba(148,163,184,0.08); border: 1px solid rgba(148,163,184,0.18); border-radius: 10px; padding: 10px 12px; }
.doc-meta { display: flex; gap: 10px; align-items: center; font-size: 12px; color: #94a3b8; margin-bottom: 6px; }
.doc-idx { background: #6366f1; color: #fff; border-radius: 6px; padding: 0 6px; font-weight: 700; }
.doc-score { color: #34d399; }
.doc-content { font-size: 13px; line-height: 1.6; white-space: pre-wrap; color: #cbd5e1; }
.dim-bars { display: flex; flex-direction: column; gap: 10px; }
.dim-bar-item { display: flex; align-items: center; gap: 12px; }
.dim-bar-name { width: 80px; font-size: 13px; color: #cbd5e1; flex-shrink: 0; }
.dim-bar-item :deep(.el-progress) { flex: 1; }
.dim-bar-val { width: 40px; text-align: right; font-weight: 700; }
.reason-box { margin-top: 14px; background: rgba(99,102,241,0.10); border-left: 3px solid #6366f1; border-radius: 8px; padding: 10px 12px; }
.reason-title { font-size: 13px; color: #a5b4fc; margin-bottom: 6px; font-weight: 600; }
.reason-box p { margin: 0; font-size: 13px; line-height: 1.6; color: #e2e8f0; white-space: pre-wrap; }
.io-block { margin-bottom: 12px; }
.io-label { font-size: 12px; color: #94a3b8; margin-bottom: 4px; }
.io-text { background: rgba(15,23,42,0.6); border: 1px solid rgba(148,163,184,0.15); border-radius: 8px; padding: 10px 12px; font-size: 12px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; max-height: 200px; overflow: auto; margin: 0; }
.meta-line { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
.header-actions { display: flex; align-items: center; gap: 8px; }
.record-model { font-size: 12px; color: #e2e8f0; line-height: 1.4; }
.record-meta { font-size: 11px; color: #94a3b8; line-height: 1.3; }
.score-excellent { color: #4ade80; }
.score-good { color: #fbbf24; }
.score-poor { color: #f87171; }
.recorder-title { color: #f0abfc; font-weight: 600; }
.recorder-subtitle { font-size: 12px; color: #c4b5fd; margin: 10px 0 6px; font-weight: 600; }
.issue-list { display: flex; flex-direction: column; gap: 8px; }
.issue-card { background: rgba(15,23,42,0.55); border: 1px solid rgba(148,163,184,0.18); border-left-width: 4px; border-radius: 8px; padding: 10px 12px; }
.issue-card.sev-high { border-left-color: #f87171; }
.issue-card.sev-medium { border-left-color: #fbbf24; }
.issue-card.sev-low { border-left-color: #60a5fa; }
.issue-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.issue-loc { font-size: 12px; color: #94a3b8; }
.issue-row { display: flex; gap: 8px; font-size: 12.5px; line-height: 1.6; margin-bottom: 4px; }
.issue-key { flex: 0 0 64px; color: #818cf8; font-weight: 600; }
.issue-claim { color: #fca5a5; flex: 1; }
.issue-evi { color: #e2e8f0; flex: 1; }
.issue-fix .issue-sug { color: #86efac; flex: 1; }
.gap-block, .rec-block { margin-top: 6px; }
.gap-list, .rec-list { margin: 0; padding-left: 18px; }
.gap-list li, .rec-list li { font-size: 12.5px; line-height: 1.7; color: #e2e8f0; }
.gap-list li { color: #fcd34d; }
.rec-list li { color: #a5f3fc; }

/* 横向执行链路流程图 */
.trace-flow {
  display: flex;
  align-items: stretch;
  gap: 0;
  padding: 12px 4px 24px;
  overflow-x: auto;
}

.trace-flow-item {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 160px;
  max-width: 260px;
  cursor: pointer;
}

.trace-flow-card {
  flex: 1;
  min-height: 130px;
  padding: 12px;
  border-radius: 12px;
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.15);
  box-shadow: 0 4px 12px rgba(2, 6, 23, 0.2);
  transition: all 0.2s ease;
}

.trace-flow-item:hover .trace-flow-card {
  transform: translateY(-2px);
  border-color: rgba(56, 189, 248, 0.4);
  box-shadow: 0 8px 24px rgba(2, 6, 23, 0.35);
}

.trace-flow-item.is-problem .trace-flow-card {
  border-color: rgba(248, 113, 113, 0.55);
  background: rgba(69, 26, 26, 0.35);
  box-shadow: 0 0 16px rgba(248, 113, 113, 0.18);
}

.trace-flow-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.trace-flow-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  color: #fff;
}

.trace-flow-icon.success { background: linear-gradient(135deg, #22c55e, #16a34a); }
.trace-flow-icon.primary { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.trace-flow-icon.danger { background: linear-gradient(135deg, #ef4444, #dc2626); }

.trace-flow-title {
  flex: 1;
  font-weight: 600;
  font-size: 14px;
  color: #e2e8f0;
}

.trace-flow-warn {
  flex-shrink: 0;
}

.trace-flow-output {
  min-height: 38px;
  margin-bottom: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.45);
  color: #cbd5e1;
  font-size: 12px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.trace-flow-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.trace-flow-meta .el-tag {
  margin: 0;
}

.trace-flow-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  flex-shrink: 0;
  color: #64748b;
}

.trace-flow-item.is-problem .trace-flow-arrow {
  color: #f87171;
}

/* 节点诊断弹窗 */
:global(.el-dialog.step-detail-dialog),
:global(.step-detail-dialog .el-dialog) {
  background: #0f172a !important;
  border: 1px solid rgba(148, 163, 184, 0.2) !important;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.6) !important;
}
:global(.step-detail-dialog .el-dialog__header) {
  background: transparent !important;
  border-bottom: 1px solid rgba(148, 163, 184, 0.15) !important;
  padding-bottom: 14px !important;
}
:global(.step-detail-dialog .el-dialog__title) {
  color: #f8fafc !important;
  font-weight: 600 !important;
}
:global(.step-detail-dialog .el-dialog__body) {
  background: #0f172a !important;
  color: #e2e8f0 !important;
  padding-top: 10px !important;
}
:global(.step-detail-dialog .el-dialog__headerbtn .el-dialog__close) {
  color: #94a3b8 !important;
}
:global(.step-detail-dialog .el-dialog__headerbtn .el-dialog__close:hover) {
  color: #f8fafc !important;
}

.step-detail-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-detail-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  color: #fff;
}

.step-detail-icon.success { background: linear-gradient(135deg, #22c55e, #16a34a); }
.step-detail-icon.primary { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.step-detail-icon.danger { background: linear-gradient(135deg, #ef4444, #dc2626); }

.step-detail-title {
  font-weight: 600;
  font-size: 16px;
  color: #e2e8f0;
  margin-bottom: 6px;
}

.step-detail-status {
  display: flex;
  gap: 8px;
}

.step-detail-section {
  margin-bottom: 18px;
}

.step-detail-label {
  font-size: 13px;
  font-weight: 600;
  color: #94a3b8;
  margin-bottom: 8px;
}

.step-detail-output {
  margin: 0;
  padding: 10px;
  border-radius: 8px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 12.5px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 220px;
  overflow: auto;
}

.step-detail-metrics {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.step-detail-metric {
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(30, 41, 59, 0.5);
  font-size: 12px;
}

.step-detail-key {
  display: block;
  color: #94a3b8;
  margin-bottom: 4px;
}

.step-detail-val {
  color: #e2e8f0;
  word-break: break-all;
}

.step-detail-diagnosis,
.step-detail-solution {
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.7;
}

.step-detail-diagnosis {
  background: rgba(69, 26, 26, 0.55);
  border: 1px solid rgba(248, 113, 113, 0.35);
  color: #fecaca;
}

.step-detail-solution {
  background: rgba(12, 74, 110, 0.45);
  border: 1px solid rgba(56, 189, 248, 0.35);
  color: #bae6fd;
}

.ml-2 { margin-left: 8px; }

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.5; }
  100% { opacity: 1; }
}
</style>

<style scoped>
.eval-center {
  padding: 24px;
  min-height: 100vh;
  background: radial-gradient(1200px 600px at 80% -10%, #243049 0%, #1e293b 55%);
  color: #e2e8f0;
}

.hero {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 24px 28px;
  margin-bottom: 20px;
  background: linear-gradient(120deg, rgba(99,102,241,0.18) 0%, rgba(45,212,191,0.10) 100%);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 16px;
  box-shadow: 0 10px 30px rgba(2, 6, 23, 0.25);
}

.hero-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.title-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #fff;
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.35);
  flex-shrink: 0;
}

.hero-left h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #f8fafc;
  line-height: 1.3;
  letter-spacing: 0.5px;
}

.subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: #cbd5e1;
}

.hero-right {
  display: flex;
  align-items: center;
  gap: 24px;
}

.hero-right .health-ring {
  display: flex;
  align-items: center;
}

.ring-value {
  display: block;
  font-size: 26px;
  font-weight: 700;
  color: #f8fafc;
  line-height: 1;
}

.ring-label {
  display: block;
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.track-wrap {
  display: inline-flex;
  align-items: center;
  margin-left: 2px;
}

/* 自动追踪 switch：未开启时提高对比度，避免在深色背景下太暗 */
:deep(.track-switch .el-switch__core) {
  border-color: rgba(148, 163, 184, 0.5);
  background-color: rgba(30, 41, 59, 0.8);
}
:deep(.track-switch .el-switch__label) {
  color: #e2e8f0;
}
:deep(.track-switch.is-checked .el-switch__core) {
  border-color: #22c55e;
  background-color: #22c55e;
}
:deep(.track-switch.is-checked .el-switch__label) {
  color: #fff;
}

.track-dot {
  width: 9px;
  height: 9px;
  margin-left: 7px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7);
  animation: track-pulse 1.4s infinite;
}

@keyframes track-pulse {
  0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
  70% { box-shadow: 0 0 0 7px rgba(34, 197, 94, 0); }
  100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
}

.metric-row {
  margin-bottom: 20px;
}

.metric-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: #27354d;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(2, 6, 23, 0.2);
  transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
}

.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(2, 6, 23, 0.3);
  border-color: rgba(148, 163, 184, 0.32);
}

.metric-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: 12px;
  flex-shrink: 0;
}

.metric-icon.blue { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.metric-icon.purple { background: rgba(139, 92, 246, 0.15); color: #a78bfa; }
.metric-icon.orange { background: rgba(249, 115, 22, 0.15); color: #fb923c; }
.metric-icon.teal { background: rgba(20, 184, 166, 0.15); color: #2dd4bf; }

.metric-body {
  flex: 1;
  min-width: 0;
}

.metric-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  color: #f8fafc;
}

.trend-header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.metric-label {
  margin-top: 4px;
  font-size: 13px;
  color: #94a3b8;
}

.score-excellent { color: #4ade80; }
.score-good { color: #fbbf24; }
.score-poor { color: #f87171; }

.dim-card {
  background: #27354d;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(2, 6, 23, 0.2);
  color: #e2e8f0;
  margin-bottom: 16px;
}

.dim-card :deep(.el-card__header) {
  padding: 16px 20px;
  font-weight: 600;
  color: #f8fafc;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.dim-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px 28px;
  padding: 8px 4px 4px;
}

.dim-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dim-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.dim-name {
  font-size: 13px;
  color: #cbd5e1;
}

.dim-score {
  font-size: 16px;
  font-weight: 700;
}

.chart-row {
  margin-bottom: 16px;
}

.chart-row.bottom-row {
  margin-top: 0;
  align-items: stretch;
}

.chart-row.bottom-row .el-col {
  display: flex;
}

.chart-row.bottom-row .chart-card {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.chart-row.bottom-row .chart-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.records-card :deep(.el-table) {
  flex: 1;
}

.records-card :deep(.el-table__body-wrapper) {
  max-height: none !important;
}

.chart-card {
  background: #27354d;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(2, 6, 23, 0.2);
  color: #e2e8f0;
}

.chart-card :deep(.el-card__header) {
  padding: 16px 20px;
  font-weight: 600;
  color: #f8fafc;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chart-box {
  position: relative;
  width: 100%;
  height: 260px;
}

.chart-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  font-size: 15px;
  font-weight: 500;
  pointer-events: none;
}

.feature-card .chart-box,
.chart-card:has(.el-table) .chart-box {
  height: 240px;
}

.bottom-row {
  margin-top: 0;
}

.info-card {
  background: #27354d;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(2, 6, 23, 0.2);
  color: #cbd5e1;
  margin-top: 16px;
}

.info-card :deep(.el-card__body) {
  padding: 20px 24px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
}

.info-title {
  font-size: 14px;
  font-weight: 600;
  color: #f8fafc;
  margin-bottom: 8px;
}

.info-item p {
  margin: 0;
  font-size: 13px;
  color: #94a3b8;
  line-height: 1.7;
}

.chart-card :deep(.el-table),
.chart-card :deep(.el-table__expanded-cell),
.chart-card :deep(.el-table th.el-table__cell),
.chart-card :deep(.el-table tr),
.chart-card :deep(.el-table td.el-table__cell) {
  background: transparent;
  color: #e2e8f0;
}

.chart-card :deep(.el-table th.el-table__cell) {
  background: rgba(15, 23, 42, 0.25);
  font-weight: 600;
  color: #f8fafc;
}

.chart-card :deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background: rgba(15, 23, 42, 0.15);
}

.chart-card :deep(.el-table__body tr:hover > td.el-table__cell) {
  background: rgba(99, 102, 241, 0.12);
}

.chart-card :deep(.el-table__empty-text) {
  color: #64748b;
}

/* 抽屉：减少遮罩雾化，增加内容对比度 */
:global(.el-overlay) {
  background-color: rgba(0, 0, 0, 0.55) !important;
}
:global(.el-drawer) {
  background: #0f172a !important;
  box-shadow: -12px 0 40px rgba(0, 0, 0, 0.55);
}
:global(.el-drawer__header) {
  color: #f8fafc !important;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  margin-bottom: 0;
  padding: 18px 20px;
  font-weight: 600;
}
:global(.el-drawer__body) {
  padding: 20px;
  color: #e2e8f0;
}
:global(.el-drawer__close-btn) {
  color: #94a3b8;
}
:global(.el-drawer__close-btn:hover) {
  color: #f8fafc;
}

@media (max-width: 768px) {
  .eval-center { padding: 16px; }
  .page-header { flex-direction: column; align-items: flex-start; }
  .metric-card { margin-bottom: 12px; }
}
</style>
