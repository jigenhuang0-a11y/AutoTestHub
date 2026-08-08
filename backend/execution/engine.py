import os
import sys
import json
import time
import subprocess
import re
import shutil
import logging
from pathlib import Path
from datetime import datetime
from django.conf import settings
from .models import TestExecution
from .sandbox_adapter import sandbox_run

logger = logging.getLogger(__name__)


def _copy_screenshot_to_media(src_path, execution_id):
    """将截图从临时目录复制到 MEDIA_ROOT，返回可访问的 URL"""
    if not src_path or not os.path.isfile(src_path):
        return None
    try:
        date_str = datetime.now().strftime('%Y%m%d')
        ts = datetime.now().strftime('%H%M%S')
        filename = f"exec_{execution_id}_{ts}_{os.path.basename(src_path)}"
        dest_dir = Path(settings.MEDIA_ROOT) / 'screenshots' / 'executions' / str(execution_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest_dir / filename)
        url = f"/media/screenshots/executions/{execution_id}/{filename}"
        return url
    except Exception as e:
        print(f"[WARN] 截图复制失败: {e}")
        return None


def _find_python_with_packages():
    """查找安装了必要包的Python解释器"""
    candidates = [sys.executable]

    if sys.platform == 'win32':
        base = os.path.dirname(sys.executable)
        for name in ['python.exe', 'python3.exe', 'python311.exe', 'python312.exe']:
            p = os.path.join(base, name)
            if os.path.exists(p) and p not in candidates:
                candidates.append(p)

    required = ['requests', 'pytest']
    for py in candidates:
        try:
            result = subprocess.run(
                [py, '-c', f"import {', '.join(required)}; print('OK')"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return py
        except Exception:
            continue

    return sys.executable


class TestExecutionEngine:
    """测试执行引擎"""

    def __init__(self, execution_id=None, global_variables=None, user_id: int = None):
        if execution_id is not None:
            self.execution = TestExecution.objects.get(id=execution_id)
            self.results_dir = settings.ALLURE_REPORT_DIR / f'exec_{execution_id}'
            self.results_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.execution = None
            self.results_dir = None
        self.python_executable = _find_python_with_packages()
        self.project_root = str(Path(__file__).resolve().parent.parent)
        self.case_details = {}  # {test_case_id: {title, method, api_endpoint, ...}}
        self.global_variables = global_variables or {}
        self.user_id = user_id

    def _execution_summary(self) -> dict:
        """返回当前执行记录的摘要字典（用于 MCP 返回）"""
        return {
            "execution_id": self.execution.id,
            "status": self.execution.status,
            "total_count": self.execution.total_count or 0,
            "passed_count": self.execution.passed_count or 0,
            "failed_count": self.execution.failed_count or 0,
            "skipped_count": self.execution.skipped_count or 0,
            "duration": self.execution.duration or 0,
        }

    def execute(self, action=None, **kwargs):
        """
        执行测试

        兼容两种调用方式：
        1. 原有方式：engine.execute()
        2. MCP 入口：engine.execute(action="execution_run", execution_id=...)
        """
        # MCP 入口：如果当前实例未初始化 execution，则从 kwargs 中初始化或新建
        if action == "execution_run" and self.execution is None:
            execution_id = kwargs.get("execution_id")
            test_case_ids = kwargs.get("test_case_ids") or []
            if not execution_id and test_case_ids:
                execution = TestExecution.objects.create(
                    name=f"AI执行-{int(time.time())}",
                    test_cases=[int(tcid) for tcid in test_case_ids],
                    status='pending',
                    total_count=len(test_case_ids),
                    trigger_type='manual_single',
                    environment='dev',
                )
                execution_id = execution.id
                logger.info(f"[TestExecutionEngine] 新建 TestExecution #{execution_id}, cases={len(test_case_ids)}")
            if not execution_id:
                return {"error": "execution_id or test_case_ids is required"}
            self.execution = TestExecution.objects.get(id=execution_id)
            self.results_dir = settings.ALLURE_REPORT_DIR / f'exec_{execution_id}'
            self.results_dir.mkdir(parents=True, exist_ok=True)

        from testcases.models import TestCase
        from web_testcases.models import WebTestCase

        start_time = time.time()
        test_case_ids = self.execution.test_cases or []
        web_test_case_ids = self.execution.web_test_cases or []
        perf_test_case_ids = self.execution.perf_test_cases or []
        
        # 确保 ID 为整数类型
        test_case_ids = [int(tcid) for tcid in test_case_ids]
        web_test_case_ids = [int(wid) for wid in web_test_case_ids]
        perf_test_case_ids = [int(pid) for pid in perf_test_case_ids]
        
        total_count = len(test_case_ids) + len(web_test_case_ids) + len(perf_test_case_ids)
        
        # 加载 API 用例（保持顺序）
        if hasattr(self.execution.test_suite, 'get_test_cases_queryset'):
            test_cases = list(self.execution.test_suite.get_test_cases_queryset())
        else:
            test_cases = list(TestCase.objects.filter(id__in=test_case_ids))

        # 加载 Web 用例（保持顺序）
        if hasattr(self.execution.test_suite, 'get_web_test_cases_queryset'):
            web_test_cases = list(self.execution.test_suite.get_web_test_cases_queryset())
        else:
            web_test_cases = list(WebTestCase.objects.filter(id__in=web_test_case_ids))

        # 保存 API 用例详情
        for tc in test_cases:
            self.case_details[tc.id] = {
                'id': tc.id,
                'title': tc.title,
                'method': tc.method,
                'api_endpoint': tc.api_endpoint,
                'headers': tc.headers,
                'request_body': tc.request_body,
                'expected_response': tc.expected_response,
                'assertion_rules': tc.assertion_rules or [],
                'extract_rules': tc.extract_rules or [],
                '__type': 'api',
            }

        # 保存 Web 用例详情
        for wtc in web_test_cases:
            self.case_details[wtc.id] = {
                'id': wtc.id,
                'title': wtc.title,
                'target_url': wtc.target_url,
                'engine': wtc.engine,
                'browser_type': wtc.browser_type,
                'priority': wtc.priority,
                'status': wtc.status,
                '__type': 'web',
            }

        self.execution.status = 'running'
        self.execution.total_count = total_count
        self.execution.execution_log += f"[INFO] 使用Python: {self.python_executable}\n"
        self.execution.save()

        if total_count == 0:
            self.execution.status = 'completed'
            self.execution.execution_results = []
            self.execution.duration = 0
            self.execution.save()
            return self._execution_summary()

        # 如果只有 Web 用例（没有 API 用例），通过 Playwright 引擎逐个执行
        if not test_cases and web_test_cases:
            from django.utils import timezone as django_tz
            from web_testcases.playwright_engine import run_web_test

            self.execution.execution_log += f"\n[INFO] 当前套件仅包含Web用例，启动Playwright引擎执行 ({len(web_test_cases)} 个用例)\n"
            web_results = []
            for wtc in web_test_cases:
                self.execution.execution_log += f"\n[INFO] 开始执行Web用例: [{wtc.title}] (ID: {wtc.id})\n"
                try:
                    # 获取当前请求用户（如果有）
                    user_id = getattr(self.execution, 'executed_by_id', None)
                    web_result = run_web_test(wtc, user_id=user_id)

                    web_status = web_result.get('status', 'error')
                    if web_status == 'passed':
                        final_status = 'passed'
                    elif web_status == 'failed':
                        final_status = 'failed'
                    else:
                        final_status = 'error'

                    # 将截图从临时目录复制到 MEDIA_ROOT，返回可访问 URL
                    _src_ss = web_result.get('screenshot_path')
                    _ss_url = _copy_screenshot_to_media(_src_ss, self.execution.id)

                    web_results.append({
                        'case_id': wtc.id,
                        'title': wtc.title,
                        'type': 'web',
                        'target_url': wtc.target_url,
                        'engine': wtc.engine,
                        'status': final_status,
                        'error': web_result.get('error'),
                        'duration': web_result.get('duration', 0),
                        'screenshot_path': _ss_url,
                        'steps_results': web_result.get('steps_results', []),
                        'assertion_errors': web_result.get('assertion_errors', []),
                    })
                    self.execution.execution_log += f"[INFO] Web用例 [{wtc.title}] 执行结果: {final_status}, 耗时: {web_result.get('duration', 0)}s\n"
                except Exception as e:
                    web_results.append({
                        'case_id': wtc.id,
                        'title': wtc.title,
                        'type': 'web',
                        'target_url': wtc.target_url,
                        'engine': wtc.engine,
                        'status': 'error',
                        'error': str(e),
                        'duration': 0,
                    })
                    self.execution.execution_log += f"[ERROR] Web用例 [{wtc.title}] 执行异常: {e}\n"

            # 统计结果
            passed = sum(1 for r in web_results if r.get('status') == 'passed')
            failed = sum(1 for r in web_results if r.get('status') in ('failed', 'error'))
            skipped = 0

            self.execution.status = 'completed' if failed == 0 else 'failed'
            self.execution.execution_results = web_results
            self.execution.total_count = len(web_test_cases)
            self.execution.passed_count = passed
            self.execution.failed_count = failed
            self.execution.skipped_count = skipped
            self.execution.duration = int(time.time() - start_time)
            self.execution.completed_at = django_tz.now()
            self.execution.save()
            return self._execution_summary()

        # 生成pytest测试文件（处理 API 用例）
        test_file = self._generate_test_file(test_cases)

        try:
            # 先尝试带allure的运行
            result = self._run_pytest(test_file, use_allure=True)

            # 检查沙箱超时
            if getattr(result, 'killed_by_timeout', False):
                self.execution.execution_log += "\n[错误] 测试执行超时（600秒）\n"
                raise TimeoutError("沙箱执行超时")

            # 如果allure不可用，回退到无allure模式
            if result.returncode != 0 and ('unrecognized arguments' in result.stderr or '--alluredir' in result.stderr):
                self.execution.execution_log += "\n[INFO] allure插件不可用，回退到普通pytest模式\n"
                result = self._run_pytest(test_file, use_allure=False)
                if getattr(result, 'killed_by_timeout', False):
                    self.execution.execution_log += "\n[错误] 测试执行超时（600秒）\n"
                    raise TimeoutError("沙箱执行超时")

            # 解析结果（包含每个用例的详情）
            # 先解析 API 用例结果
            self._parse_results(result, test_cases, web_test_cases)

            # 如果有 Web 用例，通过 Playwright 引擎逐个执行
            web_exec_results = []
            if web_test_cases:
                from web_testcases.playwright_engine import run_web_test

                self.execution.execution_log += f"\n[INFO] 混合套件检测到 {len(web_test_cases)} 个Web用例，启动Playwright引擎\n"
                user_id = getattr(self.execution, 'executed_by_id', None)

                for wtc in web_test_cases:
                    self.execution.execution_log += f"[INFO] 开始执行Web用例: [{wtc.title}] (ID: {wtc.id})\n"
                    try:
                        web_result = run_web_test(wtc, user_id=user_id)

                        web_status = web_result.get('status', 'error')
                        if web_status == 'passed':
                            final_status = 'passed'
                        elif web_status == 'failed':
                            final_status = 'failed'
                        else:
                            final_status = 'error'

                        # 将截图从临时目录复制到 MEDIA_ROOT，返回可访问 URL
                        _src_ss = web_result.get('screenshot_path')
                        _ss_url = _copy_screenshot_to_media(_src_ss, self.execution.id)

                        web_exec_results.append({
                            'case_id': wtc.id,
                            'title': wtc.title,
                            'type': 'web',
                            'target_url': wtc.target_url,
                            'engine': wtc.engine,
                            'status': final_status,
                            'error': web_result.get('error'),
                            'duration': web_result.get('duration', 0),
                            'screenshot_path': _ss_url,
                            'steps_results': web_result.get('steps_results', []),
                            'assertion_errors': web_result.get('assertion_errors', []),
                        })
                        self.execution.execution_log += f"[INFO] Web用例 [{wtc.title}] 执行结果: {final_status}, 耗时: {web_result.get('duration', 0)}s\n"
                    except Exception as e:
                        web_exec_results.append({
                            'case_id': wtc.id,
                            'title': wtc.title,
                            'type': 'web',
                            'target_url': wtc.target_url,
                            'engine': wtc.engine,
                            'status': 'error',
                            'error': str(e),
                            'duration': 0,
                        })
                        self.execution.execution_log += f"[ERROR] Web用例 [{wtc.title}] 执行异常: {e}\n"

                # 将 Web 真实结果合并到 execution_results（替换之前的 skipped 占位）
                existing_results = list(self.execution.execution_results or [])
                # 移除之前 _parse_results 追加的 Web skipped 结果
                filtered_api_results = [r for r in existing_results if r.get('type') != 'web']
                all_results = filtered_api_results + web_exec_results
                self.execution.execution_results = all_results

                # 重新统计（包含 Web 结果）
                passed = sum(1 for r in all_results if r.get('status') == 'passed')
                failed = sum(1 for r in all_results if r.get('status') in ('failed', 'error'))
                skipped = sum(1 for r in all_results if r.get('status') == 'skipped')
                self.execution.passed_count = passed
                self.execution.failed_count = failed
                self.execution.skipped_count = skipped

            # ===== 性能测试用例执行 =====
            perf_results = []
            if perf_test_case_ids:
                from performance.models import PerfTestCase, PerfExecution
                from performance.engine import PerfTestEngine
                from django.utils import timezone as django_tz_perf

                # 加载性能用例（保持顺序）
                if hasattr(self.execution.test_suite, 'get_perf_test_cases_queryset'):
                    perf_test_cases = list(self.execution.test_suite.get_perf_test_cases_queryset())
                else:
                    perf_test_cases = list(PerfTestCase.objects.filter(id__in=perf_test_case_ids))

                # 读取用户自定义的性能执行参数
                perf_config = {}
                if self.execution.test_suite and hasattr(self.execution.test_suite, 'perf_config'):
                    perf_config = self.execution.test_suite.perf_config or {}

                self.execution.execution_log += f"\n[INFO] 开始执行 {len(perf_test_cases)} 个性能测试用例\n"

                for ptc in perf_test_cases:
                    self.execution.execution_log += f"\n[INFO] 执行性能用例: [{ptc.name}] (ID: {ptc.id})\n"
                    perf_start = time.time()
                    try:
                        # 获取用户自定义参数，覆盖默认值
                        ptc_config = perf_config.get(str(ptc.id), {})
                        users = ptc_config.get('users', ptc.users)
                        duration = ptc_config.get('duration', ptc.duration)

                        # 创建 PerfExecution 记录（关联到 TestSuite 执行）
                        perf_exec = PerfExecution.objects.create(
                            test_case=ptc,
                            users=users,
                            duration=duration,
                            test_type=ptc.test_type,
                            status='running',
                            started_by_id=getattr(self.execution, 'executed_by_id', None),
                            suite_execution=self.execution,  # 关联套件执行
                        )
                        self.execution.execution_log += f"  并发用户: {users}, 持续时间: {duration}s, 类型: {ptc.test_type}\n"

                        # 同步执行（在线程内直接跑，等待完成）
                        engine = PerfTestEngine(perf_exec)
                        engine._run()

                        # 刷新执行记录获取最新状态
                        perf_exec.refresh_from_db()
                        perf_duration = round(time.time() - perf_start, 1)

                        perf_results.append({
                            'case_id': ptc.id,
                            'title': ptc.name,
                            'type': 'perf',
                            'test_type': ptc.test_type,
                            'target_url': ptc.target_url,
                            'status': perf_exec.status,
                            'users': users,
                            'duration': perf_duration,
                            'config_duration': duration,
                            'total_requests': perf_exec.total_requests,
                            'requests_per_second': perf_exec.requests_per_second,
                            'avg_response_time': perf_exec.avg_response_time,
                            'p95_response_time': perf_exec.p95_response_time,
                            'failures': perf_exec.failures,
                            'thresholds_passed': perf_exec.thresholds_passed,
                            'threshold_errors': perf_exec.threshold_errors,
                            'error': perf_exec.execution_log[-500:] if perf_exec.status == 'failed' else None,
                            'perf_execution_id': perf_exec.id,
                        })
                        self.execution.execution_log += (
                            f"[INFO] 性能用例 [{ptc.name}] 完成: {perf_exec.status}, "
                            f"请求数={perf_exec.total_requests}, "
                            f"RPS={perf_exec.requests_per_second}, "
                            f"耗时={perf_duration}s\n"
                        )

                    except Exception as e:
                        perf_results.append({
                            'case_id': ptc.id,
                            'title': ptc.name,
                            'type': 'perf',
                            'test_type': ptc.test_type,
                            'target_url': ptc.target_url,
                            'status': 'error',
                            'error': str(e),
                            'duration': round(time.time() - perf_start, 1),
                        })
                        self.execution.execution_log += f"[ERROR] 性能用例 [{ptc.name}] 执行异常: {e}\n"

            # 将性能结果合并到执行结果中
            existing_results = list(self.execution.execution_results or [])
            all_results = existing_results + perf_results
            self.execution.execution_results = all_results

            # 更新计数（total_count 已在开头正确计算，此处不再重复累加）
            passed = sum(1 for r in all_results if r.get('status') in ('passed', 'completed'))
            failed = sum(1 for r in all_results if r.get('status') in ('failed', 'error'))
            skipped = sum(1 for r in all_results if r.get('status') == 'skipped')
            self.execution.passed_count = passed
            self.execution.failed_count = failed
            self.execution.skipped_count = skipped

            # 计算最终状态
            total = self.execution.total_count
            passed = self.execution.passed_count
            failed = self.execution.failed_count
            skipped = self.execution.skipped_count

            if failed == 0 and skipped == total:
                # 全部跳过（只有Web用例时）
                self.execution.status = 'completed'
            elif failed == 0 and skipped == 0:
                self.execution.status = 'completed'
            elif passed == 0 and failed > 0:
                self.execution.status = 'failed'
            else:
                self.execution.status = 'partial'

            self.execution.allure_report_path = str(self.results_dir)

        except subprocess.TimeoutExpired:
            # 兼容回退模式下裸 subprocess 的超时
            self.execution.status = 'failed'
            self.execution.execution_log += "\n[错误] 测试执行超时（超过300秒）"
        except TimeoutError:
            self.execution.status = 'failed'
        except Exception as e:
            self.execution.status = 'failed'
            self.execution.execution_log += f"\n[错误] {str(e)}"

        finally:
            duration = int(time.time() - start_time)
            self.execution.duration = duration
            from django.utils import timezone as django_tz
            self.execution.completed_at = self.execution.completed_at or django_tz.now()
            self.execution.save()
            # 清理临时文件
            if os.path.exists(test_file):
                try:
                    os.remove(test_file)
                except Exception:
                    pass

        return self._execution_summary()

    def _generate_test_file(self, test_cases):
        """生成pytest测试文件 - 支持变量提取、替换和断言规则"""
        # 每个用例的详情写入JSON文件
        case_info_file = self.results_dir / 'case_info.json'
        case_info = {}
        for tc in test_cases:
            case_info[tc.id] = {
                'title': tc.title,
                'method': tc.method,
                'api_endpoint': tc.api_endpoint,
            }
        with open(case_info_file, 'w', encoding='utf-8') as f:
            json.dump(case_info, f, ensure_ascii=False)

        # 断言规则
        assertion_rules_file = self.results_dir / 'assertion_rules.json'
        assertion_rules_data = {}
        for tc in test_cases:
            assertion_rules_data[tc.id] = tc.assertion_rules or []
        with open(assertion_rules_file, 'w', encoding='utf-8') as f:
            json.dump(assertion_rules_data, f, ensure_ascii=False)

        # 提取规则
        extract_rules_file = self.results_dir / 'extract_rules.json'
        extract_rules_data = {}
        for tc in test_cases:
            extract_rules_data[tc.id] = tc.extract_rules or []
        with open(extract_rules_file, 'w', encoding='utf-8') as f:
            json.dump(extract_rules_data, f, ensure_ascii=False)

        # 全局变量
        global_vars_file = self.results_dir / 'global_vars.json'
        with open(global_vars_file, 'w', encoding='utf-8') as f:
            json.dump(self.global_variables, f, ensure_ascii=False)

        # 生成结果写入文件
        results_file = self.results_dir / 'case_results.json'
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump({}, f)

        # 构建测试代码
        test_code_parts = [
            'import requests',
            'import json',
            'import time',
            'import os',
            'import re',
            'from pathlib import Path',
            '',
            "RESULTS_FILE = Path(__file__).parent / 'case_results.json'",
            "ASSERTION_RULES_FILE = Path(__file__).parent / 'assertion_rules.json'",
            "EXTRACT_RULES_FILE = Path(__file__).parent / 'extract_rules.json'",
            "GLOBAL_VARS_FILE = Path(__file__).parent / 'global_vars.json'",
            '',
            '# 安全导入 allure（可选）',
            'try:',
            '    import allure',
            '    HAS_ALLURE = True',
            'except ImportError:',
            '    HAS_ALLURE = False',
            '',
            'def safe_allure_attach(content, name=""):',
            '    if HAS_ALLURE:',
            '        try:',
            '            allure.attach(content, name=name, attachment_type=allure.attachment_type.JSON)',
            '        except Exception:',
            '            pass',
            '',
            'def _save_result(case_id, result):',
            '    """保存单个用例执行结果"""',
            '    try:',
            '        if RESULTS_FILE.exists():',
            "            with open(RESULTS_FILE, 'r', encoding='utf-8') as f:",
            '                data = json.load(f)',
            '        else:',
            '            data = {}',
            '        data[str(case_id)] = result',
            "        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:",
            '            json.dump(data, f, ensure_ascii=False, indent=2)',
            '    except Exception:',
            '        pass',
            '',
            'def _replace_variables(text, variables):',
            '    """替换文本中的 {{var}} 或 ${var} 变量"""',
            '    if not text or not variables:',
            '        return text',
            '    if isinstance(text, dict):',
            '        return {k: _replace_variables(v, variables) for k, v in text.items()}',
            '    if isinstance(text, list):',
            '        return [_replace_variables(v, variables) for v in text]',
            '    if not isinstance(text, str):',
            '        return text',
            '    # 先替换 ${var} 语法',
            "    pattern1 = re.compile(r'\$\{([^}]+)\}')",
            '    def replacer1(match):',
            '        var_name = match.group(1).strip()',
            '        return str(variables.get(var_name, match.group(0)))',
            '    text = pattern1.sub(replacer1, text)',
            '    # 再替换 {{var}} 语法',
            "    pattern2 = re.compile(r'\{\{([^}]+)\}\}')",
            '    def replacer2(match):',
            '        var_name = match.group(1).strip()',
            '        return str(variables.get(var_name, match.group(0)))',
            '    text = pattern2.sub(replacer2, text)',
            '    return text',
            '',
            'def _extract_by_json_path(data, path):',
            '    """按点号路径从JSON中提取值，支持 field[idx] 数组索引格式"""',
            '    if not path or not isinstance(data, dict):',
            '        return None',
            '    # 去掉开头的$符号(JSONPath根节点标识)',
            '    if path.startswith(\'$\'):',
            '        path = path[1:]',
            '    # 去掉开头的.符号',
            '    if path.startswith(\'.\'):',
            '        path = path[1:]',
            '    # 按 . 和 [数字] 分割路径',
            '    import re as _re_path',
            "    tokens = _re_path.split(r'(\\.|\\[\\d+\\])', path)",
            '    current = data',
            '    for token in tokens:',
            '        if not token or token == \'.\':',
            '            continue',
            "        if token.startswith('[') and token.endswith(']'):",
            '            idx_str = token[1:-1]',
            '            if idx_str.isdigit():',
            '                idx = int(idx_str)',
            '                if isinstance(current, list) and 0 <= idx < len(current):',
            '                    current = current[idx]',
            '                else:',
            '                    return None',
            '            else:',
            '                return None',
            '        elif isinstance(current, dict) and token in current:',
            '            current = current[token]',
            '        elif isinstance(current, list) and token.isdigit():',
            '            idx = int(token)',
            '            if 0 <= idx < len(current):',
            '                current = current[idx]',
            '            else:',
            '                return None',
            '        else:',
            '            return None',
            '    return current',
            '',
            'def _extract_by_regex(text, pattern):',
            '    """按正则表达式提取值"""',
            '    if not text or not pattern:',
            '        return None',
            '    try:',
            '        match = re.search(pattern, text)',
            '        if match:',
            '            return match.group(1) if match.groups() else match.group(0)',
            '    except Exception:',
            '        pass',
            '    return None',
            '',
            'def _extract_variables(response, rules):',
            '    """执行提取规则，返回带类型信息的变量"""',
            '    extracted = {}',
            '    for rule in rules:',
            '        extract_type = rule.get(\'extract_type\', \'json_path\')',
            '        # 兼容 field_path 和 var_value 两种字段名',
            '        field_path = rule.get(\'field_path\', \'\') or rule.get(\'var_value\', \'\')',
            '        var_name = rule.get(\'var_name\', \'\')',
            '        var_type = rule.get(\'var_type\', \'suite\')  # 新增：获取变量类型，默认 suite',
            '        if not var_name:',
            '            continue',
            '        try:',
            '            if extract_type == \'json_path\':',
            '                data = {}',
            '                if hasattr(response, \'json\'):',
            '                    try:',
            '                        data = response.json()',
            '                    except Exception:',
            '                        data = {}',
            '                elif isinstance(response, dict):',
            '                    data = response',
            '                value = _extract_by_json_path(data, field_path)',
            '                if value is not None:',
            '                    extracted[var_name] = {\'value\': value, \'type\': var_type}',
            '            elif extract_type == \'regex\':',
            '                text = response.text if hasattr(response, \'text\') else str(response)',
            '                value = _extract_by_regex(text, field_path)',
            '                if value is not None:',
            '                    extracted[var_name] = {\'value\': value, \'type\': var_type}',
            '            elif extract_type == \'header\':',
            '                headers = response.headers if hasattr(response, \'headers\') else {}',
            '                value = headers.get(field_path)',
            '                if value is not None:',
            '                    extracted[var_name] = {\'value\': value, \'type\': var_type}',
            '        except Exception:',
            '            pass',
            '    return extracted',
            '',
            'def _run_assertions(response_data, rules, variables):',
            '    """执行断言规则"""',
            '    errors = []',
            '    for rule in rules:',
            "        field = rule.get('field', '')",
            "        operator = rule.get('operator', '==')",
            "        expected_value = rule.get('value', '')",
            '        if not field:',
            '            continue',
            '        # 替换预期值中的变量',
            '        expected_value = _replace_variables(expected_value, variables)',
            '        actual_value = _extract_by_json_path(response_data, field)',
            "        if operator == 'exists':",
            '            if actual_value is None:',
            '                errors.append(f"字段不存在: {field}")',
            '            continue',
            "        if operator == 'is_empty':",
            "            if actual_value is not None and actual_value != '' and actual_value != [] and actual_value != {}:",
            '                errors.append(f"字段不为空: {field}")',
            '            continue',
            '        # 尝试类型转换后比较',
            '        try:',
            "            if operator == '==':",
            '                if str(actual_value) != str(expected_value):',
            '                    errors.append(f"{field} 期望等于 {expected_value}, 实际 {actual_value}")',
            "            elif operator == '!=':",
            '                if str(actual_value) == str(expected_value):',
            '                    errors.append(f"{field} 期望不等于 {expected_value}, 实际 {actual_value}")',
            "            elif operator == 'contains':",
            '                if str(expected_value) not in str(actual_value):',
            '                    errors.append(f"{field} 期望包含 {expected_value}, 实际 {actual_value}")',
            "            elif operator in ('>', '<', '>=', '<='):",
            '                # 尝试数字比较',
            '                try:',
            '                    a = float(actual_value) if actual_value is not None else 0',
            '                    e = float(expected_value) if expected_value != \'\' else 0',
            "                    if operator == '>' and not (a > e):",
            '                        errors.append(f"{field} 期望 > {expected_value}, 实际 {actual_value}")',
            "                    elif operator == '<' and not (a < e):",
            '                        errors.append(f"{field} 期望 < {expected_value}, 实际 {actual_value}")',
            "                    elif operator == '>=' and not (a >= e):",
            '                        errors.append(f"{field} 期望 >= {expected_value}, 实际 {actual_value}")',
            "                    elif operator == '<=' and not (a <= e):",
            '                        errors.append(f"{field} 期望 <= {expected_value}, 实际 {actual_value}")',
            '                except (ValueError, TypeError):',
            '                    errors.append(f"{field} 无法进行数字比较: 实际 {actual_value}, 期望 {expected_value}")',
            '        except Exception as e:',
            '            errors.append(f"{field} 断言异常: {e}")',
            '    return errors',
            '',
        ]

        test_code = '\n'.join(test_code_parts)

        # 生成主测试函数，按顺序执行所有用例
        main_function_code = '''
def test_suite_execution():
    """按顺序执行套件中的所有测试用例"""
    test_cases_data = [
'''
        
        for idx, tc in enumerate(test_cases):
            # Handle headers and request_body
            headers = tc.headers
            if isinstance(headers, str):
                try:
                    headers = json.loads(headers)
                except:
                    headers = {}
            elif not isinstance(headers, dict):
                headers = {}

            request_body = tc.request_body
            if isinstance(request_body, str):
                try:
                    request_body = json.loads(request_body)
                except:
                    request_body = {}
            elif not isinstance(request_body, dict):
                request_body = {}

            expected_response = tc.expected_response
            if isinstance(expected_response, str):
                try:
                    expected_response = json.loads(expected_response)
                except:
                    expected_response = {}
            elif not isinstance(expected_response, dict):
                expected_response = {}

            # Escape title for safe use in Python string
            title_safe = tc.title.replace('\\', '\\\\').replace(
                '"', '\\"').replace('\n', ' ').replace('\r', '')
            # Escape method and api_endpoint for safe use in Python string
            method_safe = tc.method.replace('\\', '\\\\').replace('"', '\\"')
            api_endpoint_safe = tc.api_endpoint.replace('\\', '\\\\').replace('"', '\\"')
            headers_json = json.dumps(headers, ensure_ascii=False).replace(
                'true', 'True').replace('false', 'False').replace('null', 'None')
            body_json = json.dumps(request_body, ensure_ascii=False).replace(
                'true', 'True').replace('false', 'False').replace('null', 'None')
            expected_json = json.dumps(expected_response, ensure_ascii=False).replace(
                'true', 'True').replace('false', 'False').replace('null', 'None')
            has_body = 'True' if request_body else 'False'

            # 添加用例数据到列表
            main_function_code += f'''
        {{
            'index': {idx},
            'case_id': {tc.id},
            'title': "{title_safe}",
            'method': "{method_safe}",
            'api_endpoint': "{api_endpoint_safe}",
            'headers_json': {headers_json},
            'body_json': {body_json},
            'has_body': {has_body},
            'expected_json': {expected_json},
        }},
'''

        main_function_code += '''
    ]
    
    # 按顺序执行每个用例
    for tc_data in test_cases_data:
        case_id = tc_data['case_id']
        title = tc_data['title']
        method = tc_data['method']
        api_endpoint = tc_data['api_endpoint']
        headers = tc_data['headers_json']
        body = tc_data['body_json']
        has_body = tc_data['has_body']
        expected_json = tc_data['expected_json']
        
        start = time.time()
        result = {
            'case_id': case_id,
            'title': title,
            'method': method,
            'api_endpoint': api_endpoint,
            'request_url': api_endpoint,
            'request_method': method,
            'request_headers': headers,
            'request_body': body,
            'status': 'skipped',
            'response_status_code': None,
            'response_body': None,
            'error': None,
            'duration': 0,
            'extracted_vars': {},
            'assertion_errors': [],
        }

        # 加载全局变量和规则
        global_vars = {}
        extract_rules = []
        assertion_rules = []
        try:
            if GLOBAL_VARS_FILE.exists():
                with open(GLOBAL_VARS_FILE, 'r', encoding='utf-8') as f:
                    global_vars = json.load(f)
        except Exception:
            pass
        try:
            if EXTRACT_RULES_FILE.exists():
                with open(EXTRACT_RULES_FILE, 'r', encoding='utf-8') as f:
                    extract_rules = json.load(f).get(str(case_id), [])
        except Exception:
            pass
        try:
            if ASSERTION_RULES_FILE.exists():
                with open(ASSERTION_RULES_FILE, 'r', encoding='utf-8') as f:
                    assertion_rules = json.load(f).get(str(case_id), [])
        except Exception:
            pass

        # 变量池：全局变量为基础
        variables = dict(global_vars)
        unresolvable_vars = []

        # 替换请求配置中的变量
        try:
            # 调试日志
            import sys
            print(f"[DEBUG] 替换变量前 - api_endpoint: {api_endpoint}", file=sys.stderr)
            print(f"[DEBUG] 替换变量前 - variables: {variables}", file=sys.stderr)
            
            request_url = _replace_variables(api_endpoint, variables)

            # 对headers进行变量替换（headers可能是字符串或字典）
            if isinstance(headers, str):
                try:
                    headers_dict = json.loads(headers)
                    headers_dict = _replace_variables(headers_dict, variables)
                    request_headers = json.dumps(headers_dict)
                except:
                    request_headers = _replace_variables(headers, variables)
            elif isinstance(headers, dict):
                request_headers = _replace_variables(headers, variables)
            else:
                request_headers = headers
            
            request_body = _replace_variables(body, variables) if has_body else None
            
            print(f"[DEBUG] 替换变量后 - request_url: {request_url}", file=sys.stderr)
        except Exception as e:
            result['status'] = 'failed'
            result['error'] = "变量替换异常: " + str(e)
            result['duration'] = round(time.time() - start, 3)
            _save_result(case_id, result)
            continue

        try:
            response = requests.request(
                method=method,
                url=request_url,
                headers=request_headers,
                json=request_body,
                timeout=(10, 30),  # (connect_timeout, read_timeout): 连接10s, 读取30s
                allow_redirects=True
            )

            result['response_status_code'] = response.status_code
            try:
                result['response_body'] = response.json()
            except (ValueError, TypeError):
                result['response_body'] = response.text[:2000]

            # 执行变量提取（提取规则在断言之前执行）
            extracted_vars = _extract_variables(response, extract_rules)
            result['extracted_vars'] = extracted_vars
            
            # 根据变量类型分别处理
            for var_name, var_data in extracted_vars.items():
                var_value = var_data.get('value')
                var_type = var_data.get('type', 'suite')
                
                # 兼容旧版 'global' 和新版 'suite'
                if var_type == 'suite' or var_type == 'global':
                    # 套件变量：保存到全局变量池，供后续步骤使用
                    variables[var_name] = var_value
                elif var_type == 'context' or var_type == 'temporary' or var_type == 'step':
                    # 临时变量/上下文变量/步骤变量：也保存到变量池，供后续步骤使用
                    variables[var_name] = var_value

            # 保存更新后的套件变量到文件，供后续测试用例使用
            try:
                with open(GLOBAL_VARS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(variables, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

            # 检查未解析的变量
            all_request_text = str(request_url) + str(request_headers) + str(request_body)
            import re as _re
            for match in _re.finditer(r'\$\{([^}]+)\}', all_request_text):
                var_name = match.group(1).strip()
                if var_name not in variables:
                    unresolvable_vars.append(var_name)

            if unresolvable_vars:
                result['warnings'] = ["以下变量未找到对应值: " + ", ".join(unresolvable_vars)]

            # 执行断言规则
            response_data = result['response_body']
            if isinstance(response_data, str):
                try:
                    response_data = json.loads(response_data)
                except:
                    response_data = {'raw': response_data}

            # 自定义断言规则
            assertion_errors = _run_assertions(response_data, assertion_rules, variables)
            if assertion_errors:
                result['status'] = 'failed'
                result['assertion_errors'] = assertion_errors
                result['error'] = "; ".join(assertion_errors)
                result['duration'] = round(time.time() - start, 3)
                _save_result(case_id, result)
                continue

            # 检查期望响应
            if expected_json and expected_json != {}:
                try:
                    if isinstance(response_data, dict):
                        for key, value in expected_json.items():
                            if key not in response_data:
                                result['status'] = 'failed'
                                result['error'] = "响应缺少字段: " + str(key)
                                result['duration'] = round(time.time() - start, 3)
                                _save_result(case_id, result)
                                continue
                except (ValueError, KeyError, TypeError):
                    pass

            result['status'] = 'passed'

        except requests.exceptions.RequestException as e:
            result['status'] = 'failed'
            result['error'] = "请求异常: " + str(e)
        except AssertionError:
            pass
        except Exception as e:
            result['status'] = 'failed'
            result['error'] = "执行异常: " + str(e)

        result['duration'] = round(time.time() - start, 3)
        _save_result(case_id, result)

        try:
            if result.get('response_body'):
                content = json.dumps(result['response_body'], indent=2, ensure_ascii=False) if isinstance(
                    result['response_body'], dict) else str(result['response_body'])[:2000]
                safe_allure_attach(content, name="响应内容")
        except Exception:
            pass

'''

        test_code += main_function_code

        test_file = self.results_dir / 'test_generated.py'
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_code)
        
        # 调试：将生成的代码也写入一个固定位置，方便查看
        import shutil
        debug_file = Path(__file__).resolve().parent.parent / 'last_generated_test.py'
        try:
            shutil.copy2(test_file, debug_file)
            self.execution.execution_log += f"\n[调试] 测试代码已复制到: {debug_file}"
        except Exception as e:
            self.execution.execution_log += f"\n[调试] 复制失败: {e}"

        # 调试：打印生成的测试文件路径
        self.execution.execution_log += f"\n[调试] 生成的测试文件: {test_file}"

        # 尝试读取并验证生成的代码
        try:
            compile(test_code, str(test_file), 'exec')
            self.execution.execution_log += "\n[调试] 测试文件语法检查通过"
        except SyntaxError as e:
            self.execution.execution_log += f"\n[错误] 测试文件语法错误: {e}"

        return str(test_file)

    def _run_pytest(self, test_file, use_allure=True):
        """运行pytest（通过沙箱执行，不可用时回退裸 subprocess）"""
        cmd = [
            self.python_executable, '-m', 'pytest',
            test_file,
            '-v',
            '--tb=short'
        ]

        if use_allure:
            cmd.insert(4, f'--alluredir={self.results_dir}')

        env = os.environ.copy()
        if 'PYTHONPATH' in env:
            env['PYTHONPATH'] = f"{self.project_root}{os.pathsep}{env['PYTHONPATH']}"
        else:
            env['PYTHONPATH'] = self.project_root

        result = sandbox_run(
            cmd,
            timeout=600,
            max_memory_mb=1024,
            cwd=self.project_root,
            env=env,
        )

        self.execution.execution_log += result.stdout + result.stderr
        return result

    def _parse_results(self, result, test_cases, web_test_cases=None, web_execution_results=None):
        """解析测试结果 - 从 JSON 文件读取每个用例详情
        web_execution_results: Web用例的真实执行结果列表（如果已执行），为 None 时标记为 skipped
        """
        results_file = self.results_dir / 'case_results.json'
        case_results = []

        if results_file.exists():
            try:
                with open(results_file, 'r', encoding='utf-8') as f:
                    case_results_data = json.load(f)

                for case_id_str, case_result in case_results_data.items():
                    case_results.append(case_result)
            except Exception:
                pass

        # 如果没有JSON结果（比如 pytest 根本没跑起来），从 pytest 输出解析
        if not case_results:
            output = result.stdout + result.stderr
            for tc in test_cases:
                case_results.append({
                    'case_id': tc.id,
                    'title': tc.title,
                    'method': tc.method,
                    'api_endpoint': tc.api_endpoint,
                    'status': 'failed',
                    'error': '未生成执行结果',
                    'duration': 0,
                })

        # 追加 Web 用例结果（优先使用真实执行结果，否则标记为 skipped）
        if web_test_cases:
            if web_execution_results:
                # 使用真实的 Web 执行结果
                case_results.extend(web_execution_results)
            else:
                # 无真实执行结果，标记为 skipped
                for wtc in web_test_cases:
                    case_results.append({
                        'case_id': wtc.id,
                        'title': wtc.title,
                        'type': 'web',
                        'target_url': wtc.target_url,
                        'engine': wtc.engine,
                        'status': 'skipped',
                        'error': 'Web自动化用例暂不支持在套件中批量执行，请单独运行',
                        'duration': 0,
                    })

        # 保存用例详情
        self.execution.execution_results = case_results

        # 统计
        passed = sum(1 for r in case_results if r.get('status') == 'passed')
        failed = sum(1 for r in case_results if r.get('status') == 'failed')
        skipped = sum(1 for r in case_results if r.get('status') == 'skipped')

        self.execution.passed_count = passed
        self.execution.failed_count = failed
        self.execution.skipped_count = skipped

    @staticmethod
    def _json_to_python_literals(json_str):
        """将 JSON 字面量转换为 Python 字面量
        json.dumps 输出 true/false/null，需要转为 Python 的 True/False/None
        """
        replacements = [
            (': true', ': True'),
            (': false', ': False'),
            (': null', ': None'),
            (', true,', ', True,'),
            (', false,', ', False,'),
            (', null,', ', None,'),
            ('true,', 'True,'),
            ('false,', 'False,'),
            ('null,', 'None,'),
            ('true}', 'True}'),
            ('false}', 'False}'),
            ('null}', 'None}'),
            ('true]', 'True]'),
            ('false]', 'False]'),
            ('null]', 'None]'),
            ('true)', 'True)'),
            ('false)', 'False)'),
            ('null)', 'None)'),
        ]
        result = json_str
        for old, new in replacements:
            result = result.replace(old, new)
        return result

    @staticmethod
    def _sanitize_name(name):
        """清理名称用于函数名"""
        name = re.sub(r'[^\w]', '', name)
        return name[:50] or 'testcase'
