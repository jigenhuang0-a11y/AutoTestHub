from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    自定义用户模型
    角色体系：admin(管理员) / tester(测试工程师) / viewer(只读查看者)
    """
    class Role(models.TextChoices):
        ADMIN = 'admin', '管理员'
        TESTER = 'tester', '测试工程师'
        VIEWER = 'viewer', '查看者'

    email = models.EmailField('邮箱', unique=True, blank=True, null=True)
    phone = models.CharField('手机号', max_length=20, blank=True, null=True)
    role = models.CharField(
        '角色', max_length=20, choices=Role.choices, default=Role.TESTER,
        help_text='用户角色：管理员拥有全部权限，测试工程师可操作自己的数据，查看者只读'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'users'
        verbose_name = '用户'
        verbose_name_plural = '用户'

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_tester(self):
        return self.role == self.Role.TESTER

    @property
    def is_viewer(self):
        return self.role == self.Role.VIEWER

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
