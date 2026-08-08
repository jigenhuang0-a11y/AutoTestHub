from rest_framework import serializers
from .models import QualityCheckTask, QualityCheckResult, QualityStandard


class QualityCheckTaskSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    results_count = serializers.SerializerMethodField()

    class Meta:
        model = QualityCheckTask
        fields = '__all__'
        read_only_fields = ['created_by', 'status', 'total_cases',
                            'passed_cases', 'warning_cases', 'failed_cases',
                            'overall_score', 'pass_rate', 'scenario',
                            'created_at', 'updated_at']

    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else ''

    def get_results_count(self, obj):
        return obj.results.count()


class QualityCheckResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = QualityCheckResult
        fields = '__all__'
        read_only_fields = ['created_at']


class QualityStandardSerializer(serializers.ModelSerializer):
    rule_type_display = serializers.SerializerMethodField()

    class Meta:
        model = QualityStandard
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def get_rule_type_display(self, obj):
        type_map = {
            'completeness': '完整性检查',
            'format': '格式规范检查',
            'content': '内容质量检查',
            'duplicate': '重复内容检查',
        }
        return type_map.get(obj.rule_type, obj.rule_type)


class QualityCheckRequestSerializer(serializers.Serializer):
    """质检请求序列化器"""
    testcases = serializers.ListField(child=serializers.DictField(), required=True)
    scenario = serializers.ChoiceField(
        choices=[('general', '功能测试'), ('api', '接口测试')],
        default='general'
    )
    task_name = serializers.CharField(max_length=255, required=False, default='')
    task_description = serializers.CharField(required=False, default='', allow_blank=True)
    check_duplicates = serializers.BooleanField(default=True)
    check_completeness = serializers.BooleanField(default=True)
    check_format = serializers.BooleanField(default=True)
    check_content_quality = serializers.BooleanField(default=True)
    duplicate_threshold = serializers.FloatField(default=0.85, min_value=0.5, max_value=1.0)


class QualityTaskSummarySerializer(serializers.Serializer):
    """质检汇总序列化器"""
    total_tasks = serializers.IntegerField()
    total_cases_checked = serializers.IntegerField()
    average_score = serializers.FloatField()
    pass_rate = serializers.FloatField()
    recent_tasks = QualityCheckTaskSerializer(many=True)
    level_distribution = serializers.DictField()
    issue_type_distribution = serializers.DictField()
