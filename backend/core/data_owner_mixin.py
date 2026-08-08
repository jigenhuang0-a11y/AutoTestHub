"""
数据隔离 Mixin
统一处理 ViewSet 中的用户数据隔离逻辑
用法: class MyViewSet(DataOwnerMixin, viewsets.ModelViewSet): ...
"""
from rest_framework import permissions


class DataOwnerMixin:
    """
    数据隔离 Mixin：
    - 管理员看全部
    - 其他用户只看自己创建的
    自动处理 get_queryset + perform_create
    """

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # 管理员看全部
        if user.is_admin:
            return qs
        # 其他用户只看自己创建的
        return qs.filter(created_by=user)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        # 部分 ViewSet 已在 perform_create 中设置 created_by，这里做兜底
        if 'created_by' in serializer.validated_data:
            return
        serializer.save(created_by=self.request.user)
