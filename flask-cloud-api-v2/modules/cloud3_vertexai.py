import asyncio
import json
from collections.abc import Iterable

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_google_vertexai.model_garden import ChatAnthropicVertex

from modules.aws_knowledge import get_aws_knowledge_tools
from modules.session_store import StoredMessage

LOCATION = "global"
MAX_TOOL_ITERATIONS = 5

SYSTEM_PROMPT = (
    "あなたは有用なアシスタントです。"
    "AWS（Amazon Web Services）に関する質問（サービス仕様・アーキテクチャ・料金・"
    "ベストプラクティス・API・CLI など）には、必ず提供されている AWS Knowledge MCP "
    "ツール（search_documentation / read_documentation / recommend）を優先して使用し、"
    "公式ドキュメントに基づいた正確な回答を生成してください。"
    "AWS と無関係な質問では通常通り回答してください。"
)


def _build_llm() -> ChatAnthropicVertex:
    return ChatAnthropicVertex(
        location=LOCATION,
        model_name="claude-opus-4-8",
        max_tokens=2000,
        model_kwargs={
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": "medium"},
        },
    )


async def _load_tools_safely() -> list:
    try:
        return await get_aws_knowledge_tools()
    except Exception as exc:
        # MCP サーバー疎通不可でも LLM 単独で応答できるようフォールバック
        print(f"[aws_knowledge] failed to load MCP tools: {exc}")
        return []


def _build_messages(
    user_message: str,
    history: Iterable[StoredMessage] | None,
) -> list[BaseMessage]:
    messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
    for item in history or []:
        role = item.get("role")
        content = item.get("content", "")
        if not content:
            continue
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=user_message))
    return messages


def _extract_block_text(block: dict) -> tuple[str, str]:
    """content block を ("text" or "thinking", 文字列) に正規化する。"""
    block_type = block.get("type")
    if block_type == "thinking":
        return "thinking", block.get("thinking", "") or block.get("text", "")
    if block_type == "text":
        return "text", block.get("text", "")
    return "", ""


def _split_text_thinking(content) -> tuple[str, str]:
    if isinstance(content, str):
        return content, ""
    if isinstance(content, list):
        text_parts: list[str] = []
        thinking_parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            kind, value = _extract_block_text(block)
            if kind == "text":
                text_parts.append(value)
            elif kind == "thinking":
                thinking_parts.append(value)
        return "".join(text_parts), "".join(thinking_parts)
    return str(content), ""


async def _execute_tool(tool, args) -> str:
    try:
        result = await tool.ainvoke(args)
    except Exception as exc:
        return f"ツール実行エラー: {exc}"
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(result)


async def _invoke_with_tools(
    user_message: str,
    history: Iterable[StoredMessage] | None,
) -> tuple[str, str]:
    tools = await _load_tools_safely()
    tools_by_name = {t.name: t for t in tools}
    llm = _build_llm()
    llm_runnable = llm.bind_tools(tools) if tools else llm

    messages = _build_messages(user_message, history)
    final_response: AIMessage | None = None

    for _ in range(MAX_TOOL_ITERATIONS):
        response: AIMessage = await llm_runnable.ainvoke(messages)
        messages.append(response)
        final_response = response

        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            break

        for tc in tool_calls:
            name = tc.get("name", "")
            args = tc.get("args", {}) or {}
            tool = tools_by_name.get(name)
            if tool is None:
                tool_output = f"ツール {name} は利用できません"
            else:
                tool_output = await _execute_tool(tool, args)
            messages.append(
                ToolMessage(content=tool_output, tool_call_id=tc.get("id", ""))
            )

    if final_response is None:
        return "", ""
    return _split_text_thinking(final_response.content)


async def _stream_with_tools(
    user_message: str,
    history: Iterable[StoredMessage] | None,
):
    tools = await _load_tools_safely()
    tools_by_name = {t.name: t for t in tools}
    llm = _build_llm()
    llm_runnable = llm.bind_tools(tools) if tools else llm

    messages = _build_messages(user_message, history)

    for _ in range(MAX_TOOL_ITERATIONS):
        accumulated = None
        async for chunk in llm_runnable.astream(messages):
            content = chunk.content
            if isinstance(content, str):
                if content:
                    yield "text", content
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    kind, value = _extract_block_text(block)
                    if kind and value:
                        yield kind, value
            accumulated = chunk if accumulated is None else accumulated + chunk

        if accumulated is None:
            return

        messages.append(accumulated)
        tool_calls = getattr(accumulated, "tool_calls", None) or []
        if not tool_calls:
            return

        for tc in tool_calls:
            name = tc.get("name", "")
            args = tc.get("args", {}) or {}
            yield "tool_use", json.dumps(
                {"name": name, "args": args}, ensure_ascii=False
            )

            tool = tools_by_name.get(name)
            if tool is None:
                tool_output = f"ツール {name} は利用できません"
            else:
                tool_output = await _execute_tool(tool, args)

            messages.append(
                ToolMessage(content=tool_output, tool_call_id=tc.get("id", ""))
            )
            preview = tool_output if len(tool_output) <= 500 else tool_output[:500] + "…"
            yield "tool_result", preview


def chatcompletion(
    userMessage: str,
    history: Iterable[StoredMessage] | None = None,
) -> tuple[str, str]:
    """通常応答。 (text, thinking) を返す。AWS 関連の質問は MCP ツールを使用する。"""
    return asyncio.run(_invoke_with_tools(userMessage, history))


def chatcompletion_stream(
    userMessage: str,
    history: Iterable[StoredMessage] | None = None,
):
    """ストリーミング応答。 (kind, chunk) を yield する。
    kind は "text" | "thinking" | "tool_use" | "tool_result"。
    """
    loop = asyncio.new_event_loop()
    try:
        agen = _stream_with_tools(userMessage, history)
        while True:
            try:
                kind, chunk = loop.run_until_complete(agen.__anext__())
            except StopAsyncIteration:
                break
            yield kind, chunk
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
