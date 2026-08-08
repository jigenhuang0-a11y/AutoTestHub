from django.db import models
from django.conf import settings


class TestSuite(models.Model):
    """测试套件 - 测试用例的集合/文件夹,方便批量管理和执行"""
    
    name = models.CharField(max_length=200, verbose_name='套件名称')
    description = models.TextField(blank=True, default='', verbose_name='描述')
    test_cases = models.JSONField(default=list, verbose_name='API测试用例ID列表')
    web_test_cases = models.JSONField(default=list, verbose_name='Web测试用例ID列表', blank=True)
    perf_test_cases = models.JSONField(default=list, verbose_name='性能测试用例ID列表', blank=True)
    perf_config = models.JSONField(default=dict, verbose_name='性能用例执行参数', blank=True,
                                    help_text='{case_id: {"users": 20, "duration": 120}}，覆盖性能用例的默认并发和持续时间')
    suite_vars = models.JSONField(default=dict, verbose_name='套件变量汇总', blank=True)
    execution_count = models.IntegerField(default=0, verbose_name='执行次数')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='test_suites', verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = '测试套件'
        verbose_name_plural = '测试套件'
    
    def __str__(self):
        return self.name
    
    def get_test_cases_queryset(self):
        """获取套件中所有API测试用例的QuerySet（按test_cases列表顺序）"""
        from testcases.models import TestCase
        if not self.test_cases:
            return TestCase.objects.none()
        
        # 确保 ID 为整数类型
        case_ids = [int(tcid) for tcid in self.test_cases]
        
        # 使用 CASE WHEN 语句保持 test_cases 列表的顺序
        from django.db.models import Case, When, Value, IntegerField
        preserved_order = Case(
            *[When(id=value, then=Value(index)) for index, value in enumerate(case_ids)],
            output_field=IntegerField()
        )
        return TestCase.objects.filter(id__in=case_ids).order_by(preserved_order)
    
    def get_web_test_cases_queryset(self):
        """获取套件中所有Web测试用例的QuerySet（按web_test_cases列表顺序）"""
        from web_testcases.models import WebTestCase
        if not self.web_test_cases:
            return WebTestCase.objects.none()
        
        case_ids = [int(wid) for wid in self.web_test_cases]
        
        from django.db.models import Case, When, Value, IntegerField
        preserved_order = Case(
            *[When(id=value, then=Value(index)) for index, value in enumerate(case_ids)],
            output_field=IntegerField()
        )
        return WebTestCase.objects.filter(id__in=case_ids).order_by(preserved_order)
    
    def get_perf_test_cases_queryset(self):
        """获取套件中所有性能测试用例的QuerySet（按perf_test_cases列表顺序）"""
        from performance.models import PerfTestCase
        if not self.perf_test_cases:
            return PerfTestCase.objects.none()
        
        case_ids = [int(pid) for pid in self.perf_test_cases]
        
        from django.db.models import Case, When, Value, IntegerField
        preserved_order = Case(
            *[When(id=value, then=Value(index)) for index, value in enumerate(case_ids)],
            output_field=IntegerField()
        )
        return PerfTestCase.objects.filter(id__in=case_ids).order_by(preserved_order)
    
    def get_cases_count(self):
        """获取套件中的用例数量（API + Web + 性能）"""
        api_count = len(self.test_cases) if self.test_cases else 0
        web_count = len(self.web_test_cases) if self.web_test_cases else 0
        perf_count = len(self.perf_test_cases) if self.perf_test_cases else 0
        return api_count + web_count + perf_count
    
    def get_total_case_ids(self):
        """获取所有用例ID（API + Web + 性能），返回合并列表，保持原始顺序"""
        api_ids = [int(tcid) for tcid in (self.test_cases or [])]
        web_ids = [int(wid) for wid in (self.web_test_cases or [])]
        perf_ids = [int(pid) for pid in (self.perf_test_cases or [])]
        return api_ids + web_ids + perf_ids
