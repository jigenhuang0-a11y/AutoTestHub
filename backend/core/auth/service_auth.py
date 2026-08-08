from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import authentication, exceptions


User = get_user_model()


class ServiceAccount:
    """服务间调用使用的虚拟用户对象（兼容旧代码引用）。

    当数据库中尚未创建真实用户时的降级兜底对象。
    拥有 is_authenticated=True，可通过 DRF IsAuthenticated 权限检查。
    """

    is_authenticated = True
    is_active = True
    is_staff = False
    is_superuser = False
    id = 0
    pk = 0
    username = "service"

    def __str__(self):
        return "service"


class ServiceTokenAuthentication(authentication.BaseAuthentication):
    """服务间通行令牌认证。

    兼容两种 Header：
      - Authorization: Bearer <service_token>
      - X-Service-Token: <service_token>

    当 token 与 settings.SERVICE_TOKEN 匹配时，解析请求头中的
    X-Service-User-Id（可选），返回对应的真实 User；若未指定或不存在，
    则回退到 admin / 第一个活跃用户，确保 DRF 权限与 ForeignKey 关联正常。
    """

    keyword = "Bearer"

    def authenticate(self, request):
        token = self._extract_token(request)
        if not token:
            return None

        expected = getattr(settings, "SERVICE_TOKEN", None)
        if not expected:
            return None

        if token != expected:
            raise exceptions.AuthenticationFailed("服务令牌无效。")

        # 优先使用调用方指定的用户 ID
        user_id_header = request.META.get("HTTP_X_SERVICE_USER_ID")
        user = None
        if user_id_header:
            try:
                user_id = int(user_id_header.strip())
                user = User.objects.filter(id=user_id, is_active=True).first()
            except (ValueError, TypeError):
                pass

        # 兜底：admin 系统用户
        if not user:
            user = User.objects.filter(username="admin", is_active=True).first()

        # 兜底：第一个活跃用户
        if not user:
            user = User.objects.filter(is_active=True).first()

        if not user:
            # 没有任何真实用户时，才返回虚拟对象，避免后续 ForeignKey 保存失败
            return (ServiceAccount(), None)

        return (user, None)

    def _extract_token(self, request):
        # 1. 优先读取 X-Service-Token
        header = request.META.get("HTTP_X_SERVICE_TOKEN")
        if header:
            return header.strip()

        # 2. 兼容 Authorization: Bearer <token>
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == self.keyword.lower():
            return parts[1]

        # 如果 Authorization 头不是 Bearer 格式，留给下一个认证类（JWT）处理
        return None
