"""Runs analysis functions for solvable and unsolvable questions.

This module contains the core logic for the benchmark, orchestrating
the loading of questions, querying of LLM clients, and evaluation of
responses. Results are written to markdown files incrementally.
"""

import dataclasses
import logging

import requests  # For catching request exceptions

# Import project modules
from src import evaluate, llm, loader

# --- 1. Solvable Question Analysis (Cross-Evaluation) ---


def _write_markdown_header(
  filepath: str, q_id: str, question: str, true_answer: str
) -> None:
  """Writes the question header to a markdown file."""
  with open(filepath, "w", encoding="utf-8") as f:
    f.write(f"# Solvable Question Analysis (ID: {q_id})\n\n")
    f.write(f"## Question\n{question}\n\n")
    f.write(f"## True Answer\n{true_answer}\n\n")
    f.write("## Model Responses\n\n")


def _append_response_to_markdown(
  filepath: str, model_name: str, response: str
) -> None:
  """Appends a model's response to the markdown file."""
  with open(filepath, "a", encoding="utf-8") as f:
    f.write(f"### {model_name}\n")
    if response.startswith("API Error:"):
      f.write(f"**Error:** {response}\n\n")
    else:
      f.write(f"{response}\n\n")


def _start_analysis_table(
  filepath: str, model_names: list[str], evaluator_names: list[str]
) -> None:
  """Starts the analysis table in the markdown file."""
  with open(filepath, "a", encoding="utf-8") as f:
    f.write("## Analysis Table\n\n")
    # Header row
    header = "| Response | F1 Score |"
    for evaluator in evaluator_names:
      header += f" {evaluator} |"
    f.write(header + "\n")
    # Separator row
    separator = "| --- | --- |"
    for _ in evaluator_names:
      separator += " --- |"
    f.write(separator + "\n")


def _write_analysis_table_rows(
  filepath: str, responses: list["ModelResponse"]
) -> None:
  """Writes the analysis table rows to the markdown file."""
  with open(filepath, "a", encoding="utf-8") as f:
    for model_resp in responses:
      # Get F1 score
      f1_str = "N/A"
      for score in model_resp.deterministic_scores:
        if score.metric_name == "f1_score" and score.score is not None:
          f1_str = f"{score.score:.3f}"
          break

      # Start row with model name and F1 score
      row = f"| {model_resp.model_name} | {f1_str} |"

      # Add evaluator scores
      for eval_item in model_resp.llm_evaluations:
        score_val = (
          str(int(eval_item.evaluation.score))
          if eval_item.evaluation.score is not None
          else "N/A"
        )
        row += f" {score_val} |"

      f.write(row + "\n")


@dataclasses.dataclass
class CrossEvaluation:
  """Holds a single evaluation from one judge model."""

  evaluator_model_name: str
  evaluation: evaluate.EvaluationScore


@dataclasses.dataclass
class ModelResponse:
  """Holds a model's response and all evaluations of it."""

  model_name: str
  response_text: str
  deterministic_scores: list[evaluate.EvaluationScore] = dataclasses.field(
    default_factory=list
  )
  llm_evaluations: list[CrossEvaluation] = dataclasses.field(
    default_factory=list
  )


@dataclasses.dataclass(frozen=True)
class SolvableQuestionReport:
  """Full analysis for one solvable question.

  Contains the question, the true answer, and a list of responses,
  where each response has been evaluated by deterministic metrics
  and all other LLM evaluate.
  """

  question_id: str
  question: str
  true_answer: str
  responses: list[ModelResponse]


def one_solvable_question(
  solver_clients: list[llm.LlmClient],
  evaluator_clients: list[llm.LlmClient],
  dataset: loader.KaggleLoader,
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

  # 2. Extract data (schema based on your example)
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
  _write_markdown_header(markdown_path, q_id, question, true_answer)

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
      # Write response to markdown immediately
      _append_response_to_markdown(
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
      _append_response_to_markdown(
        markdown_path, client.model.value, error_message
      )

  # 4. Phase 2: Cross-Evaluation (Batch mode)
  logging.info("Starting batch cross-evaluation phase")

  # Initialize analysis table in markdown
  _start_analysis_table(
    markdown_path,
    list(valid_responses.keys()),
    [c.model.value for c in evaluator_clients],
  )

  for model_resp in all_responses:
    # Skip evaluation if the response itself was an error
    if model_resp.response_text.startswith("API Error:"):
      continue

    # Get deterministic scores
    logging.info("Running F1 score for %s", model_resp.model_name)
    f1 = evaluate.f1_score(model_resp.response_text, true_answer)
    model_resp.deterministic_scores.append(f1)

  # Batch evaluate with all evaluators
  if valid_responses:
    for evaluator_client in evaluator_clients:
      logging.info(
        "Judge %s evaluating all responses in batch",
        evaluator_client.model.value,
      )
      judge = evaluate.LlmEvaluator(judge_client=evaluator_client)
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
              evaluation=evaluate.EvaluationScore(
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


# --- 2. Unsolvable Question Analysis (Cross-Ranking) ---


@dataclasses.dataclass(frozen=True)
class ModelHypothesis:
  """Holds a single model's hypothesis for an unsolvable question."""

  model_name: str
  response_text: str  # Can be the hypothesis or an error message


@dataclasses.dataclass(frozen=True)
class CrossRanking:
  """Holds a single ranking from one judge model."""

  ranker_model_name: str
  ranking: evaluate.EvaluationScore  # 'reasoning' holds the ranked list


@dataclasses.dataclass(frozen=True)
class UnsolvableQuestionReport:
  """Full analysis for one unsolvable question.

  Contains the question, all generated hypotheses, and a list of
  rankings, one from each ranking model.
  """

  question_id: str
  question: str
  hypotheses: list[ModelHypothesis]
  rankings: list[CrossRanking]


def one_unsolvable_question(
  solver_clients: list[llm.LlmClient],
  ranking_clients: list[llm.LlmClient],
  dataset: loader.JsonLoader,
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
  with open(markdown_path, "w", encoding="utf-8") as f:
    f.write("# Unsolvable Question Analysis\n\n")

  # 1. Loop through all sequential questions
  while True:
    try:
      q_id, q_content = dataset.get_next_question()
      # Per the unsolvable example JSON, the key is 'question'
      question = q_content["question"]
      logging.info("Processing unsolvable question ID: %s", q_id)
    except IndexError:
      logging.info("Finished all sequential unsolvable questions.")
      break  # All questions have been processed
    except KeyError as e:
      logging.error(
        "Dataset schema error: %s. Expected 'question' key. Skipping.",
        e,
      )
      continue

    # Write question header to markdown
    with open(markdown_path, "a", encoding="utf-8") as f:
      f.write(f"## Question {q_id}\n{question}\n\n")
      f.write("### Hypotheses\n\n")

    # 2. Phase 1: Get all hypotheses
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
        # Write hypothesis to markdown immediately
        with open(markdown_path, "a", encoding="utf-8") as f:
          f.write(f"#### {client.model.value}\n{response_text}\n\n")
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
        with open(markdown_path, "a", encoding="utf-8") as f:
          f.write(f"#### {client.model.value}\n**Error:** {error_message}\n\n")

    # 3. Phase 2: Cross-Ranking
    all_rankings: list[CrossRanking] = []
    if not valid_hypotheses_text:
      logging.warning(
        "No valid hypotheses generated for question %s. Skipping ranking.",
        q_id,
      )
      with open(markdown_path, "a", encoding="utf-8") as f:
        f.write("_No valid hypotheses generated for ranking._\n\n")
    else:
      with open(markdown_path, "a", encoding="utf-8") as f:
        f.write("### Rankings\n\n")

      for ranker_client in ranking_clients:
        logging.info(
          "Judge %s ranking %d hypotheses.",
          ranker_client.model.value,
          len(valid_hypotheses_text),
        )
        judge = evaluate.LlmEvaluator(judge_client=ranker_client)
        ranking = judge.rank_hypotheses(question, valid_hypotheses_text)
        all_rankings.append(
          CrossRanking(
            ranker_model_name=ranker_client.model.value,
            ranking=ranking,
          )
        )
        # Write ranking to markdown immediately
        with open(markdown_path, "a", encoding="utf-8") as f:
          f.write(f"#### Judge: {ranker_client.model.value}\n")
          f.write(f"{ranking.reasoning}\n\n")

    # 4. Compile report for this question
    reports.append(
      UnsolvableQuestionReport(
        question_id=q_id,
        question=question,
        hypotheses=hypotheses,
        rankings=all_rankings,
      )
    )

    # Add separator between questions
    with open(markdown_path, "a", encoding="utf-8") as f:
      f.write("---\n\n")

  return reports
