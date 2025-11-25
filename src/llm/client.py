"""LLM API client implementation."""

import os
import random
import re
import time

import dotenv
import requests
from absl import logging

from src.llm.models import Model

_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_MAX_RETRIES = 5
_INITIAL_BACKOFF = 1.0  # In seconds


class LlmApiError(Exception):
  """Raised when the LLM API call fails after all retries."""


def _parse_api_error_message(response: requests.Response) -> str:
  """Parses a JSON error for a concise, human-readable message.

  If the response is not a known error format, it returns the
  full text or the extracted 'message' field.

  Args:
      response: The requests.Response object.

  Returns:
      A concise error message or the original response text.
  """
  try:
    data = response.json()
    message = data.get("error", {}).get("message", "")

    if not message:
      return response.text

    # Handle the 402 "Not enough tokens" error
    token_match = re.search(
      r"You requested up to (\d+) tokens, but can only afford (\d+)",
      message,
    )
    if token_match:
      requested = token_match.group(1)
      afforded = token_match.group(2)
      return (
        f"Not enough tokens: Requested {requested}, can only afford {afforded}."
      )

    # Handle the 403 "Key limit exceeded" error
    if "Key limit exceeded (total limit)" in message:
      return "Key limit exceeded (total limit)."

    return message

  except requests.exceptions.JSONDecodeError:
    return response.text
  except Exception:
    pass

  return response.text


class LlmClient:
  """LLM API client with retry and fallback logic.

  Attributes:
      model (Model): The primary model to use for API calls.
      api_key (str): The API key for authentication.
      max_retries (int): Maximum number of retries for transient errors.
      initial_backoff (float): Initial backoff time in seconds for retries.
      system_prompt (str): The system prompt to send with requests.
      max_tokens (int): The maximum number of tokens to request from the model.
  """

  def __init__(
    self,
    model: Model = Model.GEMINI_PRO_2_5,
    api_key: str | None = None,
    max_retries: int = _MAX_RETRIES,
    initial_backoff: float = _INITIAL_BACKOFF,
    system_prompt: str | None = None,
    max_tokens: int = 10000,
  ):
    """Initializes the client.

    Args:
        model: The primary model to use for API calls.
        api_key: The API key for authentication. If None, loaded from .env.
        max_retries: Maximum number of retries for transient errors.
        initial_backoff: Initial backoff time in seconds for retries.
        system_prompt: The system prompt to send with requests.
        max_tokens: The maximum number of tokens to request from the model.
    """
    dotenv.load_dotenv()
    self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not self.api_key:
      raise ValueError(
        "OPENROUTER_API_KEY must be set in .env file or "
        "provided as an argument."
      )

    self.model = model
    self.max_retries = max_retries
    self.initial_backoff = initial_backoff
    self.system_prompt = system_prompt
    self.max_tokens = max_tokens

    self._headers = {
      "Authorization": f"Bearer {self.api_key}",
      "Content-Type": "application/json",
    }

  def call_api(self, prompt: str, response_format: dict | None = None) -> str:
    """Handles the core logic of calling the LLM API with retries.

    Args:
        prompt: The user-facing prompt to send to the model.
        response_format: Optional structured output format specification.

    Returns:
        The text content of the model's response.

    Raises:
        LlmApiError: If the API call fails after all retries.
        requests.exceptions.HTTPError: For unrecoverable HTTP errors.
    """
    payload = {
      "model": self.model.value,
      "messages": [
        {"role": "user", "content": prompt},
      ],
      "max_tokens": self.max_tokens,
    }

    if self.system_prompt:
      payload["messages"].insert(
        0, {"role": "system", "content": self.system_prompt}
      )

    if response_format:
      payload["response_format"] = response_format

    backoff_time = self.initial_backoff
    start_time = time.time()

    for attempt in range(self.max_retries):
      try:
        response = requests.post(
          _API_URL,
          headers=self._headers,
          json=payload,
          timeout=30,
        )

        if response.ok:
          elapsed_time = time.time() - start_time
          logging.info(
            "LLM API call successful for model %s (Attempt %d/%d) - took %.2f seconds",
            self.model.value,
            attempt + 1,
            self.max_retries,
            elapsed_time,
          )
          data = response.json()
          return data["choices"][0]["message"]["content"]

        elif response.status_code in {
          requests.codes.too_many_requests,
          requests.codes.request_timeout,
          requests.codes.service_unavailable,
        }:
          logging.warning(
            "Transient error (status %d) for model %s (Attempt %d/%d). "
            "Retrying in %.2f s...",
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
          error_message = _parse_api_error_message(response)
          logging.error(
            "Unrecoverable error (status %d) for model %s (Attempt %d/%d): %s",
            response.status_code,
            self.model.value,
            attempt + 1,
            self.max_retries,
            error_message,
          )
          break

      except requests.exceptions.RequestException as e:
        logging.warning(
          "Network error for model %s (Attempt %d/%d): %s. Retrying...",
          self.model.value,
          attempt + 1,
          self.max_retries,
          e,
        )
        time.sleep(backoff_time)
        backoff_time *= 2 * (1 + random.random())

    if attempt + 1 >= self.max_retries:
      logging.error(
        "Max retries (%d) exceeded for LLM API call to %s.",
        self.max_retries,
        self.model.value,
      )

    raise LlmApiError(
      f"Failed to get a successful response from {self.model.value}."
    )
