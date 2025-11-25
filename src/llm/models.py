"""Model enumerations for LLM clients."""

from enum import Enum


class Model(str, Enum):
  """Enumeration of selected high-end models on OpenRouter for evaluation."""

  CLAUDE_SONNET_4_5 = "anthropic/claude-sonnet-4.5"
  GEMINI_PRO_2_5 = "google/gemini-2.5-pro"
  GPT_5 = "openai/gpt-5"
  GROK_4 = "x-ai/grok-4"
  DEEP_SEEK_3 = "deepseek/deepseek-chat-v3-0324"
