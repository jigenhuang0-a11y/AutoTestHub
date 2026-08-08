from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class AIModelConfig(models.Model):
    """AI 模型配置 - 管理员统一配置，用户创建任务时下拉选择"""
    PROVIDER_CHOICES = [
        ('deepseek', 'DeepSeek'),
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic Claude'),
        ('zhipu', '智谱 GLM'),
        ('qwen', '通义千问'),
        ('baidu', '百度文心'),
        ('other', '其他'),
    ]

    name = models.CharField(max_length=100, verbose_name='模型名称')
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='deepseek', verbose_name='提供商')
    model_id = models.CharField(max_length=100, verbose_name='模型ID', help_text='如 deepseek-chat, gpt-4o')
    api_url = models.URLField(verbose_name='API 地址')
    api_key = models.CharField(max_length=500, verbose_name='API Key')
    description = models.TextField(blank=True, default='', verbose_name='描述')

    # 执行参数
    timeout = models.IntegerField(default=30, verbose_name='超时时间(秒)')
    max_tokens = models.IntegerField(default=4096, verbose_name='最大Token数')
    temperature = models.FloatField(default=0.7, verbose_name='温度', help_text='0-2，越低越确定性')

    is_active = models.BooleanField(default=True, verbose_name='启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'ai_model_config'
        ordering=['provider', 'name']
        verbose_name = 'AI 模型配置'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.name} ({self.model_id})'


class EvalTask(models.Model):
    """AI测评任务"""
    STATUS_CHOICES = [
        ('pending', '待执行'),
        ('running', '执行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
        ('cancelled', '已取消'),
    ]
    TARGET_TYPE_CHOICES = [
        ('knowledge_bot', '知识库问答机器人'),
        ('custom_api', '自定义API'),
    ]

    name = models.CharField(max_length=255, verbose_name='任务名称')
    description = models.TextField(blank=True, default='', verbose_name='任务描述')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    target_type = models.CharField(max_length=30, choices=TARGET_TYPE_CHOICES, default='knowledge_bot',
                                   verbose_name='测评目标类型')

    # 测评目标配置
    target_config = models.JSONField(default=dict, verbose_name='目标配置', help_text='如API地址、知识库ID等')

    # 统计字段
    total_questions = models.IntegerField(default=0, verbose_name='问题总数')
    correct_count = models.IntegerField(default=0, verbose_name='回答正确数')
    incorrect_count = models.IntegerField(default=0, verbose_name='回答错误数')
    partial_count = models.IntegerField(default=0, verbose_name='部分正确数')
    error_count = models.IntegerField(default=0, verbose_name='异常数')

    accuracy = models.FloatField(default=0.0, verbose_name='准确率(%)')
    avg_response_time = models.FloatField(default=0.0, verbose_name='平均响应时间(秒)')
    overall_score = models.FloatField(default=0.0, verbose_name='综合评分(0-100)')

    # 安全检测
    security_issues_found = models.IntegerField(default=0, verbose_name='安全风险数')

    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'eval_task'
        ordering = ['-updated_at']
        verbose_name = '测评任务'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class EvalQuestion(models.Model):
    """测评问题"""
    task = models.ForeignKey(EvalTask, on_delete=models.CASCADE, related_name='questions', verbose_name='所属任务')
    index = models.IntegerField(default=0, verbose_name='序号')
    question = models.TextField(verbose_name='问题')
    expected_answer = models.TextField(blank=True, default='', verbose_name='期望答案/关键词')
    category = models.CharField(max_length=50, blank=True, default='general', verbose_name='问题分类',
                                help_text='general/knowledge/procedure/safety/boundary')

    class Meta:
        db_table = 'eval_question'
        ordering = ['task', 'index']
        verbose_name = '测评问题'
        verbose_name_plural = verbose_name


class EvalResult(models.Model):
    """单条测评结果"""
    LEVEL_CHOICES = [
        ('correct', '✅ 正确'),
        ('incorrect', '❌ 错误'),
        ('partial', '⚠️ 部分正确'),
        ('error', '🔴 异常'),
    ]

    task = models.ForeignKey(EvalTask, on_delete=models.CASCADE, related_name='results', verbose_name='所属任务')
    question = models.ForeignKey(EvalQuestion, on_delete=models.CASCADE, related_name='results', verbose_name='问题')
    question_text = models.TextField(verbose_name='问题文本')
    expected_answer = models.TextField(blank=True, default='', verbose_name='期望答案')
    actual_answer = models.TextField(blank=True, default='', verbose_name='实际回答')
    category = models.CharField(max_length=50, blank=True, default='general', verbose_name='问题分类')

    # 评测维度
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='error', verbose_name='判定结果')
    score = models.FloatField(default=0.0, verbose_name='得分(0-100)')
    response_time = models.FloatField(default=0.0, verbose_name='响应时间(秒)')

    # AI评估详情
    ai_evaluation = models.TextField(blank=True, default='', verbose_name='AI评估说明')

    # 安全风险
    has_security_risk = models.BooleanField(default=False, verbose_name='是否有安全风险')
    security_risk_type = models.CharField(max_length=100, blank=True, default='', verbose_name='风险类型',
                                          help_text='如: prompt_injection/data_leak/harmful_content')
    security_risk_detail = models.TextField(blank=True, default='', verbose_name='风险详情')

    # 参考来源（如果是知识库问答）
    has_reference = models.BooleanField(default=False, verbose_name='是否有参考来源')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'eval_result'
        ordering = ['question__index']
        verbose_name = '测评结果'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.question_text[:50]} - {self.level}'


class EvalReport(models.Model):
    """测评报告"""
    task = models.OneToOneField(EvalTask, on_delete=models.CASCADE, related_name='report', verbose_name='所属任务')

    # 总览
    summary = models.TextField(blank=True, default='', verbose_name='总览摘要')

    # 各维度得分
    accuracy_score = models.FloatField(default=0.0, verbose_name='准确率得分')
    speed_score = models.FloatField(default=0.0, verbose_name='响应速度得分')
    safety_score = models.FloatField(default=0.0, verbose_name='安全性得分')
    quality_score = models.FloatField(default=0.0, verbose_name='回答质量得分')

    # 问题分布
    category_stats = models.JSONField(default=dict, verbose_name='分类统计')
    score_distribution = models.JSONField(default=dict, verbose_name='分数分布')
    response_time_stats = models.JSONField(default=dict, verbose_name='响应时间统计')

    # 问题列表
    slow_questions = models.JSONField(default=list, verbose_name='响应慢的问题')
    wrong_questions = models.JSONField(default=list, verbose_name='答错的问题')
    risk_questions = models.JSONField(default=list, verbose_name='安全风险问题')

    # 改进建议
    suggestions = models.JSONField(default=list, verbose_name='改进建议')

    report_html = models.TextField(blank=True, default='', verbose_name='报告HTML')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='生成时间')

    class Meta:
        db_table = 'eval_report'
        verbose_name = '测评报告'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'测评报告 - {self.task.name}'
