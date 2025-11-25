"""Kaggle dataset loader implementation."""

import json
import os

import dotenv
import kagglehub
from absl import logging

from src.loader.base import (
  BaseQuestionLoader,
  QuestionContentType,
  QuestionIdentifier,
)

DATASET_HANDLE = "mohammadbinaftab/physicsqa"


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
      "Loaded %d questions from %s",
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

    with open(path, "r", encoding="utf-8") as f:
      question_data = json.load(f)

    return question_data
