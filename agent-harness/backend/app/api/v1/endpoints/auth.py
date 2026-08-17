"""
Agent Harness 认证接口 + RBAC 用户/角色权限管理

- 登录：从 SQLite 用户表验证（AuthStore）
- Profile/Logout：标准 JWT 流程
- 用户 CRUD（admin only）：增删改查用户、分配角色
- 角色 CRUD（admin only）：增删改查角色、分配权限
- 权限列表（readonly）：查看所有可用权限
"""

import logging
import os
import time
import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.auth_store import get_auth_store

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer(auto_error=False)

TOKEN_STORE: dict[str, dict] = {}


# ============================================================
# Schema
# ============================================================

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access: str
    user: dict


class CreateUserRequest(BaseModel):
    username: str
    password: str
    email: str = ""
    roles: list[str] = []


class UpdateUserRequest(BaseModel):
    username: str = None
    password: str = None
    email: str = None
    is_active: bool = None
    roles: list[str] = None


class CreateRoleRequest(BaseModel):
    name: str
    description: str = ""
    permissions: list[str] = []


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str = ""


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class RefreshResponse(BaseModel):
    access: str
    user: dict


class UpdateRoleRequest(BaseModel):
    name: str = None
    description: str = None
    permissions: list[str] = None


# ============================================================
# 工具函数
# ============================================================

# Token 有效期：7 天（秒）。避免操作中频繁跳登录。
JWT_EXPIRE_SECONDS = int(os.getenv("JWT_EXPIRE_SECONDS", "604800"))


def _issue_token(username: str, user_id: int, role: str) -> str:
    signing_key = os.getenv("JWT_SIGNING_KEY", "harness-dev-fallback-key")
    now = int(time.time())
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "token_type": "access",
        "exp": now + JWT_EXPIRE_SECONDS,
        "iat": now,
        "jti": uuid.uuid4().hex[:12],
    }
    return jwt.encode(payload, signing_key, algorithm="HS256")


# ============================================================
# 认证端点
# ============================================================

@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """用户登录，返回 JWT access token"""
    store = get_auth_store()
    user_info = store.authenticate(req.username, req.password)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    # 测试工程师账号暂时关闭
    if user_info.get("role") == "tester":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="测试工程师账号暂时关闭，请使用管理员或访客账号登录",
        )

    token = _issue_token(
        user_info["username"],
        user_info["user_id"],
        user_info["role"],
    )

    user_payload = {
        "user_id": user_info["user_id"],
        "username": user_info["username"],
        "role": user_info["role"],
        "email": user_info["email"],
        "roles": user_info.get("roles", []),
    }
    TOKEN_STORE[token] = user_payload
    return {"access": token, "user": user_payload}


@router.get("/profile")
async def profile(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """返回当前用户信息"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证信息",
        )
    token = credentials.credentials
    if token not in TOKEN_STORE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已过期或 token 无效",
        )
    return {"user": TOKEN_STORE[token]}


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """退出登录，作废 token"""
    if credentials and credentials.credentials in TOKEN_STORE:
        TOKEN_STORE.pop(credentials.credentials)
    return {"detail": "已登出"}


@router.post("/register")
async def register(req: RegisterRequest):
    """公开注册：创建普通用户（默认 viewer 角色）"""
    if len(req.username) < 3:
        raise HTTPException(status_code=422, detail="用户名长度不能少于3位")
    if len(req.password) < 6:
        raise HTTPException(status_code=422, detail="密码长度不能少于6位")

    store = get_auth_store()
    result = store.create_user(
        username=req.username,
        password=req.password,
        email=req.email,
        role_names=["viewer"],
    )
    if result is None:
        raise HTTPException(status_code=409, detail=f"用户名 '{req.username}' 已存在")

    # 注册后直接签发 token，便于前端自动登录
    user_id = result.get("id")
    token = _issue_token(req.username, user_id, "viewer")
    user_payload = {
        "user_id": user_id,
        "username": req.username,
        "role": "viewer",
        "email": req.email,
        "roles": ["viewer"],
    }
    TOKEN_STORE[token] = user_payload
    logger.info(f"[Auth] 新用户注册：{req.username}")
    return {"access": token, "user": user_payload}


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """刷新 token：使用现有有效 token 换发新的 access token"""
    if not credentials:
        raise HTTPException(status_code=401, detail="未提供认证信息")
    old_token = credentials.credentials
    if old_token not in TOKEN_STORE:
        raise HTTPException(status_code=401, detail="登录已过期或 token 无效")
    user_payload = TOKEN_STORE[old_token]
    # 作废旧 token，签发新 token
    new_token = _issue_token(
        user_payload["username"],
        user_payload["user_id"],
        user_payload["role"],
    )
    TOKEN_STORE.pop(old_token, None)
    TOKEN_STORE[new_token] = user_payload
    return {"access": new_token, "user": user_payload}


# ============================================================
# 依赖项（给其他模块用）
# ============================================================

def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """返回当前认证用户"""
    # 中间件注入的用户
    if request is not None and hasattr(request.state, "user") and request.state.user is not None:
        from app.core.auth.jwt_handler import JWTUser
        user: JWTUser = request.state.user
        if user.is_authenticated or user.auth_method == "service_token":
            return {
                "username": user.username,
                "role": user.role,
                "user_id": user.user_id,
            }

    if not credentials:
        raise HTTPException(status_code=401, detail="未提供认证信息")
    token = credentials.credentials
    if token not in TOKEN_STORE:
        raise HTTPException(status_code=401, detail="登录已过期或 token 无效")
    return TOKEN_STORE[token]


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """依赖项：仅管理员可调用"""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="仅管理员可执行此操作",
        )
    return user


def require_non_viewer(user: dict = Depends(get_current_user)) -> dict:
    """依赖项：访客（viewer）不可调用。仅 admin 和 tester 可新增/修改/删除"""
    if user.get("role") == "viewer":
        raise HTTPException(
            status_code=403,
            detail="访客模式不支持此操作。如需完整功能，请联系管理员升级为测试工程师。",
        )
    return user


@router.put("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    user: dict = Depends(get_current_user),
):
    """已登录用户修改自己的密码"""
    if len(req.new_password) < 6:
        raise HTTPException(status_code=422, detail="新密码长度不能少于6位")

    store = get_auth_store()
    # 验证旧密码并拿到 user_id
    info = store.authenticate(user["username"], req.old_password)
    if info is None:
        raise HTTPException(status_code=400, detail="原密码错误")
    store.update_user(info["user_id"], password=req.new_password)

    # 改密后作废该用户所有 token（安全起见）
    for t, p in list(TOKEN_STORE.items()):
        if p.get("username") == user["username"]:
            TOKEN_STORE.pop(t, None)
    logger.info(f"[Auth] 用户 {user['username']} 修改了密码")
    return {"detail": "密码修改成功，请重新登录"}


# ============================================================
# 用户管理 API（admin only）
# ============================================================

@router.get("/users")
async def list_users(user: dict = Depends(require_admin)):
    """获取所有用户列表"""
    store = get_auth_store()
    return {"users": store.list_users()}


@router.get("/users/{user_id}")
async def get_user(user_id: int, user: dict = Depends(require_admin)):
    """获取单个用户详情"""
    store = get_auth_store()
    result = store.get_user(user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"user": result}


@router.post("/users", status_code=201)
async def create_user(req: CreateUserRequest, user: dict = Depends(require_admin)):
    """创建新用户"""
    store = get_auth_store()
    if len(req.password) < 6:
        raise HTTPException(status_code=422, detail="密码长度不能少于6位")

    result = store.create_user(
        username=req.username,
        password=req.password,
        email=req.email,
        role_names=req.roles,
    )
    if result is None:
        raise HTTPException(status_code=409, detail=f"用户名 '{req.username}' 已存在")
    logger.info(f"[Auth] 管理员 {user['username']} 创建了用户 {req.username}")
    return {"user": result, "detail": "用户创建成功"}


@router.put("/users/{user_id}")
async def update_user(user_id: int, req: UpdateUserRequest,
                      user: dict = Depends(require_admin)):
    """更新用户信息（部分更新）"""
    store = get_auth_store()
    kwargs = {}
    if req.username is not None:
        kwargs["username"] = req.username
    if req.password is not None and req.password:
        if len(req.password) < 6:
            raise HTTPException(status_code=422, detail="密码长度不能少于6位")
        kwargs["password"] = req.password
    if req.email is not None:
        kwargs["email"] = req.email
    if req.is_active is not None:
        kwargs["is_active"] = req.is_active
    if req.roles is not None:
        kwargs["roles"] = req.roles

    result = store.update_user(user_id, **kwargs)
    if result is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    logger.info(f"[Auth] 管理员 {user['username']} 更新了用户 ID={user_id}")
    return {"user": result, "detail": "用户已更新"}


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, user: dict = Depends(require_admin)):
    """删除用户"""
    store = get_auth_store()
    success = store.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=400, detail="删除失败（用户不存在或为唯一管理员）")
    logger.info(f"[Auth] 管理员 {user['username']} 删除了用户 ID={user_id}")
    return {"detail": "用户已删除"}


# ============================================================
# 角色管理 API（admin only）
# ============================================================

@router.get("/roles")
async def list_roles(user: dict = Depends(require_admin)):
    """获取所有角色"""
    store = get_auth_store()
    return {"roles": store.list_roles()}


@router.post("/roles", status_code=201)
async def create_role(req: CreateRoleRequest, user: dict = Depends(require_admin)):
    """创建新角色"""
    store = get_auth_store()
    result = store.create_role(
        name=req.name,
        description=req.description,
        permission_codes=req.permissions,
    )
    if result is None:
        raise HTTPException(status_code=409, detail=f"角色 '{req.name}' 已存在")
    logger.info(f"[Auth] 管理员 {user['username']} 创建了角色 {req.name}")
    return {"role": result, "detail": "角色创建成功"}


@router.put("/roles/{role_id}")
async def update_role(role_id: int, req: UpdateRoleRequest,
                      user: dict = Depends(require_admin)):
    """更新角色"""
    store = get_auth_store()
    result = store.update_role(
        role_id=role_id,
        name=req.name,
        description=req.description,
        permission_codes=req.permissions,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    logger.info(f"[Auth] 管理员 {user['username']} 更新了角色 ID={role_id}")
    return {"role": result, "detail": "角色已更新"}


@router.delete("/roles/{role_id}")
async def delete_role(role_id: int, user: dict = Depends(require_admin)):
    """删除角色"""
    store = get_auth_store()
    success = store.delete_role(role_id)
    if not success:
        raise HTTPException(status_code=400, detail="删除失败（角色不存在或为内置角色）")
    logger.info(f"[Auth] 管理员 {user['username']} 删除了角色 ID={role_id}")
    return {"detail": "角色已删除"}


# ============================================================
# 权限列表（只读）
# ============================================================

@router.get("/permissions")
async def list_permissions(user: dict = Depends(require_admin)):
    """获取所有可用权限"""
    store = get_auth_store()
    return {"permissions": store.list_permissions()}
