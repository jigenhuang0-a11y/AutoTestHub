<template>
  <div class="data-factory-container">
    <!-- 顶部工具栏 -->
    <div class="factory-header">
      <h3>数据工厂</h3>
      
      <!-- 版本切换Tab -->
      <el-tabs 
        v-model="currentVersion" 
        class="version-tabs"
        @tab-change="handleVersionChange"
      >
        <el-tab-pane name="ecommerce">
          <template #label>
            <span class="version-label">
              <el-icon><ShoppingCart /></el-icon>
              跨境电商版
            </span>
          </template>
        </el-tab-pane>
        <el-tab-pane name="fintech">
          <template #label>
            <span class="version-label">
              <el-icon><Money /></el-icon>
              金融科技版
            </span>
          </template>
        </el-tab-pane>
      </el-tabs>
      
      <el-button type="primary" @click="showCreateDialog">
        <el-icon><Plus /></el-icon> 新建数据集
      </el-button>
    </div>

    <div class="factory-content">
      <!-- 左侧：数据集列表 + 模板中心 -->
      <div class="dataset-panel">
        <el-tabs v-model="leftPanelTab" class="panel-tabs">
          <el-tab-pane label="数据集" name="datasets">
            <div class="panel-header">
              <span>数据集列表</span>
              <el-input
                v-model="searchKeyword"
                placeholder="搜索数据集..."
                size="small"
                clearable
                style="width: 200px;"
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
            </div>

            <div class="dataset-list" v-loading="loading">
              <el-empty v-if="filteredDatasets.length === 0" description="暂无数据集" :image-size="60" />

              <div
                v-for="dataset in filteredDatasets.filter(d => d && d.id)"
                :key="dataset.id"
                class="dataset-item"
                :class="{ active: selectedDataset?.id === dataset.id }"
                @click="(e) => { 
                  console.log('=== 点击事件触发 ===');
                  console.log('Dataset from v-for:', JSON.stringify(dataset, null, 2));
                  console.log('Dataset ID:', dataset?.id, 'type:', typeof dataset?.id);
                  selectDataset(dataset);
                }"
              >
                <div class="item-info">
                  <div class="item-name">{{ dataset.displayName || dataset.name }}</div>
                  <!-- 显示字段Title（业务关键词列表） -->
                  <el-tooltip 
                    v-if="dataset.generation_config && dataset.generation_config.scenario && extractFieldTitle(dataset.generation_config.scenario)"
                    :content="extractFieldTitle(dataset.generation_config.scenario)"
                    placement="top"
                  >
                    <div class="item-field-title">
                      <el-icon size="12"><List /></el-icon>
                      字段Title: {{ extractFieldTitle(dataset.generation_config.scenario) }}
                    </div>
                  </el-tooltip>
                  <div v-if="dataset.purpose" class="item-purpose">
                    <el-icon size="12"><Document /></el-icon>
                    {{ dataset.purpose }}
                  </div>
                  <div class="item-meta">
                    <el-tag size="small" :type="getTypeColor(dataset.dataset_type)">
                      {{ getTypeLabel(dataset.dataset_type) }}
                    </el-tag>
                    <span class="item-count">{{ dataset.record_count }} 条</span>
                  </div>
                </div>
                <div class="item-actions">
                  <el-button 
                    size="small"
                    @click.stop="handleDatasetAction('export', dataset)"
                    title="导出"
                  >
                    <el-icon><Download /></el-icon>
                    导出
                  </el-button>
                  <el-button 
                    size="small"
                    type="danger"
                    plain
                    @click.stop="handleDatasetAction('delete', dataset)"
                    title="删除"
                  >
                    <el-icon><Delete /></el-icon>
                    删除
                  </el-button>
                </div>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="模板中心" name="templates">
            <div class="panel-header">
              <span>预置业务模板</span>
              <el-select v-model="templateFilter" size="small" placeholder="全部" style="width: 120px" clearable>
                <el-option label="订单" value="order" />
                <el-option label="物流" value="logistics" />
                <el-option label="售后" value="after_sales" />
                <el-option label="商家" value="merchant" />
              </el-select>
            </div>

            <div class="template-list" v-loading="templatesLoading">
              <el-empty v-if="presetTemplates.length === 0" description="暂无模板" :image-size="60" />

              <div
                v-for="template in filteredTemplates"
                :key="template.id"
                class="template-item"
                @click="loadTemplateToDataset(template)"
              >
                <div class="template-icon">
                  <el-icon :size="24"><Document /></el-icon>
                </div>
                <div class="template-info">
                  <div class="template-name">{{ template.name }}</div>
                  <div class="template-desc">{{ template.description }}</div>
                  <div class="template-meta">
                    <el-tag size="small" type="primary">{{ getBusinessTypeLabel(template.business_type) }}</el-tag>
                    <span class="usage-count">已使用 {{ template.usage_count }} 次</span>
                  </div>
                </div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- 中间：造数配置区 -->
      <div class="config-panel">
        <el-tabs v-model="activeTab" type="border-card">
          <!-- Tab 1: 结构化数据生成（仅当选中结构化数据集或未选中数据集时显示） -->
          <el-tab-pane 
            v-if="!selectedDataset || selectedDataset.dataset_type === 'structured'"
            label="结构化数据生成" 
            name="structured"
          >
            <div class="tab-content" :key="'structured-' + selectedDataset?.id">
              <el-form :model="structuredForm" label-width="120px" size="default">
                <!-- 数据集名称（仅当选中数据集时显示） -->
                <el-form-item v-if="selectedDataset" label="数据集名称">
                  <el-input
                    v-model="selectedDataset.name"
                    :placeholder="'请输入数据集名称'"
                    @change="handleDatasetNameChange"
                  />
                  <el-tag 
                    v-if="selectedDataset.template_id" 
                    size="small" 
                    type="warning" 
                    style="margin-top: 4px;"
                  >
                    <el-icon><Link /></el-icon> 引用自模板（可修改名称）
                  </el-tag>
                </el-form-item>

                <el-form-item label="业务域">
                  <el-select v-model="structuredForm.business_domain" placeholder="选择业务域" style="width: 100%">
                    <el-option label="订单数据" value="order" />
                    <el-option label="用户数据" value="user" />
                    <el-option label="物流数据" value="logistics" />
                    <el-option label="售后数据" value="after_sales" />
                    <el-option label="商家数据" value="merchant" />
                  </el-select>
                </el-form-item>

                <el-form-item label="数据量">
                  <el-input-number v-model="structuredForm.count" :min="1" :max="10000" style="width: 100%" />
                </el-form-item>

                <el-form-item label="边界测试">
                  <el-checkbox-group v-model="structuredForm.boundary_tests">
                    <el-checkbox label="null">空值</el-checkbox>
                    <el-checkbox label="empty">空字符串</el-checkbox>
                    <el-checkbox label="overflow">超长数据</el-checkbox>
                    <el-checkbox label="special">特殊字符</el-checkbox>
                    <el-checkbox label="negative">负数</el-checkbox>
                  </el-checkbox-group>
                </el-form-item>

                <el-form-item label="导出格式">
                  <el-radio-group v-model="structuredForm.export_format">
                    <el-radio label="json">JSON</el-radio>
                    <el-radio label="sql">SQL</el-radio>
                    <el-radio label="csv">CSV</el-radio>
                    <el-radio label="excel">Excel</el-radio>
                  </el-radio-group>
                </el-form-item>

                <el-form-item>
                  <el-button type="primary" @click="generateStructuredData" :loading="generating">
                    <el-icon><MagicStick /></el-icon> 生成数据
                  </el-button>
                </el-form-item>
              </el-form>

              <!-- 字段定义器 -->
              <el-divider content-position="left">字段定义</el-divider>
              <div class="field-definitions">
                <el-alert
                  v-if="structuredForm.fields.length > 0"
                  :title="`已从模板加载 ${structuredForm.fields.length} 个字段定义`"
                  type="info"
                  :closable="false"
                  show-icon
                  style="margin-bottom: 12px;"
                />
                <!-- 字段定义列表：固定高度，内部滚动，按钮在底部 -->
                <div class="fields-list-box">
                  <div class="fields-list-header">
                    <span class="fields-list-header-cell" style="width: 120px;">字段名</span>
                    <span class="fields-list-header-cell" style="width: 140px;">描述</span>
                    <span class="fields-list-header-cell" style="width: 90px;">类型</span>
                    <span class="fields-list-header-cell" style="width: 50px;">可空</span>
                    <span class="fields-list-header-cell" style="width: 50px;">操作</span>
                  </div>
                  <div class="fields-list-body">
                    <div
                      v-for="(field, index) in structuredForm.fields"
                      :key="index"
                      class="fields-list-row"
                    >
                      <div class="fields-list-cell" style="width: 120px;">
                        <el-input v-model="field.name" size="small" placeholder="字段名" />
                      </div>
                      <div class="fields-list-cell" style="width: 140px;">
                        <el-input v-model="field.description" size="small" placeholder="字段说明" />
                      </div>
                      <div class="fields-list-cell" style="width: 90px;">
                        <el-select v-model="field.type" size="small" style="width: 100%;">
                          <el-option label="字符串" value="string" />
                          <el-option label="整数" value="integer" />
                          <el-option label="小数" value="decimal" />
                          <el-option label="布尔" value="boolean" />
                          <el-option label="日期" value="date" />
                        </el-select>
                      </div>
                      <div class="fields-list-cell" style="width: 50px; justify-content: center;">
                        <el-checkbox v-model="field.nullable" />
                      </div>
                      <div class="fields-list-cell" style="width: 50px; justify-content: center;">
                        <el-button size="small" type="danger" link @click="removeField(index)">
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </div>
                    </div>
                  </div>
                  <div class="fields-list-footer">
                    <el-button
                      type="primary"
                      size="small"
                      @click="addField"
                      style="width: 100%;"
                    >
                      <el-icon><Plus /></el-icon> 添加字段
                    </el-button>
                  </div>
                </div>
              </div>
            </div>
          </el-tab-pane>

          <!-- Tab 2: LLM评测数据生成（仅当选中LLM数据集时显示） -->
          <el-tab-pane 
            v-if="selectedDataset && selectedDataset.dataset_type === 'llm_eval'"
            label="LLM评测数据" 
            name="llm_eval"
          >
            <div class="tab-content">
              <el-form :model="llmForm" label-width="120px" size="default">
                <el-form-item label="数据集名称">
                  <el-input
                    v-model="selectedDataset.name"
                    :disabled="!!selectedDataset.template_id"
                    :placeholder="selectedDataset.template_id ? '模板引用，不可编辑' : '请输入数据集名称'"
                    @change="handleDatasetNameChange"
                  />
                  <el-tag 
                    v-if="selectedDataset.template_id" 
                    size="small" 
                    type="info" 
                    style="margin-top: 4px;"
                  >
                    <el-icon><Link /></el-icon> 引用自模板
                  </el-tag>
                </el-form-item>

                <el-form-item label="AI 模型">
                  <el-select v-model="selectedModelId" placeholder="选择 AI 底座模型" style="width: 100%">
                    <el-option v-for="m in aiModels" :key="m.id" :label="`${m.name}（${m.provider}）`" :value="String(m.id)" />
                    <el-option v-if="!aiModels.length" label="未配置模型（将降级 mock）" value="" disabled />
                  </el-select>
                </el-form-item>

                <el-form-item label="场景描述">
                  <el-input
                    v-model="llmForm.scenario"
                    type="textarea"
                    :rows="4"
                    :placeholder="currentVersion === 'fintech' 
                      ? '标题：对公账户开户、网银限额调整、代发薪资失败场景\n内容：基于金融科技对公结算业务智能客服 Agent 对话测试，包含企业账户开立备案、网银转账限额变更、跨行汇款退回处理、批量代发薪资异常排查'
                      : '标题：退货、换货、产品破损索赔、漏发补发场景\n内容：基于跨境电商全品类售后场景，包含商品质量问题退货、尺码不符换货、物流损坏索赔、仓库漏发补发等处理流程'"
                  />
                </el-form-item>

                <el-form-item label="正样本数量">
                  <el-input-number v-model="llmForm.positive_count" :min="0" :max="500" style="width: 100%" />
                </el-form-item>

                <el-form-item label="负样本数量">
                  <el-input-number v-model="llmForm.negative_count" :min="0" :max="500" style="width: 100%" />
                </el-form-item>

                <el-form-item label="边界案例数量">
                  <el-input-number v-model="llmForm.boundary_count" :min="0" :max="200" style="width: 100%" />
                </el-form-item>

                <el-form-item label="语言">
                  <el-checkbox-group v-model="llmForm.languages">
                    <el-checkbox label="zh">中文</el-checkbox>
                    <el-checkbox label="en">英文</el-checkbox>
                  </el-checkbox-group>
                </el-form-item>

                <el-form-item>
                  <el-button type="primary" @click="generateLLMDataset" :loading="generating">
                    <el-icon><MagicStick /></el-icon> 调用 AI 生成
                  </el-button>
                </el-form-item>
              </el-form>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- 右侧：数据预览区 -->
      <div class="preview-panel">
        <div class="panel-header">
          <span>数据预览</span>
          <div>
            <el-tag v-if="selectedDataset" size="small">{{ selectedDataset.name }}</el-tag>
            <el-button-group v-if="selectedDataset && previewData.length > 0" style="margin-left: 8px;">
              <el-button size="small" @click="addPreviewRow" title="添加行">
                <el-icon><Plus /></el-icon>
              </el-button>
              <el-button size="small" @click="deleteSelectedRows" :disabled="selectedPreviewRows.length === 0" title="删除选中">
                <el-icon><Delete /></el-icon>
              </el-button>
            </el-button-group>
          </div>
        </div>

        <div class="preview-content" v-if="selectedDataset">
          <el-alert
            v-if="selectedDataset.status === 'preview'"
            type="info"
            :closable="false"
            show-icon
            style="margin-bottom: 12px; font-size: 12px;"
          >
            <template #default>
              当前为模板预览数据，您可以直接编辑或点击"生成数据"创建完整数据集
            </template>
          </el-alert>
          
          <el-table 
            :data="currentPagePreviewData" 
            border 
            size="small" 
            max-height="500"
            @selection-change="handlePreviewSelectionChange"
          >
            <el-table-column type="selection" width="40" fixed />
            <el-table-column
              v-for="col in previewColumns"
              :key="col.prop"
              :label="col.label"
              :width="col.width"
              show-overflow-tooltip
            >
              <template #default="{ row, $index }">
                <el-input
                  v-if="isEditableField(col.prop)"
                  v-model="row[col.prop]"
                  size="small"
                  placeholder="输入值"
                  @blur="onCellBlur(row, col.prop)"
                />
                <span v-else>{{ formatCellValue(row[col.prop], col.prop) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="60" align="center" fixed="right">
              <template #default="{ $index }">
                <el-button size="small" type="danger" link @click="removePreviewRow($index)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 分页组件 -->
          <div class="preview-pagination" v-if="previewPagination.total > previewPagination.pageSize">
            <el-pagination
              v-model:current-page="previewPagination.currentPage"
              v-model:page-size="previewPagination.pageSize"
              :total="previewPagination.total"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              small
              @size-change="handlePageSizeChange"
              @current-change="handlePageChange"
            />
          </div>

          <div class="preview-stats">
            <el-descriptions :column="2" size="small" border>
              <el-descriptions-item label="记录数">
                <el-tag size="small" type="primary">{{ previewData.length }}</el-tag>
                <span style="color: #909399; font-size: 12px;"> / {{ selectedDataset.record_count }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="文件大小">{{ formatFileSize(selectedDataset.file_size) }}</el-descriptions-item>
              <el-descriptions-item label="创建时间">{{ formatDate(selectedDataset.created_at) }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="getStatusColor(selectedDataset.status)" size="small">
                  {{ getStatusLabel(selectedDataset.status) }}
                </el-tag>
              </el-descriptions-item>
            </el-descriptions>
            
            <div v-if="selectedDataset.status === 'preview'" style="margin-top: 12px; text-align: center;">
              <el-button type="success" size="small" @click="savePreviewAsDataset">
                <el-icon><Check /></el-icon> 保存为数据集
              </el-button>
            </div>
          </div>
        </div>

        <el-empty v-else description="请选择一个数据集查看预览" :image-size="80" />
      </div>
    </div>

    <!-- 新建数据集对话框 -->
    <el-dialog v-model="createDialogVisible" title="新建数据集" width="500px">
      <el-form :model="newDataset" label-width="100px">
        <el-form-item label="数据集名称">
          <el-input v-model="newDataset.name" placeholder="请输入数据集名称" />
        </el-form-item>
        <el-form-item label="数据类型">
          <el-select v-model="newDataset.dataset_type" placeholder="选择数据类型" style="width: 100%">
            <el-option label="结构化数据" value="structured" />
            <el-option label="LLM评测数据" value="llm_eval" />
          </el-select>
        </el-form-item>
        <el-form-item label="业务域">
          <el-select v-model="newDataset.business_domain" placeholder="选择业务域（可选）" style="width: 100%" clearable>
            <el-option label="订单" value="order" />
            <el-option label="用户" value="user" />
            <el-option label="物流" value="logistics" />
            <el-option label="售后" value="after_sales" />
            <el-option label="商家" value="merchant" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newDataset.description" type="textarea" :rows="3" placeholder="数据集描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="createDataset">创建</el-button>
      </template>
    </el-dialog>

    <!-- 版本历史对话框 -->
    <el-dialog v-model="versionsDialogVisible" title="版本历史" width="700px">
      <div v-if="selectedDataset" class="versions-container">
        <div class="versions-header">
          <h4>{{ selectedDataset.name }}</h4>
          <el-button type="primary" size="small" @click="showCreateVersionDialog">
            <el-icon><Plus /></el-icon> 创建新版本
          </el-button>
        </div>

        <el-timeline class="versions-timeline">
          <el-timeline-item
            v-for="version in versions"
            :key="version.id"
            :timestamp="formatDate(version.created_at)"
            placement="top"
            :type="version.is_current ? 'success' : 'primary'"
          >
            <div class="version-card" :class="{ current: version.is_current }">
              <div class="version-header">
                <span class="version-number">{{ version.version_number }}</span>
                <el-tag v-if="version.is_current" size="small" type="success">当前版本</el-tag>
              </div>
              <div class="version-description">{{ version.description || '无说明' }}</div>
              <div class="version-meta">
                <span>记录数: {{ version.snapshot_records_count }}</span>
                <span>创建人: {{ version.created_by_username }}</span>
              </div>
              <div class="version-actions" v-if="!version.is_current">
                <el-button size="small" type="primary" @click="rollbackToVersion(version)">
                  回滚到此版本
                </el-button>
              </div>
            </div>
          </el-timeline-item>
        </el-timeline>

        <el-empty v-if="versions.length === 0" description="暂无版本历史" :image-size="80" />
      </div>
    </el-dialog>

    <!-- 创建版本对话框 -->
    <el-dialog v-model="createVersionDialogVisible" title="创建新版本" width="500px">
      <el-form label-width="100px">
        <el-form-item label="版本说明">
          <el-input
            v-model="newVersionDescription"
            type="textarea"
            :rows="4"
            placeholder="请描述本次变更内容..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVersionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="createNewVersion" :loading="creatingVersion">创建</el-button>
      </template>
    </el-dialog>

    <!-- 批量导出对话框 -->
    <el-dialog v-model="batchExportDialogVisible" title="批量导出数据集" width="600px">
      <div class="batch-export-container">
        <p class="export-tip">请选择要导出的数据集：</p>
        <el-table
          :data="datasets"
          @selection-change="handleBatchExportSelection"
          max-height="400"
        >
          <el-table-column type="selection" width="55" />
          <el-table-column prop="name" label="数据集名称" show-overflow-tooltip />
          <el-table-column prop="record_count" label="记录数" width="100" />
          <el-table-column prop="dataset_type" label="类型" width="120">
            <template #default="{ row }">
              <el-tag size="small" :type="getTypeColor(row.dataset_type)">
                {{ getTypeLabel(row.dataset_type) }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>

        <div class="export-options">
          <el-radio-group v-model="batchExportFormat">
            <el-radio label="json">JSON格式</el-radio>
            <el-radio label="sql">SQL格式</el-radio>
            <el-radio label="csv">CSV格式</el-radio>
          </el-radio-group>
        </div>
      </div>
      <template #footer>
        <el-button @click="batchExportDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="executeBatchExport" :loading="exporting">
          导出 ({{ batchExportSelected.length }}个)
        </el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
defineOptions({ name: 'DataFactory' })

import { ref, computed, onMounted, onActivated, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, More, Delete, MagicStick, Document, Refresh, Check, ShoppingCart, Money } from '@element-plus/icons-vue'
import { aiBaseAPI } from '@/api'

// 状态
const loading = ref(false)

// AI 底座模型选择（供 LLM 造数走真实底座）
const aiModels = ref([])
const selectedModelId = ref('')
async function loadAiModels() {
  try {
    const res = await aiBaseAPI.listModels()
    aiModels.value = res.items || res.results || []
    if (aiModels.value.length) {
      const active = aiModels.value.find(m => m.is_enabled)
      selectedModelId.value = String(active ? active.id : aiModels.value[0].id)
    }
  } catch (e) {
    aiModels.value = []
  }
}
onMounted(loadAiModels)
// 从场景描述中提取标题，用于自动生成数据集名称
const extractScenarioTitle = (scenario) => {
  if (!scenario) return 'LLM评测数据集'
  const firstLine = scenario.split(/\r?\n/)[0].trim()
  const title = firstLine.replace(/^标题[：:]\s*/, '').trim()
  return title.slice(0, 28) || 'LLM评测数据集'
}

const generating = ref(false)
const templatesLoading = ref(false)
const creatingVersion = ref(false)
const exporting = ref(false)
const searchKeyword = ref('')
const activeTab = ref('structured')
const leftPanelTab = ref('datasets')
const templateFilter = ref('')
const selectedDataset = ref(null)
const createDialogVisible = ref(false)
const versionsDialogVisible = ref(false)
const createVersionDialogVisible = ref(false)
const batchExportDialogVisible = ref(false)
const newVersionDescription = ref('')
const batchExportFormat = ref('json')
const batchExportSelected = ref([])
const selectedPreviewRows = ref([]) // 预览数据选中的行

// 版本管理
const currentVersion = ref('ecommerce') // 当前版本：'ecommerce' | 'fintech'

// 数据集列表
const datasets = ref([])

// 预置模板列表
const presetTemplates = ref([])

// 版本历史
const versions = ref([])

// 预览数据
const previewData = ref([])
const previewColumns = ref([])
const previewPagination = ref({
  currentPage: 1,
  pageSize: 20, // 每页显示20条
  total: 0
})

// 新建数据集表单
const newDataset = ref({
  name: '',
  dataset_type: 'structured',
  business_domain: '',
  description: ''
})

// 结构化数据生成表单
const structuredForm = ref({
  business_domain: 'order',
  count: 100,
  boundary_tests: [],
  export_format: 'json',
  fields: [
    { name: 'order_id', type: 'string', nullable: false },
    { name: 'amount', type: 'decimal', nullable: false },
    { name: 'currency', type: 'string', nullable: false },
  ]
})

// LLM评测数据生成表单
const llmForm = ref({
  scenario: '',
  positive_count: 1,
  negative_count: 1,
  boundary_count: 1,
  languages: ['zh']
})

// 过滤后的数据集列表（按版本隔离 + 为重复的模板名称添加编号）
const filteredDatasets = computed(() => {
  // 验证所有数据集都有id字段
  const invalidDatasets = datasets.value.filter(d => !d || !d.id)
  if (invalidDatasets.length > 0) {
    console.warn('[WARN] Found datasets without id in filteredDatasets:', invalidDatasets)
  }
  
  // 首先按版本过滤（关键：版本隔离）
  let result = datasets.value.filter(ds => {
    // 如果数据集有version字段，按当前版本过滤
    if (ds.version) {
      return ds.version === currentVersion.value
    }
    // 如果没有version字段（旧数据），默认归为ecommerce版本
    return currentVersion.value === 'ecommerce'
  })
  
  // 然后按搜索关键词过滤
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    result = result.filter(ds =>
      ds.name.toLowerCase().includes(keyword) ||
      (ds.description && ds.description.toLowerCase().includes(keyword))
    )
  }
  
  // 为重复的模板名称添加编号
  // 策略：从后往前遍历，最新的（最上面的）不编号，旧的（下面的）添加编号
  const nameCountMap = {}
  const resultWithDisplayNames = []
  
  // 从后往前处理（先处理旧的，再处理新的）
  // 按 name + dataset_type 分组编号，不同类型不互斥
  for (let i = result.length - 1; i >= 0; i--) {
    const dataset = result[i]
    const groupKey = `${dataset.name}::${dataset.dataset_type || 'unknown'}`

    // 如果这个名称+类型之前出现过（在更旧的数据集中），添加编号
    if (nameCountMap[groupKey]) {
      nameCountMap[groupKey]++
      resultWithDisplayNames.unshift({
        ...dataset,
        displayName: `${dataset.name} (${nameCountMap[groupKey]})`
      })
    } else {
      nameCountMap[groupKey] = 1
      resultWithDisplayNames.unshift({
        ...dataset,
        displayName: dataset.name
      })
    }
  }
  
  return resultWithDisplayNames
})

// 过滤后的模板列表（按版本和业务类型过滤）
const filteredTemplates = computed(() => {
  // 首先按版本过滤
  let templates = presetTemplates.value.filter(t => t.version === currentVersion.value)
  
  // 然后按业务类型过滤（如果有选择）
  if (templateFilter.value) {
    templates = templates.filter(t => t.business_type === templateFilter.value)
  }
  
  return templates
})

// 当前页的预览数据（用于表格显示）
const currentPagePreviewData = computed(() => {
  const start = (previewPagination.value.currentPage - 1) * previewPagination.value.pageSize
  const end = start + previewPagination.value.pageSize
  return previewData.value.slice(start, end)
})

// 处理分页变化
const handlePageChange = (page) => {
  previewPagination.value.currentPage = page
}

const handlePageSizeChange = (size) => {
  previewPagination.value.pageSize = size
  previewPagination.value.currentPage = 1 // 重置到第一页
}

// 加载数据集列表
const loadDatasets = async () => {
  loading.value = true
  try {
    // TODO: 调用API获取数据集列表
    // const res = await dataFactoryAPI.list()
    // datasets.value = res.results || []

    // 优先从localStorage读取用户数据集
    const savedDatasets = localStorage.getItem('data_factory_datasets')
    
    if (savedDatasets) {
      // 使用用户保存的数据集
      let parsed = JSON.parse(savedDatasets)
      
      // 强制修复：移除所有没有id或name的数据集
      const beforeCount = parsed.length
      parsed = parsed.filter(d => {
        if (!d || !d.id || !d.name) {
          console.warn('[FIX] Removing invalid dataset:', d)
          return false
        }
        return true
      })
      const afterCount = parsed.length
      
      if (beforeCount !== afterCount) {
        console.log(`[FIX] Removed ${beforeCount - afterCount} invalid datasets`)
        saveDatasetsToStorage()
      }
      
      // 关键修复：为所有数据集添加version和dataset_type字段（版本隔离）
      let needsSave = false
      parsed.forEach(dataset => {
        // 修复1：添加version字段
        if (!dataset.version) {
          // 如果没有version字段，根据业务域或场景描述推断版本
          const fintechDomains = ['bank_transaction', 'credit_card', 'loan_application', 'investment_product']
          const fintechKeywords = ['金融', '银行', '账户', '贷款', '信用卡', '投资', '理财', '对公', '网银', '转账', '汇款', '薪资', '风控', '授信', '额度', '抵押', '存款', '取款']
          
          // 判断1：根据业务域判断
          const isFintechByDomain = fintechDomains.includes(dataset.business_domain)
          
          // 判断2：根据场景描述判断（LLM评测数据集没有business_domain）
          const scenario = dataset.generation_config?.scenario || dataset.description || dataset.name || ''
          const isFintechByScenario = fintechKeywords.some(kw => scenario.includes(kw))
          
          // 判断3：根据数据内容判断（检查previewData或字段名）
          const firstRecord = dataset.records?.[0] || dataset.data?.[0]
          const recordStr = firstRecord ? JSON.stringify(firstRecord) : ''
          const isFintechByRecord = fintechKeywords.some(kw => recordStr.includes(kw))
          
          if (isFintechByDomain || isFintechByScenario || isFintechByRecord) {
            dataset.version = 'fintech'
          } else {
            dataset.version = 'ecommerce'
          }
          needsSave = true
          console.log(`[FIX] Added version to dataset "${dataset.name}": ${dataset.version} (domain=${isFintechByDomain}, scenario=${isFintechByScenario}, record=${isFintechByRecord})`)
        }
        
        // 修复2：确保dataset_type字段存在且正确
        if (!dataset.dataset_type) {
          // 如果没有dataset_type字段，根据business_domain推断类型
          if (dataset.business_domain) {
            dataset.dataset_type = 'structured'
          } else {
            // 默认设为结构化
            dataset.dataset_type = 'structured'
          }
          needsSave = true
          console.log(`[FIX] Added dataset_type to dataset "${dataset.name}": ${dataset.dataset_type}`)
        }
      })
      
      if (needsSave) {
        saveDatasetsToStorage()
      }
      
      datasets.value = parsed
      
      console.log('Loaded datasets from localStorage:', datasets.value.length)
      
      // 详细检查每个数据集的结构
      console.log('[DEBUG] Checking dataset structures:')
      datasets.value.forEach((d, idx) => {
        console.log(`  [${idx}] Has ID: ${!!d.id}, ID value: ${d.id}, Name: ${d.name}, Type: ${typeof d.id}, Version: ${d.version}`)
        if (!d.id) {
          console.error(`  [${idx}] INVALID DATASET:`, JSON.stringify(d, null, 2))
        }
      })
      
      console.log('[DEBUG] Dataset IDs summary:', datasets.value.map(d => ({ id: d.id, name: d.name, hasId: !!d.id, version: d.version })))
      
      // 恢复之前选中的数据集
      const savedSelectedId = localStorage.getItem('data_factory_selected_dataset_id')
      if (savedSelectedId && datasets.value.length > 0) {
        const selectedId = String(savedSelectedId)
        console.log('[DEBUG] Trying to restore saved ID:', selectedId)
        const foundDataset = datasets.value.find(d => String(d.id) === selectedId)
        if (foundDataset && foundDataset.id) {
          console.log('[DEBUG] Found matching dataset:', foundDataset.name, 'ID:', foundDataset.id)
          await selectDataset(foundDataset)
        } else {
          console.log('[DEBUG] Saved ID not found or invalid, selecting first valid dataset')
          // 如果之前选中的数据集不存在或无效，选择第一个有效的数据集
          const firstValid = datasets.value.find(d => d && d.id)
          if (firstValid) {
            await selectDataset(firstValid)
          }
        }
      } else if (datasets.value.length > 0) {
        // 如果没有保存的选中ID，选择第一个有效的数据集
        console.log('[DEBUG] No saved selection, selecting first valid dataset')
        const firstValid = datasets.value.find(d => d && d.id)
        if (firstValid) {
          await selectDataset(firstValid)
        }
      }
    } else {
      // 首次加载，数据集列表为空（不使用模拟数据）
      datasets.value = []
      console.log('Initialized with empty dataset list')
    }
  } catch (error) {
    console.error('Load datasets error:', error)
    ElMessage.error('加载数据集失败')
  } finally {
    loading.value = false
  }
}

// 保存数据集到localStorage
const saveDatasetsToStorage = () => {
  try {
    localStorage.setItem('data_factory_datasets', JSON.stringify(datasets.value))
    console.log('Saved datasets to localStorage:', datasets.value.length)
  } catch (error) {
    console.error('Save datasets error:', error)
  }
}

// 处理数据集名称变化（当用户手动修改名称时调用）
const handleDatasetNameChange = () => {
  if (selectedDataset.value && selectedDataset.value.id) {
    // 同步到datasets列表
    const idx = datasets.value.findIndex(d => d.id === selectedDataset.value.id)
    if (idx !== -1) {
      datasets.value[idx].name = selectedDataset.value.name
    }
    // 保存到localStorage
    saveDatasetsToStorage()
    console.log('[DEBUG] Dataset name updated to:', selectedDataset.value.name)
  }
}

// 每个数据集独立的预览状态缓存，避免不同数据集/类型共用 previewData
const previewStateCache = new Map()

const saveCurrentPreviewState = () => {
  const ds = selectedDataset.value
  if (!ds || !ds.id) return
  previewStateCache.set(String(ds.id), {
    previewData: previewData.value,
    previewColumns: previewColumns.value,
    previewPagination: { ...previewPagination.value }
  })
  console.log('[DEBUG] Cached preview state for dataset:', ds.id)
}

const restorePreviewState = (dataset) => {
  const key = String(dataset.id)
  if (previewStateCache.has(key)) {
    const cached = previewStateCache.get(key)
    previewData.value = cached.previewData || []
    previewColumns.value = cached.previewColumns || []
    previewPagination.value = { ...previewPagination.value, ...(cached.previewPagination || {}) }
    console.log('[DEBUG] Restored preview state for dataset:', dataset.id, 'records:', previewData.value.length)
    return true
  }
  return false
}

// 选择数据集
const selectDataset = async (dataset) => {
  console.log('=== selectDataset called ===')
  console.log('Dataset object keys:', Object.keys(dataset || {}))
  console.log('Dataset id:', dataset?.id, 'type:', typeof dataset?.id)
  console.log('Dataset name:', dataset?.name)
  console.log('Dataset type:', dataset?.dataset_type)
  console.log('Full dataset:', JSON.stringify(dataset, null, 2))
  
  // 安全检查：确保dataset有id
  if (!dataset || !dataset.id) {
    console.error('[ERROR] Invalid dataset object:', dataset)
    ElMessage.error('数据集信息不完整，请刷新页面重试')
    return
  }
  
  // 切换前保存当前数据集的预览状态，避免结构化/LLM 数据集共用 previewData
  saveCurrentPreviewState()
  
  selectedDataset.value = dataset
  
  // 保存选中的数据集ID到localStorage
  localStorage.setItem('data_factory_selected_dataset_id', String(dataset.id))
  console.log('[DEBUG] Saved selected dataset ID:', dataset.id)
  
  // 等待DOM更新，确保响应式系统同步
  await nextTick()
  console.log('[DEBUG] After assignment, selectedDataset.name:', selectedDataset.value?.name)
  
  // 优先恢复已缓存的预览状态，避免结构化/LLM 数据集共用 previewData
  restorePreviewState(dataset)
  
  // 根据数据集的业务域切换到正确的Tab并加载配置
  if (dataset.dataset_type === 'structured') {
    console.log('Switching to structured tab')
    activeTab.value = 'structured'
    
    // 关键修复：同步更新业务域下拉框的值
    // 使用 Object.assign 确保响应式更新
    const domainValue = dataset.business_domain || 'order'
    console.log('Setting business_domain to:', domainValue)
    
    // 创建一个新的对象副本，确保Vue能检测到变化
    structuredForm.value = {
      ...structuredForm.value,
      business_domain: domainValue
    }
    
    // 等待DOM更新
    await nextTick()
    console.log('After setting, business_domain is:', structuredForm.value.business_domain)
    
    // 先清空字段，触发响应式更新
    structuredForm.value.fields = []
    
    // 等待DOM更新
    await nextTick()
    
    // 根据业务域加载对应的字段定义
    if (dataset.business_domain === 'order') {
      console.log('Loading order fields')
      structuredForm.value.fields = [
        { name: 'order_id', type: 'string', nullable: false, description: '订单唯一标识' },
        { name: 'customer_name', type: 'string', nullable: false, description: '客户姓名' },
        { name: 'amount', type: 'decimal', nullable: false, description: '订单金额' },
        { name: 'currency', type: 'string', nullable: false, description: '币种代码' },
        { name: 'items_count', type: 'integer', nullable: false, description: '商品数量' },
      ]
      
      previewData.value = Array.from({ length: Math.min(5, dataset.record_count || 3) }, (_, i) => ({
        order_id: `ORD${Date.now()}${String(i).padStart(3, '0')}`,
        customer_name: ['张三', '李四', '王五', '赵六', '钱七'][i],
        amount: (Math.random() * 500 + 50).toFixed(2),
        currency: ['USD', 'EUR', 'CNY', 'GBP'][Math.floor(Math.random() * 4)],
        items_count: Math.floor(Math.random() * 10) + 1
      }))
      
      previewColumns.value = [
        { prop: 'order_id', label: '订单号', width: 180 },
        { prop: 'customer_name', label: '客户', width: 100 },
        { prop: 'amount', label: '金额', width: 100 },
        { prop: 'currency', label: '币种', width: 80 },
        { prop: 'items_count', label: '数量', width: 80 },
      ]
    } else if (dataset.business_domain === 'logistics') {
      console.log('Loading logistics fields')
      structuredForm.value.fields = [
        { name: 'tracking_number', type: 'string', nullable: false, description: '物流单号' },
        { name: 'carrier', type: 'string', nullable: false, description: '承运商' },
        { name: 'status', type: 'string', nullable: false, description: '运输状态' },
        { name: 'origin', type: 'string', nullable: true, description: '始发地' },
        { name: 'destination', type: 'string', nullable: false, description: '目的地' },
      ]
      
      previewData.value = Array.from({ length: Math.min(5, dataset.record_count || 3) }, (_, i) => ({
        tracking_number: ['SF', 'YT', 'ZTO', 'YD'][Math.floor(Math.random() * 4)] + Math.random().toString().slice(2, 12),
        carrier: ['顺丰速运', '圆通速递', '中通快递', '韵达快递'][Math.floor(Math.random() * 4)],
        status: ['运输中', '已签收', '待揽收', '派送中'][Math.floor(Math.random() * 4)],
        origin: ['深圳', '上海', '杭州', '广州'][Math.floor(Math.random() * 4)],
        destination: ['北京', '成都', '武汉', '南京'][Math.floor(Math.random() * 4)]
      }))
      
      previewColumns.value = [
        { prop: 'tracking_number', label: '物流单号', width: 160 },
        { prop: 'carrier', label: '承运商', width: 120 },
        { prop: 'status', label: '状态', width: 100 },
        { prop: 'origin', label: '始发地', width: 100 },
        { prop: 'destination', label: '目的地', width: 100 },
      ]
    } else if (dataset.business_domain === 'after_sales') {
      console.log('Loading after_sales fields')
      structuredForm.value.fields = [
        { name: 'ticket_id', type: 'string', nullable: false, description: '工单编号' },
        { name: 'order_id', type: 'string', nullable: false, description: '关联订单' },
        { name: 'type', type: 'string', nullable: false, description: '工单类型' },
        { name: 'reason', type: 'string', nullable: false, description: '申请原因' },
        { name: 'amount', type: 'decimal', nullable: true, description: '退款金额' },
      ]
      
      previewData.value = Array.from({ length: Math.min(5, dataset.record_count || 3) }, (_, i) => ({
        ticket_id: `TK${Date.now()}${String(i).padStart(3, '0')}`,
        order_id: `ORD${Date.now() - Math.random() * 86400000}`.slice(0, 15),
        type: ['退款', '退货', '换货', '维修'][Math.floor(Math.random() * 4)],
        reason: ['商品质量问题', '尺码不合适', '颜色不符', '物流损坏'][Math.floor(Math.random() * 4)],
        amount: Math.random() > 0.3 ? (Math.random() * 300 + 50).toFixed(2) : null
      }))
      
      previewColumns.value = [
        { prop: 'ticket_id', label: '工单号', width: 140 },
        { prop: 'order_id', label: '订单号', width: 140 },
        { prop: 'type', label: '类型', width: 80 },
        { prop: 'reason', label: '原因', width: 160 },
        { prop: 'amount', label: '退款金额', width: 100 },
      ]
    } else if (dataset.business_domain === 'merchant') {
      console.log('Loading merchant fields')
      structuredForm.value.fields = [
        { name: 'merchant_id', type: 'string', nullable: false, description: '商家ID' },
        { name: 'shop_name', type: 'string', nullable: false, description: '店铺名称' },
        { name: 'contact_person', type: 'string', nullable: false, description: '联系人' },
        { name: 'phone', type: 'string', nullable: false, description: '联系电话' },
        { name: 'business_license', type: 'string', nullable: true, description: '营业执照号' },
      ]
      
      previewData.value = Array.from({ length: Math.min(5, dataset.record_count || 3) }, (_, i) => ({
        merchant_id: `MCH${String(i + 1).padStart(3, '0')}`,
        shop_name: ['优品数码专营店', '时尚服饰旗舰店', '家居生活馆', '美妆护肤店', '图书音像店'][i],
        contact_person: ['陈经理', '林女士', '王先生', '李女士', '张先生'][i],
        phone: `13${Math.floor(Math.random() * 9)}****${Math.floor(Math.random() * 9000) + 1000}`,
        business_license: Math.random() > 0.2 ? `91${Math.floor(Math.random() * 900000) + 100000}MA5DXXXX` : null
      }))
      
      previewColumns.value = [
        { prop: 'merchant_id', label: '商家ID', width: 100 },
        { prop: 'shop_name', label: '店铺名称', width: 160 },
        { prop: 'contact_person', label: '联系人', width: 100 },
        { prop: 'phone', label: '联系电话', width: 120 },
        { prop: 'business_license', label: '营业执照', width: 160 },
      ]
    }
    
    // ========== 金融科技版业务域 ==========
    else if (dataset.business_domain === 'bank_transaction') {
      console.log('Loading bank_transaction fields')
      structuredForm.value.fields = [
        { name: 'account_number', type: 'string', nullable: false, description: '银行账号' },
        { name: 'transaction_time', type: 'date', nullable: false, description: '交易时间' },
        { name: 'amount', type: 'decimal', nullable: false, description: '交易金额' },
        { name: 'counterparty_account', type: 'string', nullable: true, description: '对方账户' },
        { name: 'transaction_type', type: 'string', nullable: false, description: '交易类型(转账/存款/取款)' },
      ]
      
      previewData.value = Array.from({ length: Math.min(5, dataset.record_count || 3) }, (_, i) => ({
        account_number: `622202${String(Math.random()).slice(2, 14)}`,
        transaction_time: new Date(Date.now() - Math.floor(Math.random() * 86400000 * 30)).toISOString().replace('T', ' ').slice(0, 19),
        amount: (Math.random() > 0.5 ? '' : '-') + (Math.random() * 10000 + 100).toFixed(2),
        counterparty_account: Math.random() > 0.3 ? `622202${String(Math.random()).slice(2, 14)}` : '',
        transaction_type: ['转账', '存款', '取款', '消费'][Math.floor(Math.random() * 4)]
      }))
      
      previewColumns.value = [
        { prop: 'account_number', label: '银行账号', width: 180 },
        { prop: 'transaction_time', label: '交易时间', width: 160 },
        { prop: 'amount', label: '交易金额', width: 100 },
        { prop: 'counterparty_account', label: '对方账户', width: 180 },
        { prop: 'transaction_type', label: '交易类型', width: 100 },
      ]
    } else if (dataset.business_domain === 'credit_card') {
      console.log('Loading credit_card fields')
      structuredForm.value.fields = [
        { name: 'card_number', type: 'string', nullable: false, description: '信用卡号' },
        { name: 'merchant_name', type: 'string', nullable: false, description: '商户名称' },
        { name: 'consumption_amount', type: 'decimal', nullable: false, description: '消费金额' },
        { name: 'installment_periods', type: 'integer', nullable: true, description: '分期期数' },
        { name: 'repayment_status', type: 'string', nullable: false, description: '还款状态' },
      ]
      
      previewData.value = Array.from({ length: Math.min(5, dataset.record_count || 3) }, (_, i) => ({
        card_number: `4532****${String(Math.floor(Math.random() * 9000) + 1000)}`,
        merchant_name: ['京东超市', '星巴克咖啡', 'Apple Store', '天猫超市', '美团外卖', '滴滴出行'][i % 6],
        consumption_amount: (Math.random() * 1000 + 10).toFixed(2),
        installment_periods: Math.random() > 0.7 ? [3, 6, 12, 24][Math.floor(Math.random() * 4)] : null,
        repayment_status: ['已还清', '待还款', '分期中'][Math.floor(Math.random() * 3)]
      }))
      
      previewColumns.value = [
        { prop: 'card_number', label: '信用卡号', width: 140 },
        { prop: 'merchant_name', label: '商户名称', width: 140 },
        { prop: 'consumption_amount', label: '消费金额', width: 100 },
        { prop: 'installment_periods', label: '分期期数', width: 100 },
        { prop: 'repayment_status', label: '还款状态', width: 100 },
      ]
    } else if (dataset.business_domain === 'loan_application') {
      console.log('Loading loan_application fields')
      structuredForm.value.fields = [
        { name: 'applicant_name', type: 'string', nullable: false, description: '申请人姓名' },
        { name: 'id_card', type: 'string', nullable: false, description: '身份证号' },
        { name: 'loan_amount', type: 'decimal', nullable: false, description: '贷款金额' },
        { name: 'interest_rate', type: 'decimal', nullable: false, description: '年利率(%)' },
        { name: 'collateral', type: 'string', nullable: true, description: '抵押物' },
      ]
      
      previewData.value = Array.from({ length: Math.min(5, dataset.record_count || 3) }, (_, i) => ({
        applicant_name: ['张三', '李四', '王五', '赵六', '钱七'][i % 5],
        id_card: `${[110, 310, 440, 510][Math.floor(Math.random() * 4)]}010119${Math.floor(Math.random() * 90) + 10}${String(Math.floor(Math.random() * 9000) + 1000)}`,
        loan_amount: (Math.random() * 900000 + 100000).toFixed(2),
        interest_rate: (Math.random() * 3 + 3.5).toFixed(2),
        collateral: Math.random() > 0.3 ? ['房产', '车辆', '存单'][Math.floor(Math.random() * 3)] : null
      }))
      
      previewColumns.value = [
        { prop: 'applicant_name', label: '申请人', width: 100 },
        { prop: 'id_card', label: '身份证号', width: 180 },
        { prop: 'loan_amount', label: '贷款金额', width: 120 },
        { prop: 'interest_rate', label: '年利率(%)', width: 100 },
        { prop: 'collateral', label: '抵押物', width: 100 },
      ]
    } else if (dataset.business_domain === 'investment_product') {
      console.log('Loading investment_product fields')
      structuredForm.value.fields = [
        { name: 'product_name', type: 'string', nullable: false, description: '产品名称' },
        { name: 'expected_return', type: 'decimal', nullable: false, description: '预期收益率(%)' },
        { name: 'risk_level', type: 'string', nullable: false, description: '风险等级' },
        { name: 'min_investment', type: 'decimal', nullable: false, description: '起投金额' },
        { name: 'term_months', type: 'integer', nullable: false, description: '期限(月)' },
      ]
      
      previewData.value = Array.from({ length: Math.min(5, dataset.record_count || 3) }, (_, i) => ({
        product_name: [`稳健理财${['A', 'B', 'C'][i % 3]}款`, `进取型债券${['X', 'Y', 'Z'][i % 3]}款`, `高收益信托${['M', 'N'][i % 2]}款`][Math.floor(Math.random() * 3)],
        expected_return: (Math.random() * 6 + 2.5).toFixed(2),
        risk_level: ['低风险', '中风险', '高风险'][Math.floor(Math.random() * 3)],
        min_investment: [10000, 50000, 100000][Math.floor(Math.random() * 3)].toFixed(2),
        term_months: [6, 12, 24, 36][Math.floor(Math.random() * 4)]
      }))
      
      previewColumns.value = [
        { prop: 'product_name', label: '产品名称', width: 160 },
        { prop: 'expected_return', label: '预期收益率(%)', width: 120 },
        { prop: 'risk_level', label: '风险等级', width: 100 },
        { prop: 'min_investment', label: '起投金额', width: 120 },
        { prop: 'term_months', label: '期限(月)', width: 100 },
      ]
    } else {
      console.log('No matching business domain, using default')
      // 默认处理
      structuredForm.value.fields = []
      previewData.value = []
      previewColumns.value = []
    }
    
    // 如果数据集有真实后端ID（后端 ds_id 是字符串 ds- 开头），加载真实数据；否则才用模拟数据
    const isBackendId = dataset.id && (
      (typeof dataset.id === 'string' && dataset.id.startsWith('ds-')) ||
      (typeof dataset.id === 'number' && dataset.id < 10000000000)
    )
    if (isBackendId) {
      console.log('[DEBUG] Dataset has real backend ID, loading real records')
      await loadDatasetRecords(dataset)
    }

    console.log('Final state:')
    console.log('activeTab:', activeTab.value)
    console.log('business_domain:', structuredForm.value.business_domain)
    console.log('structuredForm.fields:', structuredForm.value.fields)
    console.log('previewData.length:', previewData.value.length)
  } else if (dataset.dataset_type === 'llm_eval') {
    console.log('Switching to LLM tab')
    activeTab.value = 'llm_eval'
    
    // 优先使用保存的generation_config中的配置
    const config = dataset.generation_config || {}
    console.log('[DEBUG] Loaded generation_config:', JSON.stringify(config, null, 2))
    
    // 从generation_config中加载场景描述（如果有的话）
    llmForm.value.scenario = config.scenario || dataset.business_domain || ''
    console.log('[DEBUG] Loaded scenario from config:', config.scenario ? 'YES' : 'NO', 'Value:', llmForm.value.scenario?.substring(0, 50))
    
    if (config.positive_count && config.negative_count && config.boundary_count) {
      // 使用保存的实际配置
      llmForm.value.positive_count = config.positive_count
      llmForm.value.negative_count = config.negative_count
      llmForm.value.boundary_count = config.boundary_count
      llmForm.value.languages = config.languages || ['zh']
    } else {
      // 如果没有保存的配置，根据record_count估算（兼容旧数据）
      llmForm.value.positive_count = Math.floor(dataset.record_count * 0.5) || 3
      llmForm.value.negative_count = Math.floor(dataset.record_count * 0.3) || 1
      llmForm.value.boundary_count = Math.floor(dataset.record_count * 0.2) || 1
    }
    
    console.log('After setting, llmForm:', {
      scenario: llmForm.value.scenario,
      positive_count: llmForm.value.positive_count,
      negative_count: llmForm.value.negative_count,
      boundary_count: llmForm.value.boundary_count
    })
    
    // 从后端API加载LLM评测数据集的真实数据
    // 安全检查：确保dataset有id
    if (dataset && dataset.id) {
      console.log('[DEBUG] About to call loadLLMDatasetRecords with dataset:', {
        id: dataset.id,
        name: dataset.name,
        type: dataset.dataset_type
      })
      // 后端真实ID为字符串 ds- 开头或小于阈值的数字
      const isBackendId = (typeof dataset.id === 'string' && dataset.id.startsWith('ds-')) ||
        (typeof dataset.id === 'number' && dataset.id < 10000000000)
      if (isBackendId) {
        await loadLLMDatasetRecords(dataset)
      } else {
        console.log('[DEBUG] Dataset has temporary frontend ID, skipping backend load')
        // 不要覆盖可能已恢复的本地缓存；如果没有缓存再清空
        if (!previewStateCache.has(String(dataset.id))) {
          previewData.value = []
          previewColumns.value = []
        }
      }
      } else {
      console.error('[ERROR] Cannot load LLM dataset records: dataset or dataset.id is undefined')
      console.error('[ERROR] Dataset object:', JSON.stringify(dataset, null, 2))
      ElMessage.warning('数据集信息不完整，无法加载记录')
    }
  }
}

// 从后端加载LLM数据集的记录
const loadLLMDatasetRecords = async (dataset) => {
  // 安全检查：确保dataset有id
  if (!dataset || !dataset.id) {
    console.error('[ERROR] Invalid dataset object passed to loadLLMDatasetRecords:', dataset)
    ElMessage.error('数据集信息不完整，请刷新页面重试')
    return
  }
  
  try {
    console.log('[DEBUG] Loading LLM dataset records for dataset ID:', dataset.id, 'Name:', dataset.name)
    
    const token = localStorage.getItem('access_token') || localStorage.getItem('token')
    const response = await fetch(`/api/data-factory/datasets/${dataset.id}/records/?page_size=1000`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    
    if (!response.ok) {
      if (response.status === 404) {
        console.warn('[WARN] Dataset records not found in backend (404). This is expected for newly created empty datasets.')
        previewData.value = []
        previewColumns.value = []
        return
      }
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const result = await response.json()
    console.log('[DEBUG] Loaded', result.results?.length || 0, 'records from backend')
    console.log('[DEBUG] Result structure:', JSON.stringify(result, null, 2))
    
    // 更新预览数据
    if (result.results && Array.isArray(result.results) && result.results.length > 0) {
      previewData.value = result.results.map(r => r.data_content)
      
      // 动态生成列定义（基于第一条数据）
      const firstCase = previewData.value[0]
      if (!firstCase) {
        console.warn('[DEBUG] No data in first record')
        previewColumns.value = []
        previewPagination.value.total = 0
        return
      }
      
      const dynamicColumns = []

      // 通用列标题中文化映射（字段 key → 显示标题）
      const columnLabelMap = {
        'case_id': '用例ID',
        'type': '类型',
        'input': '输入',
        'expected': '期望输出',
        'note': '备注',
        'category': '类型',
        'return_reason': '退货原因',
        'refund_amount': '退款金额',
        'exchange_reason': '换货原因',
        'new_product': '换货商品',
        'damage_type': '破损类型',
        'compensation_amount': '赔偿金额',
        'missing_items': '漏发商品',
        'claim_amount': '索赔金额',
        'delivery_status': '收货状态',
        'resend_items': '补发商品'
      }
      
      // 固定显示的列：用例ID、类型
      if (firstCase.case_id) {
        dynamicColumns.push({ prop: 'case_id', label: '用例ID', width: 80 })
      }
      if (firstCase.type) {
        dynamicColumns.push({ 
          prop: 'type', 
          label: '类型', 
          width: 100,
          formatter: (row) => {
            const typeMap = {
              'positive': '正例',
              'negative': '负例',
              'boundary': '边界'
            }
            return typeMap[row.type] || row.type
          }
        })
      }
      
      // 优先使用 generation_config 中保存的 business_keywords（如果存在）
      let businessKeywords = []
      if (dataset.generation_config && dataset.generation_config.business_keywords) {
        businessKeywords = dataset.generation_config.business_keywords
        console.log('[DEBUG] Using business keywords from dataset generation_config:', businessKeywords)
      }
      
      console.log('[DEBUG] First case data:', JSON.stringify(firstCase, null, 2))
      console.log('[DEBUG] All available keys in first case:', Object.keys(firstCase))
      
      // 提取业务字段（排除基础字段和技术字段，以及场景限定内容字段）
      const excludeFields = ['case_id', 'type', 'label', 'language', 'scenario', '内容', 'content']
      
      if (businessKeywords.length > 0) {
        // 如果有明确的 business_keywords，按该顺序添加列
        businessKeywords.forEach((keyword, index) => {
          console.log(`[DEBUG] Processing keyword ${index+1}/${businessKeywords.length}: "${keyword}"`)
          
          // 查找对应的字段名
          let foundKey = null
          // 首先尝试精确匹配
          if (firstCase[keyword]) {
            foundKey = keyword
            console.log(`[DEBUG]  - Exact match found for "${keyword}"`)
          } else {
            // 尝试多种模糊匹配策略
            const normalizedKeyword = keyword.replace(/\s+/g, '').toLowerCase()
            
            // 策略1：关键词包含字段名
            foundKey = Object.keys(firstCase).find(key => {
              if (excludeFields.includes(key)) return false
              const normalizedKey = key.replace(/\s+/g, '').toLowerCase()
              return normalizedKeyword.includes(normalizedKey) || normalizedKey.includes(normalizedKeyword)
            })
            
            if (foundKey) {
              console.log(`[DEBUG]  - Fuzzy match found: "${foundKey}" for "${keyword}"`)
            } else {
              // 策略2：部分匹配（单个字匹配）
              foundKey = Object.keys(firstCase).find(key => {
                if (excludeFields.includes(key)) return false
                return keyword.split('').some(char => key.includes(char))
              })
              
              if (foundKey) {
                console.log(`[DEBUG]  - Partial character match found: "${foundKey}" for "${keyword}"`)
              }
            }
          }
          
          if (foundKey) {
            dynamicColumns.push({ 
              prop: foundKey, 
              label: columnLabelMap[keyword] || keyword,  // 优先中文化列标题
              width: 140,
              showOverflowTooltip: true
            })
          } else {
            // 如果没有找到，仍然添加列
            console.log(`[WARN]  - No match found for "${keyword}", adding empty column`)
            dynamicColumns.push({ 
              prop: keyword, 
              label: columnLabelMap[keyword] || keyword, 
              width: 140,
              showOverflowTooltip: true
            })
          }
        })
        
        // 再添加其他可能存在但未在 business_keywords 中列出的字段
        Object.keys(firstCase).forEach(key => {
          if (!excludeFields.includes(key) && !businessKeywords.includes(key)) {
            const alreadyAdded = dynamicColumns.some(col => col.prop === key)
            if (!alreadyAdded) {
              let label
              if (columnLabelMap[key]) {
                label = columnLabelMap[key]
              } else if (/^[a-z_]+$/.test(key)) {
                label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
              } else {
                label = key
              }
              
              dynamicColumns.push({ 
                prop: key, 
                label: label, 
                width: 140,
                showOverflowTooltip: true
              })
            }
          }
        })
      } else {
        // 如果没有 business_keywords，正常处理所有字段
        Object.keys(firstCase).forEach(key => {
          if (!excludeFields.includes(key)) {
            let label = columnLabelMap[key] || key
            
            if (/^[a-z_]+$/.test(key) && !columnLabelMap[key]) {
              label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
            }
            
            dynamicColumns.push({ 
              prop: key, 
              label: label, 
              width: 140,
              showOverflowTooltip: true
            })
          }
        })
      }
      
      previewColumns.value = dynamicColumns
      
      // 更新分页信息
      previewPagination.value.total = result.results.length
      previewPagination.value.currentPage = 1
      previewPagination.value.pageSize = 20
      
      // 缓存LLM预览状态
      saveCurrentPreviewState()
      
      console.log('[DEBUG] Preview data updated with', previewData.value.length, 'records')
    } else {
      console.warn('[DEBUG] No records found in dataset')
      previewData.value = []
      previewColumns.value = []
      previewPagination.value.total = 0
    }
  } catch (error) {
    console.error('[ERROR] Failed to load LLM dataset records:', error)
    ElMessage.error('加载数据失败: ' + error.message)
  }
}

// 通用：从后端加载数据集记录（适用于所有类型）
const loadDatasetRecords = async (dataset) => {
  if (!dataset || !dataset.id) {
    console.error('[ERROR] Invalid dataset object:', dataset)
    return
  }

  try {
    console.log('[DEBUG] Loading records for dataset ID:', dataset.id, 'Type:', dataset.dataset_type)

    const token = localStorage.getItem('access_token') || localStorage.getItem('token')
    const response = await fetch(`/api/data-factory/datasets/${dataset.id}/records/?page_size=1000`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const result = await response.json()
    console.log('[DEBUG] Loaded', result.results?.length || 0, 'records from backend')

    const records = result.results || result
    if (Array.isArray(records) && records.length > 0) {
      previewData.value = records.map(r => r.data_content || r)
      previewPagination.value.total = previewData.value.length
      previewPagination.value.currentPage = 1
      // 从后端加载后缓存，便于切换回来时快速恢复
      saveCurrentPreviewState()
    } else {
      previewData.value = []
      previewPagination.value.total = 0
    }
  } catch (error) {
    console.error('[ERROR] Failed to load dataset records:', error)
    // 404/403 可能是数据集对当前用户不可见或后端无记录（如前端临时数据），不弹错误
    if (error.message?.includes('404') || error.message?.includes('403')) {
      console.warn('[INFO] Dataset records not available (may be frontend-only dataset), using empty preview')
      previewData.value = []
      previewPagination.value.total = 0
    } else {
      ElMessage.error('加载数据失败: ' + error.message)
    }
  }
}

// 显示新建对话框
const showCreateDialog = () => {
  newDataset.value = {
    name: '',
    dataset_type: 'structured',
    business_domain: '',
    description: ''
  }
  createDialogVisible.value = true
}

// 创建数据集
const createDataset = async () => {
  if (!newDataset.value.name) {
    ElMessage.warning('请输入数据集名称')
    return
  }

  try {
    // 创建空数据集（不生成数据）
    const emptyDataset = {
      id: Date.now(),
      name: newDataset.value.name,
      purpose: '',
      dataset_type: newDataset.value.dataset_type,
      business_domain: newDataset.value.business_domain || '',
      description: newDataset.value.description || '',
      record_count: 0, // 初始为0条数据
      file_size: 0,
      status: 'empty', // 状态为空
      export_format: 'json',
      created_at: new Date().toISOString(),
      version: currentVersion.value // 关键修复：保存当前版本（版本隔离）
    }
    
    console.log('[CREATE DATASET] Created with version:', currentVersion.value)
    
    // 添加到数据集列表顶部
    datasets.value.unshift(emptyDataset)
    
    // 保存到localStorage
    saveDatasetsToStorage()
    
    // 自动选中新建的数据集
    selectedDataset.value = emptyDataset
    
    // 根据数据类型切换到对应的Tab
    if (newDataset.value.dataset_type === 'structured') {
      activeTab.value = 'structured'
      // 清空字段定义，让用户自己配置
      structuredForm.value.fields = []
      previewData.value = []
      previewColumns.value = []
    } else if (newDataset.value.dataset_type === 'llm_eval') {
      activeTab.value = 'llm_eval'
      // 保持表单为空，placeholder 会提示格式
      llmForm.value.scenario = ''
      llmForm.value.positive_count = 3
      llmForm.value.negative_count = 1
      llmForm.value.boundary_count = 1
      previewData.value = []
      previewColumns.value = []
    }
    
    ElMessage.success(`✓ 已创建空数据集 "${newDataset.value.name}"，请配置字段后生成数据`)
    createDialogVisible.value = false
    
    // 重置表单
    newDataset.value = {
      name: '',
      dataset_type: 'structured',
      business_domain: '',
      description: ''
    }
  } catch (error) {
    console.error('Create dataset error:', error)
    ElMessage.error('创建失败')
  }
}

// 生成结构化数据
const generateStructuredData = async () => {
  console.log('=== generateStructuredData called ===')

  if (structuredForm.value.fields.length === 0) {
    ElMessage.warning('请至少定义一个字段')
    return
  }

  generating.value = true
  try {
    const token = localStorage.getItem('access_token') || localStorage.getItem('token')
    if (!token) {
      ElMessage.error('未登录，请先登录')
      return
    }

    const requestBody = {
      name: selectedDataset.value?.name || `${getBusinessDomainLabel(structuredForm.value.business_domain)}数据-${new Date().toLocaleDateString()}`,
      business_domain: structuredForm.value.business_domain,
      count: structuredForm.value.count,
      fields: structuredForm.value.fields,
      boundary_tests: structuredForm.value.boundary_tests || [],
      export_format: structuredForm.value.export_format || 'json'
    }

    console.log('[DEBUG] Structured data request:', JSON.stringify(requestBody, null, 2))

    const response = await fetch('/api/data-factory/datasets/generate_structured/', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(requestBody)
    })

    const result = await response.json()
    console.log('[DEBUG] Structured data response:', result)

    if (!response.ok) {
      throw new Error(result.error || result.detail || '生成失败')
    }

    // 后端返回了真实数据集ID，更新前端状态
    const backendDataset = result.dataset || result
    const newDataset = {
      id: backendDataset.id,
      name: backendDataset.name,
      dataset_type: 'structured',
      business_domain: backendDataset.business_domain,
      record_count: backendDataset.record_count,
      file_size: backendDataset.file_size || 0,
      status: backendDataset.status || 'completed',
      export_format: structuredForm.value.export_format || 'json',
      created_at: backendDataset.created_at || new Date().toISOString(),
      updated_at: backendDataset.updated_at || new Date().toISOString(),
      version: currentVersion.value
    }

    if (selectedDataset.value && selectedDataset.value.dataset_type === 'structured') {
      // 更新现有数据集
      const idx = datasets.value.findIndex(d => d.id === selectedDataset.value.id)
      if (idx !== -1) {
        datasets.value.splice(idx, 1, newDataset)
      } else {
        datasets.value.unshift(newDataset)
      }
      ElMessage.success(`✓ 已更新 "${newDataset.name}"，共 ${newDataset.record_count} 条数据`)
    } else {
      // 创建新数据集
      datasets.value.unshift(newDataset)
      ElMessage.success(`✓ 已生成 "${newDataset.name}"，共 ${newDataset.record_count} 条数据`)
    }

    selectedDataset.value = newDataset
    saveDatasetsToStorage()
    localStorage.setItem('data_factory_selected_dataset_id', String(newDataset.id))

    // 加载真实数据预览
    await loadDatasetRecords(newDataset)

    // 缓存刚生成的预览状态，方便切换后恢复
    saveCurrentPreviewState()

    // 切换到数据集Tab
    leftPanelTab.value = 'datasets'
  } catch (error) {
    console.error('Generate data error:', error)
    ElMessage.error(error.message || '生成失败')
  } finally {
    generating.value = false
  }
}

// 根据业务域生成预览数据（生成所有数据，但只显示当前页）
const generatePreviewData = (dataset) => {
  // 更新分页信息
  previewPagination.value.total = dataset.record_count || 3
  previewPagination.value.currentPage = 1 // 重置到第一页
  
  // 生成所有数据（用于后续分页）
  const allData = []
  const totalCount = dataset.record_count || 3
  
  if (dataset.business_domain === 'order') {
    for (let i = 0; i < totalCount; i++) {
      allData.push({
        order_id: `ORD${Date.now()}${String(i).padStart(6, '0')}`,
        customer_name: ['张三', '李四', '王五', '赵六', '钱七', '孙八', '周九', '吴十'][i % 8],
        amount: (Math.random() * 500 + 50).toFixed(2),
        currency: ['USD', 'EUR', 'CNY', 'GBP'][Math.floor(Math.random() * 4)],
        items_count: Math.floor(Math.random() * 10) + 1
      })
    }
    
    previewColumns.value = [
      { prop: 'order_id', label: '订单号', width: 180 },
      { prop: 'customer_name', label: '客户', width: 100 },
      { prop: 'amount', label: '金额', width: 100 },
      { prop: 'currency', label: '币种', width: 80 },
      { prop: 'items_count', label: '数量', width: 80 },
    ]
  } else if (dataset.business_domain === 'logistics') {
    for (let i = 0; i < totalCount; i++) {
      allData.push({
        tracking_number: ['SF', 'YT', 'ZTO', 'YD'][Math.floor(Math.random() * 4)] + String(Math.random()).slice(2, 12),
        carrier: ['顺丰速运', '圆通速递', '中通快递', '韵达快递'][Math.floor(Math.random() * 4)],
        status: ['运输中', '已签收', '待揽收', '派送中'][Math.floor(Math.random() * 4)],
        origin: ['深圳', '上海', '杭州', '广州', '北京', '成都'][Math.floor(Math.random() * 6)],
        destination: ['北京', '成都', '武汉', '南京', '西安', '重庆'][Math.floor(Math.random() * 6)]
      })
    }
    
    previewColumns.value = [
      { prop: 'tracking_number', label: '物流单号', width: 160 },
      { prop: 'carrier', label: '承运商', width: 120 },
      { prop: 'status', label: '状态', width: 100 },
      { prop: 'origin', label: '始发地', width: 100 },
      { prop: 'destination', label: '目的地', width: 100 },
    ]
  } else if (dataset.business_domain === 'after_sales') {
    for (let i = 0; i < totalCount; i++) {
      allData.push({
        ticket_id: `TK${Date.now()}${String(i).padStart(6, '0')}`,
        order_id: `ORD${Date.now() - Math.random() * 86400000}`.slice(0, 15),
        type: ['退款', '退货', '换货', '维修'][Math.floor(Math.random() * 4)],
        reason: ['商品质量问题', '尺码不合适', '颜色不符', '物流损坏', '描述不符'][Math.floor(Math.random() * 5)],
        amount: Math.random() > 0.3 ? (Math.random() * 300 + 50).toFixed(2) : null
      })
    }
    
    previewColumns.value = [
      { prop: 'ticket_id', label: '工单号', width: 140 },
      { prop: 'order_id', label: '订单号', width: 140 },
      { prop: 'type', label: '类型', width: 80 },
      { prop: 'reason', label: '原因', width: 160 },
      { prop: 'amount', label: '退款金额', width: 100 },
    ]
  } else if (dataset.business_domain === 'merchant') {
    for (let i = 0; i < totalCount; i++) {
      allData.push({
        merchant_id: `MCH${String(i + 1).padStart(6, '0')}`,
        shop_name: ['优品数码专营店', '时尚服饰旗舰店', '家居生活馆', '美妆护肤店', '图书音像店', '食品生鲜店'][i % 6],
        contact_person: ['陈经理', '林女士', '王先生', '李女士', '张先生', '刘小姐'][i % 6],
        phone: `13${Math.floor(Math.random() * 9)}****${Math.floor(Math.random() * 9000) + 1000}`,
        business_license: Math.random() > 0.2 ? `91${Math.floor(Math.random() * 900000) + 100000}MA5DXXXX` : null
      })
    }
    
    previewColumns.value = [
      { prop: 'merchant_id', label: '商家ID', width: 100 },
      { prop: 'shop_name', label: '店铺名称', width: 160 },
      { prop: 'contact_person', label: '联系人', width: 100 },
      { prop: 'phone', label: '联系电话', width: 120 },
      { prop: 'business_license', label: '营业执照', width: 160 },
    ]
  }
  
  // ========== 金融科技版业务域 ==========
  else if (dataset.business_domain === 'bank_transaction') {
    for (let i = 0; i < totalCount; i++) {
      allData.push({
        account_number: `622202${String(Math.random()).slice(2, 14)}`,
        transaction_time: new Date(Date.now() - Math.floor(Math.random() * 86400000 * 30)).toISOString().replace('T', ' ').slice(0, 19),
        amount: (Math.random() > 0.5 ? '' : '-') + (Math.random() * 10000 + 100).toFixed(2),
        counterparty_account: Math.random() > 0.3 ? `622202${String(Math.random()).slice(2, 14)}` : '',
        transaction_type: ['转账', '存款', '取款', '消费'][Math.floor(Math.random() * 4)]
      })
    }
    
    previewColumns.value = [
      { prop: 'account_number', label: '银行账号', width: 180 },
      { prop: 'transaction_time', label: '交易时间', width: 160 },
      { prop: 'amount', label: '交易金额', width: 100 },
      { prop: 'counterparty_account', label: '对方账户', width: 180 },
      { prop: 'transaction_type', label: '交易类型', width: 100 },
    ]
  } else if (dataset.business_domain === 'credit_card') {
    for (let i = 0; i < totalCount; i++) {
      allData.push({
        card_number: `4532****${String(Math.floor(Math.random() * 9000) + 1000)}`,
        merchant_name: ['京东超市', '星巴克咖啡', 'Apple Store', '天猫超市', '美团外卖', '滴滴出行'][i % 6],
        consumption_amount: (Math.random() * 1000 + 10).toFixed(2),
        installment_periods: Math.random() > 0.7 ? [3, 6, 12, 24][Math.floor(Math.random() * 4)] : null,
        repayment_status: ['已还清', '待还款', '分期中'][Math.floor(Math.random() * 3)]
      })
    }
    
    previewColumns.value = [
      { prop: 'card_number', label: '信用卡号', width: 140 },
      { prop: 'merchant_name', label: '商户名称', width: 140 },
      { prop: 'consumption_amount', label: '消费金额', width: 100 },
      { prop: 'installment_periods', label: '分期期数', width: 100 },
      { prop: 'repayment_status', label: '还款状态', width: 100 },
    ]
  } else if (dataset.business_domain === 'loan_application') {
    for (let i = 0; i < totalCount; i++) {
      allData.push({
        applicant_name: ['张三', '李四', '王五', '赵六', '钱七'][i % 5],
        id_card: `${[110, 310, 440, 510][Math.floor(Math.random() * 4)]}010119${Math.floor(Math.random() * 90) + 10}${String(Math.floor(Math.random() * 9000) + 1000)}`,
        loan_amount: (Math.random() * 900000 + 100000).toFixed(2),
        interest_rate: (Math.random() * 3 + 3.5).toFixed(2),
        collateral: Math.random() > 0.3 ? ['房产', '车辆', '存单'][Math.floor(Math.random() * 3)] : null
      })
    }
    
    previewColumns.value = [
      { prop: 'applicant_name', label: '申请人', width: 100 },
      { prop: 'id_card', label: '身份证号', width: 180 },
      { prop: 'loan_amount', label: '贷款金额', width: 120 },
      { prop: 'interest_rate', label: '年利率(%)', width: 100 },
      { prop: 'collateral', label: '抵押物', width: 100 },
    ]
  } else if (dataset.business_domain === 'investment_product') {
    for (let i = 0; i < totalCount; i++) {
      allData.push({
        product_name: [`稳健理财${['A', 'B', 'C'][i % 3]}款`, `进取型债券${['X', 'Y', 'Z'][i % 3]}款`, `高收益信托${['M', 'N'][i % 2]}款`][Math.floor(Math.random() * 3)],
        expected_return: (Math.random() * 6 + 2.5).toFixed(2),
        risk_level: ['低风险', '中风险', '高风险'][Math.floor(Math.random() * 3)],
        min_investment: [10000, 50000, 100000][Math.floor(Math.random() * 3)].toFixed(2),
        term_months: [6, 12, 24, 36][Math.floor(Math.random() * 4)]
      })
    }
    
    previewColumns.value = [
      { prop: 'product_name', label: '产品名称', width: 160 },
      { prop: 'expected_return', label: '预期收益率(%)', width: 120 },
      { prop: 'risk_level', label: '风险等级', width: 100 },
      { prop: 'min_investment', label: '起投金额', width: 120 },
      { prop: 'term_months', label: '期限(月)', width: 100 },
    ]
  }
  
  // ========== 默认处理（使用字段定义生成） ==========
  else {
    // 默认预览
    for (let i = 0; i < totalCount; i++) {
      const row = {}
      structuredForm.value.fields.forEach(field => {
        if (field.type === 'string') row[field.name] = `示例数据${i + 1}`
        else if (field.type === 'integer') row[field.name] = Math.floor(Math.random() * 100)
        else if (field.type === 'decimal') row[field.name] = (Math.random() * 1000).toFixed(2)
        else if (field.type === 'boolean') row[field.name] = Math.random() > 0.5
        else row[field.name] = '-'
      })
      allData.push(row)
    }
    
    previewColumns.value = structuredForm.value.fields.map(f => ({
      prop: f.name,
      label: f.description || f.name,
      width: 120
    }))
  }
  
  // 将生成的所有数据存储到previewData中
  previewData.value = allData
}

// 生成LLM评测数据
const generateLLMDataset = async () => {
  if (!llmForm.value.scenario) {
    ElMessage.warning('请输入场景描述')
    return
  }

  generating.value = true
  
  // 创建180秒超时的AbortController (增加超时时间,因为DashScope API可能较慢)
  const controller = new AbortController()
  const timeoutId = setTimeout(() => {
    controller.abort()
  }, 180000) // 180秒超时 (3分钟)
  
  try {
    // 获取token
    const token = localStorage.getItem('access_token') || localStorage.getItem('token')
    
    if (!token) {
      ElMessage.error('未登录，请先登录')
      return
    }

    // 显示等待提示
    const totalCount = llmForm.value.positive_count + 
                       llmForm.value.negative_count + 
                       llmForm.value.boundary_count
    
    console.log('[DEBUG] Sending request with params:', {
      scenario: llmForm.value.scenario,
      positive_count: llmForm.value.positive_count,
      negative_count: llmForm.value.negative_count,
      boundary_count: llmForm.value.boundary_count,
      languages: llmForm.value.languages
    })
    
    if (totalCount > 50) {
      ElMessage.warning(`将生成 ${totalCount} 条数据，可能需要较长时间（预计1-3分钟），请稍候...`)
    } else {
      ElMessage.info('正在调用通义千问API生成数据，请稍候...')
    }
    
    // 关键修复：在生成数据前，先删除其他同名的旧数据集（保留当前选中的）
    // 如果数据集名称还是默认/空，自动根据场景标题命名
    const defaultNames = new Set(['', '项目订单', '新建数据集', '未命名', '数据集', 'LLM评测数据集', '新数据集', '测试数据集'])
    let datasetName = selectedDataset.value?.name?.trim() || ''
    if (defaultNames.has(datasetName)) {
      datasetName = extractScenarioTitle(llmForm.value.scenario)
      if (selectedDataset.value) {
        selectedDataset.value.name = datasetName
      }
    }

    if (datasetName && selectedDataset.value?.id) {
      // 删除其他同名的数据集（排除当前选中的）
      const oldDatasets = datasets.value.filter(d => d.name === datasetName && d.id !== selectedDataset.value.id)
      if (oldDatasets.length > 0) {
        console.log('[DEBUG] Removing', oldDatasets.length, 'other old datasets with same name:', datasetName)
        console.log('[DEBUG] Keeping current selected dataset ID:', selectedDataset.value.id)
        oldDatasets.forEach(oldDs => {
          const idx = datasets.value.findIndex(d => d.id === oldDs.id)
          if (idx !== -1) {
            datasets.value.splice(idx, 1)
          }
        })
        saveDatasetsToStorage()
        console.log('[DEBUG] After removal, datasets count:', datasets.value.length)
      }
    }

    // 调用后端API生成LLM评测数据（带超时控制）
    const requestBody = {
      scenario: llmForm.value.scenario,
      positive_count: llmForm.value.positive_count,
      negative_count: llmForm.value.negative_count,
      boundary_count: llmForm.value.boundary_count,
      languages: llmForm.value.languages,
      dataset_name: datasetName,  // 传递用户设置的数据集名称
      model_id: selectedModelId.value || ''  // 选中的 AI 底座模型
    }

    console.log('[DEBUG] Request body:', JSON.stringify(requestBody, null, 2))
    console.log('[DEBUG] Selected dataset before API call - ID:', selectedDataset.value?.id, 'Name:', selectedDataset.value?.name)

    const response = await fetch('/api/data-factory/datasets/generate_llm_dataset/', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(requestBody),
      signal: controller.signal // 添加超时信号
    })

    // 清除超时定时器
    clearTimeout(timeoutId)

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.error || `HTTP error! status: ${response.status}`)
    }

    const result = await response.json()
    
    console.log('[DEBUG] API Response:', result)
    console.log('[DEBUG] Result dataset:', JSON.stringify(result.dataset, null, 2))
    
    // 直接使用后端返回的数据集信息
    let newDataset = result.dataset
    
    if (!newDataset) {
      console.error('[ERROR] No dataset in response:', result)
      ElMessage.error('数据集创建失败：后端未返回数据集信息。请检查后端日志')
      return
    }
    
    // 关键修复：确保数据集有正确的 dataset_type 和 version 字段
    newDataset = {
      ...newDataset,
      dataset_type: 'llm_eval',  // 强制设置为LLM评测类型
      version: currentVersion.value  // 设置当前版本（电商版或金融版）
    }
    
    console.log('[DEBUG] New dataset ID:', newDataset.id, 'Name:', newDataset.name, 'Type:', newDataset.dataset_type, 'Version:', newDataset.version)
    
    // 判断是否有选中的数据集
    if (selectedDataset.value && selectedDataset.value.id) {
      // 更新现有数据集
      console.log('更新现有数据集:', selectedDataset.value?.name || 'unknown', 'record_count:', newDataset.record_count)
      
      // 使用用户修改后的名称（如果有的话），否则使用后端返回的名称
      const finalName = selectedDataset.value.name || newDataset.name
      
      // 关键修复：用后端返回的新数据集完全替换前端旧的数据集
      // 包括更新ID为后端返回的真实数据库ID
      const updatedDataset = {
        ...newDataset,
        name: finalName  // 保留用户修改的名称
      }
      
      // 找到当前选中数据集在列表中的位置
      const currentIdx = datasets.value.findIndex(d => d.id === selectedDataset.value.id)
      console.log('[DEBUG] Current dataset index in list:', currentIdx)
      
      if (currentIdx !== -1) {
        // 直接替换当前位置的数据集（不删除再unshift，保持位置不变）
        console.log('[DEBUG] Replacing dataset at index:', currentIdx)
        datasets.value.splice(currentIdx, 1, updatedDataset)
      } else {
        // 如果找不到（异常情况），添加到顶部
        console.warn('[WARN] Current dataset not found in list, adding to top')
        datasets.value.unshift(updatedDataset)
      }
      
      // 更新选中数据集为新数据集
      selectedDataset.value = updatedDataset
      
      // 关键修复：保存到localStorage，确保数据同步
      saveDatasetsToStorage()
      
      // 保存选中的数据集ID（使用后端返回的真实ID）
      localStorage.setItem('data_factory_selected_dataset_id', String(updatedDataset.id))
      console.log('[DEBUG] Updated dataset saved. New ID:', updatedDataset.id, 'Name:', updatedDataset.name)
    } else {
      // 创建新数据集
      console.log('创建新数据集:', newDataset.name, 'record_count:', newDataset.record_count)
      
      // 将新数据集添加到列表顶部
      datasets.value.unshift(newDataset)
      
      // 选中新建的数据集
      selectedDataset.value = newDataset
      
      // 保存到localStorage
      saveDatasetsToStorage()
      
      // 保存选中的数据集ID
      localStorage.setItem('data_factory_selected_dataset_id', String(newDataset.id))
    }
    
    // 使用后端返回的真实测试数据作为预览数据
    if (result.test_cases && result.test_cases.length > 0) {
      console.log('[DEBUG] Using real test cases from backend:', result.test_cases.length, 'cases')
      previewData.value = result.test_cases
      
      // 动态生成列定义
      const firstCase = result.test_cases[0]
      const dynamicColumns = []

      // 通用列标题中文化映射（字段 key → 显示标题）
      const columnLabelMap = {
        'case_id': '用例ID',
        'type': '类型',
        'input': '输入',
        'expected': '期望输出',
        'note': '备注',
        'category': '类型',
        'return_reason': '退货原因',
        'refund_amount': '退款金额',
        'exchange_reason': '换货原因',
        'new_product': '换货商品',
        'damage_type': '破损类型',
        'compensation_amount': '赔偿金额',
        'missing_items': '漏发商品',
        'claim_amount': '索赔金额',
        'delivery_status': '收货状态',
        'resend_items': '补发商品'
      }
      
      // 固定显示的列：用例ID、类型
      if (firstCase.case_id) {
        dynamicColumns.push({ prop: 'case_id', label: '用例ID', width: 80 })
      }
      if (firstCase.type) {
        dynamicColumns.push({ 
          prop: 'type', 
          label: '类型', 
          width: 100,
          formatter: (row) => {
            const typeMap = {
              'positive': '正例',
              'negative': '负例',
              'boundary': '边界'
            }
            return typeMap[row.type] || row.type
          }
        })
      }
      
      // 优先使用 generation_config 中保存的 business_keywords（如果存在）
      // 这样可以确保列的顺序和名称与用户在字段Title中指定的完全一致
      let businessKeywords = []
      if (result.dataset && result.dataset.generation_config && result.dataset.generation_config.business_keywords) {
        businessKeywords = result.dataset.generation_config.business_keywords
        console.log('[DEBUG] Using business keywords from generation_config:', businessKeywords)
      } else if (newDataset.generation_config && newDataset.generation_config.business_keywords) {
        businessKeywords = newDataset.generation_config.business_keywords
        console.log('[DEBUG] Using business keywords from newDataset:', businessKeywords)
      }
      
      console.log('[DEBUG] First case data:', JSON.stringify(firstCase, null, 2))
      console.log('[DEBUG] All available keys in first case:', Object.keys(firstCase))
      
      // 提取业务字段（排除基础字段和技术字段，以及场景限定内容字段）
      const excludeFields = ['case_id', 'type', 'label', 'language', 'scenario', '内容', 'content']
      
      if (businessKeywords.length > 0) {
        // 如果有明确的 business_keywords，按该顺序添加列
        businessKeywords.forEach((keyword, index) => {
          console.log(`[DEBUG] Processing keyword ${index+1}/${businessKeywords.length}: "${keyword}"`)
          
          // 查找对应的字段名（可能就是关键词本身，或者有变体）
          let foundKey = null
          // 首先尝试精确匹配
          if (firstCase[keyword]) {
            foundKey = keyword
            console.log(`[DEBUG]  - Exact match found for "${keyword}"`)
          } else {
            // 尝试多种模糊匹配策略
            const normalizedKeyword = keyword.replace(/\s+/g, '').toLowerCase()
            
            // 策略1：关键词包含字段名或字段名包含关键词
            foundKey = Object.keys(firstCase).find(key => {
              if (excludeFields.includes(key)) return false
              const normalizedKey = key.replace(/\s+/g, '').toLowerCase()
              return normalizedKeyword.includes(normalizedKey) || normalizedKey.includes(normalizedKeyword)
            })
            
            if (foundKey) {
              console.log(`[DEBUG]  - Fuzzy match found: "${foundKey}" for "${keyword}"`)
            } else {
              // 策略2：部分匹配（单个字匹配）
              foundKey = Object.keys(firstCase).find(key => {
                if (excludeFields.includes(key)) return false
                return keyword.split('').some(char => key.includes(char))
              })
              
              if (foundKey) {
                console.log(`[DEBUG]  - Partial character match found: "${foundKey}" for "${keyword}"`)
              }
            }
          }
          
          if (foundKey) {
            dynamicColumns.push({ 
              prop: foundKey, 
              label: columnLabelMap[keyword] || keyword,  // 优先中文化列标题
              minWidth: 150 
            })
          } else {
            // 如果没有找到，仍然添加列（显示为空，确保列完整性）
            console.log(`[WARN]  - No match found for "${keyword}", adding empty column`)
            dynamicColumns.push({ 
              prop: keyword, 
              label: columnLabelMap[keyword] || keyword, 
              minWidth: 150 
            })
          }
        })
        
        // 再添加其他可能存在但未在 business_keywords 中列出的字段
        Object.keys(firstCase).forEach(key => {
          if (!excludeFields.includes(key) && !businessKeywords.includes(key)) {
            // 检查是否已经通过模糊匹配添加了
            const alreadyAdded = dynamicColumns.some(col => col.prop === key)
            if (!alreadyAdded) {
              let label = columnLabelMap[key] || key
              if (!columnLabelMap[key] && /^[\u4e00-\u9fa5]+$/.test(key)) {
                label = key
              } else if (!columnLabelMap[key]) {
                label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
              }
              
              dynamicColumns.push({ prop: key, label: label, minWidth: 150 })
            }
          }
        })
      } else {
        // 如果没有 business_keywords，正常处理所有字段
        Object.keys(firstCase).forEach(key => {
          if (!excludeFields.includes(key)) {
            let label = columnLabelMap[key] || key
            if (!columnLabelMap[key] && /^[\u4e00-\u9fa5]+$/.test(key)) {
              label = key
            } else if (!columnLabelMap[key]) {
              label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
            }
            
            dynamicColumns.push({ prop: key, label: label, minWidth: 150 })
          }
        })
      }
      
      previewColumns.value = dynamicColumns
      console.log('[DEBUG] Dynamic columns:', dynamicColumns.map(c => c.label).join(', '))
      
      // 更新分页信息
      previewPagination.value.total = selectedDataset.value.record_count
      previewPagination.value.currentPage = 1
      previewPagination.value.pageSize = 20
      
      // 缓存刚生成的LLM预览状态
      saveCurrentPreviewState()
    } else {
      console.log('[INFO] No test_cases in response, showing empty state')
      // 如果没有真实数据，显示空状态（不再生成占位符数据）
      previewData.value = []
      previewColumns.value = []
    }
    
    // 切换到数据集Tab
    leftPanelTab.value = 'datasets'
    
    // 根据是更新还是创建显示不同的消息
    if (selectedDataset.value && selectedDataset.value.id) {
      ElMessage.success(`✓ 已更新 "${selectedDataset.value.name}"，共 ${newDataset.record_count} 条LLM评测数据`)
    } else {
      ElMessage.success(`✓ 已生成 "${newDataset.name}"，共 ${newDataset.record_count} 条LLM评测数据`)
    }
    
    // 优先使用保存的generation_config中的配置
    const config = newDataset.generation_config || {}
    if (config.positive_count && config.negative_count && config.boundary_count) {
      // 使用保存的实际配置
      llmForm.value.positive_count = config.positive_count
      llmForm.value.negative_count = config.negative_count
      llmForm.value.boundary_count = config.boundary_count
      llmForm.value.languages = config.languages || ['zh']
    } else {
      // 如果没有保存的配置，根据record_count估算（兼容旧数据）
      llmForm.value.positive_count = Math.floor(newDataset.record_count * 0.5) || 3
      llmForm.value.negative_count = Math.floor(newDataset.record_count * 0.3) || 1
      llmForm.value.boundary_count = Math.floor(newDataset.record_count * 0.2) || 1
    }
  } catch (error) {
    // 清除超时定时器
    clearTimeout(timeoutId)
    
    console.error('Generate LLM dataset error:', error)
    
    if (error.name === 'AbortError') {
      ElMessage.error('请求超时：AI生成数据时间过长，请稍后重试或减少数据量')
    } else {
      ElMessage.error('生成失败: ' + (error.message || '未知错误'))
    }
  } finally {
    generating.value = false
  }
}

// 生成LLM评测预览数据（已废弃 - 现在使用后端返回的真实数据）
// const generateLLMPreviewData = (dataset) => {
//   // 更新分页信息
//   previewPagination.value.total = dataset.record_count || 100
//   previewPagination.value.currentPage = 1
//   
//   // 生成所有数据（用于后续分页）
//   const allData = []
//   
//   // 根据表单配置生成不同类型的数据
//   const positiveCount = llmForm.value.positive_count || 3
//   const negativeCount = llmForm.value.negative_count || 1
//   const boundaryCount = llmForm.value.boundary_count || 1
//   
//   // 生成正样本数据
//   for (let i = 0; i < positiveCount; i++) {
//     allData.push({
//       case_id: `POS${String(i + 1).padStart(4, '0')}`,
//       scenario: llmForm.value.scenario,
//       type: 'positive',
//       query: `测试查询 ${i + 1} - 正常场景`,
//       expected_response: '这是预期的正确响应',
//       actual_response: '这是实际返回的响应',
//       label: 1,
//       language: llmForm.value.languages[0] || 'zh'
//     })
//   }
//   
//   // 生成负样本数据
//   for (let i = 0; i < negativeCount; i++) {
//     allData.push({
//       case_id: `NEG${String(i + 1).padStart(4, '0')}`,
//       scenario: llmForm.value.scenario,
//       type: 'negative',
//       query: `测试查询 ${i + 1} - 异常场景`,
//       expected_response: '应该返回错误提示',
//       actual_response: '实际返回了错误',
//       label: 0,
//       language: llmForm.value.languages[0] || 'zh'
//     })
//   }
//   
//   // 生成边界测试数据
//   for (let i = 0; i < boundaryCount; i++) {
//     allData.push({
//       case_id: `BND${String(i + 1).padStart(4, '0')}`,
//       scenario: llmForm.value.scenario,
//       type: 'boundary',
//       query: `测试查询 ${i + 1} - 边界条件`,
//       expected_response: '边界情况处理',
//       actual_response: '实际边界响应',
//       label: -1,
//       language: llmForm.value.languages[0] || 'zh'
//     })
//   }
//   
//   // 将生成的数据存储到previewData中
//   previewData.value = allData
//   
//   // 设置列定义
//   previewColumns.value = [
//     { prop: 'case_id', label: '用例ID', width: 120 },
//     { prop: 'type', label: '类型', width: 100 },
//     { prop: 'query', label: '查询', minWidth: 200 },
//     { prop: 'expected_response', label: '预期响应', minWidth: 200 },
//     { prop: 'label', label: '标签', width: 80 },
//     { prop: 'language', label: '语言', width: 80 }
//   ]
// }

// 数据集操作
const handleDatasetAction = async (command, dataset) => {
  switch (command) {
    case 'view':
      selectDataset(dataset)
      break
    case 'versions':
      selectedDataset.value = dataset
      await loadVersions()
      versionsDialogVisible.value = true
      break
    case 'export':
      try {
        // 获取当前选中数据集的预览数据
        const dataToExport = previewData.value.length > 0 ? previewData.value : []
        
        if (dataToExport.length === 0) {
          ElMessage.warning('该数据集暂无数据可导出')
          return
        }
        
        // 使用数据集保存的导出格式（如果没有则根据类型选择默认格式）
        let exportFormat = dataset.export_format || 'json'
        if (!dataset.export_format && dataset.dataset_type === 'llm_eval') {
          exportFormat = 'csv'
        }
        
        // 执行导出
        await exportDataset(dataset, dataToExport, exportFormat)
        
        ElMessage.success(`✓ 已导出 ${dataToExport.length} 条数据`)
      } catch (error) {
        console.error('Export error:', error)
        ElMessage.error('导出失败')
      }
      break
    case 'delete':
      try {
        await ElMessageBox.confirm(`确定要删除数据集"${dataset.name}"吗？`, '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        // 从前端列表中删除
        const index = datasets.value.findIndex(d => d.id === dataset.id)
        if (index > -1) {
          datasets.value.splice(index, 1)
          // 保存到localStorage
          saveDatasetsToStorage()
          // 如果删除的是当前选中的数据集，清空选中状态
          if (selectedDataset.value?.id === dataset.id) {
            selectedDataset.value = null
            previewData.value = []
            previewColumns.value = []
          }
          ElMessage.success('删除成功')
        } else {
          ElMessage.error('删除失败：数据集不存在')
        }
      } catch (error) {
        if (error !== 'cancel') {
          console.error('Delete error:', error)
          ElMessage.error('删除失败')
        }
      }
      break
  }
}

// 导出数据集
const exportDataset = (dataset, data, format) => {
  let content = ''
  let filename = `${dataset.name}.${format}`
  let mimeType = ''
  
  // 获取列配置（优先使用previewColumns中的中文标签）
  const columns = previewColumns.value.length > 0 ? previewColumns.value : []
  const hasColumnConfig = columns.length > 0
  
  if (format === 'json') {
    // JSON格式 - 保持原始数据结构
    content = JSON.stringify(data, null, 2)
    mimeType = 'application/json'
  } else if (format === 'csv') {
    // CSV格式 - 使用中文列标题
    const csvRows = []
    
    if (hasColumnConfig) {
      // 有列配置，使用中文标签作为表头
      const headers = columns.map(col => col.label || col.prop)
      csvRows.push(headers.join(','))
      
      // 添加数据行
      data.forEach(row => {
        const values = columns.map(col => {
          const value = row[col.prop]
          // 处理包含逗号或引号的值
          if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
            return `"${value.replace(/"/g, '""')}"`
          }
          return value ?? ''
        })
        csvRows.push(values.join(','))
      })
    } else {
      // 无列配置，使用原始字段名
      const headers = Object.keys(data[0] || {})
      csvRows.push(headers.join(','))
      
      data.forEach(row => {
        const values = headers.map(header => {
          const value = row[header]
          if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
            return `"${value.replace(/"/g, '""')}"`
          }
          return value ?? ''
        })
        csvRows.push(values.join(','))
      })
    }
    
    content = csvRows.join('\n')
    mimeType = 'text/csv;charset=utf-8;'
    filename = `${dataset.name}.csv`
  } else if (format === 'sql') {
    // SQL格式（INSERT语句）- 使用中文列名
    const tableName = dataset.name.replace(/\s+/g, '_').toLowerCase()
    const sqlStatements = []
    
    if (hasColumnConfig) {
      // 有列配置，使用中文列名
      const columnNames = columns.map(col => `\`${col.label || col.prop}\``).join(', ')
      
      data.forEach(row => {
        const values = columns.map(col => {
          const val = row[col.prop]
          if (typeof val === 'string') {
            return `'${val.replace(/'/g, "''")}'`
          }
          return val ?? 'NULL'
        }).join(', ')
        
        sqlStatements.push(`INSERT INTO ${tableName} (${columnNames}) VALUES (${values});`)
      })
    } else {
      // 无列配置，使用原始字段名
      const columnNames = Object.keys(data[0] || {}).map(key => `\`${key}\``).join(', ')
      
      data.forEach(row => {
        const values = Object.values(row).map(val => {
          if (typeof val === 'string') {
            return `'${val.replace(/'/g, "''")}'`
          }
          return val ?? 'NULL'
        }).join(', ')
        
        sqlStatements.push(`INSERT INTO ${tableName} (${columnNames}) VALUES (${values});`)
      })
    }
    
    content = sqlStatements.join('\n')
    mimeType = 'application/sql;charset=utf-8;'
    filename = `${dataset.name}.sql`
  } else if (format === 'excel') {
    // Excel格式 - 使用Tab分隔，支持中文列标题
    const excelRows = []
    
    if (hasColumnConfig) {
      // 有列配置，使用中文标签作为表头
      const headers = columns.map(col => col.label || col.prop)
      excelRows.push(headers.join('\t'))
      
      data.forEach(row => {
        const values = columns.map(col => row[col.prop] ?? '')
        excelRows.push(values.join('\t'))
      })
    } else {
      // 无列配置，使用原始字段名
      const headers = Object.keys(data[0] || {})
      excelRows.push(headers.join('\t'))
      
      data.forEach(row => {
        const values = headers.map(header => row[header] ?? '')
        excelRows.push(values.join('\t'))
      })
    }
    
    content = '\uFEFF' + excelRows.join('\n') // 添加BOM标记以支持中文
    mimeType = 'application/vnd.ms-excel;charset=utf-8;'
    filename = `${dataset.name}.xls`
  }
  
  // 创建下载链接
  const blob = new Blob([content], { type: mimeType })
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)
  
  link.setAttribute('href', url)
  link.setAttribute('download', filename)
  link.style.visibility = 'hidden'
  
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  
  // 释放URL对象
  URL.revokeObjectURL(url)
}

// 加载预置模板列表
const loadPresetTemplates = async () => {
  templatesLoading.value = true
  
  // 强制使用模拟数据（用于测试）
  const forceMockData = true
  
  if (forceMockData) {
    console.log('[TEMPLATES] Using mock data (forced)')
    useMockTemplates()
    templatesLoading.value = false
    return
  }
  
  try {
    // 获取token - 优先从localStorage的access_token获取
    const token = localStorage.getItem('access_token') || localStorage.getItem('token')
    
    if (!token) {
      console.warn('No auth token found, using mock data')
      throw new Error('未登录')
    }
    
    // 调用真实API获取预置模板列表
    const response = await fetch('/api/data-factory/preset-templates/', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })
    
    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('认证失败，请重新登录')
      }
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const data = await response.json()
    let templates = data.results || data
    
    // 确保所有模板都有version字段（默认为ecommerce）
    templates = templates.map(t => ({
      ...t,
      version: t.version || 'ecommerce'  // 如果没有version字段，默认为跨境电商版
    }))
    
    presetTemplates.value = templates
    
    console.log('Loaded templates from API:', presetTemplates.value.length)
    console.log('Ecommerce templates:', presetTemplates.value.filter(t => t.version === 'ecommerce').length)
    console.log('Fintech templates:', presetTemplates.value.filter(t => t.version === 'fintech').length)
  } catch (error) {
    console.error('Load templates error:', error)
    ElMessage.warning('使用模拟数据: ' + error.message)
    
    // 降级到模拟数据
    useMockTemplates()
  } finally {
    templatesLoading.value = false
  }
}

// 使用模拟模板数据
const useMockTemplates = () => {
  presetTemplates.value = [
    // ========== 跨境电商版模板 ==========
    {
      id: 1,
      version: 'ecommerce',
      name: '跨境电商订单数据',
      business_type: 'order',
      description: '生成包含订单ID、金额、币种、商品信息的完整订单数据',
      usage_count: 128,
      field_definitions: [],
      boundary_rules: {},
      faker_mappings: {}
    },
    {
      id: 2,
      version: 'ecommerce',
      name: '国际物流追踪数据',
      business_type: 'logistics',
      description: '生成物流单号、运输状态、轨迹信息等物流相关数据',
      usage_count: 95,
      field_definitions: [],
      boundary_rules: {},
      faker_mappings: {}
    },
    {
      id: 3,
      version: 'ecommerce',
      name: '售后工单数据',
      business_type: 'after_sales',
      description: '生成退款申请、退货工单、投诉记录等售后场景数据',
      usage_count: 67,
      field_definitions: [],
      boundary_rules: {},
      faker_mappings: {}
    },
    {
      id: 4,
      version: 'ecommerce',
      name: '商家入驻信息',
      business_type: 'merchant',
      description: '生成商家资质、店铺信息、联系方式等商家相关数据',
      usage_count: 42,
      field_definitions: [],
      boundary_rules: {},
      faker_mappings: {}
    },
    
    // ========== 金融科技版模板 ==========
    {
      id: 101,
      version: 'fintech',
      name: '银行账户交易流水',
      business_type: 'bank_transaction',
      description: '生成银行账号、交易时间、金额、对方账户、交易类型等流水数据',
      usage_count: 56,
      field_definitions: [],
      boundary_rules: {},
      faker_mappings: {}
    },
    {
      id: 102,
      version: 'fintech',
      name: '信用卡消费记录',
      business_type: 'credit_card',
      description: '生成信用卡号、商户名称、消费金额、分期期数、还款状态等数据',
      usage_count: 43,
      field_definitions: [],
      boundary_rules: {},
      faker_mappings: {}
    },
    {
      id: 103,
      version: 'fintech',
      name: '贷款申请数据',
      business_type: 'loan_application',
      description: '生成申请人姓名、身份证号、贷款金额、利率、抵押物等信贷数据',
      usage_count: 38,
      field_definitions: [],
      boundary_rules: {},
      faker_mappings: {}
    },
    {
      id: 104,
      version: 'fintech',
      name: '投资理财产品信息',
      business_type: 'investment_product',
      description: '生成产品名称、预期收益率、风险等级、起投金额、期限等理财数据',
      usage_count: 29,
      field_definitions: [],
      boundary_rules: {},
      faker_mappings: {}
    }
  ]
  
  console.log('[TEMPLATES] Mock data loaded:')
  console.log('  Total:', presetTemplates.value.length)
  console.log('  Ecommerce:', presetTemplates.value.filter(t => t.version === 'ecommerce').length)
  console.log('  Fintech:', presetTemplates.value.filter(t => t.version === 'fintech').length)
  
  ElMessage.success(`已加载 ${presetTemplates.value.length} 个模板（电商${presetTemplates.value.filter(t => t.version === 'ecommerce').length}个 + 金融${presetTemplates.value.filter(t => t.version === 'fintech').length}个）`)
}

// 版本切换处理
const handleVersionChange = (version) => {
  console.log('[VERSION] Switched to:', version)
  
  // 关键修复：更新当前版本（必须在过滤之前）
  currentVersion.value = version
  
  // 保留上一个选中的数据集，如果它仍属于当前版本则恢复选中
  const previousDataset = selectedDataset.value
  
  // 先清空当前选中的数据集和预览数据
  selectedDataset.value = null
  previewData.value = []
  previewColumns.value = []
  
  // 重置业务域选择
  structuredForm.value.business_domain = ''
  
  // 如果上一个选中的数据集仍属于当前版本，重新选中并加载真实数据
  if (previousDataset) {
    const dsVersion = previousDataset.version || 'ecommerce'
    if (dsVersion === version) {
      selectDataset(previousDataset)
    }
  }
  
  // 显示提示
  const versionName = version === 'ecommerce' ? '跨境电商版' : '金融科技版'
  ElMessage.success(`已切换到 ${versionName}`)
}

// 调试模板加载
const debugTemplates = () => {
  console.log('=== Template Debug Info ===')
  console.log('presetTemplates:', presetTemplates.value)
  console.log('presetTemplates.length:', presetTemplates.value.length)
  console.log('filteredTemplates:', filteredTemplates.value)
  console.log('filteredTemplates.length:', filteredTemplates.value.length)
  console.log('templateFilter:', templateFilter.value)
  ElMessage.info(`已加载 ${presetTemplates.value.length} 个模板, 过滤后: ${filteredTemplates.value.length}`)
}

// 从模板加载到数据集
const loadTemplateToDataset = async (template) => {
  try {
    // TODO: 调用API加载模板配置
    // const res = await dataFactoryAPI.loadFromTemplate(template.id)
    // structuredForm.value.fields = res.field_definitions
    // structuredForm.value.boundary_tests = Object.keys(res.boundary_rules)

    // 切换面板
    leftPanelTab.value = 'datasets'
    activeTab.value = 'structured'
    // 关键修复：先同步更新业务域下拉框的值
    structuredForm.value.business_domain = template.business_type

    // 模拟加载字段定义
    if (template.business_type === 'order') {
      structuredForm.value.fields = [
        { name: 'order_id', type: 'string', nullable: false, description: '订单唯一标识' },
        { name: 'customer_name', type: 'string', nullable: false, description: '客户姓名' },
        { name: 'amount', type: 'decimal', nullable: false, description: '订单金额' },
        { name: 'currency', type: 'string', nullable: false, description: '币种代码' },
        { name: 'items_count', type: 'integer', nullable: false, description: '商品数量' },
      ]
      
      // 生成示例预览数据
      previewData.value = [
        { order_id: 'ORD20240602001', customer_name: '张三', amount: 299.99, currency: 'USD', items_count: 3 },
        { order_id: 'ORD20240602002', customer_name: '李四', amount: 159.50, currency: 'EUR', items_count: 2 },
        { order_id: 'ORD20240602003', customer_name: '王五', amount: 89.00, currency: 'CNY', items_count: 1 },
      ]
      
      // 设置预览列
      previewColumns.value = [
        { prop: 'order_id', label: '订单号', width: 160 },
        { prop: 'customer_name', label: '客户', width: 100 },
        { prop: 'amount', label: '金额', width: 100 },
        { prop: 'currency', label: '币种', width: 80 },
        { prop: 'items_count', label: '数量', width: 80 },
      ]
    } else if (template.business_type === 'logistics') {
      structuredForm.value.fields = [
        { name: 'tracking_number', type: 'string', nullable: false, description: '物流单号' },
        { name: 'carrier', type: 'string', nullable: false, description: '承运商' },
        { name: 'status', type: 'string', nullable: false, description: '运输状态' },
        { name: 'origin', type: 'string', nullable: true, description: '始发地' },
        { name: 'destination', type: 'string', nullable: false, description: '目的地' },
      ]
      
      previewData.value = [
        { tracking_number: 'SF1234567890', carrier: '顺丰速运', status: '运输中', origin: '深圳', destination: '北京' },
        { tracking_number: 'YT9876543210', carrier: '圆通速递', status: '已签收', origin: '上海', destination: '广州' },
        { tracking_number: 'ZTO5678901234', carrier: '中通快递', status: '待揽收', origin: '杭州', destination: '成都' },
      ]
      
      previewColumns.value = [
        { prop: 'tracking_number', label: '物流单号', width: 160 },
        { prop: 'carrier', label: '承运商', width: 120 },
        { prop: 'status', label: '状态', width: 100 },
        { prop: 'origin', label: '始发地', width: 100 },
        { prop: 'destination', label: '目的地', width: 100 },
      ]
    } else if (template.business_type === 'after_sales') {
      structuredForm.value.fields = [
        { name: 'ticket_id', type: 'string', nullable: false, description: '工单编号' },
        { name: 'order_id', type: 'string', nullable: false, description: '关联订单' },
        { name: 'type', type: 'string', nullable: false, description: '工单类型' },
        { name: 'reason', type: 'string', nullable: false, description: '申请原因' },
        { name: 'amount', type: 'decimal', nullable: true, description: '退款金额' },
      ]
      
      previewData.value = [
        { ticket_id: 'TK20240602001', order_id: 'ORD20240601001', type: '退款', reason: '商品质量问题', amount: 299.99 },
        { ticket_id: 'TK20240602002', order_id: 'ORD20240601002', type: '退货', reason: '尺码不合适', amount: 159.50 },
        { ticket_id: 'TK20240602003', order_id: 'ORD20240601003', type: '换货', reason: '颜色不符', amount: null },
      ]
      
      previewColumns.value = [
        { prop: 'ticket_id', label: '工单号', width: 140 },
        { prop: 'order_id', label: '订单号', width: 140 },
        { prop: 'type', label: '类型', width: 80 },
        { prop: 'reason', label: '原因', width: 160 },
        { prop: 'amount', label: '退款金额', width: 100 },
      ]
    } else if (template.business_type === 'merchant') {
      structuredForm.value.fields = [
        { name: 'merchant_id', type: 'string', nullable: false, description: '商家ID' },
        { name: 'shop_name', type: 'string', nullable: false, description: '店铺名称' },
        { name: 'contact_person', type: 'string', nullable: false, description: '联系人' },
        { name: 'phone', type: 'string', nullable: false, description: '联系电话' },
        { name: 'business_license', type: 'string', nullable: true, description: '营业执照号' },
      ]
      
      previewData.value = [
        { merchant_id: 'MCH001', shop_name: '优品数码专营店', contact_person: '陈经理', phone: '138****1234', business_license: '91440300MA5DXXXX' },
        { merchant_id: 'MCH002', shop_name: '时尚服饰旗舰店', contact_person: '林女士', phone: '139****5678', business_license: '91310000MA1KXXXX' },
        { merchant_id: 'MCH003', shop_name: '家居生活馆', contact_person: '王先生', phone: '137****9012', business_license: null },
      ]
      
      previewColumns.value = [
        { prop: 'merchant_id', label: '商家ID', width: 100 },
        { prop: 'shop_name', label: '店铺名称', width: 160 },
        { prop: 'contact_person', label: '联系人', width: 100 },
        { prop: 'phone', label: '联系电话', width: 120 },
        { prop: 'business_license', label: '营业执照', width: 160 },
      ]
    }
    
    // ========== 金融科技版模板字段定义 ==========
    else if (template.business_type === 'bank_transaction') {
      structuredForm.value.fields = [
        { name: 'account_number', type: 'string', nullable: false, description: '银行账号' },
        { name: 'transaction_time', type: 'date', nullable: false, description: '交易时间' },
        { name: 'amount', type: 'decimal', nullable: false, description: '交易金额' },
        { name: 'counterparty_account', type: 'string', nullable: true, description: '对方账户' },
        { name: 'transaction_type', type: 'string', nullable: false, description: '交易类型(转账/存款/取款)' },
      ]
      
      previewData.value = [
        { account_number: '6222021234567890', transaction_time: '2026-06-04 10:23:45', amount: 5000.00, counterparty_account: '6222029876543210', transaction_type: '转账' },
        { account_number: '6222021234567890', transaction_time: '2026-06-04 14:56:12', amount: -200.00, counterparty_account: '', transaction_type: '取款' },
        { account_number: '6222021234567890', transaction_time: '2026-06-05 09:15:30', amount: 10000.00, counterparty_account: '6222021111222233', transaction_type: '存款' },
      ]
      
      previewColumns.value = [
        { prop: 'account_number', label: '银行账号', width: 180 },
        { prop: 'transaction_time', label: '交易时间', width: 160 },
        { prop: 'amount', label: '交易金额', width: 100 },
        { prop: 'counterparty_account', label: '对方账户', width: 180 },
        { prop: 'transaction_type', label: '交易类型', width: 100 },
      ]
    } else if (template.business_type === 'credit_card') {
      structuredForm.value.fields = [
        { name: 'card_number', type: 'string', nullable: false, description: '信用卡号' },
        { name: 'merchant_name', type: 'string', nullable: false, description: '商户名称' },
        { name: 'consumption_amount', type: 'decimal', nullable: false, description: '消费金额' },
        { name: 'installment_periods', type: 'integer', nullable: true, description: '分期期数' },
        { name: 'repayment_status', type: 'string', nullable: false, description: '还款状态' },
      ]
      
      previewData.value = [
        { card_number: '4532****1234', merchant_name: '京东超市', consumption_amount: 299.99, installment_periods: null, repayment_status: '已还清' },
        { card_number: '4532****1234', merchant_name: '星巴克咖啡', consumption_amount: 35.00, installment_periods: null, repayment_status: '待还款' },
        { card_number: '4532****1234', merchant_name: 'Apple Store', consumption_amount: 8999.00, installment_periods: 12, repayment_status: '分期中' },
      ]
      
      previewColumns.value = [
        { prop: 'card_number', label: '信用卡号', width: 140 },
        { prop: 'merchant_name', label: '商户名称', width: 140 },
        { prop: 'consumption_amount', label: '消费金额', width: 100 },
        { prop: 'installment_periods', label: '分期期数', width: 100 },
        { prop: 'repayment_status', label: '还款状态', width: 100 },
      ]
    } else if (template.business_type === 'loan_application') {
      structuredForm.value.fields = [
        { name: 'applicant_name', type: 'string', nullable: false, description: '申请人姓名' },
        { name: 'id_card', type: 'string', nullable: false, description: '身份证号' },
        { name: 'loan_amount', type: 'decimal', nullable: false, description: '贷款金额' },
        { name: 'interest_rate', type: 'decimal', nullable: false, description: '年利率(%)' },
        { name: 'collateral', type: 'string', nullable: true, description: '抵押物' },
      ]
      
      previewData.value = [
        { applicant_name: '张三', id_card: '110101199001011234', loan_amount: 500000.00, interest_rate: 4.35, collateral: '房产' },
        { applicant_name: '李四', id_card: '310101198505056789', loan_amount: 200000.00, interest_rate: 4.75, collateral: '车辆' },
        { applicant_name: '王五', id_card: '440101199208089012', loan_amount: 100000.00, interest_rate: 5.20, collateral: null },
      ]
      
      previewColumns.value = [
        { prop: 'applicant_name', label: '申请人', width: 100 },
        { prop: 'id_card', label: '身份证号', width: 180 },
        { prop: 'loan_amount', label: '贷款金额', width: 120 },
        { prop: 'interest_rate', label: '年利率(%)', width: 100 },
        { prop: 'collateral', label: '抵押物', width: 100 },
      ]
    } else if (template.business_type === 'investment_product') {
      structuredForm.value.fields = [
        { name: 'product_name', type: 'string', nullable: false, description: '产品名称' },
        { name: 'expected_return', type: 'decimal', nullable: false, description: '预期收益率(%)' },
        { name: 'risk_level', type: 'string', nullable: false, description: '风险等级' },
        { name: 'min_investment', type: 'decimal', nullable: false, description: '起投金额' },
        { name: 'term_months', type: 'integer', nullable: false, description: '期限(月)' },
      ]
      
      previewData.value = [
        { product_name: '稳健理财A款', expected_return: 3.50, risk_level: '低风险', min_investment: 10000.00, term_months: 12 },
        { product_name: '进取型债券B款', expected_return: 5.80, risk_level: '中风险', min_investment: 50000.00, term_months: 24 },
        { product_name: '高收益信托C款', expected_return: 8.20, risk_level: '高风险', min_investment: 100000.00, term_months: 36 },
      ]
      
      previewColumns.value = [
        { prop: 'product_name', label: '产品名称', width: 160 },
        { prop: 'expected_return', label: '预期收益率(%)', width: 120 },
        { prop: 'risk_level', label: '风险等级', width: 100 },
        { prop: 'min_investment', label: '起投金额', width: 120 },
        { prop: 'term_months', label: '期限(月)', width: 100 },
      ]
    }

    // 自动创建并保存数据集到左侧列表
    // 引用模板时默认数据量为3条（与预览数据数量一致）
    const defaultCount = 3
    structuredForm.value.count = defaultCount
    
    const newDataset = {
      id: Date.now(),
      name: template.name,
      purpose: '',
      dataset_type: 'structured',
      business_domain: template.business_type,
      version: template.version || currentVersion.value, // 保存版本信息（关键：版本隔离）
      record_count: defaultCount,
      file_size: Math.floor(defaultCount * 1024),
      status: 'completed',
      export_format: structuredForm.value.export_format || 'json', // 保存导出格式
      created_at: new Date().toISOString(),
      template_id: template.id, // 标记为模板引用，不可编辑名称
      is_template_reference: true // 额外标记，用于前端判断
    }
    
    // 添加到数据集列表顶部
    datasets.value.unshift(newDataset)
    
    // 保存到localStorage
    saveDatasetsToStorage()
    
    // 自动选中新建的数据集
    selectedDataset.value = newDataset
    
    // 显示简单的成功提示（不弹窗）
    ElMessage.success(`✓ 已引用模板 "${template.name}"，共 ${structuredForm.value.fields.length} 个字段，已保存到数据集列表`)
  } catch (error) {
    console.error('Load template error:', error)
    ElMessage.error('加载模板失败')
  }
}

// 预览数据操作函数
const addPreviewRow = () => {
  if (!selectedDataset.value) return
  
  // 根据业务域创建新行
  const newRow = {}
  structuredForm.value.fields.forEach(field => {
    if (field.type === 'string') newRow[field.name] = ''
    else if (field.type === 'integer') newRow[field.name] = 0
    else if (field.type === 'decimal') newRow[field.name] = 0.00
    else if (field.type === 'boolean') newRow[field.name] = false
    else newRow[field.name] = null
  })
  
  previewData.value.push(newRow)
  ElMessage.success('已添加新行')
}

const removePreviewRow = (index) => {
  try {
    ElMessageBox.confirm('确定要删除这一行吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(() => {
      previewData.value.splice(index, 1)
      ElMessage.success('已删除')
    }).catch(() => {})
  } catch (error) {
    console.error('Remove row error:', error)
  }
}

const deleteSelectedRows = () => {
  if (selectedPreviewRows.value.length === 0) return
  
  try {
    ElMessageBox.confirm(`确定要删除选中的 ${selectedPreviewRows.value.length} 行吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(() => {
      // 从后往前删除，避免索引变化
      const indices = previewData.value.map((row, idx) => 
        selectedPreviewRows.value.includes(row) ? idx : -1
      ).filter(i => i !== -1).sort((a, b) => b - a)
      
      indices.forEach(idx => {
        previewData.value.splice(idx, 1)
      })
      
      selectedPreviewRows.value = []
      ElMessage.success(`已删除 ${indices.length} 行`)
    }).catch(() => {})
  } catch (error) {
    console.error('Delete rows error:', error)
  }
}

const handlePreviewSelectionChange = (selection) => {
  selectedPreviewRows.value = selection
}

const onCellBlur = (row, prop) => {
  // 单元格失去焦点时的处理（可以添加验证逻辑）
  console.log(`Cell edited: ${prop} = ${row[prop]}`)
}

const isEditableField = (prop) => {
  // 判断字段是否可编辑（除了ID类字段）
  return !prop.toLowerCase().includes('_id') && !prop.toLowerCase().includes('license')
}

const formatCellValue = (value, prop) => {
  // 格式化单元格显示值
  if (value === null || value === undefined) return '-'
  if (typeof value === 'boolean') return value ? '是' : '否'
  return value
}

const savePreviewAsDataset = () => {
  if (!selectedDataset.value || previewData.value.length === 0) return
  
  try {
    ElMessageBox.confirm(
      `将当前 ${previewData.value.length} 条预览数据保存为正式数据集？`,
      '确认保存',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    ).then(async () => {
      // 创建正式数据集
      const formalDataset = {
        ...selectedDataset.value,
        id: Date.now(),
        name: selectedDataset.value.name.replace('（预览）', ''),
        status: 'completed',
        record_count: previewData.value.length,
        file_size: Math.floor(previewData.value.length * 1024),
        created_at: new Date().toISOString()
      }
      
      // 添加到列表
      datasets.value.unshift(formalDataset)
      selectedDataset.value = formalDataset
      
      ElMessage.success('✓ 数据集保存成功')
    }).catch(() => {})
  } catch (error) {
    console.error('Save dataset error:', error)
    ElMessage.error('保存失败')
  }
}

// 加载版本历史
const loadVersions = async () => {
  if (!selectedDataset.value) return

  try {
    // TODO: 调用API获取版本列表
    // const res = await dataFactoryAPI.getVersions(selectedDataset.value.id)
    // versions.value = res

    // 模拟数据
    versions.value = [
      {
        id: 1,
        version_number: 'v1.0',
        description: '初始版本',
        snapshot_records_count: 500,
        is_current: false,
        created_by_username: 'admin',
        created_at: '2024-06-01T10:00:00Z'
      },
      {
        id: 2,
        version_number: 'v1.1',
        description: '增加边界测试数据',
        snapshot_records_count: 600,
        is_current: true,
        created_by_username: 'admin',
        created_at: '2024-06-02T15:30:00Z'
      }
    ]
  } catch (error) {
    console.error('Load versions error:', error)
    ElMessage.error('加载版本历史失败')
  }
}

// 显示创建版本对话框
const showCreateVersionDialog = () => {
  newVersionDescription.value = ''
  createVersionDialogVisible.value = true
}

// 创建新版本
const createNewVersion = async () => {
  if (!selectedDataset.value) return

  creatingVersion.value = true
  try {
    // TODO: 调用API创建版本
    // await dataFactoryAPI.createVersion(selectedDataset.value.id, {
    //   description: newVersionDescription.value
    // })

    ElMessage.success('版本创建成功')
    createVersionDialogVisible.value = false
    await loadVersions()
  } catch (error) {
    console.error('Create version error:', error)
    ElMessage.error('创建版本失败')
  } finally {
    creatingVersion.value = false
  }
}

// 回滚到指定版本
const rollbackToVersion = async (version) => {
  try {
    await ElMessageBox.confirm(
      `确定要回滚到版本 ${version.version_number} 吗？当前配置将被覆盖。`,
      '确认回滚',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    // TODO: 调用API回滚
    // await dataFactoryAPI.rollback(selectedDataset.value.id, {
    //   version_id: version.id
    // })

    ElMessage.success(`已回滚到版本 ${version.version_number}`)
    await loadVersions()
    await loadDatasets()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Rollback error:', error)
      ElMessage.error('回滚失败')
    }
  }
}

// 批量导出选择变化
const handleBatchExportSelection = (selection) => {
  batchExportSelected.value = selection
}

// 执行批量导出
const executeBatchExport = async () => {
  if (batchExportSelected.value.length === 0) {
    ElMessage.warning('请至少选择一个数据集')
    return
  }

  exporting.value = true
  try {
    // TODO: 调用API批量导出
    // const res = await dataFactoryAPI.batchExport({
    //   dataset_ids: batchExportSelected.value.map(d => d.id),
    //   format: batchExportFormat.value
    // })
    // 下载文件...

    ElMessage.success(`已导出 ${batchExportSelected.value.length} 个数据集`)
    batchExportDialogVisible.value = false
  } catch (error) {
    console.error('Batch export error:', error)
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

// 添加字段
const addField = () => {
  console.log('[ADD FIELD] Before adding, fields count:', structuredForm.value.fields.length)
  structuredForm.value.fields.push({
    name: '',
    description: '',
    type: 'string',
    nullable: false
  })
  console.log('[ADD FIELD] After adding, fields count:', structuredForm.value.fields.length)
  
  // 滚动到表格底部，确保新字段可见
  nextTick(() => {
    const container = document.querySelector('.fields-table-container')
    if (container) {
      container.scrollTop = container.scrollHeight
    }
    // 聚焦到新行的第一个输入框
    const inputs = container?.querySelectorAll('.el-input__inner')
    const lastRowStart = (structuredForm.value.fields.length - 1) * 5
    if (inputs && inputs[lastRowStart]) {
      inputs[lastRowStart].focus()
    }
  })
}

// 移除字段
const removeField = (index) => {
  structuredForm.value.fields.splice(index, 1)
}

// 辅助函数
const getTypeLabel = (type) => {
  const map = {
    'structured': '结构化',
    'llm_eval': 'LLM评测',
    'agent_dialog': 'Agent对话'
  }
  return map[type] || type
}

// 从场景描述中提取字段Title
const extractFieldTitle = (scenario) => {
  if (!scenario) return ''
  
  // 查找各种可能的标题格式
  const patterns = ['字段Title:', '字段标题:', '字段Title：', '字段标题：', 'Title:', '标题:', 'Title：', '标题：']
  for (const pattern of patterns) {
    if (scenario.includes(pattern)) {
      let result = scenario.split(pattern)[1].trim()
      
      // 去除"内容:"及其后面的部分（因为内容是场景限定，不是字段标题）
      const contentPatterns = ['内容:', '内容：']
      for (const contentPattern of contentPatterns) {
        if (result.includes(contentPattern)) {
          result = result.split(contentPattern)[0].trim()
        }
      }
      
      // 去除末尾的标点符号
      result = result.replace(/[。.，,、\s]*$/, '')
      
      return result
    }
  }
  
  // 如果没有找到，返回空字符串
  return ''
}

const getTypeColor = (type) => {
  const map = {
    'structured': 'success',
    'llm_eval': 'warning',
    'agent_dialog': 'info'
  }
  return map[type] || ''
}

const getBusinessDomainLabel = (domain) => {
  const map = {
    'order': '订单',
    'user': '用户',
    'logistics': '物流',
    'after_sales': '售后'
  }
  return map[domain] || domain
}

const getBusinessTypeLabel = (type) => {
  const map = {
    'order': '订单',
    'logistics': '物流',
    'after_sales': '售后',
    'merchant': '商家'
  }
  return map[type] || type
}

const getStatusLabel = (status) => {
  const map = {
    'draft': '草稿',
    'generating': '生成中',
    'completed': '已完成',
    'failed': '失败'
  }
  return map[status] || status
}

const getStatusColor = (status) => {
  const map = {
    'draft': 'info',
    'generating': 'warning',
    'completed': 'success',
    'failed': 'danger'
  }
  return map[status] || ''
}

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 监控datasets.value的变化，确保所有数据集都有id
watch(
  () => datasets.value,
  (newDatasets) => {
    const invalidDatasets = newDatasets.filter(d => !d || !d.id)
    if (invalidDatasets.length > 0) {
      console.warn('[WATCH] Detected datasets without id:', invalidDatasets)
      // 自动修复：为没有id的数据集生成临时id
      invalidDatasets.forEach((d, idx) => {
        if (!d.id) {
          d.id = Date.now() + idx
          console.log('[WATCH] Auto-generated ID for dataset:', d.name, 'New ID:', d.id)
        }
      })
      saveDatasetsToStorage()
    }
  },
  { deep: true }
)

// 监控llmForm.scenario的变化，自动保存到选中的数据集
watch(
  () => llmForm.value.scenario,
  (newScenario) => {
    if (selectedDataset.value && selectedDataset.value.dataset_type === 'llm_eval') {
      // 只有当场景描述有内容时才保存，或者数据集已经有过配置时才保存
      if (newScenario || (selectedDataset.value.generation_config && selectedDataset.value.generation_config.scenario)) {
        console.log('[WATCH] Saving scenario to dataset:', newScenario?.substring(0, 50))
        // 确保generation_config存在
        if (!selectedDataset.value.generation_config) {
          selectedDataset.value.generation_config = {}
        }
        // 更新场景描述
        selectedDataset.value.generation_config.scenario = newScenario
        // 保存到localStorage
        saveDatasetsToStorage()
      }
    }
  }
)

onMounted(() => {
  loadDatasets()
  loadPresetTemplates()
})

//  keep-alive 激活时刷新数据集和预览（解决切走再回来时状态丢失）
onActivated(() => {
  loadDatasets()
  loadPresetTemplates()
})
</script>

<style scoped>
.data-factory-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f5f7fa;
}

.factory-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: white;
  border-bottom: 1px solid #e4e7ed;
}

.factory-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

/* 版本切换Tab样式 */
.version-tabs {
  flex: 1;
  margin-left: 40px;
  margin-right: 20px;
}

.version-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
  border-bottom: none;
}

.version-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.version-tabs :deep(.el-tabs__item) {
  font-size: 15px;
  font-weight: 500;
  padding: 0 20px;
  height: 40px;
  line-height: 40px;
}

.version-label {
  display: flex;
  align-items: center;
  gap: 6px;
}

.version-label .el-icon {
  font-size: 18px;
}

.factory-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  gap: 16px;
  padding: 16px;
}

/* 左侧面板 */
.dataset-panel {
  width: 380px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.panel-tabs :deep(.el-tabs__content) {
  flex: 1;
  overflow: hidden;
  padding: 0;
}

.panel-tabs :deep(.el-tab-pane) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e4e7ed;
  font-weight: 600;
  font-size: 14px;
}

.dataset-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.dataset-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fafafa;
}

.dataset-item:hover {
  background: #f0f2f5;
}

.dataset-item.active {
  background: #ecf5ff;
  border-left: 3px solid #409eff;
}

.item-info {
  flex: 1;
  min-width: 0;
}

.item-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.item-count {
  font-size: 12px;
  color: #909399;
}

.item-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.item-actions .el-button {
  padding: 6px 12px;
  font-size: 13px;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.item-actions .el-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

/* 模板列表样式 */
.template-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.template-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fafafa;
  border: 1px solid transparent;
}

.template-item:hover {
  background: #f0f2f5;
  border-color: #409eff;
}

.template-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 8px;
  color: white;
  flex-shrink: 0;
}

.template-info {
  flex: 1;
  min-width: 0;
}

.template-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
}

.template-desc {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.usage-count {
  font-size: 12px;
  color: #c0c4cc;
}

/* 中间面板 */
.config-panel {
  flex: 1;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.tab-content {
  padding: 20px;
}

.field-definitions {
  margin-top: 16px;
}

/* 字段定义列表：固定高度数据框 */
.fields-list-box {
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 12px;
}

.fields-list-header {
  display: flex;
  background-color: #f5f7fa;
  border-bottom: 1px solid #dcdfe6;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
  color: #606266;
}

.fields-list-header-cell {
  flex-shrink: 0;
  padding: 0 4px;
}

.fields-list-body {
  max-height: 176px;
  overflow-y: auto;
  background-color: #fff;
}

.fields-list-row {
  display: flex;
  align-items: center;
  padding: 4px 12px;
  border-bottom: 1px solid #ebeef5;
  min-height: 38px;
}

.fields-list-row:last-child {
  border-bottom: none;
}

.fields-list-cell {
  flex-shrink: 0;
  padding: 0 4px;
  display: flex;
  align-items: center;
}

.fields-list-body::-webkit-scrollbar {
  width: 6px;
}

.fields-list-body::-webkit-scrollbar-thumb {
  background-color: #c0c4cc;
  border-radius: 3px;
}

.fields-list-body::-webkit-scrollbar-track {
  background-color: #f5f7fa;
}

.fields-list-footer {
  padding: 6px 12px;
  background-color: #f5f7fa;
  border-top: 1px solid #dcdfe6;
}

/* 添加字段按钮样式 - 确保始终可见 */
.field-definitions .el-button {
  display: block; /* 确保按钮独占一行 */
  width: 100%; /* 全宽显示 */
  margin-top: 0; /* 移除margin，使用容器的padding */
}

/* 右侧面板 */
.preview-panel {
  width: 500px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.preview-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.preview-stats {
  margin-top: 16px;
}

/* 分页组件样式 */
.preview-pagination {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  padding: 8px 0;
}

/* 模板加载成功对话框样式 */
:deep(.template-success-dialog) {
  .el-message-box__header {
    padding-bottom: 0;
  }

  .el-message-box__content {
    font-size: 14px;
    line-height: 1.8;
  }

  .el-message-box__content h4 {
    color: #409EFF;
    font-size: 18px;
    margin-bottom: 12px;
  }

  .el-message-box__content p {
    margin: 8px 0;
    color: #303133;
  }

  .el-message-box__content strong {
    color: #606266;
    font-weight: 600;
  }

  .el-message-box__content ul {
    margin: 8px 0;
    padding-left: 20px;
  }

  .el-message-box__content li {
    margin: 4px 0;
    color: #606266;
  }
}

/* 数据集列表项样式 */
.dataset-item {
  padding: 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s;
  margin-bottom: 8px;
  background: white;
  border: 1px solid #e4e7ed;
}

.dataset-item:hover {
  border-color: #409EFF;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.1);
}

.dataset-item.active {
  border-color: #409EFF;
  background: #ecf5ff;
}

.item-info {
  flex: 1;
}

.item-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-purpose {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-purpose .el-icon {
  flex-shrink: 0;
}

/* 字段Title样式 */
.item-field-title {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #409EFF;
  font-weight: 500;
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-field-title .el-icon {
  flex-shrink: 0;
}

.item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.item-count {
  font-size: 12px;
  color: #909399;
}
</style>
