"""
变量绑定工具 — 将生成的数据绑定到测试用例变量

功能：
1. 智能匹配变量名 → 数据字段名
2. 绑定到 TestCase.global_vars / context_vars
3. 记录引用日志 (DataFactoryUsageLog)
"""
import logging
from typing import List, Dict, Any, Optional

from core.tools import BaseTool

logger = logging.getLogger(__name__)


class VariableBindingTool(BaseTool):
    """
    变量绑定工具

    将数据集中的字段值，智能绑定到测试用例的 global_vars / context_vars。

    绑定规则：
    1. 精确匹配：变量名 == 字段名
    2. 语义匹配：通过 Common Matches 映射（如 username → name）
    3. 手动映射：用户显式指定的映射关系
    """

    name = "variable_binding"
    description = "将生成的数据绑定到测试用例的变量上，支持智能名称匹配和手动映射"

    # 常见变量名 → 数据字段名的语义映射
    SEMANTIC_MAP = {
        "username": ["name", "user_name", "account"],
        "password": ["pwd", "pass", "secret"],
        "token": ["access_token", "auth_token", "jwt"],
        "email": ["mail", "user_email", "contact_email"],
        "phone": ["mobile", "tel", "phone_number", "contact"],
        "user_id": ["id", "uid", "member_id"],
        "order_id": ["order_no", "order_num", "trade_id"],
        "amount": ["price", "total", "pay_amount", "sum"],
        "address": ["addr", "location", "shipping_address"],
        "timestamp": ["time", "date", "created_at", "ts"],
        "status": ["state", "order_status", "result"],
        "sku": ["product_id", "item_id", "goods_id"],
    }

    def __init__(self, user_id: int = None):
        super().__init__()
        self.user_id = user_id

    def execute(self, **kwargs) -> dict:
        """执行变量绑定"""
        testcase_id = kwargs.get("testcase_id")
        dataset_id = kwargs.get("dataset_id")
        record_index = kwargs.get("record_index", 0)
        field_mapping = kwargs.get("field_mapping", {})

        if not testcase_id:
            return {"success": False, "error": "testcase_id 是必填参数"}

        return self.bind_to_testcase(
            testcase_id=testcase_id,
            dataset_id=dataset_id,
            record_index=record_index,
            field_mapping=field_mapping,
        )

    def bind_to_testcase(
        self,
        testcase_id: int,
        dataset_id: Optional[int] = None,
        record_index: int = 0,
        field_mapping: Optional[Dict[str, str]] = None,
    ) -> dict:
        """
        将数据绑定到测试用例

        Args:
            testcase_id: 测试用例 ID
            dataset_id: 数据集 ID（从中取第 record_index 条记录）
            record_index: 使用第几条记录（0-based）
            field_mapping: 手动映射 {"变量名": "数据字段名"}

        Returns:
            {"success": bool, "bound_variables": {...}, "error": str}
        """
        try:
            from testcases.models import TestCase

            testcase = TestCase.objects.get(id=testcase_id)

            # 获取用例定义的变量
            target_vars = self._get_target_variables(testcase)
            if not target_vars:
                return {"success": False, "error": "该用例没有定义变量"}

            # 获取记录数据
            record_data = self._get_record_data(dataset_id, record_index) if dataset_id else {}

            # 合并手动映射
            mapping = dict(field_mapping or {})

            # 智能绑定
            bound = {}
            unmatched = []
            for var_name in target_vars:
                # 1. 手动映射优先
                if var_name in mapping:
                    data_key = mapping[var_name]
                    if data_key in record_data:
                        bound[var_name] = record_data[data_key]
                        continue

                # 2. 精确匹配
                if var_name in record_data:
                    bound[var_name] = record_data[var_name]
                    continue

                # 3. 语义匹配
                matched = self._semantic_match(var_name, record_data)
                if matched:
                    bound[var_name] = matched
                    continue

                unmatched.append(var_name)

            # 写入 TestCase
            self._write_variables(testcase, bound)

            # 记录引用日志
            if dataset_id:
                self._log_usage(dataset_id, testcase_id, list(bound.keys()))

            return {
                "success": True,
                "testcase_id": testcase_id,
                "bound_variables": bound,
                "bound_count": len(bound),
                "total_variables": len(target_vars),
                "unmatched": unmatched,
            }

        except TestCase.DoesNotExist:
            return {"success": False, "error": f"用例 #{testcase_id} 不存在"}
        except Exception as e:
            logger.error(f"[VariableBinding] 绑定失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def bind_batch(
        self,
        testcase_ids: List[int],
        dataset_id: int,
        field_mapping: Optional[Dict[str, str]] = None,
    ) -> list:
        """
        批量绑定：每条用例绑定数据集中的一条记录（按索引对应）
        
        Returns:
            List[dict] 每条用例的绑定结果
        """
        results = []
        for i, tc_id in enumerate(testcase_ids):
            result = self.bind_to_testcase(
                testcase_id=tc_id,
                dataset_id=dataset_id,
                record_index=i,
                field_mapping=field_mapping,
            )
            results.append(result)
        return results

    # ============================================================
    # 内部方法
    # ============================================================

    def _get_target_variables(self, testcase) -> List[str]:
        """提取测试用例中定义的所有变量名"""
        var_names = []
        for var_def in (testcase.global_vars or []):
            if isinstance(var_def, dict):
                var_names.append(var_def.get("name", var_def.get("key", "")))
            elif isinstance(var_def, str):
                var_names.append(var_def)
        for var_def in (testcase.context_vars or []):
            if isinstance(var_def, dict):
                var_names.append(var_def.get("name", var_def.get("key", "")))
            elif isinstance(var_def, str):
                var_names.append(var_def)
        return [v for v in var_names if v]

    def _get_record_data(self, dataset_id: Optional[int], index: int) -> dict:
        """获取数据集的第 index 条记录"""
        if not dataset_id:
            return {}

        try:
            from data_factory.models import DataFactoryRecord
            records = list(
                DataFactoryRecord.objects
                .filter(dataset_id=dataset_id)
                .order_by("id")[index:index + 1]
            )
            if records:
                return records[0].data_content or {}
        except Exception as e:
            logger.warning(f"[VariableBinding] 读取记录失败: {e}")

        return {}

    def _semantic_match(self, var_name: str, record_data: dict) -> Optional[Any]:
        """语义匹配变量名到数据字段"""
        var_lower = var_name.lower()
        candidates = self.SEMANTIC_MAP.get(var_lower, [])

        for candidate in candidates:
            if candidate in record_data:
                return record_data[candidate]

        # 模糊匹配：包含关系
        for key in record_data:
            if var_lower in key.lower() or key.lower() in var_lower:
                return record_data[key]

        return None

    def _write_variables(self, testcase, bound: dict):
        """将绑定的变量值写回 TestCase"""
        # 更新 global_vars 中的值
        updated_global = []
        for var_def in (testcase.global_vars or []):
            if isinstance(var_def, dict):
                name = var_def.get("name", var_def.get("key", ""))
                if name in bound:
                    var_def = {**var_def, "value": bound[name]}
            updated_global.append(var_def)

        # 更新 context_vars 中的值
        updated_context = []
        for var_def in (testcase.context_vars or []):
            if isinstance(var_def, dict):
                name = var_def.get("name", var_def.get("key", ""))
                if name in bound:
                    var_def = {**var_def, "value": bound[name]}
            updated_context.append(var_def)

        testcase.global_vars = updated_global
        testcase.context_vars = updated_context
        testcase.save(update_fields=["global_vars", "context_vars"])

    def _log_usage(self, dataset_id: int, testcase_id: int, field_names: List[str]):
        """记录数据集引用日志"""
        try:
            from data_factory.models import DataFactoryDataset, DataFactoryUsageLog
            from django.contrib.auth import get_user_model

            User = get_user_model()
            kwargs = {
                "dataset_id": dataset_id,
                "testcase_id": testcase_id,
                "referenced_fields": field_names,
                "reference_type": "request_param",
            }
            if self.user_id:
                try:
                    kwargs["referenced_by"] = User.objects.get(id=self.user_id)
                except User.DoesNotExist:
                    pass

            # 仅在未记录时创建
            DataFactoryUsageLog.objects.get_or_create(
                dataset_id=dataset_id,
                testcase_id=testcase_id,
                defaults=kwargs,
            )
        except Exception as e:
            logger.warning(f"[VariableBinding] 记录引用日志失败: {e}")

    def _get_parameters_schema(self) -> dict:
        return {
            "testcase_id": {"type": "integer", "description": "测试用例 ID"},
            "dataset_id": {"type": "integer", "description": "数据集 ID"},
            "record_index": {"type": "integer", "description": "使用第几条记录 (0-based)", "default": 0},
            "field_mapping": {
                "type": "object",
                "description": "手动映射: {{'变量名': '数据字段名'}}",
            },
        }

    def _get_required_params(self) -> list:
        return ["testcase_id"]
