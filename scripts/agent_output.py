"""Utilities for normalizing and printing LangChain agent output."""

from collections.abc import Iterator
from typing import Any, Literal, TextIO, TypedDict, cast

from langchain_core.messages import AIMessage


class TextBlock(TypedDict):
  """Typed text content block returned by the model."""

  type: str
  text: str


class ToolUseBlock(TypedDict, total=False):
  """Typed tool-use content block returned by the model."""

  type: str
  name: str
  input: dict[str, Any]


class TextEvent(TypedDict):
  """Normalized text event extracted from an agent message."""

  kind: Literal["text"]
  text: str


class ToolUseEvent(TypedDict):
  """Normalized tool-use event extracted from an agent message."""

  kind: Literal["tool_use"]
  name: str
  input: dict[str, Any]


type AgentEvent = TextEvent | ToolUseEvent


def iter_ai_messages(messages: list[Any]) -> Iterator[AIMessage]:
  """Yield only AI messages from an agent response."""
  for msg in messages:
    if isinstance(msg, AIMessage):
      yield msg


def iter_message_events(message: AIMessage) -> Iterator[AgentEvent]:
  """Yield normalized events from a single AI message."""
  content = message.content

  if isinstance(content, str):
    yield {"kind": "text", "text": content}
    return

  if not isinstance(content, list):
    return

  for block in content:
    if not isinstance(block, dict):
      continue

    block_type = block.get("type")
    if block_type == "text":
      text_block = cast(TextBlock, block)
      yield {"kind": "text", "text": text_block["text"]}
    elif block_type == "tool_use":
      tool_block = cast(ToolUseBlock, block)
      yield {
        "kind": "tool_use",
        "name": tool_block.get("name", "unknown"),
        "input": tool_block.get("input", {}),
      }


def print_agent_events(messages: list[Any], stream: TextIO) -> None:
  """Print normalized AI message events to the provided stream."""
  for message in iter_ai_messages(messages):
    for event in iter_message_events(message):
      if event["kind"] == "text":
        print(event["text"], file=stream)
      elif event["kind"] == "tool_use":
        print(f"[Tool Call: {event['name']}({event['input']})]", file=stream)


def collect_token_usage(messages: list[Any]) -> tuple[int, int]:
  """Aggregate input and output token counts across AI messages."""
  total_input_tokens = 0
  total_output_tokens = 0

  for message in iter_ai_messages(messages):
    if message.usage_metadata:
      total_input_tokens += message.usage_metadata.get("input_tokens", 0)
      total_output_tokens += message.usage_metadata.get("output_tokens", 0)

  return total_input_tokens, total_output_tokens
