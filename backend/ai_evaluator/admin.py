from django.contrib import admin
from .models import AIModelConfig, EvalTask, EvalQuestion, EvalResult, EvalReport


@admin.register(AIModelConfig)
class AIModelConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider', 'model_id', 'is_active', 'created_at']
    list_filter = ['provider', 'is_active']
    search_fields = ['name', 'model_id']
    fields = ['name', 'provider', 'model_id', 'api_url', 'api_key',
              'timeout', 'max_tokens', 'temperature', 'is_active', 'description']


@admin.register(EvalTask)
class EvalTaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'status', 'accuracy', 'overall_score', 'created_by', 'created_at']
    list_filter = ['status', 'target_type']
    search_fields = ['name']


@admin.register(EvalQuestion)
class EvalQuestionAdmin(admin.ModelAdmin):
    list_display = ['task', 'index', 'question', 'category']
    list_filter = ['category']


@admin.register(EvalResult)
class EvalResultAdmin(admin.ModelAdmin):
    list_display = ['task', 'question_text', 'level', 'score', 'response_time', 'created_at']
    list_filter = ['level', 'has_security_risk']


@admin.register(EvalReport)
class EvalReportAdmin(admin.ModelAdmin):
    list_display = ['task', 'accuracy_score', 'safety_score', 'quality_score', 'created_at']
