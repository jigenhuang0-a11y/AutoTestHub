from rest_framework import serializers
from .models import TestSuite
from testcases.models import TestCase


class WebTestCaseInSuiteSerializer(serializers.Serializer):
    """Web 用例在套件中的简化序列化"""
    id = serializers.IntegerField()
    title = serializers.CharField()
    url = serializers.CharField(required=False, default='')
    status = serializers.CharField(required=False, default='')


class PerfTestCaseInSuiteSerializer(serializers.Serializer):
    """性能测试用例在套件中的简化序列化"""
    id = serializers.IntegerField()
    name = serializers.CharField()
    target_url = serializers.CharField(required=False, default='')
    method = serializers.CharField(required=False, default='GET')
    test_type = serializers.CharField(required=False, default='baseline')
    users = serializers.IntegerField(required=False, default=10)
    duration = serializers.IntegerField(required=False, default=60)


class TestCaseInSuiteSerializer(serializers.ModelSerializer):
    """套件中的用例序列化器（包含 extract_rules）"""
    class Meta:
        model = TestCase
        fields = ['id', 'title', 'method', 'api_endpoint', 'status', 'priority', 'extract_rules']


class TestSuiteSerializer(serializers.ModelSerializer):
    """测试套件序列化器"""
    
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    cases_count = serializers.SerializerMethodField()
    test_case_details = serializers.SerializerMethodField()
    web_test_case_details = serializers.SerializerMethodField()
    perf_test_case_details = serializers.SerializerMethodField()
    pending_schedule = serializers.SerializerMethodField()
    
    class Meta:
        model = TestSuite
        fields = [
            'id', 'name', 'description', 'test_cases', 'web_test_cases', 'perf_test_cases',
            'perf_config',
            'created_by', 
            'created_by_username', 'cases_count', 'execution_count',
            'test_case_details', 'web_test_case_details', 'perf_test_case_details',
            'suite_vars',
            'pending_schedule',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def get_cases_count(self, obj):
        return obj.get_cases_count()
    
    def get_test_case_details(self, obj):
        """获取套件中 API 用例的详细信息"""
        cases = obj.get_test_cases_queryset()
        return TestCaseInSuiteSerializer(cases, many=True).data

    def get_web_test_case_details(self, obj):
        """获取套件中 Web 用例的详细信息"""
        if not obj.web_test_cases:
            return []
        from web_testcases.models import WebTestCase
        cases = WebTestCase.objects.filter(id__in=obj.web_test_cases)
        # 保持列表顺序
        ordered = []
        for wid in obj.web_test_cases:
            for c in cases:
                if c.id == wid:
                    ordered.append(c)
                    break
        return WebTestCaseInSuiteSerializer(ordered, many=True).data

    def get_perf_test_case_details(self, obj):
        """获取套件中性能测试用例的详细信息"""
        if not obj.perf_test_cases:
            return []
        cases = obj.get_perf_test_cases_queryset()
        return PerfTestCaseInSuiteSerializer(cases, many=True).data

    def get_pending_schedule(self, obj):
        """获取该套件待执行的定时任务信息（最近的一条 pending scheduled 任务）"""
        from execution.models import TestExecution
        from django.utils import timezone
        try:
            schedule = TestExecution.objects.filter(
                test_suite=obj,
                trigger_type='scheduled',
                status='pending',
                scheduled_at__isnull=False,
            ).order_by('scheduled_at').first()
            if schedule:
                # 过期锁定自动清理：已锁定 + 已过期 → 解锁，返回 None
                if schedule.locked and schedule.scheduled_at and schedule.scheduled_at < timezone.now():
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f'定时任务 #{schedule.id} 已过期且锁定，自动清理 '
                        f'(原定时间: {schedule.scheduled_at})'
                    )
                    schedule.locked = False
                    schedule.status = 'failed'  # 标记为失败（过期未执行）
                    schedule.save(update_fields=['locked', 'status'])
                    return None

                return {
                    'id': schedule.id,
                    'scheduled_at': schedule.scheduled_at.isoformat() if schedule.scheduled_at else None,
                    'environment': schedule.environment,
                    'locked': schedule.locked,
                    'started_by_id': schedule.started_by_id,
                    'started_by_username': schedule.started_by.username if schedule.started_by else None,
                }
            return None
        except Exception:
            return None
    
    def validate_test_cases(self, value):
        """验证 API 测试用例ID列表"""
        if not isinstance(value, list):
            raise serializers.ValidationError('API测试用例必须是列表格式')
        
        if value:
            existing_ids = set(TestCase.objects.filter(id__in=value).values_list('id', flat=True))
            invalid_ids = set(value) - existing_ids
            if invalid_ids:
                raise serializers.ValidationError(f'以下API用例ID不存在: {invalid_ids}')
        
        return value

    def validate_web_test_cases(self, value):
        """验证 Web 测试用例ID列表"""
        if not isinstance(value, list):
            raise serializers.ValidationError('Web测试用例必须是列表格式')
        
        if value:
            from web_testcases.models import WebTestCase
            existing_ids = set(WebTestCase.objects.filter(id__in=value).values_list('id', flat=True))
            invalid_ids = set(value) - existing_ids
            if invalid_ids:
                raise serializers.ValidationError(f'以下Web用例ID不存在: {invalid_ids}')
        
        return value

    def validate_perf_test_cases(self, value):
        """验证性能测试用例ID列表"""
        if not isinstance(value, list):
            raise serializers.ValidationError('性能测试用例必须是列表格式')
        
        if value:
            from performance.models import PerfTestCase
            existing_ids = set(PerfTestCase.objects.filter(id__in=value).values_list('id', flat=True))
            invalid_ids = set(value) - existing_ids
            if invalid_ids:
                raise serializers.ValidationError(f'以下性能用例ID不存在: {invalid_ids}')
        
        return value
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """更新套件时，同时更新用例的 extract_rules 和 api_endpoint"""
        # 处理 suite_vars
        if 'suite_vars' in validated_data:
            instance.suite_vars = validated_data.pop('suite_vars')
        
        # 处理 test_case_details 中的字段
        test_case_details = self.initial_data.get('test_case_details', [])
        if test_case_details:
            for tc_data in test_case_details:
                if 'id' in tc_data:
                    try:
                        tc = TestCase.objects.get(id=tc_data['id'])
                        # 保存所有可编辑字段
                        if 'extract_rules' in tc_data:
                            tc.extract_rules = tc_data['extract_rules']
                        if 'api_endpoint' in tc_data:
                            tc.api_endpoint = tc_data['api_endpoint']
                        if 'headers' in tc_data:
                            tc.headers = tc_data['headers']
                        if 'request_body' in tc_data:
                            tc.request_body = tc_data['request_body']
                        if 'method' in tc_data:
                            tc.method = tc_data['method']
                        tc.save()
                    except TestCase.DoesNotExist:
                        pass
        
        return super().update(instance, validated_data)