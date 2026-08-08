from rest_framework import serializers
from .models import DataFactoryDataset, DataFactoryRecord, DataFactoryTemplate, DataFactoryUsageLog, PresetTemplate, DataFactoryDatasetVersion


class DataFactoryDatasetSerializer(serializers.ModelSerializer):
    """数据集序列化器"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = DataFactoryDataset
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class PresetTemplateSerializer(serializers.ModelSerializer):
    """预置模板序列化器"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    business_type_display = serializers.CharField(source='get_business_type_display', read_only=True)

    class Meta:
        model = PresetTemplate
        fields = '__all__'
        read_only_fields = ['usage_count', 'created_at', 'updated_at', 'created_by']


class DataFactoryDatasetVersionSerializer(serializers.ModelSerializer):
    """数据集版本序列化器"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = DataFactoryDatasetVersion
        fields = '__all__'
        read_only_fields = ['created_at', 'created_by']


class DataFactoryRecordSerializer(serializers.ModelSerializer):
    """数据记录序列化器"""

    class Meta:
        model = DataFactoryRecord
        fields = '__all__'


class DataFactoryTemplateSerializer(serializers.ModelSerializer):
    """模板序列化器"""
    owner_username = serializers.CharField(source='owner.username', read_only=True)

    class Meta:
        model = DataFactoryTemplate
        fields = '__all__'
        read_only_fields = ['usage_count', 'created_at', 'updated_at']


class DataFactoryUsageLogSerializer(serializers.ModelSerializer):
    """引用日志序列化器"""

    class Meta:
        model = DataFactoryUsageLog
        fields = '__all__'
        read_only_fields = ['referenced_at', 'referenced_by']
