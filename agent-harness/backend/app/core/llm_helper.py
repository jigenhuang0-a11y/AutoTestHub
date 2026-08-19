"""
统一的「AI 底座」调用助手。

测试平台各模块（用例生成 / 接口调试 / 数据工厂 LLM 造数 / 执行）需要真实 LLM 能力时，
统一从这里取 Provider，避免各自重复构造。

- 优先使用调用方传入的 model_id（来自前端选中的 AI 底座模型）
- 否则回退到 DB 中当前激活的模型
- 再不行回退到 provider_pool 的默认可用模型
- 全部不可用时抛出清晰异常，由调用方降级为 mock

追踪集成：
- 每次真实 LLM 调用都会向 EvalEventStore 写入事件，供 EvalCenter 事件驱动刷新。
"""
import logging
import time
import uuid
from typing import Optional

from app.core.task_store import get_task_store, ModelConfigRecord
from app.core.provider_pool import get_provider_pool
from app.core.eval_event_store import build_event, get_eval_event_store, TraceContext, estimate_cost

logger = logging.getLogger(__name__)


def _resolve_model_id(model_id: Optional[str]) -> Optional[str]:
    """把前端传来的 model_id 解析成真实的 provider 模型名。

    model_id 可能是：
      - 数字字符串（DB 的 model_configs.id）
      - 直接是模型名（如 deepseek-chat / qwen-plus）
      - 空（回退到激活模型）
    """
    if not model_id:
        return None
    # 已是模型名
    store = get_task_store()
    try:
        m = store.get_model_config_by_id(int(model_id))
        if m:
            return m.name
    except (ValueError, TypeError):
        # 不是数字，当作模型名
        return model_id
    return model_id


def get_llm_for_test(model_id: Optional[str] = None):
    """返回 (provider, model_name)。失败时抛 ValueError。"""
    pool = get_provider_pool()
    store = get_task_store()

    # 1. 调用方指定模型
    resolved = _resolve_model_id(model_id)
    if resolved:
        try:
            return pool.get_for_model(resolved), resolved
        except Exception as e:
            logger.warning(f"[llm_helper] 指定模型 {resolved} 不可用: {e}")

    # 2. DB 激活模型
    active: Optional[ModelConfigRecord] = store.get_active_model()
    if active:
        try:
            return pool.get_for_model(active.name), active.name
        except Exception as e:
            logger.warning(f"[llm_helper] 激活模型 {active.name} 不可用: {e}")

    # 3. provider_pool 默认可用
    provider = pool.get_default()
    return provider, provider.model


async def generate_text(
    prompt: str,
    model_id: Optional[str] = None,
    temperature: float = 0.7,
    task_type: str = "agent_loop",
    trace_id: Optional[str] = None,
) -> str:
    """调用真实 LLM 生成文本（同步 Provider 包成 async）。

    Args:
        task_type: 业务模块类型，用于 EvalCenter 按功能追踪。可选值参考 eval_event_store 的 TRACKED_FEATURES。
        trace_id: 父业务 trace_id。未传入时自动从 TraceContext 取，实现无侵入挂载。
    """
    # 显式传入优先；否则复用当前 TraceContext；都没有则新建一个本链路 trace_id
    effective_trace_id = trace_id or TraceContext.get() or str(uuid.uuid4())
    provider, model_name = get_llm_for_test(model_id)
    logger.info(f"[llm_helper] generate_text via {model_name} task_type={task_type}")

    async with TraceContext.async_bind(effective_trace_id):
        start = time.time()
        raw = provider.chat_raw([
            {"role": "system", "content": "你是资深测试开发工程师。"},
            {"role": "user", "content": prompt},
        ], temperature=temperature)
        latency_ms = int((time.time() - start) * 1000)
        content = (raw.get("content", "") if isinstance(raw, dict) else str(raw)).strip()

        # 真实 token/cost 指标
        usage = raw.get("usage") or {} if isinstance(raw, dict) else {}
        input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        output_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0
        total_tokens = usage.get("total_tokens") or (input_tokens + output_tokens) or max(1, len(content) // 4)
        cost_usd = estimate_cost(model_name, input_tokens, output_tokens)
        metrics = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
        }

        # 记录到 EvalEventStore，供 EvalCenter 事件驱动刷新
        try:
            trace_steps = [
                {
                    "type": "route",
                    "title": "LLM 路由",
                    "status": "completed",
                    "input": f"task_type={task_type}",
                    "output": f"llm_helper 直连 {model_name}",
                    "metadata": {
                        "task_type": task_type,
                        "model": model_name,
                        "provider": provider.__class__.__name__,
                        "source": "llm_helper",
                    },
                },
                {
                    "type": "llm",
                    "title": "LLM 生成",
                    "status": "completed",
                    "input": prompt[:500],
                    "output": content[:500] + ("..." if len(content) > 500 else ""),
                    "metadata": {
                        "model": model_name,
                        "provider": provider.__class__.__name__,
                        "latency_ms": latency_ms,
                        "token_usage": total_tokens,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cost_usd": cost_usd,
                    },
                },
            ]
            event = build_event(
                feature=task_type,
                task_type=task_type,
                model=model_name,
                provider=provider.__class__.__name__,
                input_text=prompt,
                output_text=content,
                latency_ms=latency_ms,
                token_usage=total_tokens,
                trace_id=effective_trace_id,
                trace_steps=trace_steps,
                metrics=metrics,
            )
            get_eval_event_store().add(event)
            # 把本 LLM 步骤追加到父 trace（若父事件已存在）
            try:
                get_eval_event_store().append_trace_steps(effective_trace_id, trace_steps)
            except Exception:
                pass
            # 兜底：把本次调用过程中已落库的底座子链路挂载到父 trace
            try:
                get_eval_event_store().flush_infra_steps(effective_trace_id)
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"[llm_helper] 记录 EvalEvent 失败: {e}")

    return content
