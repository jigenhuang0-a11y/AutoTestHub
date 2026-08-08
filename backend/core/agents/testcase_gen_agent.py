"""
用例生成 Agent — 根据需求自动生成测试用例

功能：
1. 接收需求描述 → 搜索知识库 → 生成用例 → 保存到数据库
2. 支持流式输出进度
3. 支持 4 种生成策略
"""
import json
import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncIterator

from .base_agent import BaseAgent
from core.tools.knowledge_search import get_knowledge_tool
from core.tools.testcase_storage import TestCaseStorageTool
from core.models.prompts.testcase_gen import TestCasePrompt

logger = logging.getLogger(__name__)


class TestCaseGeneratorAgent(BaseAgent):
    """
    用例生成 Agent

    工作流：
    1. 解析需求 → 搜索知识库获取上下文
    2. 构建 Prompt → 调用 LLM 生成用例
    3. 解析 JSON → 校验用例结构
    4. 保存到数据库 → 返回结果

    用法:
        agent = TestCaseGeneratorAgent()
        async for event in agent.generate(
            requirement="用户登录功能",
            strategy="standard",
            case_count=10,
        ):
            print(event)
    """

    name = "test_case_generator"
    description = "根据需求描述自动生成结构化测试用例"
    task_type = "generation"
    system_prompt = TestCasePrompt.SYSTEM_PROMPTS["standard"]

    def __init__(self, user_id: int = None, router=None):
        super().__init__(router=router)
        self.user_id = user_id
        self._knowledge_tool = get_knowledge_tool()
        self._storage_tool = TestCaseStorageTool(user_id=user_id)

    def run(self, prompt: str, context: dict = None) -> dict:
        """
        同步执行（兼容 BaseAgent 接口）
        简单场景下直接生成并返回

        Args:
            prompt: 需求描述
            context: {"strategy": str, "case_count": int, "knowledge_context": str}

        Returns:
            {"status": "success|error", "data": [...], "stats": {...}}
        """
        ctx = context or {}
        strategy = ctx.get("strategy", "standard")
        case_count = ctx.get("case_count", 10)
        knowledge_context = ctx.get("knowledge_context", "")
        extra_context = ctx.get("extra_context", "")

        # 自动注入 API 文档（如果没有显式传入知识上下文）
        if not knowledge_context:
            api_docs = self._load_api_docs()
            if api_docs:
                knowledge_context = api_docs
                logger.info("[TestCaseAgent] 已自动注入 Demo API 接口文档")

        try:
            # 构建 messages
            messages = TestCasePrompt.build_messages(
                requirement=prompt,
                strategy=strategy,
                case_count=case_count,
                knowledge_context=knowledge_context,
                extra_context=extra_context,
            )
            system = messages[0]["content"]
            user_prompt = messages[-1]["content"]

            # 重试机制：两阶段策略
            # 第 1 次：正常 prompt
            # 第 2 次：缩短 + 极简化 prompt，强制格式
            # 第 3 次：最后一次尝试
            max_retries = 3
            for attempt in range(max_retries):
                response = self.ask_llm(
                    prompt=user_prompt,
                    context={"system": system},
                )
                cases = self._parse_cases_from_response(response)
                valid_cases = self._validate_cases(cases)

                if valid_cases:
                    return self._success(
                        data=valid_cases,
                        stats={
                            "total": len(cases),
                            "valid": len(valid_cases),
                            "strategy": strategy,
                            "retries": attempt,
                        },
                    )

                logger.warning(f"[test_case_generator] 第 {attempt + 1} 次解析失败（共解析到 {len(cases)} 个对象，{len(valid_cases)} 个有效）")

                # 换策略：使用超精简 prompt 强调格式
                if attempt < max_retries - 1:
                    user_prompt = (
                        f"请为以下需求生成 {case_count} 个测试用例：\n\n"
                        f"「{prompt}」\n\n"
                        f"严格按此 JSON 数组格式输出（只输出 JSON，不要 markdown 代码块，不要任何解释）：\n"
                        f'[\n'
                        f'  {{"title":"用例标题","description":"描述","api_endpoint":"TBD","method":"POST",'
                        f'"headers":{{}},"request_body":{{}},"expected_response":{{"status_code":200}},'
                        f'"assertion_rules":[{{"field":"status_code","operator":"equals","expected":200}}],'
                        f'"priority":"P1","tags":["标签"],"assertions":"断言说明"}}\n'
                        f']'
                    )
                    system = (
                        "你是 API 测试工程师。只输出 JSON 数组，不可输出任何额外文字、markdown 标记或解释。"
                        "api_endpoint 如不确定填 \"TBD\"。"
                    )

            return self._error("未能解析出有效用例")
        except Exception as e:
            logger.error(f"[test_case_generator] 异常: {e}", exc_info=True)
            return self._error(str(e))

    def get_tools(self) -> List[dict]:
        """注册可用工具"""
        return [
            self._knowledge_tool.get_tool_schema(),
            self._storage_tool.get_tool_schema(),
        ]

    async def generate(
        self,
        requirement: str,
        strategy: str = "standard",
        case_count: int = 10,
        knowledge_doc_ids: Optional[List[int]] = None,
        extra_context: str = "",
        stream: bool = True,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        主入口：生成测试用例

        Args:
            requirement: 需求描述
            strategy: 生成策略 (standard/api_only/business/quick)
            case_count: 用例数量
            knowledge_doc_ids: 指定知识库文档ID列表
            extra_context: 额外上下文信息
            stream: 是否流式输出进度

        Yields:
            进度事件: {"type": "progress", "stage": "...", "message": "..."}
            最终结果: {"type": "done", "cases": [...], "stats": {...}}
        """
        try:
            # Step 1: 知识检索
            yield {"type": "progress", "stage": "knowledge_search", "message": "正在搜索知识库..."}
            knowledge_context = ""
            if knowledge_doc_ids:
                knowledge_context = await self._search_by_ids(knowledge_doc_ids)
            else:
                knowledge_context = await self._auto_search(requirement)

            yield {
                "type": "progress",
                "stage": "knowledge_search",
                "message": f"找到 {len(knowledge_context) if knowledge_context else 0} 条相关文档",
                "knowledge_found": bool(knowledge_context),
            }

            # Step 2: 构建 Prompt
            yield {"type": "progress", "stage": "prompt_build", "message": "正在构建生成提示词..."}
            messages = TestCasePrompt.build_messages(
                requirement=requirement,
                strategy=strategy,
                case_count=case_count,
                knowledge_context=knowledge_context,
                extra_context=extra_context,
            )

            # Step 3: 调用 LLM
            yield {"type": "progress", "stage": "llm_call", "message": "AI 正在生成用例..."}

            if stream:
                # 流式调用
                full_response = ""
                async for chunk in self._router.chat_stream(
                    messages=messages,
                    task_type="generation",
                ):
                    full_response += chunk
                    yield {"type": "token", "content": chunk}
            else:
                full_response = self._router.chat(
                    messages=messages,
                    task_type="generation",
                )

            # Step 4: 解析 JSON
            yield {"type": "progress", "stage": "parse", "message": "正在解析生成结果..."}
            cases = self._parse_cases_from_response(full_response)

            valid_cases = self._validate_cases(cases)
            yield {
                "type": "progress",
                "stage": "parse",
                "message": f"解析完成：{len(valid_cases)} 个有效用例，{len(cases) - len(valid_cases)} 个被过滤",
            }

            if not valid_cases:
                yield {
                    "type": "error",
                    "message": "未能解析出有效用例，请检查需求描述后重试",
                }
                return

            # Step 5: 保存到数据库
            yield {"type": "progress", "stage": "save", "message": f"正在保存 {len(valid_cases)} 个用例..."}
            save_results = self._storage_tool.save_cases(
                cases=valid_cases,
                batch_name=f"AI生成-{strategy}",
            )

            saved_count = sum(1 for r in save_results if r.success)
            failed_count = len(save_results) - saved_count

            yield {
                "type": "progress",
                "stage": "save",
                "message": f"保存完成：{saved_count} 成功，{failed_count} 失败",
            }

            # Step 6: 最终结果
            yield {
                "type": "done",
                "cases": valid_cases,
                "save_results": [r.model_dump() if hasattr(r, 'model_dump') else vars(r) for r in save_results],
                "stats": {
                    "total": len(cases),
                    "valid": len(valid_cases),
                    "saved": saved_count,
                    "failed": failed_count,
                    "strategy": strategy,
                    "knowledge_found": bool(knowledge_context),
                },
            }

        except Exception as e:
            logger.error(f"[TestCaseAgent] 生成失败: {e}", exc_info=True)
            yield {"type": "error", "message": str(e)}

    async def _auto_search(self, requirement: str) -> str:
        """自动从知识库搜索相关内容 + 加载 API 文档"""
        parts = []

        # 1. 优先加载本地 API 文档（包含真实路由信息）
        api_docs = self._load_api_docs()
        if api_docs:
            parts.append("## 可用 API 接口文档（真实部署地址）\n\n" + api_docs)

        # 2. 尝试从向量知识库检索补充内容
        try:
            results = await self._knowledge_tool.search(
                query=requirement,
                top_k=3,
            )
            kb_result = self._knowledge_tool.format_for_prompt(results)
            if kb_result and kb_result.strip():
                parts.append("## 知识库检索结果\n\n" + kb_result)
        except Exception:
            pass

        return "\n\n---\n\n".join(parts) if parts else ""

    async def _search_by_ids(self, doc_ids: List[int]) -> str:
        """根据文档ID搜索（未来实现）"""
        # TODO: 实现按文档ID精确检索
        return ""

    @staticmethod
    def _load_api_docs() -> str:
        """加载本地 Demo API 接口文档。

        按顺序搜索以下位置的 api_docs.txt：
        1. backend/demo_api/api_docs.txt
        2. demo_api/api_docs.txt（相对于当前工作目录）
        3. ai-orchestration-service/ 同级目录

        Returns:
            API 文档文本；文件不存在时返回空字符串
        """
        search_paths = [
            # Docker 容器内路径
            Path("/app/demo_api/api_docs.txt"),
            # 项目内相对路径
            Path(__file__).resolve().parent.parent.parent / "demo_api" / "api_docs.txt",
            # 当前工作目录
            Path("demo_api/api_docs.txt"),
        ]

        for path in search_paths:
            try:
                if path.exists() and path.is_file():
                    return path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

        logger.debug("[TestCaseAgent] 未找到 API 文档文件（api_docs.txt），将跳过接口文档注入")
        return ""

    def _parse_cases_from_response(self, response: str) -> List[dict]:
        """
        从 LLM 响应中解析 JSON 用例数组。

        解析策略（按优先级）：
        1. 提取 ```json/``` 代码块 → json.loads
        2. 平衡括号提取 JSON 数组 → json.loads
        3. 逐个提取平衡的大括号对象 → json.loads
        4. 修复常见 LLM 错误（尾逗号、单引号、NaN）后再试
        5. 全部失败 → 空列表
        """
        text = response.strip()
        if not text:
            return []

        # ── 策略 1: 提取 markdown 代码块 ──
        code_block_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', text)
        if code_block_match:
            text = code_block_match.group(1).strip()

        # ── 策略 2: 平衡括号提取 JSON 数组 ──
        array_result = self._extract_balanced_json(text, bracket_type='[')
        if array_result is not None:
            try:
                parsed = json.loads(array_result)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass

        # ── 策略 3: 逐个提取平衡大括号对象 ──
        objects = self._extract_all_balanced_objects(text)
        if objects:
            cases = []
            for obj_str in objects:
                try:
                    obj = json.loads(obj_str)
                    if isinstance(obj, dict):
                        cases.append(obj)
                except json.JSONDecodeError:
                    continue
            if cases:
                return cases

        # ── 策略 4: 修复常见 LLM JSON 错误后重试 ──
        repaired = self._repair_llm_json(text)
        if repaired:
            try:
                parsed = json.loads(repaired)
                if isinstance(parsed, list):
                    return parsed
                elif isinstance(parsed, dict):
                    return [parsed]
            except json.JSONDecodeError:
                pass

        # ── 策略 5: 直接解析 ──
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError:
            pass

        logger.warning(f"[TestCaseAgent] 无法解析 JSON，原始响应前200字符: {response[:200]}")
        return []

    @staticmethod
    def _extract_balanced_json(text: str, bracket_type: str = '[') -> str | None:
        """提取第一个平衡括号包裹的 JSON 文本。"""
        open_b, close_b = ('[', ']') if bracket_type == '[' else ('{', '}')
        start = text.find(open_b)
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == open_b:
                depth += 1
            elif ch == close_b:
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        return None

    @staticmethod
    def _extract_all_balanced_objects(text: str) -> List[str]:
        """逐个提取所有平衡大括号包裹的 JSON 对象。"""
        results = []
        in_string = False
        escape = False
        depth = 0
        obj_start = None

        for i, ch in enumerate(text):
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                if depth == 0:
                    obj_start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and obj_start is not None:
                    results.append(text[obj_start:i + 1])
                    obj_start = None

        return results

    @staticmethod
    def _repair_llm_json(text: str) -> str | None:
        """修复 LLM 输出中常见的 JSON 格式错误。"""
        repaired = text

        # 去掉 JSON 数组/对象前后的非 JSON 文本
        m = re.search(r'(\[.*\]|\{.*\})', repaired, re.DOTALL)
        if m:
            repaired = m.group(0)

        # 修复：尾随逗号在 } 或 ] 前
        repaired = re.sub(r',\s*(\}|\])', r'\1', repaired)

        # 修复：缺少逗号的情况（两个相邻的 "key": value 对象之间）
        repaired = re.sub(r'\}\s*\{', '},{', repaired)

        # 修复：NaN / Infinity → null
        repaired = re.sub(r'\bNaN\b', 'null', repaired)
        repaired = re.sub(r'\bInfinity\b', 'null', repaired)

        # 修复：Python 风格 None/True/False → JSON 风格
        repaired = re.sub(r'\bNone\b', 'null', repaired)
        repaired = re.sub(r'\bTrue\b', 'true', repaired)
        repaired = re.sub(r'\bFalse\b', 'false', repaired)

        # 验证修复是否有效
        try:
            json.loads(repaired)
            return repaired
        except json.JSONDecodeError:
            return None

    def _validate_cases(self, cases: List[dict]) -> List[dict]:
        """
        校验并清理用例数据

        Returns:
            通过校验的用例列表
        """
        valid = []
        for case in cases:
            if not isinstance(case, dict):
                continue

            # 必填字段检查
            if not case.get("title") or not case.get("method"):
                continue

            # 方法名标准化
            method = case.get("method", "GET").upper()
            if method not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                method = "GET"

            # 清理默认值
            clean_case = {
                "title": str(case.get("title", ""))[:200],
                "description": str(case.get("description", "")),
                "api_endpoint": str(case.get("api_endpoint", "")),
                "method": method,
                "headers": case.get("headers") if isinstance(case.get("headers"), dict) else {},
                "request_body": case.get("request_body") if isinstance(case.get("request_body"), dict) else {},
                "expected_response": case.get("expected_response") if isinstance(case.get("expected_response"), dict) else {},
                "assertion_rules": case.get("assertion_rules") if isinstance(case.get("assertion_rules"), list) else [],
                "priority": case.get("priority", "P2") if case.get("priority") in ("P0", "P1", "P2", "P3") else "P2",
                "tags": case.get("tags") if isinstance(case.get("tags"), list) else [],
                "assertions": str(case.get("assertions", "")),
            }
            valid.append(clean_case)

        return valid


# 工厂函数
def create_generator(user_id: int = None) -> TestCaseGeneratorAgent:
    return TestCaseGeneratorAgent(user_id=user_id)
