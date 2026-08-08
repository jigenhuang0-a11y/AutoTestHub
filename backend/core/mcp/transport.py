"""
MCP 传输层 — SSE 和 stdio 传输实现

- StdioTransport: 标准输入输出 (用于 IDE/CLI 集成)
- SSETransport: Server-Sent Events (用于 Web 远程调用)
"""

import json
import logging
import sys
import time
from typing import Iterator, Optional

logger = logging.getLogger(__name__)


class StdioTransport:
    """
    标准 I/O 传输 — 通过 stdin/stdout 通信

    用于 IDE 集成（如 VS Code MCP 扩展）或 CLI 工具调用

    Usage (Server 端):
        transport = StdioTransport(server)
        transport.serve()        # 阻塞，等待 stdin 输入
    """

    def __init__(self, server):
        self.server = server
        self._running = False

    def serve(self):
        """启动 stdio 服务（阻塞）"""
        self._running = True
        logger.info("[MCP.Transport] stdio 服务启动，等待请求...")

        try:
            while self._running:
                line = sys.stdin.readline()
                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    self._send_error(-32700, "Parse error")
                    continue

                response = self._process(request)
                self._send(response)

        except KeyboardInterrupt:
            logger.info("[MCP.Transport] stdio 服务被中断")
        finally:
            self._running = False

    def _process(self, request: dict) -> dict:
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        try:
            result = self.server.handle_request(method, params)
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}}

    def _send(self, data: dict):
        sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def _send_error(self, code: int, message: str):
        self._send({"jsonrpc": "2.0", "id": None, "error": {"code": code, "message": message}})

    def stop(self):
        self._running = False


class SSETransport:
    """
    SSE 传输 — 通过 HTTP SSE 实时推送

    用于 Web 前端实时调用 MCP 工具

    Usage (Django View):
        def mcp_sse_view(request):
            transport = SSETransport(server)
            return StreamingHttpResponse(
                transport.stream_response(request.body),
                content_type='text/event-stream'
            )
    """

    def __init__(self, server):
        self.server = server

    def handle_event(self, event_type: str, data: dict) -> Iterator[str]:
        """
        处理单个 SSE 事件

        Yields:
            SSE 格式的数据流
        """
        if event_type == "initialize":
            result = self.server.handle_request("initialize")
            yield self._format_sse("initialized", result)

        elif event_type == "tools/list":
            result = self.server.handle_request("tools/list")
            yield self._format_sse("tools", result)

        elif event_type == "tools/call":
            name = data.get("name", "")
            arguments = data.get("arguments", {})
            result = self.server.handle_request("tools/call", {"name": name, "arguments": arguments})
            yield self._format_sse("tool_result", result)

        elif event_type == "server/info":
            result = self.server.handle_request("server/info")
            yield self._format_sse("server_info", result)

        else:
            yield self._format_sse("error", {"message": f"Unknown event: {event_type}"})

    def stream_response(self, request_body: bytes) -> Iterator[str]:
        """
        处理 HTTP 请求体，返回 SSE 流

        Args:
            request_body: 原始请求体 (可能是多行 JSON)

        Yields:
            SSE 格式字符串
        """
        try:
            lines = request_body.decode("utf-8").strip().split("\n")
        except Exception as e:
            yield self._format_sse("error", {"message": f"Invalid request: {e}"})
            return

        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                yield self._format_sse("error", {"message": "Invalid JSON"})
                continue

            event_type = event.get("type", event.get("event", ""))
            data = event.get("data", event.get("params", {}))

            for sse_msg in self.handle_event(event_type, data):
                yield sse_msg

        # 结束标记
        yield self._format_sse("done", {"status": "complete"})

    def _format_sse(self, event: str, data: dict) -> str:
        payload = json.dumps(data, ensure_ascii=False)
        return f"event: {event}\ndata: {payload}\n\n"

    # ============================================================
    # 请求方法 — 一次性调用
    # ============================================================

    def make_request(self, method: str, params: dict = None) -> dict:
        """发起一次 MCP 请求，返回结果"""
        if method == "tools/call":
            return self.server.call_tool(
                params.get("name", ""),
                params.get("arguments", {}),
            )
        return self.server.handle_request(method, params)
