"""
RBAC 权限存储 — 用户/角色/权限持久化

设计：与 task_store.py 同模式，使用 SQLite 原生操作。
- users 表：系统用户（密码 bcrypt 哈希）
- roles 表：角色定义
- permissions 表：权限定义（resource.action）
- user_roles 表：用户-角色关联
- role_permissions 表：角色-权限关联

种子数据：admin/tester/viewer 三种角色 + 默认权限 + 3个默认用户
"""

import hashlib
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

DB_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
)
DB_PATH = os.path.join(DB_DIR, "harness.db")


# ============================================================
# 数据类
# ============================================================

@dataclass
class UserRecord:
    id: Optional[int] = None
    username: str = ""
    password_hash: str = ""
    email: str = ""
    is_active: bool = True
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "created_at": self.created_at,
        }

    def to_admin_dict(self, roles: list[str] = None) -> dict:
        return {
            **self.to_dict(),
            "roles": roles or [],
        }


@dataclass
class RoleRecord:
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    created_at: str = ""

    def to_dict(self, permissions: list[str] = None) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "permissions": permissions or [],
            "created_at": self.created_at,
        }


@dataclass
class PermissionRecord:
    id: Optional[int] = None
    code: str = ""        # e.g. "user.manage"
    name: str = ""        # e.g. "用户管理"
    description: str = ""
    resource: str = ""    # e.g. "user"
    action: str = ""      # e.g. "manage"


# ============================================================
# 密码工具（不含 bcrypt 依赖，用 SHA256 + salt）
# ============================================================

SALT = "agent-harness-rbac-2026"


def hash_password(password: str) -> str:
    """简单密码哈希（生产环境应替换为 bcrypt）"""
    return hashlib.sha256(f"{SALT}:{password}".encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


# ============================================================
# RBAC 默认数据
# ============================================================

DEFAULT_PERMISSIONS = [
    # 管理类
    ("user.manage", "用户管理", "创建/编辑/删除用户，分配角色", "user", "manage"),
    ("role.manage", "角色管理", "创建/编辑/删除角色，分配权限", "role", "manage"),
    ("tenant.manage", "租户管理", "管理业务接入方、API Key、限流策略", "tenant", "manage"),
    ("sandbox.manage", "沙箱管理", "创建/销毁沙箱，资源监控", "sandbox", "manage"),
    ("mcp.manage", "MCP工具管理", "注册/启停 MCP 工具", "mcp", "manage"),
    ("prompt.manage", "Prompt管理", "编辑 Prompt 模板、版本管理", "prompt", "manage"),
    ("model.manage", "模型管理", "模型配置、启停、路由策略", "model", "manage"),
    ("audit.view", "审计查看", "查看审计日志、操作记录", "audit", "view"),
    ("audit.export", "审计导出", "导出审计日志", "audit", "export"),
    # 执行类
    ("task.execute", "任务执行", "创建和执行 AI 任务", "task", "execute"),
    ("task.view", "任务查看", "查看任务列表、链路日志", "task", "view"),
    ("workflow.run", "工作流执行", "触发和执行工作流", "workflow", "run"),
    ("tool.use", "工具使用", "调用已注册的 MCP 工具", "tool", "use"),
]

DEFAULT_ROLES = [
    ("admin", "系统管理员", "拥有所有权限，可以管理用户、角色、租户和系统配置"),
    ("tester", "测试工程师", "可以使用 AI 测试功能，执行任务，查看报告"),
    ("viewer", "访客", "只能查看系统状态和数据，不能执行任何写操作"),
]

# 角色 → 权限分配
ROLE_PERMISSION_MAP = {
    "admin": [
        "user.manage", "role.manage", "tenant.manage", "sandbox.manage",
        "mcp.manage", "prompt.manage", "model.manage",
        "audit.view", "audit.export",
        "task.execute", "task.view", "workflow.run", "tool.use",
    ],
    "tester": [
        "task.execute", "task.view", "workflow.run", "tool.use",
        "audit.view",
    ],
    "viewer": [
        "task.view", "task.execute", "workflow.run", "tool.use",
        "audit.view",
    ],
}

DEFAULT_USERS = [
    ("admin", "admin123456", "admin@agent-harness.local", ["admin"]),
    ("debug_user", "admin123456", "tester@agent-harness.local", ["tester"]),
    ("demo", "demo123456", "demo@agent-harness.local", ["viewer"]),
]


# ============================================================
# AuthStore 实现
# ============================================================

class AuthStore:
    """RBAC 权限持久化存储（SQLite）"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
        self._seed_defaults()

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    resource TEXT NOT NULL DEFAULT '',
                    action TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS user_roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    UNIQUE(user_id, role_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS role_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role_id INTEGER NOT NULL,
                    permission_id INTEGER NOT NULL,
                    UNIQUE(role_id, permission_id),
                    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
                    FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
                CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);
                CREATE INDEX IF NOT EXISTS idx_role_perms_role ON role_permissions(role_id);
            """)
            conn.commit()

    def _seed_defaults(self):
        """首次运行时写入默认角色、权限、用户"""
        now = datetime.now(timezone.utc).isoformat()

        with self._get_conn() as conn:
            # 种子权限
            perm_count = conn.execute("SELECT COUNT(*) FROM permissions").fetchone()[0]
            if perm_count == 0:
                conn.executemany(
                    """INSERT INTO permissions (code, name, description, resource, action)
                    VALUES (?,?,?,?,?)""",
                    DEFAULT_PERMISSIONS,
                )
                conn.commit()
                logger.info(f"[AuthStore] 已写入 {len(DEFAULT_PERMISSIONS)} 条权限")

            # 种子角色
            role_count = conn.execute("SELECT COUNT(*) FROM roles").fetchone()[0]
            if role_count == 0:
                for name, desc, _full_desc in DEFAULT_ROLES:
                    conn.execute(
                        "INSERT INTO roles (name, description, created_at) VALUES (?,?,?)",
                        (name, desc, now),
                    )
                conn.commit()
                logger.info(f"[AuthStore] 已写入 {len(DEFAULT_ROLES)} 个角色")

                # 角色-权限关联
                perm_map = {
                    row["code"]: row["id"]
                    for row in conn.execute("SELECT id, code FROM permissions").fetchall()
                }
                role_map = {
                    row["name"]: row["id"]
                    for row in conn.execute("SELECT id, name FROM roles").fetchall()
                }
                for role_name, perm_codes in ROLE_PERMISSION_MAP.items():
                    role_id = role_map.get(role_name)
                    for code in perm_codes:
                        perm_id = perm_map.get(code)
                        if role_id and perm_id:
                            conn.execute(
                                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?,?)",
                                (role_id, perm_id),
                            )
                conn.commit()

            # 种子用户
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            if user_count == 0:
                for username, password, email, role_names in DEFAULT_USERS:
                    conn.execute(
                        "INSERT INTO users (username, password_hash, email, is_active, created_at) VALUES (?,?,?,?,?)",
                        (username, hash_password(password), email, 1, now),
                    )
                conn.commit()

                # 用户-角色关联
                user_map = {
                    row["username"]: row["id"]
                    for row in conn.execute("SELECT id, username FROM users").fetchall()
                }
                role_map = {
                    row["name"]: row["id"]
                    for row in conn.execute("SELECT id, name FROM roles").fetchall()
                }
                for username, _, _, role_names in DEFAULT_USERS:
                    user_id = user_map.get(username)
                    for rn in role_names:
                        role_id = role_map.get(rn)
                        if user_id and role_id:
                            conn.execute(
                                "INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?,?)",
                                (user_id, role_id),
                            )
                conn.commit()
                logger.info(f"[AuthStore] 已写入 {len(DEFAULT_USERS)} 个默认用户")

    # ── 认证方法 ──

    def authenticate(self, username: str, password: str) -> Optional[dict]:
        """验证用户，返回用户信息字典（含角色列表）"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? AND is_active = 1",
                (username,),
            ).fetchone()
            if row is None:
                return None
            user = UserRecord(**dict(row))
            if not verify_password(password, user.password_hash):
                return None
            roles = self._get_user_roles(conn, user.id)
            return {
                "user_id": user.id,
                "username": user.username,
                "role": roles[0] if roles else "viewer",
                "email": user.email,
                "roles": roles,
            }

    def _get_user_roles(self, conn, user_id: int) -> list[str]:
        rows = conn.execute(
            """SELECT r.name FROM roles r
            INNER JOIN user_roles ur ON r.id = ur.role_id
            WHERE ur.user_id = ?""",
            (user_id,),
        ).fetchall()
        return [r["name"] for r in rows]

    def get_user_roles(self, user_id: int) -> list[str]:
        with self._get_conn() as conn:
            return self._get_user_roles(conn, user_id)

    def get_user_permissions(self, user_id: int) -> list[str]:
        """获取用户所有权限 code 列表"""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT DISTINCT p.code FROM permissions p
                INNER JOIN role_permissions rp ON p.id = rp.permission_id
                INNER JOIN user_roles ur ON rp.role_id = ur.role_id
                WHERE ur.user_id = ?""",
                (user_id,),
            ).fetchall()
            return [r["code"] for r in rows]

    # ── 用户 CRUD ──

    def list_users(self) -> list[dict]:
        with self._get_conn() as conn:
            user_rows = conn.execute(
                "SELECT * FROM users ORDER BY id"
            ).fetchall()
            result = []
            for row in user_rows:
                user = UserRecord(**dict(row))
                roles = self._get_user_roles(conn, user.id)
                result.append(user.to_admin_dict(roles))
            return result

    def get_user(self, user_id: int) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if row is None:
                return None
            user = UserRecord(**dict(row))
            roles = self._get_user_roles(conn, user.id)
            return user.to_admin_dict(roles)

    def create_user(self, username: str, password: str,
                    email: str = "", role_names: list[str] = None) -> Optional[dict]:
        """创建用户，返回完整信息"""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._get_conn() as conn:
                # 检查用户名唯一
                existing = conn.execute(
                    "SELECT id FROM users WHERE username = ?", (username,)
                ).fetchone()
                if existing:
                    return None

                cursor = conn.execute(
                    """INSERT INTO users (username, password_hash, email, is_active, created_at)
                    VALUES (?,?,?,?,?)""",
                    (username, hash_password(password), email, 1, now),
                )
                conn.commit()
                user_id = cursor.lastrowid

                # 分配角色
                if role_names:
                    role_map = {
                        row["name"]: row["id"]
                        for row in conn.execute("SELECT id, name FROM roles").fetchall()
                    }
                    for rn in role_names:
                        rid = role_map.get(rn)
                        if rid:
                            conn.execute(
                                "INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?,?)",
                                (user_id, rid),
                            )
                    conn.commit()

        return self.get_user(user_id)

    def update_user(self, user_id: int, **kwargs) -> Optional[dict]:
        """更新用户字段（username/email/is_active/password/roles）"""
        with self._lock:
            with self._get_conn() as conn:
                # 基础字段
                basic_updates = {}
                if "username" in kwargs and kwargs["username"]:
                    basic_updates["username"] = kwargs["username"]
                if "email" in kwargs:
                    basic_updates["email"] = kwargs["email"]
                if "is_active" in kwargs and kwargs["is_active"] is not None:
                    basic_updates["is_active"] = 1 if kwargs["is_active"] else 0
                if "password" in kwargs and kwargs["password"]:
                    basic_updates["password_hash"] = hash_password(kwargs["password"])

                if basic_updates:
                    set_clause = ", ".join(f"{k} = ?" for k in basic_updates)
                    values = list(basic_updates.values()) + [user_id]
                    conn.execute(
                        f"UPDATE users SET {set_clause} WHERE id = ?", values
                    )

                # 角色更新
                if "roles" in kwargs and kwargs["roles"] is not None:
                    conn.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
                    role_map = {
                        row["name"]: row["id"]
                        for row in conn.execute("SELECT id, name FROM roles").fetchall()
                    }
                    for rn in kwargs["roles"]:
                        rid = role_map.get(rn)
                        if rid:
                            conn.execute(
                                "INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?,?)",
                                (user_id, rid),
                            )

                conn.commit()
        return self.get_user(user_id)

    def delete_user(self, user_id: int) -> bool:
        with self._lock:
            with self._get_conn() as conn:
                # 禁止删除最后一个 admin
                admin_count = conn.execute(
                    """SELECT COUNT(*) FROM user_roles ur
                    INNER JOIN roles r ON ur.role_id = r.id
                    WHERE r.name = 'admin'"""
                ).fetchone()[0]
                is_admin = conn.execute(
                    """SELECT 1 FROM user_roles ur
                    INNER JOIN roles r ON ur.role_id = r.id
                    WHERE ur.user_id = ? AND r.name = 'admin'""",
                    (user_id,),
                ).fetchone()
                if is_admin and admin_count <= 1:
                    return False  # 拒绝删除唯一管理员

                conn.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
                cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                return cursor.rowcount > 0

    # ── 角色 CRUD ──

    def list_roles(self) -> list[dict]:
        with self._get_conn() as conn:
            role_rows = conn.execute("SELECT * FROM roles ORDER BY id").fetchall()
            result = []
            for row in role_rows:
                role = RoleRecord(**dict(row))
                # 查询关联权限
                perm_rows = conn.execute(
                    """SELECT p.code FROM permissions p
                    INNER JOIN role_permissions rp ON p.id = rp.permission_id
                    WHERE rp.role_id = ?""",
                    (role.id,),
                ).fetchall()
                perms = [p["code"] for p in perm_rows]
                # 查询关联用户数
                user_count = conn.execute(
                    "SELECT COUNT(*) FROM user_roles WHERE role_id = ?", (role.id,)
                ).fetchone()[0]
                result.append({**role.to_dict(perms), "user_count": user_count})
            return result

    def create_role(self, name: str, description: str = "",
                    permission_codes: list[str] = None) -> Optional[dict]:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._get_conn() as conn:
                existing = conn.execute(
                    "SELECT id FROM roles WHERE name = ?", (name,)
                ).fetchone()
                if existing:
                    return None

                cursor = conn.execute(
                    "INSERT INTO roles (name, description, created_at) VALUES (?,?,?)",
                    (name, description, now),
                )
                conn.commit()
                role_id = cursor.lastrowid

                if permission_codes:
                    perm_map = {
                        row["code"]: row["id"]
                        for row in conn.execute("SELECT id, code FROM permissions").fetchall()
                    }
                    for code in permission_codes:
                        pid = perm_map.get(code)
                        if pid:
                            conn.execute(
                                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?,?)",
                                (role_id, pid),
                            )
                    conn.commit()

        return self.get_role(role_id)

    def get_role(self, role_id: int) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM roles WHERE id = ?", (role_id,)).fetchone()
            if row is None:
                return None
            role = RoleRecord(**dict(row))
            perm_rows = conn.execute(
                """SELECT p.code FROM permissions p
                INNER JOIN role_permissions rp ON p.id = rp.permission_id
                WHERE rp.role_id = ?""",
                (role_id,),
            ).fetchall()
            perms = [p["code"] for p in perm_rows]
            user_count = conn.execute(
                "SELECT COUNT(*) FROM user_roles WHERE role_id = ?", (role_id,)
            ).fetchone()[0]
            return {**role.to_dict(perms), "user_count": user_count}

    def update_role(self, role_id: int, name: str = None,
                    description: str = None, permission_codes: list[str] = None) -> Optional[dict]:
        with self._lock:
            with self._get_conn() as conn:
                if name or description is not None:
                    updates = {}
                    if name:
                        updates["name"] = name
                    if description is not None:
                        updates["description"] = description
                    set_clause = ", ".join(f"{k} = ?" for k in updates)
                    values = list(updates.values()) + [role_id]
                    conn.execute(f"UPDATE roles SET {set_clause} WHERE id = ?", values)

                if permission_codes is not None:
                    conn.execute("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
                    perm_map = {
                        row["code"]: row["id"]
                        for row in conn.execute("SELECT id, code FROM permissions").fetchall()
                    }
                    for code in permission_codes:
                        pid = perm_map.get(code)
                        if pid:
                            conn.execute(
                                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?,?)",
                                (role_id, pid),
                            )
                conn.commit()
        return self.get_role(role_id)

    def delete_role(self, role_id: int) -> bool:
        with self._lock:
            with self._get_conn() as conn:
                # 禁止删除 admin/tester/viewer 内置角色
                role_name = conn.execute(
                    "SELECT name FROM roles WHERE id = ?", (role_id,)
                ).fetchone()
                if role_name and role_name["name"] in ("admin", "tester", "viewer"):
                    return False

                conn.execute("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
                conn.execute("DELETE FROM user_roles WHERE role_id = ?", (role_id,))
                cursor = conn.execute("DELETE FROM roles WHERE id = ?", (role_id,))
                conn.commit()
                return cursor.rowcount > 0

    # ── 权限查询 ──

    def list_permissions(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM permissions ORDER BY resource, action"
            ).fetchall()
            return [{
                "id": r["id"],
                "code": r["code"],
                "name": r["name"],
                "description": r["description"],
                "resource": r["resource"],
                "action": r["action"],
            } for r in rows]


# ============================================================
# 全局单例
# ============================================================

_auth_store: Optional[AuthStore] = None


def get_auth_store() -> AuthStore:
    global _auth_store
    if _auth_store is None:
        _auth_store = AuthStore()
        logger.info(f"[AuthStore] 初始化完成 db={_auth_store.db_path}")
    return _auth_store
