from django.contrib import admin
from .models import TestSuite


@admin.register(TestSuite)
class TestSuiteAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_by', 'get_cases_count', 'created_at', 'updated_at']
    search_fields = ['name', 'description']
    list_filter = ['created_at']
    
    def get_cases_count(self, obj):
        return obj.get_cases_count()
    get_cases_count.short_description = '用例数量'
