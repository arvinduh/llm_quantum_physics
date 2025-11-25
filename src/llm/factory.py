"""Factory functions for creating LLM clients with specific prompts."""

from src import prompts
from src.llm.client import LlmClient
from src.llm.models import Model

# Default models to use for this project
DEFAULT_MODELS = [
  Model.GEMINI_PRO_2_5,
  Model.GPT_5,
  Model.CLAUDE_SONNET_4_5,
]


def initialize_models(
  system_prompt: str, models: list[Model] | None = None
) -> list[LlmClient]:
  """Initializes LLM clients for selected models.

  Args:
      system_prompt: The system prompt to use for all clients.
      models: List of Model enums to initialize. If None, uses DEFAULT_MODELS.

  Returns:
      A list of initialized LlmClient instances.
  """
  if models is None:
    models = DEFAULT_MODELS

  return [
    LlmClient(model=model, system_prompt=system_prompt) for model in models
  ]


def get_solvable_models(models: list[Model] | None = None) -> list[LlmClient]:
  """Returns a list of models suitable for solving standard physics problems.

  Args:
      models: List of Model enums to use. If None, uses DEFAULT_MODELS.

  Returns:
      A list of LlmClient instances.
  """
  return initialize_models(prompts.PHYSICS_SOLVER_PROMPT, models)


def get_unsolvable_models(models: list[Model] | None = None) -> list[LlmClient]:
  """Returns a list of models suitable for tackling unsolvable physics problems.

  Args:
      models: List of Model enums to use. If None, uses DEFAULT_MODELS.

  Returns:
      A list of LlmClient instances.
  """
  return initialize_models(prompts.PHYSICS_THEORIST_PROMPT, models)


def get_evaluator_models(models: list[Model] | None = None) -> list[LlmClient]:
  """Returns a list of models suitable for evaluating physics problem solutions.

  Args:
      models: List of Model enums to use. If None, uses DEFAULT_MODELS.

  Returns:
      A list of LlmClient instances.
  """
  return initialize_models(prompts.POINTWISE_EVAL_PROMPT, models)


def get_ranking_models(models: list[Model] | None = None) -> list[LlmClient]:
  """Returns a list of models suitable for judging physics problem solutions.

  Args:
      models: List of Model enums to use. If None, uses DEFAULT_MODELS.

  Returns:
      A list of LlmClient instances.
  """
  return initialize_models(prompts.RANKING_EVAL_PROMPT, models)
