"""Solvable question analysis functionality."""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from absl import logging

from src import evaluation, llm, reporting
from src.analysis.models import (
  CrossEvaluation,
  ModelResponse,
  SolvableQuestionReport,
)
from src.loader import KaggleLoader


def _query_solver(client: llm.LlmClient, question: str) -> ModelResponse:
  """Query a single solver model and return the response.

  Args:
      client: The LLM client to query.
      question: The question to ask.

  Returns:
      ModelResponse with the result or error message.
  """
  logging.info("Querying solver: %s", client.model.value)
  try:
    response_text, elapsed_time = client.call_api(question)
    return ModelResponse(
      model_name=client.model.value,
      response_text=response_text,
      generation_time=elapsed_time,
    )
  except (llm.LlmApiError, requests.exceptions.RequestException) as e:
    logging.error(
      "API call failed for solver model %s: %s", client.model.value, e
    )
    error_message = f"API Error: {e}"
    return ModelResponse(
      model_name=client.model.value,
      response_text=error_message,
      generation_time=0.0,
    )


def analyze_solvable_question(
  solver_clients: list[llm.LlmClient],
  evaluator_clients: list[llm.LlmClient],
  dataset: KaggleLoader,
  output_dir: str,
) -> SolvableQuestionReport:
  """Runs one random solvable question against all solvers.

  Then, all evaluators score all solver responses using batch evaluation.
  Results are written to a markdown file named with the question ID.

  Args:
      solver_clients: List of clients to generate solutions.
      evaluator_clients: List of clients to judge solutions.
      dataset: The KaggleLoader for solvable questions.
      output_dir: Directory to save the output markdown file.

  Returns:
      A SolvableQuestionReport with comprehensive cross-evaluation.

  Raises:
      KeyError: If the loaded question content does not contain
          'message_1' (question) or 'message_2' (answer) keys.
  """
  import os

  # 1. Get a random question that hasn't been solved yet
  os.makedirs(output_dir, exist_ok=True)

  max_attempts = len(dataset.data) if hasattr(dataset, "data") else 1000
  attempts = 0
  q_id = None
  q_content = None

  while attempts < max_attempts:
    try:
      q_id, q_content = dataset.get_random_question()
    except IndexError:
      logging.warning("All random questions have been used. Resetting history.")
      dataset.reset_random_history()
      try:
        q_id, q_content = dataset.get_random_question()
      except IndexError:
        raise ValueError("No questions available in dataset.") from None

    # Check if this question has already been solved
    markdown_path = os.path.join(output_dir, f"solvable_{q_id}.md")
    if not os.path.exists(markdown_path):
      break  # Found an unsolved question

    logging.warning("Question %s already solved, finding another", q_id)
    attempts += 1

  if attempts >= max_attempts:
    raise ValueError(
      "All solvable questions have already been solved. "
      "Delete output files or reset the output directory to run again."
    )

  # 2. Extract data
  try:
    question = q_content["message_1"]
    true_answer = q_content["message_2"]
  except KeyError as e:
    logging.error("Solvable question %s is missing expected keys: %s", q_id, e)
    raise KeyError(
      f"Question {q_id} is missing 'message_1' or 'message_2' key."
    ) from e
  logging.info("Selected solvable question ID: %s", q_id)

  # Write question and true answer to markdown
  reporting.write_solvable_header(markdown_path, q_id, question, true_answer)

  # 3. Phase 1: Get all responses in parallel
  all_responses: list[ModelResponse] = []
  valid_responses: dict[str, str] = {}  # For batch evaluation
  file_lock = threading.Lock()  # Protect concurrent file writes

  logging.info("Querying %d solver models", len(solver_clients))
  with ThreadPoolExecutor(max_workers=len(solver_clients)) as executor:
    # Submit all tasks
    future_to_client = {
      executor.submit(_query_solver, client, question): client
      for client in solver_clients
    }

    try:
      # Collect results as they complete
      for future in as_completed(future_to_client):
        model_resp = future.result()
        all_responses.append(model_resp)

        # Write response to markdown immediately (thread-safe)
        with file_lock:
          reporting.append_response(
            markdown_path, model_resp.model_name, model_resp.response_text
          )

        # Track valid responses for batch evaluation
        if not model_resp.response_text.startswith("API Error:"):
          valid_responses[model_resp.model_name] = model_resp.response_text
    except KeyboardInterrupt:
      logging.warning("Keyboard interrupt received, canceling solver tasks...")
      for future in future_to_client:
        future.cancel()
      executor.shutdown(wait=False, cancel_futures=True)
      raise

  # 4. Phase 2: Cross-Evaluation (Batch mode)
  logging.info("Starting cross-evaluation")

  # Calculate deterministic scores for all responses
  for model_resp in all_responses:
    if not model_resp.response_text.startswith("API Error:"):
      # Token F1 score
      token_f1 = evaluation.f1_score(model_resp.response_text, true_answer)
      model_resp.deterministic_scores.append(token_f1)

      # METEOR score
      meteor = evaluation.meteor_score_eval(
        model_resp.response_text, true_answer
      )
      model_resp.deterministic_scores.append(meteor)

      # ROUGE-L score
      rouge_l = evaluation.rouge_l_score(model_resp.response_text, true_answer)
      model_resp.deterministic_scores.append(rouge_l)

      # Symbol/Math F1 score
      symbol_f1 = evaluation.symbol_precision(
        model_resp.response_text, true_answer
      )
      model_resp.deterministic_scores.append(symbol_f1)

  # Batch evaluate with all evaluators
  evaluator_results = {}  # Store results by evaluator name

  if valid_responses:

    def _run_evaluator(evaluator_client):
      """Run a single evaluator and return results."""
      logging.info(
        "Querying evaluator %s",
        evaluator_client.model.value,
      )
      judge = evaluation.LlmEvaluator(judge_client=evaluator_client)
      scores, elapsed_time = judge.evaluate_all_solutions(
        question, valid_responses, true_answer
      )
      return evaluator_client.model.value, scores, elapsed_time

    # Run all evaluators in parallel and collect results
    with ThreadPoolExecutor(max_workers=len(evaluator_clients)) as executor:
      future_to_evaluator = {
        executor.submit(_run_evaluator, client): client
        for client in evaluator_clients
      }

      try:
        for future in as_completed(future_to_evaluator):
          evaluator_name, results, eval_time = future.result()
          evaluator_results[evaluator_name] = (results, eval_time)
      except KeyboardInterrupt:
        logging.warning(
          "Keyboard interrupt received, canceling evaluator tasks..."
        )
        for future in future_to_evaluator:
          future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise

  # Now assign scores to responses in the correct order
  evaluator_names = [c.model.value for c in evaluator_clients]
  for model_resp in all_responses:
    for evaluator_name in evaluator_names:
      if evaluator_name in evaluator_results:
        results, eval_time = evaluator_results[evaluator_name]
        if model_resp.model_name in results:
          score_value, reasoning = results[model_resp.model_name]
          model_resp.llm_evaluations.append(
            CrossEvaluation(
              evaluator_model_name=evaluator_name,
              evaluation=evaluation.EvaluationScore(
                metric_name="llm_logicality_score",
                score=score_value,
                reasoning=reasoning,
              ),
              evaluation_time=eval_time,
            )
          )

  # Initialize analysis table in markdown AFTER all evaluations complete
  reporting.start_analysis_table(
    markdown_path,
    list(valid_responses.keys()),
    evaluator_names,
  )

  # Write analysis table rows
  _write_analysis_table_rows(markdown_path, all_responses)

  # Write evaluator reasoning section
  reporting.start_evaluator_reasoning_section(markdown_path)
  _write_evaluator_reasoning(markdown_path, all_responses, evaluator_names)

  # Write timing summary
  generation_times = {
    resp.model_name: resp.generation_time
    for resp in all_responses
    if resp.generation_time > 0
  }
  evaluation_times = {}
  for model_resp in all_responses:
    for eval_item in model_resp.llm_evaluations:
      if eval_item.evaluation_time > 0:
        evaluation_times[eval_item.evaluator_model_name] = (
          eval_item.evaluation_time
        )

  if generation_times or evaluation_times:
    reporting.write_timing_summary(
      markdown_path, generation_times, evaluation_times
    )

  # 5. Compile and return the final report
  logging.info("Solvable question report saved to: %s", markdown_path)
  return SolvableQuestionReport(
    question_id=q_id,
    question=question,
    true_answer=true_answer,
    responses=all_responses,
  )


def _write_analysis_table_rows(
  filepath: str, responses: list[ModelResponse]
) -> None:
  """Writes the analysis table rows to the markdown file."""
  for model_resp in responses:
    # Get deterministic scores
    scores_dict = {}
    for score in model_resp.deterministic_scores:
      if score.score is not None:
        scores_dict[score.metric_name] = f"{score.score:.3f}"
      else:
        scores_dict[score.metric_name] = "N/A"

    # Get scores in order
    token_f1 = scores_dict.get("token_f1", "N/A")
    meteor = scores_dict.get("meteor", "N/A")
    rouge_l = scores_dict.get("rouge_l", "N/A")
    symbol_f1 = scores_dict.get("symbol_f1", "N/A")

    # Collect evaluator scores
    evaluator_scores = []
    for eval_item in model_resp.llm_evaluations:
      score_val = (
        str(int(eval_item.evaluation.score))
        if eval_item.evaluation.score is not None
        else "N/A"
      )
      evaluator_scores.append(score_val)

    reporting.write_analysis_table_row(
      filepath,
      model_resp.model_name,
      token_f1,
      meteor,
      rouge_l,
      symbol_f1,
      evaluator_scores,
    )


def _write_evaluator_reasoning(
  filepath: str, responses: list[ModelResponse], evaluator_names: list[str]
) -> None:
  """Writes the evaluator reasoning section to the markdown file."""
  for evaluator_name in evaluator_names:
    for model_resp in responses:
      # Find the evaluation from this evaluator for this response
      for eval_item in model_resp.llm_evaluations:
        if eval_item.evaluator_model_name == evaluator_name:
          score_val = (
            f"{int(eval_item.evaluation.score)}/5"
            if eval_item.evaluation.score is not None
            else "N/A"
          )
          reporting.write_evaluator_reasoning(
            filepath,
            evaluator_name,
            model_resp.model_name,
            score_val,
            eval_item.evaluation.reasoning,
          )
