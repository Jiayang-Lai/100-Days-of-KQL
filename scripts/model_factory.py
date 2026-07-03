"""Shared chat model factory for generator scripts."""

from langchain.chat_models import BaseChatModel
from langchain_anthropic import ChatAnthropic

DEFAULT_MODEL_PROVIDER = "anthropic"
DEFAULT_MODEL_NAME = "claude-haiku-4-5-20251001"


def create_chat_model(
  provider: str = DEFAULT_MODEL_PROVIDER,
  model_name: str = DEFAULT_MODEL_NAME,
) -> BaseChatModel:
  """Create a chat model instance for the requested provider.

  Args:
    provider: The model provider to use (e.g., "anthropic").
    model_name: The name of the model to use (e.g., "claude-haiku-4-5-20251001").

  Returns:
    An instance of a chat model class corresponding to the provider.
  """
  normalized_provider = provider.strip().lower()

  if normalized_provider == "anthropic":
    return ChatAnthropic(
      model_name=model_name,
      timeout=60,
      max_retries=3,
      stop=None,
    )

  raise ValueError(
    f"Unsupported model provider: {provider}. "
    "Add it to scripts/model_factory.py before using it."
  )
