"""Deterministic evaluation functions."""

import re
from collections import Counter

from src.evaluation.models import EvaluationScore


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
