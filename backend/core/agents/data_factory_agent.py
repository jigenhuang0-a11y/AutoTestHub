"""
数据工厂 Agent — 智能构造测试数据 + 动态变量绑定

功能：
1. 接收字段定义 → 搜索知识库 → LLM 生成数据 → 写入数据集
2. 支持 3 种生成策略：smart / boundary / template
3. 自动变量绑定：生成的数据 → TestCase.global_vars / context_vars
4. 预置模板驱动：支持 order / user / logistics / after_sales
"""
import json
import re
import logging
from typing import List, Dict, Any, Optional, AsyncIterator

from .base_agent import BaseAgent
from core.tools.knowledge_search import get_knowledge_tool
from core.tools.data_factory_storage import DataFactoryStorageTool
from core.tools.variable_binding import VariableBindingTool
from core.models.prompts.data_factory import DataFactoryPrompt

logger = logging.getLogger(__name__)


class DataFactoryAgent(BaseAgent):
    """
    数据工厂 Agent

    工作流：
    1. 解析字段定义 → 匹配预置模板
    2. 搜索知识库获取业务上下文
    3. 构建 Prompt → 调用 LLM 生成数据
    4. 解析 JSON → 存入 DataFactoryDataset + DataFactoryRecord
    5. 变量绑定 → 绑定到关联用例的 global_vars / context_vars

    用法:
        agent = DataFactoryAgent(user_id=1)
        result = agent.run(
            prompt="生成订单测试数据",
            context={
                "fields": [...],
                "strategy": "smart",
                "business_domain": "order",
                "record_count": 20,
            }
        )
    """

    name = "data_factory"
    description = "智能构造测试数据并绑定到用例变量"
    task_type = "generation"
    system_prompt = DataFactoryPrompt.SYSTEM_PROMPTS["smart"]

    # 预置业务字段
    PRESET_FIELDS = {
        "order": [
            {"name": "order_id", "type": "string", "description": "订单号，如 ORD202407010001"},
            {"name": "buyer_name", "type": "string", "description": "买家姓名"},
            {"name": "buyer_phone", "type": "string", "description": "买家手机号"},
            {"name": "order_amount", "type": "number", "description": "订单金额（元）"},
            {"name": "order_status", "type": "string", "description": "订单状态: pending/paid/shipped/completed/cancelled"},
            {"name": "payment_method", "type": "string", "description": "支付方式: wechat/alipay/card"},
            {"name": "shipping_address", "type": "string", "description": "收货地址"},
            {"name": "items", "type": "array", "description": "商品列表 [{sku, name, qty, price}]"},
            {"name": "created_at", "type": "string", "description": "下单时间 ISO8601"},
        ],
        "user": [
            {"name": "user_id", "type": "string", "description": "用户ID，如 USR2024001"},
            {"name": "username", "type": "string", "description": "用户名"},
            {"name": "email", "type": "string", "description": "邮箱地址"},
            {"name": "phone", "type": "string", "description": "手机号"},
            {"name": "nickname", "type": "string", "description": "昵称"},
            {"name": "gender", "type": "string", "description": "性别: male/female/other"},
            {"name": "age", "type": "number", "description": "年龄"},
            {"name": "vip_level", "type": "string", "description": "会员等级: normal/silver/gold/diamond"},
            {"name": "register_at", "type": "string", "description": "注册时间"},
        ],
        "logistics": [
            {"name": "tracking_no", "type": "string", "description": "物流单号"},
            {"name": "order_id", "type": "string", "description": "关联订单号"},
            {"name": "carrier", "type": "string", "description": "承运商: SF/YTO/ZTO/EMS"},
            {"name": "ship_from", "type": "string", "description": "发货地"},
            {"name": "ship_to", "type": "string", "description": "收货地"},
            {"name": "current_status", "type": "string", "description": "当前状态: pending/picked_up/in_transit/delivered"},
            {"name": "eta_days", "type": "number", "description": "预计送达天数"},
            {"name": "weight_kg", "type": "number", "description": "重量(kg)"},
        ],
        "after_sales": [
            {"name": "ticket_id", "type": "string", "description": "售后工单号"},
            {"name": "order_id", "type": "string", "description": "关联订单号"},
            {"name": "reason", "type": "string", "description": "售后原因: quality/damage/wrong_item/not_needed"},
            {"name": "refund_amount", "type": "number", "description": "退款金额"},
            {"name": "status", "type": "string", "description": "工单状态: pending/processing/approved/rejected/completed"},
            {"name": "customer_notes", "type": "string", "description": "客户备注"},
            {"name": "handler", "type": "string", "description": "处理人"},
            {"name": "images", "type": "array", "description": "凭证图片URL列表"},
        ],
    }

    def __init__(self, user_id: int = None, router=None):
        super().__init__(router=router)
        self.user_id = user_id
        self._knowledge_tool = get_knowledge_tool()
        self._storage_tool = DataFactoryStorageTool(user_id=user_id)
        self._binding_tool = VariableBindingTool(user_id=user_id)

    def run(self, prompt: str, context: dict = None) -> dict:
        """
        同步执行（兼容 BaseAgent 接口）

        Args:
            prompt: 需求描述
            context: {
                "fields": list,           # 字段定义列表
                "strategy": str,          # smart/boundary/template
                "business_domain": str,   # order/user/logistics/after_sales
                "record_count": int,      # 生成数量
                "knowledge_context": str, # 知识库上下文
                "extra_context": str,     # 额外约束
                "dataset_name": str,      # 数据集名称
                "bind_testcase_ids": list,# 自动绑定的用例ID列表
            }

        Returns:
            {"status": "success|error", "data": [...], "dataset_id": int, "stats": {...}}
        """
        ctx = context or {}
        fields = ctx.get("fields") or self.PRESET_FIELDS.get(ctx.get("business_domain", ""), [])
        strategy = ctx.get("strategy", "smart")
        business_domain = ctx.get("business_domain", "")
        record_count = ctx.get("record_count", 10)
        knowledge_context = ctx.get("knowledge_context", "")
        extra_context = ctx.get("extra_context", "")
        dataset_name = ctx.get("dataset_name") or f"AI生成-{business_domain or '通用'}-数据"
        bind_testcase_ids = ctx.get("bind_testcase_ids", [])

        try:
            # Step 1: 构建 Prompt
            messages = DataFactoryPrompt.build_messages(
                business_domain=business_domain,
                field_definitions=fields,
                record_count=record_count,
                strategy=strategy,
                knowledge_context=knowledge_context,
                extra_context=extra_context,
            )

            # Step 2: 调用 LLM
            self.system_prompt = messages[0]["content"]
            response = self.ask_llm(prompt=messages[1]["content"])

            # Step 3: 解析 JSON
            records = self._parse_records(response)
            if not records:
                return self._error("未能从 LLM 响应中解析出有效数据记录")

            # Step 4: 创建数据集并保存
            dataset_result = self._storage_tool.create_dataset(
                name=dataset_name,
                dataset_type="structured",
                business_domain=business_domain,
                description=f"AI 自动生成 - {strategy} 策略 - {prompt}",
                generation_config={
                    "strategy": strategy,
                    "fields": fields,
                    "record_count": record_count,
                    "prompt": prompt,
                },
            )

            if not dataset_result.success:
                return self._error(f"创建数据集失败: {dataset_result.error}")

            saved_count = self._storage_tool.add_records(
                dataset_id=dataset_result.dataset_id,
                records=records,
            )

            # Step 5: 变量绑定
            binding_results = []
            if bind_testcase_ids and dataset_result.dataset_id:
                binding_results = self._binding_tool.bind_batch(
                    testcase_ids=bind_testcase_ids,
                    dataset_id=dataset_result.dataset_id,
                )

            return self._success(
                data=records,
                stats={
                    "dataset_id": dataset_result.dataset_id,
                    "dataset_name": dataset_result.dataset_name,
                    "total": len(records),
                    "saved": saved_count,
                    "strategy": strategy,
                    "business_domain": business_domain,
                    "bound_count": sum(1 for r in binding_results if r.get("success")),
                },
                binding_results=binding_results,
            )

        except Exception as e:
            return self._error(str(e))

    async def generate(
        self,
        fields: Optional[List[dict]] = None,
        strategy: str = "smart",
        business_domain: str = "",
        record_count: int = 10,
        knowledge_doc_ids: Optional[List[int]] = None,
        extra_context: str = "",
        dataset_name: str = "",
        bind_testcase_ids: Optional[List[int]] = None,
        stream: bool = True,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        异步主入口：流式生成测试数据

        Args:
            fields: 字段定义列表
            strategy: 生成策略
            business_domain: 业务领域
            record_count: 生成数量
            knowledge_doc_ids: 知识库文档ID
            extra_context: 额外约束
            dataset_name: 数据集名称
            bind_testcase_ids: 绑定用例ID列表
            stream: 是否流式

        Yields:
            进度事件 + 最终结果
        """
        # 默认字段
        if not fields:
            fields = self.PRESET_FIELDS.get(business_domain, [])

        dataset_name = dataset_name or f"AI生成-{business_domain or '通用'}-数据"

        try:
            # Step 1: 知识检索
            yield {"type": "progress", "stage": "knowledge_search", "message": "正在搜索相关知识..."}
            knowledge_context = ""
            if knowledge_doc_ids:
                knowledge_context = await self._search_by_ids(knowledge_doc_ids)
            else:
                knowledge_context = await self._auto_search(
                    f"{business_domain} {json.dumps(fields, ensure_ascii=False)}"
                )

            yield {
                "type": "progress", "stage": "knowledge_search",
                "message": f"知识检索完成",
                "knowledge_found": bool(knowledge_context),
            }

            # Step 2: 构建 Prompt
            yield {"type": "progress", "stage": "prompt_build", "message": "构建生成提示词..."}
            messages = DataFactoryPrompt.build_messages(
                business_domain=business_domain,
                field_definitions=fields,
                record_count=record_count,
                strategy=strategy,
                knowledge_context=knowledge_context,
                extra_context=extra_context,
            )

            # Step 3: LLM 调用
            yield {"type": "progress", "stage": "llm_call", "message": f"AI 正在生成 {record_count} 条数据..."}
            self.system_prompt = messages[0]["content"]

            if stream:
                full_response = ""
                async for chunk in self.router.chat_stream(
                    messages=[{"role": "user", "content": messages[1]["content"]}],
                    task_type=self.task_type,
                ):
                    full_response += chunk
                    yield {"type": "token", "content": chunk}
            else:
                full_response = self.router.chat(
                    messages=[{"role": "user", "content": messages[1]["content"]}],
                    task_type=self.task_type,
                )

            # Step 4: 解析
            yield {"type": "progress", "stage": "parse", "message": "解析生成结果..."}
            records = self._parse_records(full_response)

            if not records:
                yield {"type": "error", "message": "无法从 LLM 响应中解析出有效数据"}
                return

            yield {
                "type": "progress", "stage": "parse",
                "message": f"解析完成: {len(records)} 条数据记录",
            }

            # Step 5: 保存数据集
            yield {"type": "progress", "stage": "save", "message": f"创建数据集 {dataset_name}..."}
            dataset_result = self._storage_tool.create_dataset(
                name=dataset_name,
                dataset_type="structured",
                business_domain=business_domain,
                description=f"AI 自动生成 - {strategy} 策略",
                generation_config={
                    "strategy": strategy,
                    "fields": fields,
                    "record_count": record_count,
                },
            )

            if not dataset_result.success:
                yield {"type": "error", "message": f"创建数据集失败: {dataset_result.error}"}
                return

            saved_count = self._storage_tool.add_records(
                dataset_id=dataset_result.dataset_id,
                records=records,
            )

            yield {
                "type": "progress", "stage": "save",
                "message": f"保存完成: {saved_count}/{len(records)} 条",
            }

            # Step 6: 变量绑定
            binding_results = []
            if bind_testcase_ids:
                yield {
                    "type": "progress", "stage": "binding",
                    "message": f"绑定变量到 {len(bind_testcase_ids)} 个用例...",
                }
                binding_results = self._binding_tool.bind_batch(
                    testcase_ids=bind_testcase_ids,
                    dataset_id=dataset_result.dataset_id,
                )
                bound_count = sum(1 for r in binding_results if r.get("success"))
                yield {
                    "type": "progress", "stage": "binding",
                    "message": f"变量绑定完成: {bound_count}/{len(bind_testcase_ids)} 个用例",
                }

            # Step 7: 最终结果
            yield {
                "type": "done",
                "records": records[:10],  # 只返回前10条预览
                "dataset_id": dataset_result.dataset_id,
                "dataset_name": dataset_result.dataset_name,
                "stats": {
                    "total": len(records),
                    "saved": saved_count,
                    "strategy": strategy,
                    "business_domain": business_domain,
                    "knowledge_found": bool(knowledge_context),
                    "bound_count": sum(1 for r in binding_results if r.get("success")),
                },
                "binding_results": binding_results,
            }

        except Exception as e:
            logger.error(f"[DataFactoryAgent] 生成失败: {e}", exc_info=True)
            yield {"type": "error", "message": str(e)}

    # ============================================================
    # 解析
    # ============================================================

    def _parse_records(self, response: str) -> List[dict]:
        """从 LLM 响应中解析 JSON 数据数组（与 TestCase Agent 一致的容错策略）"""
        # 1. 提取 markdown 代码块
        code_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
        if code_match:
            response = code_match.group(1)

        # 2. 提取 JSON 数组
        array_match = re.search(r'\[[\s\S]*\]', response)
        if array_match:
            try:
                data = json.loads(array_match.group(0))
                if isinstance(data, list):
                    return [item for item in data if isinstance(item, dict)]
            except json.JSONDecodeError:
                pass

        # 3. 提取多个 JSON 对象
        objects = re.findall(r'\{[^{}]*\}', response)
        if objects:
            records = []
            for obj_str in objects:
                try:
                    records.append(json.loads(obj_str))
                except json.JSONDecodeError:
                    continue
            if records:
                return records

        # 4. 直接解析
        try:
            data = json.loads(response)
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            if isinstance(data, dict):
                return [data]
        except json.JSONDecodeError:
            pass

        logger.warning(f"[DataFactoryAgent] 无法解析 JSON: {response[:200]}")
        return []

    # ============================================================
    # 知识检索
    # ============================================================

    async def _auto_search(self, query: str) -> str:
        """自动搜索知识库"""
        try:
            results = await self._knowledge_tool.search(query=query, top_k=3)
            return self._knowledge_tool.format_for_prompt(results)
        except Exception:
            return ""

    async def _search_by_ids(self, doc_ids: List[int]) -> str:
        """按文档ID搜索"""
        return ""  # TODO: 实现按ID精确检索

    # ============================================================
    # 工具
    # ============================================================

    def get_tools(self) -> List[dict]:
        """注册可用工具"""
        return [
            self._storage_tool.to_openai_function(),
            self._binding_tool.to_openai_function(),
        ]


# 工厂函数
def create_data_factory(user_id: int = None) -> DataFactoryAgent:
    return DataFactoryAgent(user_id=user_id)
