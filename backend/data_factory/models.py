from django.db import models
from django.conf import settings


class DataFactoryDataset(models.Model):
    """数据集主表"""
    DATASET_TYPE_CHOICES = [
        ('structured', '结构化数据'),
        ('llm_eval', 'LLM评测数据'),
        ('agent_dialog', 'Agent对话数据'),
    ]

    BUSINESS_DOMAIN_CHOICES = [
        ('order', '订单'),
        ('user', '用户'),
        ('logistics', '物流'),
        ('after_sales', '售后'),
    ]

    name = models.CharField('数据集名称', max_length=200)
    dataset_type = models.CharField('数据类型', max_length=20, choices=DATASET_TYPE_CHOICES)
    business_domain = models.CharField('业务域', max_length=20, choices=BUSINESS_DOMAIN_CHOICES, blank=True, null=True)
    description = models.TextField('描述', blank=True)
    purpose = models.CharField('用途说明', max_length=500, blank=True, help_text='例如：618活动订单测试、跨境退货流程Agent评测等')

    # 生成配置快照（JSON存储）
    generation_config = models.JSONField('生成配置', default=dict, blank=True)

    # 统计信息
    record_count = models.IntegerField('记录数', default=0)
    file_size = models.BigIntegerField('文件大小(字节)', default=0)

    # 状态管理
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('generating', '生成中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ]
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='draft')

    # 版本管理
    version = models.CharField('版本号', max_length=20, default='v1.0')
    parent_dataset = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='父数据集')
    change_log = models.TextField('变更日志', blank=True)

    # LLM评测配置
    eval_config = models.JSONField('评测配置', default=dict, blank=True)
    sample_distribution = models.JSONField('样本分布', default=dict, blank=True)

    # 平台集成
    linked_suites = models.JSONField('关联套件', default=list, blank=True)

    # 审计字段
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='创建人')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'data_factory_dataset'
        verbose_name = '数据集'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_dataset_type_display()})"


class DataFactoryRecord(models.Model):
    """单条数据记录"""
    dataset = models.ForeignKey(DataFactoryDataset, on_delete=models.CASCADE, related_name='records', verbose_name='所属数据集')

    # 数据内容（JSON存储，支持灵活结构）
    data_content = models.JSONField('数据内容', default=dict)

    # 元数据
    tags = models.JSONField('标签', default=list, blank=True)  # 如 ["positive_sample", "difficult"]
    difficulty_level = models.CharField('难度级别', max_length=10, choices=[
        ('easy', '简单'),
        ('medium', '中等'),
        ('hard', '困难'),
    ], blank=True, null=True)

    # LLM评测专用字段
    expected_output = models.JSONField('期望输出', default=dict, blank=True)  # 用于评测对比
    actual_output = models.JSONField('实际输出', default=dict, blank=True)    # 测试后填充

    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'data_factory_record'
        verbose_name = '数据记录'
        indexes = [
            models.Index(fields=['dataset', 'created_at']),
        ]

    def __str__(self):
        return f"Record {self.id} in {self.dataset.name}"


class DataFactoryTemplate(models.Model):
    """造数模板"""
    TEMPLATE_SCOPE_CHOICES = [
        ('global', '全局共享'),
        ('team', '团队私有'),
        ('personal', '个人私有'),
    ]

    name = models.CharField('模板名称', max_length=200)
    template_type = models.CharField('模板类型', max_length=20, choices=[
        ('order', '订单模板'),
        ('user', '用户模板'),
        ('logistics', '物流模板'),
        ('after_sales', '售后模板'),
        ('llm_prompt', 'LLM Prompt模板'),
    ])

    # 模板配置
    field_definitions = models.JSONField('字段定义', default=list)  # 字段结构列表
    generation_rules = models.JSONField('生成规则', default=dict)   # Faker规则映射
    prompt_template = models.TextField('Prompt模板', blank=True)    # LLM场景用

    # 适用范围
    scope = models.CharField('适用范围', max_length=20, choices=TEMPLATE_SCOPE_CHOICES, default='global')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='所有者')

    # 使用统计
    usage_count = models.IntegerField('使用次数', default=0)

    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'data_factory_template'
        verbose_name = '造数模板'
        ordering = ['-usage_count']

    def __str__(self):
        return self.name


class PresetTemplate(models.Model):
    """预置业务模板"""
    BUSINESS_TYPE_CHOICES = [
        ('order', '订单'),
        ('logistics', '物流'),
        ('after_sales', '售后'),
        ('merchant', '商家'),
    ]

    name = models.CharField('模板名称', max_length=200)
    business_type = models.CharField('业务类型', max_length=20, choices=BUSINESS_TYPE_CHOICES)
    description = models.TextField('描述', blank=True)

    # 字段定义（JSON存储）
    field_definitions = models.JSONField('字段定义', default=list)
    # 边界规则包
    boundary_rules = models.JSONField('边界规则', default=dict, blank=True)
    # Faker映射
    faker_mappings = models.JSONField('Faker映射', default=dict, blank=True)

    # 状态和统计
    is_active = models.BooleanField('是否启用', default=True)
    usage_count = models.IntegerField('使用次数', default=0)

    # 审计
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='创建人')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'data_factory_preset_template'
        verbose_name = '预置模板'
        ordering = ['-usage_count']

    def __str__(self):
        return f"{self.name} ({self.get_business_type_display()})"


class DataFactoryDatasetVersion(models.Model):
    """数据集版本快照"""
    dataset = models.ForeignKey(DataFactoryDataset, on_delete=models.CASCADE, related_name='versions', verbose_name='所属数据集')
    version_number = models.CharField('版本号', max_length=20)
    description = models.TextField('版本说明', blank=True)

    # 快照数据
    snapshot_config = models.JSONField('配置快照', default=dict)
    snapshot_records_count = models.IntegerField('记录数快照', default=0)

    # 回滚支持
    is_current = models.BooleanField('是否当前版本', default=False)
    parent_version = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='父版本')

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='创建人')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'data_factory_dataset_version'
        verbose_name = '数据集版本'
        ordering = ['-created_at']
        unique_together = [['dataset', 'version_number']]

    def __str__(self):
        return f"{self.dataset.name} - {self.version_number}"


class DataFactoryUsageLog(models.Model):
    """数据集引用日志"""
    dataset = models.ForeignKey(DataFactoryDataset, on_delete=models.CASCADE, verbose_name='被引用数据集')
    testcase = models.ForeignKey('testcases.TestCase', on_delete=models.CASCADE, verbose_name='引用用例')

    referenced_fields = models.JSONField('引用字段', default=list)  # 如 ["order_id", "amount"]
    reference_type = models.CharField('引用类型', max_length=20, choices=[
        ('precondition', '前置条件'),
        ('request_param', '请求参数'),
        ('assertion', '断言数据'),
    ])

    referenced_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='引用人')
    referenced_at = models.DateTimeField('引用时间', auto_now_add=True)

    class Meta:
        db_table = 'data_factory_usage_log'
        verbose_name = '引用日志'
        unique_together = [['dataset', 'testcase']]

    def __str__(self):
        return f"{self.dataset.name} -> {self.testcase.name}"
