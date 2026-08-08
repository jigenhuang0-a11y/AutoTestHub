from rest_framework import serializers
from .models import WebTestCase, WebTestExecution


class WebTestExecutionSerializer(serializers.ModelSerializer):
    """Web 测试执行历史记录序列化器"""
    executed_by_username = serializers.CharField(source='executed_by.username', read_only=True)
    screenshot_url = serializers.SerializerMethodField()
    test_case_title = serializers.CharField(source='test_case.title', read_only=True)
    test_case_steps = serializers.SerializerMethodField()

    class Meta:
        model = WebTestExecution
        fields = [
            'id', 'test_case', 'test_case_title', 'status', 'duration',
            'result_data', 'screenshot', 'screenshot_url',
            'executed_by', 'executed_by_username', 'executed_at',
            'test_case_steps',
        ]
        read_only_fields = fields

    def get_screenshot_url(self, obj):
        if obj.screenshot:
            return f"/media/{obj.screenshot}"
        return None

    def get_test_case_steps(self, obj):
        """返回关联用例的步骤定义，用于详情页展示"""
        if hasattr(obj, 'test_case') and obj.test_case:
            return obj.test_case.steps or []
        return []


class WebTestCaseSerializer(serializers.ModelSerializer):
    """Web 测试用例序列化器"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    engine_display = serializers.CharField(source='get_engine_display', read_only=True)
    last_execution_status = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = WebTestCase
        fields = [
            'id', 'title', 'description', 'engine', 'engine_display',
            'target_url', 'browser_type', 'headless', 'viewport',
            'steps', 'ai_prompt', 'assertions',
            'cookies',
            'screenshot_enabled', 'full_page_screenshot', 'record_video',
            'priority', 'status', 'tags',
            'created_by', 'created_by_username',
            'last_execution_status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_by_username']

    def get_last_execution_status(self, obj):
        latest = obj.executions.order_by('-executed_at').first()
        return latest.status if latest else None

    def validate_steps(self, value):
        """校验步骤格式"""
        if not isinstance(value, list):
            raise serializers.ValidationError('steps 必须是数组格式')

        valid_actions = {
            'navigate', 'click', 'fill', 'select', 'hover',
            'wait_for', 'screenshot', 'scroll',
            'assert_text', 'assert_visible', 'assert_url', 'assert_value',
            'press_key', 'upload_file', 'execute_js'
        }

        for idx, step in enumerate(value):
            if not isinstance(step, dict) or 'action' not in step:
                raise serializers.ValidationError(f"步骤 {idx + 1}: 缺少 action 字段")
            if step['action'] not in valid_actions:
                raise serializers.ValidationError(f"步骤 {idx + 1}: 不支持的 action '{step['action']}'")
            if 'params' not in step and step['action'] != 'screenshot':
                raise serializers.ValidationError(f"步骤 {idx + 1}: 缺少 params 字段")

        return value

    def validate_assertions(self, value):
        """校验断言格式"""
        if not isinstance(value, list):
            raise serializers.ValidationError('assertions 必须是数组格式')

        valid_types = {
            'url_contains', 'url_match', 'url_equals',
            'text_exists', 'text_not_exists',
            'element_visible', 'element_not_visible',
            'element_count', 'element_enabled',
            'screenshot_compare',
            'custom_script'
        }

        for idx, assertion in enumerate(value):
            if not isinstance(assertion, dict) or 'type' not in assertion:
                raise serializers.ValidationError(f"断言 {idx + 1}: 缺少 type 字段")
            if assertion['type'] not in valid_types:
                raise serializers.ValidationError(f"断言 {idx + 1}: 不支持的类型 '{assertion['type']}'")

        return value


class WebTestCaseDebugSerializer(serializers.Serializer):
    """Web 用例调试执行的输入参数（无需保存用例）"""
    engine = serializers.ChoiceField(choices=[('playwright', 'Playwright'), ('ai', 'AI')])
    target_url = serializers.URLField()
    browser_type = serializers.ChoiceField(choices=[('chromium', 'Chromium'), ('firefox', 'Firefox'), ('webkit', 'WebKit (Safari)')], default='chromium')
    headless = serializers.BooleanField(default=True)
    steps = serializers.ListField(required=False)
    ai_prompt = serializers.CharField(required=False, allow_blank=True)
    assertions = serializers.ListField(required=False)
    screenshot_enabled = serializers.BooleanField(default=True)
    full_page_screenshot = serializers.BooleanField(default=False)
    record_video = serializers.BooleanField(default=False)
    cookies = serializers.JSONField(required=False, default=list)
