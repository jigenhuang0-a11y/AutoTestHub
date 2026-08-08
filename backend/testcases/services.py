import json
import logging
from django.conf import settings
from core.llm_provider import LLMProviderFactory

logger = logging.getLogger(__name__)


class AITestCaseGenerator:
    """AI测试用例生成器（使用统一 LLM Provider，默认 DeepSeek）"""

    def __init__(self, provider_name: str = None, model: str = None):
        # 优先 DeepSeek（Key 已配置），其次 DashScope
        self.provider_name = provider_name or (
            'deepseek' if settings.DEEPSEEK_API_KEY else
            'dashscope' if settings.DASHSCOPE_API_KEY else
            None
        )
        self.model = model or (
            'deepseek-chat' if self.provider_name == 'deepseek' else
            'qwen-plus'
        )

        if not self.provider_name:
            raise ValueError("未配置任何 LLM API Key（DEEPSEEK_API_KEY 或 DASHSCOPE_API_KEY）")

        self.llm = LLMProviderFactory.create(self.provider_name, model=self.model)

    def generate_test_cases(self, api_document: str) -> list:
        """
        根据接口文档生成测试用例

        Args:
            api_document: 接口文档内容

        Returns:
            生成的测试用例列表
        """
        prompt = f"""你是一个专业的测试工程师。请根据以下接口文档，生成详细的测试用例。

接口文档：
{api_document}

请以JSON数组格式返回测试用例，每个测试用例包含以下字段：
- title: 测试用例标题
- description: 测试描述
- api_endpoint: 接口地址
- method: HTTP方法 (GET/POST/PUT/DELETE/PATCH)
- headers: 请求头对象
- request_body: 请求体对象
- expected_response: 预期响应示例
- assertions: 断言说明
- priority: 优先级 (P0/P1/P2/P3)
- tags: 标签数组

只返回JSON数组，不要有其他文字说明。确保JSON格式正确。
"""

        try:
            logger.info(f"AI生成测试用例，Provider: {self.provider_name}, Model: {self.model}")
            content = self.llm.chat([
                {'role': 'system', 'content': '你是一个专业的API测试专家'},
                {'role': 'user', 'content': prompt}
            ])

            test_cases = self._parse_json_response(content)
            return test_cases

        except Exception as e:
            raise Exception(f"AI生成测试用例失败: {str(e)}")

    def _parse_json_response(self, content: str) -> list:
        """解析AI返回的JSON响应（多策略容错）"""
        import re

        def extract_bracket_json(text):
            """从文本中提取最外层的 [] JSON数组（处理嵌套括号）"""
            start = text.find('[')
            if start == -1:
                return None
            depth = 0
            for i in range(start, len(text)):
                if text[i] == '[':
                    depth += 1
                elif text[i] == ']':
                    depth -= 1
                    if depth == 0:
                        return text[start:i+1]
            return None

        strategies = [
            # 策略1: 直接解析
            ("直接解析", lambda c: json.loads(c.strip())),
            # 策略2: 提取 ```json ... ``` 代码块（括号匹配）
            ("JSON代码块", lambda c: json.loads(
                extract_bracket_json(
                    re.search(r'```json\s*([\s\S]*?)\s*```', c, re.DOTALL)
                    .group(1) if re.search(r'```json\s*([\s\S]*?)\s*```', c, re.DOTALL) else c
                )
            )),
            # 策略3: 提取 ``` ... ``` 通用代码块（括号匹配）
            ("通用代码块", lambda c: json.loads(
                extract_bracket_json(
                    re.search(r'```\s*([\s\S]*?)\s*```', c, re.DOTALL)
                    .group(1) if re.search(r'```\s*([\s\S]*?)\s*```', c, re.DOTALL) else c
                )
            )),
            # 策略4: 全文中找最外层 [] （括号匹配）
            ("全文字段提取", lambda c: json.loads(extract_bracket_json(c))),
            # 策略5: 修复 trailing commas 后重试
            ("去尾逗号", lambda c: json.loads(
                re.sub(r',\s*(\}|\])', r'\1',
                       extract_bracket_json(c) or c)
            )),
        ]

        errors = []
        for name, strategy in strategies:
            try:
                result = strategy(content)
                if isinstance(result, list):
                    logger.info(f"JSON解析成功（策略: {name}），得到 {len(result)} 条用例")
                    return result
            except (json.JSONDecodeError, AttributeError, ValueError, IndexError, TypeError) as e:
                errors.append(f"{name}: {e}")
                continue

        logger.error(f"JSON解析全部失败: {errors}\n原始内容前500字符: {content[:500]}")
        raise ValueError(f"无法解析AI返回的结果。尝试了 {len(errors)} 种策略均失败")
