from django.db import models
from django.conf import settings


class TestExecution(models.Model):
    """测试执行记录模型"""
    STATUS_CHOICES = [
        ('pending', '等待中'),
        ('running', '执行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
        ('partial', '部分通过'),
    ]

    TRIGGER_CHOICES = [
        ('manual_suite', '套件执行'),
        ('manual_case', '用例执行'),
        ('debug', '调试模式'),
        ('scheduled', '定时任务'),
        ('ci', 'CI/CD'),
    ]

    ENVIRONMENT_CHOICES = [
        ('dev', '开发环境'),
        ('test', '测试环境'),
        ('prod', '生产环境'),
    ]

    name = models.CharField('执行名称', max_length=200, blank=True, default='')
    test_suite = models.ForeignKey(
        'testsuites.TestSuite',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='executions',
        verbose_name='关联套件'
    )
    test_cases = models.JSONField('API测试用例ID列表', default=list)
    web_test_cases = models.JSONField('Web测试用例ID列表', default=list, blank=True)
    perf_test_cases = models.JSONField('性能测试用例ID列表', default=list, blank=True)
    status = models.CharField('状态', max_length=10, choices=STATUS_CHOICES, default='pending')
    trigger_type = models.CharField('触发方式', max_length=20, choices=TRIGGER_CHOICES, default='manual_suite')
    environment = models.CharField('环境', max_length=10, choices=ENVIRONMENT_CHOICES, default='dev')
    total_count = models.IntegerField('用例总数', default=0)
    passed_count = models.IntegerField('通过数', default=0)
    failed_count = models.IntegerField('失败数', default=0)
    skipped_count = models.IntegerField('跳过数', default=0)
    execution_log = models.TextField('执行日志', blank=True, default='')
    execution_results = models.JSONField('用例执行结果详情', default=list, blank=True)
    allure_report_path = models.CharField('Allure报告路径', max_length=500, blank=True, default='')
    duration = models.IntegerField('执行耗时(秒)', default=0)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='executions',
        verbose_name='执行人'
    )
    started_at = models.DateTimeField('开始时间', auto_now_add=True)
    completed_at = models.DateTimeField('完成时间', null=True, blank=True)
    scheduled_at = models.DateTimeField('计划执行时间', null=True, blank=True, help_text='定时任务: 设定何时自动执行')
    locked = models.BooleanField('已锁定', default=False, help_text='锁定后不可修改或取消定时任务')

    class Meta:
        db_table = 'test_executions'
        verbose_name = '测试执行记录'
        verbose_name_plural = '测试执行记录'
        ordering = ['-started_at']

    def __str__(self):
        return self.name or f'执行 #{self.id}'
