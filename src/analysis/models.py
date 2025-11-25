"""Data models for analysis results."""

import dataclasses

from src.evaluation.models import EvaluationScore


@dataclasses.dataclass
class CrossEvaluation:
  """Holds a single evaluation from one judge model."""

  evaluator_model_name: str
  evaluation: EvaluationScore
  evaluation_time: float = 0.0  # Time in seconds to perform evaluation


@dataclasses.dataclass
class ModelResponse:
  """Holds a model's response and all evaluations of it."""

  model_name: str
  response_text: str
  generation_time: float = 0.0  # Time in seconds to generate response
  deterministic_scores: list[EvaluationScore] = dataclasses.field(
    default_factory=list
  )
  llm_evaluations: list[CrossEvaluation] = dataclasses.field(
    default_factory=list
  )


@dataclasses.dataclass(frozen=True)
class SolvableQuestionReport:
  """Full analysis for one solvable question."""

  question_id: str
  question: str
  true_answer: str
  responses: list[ModelResponse]


@dataclasses.dataclass(frozen=True)
class ModelHypothesis:
  """Holds a single model's hypothesis for an unsolvable question."""

  model_name: str
  response_text: str  # Can be the hypothesis or an error message
  generation_time: float = 0.0  # Time in seconds to generate hypothesis


@dataclasses.dataclass(frozen=True)
class CrossRanking:
  """Holds a single ranking from one judge model."""

  ranker_model_name: str
  ranking: EvaluationScore  # 'reasoning' holds the ranked list
  ranking_time: float = 0.0  # Time in seconds to perform ranking


@dataclasses.dataclass(frozen=True)
class UnsolvableQuestionReport:
  """Full analysis for one unsolvable question."""

  question_id: str
  question: str
  hypotheses: list[ModelHypothesis]
  rankings: list[CrossRanking]
