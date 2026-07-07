"""Shared chat model factory for generator scripts."""

import os

from azure.identity import DefaultAzureCredential
from langchain.chat_models import BaseChatModel
from langchain_anthropic import ChatAnthropic
from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel

DEFAULT_MODEL_PROVIDER = "anthropic"

DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_AZURE_MODEL_NAME = "gpt-5.4"


def create_chat_model(
  provider: str = DEFAULT_MODEL_PROVIDER,
  model_name: str | None = None,
) -> BaseChatModel:
  """Create a chat model instance for the requested provider.

  Args:
    provider: The model provider to use (e.g., "anthropic").
    model_name: The name of the model to use (e.g., "claude-haiku-4-5-20251001").

  Returns:
    An instance of a chat model class corresponding to the provider.
  """
  normalized_provider = provider.strip().lower()

  match normalized_provider:
    case "anthropic":
      return ChatAnthropic(
        model_name=model_name or DEFAULT_ANTHROPIC_MODEL,
        timeout=60,
        max_retries=3,
        stop=None,
      )
    case "azure":
      AZURE_AI_PROJECT_ENDPOINT = os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
      if not AZURE_AI_PROJECT_ENDPOINT:
        raise ValueError(
          "AZURE_AI_PROJECT_ENDPOINT environment variable is not set. "
          "Please set it to your Azure OpenAI endpoint before using the Azure provider."
        )
      return AzureAIOpenAIApiChatModel(
        model=model_name or DEFAULT_AZURE_MODEL_NAME,
        project_endpoint=AZURE_AI_PROJECT_ENDPOINT,
        credential=DefaultAzureCredential(),
      )

  raise ValueError(
    f"Unsupported model provider: {provider}. "
    "Add it to scripts/model_factory.py before using it."
  )
