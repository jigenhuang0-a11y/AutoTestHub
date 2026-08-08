from django.contrib import admin
from .models import AgentTask, AgentPromptConfig


@admin.register(AgentTask)
class AgentTaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'task_type', 'user_request_preview', 'status', 'user', 'created_at']
    list_filter = ['status', 'task_type', 'created_at']
    search_fields = ['user_request']
    readonly_fields = ['created_at', 'updated_at']

    def user_request_preview(self, obj):
        return obj.user_request[:60] + ('...' if len(obj.user_request) > 60 else '')
    user_request_preview.short_description = '请求预览'


@admin.register(AgentPromptConfig)
class AgentPromptConfigAdmin(admin.ModelAdmin):
    list_display = ['agent_name', 'prompt_subtype', 'prompt_type', 'description', 'version', 'is_active', 'updated_at']
    list_filter = ['agent_name', 'prompt_type', 'is_active']
    search_fields = ['agent_name', 'description', 'system_prompt']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['is_active']
    
    fieldsets = [
        ('基本信息', {'fields': ['agent_name', 'prompt_subtype', 'prompt_type', 'description', 'is_active', 'version']}),
        ('Prompt 内容', {'fields': ['system_prompt', 'user_prompt_template'], 'classes': ['wide']}),
        ('时间戳', {'fields': ['created_at', 'updated_at']}),
    ]
