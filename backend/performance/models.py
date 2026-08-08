"""
性能测试模块 — 数据模型
PerfTestCase:        性能测试用例（目标URL、并发参数、断言阈值）
PerfExecution:       执行记录（QPS、P50/P90/P95/P99、实时指标时间线）
"""
from django.db import models
from django.conf import settings


class PerfTestCase(models.Model):
    """性能测试用例"""
    STATUS_CHOICES = [
        ('active', '启用'),
        ('inactive', '停用'),
    ]
    METHOD_CHOICES = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('DELETE', 'DELETE'),
    ]
    TEST_TYPE_CHOICES = [
        ('baseline', '基准测试'),
        ('ramp', '阶梯递增'),
        ('spike', '尖峰测试'),
        ('stress', '压力测试'),
        ('mixed', '混合场景'),
    ]

    name = models.CharField('用例名称', max_length=200)
    target_url = models.URLField('目标URL', max_length=500)
    method = models.CharField('请求方法', max_length=10, choices=METHOD_CHOICES, default='GET')
    headers = models.JSONField('请求头', default=dict, blank=True,
                               help_text='例如 {"Content-Type": "application/json", "Authorization": "Bearer xxx"}')
    body = models.JSONField('请求体', null=True, blank=True,
                            help_text='POST/PUT 请求体，JSON 格式')

    # 测试类型（核心差异化）
    test_type = models.CharField('测试类型', max_length=20, choices=TEST_TYPE_CHOICES, default='baseline',
                                 help_text='基准=固定并发 / 梯度=阶梯加压找拐点 / 混合=多接口权重配比')

    # 压测参数
    users = models.IntegerField('并发用户数', default=10, help_text='同时发压的虚拟用户数')
    spawn_rate = models.IntegerField('每秒启动用户数', default=1, help_text='用户启动速率，默认每秒启动1个')
    duration = models.IntegerField('持续时间(秒)', default=60, help_text='压测持续时长')

    # 梯度增压专属参数
    ramp_step_users = models.IntegerField('每步增加用户数', default=5,
                                          help_text='梯度增压模式下，每个阶梯增加的用户数')
    ramp_step_duration = models.IntegerField('每步持续时间(秒)', default=30,
                                             help_text='梯度增压模式下，每个阶梯的持续时间')

    # 混合场景专属参数
    mixed_scenarios = models.JSONField('混合场景配置', default=list, blank=True,
                                       help_text='混合场景下多接口按权重配比，格式: [{"url":"...","method":"GET","headers":{},"body":null,"weight":70}]')

    # 断言阈值
    max_avg_response_time = models.IntegerField('最大平均响应时间(ms)', default=1000,
                                                 help_text='平均响应时间超过此值视为性能不达标')
    max_p95_response_time = models.IntegerField('最大P95响应时间(ms)', default=2000,
                                                 help_text='P95响应时间超过此值视为性能不达标')
    max_failure_rate = models.FloatField('最大失败率', default=0.01,
                                          help_text='请求失败率超过此值视为性能不达标，例如 0.01 = 1%')

    # 元信息
    status = models.CharField('状态', max_length=10, choices=STATUS_CHOICES, default='active')
    description = models.TextField('描述', blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='perf_test_cases',
        verbose_name='创建人'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'perf_test_cases'
        verbose_name = '性能测试用例'
        verbose_name_plural = '性能测试用例'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.method} {self.target_url})'


class PerfExecution(models.Model):
    """性能测试执行记录"""
    STATUS_CHOICES = [
        ('pending', '等待中'),
        ('running', '执行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
        ('stopped', '已停止'),
    ]

    test_case = models.ForeignKey(
        PerfTestCase,
        on_delete=models.CASCADE,
        related_name='executions',
        verbose_name='性能用例'
    )

    status = models.CharField('状态', max_length=10, choices=STATUS_CHOICES, default='pending')
    test_type = models.CharField('测试类型', max_length=20, default='baseline')

    # 压测参数快照（执行时的参数，方便回溯）
    users = models.IntegerField('并发用户数')
    duration = models.IntegerField('持续时间(秒)')

    # 汇总指标
    total_requests = models.IntegerField('总请求数', default=0)
    requests_per_second = models.FloatField('QPS', default=0)
    failures = models.IntegerField('失败数', default=0)

    # 响应时间分布 (ms)
    avg_response_time = models.FloatField('平均响应时间(ms)', default=0)
    min_response_time = models.FloatField('最小响应时间(ms)', default=0)
    max_response_time = models.FloatField('最大响应时间(ms)', default=0)
    p50_response_time = models.FloatField('P50响应时间(ms)', default=0)
    p90_response_time = models.FloatField('P90响应时间(ms)', default=0)
    p95_response_time = models.FloatField('P95响应时间(ms)', default=0)
    p99_response_time = models.FloatField('P99响应时间(ms)', default=0)

    # 时间序列指标（每秒采样，用于实时曲线图）
    metrics_timeline = models.JSONField('指标时间线', default=list, blank=True)
    # 格式: [{"timestamp": 1, "rps": 10.5, "users": 10, "p50": 12.3, "p95": 45.6, "p99": 89.1, "avg": 25.4, "failures_per_sec": 0.0}, ...]

    # 断言结果
    thresholds_passed = models.BooleanField('阈值通过', default=True)
    threshold_errors = models.JSONField('阈值违规', default=list, blank=True)

    # AI 诊断总结（结构化）
    exec_summary = models.JSONField('AI 执行总结', default=dict, blank=True,
                                    help_text='AI 诊断后的结构化总结，包含 score/summary/issues/recommendations')

    # 执行日志
    execution_log = models.TextField('执行日志', blank=True, default='')

    # 元数据
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='perf_executions',
        verbose_name='执行人'
    )
    suite_execution = models.ForeignKey(
        'execution.TestExecution',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='perf_executions',
        verbose_name='所属套件执行',
        help_text='当从测试套件中触发时，关联到套件执行记录'
    )
    started_at = models.DateTimeField('开始时间', auto_now_add=True)
    completed_at = models.DateTimeField('完成时间', null=True, blank=True)

    class Meta:
        db_table = 'perf_executions'
        verbose_name = '性能测试执行记录'
        verbose_name_plural = '性能测试执行记录'
        ordering = ['-started_at']

    def __str__(self):
        return f'性能执行 #{self.id} — {self.test_case.name}'

    @property
    def failure_rate(self):
        if self.total_requests == 0:
            return 0
        return round(self.failures / self.total_requests, 4)
