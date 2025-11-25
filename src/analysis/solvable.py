"""Solvable question analysis functionality."""

import logging

import requests

from src import evaluation, llm, reporting
from src.analysis.models import (
  CrossEvaluation,
  ModelResponse,
  SolvableQuestionReport,
)
from src.loader import KaggleLoader


def analyze_solvable_question(
  solver_clients: list[llm.LlmClient],
  evaluator_clients: list[llm.LlmClient],
  dataset: KaggleLoader,
  markdown_path: str,
) -> SolvableQuestionReport:
  """Runs one random solvable question against all solvers.

  Then, all evaluators score all solver responses using batch evaluation.
  Results are written to markdown incrementally as they are generated.

  Args:
      solver_clients: List of clients to generate solutions.
      evaluator_clients: List of clients to judge solutions.
      dataset: The KaggleLoader for solvable questions.
      markdown_path: Path to the markdown file to write results to.

  Returns:
      A SolvableQuestionReport with comprehensive cross-evaluation.

  Raises:
      KeyError: If the loaded question content does not contain
          'message_1' (question) or 'message_2' (answer) keys.
  """
  # 1. Get a random question
  logging.info("Retrieving random solvable question")
  try:
    q_id, q_content = dataset.get_random_question()
  except IndexError:
    logging.warning("All random questions have been used. Resetting history.")
    dataset.reset_random_history()
    q_id, q_content = dataset.get_random_question()

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

  # 3. Phase 1: Get all responses
  all_responses: list[ModelResponse] = []
  valid_responses: dict[str, str] = {}  # For batch evaluation

  for client in solver_clients:
    logging.info("Querying solver: %s", client.model.value)
    try:
      response_text = client.call_api(question)
      all_responses.append(
        ModelResponse(
          model_name=client.model.value, response_text=response_text
        )
      )
      valid_responses[client.model.value] = response_text
      reporting.append_response(
        markdown_path, client.model.value, response_text
      )
    except (llm.LlmApiError, requests.exceptions.RequestException) as e:
      logging.error(
        "API call failed for solver model %s: %s", client.model.value, e
      )
      error_message = f"API Error: {e}"
      all_responses.append(
        ModelResponse(
          model_name=client.model.value,
          response_text=error_message,
        )
      )
      reporting.append_response(
        markdown_path, client.model.value, error_message
      )

  # 4. Phase 2: Cross-Evaluation (Batch mode)
  logging.info("Starting batch cross-evaluation phase")

  # Initialize analysis table in markdown
  reporting.start_analysis_table(
    markdown_path,
    list(valid_responses.keys()),
    [c.model.value for c in evaluator_clients],
  )

  # Calculate F1 scores
  for model_resp in all_responses:
    if not model_resp.response_text.startswith("API Error:"):
      logging.info("Running F1 score for %s", model_resp.model_name)
      f1 = evaluation.f1_score(model_resp.response_text, true_answer)
      model_resp.deterministic_scores.append(f1)

  # Batch evaluate with all evaluators
  if valid_responses:
    for evaluator_client in evaluator_clients:
      logging.info(
        "Judge %s evaluating all responses in batch",
        evaluator_client.model.value,
      )
      judge = evaluation.LlmEvaluator(judge_client=evaluator_client)
      scores = judge.evaluate_all_solutions(
        question, valid_responses, true_answer
      )

      # Assign scores to corresponding responses
      for model_resp in all_responses:
        if model_resp.model_name in scores:
          score_value = scores[model_resp.model_name]
          model_resp.llm_evaluations.append(
            CrossEvaluation(
              evaluator_model_name=evaluator_client.model.value,
              evaluation=evaluation.EvaluationScore(
                metric_name="llm_logicality_score",
                score=score_value,
                reasoning=f"Score: {score_value}/5"
                if score_value
                else "Evaluation failed",
              ),
            )
          )

  # Write analysis table rows
  _write_analysis_table_rows(markdown_path, all_responses)

  # 5. Compile and return the final report
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
    # Get F1 score
    f1_str = "N/A"
    for score in model_resp.deterministic_scores:
      if score.metric_name == "f1_score" and score.score is not None:
        f1_str = f"{score.score:.3f}"
        break

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
      filepath, model_resp.model_name, f1_str, evaluator_scores
    )
