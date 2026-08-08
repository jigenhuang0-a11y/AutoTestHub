from rest_framework import serializers
from .models import TestCase


class JSONFieldSerializer(serializers.JSONField):
    """自定义JSON字段序列化器，确保始终返回对象"""
    def to_representation(self, value):
        result = super().to_representation(value)
        if result is None or result == 0:
            return {}
        return result


class JSONListFieldSerializer(serializers.JSONField):
    """自定义JSON字段序列化器，确保始终返回数组"""
    def to_representation(self, value):
        result = super().to_representation(value)
        if result is None or result == 0:
            return []
        return result


class TestCaseSerializer(serializers.ModelSerializer):
    """测试用例序列化器"""
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    headers = JSONFieldSerializer(default=dict)
    request_body = JSONFieldSerializer(default=dict)
    expected_response = JSONFieldSerializer(default=dict)
    tags = JSONFieldSerializer(default=list)
    assertion_rules = JSONListFieldSerializer(default=list)
    extract_rules = JSONListFieldSerializer(default=list)

    class Meta:
        model = TestCase
        fields = '__all__'
        read_only_fields = ('id', 'created_by', 'created_at', 'updated_at')

    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user

        # 确保JSON对象字段不为0
        for field in ['headers', 'request_body', 'expected_response']:
            if validated_data.get(field) is None or validated_data.get(field) == 0:
                validated_data[field] = {}
        # 确保JSON数组字段不为0
        for field in ['tags', 'assertion_rules', 'extract_rules']:
            if validated_data.get(field) is None or validated_data.get(field) == 0:
                validated_data[field] = []

        return super().create(validated_data)

    def update(self, instance, validated_data):
        # 确保JSON对象字段不为0
        for field in ['headers', 'request_body', 'expected_response']:
            if field in validated_data:
                if validated_data[field] is None or validated_data[field] == 0:
                    validated_data[field] = {}
        # 确保JSON数组字段不为0
        for field in ['tags', 'assertion_rules', 'extract_rules']:
            if field in validated_data:
                if validated_data[field] is None or validated_data[field] == 0:
                    validated_data[field] = []

        return super().update(instance, validated_data)
