"""
Scenario Test Execution Engine
Supports parameter passing between steps and conditional execution
"""
import json
import logging
import requests
from datetime import datetime
from typing import Dict, Any, Optional
from django.utils import timezone
from jsonpath_ng.ext import parse as jsonpath_parse

logger = logging.getLogger(__name__)


class ScenarioExecutionContext:
    """Execution context - passes data between steps"""
    
    def __init__(self):
        self.variables: Dict[str, Any] = {}
        self.step_results: Dict[int, Dict] = {}
        self.current_step: int = 0
    
    def set_variable(self, name: str, value: Any):
        self.variables[name] = value
        logger.info(f"Set variable: {name} = {value}")
    
    def get_variable(self, name: str) -> Optional[Any]:
        return self.variables.get(name)
    
    def add_step_result(self, step_order: int, result: Dict):
        self.step_results[step_order] = result
    
    def should_skip_step(self, step_order: int, skip_on_failure: bool) -> bool:
        if not skip_on_failure:
            return False
        
        for order in range(1, step_order):
            if order in self.step_results:
                if not self.step_results[order].get('success', True):
                    return True
        return False


class ScenarioExecutionEngine:
    """Scenario execution engine"""
    
    def __init__(self, suite_id: int, user_id: int):
        self.suite_id = suite_id
        self.user_id = user_id
        self.context = ScenarioExecutionContext()
        self.execution_result = {
            'suite_id': suite_id,
            'started_at': None,
            'completed_at': None,
            'total_steps': 0,
            'passed_steps': 0,
            'failed_steps': 0,
            'skipped_steps': 0,
            'step_details': [],
            'status': 'pending'
        }
    
    def execute(self) -> Dict[str, Any]:
        from testsuites.models import TestSuite, TestStep
        
        self.execution_result['started_at'] = timezone.now().isoformat()
        self.execution_result['status'] = 'running'
        
        try:
            suite = TestSuite.objects.select_related('created_by').get(id=self.suite_id)
            steps = TestStep.objects.filter(
                suite=suite, 
                enabled=True
            ).select_related('test_case').prefetch_related('output_params').order_by('order')
            
            self.execution_result['total_steps'] = steps.count()
            
            logger.info(f"Executing suite {self.suite_id}: {suite.name} with {steps.count()} steps")
            
            for step in steps:
                step_result = self._execute_step(step)
                self.execution_result['step_details'].append(step_result)
                
                if step_result['status'] == 'passed':
                    self.execution_result['passed_steps'] += 1
                elif step_result['status'] == 'failed':
                    self.execution_result['failed_steps'] += 1
                elif step_result['status'] == 'skipped':
                    self.execution_result['skipped_steps'] += 1
            
            if self.execution_result['failed_steps'] > 0:
                self.execution_result['status'] = 'failed'
            elif self.execution_result['skipped_steps'] > 0:
                self.execution_result['status'] = 'partial'
            else:
                self.execution_result['status'] = 'success'
            
        except Exception as e:
            logger.error(f"Suite execution error: {str(e)}", exc_info=True)
            self.execution_result['status'] = 'error'
            self.execution_result['error'] = str(e)
        
        finally:
            self.execution_result['completed_at'] = timezone.now().isoformat()
        
        return self.execution_result
    
    def _execute_step(self, step) -> Dict[str, Any]:
        step_result = {
            'step_id': step.id,
            'step_order': step.order,
            'test_case_id': step.test_case.id,
            'test_case_title': step.test_case.title,
            'status': 'pending',
            'started_at': None,
            'completed_at': None,
            'duration_ms': 0,
            'error': None,
            'extracted_params': {},
            'response_data': None
        }
        
        started_at = datetime.now()
        step_result['started_at'] = started_at.isoformat()
        
        try:
            if self.context.should_skip_step(step.order, step.skip_on_failure):
                step_result['status'] = 'skipped'
                step_result['error'] = 'Skipped due to previous step failure'
                logger.info(f"Step {step.order} skipped due to previous failure")
                return step_result
            
            test_case = step.test_case
            mapped_headers = self._apply_mapping_to_dict(test_case.headers or {}, step.parameter_mapping)
            mapped_body = self._apply_mapping_to_dict(test_case.request_body or {}, step.parameter_mapping)
            mapped_endpoint = self._replace_variables_in_string(test_case.api_endpoint or '', step.parameter_mapping)
            
            if not mapped_endpoint.startswith('http'):
                mapped_endpoint = f"https://{mapped_endpoint}"
            
            method = (test_case.method or 'GET').upper()
            response = requests.request(
                method=method,
                url=mapped_endpoint,
                headers=mapped_headers,
                json=mapped_body if mapped_body else None,
                timeout=(10, 30),  # (connect_timeout, read_timeout): 连接10s, 读取30s
                allow_redirects=True
            )
            
            step_result['status'] = 'passed'
                
                try:
                    response_data = response.json()
                    step_result['response_data'] = response_data
                    
                    extracted = self._extract_output_params(step, response_data)
                    step_result['extracted_params'] = extracted
                except Exception as e:
                    logger.warning(f"Failed to parse response as JSON: {e}")
                    step_result['response_data'] = response.text[:1000]
                
                expected_response = test_case.expected_response or {}
                if expected_response:
                    try:
                        response_json = response.json() if isinstance(step_result['response_data'], dict) else {}
                        for key, value in expected_response.items():
                            if key not in response_json:
                                step_result['status'] = 'failed'
                                step_result['error'] = f"Response missing field: {key}"
                                break
                    except Exception:
                        pass
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Step {step.order} request error: {str(e)}", exc_info=True)
            step_result['status'] = 'failed'
            step_result['error'] = f"Request failed: {str(e)}"
        
        except Exception as e:
            logger.error(f"Step {step.order} execution error: {str(e)}", exc_info=True)
            step_result['status'] = 'failed'
            step_result['error'] = str(e)
        
        finally:
            completed_at = datetime.now()
            step_result['completed_at'] = completed_at.isoformat()
            step_result['duration_ms'] = int((completed_at - started_at).total_seconds() * 1000)
            
            self.context.add_step_result(step.order, step_result)
        
        return step_result
    
    def _apply_mapping_to_dict(self, data: Dict, mapping: Dict) -> Dict:
        if not mapping:
            return data
        
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self._replace_variables_in_string(value, mapping)
            elif isinstance(value, dict):
                result[key] = self._apply_mapping_to_dict(value, mapping)
            elif isinstance(value, list):
                result[key] = [
                    self._replace_variables_in_string(item, mapping) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                result[key] = value
        
        return result
    
    def _replace_variables_in_string(self, text: str, mapping: Dict) -> str:
        import re
        
        def replace_match(match):
            var_name = match.group(1).strip()
            
            if var_name in mapping:
                mapped_value = mapping[var_name]
                if isinstance(mapped_value, str):
                    nested_match = re.match(r'\{\{([^}]+)\}\}', mapped_value.strip())
                    if nested_match:
                        inner_var = nested_match.group(1).strip()
                        value = self.context.get_variable(inner_var)
                        return str(value) if value is not None else mapped_value
                return str(mapped_value)
            else:
                value = self.context.get_variable(var_name)
                return str(value) if value is not None else match.group(0)
        
        pattern = r'\{\{([^}]+)\}\}'
        return re.sub(pattern, replace_match, text)
    
    def _extract_output_params(self, step, response_data: Any) -> Dict[str, Any]:
        extracted = {}
        
        try:
            for param in step.output_params.all():
                try:
                    jsonpath_expr = jsonpath_parse(param.json_path)
                    matches = jsonpath_expr.find(response_data)
                    
                    if matches:
                        value = matches[0].value
                        self.context.set_variable(param.param_name, value)
                        extracted[param.param_name] = value
                        logger.info(f"Extracted param {param.param_name} = {value}")
                    else:
                        logger.warning(f"JSONPath {param.json_path} did not match any value")
                        extracted[param.param_name] = None
                        
                except Exception as e:
                    logger.error(f"Error extracting param {param.param_name}: {str(e)}")
                    extracted[param.param_name] = None
        
        except Exception as e:
            logger.error(f"Error processing output params: {str(e)}")
        
        return extracted
