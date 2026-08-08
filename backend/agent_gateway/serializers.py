from rest_framework import serializers
from .models import AgentTask, AgentPromptConfig


class AgentTaskSerializer(serializers.ModelSerializer):
    """Agent 任务序列化"""
    
    class Meta:
        model = AgentTask
        fields = [
            'id', 'task_type', 'user_request', 'status',
            'result', 'error_message', 'steps_count', 'duration_ms',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['status', 'result', 'error_message', 'steps_count', 'duration_ms']


class AgentPromptConfigSerializer(serializers.ModelSerializer):
    """Agent Prompt 配置序列化（支持 CRUD）"""
    
    preview = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = AgentPromptConfig
        fields = [
            'id', 'agent_name', 'prompt_subtype', 'prompt_type',
            'system_prompt', 'user_prompt_template', 'description',
            'is_active', 'version', 'preview', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_preview(self, obj):
        """返回 prompt 前 100 字符预览"""
        return obj.system_prompt[:100] + '...' if len(obj.system_prompt) > 100 else obj.system_prompt
