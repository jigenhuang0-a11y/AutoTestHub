import requests
import json
import time
import os
import re
from pathlib import Path

RESULTS_FILE = Path(__file__).parent / 'case_results.json'
ASSERTION_RULES_FILE = Path(__file__).parent / 'assertion_rules.json'
EXTRACT_RULES_FILE = Path(__file__).parent / 'extract_rules.json'
GLOBAL_VARS_FILE = Path(__file__).parent / 'global_vars.json'

# 安全导入 allure（可选）
try:
    import allure
    HAS_ALLURE = True
except ImportError:
    HAS_ALLURE = False

def safe_allure_attach(content, name=""):
    if HAS_ALLURE:
        try:
            allure.attach(content, name=name, attachment_type=allure.attachment_type.JSON)
        except Exception:
            pass

def _save_result(case_id, result):
    """保存单个用例执行结果"""
    try:
        if RESULTS_FILE.exists():
            with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {}
        data[str(case_id)] = result
        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _replace_variables(text, variables):
    """替换文本中的 {{var}} 或 ${var} 变量"""
    if not text or not variables:
        return text
    if isinstance(text, dict):
        return {k: _replace_variables(v, variables) for k, v in text.items()}
    if isinstance(text, list):
        return [_replace_variables(v, variables) for v in text]
    if not isinstance(text, str):
        return text
    # 先替换 ${var} 语法
    pattern1 = re.compile(r'\$\{([^}]+)\}')
    def replacer1(match):
        var_name = match.group(1).strip()
        return str(variables.get(var_name, match.group(0)))
    text = pattern1.sub(replacer1, text)
    # 再替换 {{var}} 语法
    pattern2 = re.compile(r'\{\{([^}]+)\}\}')
    def replacer2(match):
        var_name = match.group(1).strip()
        return str(variables.get(var_name, match.group(0)))
    text = pattern2.sub(replacer2, text)
    return text

def _extract_by_json_path(data, path):
    """按点号路径从JSON中提取值，支持 field[idx] 数组索引格式"""
    if not path or not isinstance(data, dict):
        return None
    # 去掉开头的$符号(JSONPath根节点标识)
    if path.startswith('$'):
        path = path[1:]
    # 去掉开头的.符号
    if path.startswith('.'):
        path = path[1:]
    # 按 . 和 [数字] 分割路径
    import re as _re_path
    tokens = _re_path.split(r'(\.|\[\d+\])', path)
    current = data
    for token in tokens:
        if not token or token == '.':
            continue
        if token.startswith('[') and token.endswith(']'):
            idx_str = token[1:-1]
            if idx_str.isdigit():
                idx = int(idx_str)
                if isinstance(current, list) and 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                return None
        elif isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit():
            idx = int(token)
            if 0 <= idx < len(current):
                current = current[idx]
            else:
                return None
        else:
            return None
    return current

def _extract_by_regex(text, pattern):
    """按正则表达式提取值"""
    if not text or not pattern:
        return None
    try:
        match = re.search(pattern, text)
        if match:
            return match.group(1) if match.groups() else match.group(0)
    except Exception:
        pass
    return None

def _extract_variables(response, rules):
    """执行提取规则，返回带类型信息的变量"""
    extracted = {}
    for rule in rules:
        extract_type = rule.get('extract_type', 'json_path')
        # 兼容 field_path 和 var_value 两种字段名
        field_path = rule.get('field_path', '') or rule.get('var_value', '')
        var_name = rule.get('var_name', '')
        var_type = rule.get('var_type', 'suite')  # 新增：获取变量类型，默认 suite
        if not var_name:
            continue
        try:
            if extract_type == 'json_path':
                data = {}
                if hasattr(response, 'json'):
                    try:
                        data = response.json()
                    except Exception:
                        data = {}
                elif isinstance(response, dict):
                    data = response
                value = _extract_by_json_path(data, field_path)
                if value is not None:
                    extracted[var_name] = {'value': value, 'type': var_type}
            elif extract_type == 'regex':
                text = response.text if hasattr(response, 'text') else str(response)
                value = _extract_by_regex(text, field_path)
                if value is not None:
                    extracted[var_name] = {'value': value, 'type': var_type}
            elif extract_type == 'header':
                headers = response.headers if hasattr(response, 'headers') else {}
                value = headers.get(field_path)
                if value is not None:
                    extracted[var_name] = {'value': value, 'type': var_type}
        except Exception:
            pass
    return extracted

def _run_assertions(response_data, rules, variables):
    """执行断言规则"""
    errors = []
    for rule in rules:
        field = rule.get('field', '')
        operator = rule.get('operator', '==')
        expected_value = rule.get('value', '')
        if not field:
            continue
        # 替换预期值中的变量
        expected_value = _replace_variables(expected_value, variables)
        actual_value = _extract_by_json_path(response_data, field)
        if operator == 'exists':
            if actual_value is None:
                errors.append(f"字段不存在: {field}")
            continue
        if operator == 'is_empty':
            if actual_value is not None and actual_value != '' and actual_value != [] and actual_value != {}:
                errors.append(f"字段不为空: {field}")
            continue
        # 尝试类型转换后比较
        try:
            if operator == '==':
                if str(actual_value) != str(expected_value):
                    errors.append(f"{field} 期望等于 {expected_value}, 实际 {actual_value}")
            elif operator == '!=':
                if str(actual_value) == str(expected_value):
                    errors.append(f"{field} 期望不等于 {expected_value}, 实际 {actual_value}")
            elif operator == 'contains':
                if str(expected_value) not in str(actual_value):
                    errors.append(f"{field} 期望包含 {expected_value}, 实际 {actual_value}")
            elif operator in ('>', '<', '>=', '<='):
                # 尝试数字比较
                try:
                    a = float(actual_value) if actual_value is not None else 0
                    e = float(expected_value) if expected_value != '' else 0
                    if operator == '>' and not (a > e):
                        errors.append(f"{field} 期望 > {expected_value}, 实际 {actual_value}")
                    elif operator == '<' and not (a < e):
                        errors.append(f"{field} 期望 < {expected_value}, 实际 {actual_value}")
                    elif operator == '>=' and not (a >= e):
                        errors.append(f"{field} 期望 >= {expected_value}, 实际 {actual_value}")
                    elif operator == '<=' and not (a <= e):
                        errors.append(f"{field} 期望 <= {expected_value}, 实际 {actual_value}")
                except (ValueError, TypeError):
                    errors.append(f"{field} 无法进行数字比较: 实际 {actual_value}, 期望 {expected_value}")
        except Exception as e:
            errors.append(f"{field} 断言异常: {e}")
    return errors

def test_suite_execution():
    """按顺序执行套件中的所有测试用例"""
    test_cases_data = [

        {
            'index': 0,
            'case_id': 21,
            'title': "debug_user_用例_2",
            'method': "GET",
            'api_endpoint': "",
            'headers_json': {},
            'body_json': {},
            'has_body': False,
            'expected_json': {},
        },

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

