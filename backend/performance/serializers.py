from rest_framework import serializers
from .models import PerfTestCase, PerfExecution


class PerfTestCaseSerializer(serializers.ModelSerializer):
    """性能测试用例序列化器"""
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    test_type_display = serializers.CharField(source='get_test_type_display', read_only=True)
    execution_count = serializers.SerializerMethodField()
    last_execution_status = serializers.SerializerMethodField()

    class Meta:
        model = PerfTestCase
        fields = '__all__'
        read_only_fields = ('id', 'created_by', 'created_at', 'updated_at')

    def get_execution_count(self, obj):
        return obj.executions.count()

    def get_last_execution_status(self, obj):
        # 只显示手动执行（非套件触发）的最近状态
        last = obj.executions.filter(suite_execution__isnull=True).first()
        if last:
            return {'id': last.id, 'status': last.status, 'status_display': last.get_status_display()}
        return None



class PerfExecutionSerializer(serializers.ModelSerializer):
    """性能测试执行记录序列化器"""
    test_case = serializers.PrimaryKeyRelatedField(read_only=True)
    test_case_name = serializers.CharField(source='test_case.name', read_only=True)
    test_case_url = serializers.CharField(source='test_case.target_url', read_only=True)
    test_case_method = serializers.CharField(source='test_case.method', read_only=True)
    started_by_name = serializers.CharField(source='started_by.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    failure_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = PerfExecution
        fields = '__all__'
        read_only_fields = ('id', 'started_by', 'started_at', 'completed_at',
                           'total_requests', 'requests_per_second', 'failures',
                           'avg_response_time', 'min_response_time', 'max_response_time',
                           'p50_response_time', 'p90_response_time', 'p95_response_time', 'p99_response_time',
                           'metrics_timeline', 'thresholds_passed', 'threshold_errors', 'execution_log')


class PerfExecutionCreateSerializer(serializers.Serializer):
    """新建/重跑执行的请求体"""
    test_case_id = serializers.IntegerField(required=True, help_text='性能用例ID')
    execution_id = serializers.IntegerField(required=False, help_text='执行记录ID（重跑模式复用原记录）')
