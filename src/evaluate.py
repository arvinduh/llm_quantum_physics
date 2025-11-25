"""
Defines evaluators for the quantum physics LLM benchmark.

This module provides two types of evaluators:
1.  **Deterministic Evaluators:** Fast, objective functions (e.g., F1).
2.  **LLM-based Evaluator:** A class that uses an LLM to provide
    qualitative scores (logicality) and rankings (novelty).
"""

import json
import re
import textwrap
from collections import Counter
from dataclasses import dataclass
from typing import Final, Sequence

import requests
from absl import logging

# Import your client, models, and prompts
from src import llm

# A simple regex to parse the score from the evaluator's response
_SCORE_PARSER: Final = re.compile(r"Score:\s*(\d)\/5")


@dataclass(frozen=True)
class EvaluationScore:
  """A standardized dataclass for holding an evaluation result."""

  metric_name: str
  score: float | None  # Score (e.g., F1, 1-5) or None for ranking tasks
  reasoning: str  # Justification, raw ranking text, or error message


# --- 1. Deterministic Evaluators (Baseline) ---


def _tokenize(text: str) -> Counter:
  """A simple tokenizer for F1 calculation."""
  tokens = re.findall(r"\b\w+\b", text.lower())
  return Counter(tokens)


def f1_score(generated_response: str, true_answer: str) -> EvaluationScore:
  """Calculates the F1 score between token sets."""
  gen_tokens = _tokenize(generated_response)
  true_tokens = _tokenize(true_answer)

  if not true_tokens and not gen_tokens:
    return EvaluationScore(
      metric_name="f1_score", score=1.0, reasoning="Both empty."
    )
  if not true_tokens or not gen_tokens:
    return EvaluationScore(
      metric_name="f1_score", score=0.0, reasoning="One is empty."
    )

  common = gen_tokens & true_tokens
  num_common = sum(common.values())

  precision = num_common / sum(gen_tokens.values())
  recall = num_common / sum(true_tokens.values())

  f1 = 0.0
  if (precision + recall) > 0:
    f1 = 2 * (precision * recall) / (precision + recall)

  return EvaluationScore(
    metric_name="f1_score",
    score=f1,
    reasoning=f"Precision: {precision:.3f}, Recall: {recall:.3f}",
  )


# --- 2. LLM-based Evaluator (Primary) ---


class LlmEvaluator:
  """Uses an LLM to perform qualitative evaluations."""

  def __init__(self, judge_client: llm.LlmClient):
    """
    Initializes the evaluator with a specific "judge" LLM client.

    Args:
        judge_client: An initialized LlmClient to use for evaluation.
            This client should have the appropriate evaluator prompt.
    """
    logging.info(
      "Initializing LlmEvaluator with judge client: %s",
      judge_client.model.value,
    )
    self.client = judge_client

  def evaluate_all_solutions(
    self, question: str, responses: dict[str, str], true_answer: str
  ) -> dict[str, float | None]:
    """Uses the injected LLM client to grade all answers at once.

    Args:
        question: The physics question being evaluated.
        responses: Dictionary mapping model names to their response texts.
        true_answer: The correct answer to the question.

    Returns:
        Dictionary mapping model names to scores (1-5) or None if parsing failed.
    """
    logging.info(
      "Requesting batch LLM-based logicality scores from judge: %s",
      self.client.model.value,
    )

    # Format all responses for the prompt
    response_block = ""
    for model_name, response_text in responses.items():
      response_block += f"## Response from {model_name}:\n{response_text}\n\n"

    user_prompt = textwrap.dedent(f"""
      ## Question:
      {question}

      ## True Answer:
      {true_answer}

      {response_block}
    """)

    # Create JSON schema for structured output
    model_names = list(responses.keys())
    response_format = {
      "type": "json_schema",
      "json_schema": {
        "name": "evaluation_scores",
        "strict": True,
        "schema": {
          "type": "object",
          "properties": {
            "scores": {
              "type": "object",
              "properties": {
                model_name: {
                  "type": "integer",
                  "description": f"Score for {model_name} (1-5)",
                  "minimum": 1,
                  "maximum": 5,
                }
                for model_name in model_names
              },
              "required": model_names,
              "additionalProperties": False,
            }
          },
          "required": ["scores"],
          "additionalProperties": False,
        },
      },
    }

    try:
      raw_response = self.client.call_api(
        user_prompt, response_format=response_format
      )
      # Parse the JSON response
      response_data = json.loads(raw_response)
      scores = response_data.get("scores", {})

      # Convert to float and validate
      result = {}
      for model_name in model_names:
        score = scores.get(model_name)
        if score is not None:
          result[model_name] = float(score)
        else:
          logging.warning(
            "Score for model %s not found in response from judge %s",
            model_name,
            self.client.model.value,
          )
          result[model_name] = None

      return result

    except (llm.LlmApiError, requests.exceptions.RequestException) as e:
      logging.error("LLM evaluator call failed: %s", e)
      return {model_name: None for model_name in model_names}
    except (json.JSONDecodeError, KeyError) as e:
      logging.error("Failed to parse JSON response from evaluator: %s", e)
      return {model_name: None for model_name in model_names}

  def evaluate_solution(
    self, question: str, generated_response: str, true_answer: str
  ) -> EvaluationScore:
    """Uses the injected LLM client to grade a single answer."""
    logging.info(
      "Requesting LLM-based logicality score from judge: %s",
      self.client.model.value,
    )
    # The client should already have the system prompt set
    # from when it was initialized (e.g., by `get_evaluator_models`).

    user_prompt = textwrap.dedent(f"""
      ## Question:
      {question}

      ## True Answer:
      {true_answer}

      ## Generated Answer:
      {generated_response}
    """)

    try:
      raw_response = self.client.call_api(user_prompt)

      # Try to parse the score
      match = _SCORE_PARSER.search(raw_response)
      score = float(match.group(1)) if match else None
      if score is None:
        logging.warning(
          "Could not parse score from LLM response: %s", raw_response
        )

      return EvaluationScore(
        metric_name="llm_logicality_score",
        score=score,
        reasoning=raw_response,
      )
    except (llm.LlmApiError, requests.exceptions.RequestException) as e:
      logging.error("LLM evaluator call failed: %s", e)
      return EvaluationScore(
        metric_name="llm_logicality_score",
        score=None,
        reasoning=f"Evaluation failed: {e}",
      )

  def rank_hypotheses(
    self, question: str, responses: Sequence[str]
  ) -> EvaluationScore:
    """Uses the injected LLM client to rank hypotheses."""
    logging.info(
      "Requesting LLM-based ranking from judge: %s",
      self.client.model.value,
    )
    # The client should already have the ranking system prompt.

    # Format the list of responses for the prompt
    response_block = ""
    for i, resp in enumerate(responses, 1):
      response_block += f"--- Response {i} ---\n{resp}\n\n"

    user_prompt = textwrap.dedent(f"""
      ## Unsolved Question:
      {question}

      ## Generated Responses:
      {response_block}
    """)
    try:
      raw_ranking_text = self.client.call_api(user_prompt)
      return EvaluationScore(
        metric_name="llm_hypothesis_ranking",
        score=None,  # No single score for a ranking
        reasoning=raw_ranking_text,
      )
    except (llm.LlmApiError, requests.exceptions.RequestException) as e:
      logging.error("LLM evaluator call failed: %s", e)
      return EvaluationScore(
        metric_name="llm_hypothesis_ranking",
        score=None,
        reasoning=f"Ranking failed: {e}",
      )
