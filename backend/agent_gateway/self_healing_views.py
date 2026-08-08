"""
自愈 API 端点

POST /api/agent/self-healing/analyze/  → 分析错误
POST /api/agent/self-healing/heal/     → 执行自愈
GET  /api/agent/self-healing/stats/    → 统计数据
GET  /api/agent/self-healing/history/  → 修复历史
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from core.agents.self_healing import (
    ErrorClassifier, SelfHealingEngine, create_self_healing_engine,
)

logger = logging.getLogger(__name__)

# 全局引擎实例 (在生产环境应考虑作用域)
_engine: SelfHealingEngine | None = None


def _get_engine() -> SelfHealingEngine:
    global _engine
    if _engine is None:
        _engine = create_self_healing_engine(max_attempts=3, use_ai=True)
    return _engine


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_error(request):
    """
    分析错误 — 分类 + 根因 + 修复建议

    POST /api/agent/self-healing/analyze/
    {
        "error": "ConnectionError: 无法连接 API 服务器",
        "context": {"step_name": "testcase_generation", "agent": "generator"}
    }
    """
    error_msg = request.data.get("error", "")
    context = request.data.get("context", {})

    if not error_msg:
        return Response({"error": "error 字段不能为空"}, status=status.HTTP_400_BAD_REQUEST)

    analysis = ErrorClassifier.classify(error_msg, context)

    return Response({
        "analysis": analysis.to_dict(),
        "raw_error": error_msg,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def heal_step(request):
    """
    对单步执行进行自愈

    POST /api/agent/self-healing/heal/
    {
        "step_name": "testcase_generation",
        "execution_id": 123,          // 可选
        "error": "AssertionError: ..." // 可选, 如果提供则直接分析
    }
    """
    step_name = request.data.get("step_name", "")
    execution_id = request.data.get("execution_id")
    error_msg = request.data.get("error", "")

    if not step_name:
        return Response({"error": "step_name 不能为空"}, status=status.HTTP_400_BAD_REQUEST)

    engine = _get_engine()

    # 如果提供了错误信息，进行分类分析
    if error_msg:
        analysis = ErrorClassifier.classify(error_msg, {"step_name": step_name})
        return Response({
            "status": "analyzed",
            "step_name": step_name,
            "analysis": analysis.to_dict(),
            "can_heal": analysis.fixable,
            "suggested_strategies": analysis.suggested_strategies,
        })

    # 如果提供了 execution_id，从数据库获取执行信息
    if execution_id:
        try:
            from execution.models import Execution
            execution = Execution.objects.get(id=execution_id)
            if execution.error_log:
                analysis = ErrorClassifier.classify(execution.error_log, {
                    "step_name": step_name,
                    "execution_id": execution_id,
                })
                return Response({
                    "status": "analyzed",
                    "step_name": step_name,
                    "execution_id": execution_id,
                    "analysis": analysis.to_dict(),
                    "can_heal": analysis.fixable,
                })
        except Exception as e:
            logger.warning(f"获取执行记录失败: {e}")

    return Response({
        "status": "ready",
        "step_name": step_name,
        "message": "步骤已准备好自愈，请提供更多信息或直接触发修复",
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def execute_healing(request):
    """
    执行自愈修复

    POST /api/agent/self-healing/execute/
    {
        "step_name": "testcase_generation",
        "error": "AssertionError: ...",
        "step_params": {"prompt": "...", "context": {}},
        "max_attempts": 3
    }
    """
    step_name = request.data.get("step_name", "")
    error_msg = request.data.get("error", "")
    step_params = request.data.get("step_params", {})
    max_attempts = int(request.data.get("max_attempts", 3))

    if not step_name:
        return Response({"error": "step_name 不能为空"}, status=status.HTTP_400_BAD_REQUEST)

    engine = _get_engine()
    engine.max_attempts = max_attempts

    # 用模拟步骤函数执行（实际使用需要前端传递具体调用）
    def step_func(**kwargs):
        # 这里需要实际执行步骤，但由于 API 限制，返回传入的错误
        return {"status": "error", "error": error_msg}

    result = engine.heal(
        step_func=step_func,
        step_params={"step_name": step_name, **step_params},
        step_name=step_name,
        context={"source": "api"},
    )

    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def healing_stats(request):
    """
    查看自愈统计

    GET /api/agent/self-healing/stats/
    """
    engine = _get_engine()
    return Response({
        "stats": engine.get_stats(),
        "total_history": len(engine.get_history()),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def healing_history(request):
    """
    查看修复历史

    GET /api/agent/self-healing/history/?limit=20
    """
    limit = int(request.query_params.get("limit", 20))
    engine = _get_engine()
    history = engine.get_history(limit=limit)

    return Response({
        "count": len(history),
        "history": history,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def classify_batch(request):
    """
    批量错误分类

    POST /api/agent/self-healing/classify-batch/
    {
        "errors": [
            {"error": "ConnectionError: ...", "context": {"step": "gen"}},
            {"error": "AssertionError: ...", "context": {"step": "eval"}}
        ]
    }
    """
    errors = request.data.get("errors", [])
    if not errors:
        return Response({"error": "errors 列表不能为空"}, status=status.HTTP_400_BAD_REQUEST)

    results = []
    for item in errors:
        error_msg = item.get("error", "")
        context = item.get("context", {})
        analysis = ErrorClassifier.classify(error_msg, context)
        results.append({
            "error": error_msg[:200],
            "analysis": analysis.to_dict(),
        })

    return Response({
        "count": len(results),
        "results": results,
        "summary": {
            "fixable": sum(1 for r in results if r["analysis"]["fixable"]),
            "unfixable": sum(1 for r in results if not r["analysis"]["fixable"]),
            "categories": list(set(r["analysis"]["category"] for r in results)),
        },
    })
