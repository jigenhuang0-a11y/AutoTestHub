from django.db import models
from django.conf import settings


class TestCase(models.Model):
    """测试用例模型"""
    PRIORITY_CHOICES = [
        ('P0', 'P0 - 最高'),
        ('P1', 'P1 - 高'),
        ('P2', 'P2 - 中'),
        ('P3', 'P3 - 低'),
    ]

    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('active', '激活'),
        ('inactive', '停用'),
    ]

    title = models.CharField('标题', max_length=200)
    description = models.TextField('描述', blank=True, default='')
    api_endpoint = models.CharField('接口地址', max_length=500, blank=True, default='')
    method = models.CharField('请求方法', max_length=10, default='GET')
    headers = models.JSONField('请求头', default=dict, blank=True)
    request_body = models.JSONField('请求体', default=dict, blank=True)
    expected_response = models.JSONField('预期响应', default=dict, blank=True)
    assertion_rules = models.JSONField('断言规则', default=list, blank=True)
    extract_rules = models.JSONField('变量提取规则', default=list, blank=True)
    global_vars = models.JSONField('全局变量', default=list, blank=True)
    context_vars = models.JSONField('上下文变量', default=list, blank=True)
    assertions = models.TextField('断言说明', blank=True, default='')
    priority = models.CharField('优先级', max_length=2, choices=PRIORITY_CHOICES, default='P2')
    status = models.CharField('状态', max_length=10, choices=STATUS_CHOICES, default='draft')
    tags = models.JSONField('标签', default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='test_cases',
        verbose_name='创建人'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'test_cases'
        verbose_name = '测试用例'
        verbose_name_plural = '测试用例'
        ordering = ['-created_at']

    def __str__(self):
        return self.title
