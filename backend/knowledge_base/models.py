from django.db import models
from django.conf import settings


class KnowledgeBase(models.Model):
    """知识库模型"""
    name = models.CharField('名称', max_length=200)
    description = models.TextField('描述', blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='knowledge_bases',
        verbose_name='创建人'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'knowledge_bases'
        verbose_name = '知识库'
        verbose_name_plural = '知识库'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Document(models.Model):
    """文档模型"""
    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='所属知识库'
    )
    title = models.CharField('标题', max_length=500)
    file_path = models.CharField('文件路径', max_length=500)
    file_type = models.CharField('文件类型', max_length=20)  # pdf, docx, txt
    file_size = models.IntegerField('文件大小（字节）', default=0)
    chunk_count = models.IntegerField('分块数量', default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_documents',
        verbose_name='上传人'
    )
    uploaded_at = models.DateTimeField('上传时间', auto_now_add=True)

    class Meta:
        db_table = 'knowledge_documents'
        verbose_name = '文档'
        verbose_name_plural = '文档'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.title} ({self.knowledge_base.name})"


class ChatMessage(models.Model):
    """对话消息模型"""
    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='chat_messages',
        verbose_name='所属知识库'
    )
    session_id = models.CharField(
        '会话ID',
        max_length=50,
        blank=True,
        default='',
        db_index=True
    )
    mode = models.CharField(
        '问答模式',
        max_length=20,
        choices=[('chat', '日常对话'), ('knowledge', '知识库问答'), ('workflow', '多Agent工作流')],
        default='knowledge',
        db_index=True
    )
    question = models.TextField('问题')
    answer = models.TextField('回答', blank=True, default='')
    context_docs = models.JSONField('参考文档', default=list, blank=True)
    response_time = models.IntegerField('响应耗时(ms)', default=0, blank=True,
        help_text='从请求到完成的总耗时，单位毫秒')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='chat_messages',
        verbose_name='提问人'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'chat_messages'
        verbose_name = '对话消息'
        verbose_name_plural = '对话消息'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.question[:50]}..."
