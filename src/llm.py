"""Defines a base class for LLM API clients."""

import os
import random
import time
from enum import Enum

import dotenv
import requests
from absl import logging

from src import prompts

_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_MAX_RETRIES = 5
_INITIAL_BACKOFF = 1.0  # In seconds


class Model(str, Enum):
  """
  Enumeration of selected high-end models on OpenRouter for evaluation.
  """

  CLAUDE_SONNET_4_5 = "anthropic/claude-sonnet-4.5"
  GEMINI_PRO_2_5 = "google/gemini-2.5-pro"
  GPT_5 = "openai/gpt-5"
  GROK_4 = "x-ai/grok-4"
  DEEP_SEEK_3 = "deepseek/deepseek-chat-v3-0324"


class LlmApiError(Exception):
  """Raised when the LLM API call fails after all retries."""


class LlmClient:
  """LLM API client with retry and fallback logic.

  Attributes:
    model (Model): The primary model to use for API calls.
    api_key (str): The API key for authentication.
    max_retries (int): Maximum number of retries for transient errors.
    initial_backoff (float): Initial backoff time in seconds for retries.
    system_prompt (str): The system prompt to send with requests.
  """

  def __init__(
    self,
    model: Model = Model.GEMINI_PRO_2_5,
    api_key: str | None = None,
    max_retries: int = _MAX_RETRIES,
    initial_backoff: float = _INITIAL_BACKOFF,
    system_prompt: str | None = None,
  ):
    """Initializes the client.

    Args:
      model: The primary model to use for API calls.
      api_key: The API key for authentication. If None, loaded from .env.
      max_retries: Maximum number of retries for transient errors.
      initial_backoff: Initial backoff time in seconds for retries.
      system_prompt: The system prompt to send with requests.
    """
    # Load API key from .env if not provided
    dotenv.load_dotenv()
    self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not self.api_key:
      raise ValueError(
        "OPENROUTER_API_KEY must be set in .env file or "
        "provided as an argument."
      )

    # Self attributes
    self.model = model
    self.max_retries = max_retries
    self.initial_backoff = initial_backoff
    self.system_prompt = system_prompt

    # Use standard header names; some proxies/hosts reject nonstandard keys.
    self._headers = {
      "Authorization": f"Bearer {self.api_key}",
      "Content-Type": "application/json",
    }

  def call_api(self, prompt: str) -> str:
    """Handles the core logic of calling the LLM API with retries.

    Args:
      prompt: The user-facing prompt to send to the model.

    Returns:
      The text content of the model's response.

    Raises:
      LlmApiError: If the API call fails after all retries.
      requests.exceptions.HTTPError: For unrecoverable HTTP errors.
    """
    payload = {
      "model": self.model.value,  # Use the enum's string value
      "messages": [
        {"role": "user", "content": prompt},
      ],
    }

    if self.system_prompt:
      payload["messages"].insert(
        0, {"role": "system", "content": self.system_prompt}
      )

    backoff_time = self.initial_backoff

    # Attempt the API call with retries
    for attempt in range(self.max_retries):
      try:
        response = requests.post(
          _API_URL,
          headers=self._headers,
          json=payload,
          timeout=30,
        )

        if response.ok:
          logging.info(
            "LLM API call successful for model %s (Attempt %d/%d)",
            self.model.value,
            attempt + 1,
            self.max_retries,
          )
          data = response.json()
          return data["choices"][0]["message"]["content"]

        elif response.status_code in {
          requests.codes.too_many_requests,
          requests.codes.request_timeout,
          requests.codes.service_unavailable,
        }:
          logging.warning(
            "Transient error (status %d) for model %s (Attempt %d/%d). Retrying in %.2f s...",
            response.status_code,
            self.model.value,
            attempt + 1,
            self.max_retries,
            backoff_time,
          )
          time.sleep(backoff_time)
          backoff_time *= 2 * (1 + random.random())
          continue

        else:
          # Unrecoverable error
          logging.error(
            "Unrecoverable error (status %d) for model %s (Attempt %d/%d): %s",
            response.status_code,
            self.model.value,
            attempt + 1,
            self.max_retries,
            response.text,
          )
          break

      except requests.exceptions.RequestException as e:
        # Handle network-level errors
        logging.warning(
          "Network error for model %s (Attempt %d/%d): %s. Retrying...",
          self.model.value,
          attempt + 1,
          self.max_retries,
          e,
        )
        time.sleep(backoff_time)
        backoff_time *= 2 * (1 + random.random())

    # If we exit the loop, all retries have been exhausted
    if attempt + 1 >= self.max_retries:
      logging.error(
        "Max retries (%d) exceeded for LLM API call to %s.",
        self.max_retries,
        self.model.value,
      )

    raise LlmApiError(
      f"Failed to get a successful response from {self.model.value}."
    )


def initialize_models(system_prompt: str) -> list[LlmClient]:
  """Initializes LLM clients for all selected models.

  Args:
    system_prompt (str): The system prompt to use for all clients.

  Returns:
    A list of initialized LlmClient instances.
  """

  return [
    LlmClient(model=model, system_prompt=system_prompt) for model in Model
  ]


def get_solvable_models() -> list[Model]:
  """Returns a list of models suitable for solving standard physics problems.

  Returns:
    A list of Model enum members.
  """
  return initialize_models(prompts.PHYSICS_SOLVER_PROMPT)


def get_unsolvable_models() -> list[Model]:
  """Returns a list of models suitable for tackling unsolvable physics problems.

  Returns:
    A list of Model enum members.
  """
  return initialize_models(prompts.PHYSICS_THEORIST_PROMPT)


def get_evaluator_models() -> list[Model]:
  """Returns a list of models suitable for evaluating physics problem solutions.

  Returns:
    A list of Model enum members.
  """
  return initialize_models(prompts.POINTWISE_EVAL_PROMPT)


def get_ranking_models() -> list[Model]:
  """Returns a list of models suitable for judging physics problem solutions.

  Returns:
    A list of Model enum members.
  """
  return initialize_models(prompts.RANKING_EVAL_PROMPT)
