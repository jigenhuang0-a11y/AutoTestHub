# 功能增强说明

## 新增功能概览

### 1. 数据看板 Dashboard

**文件**: `frontend/src/views/Dashboard.vue`

#### 功能特性

##### 顶部指标卡（4个）
- **总用例数**: 显示当前系统中的测试用例总数，含趋势百分比
- **今日通过率**: 今日测试执行的通过率，含较昨日的变化
- **缺陷密度**: 每千行代码的缺陷数量，含较上周的变化
- **自动化覆盖率**: 自动化测试覆盖的百分比，含较上月的变化

##### 报错趋势曲线图（ECharts折线图）
- 展示最近7天的错误数量变化趋势
- 支持切换7天/30天视图
- 平滑曲线 + 渐变填充效果
- Tooltip悬浮提示详细数据

##### 缺陷根因鱼骨图（ECharts关系图）
- 按5大类别分类：人员、环境、代码、数据、配置
- 力导向布局展示因果关系
- 节点大小反映缺陷数量
- 支持拖拽和缩放交互

##### 测试能效仪表盘（3个ECharts仪表盘）
- **执行率**: 已执行用例占总用例的比例
- **通过率**: 通过用例占执行用例的比例
- **缺陷发现率**: 发现缺陷的比率
- 动态指针动画 + 进度条显示

##### 最近执行记录表格
- 展示最近10条执行记录
- 显示ID、名称、总数、通过/失败数、状态、时间
- 点击"详情"按钮查看完整执行日志
- 支持刷新按钮手动更新

##### 错误日志实时滚动区
- 黑色背景 + 绿色文字（终端风格）
- 实时滚动显示最新错误日志（每3秒模拟一条）
- 显示时间戳、日志级别（ERROR/WARN/INFO）、消息内容
- 支持清空按钮清除所有日志
- 自动滚动到最新消息

---

### 2. AI生成用例页面增强

**文件**: `frontend/src/views/AIGenerate.vue`

#### 已有功能
- 左侧输入接口文档
- 点击"AI生成"调用通义千问API
- 右侧显示生成的用例列表（折叠面板形式）
- 每条用例显示：标题、描述、接口地址、方法、请求头、请求体、预期响应、断言、优先级
- 复选框选择要保存的用例
- "全选"按钮快速选择所有用例
- "保存选中"按钮批量保存到数据库
- "生成后直接保存"开关选项

---

### 3. 测试报告页面增强

**文件**: `frontend/src/views/ReportView.vue`

#### 新增功能

##### PDF下载
- 安装 `html2pdf.js` 库
- 点击"PDF"按钮下载报告
- 自动生成包含报告标题、执行信息、摘要的PDF文件
- 文件名格式：`{报告标题}_{时间戳}.pdf`
- 下载时按钮显示Loading状态

##### Allure报告HTML嵌入
- 使用iframe嵌入Allure报告的HTML内容
- 支持sandbox安全策略
- "新窗口打开"按钮在独立窗口查看完整报告
- 响应式高度适配

##### 空状态优化
- 无报告时显示插画 + "去执行测试"引导按钮
- 无HTML报告内容时显示文档图标 + 提示文字

---

### 4. 全局交互体验优化

#### Toast通知系统
**文件**: `frontend/src/utils/helpers.js`

提供统一的提示函数：
```javascript
import { showSuccess, showError, showWarning } from '@/utils/helpers'

showSuccess('操作成功')   // 成功提示（绿色）
showError('操作失败')     // 错误提示（红色）
showWarning('请注意')     // 警告提示（橙色）
```

#### 确认对话框
```javascript
import { showConfirm, showDeleteConfirm } from '@/utils/helpers'

// 普通确认
await showConfirm('确定要执行此操作吗？')

// 删除确认（红色按钮）
await showDeleteConfirm('确定要删除吗？此操作不可恢复')
```

#### 加载状态
- 按钮Loading: `:loading="isLoading"`
- 表格骨架屏: `<TableSkeleton :rows="5" :cols="4" />`
- 全屏加载: `createLoading({ text: '加载中...' })`

#### 空状态组件
**文件**: `frontend/src/components/EmptyState.vue`

```vue
<EmptyState
  title="暂无数据"
  description="点击按钮创建第一条数据"
>
  <template #icon>
    <el-icon :size="80"><Document /></el-icon>
  </template>
  <template #action>
    <el-button type="primary">新建</el-button>
  </template>
</EmptyState>
```

#### 骨架屏组件
**文件**: `frontend/src/components/TableSkeleton.vue`

```vue
<TableSkeleton :rows="5" :cols="4" :col-widths="['60px', '150px', '100px', '80px']" />
```

---

## 技术栈更新

### 新增依赖

```json
{
  "echarts": "^5.x",
  "vue-echarts": "^6.x",
  "html2pdf.js": "^0.x"
}
```

### 新增文件

```
frontend/src/
├── components/
│   ├── TableSkeleton.vue      # 表格骨架屏组件
│   └── EmptyState.vue         # 空状态组件
├── utils/
│   └── helpers.js             # 工具函数库
└── views/
    └── Dashboard.vue          # 数据看板页面
```

---

## 路由更新

新增Dashboard路由作为首页：

```javascript
{
  path: '/dashboard',
  name: 'Dashboard',
  component: () => import('@/views/Dashboard.vue'),
  meta: { requiresAuth: true, title: '数据看板' },
}
```

侧边栏菜单顺序：
1. 数据看板 (默认首页)
2. 测试用例
3. AI生成
4. 测试执行
5. 测试报告

---

## 使用示例

### Dashboard数据刷新
Dashboard页面会在挂载时自动加载数据，错误日志会每3秒模拟添加一条。实际项目中应替换为WebSocket或轮询获取真实数据。

### PDF报告下载
在报告列表页面，点击任意报告的"PDF"按钮即可下载。需要后端返回有效的 `report_html` 字段。

### 空状态显示
当表格数据为空时，自动显示EmptyState组件，包含引导操作的按钮。

### 删除确认
所有删除操作都会弹出二次确认对话框，防止误操作。

---

## 注意事项

1. **ECharts配置**: Dashboard中的图表数据目前为模拟数据，实际项目需要从后端API获取真实数据
2. **错误日志**: Dashboard的错误日志目前是前端模拟生成，实际应通过WebSocket连接后端实时推送
3. **PDF下载**: html2pdf.js在前端生成PDF，对于复杂HTML可能需要调整配置以获得最佳效果
4. **Allure报告**: iframe嵌入需要后端提供完整的HTML报告内容，注意CSP策略配置
