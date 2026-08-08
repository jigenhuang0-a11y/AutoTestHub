from django.contrib import admin
from .models import WebTestCase


@admin.register(WebTestCase)
class WebTestCaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'engine', 'target_url', 'browser_type', 'priority', 'status', 'created_by', 'created_at')
    list_filter = ('engine', 'browser_type', 'priority', 'status')
    search_fields = ('title', 'description', 'target_url', 'ai_prompt')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('基本信息', {
            'fields': ('title', 'description', 'engine', 'priority', 'status', 'tags')
        }),
        ('目标配置', {
            'fields': ('target_url', 'browser_type', 'headless', 'viewport')
        }),
        ('Playwright 步骤模式', {
            'fields': ('steps',)
        }),
        ('AI 模式', {
            'fields': ('ai_prompt',)
        }),
        ('断言规则', {
            'fields': ('assertions',)
        }),
        ('执行选项', {
            'fields': ('screenshot_enabled', 'full_page_screenshot', 'record_video')
        }),
        ('元数据', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
