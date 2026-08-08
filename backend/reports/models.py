from django.db import models
from django.conf import settings


class TestReport(models.Model):
    """测试报告模型"""
    execution = models.OneToOneField(
        'execution.TestExecution',
        on_delete=models.CASCADE,
        related_name='report',
        verbose_name='执行记录'
    )
    title = models.CharField('报告标题', max_length=200)
    summary = models.TextField('报告摘要', blank=True, default='')
    report_html = models.TextField('HTML报告内容', blank=True, default='')
    report_path = models.CharField('报告文件路径', max_length=500, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'test_reports'
        verbose_name = '测试报告'
        verbose_name_plural = '测试报告'
        ordering = ['-created_at']

    def __str__(self):
        return self.title
