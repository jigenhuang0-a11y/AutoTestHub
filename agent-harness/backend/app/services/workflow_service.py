"""
工作流服务层

用于封装工作流调用逻辑，供 API 层使用。
"""
import uuid
import logging

from app.core.workflow import build_default_workflow, run_workflow_stream
from app.core.state import WorkflowProgress

logger = logging.getLogger(__name__)


class WorkflowService:
    """工作流编排服务"""

    def run_sync(self, user_request: str, user_id: int = None, auth_token: str = None,
                 team_id: str = "default", template_id: str = None) -> dict:
        task_id = str(uuid.uuid4())[:12]
        logger.info(f"[WorkflowService] 同步工作流: task_id={task_id} team={team_id}")

        workflow = build_default_workflow(use_parallel=True)
        initial_state = {
            "user_request": user_request,
            "task_id": task_id,
            "user_id": user_id,
            "team_id": team_id,
            "template_id": template_id,
            "auth_token": auth_token,
            "context": {},
        }
        final_state = workflow.invoke(initial_state)

        return {
            "task_id": task_id,
            "status": "completed",
            "plan": final_state.get("plan", []),
            "results": final_state.get("results", []),
            "verification": final_state.get("verification", {}),
        }

    def run_stream(self, user_request: str, user_id: int = None, auth_token: str = None,
                   team_id: str = "default", template_id: str = None):
        task_id = str(uuid.uuid4())[:12]
        logger.info(f"[WorkflowService] 流式工作流: task_id={task_id} team={team_id}")

        yield from run_workflow_stream(
            user_request=user_request,
            task_id=task_id,
            user_id=user_id,
            auth_token=auth_token,
            team_id=team_id,
            template_id=template_id,
        )

    def get_progress(self, task_id: str) -> dict:
        return WorkflowProgress.get(task_id)
