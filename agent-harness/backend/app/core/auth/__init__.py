"""
Agent Harness 认证模块

提供：
- JWTValidator: HS256 JWT 验证（与 Django SIMPLE_JWT 互通）
- AuthMiddleware: 请求级鉴权中间件（Bearer JWT + X-Service-Token 双通道）
- get_current_user: FastAPI Depends 依赖项，供端点内联使用
"""

from app.core.auth.jwt_handler import (
    JWTValidator,
    JWTUser,
    AuthMiddleware,
    get_current_user,
    SERVICE_AUTH_PREFIX,
)

__all__ = [
    "JWTValidator",
    "JWTUser",
    "AuthMiddleware",
    "get_current_user",
    "SERVICE_AUTH_PREFIX",
]
