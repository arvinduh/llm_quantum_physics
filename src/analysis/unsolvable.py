"""Unsolvable question analysis functionality."""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from src import evaluation, llm, reporting
from src.analysis.models import (
  CrossRanking,
  ModelHypothesis,
  UnsolvableQuestionReport,
)
from src.loader import JsonLoader


def _query_theorist(client: llm.LlmClient, question: str) -> ModelHypothesis:
  """Query a single theorist model and return the hypothesis.

  Args:
      client: The LLM client to query.
      question: The question to ask.

  Returns:
      ModelHypothesis with the result or error message.
  """
  logging.info("Querying solver: %s", client.model.value)
  try:
    response_text = client.call_api(question)
    return ModelHypothesis(
      model_name=client.model.value,
      response_text=response_text,
    )
  except (llm.LlmApiError, requests.exceptions.RequestException) as e:
    logging.error(
      "API call failed for solver model %s: %s",
      client.model.value,
      e,
    )
    error_message = f"API Error: {e}"
    return ModelHypothesis(
      model_name=client.model.value,
      response_text=error_message,
    )


def analyze_unsolvable_questions(
  solver_clients: list[llm.LlmClient],
  ranking_clients: list[llm.LlmClient],
  dataset: JsonLoader,
  output_dir: str,
) -> list[UnsolvableQuestionReport]:
  """Runs ALL unsolvable questions sequentially against all solvers.

  Then, all ranking models rank the full set of hypotheses for each question.
  Results are written to separate markdown files per question.

  Args:
      solver_clients: List of clients to generate hypotheses.
      ranking_clients: List of clients to rank the hypotheses.
      dataset: The JsonLoader for unsolvable questions.
      output_dir: Directory to save the output markdown files.

  Returns:
      A list of UnsolvableQuestionReport objects, one for each question.
  """
  import os

  logging.info("Starting sequential run of all unsolvable questions")
  reports: list[UnsolvableQuestionReport] = []
  dataset.reset_sequential_history()

  # Ensure output directory exists
  os.makedirs(output_dir, exist_ok=True)

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

    # Create a separate markdown file for this question
    markdown_path = os.path.join(output_dir, f"unsolvable_{q_id}.md")

    # Initialize markdown file with header
    reporting.write_unsolvable_header(markdown_path)

    # Write question header to markdown
    reporting.write_unsolvable_question_header(markdown_path, q_id, question)

    # Phase 1: Get all hypotheses in parallel
    hypotheses: list[ModelHypothesis] = []
    valid_hypotheses_text: list[str] = []
    file_lock = threading.Lock()  # Protect concurrent file writes

    logging.info(
      "Querying %d solver models in parallel...", len(solver_clients)
    )
    with ThreadPoolExecutor(max_workers=len(solver_clients)) as executor:
      # Submit all tasks
      future_to_client = {
        executor.submit(_query_theorist, client, question): client
        for client in solver_clients
      }

      # Collect results as they complete
      for future in as_completed(future_to_client):
        hypothesis = future.result()
        hypotheses.append(hypothesis)

        # Write hypothesis to markdown immediately (thread-safe)
        with file_lock:
          reporting.append_hypothesis(
            markdown_path, hypothesis.model_name, hypothesis.response_text
          )

        # Track valid hypotheses for ranking
        if not hypothesis.response_text.startswith("API Error:"):
          valid_hypotheses_text.append(hypothesis.response_text)

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

    logging.info("Unsolvable question report saved to: %s", markdown_path)

  return reports
