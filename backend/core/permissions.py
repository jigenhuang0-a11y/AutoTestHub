"""
RBAC 权限控制层
提供角色检查 + 数据隔离的 DRF 权限类
"""
from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """仅管理员可访问"""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_admin


class IsAdminOrTester(permissions.BasePermission):
    """管理员 + 测试工程师可访问（排除查看者）"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_viewer:
            return request.method in permissions.SAFE_METHODS
        return True


class CanManageOwnData(permissions.BasePermission):
    """
    数据级权限：
    - 管理员：可看/改所有数据
    - 测试工程师：可看/改自己创建的数据
    - 查看者：只能看自己相关的数据（只读）
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin:
            return True
        # 检查对象是否有 created_by 字段
        if hasattr(obj, 'created_by'):
            if request.user.is_viewer:
                return request.method in permissions.SAFE_METHODS and obj.created_by == request.user
            return obj.created_by == request.user
        # 没有 created_by 字段的数据，只允许管理员
        return request.user.is_admin


class IsOwnerOrReadOnly(permissions.BasePermission):
    """自己创建的数据可写，其他人只读"""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return hasattr(obj, 'created_by') and obj.created_by == request.user
