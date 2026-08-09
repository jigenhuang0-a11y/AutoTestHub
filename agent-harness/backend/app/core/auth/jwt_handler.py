"""
JWT 鉴权引擎

与 Django SIMPLE_JWT (HS256) 互通：
- Django 签发 JWT → agent_gateway 转发 → 底座验证 → 注入 request.state.user
- 同时支持 X-Service-Token（服务间通行令牌，供 MCP 工具回调等场景）

安全设计：
- JWT 验证失败 → 401 + 结构化错误响应
- 过期 Token → 401 + "token_expired"
- 签名不匹配 → 401 + "invalid_token"
- 服务间 Token 仅作 fallback，优先走用户 JWT
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import jwt
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# ============================================================
# 常量
# ============================================================

# 服务间认证 Token 前缀（用于 request.state.auth_method 标识）
SERVICE_AUTH_PREFIX = "service_token"

# 不需要鉴权的路径（健康检查、指标采集、登录页面）
# 注意：同时添加有/无尾斜杠版本，FastAPI 会自动重定向
PUBLIC_PATHS = {
    "/health",
    "/health/",
    "/api/v1/health",
    "/api/v1/health/",
    "/metrics",
    "/metrics/",
    "/api/v1/auth/login",
    "/api/v1/auth/login/",
}

# 路径前缀白名单（以这些前缀开头的路径可公开访问）
PUBLIC_PATH_PREFIXES = (
    "/health",
    "/metrics",
    "/api/v1/health",
    "/api/v1/auth/login",
)


# ============================================================
# 数据模型
# ============================================================

@dataclass
class JWTUser:
    """从 JWT 解析出的用户身份"""
    user_id: int
    username: str = ""
    role: str = "tester"
    auth_method: str = "jwt"          # jwt | service_token
    extra: dict = field(default_factory=dict)

    @property
    def is_authenticated(self) -> bool:
        return self.user_id > 0


# ============================================================
# JWT 验证器
# ============================================================

class JWTValidator:
    """
    HS256 JWT 验证器

    与 Django djangorestframework-simplejwt 兼容：
    - Algorithm: HS256
    - Signing Key: Django 的 SECRET_KEY（通过 JWT_SIGNING_KEY 环境变量传入）
    - Claims: token_type="access", user_id=<int>, exp, iat, jti
    """

    ALGORITHM = "HS256"
    # 时钟偏差容忍（秒），允许客户端时钟轻微不同步
    LEEWAY_SECONDS = 30

    def __init__(self, signing_key: Optional[str] = None):
        # 优先用显式传入的 key；否则读环境变量；环境未配置（含空串）时回退到开发默认 key，
        # 与 auth.py 的 _issue_token 保持一致，避免签发/验签 key 不匹配导致 500。
        self._signing_key = signing_key or os.getenv("JWT_SIGNING_KEY") or "harness-dev-fallback-key"

    @property
    def is_configured(self) -> bool:
        """JWT 签名密钥是否已配置"""
        return bool(self._signing_key)

    def decode(self, token: str) -> JWTUser:
        """
        验证并解码 JWT Token

        Args:
            token: 原始 JWT 字符串（不含 Bearer 前缀）

        Returns:
            JWTUser: 解析出的用户信息

        Raises:
            HTTPException(401): Token 无效或过期
        """
        if not self._signing_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "auth_not_configured", "reason": "JWT_SIGNING_KEY 未配置"},
            )

        try:
            payload = jwt.decode(
                token,
                self._signing_key,
                algorithms=[self.ALGORITHM],
                options={
                    "verify_exp": True,
                    "verify_iat": True,
                    "require": ["user_id", "exp"],
                },
                leeway=self.LEEWAY_SECONDS,
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "token_expired", "reason": "Token 已过期，请重新登录"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"[JWT] Token 验证失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "invalid_token", "reason": "Token 无效"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 可选：校验 token_type（Django SimpleJWT 的 access token 有此字段）
        token_type = payload.get("token_type")
        if token_type and token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "invalid_token_type", "reason": f"需要 access token，收到 {token_type}"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return JWTUser(
            user_id=payload["user_id"],
            username=payload.get("username", f"user_{payload['user_id']}"),
            role=payload.get("role", "tester"),
            auth_method="jwt",
            extra={k: v for k, v in payload.items()
                   if k not in ("user_id", "username", "role", "exp", "iat", "jti", "token_type")},
        )


# ============================================================
# 模块级单例
# ============================================================

_validator: Optional[JWTValidator] = None


def get_jwt_validator() -> JWTValidator:
    global _validator
    if _validator is None:
        _validator = JWTValidator()
    return _validator


# ============================================================
# 认证中间件
# ============================================================

class AuthMiddleware(BaseHTTPMiddleware):
    """
    请求级 JWT 鉴权中间件

    鉴权链路（按优先级）：
    1. Authorization: Bearer <jwt> → 验证 HS256 JWT → 注入 request.state.user
    2. X-Service-Token: <token>   → 比对 SERVICE_TOKEN → service_user
    3. 白名单路径 → 跳过鉴权（/health, /metrics）
    4. 无凭证 → 401 Unauthorized

    鉴权结果写入 request.state：
    - request.state.user: JWTUser 实例
    - request.state.auth_method: "jwt" | "service_token"
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # ====== 白名单：公开路径 ======
        if self._is_public_path(path):
            # 注入匿名用户（避免端点内 .user 访问报错）
            request.state.user = JWTUser(user_id=0, username="anonymous", auth_method="none")
            request.state.auth_method = "none"
            return await call_next(request)

        # ====== 通道1：Bearer JWT ======
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") and len(auth_header) > 7:
            token = auth_header[7:]
            try:
                user = get_jwt_validator().decode(token)
                request.state.user = user
                request.state.auth_method = "jwt"
                logger.debug(f"[Auth] JWT 验证通过 user_id={user.user_id} role={user.role} path={path}")
                return await call_next(request)
            except HTTPException as e:
                logger.warning(
                    f"[Auth] JWT 校验失败 path={path} status={e.status_code} "
                    f"detail={e.detail} client={request.client.host if request.client else 'unknown'}"
                )
                # JWT 校验失败直接返回，不 fallback 到 ServiceToken
                # （防止行为不一致：同一个 Authorization header 不能既是用户又是服务）
                from fastapi.responses import JSONResponse
                detail = e.detail
                headers = {"WWW-Authenticate": "Bearer"}
                if hasattr(e, 'headers') and e.headers:
                    headers.update(e.headers)
                return JSONResponse(status_code=e.status_code, content=detail, headers=headers)

        # ====== 通道2：X-Service-Token（服务间通行） ======
        service_token = request.headers.get("X-Service-Token", "").strip()
        if service_token:
            expected = os.getenv("SERVICE_TOKEN", "").strip()
            if expected and service_token == expected:
                request.state.user = JWTUser(
                    user_id=0,
                    username="orchestrator_service",
                    role="admin",
                    auth_method="service_token",
                )
                request.state.auth_method = "service_token"
                logger.debug(f"[Auth] ServiceToken 验证通过 path={path}")
                return await call_next(request)
            else:
                logger.warning(
                    f"[Auth] ServiceToken 不匹配 path={path} "
                    f"client={request.client.host if request.client else 'unknown'}"
                )
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"error": "invalid_service_token", "reason": "服务通行令牌无效"},
                )

        # ====== 无凭证 → 401 ======
        logger.warning(
            f"[Auth] 未提供凭证 path={path} "
            f"client={request.client.host if request.client else 'unknown'}"
        )
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "unauthorized", "reason": "请提供 Bearer Token 或 X-Service-Token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @staticmethod
    def _is_public_path(path: str) -> bool:
        """检查路径是否在公开白名单中"""
        if path in PUBLIC_PATHS:
            return True
        for prefix in PUBLIC_PATH_PREFIXES:
            if path.startswith(prefix):
                return True
        return False


# ============================================================
# FastAPI Depends：内联鉴权依赖
# ============================================================

# HTTPBearer 用于提取 Authorization header
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = None,
) -> JWTUser:
    """
    FastAPI Depends 鉴权依赖项

    用法：
        @router.post("/chat")
        async def llm_chat(request: LLMChatRequest, user: JWTUser = Depends(get_current_user)):
            ...

    优先级：
    1. 已由中间件注入的 request.state.user（避免重复验证）
    2. Authorization: Bearer <jwt> header

    Raises:
        HTTPException(401): 未通过鉴权
    """
    # 如果中间件已注入，直接返回（避免重复解码）
    if hasattr(request.state, "user") and request.state.user is not None:
        user: JWTUser = request.state.user
        if user.is_authenticated or user.auth_method == "service_token":
            return user
        # auth_method == "none" 说明是白名单路径，但端点显式声明了鉴权
        # → 按需走下面逻辑

    # Fallback：中间件未运行或白名单路径但端点要求鉴权时，手动验证
    if credentials is None:
        credentials = await _bearer_scheme(request)

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "reason": "请提供 Bearer Token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return get_jwt_validator().decode(credentials.credentials)
