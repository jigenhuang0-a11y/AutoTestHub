"""
数据工厂 Prompt 模板 — 智能造数 + 变量绑定

三套策略：
- smart:    智能生成，基于字段语义 + 业务规则
- boundary: 边界值生成，覆盖 null/空/超长/特殊字符
- template: 模板驱动，基于现有模板生成
"""
from typing import Dict


class DataFactoryPrompt:
    """数据工厂 Prompt 模板集"""

    # ============================================================
    # 系统提示词
    # ============================================================
    SYSTEM_PROMPTS: Dict[str, str] = {
        "smart": """你是一个专业的测试数据生成专家。你需要根据字段定义和业务规则，生成真实、合理、多样化的测试数据。

生成规则：
1. **真实性**：数据应符合真实业务场景（如订单金额、用户名、地址等）
2. **多样性**：覆盖正常值、边界值、异常值
3. **关联性**：字段间保持业务逻辑一致性（如订单状态与物流状态匹配）
4. **可测试性**：数据应能覆盖测试用例的断言需求

返回格式：纯 JSON 数组，每个元素是一条数据记录，字段名与定义一致。

例：
[
  {{"field1": "value1", "field2": 100}},
  {{"field1": "value2", "field2": 200}}
]""",

        "boundary": """你是一个边界值测试数据生成专家。你需要为每个字段生成覆盖以下场景的测试数据：

1. **正常值**：常规有效数据
2. **null/空值**：字段为 null 或空字符串
3. **超长值**：超过最大长度的字符串
4. **特殊字符**：注入 <script>、SQL 注入、emoji 等
5. **负数/零值**：数值类字段的特殊情况
6. **格式错误**：不符合格式要求的数据

返回格式：纯 JSON 数组，添加 `_boundary_tag` 字段标记边界类型。

例：
[
  {{"name": "正常用户", "amount": 100, "_boundary_tag": "normal"}},
  {{"name": null, "amount": -1, "_boundary_tag": "null_and_negative"}}
]""",

        "template": """你是一个数据生成专家。你需要根据提供的模板定义和生成规则，批量生成符合规范的测试数据。

请严格按照模板的字段类型和约束条件生成数据，确保每个字段的值都在合法范围内。

返回格式：纯 JSON 数组，每个元素是一条完整的数据记录。""",
    }

    # ============================================================
    # 用户提示词模板
    # ============================================================
    USER_PROMPT_TEMPLATE = """请根据以下信息生成测试数据：

【业务领域】
{business_domain}

【字段定义】
{field_definitions}

【生成数量】
{record_count} 条

【生成要求】
{requirements}

【知识库参考】
{knowledge_context}

【额外约束】
{extra_context}

请严格按照 JSON 数组格式返回，不要包含任何其他文字。"""

    # ============================================================
    # 字段定义格式化
    # ============================================================
    @staticmethod
    def format_field_definitions(fields: list) -> str:
        """将字段列表格式化为可读文本"""
        lines = []
        for i, f in enumerate(fields, 1):
            if isinstance(f, dict):
                name = f.get("name", f"field_{i}")
                ftype = f.get("type", "string")
                desc = f.get("description", "")
                constraints = f.get("constraints", {})
                parts = [f"{i}. **{name}** (类型: {ftype})"]
                if desc:
                    parts.append(f"   描述: {desc}")
                if constraints:
                    for k, v in constraints.items():
                        parts.append(f"   {k}: {v}")
                lines.append("\n".join(parts))
            elif isinstance(f, str):
                lines.append(f"{i}. **{f}**")
        return "\n".join(lines)

    # ============================================================
    # 变量绑定提示词
    # ============================================================
    VARIABLE_BINDING_PROMPT = """你是一个测试变量绑定专家。请根据测试用例的变量定义，从生成的数据集中智能匹配并绑定合适的变量值。

规则：
1. **名称匹配**：优先匹配变量名与数据字段名相同的
2. **语义匹配**：变量名意义相似的（如 `{{username}}` 匹配 `name` 字段）
3. **类型匹配**：确保数据类型一致
4. **占位符格式**：使用 `{{{{var_name}}}}` 格式
    
返回 JSON 对象，key 为变量名，value 为绑定的值。

例：
{{"username": "test_user_001", "order_amount": 100, "token": "Bearer xxx"}}"""

    # ============================================================
    # 构建方法
    # ============================================================
    @classmethod
    def build_messages(cls,
                       business_domain: str = "",
                       field_definitions: list = None,
                       record_count: int = 10,
                       strategy: str = "smart",
                       knowledge_context: str = "",
                       extra_context: str = "",
                       requirements: str = "") -> list:
        """
        构建完整的 LLM 消息列表

        Args:
            business_domain: 业务领域 (order/user/logistics/after_sales)
            field_definitions: 字段定义列表
            record_count: 生成数量
            strategy: 生成策略
            knowledge_context: 知识库上下文
            extra_context: 额外约束
            requirements: 生成要求

        Returns:
            [system_msg, user_msg]
        """
        system_prompt = cls.SYSTEM_PROMPTS.get(strategy, cls.SYSTEM_PROMPTS["smart"])

        if not requirements:
            requirements = f"生成 {record_count} 条{business_domain or '通用'}业务测试数据"

        field_text = cls.format_field_definitions(field_definitions or [])

        user_prompt = cls.USER_PROMPT_TEMPLATE.format(
            business_domain=business_domain or "通用",
            field_definitions=field_text or "（自动推断字段）",
            record_count=record_count,
            requirements=requirements,
            knowledge_context=knowledge_context or "无",
            extra_context=extra_context or "无",
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
