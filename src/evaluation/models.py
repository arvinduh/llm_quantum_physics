"""Data models for evaluation results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationScore:
  """A standardized dataclass for holding an evaluation result."""

  metric_name: str
  score: float | None  # Score (e.g., F1, 1-5) or None for ranking tasks
  reasoning: str  # Justification, raw ranking text, or error message
