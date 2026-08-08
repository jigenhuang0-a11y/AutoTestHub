"""
管理命令：将硬编码的 Agent System Prompt 同步到数据库

运行方式:
    python manage.py seed_agent_prompts
    python manage.py seed_agent_prompts --dry-run    # 仅显示，不写入

阿里云部署后只需运行一次此命令即可初始化默认 prompt 数据。
之后可在 Django Admin 中手动编辑，或通过 API 更新。
"""
from django.core.management.base import BaseCommand
from agent_gateway.models import AgentPromptConfig


class Command(BaseCommand):
    help = '将代码中硬编码的 Agent System Prompt 同步到数据库（初始化默认值）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='仅显示将要写入的 prompt，不实际写入数据库'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        seed_data = self._collect_seeds()
        
        created_count = 0
        skipped_count = 0
        
        for item in seed_data:
            agent_name = item['agent_name']
            prompt_subtype = item.get('prompt_subtype', 'default')
            
            # 检查是否已存在
            existing = AgentPromptConfig.objects.filter(
                agent_name=agent_name,
                prompt_subtype=prompt_subtype,
            ).first()
            
            if existing:
                self.stdout.write(f'  [跳过] {agent_name}/{prompt_subtype} 已存在 (v{existing.version})')
                skipped_count += 1
                continue
            
            if dry_run:
                preview = item['system_prompt'][:80].replace('\n', ' ')
                self.stdout.write(f'  [预览] {agent_name}/{prompt_subtype}: "{preview}..."')
                created_count += 1
                continue
            
            AgentPromptConfig.objects.create(**item)
            self.stdout.write(f'  [创建] {agent_name}/{prompt_subtype}')
            created_count += 1
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f'\n--- DRY RUN: 将创建 {created_count} 条记录，跳过 {skipped_count} 条已存在 ---'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\n✓ 完成: 创建 {created_count} 条，跳过 {skipped_count} 条（已存在）'
            ))
            self.stdout.write('\n接下来:')
            self.stdout.write('  1. 访问 /admin/agent_gateway/agentpromptconfig/ 管理 Prompt')
            self.stdout.write('  2. 修改后即时生效（无需重启）')
            self.stdout.write('  3. 阿里云部署后只需运行一次此命令')

    def _collect_seeds(self):
        """收集所有 Agent 的默认 System Prompt"""
        seeds = []
        
        # --- PlanAgent ---
        from core.agents.plan_agent import PlanAgent
        seeds.append({
            'agent_name': PlanAgent.name,
            'prompt_subtype': 'default',
            'prompt_type': 'system',
            'system_prompt': PlanAgent.system_prompt,
            'description': '测试计划规划师 - 拆解需求为执行步骤',
        })
        
        # --- TestCaseGeneratorAgent ---
        from core.agents.testcase_gen_agent import TestCaseGeneratorAgent
        from core.models.prompts.testcase_gen import TestCasePrompt
        seeds.append({
            'agent_name': TestCaseGeneratorAgent.name,
            'prompt_subtype': 'default',
            'prompt_type': 'system',
            'system_prompt': TestCasePrompt.SYSTEM_PROMPTS.get('standard', ''),
            'description': '用例生成 Agent - 标准策略',
        })
        
        # --- DataFactoryAgent ---
        from core.agents.data_factory_agent import DataFactoryAgent
        from core.models.prompts.data_factory import DataFactoryPrompt
        for strategy in ['smart', 'boundary', 'template']:
            prompt_text = DataFactoryPrompt.SYSTEM_PROMPTS.get(strategy, '')
            if prompt_text:
                seeds.append({
                    'agent_name': DataFactoryAgent.name,
                    'prompt_subtype': strategy,
                    'prompt_type': 'system',
                    'system_prompt': prompt_text,
                    'description': f'数据工厂 Agent - {strategy} 策略',
                })
        
        # --- ExecutionEngineAgent ---
        from core.agents.execution_agent import ExecutionEngineAgent
        from core.models.prompts.execution import FAILURE_ANALYSIS_SYSTEM
        seeds.append({
            'agent_name': ExecutionEngineAgent.name,
            'prompt_subtype': 'default',
            'prompt_type': 'system',
            'system_prompt': FAILURE_ANALYSIS_SYSTEM,
            'description': '执行引擎 Agent - 失败分析 prompt',
        })
        
        # --- EvaluatorAgent ---
        from core.agents.evaluator_agent import EvaluatorAgent
        from core.models.prompts.evaluation import EVALUATION_SYSTEM
        seeds.append({
            'agent_name': EvaluatorAgent.name,
            'prompt_subtype': 'default',
            'prompt_type': 'system',
            'system_prompt': EVALUATION_SYSTEM,
            'description': '评估 Agent - 质量评估 prompt',
        })
        
        # --- KnowledgeAgent ---
        from core.agents.knowledge_agent import KnowledgeAgent
        seeds.append({
            'agent_name': KnowledgeAgent.name,
            'prompt_subtype': 'default',
            'prompt_type': 'system',
            'system_prompt': KnowledgeAgent.system_prompt,
            'description': '知识库 RAG Agent',
        })
        
        return seeds
