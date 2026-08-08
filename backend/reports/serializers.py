from rest_framework import serializers
from .models import TestReport


class TestReportSerializer(serializers.ModelSerializer):
    """测试报告序列化器"""
    execution_name = serializers.CharField(source='execution.name', read_only=True)

    class Meta:
        model = TestReport
        fields = '__all__'
        read_only_fields = ('id', 'created_at')
