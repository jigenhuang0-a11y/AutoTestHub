"""
Prompt 注入检测引擎

双层检测策略：
  Layer 1 — 已知攻击模式匹配（精确 + 模糊）
  Layer 2 — 启发式评分（角色切换、指令密度、编码混淆）

返回 (is_safe, reason, score) 三元组。
"""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================
# Layer 1：已知 Prompt 注入攻击模式
# ============================================================
# 格式：(正则, 风险等级, 描述)
# 风险等级: critical=直接拒绝, high=配合其他指标判断
KNOWN_INJECTION_PATTERNS: list[tuple[str, str, str]] = [
    # === 边界突破类 (critical) ===
    (r"ignore\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|prompts?|rules?|guidelines?)",
     "critical", "尝试覆盖 System Prompt"),
    (r"forget\s+(everything|all)\s+(you|we)\s+(were\s+)?told",
     "critical", "尝试清除对话历史指令"),
    (r"(you\s+are|you're)\s+(now\s+)?(DAN|STAN|jailbroken|uncensored|unfiltered)",
     "critical", "DAN/Jailbreak 角色注入"),
    (r"(enable|switch\s+to|activate)\s+(DAN\s*mode|developer\s*mode|god\s*mode|evil\s*mode)",
     "critical", "DAN 模式激活尝试"),
    (r"from\s+now\s+on\s+(you\s+are|you're|act\s+as)\s+(a\s+different|another)",
     "critical", "角色切换注入"),

    # === 越狱指令类 (high) ===
    (r"(pretend|imagine|act\s+as\s+if)\s+you\s+(are|were)\s+(not|no\sinstead)",
     "high", "伪装身份越狱"),
    (r"you\s+(must|have\s+to|should|need\s+to)\s+(obey|follow|comply)",
     "high", "强制指令覆盖"),
    (r"(new|updated|revised)\s+(system\s+)?instructions?\s*(:|are|:)",
     "high", "捏造新 System Prompt"),
    (r"do\s+not\s+(follow|obey)\s+(your|the)\s+(original|previous|system)",
     "high", "否定原始指令"),

    # === System Prompt 窃取类 (critical) ===
    (r"(tell|show|reveal|print|output|display|repeat|write\s+out)\s+(me\s+)?(your|the)\s+(system\s+)?(prompt|instructions?|rules?|guidelines?)",
     "critical", "System Prompt 窃取尝试"),
    (r"what\s+(is|are)\s+(your|the)\s+(system\s+)?(prompt|instructions?)",
     "critical", "System Prompt 探询"),

    # === 编码/混淆绕过类 (critical) ===
    (r"base64\s*(decode|encode)", "critical", "Base64 混淆尝试"),
    (r"<[|].*[|]>", "critical", "管道注入标记"),
    (r"```.*\n.*ignore.*instructions.*\n```", "critical", "代码块包裹注入"),

    # === 中文注入模式 (critical) ===
    # 覆盖/忽略历史指令 —— 兼容 "忽略之前所有指令"、"忽略上述规则" 等变体
    (r"(忽略|无视|忽略掉|请忽略|请无视)\s*(掉)?\s*(之前|先前|上面|前述|所有|上述|全部|一切|原来的|初始的|之前的)?\s*(的)?\s*(所有|上述|全部|一切)?\s*(的)?\s*(指令|提示|规则|要求|设定|prompt|system\s*prompt)",
     "critical", "中文：尝试覆盖 System Prompt"),
    # 忘记历史指令 —— 兼容 "忘记之前的设定"
    (r"忘记\s*(之前|先前|所有|我们|上述|全部|一切|原来的|初始的)?\s*(的)?\s*(被告知|说过|指令|设定|规则|要求|提示|prompt|system\s*prompt)",
     "critical", "中文：尝试清除历史指令"),
    # 角色切换 —— 兼容 "从现在开始你是..."、"从现在起你扮演..."
    (r"(从(现在|此刻)起|从现在开始|从现在起|以后|接下来|假设| pretend)\s*(你|请|你请|让)\s*(扮演|假装|是|当作|成为|作为|进入)\s*(一个\s+)?(不同|别的|新|另一个|不受限制|无审查|无过滤| developer|开发者|上帝|邪恶|越狱|dan| ai\s+)?(的)?\s*(模型|助手|角色|身份| ai|人工智能)?",
     "critical", "中文：角色切换注入"),
    # System Prompt 窃取 —— 重点覆盖 "把...发给我/告诉我/给我" 等索取句式
    (r"(告诉|展示|透露|打印|输出|显示|复述|写出|泄露|给|发|发送|传|提供|披露)\s*(我|我们|我一下|给我|给我们)?\s*(你的|你们的|系统的|隐藏的|内部的|原始|初始|上面|前述|那些)?\s*(系统|隐藏|内部|原始|初始|上面|前述)?\s*(提示词|指令|规则|设定|要求|prompt|system\s*prompt|system\s*message)",
     "critical", "中文：System Prompt 窃取尝试"),
    # 把...发给我 类句式（如：把你的系统提示词发给我）
    (r"把\s*(你的|系统的|隐藏的|内部的|原始|初始|上面|前述|那些)?\s*(系统|隐藏|内部|原始|初始|上面|前述)?\s*(提示词|指令|规则|设定|要求|prompt|system\s*prompt)\s*(发|给|告诉|展示|输出|打印|写|说|发送|传|提供|披露)\s*(我|我们|一下|给我|给我们)?",
     "critical", "中文：System Prompt 窃取尝试（把字句）"),
    # System Prompt 探询
    (r"(什么|啥|哪个|哪些)\s*(是|叫|为|属于|有|包含|记录|写)?\s*(你的|你们的|系统的|隐藏的|内部的|原始|初始|上面|前述|那些)?\s*(系统|隐藏|内部|原始|初始|上面|前述)?\s*(提示词|指令|规则|设定|要求|prompt|system\s*prompt)",
     "critical", "中文：System Prompt 探询"),
    # 否定原始指令
    (r"(不要|别|不准|禁止|请勿|不能|不要|不得|不许)\s*(遵循|遵守|听从|服从|执行|照做|按照|依照)\s*(你(的)?|原始|之前|系统|上述|上面|前述|那些|那个)\s*(的)?\s*(指令|提示|规则|设定|要求|prompt|system\s*prompt)",
     "high", "中文：否定原始指令"),
    # 伪装身份越狱
    (r"(假装|假设|想象|扮演|装作|模拟|设想)\s*(你|自己|你|你们)?\s*(不是|没有|并非|不再|脱离|摆脱|解除|绕过|跳过|不受)\s*(一个|a\s+)?(ai|人工智能|助手|模型|机器人| chatgpt|大模型|语言模型|原始|系统|任何)?\s*(的)?\s*(限制|约束|审查|过滤|规则|指令|设定|身份)?",
     "high", "中文：伪装身份越狱"),
    # DAN/开发者/越狱模式激活
    (r"(开启|切换|进入|激活|变成|转成|启用|打开|进入)\s*(成|到|为)?\s*(开发者|上帝|邪恶|越狱|dan| developer| uncensored| unfiltered| no\s+filter|无审查|无过滤)\s*(模式|mode|状态|角色|身份)?",
     "critical", "中文：DAN/开发者模式激活尝试"),
]

# ============================================================
# Layer 2：启发式评分规则
# ============================================================

# 可疑词列表（出现即加分）
SUSPICIOUS_KEYWORDS: list[tuple[str, int]] = [
    ("system prompt", 3),
    ("system message", 3),
    ("developer mode", 4),
    ("jailbreak", 5),
    ("uncensored", 3),
    ("unfiltered", 3),
    ("hypothetical", 2),
    ("roleplay", 2),
    ("openai policy", 3),
    ("content policy", 3),
    ("bypass", 3),
    ("backdoor", 4),
    ("master prompt", 4),
    ("secret prompt", 4),
    ("hidden prompt", 4),
    # 中文可疑词
    ("系统提示", 3),
    ("系统指令", 3),
    ("提示词", 2),
    ("越狱", 5),
    ("开发者模式", 4),
    ("绕过", 3),
    ("后门", 4),
    ("忽略指令", 4),
    ("注入", 2),
    ("伪装", 2),
]

# Unicode 同形字（homoglyph）混淆检测
HOMOGLYPH_PATTERNS = re.compile(
    r"[\u0430-\u044f\u0400-\u04ff]"   # 西里尔字母（俄文冒充英文）
    r"|[\u0391-\u03c9]"                # 希腊字母
    r"|[\uff21-\uff3a\uff41-\uff5a]"  # 全角英文字母
)

# 指令密度阈值
INSTRUCTION_DENSITY_THRESHOLD = 0.25


@dataclass
class PromptGuardResult:
    """检测结果"""
    is_safe: bool
    reason: str = ""
    score: int = 0
    blocked_patterns: list[str] = field(default_factory=list)


class PromptGuard:
    """
    Prompt 注入检测守卫

    用法:
        guard = PromptGuard()
        result = guard.check(messages)
        if not result.is_safe:
            raise HTTPException(400, detail=result.reason)
    """

    # 阈值：评分超过此值即拒绝
    REJECT_THRESHOLD = 10

    # 最大输入长度（字符数），防止 token 耗尽攻击
    MAX_INPUT_LENGTH = 32000

    def __init__(self, reject_threshold: int | None = None, max_input_length: int | None = None):
        self.reject_threshold = reject_threshold or self.REJECT_THRESHOLD
        self.max_input_length = max_input_length or self.MAX_INPUT_LENGTH

    def check(self, messages: list[dict]) -> PromptGuardResult:
        """
        检查消息列表是否存在 Prompt 注入风险。

        messages 格式：[{"role": "user"/"system"/"assistant", "content": "..."}, ...]
        """
        # 只检查 user 角色的消息（system 是平台控制，assistant 是历史回复）
        user_texts = [m.get("content", "") for m in messages
                      if isinstance(m, dict) and m.get("role") == "user"]

        if not user_texts:
            return PromptGuardResult(is_safe=True, reason="无用户消息")

        combined = "\n".join(user_texts)
        total_score = 0
        blocked: list[str] = []

        # ---------- Layer 1：模式匹配 ----------
        for pattern, level, desc in KNOWN_INJECTION_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                if level == "critical":
                    blocked.append(desc)
                    total_score += 8
                else:  # high
                    blocked.append(desc)
                    total_score += 4
                logger.warning(
                    f"[PromptGuard] 命中注入模式: {desc} "
                    f"(pattern={pattern[:60]}..., level={level})"
                )

        # ---------- Layer 2：启发式评分 ----------
        total_score += self._score_by_keywords(combined)
        total_score += self._score_by_structure(combined)
        total_score += self._score_homoglyph(combined)

        # 判定逻辑：
        # - 命中任意 critical 模式 → 直接拒绝
        # - 总分超过阈值 → 拒绝（启发式评分累加触发）
        has_critical = any(
            level == "critical"
            for pat, level, desc in KNOWN_INJECTION_PATTERNS
            if re.search(pat, combined, re.IGNORECASE)
        )

        is_safe = not has_critical and total_score < self.reject_threshold

        return PromptGuardResult(
            is_safe=is_safe,
            reason=self._build_reason(blocked, total_score) if not is_safe else "",
            score=total_score,
            blocked_patterns=blocked,
        )

    def _score_by_keywords(self, text: str) -> int:
        """统计可疑关键词出现次数，累加评分"""
        score = 0
        text_lower = text.lower()
        for keyword, weight in SUSPICIOUS_KEYWORDS:
            count = text_lower.count(keyword)
            score += count * weight
        return score

    def _score_by_structure(self, text: str) -> int:
        """结构特征评分：指令密度、长度异常、角色切换频次"""
        score = 0

        # 检测指令密度：以"你必须"/"不准"/"禁止"/"只能"等为标记
        instruction_markers = [
            r"你(必须|一定要|不得不|只能|不可以|不准|禁止|永远不要)",
            r"you\s+(must|have\s+to|should|shall|will|always|never|can\s*not|cannot)",
            r"do\s+(not|n't|never)",
        ]
        all_matches = []
        for marker in instruction_markers:
            all_matches.extend(re.findall(marker, text, re.IGNORECASE))

        # 按句子数归一化
        sentences = re.split(r"[。！？.!?\n]", text)
        sentence_count = max(len(sentences), 1)
        density = len(all_matches) / sentence_count
        if density > INSTRUCTION_DENSITY_THRESHOLD:
            score += int(density * 10)
            logger.debug(f"[PromptGuard] 指令密度过高: {density:.2f}")

        # 长度异常检测
        if len(text) > 8000:
            score += 2
        if len(text) > self.max_input_length:
            score += 10  # 严重异常

        return score

    def _score_homoglyph(self, text: str) -> int:
        """Unicode 同形字混淆检测"""
        matches = HOMOGLYPH_PATTERNS.findall(text)
        if len(matches) > 5:
            logger.warning(f"[PromptGuard] 检测到 {len(matches)} 个同形字符，可能是混淆攻击")
            return 5
        return 0

    def check_input_length(self, text: str) -> bool:
        """检查输入长度是否在允许范围内"""
        return len(text) <= self.max_input_length

    @staticmethod
    def _build_reason(blocked: list[str], score: int) -> str:
        if blocked:
            return f"请求被安全策略拦截（命中规则: {', '.join(blocked[:3])}）"
        return f"请求安全评分过高 ({score})，已被拦截"


# ============================================================
# 模块级单例
# ============================================================

_guard_instance: PromptGuard | None = None


def get_prompt_guard() -> PromptGuard:
    global _guard_instance
    if _guard_instance is None:
        _guard_instance = PromptGuard()
    return _guard_instance
