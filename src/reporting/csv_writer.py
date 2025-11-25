"""CSV writing functionality for benchmark results."""

import csv
import os
from typing import Any

from src.analysis.models import (
  SolvableQuestionReport,
  UnsolvableQuestionReport,
)


def write_solvable_csv(
  reports: list[SolvableQuestionReport],
  output_dir: str,
) -> None:
  """Write solvable question results to a CSV file.

  CSV columns include: question_id, question, true_answer, model,
  response, time, token_f1, meteor, rouge_l, symbol_f1, and
  evaluator ratings (model1_rating, model2_rating, etc.).

  Args:
      reports: List of SolvableQuestionReport objects.
      output_dir: Directory to save the CSV file.
  """
  if not reports:
    return

  csv_dir = os.path.join(output_dir, "csv")
  csv_path = os.path.join(csv_dir, "solvable.csv")
  os.makedirs(csv_dir, exist_ok=True)

  # Collect all evaluator names across all reports
  evaluator_names = set()
  for report in reports:
    for response in report.responses:
      for eval_item in response.llm_evaluations:
        evaluator_names.add(eval_item.evaluator_model_name)
  evaluator_names = sorted(evaluator_names)

  # Define CSV headers (excluding question, true_answer, response)
  headers = [
    "question_id",
    "model",
    "time",
    "token_f1",
    "meteor",
    "rouge_l",
    "symbol_f1",
  ]
  # Add evaluator rating columns
  for evaluator in evaluator_names:
    headers.append(f"{evaluator}_rating")

  # Write CSV
  with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=headers)
    writer.writeheader()

    for report in reports:
      for response in report.responses:
        row: dict[str, Any] = {
          "question_id": report.question_id,
          "model": response.model_name,
          "time": response.generation_time,
        }

        # Add deterministic scores
        for score in response.deterministic_scores:
          if score.metric_name in [
            "token_f1",
            "meteor",
            "rouge_l",
            "symbol_f1",
          ]:
            row[score.metric_name] = (
              score.score if score.score is not None else ""
            )

        # Add evaluator ratings
        for eval_item in response.llm_evaluations:
          col_name = f"{eval_item.evaluator_model_name}_rating"
          row[col_name] = (
            eval_item.evaluation.score
            if eval_item.evaluation.score is not None
            else ""
          )

        # Fill in missing evaluator columns with empty strings
        for evaluator in evaluator_names:
          col_name = f"{evaluator}_rating"
          if col_name not in row:
            row[col_name] = ""

        writer.writerow(row)


def write_unsolvable_csv(
  reports: list[UnsolvableQuestionReport],
  output_dir: str,
) -> None:
  """Write unsolvable question results to a CSV file.

  This creates a CSV with hypothesis-level data (one row per hypothesis).
  Rankings from each ranker model are included as columns showing the rank
  assigned to that specific hypothesis.

  CSV columns include: question_id, question, model, hypothesis, time,
  and {ranker_model}_rank columns for each ranker.

  Args:
      reports: List of UnsolvableQuestionReport objects.
      output_dir: Directory to save the CSV file.
  """
  import json

  if not reports:
    return

  csv_dir = os.path.join(output_dir, "csv")
  csv_path = os.path.join(csv_dir, "unsolvable.csv")
  os.makedirs(csv_dir, exist_ok=True)

  # Collect all ranker names across all reports
  ranker_names = set()
  for report in reports:
    for ranking in report.rankings:
      ranker_names.add(ranking.ranker_model_name)
  ranker_names = sorted(ranker_names)

  # Define CSV headers (excluding question and hypothesis)
  headers = [
    "question_id",
    "model",
    "time",
  ]
  # Add ranker ranking columns
  for ranker in ranker_names:
    headers.append(f"{ranker}_rank")

  # Write CSV
  with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=headers)
    writer.writeheader()

    for report in reports:
      for hyp_idx, hypothesis in enumerate(report.hypotheses):
        row: dict[str, Any] = {
          "question_id": report.question_id,
          "model": hypothesis.model_name,
          "time": hypothesis.generation_time,
        }

        # Add ranker rankings - parse JSON and extract rank for this hypothesis
        for ranking in report.rankings:
          col_name = f"{ranking.ranker_model_name}_rank"
          try:
            # Parse the JSON response
            ranking_data = json.loads(ranking.ranking.reasoning)
            rankings_list = ranking_data.get("rankings", [])

            # Get the rank for this hypothesis (hyp_idx corresponds to Response i+1)
            if hyp_idx < len(rankings_list):
              row[col_name] = rankings_list[hyp_idx]
            else:
              row[col_name] = ""
          except (json.JSONDecodeError, KeyError, TypeError):
            # If parsing fails, leave empty
            row[col_name] = ""

        # Fill in missing ranker columns with empty strings
        for ranker in ranker_names:
          col_name = f"{ranker}_rank"
          if col_name not in row:
            row[col_name] = ""

        writer.writerow(row)


def write_evaluations_csv(
  solvable_reports: list[SolvableQuestionReport],
  unsolvable_reports: list[UnsolvableQuestionReport],
  output_dir: str,
) -> None:
  """Write evaluation results to a separate CSV file.

  This CSV contains information about the evaluations themselves,
  including: question_type, question_id, evaluator_model, time, etc.

  Args:
      solvable_reports: List of SolvableQuestionReport objects.
      unsolvable_reports: List of UnsolvableQuestionReport objects.
      output_dir: Directory to save the CSV file.
  """
  csv_dir = os.path.join(output_dir, "csv")
  csv_path = os.path.join(csv_dir, "evaluations.csv")
  os.makedirs(csv_dir, exist_ok=True)

  headers = [
    "question_type",
    "question_id",
    "evaluator_model",
    "evaluated_model",
    "time",
    "score",
  ]

  with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=headers)
    writer.writeheader()

    # Write solvable evaluations
    for report in solvable_reports:
      for response in report.responses:
        for eval_item in response.llm_evaluations:
          row = {
            "question_type": "solvable",
            "question_id": report.question_id,
            "evaluator_model": eval_item.evaluator_model_name,
            "evaluated_model": response.model_name,
            "time": eval_item.evaluation_time,
            "score": (
              eval_item.evaluation.score
              if eval_item.evaluation.score is not None
              else ""
            ),
          }
          writer.writerow(row)

    # Write unsolvable evaluations (rankings)
    for report in unsolvable_reports:
      for ranking in report.rankings:
        row = {
          "question_type": "unsolvable",
          "question_id": report.question_id,
          "evaluator_model": ranking.ranker_model_name,
          "evaluated_model": "",  # Rankings evaluate all hypotheses together
          "time": ranking.ranking_time,
          "score": "",  # Rankings don't have numeric scores
        }
        writer.writerow(row)
