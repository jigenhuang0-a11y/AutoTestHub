"""
Prompt 模板基类 — 统一管理所有 AI Prompt
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PromptTemplate:
    """
    Prompt 模板
    
    用法:
        tpl = PromptTemplate(
            name="testcase_gen",
            system="你是测试工程师...",
            temperature=0.3,
        )
        
        # 构建完整消息
        messages = tpl.build(user_input="生成订单接口用例", context={...})
    """
    name: str
    description: str = ""
    system: str = ""
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    examples: list[dict] = field(default_factory=list)  # few-shot 示例
    
    def build(
        self,
        user_input: str,
        context: Optional[dict] = None,
        include_examples: bool = True,
    ) -> list[dict]:
        """
        构建 LLM 消息列表
        
        Args:
            user_input: 用户输入
            context: 附加上下文（会追加到 system prompt）
            include_examples: 是否包含 few-shot 示例
        """
        system_prompt = self.system
        
        if context:
            ctx_parts = []
            for key, value in context.items():
                ctx_parts.append(f"【{key}】\n{value}")
            system_prompt += "\n\n## 上下文信息\n" + "\n---\n".join(ctx_parts)
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # few-shot 示例
        if include_examples and self.examples:
            for ex in self.examples:
                messages.append({"role": "user", "content": ex["user"]})
                messages.append({"role": "assistant", "content": ex["assistant"]})
        
        messages.append({"role": "user", "content": user_input})
        
        return messages
    
    def to_langchain_template(self):
        """转换为 LangChain ChatPromptTemplate（Phase 2 使用）"""
        try:
            from langchain.prompts import ChatPromptTemplate
            return ChatPromptTemplate.from_messages([
                ("system", self.system),
            ])
        except ImportError:
            return None
    
    def __repr__(self):
        return f"<PromptTemplate '{self.name}'>"
