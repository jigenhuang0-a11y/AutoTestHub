"""
Allure 报告生成工具 — 打包 Allure 原始数据 + 生成 HTML 报告
"""
import os
import json
import shutil
import zipfile
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class AllureReporterTool:
    """
    Allure 报告工具

    功能：
    1. 检查 allure-data 目录中是否有结果文件
    2. 尝试调用 allure 命令行生成 HTML 报告
    3. 打包 allure 结果文件为 zip 供下载
    4. 生成简易 JSON 摘要（当 allure CLI 不可用时回退）
    """

    name = "allure_reporter"
    description = "生成和打包 Allure 测试报告"

    def __init__(self, user_id: int = None):
        try:
            self.report_base = settings.ALLURE_REPORT_DIR
        except AttributeError:
            self.report_base = Path(__file__).resolve().parent.parent.parent / "allure_reports"
        self.report_base = Path(self.report_base)
        self.user_id = user_id

    def check_allure_cli(self) -> bool:
        """检查 allure 命令行是否可用"""
        import subprocess
        try:
            result = subprocess.run(
                ["allure", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def generate_html_report(self, exec_dir: Path) -> Optional[Path]:
        """
        使用 allure CLI 生成 HTML 报告

        Args:
            exec_dir: allure 原始数据目录 (exec_N)

        Returns:
            HTML 报告目录路径，失败返回 None
        """
        import subprocess

        if not self.check_allure_cli():
            logger.warning("[AllureReporter] allure CLI 不可用，跳过 HTML 生成")
            return None

        html_dir = exec_dir / "html"
        html_dir.mkdir(parents=True, exist_ok=True)

        try:
            result = subprocess.run(
                [
                    "allure", "generate",
                    str(exec_dir),
                    "-o", str(html_dir),
                    "--clean",
                ],
                capture_output=True, text=True, timeout=60,
            )

            if result.returncode == 0:
                logger.info(f"[AllureReporter] HTML 报告已生成: {html_dir}")
                return html_dir
            else:
                logger.warning(f"[AllureReporter] allure generate 失败: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            logger.error("[AllureReporter] allure generate 超时")
            return None
        except Exception as e:
            logger.error(f"[AllureReporter] allure generate 异常: {e}")
            return None

    def zip_results(self, exec_dir: Path) -> Optional[Path]:
        """
        打包 allure 原始结果文件为 zip

        Args:
            exec_dir: allure 原始数据目录

        Returns:
            zip 文件路径，失败返回 None
        """
        if not exec_dir.exists():
            return None

        zip_path = exec_dir / f"allure_{exec_dir.name}.zip"

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(exec_dir):
                    for f in files:
                        if f.endswith('.zip'):
                            continue
                        file_path = Path(root) / f
                        arcname = file_path.relative_to(exec_dir)
                        zf.write(file_path, arcname)

            logger.info(f"[AllureReporter] 打包完成: {zip_path} ({zip_path.stat().st_size} bytes)")
            return zip_path

        except Exception as e:
            logger.error(f"[AllureReporter] 打包失败: {e}")
            return None

    def generate_json_summary(self, execution_results: list, execution_stats: dict) -> dict:
        """
        当 Allure CLI 不可用时，生成 JSON 格式的执行摘要

        Args:
            execution_results: 用例执行结果列表
            execution_stats: 统计信息

        Returns:
            JSON 摘要 dict
        """
        cases_summary = []
        for r in execution_results or []:
            cases_summary.append({
                "title": r.get("title", ""),
                "method": r.get("method", ""),
                "endpoint": r.get("api_endpoint", ""),
                "status": r.get("status", "unknown"),
                "duration": r.get("duration", 0),
                "error": r.get("error") or r.get("assertion_errors", []),
                "response_code": r.get("response_status_code"),
            })

        return {
            "generated_at": datetime.now().isoformat(),
            "stats": execution_stats,
            "cases": cases_summary,
            "failures_breakdown": {
                "assertion_failure": sum(
                    1 for r in (execution_results or [])
                    if r.get("status") == "failed" and r.get("assertion_errors")
                ),
                "network_error": sum(
                    1 for r in (execution_results or [])
                    if r.get("status") == "failed" and "请求异常" in str(r.get("error", ""))
                ),
                "variable_error": sum(
                    1 for r in (execution_results or [])
                    if r.get("status") == "failed" and "变量" in str(r.get("error", ""))
                ),
                "other": sum(
                    1 for r in (execution_results or [])
                    if r.get("status") == "failed"
                    and not r.get("assertion_errors")
                    and "请求异常" not in str(r.get("error", ""))
                    and "变量" not in str(r.get("error", ""))
                ),
            },
        }

    def build_report_bundle(
        self,
        execution_id: int,
        execution_results: list,
        execution_stats: dict,
    ) -> dict:
        """
        构建完整的报告包

        优先使用 Allure HTML，不可用时使用 JSON 摘要

        Returns:
            {
                "execution_id": int,
                "report_type": "allure_html" | "json_summary",
                "html_path": str or None,
                "zip_path": str or None,
                "json_summary": dict,
                "has_allure": bool,
            }
        """
        exec_dir = self.report_base / f"exec_{execution_id}"

        # 1. 尝试生成 Allure HTML
        html_path = self.generate_html_report(exec_dir) if exec_dir.exists() else None

        # 2. 打包 allure 数据
        zip_path = self.zip_results(exec_dir) if exec_dir.exists() else None

        # 3. 生成 JSON 摘要
        json_summary = self.generate_json_summary(execution_results, execution_stats)

        return {
            "execution_id": execution_id,
            "report_type": "allure_html" if html_path else "json_summary",
            "html_path": str(html_path) if html_path else None,
            "zip_path": str(zip_path) if zip_path else None,
            "json_summary": json_summary,
            "has_allure": html_path is not None,
        }

    def to_openai_function(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "execution_id": {
                            "type": "integer",
                            "description": "执行记录 ID",
                        },
                    },
                    "required": ["execution_id"],
                },
            },
        }

    def execute(self, action: str = None, **kwargs) -> dict:
        """MCP 统一入口"""
        if action == "report_generate":
            return self.build_report_bundle(
                execution_id=kwargs.get("execution_id"),
                execution_results=kwargs.get("execution_results", []),
                execution_stats=kwargs.get("execution_stats", {}),
            )
        return {"error": f"unknown action: {action}"}
