from django.contrib import admin
from .models import PerfTestCase, PerfExecution


@admin.register(PerfTestCase)
class PerfTestCaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'target_url', 'method', 'users', 'duration', 'status', 'created_at')
    list_filter = ('status', 'method')
    search_fields = ('name', 'target_url')


@admin.register(PerfExecution)
class PerfExecutionAdmin(admin.ModelAdmin):
    list_display = ('id', 'test_case', 'status', 'requests_per_second', 'avg_response_time', 'p95_response_time', 'thresholds_passed', 'started_at')
    list_filter = ('status', 'thresholds_passed')
    search_fields = ('test_case__name',)
