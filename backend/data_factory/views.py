from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import json
import random
import logging
import re
from datetime import datetime
from django.utils import timezone
from django.conf import settings
import requests

from core.llm_provider import LLMProviderFactory

# 配置日志
logger = logging.getLogger(__name__)


def _generate_with_fallback(prompt: str, max_tokens: int):
    """按优先级调用 LLM，支持 Provider 降级。"""
    default_provider = getattr(settings, 'DEFAULT_LLM_PROVIDER', 'deepseek')
    default_model = getattr(settings, 'DEFAULT_LLM_MODEL', 'deepseek-chat')

    candidates = [(default_provider, default_model)]

    # 如果默认不是 DeepSeek，且配置了 Key，加入降级候选
    if default_provider != 'deepseek' and getattr(settings, 'DEEPSEEK_API_KEY', ''):
        candidates.append(('deepseek', 'deepseek-chat'))
    if default_provider != 'glm' and getattr(settings, 'GLM_API_KEY', ''):
        candidates.append(('glm', 'glm-4-flash'))
    if default_provider != 'dashscope' and getattr(settings, 'DASHSCOPE_API_KEY', ''):
        candidates.append(('dashscope', 'qwen-turbo'))

    last_error = ''
    for provider_name, model in candidates:
        try:
            print(f"[DEBUG] Trying LLM provider: {provider_name}/{model}")
            llm = LLMProviderFactory.create(
                provider_name,
                model=model,
                temperature=0.5,
                max_tokens=max_tokens,
            )
            content = llm.chat([{"role": "user", "content": prompt}])
            print(f"[DEBUG] Provider {provider_name} succeeded")
            return content, provider_name
        except Exception as e:
            last_error = str(e)
            print(f"[WARN] Provider {provider_name} failed: {last_error}")
            continue

    raise RuntimeError(f'所有 LLM Provider 均调用失败: {last_error}')

from .models import DataFactoryDataset, DataFactoryRecord, DataFactoryTemplate, DataFactoryUsageLog, PresetTemplate, DataFactoryDatasetVersion
from .serializers import (
    DataFactoryDatasetSerializer,
    DataFactoryRecordSerializer,
    DataFactoryTemplateSerializer,
    DataFactoryUsageLogSerializer,
    PresetTemplateSerializer,
    DataFactoryDatasetVersionSerializer
)


class DatasetViewSet(viewsets.ModelViewSet):
    """数据集管理ViewSet（用户数据隔离）"""
    permission_classes = [IsAuthenticated]
    serializer_class = DataFactoryDatasetSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return DataFactoryDataset.objects.all()
        return DataFactoryDataset.objects.filter(created_by=user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['post'])
    def generate_structured(self, request):
        """生成结构化数据"""
        try:
            data = request.data
            dataset_name = data.get('name', f'结构化数据_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
            business_domain = data.get('business_domain', 'order')
            count = int(data.get('count', 100))
            fields = data.get('fields', [])
            boundary_tests = data.get('boundary_tests', [])

            # 创建数据集
            dataset = DataFactoryDataset.objects.create(
                name=dataset_name,
                dataset_type='structured',
                business_domain=business_domain,
                description=f'生成的{count}条{business_domain}业务数据',
                generation_config=data,
                record_count=count,
                status='generating',
                created_by=request.user
            )

            # 生成数据记录
            records = []
            for i in range(count):
                record_data = {}
                for field in fields:
                    field_name = field.get('name', '')
                    field_type = field.get('type', 'string')

                    if field_type == 'string':
                        lower_name = field_name.lower()
                        if 'id' in lower_name or 'number' in lower_name or 'account' in lower_name or 'code' in lower_name:
                            record_data[field_name] = f"{random.randint(100000000000, 999999999999)}"
                        elif 'currency' in lower_name:
                            record_data[field_name] = random.choice(['USD', 'EUR', 'CNY', 'GBP'])
                        elif 'carrier' in lower_name:
                            record_data[field_name] = random.choice(['DHL', 'FedEx', 'UPS', 'China Post', 'SF Express', 'YTO Express', 'STO Express'])
                        elif 'name' in lower_name:
                            record_data[field_name] = random.choice(['张三', '李四', '王五', '赵六', '陈七', '刘八', '周九', '吴十'])
                        elif 'address' in lower_name or 'city' in lower_name or 'location' in lower_name:
                            record_data[field_name] = random.choice(['北京市', '上海市', '广州市', '深圳市', '杭州市', '成都市', '武汉市'])
                        elif 'status' in lower_name:
                            record_data[field_name] = random.choice(['pending', 'processing', 'completed', 'cancelled', 'failed', 'on_hold'])
                        elif 'origin' in lower_name or 'source' in lower_name:
                            record_data[field_name] = random.choice(['Beijing', 'Shanghai', 'Guangzhou', 'Shenzhen', 'Hangzhou', 'Chengdu', 'Wuhan'])
                        elif 'destination' in lower_name or 'dest' in lower_name or 'target' in lower_name:
                            record_data[field_name] = random.choice(['New York', 'London', 'Tokyo', 'Singapore', 'Sydney', 'Dubai', 'Paris'])
                        elif 'type' in lower_name:
                            record_data[field_name] = random.choice(['standard', 'express', 'overnight', 'international', 'economy'])
                        elif 'time' in lower_name or 'date' in lower_name:
                            from datetime import timedelta
                            random_days = random.randint(0, 365)
                            random_time = datetime.now() - timedelta(days=random_days)
                            record_data[field_name] = random_time.strftime('%Y-%m-%d %H:%M:%S')
                        elif 'email' in lower_name:
                            record_data[field_name] = f"user{i+1}@example.com"
                        elif 'phone' in lower_name or 'mobile' in lower_name or 'tel' in lower_name:
                            record_data[field_name] = f"1{random.randint(30, 99)}{random.randint(100000000, 999999999)}"
                        elif 'weight' in lower_name:
                            record_data[field_name] = f"{round(random.uniform(0.1, 50.0), 2)}kg"
                        elif 'desc' in lower_name or 'remark' in lower_name or 'note' in lower_name or 'comment' in lower_name:
                            record_data[field_name] = random.choice(['正常', '加急', '特殊处理', '需审核', '已确认', '待跟进', '无异常'])
                        else:
                            record_data[field_name] = f"{field_name}_{i+1:04d}"
                    elif field_type == 'integer':
                        record_data[field_name] = random.randint(1, 100000)
                    elif field_type == 'decimal':
                        record_data[field_name] = round(random.uniform(10.0, 999999.99), 2)
                    elif field_type == 'boolean':
                        record_data[field_name] = random.choice([True, False])
                    elif field_type == 'date':
                        from datetime import timedelta
                        random_days = random.randint(0, 365)
                        random_date = datetime.now() - timedelta(days=random_days)
                        record_data[field_name] = random_date.strftime('%Y-%m-%d')

                # 应用边界测试
                if 'null' in boundary_tests and random.random() < 0.1:
                    null_field = random.choice(fields)['name']
                    record_data[null_field] = None
                if 'empty' in boundary_tests and random.random() < 0.1:
                    empty_field = random.choice(fields)['name']
                    record_data[empty_field] = ''
                if 'long' in boundary_tests and random.random() < 0.05:
                    long_field = random.choice(fields)['name']
                    record_data[long_field] = 'A' * 500
                if 'special' in boundary_tests and random.random() < 0.05:
                    special_field = random.choice(fields)['name']
                    record_data[special_field] = "' OR 1=1 -- <script>alert(1)</script>"
                if 'negative' in boundary_tests and random.random() < 0.05:
                    for f in fields:
                        if f.get('type') in ['integer', 'decimal']:
                            record_data[f['name']] = random.randint(-99999, -1)
                            break

                records.append(DataFactoryRecord(dataset=dataset, data_content=record_data))

            DataFactoryRecord.objects.bulk_create(records)

            # 更新数据集状态
            dataset.status = 'completed'
            dataset.file_size = len(json.dumps([r.data_content for r in records]).encode())
            dataset.save()

            # 序列化数据集返回完整信息
            serializer = DataFactoryDatasetSerializer(dataset)
            return Response({
                'message': f'成功生成 {len(records)} 条数据',
                'dataset': serializer.data
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def test_api(self, request):
        """测试API是否正常工作"""
        print("[TEST] test_api endpoint called!")
        return Response({
            'status': 'ok',
            'message': 'Backend API is working!',
            'timestamp': datetime.now().isoformat()
        })

    @action(detail=False, methods=['get'])
    def debug_llm_response(self, request):
        """调试LLM API响应 - 返回原始AI内容"""
        import requests
        
        scenario = "电商客服订单查询Agent"
        
        prompt = f"""# Role
You are a professional test data generation expert.

# Task
Generate mock test data for: {scenario}

# Instructions
Extract 3-5 business fields and generate 2 test items (1 positive, 1 negative).

# CRITICAL RULES
1. Return ONLY valid JSON array - no markdown, no comments
2. NO programming syntax like .repeat()
3. All strings properly quoted with double quotes
4. No trailing commas

# Output Format Example
[
  {{"case_id":"POS0001","type":"positive","label":1,"language":"zh","order_id":"ORD001","product_name":"Test Product"}},
  {{"case_id":"NEG0001","type":"negative","label":0,"language":"zh","order_id":"","product_name":""}}
]

# NOW EXECUTE
Return ONLY the JSON array.
"""
        
        api_key = settings.DASHSCOPE_API_KEY
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            "model": "qwen-plus",
            "input": {"messages": [{"role": "user", "content": prompt}]},
            "parameters": {"result_format": "text", "temperature": 0.1, "max_tokens": 2000}
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                ai_content = result['output']['text']
                
                # 尝试解析JSON
                import json as json_module
                json_match = re.search(r'\[\s*\{{.*}}\s*\]', ai_content, re.DOTALL)
                
                parsed_data = None
                parse_error = None
                
                if json_match:
                    try:
                        parsed_data = json_module.loads(json_match.group())
                    except Exception as e:
                        parse_error = str(e)
                
                return Response({
                    'status': 'success',
                    'ai_raw_content': ai_content[:3000],
                    'json_found': bool(json_match),
                    'parsed_data': parsed_data,
                    'parse_error': parse_error
                })
            else:
                return Response({
                    'status': 'error',
                    'message': f'API call failed: {response.text}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def generate_llm_dataset(self, request):
        """调用通义千问API生成LLM评测数据"""
        print("=" * 80)
        print("[DEBUG] generate_llm_dataset method called!")
        print("=" * 80)
        
        # 确保re模块可用
        global re
        try:
            import re
        except:
            pass
        
        try:
            data = request.data
            
            # 调试：打印完整的请求数据
            print(f"[DEBUG] Full request.data: {data}")
            print(f"[DEBUG] Request headers: {dict(request.headers)}")
            
            scenario = data.get('scenario', '')
            dataset_name_from_frontend = data.get('dataset_name', '')
            print(f"[DEBUG] Received dataset_name from frontend: '{dataset_name_from_frontend}'")
            
            # 限制生成数量用于演示（面试用途）
            positive_count = min(int(data.get('positive_count', 2)), 3)
            negative_count = min(int(data.get('negative_count', 1)), 2)
            boundary_count = min(int(data.get('boundary_count', 1)), 2)
            languages = data.get('languages', ['zh'])

            # 调试日志：打印接收到的参数
            print(f"[DEBUG] Received params: scenario={scenario[:30]}..., positive={positive_count}, negative={negative_count}, boundary={boundary_count}")

            if not scenario:
                return Response(
                    {'error': '请提供场景描述'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # ========== 极速版 Prompt (目标: 3-5秒内响应) ==========
            total_count = positive_count + negative_count + boundary_count
            
            # 解析场景描述中的字段Title和内容（场景限定）
            field_title = ""
            content = scenario
            
            # 同时支持中文冒号和英文冒号，支持多种标题格式
            title_pattern = re.compile(r'字段Title[：:]|字段标题[：:]|Title[：:]|标题[：:]')
            content_pattern = re.compile(r'内容[：:]')
            
            if title_pattern.search(scenario):
                # 提取字段Title和内容
                parts = title_pattern.split(scenario)
                field_title = parts[1].strip() if len(parts) > 1 else ""
                
                # 从field_title中提取真正的字段标题（去除"内容:"及其后面的部分）
                if content_pattern.search(field_title):
                    field_title_parts = content_pattern.split(field_title)
                    field_title = field_title_parts[0].strip()
                    # 如果有内容部分，更新content
                    if len(field_title_parts) > 1:
                        content = field_title_parts[1].strip()
                else:
                    # 如果没有找到"内容:"，则content保持为原始场景（字段Title之前的部分）
                    content = parts[0].strip()
            else:
                # 如果没有字段Title，检查是否有单独的"内容:"
                if content_pattern.search(scenario):
                    content_parts = content_pattern.split(scenario)
                    content = content_parts[1].strip() if len(content_parts) > 1 else scenario
            
            print(f"[DEBUG] Scenario before split: {scenario[:100]}...")
            print(f"[DEBUG] Content after split: '{content}'")
            print(f"[DEBUG] Field title extracted: '{field_title}'")
            
            # 解析字段Title为独立的业务关键词列表（用于指导AI生成对应字段）
            business_keywords = []
            if field_title:
                # 按逗号或顿号分割
                business_keywords = [kw.strip() for kw in re.split(r'[、,，]', field_title) if kw.strip()]
                print(f"[DEBUG] Business keywords parsed: {business_keywords}")
            
            # 将解析的字段信息保存到generation_config中（供前端使用）
            data['field_title'] = field_title
            data['business_keywords'] = business_keywords
            
            # 计算总数量：直接等于正+负+边界，多语言时AI自行分配
            grand_total = total_count
            
            # 构建语言分布说明（极简版）
            lang_dist = f"{len(languages)} langs" if len(languages) > 1 else "zh only"
            per_lang_counts = f"{positive_count}p+{negative_count}n+{boundary_count}b total"
            
            # ========== 极速版 Prompt - 精简示例、减少token、提升速度 ==========
            fields_str = ', '.join([f'"{kw}"' for kw in business_keywords]) if business_keywords else '"field1", "field2"'
            
            # 只生成1条极简示例（而非每种语言各3条），大幅减少prompt token
            example_fields = {}
            for kw in business_keywords[:4]:
                example_fields[kw] = f"示例{kw}数据"
            
            example_str = json.dumps([{
                "case_id": "T001",
                "type": "positive",
                "language": "zh",
                **example_fields
            }], ensure_ascii=False)
            
            # 构建语言说明 - 极简版
            if len(languages) > 1:
                lang_instructions = f"""Languages: {', '.join(languages)}. Distribute across languages. Include 'language' field."""
            else:
                lang_instructions = f"""Language: {languages[0]}. Include 'language' field."""
            
            prompt = f"""Generate EXACTLY {grand_total} test cases (NO MORE, NO LESS) for: {content[:120]}

Fields: {fields_str}
Distribution: {positive_count} positive + {negative_count} negative + {boundary_count} boundary = {grand_total} total
Rules:
1. Use exact field names as JSON keys
2. Write concise TEXT (20-40 chars per field)
3. positive=valid normal data, negative=invalid/wrong data, boundary=edge/extreme cases
4. Include case_id (T001) and type fields
5. {lang_instructions}
6. Output ONLY a JSON array, nothing else

Example:
{example_str}"""

            print("[DEBUG] ========== Final Prompt for AI ==========")
            print(f"[DEBUG] Prompt length: {len(prompt)} chars, ~{len(prompt)//4} tokens")
            print("[DEBUG] =====================================")

            # 调用统一 LLM Provider（默认优先 DeepSeek，自动降级）
            estimated_response_tokens = grand_total * 80  # 每条约80token（精简后）
            max_tokens = min(2500, max(800, estimated_response_tokens))

            import time
            start_time = time.time()

            try:
                ai_content, used_provider = _generate_with_fallback(prompt, max_tokens)
                print(f"[DEBUG] Used LLM provider: {used_provider}")
            except Exception as e:
                return Response(
                    {'error': f'LLM调用失败: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            elapsed_time = time.time() - start_time
            print(f"[PERF] API call completed in {elapsed_time:.2f}s")

            # 解析 AI 返回的数据
            print("[DEBUG] Parsing AI response...", flush=True)
            
            # 处理可能的编码问题：修复乱码
            try:
                if ai_content and isinstance(ai_content, str):
                    print(f"[DEBUG] AI content before encoding fix: {ai_content[:200]}", flush=True)
                    
                    # 检测是否包含典型的GBK乱码模式（中文UTF-8被当作GBK解码产生的乱码）
                    has_gbk_garbage = any(char in ai_content for char in ['鏀', '惰', '揣', '閫', '鎹', '浜', '搧', '婕', '忓'])
                    print(f"[DEBUG] has_gbk_garbage: {has_gbk_garbage}", flush=True)
                    
                    # 使用字符映射修复乱码字段名
                    field_mapping = {
                        '鏀惰揣': '收货',
                        '閫€璐?': '退货',
                        '閫€璐': '退货',
                        '鎹㈣揣': '换货',
                        '浜у搧鐮存崯绱㈣禂': '产品破损索赔',
                        '婕忓彂琛ュ彂鍦烘櫙': '漏发补发场景',
                        '鏀惰揣 ': '收货',
                        ' 鏀惰揣': '收货',
                        '閫€璐?': '退货',
                        '閫€璐? ': '退货',
                        ' 閫€璐?': '退货',
                        '鎹㈣揣 ': '换货',
                        ' 鎹㈣揣': '换货',
                        '浜у搧鐮存崯绱㈣禂 ': '产品破损索赔',
                        ' 浜у搧鐮存崯绱㈣禂': '产品破损索赔',
                        '婕忓彂琛ュ彂鍦烘櫙 ': '漏发补发场景',
                        ' 婕忓彂琛ュ彂鍦烘櫙': '漏发补发场景'
                    }
                    
                    # 逐个替换乱码字段名
                    for garbage, correct in field_mapping.items():
                        if garbage in ai_content:
                            ai_content = ai_content.replace(garbage, correct)
                            print(f"[DEBUG] Replaced '{garbage}' with '{correct}'", flush=True)
                
                print(f"[DEBUG] AI content after encoding fix: {ai_content[:200]}", flush=True)
            except Exception as e:
                print(f"[DEBUG] Encoding fix attempt failed: {e}", flush=True)
            
            # 立即保存AI原始响应到文件（用于调试）
            try:
                with open('backend_ai_raw.txt', 'w', encoding='utf-8') as f:
                    f.write(f"Length: {len(ai_content)}\n\n")
                    f.write(f"Content:\n{ai_content}\n")
                print("[DEBUG] Saved AI raw content to backend_ai_raw.txt", flush=True)
            except Exception as save_err:
                print(f"[ERROR] Failed to save debug file: {save_err}", flush=True)
            
            print(f"[DEBUG] AI content length: {len(ai_content)} characters", flush=True)
            print(f"[DEBUG] AI full content:\n{ai_content}", flush=True)
            
            # 提取 JSON 数组（可能包含在markdown代码块中）
            
            # 首先尝试查找markdown代码块中的JSON
            markdown_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', ai_content, re.DOTALL)
            if markdown_match:
                json_str = markdown_match.group(1)
                print("[DEBUG] Found JSON in markdown code block")
            else:
                # 使用贪婪匹配查找完整的JSON数组（从第一个[到最后一个]）
                json_match = re.search(r'\[.*\]', ai_content, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    print("[DEBUG] Found complete JSON array with greedy regex")
                else:
                    json_str = None
                    print("[DEBUG] No JSON array found")
            
            if json_str:
                print(f"[DEBUG] JSON string length: {len(json_str)} chars")
                print(f"[DEBUG] Full JSON string:\n{json_str}")
                
                # 尝试解析JSON
                try:
                    test_cases = json.loads(json_str)
                    print(f"[DEBUG] Successfully parsed {len(test_cases)} test cases")
                except json.JSONDecodeError as e:
                    print(f"[DEBUG] JSON parse failed, trying to fix: {e}")
                    
                    # 修复策略1：处理多个独立JSON数组的情况 [{...}], [{...}], [{...}]
                    # 尝试提取所有 {...} 对象并合并成一个数组
                    object_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', json_str)
                    if object_matches:
                        print(f"[DEBUG] Found {len(object_matches)} JSON objects, merging into array")
                        try:
                            test_cases = [json.loads(obj) for obj in object_matches]
                            print(f"[DEBUG] Successfully merged {len(test_cases)} objects into array")
                        except Exception as merge_err:
                            print(f"[DEBUG] Merge failed: {merge_err}")
                            object_matches = None
                    
                    if not object_matches:
                        # 修复策略2：修复不完整的JSON
                        fixed_json_str = json_str
                        
                        # 修复：添加缺失的闭合括号
                        if fixed_json_str.count('[') > fixed_json_str.count(']'):
                            fixed_json_str += ']' * (fixed_json_str.count('[') - fixed_json_str.count(']'))
                        if fixed_json_str.count('{') > fixed_json_str.count('}'):
                            fixed_json_str += '}' * (fixed_json_str.count('{') - fixed_json_str.count('}'))
                        
                        # 修复：修复不完整的字符串（移除末尾不完整的部分）
                        last_brace = fixed_json_str.rfind('}')
                        if last_brace != -1:
                            fixed_json_str = fixed_json_str[:last_brace + 1] + ']'
                        
                        print(f"[DEBUG] Fixed JSON string:\n{fixed_json_str}")
                        
                        try:
                            test_cases = json.loads(fixed_json_str)
                            print(f"[DEBUG] Successfully parsed after fix: {len(test_cases)} test cases")
                        except json.JSONDecodeError as e2:
                            print(f"[DEBUG] Failed to parse fixed JSON: {e2}")
                            raise
                    
                    # 详细调试：打印每条测试用例的完整内容
                    print(f"[DEBUG] ========== All test cases ==========")
                    for i, case in enumerate(test_cases):
                        print(f"[DEBUG] Case {i+1}: {json.dumps(case, ensure_ascii=False)}")
                    print(f"[DEBUG] ====================================")
                    
                    # 调试：打印第一条测试用例的字段列表
                    if len(test_cases) > 0:
                        first_case = test_cases[0]
                        print(f"[DEBUG] First case fields: {list(first_case.keys())}")
                        print(f"[DEBUG] First case content: {json.dumps(first_case, ensure_ascii=False)}")
                    
                    # 验证是否包含中英文数据
                    zh_count = sum(1 for case in test_cases if case.get('language') == 'zh')
                    en_count = sum(1 for case in test_cases if case.get('language') == 'en')
                    print(f"[DEBUG] Language distribution: zh={zh_count}, en={en_count}")
                except Exception as e:
                    print(f"[ERROR] JSON parse failed: {e}")
                    # 保存详细的调试信息
                    with open('json_parse_error.txt', 'w', encoding='utf-8') as f:
                        f.write(f"Error: {str(e)}\n\n")
                        f.write(f"JSON String (full):\n{json_str}\n\n")
                        f.write(f"Full AI Content:\n{ai_content}\n")
                    raise
            else:
                # 尝试直接解析整个内容
                print("[DEBUG] Trying to parse entire content as JSON")
                test_cases = json.loads(ai_content.strip())
                print(f"[DEBUG] Successfully parsed {len(test_cases)} test cases from direct parse")

            # 如果AI返回的数据超过预期数量，截断到 grand_total
            if len(test_cases) > grand_total:
                print(f"[DEBUG] Truncating from {len(test_cases)} to {grand_total} test cases")
                test_cases = test_cases[:grand_total]
            elif len(test_cases) < grand_total:
                # AI返回不够，用模板补齐到 grand_total
                missing = grand_total - len(test_cases)
                print(f"[WARN] AI returned only {len(test_cases)} cases, padding {missing} to reach {grand_total}")
                template_case = test_cases[0] if test_cases else {"case_id": "T001", "type": "positive", "language": "zh"}
                for j in range(missing):
                    padding = dict(template_case)
                    padding["case_id"] = f"PAD{j+1:03d}"
                    test_cases.append(padding)

            # 创建新数据集（始终创建，不支持更新）
            # 优先使用前端传递的数据集名称，否则自动生成
            dataset_name = data.get('dataset_name', '').strip()
            if not dataset_name:
                # 如果没有提供名称，则根据场景描述生成
                dataset_name = f"{scenario[:20]}-LLM评测-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 调试：打印实际生成的数据数量
            print(f"[DEBUG] Creating dataset with record_count={len(test_cases)} (grand_total should be {grand_total})")
            print(f"[DEBUG] Dataset name: {dataset_name}")
            
            dataset = DataFactoryDataset.objects.create(
                name=dataset_name,
                dataset_type='llm_eval',
                business_domain=None,  # 场景描述不应存到业务域枚举字段
                description=f'场景：{scenario[:500]}',
                generation_config=data,
                record_count=len(test_cases),  # 使用实际生成的数据数量
                status='completed',
                created_by=request.user
            )
            
            print(f"[DEBUG] Saved generation_config: {data}")
            print(f"[DEBUG] Scenario in config: {data.get('scenario', 'NOT FOUND')[:100]}...")

            # 保存记录 - 支持动态字段
            records = []
            for case in test_cases:
                # 提取所有字段
                case_id = case.get('case_id', '')
                case_type = case.get('type', 'positive')
                
                # 构建data_content，包含case_id、type和业务字段（排除scenario、内容等场景限定字段）
                data_content = {
                    'case_id': case_id,
                    'type': case_type,
                    # 添加所有业务字段，排除场景限定字段
                    **{k: v for k, v in case.items() if k not in ['case_id', 'type', 'scenario', 'label', '内容', 'content']}
                }
                
                records.append(DataFactoryRecord(
                    dataset=dataset,
                    data_content=data_content,
                    tags=[case_type],
                    difficulty_level='medium'
                ))

            DataFactoryRecord.objects.bulk_create(records)
            
            # 序列化数据集信息返回给前端
            from .serializers import DataFactoryDatasetSerializer
            serializer = DataFactoryDatasetSerializer(dataset)

            return Response({
                'message': f'AI成功生成 {len(test_cases)} 条LLM评测数据',
                'dataset': serializer.data,  # 返回完整的数据集信息
                'total_count': len(test_cases),
                'test_cases': [r.data_content for r in records]  # 返回所有数据，让前端分页
            }, status=status.HTTP_201_CREATED)

        except json.JSONDecodeError as e:
            # 保存AI原始响应到文件,便于调试
            debug_content = None
            try:
                with open('ai_response_debug.txt', 'w', encoding='utf-8') as f:
                    f.write(f"Error: {str(e)}\n\n")
                    f.write(f"AI Content:\n{ai_content}\n\n")
                    f.write(f"JSON Match:\n{json_match.group() if json_match else 'Not found'}")
                debug_content = ai_content[:3000]  # 读取前3000字符
            except:
                pass
            
            return Response(
                {
                    'error': f'AI返回的数据格式错误: {str(e)}',
                    'debug_ai_content': debug_content,
                    'json_match_found': bool(json_match) if 'json_match' in locals() else None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'生成失败: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """导出数据集"""
        dataset = self.get_object()
        format_type = request.query_params.get('format', 'json')
        records = DataFactoryRecord.objects.filter(dataset=dataset)

        if format_type == 'json':
            data = [r.data_content for r in records]
            return Response(data)
        elif format_type == 'sql':
            # 简化版SQL导出
            sql_statements = []
            for record in records[:10]:  # 限制导出数量
                values = ", ".join([f"'{v}'" if isinstance(v, str) else str(v)
                                   for v in record.data_content.values()])
                keys = ", ".join(record.data_content.keys())
                sql_statements.append(f"INSERT INTO table ({keys}) VALUES ({values});")
            return Response('\n'.join(sql_statements))
        else:
            return Response({'error': 'Unsupported format'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def records(self, request, pk=None):
        """获取数据集的所有记录"""
        dataset = self.get_object()
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 20)

        records = DataFactoryRecord.objects.filter(dataset=dataset)
        total = records.count()

        start = (int(page) - 1) * int(page_size)
        end = start + int(page_size)
        records_page = records[start:end]

        serializer = DataFactoryRecordSerializer(records_page, many=True)
        return Response({
            'count': total,
            'results': serializer.data,
            'page': int(page),
            'page_size': int(page_size)
        })

    @action(detail=True, methods=['post'])
    def create_version(self, request, pk=None):
        """创建数据集版本快照"""
        dataset = self.get_object()
        description = request.data.get('description', '')

        # 计算下一个版本号
        last_version = DataFactoryDatasetVersion.objects.filter(
            dataset=dataset
        ).order_by('-version_number').first()

        if last_version:
            version_num = f"v{int(last_version.version_number[1:]) + 1}"
        else:
            version_num = "v1.0"

        # 标记旧版本为非当前版本
        DataFactoryDatasetVersion.objects.filter(
            dataset=dataset, is_current=True
        ).update(is_current=False)

        # 创建新版本
        version = DataFactoryDatasetVersion.objects.create(
            dataset=dataset,
            version_number=version_num,
            description=description,
            snapshot_config=dataset.generation_config,
            snapshot_records_count=dataset.record_count,
            is_current=True,
            parent_version=last_version,
            created_by=request.user
        )

        # 更新主数据集的版本号
        dataset.version = version_num
        dataset.save(update_fields=['version'])

        serializer = DataFactoryDatasetVersionSerializer(version)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def get_versions(self, request, pk=None):
        """获取数据集的所有版本"""
        dataset = self.get_object()
        versions = DataFactoryDatasetVersion.objects.filter(
            dataset=dataset
        ).order_by('-created_at')

        serializer = DataFactoryDatasetVersionSerializer(versions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def rollback(self, request, pk=None):
        """回滚到指定版本"""
        dataset = self.get_object()
        version_id = request.data.get('version_id')

        try:
            target_version = DataFactoryDatasetVersion.objects.get(
                id=version_id, dataset=dataset
            )
        except DataFactoryDatasetVersion.DoesNotExist:
            return Response(
                {'error': '版本不存在'},
                status=status.HTTP_404_NOT_FOUND
            )

        # 恢复配置
        dataset.generation_config = target_version.snapshot_config
        dataset.version = target_version.version_number
        dataset.change_log = f"回滚到版本 {target_version.version_number}: {target_version.description}"
        dataset.save()

        return Response({
            'message': f'成功回滚到版本 {target_version.version_number}',
            'dataset_id': dataset.id
        })

    @action(detail=True, methods=['post'])
    def batch_export(self, request, pk=None):
        """批量导出多个数据集"""
        dataset_ids = request.data.get('dataset_ids', [])
        format_type = request.data.get('format', 'json')

        datasets = DataFactoryDataset.objects.filter(id__in=dataset_ids)
        all_data = []

        for dataset in datasets:
            records = DataFactoryRecord.objects.filter(dataset=dataset)
            dataset_data = {
                'dataset_name': dataset.name,
                'dataset_type': dataset.dataset_type,
                'records': [r.data_content for r in records]
            }
            all_data.append(dataset_data)

        if format_type == 'json':
            return Response(all_data)
        else:
            return Response({'error': 'Unsupported format'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def load_from_template(self, request):
        """从预置模板加载字段定义和边界规则"""
        template_id = request.data.get('template_id')

        try:
            template = PresetTemplate.objects.get(id=template_id, is_active=True)
        except PresetTemplate.DoesNotExist:
            return Response(
                {'error': '模板不存在或已禁用'},
                status=status.HTTP_404_NOT_FOUND
            )

        # 增加使用次数
        template.usage_count += 1
        template.save(update_fields=['usage_count'])

        return Response({
            'template_name': template.name,
            'business_type': template.business_type,
            'field_definitions': template.field_definitions,
            'boundary_rules': template.boundary_rules,
            'faker_mappings': template.faker_mappings
        })


class TemplateViewSet(viewsets.ModelViewSet):
    """模板管理ViewSet（用户数据隔离）"""
    serializer_class = DataFactoryTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return DataFactoryTemplate.objects.all()
        # 个人模板 + 全局模板
        return DataFactoryTemplate.objects.filter(owner=user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, created_by=self.request.user)


class PresetTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """预置模板ViewSet(只读)"""
    queryset = PresetTemplate.objects.filter(is_active=True)
    serializer_class = PresetTemplateSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def by_business_type(self, request):
        """按业务类型获取模板"""
        business_type = request.query_params.get('business_type')
        if business_type:
            templates = PresetTemplate.objects.filter(
                business_type=business_type, is_active=True
            )
        else:
            templates = self.get_queryset()

        serializer = self.get_serializer(templates, many=True)
        return Response(serializer.data)


class UsageLogViewSet(viewsets.ReadOnlyModelViewSet):
    """引用日志ViewSet（用户数据隔离）"""
    serializer_class = DataFactoryUsageLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return DataFactoryUsageLog.objects.all()
        return DataFactoryUsageLog.objects.filter(referenced_by=user)
