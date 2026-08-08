from django.db import models


class AgentTask(models.Model):
    """
    Agent 任务记录
    
    追踪每次 Agent 调用的生命周期：创建 → 处理中 → 完成/失败
    """
    STATUS_CHOICES = [
        ('pending', '等待中'),
        ('running', '执行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
        ('cancelled', '已取消'),
    ]

    task_type = models.CharField('任务类型', max_length=50, db_index=True)
    user_request = models.TextField('用户请求')
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    result = models.JSONField('执行结果', null=True, blank=True)
    error_message = models.TextField('错误信息', blank=True)
    
    # 执行统计
    steps_count = models.PositiveIntegerField('执行步骤数', default=0)
    duration_ms = models.PositiveIntegerField('耗时(毫秒)', default=0)
    
    # 归属
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, verbose_name='创建者')
    
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'agent_tasks'
        verbose_name = 'Agent 任务'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.task_type}] {self.user_request[:50]}..."


class AgentPromptConfig(models.Model):
    """
    Agent Prompt 配置 — 数据库驱动的 System Prompt 管理
    
    设计目的：
    - 本地/阿里云共享同一份 prompt 配置（通过数据库同步）
    - 修改 prompt 无需重新部署代码
    - 支持版本管理和启用/禁用
    
    使用方式：
    1. 每个 Agent 子类在 __init__ 时调用 _load_prompt_from_db()
    2. 如果数据库中有记录，覆盖硬编码的 system_prompt
    3. 如果数据库中没有，使用代码中的默认值（fallback）
    """
    PROMPT_TYPE_CHOICES = [
        ('system', 'System Prompt'),
        ('user', 'User Prompt 模板'),
    ]

    agent_name = models.CharField('Agent 名称', max_length=100, db_index=True,
        help_text='对应 Agent 类的 name 属性，如 "test_case_generator"')
    prompt_subtype = models.CharField('Prompt 子类型', max_length=50, default='default',
        help_text='同一 Agent 不同策略的 prompt，如 standard/smart/boundary')
    prompt_type = models.CharField('Prompt 类型', max_length=20,
        choices=PROMPT_TYPE_CHOICES, default='system')
    system_prompt = models.TextField('System Prompt', blank=True,
        help_text='核心提示词内容')
    user_prompt_template = models.TextField('User Prompt 模板', blank=True,
        help_text='用户消息模板（支持 {变量} 占位）')
    description = models.CharField('描述', max_length=200, blank=True,
        help_text='此 Prompt 的用途说明')
    is_active = models.BooleanField('启用', default=True, db_index=True)
    version = models.PositiveIntegerField('版本号', default=1)
    
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'agent_prompt_configs'
        verbose_name = 'Agent Prompt 配置'
        verbose_name_plural = verbose_name
        ordering = ['agent_name', 'prompt_subtype']
        unique_together = [['agent_name', 'prompt_subtype']]

    def __str__(self):
        return f"[{self.agent_name}/{self.prompt_subtype}] v{self.version} - {self.description}"

    @classmethod
    def load_prompt(cls, agent_name: str, prompt_subtype: str = 'default',
                    fallback: str = '') -> str:
        """从数据库加载 prompt，找不到时返回 fallback"""
        try:
            config = cls.objects.filter(
                agent_name=agent_name,
                prompt_subtype=prompt_subtype,
                is_active=True,
            ).first()
            if config and config.system_prompt:
                return config.system_prompt
        except Exception:
            pass  # 数据库不可用时静默 fallback
        return fallback
