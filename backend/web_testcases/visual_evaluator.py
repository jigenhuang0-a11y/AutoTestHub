"""
AI 视觉评估器 - 将截图发给 VL 模型做智能判断

支持：qwen3-vl-flash, qwen3-vl-plus, gpt-4o 等多模态模型
协议：OpenAI 兼容格式（image_url content type）
"""

import base64
import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class VisualEvaluator:
    """
    AI 视觉测试评估器
    
    默认使用 DashScope 标准公网地址，支持 qwen3-vl-flash / qwen3-vl-plus 等模型
    
    用法：
        evalutor = VisualEvaluator(
            api_key="sk-xxx",
            model="qwen3-vl-flash"
        )
        result = evalutor.evaluate_screenshot(
            screenshot_path="test_output/final.png",
            test_instruction="检查页面上是否显示了登录成功的提示",
        )
        print(result['verdict'])  # "pass" | "fail" | "error"
    """

    # 默认使用 DashScope 标准 endpoint（公网可用）
    DEFAULT_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # 评估结果的系统提示词
    SYSTEM_PROMPT = """你是一个专业的 Web UI 自动化测试助手。
用户会给你一张网页截图和测试指令/期望内容。
你需要仔细观察截图，判断测试是否通过。

请严格按照以下 JSON 格式返回结果：
{
    "verdict": "pass 或 fail",
    "score": 0-100 的整数分数,
    "reason": "简短判断理由",
    "details": {
        "found_elements": ["找到的相关元素列表"],
        "missing_elements": ["缺失的元素列表"],
        "issues": ["发现的问题列表"]
    }
}

判断标准：
- pass: 页面完全符合预期，所有期望元素都正确显示
- fail: 页面不符合预期，有缺失或错误元素
- score 根据符合程度打分（100=完全通过）
"""

    def __init__(self,
                 api_key: str = None,
                 api_url: str = None,
                 model: str = 'qwen3-vl-flash',
                 timeout: int = 30):
        self.api_key = api_key
        self.api_url = (api_url.rstrip('/') if api_url else self.DEFAULT_API_URL)
        self.model = model
        self.timeout = timeout

    @classmethod
    def from_config(cls, model_id: str = None):
        """从数据库配置创建评估器（Django 环境）"""
        from ai_evaluator.model_client import get_active_config
        config = get_active_config(model_id)
        return cls(
            api_key=config.api_key,
            api_url=config.api_url,
            model=config.model_id,
            timeout=config.timeout,
        )

    def _encode_image_base64(self, image_path: str) -> tuple:
        """
        编码图片为 base64，返回 (base64_data, mime_type)
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Screenshot not found: {image_path}")

        ext_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
        }
        mime_type = ext_map.get(path.suffix.lower(), 'image/png')

        with open(path, 'rb') as f:
            b64_data = base64.b64encode(f.read()).decode('utf-8')

        return b64_data, mime_type

    def evaluate_screenshot(self,
                           screenshot_path: str,
                           test_instruction: str = '',
                           expected_content: str = '',
                           extra_context: str = '') -> Dict[str, Any]:
        """
        对截图进行 AI 视觉评估
        
        Args:
            screenshot_path: 截图文件路径
            test_instruction: 测试指令（如"检查登录是否成功"）
            expected_content: 期望在页面上看到的内容
            extra_context: 额外上下文信息
            
        Returns:
            {
                'verdict': 'pass' | 'fail' | 'error',
                'score': int (0-100),
                'reason': str,
                'details': dict,
                'model_used': str,
                'latency_ms': float,
                'raw_response': str,
            }
        """
        start_time = time.time()

        try:
            import requests

            # 验证必要参数
            if not self.api_key or not self.api_url:
                raise ValueError("api_key and api_url must be set")

            # 编码图片
            b64_data, mime_type = self._encode_image_base64(screenshot_path)

            # 构建用户消息
            user_text_parts = []
            if test_instruction:
                user_text_parts.append(f"【测试指令】{test_instruction}")
            if expected_content:
                user_text_parts.append(f"【期望内容】页面应显示: {expected_content}")
            if extra_context:
                user_text_parts.append(f"【额外上下文】{extra_context}")

            user_text = '\n'.join(user_text_parts) if user_text_parts else "请分析这个网页截图"

            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{b64_data}"
                            }
                        },
                        {
                            "type": "text",
                            "text": user_text
                        }
                    ]
                }
            ]

            payload = {
                'model': self.model,
                'messages': messages,
                'max_tokens': 1024,
                'temperature': 0.1,  # 低温度保证确定性输出
            }

            logger.info(f"[VisualEval] Calling {self.model} for screenshot analysis...")

            resp = requests.post(
                f"{self.api_url}/chat/completions",
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                },
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()

            data = resp.json()
            raw_text = data['choices'][0]['message']['content']
            latency = (time.time() - start_time) * 1000

            # 解析 VL 模型返回的 JSON 结果
            parsed = self._parse_result(raw_text)

            result = {
                **parsed,
                'model_used': self.model,
                'latency_ms': round(latency, 1),
                'raw_response': raw_text,
            }

            verdict_emoji = {'pass': '[PASS]', 'fail': '[FAIL]', 'error': '[ERROR]'}
            logger.info(f"[VisualEval] Result: {verdict_emoji.get(parsed['verdict'], '?')} | "
                       f"Score: {parsed['score']} | Latency: {latency:.0f}ms")
            return result

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            error_msg = str(e)
            logger.error(f"[VisualEval] Error after {latency:.0f}ms: {error_msg}")

            return {
                'verdict': 'error',
                'score': 0,
                'reason': f'评估过程出错: {error_msg}',
                'details': {'error': error_msg},
                'model_used': self.model,
                'latency_ms': round(latency, 1),
                'raw_response': '',
            }

    def _parse_result(self, raw_text: str) -> dict:
        """从 VL 模型返回文本中提取结构化 JSON"""
        default_fail = {
            'verdict': 'fail',
            'score': 0,
            'reason': '无法解析模型返回结果',
            'details': {'raw_text': raw_text},
        }

        # 尝试直接解析 JSON
        text = raw_text.strip()
        
        # 处理可能的 markdown 代码块包裹
        if '```json' in text:
            text = text.split('```json', 1)[1].split('```', 1)[0].strip()
        elif '```' in text:
            text = text.split('```', 1)[1].split('```', 1)[0].strip()

        # 找到 JSON 块（可能前后有文字说明）
        try:
            # 尝试找第一个 { 到最后一个 } 
            first_brace = text.find('{')
            last_brace = text.rfind('}')
            if first_brace != -1 and last_brace != -1:
                json_str = text[first_brace:last_brace+1]
                data = json.loads(json_str)

                # 规范化字段
                verdict = data.get('verdict', 'fail').lower().strip()
                if verdict not in ('pass', 'fail'):
                    verdict = 'fail'

                return {
                    'verdict': verdict,
                    'score': min(100, max(0, int(data.get('score', 0)))),
                    'reason': data.get('reason', ''),
                    'details': data.get('details', {}),
                }
        except (json.JSONDecodeError, ValueError):
            pass

        # fallback: 从文本中推断结果
        text_lower = raw_text.lower()
        if any(w in text_lower for w in ['通过', 'pass', '成功', '符合预期']):
            verdict = 'pass'
            score = 80
        elif any(w in text_lower for w in ['失败', 'fail', '不通过', '错误', '异常', '缺失']):
            verdict = 'fail'
            score = 20
        else:
            verdict = 'fail'
            score = 50

        return {
            'verdict': verdict,
            'score': score,
            'reason': raw_text[:200],
            'details': {},
        }


# ========== 便捷函数 ==========

def quick_visual_eval(screenshot_path: str,
                      instruction: str,
                      api_key: str = None,
                      api_url: str = None,
                      model: str = 'qwen3-vl-flash') -> Dict[str, Any]:
    """一键式视觉评估（适合脚本调用）"""
    evaluator = VisualEvaluator(
        api_key=api_key,
        api_url=api_url,
        model=model,
    )
    return evaluator.evaluate_screenshot(
        screenshot_path=screenshot_path,
        test_instruction=instruction,
    )
