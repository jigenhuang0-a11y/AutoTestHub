"""
PlanAgent — 智能需求分析与规划 Agent

功能：
- 分析用户自然语言需求，自动拆解为多步骤执行计划
- 智能识别所需的 Agent 类型（generator/data_factory/execution/evaluator/knowledge）
- 返回符合 LangGraph Harness 格式的结构化计划
"""
import json
import logging
from typing import Optional

from core.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class PlanAgent(BaseAgent):
    """
    智能规划 Agent — 将用户需求拆解为可执行的多步计划
    
    输入: 自然语言需求描述
    输出: 结构化执行计划 { plan: [...], dependencies: {...}, reasoning: "..." }
    
    支持的 Agent 类型:
        knowledge    — 知识库检索
        generator    — 测试用例生成
        data_factory — 测试数据生成
        execution    — 测试执行
        evaluator    — AI 评估
    """

    name = "PlanAgent"
    description = "智能需求分析与多步执行规划 Agent"
    task_type = "planning"

    system_prompt = """你是一个专业的测试计划规划师。你的任务是把用户的测试需求拆解成可执行的步骤。

## 可用的 Agent 类型（只能从以下选择）：
- **knowledge**     : 知识库检索 — 当需要参考历史文档、接口规范、测试经验时使用
- **generator**     : 测试用例生成 — 需要生成新的测试用例时使用
- **data_factory**  : 测试数据生成 — 需要构造测试输入数据时使用  
- **execution**     : 测试执行 — 需要运行测试并收集结果时使用
- **evaluator**     : AI 评估 — 需要评估测试质量或分析结果时使用

## 规划规则：
1. 第一步通常是 knowledge（检索相关文档和规范）
2. 如果有"生成用例"、"创建测试"等需求 → 用 generator
3. 如果有"造数据"、"构造数据"等需求 → 用 data_factory
4. 如果有"执行"、"运行测试"等需求 → 用 execution
5. 如果有"评估"、"分析结果"等需求 → 用 evaluator
6. 每个步骤必须有清晰的 prompt（用中文描述该步要做什么）
7. 步骤数量：1-5 步

## 输出格式（严格 JSON）：
```json
{
    "plan": [
        {
            "step": 1,
            "agent": "knowledge",
            "prompt": "检索与「用户登录」相关的测试文档和接口规范",
            "description": "知识库检索"
        },
        {
            "step": 2,
            "agent": "generator",
            "prompt": "为登录接口生成测试用例，覆盖正常登录、异常登录、边界值",
            "description": "生成测试用例"
        }
    ],
    "dependencies": {
        "generator": ["knowledge"]
    },
    "reasoning": "先检索登录接口文档，再基于文档生成全面测试用例"
}
```

请严格输出 JSON，不要包含 markdown 代码块标记。"""

    def run(self, prompt: str, context: Optional[dict] = None) -> dict:
        """
        分析需求，生成执行计划
        
        Args:
            prompt: 用户需求
            context: 额外上下文
        
        Returns:
            {"status": "success", "data": {"plan": [...], "reasoning": "..."}}
        """
        logger.info(f"[PlanAgent] 分析需求: {prompt[:100]}...")

        try:
            # 构建带上下文的提示
            enhanced_prompt = prompt
            if context:
                context_items = []
                if context.get("api_spec"):
                    context_items.append(f"接口规范: {context['api_spec']}")
                if context.get("existing_cases"):
                    context_items.append(f"已有用例: {context['existing_cases']}")
                if context.get("constraints"):
                    context_items.append(f"约束条件: {context['constraints']}")
                if context_items:
                    enhanced_prompt = "已知信息:\n" + "\n".join(context_items) + "\n\n需求:\n" + prompt

            # 调用 LLM 生成计划
            raw = self.ask_llm(enhanced_prompt)

            # 解析 JSON
            plan_data = self._parse_plan(raw)

            # 校验计划
            plan_data = self._validate_and_fix(plan_data, prompt)

            return self._success(
                data={
                    "plan": plan_data.get("plan", []),
                    "dependencies": plan_data.get("dependencies", {}),
                    "reasoning": plan_data.get("reasoning", ""),
                }
            )

        except Exception as e:
            logger.exception(f"[PlanAgent] 规划失败: {e}")
            # 回退：返回默认单步计划
            fallback_plan = self._fallback_plan(prompt)
            return self._success(
                data={
                    "plan": fallback_plan,
                    "dependencies": {},
                    "reasoning": f"自动回退计划（原因: {str(e)}）",
                },
                fallback=True,
            )

    # ================================================================
    # 内部方法
    # ================================================================

    def _parse_plan(self, raw: str) -> dict:
        """从 LLM 原始输出中解析 JSON 计划"""
        raw = raw.strip()

        # 尝试直接解析
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 去除 markdown 代码块
        if raw.startswith("```"):
            lines = raw.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            raw = "\n".join(lines).strip()

        # 提取 JSON 块
        import re
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        raise ValueError(f"无法解析计划 JSON: {raw[:200]}")

    def _validate_and_fix(self, plan_data: dict, original_prompt: str) -> dict:
        """验证并修复计划"""
        valid_agents = {"knowledge", "generator", "data_factory", "execution", "evaluator"}

        if "plan" not in plan_data or not plan_data["plan"]:
            return {"plan": self._fallback_plan(original_prompt), "reasoning": "默认计划"}

        fixed_plan = []
        for i, step in enumerate(plan_data["plan"]):
            agent = step.get("agent", "").lower().strip()
            # 修正无效的 agent
            if agent not in valid_agents:
                logger.warning(f"[PlanAgent] 修正无效 Agent: '{agent}' → 'generator'")
                agent = "generator"

            fixed_plan.append({
                "step": i + 1,
                "agent": agent,
                "prompt": step.get("prompt", original_prompt),
                "description": step.get("description", f"步骤 {i+1}"),
            })

        return {
            "plan": fixed_plan,
            "dependencies": plan_data.get("dependencies", {}),
            "reasoning": plan_data.get("reasoning", "智能规划"),
        }

    def _fallback_plan(self, prompt: str) -> list:
        """当 LLM 解析失败时的回退计划"""
        # 关键词匹配简单路由
        prompt_lower = prompt.lower()

        plan = [
            {"step": 1, "agent": "knowledge", "prompt": prompt, "description": "知识库检索"},
        ]

        if any(kw in prompt_lower for kw in ["生成", "用例", "测试用例", "testcase"]):
            plan.append({"step": len(plan)+1, "agent": "generator", "prompt": prompt, "description": "生成测试用例"})

        if any(kw in prompt_lower for kw in ["数据", "造数", "data"]):
            plan.append({"step": len(plan)+1, "agent": "data_factory", "prompt": prompt, "description": "生成测试数据"})

        if any(kw in prompt_lower for kw in ["执行", "运行", "run", "execute"]):
            plan.append({"step": len(plan)+1, "agent": "execution", "prompt": prompt, "description": "执行测试"})

        if any(kw in prompt_lower for kw in ["评估", "打分", "评价", "evaluate"]):
            plan.append({"step": len(plan)+1, "agent": "evaluator", "prompt": prompt, "description": "评估结果"})

        return plan


def create_planner() -> PlanAgent:
    """工厂函数：创建规划 Agent"""
    return PlanAgent()
