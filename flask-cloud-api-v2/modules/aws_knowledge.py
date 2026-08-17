"""AWS Knowledge MCP サーバーからツールを取得するモジュール。

公開エンドポイント: https://knowledge-mcp.global.api.aws
認証不要のリモート MCP サーバー。
"""
from __future__ import annotations

import threading
from typing import Iterable

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

AWS_KNOWLEDGE_MCP_URL = "https://knowledge-mcp.global.api.aws"

# 公開したいツール名のサフィックス。サーバーが "aws___search_documentation" や
# "search_documentation" など名前空間付きで返すケースに備え、後方一致で判定する。
_ALLOWED_TOOL_SUFFIXES: tuple[str, ...] = (
    "search_documentation",
    "read_documentation",
    "recommend",
)

_cached_tools: list[BaseTool] | None = None
_cache_lock = threading.Lock()


def _build_client() -> MultiServerMCPClient:
    return MultiServerMCPClient(
        {
            "aws-knowledge": {
                "url": AWS_KNOWLEDGE_MCP_URL,
                "transport": "streamable_http",
            }
        }
    )


def _filter_tools(tools: Iterable[BaseTool]) -> list[BaseTool]:
    return [t for t in tools if any(t.name.endswith(s) for s in _ALLOWED_TOOL_SUFFIXES)]


async def get_aws_knowledge_tools() -> list[BaseTool]:
    """AWS Knowledge MCP のツール一覧を取得（プロセス内でキャッシュ）。

    呼び出し元のイベントループ上で MCP サーバーへ接続するため、本関数は
    必ず async 関数から ``await`` で呼び出すこと。
    """
    global _cached_tools
    if _cached_tools is not None:
        return _cached_tools

    client = _build_client()
    all_tools = await client.get_tools()
    filtered = _filter_tools(all_tools)

    with _cache_lock:
        if _cached_tools is None:
            _cached_tools = filtered
    return _cached_tools
