"""
租户限流（Phase 2.2 真正生效）

之前 tenants 表有 qps / daily_cap 字段与 CRUD，但执行时 team_id 写死 "default"，
没有任何限流逻辑真正生效。本模块提供进程内配额检查：
  - QPS：滑动窗口（最近 1 秒内的请求数不超过 qps）
  - 日调用上限：按自然日累计，超过 daily_cap 拒绝

额度优先取 tenants 表中 team==team_id 的记录，找不到则用全局默认。
注意：进程内计数，重启清零；多副本部署需换成 Redis，此处先打通单实例能力。
"""

import threading
import time
from datetime import datetime, timezone
from typing import Tuple

from app.core.task_store import get_task_store

_DEFAULT_QPS = 50
_DEFAULT_DAILY_CAP = 5000

_lock = threading.Lock()
# team_id -> {"second": [timestamps], "day": count, "day_key": "YYYY-MM-DD"}
_usage: dict[str, dict] = {}


def _get_team_quota(team_id: str) -> Tuple[int, int]:
    try:
        store = get_task_store()
        tenant = store.get_tenant_by_team(team_id)
        if tenant:
            return tenant.qps, tenant.daily_cap
    except Exception:
        pass
    return _DEFAULT_QPS, _DEFAULT_DAILY_CAP


def check_quota(team_id: str) -> Tuple[bool, str]:
    """
    检查 team_id 是否还有配额。返回 (allowed, reason)。
    """
    qps, daily_cap = _get_team_quota(team_id)
    now = time.time()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with _lock:
        rec = _usage.setdefault(team_id, {"second": [], "day": 0, "day_key": today})
        # 跨天重置日计数
        if rec["day_key"] != today:
            rec["day"] = 0
            rec["day_key"] = today
        # 清理 1 秒外的请求时间戳
        rec["second"] = [t for t in rec["second"] if now - t < 1.0]

        # QPS 检查
        if len(rec["second"]) >= qps:
            return False, f"QPS 超限（{qps}/s）"
        # 日调用上限检查
        if daily_cap and rec["day"] >= daily_cap:
            return False, f"今日调用已达上限（{daily_cap}）"

        # 放行并记账
        rec["second"].append(now)
        rec["day"] += 1
        return True, ""
