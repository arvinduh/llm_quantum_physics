"""Abstract base class for question loaders."""

import abc
import random
from typing import Any, TypeAlias

QuestionContentType: TypeAlias = dict[str, Any]
QuestionIdentifier: TypeAlias = str


class BaseQuestionLoader(abc.ABC):
  """Abstract base class for loading questions.

  This class manages common logic for tracking available questions and
  providing a non-repeating random selection.
  """

  def __init__(self):
    """Initializes the base loader."""
    # _all_identifiers must be populated by the subclass's
    # _load_all_identifiers method.
    self._all_identifiers: set[QuestionIdentifier] = (
      self._load_all_identifiers()
    )
    self._random_used_identifiers: set[QuestionIdentifier] = set()

  @abc.abstractmethod
  def _load_all_identifiers(self) -> set[QuestionIdentifier]:
    """Subclass-specific method to load all unique question identifiers."""
    pass

  @abc.abstractmethod
  def _load_question(
    self, identifier: QuestionIdentifier
  ) -> QuestionContentType:
    """Subclass-specific method to load the content for one question."""
    pass

  def __len__(self) -> int:
    """Returns the total number of questions."""
    return len(self._all_identifiers)

  def get_question(self, identifier: QuestionIdentifier) -> QuestionContentType:
    """Retrieves a specific question by its identifier.

    Args:
      identifier: The unique identifier for the question.

    Returns:
      The content of the question file.

    Raises:
      KeyError: If the identifier is not found.
    """
    if identifier not in self._all_identifiers:
      raise KeyError(f"Question identifier '{identifier}' not found.")
    return self._load_question(identifier)

  def get_random_question(
    self,
  ) -> tuple[QuestionIdentifier, QuestionContentType]:
    """Returns a random, previously unused question.

    This tracks its own "used" list, independent of other methods.

    Returns:
      A tuple of (question_identifier, question_content).

    Raises:
      IndexError: If all questions have been used.
    """
    available_identifiers = (
      self._all_identifiers - self._random_used_identifiers
    )
    if not available_identifiers:
      raise IndexError("All questions have been used by get_random_question.")

    identifier = random.choice(list(available_identifiers))
    self._random_used_identifiers.add(identifier)
    return identifier, self._load_question(identifier)

  def reset_random_history(self) -> None:
    """Resets the history for get_random_question."""
    self._random_used_identifiers.clear()

  def get_next_question(
    self,
  ) -> tuple[QuestionIdentifier, QuestionContentType]:
    """Retrieves the next question in a sequence.

    This method is not implemented by all loaders.

    Raises:
      NotImplementedError: If the loader does not support sequential access.
    """
    raise NotImplementedError("This loader does not support sequential access.")
