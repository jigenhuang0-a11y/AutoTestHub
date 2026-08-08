"""
代码安全检查器 — AI 生成代码入沙箱前的最后一道防线

职责：
1. 静态分析：扫描危险模式（eval/exec/os.system/文件破坏/网络滥用）
2. 风险分级：safe / warning / dangerous
3. 生成安全报告：哪些行有风险、风险原因、建议
4. 拦截 dangerous 级代码，拒绝进入沙箱

设计原则：
- 宁可误报也不能漏过（偏严格）
- warning 级别放行但留记录（测试代码必然有网络/文件操作）
- dangerous 级别直接拒绝（eval/exec/subprocess shell 注入）
- 所有扫描结果写入审计日志
"""

import re
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class SafetyLevel(str, Enum):
    """安全等级"""
    SAFE = "safe"           # 无风险，直接放行
    WARNING = "warning"     # 有潜在风险但属于测试常见操作（网络请求、文件读写），放行+标记
    DANGEROUS = "dangerous" # 高风险（eval/exec/系统调用），拒绝执行


@dataclass
class SafetyIssue:
    """单个安全问题"""
    line: int                   # 行号
    pattern: str                # 匹配到的危险模式
    category: str               # 类别：injection / system / file_destroy / network / resource
    severity: str               # high / medium / low
    snippet: str                # 问题代码片段（最多80字符）
    explanation: str            # 中文解释


@dataclass
class SafetyReport:
    """代码安全检查报告"""
    code_hash: str              # 代码 SHA256 哈希
    code_length: int            # 代码总字符数
    code_lines: int             # 代码总行数
    level: SafetyLevel          # 最终安全等级
    issues: list[SafetyIssue] = field(default_factory=list)
    passed: bool = True         # 是否放行
    scan_duration_ms: int = 0   # 扫描耗时
    scanned_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def summary(self) -> str:
        """一行摘要"""
        if not self.issues:
            return "代码安全检查通过，未发现风险模式"
        high = sum(1 for i in self.issues if i.severity == "high")
        med = sum(1 for i in self.issues if i.severity == "medium")
        return (
            f"发现 {len(self.issues)} 个风险点"
            + (f"（高危:{high}" if high else "")
            + (f", 中危:{med}" if med else "")
            + "）"
        )

    def to_dict(self) -> dict:
        return {
            "code_hash": self.code_hash,
            "code_length": self.code_length,
            "code_lines": self.code_lines,
            "level": self.level.value,
            "passed": self.passed,
            "issues_count": len(self.issues),
            "issues": [
                {
                    "line": i.line,
                    "pattern": i.pattern,
                    "category": i.category,
                    "severity": i.severity,
                    "snippet": i.snippet,
                    "explanation": i.explanation,
                }
                for i in self.issues
            ],
            "summary": self.summary(),
            "scan_duration_ms": self.scan_duration_ms,
            "scanned_at": self.scanned_at,
        }


# ============================================================
# 危险模式规则库
# ============================================================

# 规则：(正则模式, 类别, 严重程度, 中文解释)
DANGER_RULES = [
    # ── 代码注入（高危）──
    (r'\beval\s*\(', "injection", "high", "eval() 可执行任意 Python 代码，存在代码注入风险"),
    (r'\bexec\s*\(', "injection", "high", "exec() 可执行任意 Python 代码，存在代码注入风险"),
    (r'\bcompile\s*\(', "injection", "high", "compile() 配合 exec 可执行任意代码"),
    (r'\b__import__\s*\(', "injection", "high", "__import__() 可动态导入任意模块，可能绕过安全限制"),

    # ── 系统调用（高危）──
    (r'\bos\.system\s*\(', "system", "high", "os.system() 直接执行系统命令，可造成主机入侵"),
    (r'\bos\.popen\s*\(', "system", "high", "os.popen() 可执行系统命令并读取输出"),
    (r'\bsubprocess\.(call|Popen|run|check_output|check_call)\s*\(', "system", "high",
     "subprocess 调用可执行系统命令"),
    (r'shell\s*=\s*True', "system", "high", "shell=True 存在命令注入风险"),

    # ── 文件破坏（中危 - 测试中可能使用）──
    (r'\bos\.(remove|unlink)\s*\(', "file_destroy", "medium", "删除文件操作"),
    (r'\bshutil\.rmtree\s*\(', "file_destroy", "medium", "递归删除目录，可能造成数据丢失"),
    (r'\bos\.rmdir\s*\(', "file_destroy", "medium", "删除目录操作"),
    (r'open\([^)]*,\s*[\'"]w[\'"]', "file_destroy", "medium", "以写入模式打开文件，可能覆盖重要数据"),

    # ── 网络滥用（低危 - 测试常用）──
    (r'\bsocket\.(socket|connect)\s*\(', "network", "medium", "原始 socket 连接"),
    (r'\brequests\.(get|post|put|delete|patch)\s*\(', "network", "low",
     "HTTP 网络请求（测试常用，但需确认目标地址）"),
    (r'\burllib\.(request|urlopen)\s*\(', "network", "low", "urllib 网络请求"),
    (r'\bhttpx\.(get|post|put|delete)\s*\(', "network", "low", "httpx 网络请求"),

    # ── 资源滥用（中危）──
    (r'\bwhile\s+True\s*:', "resource", "medium", "无限循环，可能导致沙箱超时"),
    (r'\bmultiprocessing\.(Process|Pool)\s*\(', "resource", "medium", "多进程创建，可能绕过进程数限制"),
    (r'\bthreading\.Thread\s*\(', "resource", "medium", "多线程创建，大量线程可能耗尽资源"),
    (r'time\.sleep\s*\(\s*\d{3,}', "resource", "low", "长时间 sleep，可能触发沙箱超时"),

    # ── 敏感路径访问（中危）──
    (r'[\'"]/(etc|proc|sys|dev|root|var/log)/', "file_destroy", "medium",
     "访问系统敏感路径（Linux）"),
    (r'[\'"]C:\\(Windows|Program Files|System32)', "file_destroy", "medium",
     "访问系统敏感路径（Windows）"),
    (r'os\.environ\[', "system", "medium", "读取环境变量，可能泄露敏感信息"),
]

# 白名单：这些 import 语句本身不是危险操作
WHITELIST_IMPORT_PATTERNS = [
    r'^\s*(from|import)\s+',  # import 语句本身不危险
    r'^\s*#',                  # 注释
    r'^\s*$',                  # 空行
]


class CodeSafetyChecker:
    """
    AI 生成代码安全检查器

    使用方式：
        checker = CodeSafetyChecker()
        report = checker.scan(ai_generated_code)

        if report.passed:
            # 放行，进入沙箱执行
            sandbox.run_script(code)
        else:
            # 拒绝，返回 report.to_dict() 给前端
            raise SafetyRejected(report)
    """

    def __init__(self, strict_mode: bool = True):
        """
        Args:
            strict_mode: True=任何高危模式直接拒绝，False=高危也仅 warning（调试用）
        """
        self.strict_mode = strict_mode

    def scan(self, code: str) -> SafetyReport:
        """扫描代码并返回安全报告"""
        import time
        start = time.time()

        code_hash = hashlib.sha256(code.encode()).hexdigest()
        lines = code.split("\n")
        issues = []

        for line_no, line in enumerate(lines, start=1):
            # 跳过 import 和注释行
            if self._is_whitelisted(line):
                continue

            for pattern, category, severity, explanation in DANGER_RULES:
                if re.search(pattern, line, re.IGNORECASE):
                    snippet = line.strip()[:80]
                    issues.append(SafetyIssue(
                        line=line_no,
                        pattern=pattern,
                        category=category,
                        severity=severity,
                        snippet=snippet,
                        explanation=explanation,
                    ))
                    break  # 一行只记录第一个命中规则

        # 确定安全等级
        if not issues:
            level = SafetyLevel.SAFE
            passed = True
        elif self.strict_mode and any(i.severity == "high" for i in issues):
            level = SafetyLevel.DANGEROUS
            passed = False
        else:
            level = SafetyLevel.WARNING
            passed = True

        scan_duration = int((time.time() - start) * 1000)

        report = SafetyReport(
            code_hash=code_hash,
            code_length=len(code),
            code_lines=len(lines),
            level=level,
            issues=issues,
            passed=passed,
            scan_duration_ms=scan_duration,
        )

        log_msg = (
            f"[SafetyCheck] hash={code_hash[:12]} "
            f"level={level.value} passed={passed} "
            f"issues={len(issues)} duration={scan_duration}ms"
        )
        if passed:
            logger.info(log_msg)
        else:
            logger.warning(f"{log_msg}  | BLOCKED - {report.summary()}")

        return report

    def _is_whitelisted(self, line: str) -> bool:
        """检查该行是否属于安全白名单（import/注释/空行）
        
        注意：只白名单纯 import 行，如果 import 后面通过 ; 拼接了其他操作，
        则只去掉 import 部分，剩余部分仍需安全扫描。
        """
        for pattern in WHITELIST_IMPORT_PATTERNS:
            if re.match(pattern, line):
                # 纯 import/注释/空行 → 完全放行
                if ';' not in line:
                    return True
                # import os; os.system(...) → 将 import 后的部分提取出来继续扫描
                # 这种情况不能整行放行
                return False
        return False


class SafetyRejected(Exception):
    """安全检查拒绝异常"""

    def __init__(self, report: SafetyReport):
        self.report = report
        super().__init__(f"代码安全检查未通过: {report.summary()}")


# 全局单例
_safety_checker: Optional[CodeSafetyChecker] = None


def get_safety_checker() -> CodeSafetyChecker:
    """获取全局安全检查器"""
    global _safety_checker
    if _safety_checker is None:
        _safety_checker = CodeSafetyChecker(strict_mode=True)
    return _safety_checker
