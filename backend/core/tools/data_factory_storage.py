"""
数据工厂存储工具 — 将生成的数据写入 DataFactoryDataset + DataFactoryRecord
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from core.tools import BaseTool

logger = logging.getLogger(__name__)


@dataclass
class DatasetCreateResult:
    """数据集创建结果"""
    success: bool
    dataset_id: Optional[int] = None
    dataset_name: str = ""
    record_count: int = 0
    error: str = ""


@dataclass
class VariableBindingResult:
    """变量绑定结果"""
    success: bool
    dataset_id: Optional[int] = None
    testcase_id: Optional[int] = None
    bound_variables: Dict[str, Any] = field(default_factory=dict)
    error: str = ""


class DataFactoryStorageTool(BaseTool):
    """
    数据工厂存储工具

    功能：
    - 创建数据集 (DataFactoryDataset)
    - 批量写入数据记录 (DataFactoryRecord)
    - 记录引用日志 (DataFactoryUsageLog)
    """

    name = "data_factory_storage"
    description = "将生成的测试数据写入数据集和数据记录表"

    def __init__(self, user_id: int = None):
        super().__init__()
        self.user_id = user_id

    def execute(self, **kwargs) -> dict:
        """执行存储"""
        action = kwargs.get("action", "create_dataset")
        # MCP 注册名是 data_generate，映射为 create_dataset
        if action == "data_generate":
            action = "create_dataset"
        if action == "create_dataset":
            return self._create_dataset(**kwargs)
        elif action == "add_records":
            return self._add_records(**kwargs)
        else:
            return {"error": f"未知操作: {action}"}

    def create_dataset(
        self,
        name: str,
        dataset_type: str = "structured",
        business_domain: str = "",
        description: str = "",
        generation_config: dict = None,
    ) -> DatasetCreateResult:
        """创建数据集"""
        try:
            from data_factory.models import DataFactoryDataset
            from django.contrib.auth import get_user_model

            User = get_user_model()
            kwargs = {
                "name": name,
                "dataset_type": dataset_type,
                "business_domain": business_domain,
                "description": description,
                "generation_config": generation_config or {},
                "status": "generating",
            }

            if self.user_id:
                try:
                    kwargs["created_by"] = User.objects.get(id=self.user_id)
                except User.DoesNotExist:
                    pass

            dataset = DataFactoryDataset.objects.create(**kwargs)

            return DatasetCreateResult(
                success=True,
                dataset_id=dataset.id,
                dataset_name=dataset.name,
            )

        except Exception as e:
            logger.error(f"[DataFactoryStorage] 创建数据集失败: {e}")
            return DatasetCreateResult(success=False, error=str(e))

    def add_records(
        self,
        dataset_id: int,
        records: List[dict],
        tags: List[str] = None,
    ) -> int:
        """
        批量添加数据记录
        
        Returns:
            成功写入的记录数
        """
        if not records:
            return 0

        try:
            from data_factory.models import DataFactoryDataset, DataFactoryRecord

            dataset = DataFactoryDataset.objects.get(id=dataset_id)
            created = 0

            records_to_create = []
            for i, record_data in enumerate(records):
                if not isinstance(record_data, dict):
                    continue
                # 移除内部标记字段
                clean_data = {k: v for k, v in record_data.items() if not k.startswith("_")}
                _boundary_tag = record_data.get("_boundary_tag", "")
                _tags = list(tags or [])
                if _boundary_tag:
                    _tags.append(_boundary_tag)

                records_to_create.append(DataFactoryRecord(
                    dataset=dataset,
                    data_content=clean_data,
                    tags=_tags,
                ))

            if records_to_create:
                DataFactoryRecord.objects.bulk_create(records_to_create, batch_size=500)
                created = len(records_to_create)

            # 更新数据集统计
            dataset.record_count = DataFactoryRecord.objects.filter(dataset=dataset).count()
            dataset.status = "completed"
            dataset.save(update_fields=["record_count", "status"])

            logger.info(f"[DataFactoryStorage] 写入 {created} 条记录到数据集 #{dataset_id}")
            return created

        except Exception as e:
            logger.error(f"[DataFactoryStorage] 添加记录失败: {e}")
            # 更新状态为失败
            try:
                from data_factory.models import DataFactoryDataset
                DataFactoryDataset.objects.filter(id=dataset_id).update(status="failed")
            except Exception:
                pass
            return 0

    def _create_dataset(self, **kwargs) -> dict:
        result = self.create_dataset(
            name=kwargs.get("name", "未命名数据集"),
            dataset_type=kwargs.get("dataset_type", "structured"),
            business_domain=kwargs.get("business_domain", ""),
            description=kwargs.get("description", ""),
            generation_config=kwargs.get("generation_config", {}),
        )
        return {
            "success": result.success,
            "dataset_id": result.dataset_id,
            "dataset_name": result.dataset_name,
            "error": result.error,
        }

    def _add_records(self, **kwargs) -> dict:
        count = self.add_records(
            dataset_id=kwargs["dataset_id"],
            records=kwargs.get("records", []),
            tags=kwargs.get("tags", []),
        )
        return {"success": True, "records_added": count}

    def _get_parameters_schema(self) -> dict:
        return {
            "action": {
                "type": "string",
                "description": "操作类型: create_dataset | add_records",
                "enum": ["create_dataset", "add_records"],
            },
            "name": {"type": "string", "description": "数据集名称"},
            "dataset_type": {
                "type": "string",
                "description": "数据类型",
                "enum": ["structured", "llm_eval", "agent_dialog"],
            },
            "business_domain": {
                "type": "string",
                "description": "业务领域",
                "enum": ["order", "user", "logistics", "after_sales", ""],
            },
            "dataset_id": {"type": "integer", "description": "数据集ID（添加记录时使用）"},
            "records": {"type": "array", "description": "数据记录列表"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "标签列表"},
        }

    def _get_required_params(self) -> list:
        return ["action"]
