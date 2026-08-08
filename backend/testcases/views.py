from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import TestCase
from .serializers import TestCaseSerializer
from .services import AITestCaseGenerator
import re
import json
import requests
from urllib.parse import urlparse


# Debug执行引擎（不保存执行历史）
def run_debug_execution(test_case, global_variables=None):
    """直接执行单个测试用例，不保存到执行历史
    test_case 可以是数据库对象或字典（来自前端表单数据）
    """
    import tempfile
    import subprocess
    import os
    from pathlib import Path
    from django.conf import settings

    results_dir = Path(tempfile.mkdtemp(prefix='debug_exec_'))
    global_vars = global_variables or {}

    # 统一从对象或字典中提取字段
    def _get(attr, default=None):
        if isinstance(test_case, dict):
            return test_case.get(attr, default)
        return getattr(test_case, attr, default)

    headers = _get('headers') or {}
    request_body = _get('request_body') or {}
    if isinstance(headers, str):
        try:
            headers = json.loads(headers)
        except:
            headers = {}
    if isinstance(request_body, str):
        try:
            request_body = json.loads(request_body)
        except:
            request_body = {}

    extract_rules = _get('extract_rules') or []
    assertion_rules = _get('assertion_rules') or []

    title_safe = _get('title', 'Untitled').replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', '')
    method_safe = _get('method', 'GET').replace('\\', '\\\\').replace('"', '\\"')
    case_id = _get('id', 'temp')
    api_endpoint_safe = _get('api_endpoint', '').replace('\\', '\\\\').replace('"', '\\"')
    headers_json = json.dumps(headers, ensure_ascii=False).replace('true', 'True').replace('false', 'False').replace('null', 'None')
    body_json = json.dumps(request_body, ensure_ascii=False).replace('true', 'True').replace('false', 'False').replace('null', 'None')
    has_body = 'True' if request_body else 'False'

    test_code = f"""import requests
import json
import time
import re
from pathlib import Path

RESULTS_FILE = Path(r'{results_dir}') / 'case_results.json'

EXTRACT_RULES = {json.dumps(extract_rules, ensure_ascii=False)}
ASSERTION_RULES = {json.dumps(assertion_rules, ensure_ascii=False)}
GLOBAL_VARS = {json.dumps(global_vars, ensure_ascii=False)}

def _replace_variables(text, variables):
    if not text or not variables:
        return text
    if isinstance(text, dict):
        return {{k: _replace_variables(v, variables) for k, v in text.items()}}
    if isinstance(text, list):
        return [_replace_variables(v, variables) for v in text]
    if not isinstance(text, str):
        return text
    pattern = re.compile(r'\\{{\\{{([^}}]+)\\}}\\}}')
    def replacer(match):
        var_name = match.group(1).strip()
        return str(variables.get(var_name, match.group(0)))
    return pattern.sub(replacer, text)

def _extract_by_json_path(data, path):
    # 按点号路径从JSON中提取值, 支持 field[idx] 数组索引格式
    if not path or not isinstance(data, dict):
        return None
    # 按 . 和 [数字] 分割路径
    tokens = re.split(r'(\.|\[\d+\])', path)
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
    extracted = {{}}
    for rule in rules:
        extract_type = rule.get('extract_type', 'json_path')
        field_path = rule.get('field_path', '')
        var_name = rule.get('var_name', '')
        if not var_name:
            continue
        try:
            if extract_type == 'json_path':
                data = {{}}
                if hasattr(response, 'json'):
                    try:
                        data = response.json()
                    except Exception:
                        data = {{}}
                elif isinstance(response, dict):
                    data = response
                value = _extract_by_json_path(data, field_path)
                if value is not None:
                    extracted[var_name] = value
            elif extract_type == 'regex':
                text = response.text if hasattr(response, 'text') else str(response)
                value = _extract_by_regex(text, field_path)
                if value is not None:
                    extracted[var_name] = value
            elif extract_type == 'header':
                headers = response.headers if hasattr(response, 'headers') else {{}}
                value = headers.get(field_path)
                if value is not None:
                    extracted[var_name] = value
        except Exception:
            pass
    return extracted

def _run_assertions(response_data, rules, variables):
    errors = []
    for rule in rules:
        field = rule.get('field', '')
        operator = rule.get('operator', '==')
        expected_value = rule.get('value', '')
        if not field:
            continue
        expected_value = _replace_variables(expected_value, variables)
        actual_value = _extract_by_json_path(response_data, field)
        if operator == 'exists':
            if actual_value is None:
                errors.append(f"字段不存在: {{field}}")
            continue
        if operator == 'is_empty':
            if actual_value is not None and actual_value != '' and actual_value != [] and actual_value != {{}}:
                errors.append(f"字段不为空: {{field}}")
            continue
        try:
            if operator == '==':
                if str(actual_value) != str(expected_value):
                    errors.append(f"{{field}} 期望等于 {{expected_value}}, 实际 {{actual_value}}")
            elif operator == '!=':
                if str(actual_value) == str(expected_value):
                    errors.append(f"{{field}} 期望不等于 {{expected_value}}, 实际 {{actual_value}}")
            elif operator == 'contains':
                if str(expected_value) not in str(actual_value):
                    errors.append(f"{{field}} 期望包含 {{expected_value}}, 实际 {{actual_value}}")
            elif operator in ('>', '<', '>=', '<='):
                try:
                    a = float(actual_value) if actual_value is not None else 0
                    e = float(expected_value) if expected_value != '' else 0
                    if operator == '>' and not (a > e):
                        errors.append(f"{{field}} 期望 > {{expected_value}}, 实际 {{actual_value}}")
                    elif operator == '<' and not (a < e):
                        errors.append(f"{{field}} 期望 < {{expected_value}}, 实际 {{actual_value}}")
                    elif operator == '>=' and not (a >= e):
                        errors.append(f"{{field}} 期望 >= {{expected_value}}, 实际 {{actual_value}}")
                    elif operator == '<=' and not (a <= e):
                        errors.append(f"{{field}} 期望 <= {{expected_value}}, 实际 {{actual_value}}")
                except (ValueError, TypeError):
                    errors.append(f"{{field}} 无法进行数字比较: 实际 {{actual_value}}, 期望 {{expected_value}}")
        except Exception as e:
            errors.append(f"{{field}} 断言异常: {{e}}")
    return errors

def test_debug():
    start = time.time()
    result = {{
        'case_id': {case_id},
        'title': "{title_safe}",
        'method': "{method_safe}",
        'api_endpoint': "{api_endpoint_safe}",
        'status': 'skipped',
        'response_status_code': None,
        'response_body': None,
        'error': None,
        'duration': 0,
        'extracted_vars': {{}},
        'assertion_errors': [],
    }}
    variables = dict(GLOBAL_VARS)
    try:
        request_url = _replace_variables("{api_endpoint_safe}", variables)
        request_headers = _replace_variables({headers_json}, variables)
        request_body = _replace_variables({body_json}, variables) if {has_body} else None
    except Exception as e:
        result['status'] = 'failed'
        result['error'] = "变量替换异常: " + str(e)
        result['duration'] = round(time.time() - start, 3)
        return result
    try:
        response = requests.request(
            method="{method_safe}",
            url=request_url,
            headers=request_headers,
            json=request_body,
            timeout=30,
            allow_redirects=True
        )
        result['response_status_code'] = response.status_code
        try:
            result['response_body'] = response.json()
        except (ValueError, TypeError):
            result['response_body'] = response.text[:2000]
        extracted_vars = _extract_variables(response, EXTRACT_RULES)
        result['extracted_vars'] = extracted_vars
        variables.update(extracted_vars)
        response_data = result['response_body'] if isinstance(result['response_body'], dict) else {{}}
        assertion_errors = _run_assertions(response_data, ASSERTION_RULES, variables)
        result['assertion_errors'] = assertion_errors
        if assertion_errors:
            result['status'] = 'failed'
            result['error'] = "断言失败: " + "; ".join(assertion_errors)
            result['duration'] = round(time.time() - start, 3)
            return result
        result['status'] = 'passed'
    except requests.exceptions.RequestException as e:
        result['status'] = 'failed'
        result['error'] = "请求异常: " + str(e)
    except Exception as e:
        result['status'] = 'failed'
        result['error'] = "执行异常: " + str(e)
    result['duration'] = round(time.time() - start, 3)
    return result

if __name__ == '__main__':
    import sys
    result = test_debug()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result['status'] == 'passed' else 1)
"""

    test_file = results_dir / 'test_debug.py'
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_code)

    try:
        # 使用项目虚拟环境中的 Python 解释器
        import sys
        python_executable = sys.executable
        result = subprocess.run(
            [python_executable, str(test_file)],
            capture_output=True,
            text=True,
            timeout=60,
        )
                # 解析结果
        output = result.stdout.strip()
        error_output = result.stderr.strip()
        
        # 优先尝试解析 stdout 中的 JSON 结果
        exec_result = None
        if output:
            try:
                exec_result = json.loads(output)
            except json.JSONDecodeError:
                # 如果直接解析失败，尝试找到最后一个完整的JSON对象
                for i in range(len(output) - 1, -1, -1):
                    if output[i] == '{':
                        try:
                            candidate = output[i:]
                            exec_result = json.loads(candidate)
                            break
                        except json.JSONDecodeError:
                            continue
        
        # 只有解析 stdout 失败时，才用 stderr 作为错误信息
        if exec_result is None:
            if error_output:
                exec_result = {'status': 'failed', 'error': error_output[-1000:]}
            else:
                exec_result = {
                    'status': 'failed', 
                    'error': f"无法解析JSON输出\n原始输出:\n{output[-500:] if output else '(empty)'}"
                }
    except subprocess.TimeoutExpired:
        exec_result = {'status': 'failed', 'error': '执行超时'}
    except Exception as e:
        exec_result = {'status': 'failed', 'error': str(e)}
    finally:
        # 清理临时文件
        import shutil
        try:
            shutil.rmtree(results_dir)
        except Exception:
            pass

    return exec_result


class TestCaseViewSet(viewsets.ModelViewSet):
    """测试用例视图集（用户数据隔离）"""
    queryset = TestCase.objects.all()
    serializer_class = TestCaseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority', 'method']
    search_fields = ['title', 'description', 'api_endpoint']
    ordering_fields = ['created_at', 'updated_at', 'priority']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_admin:
            return qs
        return qs.filter(created_by=user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def debug(self, request, pk=None):
        """调试执行单个测试用例（不保存执行历史）"""
        test_case = self.get_object()

        if test_case.status == 'draft':
            return Response(
                {'error': '草稿状态用例不允许执行，请先激活'},
                status=status.HTTP_400_BAD_REQUEST
            )

        global_variables = request.data.get('global_variables', {})

        try:
            result = run_debug_execution(test_case, global_variables=global_variables)
            return Response({
                'execution_results': [result],
                'passed_count': 1 if result.get('status') == 'passed' else 0,
                'failed_count': 0 if result.get('status') == 'passed' else 1,
                'skipped_count': 0,
            })
        except Exception as e:
            return Response(
                {'error': f'调试执行失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='debug-temp')
    def debug_temp(self, request):
        """临时调试：无需保存用例，直接传表单数据即可执行调试"""
        global_variables = request.data.get('global_variables', {})
        
        # 从请求体中提取用例字段
        case_data = {
            'title': request.data.get('title', 'Untitled'),
            'method': request.data.get('method', 'GET'),
            'api_endpoint': request.data.get('api_endpoint', ''),
            'headers': request.data.get('headers', {}),
            'request_body': request.data.get('request_body', {}),
            'expected_response': request.data.get('expected_response', {}),
            'extract_rules': request.data.get('extract_rules', []),
            'assertion_rules': request.data.get('assertion_rules', []),
        }

        try:
            result = run_debug_execution(case_data, global_variables=global_variables)
            return Response({
                'execution_results': [result],
                'passed_count': 1 if result.get('status') == 'passed' else 0,
                'failed_count': 0 if result.get('status') == 'passed' else 1,
                'skipped_count': 0,
            })
        except Exception as e:
            return Response(
                {'error': f'调试执行失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def data_factory_datasets(self, request):
        """获取数据工厂的数据集列表，供测试用例导入使用"""
        from data_factory.models import DataFactoryDataset, DataFactoryRecord
        from data_factory.serializers import DataFactoryDatasetSerializer

        datasets = DataFactoryDataset.objects.filter(
            status='completed'
        ).order_by('-created_at')

        serializer = DataFactoryDatasetSerializer(datasets, many=True)
        results = serializer.data

        # 为每个数据集附加 available_fields，方便前端展示可导入字段
        for item in results:
            ds_id = item['id']
            gc = item.get('generation_config') or {}
            fields = []

            if item.get('dataset_type') == 'structured' and isinstance(gc, dict):
                # structured 类型：从 generation_config.fields 提取
                raw_fields = gc.get('fields', [])
                fields = [{
                    'name': f.get('name', ''),
                    'type': f.get('type', 'string'),
                    'label': f.get('label') or f.get('description') or f.get('name', '')
                } for f in raw_fields]
            elif item.get('dataset_type') == 'llm_eval':
                # LLM评测类型：从第一条 record 的 data_content keys 推断字段
                try:
                    first_record = DataFactoryRecord.objects.filter(
                        dataset_id=ds_id
                    ).first()
                    if first_record and isinstance(first_record.data_content, dict):
                        for key in first_record.data_content.keys():
                            fields.append({
                                'name': key,
                                'type': 'string',
                                'label': key
                            })
                except Exception:
                    pass
            elif item.get('dataset_type') == 'agent_dialog':
                # Agent对话类型：同样从 record 推断
                try:
                    first_record = DataFactoryRecord.objects.filter(
                        dataset_id=ds_id
                    ).first()
                    if first_record and isinstance(first_record.data_content, dict):
                        for key in first_record.data_content.keys():
                            fields.append({
                                'name': key,
                                'type': 'string',
                                'label': key
                            })
                except Exception:
                    pass

            item['available_fields'] = fields

        return Response({
            'count': datasets.count(),
            'results': results
        })

    @action(detail=False, methods=['post'])
    def data_factory_import(self, request):
        """从数据工厂导入数据到测试用例的请求体"""
        dataset_id = request.data.get('dataset_id')
        fields = request.data.get('fields', [])

        if not dataset_id:
            return Response({'error': '请选择数据集'}, status=status.HTTP_400_BAD_REQUEST)
        if not fields:
            return Response({'error': '请选择要导入的字段'}, status=status.HTTP_400_BAD_REQUEST)

        from data_factory.models import DataFactoryDataset, DataFactoryRecord

        try:
            dataset = DataFactoryDataset.objects.get(id=dataset_id)
        except DataFactoryDataset.DoesNotExist:
            return Response({'error': '数据集不存在'}, status=status.HTTP_404_NOT_FOUND)

        # 获取数据集的前 5 条记录作为示例
        records = DataFactoryRecord.objects.filter(
            dataset=dataset
        ).order_by('created_at')[:5]

        record_count = dataset.record_count
        sample_data = [r.data_content for r in records]

        # 构建请求体字段映射
        body_fields = {}
        for field_name in fields:
            body_fields[field_name] = f'{{{{context.{field_name}}}}}'

        return Response({
            'dataset_name': dataset.name,
            'record_count': record_count,
            'sample_data': sample_data,
            'body_fields': body_fields,
            'message': f'从"{dataset.name}"导入 {len(fields)} 个字段'
        })


class AIParseInterfaceView(APIView):
    """AI解析接口视图 - 自动识别接口信息并生成测试用例字段"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        api_url = request.data.get('api_url', '')
        method = request.data.get('method', '').upper()
        response_json = request.data.get('response_json', '')
        request_body = request.data.get('request_body', '')

        if not api_url:
            return Response(
                {'error': '请提供接口地址'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            result = self._parse_interface(api_url, method, response_json, request_body)
            return Response(result)

        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'解析失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _parse_interface(self, api_url, method='', response_json='', request_body=''):
        """解析接口信息"""
        # method 优先级：前端传入 > URL推测
        if method and method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
            final_method = method
        else:
            final_method = self._detect_method_from_url(api_url)
        
        result = {
            'api_endpoint': api_url,
            'method': final_method,
            'headers': {},
            'request_body': {},
            'expected_response': None,  # 预期响应JSON
            'assertion_rules': [],      # 断言规则（包含 core/optional/dynamic）
            'extracted_fields': [],
            'warnings': [],
        }

        # 1. 根据URL路径匹配请求头模板
        result['headers'] = self._get_headers_template(api_url, result['method'])

        # 2. 如果没有提供响应JSON，尝试实际调用接口获取响应
        parsed_json = None
        if not response_json:
            try:
                # 解析请求体（如果有）
                req_body = {}
                if request_body:
                    try:
                        req_body = json.loads(request_body)
                    except json.JSONDecodeError:
                        req_body = {}
                
                actual_response = self._fetch_actual_response(api_url, result['method'], result['headers'], req_body)
                if actual_response:
                    parsed_json = actual_response
                    result['expected_response'] = json.dumps(actual_response, ensure_ascii=False, indent=2)
                    result['warnings'].append('已从实际接口调用获取响应数据')
            except Exception as e:
                result['warnings'].append(f'无法自动获取接口响应: {str(e)}')
        
        # 3. 如果有响应JSON（用户提供的或实际调用的），提取字段
        if not parsed_json and response_json:
            try:
                parsed_json = json.loads(response_json)
                result['expected_response'] = response_json
            except json.JSONDecodeError as e:
                result['warnings'].append(f'响应JSON格式错误: {str(e)}')
        
        # 4. 如果成功获取到JSON，提取字段和生成断言（统一数据模型）
        if parsed_json:
            # 使用新的统一数据模型生成断言和可提取字段
            unified_data = self._generate_assertions(parsed_json, api_url)
            
            # 将统一数据拆分到前端需要的格式
            result['assertion_rules'] = unified_data['assertions']
            result['extracted_fields'] = unified_data['extractable_fields']
            
            # 6. 如果是POST/PUT/PATCH，尝试从响应推断请求体结构
            if result['method'] in ['POST', 'PUT', 'PATCH']:
                result['request_body'] = self._infer_request_body(parsed_json)

        # 7. GET请求特殊处理
        if result['method'] == 'GET':
            result['request_body'] = {}
            if not any('已' in w for w in result['warnings']):
                result['warnings'].append('GET请求通常不包含请求体，如需发送数据请使用URL参数或请求头')

        return result

    def _fetch_actual_response(self, api_url, method, headers, request_body=None):
        """实际调用接口获取响应"""
        try:
            # 替换变量占位符为空值
            clean_headers = {}
            for key, value in headers.items():
                # 移除 {{global.xxx}} 等变量占位符
                clean_value = re.sub(r'\{\{[^}]+\}\}', '', value).strip()
                if clean_value:
                    clean_headers[key] = clean_value
            
            req_json = request_body if request_body else {}
            
            # 根据方法发送请求
            if method == 'GET':
                response = requests.get(api_url, headers=clean_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(api_url, headers=clean_headers, json=req_json, timeout=10)
            elif method == 'PUT':
                response = requests.put(api_url, headers=clean_headers, json=req_json, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(api_url, headers=clean_headers, timeout=10)
            elif method == 'PATCH':
                response = requests.patch(api_url, headers=clean_headers, json=req_json, timeout=10)
            else:
                response = requests.get(api_url, headers=clean_headers, timeout=10)
            
            # 返回JSON响应
            if response.headers.get('Content-Type', '').startswith('application/json'):
                return response.json()
            else:
                return None
                
        except requests.exceptions.Timeout:
            raise Exception('接口调用超时')
        except requests.exceptions.ConnectionError:
            raise Exception('无法连接到接口服务器')
        except requests.exceptions.RequestException as e:
            raise Exception(f'接口调用失败: {str(e)}')
        except Exception as e:
            raise Exception(f'解析响应失败: {str(e)}')

    def _detect_method_from_url(self, url):
        """根据URL路径推断请求方法"""
        url_lower = url.lower()
        
        # 包含特定关键词的路径推断
        if any(keyword in url_lower for keyword in ['/delete', '/remove', '/destroy']):
            return 'DELETE'
        elif any(keyword in url_lower for keyword in ['/update', '/modify', '/edit']):
            return 'PUT'
        elif any(keyword in url_lower for keyword in ['/create', '/add', '/insert', '/save', '/login', '/register', '/signin', '/signup', '/auth', '/submit']):
            return 'POST'
        elif any(keyword in url_lower for keyword in ['/list', '/all', '/search', '/query']):
            return 'GET'
        
        # 默认GET
        return 'GET'

    def _get_headers_template(self, url, method):
        """根据接口路径和方法返回请求头模板"""
        headers = {
            'Content-Type': 'application/json'
        }
        
        # 如果需要认证，添加Authorization占位符
        if any(keyword in url.lower() for keyword in ['/user', '/profile', '/account', '/auth']):
            headers['Authorization'] = 'Bearer {{global.token}}'
        
        # 如果是文件上传相关
        if any(keyword in url.lower() for keyword in ['/upload', '/file', '/image']):
            headers['Content-Type'] = 'multipart/form-data'
        
        return headers

    def _extract_json_fields(self, json_obj, prefix=''):
        """递归提取JSON字段"""
        fields = []
        
        if not isinstance(json_obj, dict):
            return fields
        
        for key, value in json_obj.items():
            field_path = f"{prefix}.{key}" if prefix else key
            field_type = type(value).__name__
            
            # 处理数组类型
            if isinstance(value, list):
                field_type = 'array'
                if value and isinstance(value[0], dict):
                    # 递归提取数组元素字段
                    fields.extend(self._extract_json_fields(value[0], f"{field_path}[0]"))
            
            fields.append({
                'path': field_path,
                'type': field_type,
                'value': value if not isinstance(value, (dict, list)) else None,
            })
            
            # 递归处理嵌套对象
            if isinstance(value, dict):
                fields.extend(self._extract_json_fields(value, field_path))
        
        return fields

    def _generate_assertions(self, json_obj, url=''):
        """根据响应JSON生成断言规则和可提取字段列表
        
        设计原则：
        - 核心状态字段（code/msg/status等）自动生成核心断言
        - 所有业务数据字段放入可提取字段列表，由用户自主选择生成断言
        """
        fields_data = {
            'assertions': [],           # 断言规则列表（仅核心状态字段）
            'extractable_fields': [],   # 可提取字段列表（所有业务字段）
        }
        
        # 核心状态字段：接口返回的状态标识，自动断言
        CORE_FIELDS = {
            'code', 'status', 'success', 'result', 'error_code', 'errno',
            'message', 'msg', 'error_msg', 'errmsg',
        }
        
        def is_core_field(field_name):
            """判断是否为关键核心字段"""
            field_lower = field_name.lower()
            return any(core == field_lower for core in CORE_FIELDS)
        
        def get_operator_for_value(value):
            """根据值类型返回合适的运算符"""
            if isinstance(value, bool):
                return '=='
            elif isinstance(value, (int, float)):
                return '=='
            elif isinstance(value, str):
                if len(value) > 100:
                    return 'exists'
                return 'contains' if len(value) > 10 else '=='
            else:
                return 'exists'
        
        def process_fields(obj, prefix=''):
            """递归处理所有字段：核心字段生成断言，其他放入可提取列表"""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{prefix}.{key}" if prefix else key
                    
                    if isinstance(value, (dict, list)):
                        # 嵌套对象/数组
                        if is_core_field(key):
                            # 核心字段的嵌套结构：添加存在性断言
                            fields_data['assertions'].append({
                                'field': current_path,
                                'operator': 'exists',
                                'value': '',
                                'category': 'core',
                                '_type': 'assertion_only',
                            })
                        # 递归处理子字段
                        process_fields(value, current_path)
                    else:
                        # 简单类型字段
                        if is_core_field(key):
                            # 核心字段：自动生成断言
                            operator = get_operator_for_value(value)
                            str_value = str(value) if value is not None else ''
                            fields_data['assertions'].append({
                                'field': current_path,
                                'operator': operator,
                                'value': str_value,
                                'category': 'core',
                                '_type': 'assertion_only',
                            })
                        else:
                            # 其他字段：放入可提取列表，供用户自主选择
                            fields_data['extractable_fields'].append({
                                'path': current_path,
                                'value': value,
                                'type': type(value).__name__,
                                '_type': 'extract_only',
                                '_description': f'勾选后点击"生成断言规则"即可添加对 {current_path} 的断言',
                            })
                            
            elif isinstance(obj, list):
                # 数组类型
                if prefix and is_core_field(prefix.split('.')[-1]):
                    fields_data['assertions'].append({
                        'field': prefix,
                        'operator': 'exists',
                        'value': '',
                        'category': 'core',
                        '_type': 'assertion_only',
                    })
                # 处理数组元素（只处理前3个避免过多）
                for idx, item in enumerate(obj[:3]):
                    current_path = f"{prefix}[{idx}]"
                    if isinstance(item, (dict, list)):
                        process_fields(item, current_path)
                    else:
                        fields_data['extractable_fields'].append({
                            'path': current_path,
                            'value': item,
                            'type': type(item).__name__,
                            '_type': 'extract_only',
                        })
        
        # 生成断言和可提取字段
        process_fields(json_obj)
        
        return fields_data

    def _detect_scene_type(self, url):
        """根据URL路径推断接口场景类型"""
        url_lower = url.lower()
        
        # 登录/认证相关
        if any(keyword in url_lower for keyword in ['/login', '/auth', '/signin', '/oauth']):
            return 'login'
        
        # 查询/列表相关
        if any(keyword in url_lower for keyword in ['/list', '/query', '/search', '/all', '/get']):
            return 'query'
        
        # 提交/创建相关
        if any(keyword in url_lower for keyword in ['/create', '/add', '/submit', '/save', '/insert']):
            return 'submit'
        
        return 'default'

    def _infer_request_body(self, response_json):
        """从响应推断请求体结构（简化版）"""
        # 这里只是简单示例，实际应该根据接口文档或历史数据推断
        if isinstance(response_json, dict):
            # 移除响应特有的字段，保留可能的请求字段
            request_fields = {}
            exclude_keys = ['code', 'msg', 'message', 'status', 'timestamp']
            
            for key, value in response_json.items():
                if key not in exclude_keys and not isinstance(value, (dict, list)):
                    request_fields[key] = ''
            
            return request_fields
        
        return {}


class AIGenerateView(APIView):
    """AI生成测试用例视图"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        api_document = request.data.get('api_document', '')

        if not api_document:
            return Response(
                {'error': '请提供接口文档内容'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            generator = AITestCaseGenerator()
            test_cases = generator.generate_test_cases(api_document)

            # 可选：直接保存到数据库
            save_to_db = request.data.get('save_to_db', False)
            if save_to_db:
                created_cases = []
                for case_data in test_cases:
                    serializer = TestCaseSerializer(
                        data=case_data,
                        context={'request': request}
                    )
                    if serializer.is_valid():
                        case = serializer.save()
                        created_cases.append(TestCaseSerializer(case).data)
                return Response({
                    'message': f'成功生成并保存 {len(created_cases)} 个测试用例',
                    'test_cases': created_cases
                })

            return Response({
                'test_cases': test_cases,
                'count': len(test_cases)
            })

        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'生成失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
