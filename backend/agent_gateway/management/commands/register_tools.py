"""
Django 管理命令：手动注册/刷新 MCP 工具到编排服务底座

用法：
    python manage.py register_tools [--team-id TEAM_ID]
    python manage.py register_tools --status
    python manage.py register_tools --refresh
    python manage.py register_tools --capabilities
"""
from django.core.management.base import BaseCommand
from agent_gateway.tool_registration import (
    register_tools_on_startup,
    get_tool_registration_manager,
)


class Command(BaseCommand):
    help = '注册/刷新 MCP 工具到编排服务底座，或查看注册状态'

    def add_arguments(self, parser):
        parser.add_argument(
            '--team-id',
            type=str,
            default=None,
            help='团队 ID（默认注册全局工具）',
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='查看底座工具缓存状态',
        )
        parser.add_argument(
            '--refresh',
            action='store_true',
            help='通知底座立即刷新工具列表',
        )
        parser.add_argument(
            '--capabilities',
            action='store_true',
            help='获取底座的编排能力列表',
        )

    def handle(self, *args, **options):
        team_id = options.get('team_id')
        manager = get_tool_registration_manager()

        if options.get('status'):
            self._show_status(manager)
        elif options.get('refresh'):
            self._do_refresh(manager, team_id)
        elif options.get('capabilities'):
            self._show_capabilities(manager)
        else:
            self._do_register(team_id)

    def _do_register(self, team_id):
        self.stdout.write(self.style.WARNING('正在将 MCP 工具注册到编排服务底座...'))
        result = register_tools_on_startup(team_id=team_id)
        self.stdout.write(self.style.SUCCESS(
            f'注册完成（后台线程已启动，请查看日志确认）'
        ))

    def _show_status(self, manager):
        self.stdout.write('查询底座工具缓存状态...')
        status = manager.check_orchestrator_status()
        if 'error' in status:
            self.stdout.write(self.style.ERROR(f'查询失败: {status["error"]}'))
            return
        self.stdout.write(self.style.SUCCESS(
            f'工具数: {status.get("total_tools", 0)}, '
            f'Agent映射: {status.get("agent_mappings", 0)}, '
            f'上次刷新: {status.get("last_refresh", 0)}, '
            f'已过期: {status.get("is_stale", True)}'
        ))

    def _do_refresh(self, manager, team_id):
        self.stdout.write('通知底座刷新工具列表...')
        result = manager.notify_tool_change(team_id=team_id)
        self.stdout.write(self.style.SUCCESS(
            f'刷新结果: {result}'
        ))

    def _show_capabilities(self, manager):
        self.stdout.write('获取底座编排能力...')
        caps = manager.fetch_orchestrator_capabilities()
        if 'error' in caps:
            self.stdout.write(self.style.ERROR(f'获取失败: {caps["error"]}'))
            return
        self.stdout.write(self.style.SUCCESS(
            f'底座暴露 {caps.get("count", 0)} 个编排元工具:'
        ))
        for tool in caps.get('tools', []):
            self.stdout.write(
                f'  • {tool["name"]}: {tool["description"][:60]}'
            )
