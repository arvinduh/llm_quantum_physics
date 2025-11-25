"""Runs analysis functions for solvable and unsolvable questions.

This module contains the core logic for the benchmark, orchestrating
the loading of questions, querying of LLM clients, and evaluation of
responses.
"""

import dataclasses
import logging

import requests  # For catching request exceptions

# Import project modules
from src import evaluate, llm, loader, prompts

# --- 1. Solvable Question Analysis ---


@dataclasses.dataclass(frozen=True)
class ModelEvaluation:
  """Holds the evaluation for a single model's response.

  Attributes:
      model_name: The identifier of the model that was evaluated.
      response: The raw text response from the model.
      scores: A list of scores (e.g., F1, logicality) for the response.
  """

  model_name: str
  response: str
  scores: list[evaluate.EvaluationScore]


@dataclasses.dataclass(frozen=True)
class SolvableQuestionReport:
  """Full analysis for one solvable question.

  Attributes:
      question_id: The unique identifier for the question.
      question: The text of the question.
      true_answer: The ground-truth answer.
      evaluations: A list of evaluations, one for each model.
  """

  question_id: str
  question: str
  true_answer: str
  evaluations: list[ModelEvaluation]


def one_solvable_question(
  clients: list[llm.LlmClient], dataset: loader.KaggleLoader
) -> SolvableQuestionReport:
  """Runs one random solvable question against all clients and evaluates.

  This function performs the following steps:
  1.  Retrieves a single random question from the KaggleLoader.
  2.  Initializes an LLM-based evaluator.
  3.  For each client, it generates a response to the question.
  4.  It scores each response using both F1 and the LLM evaluator.
  5.  It returns a consolidated report.

  Args:
      clients: A list of initialized LlmClient instances to query.
      dataset: The KaggleLoader instance for solvable questions.

  Returns:
      A SolvableQuestionReport containing the question, responses, and scores.

  Raises:
      KeyError: If the loaded question content does not contain
          'message_1' (question) or 'message_2' (answer) keys,
          based on the provided example data schema.
  """
  # 1. Get a random question
  logging.info("Retrieving random solvable question...")
  try:
    q_id, q_content = dataset.get_random_question()
  except IndexError:
    # As per the loader.py implementation, this can happen.
    logging.warning("All random questions have been used. Resetting history.")
    dataset.reset_random_history()
    q_id, q_content = dataset.get_random_question()

  # 2. Extract data based on the example JSON schema provided
  #    [cite: 161-163]
  try:
    # Per the solvable example JSON, 'message_1' is the question
    # and 'message_2' is the ground-truth answer.
    question = q_content["message_1"]
    true_answer = q_content["message_2"]
  except KeyError as e:
    logging.error("Solvable question %s is missing expected keys: %s", q_id, e)
    raise KeyError(
      f"Question {q_id} is missing 'message_1' or 'message_2' key."
    ) from e
  logging.info("Selected solvable question ID: %s", q_id)

  # 3. Initialize evaluator
  # This uses the default high-tier model as a judge
  evaluator = evaluate.LlmEvaluator()

  # 4. Get responses and evaluate
  evaluations: list[ModelEvaluation] = []
  for client in clients:
    logging.info("...Querying model: %s", client.model.value)
    # Set the correct prompt for a solvable question
    client.system_prompt = prompts.PHYSICS_SOLVER_PROMPT

    try:
      response_text = client.call_api(question)

      # 5. Score the valid response
      logging.info("...Scoring response from %s", client.model.value)
      f1 = evaluate.f1_score(response_text, true_answer)
      logicality = evaluator.evaluate_solution(
        question, response_text, true_answer
      )
      # The evaluator methods handle their own API errors
      scores = [f1, logicality]

      evaluations.append(
        ModelEvaluation(
          model_name=client.model.value,
          response=response_text,
          scores=scores,
        )
      )

    except (llm.LlmApiError, requests.exceptions.RequestException) as e:
      # Handle failure to get a response from the client [cite: 157]
      logging.error("API call failed for model %s: %s", client.model.value, e)
      evaluations.append(
        ModelEvaluation(
          model_name=client.model.value,
          response=f"API Error: {e}",
          scores=[],  # No scores if API failed
        )
      )

  # 6. Compile and return the final report
  return SolvableQuestionReport(
    question_id=q_id,
    question=question,
    true_answer=true_answer,
    evaluations=evaluations,
  )


# --- 2. Unsolvable Question Analysis ---


@dataclasses.dataclass(frozen=True)
class ModelResponse:
  """Holds a single model's response for ranking.

  Attributes:
      model_name: The identifier of the model.
      response: The raw text response or an error message.
  """

  model_name: str
  response: str


@dataclasses.dataclass(frozen=True)
class UnsolvableQuestionReport:
  """Full analysis for one unsolvable question.

  Attributes:
      question_id: The unique identifier (index) for the question.
      question: The text of the question.
      responses: A list of responses, one from each model.
      ranking: An EvaluationScore object where the 'reasoning' field
          contains the full text of the LLM judge's ranking.
  """

  question_id: str
  question: str
  responses: list[ModelResponse]
  ranking: evaluate.EvaluationScore


def one_unsolvable_question(
  clients: list[llm.LlmClient], dataset: loader.JsonLoader
) -> list[UnsolvableQuestionReport]:
  """Runs ALL unsolvable questions sequentially against all clients and ranks.

  This function performs the following steps:
  1.  Initializes an LLM-based evaluator.
  2.  Iterates through every question in the JsonLoader sequentially.
  3.  For each question, it gathers one "hypothesis" from each client.
  4.  It sends all valid hypotheses to the LLM evaluator for ranking.
  5.  It compiles a list of reports, one for each question.

  Args:
      clients: A list of initialized LlmClient instances to query.
      dataset: The JsonLoader instance for unsolvable questions.

  Returns:
      A list of UnsolvableQuestionReport objects, one for each question.
  """
  logging.info("Starting sequential run of all unsolvable questions...")
  reports: list[UnsolvableQuestionReport] = []

  # 1. Initialize evaluator
  evaluator = evaluate.LlmEvaluator()
  dataset.reset_sequential_history()

  # 2. Loop through all sequential questions
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
      continue  # Skip this bad question

    # 3. Get all responses for this question
    model_responses: list[ModelResponse] = []
    raw_responses_for_ranking: list[str] = []

    for client in clients:
      logging.info("...Querying model: %s", client.model.value)
      # Set the correct prompt for an unsolvable question
      client.system_prompt = prompts.PHYSICS_THEORIST_PROMPT

      try:
        response_text = client.call_api(question)
        model_responses.append(
          ModelResponse(model_name=client.model.value, response=response_text)
        )
        # Only add valid responses to be ranked
        raw_responses_for_ranking.append(response_text)

      except (llm.LlmApiError, requests.exceptions.RequestException) as e:
        # Handle failure to get a response from the client [cite: 157]
        logging.error("API call failed for model %s: %s", client.model.value, e)
        model_responses.append(
          ModelResponse(
            model_name=client.model.value,
            response=f"API Error: {e}",
          )
        )
        # Do not add the error to the list for ranking

    # 4. Get ranking for the collected valid responses
    logging.info(
      "...Sending %d valid responses to judge for ranking.",
      len(raw_responses_for_ranking),
    )
    ranking_score = evaluator.rank_hypotheses(
      question, raw_responses_for_ranking
    )

    # 5. Compile report for this question
    reports.append(
      UnsolvableQuestionReport(
        question_id=q_id,
        question=question,
        responses=model_responses,
        ranking=ranking_score,
      )
    )

  return reports
