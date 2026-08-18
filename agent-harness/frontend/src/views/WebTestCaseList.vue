<template>
  <div class="web-testcase-container">
    <el-card class="glass-card" shadow="never" :body-style="{ padding: '0' }">
      <template #header>
        <div class="page-hero">
          <div class="hero-main">
            <div class="hero-title">
              <div class="hero-icon-wrap">
                <el-icon :size="22"><Monitor /></el-icon>
              </div>
              <div class="hero-title-text">
                <h1>Web 自动化用例</h1>
                <p>双引擎驱动的浏览器自动化测试工作台</p>
              </div>
            </div>
            <el-button type="primary" size="large" class="hero-btn" @click="showCreateDialog">
              <el-icon><Plus /></el-icon>
              新建 Web 用例
            </el-button>
          </div>
          <div class="hero-stats" v-if="testCases.length">
            <div class="stat-item">
              <div class="stat-value">{{ pagination.total }}</div>
              <div class="stat-label">用例总数</div>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <div class="stat-value ai">{{ testCases.filter(t => t.engine === 'ai').length }}</div>
              <div class="stat-label">AI 模式</div>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <div class="stat-value playwright">{{ testCases.filter(t => t.engine === 'playwright').length }}</div>
              <div class="stat-label">步骤模式</div>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <div class="stat-value success">{{ testCases.filter(t => t.last_execution_status === 'passed').length }}</div>
              <div class="stat-label">最近通过</div>
            </div>
          </div>
        </div>
      </template>

      <!-- 搜索栏 -->
      <div class="page-toolbar">
        <el-form :inline="true" :model="searchForm" class="toolbar-form">
          <el-form-item>
            <el-input v-model="searchForm.search" placeholder="搜索标题/描述/目标URL" clearable prefix-icon="Search" style="width: 260px" />
          </el-form-item>
          <el-form-item label="引擎">
            <el-select v-model="searchForm.engine" placeholder="全部" clearable style="width: 130px">
              <el-option label="AI 模式" value="ai">
                <span style="display: flex; align-items: center; gap: 6px">
                  <el-icon color="#E6A23C"><MagicStick /></el-icon> AI 模式
                </span>
              </el-option>
              <el-option label="步骤模式" value="playwright">
                <span style="display: flex; align-items: center; gap: 6px">
                  <el-icon color="#409EFF"><SetUp /></el-icon> 步骤模式
                </span>
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 120px">
              <el-option label="草稿" value="draft"><span class="option-dot option-dot--draft"></span>草稿</el-option>
              <el-option label="激活" value="active"><span class="option-dot option-dot--active"></span>激活</el-option>
              <el-option label="停用" value="inactive"><span class="option-dot option-dot--inactive"></span>停用</el-option>
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="loadTestCases" class="toolbar-btn-primary">查询</el-button>
            <el-button @click="resetSearch" class="toolbar-btn-default">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <div class="page-content" v-loading="loading">
        <!-- 空状态 -->
        <div v-if="!loading && !testCases.length" class="empty-state-glass">
          <div class="empty-icon-wrap">
            <el-icon :size="64"><Monitor /></el-icon>
          </div>
          <div class="empty-title">暂无 Web 自动化测试用例</div>
          <div class="empty-description">创建第一个用例，开启 AI 或步骤模式的浏览器自动化测试</div>
          <div class="empty-actions">
            <el-button type="primary" size="large" @click="showCreateDialog">
              <el-icon><Plus /></el-icon> 新建第一个 Web 用例
            </el-button>
          </div>
        </div>

        <!-- 表格 -->
        <template v-if="testCases.length">
          <el-table :data="testCases" class="data-table" row-key="id">
            <el-table-column prop="id" label="ID" width="120" sortable align="center" show-overflow-tooltip />
            <el-table-column prop="title" label="标题" min-width="160" sortable show-overflow-tooltip />
            <el-table-column prop="target_url" label="目标 URL" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                <el-link :href="row.target_url" target="_blank" type="primary" :underline="false">
                  {{ truncateUrl(row.target_url) }}
                  <el-icon><Link /></el-icon>
                </el-link>
              </template>
            </el-table-column>
            <el-table-column prop="engine" label="引擎" width="120" sortable>
              <template #default="{ row }">
                <el-tag v-if="row.engine === 'ai'" size="small" type="warning">
                  <el-icon style="margin-right:4px;vertical-align:-1px"><MagicStick /></el-icon> AI模式
                </el-tag>
                <el-tag v-else size="small" type="info">
                  <el-icon style="margin-right:4px;vertical-align:-1px"><SetUp /></el-icon> 步骤模式
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="80" sortable>
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusText(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="last_execution_status" label="上次执行" width="95" sortable>
              <template #default="{ row }">
                <el-tag v-if="row.last_execution_status === 'passed'" type="success" size="small">通过</el-tag>
                <el-tag v-else-if="row.last_execution_status === 'failed'" type="danger" size="small">失败</el-tag>
                <el-tag v-else-if="row.last_execution_status === 'error'" type="warning" size="small">异常</el-tag>
                <span v-else class="no-execution-text">未执行</span>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="160" sortable>
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="340" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="success" @click="debugExecute(row)" :loading="executingId === row.id">
                  <el-icon><VideoPlay /></el-icon> 执行
                </el-button>
                <el-button size="small" @click="showViewDialog(row)">查看</el-button>
                <el-button size="small" type="primary" @click="showEditDialog(row)">编辑</el-button>
                <el-button size="small" type="danger" @click="deleteTestCase(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 分页 -->
          <div class="page-pagination">
            <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.pageSize"
              :total="pagination.total" :page-sizes="[10, 20, 50]"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="loadTestCases" @current-change="loadTestCases" />
          </div>
        </template>
      </div>

    <!-- 执行结果已改为 ElMessage 提示，详情请通过「查看历史」查看 -->
    </el-card>

    <!-- ========== 创建/编辑对话框 ========== -->
    <el-dialog v-model="dialogVisible"
      :title="dialogTitle"
      width="900px"
      top="5vh"
      destroy-on-close
      class="web-testcase-dialog">

      <div v-if="!isView" class="engine-toggle-bar">
        <span class="toggle-label">测试引擎：</span>
        <el-radio-group v-model="formData.engine" size="large">
          <el-radio-button value="ai">
            <el-icon style="margin-right:4px;vertical-align:-2px"><MagicStick /></el-icon>
            AI 模式（自然语言）
          </el-radio-button>
          <el-radio-button value="playwright">
            <el-icon style="margin-right:4px;vertical-align:-2px"><SetUp /></el-icon>
            步骤模式（精确控制）
          </el-radio-button>
        </el-radio-group>
        <div class="engine-hint">
          <el-text v-if="formData.engine === 'ai'" type="info" size="small">
            用自然语言描述测试步骤，AI 自动驱动浏览器执行，适合快速冒烟和回归巡检
          </el-text>
          <el-text v-else type="info" size="small">
            精确编写每个浏览器操作步骤，适合复杂交互、表单验证等需要精确控制的场景
          </el-text>
        </div>
      </div>

      <el-form :model="formData" ref="formRef" label-width="90px" :disabled="isView">
        <!-- 基本信息 -->
        <el-divider content-position="left"><el-icon><Document /></el-icon> 基本信息</el-divider>

        <el-row :gutter="16">
          <el-col :span="16">
            <el-form-item label="标题" prop="title" :rules="[{ required: true, message: '请输入用例标题', trigger: 'blur' }]">
              <el-input v-model="formData.title" placeholder="如：登录功能验证 - AI 模式" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="优先级">
              <el-select v-model="formData.priority" style="width: 100%">
                <el-option label="P0 - 最高" value="P0" />
                <el-option label="P1 - 高" value="P1" />
                <el-option label="P2 - 中" value="P2" />
                <el-option label="P3 - 低" value="P3" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="目标URL" prop="target_url" :rules="[{ required: true, message: '请输入目标URL', trigger: 'blur' }]">
          <el-input v-model="formData.target_url" placeholder="https://example.com 或 http://localhost:3000/login">
            <template #prefix><el-icon><Link /></el-icon></template>
          </el-input>
        </el-form-item>

        <el-form-item label="描述">
          <el-input v-model="formData.description" type="textarea" :autosize="{ minRows: 2, maxRows: 3 }"
            placeholder="用例用途说明..." />
        </el-form-item>

        <!-- ====== AI 模式面板 ====== -->
        <template v-if="formData.engine === 'ai'">
          <el-divider content-position="left">
            <el-icon color="#E6A23C"><MagicStick /></el-icon> AI 测试描述
          </el-divider>
          <el-form-item label="测试描述" prop="ai_prompt" :rules="[{ required: true, message: '请输入AI测试描述', trigger: 'blur' }]">
            <el-input v-model="formData.ai_prompt" type="textarea" :autosize="{ minRows: 6, maxRows: 12 }"
              placeholder="&#10;&#10;示例（每行一个步骤）：&#10;&#10;打开登录页面&#10;在用户名输入框中输入 admin&#10;在密码输入框中输入 123456&#10;点击登录按钮&#10;验证页面跳转到首页&#10;验证页面包含&quot;欢迎&quot;文字" />
          </el-form-item>
          <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px; padding: 8px 12px">
            <template #title>
              <span style="font-weight: normal">使用<strong>自然语言</strong>描述测试步骤，<strong>每行一条</strong>。</span>
              <el-tooltip placement="bottom" effect="light" :width="360">
                <template #content>
                  <div style="line-height: 2">
                    <div><code>打开/访问 [URL]</code> — 导航到指定页面</div>
                    <div><code>点击 [元素描述]</code> — 点击按钮或链接</div>
                    <div><code>在[位置]输入 [值]</code> — 填写表单字段</div>
                    <div><code>选择[下拉框]的[选项]</code> — 下拉选择</div>
                    <div><code>验证 [条件]</code> — 断言检查（文本、URL、元素可见性等）</div>
                    <div><code>等待 [秒数]秒</code> — 显式等待</div>
                    <div><code>截图保存为 [名称]</code> — 截图并作为基线</div>
                  </div>
                </template>
                <el-button size="small" type="primary" plain round style="margin-left: 8px; padding: 2px 10px">
                  <el-icon><InfoFilled /></el-icon> 指令语法参考
                </el-button>
              </el-tooltip>
            </template>
          </el-alert>
        </template>

        <!-- ====== Playwright 步骤模式面板 ====== -->
        <template v-if="formData.engine === 'playwright'">
          <el-divider content-position="left">
            <el-icon color="#409EFF"><SetUp /></el-icon> 操作步骤
            <el-button size="small" type="primary" plain style="margin-left: 12px" @click="addStep">
              <el-icon><Plus /></el-icon> 添加步骤
            </el-button>
          </el-divider>

          <div class="steps-editor">
            <div v-for="(step, index) in formData.steps" :key="step.__uid" class="step-row">
              <div class="step-index">{{ index + 1 }}</div>
              <div class="step-action">
                <el-select v-model="step.action" placeholder="操作类型" style="width: 140px" @change="onStepActionChange(step)">
                  <el-option-group label="导航">
                    <el-option label="打开页面" value="navigate" />
                    <el-option label="返回上一页" value="go_back" />
                    <el-option label="刷新页面" value="refresh" />
                  </el-option-group>
                  <el-option-group label="输入">
                    <el-option label="填写输入框" value="fill" />
                    <el-option label="清空输入框" value="clear" />
                    <el-option label="键盘按键" value="press" />
                  </el-option-group>
                  <el-option-group label="点击">
                    <el-option label="点击元素" value="click" />
                    <el-option label="双击元素" value="dblclick" />
                    <el-option label="右键点击" value="right_click" />
                    <el-option label="悬停" value="hover" />
                  </el-option-group>
                  <el-option-group label="选择">
                    <el-option label="下拉选择(选项)" value="select_option" />
                    <el-option label="复选框" value="check" />
                    <el-option label="单选框" value="radio" />
                  </el-option-group>
                  <el-option-group label="断言">
                    <el-option label="断言文本存在" value="assert_text" />
                    <el-option label="断言URL包含" value="assert_url" />
                    <el-option label="断言元素可见" value="assert_visible" />
                    <el-option label="断言元素隐藏" value="assert_hidden" />
                    <el-option label="截图对比" value="screenshot_compare" />
                  </el-option-group>
                  <el-option-group label="其他">
                    <el-option label="等待时间" value="wait" />
                    <el-option label="等待元素出现" value="wait_for_selector" />
                    <el-option label="截取屏幕" value="screenshot" />
                    <el-option label="滚动页面" value="scroll" />
                  </el-option-group>
                </el-select>
              </div>
              <div class="step-params">
                <template v-if="step.action === 'navigate' || step.action === 'fill' || step.action === 'assert_text' || step.action === 'assert_visible' || step.action === 'wait_for_selector' || step.action === 'click' || step.action === 'hover'">
                  <el-input v-model="step.params.selector_or_value" :placeholder="getStepPlaceholder(step.action)" />
                </template>
                <template v-else-if="step.action === 'select_option'">
                  <el-input v-model="step.params.selector_or_value" placeholder="选择器" style="flex:1" />
                  <el-input v-model="step.params.option_value" placeholder="选项值" style="flex:1" />
                </template>
                <template v-else-if="step.action === 'assert_url'">
                  <el-input v-model="step.params.selector_or_value" placeholder="URL 关键词" />
                </template>
                <template v-else-if="step.action === 'wait'">
                  <el-input-number v-model="step.params.timeout" :min="0.1" :max="30" :step="0.5" :precision="1"
                    controls-position="right" style="width: 120px" />
                  <span class="param-unit">秒</span>
                </template>
                <template v-else-if="step.action === 'press'">
                  <el-input v-model="step.params.selector_or_value" placeholder="如 Enter, Tab, ArrowDown" />
                </template>
                <template v-else-if="step.action === 'screenshot_compare' || step.action === 'screenshot'">
                  <el-input v-model="step.params.baseline_name" placeholder="基线名称（用于对比）" />
                </template>
                <template v-else-if="step.action === 'scroll'">
                  <el-input-number v-model="step.params.x" :min="-5000" :max="5000" controls-position="right" style="width: 90px" />
                  <el-input-number v-model="step.params.y" :min="-5000" :max="5000" controls-position="right" style="width: 90px" />
                </template>
                <template v-else>
                  <span class="no-param-hint">{{ getStepPlaceholder(step.action) }}</span>
                </template>
              </div>
              <div class="step-actions">
                <el-button link size="small" @click="moveStepUp(index)" :disabled="index === 0" title="上移">
                  <el-icon><Top /></el-icon>
                </el-button>
                <el-button link size="small" @click="moveStepDown(index)" :disabled="index === formData.steps.length - 1" title="下移">
                  <el-icon><Bottom /></el-icon>
                </el-button>
                <el-button link size="small" type="danger" @click="removeStep(index)" title="删除">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>

            <div v-if="!formData.steps.length" class="steps-empty">
              <el-icon><InfoFilled /></el-icon>
              <span>暂无操作步骤，点击上方「添加步骤」按钮开始编辑</span>
            </div>

            <el-alert v-if="formData.engine === 'playwright'" type="info" :closable="false" show-icon
              style="margin-top: 12px" title="选择器提示">
              支持 CSS 选择器（#id .class）、XPath（//div[@class='x']）或文本选择器（text='登录'），
              推荐使用 <strong>data-testid</strong> 属性定位以提高稳定性。
            </el-alert>
          </div>
        </template>

        <!-- ====== 断言规则（通用） ====== -->
        <el-divider content-position="left"><el-icon><CircleCheck /></el-icon> 断言规则</el-divider>
        <div class="assertions-section">
          <div v-for="(assertion, idx) in formData.assertions" :key="assertion.__uid" class="assertion-row">
            <el-select v-model="assertion.type" placeholder="断言类型" style="width: 170px">
              <el-option label="文本包含" value="text_contains" />
              <el-option label="文本等于" value="text_equals" />
              <el-option label="URL 包含" value="url_contains" />
              <el-option label="URL 匹配正则" value="url_matches_regex" />
              <el-option label="元素可见" value="element_visible" />
              <el-option label="元素不可见" value="element_hidden" />
              <el-option label="截图对比基线" value="screenshot_baseline" />
              <el-option label="自定义 JS 表达式" value="custom_js" />
            </el-select>
            <el-input v-model="assertion.value" placeholder="断言值（选择器或期望值）" style="flex:1" />
            <el-button link size="small" type="danger" @click="removeAssertion(idx)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
          <el-button size="small" plain @click="addAssertion" style="margin-top: 8px">
            <el-icon><Plus /></el-icon> 添加断言
          </el-button>
          <div v-if="!formData.assertions.length" class="empty-hint-text">
            无额外断言。AI 模式会自动从描述中提取断言；步骤模式的断言已内联在步骤中。
          </div>
        </div>

        <!-- ====== Cookie 注入（登录态保持）====== -->
        <el-divider content-position="left">
          <el-icon color="#67C23A"><Key /></el-icon> Cookie 注入（保持登录态）
          <el-button size="small" type="success" plain style="margin-left: 12px" @click="addCookieRow">
            <el-icon><Plus /></el-icon> 添加 Cookie
          </el-button>
        </el-divider>
        <el-alert type="warning" :closable="false" show-icon style="margin-bottom: 12px">
          <p><strong>重要：</strong>如果目标页面需要登录，请在此填入登录后的 Cookie。执行时平台会自动注入这些 Cookie，使浏览器以登录态打开页面。</p>
          <p style="margin-top: 4px; font-size: 12px;">
            获取方式：浏览器 F12 → Application → Cookies → 选择目标域名 → 复制关键 Cookie 的 Name 和 Value
          </p>
        </el-alert>
        <div v-if="!formData.cookies.length" class="empty-hint-text">
          未配置 Cookie。如果目标页面公开无需登录，可跳过此项。
        </div>
        <div v-else class="cookie-editor">
          <div v-for="(ck, idx) in formData.cookies" :key="idx" class="cookie-row">
            <span class="cookie-index">{{ idx + 1 }}</span>
            <el-input v-model="ck.name" placeholder="名称 (如 sessionid)" style="width: 180px" size="small" />
            <el-input v-model="ck.value" placeholder="值" style="flex:1;min-width:200px" size="small" />
            <el-input v-model="ck.domain" placeholder="域名 (如 .doubao.com)" style="width: 180px" size="small" />
            <el-input v-model="ck.path" placeholder="路径" style="width: 60px" size="small" value="/" />
            <el-button size="small" type="danger" plain :icon="Delete" circle @click="removeCookieRow(idx)" />
          </div>
        </div>

        <!-- ====== 执行配置 ====== -->
        <el-divider content-position="left"><el-icon><Setting /></el-icon> 执行配置</el-divider>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="浏览器">
              <el-select v-model="formData.browser_type" style="width: 100%">
                <el-option label="Chromium (Chrome)" value="chromium">
                  <span style="display:flex;align-items:center;gap:6px">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="#4285F4"><circle cx="12" cy="12" r="10"/></svg>
                    Chromium
                  </span>
                </el-option>
                <el-option label="Firefox" value="firefox">
                  <span style="display:flex;align-items:center;gap:6px">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="#FF7139"><circle cx="12" cy="12" r="10"/></svg>
                    Firefox
                  </span>
                </el-option>
                <el-option label="WebKit (Safari)" value="webkit">
                  <span style="display:flex;align-items:center;gap:6px">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="#0095D9"><circle cx="12" cy="12" r="10"/></svg>
                    WebKit
                  </span>
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="无头模式">
              <el-switch v-model="formData.browser_config.headless"
                active-text="是（后台运行）"
                inactive-text="否（显示浏览器）" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="状态">
              <el-select v-model="formData.status" style="width: 100%">
                <el-option label="草稿" value="draft"><span class="option-dot option-dot--draft"></span>草稿</el-option>
                <el-option label="激活" value="active"><span class="option-dot option-dot--active"></span>激活</el-option>
                <el-option label="停用" value="inactive"><span class="option-dot option-dot--inactive"></span>停用</el-option>
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="录制选项">
          <el-checkbox v-model="formData.screenshot_enabled">自动截图（每个步骤后截屏）</el-checkbox>
          <el-checkbox v-model="formData.record_video" style="margin-left: 20px">录屏记录整个执行过程</el-checkbox>
          <el-checkbox v-model="formData.full_page_screenshot" style="margin-left: 20px">全页长截图</el-checkbox>
        </el-form-item>
      </el-form>

      <template #footer>
        <div v-if="!isView" style="display: flex; justify-content: space-between;">
          <div>
            <el-button @click="handleDebug" :loading="debugging" type="warning" plain>
              <el-icon><VideoPlay /></el-icon> 调试运行
            </el-button>
          </div>
          <div>
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
          </div>
        </div>
        <div v-else style="text-align: right">
          <el-button @click="dialogVisible = false">关闭</el-button>
          <el-button type="primary" @click="switchToEdit">编辑此用例</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- ========== 执行历史弹窗 ========== -->
    <el-dialog v-model="historyVisible" title="执行历史" width="900px" top="5vh" destroy-on-close>
      <template #header>
        <div style="display:flex;align-items:center;gap:8px">
          <el-icon><Clock /></el-icon>
          <span>执行历史 — {{ historyCaseTitle }}</span>
        </div>
      </template>

      <el-table :data="executionHistory" border stripe v-loading="historyLoading" size="small"
        style="width: 100%" row-key="id" max-height="500">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="状态" width="85">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'passed'" type="success" size="small">通过</el-tag>
            <el-tag v-else-if="row.status === 'failed'" type="danger" size="small">失败</el-tag>
            <el-tag v-else type="warning" size="small">异常</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="duration" label="耗时" width="75">
          <template #default="{ row }">{{ row.duration ? row.duration.toFixed(1) + 's' : '-' }}</template>
        </el-table-column>
        <el-table-column label="执行人" width="90">
          <template #default="{ row }">{{ row.executed_by_username || '-' }}</template>
        </el-table-column>
        <el-table-column prop="executed_at" label="执行时间" width="160">
          <template #default="{ row }">{{ formatHistoryDate(row.executed_at) }}</template>
        </el-table-column>
        <el-table-column label="截图" width="70" align="center">
          <template #default="{ row }">
            <el-button v-if="row.screenshot_url" size="small" link type="primary" @click="previewScreenshot(row.screenshot_url)">
              查看
            </el-button>
            <span v-else style="color:#c0c4cc">无</span>
          </template>
        </el-table-column>
        <el-table-column label="步骤摘要" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.result_data && row.result_data.steps_results">
              {{ row.result_data.steps_results.length }} 步骤完成
            </span>
            <span v-else-if="row.result_data && row.result_data.error" style="color:#F56C6C">
              错误: {{ row.result_data.error.slice(0, 50) }}...
            </span>
            <span v-else style="color:#c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="viewHistoryDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!historyLoading && !executionHistory.length" description="暂无执行历史记录" />

      <template #footer>
        <el-button @click="historyVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- ========== 历史截图预览弹窗 ========== -->
    <el-dialog v-model="screenshotPreviewVisible" title="截图预览" width="90%" top="3vh" destroy-on-close>
      <img :src="screenshotPreviewUrl" alt="截图" 
        style="max-width:100%; max-height:80vh; object-fit:contain; border-radius:8px" />
    </el-dialog>

    <!-- ========== 历史详情弹窗（完整信息在此展示）========== -->
    <el-dialog v-model="historyDetailVisible" title="执行详情" width="960px" top="3vh" destroy-on-close
      class="history-detail-dialog">
      <template #header>
        <div style="display:flex;align-items:center;gap:8px">
          <el-icon><Tickets /></el-icon>
          <span>执行详情 #{{ historyDetail.id }}</span>
          <el-tag :type="historyDetail.status === 'passed' ? 'success' : historyDetail.status === 'failed' ? 'danger' : 'warning'" size="small">
            {{ historyDetail.status === 'passed' ? '通过' : historyDetail.status === 'failed' ? '失败' : '异常' }}
          </el-tag>
          <span style="color:#909399;font-size:12px">{{ formatHistoryDate(historyDetail.executed_at) }} · {{ historyDetail.duration ? historyDetail.duration.toFixed(1) + 's' : '-' }}</span>
        </div>
      </template>

      <!-- 截图展示（下拉选择 + 固定尺寸预览） -->
      <div v-if="allScreenshots.length > 0" style="margin-bottom:20px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
          <h4 style="margin:0;font-size:14px;display:flex;align-items:center;gap:6px">
            <el-icon><Picture /></el-icon> 执行截图 ({{ allScreenshots.length }})
          </h4>
          <el-button size="small" type="primary" plain @click="downloadHistoryScreenshot(selectedScreenshotUrl)">
            <el-icon><Download /></el-icon> 下载
          </el-button>
        </div>
        <div style="display:flex;align-items:flex-start;gap:12px">
          <el-select v-model="selectedScreenshotIdx" size="default" style="width:200px;flex-shrink:0"
            placeholder="选择截图">
            <el-option v-for="(ss, idx) in allScreenshots" :key="idx" :label="ss.label" :value="idx" />
          </el-select>
          <div style="flex:1;text-align:center;background:#f5f7fa;border-radius:8px;padding:12px;border:1px solid #e4e7ed;overflow:auto;max-height:400px;min-height:240px;display:flex;align-items:center;justify-content:center">
            <img :src="selectedScreenshotUrl" alt="执行截图"
              style="max-width:100%;max-height:376px;object-fit:contain;border-radius:6px;border:1px solid #dcdfe6;cursor:pointer"
              @click="previewScreenshot(selectedScreenshotUrl)" />
          </div>
        </div>
      </div>

      <!-- 步骤执行结果 -->
      <div v-if="historyDetail.result_data && historyDetail.result_data.steps_results" style="margin-bottom:20px">
        <h4 style="font-size:14px;margin:0 0 10px;display:flex;align-items:center;gap:6px">
          <el-icon><VideoPlay /></el-icon> 步骤执行结果 ({{ historyDetail.result_data.steps_results.length }} 步)
        </h4>
        <el-timeline>
          <el-timeline-item v-for="(step, idx) in historyDetail.result_data.steps_results" :key="idx"
            :type="step.status === 'completed' ? 'success' : 'danger'"
            :timestamp="'Step ' + (idx + 1)" placement="top"
            size="large" :hollow="step.status !== 'completed'">
            <el-card shadow="never" size="small" style="margin-bottom:4px">
              <div style="display:flex;align-items:center;gap:8px">
                <el-tag size="small" :type="step.status === 'completed' ? 'success' : 'danger'">
                  {{ step.status === 'completed' ? '通过' : step.status || '失败' }}
                </el-tag>
                <code style="color:#303133;font-size:13px">{{ step.action || step.step || `步骤${idx+1}` }}</code>
                <span v-if="step.instruction" style="color:#909399;font-size:12px">— {{ step.instruction }}</span>
              </div>
              <div v-if="step.selector || step.value" style="margin-top:6px;color:#606266;font-size:12px">
                <span v-if="step.selector">选择器: <code>{{ step.selector }}</code></span>
                <span v-if="step.value" style="margin-left:12px">值: <code>{{ step.value }}</code></span>
              </div>
              <div v-if="step.error" style="margin-top:6px;color:#F56C6C;font-size:12px">
                错误: {{ step.error }}
              </div>
              <!-- 步骤截图提示 -->
              <el-tag v-if="step.screenshot" size="small" type="info" style="margin-top:6px;cursor:pointer"
                @click="jumpToStepScreenshot(step.screenshot)">
                <el-icon><Picture /></el-icon> 有截图
              </el-tag>
            </el-card>
          </el-timeline-item>
        </el-timeline>
      </div>

      <!-- 执行日志 / 原始数据 -->
      <div v-if="historyDetail.result_data" style="margin-bottom:16px">
        <h4 style="font-size:14px;margin:0 0 8px;display:flex;align-items:center;gap:6px">
          <el-icon><Tickets /></el-icon> 执行数据
        </h4>
        <pre class="log-content">{{ JSON.stringify(historyDetail.result_data, null, 2) }}</pre>
      </div>

      <!-- 错误信息 -->
      <el-alert v-if="historyDetail.error_message || (historyDetail.result_data && historyDetail.result_data.error)"
        type="error" :closable="false" show-icon
        :title="historyDetail.error_message || historyDetail.result_data.error" />

      <template #footer>
        <el-button @click="historyDetailVisible = false">关闭</el-button>
        <el-button type="primary" @click="historyDetailVisible = false; showExecutionHistory({ id: historyDetail.test_case, title: historyCaseTitle })">
          返回历史列表
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import {
  Monitor, Plus, Link, MagicStick, SetUp, Document, Setting, VideoPlay,
  Top, Bottom, Delete, CircleCheck, InfoFilled, SuccessFilled,
  CircleCloseFilled, Picture, Tickets, Clock, Download, Key, Search,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { webTestcaseAPI } from '@/api'

// ========== 数据 ==========
const loading = ref(false)
const executingId = ref(null)
const testCases = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const isView = ref(false)
const submitting = ref(false)
const debugging = ref(false)
const formRef = ref(null)

const searchForm = reactive({ search: '', engine: '', status: '' })
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

// 执行历史弹窗
const historyVisible = ref(false)
const historyLoading = ref(false)
const executionHistory = ref([])
const historyCaseTitle = ref('')
const screenshotPreviewVisible = ref(false)
const screenshotPreviewUrl = ref('')
const historyDetailVisible = ref(false)
const historyDetail = ref({})
const historyTargetCaseId = ref(null)  // 保存目标用例ID

// ========== 历史详情截图（下拉选择器）==========
const selectedScreenshotIdx = ref(0)
const allScreenshots = computed(() => {
  const list = []
  const hd = historyDetail.value
  // 最终截图
  if (hd?.screenshot_url) {
    list.push({ label: '最终截图', url: hd.screenshot_url })
  }
  // 步骤级截图
  if (hd?.result_data?.steps_results) {
    hd.result_data.steps_results.forEach((step, idx) => {
      if (step.screenshot) {
        list.push({ label: `步骤${idx + 1}: ${step.action || step.step || ''}`, url: step.screenshot })
      }
    })
  }
  return list
})
const selectedScreenshotUrl = computed(() => {
  return allScreenshots.value.length > 0 ? allScreenshots.value[selectedScreenshotIdx.value]?.url : ''
})

// 内嵌执行结果面板（已移除，改为 ElMessage 轻量提示）

// 步骤 uid 计数器
let _uidCounter = 1

// 表单数据
const formData = reactive({
  title: '',
  description: '',
  priority: 'P1',
  target_url: '',
  engine: 'playwright',
  status: 'active',
  // AI 模式
  ai_prompt: '',
  // Playwright 模式
  steps: [],
  // 断言
  assertions: [],
  // 浏览器配置
  browser_type: 'chromium',
  browser_config: { headless: false },
  // Cookie 注入
  cookies: [],
  // 录制选项
  screenshot_enabled: true,
  record_video: false,
  full_page_screenshot: false,
})

// 对话框标题
const dialogTitle = computed(() => {
  if (isView.value) return '查看 Web 用例'
  return isEdit.value ? '编辑 Web 用例' : '新建 Web 用例'
})

// ========== API 操作 ==========
const loadTestCases = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      search: searchForm.search || undefined,
      engine: searchForm.engine || undefined,
      status: searchForm.status || undefined,
    }
    const res = await webTestcaseAPI.list(params)
    testCases.value = res.results || res
    pagination.total = res.total
  } catch (e) {
    console.error('Load web testcases error:', e)
  } finally {
    loading.value = false
  }
}

const resetSearch = () => {
  searchForm.search = ''
  searchForm.engine = ''
  searchForm.status = ''
  pagination.page = 1
  loadTestCases()
}

const resetForm = () => {
  // 先删除 id 确保不会误走更新接口
  const cleanData = {
    id: undefined,
    title: '', description: '', priority: 'P1', target_url: '',
    engine: 'playwright', status: 'active', ai_prompt: '',
    steps: [], assertions: [], cookies: [],
    browser_type: 'chromium', browser_config: { headless: false },
    screenshot_enabled: true, record_video: false, full_page_screenshot: false,
  }
  Object.keys(formData).forEach(k => delete formData[k])
  Object.assign(formData, cleanData)
}

// ========== 对话框 ==========
const showCreateDialog = () => {
  isEdit.value = false
  isView.value = false
  resetForm()
  dialogVisible.value = true
}

const showEditDialog = async (row) => {
  isEdit.value = true
  isView.value = false
  const data = await webTestcaseAPI.get(row.id)
  resetForm()
  Object.assign(formData, data)
  // 确保 steps 有 __uid
  formData.steps = (data.steps || []).map(s => ({ ...s, __uid: ++_uidCounter }))
  formData.assertions = (data.assertions || []).map(a => ({ ...a, __uid: ++_uidCounter }))
  if (!formData.cookies) formData.cookies = []
  if (!formData.browser_config) formData.browser_config = { headless: false }
  dialogVisible.value = true
}

const showViewDialog = async (row) => {
  isEdit.value = false
  isView.value = true
  const data = await webTestcaseAPI.get(row.id)
  Object.assign(formData, data)
  formData.steps = (data.steps || []).map(s => ({ ...s, __uid: ++_uidCounter }))
  formData.assertions = (data.assertions || []).map(a => ({ ...a, __uid: ++_uidCounter }))
  if (!formData.browser_config) formData.browser_config = {}
  dialogVisible.value = true
}

const switchToEdit = () => {
  isView.value = false
  isEdit.value = true
}

// 提交
const handleSubmit = async () => {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch { return }

  submitting.value = true
  try {
    // 清理 __uid 字段
    const payload = JSON.parse(JSON.stringify(formData))
    payload.steps = (payload.steps || []).map(({ __uid, ...rest }) => rest)
    payload.assertions = (payload.assertions || []).map(({ __uid, ...rest }) => rest)

    if (isEdit.value) {
      await webTestcaseAPI.update(payload.id, payload)
      ElMessage.success('更新成功')
    } else {
      // 创建时必须清除 id，防止误走到更新接口
      delete payload.id
      await webTestcaseAPI.create(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadTestCases()
  } catch (e) {
    console.error('Submit error:', e)
  } finally {
    submitting.value = false
  }
}

// 删除
const deleteTestCase = async (id) => {
  await ElMessageBox.confirm('确认删除该 Web 测试用例？', '提示', { type: 'warning' })
  await webTestcaseAPI.delete(id)
  ElMessage.success('删除成功')
  loadTestCases()
}

// 调试运行
const handleDebug = async () => {
  debugging.value = true
  try {
    const payload = JSON.parse(JSON.stringify(formData))
    payload.steps = (payload.steps || []).map(({ __uid, ...rest }) => rest)
    payload.assertions = (payload.assertions || []).map(({ __uid, ...rest }) => rest)
    const res = await webTestcaseAPI.debugTemp(payload)
    showResultDialog(res, { id: formData.id, title: formData.title })
  } catch (e) {
    console.error('Debug error:', e)
  } finally {
    debugging.value = false
  }
}

// 列表直接执行
const debugExecute = async (row) => {
  executingId.value = row.id
  historyTargetCaseId.value = row.id
  try {
    const res = await webTestcaseAPI.debug(row.id)
    showResultDialog(res, row)
  } catch (e) {
    console.error('Execute error:', e)
  } finally {
    executingId.value = null
  }
}

const showResultDialog = (res, caseInfo) => {
  if (!res) {
    ElMessage.error('执行异常：未知错误')
    return
  }
  const er = res.execution_result || {}
  const status = er.status || (res.passed ? 'passed' : 'failed')
  const duration = res.duration || er.duration

  // 仅消息提示，详情请通过执行历史查看
  if (status === 'passed') {
    ElMessage.success(`✅ 执行通过！耗时 ${duration ? Number(duration).toFixed(1) : '-'}s，请到「执行历史」查看详情`)
  } else if (status === 'failed') {
    ElMessage.error(`❌ 执行失败！耗时 ${duration ? Number(duration).toFixed(1) : '-'}s，请到「执行历史」查看详情`)
  } else {
    ElMessage.warning('⚠️ 执行异常，请到「执行历史」查看详情')
  }
}


// ========== 执行历史 ==========
const showExecutionHistory = async (row) => {
  historyCaseTitle.value = row.title || `用例 #${row.id}`
  historyTargetCaseId.value = row.id
  historyVisible.value = true
  historyLoading.value = true
  executionHistory.value = []
  try {
    const res = await webTestcaseAPI.executions(row.id)
    executionHistory.value = res.results || res || []
  } catch (e) {
    console.error('Load execution history error:', e)
  } finally {
    historyLoading.value = false
  }
}

const formatHistoryDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const previewScreenshot = (url) => {
  screenshotPreviewUrl.value = url
  screenshotPreviewVisible.value = true
}

const viewHistoryDetail = (row) => {
  historyDetail.value = row
  historyDetailVisible.value = true
  // 重置截图选择到第一张
  selectedScreenshotIdx.value = 0
}

// 点击步骤"有截图"标签，自动选中下拉中对应截图
const jumpToStepScreenshot = (url) => {
  const idx = allScreenshots.value.findIndex(ss => ss.url === url)
  if (idx >= 0) {
    selectedScreenshotIdx.value = idx
  }
}

const downloadHistoryScreenshot = (url) => {
  if (!url) return
  const a = document.createElement('a')
  a.href = url
  a.download = url.split('/').pop() || 'screenshot.png'
  a.click()
}

// ========== 步骤操作 ==========
const addStep = () => {
  formData.steps.push({
    __uid: ++_uidCounter,
    action: '',
    params: { selector_or_value: '' },
  })
}

const removeStep = (idx) => { formData.steps.splice(idx, 1) }

// Cookie 管理
const addCookieRow = () => {
  formData.cookies.push({ name: '', value: '', domain: '', path: '/' })
}
const removeCookieRow = (idx) => { formData.cookies.splice(idx, 1) }

const moveStepUp = (idx) => {
  if (idx > 0) { const tmp = formData.steps[idx]; formData.steps[idx] = formData.steps[idx - 1]; formData.steps[idx - 1] = tmp }
}
const moveStepDown = (idx) => {
  if (idx < formData.steps.length - 1) { const tmp = formData.steps[idx]; formData.steps[idx] = formData.steps[idx + 1]; formData.steps[idx + 1] = tmp }
}

const onStepActionChange = (step) => {
  step.params = { selector_or_value: '' }
}

const getStepPlaceholder = (action) => {
  const map = {
    navigate: 'URL 地址',
    fill: '#username 或 [placeholder="用户名"]',
    click: '选择器或文本',
    hover: '选择器或文本',
    assert_text: '期望包含的文本',
    assert_visible: '应存在的元素选择器',
    wait_for_selector: '要等待的选择器',
    press: 'Enter / Tab / ArrowDown',
    screenshot_compare: '基线文件名',
    screenshot: '截图命名前缀',
    go_back: '无需参数',
    refresh: '无需参数',
    clear: '输入框选择器',
    dblclick: '选择器',
    right_click: '选择器',
    check: '复选框选择器',
    radio: '单选框选择器',
    select_option: '见下方双输入框',
    assert_text: '期望文本',
    assert_url: 'URL关键词',
    assert_hidden: '应隐藏的元素选择器',
    wait: '见下方数字输入',
    scroll: '见下方坐标',
  }
  return map[action] || '参数'
}

// ========== 断言操作 ==========
const addAssertion = () => {
  formData.assertions.push({ __uid: ++_uidCounter, type: 'text_contains', value: '' })
}
const removeAssertion = (idx) => { formData.assertions.splice(idx, 1) }

// ========== 工具函数 ==========
const truncateUrl = (url) => {
  if (!url) return '-'
  return url.length > 50 ? url.substring(0, 47) + '...' : url
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const getStatusType = (status) => {
  const statusMap = { draft: 'info', active: 'success', inactive: 'danger' }
  return statusMap[status] || ''
}
const getStatusText = (status) => {
  return { draft: '草稿', active: '激活', inactive: '停用' }[status] || status
}

// 初始化加载
loadTestCases()
</script>

<style scoped>
.web-testcase-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
}

.search-form {
  margin-bottom: 16px;
}
.no-execution-text {
  color: #c0c4cc;
  font-size: 12px;
}

/* 引擎切换 */
.engine-toggle-bar {
  background: #f5f7fa;
  padding: 14px 18px;
  border-radius: 8px;
  margin-bottom: 20px;
  border: 1px solid #e4e7ed;
}
.toggle-label {
  font-weight: 600;
  font-size: 14px;
  margin-right: 12px;
  vertical-align: middle;
}
.engine-hint {
  margin-top: 8px;
  padding-left: calc(var(--el-font-size-base) + 26px);
}

/* 步骤编辑器 */
.steps-editor {
  background: #fafafa;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 12px;
}
.step-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: white;
  border-radius: 6px;
  margin-bottom: 8px;
  border: 1px solid #ebeef5;
  transition: box-shadow 0.2s;
}
.step-row:hover {
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
.step-index {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #409eff;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}
.step-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}
.step-params {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
}
.param-unit {
  color: #999;
  font-size: 12px;
}
.no-param-hint {
  color: #c0c4cc;
  font-size: 12px;
}
.steps-empty {
  text-align: center;
  padding: 24px;
  color: #c0c4cc;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

/* 断言 */
.assertions-section {
  padding: 4px 0;
}
.assertion-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.empty-hint-text {
  color: #c0c4cc;
  font-size: 12px;
  margin-top: 4px;
}

/* Cookie 编辑器 */
.cookie-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.cookie-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: #f0f9eb;
  border: 1px solid #e1f3d8;
  border-radius: 6px;
}
.cookie-row:hover {
  border-color: #b3e19d;
}
.cookie-index {
  width: 24px;
  height: 24px;
  background: #67C23A;
  color: white;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* ================= 明亮清爽列表页 UI ================= */
.web-testcase-container {
  padding: 20px;
  min-height: calc(100vh - 84px);
  background: #f5f7fa;
}

.glass-card {
  background: #ffffff !important;
  border: 1px solid #e4e7ed !important;
  border-radius: 12px !important;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06) !important;
  overflow: hidden;
  color: #303133;
}

.glass-card :deep(.el-card__header) {
  padding: 0 !important;
  border-bottom: 1px solid #ebeef5 !important;
  background: linear-gradient(135deg, #f0f7ff, #ffffff);
}

.page-hero {
  padding: 22px 26px;
}

.hero-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.hero-title {
  display: flex;
  align-items: center;
  gap: 16px;
}

.hero-icon-wrap {
  width: 50px;
  height: 50px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e6f2ff, #d9ecff);
  border: 1px solid #c6e2ff;
  color: #409eff;
}

.hero-title-text h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  letter-spacing: 0.3px;
}

.hero-title-text p {
  margin: 4px 0 0;
  font-size: 13px;
  color: #606266;
}

.hero-btn {
  background: #409eff !important;
  border: none !important;
  font-weight: 500;
  padding: 0 20px;
  height: 40px;
}

.hero-btn:hover {
  background: #66b1ff !important;
}

.hero-stats {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid #ebeef5;
}

.stat-item {
  display: flex;
  flex-direction: column;
  min-width: 90px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  line-height: 1;
  margin-bottom: 6px;
}

.stat-value.ai { color: #e6a23c; }
.stat-value.playwright { color: #409eff; }
.stat-value.success { color: #67c23a; }

.stat-label {
  font-size: 12px;
  color: #909399;
}

.stat-divider {
  width: 1px;
  height: 36px;
  background: #e4e7ed;
  margin: 0 16px;
}

.page-toolbar {
  padding: 16px 26px;
  border-bottom: 1px solid #ebeef5;
  background: #fafbfc;
}

.toolbar-form :deep(.el-form-item) {
  margin-bottom: 0;
  margin-right: 14px;
}

.toolbar-form :deep(.el-form-item__label) {
  color: #606266;
  font-weight: 500;
  padding-right: 8px;
}

.toolbar-form :deep(.el-input__wrapper),
.toolbar-form :deep(.el-select .el-input__wrapper) {
  background: #ffffff !important;
  box-shadow: 0 0 0 1px #dcdfe6 inset !important;
  color: #303133;
}

.toolbar-form :deep(.el-input__inner) {
  color: #303133;
}

.toolbar-form :deep(.el-input__inner::placeholder) {
  color: #a8abb2;
}

.toolbar-btn-primary {
  background: #409eff !important;
  border: none !important;
}

.toolbar-btn-primary:hover {
  background: #66b1ff !important;
}

.toolbar-btn-default {
  background: #ffffff !important;
  border: 1px solid #dcdfe6 !important;
  color: #606266 !important;
}

.toolbar-btn-default:hover {
  color: #409eff !important;
  border-color: #c6e2ff !important;
  background: #f5f7fa !important;
}

.page-content {
  padding: 22px 26px;
  background: #ffffff;
}

.data-table {
  background: #ffffff !important;
}

.data-table :deep(.el-table__header-wrapper th.el-table__cell) {
  background: #f5f7fa !important;
  color: #606266 !important;
  font-weight: 600;
  border-bottom: 1px solid #ebeef5 !important;
  padding: 12px 0;
}

.data-table :deep(.el-table__body-wrapper td.el-table__cell) {
  background: #ffffff !important;
  color: #303133;
  border-bottom: 1px solid #ebeef5 !important;
  padding: 14px 0;
}

.data-table :deep(.el-table__row:hover td.el-table__cell) {
  background: #f5f7fa !important;
}

.data-table :deep(.el-table__empty-block) {
  background: #ffffff;
}

/* 解决切换时白色加载闪烁 */
.data-table :deep(.el-loading-mask) {
  background-color: rgba(255, 255, 255, 0.85) !important;
  backdrop-filter: blur(2px);
}

.data-table :deep(.el-loading-spinner .circular) {
  width: 28px;
  height: 28px;
}

.page-pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.page-pagination :deep(.el-pagination__total),
.page-pagination :deep(.el-pagination__jump) {
  color: #606266;
}

.page-pagination :deep(.el-pager li) {
  background: #ffffff;
  border: 1px solid #e4e7ed;
  color: #606266;
}

.page-pagination :deep(.el-pager li.is-active) {
  background: #409eff;
  border-color: #409eff;
  color: #fff;
}

.page-pagination :deep(.el-pagination button) {
  background: #ffffff;
  border: 1px solid #e4e7ed;
  color: #606266;
}

.empty-state-glass {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 72px 20px;
  text-align: center;
  background: #fafbfc;
  border-radius: 12px;
  border: 1px dashed #dcdfe6;
}

.empty-icon-wrap {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ecf5ff;
  border: 1px solid #d9ecff;
  color: #409eff;
  margin-bottom: 20px;
}

.empty-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.empty-description {
  font-size: 14px;
  color: #606266;
  margin-bottom: 24px;
  max-width: 420px;
  line-height: 1.6;
}

.empty-actions .el-button {
  background: #409eff !important;
  border: none !important;
}

/* 修复弹窗与表单 */
.web-testcase-dialog :deep(.el-dialog) {
  background: #ffffff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
}

.web-testcase-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid #ebeef5;
  padding: 18px 24px;
  margin-right: 0;
}

.web-testcase-dialog :deep(.el-dialog__title) {
  color: #303133;
  font-weight: 600;
}

.web-testcase-dialog :deep(.el-divider__text) {
  background: #ffffff;
  color: #909399;
}

.web-testcase-dialog :deep(.el-divider) {
  border-color: #ebeef5;
}

/* 执行结果 */
.screenshot-gallery {
  margin-bottom: 16px;
}
.log-output pre {
  background: #f5f7fa;
  color: #303133;
  padding: 12px 16px;
  border-radius: 6px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  line-height: 1.6;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 通用 */
.option-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}
.option-dot--draft { background: #909399; }
.option-dot--active { background: #67c23a; }
.option-dot--inactive { background: #f56c6c; }

/* 执行结果面板已移除，改用 ElMessage 轻量提示 */


</style>
