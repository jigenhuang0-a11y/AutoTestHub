"""
质量数字人 - 质检引擎
支持功能测试和接口测试两种场景
"""
import re
from difflib import SequenceMatcher
from typing import List, Dict, Any, Tuple


class QualityCheckEngine:
    """质量检查引擎 - 支持功能测试/接口测试场景"""

    # ==================== 通用字段定义 ====================
    REQUIRED_FIELDS_COMMON = {
        'title': ['用例标题', '标题', 'title', 'name', '用例名称', '接口名称'],
        'priority': ['优先级', 'priority', '等级', 'level', 'severity'],
    }

    # 功能测试专属
    REQUIRED_FIELDS_FUNC = {
        'steps': ['测试步骤', '步骤', 'steps', '操作步骤', 'test_steps'],
        'expected': ['预期结果', '预期', 'expected', 'expected_result', '期望结果'],
        'precondition': ['前置条件', '前提条件', 'precondition', 'pre_condition'],
    }

    # 接口测试专属
    REQUIRED_FIELDS_API = {
        'url': ['请求地址', 'URL', 'url', '接口地址', 'api', 'path', 'endpoint', '请求URL'],
        'method': ['请求方法', 'method', '请求方式', 'http_method', '请求类型'],
        'request_params': ['请求参数', '参数', 'params', 'request_body', '请求体', 'body', '入参', '请求参数/请求体'],
        'expected_response': ['预期响应', '响应断言', '断言', 'assertions', 'expected_response', 
                              'response_check', '校验点', '响应结果', '预期状态码', '断言校验规则'],
    }

    # ==================== 扣分规则 ====================
    # 通用规则
    COMMON_RULES = {
        'missing_title': {'score': -20, 'severity': 'high', 'msg': '缺少用例/接口标题'},
        'title_too_short': {'score': -10, 'severity': 'medium', 'msg': '标题过短(少于5字)'},
        'title_too_vague': {'score': -15, 'severity': 'medium', 'msg': '标题过于模糊，缺少关键信息'},
        'missing_priority': {'score': -8, 'severity': 'low', 'msg': '缺少优先级'},
        'vague_content': {'score': -15, 'severity': 'high', 'msg': '内容描述模糊，缺少具体验证点'},
    }

    # 功能测试规则
    FUNC_RULES = {
        'missing_steps': {'score': -25, 'severity': 'critical', 'msg': '缺少测试步骤'},
        'missing_expected': {'score': -25, 'severity': 'critical', 'msg': '缺少预期结果'},
        'missing_precondition': {'score': -10, 'severity': 'low', 'msg': '缺少前置条件'},
        'steps_too_few': {'score': -10, 'severity': 'medium', 'msg': '测试步骤过少(建议至少2步)'},
        'steps_format_issue': {'score': -5, 'severity': 'low', 'msg': '步骤格式不规范(建议编号)'},
        'expected_too_short': {'score': -10, 'severity': 'medium', 'msg': '预期结果描述过短'},
        'no_verification': {'score': -15, 'severity': 'high', 'msg': '缺少明确的验证条件'},
        'inconsistent_steps_expected': {'score': -8, 'severity': 'medium', 'msg': '步骤数与预期结果数不匹配'},
        'no_boundary_test': {'score': -5, 'severity': 'low', 'msg': '未考虑边界条件测试'},
        'no_error_scenario': {'score': -5, 'severity': 'low', 'msg': '未考虑异常/错误场景'},
    }

    # 接口测试规则
    API_RULES = {
        'missing_url': {'score': -15, 'severity': 'critical', 'msg': '缺少请求URL'},
        'missing_method': {'score': -10, 'severity': 'critical', 'msg': '缺少请求方法(GET/POST等)'},
        'missing_request_params': {'score': -10, 'severity': 'high', 'msg': '缺少请求参数定义'},
        'missing_expected_response': {'score': -15, 'severity': 'critical', 'msg': '缺少预期响应/断言'},
        'invalid_url': {'score': -5, 'severity': 'medium', 'msg': 'URL格式不规范'},
        'invalid_method': {'score': -5, 'severity': 'medium', 'msg': '请求方法不在标准范围内'},
        'no_status_check': {'score': -8, 'severity': 'high', 'msg': '未校验HTTP状态码'},
        'no_response_body_check': {'score': -8, 'severity': 'high', 'msg': '未校验响应体关键字段'},
        'params_no_type': {'score': -3, 'severity': 'low', 'msg': '请求参数缺少类型说明'},
        'params_no_required_mark': {'score': -3, 'severity': 'low', 'msg': '请求参数未标注必填/选填'},
        'no_error_code_check': {'score': -5, 'severity': 'medium', 'msg': '未覆盖异常状态码/错误码场景'},
        'no_header_check': {'score': -3, 'severity': 'low', 'msg': '未校验关键响应头(Content-Type等)'},
    }

    # 模糊关键词
    VAGUE_KEYWORDS = [
        '正常', '正确', '没问题', 'OK', '可以', '能', '应该',
        '大概', '可能', '差不多', '基本', '一般', '简单', '返回成功',
        '返回失败', '返回正确',
    ]

    QUALITY_KEYWORDS = [
        '验证', '检查', '确认', '断言', '等于', '包含', '匹配',
        '大于', '小于', '不等于', '边界', '异常', '错误',
        '空值', '超长', '特殊字符', 'status_code', 'code',
    ]

    VALID_HTTP_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']

    def __init__(self, scenario='general', check_duplicates=True,
                 check_completeness=True, check_format=True,
                 check_content_quality=True, duplicate_threshold=0.85):
        """
        scenario: 'general'(功能测试) / 'api'(接口测试)
        """
        self.scenario = scenario
        self.check_duplicates = check_duplicates
        self.check_completeness = check_completeness
        self.check_format = check_format
        self.check_content_quality = check_content_quality
        self.duplicate_threshold = duplicate_threshold

    def run_check(self, testcases: List[Dict]) -> List[Dict]:
        """批量质检"""
        results = []
        all_texts = []

        if self.check_duplicates:
            for tc in testcases:
                all_texts.append(self._extract_full_text(tc))

        for i, tc in enumerate(testcases):
            result = self._check_single(tc, i, all_texts if self.check_duplicates else None)
            results.append(result)

        return results

    def _check_single(self, testcase: Dict, index: int,
                       all_texts: List[str] = None) -> Dict:
        """检查单个用例"""
        title = self._get_field(testcase, self.REQUIRED_FIELDS_COMMON['title']) or f'用例{index + 1}'
        issues = []
        suggestions = []

        completeness_score = 40.0
        format_score = 20.0
        content_score = 40.0

        # 1. 完整性检查
        if self.check_completeness:
            completeness_score, c_issues, c_suggestions = self._check_completeness(testcase)
            issues.extend(c_issues)
            suggestions.extend(c_suggestions)

        # 2. 格式规范检查
        if self.check_format:
            format_score, f_issues, f_suggestions = self._check_format(testcase)
            issues.extend(f_issues)
            suggestions.extend(f_suggestions)

        # 3. 内容质量检查
        if self.check_content_quality:
            content_score, q_issues, q_suggestions = self._check_content_quality(testcase)
            issues.extend(q_issues)
            suggestions.extend(q_suggestions)

        total_score = round(completeness_score + format_score + content_score, 1)
        total_score = max(0, min(100, total_score))

        # 等级
        if total_score >= 80:
            level = 'pass'
        elif total_score >= 60:
            level = 'warning'
        else:
            level = 'fail'

        # 4. 重复检查
        duplicate_of = ''
        duplicate_similarity = 0.0
        if self.check_duplicates and all_texts and len(all_texts) > 1:
            for j in range(len(all_texts)):
                if j == index:
                    continue
                sim = SequenceMatcher(None, all_texts[index], all_texts[j]).ratio()
                if sim >= self.duplicate_threshold and sim > duplicate_similarity:
                    duplicate_similarity = round(sim, 3)
                    duplicate_of = f'用例{j + 1}'
            if duplicate_of:
                issues.append({
                    'type': 'duplicate', 'severity': 'high',
                    'message': f'与{duplicate_of}高度相似({duplicate_similarity*100:.1f}%)，疑似重复',
                    'detail': f'相似度: {duplicate_similarity*100:.1f}%'
                })
                suggestions.append({
                    'type': 'duplicate',
                    'message': f'建议合并或删除重复用例，保留其中一个'
                })
                total_score = max(0, total_score - 15)
                if total_score < 60:
                    level = 'fail'

        return {
            'case_id': self._get_field(testcase, ['用例编号', 'case_id', 'id', '编号']) or '',
            'case_title': title,
            'case_content': testcase,
            'score': total_score,
            'level': level,
            'completeness_score': completeness_score,
            'format_score': format_score,
            'content_score': content_score,
            'issues': issues,
            'suggestions': suggestions,
            'duplicate_of': duplicate_of,
            'duplicate_similarity': duplicate_similarity,
        }

    # ==================== 完整性检查 ====================
    def _check_completeness(self, tc: Dict) -> Tuple[float, List, List]:
        score = 40.0
        issues = []
        suggestions = []

        # 通用字段
        title = self._get_field(tc, self.REQUIRED_FIELDS_COMMON['title'])
        priority = self._get_field(tc, self.REQUIRED_FIELDS_COMMON['priority'])

        if not title:
            score += self.COMMON_RULES['missing_title']['score']
            issues.append(self._issue('completeness', self.COMMON_RULES['missing_title']))
            suggestions.append(self._suggest('completeness', '请添加清晰的标题，描述测试目标'))
        if not priority:
            score += self.COMMON_RULES['missing_priority']['score']
            issues.append(self._issue('completeness', self.COMMON_RULES['missing_priority']))
            suggestions.append(self._suggest('completeness', '请标注优先级(P0/P1/P2/P3)'))

        if self.scenario == 'api':
            score, issues, suggestions = self._api_completeness(tc, score, issues, suggestions)
        else:
            score, issues, suggestions = self._func_completeness(tc, score, issues, suggestions)

        return max(0, score), issues, suggestions

    def _func_completeness(self, tc, score, issues, suggestions):
        steps = self._get_field(tc, self.REQUIRED_FIELDS_FUNC['steps'])
        expected = self._get_field(tc, self.REQUIRED_FIELDS_FUNC['expected'])
        precondition = self._get_field(tc, self.REQUIRED_FIELDS_FUNC['precondition'])

        if not steps:
            score += self.FUNC_RULES['missing_steps']['score']
            issues.append(self._issue('completeness', self.FUNC_RULES['missing_steps']))
            suggestions.append(self._suggest('completeness', '请添加详细测试步骤，按操作顺序编号'))
        if not expected:
            score += self.FUNC_RULES['missing_expected']['score']
            issues.append(self._issue('completeness', self.FUNC_RULES['missing_expected']))
            suggestions.append(self._suggest('completeness', '请为每个步骤添加明确的预期结果'))
        if not precondition:
            score += self.FUNC_RULES['missing_precondition']['score']
            issues.append(self._issue('completeness', self.FUNC_RULES['missing_precondition']))
            suggestions.append(self._suggest('completeness', '建议补充前置条件(登录状态、数据准备等)'))
        return score, issues, suggestions

    def _api_completeness(self, tc, score, issues, suggestions):
        url = self._get_field(tc, self.REQUIRED_FIELDS_API['url'])
        method = self._get_field(tc, self.REQUIRED_FIELDS_API['method'])
        params = self._get_field(tc, self.REQUIRED_FIELDS_API['request_params'])
        expected_resp = self._get_field(tc, self.REQUIRED_FIELDS_API['expected_response'])

        if not url:
            score += self.API_RULES['missing_url']['score']
            issues.append(self._issue('completeness', self.API_RULES['missing_url']))
            suggestions.append(self._suggest('completeness', '请填写接口请求URL'))
        if not method:
            score += self.API_RULES['missing_method']['score']
            issues.append(self._issue('completeness', self.API_RULES['missing_method']))
            suggestions.append(self._suggest('completeness', '请填写HTTP请求方法(GET/POST/PUT/DELETE等)'))
        if not params:
            score += self.API_RULES['missing_request_params']['score']
            issues.append(self._issue('completeness', self.API_RULES['missing_request_params']))
            suggestions.append(self._suggest('completeness', '请补充请求参数定义(参数名、类型、必填等)'))
        if not expected_resp:
            score += self.API_RULES['missing_expected_response']['score']
            issues.append(self._issue('completeness', self.API_RULES['missing_expected_response']))
            suggestions.append(self._suggest('completeness', '请补充预期响应和断言条件(状态码、关键字段等)'))
        return score, issues, suggestions

    # ==================== 格式规范检查 ====================
    def _check_format(self, tc: Dict) -> Tuple[float, List, List]:
        score = 20.0
        issues = []
        suggestions = []

        title = self._get_field(tc, self.REQUIRED_FIELDS_COMMON['title'])

        if not title:
            # 缺少标题已在完整性检查中扣分，这里不再重复
            pass
        elif len(str(title)) < 3:
            score += self.COMMON_RULES['title_too_short']['score']
            issues.append(self._issue('format', self.COMMON_RULES['title_too_short']))
            suggestions.append(self._suggest('format', '标题建议10-50字，清晰描述测试场景'))
        elif len(str(title)) < 5:
            score += -5
            issues.append(self._issue('format', {'score': -5, 'severity': 'medium', 'msg': '标题过短(少于5字)'}))
            suggestions.append(self._suggest('format', '标题建议10-50字，清晰描述测试场景'))

        if title and any(kw in str(title) for kw in self.VAGUE_KEYWORDS):
            score += self.COMMON_RULES['title_too_vague']['score']
            issues.append(self._issue('format', self.COMMON_RULES['title_too_vague']))
            suggestions.append(self._suggest('format', '标题应具体描述测试对象和预期行为'))
        
        # 检测无意义的标题（纯数字、纯字母、重复字符等）
        if title:
            title_str = str(title).strip()
            if title_str and (title_str.isdigit() or 
                              (len(title_str) <= 3 and title_str.isalpha()) or
                              len(set(title_str)) <= 2):
                score += -15
                issues.append(self._issue('format', {'score': -15, 'severity': 'high', 'msg': '标题无意义（纯数字、过短或无信息量）'}))
                suggestions.append(self._suggest('format', '标题应描述具体的测试场景和目标'))

        if self.scenario == 'api':
            score, issues, suggestions = self._api_format(tc, score, issues, suggestions)
        else:
            score, issues, suggestions = self._func_format(tc, score, issues, suggestions)

        return max(0, score), issues, suggestions

    def _func_format(self, tc, score, issues, suggestions):
        steps = self._get_field(tc, self.REQUIRED_FIELDS_FUNC['steps'])
        expected = self._get_field(tc, self.REQUIRED_FIELDS_FUNC['expected'])

        if steps:
            step_list = self._parse_steps(steps)
            if len(step_list) < 2:
                score += self.FUNC_RULES['steps_too_few']['score']
                issues.append(self._issue('format', self.FUNC_RULES['steps_too_few']))
                suggestions.append(self._suggest('format', '建议至少2个测试步骤，覆盖主流程和分支'))
            if not any(re.match(r'^\d', s.strip()) for s in step_list):
                score += self.FUNC_RULES['steps_format_issue']['score']
                issues.append(self._issue('format', self.FUNC_RULES['steps_format_issue']))
                suggestions.append(self._suggest('format', '建议用"1. 2. 3."对步骤进行编号'))
            if expected:
                exp_list = self._parse_steps(expected)
                if len(exp_list) < len(step_list):
                    score += self.FUNC_RULES['inconsistent_steps_expected']['score']
                    issues.append(self._issue('format', self.FUNC_RULES['inconsistent_steps_expected']))
                    suggestions.append(self._suggest('format', '每个步骤应有对应的预期结果'))

        if expected and len(str(expected)) < 10:
            score += self.FUNC_RULES['expected_too_short']['score']
            issues.append(self._issue('format', self.FUNC_RULES['expected_too_short']))
            suggestions.append(self._suggest('format', '预期结果应具体描述期望的行为或数据变化'))
        return score, issues, suggestions

    def _api_format(self, tc, score, issues, suggestions):
        url = self._get_field(tc, self.REQUIRED_FIELDS_API['url'])
        method = self._get_field(tc, self.REQUIRED_FIELDS_API['method'])

        if url and not re.match(r'^https?://|^/', str(url)):
            score += self.API_RULES['invalid_url']['score']
            issues.append(self._issue('format', self.API_RULES['invalid_url']))
            suggestions.append(self._suggest('format', 'URL应以 http(s):// 或 / 开头'))
        if method and str(method).upper() not in self.VALID_HTTP_METHODS:
            score += self.API_RULES['invalid_method']['score']
            issues.append(self._issue('format', self.API_RULES['invalid_method']))
            suggestions.append(self._suggest('format', f'请求方法应为: {", ".join(self.VALID_HTTP_METHODS)}'))
        return score, issues, suggestions

    # ==================== 内容质量检查 ====================
    def _check_content_quality(self, tc: Dict) -> Tuple[float, List, List]:
        score = 40.0
        issues = []
        suggestions = []

        full_text = self._extract_full_text(tc)
        title = self._get_field(tc, self.REQUIRED_FIELDS_COMMON['title'])

        if title and any(kw in str(title) for kw in self.VAGUE_KEYWORDS):
            score += self.COMMON_RULES['vague_content']['score']
            issues.append(self._issue('content', self.COMMON_RULES['vague_content']))
            suggestions.append(self._suggest('content', '使用具体明确的验证描述，如"验证返回status_code=200"'))

        quality_count = sum(1 for kw in self.QUALITY_KEYWORDS if kw in str(full_text).lower())
        if quality_count < 2:
            score += self.COMMON_RULES['vague_content']['score']
            issues.append(self._issue('content', self.COMMON_RULES['vague_content']))
            suggestions.append(self._suggest('content', '建议添加明确的验证关键词(验证/检查/断言/等于/包含等)'))

        if self.scenario == 'api':
            score, issues, suggestions = self._api_content_quality(tc, score, issues, suggestions)
        else:
            score, issues, suggestions = self._func_content_quality(tc, score, issues, suggestions)

        return max(0, score), issues, suggestions

    def _func_content_quality(self, tc, score, issues, suggestions):
        full_text = self._extract_full_text(tc)
        steps = self._get_field(tc, self.REQUIRED_FIELDS_FUNC['steps'])
        expected = self._get_field(tc, self.REQUIRED_FIELDS_FUNC['expected'])
        title = self._get_field(tc, self.REQUIRED_FIELDS_COMMON['title'])

        # 步骤内容质量检查
        if steps:
            steps_str = str(steps).strip()
            # 检测步骤是否过于模糊
            if len(steps_str) < 10 or any(kw in steps_str for kw in ['点一下', '看看', '试试', '操作', '测试', '执行', '走一下', '跑一下']):
                score += -12
                issues.append(self._issue('content', {'score': -12, 'severity': 'high', 'msg': '测试步骤描述过于模糊，缺少具体操作'}))
                suggestions.append(self._suggest('content', '步骤应具体描述操作对象和方式，如"点击登录按钮"'))
            # 检测步骤是否只有编号无内容
            step_list = self._parse_steps(steps)
            if step_list and all(len(s) <= 5 for s in step_list):
                score += -10
                issues.append(self._issue('content', {'score': -10, 'severity': 'high', 'msg': '测试步骤内容过短，缺少具体操作描述'}))
                suggestions.append(self._suggest('content', '每个步骤应包含具体操作和输入数据'))
        
        # 预期结果内容质量检查
        if expected:
            exp_str = str(expected).strip()
            if len(exp_str) < 10 or any(kw in exp_str for kw in ['成功', '正常', 'OK', '可以', '没问题']):
                score += -12
                issues.append(self._issue('content', {'score': -12, 'severity': 'high', 'msg': '预期结果描述过于模糊'}))
                suggestions.append(self._suggest('content', '预期结果应具体描述界面变化、数据状态或提示信息'))
        
        # 标题与步骤重复检查
        if title and steps:
            if str(title).strip() == str(steps).strip():
                score += -10
                issues.append(self._issue('content', {'score': -10, 'severity': 'high', 'msg': '用例标题与测试步骤内容重复'}))
                suggestions.append(self._suggest('content', '标题应概括测试目标，步骤应描述具体操作'))

        if not any(kw in str(full_text).lower() for kw in ['边界', '异常', '错误', '空值', '超长']):
            score += self.FUNC_RULES['no_boundary_test']['score']
            issues.append(self._issue('content', self.FUNC_RULES['no_boundary_test']))
            suggestions.append(self._suggest('content', '建议增加边界值测试(空值/超长/特殊字符等)'))

        if not any(kw in str(full_text).lower() for kw in ['异常', '错误', '失败', 'error', 'exception']):
            score += self.FUNC_RULES['no_error_scenario']['score']
            issues.append(self._issue('content', self.FUNC_RULES['no_error_scenario']))
            suggestions.append(self._suggest('content', '建议补充异常场景测试(网络异常/超时/权限不足等)'))
        return score, issues, suggestions

    def _api_content_quality(self, tc, score, issues, suggestions):
        expected_resp = self._get_field(tc, self.REQUIRED_FIELDS_API['expected_response'])
        resp_text = str(expected_resp).lower() if expected_resp else ''
        params = self._get_field(tc, self.REQUIRED_FIELDS_API['request_params'])
        params_text = str(params).lower() if params else ''

        if not any(kw in resp_text for kw in ['status_code', '状态码', 'http状态', 'code']):
            score += self.API_RULES['no_status_check']['score']
            issues.append(self._issue('content', self.API_RULES['no_status_check']))
            suggestions.append(self._suggest('content', '请添加HTTP状态码校验(如status_code=200/400/500)'))

        if not any(kw in resp_text for kw in ['body', '响应体', '字段', 'field', 'data', 'msg', 'message']):
            score += self.API_RULES['no_response_body_check']['score']
            issues.append(self._issue('content', self.API_RULES['no_response_body_check']))
            suggestions.append(self._suggest('content', '请校验响应体关键字段(如 code、data、message)'))

        if params_text and not any(kw in params_text for kw in ['类型', 'type', '必填', 'required', 'string', 'int']):
            score += self.API_RULES['params_no_type']['score']
            issues.append(self._issue('content', self.API_RULES['params_no_type']))
            suggestions.append(self._suggest('content', '请求参数建议标注类型(string/int/boolean等)和是否必填'))

        if not any(kw in resp_text for kw in ['401', '403', '404', '500', '错误码', 'error_code']):
            score += self.API_RULES['no_error_code_check']['score']
            issues.append(self._issue('content', self.API_RULES['no_error_code_check']))
            suggestions.append(self._suggest('content', '建议覆盖异常场景(401/403/404/500等错误状态码)'))
        return score, issues, suggestions

    # ==================== 工具方法 ====================
    def _get_field(self, tc: Dict, field_names: List[str]) -> Any:
        """根据多种可能的字段名获取值"""
        for name in field_names:
            # 精确匹配
            if name in tc and tc[name]:
                return tc[name]
            # 小写匹配
            lower_name = name.lower()
            for key in tc:
                if key.lower() == lower_name and tc[key]:
                    return tc[key]
        return None

    def _parse_steps(self, steps) -> List[str]:
        """解析步骤文本为列表"""
        text = str(steps) if steps else ''
        # 按数字编号或换行分割
        parts = re.split(r'\n|(?<=\d)[.、．)\s]', text)
        return [p.strip() for p in parts if p.strip() and len(p.strip()) > 2]

    def _extract_full_text(self, tc: Dict) -> str:
        """提取用例全文用于相似度比较"""
        parts = []
        for key, val in tc.items():
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, (list, dict)):
                parts.append(str(val))
        return ' '.join(parts)

    def _issue(self, issue_type: str, rule: Dict) -> Dict:
        return {'type': issue_type, 'severity': rule['severity'], 'message': rule['msg']}

    def _suggest(self, suggest_type: str, message: str) -> Dict:
        return {'type': suggest_type, 'message': message}
