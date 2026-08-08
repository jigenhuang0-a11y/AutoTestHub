from pydantic import BaseModel, Field
from typing import Optional


class LLMChatRequest(BaseModel):
    """LLM 对话请求"""
    messages: list[dict] = Field(..., description="消息列表 [{\"role\": \"user\", \"content\": \"...\"}]")
    task_type: str = Field("fast_chat", description="任务类型，决定模型路由")
    model: Optional[str] = Field(None, description="指定模型名；为空则自动路由")
    temperature: Optional[float] = Field(None, description="温度参数")
    max_tokens: Optional[int] = Field(None, description="最大 Token 数")


class LLMChatResponse(BaseModel):
    """LLM 对话响应"""
    answer: str
    model_used: str


class LLMChatStreamRequest(BaseModel):
    """LLM 流式对话请求"""
    messages: list[dict] = Field(..., description="消息列表")
    task_type: str = Field("fast_chat", description="任务类型")
    model: Optional[str] = Field(None, description="指定模型名")
