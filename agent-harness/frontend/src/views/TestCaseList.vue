<template>
  <div class="testcase-container">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>测试用例列表</span>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon>
              <Plus />
            </el-icon>
            新建用例
          </el-button>
        </div>
      </template>

      <!-- 批量操作栏 -->
      <div class="batch-actions">
        <el-alert :title="selectedRows.length > 0 ? `已选择 ${selectedRows.length} 项` : '未选择任何项'"
          :type="selectedRows.length > 0 ? 'info' : 'warning'" :closable="false"
          style="display: inline-block; margin-right: 10px" />
        <el-button size="small" type="primary" :disabled="selectedRows.length === 0" @click="showBatchAddToSuiteDialog">
          <el-icon>
            <FolderAdd />
          </el-icon>
          批量加入测试套件
        </el-button>
        <el-button size="small" type="success" :disabled="selectedRows.length === 0" @click="batchExecute">
          <el-icon>
            <VideoPlay />
          </el-icon>
          批量执行
        </el-button>
        <el-button size="small" type="danger" :disabled="selectedRows.length === 0" @click="batchDelete">
          <el-icon>
            <Delete />
          </el-icon>
          批量删除
        </el-button>
      </div>

      <!-- 搜索栏 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="搜索">
          <el-input v-model="searchForm.search" placeholder="标题/描述/接口地址" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="草稿" value="draft"><span class="option-dot option-dot--draft"></span>草稿</el-option>
            <el-option label="激活" value="active"><span class="option-dot option-dot--active"></span>激活</el-option>
            <el-option label="停用" value="inactive"><span class="option-dot option-dot--inactive"></span>停用</el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="searchForm.priority" placeholder="全部" clearable style="width: 120px">
            <el-option label="P0" value="P0"><span class="option-dot option-dot--p0"></span>P0</el-option>
            <el-option label="P1" value="P1"><span class="option-dot option-dot--p1"></span>P1</el-option>
            <el-option label="P2" value="P2"><span class="option-dot option-dot--p2"></span>P2</el-option>
            <el-option label="P3" value="P3"><span class="option-dot option-dot--p3"></span>P3</el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="请求方法">
          <el-select v-model="searchForm.method" placeholder="全部" clearable style="width: 120px">
            <el-option label="GET" value="GET" />
            <el-option label="POST" value="POST" />
            <el-option label="PUT" value="PUT" />
            <el-option label="DELETE" value="DELETE" />
            <el-option label="PATCH" value="PATCH" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadTestCases">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 空状态 -->
      <EmptyState v-if="!loading && !testCases.length" title="暂无测试用例" description="点击新建用例按钮创建第一个测试用例，或使用AI生成功能批量生成">
        <template #action>
          <el-button type="primary" @click="showCreateDialog">新建用例</el-button>
          <el-button @click="$router.push('/testcases/ai-generate')">AI生成</el-button>
        </template>
      </EmptyState>

      <!-- 表格 -->
      <el-table v-else :data="testCases" border stripe v-loading="loading" @selection-change="handleSelectionChange"
        style="width: 100%">
        <el-table-column type="selection" width="55" />
        <el-table-column prop="id" label="ID" width="60" sortable />
        <el-table-column prop="title" label="标题" min-width="150" sortable />
        <el-table-column prop="api_endpoint" label="接口地址" min-width="200" show-overflow-tooltip sortable>
          <template #default="{ row }">
            <el-tooltip :content="row.api_endpoint" placement="top" effect="dark">
              <span class="api-endpoint-text">{{ truncateApiEndpoint(row.api_endpoint) }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="method" label="请求方法" width="90" sortable>
          <template #default="{ row }">
            <el-tag :type="getMethodType(row.method)" size="small">{{ row.method }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_execution_status" label="上次执行状态" width="100" sortable>
          <template #default="{ row }">
            <el-tag v-if="row.last_execution_status" :type="getExecutionStatusType(row.last_execution_status)"
              size="small">
              {{ getExecutionStatusText(row.last_execution_status) }}
            </el-tag>
            <span v-else class="no-execution-text">未执行</span>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="80" sortable>
          <template #default="{ row }">
            <el-tag :type="getPriorityType(row.priority)" size="small">{{ row.priority }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80" sortable>
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160" sortable>
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="340" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="success" @click="executeTestCase(row)">
              <el-icon>
                <VideoPlay />
              </el-icon>
              执行
            </el-button>
            <el-button size="small" @click="showViewDialog(row)">查看</el-button>
            <el-button size="small" type="primary" @click="copyTestCase(row)">复制</el-button>
            <el-button size="small" @click="showEditDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteTestCase(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.pageSize"
        :total="pagination.total" :page-sizes="[10, 20, 50, 100]" layout="total, sizes, prev, pager, next, jumper"
        style="margin-top: 20px; justify-content: flex-end" @size-change="loadTestCases"
        @current-change="loadTestCases" />
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isView ? '查看测试用例' : (isEdit ? '编辑测试用例' : '新建测试用例')" width="960px"
      top="5vh" class="refined-edit-dialog">
      <!-- 快捷功能栏（仅编辑/新建模式显示） -->
      <div v-if="!isView" class="quick-actions-bar">
        <el-button-group>
          <el-button size="small" class="ghost-btn" @click="aiParseInterface" :loading="aiParsing">
            <el-icon>
              <MagicStick />
            </el-icon>
            AI一键解析接口
          </el-button>
          <el-button size="small" class="ghost-btn" @click="oneClickDebug">
            <el-icon>
              <VideoPlay />
            </el-icon>
            一键调试
          </el-button>
          <el-button size="small" class="ghost-btn" @click="formatJSON">
            <el-icon>
              <DocumentChecked />
            </el-icon>
            JSON格式化
          </el-button>
          <el-button size="small" class="ghost-btn" @click="previewVariables">
            <el-icon>
              <View />
            </el-icon>
            变量预览
          </el-button>
        </el-button-group>

        <!-- AI解析状态提示 -->
        <el-tag v-if="aiParsing" class="ai-status-tag" size="small">
          <el-icon class="is-loading">
            <Loading />
          </el-icon>
          AI正在解析接口...
        </el-tag>
        <el-tag v-else-if="aiParsedFields.size > 0" class="ai-status-tag" size="small">
          <el-icon>
            <Check />
          </el-icon>
          接口解析完成 (已填充 {{ aiParsedFields.size }} 个字段)
        </el-tag>
      </div>

      <!-- AI解析预览面板（仅在有AI生成内容时显示） -->
      <div v-if="!isView && aiParsedFields.size > 0" class="parse-preview-panel">
        <div class="parse-preview-header">
          <span class="parse-preview-title">
            <el-icon>
              <MagicStick />
            </el-icon>
            AI解析结果预览
          </span>
          <div class="parse-preview-actions">
            <el-button size="small" text @click="keepOnlyCoreAssertions">仅保留核心断言</el-button>
            <el-button size="small" text @click="clearAIAssertions">清空AI断言</el-button>
            <el-button size="small" text @click="clearAIParsedFields">清除AI标记</el-button>
            <el-button size="small" type="primary" @click="applyAllAIFields">全部应用</el-button>
          </div>
        </div>
        <div class="parse-preview-content">
          <div v-if="aiParsedFields.has('method') && formData.method" class="preview-item">
            <div class="preview-item-label">请求方法</div>
            <div class="preview-item-value" :class="'method-' + (formData.method || 'get').toLowerCase()">{{
              formData.method
            }}</div>
          </div>
          <div v-if="aiParsedFields.has('headers')" class="preview-item">
            <div class="preview-item-label">请求头</div>
            <div class="preview-item-value">{{ Object.keys(JSON.parse(headersText.value || '{}')).length }} 个字段</div>
          </div>
          <div v-if="aiParsedFields.has('request_body')" class="preview-item">
            <div class="preview-item-label">请求体</div>
            <div class="preview-item-value">{{ bodyText.value ? Object.keys(JSON.parse(bodyText.value)).length : 0 }}
              个字段
            </div>
          </div>
          <div v-if="aiParsedFields.has('assertions')" class="preview-item">
            <div class="preview-item-label">断言规则</div>
            <div class="preview-item-value">
              {{(formData.assertion_rules || []).filter(r => r._aiGenerated && r._enabled !== false).length}} 条核心 /
              {{(formData.assertion_rules || []).filter(r => r._aiGenerated && r._category === 'optional').length}}
              条可选
            </div>
          </div>
        </div>
      </div>

      <el-form :model="formData" :rules="formRules" ref="formRef" label-width="100px">
        <!-- 基础请求配置区 -->
        <div class="section-basic-config">
          <el-row :gutter="12">
            <el-col :span="16">
              <el-form-item label="标题" prop="title">
                <el-input v-model="formData.title" placeholder="请输入用例标题" :disabled="isView" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="优先级" prop="priority">
                <el-select v-model="formData.priority" style="width: 100%" :disabled="isView">
                  <el-option label="P0 - 最高" value="P0"><span class="option-dot option-dot--p0"></span>P0 -
                    最高</el-option>
                  <el-option label="P1 - 高" value="P1"><span class="option-dot option-dot--p1"></span>P1 - 高</el-option>
                  <el-option label="P2 - 中" value="P2"><span class="option-dot option-dot--p2"></span>P2 - 中</el-option>
                  <el-option label="P3 - 低" value="P3"><span class="option-dot option-dot--p3"></span>P3 - 低</el-option>
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="描述">
            <el-input v-model="formData.description" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }"
              placeholder="用例描述" :disabled="isView" />
          </el-form-item>

          <el-row :gutter="12">
            <el-col :span="16">
              <el-form-item label="接口地址" prop="api_endpoint">
                <div class="variable-input-wrapper">
                  <el-input v-model="formData.api_endpoint" placeholder="/api/example 或 http://..." :disabled="isView"
                    @input="onApiEndpointChange" />
                  <div v-if="!isView && /\{\{[^}]+\}\}/.test(formData.api_endpoint)" class="variable-highlight-bar"
                    v-html="highlightedApiText"></div>
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="请求方法" prop="method" :class="{ 'ai-generated-field': aiParsedFields.has('method') }">
                <el-select v-model="formData.method" style="width: 100%" :disabled="isView" @change="onMethodChange">
                  <el-option label="GET" value="GET" />
                  <el-option label="POST" value="POST" />
                  <el-option label="PUT" value="PUT" />
                  <el-option label="DELETE" value="DELETE" />
                  <el-option label="PATCH" value="PATCH" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="请求头" :class="{ 'ai-generated-field': aiParsedFields.has('headers') }">
            <div class="request-body-wrapper">
              <el-input v-model="headersText" type="textarea" :autosize="{ minRows: 4, maxRows: 8 }"
                :placeholder="isView ? '' : JSONPlaceholder.headers" :disabled="isView" />
              <div v-if="!isView && /\{\{[^}]+\}\}/.test(headersText)" class="variable-highlight-preview"
                v-html="highlightedHeadersText"></div>
            </div>
          </el-form-item>

          <!-- 请求体：GET请求自动隐藏 -->
          <el-form-item v-if="shouldShowRequestBody" label="请求体"
            :class="{ 'ai-generated-field': aiParsedFields.has('request_body') }">
            <div class="request-body-wrapper">
              <el-input v-model="bodyText" type="textarea" :autosize="{ minRows: 4, maxRows: 8 }"
                :placeholder="isView ? '' : JSONPlaceholder.body" :disabled="isView"
                @input="highlightVariablesInBody" />
              <!-- 变量高亮预览区域 -->
              <div v-if="!isView && hasVariables" class="variable-highlight-preview" v-html="highlightedBodyText"></div>
            </div>
          </el-form-item>
          <el-alert v-else-if="!isView && (formData.method || 'GET') === 'GET'" type="info" :closable="false" show-icon
            style="margin-bottom: 8px">
            GET 请求通常不包含请求体，如需发送数据请使用 URL 参数或请求头
          </el-alert>

          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="状态">
                <el-select v-model="formData.status" style="width: 100%" :disabled="isView">
                  <el-option label="草稿" value="draft"><span class="option-dot option-dot--draft"></span>草稿</el-option>
                  <el-option label="激活" value="active"><span class="option-dot option-dot--active"></span>激活</el-option>
                  <el-option label="停用" value="inactive"><span
                      class="option-dot option-dot--inactive"></span>停用</el-option>
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <!-- 断言&预期响应区 -->
        <div class="section-assertion-response">
          <!-- 断言规则区域（编辑/新建模式） -->
          <el-form-item label="断言规则" v-if="!isView" class="module-title-item">
            <div class="assertion-rules-area">
              <div class="rule-header">
                <span class="rule-col field-col">字段路径</span>
                <span class="rule-col op-col">运算符</span>
                <span class="rule-col value-col">预期值</span>
                <span class="rule-col action-col"></span>
              </div>
              <div class="rule-body">
                <!-- 空状态引导提示 -->
                <div v-if="formData.assertion_rules.length === 0" class="rule-empty-hint">
                  <el-icon class="empty-hint-icon"><InfoFilled /></el-icon>
                  <div class="empty-hint-text">
                    <p v-if="parsedFieldList.length > 0"><strong>请在下方「可提取字段」中勾选字段，点击「生成断言规则」来添加断言</strong></p>
                    <p v-else>请先填写「预期响应」JSON 或点击「AI 一键解析」来获取可提取字段</p>
                    <p>你也可以点击下方「添加断言规则」手动输入</p>
                  </div>
                </div>
                <div v-for="(rule, index) in formData.assertion_rules" :key="rule.id" class="rule-row" :class="{
                'assertion-rule-ai-generated': rule._aiGenerated,
                'assertion-rule-core': rule._category === 'core',
                'assertion-rule-optional': rule._category === 'optional',
                'assertion-rule-disabled': rule._enabled === false
              }">
                <!-- AI 标识 -->
                <span v-if="rule._aiGenerated" class="ai-badge">AI</span>
                <!-- 字段路径：下拉选择 + 可手动输入 -->
                <el-select v-model="rule.field" filterable allow-create default-first-option placeholder="选择或输入字段"
                  class="rule-col field-col" @change="(val) => { handleFieldSelect(rule); watchFieldChange(rule); }">
                  <el-option-group label="内置字段">
                    <el-option v-for="field in BUILTIN_FIELDS" :key="field.value" :label="field.label"
                      :value="field.value" />
                  </el-option-group>
                  <el-option-group v-if="parsedFieldList.length > 0" label="从预期响应提取">
                    <el-option v-for="field in parsedFieldList.filter(f => f._category !== 'dynamic')" :key="field.path"
                      :label="field.path" :value="field.path" />
                  </el-option-group>
                  <el-option-group v-if="parsedFieldList.some(f => f._category === 'dynamic')" label="动态字段（仅提取）">
                    <el-option v-for="field in parsedFieldList.filter(f => f._category === 'dynamic')" :key="field.path"
                      :label="`${field.path} (${field._description || '动态字段'})`" :value="field.path" disabled />
                  </el-option-group>
                </el-select>

                <!-- 运算符下拉 -->
                <el-select v-model="rule.operator" placeholder="运算符" class="rule-col op-col"
                  @change="handleOperatorChange(rule)">
                  <el-option v-for="op in ASSERTION_OPERATORS" :key="op.value" :label="op.label" :value="op.value" />
                </el-select>

                <!-- 预期值输入框（条件显示） -->
                <el-input v-if="rule._showValue !== false" v-model="rule.value"
                  :placeholder="getValuePlaceholder(rule.operator)" class="rule-col value-col"
                  :class="{ 'value-missing': isValueMissing(rule) }"
                  :disabled="rule._enabled === false && rule._category === 'optional'" />
                <span v-else-if="rule._enabled === false && rule._category === 'optional'"
                  class="no-value-hint">未启用</span>
                <span v-else class="no-value-hint">无需输入</span>

                <!-- 删除按钮 -->
                <el-button link @click="removeRule(index)" class="rule-col action-col delete-rule-btn">
                  <el-icon>
                    <Delete />
                  </el-icon>
                </el-button>
              </div>
              </div>
              <!-- rule-body 结束 -->

              <el-button class="add-rule-btn" size="small" @click="addRule">
                <el-icon>
                  <Plus />
                </el-icon> 添加断言规则
              </el-button>
            </div>
          </el-form-item>

          <!-- 变量提取规则区域 -->
          <el-form-item label="变量提取" v-if="!isView" class="module-title-item">
            <div class="assertion-rules-area extract-rules-area">
              <div class="rule-header extract-rule-header">
                <span class="rule-col field-col">字段路径</span>
                <span class="rule-col name-col">变量名</span>
                <span class="rule-col val-col">变量值</span>
                <span class="rule-col var-setting-col">变量设置</span>
                <span class="rule-col action-col" style="width: 40px;"></span>
              </div>
              <div class="rule-body">
                <div v-for="(rule, index) in formData.extract_rules" :key="rule.id" class="rule-row extract-rule-row">
                <!-- 字段路径：下拉选择 + 可手动输入 -->
                <el-select v-model="rule.field_path" filterable allow-create default-first-option placeholder="选择或输入字段"
                  class="rule-col field-col" @change="(val) => handleExtractFieldSelect(rule)" required>
                  <el-option-group v-if="parsedFieldList.length > 0" label="从预期响应提取">
                    <el-option v-for="field in parsedFieldList.filter(f => f._category !== 'dynamic')" :key="field.path"
                      :label="field.path" :value="field.path" />
                  </el-option-group>
                </el-select>

                <el-input v-model="rule.var_name" placeholder="如 token" class="rule-col name-col" required />

                <el-input v-model="rule.var_value" placeholder="变量值" class="rule-col val-col" required />

                <!-- 变量设置：选择全局变量或上下文变量 -->
                <el-select v-model="rule.var_type" placeholder="选择变量类型" class="rule-col var-setting-col" clearable>
                  <el-option label="全局变量" value="global" />
                  <el-option label="上下文变量" value="context" />
                </el-select>

                <!-- 删除按钮 -->
                <div class="rule-col action-col" style="width: 40px;">
                  <el-button link @click="removeExtractRule(index)" class="delete-rule-btn">
                    <el-icon>
                      <Delete />
                    </el-icon>
                  </el-button>
                </div>
              </div>
              </div>
              <!-- rule-body 结束 -->

              <el-button class="add-rule-btn" size="small" @click="addExtractRule">
                <el-icon>
                  <Plus />
                </el-icon> 添加提取规则
              </el-button>
            </div>
          </el-form-item>

          <!-- 预期响应区 -->
          <el-form-item label="预期响应" class="expected-response-form-item">
            <div class="expected-response-area">
              <div class="expected-response-toolbar">
                <el-button-group>
                  <el-tooltip content="复制" placement="top">
                    <el-button size="small" text @click="copyExpectedResponse">
                      <el-icon>
                        <DocumentCopy />
                      </el-icon>
                    </el-button>
                  </el-tooltip>
                  <el-tooltip content="格式化 JSON" placement="top">
                    <el-button size="small" text @click="formatJSON">
                      <el-icon>
                        <DocumentChecked />
                      </el-icon>
                    </el-button>
                  </el-tooltip>
                  <el-tooltip :content="isExpectedCollapsed ? '展开' : '折叠'" placement="top">
                    <el-button size="small" text @click="toggleExpectedCollapse">
                      <el-icon>
                        <component :is="isExpectedCollapsed ? Expand : Fold" />
                      </el-icon>
                    </el-button>
                  </el-tooltip>
                </el-button-group>
              </div>
              <!-- JSON 编辑器 -->
              <el-input v-model="expectedText" type="textarea"
                :autosize="{ minRows: isExpectedCollapsed ? 2 : 5, maxRows: 10 }"
                :placeholder="JSONPlaceholder.response" @input="onExpectedTextChange" />

              <!-- JSON 错误提示 -->
              <el-alert v-if="jsonError" type="error" :closable="false" style="margin-top: 8px" show-icon>
                {{ jsonError }}
              </el-alert>
            </div>
          </el-form-item>

        </div>

        <!-- 可提取字段&提交区 -->
        <div class="section-extract-submit">
          <!-- 智能断言生成面板（编辑/新建模式） -->
          <el-form-item label="可提取字段" v-if="!isView" class="module-title-item">
            <div class="field-list-area">
              <div class="field-list-header">
                <span class="field-list-title">可提取字段 ({{ filteredFieldList.length }}/{{ parsedFieldList.length
                }})</span>
                <div class="field-list-actions">
                  <el-switch v-model="showOnlyUnassertedFields" size="small" active-text="只显示未断言字段" />
                  <el-button size="small" text @click="selectAllFields">全选</el-button>
                  <el-tooltip content="一键取消所有字段勾选状态" placement="top">
                    <el-button size="small" text @click="deselectAllFields">清空勾选</el-button>
                  </el-tooltip>
                  <el-button type="primary" size="small" @click="generateRulesFromFields"
                    :disabled="selectedFieldPaths.size === 0">
                    <el-icon>
                      <Plus />
                    </el-icon> 生成断言规则
                  </el-button>
                </div>
              </div>

              <div class="field-list-body">
                <div v-for="field in filteredFieldList" :key="field.path" class="field-item"
                  :class="{ 'field-item-selected': selectedFieldPaths.has(field.path) }">
                  <el-checkbox :model-value="selectedFieldPaths.has(field.path)"
                    @change="handleFieldCheckbox(field.path, $event)" />
                  <span class="field-path">{{ field.path }}</span>
                  <span class="field-value-preview">{{ formatFieldPreview(field.value) }}</span>
                  <el-tag v-if="isFieldAsserted(field.path)" size="small" type="success" class="field-asserted-tag">
                    已断言
                  </el-tag>
                  <el-tag size="small" class="field-type-tag" :class="'type-tag--' + field.type">
                    {{ field.type }}
                  </el-tag>
                </div>
              </div>
            </div>
          </el-form-item>

          <!-- 标签输入框 -->
          <el-form-item label="标签">
            <el-input v-model="tagsText" placeholder="逗号分隔，如: API,回归测试" :disabled="isView" />
          </el-form-item>
        </div>
      </el-form>

      <!-- 防呆校验提示区域 -->
      <div v-if="!isView && validationErrors.length > 0" class="validation-errors">
        <el-alert type="error" :closable="false" show-icon>
          <template #title>
            <span>发现 {{ validationErrors.length }} 个问题，请修复后再保存：</span>
          </template>
          <ul>
            <li v-for="(error, index) in validationErrors" :key="index">{{ error }}</li>
          </ul>
        </el-alert>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button v-if="!isView" type="primary" @click="submitForm" :loading="submitting"
          :disabled="validationErrors.length > 0">
          确定{{ validationErrors.length > 0 ? ` (${validationErrors.length} 个错误)` : '' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量加入测试套件对话框 -->
    <el-dialog v-model="batchAddToSuiteDialogVisible" title="批量加入测试套件" width="500px">
      <el-form label-width="100px">
        <el-form-item label="选择测试套件">
          <el-select v-model="selectedSuiteId" placeholder="请选择测试套件" style="width: 100%">
            <el-option v-for="suite in testSuites" :key="suite.id" :label="suite.name" :value="suite.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchAddToSuiteDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmBatchAddToSuite" :loading="batchAddingToSuite">确定</el-button>
      </template>
    </el-dialog>

    <!-- 变量预览对话框 -->
    <el-dialog v-model="variablePreviewDialogVisible" title="变量预览" width="640px">
      <div class="variable-preview-content">
        <el-tabs v-model="activeVariableTab">
          <el-tab-pane label="全局变量" name="global">
            <el-empty v-if="globalVariables.length === 0">
              <template #description>
                <div class="empty-desc">未配置全局变量</div>
                <el-button size="small" type="primary" text @click="goToGlobalVarSettings">
                  点击管理 →
                </el-button>
              </template>
            </el-empty>
            <el-table v-else :data="globalVariables" border size="small">
              <el-table-column prop="name" label="变量名" width="150" />
              <el-table-column prop="value" label="值" />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="上下文变量" name="context">
            <el-empty v-if="contextVariables.length === 0" description="暂无上下文变量" />
            <el-table v-else :data="contextVariables" border size="small">
              <el-table-column prop="name" label="变量名" width="150" />
              <el-table-column prop="value" label="值" />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="提取的变量" name="extracted">
            <div v-if="extractedVariables.length === 0" class="extracted-empty">
              <el-empty description="">
                <template #description>
                  <div class="empty-desc">尚未执行用例</div>
                  <div class="empty-hint">执行后将自动提取变量至此</div>
                </template>
                <el-button size="small" type="primary" @click="reExecuteAndRefreshVars">
                  <el-icon>
                    <VideoPlay />
                  </el-icon> 执行并提取
                </el-button>
              </el-empty>
            </div>
            <div v-else>
              <div class="extracted-vars-header">
                <div class="extracted-meta">
                  <el-icon>
                    <Timer />
                  </el-icon>
                  <span>{{ lastExecutionTimeLabel }}</span>
                </div>
              </div>
              <el-table :data="extractedVariables" border size="small">
                <el-table-column prop="name" label="变量名" width="150" />
                <el-table-column prop="source" label="来源" width="120" />
                <el-table-column prop="value" label="值" />
              </el-table>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
      <template #footer>
        <el-button @click="variablePreviewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 执行结果面板（底部内嵌） -->
    <div v-if="resultPanelVisible" class="execution-result-panel">
      <div class="result-panel-header">
        <div class="result-panel-left">
          <el-icon :size="18"><DataAnalysis /></el-icon>
          <span class="result-panel-title">执行结果 · {{ lastResult.name }}</span>
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
          :class="{ 'result-passed': r.status === 'passed', 'result-failed': r.status === 'failed' }"
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
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { testcaseAPI, executionAPI, testsuiteAPI } from '@/api'
import { ElMessage } from 'element-plus'
import EmptyState from '@/components/EmptyState.vue'
import { showDeleteConfirm, showSuccess, showError } from '@/utils/helpers'
import { Delete, Plus, InfoFilled, VideoPlay, FolderAdd, MagicStick, DocumentChecked, View, Loading, Check, DocumentCopy, Fold, Expand, Search, Lightning, CircleCheck, CircleClose, Close, DataAnalysis, Timer, Star, Connection } from '@element-plus/icons-vue'
const router = useRouter()

const loading = ref(false)
const testCases = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const isView = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const selectedRows = ref([])

// 内嵌执行结果面板
const lastResult = ref(null)
const resultPanelVisible = ref(false)

// 批量加入测试套件相关
const batchAddToSuiteDialogVisible = ref(false)
const selectedSuiteId = ref(null)
const testSuites = ref([])
const batchAddingToSuite = ref(false)

// 变量预览相关
const variablePreviewDialogVisible = ref(false)
const activeVariableTab = ref('global')
const globalVariables = ref([])
const contextVariables = ref([])
const extractedVariables = ref([])

// 执行状态
const reExecuting = ref(false)
const lastExecutionTime = ref(null)

// 执行时间标签
const lastExecutionTimeLabel = computed(() => {
  if (!lastExecutionTime.value) return ''
  const now = new Date()
  const diff = Math.floor((now - lastExecutionTime.value) / 1000)
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  return `${Math.floor(diff / 86400)}天前`
})

// 防呆校验错误
const validationErrors = ref([])

// 智能断言面板状态
const jsonError = ref('')
const parsedFieldList = ref([])
const selectedFieldPaths = ref(new Set())
const showOnlyUnassertedFields = ref(true) // 默认只显示未断言字段

// 过滤后的字段列表（根据开关显示/隐藏已断言字段，且只显示 extract_only 类型）
const filteredFieldList = computed(() => {
  let fields = parsedFieldList.value

  // 只显示标记为 extract_only 的字段（可提取变量字段）
  fields = fields.filter(field => field._type === 'extract_only' || !field._type)

  if (!showOnlyUnassertedFields.value) {
    return fields
  }
  // 只显示未断言的字段
  return fields.filter(field => !isFieldAsserted(field.path))
})

// 断言运算符枚举
const ASSERTION_OPERATORS = [
  { label: '等于 (==)', value: '==', needsValue: true },
  { label: '不等于 (!=)', value: '!=', needsValue: true },
  { label: '大于 (>)', value: '>', needsValue: true },
  { label: '小于 (<)', value: '<', needsValue: true },
  { label: '大于等于 (>=)', value: '>=', needsValue: true },
  { label: '小于等于 (<=)', value: '<=', needsValue: true },
  { label: '包含 (contains)', value: 'contains', needsValue: true },
  { label: '存在 (exists)', value: 'exists', needsValue: false },
  { label: '为空 (is empty)', value: 'is_empty', needsValue: false },
  { label: '正则匹配', value: 'matches_regex', needsValue: true },
  { label: 'JSON包含', value: 'json_contains', needsValue: true },
]

// 内置字段选项
const BUILTIN_FIELDS = [
  { label: 'HTTP状态码', value: 'status_code' },
  { label: '响应时间(ms)', value: 'response_time' },
  { label: '业务状态码(code)', value: 'code' },
  { label: '业务消息(msg)', value: 'msg' },
  { label: '响应数据(data)', value: 'data' },
]

// 提取方式选项
const EXTRACT_TYPES = [
  { label: 'JSON Path', value: 'json_path' },
  { label: '正则表达式', value: 'regex' },
  { label: 'Response Header', value: 'header' },
]

// JSON字段占位符
const JSONPlaceholder = {
  headers: '{"Content-Type": "application/json"}',
  body: '{"key": "value"}',
  response: '{"code": 0, "msg": "success"}',
}

const searchForm = reactive({
  search: '',
  status: '',
  priority: '',
  method: '',
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
})

const formData = reactive({
  title: '',
  description: '',
  api_endpoint: '',
  method: 'GET',
  headers: {},
  request_body: {},
  expected_response: {},
  assertion_rules: [],
  extract_rules: [],
  assertions: '',
  priority: 'P2',
  status: 'active',
  tags: [],
})

const headersText = ref('')
const bodyText = ref('')
const expectedText = ref('')
const isExpectedCollapsed = ref(false)
const tagsText = ref('')

const formRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  api_endpoint: [{ required: true, message: '请输入接口地址', trigger: 'blur' }],
}

// ========== 计算属性 ==========

// GET请求自动隐藏请求体
const shouldShowRequestBody = computed(() => {
  const method = formData.method?.toUpperCase()
  return method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS'
})

// 检测是否有变量（{{variable}}格式）
const hasVariables = computed(() => {
  const text = bodyText.value + headersText.value + expectedText.value + formData.api_endpoint
  return /\{\{[^}]+\}\}/.test(text)
})

// 通用高亮变量函数
function highlightVariables(text) {
  if (!text) return ''
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  const varMap = new Map()
  globalVariables.value.forEach(v => varMap.set(v.name, v.value))
  contextVariables.value.forEach(v => varMap.set(v.name, v.value))
  extractedVariables.value.forEach(v => varMap.set(v.name, v.value))

  function makeSpan(varName, className) {
    const val = varMap.get(varName)
    const title = val !== undefined ? `值: ${val}` : '未解析'
    return `<span class="var-highlight ${className}" title="${title}">{{${varName}}}</span>`
  }

  // 高亮全局变量 {{global.xxx}} - 蓝色
  html = html.replace(/\{\{(global\.[^}]+)\}\}/g, (m, p1) => makeSpan(p1, 'var-global'))
  // 高亮上下文变量 {{context.xxx}} - 绿色
  html = html.replace(/\{\{(context\.[^}]+)\}\}/g, (m, p1) => makeSpan(p1, 'var-context'))
  // 高亮其他变量 {{xxx}} - 浅紫色
  html = html.replace(/\{\{([^}]+)\}\}/g, (m, p1) => makeSpan(p1, 'var-other'))

  return html
}

// 高亮显示变量（全局变量蓝色，上下文变量绿色）
const highlightedBodyText = computed(() => highlightVariables(bodyText.value))
const highlightedHeadersText = computed(() => highlightVariables(headersText.value))
const highlightedApiText = computed(() => highlightVariables(formData.api_endpoint))

// 执行状态类型映射
const getExecutionStatusType = (status) => {
  const types = { passed: 'success', failed: 'danger', skipped: 'info', running: 'warning' }
  return types[status] || 'info'
}

// 执行状态文本映射
const getExecutionStatusText = (status) => {
  const texts = { passed: '通过', failed: '失败', skipped: '跳过', running: '运行中' }
  return texts[status] || status
}

// 截断API端点显示
const truncateApiEndpoint = (endpoint) => {
  if (!endpoint) return ''
  if (endpoint.length <= 50) return endpoint
  return endpoint.substring(0, 47) + '...'
}

// ========== 快捷功能栏函数 ==========

// AI解析状态
const aiParsing = ref(false)
const aiParsedFields = ref(new Set()) // 记录AI自动填充的字段

// AI一键解析接口
const aiParseInterface = async () => {
  if (!formData.api_endpoint) {
    ElMessage.warning('请先输入接口地址')
    return
  }

  // URL格式校验
  try {
    new URL(formData.api_endpoint.startsWith('http') ? formData.api_endpoint : `http://${formData.api_endpoint}`)
  } catch {
    ElMessage.error('URL格式错误，请输入有效的接口地址（如: http://localhost:8000/api/users）')
    return
  }

  aiParsing.value = true
  aiParsedFields.value.clear()

  try {
    const response = await testcaseAPI.aiParseInterface({
      api_url: formData.api_endpoint,
      method: formData.method || '',
      response_json: expectedText.value || '',
      request_body: bodyText.value || '',
    })

    // 1. 自动填充请求方法（如果当前为空或是GET但AI识别为其他）
    if (response.method) {
      const currentMethod = formData.method || 'GET'
      if (currentMethod === 'GET' || !formData.method) {
        formData.method = response.method
        aiParsedFields.value.add('method')
      }
    }

    // 2. 自动填充请求头
    if (response.headers && Object.keys(response.headers).length > 0) {
      headersText.value = JSON.stringify(response.headers, null, 2)
      aiParsedFields.value.add('headers')
    }

    // 3. 自动填充请求体（非GET请求）
    if (response.request_body && Object.keys(response.request_body).length > 0 && (formData.method || 'GET') !== 'GET') {
      bodyText.value = JSON.stringify(response.request_body, null, 2)
      aiParsedFields.value.add('request_body')
    }

    // 4. 自动应用断言规则（统一数据模型：只处理核心断言）
    if (response.assertion_rules && Array.isArray(response.assertion_rules)) {
      // 清空现有规则
      formData.assertion_rules = []

      // 添加所有断言规则（后端已按类型分类）
      response.assertion_rules.forEach(rule => {
        formData.assertion_rules.push({
          id: generateRuleId(),
          field: rule.field,
          operator: rule.operator,
          value: rule.value || '',
          _showValue: rule.operator !== 'exists' && rule.operator !== 'is_empty',
          _aiGenerated: true,
          _category: rule.category || 'core',
          _enabled: rule.category === 'core', // 核心断言默认启用
          _type: rule._type || 'assertion_only',
        })
      })

      aiParsedFields.value.add('assertions')
    }

    // 5. 自动填充预期响应（完整JSON，用于手动提取未断言字段）
    if (response.expected_response) {
      try {
        // 格式化显示
        const fullResponse = typeof response.expected_response === 'string'
          ? JSON.parse(response.expected_response)
          : response.expected_response
        expectedText.value = JSON.stringify(fullResponse, null, 2)
        aiParsedFields.value.add('expected_response')
      } catch (e) {
        console.error('Failed to parse expected_response:', e)
        expectedText.value = response.expected_response
      }
    }

    // 6. 更新可提取字段列表（只显示标记为 extract_only 的字段）
    if (response.extracted_fields && Array.isArray(response.extracted_fields)) {
      parsedFieldList.value = response.extracted_fields.map(f => ({
        path: f.path,
        value: f.value,
        type: f.type,
        _type: f._type || 'extract_only',
        _description: f._description || '',
      }))

      aiParsedFields.value.add('extracted_fields')
    }

    // 7. 显示警告信息
    if (response.warnings && response.warnings.length > 0) {
      response.warnings.forEach(warning => {
        ElMessage.warning(warning)
      })
    }

    ElMessage.success('接口解析完成')

  } catch (error) {
    console.error('AI parse error:', error)
    const errorMsg = error.response?.data?.error || error.message || '解析失败'
    ElMessage.error(errorMsg)

    // 给出修复建议
    if (errorMsg.includes('URL')) {
      ElMessage.info('建议：请检查接口地址格式，确保包含协议（http://或https://）')
    } else if (errorMsg.includes('JSON')) {
      ElMessage.info('建议：请检查预期响应JSON格式是否正确')
    }
  } finally {
    aiParsing.value = false
  }
}

// 仅保留核心断言（删除所有AI非核心断言，保留用户手动添加的断言）
const keepOnlyCoreAssertions = () => {
  const coreCount = formData.assertion_rules.filter(r => r._aiGenerated && r._category === 'core').length
  const manualCount = formData.assertion_rules.filter(r => !r._aiGenerated).length

  formData.assertion_rules = formData.assertion_rules.filter(rule => {
    // 保留：1. 用户手动添加的断言 2. AI生成的核心断言
    return !rule._aiGenerated || rule._category === 'core'
  })

  const removedCount = formData.assertion_rules.length - coreCount - manualCount
  ElMessage.success(`已保留 ${coreCount} 条核心断言和 ${manualCount} 条手动断言，删除了 ${removedCount} 条AI非核心断言`)
}

// 清空所有AI生成的断言（只删除带AI标记的断言）
const clearAIAssertions = () => {
  const removedCount = formData.assertion_rules.filter(r => r._aiGenerated).length
  formData.assertion_rules = formData.assertion_rules.filter(rule => !rule._aiGenerated)

  if (removedCount > 0) {
    ElMessage.success(`已清空 ${removedCount} 条AI生成的断言`)
  } else {
    ElMessage.info('没有AI生成的断言需要清空')
  }
}

// 清除AI标记（将AI断言转为用户手动断言）
const clearAIParsedFields = () => {
  let clearedCount = 0
  formData.assertion_rules.forEach(rule => {
    if (rule._aiGenerated) {
      delete rule._aiGenerated
      delete rule._category
      delete rule._enabled
      clearedCount++
    }
  })

  if (clearedCount > 0) {
    ElMessage.success(`已将 ${clearedCount} 条AI断言转为用户手动断言`)
  } else {
    ElMessage.info('没有AI断言需要转换')
  }
}

// 全部应用AI生成的字段（一次性填入核心断言和预期响应）
const applyAllAIFields = () => {
  // 启用所有核心断言
  formData.assertion_rules.forEach(rule => {
    if (rule._aiGenerated && rule._category === 'core') {
      rule._enabled = true
    }
  })

  const enabledCount = formData.assertion_rules.filter(r => r._aiGenerated && r._category === 'core').length
  ElMessage.success(`已应用 ${enabledCount} 条核心断言和预期响应`)
}

// 一键调试
const oneClickDebug = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      ElMessage.info('正在执行调试...')
      try {
        const globalVars = {}
        globalVariables.value.forEach(v => {
          globalVars[v.name] = v.value
        })

        // 统一走 debug-temp 接口，使用表单当前值（避免数据库与表单不一致）
        const response = await testcaseAPI.debugTemp({
          title: formData.title,
          method: formData.method,
          api_endpoint: formData.api_endpoint,
          headers: formData.headers,
          request_body: formData.request_body,
          expected_response: formData.expected_response,
          extract_rules: formData.extract_rules,
          assertion_rules: formData.assertion_rules,
          global_variables: globalVars,
        })
        // 更新提取的变量到全局变量池
        extractedVariables.value = []
        const results = response.execution_results || []
        results.forEach(r => {
          const extracted = r.extracted_vars || {}
          // 自动回填所有提取规则的变量值列
          fillExtractValues(extracted)
          Object.entries(extracted).forEach(([name, value]) => {
            const existing = globalVariables.value.find(v => v.name === name)
            if (existing) {
              existing.value = value
            } else {
              globalVariables.value.push({ name, value })
            }
            extractedVariables.value.push({ name, source: r.title || '响应提取', value })
          })
          lastExecutionTime.value = new Date()
        })
        // 若变量预览弹窗已打开，自动切换到提取的变量Tab
        if (variablePreviewDialogVisible.value) {
          activeVariableTab.value = 'extracted'
        }
        showSuccess(`调试完成: ${response.passed_count || 0} 通过, ${response.failed_count || 0} 失败`)
      } catch (error) {
        ElMessage.error('调试失败: ' + (error.message || '未知错误'))
      }
    }
  })
}

// 复制预期响应
const copyExpectedResponse = async () => {
  try {
    await navigator.clipboard.writeText(expectedText.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

// 折叠/展开预期响应
const toggleExpectedCollapse = () => {
  isExpectedCollapsed.value = !isExpectedCollapsed.value
}

// JSON格式化
const formatJSON = () => {
  try {
    if (headersText.value) {
      headersText.value = JSON.stringify(JSON.parse(headersText.value), null, 2)
    }
    if (bodyText.value) {
      bodyText.value = JSON.stringify(JSON.parse(bodyText.value), null, 2)
    }
    if (expectedText.value) {
      expectedText.value = JSON.stringify(JSON.parse(expectedText.value), null, 2)
    }
    ElMessage.success('JSON格式化完成')
  } catch (error) {
    ElMessage.error('JSON格式错误: ' + error.message)
  }
}

// 变量预览
const previewVariables = () => {
  // 提取所有变量（从文本中提取 {{global.xxx}} 和 {{context.xxx}}）
  const globalVars = new Set()
  const contextVars = new Set()
  const otherVars = new Set()

  const allText = bodyText.value + ' ' + headersText.value + ' ' + expectedText.value + ' ' + formData.api_endpoint
  const varRegex = /\{\{([^}]+)\}\}/g
  let match

  while ((match = varRegex.exec(allText)) !== null) {
    const varName = match[1].trim()
    if (varName.startsWith('global.')) {
      globalVars.add(varName)
    } else if (varName.startsWith('context.')) {
      contextVars.add(varName)
    } else {
      otherVars.add(varName)
    }
  }

  // 优先从 formData.global_vars 和 formData.context_vars 中读取已保存的变量
  const savedGlobalMap = new Map((formData.global_vars || []).map(v => [v.name, v.value]))
  const savedContextMap = new Map((formData.context_vars || []).map(v => [v.name, v.value]))

  // 合并：保存的变量 + 扫描到的变量（保存的优先）
  const existingGlobalMap = new Map(globalVariables.value.map(v => [v.name, v.value]))
  globalVariables.value = Array.from(new Set([
    ...Array.from(savedGlobalMap.keys()),
    ...Array.from(globalVars)
  ])).map(name => ({
    name,
    value: savedGlobalMap.get(name) ?? existingGlobalMap.get(name) ?? '待解析'
  }))

  const existingContextMap = new Map(contextVariables.value.map(v => [v.name, v.value]))
  contextVariables.value = Array.from(new Set([
    ...Array.from(savedContextMap.keys()),
    ...Array.from(contextVars)
  ])).map(name => ({
    name,
    value: savedContextMap.get(name) ?? existingContextMap.get(name) ?? '待解析'
  }))

  // 提取的变量：合并当前编辑的规则和已执行的变量
  const existingExtractMap = new Map(extractedVariables.value.map(v => [v.name, v.value]))

  // 从当前编辑的提取规则中读取变量
  const currentExtractRules = formData.extract_rules
    .filter(rule => rule.var_name && rule.var_name.trim() !== '')
    .map(rule => ({
      name: rule.var_name,
      source: '当前配置',
      value: rule.var_value || '待提取'
    }))

  // 合并：当前编辑的规则 + 已执行的变量（去重）
  const mergedExtracted = new Map()
  currentExtractRules.forEach(v => mergedExtracted.set(v.name, v))
  Array.from(otherVars).forEach(name => {
    if (!mergedExtracted.has(name)) {
      mergedExtracted.set(name, {
        name,
        source: '响应提取',
        value: existingExtractMap.get(name) ?? '执行用例后将自动提取变量至此'
      })
    }
  })

  extractedVariables.value = Array.from(mergedExtracted.values())

  variablePreviewDialogVisible.value = true
}

// 复制变量名
const copyVarName = (name) => {
  navigator.clipboard.writeText(`{{${name}}}`).then(() => {
    ElMessage.success(`已复制 {{${name}}}`)
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

// ========== 防呆校验 ==========

// 运行防呆校验
const runValidation = () => {
  validationErrors.value = []

  // 检查未定义的变量
  const allText = bodyText.value + ' ' + headersText.value + ' ' + expectedText.value
  const varRegex = /\{\{([^}]+)\}\}/g
  let match
  const foundVars = new Set()

  while ((match = varRegex.exec(allText)) !== null) {
    foundVars.add(match[1].trim())
  }

  // 这里可以添加变量定义检查逻辑
  // 目前简单提示
  if (foundVars.size > 0) {
    // 检查变量是否已定义（实际项目中需要查询变量管理模块）
    const undefinedVars = Array.from(foundVars).filter(v => !v.startsWith('global.') && !v.startsWith('context.'))
    if (undefinedVars.length > 0) {
      validationErrors.value.push(`发现未定义的变量: ${undefinedVars.join(', ')}`)
    }
  }

  // 检查JSON格式
  if (headersText.value) {
    try {
      JSON.parse(headersText.value)
    } catch {
      validationErrors.value.push('请求头JSON格式错误')
    }
  }

  if (bodyText.value) {
    try {
      JSON.parse(bodyText.value)
    } catch {
      validationErrors.value.push('请求体JSON格式错误')
    }
  }

  if (expectedText.value) {
    try {
      JSON.parse(expectedText.value)
    } catch {
      validationErrors.value.push('预期响应JSON格式错误')
    }
  }

  // 检查断言规则
  formData.assertion_rules.forEach((rule, index) => {
    if (!rule.field || !rule.field.trim()) {
      validationErrors.value.push(`断言规则 #${index + 1}: 字段路径不能为空`)
    }
  })
}

// 监听表单变化，实时校验
watch([bodyText, headersText, expectedText, () => formData.assertion_rules], () => {
  if (!isView.value) {
    runValidation()
  }
}, { deep: true })

// ========== 智能断言生成面板相关函数 ==========

// 解析 JSON 并提取字段（带类型和值信息）
function parseExpectedJson(text) {
  if (!text || !text.trim()) {
    parsedFieldList.value = []
    selectedFieldPaths.value = new Set()
    jsonError.value = ''
    return
  }

  try {
    const jsonObj = JSON.parse(text)
    if (jsonObj === null || typeof jsonObj !== 'object') {
      parsedFieldList.value = []
      jsonError.value = '预期响应应为 JSON 对象格式'
      return
    }

    const fields = extractJsonFieldsWithValues(jsonObj)
    parsedFieldList.value = fields
    jsonError.value = ''
  } catch (error) {
    parsedFieldList.value = []
    selectedFieldPaths.value = new Set()
    jsonError.value = 'JSON 格式错误，无法解析: ' + error.message
  }
}

// 从 JSON 对象提取字段路径、值和类型（递归，支持数组元素提取）
function extractJsonFieldsWithValues(jsonObj, prefix = '', maxDepth = 5) {
  const fields = []
  if (!jsonObj || typeof jsonObj !== 'object' || maxDepth <= 0) {
    return fields
  }

  Object.keys(jsonObj).forEach(key => {
    const fullPath = prefix ? `${prefix}.${key}` : key
    const value = jsonObj[key]
    const type = getValueType(value)

    const fieldInfo = {
      path: fullPath,
      value: value,
      type: type,
    }

    // 对于数组类型，添加额外元数据
    if (type === 'array') {
      fieldInfo.length = value.length
      if (value.length > 0) {
        fieldInfo.elementType = getValueType(value[0])
      }
    }

    fields.push(fieldInfo)

    // 如果值是对象，递归提取子字段
    if (type === 'object') {
      fields.push(...extractJsonFieldsWithValues(value, fullPath, maxDepth - 1))
    }

    // 如果值是非空数组，取第一个元素作为代表继续提取（如 data.permissions.0.resource）
    if (type === 'array' && value.length > 0 && maxDepth > 1) {
      const firstItem = value[0]
      if (typeof firstItem === 'object' && firstItem !== null && !Array.isArray(firstItem)) {
        const itemPath = `${fullPath}.0`
        // 数组本身也算一个字段，但只展示其包含的对象结构
        fields.push(...extractJsonFieldsWithValues(firstItem, itemPath, maxDepth - 1))
      } else if (typeof firstItem === 'object' && firstItem !== null && Array.isArray(firstItem)) {
        // 嵌套数组，取第一个元素继续
        const nestedPath = `${fullPath}.0`
        fields.push(...extractJsonFieldsWithValues(firstItem, nestedPath, maxDepth - 1))
      }
    }
  })

  return fields
}

// 获取值的类型
function getValueType(value) {
  if (value === null) return 'null'
  if (Array.isArray(value)) return 'array'
  return typeof value
}

// 格式化字段值预览
function formatFieldPreview(value) {
  if (value === null) return 'null'
  if (value === undefined) return 'undefined'
  if (typeof value === 'object') {
    if (Array.isArray(value)) {
      if (value.length === 0) return '[]'
      // 对于原始值数组，显示长度和前几个元素
      const firstElement = value[0]
      if (typeof firstElement !== 'object') {
        const sample = value.slice(0, 3).map(v => String(v)).join(', ')
        return `[${value.length}] ${sample}${value.length > 3 ? '...' : ''}`
      }
      // 对于对象数组，只显示长度
      return `[Array(${value.length})]`
    }
    return '[Object]'
  }
  if (typeof value === 'string') {
    return value.length > 20 ? value.slice(0, 20) + '...' : value
  }
  return String(value)
}

// 获取类型标签的 Element Plus 类型
function getTypeTagType(type) {
  const typeMap = {
    string: '',
    number: 'success',
    boolean: 'warning',
    object: 'info',
    array: '',
    null: 'danger',
  }
  return typeMap[type] || ''
}

// 判断字段是否已生成断言
function isFieldAsserted(fieldPath) {
  if (!formData.assertion_rules || formData.assertion_rules.length === 0) {
    return false
  }
  // 检查断言规则中是否包含该字段
  return formData.assertion_rules.some(rule =>
    rule.field === fieldPath ||
    rule.field === fieldPath.split('.').pop() // 支持匹配简单字段名
  )
}

// JSON 文本变化时自动解析（防抖）
let parseTimer = null
function onExpectedTextChange() {
  if (parseTimer) clearTimeout(parseTimer)
  parseTimer = setTimeout(() => {
    parseExpectedJson(expectedText.value)
  }, 300)
}

// 全选字段
function selectAllFields() {
  selectedFieldPaths.value = new Set(parsedFieldList.value.map(f => f.path))
}

// 反选字段
function deselectAllFields() {
  selectedFieldPaths.value = new Set()
}

// 处理字段复选框
function handleFieldCheckbox(path, checked) {
  const newSet = new Set(selectedFieldPaths.value)
  if (checked) {
    newSet.add(path)
  } else {
    newSet.delete(path)
  }
  selectedFieldPaths.value = newSet
}

// 从勾选的字段生成断言规则（仅处理 extract_only 类型字段）
function generateRulesFromFields() {
  const existingFields = new Set(
    formData.assertion_rules
      .filter(r => r.field && r.field.trim())
      .map(r => r.field)
  )

  let addedCount = 0

  parsedFieldList.value.forEach(field => {
    // 只处理标记为 extract_only 的字段（可提取变量字段）
    if (field._type !== 'extract_only' && field._type) return

    if (!selectedFieldPaths.value.has(field.path)) return

    // 静默跳过已存在的字段，不提示（互斥逻辑）
    if (existingFields.has(field.path)) {
      return
    }

    // 根据类型确定默认运算符和预期值
    let operator = '=='
    let value = field.value
    let showValue = true

    if (field.type === 'object' || field.type === 'array') {
      operator = 'json_contains'
      showValue = true
    } else if (field.type === 'null') {
      operator = 'is_empty'
      showValue = false
      value = ''
    } else if (field.type === 'boolean') {
      operator = '=='
      showValue = true
    }

    formData.assertion_rules.push({
      id: generateRuleId(),
      field: field.path,
      operator: operator,
      value: typeof value === 'object' ? JSON.stringify(value) : value,
      _showValue: showValue,
      _aiGenerated: false, // 手动生成的断言
      _category: 'optional', // 手动添加的归为可选
      _enabled: true,
      _type: 'assertion_only', // 转换为断言类型
    })

    addedCount++
  })

  // 清除已选字段
  selectedFieldPaths.value = new Set()

  if (addedCount > 0) {
    ElMessage.success(`已添加 ${addedCount} 条断言规则`)
  }
  // 不再显示"已跳过"提示
}

// ========== 断言规则核心函数 ==========

// 生成唯一ID
let ruleIdCounter = 0
function generateRuleId() {
  return `rule_${Date.now()}_${++ruleIdCounter}`
}

// 获取运算符显示文本
function getOperatorDisplayText(operator) {
  const op = ASSERTION_OPERATORS.find(o => o.value === operator)
  return op ? op.label.split(' ')[0] : operator
}

// 格式化预期值显示
function formatValueDisplay(value, operator) {
  if (value === null || value === undefined || value === '') {
    return 'null'
  }
  if (typeof value === 'string') {
    if (operator === 'matches_regex') {
      return `/${value}/`
    }
    return `"${value}"`
  }
  if (typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value)
}

// 获取预期值输入框占位符
function getValuePlaceholder(operator) {
  switch (operator) {
    case 'matches_regex':
      return '正则表达式，如 ^\\d+$'
    case 'json_contains':
      return '{"key": "value"}'
    case 'contains':
      return '包含的文本'
    default:
      return '预期值'
  }
}

// 判断预期值是否为空（用于红色边框提示）
function isValueMissing(rule) {
  if (rule._showValue === false) return false
  const op = ASSERTION_OPERATORS.find(o => o.value === rule.operator)
  if (!op || !op.needsValue) return false
  return !rule.value && rule.value !== 0 && rule.value !== false
}

// 运算符切换时控制预期值显隐
function handleOperatorChange(rule) {
  const op = ASSERTION_OPERATORS.find(o => o.value === rule.operator)
  rule._showValue = op ? op.needsValue : true
  if (!rule._showValue) {
    rule.value = ''
  }
}

// 字段选择时智能填充预期值
function handleFieldSelect(rule) {
  if (!rule.field) return

  // 尝试从解析的字段列表中找到匹配的值
  const matchedField = parsedFieldList.value.find(f => f.path === rule.field)
  if (matchedField && matchedField.value !== undefined && matchedField.value !== null) {
    const type = matchedField.type

    // 自动设置运算符和预期值
    if (type === 'object' || type === 'array') {
      rule.operator = 'json_contains'
      rule.value = JSON.stringify(matchedField.value)
      rule._showValue = true
    } else if (type === 'null') {
      rule.operator = 'is_empty'
      rule.value = ''
      rule._showValue = false
    } else {
      rule.operator = '=='
      rule.value = typeof matchedField.value === 'object'
        ? JSON.stringify(matchedField.value)
        : matchedField.value
      rule._showValue = true
    }
  }
}

// 变量提取：字段选择时智能填充变量值
function handleExtractFieldSelect(rule) {
  if (!rule.field_path) return

  // 尝试从解析的字段列表中找到匹配的值
  const matchedField = parsedFieldList.value.find(f => f.path === rule.field_path)
  if (matchedField && matchedField.value !== undefined && matchedField.value !== null) {
    const type = matchedField.type

    // 自动填充变量值
    if (type === 'object' || type === 'array') {
      rule.var_value = JSON.stringify(matchedField.value)
    } else {
      rule.var_value = typeof matchedField.value === 'object'
        ? JSON.stringify(matchedField.value)
        : String(matchedField.value)
    }
  }
}

// 添加规则
function addRule() {
  formData.assertion_rules.push({
    id: generateRuleId(),
    field: '',
    operator: '==',
    value: '',
    _showValue: true,
  })
}

// 监听字段变化，检测HTTP状态码重复
function watchFieldChange(rule) {
}

// 删除规则
function removeRule(index) {
  formData.assertion_rules.splice(index, 1)
}

// 初始化断言规则（从后端数据加载）
function initAssertionRules(rawRules) {
  if (!rawRules || !Array.isArray(rawRules) || rawRules.length === 0) {
    return []
  }

  return rawRules.map(rule => {
    const op = ASSERTION_OPERATORS.find(o => o.value === rule.operator)
    return {
      id: generateRuleId(),
      field: rule.field || '',
      operator: rule.operator || '==',
      value: rule.value ?? '',
      _showValue: op ? op.needsValue : true,
    }
  })
}

// 添加提取规则
function addExtractRule() {
  formData.extract_rules.push({
    id: generateRuleId(),
    field_path: '',
    var_name: '',
    var_value: '',
    var_type: '',  // 新增：变量类型（global 或 context）
    extract_type: 'json_path',
    _testing: false,
    _extractValue: undefined,
    _extractSuccess: false,
  })
}

// 添加全局变量
function addGlobalVar() {
  formData.global_vars.push({ name: '', value: '' })
}

// 删除全局变量
function removeGlobalVar(index) {
  formData.global_vars.splice(index, 1)
}

// 添加上下文变量
function addContextVar() {
  formData.context_vars.push({ name: '', value: '' })
}

// 删除上下文变量
function removeContextVar(index) {
  formData.context_vars.splice(index, 1)
}

// 删除提取规则
function removeExtractRule(index) {
  formData.extract_rules.splice(index, 1)
}

// 初始化提取规则（从后端数据加载）
function initExtractRules(rawRules) {
  if (!rawRules || !Array.isArray(rawRules) || rawRules.length === 0) {
    return []
  }

  return rawRules.map(rule => ({
    id: generateRuleId(),
    field_path: rule.field_path || '',
    var_name: rule.var_name || '',
    var_value: rule.var_value || '',
    var_type: rule.var_type || '',  // 新增：变量类型
    extract_type: rule.extract_type || 'json_path',
    _testing: false,
    _extractValue: undefined,
    _extractSuccess: false,
  }))
}

// 回填提取变量值到所有规则行
function fillExtractValues(extracted) {
  formData.extract_rules.forEach(rule => {
    if (!rule.var_name) return
    const value = extracted[rule.var_name]
    if (value !== undefined) {
      rule._extractValue = value
      rule._extractSuccess = true
    } else {
      rule._extractValue = '路径无效'
      rule._extractSuccess = false
    }
  })
}

// 测试单个提取规则
async function testExtractRule(index) {
  const rule = formData.extract_rules[index]
  if (!rule.field_path || !rule.var_name) {
    ElMessage.warning('请填写字段路径和变量名')
    return
  }
  rule._testing = true
  try {
    const globalVars = {}
    globalVariables.value.forEach(v => { globalVars[v.name] = v.value })
    const response = await testcaseAPI.debug(formData.id, {
      global_variables: globalVars,
    })
    const results = response.execution_results || []
    const result = results[0]
    if (result) {
      const extracted = result.extracted_vars || {}
      // 回填所有规则的变量值
      fillExtractValues(extracted)
      // 同时更新全局变量池和提取变量
      extractedVariables.value = []
      Object.entries(extracted).forEach(([name, val]) => {
        const existing = globalVariables.value.find(v => v.name === name)
        if (existing) {
          existing.value = val
        } else {
          globalVariables.value.push({ name, value: val })
        }
        extractedVariables.value.push({ name, source: result.title || '响应提取', value: val })
      })
      lastExecutionTime.value = new Date()
      // 若弹窗已打开，自动刷新提取的变量Tab
      if (variablePreviewDialogVisible.value) {
        activeVariableTab.value = 'extracted'
      }
    } else {
      rule._extractValue = '未匹配'
      rule._extractSuccess = false
    }
  } catch (error) {
    rule._extractValue = error.message || '测试失败'
    rule._extractSuccess = false
  } finally {
    rule._testing = false
  }
}

// 重新执行并刷新变量
async function reExecuteAndRefreshVars() {
  if (!formData.id) {
    ElMessage.warning('请先保存用例')
    return
  }
  reExecuting.value = true
  try {
    await oneClickDebug()
    activeVariableTab.value = 'extracted'
  } finally {
    reExecuting.value = false
  }
}

// 跳转到全局变量设置
function goToGlobalVarSettings() {
  ElMessage.info('全局变量设置功能开发中')
}

// 打开变量预览弹窗
function openVariablePreview() {
  variablePreviewDialogVisible.value = true
  activeVariableTab.value = 'extracted'
}

// ========== 数据加载/提交 ==========

// 加载测试用例
const loadTestCases = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      search: searchForm.search || undefined,
      status: searchForm.status || undefined,
      priority: searchForm.priority || undefined,
      method: searchForm.method || undefined,
    }
    const response = await testcaseAPI.list(params)
    testCases.value = response.results || response
    pagination.total = response.count || response.length
  } catch (error) {
    console.error('Load test cases error:', error)
  } finally {
    loading.value = false
  }
}

// 重置搜索
const resetSearch = () => {
  searchForm.search = ''
  searchForm.status = ''
  searchForm.priority = ''
  searchForm.method = ''
  pagination.page = 1
  loadTestCases()
}

// 解析JSON工具函数
const parseJSON = (str, defaultValue = {}) => {
  if (!str) return defaultValue
  try {
    return JSON.parse(str)
  } catch {
    return defaultValue
  }
}

// 安全转换JSON为字符串（空值返回空字符串以显示placeholder提示）
// 安全转换JSON为字符串（空值、空对象、数字0返回空字符串以显示placeholder提示）
const parseToJSON = (val) => {
  if (!val && val !== 0) return ''
  if (val === 0) return ''
  if (typeof val === 'string') return val
  // 处理空对象和空数组，返回空字符串
  if (typeof val === 'object') {
    if (Array.isArray(val) && val.length === 0) return ''
    if (!Array.isArray(val) && Object.keys(val).length === 0) return ''
  }
  return JSON.stringify(val, null, 2)
}

// 显示创建对话框
const showCreateDialog = () => {
  isEdit.value = false
  isView.value = false
  resetForm()
  dialogVisible.value = true
  formData.global_vars = []
  formData.context_vars = []
}

// 显示编辑对话框
const showEditDialog = (row) => {
  isEdit.value = true
  isView.value = false
  Object.assign(formData, row)
  // 初始化全局变量
  formData.global_vars = row.global_vars ? row.global_vars.map(v => ({ ...v })) : []
  // 初始化上下文变量
  formData.context_vars = row.context_vars ? row.context_vars.map(v => ({ ...v })) : []

  // 确保 method 有默认值（防止后端返回 null/undefined）
  if (!formData.method) {
    formData.method = 'GET'
  }

  headersText.value = parseToJSON(row.headers)
  bodyText.value = parseToJSON(row.request_body)
  expectedText.value = parseToJSON(row.expected_response)
  tagsText.value = (row.tags || []).join(', ')

  // 初始化断言规则
  formData.assertion_rules = initAssertionRules(row.assertion_rules)
  // 初始化提取规则
  formData.extract_rules = initExtractRules(row.extract_rules)

  // 解析预期响应JSON以填充字段列表
  jsonError.value = ''
  parsedFieldList.value = []
  selectedFieldPaths.value = new Set()
  aiParsedFields.value.clear() // 清除之前的AI解析标记
  try {
    const jsonObj = typeof row.expected_response === 'string'
      ? JSON.parse(row.expected_response)
      : row.expected_response
    if (jsonObj && typeof jsonObj === 'object' && expectedText.value.trim()) {
      parsedFieldList.value = extractJsonFieldsWithValues(jsonObj)
    }
  } catch {
    // 忽略解析错误
  }

  dialogVisible.value = true
}

// 显示查看对话框(只读模式)
const showViewDialog = (row) => {
  isEdit.value = false
  isView.value = true
  Object.assign(formData, row)

  // 确保 method 有默认值（防止后端返回 null/undefined）
  if (!formData.method) {
    formData.method = 'GET'
  }

  headersText.value = parseToJSON(row.headers)
  bodyText.value = parseToJSON(row.request_body)
  expectedText.value = parseToJSON(row.expected_response)
  tagsText.value = (row.tags || []).join(', ')

  // 查看模式下也加载规则
  formData.assertion_rules = initAssertionRules(row.assertion_rules)
  formData.extract_rules = initExtractRules(row.extract_rules)

  dialogVisible.value = true
}

// 复制测试用例
const copyTestCase = (row) => {
  isEdit.value = false
  isView.value = false
  Object.assign(formData, row)
  formData.title = `${row.title} (副本)`
  delete formData.id

  // 确保 method 有默认值（防止后端返回 null/undefined）
  if (!formData.method) {
    formData.method = 'GET'
  }

  headersText.value = parseToJSON(row.headers)
  bodyText.value = parseToJSON(row.request_body)
  expectedText.value = parseToJSON(row.expected_response)
  tagsText.value = (row.tags || []).join(', ')

  // 初始化断言规则
  formData.assertion_rules = initAssertionRules(row.assertion_rules)
  formData.extract_rules = initExtractRules(row.extract_rules)

  jsonError.value = ''
  parsedFieldList.value = []
  selectedFieldPaths.value = new Set()
  try {
    const jsonObj = typeof row.expected_response === 'string'
      ? JSON.parse(row.expected_response)
      : row.expected_response
    if (jsonObj && typeof jsonObj === 'object' && expectedText.value.trim()) {
      parsedFieldList.value = extractJsonFieldsWithValues(jsonObj)
    }
  } catch {
    // 忽略解析错误
  }

  dialogVisible.value = true
}

// 重置表单
const resetForm = () => {
  Object.assign(formData, {
    title: '',
    description: '',
    api_endpoint: '',
    method: 'GET',
    headers: {},
    request_body: {},
    expected_response: {},
    assertion_rules: [],
    extract_rules: [],
    assertions: '',
    priority: 'P2',
    status: 'active',
    tags: [],
  })
  headersText.value = ''
  bodyText.value = ''
  expectedText.value = ''
  tagsText.value = ''
  jsonError.value = ''
  parsedFieldList.value = []
  selectedFieldPaths.value = new Set()
  aiParsedFields.value.clear() // 清除AI解析标记
  ruleIdCounter = 0
}

// 提交表单
const submitForm = async () => {
  if (!formRef.value) return

  // 先校验变量提取规则的完整性
  const incompleteExtractRules = formData.extract_rules.filter(rule => {
    const hasFieldPath = rule.field_path && rule.field_path.trim() !== ''
    const hasVarName = rule.var_name && rule.var_name.trim() !== ''
    const hasVarValue = rule.var_value && rule.var_value.trim() !== ''
    // 校验全局变量：如果有填写了部分字段，必须全部填写
    const incompleteGlobalVars = formData.global_vars.filter(v => {
      const hasName = v.name && v.name.trim() !== ''
      const hasValue = v.value && v.value.trim() !== ''
      return (hasName || hasValue) && !(hasName && hasValue)
    })

    if (incompleteGlobalVars.length > 0) {
      showError('全局变量：变量名和变量值必须全部填写')
      return
    }

    // 校验上下文变量：如果有填写了部分字段，必须全部填写
    const incompleteContextVars = formData.context_vars.filter(v => {
      const hasName = v.name && v.name.trim() !== ''
      const hasValue = v.value && v.value.trim() !== ''
      return (hasName || hasValue) && !(hasName && hasValue)
    })

    if (incompleteContextVars.length > 0) {
      showError('上下文变量：变量名和变量值必须全部填写')
      return
    }


    // 如果填写了任意一个字段，但其他字段为空，则视为不完整
    return (hasFieldPath || hasVarName || hasVarValue) &&
      !(hasFieldPath && hasVarName && hasVarValue)
  })

  if (incompleteExtractRules.length > 0) {
    showError('变量提取规则：字段路径、变量名、变量值必须全部填写')
    return
  }

  await formRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        // 解析JSON字段
        formData.headers = parseJSON(headersText.value, {})
        formData.request_body = parseJSON(bodyText.value, {})
        formData.expected_response = parseJSON(expectedText.value, {})
        formData.tags = tagsText.value.split(',').map(t => t.trim()).filter(t => t)

        // 过滤无效断言规则
        const validRules = formData.assertion_rules
          .filter(rule => rule.field && rule.field.trim() !== '')
          .map(rule => ({
            field: rule.field,
            operator: rule.operator,
            value: rule.value,
          }))

        formData.assertion_rules = validRules

        // 过滤完全空的提取规则（三个字段都为空）
        const validExtractRules = formData.extract_rules
          .filter(rule => rule.field_path && rule.field_path.trim() !== '' && rule.var_name && rule.var_name.trim() !== '')
          .map(rule => ({
            field_path: rule.field_path,
            var_name: rule.var_name,
            var_value: rule.var_value || '',
            var_type: rule.var_type || '',  // 新增：变量类型
            var_type: rule.var_type || '',  // 新增：变量类型
            extract_type: rule.extract_type || 'json_path',
          }))

        formData.extract_rules = validExtractRules

        // 根据 var_type 自动填充 global_vars 和 context_vars
        formData.global_vars = validExtractRules
          .filter(rule => rule.var_type === 'global')
          .map(rule => ({ name: rule.var_name, value: rule.var_value }))

        formData.context_vars = validExtractRules
          .filter(rule => rule.var_type === 'context')
          .map(rule => ({ name: rule.var_name, value: rule.var_value }))

        // 根据 var_type 自动填充 global_vars 和 context_vars
        formData.global_vars = validExtractRules
          .filter(rule => rule.var_type === 'global')
          .map(rule => ({ name: rule.var_name, value: rule.var_value }))

        formData.context_vars = validExtractRules
          .filter(rule => rule.var_type === 'context')
          .map(rule => ({ name: rule.var_name, value: rule.var_value }))

        // 生成断言摘要（用于后端 assertions 字段存储）
        formData.assertions = validRules.map((rule, index) => {
          const op = ASSERTION_OPERATORS.find(o => o.value === rule.operator)
          const needsValue = op ? op.needsValue : true
          if (!needsValue) {
            return `${index + 1}. ${rule.field} ${op ? op.label.split(' ')[0] : rule.operator}`
          }
          const valueDisplay = formatValueDisplay(rule.value, rule.operator)
          return `${index + 1}. ${rule.field} ${op ? op.label.split(' ')[0] : rule.operator} ${valueDisplay}`
        }).join('\n')

        if (isEdit.value) {
          await testcaseAPI.update(formData.id, formData)
          showSuccess('更新成功')
        } else {
          await testcaseAPI.create(formData)
          showSuccess('创建成功')
        }
        dialogVisible.value = false
        loadTestCases()
      } catch (error) {
        console.error('Submit error:', error)
      } finally {
        submitting.value = false
      }
    }
  })
}

// 删除测试用例
const deleteTestCase = async (id) => {
  try {
    await showDeleteConfirm('确定要删除这个测试用例吗？此操作不可恢复')
    await testcaseAPI.delete(id)
    showSuccess('删除成功')
    loadTestCases()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Delete error:', error)
    }
  }
}

// 处理表格选择变化
const handleSelectionChange = (selection) => {
  selectedRows.value = selection
}

// 批量删除
const batchDelete = async () => {
  if (selectedRows.value.length === 0) return

  try {
    await showDeleteConfirm(`确定要删除选中的 ${selectedRows.value.length} 个测试用例吗？此操作不可恢复`)

    const deletePromises = selectedRows.value.map(row => testcaseAPI.delete(row.id))
    await Promise.all(deletePromises)

    showSuccess(`成功删除 ${selectedRows.value.length} 个测试用例`)
    selectedRows.value = []
    loadTestCases()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Batch delete error:', error)
    }
  }
}

// 单条执行测试用例
const executeTestCase = async (row) => {
  if (row.status === 'draft') {
    ElMessage.warning('草稿状态用例不允许执行，请先激活')
    return
  }
  try {
    ElMessage.info(`正在执行测试用例: ${row.title}`)

    const globalVars = {}
    globalVariables.value.forEach(v => {
      globalVars[v.name] = v.value
    })
    const response = await executionAPI.execute({
      test_case_ids: [row.id],
      trigger_type: 'debug',
      global_variables: globalVars,
    })

    // 更新提取的变量
    const results = response.execution_results || []
    results.forEach(r => {
      const extracted = r.extracted_vars || {}
      Object.entries(extracted).forEach(([name, value]) => {
        const existing = globalVariables.value.find(v => v.name === name)
        if (existing) {
          existing.value = value
        } else {
          globalVariables.value.push({ name, value })
        }
      })
    })

    showSuccess(`执行完成: ${response.passed_count || 0} 通过, ${response.failed_count || 0} 失败`)
    lastResult.value = {
      id: response.id,
      name: row.title,
      passed: response.passed_count || 0,
      failed: response.failed_count || 0,
      skipped: response.skipped_count || 0,
      results: response.results || [],
      time: new Date()
    }
    resultPanelVisible.value = true
  } catch (error) {
    console.error('Execute error:', error)
    ElMessage.error('执行失败: ' + (error.message || '未知错误'))
  }
}

// 批量执行（调试模式，不进入主历史列表）
const batchExecute = async () => {
  if (selectedRows.value.length === 0) return

  const draftRows = selectedRows.value.filter(row => row.status === 'draft')
  if (draftRows.length > 0) {
    ElMessage.warning(`选中的用例中有 ${draftRows.length} 个草稿状态，不允许执行，请先激活`)
    return
  }

  try {
    const testIds = selectedRows.value.map(row => row.id)

    ElMessage.info(`正在调试执行 ${testIds.length} 个测试用例...`)

    const globalVars = {}
    globalVariables.value.forEach(v => {
      globalVars[v.name] = v.value
    })
    const response = await executionAPI.execute({
      test_case_ids: testIds,
      trigger_type: 'debug',
      global_variables: globalVars,
    })

    // 更新提取的变量
    const results = response.execution_results || []
    results.forEach(r => {
      const extracted = r.extracted_vars || {}
      Object.entries(extracted).forEach(([name, value]) => {
        const existing = globalVariables.value.find(v => v.name === name)
        if (existing) {
          existing.value = value
        } else {
          globalVariables.value.push({ name, value })
        }
      })
    })

    showSuccess(`调试执行完成: ${response.passed_count || 0} 通过, ${response.failed_count || 0} 失败`)
    lastResult.value = {
      id: response.id,
      name: `批量执行 (${selectedRows.value.length} 个用例)`,
      passed: response.passed_count || 0,
      failed: response.failed_count || 0,
      skipped: response.skipped_count || 0,
      results: response.results || [],
      time: new Date()
    }
    resultPanelVisible.value = true
  } catch (error) {
    console.error('Batch execute error:', error)
    ElMessage.error('执行失败: ' + (error.message || '未知错误'))
  }
}

// 显示批量加入测试套件对话框
const showBatchAddToSuiteDialog = async () => {
  if (selectedRows.value.length === 0) return

  try {
    // 加载测试套件列表
    const response = await testsuiteAPI.list({ page_size: 100 })
    testSuites.value = response.results || response
    batchAddToSuiteDialogVisible.value = true
  } catch (error) {
    console.error('Load test suites error:', error)
    ElMessage.error('加载测试套件列表失败')
  }
}

// 确认批量加入测试套件
const confirmBatchAddToSuite = async () => {
  if (!selectedSuiteId.value) {
    ElMessage.warning('请选择测试套件')
    return
  }

  batchAddingToSuite.value = true
  try {
    const testIds = selectedRows.value.map(row => row.id)
    await testsuiteAPI.addTestCases(selectedSuiteId.value, testIds)
    showSuccess(`成功将 ${testIds.length} 个用例加入测试套件`)
    batchAddToSuiteDialogVisible.value = false
    selectedSuiteId.value = null
  } catch (error) {
    console.error('Batch add to suite error:', error)
    ElMessage.error('加入测试套件失败: ' + (error.message || '未知错误'))
  } finally {
    batchAddingToSuite.value = false
  }
}

// 辅助函数
const getMethodType = (method) => {
  const types = { GET: '', POST: 'success', PUT: 'warning', DELETE: 'danger', PATCH: 'info' }
  return types[method] || ''
}

const getPriorityType = (priority) => {
  const types = { P0: 'danger', P1: 'warning', P2: '', P3: 'info' }
  return types[priority] || ''
}

const getStatusType = (status) => {
  const types = { draft: 'info', active: 'success', inactive: '' }
  return types[status] || ''
}

const getStatusText = (status) => {
  const texts = { draft: '草稿', active: '激活', inactive: '停用' }
  return texts[status] || status
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 请求方法变化处理
const onMethodChange = () => {
  // GET请求自动清空请求体
  if ((formData.method || 'GET') === 'GET') {
    bodyText.value = ''
  }
}

// API端点变化处理（可用于AI解析触发）
const onApiEndpointChange = () => {
  // 可以在这里添加自动解析逻辑
}

// 高亮变量（用于实时更新）
const highlightVariablesInBody = () => {
  // 已在computed中实现，这里保留空函数供未来扩展
}

onMounted(() => {
  loadTestCases()
})
</script>

<style scoped>
/* ========== 编辑弹窗空间优化 ========== */

/* 一、弹窗整体 */
.refined-edit-dialog :deep(.el-dialog) {
  width: 960px !important;
  max-height: 92vh;
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  margin: 4vh auto !important;
  overflow: hidden;
}

.refined-edit-dialog :deep(.el-dialog__header) {
  padding: 12px 20px;
  border-bottom: 1px solid #e4e7ed;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.refined-edit-dialog :deep(.el-dialog__header .el-dialog__title) {
  color: #fff;
  font-weight: 600;
  font-size: 16px;
}

.refined-edit-dialog :deep(.el-dialog__headerbtn .el-dialog__close) {
  color: #fff;
}

.refined-edit-dialog :deep(.el-dialog__body) {
  max-height: calc(92vh - 96px);
  overflow-y: auto;
  padding: 4px 0;
  background-color: #f5f7fa;
}

.refined-edit-dialog :deep(.el-dialog__footer) {
  padding: 10px 20px;
  border-top: 1px solid #e4e7ed;
  background: #fff;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.refined-edit-dialog :deep(.el-dialog__footer .el-button) {
  width: 90px;
  height: 34px;
  border-radius: 4px;
  font-weight: 500;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.refined-edit-dialog :deep(.el-dialog__footer .el-button--primary) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
}

/* 表单基础 */
.refined-edit-dialog :deep(.el-form-item) {
  margin-bottom: 8px !important;
}

.refined-edit-dialog :deep(.el-form-item__label) {
  font-weight: 500;
  color: #606266;
  font-size: 13px;
  padding-right: 8px;
  line-height: 32px;
}

/* 模块标题紫色竖线 */
.module-title-item :deep(.el-form-item__label) {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  border-left: 3px solid #7B2FF7;
  padding-left: 8px;
  margin-left: 0;
  margin-bottom: 4px !important;
  line-height: 28px;
}

/* 控件高度统一32px */
.refined-edit-dialog :deep(.el-input__inner),
.refined-edit-dialog :deep(.el-select .el-input__inner) {
  height: 32px !important;
  line-height: 32px !important;
  padding: 0 10px;
  font-size: 13px;
  border-radius: 4px;
}

.refined-edit-dialog :deep(.el-input__wrapper) {
  border-radius: 4px;
  transition: box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.refined-edit-dialog :deep(.el-input__wrapper.is-focus),
.refined-edit-dialog :deep(.el-select .el-input.is-focus .el-input__wrapper) {
  box-shadow: 0 0 0 1px #7B2FF7 inset !important;
}

/* 文本域 - 基于容器选择器，[rows]属性对Element Plus textarea不可靠 */
.refined-edit-dialog :deep(.el-textarea__inner) {
  font-family: 'Menlo', 'Monaco', 'Consolas', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  padding: 8px 10px;
  border-radius: 4px;
}

/* textarea 字体等基础样式保留，高度由 autosize 控制 */

/* 二、顶部AI工具栏 */
.quick-actions-bar {
  margin: 0 16px 12px 16px;
  padding: 8px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 6px;
}

.quick-actions-bar .el-button-group {
  display: flex;
  gap: 6px;
}

.quick-actions-bar .ghost-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: #fff;
  font-weight: 500;
  font-size: 12px;
  padding: 5px 10px;
  border-radius: 4px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.quick-actions-bar .ghost-btn:hover {
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.6);
}

.ai-status-tag {
  background-color: #e6f7e6 !important;
  border-color: #b7eb8f !important;
  color: #52c41a !important;
  border-radius: 12px !important;
  padding: 0 8px !important;
  height: 24px !important;
  line-height: 22px !important;
  font-size: 12px !important;
  font-weight: 500;
}

/* 三、模块卡片 */
.section-basic-config,
.section-assertion-response,
.section-extract-submit {
  margin: 0 12px 8px 12px;
  padding: 10px;
  background: #fff;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
}

/* 四、断言规则 - 紧凑扁平 */
.assertion-rules-area {
  width: 100%;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #fff;
  overflow: hidden;
}

.rule-header {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 6px 10px;
  font-weight: 600;
  font-size: 11px;
  color: #909399;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  min-height: 28px;
}

.rule-body {
  overflow-y: auto;
  max-height: 300px;
}

/* 断言规则空状态引导提示 */
.rule-empty-hint {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 16px 14px;
  background: #f0f7ff;
  border-bottom: 1px solid #d9ecff;
}

.empty-hint-icon {
  font-size: 20px;
  color: #409eff;
  flex-shrink: 0;
  margin-top: 2px;
}

.empty-hint-text {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

.empty-hint-text p {
  margin: 0 0 4px 0;
}

.empty-hint-text p:last-child {
  margin-bottom: 0;
  font-size: 12px;
  color: #909399;
}

.rule-row {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 0 10px;
  min-height: 32px;
  border-bottom: 1px solid #f0f0f0;
  background: #fff;
  transition: background-color 0.15s ease;
  position: relative;
}

.rule-row:nth-child(even) {
  background: #fafafa;
}

.rule-row:hover {
  background: #f5f7fa;
}

.rule-row:last-child {
  border-bottom: none;
}

.field-col {
  flex: 1;
  min-width: 0;
}

.op-col {
  flex: 1;
  min-width: 0;
}

.value-col {
  flex: 1;
  min-width: 0;
}

.action-col {
  width: 24px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.no-value-hint {
  flex: 1;
  min-width: 0;
  color: #c0c4cc;
  font-size: 12px;
  padding: 0 8px;
  line-height: 36px;
}

/* AI 标识徽章 */
.ai-badge {
  font-size: 9px;
  color: #fff;
  background: #7B2FF7;
  padding: 1px 4px;
  border-radius: 3px;
  font-weight: 700;
  flex-shrink: 0;
  line-height: 14px;
  letter-spacing: 0.3px;
}

/* 删除按钮 - 始终红色 */
.delete-rule-btn {
  width: 16px !important;
  height: 16px !important;
  padding: 0 !important;
  display: inline-flex !important;
  align-items: center;
  justify-content: center;
  color: #f56c6c !important;
  transition: all 0.15s ease;
}

.delete-rule-btn:hover {
  color: #ff4d4f !important;
}

/* 添加规则按钮 - 虚线行 */
.add-rule-btn {
  width: 100%;
  height: 28px;
  margin-top: 0;
  border: none !important;
  border-top: 1px dashed #7B2FF7 !important;
  color: #7B2FF7 !important;
  background: transparent !important;
  font-size: 12px;
  font-weight: 600;
  border-radius: 0 !important;
  transition: all 0.15s ease;
}

.add-rule-btn:hover {
  color: #5a1ed4 !important;
  background: rgba(123, 47, 247, 0.06) !important;
}

/* 断言类别色条 */
.assertion-rule-core {
  border-left: 3px solid #52c41a;
  padding-left: 7px;
}

.assertion-rule-optional {
  border-left: 3px solid #fa8c16;
  padding-left: 7px;
}

.assertion-rule-ai-generated {
  border-left: 3px solid #7B2FF7;
  padding-left: 7px;
}

.assertion-rule-disabled {
  opacity: 0.45;
}

/* 五、预期响应区 */
.expected-response-form-item {
  border-top: 1px solid #e4e7ed;
  padding-top: 8px;
  margin-top: 0 !important;
  margin-bottom: 0 !important;
}

.expected-response-area {
  width: 100%;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
  background: #fff;
}

.expected-response-toolbar {
  display: flex;
  justify-content: flex-end;
  padding: 4px 8px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  min-height: 28px;
}

.expected-response-toolbar .el-button {
  width: 24px;
  height: 24px;
  padding: 0;
  color: #8c8c8c;
  transition: all 0.15s ease;
}

.expected-response-toolbar .el-button:hover {
  color: #667eea;
  background: rgba(102, 126, 234, 0.08);
}

.expected-response-area :deep(.el-textarea__inner) {
  background: #f8f9fa;
  font-family: 'Menlo', 'Monaco', 'Consolas', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  border: none;
  padding: 10px;
  border-radius: 0;
}

/* 六、可提取字段 - 紧凑 */
.field-list-area {
  width: 100%;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #fff;
  overflow: hidden;
}

.field-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  min-height: 28px;
}

.field-list-title {
  font-weight: 600;
  font-size: 12px;
  color: #606266;
}

.field-list-actions {
  display: flex;
  gap: 4px;
  align-items: center;
  flex-wrap: nowrap;
}

.field-list-actions .el-button {
  padding: 2px 8px;
  font-size: 12px;
  height: 24px;
  border-radius: 4px;
  transition: all 0.15s ease;
}

.field-list-body {
  overflow-y: auto;
  max-height: 300px;
}

.field-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  min-height: 28px;
  border-bottom: 1px solid #f0f0f0;
  background: #fff;
  transition: background-color 0.15s ease;
}

.field-item:nth-child(even) {
  background: #fafafa;
}

.field-item:hover {
  background: #f5f7fa;
}

.field-item:last-child {
  border-bottom: none;
}

.field-item-selected {
  background: #e6f7ff !important;
}

.field-path {
  flex: 1;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.field-value-preview {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  color: #8c8c8c;
}

.field-asserted-tag {
  flex-shrink: 0;
}

/* 类型标签 - pill */
.field-type-tag {
  flex-shrink: 0;
  border-radius: 4px !important;
  padding: 1px 6px !important;
  height: 18px !important;
  line-height: 16px !important;
  font-size: 11px !important;
  font-weight: 500 !important;
  border: none !important;
}

.type-tag--string,
.type-tag--str {
  background: #e6f4ff !important;
  color: #1890ff !important;
}

.type-tag--number,
.type-tag--int,
.type-tag--float {
  background: #f6ffed !important;
  color: #52c41a !important;
}

.type-tag--boolean,
.type-tag--bool {
  background: #fff2e8 !important;
  color: #fa8c16 !important;
}

.type-tag--null,
.type-tag--NoneType {
  background: #f5f5f5 !important;
  color: #8c8c8c !important;
}

.type-tag--object {
  background: #f0f5ff !important;
  color: #2f54eb !important;
}

.type-tag--array {
  background: #f9f0ff !important;
  color: #722ed1 !important;
}

/* 七、解析预览面板 */
.parse-preview-panel {
  margin: 0 12px 8px 12px;
  padding: 8px 10px;
  background: #f5f7fa;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
}

.parse-preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.parse-preview-title {
  font-weight: 600;
  font-size: 13px;
  color: #303133;
}

.parse-preview-actions {
  display: flex;
  gap: 6px;
}

.parse-preview-actions .el-button {
  font-size: 11px;
  padding: 3px 8px;
  height: 24px;
}

.parse-preview-content {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 8px;
}

.preview-item {
  background: #fff;
  padding: 6px 10px;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
}

.preview-item-label {
  font-size: 11px;
  color: #8c8c8c;
  margin-bottom: 2px;
}

.preview-item-value {
  font-size: 12px;
  color: #303133;
  font-weight: 500;
}

.method-get {
  color: #67c23a;
}

.method-post {
  color: #409eff;
}

.method-put {
  color: #e6a23c;
}

.method-delete {
  color: #f56c6c;
}

.method-patch {
  color: #8c8c8c;
}

/* AI字段高亮 */
.ai-generated-field :deep(.el-input__inner),
.ai-generated-field :deep(.el-textarea__inner) {
  border-color: #67c23a !important;
  background-color: #f0fff4 !important;
}

/* 表单校验 */
.validation-errors {
  margin: 0 16px 12px 16px;
}

/* 滚动条 */
.assertion-rules-area::-webkit-scrollbar,
.expected-response-area::-webkit-scrollbar,
.field-list-area::-webkit-scrollbar,
.refined-edit-dialog :deep(.el-dialog__body)::-webkit-scrollbar {
  width: 4px;
}

.assertion-rules-area::-webkit-scrollbar-thumb,
.expected-response-area::-webkit-scrollbar-thumb,
.field-list-area::-webkit-scrollbar-thumb,
.refined-edit-dialog :deep(.el-dialog__body)::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 2px;
}

/* 页面其他样式 */
.testcase-container {
  padding: 0;
}

.search-form {
  margin-bottom: 16px;
}

.batch-actions {
  margin-bottom: 12px;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
  display: flex;
  align-items: center;
}

.api-endpoint-text {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  color: #303133;
}

.no-execution-text {
  color: #c0c4cc;
  font-size: 12px;
}

.request-body-wrapper {
  position: relative;
  width: 100%;
}

.variable-input-wrapper {
  position: relative;
  width: 100%;
}

.variable-highlight-preview {
  margin-top: 6px;
  padding: 8px;
  background: #f8f9fa;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 100px;
  overflow-y: auto;
}

.variable-highlight-bar {
  margin-top: 4px;
  padding: 4px 8px;
  background: #f8f9fa;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 11px;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.var-highlight {
  padding: 1px 4px;
  border-radius: 3px;
  font-weight: 500;
}

.var-global {
  background: #e6f7ff;
  color: #1890ff;
}

.var-context {
  background: #f6ffed;
  color: #52c41a;
}

.var-other {
  background: #f0e6ff;
  color: #722ed1;
}

.value-missing :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px #f56c6c inset !important;
}

.validation-errors ul {
  margin: 6px 0 0 0;
  padding-left: 16px;
}

.validation-errors li {
  margin-bottom: 2px;
  font-size: 12px;
}

/* 下拉选项颜色圆点 */
.option-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}

.option-dot--draft {
  background: #909399;
}

.option-dot--active {
  background: #67C23A;
}

.option-dot--inactive {
  background: #F56C6C;
}

.option-dot--p0 {
  background: #F56C6C;
}

.option-dot--p1 {
  background: #E6A23C;
}

.option-dot--p2 {
  background: #409EFF;
}

.option-dot--p3 {
  background: #67C23A;
}

/* ===== 提取规则区域增强 ===== */
.extract-type-toggle {
  display: flex;
  gap: 2px;
  align-items: center;
}

.type-btn {
  width: 24px;
  height: 24px;
  border: 1px solid #dcdfe6;
  background: #fff;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  color: #606266;
  cursor: pointer;
  transition: all 0.15s ease;
  padding: 0;
  line-height: 22px;
}

.type-btn:hover {
  border-color: #7B2FF7;
  color: #7B2FF7;
}

.type-btn.active {
  background: #7B2FF7;
  border-color: #7B2FF7;
  color: #fff;
}

/* ===== 变量预览弹窗增强 ===== */
.variable-preview-content :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.empty-desc {
  color: #606266;
  font-size: 14px;
  margin-bottom: 4px;
}

.empty-hint {
  color: #909399;
  font-size: 12px;
  margin-bottom: 12px;
}

.extracted-empty {
  padding: 20px 0;
}

.extracted-vars-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding: 0 4px;
}

.extracted-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #909399;
}

/* ===== 变量提取区域增强 ===== */
.extract-rules-area {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #fff;
  overflow: hidden;
}

.extract-rule-header {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 6px 10px;
  font-weight: 600;
  font-size: 11px;
  color: #909399;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  min-height: 28px;
}

.extract-rule-header .field-col {
  flex: 1;
}

.extract-rule-header .name-col {
  flex: 0.7;
}

.extract-rule-header .val-col {
  flex: 0.7;
}

/* 变量提取输入框样式 */
.extract-rule-row .el-input {
  height: 32px;
}

.extract-rule-row .el-input__inner {
  height: 32px !important;
  line-height: 32px !important;
  font-size: 12px;
}

.extract-rule-row {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 0 10px;
  min-height: 36px;
  border-bottom: 1px solid #f0f0f0;
  background: #fff;
  transition: background-color 0.15s ease;
}

.extract-rule-row:nth-child(even) {
  background: #fafafa;
}

.extract-rule-row:hover {
  background: #f5f7fa;
}

.extract-rule-row:last-child {
  border-bottom: none;
}

.extract-rule-row .field-col {
  flex: 1;
  min-width: 0;
}

.extract-rule-row .name-col {
  flex: 0.7;
  min-width: 0;
}

.extract-rule-row .val-col {
  flex: 0.7;
  min-width: 0;
}

.extract-value-display {
  font-size: 12px;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  padding: 0 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-height: 24px;
  display: flex;
  align-items: center;
}

.value-success {
  color: #67c23a;
}

.value-error {
  color: #f56c6c;
}

.value-placeholder {
  color: #c0c4cc;
}

.extract-actions {
  display: flex;
  gap: 2px;
  align-items: center;
  justify-content: flex-end;
}

.extract-actions .extract-type-toggle {
  display: flex;
  gap: 2px;
  margin-right: 4px;
}

.extract-test-btn {
  width: 20px !important;
  height: 20px !important;
  padding: 0 !important;
  color: #909399 !important;
}

.extract-test-btn:hover {
  color: #7B2FF7 !important;
}

/* 变量提取 - 变量名短列 */
.extract-rule-header .name-col-short {
  width: 100px !important;
  min-width: 80px !important;
  max-width: 120px !important;
}

.extract-rule-row .name-col-short {
  width: 100px !important;
  min-width: 80px !important;
  max-width: 120px !important;
}

/* 变量提取 - 变量设置列 */
.extract-rule-header .var-setting-col {
  width: 120px !important;
  min-width: 100px !important;
}

.extract-rule-row .var-setting-col {
  width: 120px !important;
  min-width: 100px !important;
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

</style>
