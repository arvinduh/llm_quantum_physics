"""LLM-based evaluation functionality."""

import json
import re
import textwrap
from typing import Final, Sequence

import requests
from absl import logging

from src import llm
from src.evaluation.models import EvaluationScore

# A simple regex to parse the score from the evaluator's response
_SCORE_PARSER: Final = re.compile(r"Score:\s*(\d)\/5")


class LlmEvaluator:
  """Uses an LLM to perform qualitative evaluations."""

  def __init__(self, judge_client: llm.LlmClient):
    """Initializes the evaluator with a specific "judge" LLM client.

    Args:
        judge_client: An initialized LlmClient to use for evaluation.
            This client should have the appropriate evaluator prompt.
    """
    self.client = judge_client

  def evaluate_all_solutions(
    self, question: str, responses: dict[str, str], true_answer: str
  ) -> tuple[dict[str, tuple[float | None, str]], float]:
    """Uses the injected LLM client to grade all answers at once.

    Args:
        question: The physics question being evaluated.
        responses: Dictionary mapping model names to their response texts.
        true_answer: The correct answer to the question.

    Returns:
        A tuple of (evaluations_dict, elapsed_time) where:
        - evaluations_dict maps model names to tuples of (score, reasoning)
        - elapsed_time is the time in seconds to perform all evaluations
    """
    # Format all responses for the prompt
    response_block = ""
    for model_name, response_text in responses.items():
      response_block += f"## Response from {model_name}:\n{response_text}\n\n"

    user_prompt = textwrap.dedent(f"""
      ## Question:
      {question}

      ## True Answer:
      {true_answer}

      {response_block}
    """)

    # Create JSON schema for structured output with scores and reasoning
    model_names = list(responses.keys())

    # Build properties for each model with score and reasoning
    model_properties = {}
    for model_name in model_names:
      model_properties[model_name] = {
        "type": "object",
        "properties": {
          "score": {
            "type": "integer",
            "description": f"Score for {model_name} (1-5)",
          },
          "reasoning": {
            "type": "string",
            "description": f"Brief explanation for the score given to {model_name}",
          },
        },
        "required": ["score", "reasoning"],
        "additionalProperties": False,
      }

    response_format = {
      "type": "json_schema",
      "json_schema": {
        "name": "evaluation_scores",
        "strict": True,
        "schema": {
          "type": "object",
          "properties": {
            "evaluations": {
              "type": "object",
              "properties": model_properties,
              "required": model_names,
              "additionalProperties": False,
            }
          },
          "required": ["evaluations"],
          "additionalProperties": False,
        },
      },
    }

    try:
      raw_response, elapsed_time = self.client.call_api(
        user_prompt, response_format=response_format
      )
      # Parse the JSON response
      response_data = json.loads(raw_response)
      evaluations = response_data.get("evaluations", {})

      # Extract scores and reasoning for each model
      result = {}
      for model_name in model_names:
        evaluation = evaluations.get(model_name)
        if evaluation is not None:
          score = evaluation.get("score")
          reasoning = evaluation.get("reasoning", "No reasoning provided")
          if score is not None:
            result[model_name] = (float(score), reasoning)
          else:
            logging.warning(
              "Score for model %s not found in response from judge %s",
              model_name,
              self.client.model.value,
            )
            result[model_name] = (None, reasoning)
        else:
          logging.warning(
            "Evaluation for model %s not found in response from judge %s",
            model_name,
            self.client.model.value,
          )
          result[model_name] = (None, "Evaluation failed")

      return result, elapsed_time

    except (llm.LlmApiError, requests.exceptions.RequestException) as e:
      logging.error("Evaluator call failed: %s", e)
      return (
        {model_name: (None, f"API Error: {e}") for model_name in model_names},
        0.0,
      )
    except (json.JSONDecodeError, KeyError) as e:
      logging.error("Failed to parse evaluator JSON response: %s", e)
      return (
        {model_name: (None, f"Parse Error: {e}") for model_name in model_names},
        0.0,
      )

  def evaluate_solution(
    self, question: str, generated_response: str, true_answer: str
  ) -> EvaluationScore:
    """Uses the injected LLM client to grade a single answer."""
    user_prompt = textwrap.dedent(f"""
      ## Question:
      {question}

      ## True Answer:
      {true_answer}

      ## Generated Answer:
      {generated_response}
    """)

    try:
      raw_response, _ = self.client.call_api(user_prompt)

      # Try to parse the score
      match = _SCORE_PARSER.search(raw_response)
      score = float(match.group(1)) if match else None
      if score is None:
        logging.warning(
          "Could not parse score from LLM response: %s", raw_response
        )

      return EvaluationScore(
        metric_name="llm_logicality_score",
        score=score,
        reasoning=raw_response,
      )
    except (llm.LlmApiError, requests.exceptions.RequestException) as e:
      logging.error("Evaluator call failed: %s", e)
      return EvaluationScore(
        metric_name="llm_logicality_score",
        score=None,
        reasoning=f"Evaluation failed: {e}",
      )

  def rank_hypotheses(
    self, question: str, responses: Sequence[str]
  ) -> tuple[EvaluationScore, float]:
    """Uses the injected LLM client to rank hypotheses.

    Returns:
        A tuple of (EvaluationScore, elapsed_time_seconds)
        The EvaluationScore.reasoning contains a JSON string with:
        - "rankings": list of integers where rankings[i] is the rank (1-N) for response i
        - "explanation": string explaining the ranking rationale
    """
    # Format the list of responses for the prompt
    response_block = ""
    for i, resp in enumerate(responses, 1):
      response_block += f"--- Response {i} ---\n{resp}\n\n"

    user_prompt = textwrap.dedent(f"""
      ## Unsolved Question:
      {question}

      ## Generated Responses:
      {response_block}
    """)

    # Create JSON schema for structured rankings
    num_responses = len(responses)
    response_format = {
      "type": "json_schema",
      "json_schema": {
        "name": "hypothesis_rankings",
        "strict": True,
        "schema": {
          "type": "object",
          "properties": {
            "rankings": {
              "type": "array",
              "description": f"MUST contain exactly {num_responses} integers. rankings[i] is the rank (1 to {num_responses}) assigned to Response {{i+1}}. Lower rank means better quality. Each rank value must be used exactly once.",
              "items": {"type": "integer"},
            },
            "explanation": {
              "type": "string",
              "description": "Brief explanation of the ranking rationale and why each response was ranked as it was.",
            },
          },
          "required": ["rankings", "explanation"],
          "additionalProperties": False,
        },
      },
    }

    try:
      raw_response, elapsed_time = self.client.call_api(
        user_prompt, response_format=response_format
      )
      # Store the full JSON response in reasoning for later parsing
      return EvaluationScore(
        metric_name="llm_hypothesis_ranking",
        score=None,  # No single score for a ranking
        reasoning=raw_response,  # JSON string
      ), elapsed_time
    except (llm.LlmApiError, requests.exceptions.RequestException) as e:
      logging.error("Ranker call failed: %s", e)
      # Return a JSON string with error info
      error_json = json.dumps(
        {"rankings": [0] * num_responses, "explanation": f"Ranking failed: {e}"}
      )
      return EvaluationScore(
        metric_name="llm_hypothesis_ranking",
        score=None,
        reasoning=error_json,
      ), 0.0
