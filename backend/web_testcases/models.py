from django.db import models
from django.conf import settings


class WebTestCase(models.Model):
    """Web 自动化测试用例模型（双引擎支持）"""

    ENGINE_CHOICES = [
        ('playwright', 'Playwright 精确模式'),
        ('ai', 'AI 模式 (midscene)'),
    ]

    PRIORITY_CHOICES = [
        ('P0', 'P0 - 最高'),
        ('P1', 'P1 - 高'),
        ('P2', 'P2 - 中'),
        ('P3', 'P3 - 低'),
    ]

    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('active', '激活'),
        ('inactive', '停用'),
    ]

    BROWSER_CHOICES = [
        ('chromium', 'Chromium'),
        ('firefox', 'Firefox'),
        ('webkit', 'WebKit (Safari)'),
    ]

    title = models.CharField('标题', max_length=200)
    description = models.TextField('描述', blank=True, default='')

    # === 引擎选择 ===
    engine = models.CharField(
        '引擎',
        max_length=12,
        choices=ENGINE_CHOICES,
        default='playwright',
        help_text='Playwright精确控制 或 AI自然语言驱动'
    )

    # === 通用字段 ===
    target_url = models.CharField('目标URL', max_length=500)
    browser_type = models.CharField('浏览器类型', max_length=10, choices=BROWSER_CHOICES, default='chromium')
    headless = models.BooleanField('无头模式', default=True)
    viewport = models.JSONField('视口尺寸', default=dict, blank=True, help_text='如 {"width": 1280, "height": 720}')

    # === Playwright 步骤模式字段 ===
    steps = models.JSONField('操作步骤', default=list, blank=True, help_text='[{"action": "navigate", "params": {"url": "..."}}, ...]')
    """
    支持的 action 类型：
    - navigate: 导航到 URL
    - click: 点击元素
    - fill: 填充输入框
    - select: 下拉选择
    - hover: 悬停
    - wait_for: 等待（时间/元素/网络空闲）
    - screenshot: 截图
    - assert_text: 断言文本存在
    - assert_visible: 断言元素可见
    - assert_url: 断言 URL 包含/匹配
    """

    # === AI 模式字段 ===
    ai_prompt = models.TextField('AI 测试描述', blank=True, default='', help_text='用自然语言描述测试步骤')

    # === 断言规则（通用）===
    assertions = models.JSONField('断言规则', default=list, blank=True)
    """
    [{"type": "url_contains", "value": "/home"},
     {"type": "text_exists", "selector/value": "...", "expected": "..."},
     {"type": "screenshot_compare", "baseline_path": "..."}]
    """

    # === 登录态 / Cookie ===
    cookies = models.JSONField('Cookie 注入', default=list, blank=True,
        help_text='从浏览器复制的 cookie 数组，执行前自动注入。格式：[{"name":"sid","value":"xxx","domain":".doubao.com"}]')
    """
    支持两种格式：
    1. JSON 数组: [{"name":"sessionId","value":"abc123","domain":".example.com","path":"/"}]
    2. 字符串: "name1=value1; name2=value2" （自动解析）
    """

    # === 执行选项 ===
    screenshot_enabled = models.BooleanField('启用截图', default=True)
    full_page_screenshot = models.BooleanField('全屏截图', default=False)
    record_video = models.BooleanField('录屏', default=False)

    # === 元数据 ===
    priority = models.CharField('优先级', max_length=2, choices=PRIORITY_CHOICES, default='P2')
    status = models.CharField('状态', max_length=10, choices=STATUS_CHOICES, default='draft')
    tags = models.JSONField('标签', default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='web_test_cases',
        verbose_name='创建人'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'web_test_cases'
        verbose_name = 'Web 测试用例'
        verbose_name_plural = 'Web 测试用例'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_engine_display()}] {self.title}"


class WebTestExecution(models.Model):
    """Web 测试用例执行历史记录"""
    STATUS_CHOICES = [
        ('running', '执行中'),
        ('passed', '通过'),
        ('failed', '失败'),
        ('error', '异常'),
    ]

    test_case = models.ForeignKey(
        WebTestCase,
        on_delete=models.CASCADE,
        related_name='executions',
        verbose_name='测试用例'
    )
    status = models.CharField('执行状态', max_length=10, choices=STATUS_CHOICES)
    duration = models.FloatField('执行耗时(秒)', default=0)

    # 执行结果详情（步骤结果、断言等）
    result_data = models.JSONField('结果详情', default=dict, blank=True)

    # 截图存储路径（相对于 MEDIA_ROOT）
    screenshot = models.CharField('截图路径', max_length=500, blank=True, default='')

    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='web_test_executions',
        verbose_name='执行人'
    )
    executed_at = models.DateTimeField('执行时间', auto_now_add=True)

    class Meta:
        db_table = 'web_test_executions'
        verbose_name = 'Web 测试执行记录'
        verbose_name_plural = 'Web 测试执行记录'
        ordering = ['-executed_at']

    def __str__(self):
        return f"[{self.get_status_display()}] {self.test_case.title} @ {self.executed_at.strftime('%m-%d %H:%M')}"
