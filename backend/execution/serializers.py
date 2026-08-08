from rest_framework import serializers
from .models import TestExecution


class TestExecutionSerializer(serializers.ModelSerializer):
    """测试执行序列化器"""
    started_by_name = serializers.CharField(source='started_by.username', read_only=True)
    suite_name = serializers.SerializerMethodField()
    suite_id = serializers.SerializerMethodField()
    environment_display = serializers.CharField(source='get_environment_display', read_only=True)
    trigger_type_display = serializers.CharField(source='get_trigger_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = TestExecution
        fields = '__all__'
        read_only_fields = ('id', 'started_at', 'completed_at')

    def get_suite_name(self, obj):
        if obj.test_suite:
            return obj.test_suite.name
        return ''

    def get_suite_id(self, obj):
        if obj.test_suite:
            return obj.test_suite.id
        return None


class ExecutionDetailSerializer(serializers.ModelSerializer):
    """执行详情序列化器 - 包含用例执行结果"""
    started_by_name = serializers.CharField(source='started_by.username', read_only=True)
    suite_name = serializers.SerializerMethodField()
    suite_id = serializers.SerializerMethodField()
    environment_display = serializers.CharField(source='get_environment_display', read_only=True)
    trigger_type_display = serializers.CharField(source='get_trigger_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = TestExecution
        fields = '__all__'
        read_only_fields = ('id', 'started_at', 'completed_at')

    def get_suite_name(self, obj):
        if obj.test_suite:
            return obj.test_suite.name
        return ''

    def get_suite_id(self, obj):
        if obj.test_suite:
            return obj.test_suite.id
        return None
