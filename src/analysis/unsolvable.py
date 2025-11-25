"""Unsolvable question analysis functionality."""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from absl import logging

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


def analyze_unsolvable_question(
  solver_clients: list[llm.LlmClient],
  ranking_clients: list[llm.LlmClient],
  dataset: JsonLoader,
  output_dir: str,
) -> UnsolvableQuestionReport:
  """Runs one unsolvable question against all solvers.

  Then, all ranking models rank the full set of hypotheses for the question.
  Results are written to a markdown file named with the question ID.

  Args:
      solver_clients: List of clients to generate hypotheses.
      ranking_clients: List of clients to rank the hypotheses.
      dataset: The JsonLoader for unsolvable questions.
      output_dir: Directory to save the output markdown file.

  Returns:
      An UnsolvableQuestionReport object.
  """
  import os

  # Ensure output directory exists
  os.makedirs(output_dir, exist_ok=True)

  # Find an unsolved question
  max_attempts = 1000  # Prevent infinite loop
  attempts = 0
  q_id = None
  question = None

  while attempts < max_attempts:
    try:
      q_id, q_content = dataset.get_next_question()
      question = q_content["question"]
    except IndexError:
      # Reached end of dataset, reset and try again
      logging.info("Reached end of dataset, resetting")
      dataset.reset_sequential_history()
      try:
        q_id, q_content = dataset.get_next_question()
        question = q_content["question"]
      except IndexError:
        raise ValueError("No questions available in dataset.") from None
    except KeyError as e:
      logging.error(
        "Dataset schema error: %s. Expected 'question' key. Skipping.",
        e,
      )
      attempts += 1
      continue

    # Check if this question has already been solved
    markdown_path = os.path.join(output_dir, f"unsolvable_{q_id}.md")
    if not os.path.exists(markdown_path):
      break  # Found an unsolved question

    logging.warning("Question %s already solved, finding another", q_id)
    attempts += 1

  if attempts >= max_attempts:
    raise ValueError(
      "All unsolvable questions have already been solved. "
      "Delete output files or reset the output directory to run again."
    )

  logging.info("Processing unsolvable question ID: %s", q_id)

  # Initialize markdown file with header
  reporting.write_unsolvable_header(markdown_path)

  # Write question header to markdown
  reporting.write_unsolvable_question_header(markdown_path, q_id, question)

  # Phase 1: Get all hypotheses in parallel
  hypotheses: list[ModelHypothesis] = []
  valid_hypotheses_text: list[str] = []
  file_lock = threading.Lock()  # Protect concurrent file writes

  logging.info("Querying %d solver models", len(solver_clients))
  with ThreadPoolExecutor(max_workers=len(solver_clients)) as executor:
    # Submit all tasks
    future_to_client = {
      executor.submit(_query_theorist, client, question): client
      for client in solver_clients
    }

    try:
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
    except KeyboardInterrupt:
      logging.warning("Keyboard interrupt received, canceling solver tasks...")
      for future in future_to_client:
        future.cancel()
      executor.shutdown(wait=False, cancel_futures=True)
      raise

  # Phase 2: Cross-Ranking
  all_rankings: list[CrossRanking] = []
  if not valid_hypotheses_text:
    logging.warning(
      "No valid hypotheses generated for question %s. Skipping ranking.",
      q_id,
    )
    reporting.append_no_hypotheses_message(markdown_path)
  else:

    def _run_ranker(ranker_client):
      """Run a single ranker and return results."""
      logging.info(
        "Querying ranker %s",
        ranker_client.model.value,
      )
      judge = evaluation.LlmEvaluator(judge_client=ranker_client)
      ranking = judge.rank_hypotheses(question, valid_hypotheses_text)
      return ranker_client.model.value, ranking

    # Run all rankers in parallel and collect results
    ranker_results = {}
    with ThreadPoolExecutor(max_workers=len(ranking_clients)) as executor:
      future_to_ranker = {
        executor.submit(_run_ranker, client): client
        for client in ranking_clients
      }

      try:
        for future in as_completed(future_to_ranker):
          ranker_name, ranking = future.result()
          ranker_results[ranker_name] = ranking
      except KeyboardInterrupt:
        logging.warning(
          "Keyboard interrupt received, canceling ranker tasks..."
        )
        for future in future_to_ranker:
          future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise

    # Write rankings section AFTER all rankers complete
    reporting.start_rankings_section(markdown_path)

    # Write rankings in the order of ranking_clients
    for client in ranking_clients:
      ranker_name = client.model.value
      if ranker_name in ranker_results:
        ranking = ranker_results[ranker_name]
        all_rankings.append(
          CrossRanking(
            ranker_model_name=ranker_name,
            ranking=ranking,
          )
        )
        reporting.append_ranking(markdown_path, ranker_name, ranking.reasoning)

  # Compile report for this question
  report = UnsolvableQuestionReport(
    question_id=q_id,
    question=question,
    hypotheses=hypotheses,
    rankings=all_rankings,
  )

  logging.info("Unsolvable question report saved to: %s", markdown_path)
  return report
