from rest_framework import serializers
from .models import EvalTask, EvalQuestion, EvalResult, EvalReport, AIModelConfig


class AIModelConfigSerializer(serializers.ModelSerializer):
    """AI模型配置序列化器 - 列表/选择用（隐藏敏感信息）"""
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)

    class Meta:
        model = AIModelConfig
        fields = ['id', 'name', 'provider', 'provider_display', 'model_id',
                  'description', 'timeout', 'max_tokens', 'temperature', 'is_active']


class AIModelConfigDetailSerializer(serializers.ModelSerializer):
    """AI模型配置完整序列化器 - 管理员编辑用（含API Key）"""
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    api_key_masked = serializers.SerializerMethodField()

    class Meta:
        model = AIModelConfig
        fields = '__all__'

    def get_api_key_masked(self, obj):
        if obj.api_key:
            return obj.api_key[:8] + '...' + obj.api_key[-4:] if len(obj.api_key) > 12 else '****'
        return ''


class EvalQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvalQuestion
        fields = '__all__'
        read_only_fields = ['task']


class EvalResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvalResult
        fields = '__all__'
        read_only_fields = ['task', 'question', 'created_at']


class EvalReportSerializer(serializers.ModelSerializer):
    overall_score = serializers.SerializerMethodField()

    class Meta:
        model = EvalReport
        fields = '__all__'
        read_only_fields = ['task', 'created_at']

    def get_overall_score(self, obj):
        """从关联任务获取综合评分"""
        return obj.task.overall_score if obj.task else 0


class EvalTaskSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    results_count = serializers.SerializerMethodField()
    questions = EvalQuestionSerializer(many=True, read_only=True, source='questions.all')

    class Meta:
        model = EvalTask
        fields = '__all__'
        read_only_fields = ['created_by', 'status', 'total_questions',
                            'correct_count', 'incorrect_count', 'partial_count',
                            'error_count', 'accuracy', 'avg_response_time',
                            'overall_score', 'security_issues_found',
                            'created_at', 'updated_at']

    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else ''

    def get_results_count(self, obj):
        return obj.results.count()


class EvalTaskCreateSerializer(serializers.Serializer):
    """创建测评任务请求"""
    task_name = serializers.CharField(max_length=255, required=True)
    task_description = serializers.CharField(required=False, default='', allow_blank=True)
    target_type = serializers.ChoiceField(
        choices=[('knowledge_bot', '知识库问答机器人'), ('custom_api', '自定义API')],
        default='knowledge_bot'
    )
    target_config = serializers.DictField(default=dict)
    questions = serializers.ListField(
        child=serializers.DictField(),
        required=True,
        help_text='问题列表，每项含: question(必填), expected_answer(选填), category(选填)'
    )


class EvalTaskRunSerializer(serializers.Serializer):
    """执行测评请求"""
    task_id = serializers.IntegerField(required=True)


class EvalQuestionGenerateSerializer(serializers.Serializer):
    """AI生成测评问题请求"""
    topic = serializers.CharField(max_length=500, required=True, help_text='测评主题')
    count = serializers.IntegerField(default=10, min_value=1, max_value=50, help_text='生成数量')
    categories = serializers.ListField(
        child=serializers.ChoiceField(
            choices=['general', 'knowledge', 'procedure', 'safety', 'boundary']
        ),
        required=False,
        default=list,
        help_text='问题分类过滤'
    )
