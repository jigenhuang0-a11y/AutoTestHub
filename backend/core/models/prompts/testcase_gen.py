"""
用例生成 Prompt 模板

提供多套 Prompt 策略，支持不同场景的用例生成需求。
"""
import json


class TestCasePrompt:
    """
    用例生成 Prompt 模板集

    策略说明：
    - standard: 标准策略 — 覆盖正向+逆向+边界+异常
    - api_only: 纯接口策略 — 只生成接口测试用例
    - business: 业务策略 — 侧重业务流程和场景
    - quick: 快速策略 — 轻量级快速评估
    """

    # ================================================================
    # 系统角色提示词
    # ================================================================

    SYSTEM_PROMPTS = {
        "standard": """你是一个资深软件测试工程师，专精于 API 自动化测试用例设计。

你的任务是根据需求描述，生成高质量、可执行的 API 测试用例。

设计原则：
1. **全面覆盖**：正向场景、异常场景、边界场景、安全场景
2. **可执行性**：每个用例必须包含完整的请求信息和预期结果；如果需求中未提供具体接口路径，api_endpoint 使用 "TBD"，不要虚构不存在的接口
3. **结构化**：严格遵循 JSON 格式输出
4. **优先级明确**：P0(核心流程) > P1(重要功能) > P2(一般场景) > P3(边缘情况)
5. **断言可验证**：每个断言必须可程序化验证""",

        "api_only": """你是一个 API 自动化测试专家。

请基于提供的接口信息，生成结构化的 API 测试用例。
重点关注：参数校验、响应状态码、返回数据结构、异常处理。
确保每个用例都包含具体的断言规则。

注意：如果需求中没有明确给出接口路径，请使用 "TBD" 占位，不要虚构不存在的接口。""",

        "business": """你是一个业务测试分析师。

请根据业务需求，设计端到端的业务流程测试用例。
涵盖：主流程、分支流程、异常流程、回退流程。
注意数据的前后依赖关系和状态的流转。""",

        "quick": """快速生成 3-5 个核心测试用例。
只覆盖最重要的正向场景和关键异常场景。
输出简洁，每个用例 3-5 行描述。""",
    }

    # ================================================================
    # 生成指令 Prompt
    # ================================================================

    USER_PROMPT_TEMPLATE = """## 测试需求

{requirement}

{extra_context}

## 输出要求

生成 {case_count} 个测试用例，以 JSON 数组格式输出。

每个用例对象包含以下字段：
- title: 用例标题（简洁明确，20字以内）
- description: 用例描述（场景说明）
- api_endpoint: 接口路径（如不确定填 "TBD"）
- method: HTTP方法（GET/POST/PUT/DELETE/PATCH）
- headers: 请求头（JSON对象）
- request_body: 请求体（JSON对象，GET请求为空对象）
- expected_response: 预期响应（JSON对象，含status_code和body）
- assertion_rules: 断言规则数组 [{{"field":"...","operator":"...","expected":"..."}}]
- priority: 优先级（P0/P1/P2/P3）
- tags: 标签数组
- assertions: 断言说明文本

assertion_rules 的 operator: equals / not_equals / contains / not_null / gt / lt / matches

## 格式示例

[
  {{
    "title": "正常登录验证",
    "description": "使用有效用户名和密码登录",
    "api_endpoint": "TBD",
    "method": "POST",
    "headers": {{"Content-Type": "application/json"}},
    "request_body": {{"username": "testuser", "password": "Test@123"}},
    "expected_response": {{"status_code": 200, "body": {{"token": "not_null"}}}},
    "assertion_rules": [
      {{"field": "status_code", "operator": "equals", "expected": 200}},
      {{"field": "body.token", "operator": "not_null", "expected": ""}}
    ],
    "priority": "P0",
    "tags": ["登录", "正向用例"],
    "assertions": "1.状态码200 2.返回token不为空"
  }}
]

**重要规则**：
- 直接输出上述 JSON 数组，不要用 ```json 代码块包裹
- 不要输出任何解释文字，只输出 JSON
- 不确定的字段填 "TBD" 或空对象，不可省略"""


    KNOWLEDGE_CONTEXT_TEMPLATE = """
## 知识库参考文档

以下是从知识库中检索到的相关文档，请参考其中的接口定义、业务规则：

{knowledge_content}
"""

    @classmethod
    def get_system_prompt(cls, strategy: str = "standard") -> str:
        """获取指定策略的系统提示词"""
        return cls.SYSTEM_PROMPTS.get(strategy, cls.SYSTEM_PROMPTS["standard"])

    @classmethod
    def build_user_prompt(
        cls,
        requirement: str,
        case_count: int = 10,
        knowledge_context: str = "",
        extra_context: str = "",
    ) -> str:
        """
        构建用户生成 Prompt

        Args:
            requirement: 需求描述
            case_count: 生成用例数量
            knowledge_context: 知识库检索结果（文本格式）
            extra_context: 额外上下文（如接口文档）

        Returns:
            完整用户 Prompt
        """
        # 组装额外上下文
        context_parts = []
        if knowledge_context:
            context_parts.append(
                cls.KNOWLEDGE_CONTEXT_TEMPLATE.format(
                    knowledge_content=knowledge_context
                )
            )
        if extra_context:
            context_parts.append(f"## 补充信息\n\n{extra_context}")

        return cls.USER_PROMPT_TEMPLATE.format(
            requirement=requirement,
            case_count=case_count,
            extra_context="\n".join(context_parts),
        )

    @classmethod
    def build_messages(
        cls,
        requirement: str,
        strategy: str = "standard",
        case_count: int = 10,
        knowledge_context: str = "",
        extra_context: str = "",
    ) -> list:
        """构建完整的 messages 列表"""
        return [
            {"role": "system", "content": cls.get_system_prompt(strategy)},
            {"role": "user", "content": cls.build_user_prompt(
                requirement=requirement,
                case_count=case_count,
                knowledge_context=knowledge_context,
                extra_context=extra_context,
            )},
        ]
