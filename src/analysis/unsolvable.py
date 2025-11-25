"""Unsolvable question analysis functionality."""

import logging

import requests

from src import evaluation, llm, reporting
from src.analysis.models import (
  CrossRanking,
  ModelHypothesis,
  UnsolvableQuestionReport,
)
from src.loader import JsonLoader


def analyze_unsolvable_questions(
  solver_clients: list[llm.LlmClient],
  ranking_clients: list[llm.LlmClient],
  dataset: JsonLoader,
  markdown_path: str,
) -> list[UnsolvableQuestionReport]:
  """Runs ALL unsolvable questions sequentially against all solvers.

  Then, all ranking models rank the full set of hypotheses for each question.
  Results are written to markdown incrementally.

  Args:
      solver_clients: List of clients to generate hypotheses.
      ranking_clients: List of clients to rank the hypotheses.
      dataset: The JsonLoader for unsolvable questions.
      markdown_path: Path to the markdown file to write results to.

  Returns:
      A list of UnsolvableQuestionReport objects, one for each question.
  """
  logging.info("Starting sequential run of all unsolvable questions")
  reports: list[UnsolvableQuestionReport] = []
  dataset.reset_sequential_history()

  # Initialize markdown file
  reporting.write_unsolvable_header(markdown_path)

  # Loop through all sequential questions
  while True:
    try:
      q_id, q_content = dataset.get_next_question()
      question = q_content["question"]
      logging.info("Processing unsolvable question ID: %s", q_id)
    except IndexError:
      logging.info("Finished all sequential unsolvable questions.")
      break
    except KeyError as e:
      logging.error(
        "Dataset schema error: %s. Expected 'question' key. Skipping.",
        e,
      )
      continue

    # Write question header to markdown
    reporting.write_unsolvable_question_header(markdown_path, q_id, question)

    # Phase 1: Get all hypotheses
    hypotheses: list[ModelHypothesis] = []
    valid_hypotheses_text: list[str] = []

    for client in solver_clients:
      logging.info("Querying solver: %s", client.model.value)
      try:
        response_text = client.call_api(question)
        hypotheses.append(
          ModelHypothesis(
            model_name=client.model.value,
            response_text=response_text,
          )
        )
        valid_hypotheses_text.append(response_text)
        reporting.append_hypothesis(
          markdown_path, client.model.value, response_text
        )
      except (llm.LlmApiError, requests.exceptions.RequestException) as e:
        logging.error(
          "API call failed for solver model %s: %s",
          client.model.value,
          e,
        )
        error_message = f"API Error: {e}"
        hypotheses.append(
          ModelHypothesis(
            model_name=client.model.value,
            response_text=error_message,
          )
        )
        reporting.append_hypothesis(
          markdown_path, client.model.value, error_message
        )

    # Phase 2: Cross-Ranking
    all_rankings: list[CrossRanking] = []
    if not valid_hypotheses_text:
      logging.warning(
        "No valid hypotheses generated for question %s. Skipping ranking.",
        q_id,
      )
      reporting.append_no_hypotheses_message(markdown_path)
    else:
      reporting.start_rankings_section(markdown_path)

      for ranker_client in ranking_clients:
        logging.info(
          "Judge %s ranking %d hypotheses.",
          ranker_client.model.value,
          len(valid_hypotheses_text),
        )
        judge = evaluation.LlmEvaluator(judge_client=ranker_client)
        ranking = judge.rank_hypotheses(question, valid_hypotheses_text)
        all_rankings.append(
          CrossRanking(
            ranker_model_name=ranker_client.model.value,
            ranking=ranking,
          )
        )
        reporting.append_ranking(
          markdown_path, ranker_client.model.value, ranking.reasoning
        )

    # Compile report for this question
    reports.append(
      UnsolvableQuestionReport(
        question_id=q_id,
        question=question,
        hypotheses=hypotheses,
        rankings=all_rankings,
      )
    )

    # Add separator between questions
    reporting.append_question_separator(markdown_path)

  return reports
