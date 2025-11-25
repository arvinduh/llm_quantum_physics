"""Loads questions from Kaggle and local JSON files.

Provides an abstract base class and two concrete implementations for loading
programming questions:
  - KaggleLoader: Loads individual .json files from a Kaggle dataset.
  - JsonLoader: Loads a list of questions from a single .json file.
"""

import abc
import json
import os
import random
from typing import Any, TypeAlias

import dotenv
import kagglehub
from absl import logging

# Datasets to use
DATASET_HANDLE = "mohammadbinaftab/physicsqa"
UNSOLVABLE_QUESTIONS_PATH = "data/unsolvable.json"

# Use TypeAlias for complex type definitions.
QuestionContentType: TypeAlias = dict[str, Any]
QuestionIdentifier: TypeAlias = str


def setup_kaggle_auth(
  kaggle_username: str | None = None, kaggle_key: str | None = None
) -> None:
  """Sets up Kaggle authentication from environment variables.

  Reads KAGGLE_USERNAME and KAGGLE_KEY from .env file and sets them
  as environment variables for kagglehub to use.

  Args:
    kaggle_username: Kaggle username. If None, read from .env.
    kaggle_key: Kaggle API key. If None, read from .env.
  """
  dotenv.load_dotenv()

  kaggle_username = kaggle_username or os.getenv("KAGGLE_USERNAME")
  kaggle_key = kaggle_key or os.getenv("KAGGLE_KEY")

  if not kaggle_username or not kaggle_key:
    # [cite_start]Wrap long strings using implicit line joining. [cite: 538, 561-562]
    raise ValueError(
      "KAGGLE_USERNAME and KAGGLE_KEY must be set in .env file. "
      "You can find your credentials at "
      "https://www.kaggle.com/settings/account"
    )

  # Set environment variables for kagglehub
  os.environ["KAGGLE_USERNAME"] = kaggle_username
  os.environ["KAGGLE_KEY"] = kaggle_key


def retrieve_data(
  dataset_handle: str,
  kaggle_username: str | None = None,
  kaggle_key: str | None = None,
) -> str:
  """Retrieves a dataset from Kaggle Hub.

  Args:
    dataset_handle: The name of the dataset to retrieve.
    kaggle_username: Kaggle username. If None, read from .env.
    kaggle_key: Kaggle API key. If None, read from .env.

  Returns:
    The path to the downloaded dataset.
  """
  setup_kaggle_auth(kaggle_username=kaggle_username, kaggle_key=kaggle_key)

  dataset_path = kagglehub.dataset_download(dataset_handle)
  logging.info("Dataset downloaded to: %s", dataset_path)
  return dataset_path


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
    """RetrieFves the next question in a sequence.

    This method is not implemented by all loaders.

    Raises:
      NotImplementedError: If the loader does not support sequential access.
    """
    raise NotImplementedError("This loader does not support sequential access.")


class KaggleLoader(BaseQuestionLoader):
  """Loads questions from a Kaggle dataset directory.

  Assumes each question is a separate .json file.

  Attributes:
    dataset_handle: The handle of the dataset on Kaggle Hub.
    dataset_path: The local path where the dataset is stored.
  """

  def __init__(
    self,
    dataset_handle: str = DATASET_HANDLE,
    kaggle_username: str | None = None,
    kaggle_key: str | None = None,
  ):
    """Initializes the KaggleLoader.

    Args:
      dataset_handle: The handle of the dataset on Kaggle Hub.
      kaggle_username: Kaggle username. If None, read from .env.
      kaggle_key: Kaggle API key. If None, read from .env.
    """
    self.dataset_handle = dataset_handle
    self.dataset_path = retrieve_data(
      dataset_handle, kaggle_username=kaggle_username, kaggle_key=kaggle_key
    )
    # Call super().__init__ after dataset_path is set, as it calls
    # _load_all_identifiers() which depends on it.
    super().__init__()
    logging.info(
      "KaggleLoader initialized with %d questions from %s",
      len(self),
      dataset_handle,
    )

  def _load_all_identifiers(self) -> set[QuestionIdentifier]:
    """Loads all .json filenames from the dataset directory."""
    all_files = {
      file for file in os.listdir(self.dataset_path) if file.endswith(".json")
    }
    # The identifier is the filename without the .json extension.
    return {file.removesuffix(".json") for file in all_files}

  def _load_question(
    self, identifier: QuestionIdentifier
  ) -> QuestionContentType:
    """Reads a specific question file from the dataset."""
    file_name = f"{identifier}.json"
    path = os.path.join(self.dataset_path, file_name)
    logging.info("Reading question file: %s", path)

    with open(path, "r", encoding="utf-8") as f:
      question_data = json.load(f)

    return question_data


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
    # We can use _load_question directly, as get_question adds an
    # unnecessary key check we know will pass.
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
