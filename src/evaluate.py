"""
Defines evaluators for the quantum physics LLM benchmark.

This module provides two types of evaluators:
1.  **Deterministic Evaluators:** Fast, objective functions (e.g., F1).
2.  **LLM-based Evaluator:** A class that uses an LLM to provide
    qualitative scores (logicality) and rankings (novelty).
"""

import re
import textwrap
from collections import Counter
from dataclasses import dataclass
from typing import Final, Sequence

import requests
from absl import logging

# Import your client, models, and prompts
from src import llm, prompts

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

  def __init__(self, judge_model: llm.Model = llm.Model.GEMINI_PRO_2_5):
    """
    Initializes the evaluator with a specific "judge" LLM.

    It's highly recommended to use a top-tier model (like GPT-4o or
    Claude 3 Opus) as the judge for the most reliable results.

    Args:
      judge_model: The model to use for performing the evaluation.
    """
    logging.info("Initializing LlmEvaluator with judge model: %s", judge_model)
    self.client = llm.LlmClient(model=judge_model)

  def evaluate_solution(
    self, question: str, generated_response: str, true_answer: str
  ) -> EvaluationScore:
    """Uses an LLM to grade the logicality of a single answer."""
    logging.info(
      "Requesting LLM-based logicality score from judge: %s",
      self.client.model.value,
    )
    self.client.system_prompt = prompts.POINTWISE_EVAL_PROMPT

    # Generate the user prompt for the judge
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
    """Uses an LLM to rank a list of hypotheses for an unsolved problem."""
    logging.info(
      "Requesting LLM-based ranking from judge: %s", self.client.model.value
    )
    self.client.system_prompt = prompts.RANKING_EVAL_PROMPT

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
