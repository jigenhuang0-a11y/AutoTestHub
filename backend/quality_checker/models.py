from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class QualityCheckTask(models.Model):
    """质检任务"""
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processing', '处理中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ]
    
    name = models.CharField(max_length=255, verbose_name='任务名称')
    description = models.TextField(blank=True, default='', verbose_name='任务描述')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    total_cases = models.IntegerField(default=0, verbose_name='用例总数')
    passed_cases = models.IntegerField(default=0, verbose_name='合格用例数')
    warning_cases = models.IntegerField(default=0, verbose_name='警告用例数')
    failed_cases = models.IntegerField(default=0, verbose_name='不合格用例数')
    overall_score = models.FloatField(default=0.0, verbose_name='综合评分')
    pass_rate = models.FloatField(default=0.0, verbose_name='通过率(%)')
    scenario = models.CharField(max_length=20, default='general', verbose_name='测试场景',
                                help_text='general-功能测试, api-接口测试')
    # 质检规则配置
    check_duplicates = models.BooleanField(default=True, verbose_name='检查重复')
    check_completeness = models.BooleanField(default=True, verbose_name='检查完整性')
    check_format = models.BooleanField(default=True, verbose_name='检查格式规范')
    check_content_quality = models.BooleanField(default=True, verbose_name='检查内容质量')
    duplicate_threshold = models.FloatField(default=0.85, verbose_name='相似度阈值')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'quality_check_task'
        ordering = ['-created_at']
        verbose_name = '质检任务'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class QualityCheckResult(models.Model):
    """单个用例的质检结果"""
    task = models.ForeignKey(QualityCheckTask, on_delete=models.CASCADE, related_name='results', verbose_name='所属任务')
    case_id = models.CharField(max_length=100, blank=True, default='', verbose_name='用例编号')
    case_title = models.CharField(max_length=500, verbose_name='用例标题')
    case_content = models.JSONField(default=dict, verbose_name='用例内容')
    score = models.FloatField(default=0.0, verbose_name='评分(0-100)')
    level = models.CharField(max_length=20, default='warning', verbose_name='等级',
                             help_text='pass/warning/fail')
    
    # 各维度得分
    completeness_score = models.FloatField(default=0.0, verbose_name='完整性得分')
    format_score = models.FloatField(default=0.0, verbose_name='格式规范得分')
    content_score = models.FloatField(default=0.0, verbose_name='内容质量得分')
    
    # 问题详情
    issues = models.JSONField(default=list, verbose_name='问题列表')
    suggestions = models.JSONField(default=list, verbose_name='优化建议')
    duplicate_of = models.CharField(max_length=100, blank=True, default='', verbose_name='疑似重复于')
    duplicate_similarity = models.FloatField(default=0.0, verbose_name='重复相似度')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'quality_check_result'
        ordering = ['-score']
        verbose_name = '质检结果'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.case_title} - {self.score}分'


class QualityStandard(models.Model):
    """质检标准/规则配置"""
    name = models.CharField(max_length=255, verbose_name='规则名称')
    rule_type = models.CharField(max_length=50, verbose_name='规则类型',
                                 help_text='completeness/format/content/duplicate')
    description = models.TextField(blank=True, default='', verbose_name='规则描述')
    weight = models.FloatField(default=1.0, verbose_name='权重')
    check_points = models.JSONField(default=list, verbose_name='检查点')
    deduction_rules = models.JSONField(default=dict, verbose_name='扣分规则')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'quality_standard'
        ordering = ['rule_type', '-weight']
        verbose_name = '质检标准'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.name} ({self.get_rule_type_display()})'
