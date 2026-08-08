"""
Phase 1.2：模板存储层

提供模板 CRUD 的抽象接口和两种实现：
- MemoryTemplateStore：内存存储（回退方案），种子数据来自 DEFAULT_TEMPLATES
- RedisTemplateStore：Redis 存储（生产方案）
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

from app.core.template import (
    WorkflowTemplate, WorkflowStep, TemplateStatus,
    DEFAULT_TEMPLATES, dumps, loads,
)

logger = logging.getLogger(__name__)


# ============================================================
# 抽象接口
# ============================================================

class TemplateStore(ABC):
    """模板存储抽象——未来可无缝切换到 Postgres"""

    @abstractmethod
    async def get(self, team_id: str, template_id: str) -> Optional[WorkflowTemplate]:
        """获取单个模板"""
        ...

    @abstractmethod
    async def list(self, team_id: str) -> list[WorkflowTemplate]:
        """列出团队所有模板"""
        ...

    @abstractmethod
    async def save(self, template: WorkflowTemplate) -> bool:
        """保存/更新模板"""
        ...

    @abstractmethod
    async def delete(self, team_id: str, template_id: str) -> bool:
        """删除模板"""
        ...

    @abstractmethod
    async def get_default(self, team_id: str) -> Optional[WorkflowTemplate]:
        """获取团队的默认模板（第一个 published 模板）"""
        ...


# ============================================================
# 内存实现
# ============================================================

class MemoryTemplateStore(TemplateStore):
    """内存存储——Redis 不可用时的降级方案"""

    def __init__(self, seed_defaults: bool = True):
        self._store: dict[str, dict[str, WorkflowTemplate]] = {}  # team_id -> {template_id -> template}
        if seed_defaults:
            self._seed_defaults()

    def _seed_defaults(self):
        """将 DEFAULT_TEMPLATES 加载到内存"""
        for tmpl in DEFAULT_TEMPLATES.values():
            team = tmpl.team_id
            if team not in self._store:
                self._store[team] = {}
            self._store[team][tmpl.template_id] = tmpl
        logger.info(f"[TemplateStore.Memory] 加载 {len(DEFAULT_TEMPLATES)} 个预设模板")

    async def get(self, team_id: str, template_id: str) -> Optional[WorkflowTemplate]:
        return self._store.get(team_id, {}).get(template_id)

    async def list(self, team_id: str) -> list[WorkflowTemplate]:
        templates = list(self._store.get(team_id, {}).values())
        return sorted(templates, key=lambda t: t.created_at, reverse=True)

    async def save(self, template: WorkflowTemplate) -> bool:
        team = template.team_id
        if team not in self._store:
            self._store[team] = {}
        self._store[team][template.template_id] = template
        logger.info(f"[TemplateStore.Memory] 保存模板: {template.team_id}/{template.template_id} v{template.version}")
        return True

    async def delete(self, team_id: str, template_id: str) -> bool:
        team_dict = self._store.get(team_id, {})
        if template_id in team_dict:
            del team_dict[template_id]
            logger.info(f"[TemplateStore.Memory] 删除模板: {team_id}/{template_id}")
            return True
        return False

    async def get_default(self, team_id: str) -> Optional[WorkflowTemplate]:
        templates = await self.list(team_id)
        for t in templates:
            if t.status == TemplateStatus.PUBLISHED:
                return t
        return None


# ============================================================
# Redis 实现
# ============================================================

class RedisTemplateStore(TemplateStore):
    """Redis 存储"""

    KEY_PREFIX = "template"      # template:{team_id}:{template_id}
    INDEX_PREFIX = "template:index"  # template:index:{team_id}

    def __init__(self, redis_url: str, seed_defaults: bool = True):
        import redis
        self._redis = redis.from_url(redis_url)
        self._redis.ping()
        logger.info("[TemplateStore.Redis] Redis 连接成功")
        if seed_defaults:
            self._seed_defaults()

    def _template_key(self, team_id: str, template_id: str) -> str:
        return f"{self.KEY_PREFIX}:{team_id}:{template_id}"

    def _index_key(self, team_id: str) -> str:
        return f"{self.INDEX_PREFIX}:{team_id}"

    def _seed_defaults(self):
        """按需将预设模板写入 Redis（只在模板不存在时才写）"""
        import asyncio
        for tmpl in DEFAULT_TEMPLATES.values():
            key = self._template_key(tmpl.team_id, tmpl.template_id)
            if not self._redis.exists(key):
                self._redis.set(key, dumps(tmpl))
                self._redis.sadd(self._index_key(tmpl.team_id), tmpl.template_id)
        logger.info(f"[TemplateStore.Redis] 预设模板已就绪")

    async def get(self, team_id: str, template_id: str) -> Optional[WorkflowTemplate]:
        raw = self._redis.get(self._template_key(team_id, template_id))
        if not raw:
            return None
        try:
            return loads(raw)
        except Exception as e:
            logger.warning(f"[TemplateStore.Redis] 解析模板失败: {e}")
            return None

    async def list(self, team_id: str) -> list[WorkflowTemplate]:
        ids = self._redis.smembers(self._index_key(team_id))
        templates = []
        for tid in ids:
            tid_str = tid.decode() if isinstance(tid, bytes) else tid
            tmpl = await self.get(team_id, tid_str)
            if tmpl:
                templates.append(tmpl)
        return sorted(templates, key=lambda t: t.created_at, reverse=True)

    async def save(self, template: WorkflowTemplate) -> bool:
        key = self._template_key(template.team_id, template.template_id)
        self._redis.set(key, dumps(template))
        self._redis.sadd(self._index_key(template.team_id), template.template_id)
        logger.info(
            f"[TemplateStore.Redis] 保存模板: {template.team_id}/{template.template_id} v{template.version}"
        )
        return True

    async def delete(self, team_id: str, template_id: str) -> bool:
        tk = self._template_key(team_id, template_id)
        existed = self._redis.delete(tk) > 0
        self._redis.srem(self._index_key(team_id), template_id)
        if existed:
            logger.info(f"[TemplateStore.Redis] 删除模板: {team_id}/{template_id}")
        return existed

    async def get_default(self, team_id: str) -> Optional[WorkflowTemplate]:
        templates = await self.list(team_id)
        for t in templates:
            if t.status == TemplateStatus.PUBLISHED:
                return t
        return None


# ============================================================
# 单例工厂（优先 Redis，失败降级 Memory）
# ============================================================

_store_instance: Optional[TemplateStore] = None
_store_available: Optional[bool] = None


def _get_redis_url() -> str:
    from app.core.config import REDIS_URL
    return REDIS_URL


def get_template_store() -> TemplateStore:
    """获取全局 TemplateStore 单例"""
    global _store_instance, _store_available

    if _store_instance is not None:
        return _store_instance
    if _store_available is False:
        return MemoryTemplateStore(seed_defaults=True)

    try:
        _store_instance = RedisTemplateStore(_get_redis_url(), seed_defaults=True)
        _store_available = True
    except Exception as e:
        logger.warning(f"[TemplateStore] Redis 不可用 ({e})，回退内存存储")
        _store_available = False
        _store_instance = MemoryTemplateStore(seed_defaults=True)

    return _store_instance


# 便捷函数：同步获取模板（供 workflow plan_node 使用）
def get_template_sync(team_id: str, template_id: Optional[str] = None) -> Optional[WorkflowTemplate]:
    """同步获取模板——优先指定模板，否则取团队默认"""
    import asyncio
    import concurrent.futures

    store = get_template_store()

    # 内存存储直接查字典，不走异步
    if isinstance(store, MemoryTemplateStore):
        if template_id:
            return store._store.get(team_id, {}).get(template_id)
        templates = list(store._store.get(team_id, {}).values())
        for t in templates:
            if t.status == TemplateStatus.PUBLISHED:
                return t
        return None

    async def _get():
        if template_id:
            return await store.get(team_id, template_id)
        return await store.get_default(team_id)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 避免死锁：在新线程的独立事件循环中执行
            def _run():
                new_loop = asyncio.new_event_loop()
                try:
                    return new_loop.run_until_complete(_get())
                finally:
                    new_loop.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_run)
                return future.result(timeout=10)
        return loop.run_until_complete(_get())
    except RuntimeError:
        return asyncio.run(_get())
