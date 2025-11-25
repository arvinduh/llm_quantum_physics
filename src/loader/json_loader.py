"""JSON file loader implementation."""

import json

from absl import logging

from src.loader.base import (
  BaseQuestionLoader,
  QuestionContentType,
  QuestionIdentifier,
)

UNSOLVABLE_QUESTIONS_PATH = "data/unsolvable.json"


class JsonLoader(BaseQuestionLoader):
  """Loads questions from a single JSON file containing a list.

  Attributes:
    file_path: The path to the JSON file.
    questions: A list of the loaded question objects.
  """

  def __init__(self, file_path: str = UNSOLVABLE_QUESTIONS_PATH):
    """Initializes the JsonLoader.

    Args:
      file_path: The path to the JSON file containing a list of questions.
    """
    self.file_path = file_path

    with open(self.file_path, "r", encoding="utf-8") as f:
      self.questions: list[QuestionContentType] = json.load(f)

    # State for get_next_question()
    self._next_index = 0

    # Call super().__init__ after questions are loaded.
    super().__init__()
    logging.info(
      "JsonLoader initialized with %d questions from %s",
      len(self),
      self.file_path,
    )

  def _load_all_identifiers(self) -> set[QuestionIdentifier]:
    """Generates string-based identifiers from the list indices."""
    return {str(i) for i in range(len(self.questions))}

  def _load_question(
    self, identifier: QuestionIdentifier
  ) -> QuestionContentType:
    """Returns a question by its string-based index."""
    try:
      index = int(identifier)
    except ValueError as e:
      raise KeyError(f"Invalid identifier: '{identifier}'") from e

    if not 0 <= index < len(self.questions):
      raise KeyError(f"Identifier '{identifier}' is out of range.")
    return self.questions[index]

  def get_next_question(
    self,
  ) -> tuple[QuestionIdentifier, QuestionContentType]:
    """Returns the next sequential unsolvable question.

    This method's history is independent of get_random_question.

    Returns:
      A tuple of (question_identifier, question_content).

    Raises:
      IndexError: If all sequential questions have been used.
    """
    if self._next_index >= len(self.questions):
      raise IndexError("All sequential unsolvable questions have been used.")

    identifier = str(self._next_index)
    question_content = self._load_question(identifier)
    self._next_index += 1
    return identifier, question_content

  def reset_sequential_history(self) -> None:
    """Resets the history for get_next_question."""
    self._next_index = 0

  def reset_all_history(self) -> None:
    """Resets all tracking history."""
    self.reset_sequential_history()
    self.reset_random_history()
