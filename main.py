"""
Main execution loop for the LLM Physics Benchmark.

This script initializes LLM clients, loads datasets, runs analyses for
both solvable and unsolvable questions, and saves the results to
markdown files.
"""

import logging as std_logging
from typing import Sequence

import colorlog
from absl import app, flags, logging

from src import analysis, llm, loader


def setup_colored_logging():
  """Configure colored logging output."""
  handler = colorlog.StreamHandler()
  handler.setFormatter(
    colorlog.ColoredFormatter(
      "%(log_color)s%(levelname).1s%(asctime)s.%(msecs)03d %(process)d [%(filename)s:%(lineno)d]%(reset)s %(message)s",
      datefmt="%m%d %H:%M:%S",
      log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "red,bg_white",
      },
    )
  )

  logger = std_logging.getLogger()
  logger.handlers = []
  logger.addHandler(handler)
  logger.setLevel(std_logging.INFO)


# --- Constants ---
DATASET_HANDLE: str = "mohammadbinaftab/physicsqa"
UNSOLVABLE_QUESTIONS_PATH: str = "data/unsolvable.json"
OUTPUT_DIR: str = "outputs/v3"

# Define a flag for how many solvable questions to run
_SOLVABLE_ITERATIONS = flags.DEFINE_integer(
  "solvable_iterations",
  1,
  "The number of random solvable questions to run.",
)

# Define a flag for how many unsolvable questions to run
_UNSOLVABLE_ITERATIONS = flags.DEFINE_integer(
  "unsolvable_iterations",
  0,
  "The number of unsolvable questions to run.",
)


# --- Main Execution ---


def main(argv: Sequence[str]) -> None:
  """Main execution function for the benchmark."""
  del argv

  setup_colored_logging()

  # --- 1. Load Datasets ---
  logging.info("Loading solvable questions from Kaggle: %s", DATASET_HANDLE)
  solvable_dataset = loader.KaggleLoader(DATASET_HANDLE)

  logging.info(
    "Loading unsolvable questions from JSON: %s",
    UNSOLVABLE_QUESTIONS_PATH,
  )
  unsolvable_dataset = loader.JsonLoader(UNSOLVABLE_QUESTIONS_PATH)

  # --- 2. Initialize All Clients ---
  # As per your new functions in `llm.py`, we initialize
  # lists of clients, each with the correct system prompt.
  logging.info("Initializing LLM clients")
  solver_clients = llm.get_solvable_models()
  evaluator_clients = llm.get_evaluator_models()
  theorist_clients = llm.get_unsolvable_models()
  ranking_clients = llm.get_ranking_models()

  # --- 3. Run Solvable Question Analysis ---
  logging.info(
    "Running %d solvable question iteration(s)",
    _SOLVABLE_ITERATIONS.value,
  )
  solvable_reports: list[analysis.SolvableQuestionReport] = []
  for i in range(_SOLVABLE_ITERATIONS.value):
    logging.info(
      "Starting solvable iteration %d/%d", i + 1, _SOLVABLE_ITERATIONS.value
    )
    report = analysis.analyze_solvable_question(
      solver_clients=solver_clients,
      evaluator_clients=evaluator_clients,
      dataset=solvable_dataset,
      output_dir=OUTPUT_DIR,
    )
    solvable_reports.append(report)
    logging.info(
      "Completed solvable iteration %d/%d", i + 1, _SOLVABLE_ITERATIONS.value
    )

  # --- 4. Run Unsolvable Question Analysis ---
  logging.info(
    "Running %d unsolvable question iteration(s)",
    _UNSOLVABLE_ITERATIONS.value,
  )
  unsolvable_reports: list[analysis.UnsolvableQuestionReport] = []
  for i in range(_UNSOLVABLE_ITERATIONS.value):
    logging.info(
      "Starting unsolvable iteration %d/%d", i + 1, _UNSOLVABLE_ITERATIONS.value
    )
    report = analysis.analyze_unsolvable_question(
      solver_clients=theorist_clients,
      ranking_clients=ranking_clients,
      dataset=unsolvable_dataset,
      output_dir=OUTPUT_DIR,
    )
    unsolvable_reports.append(report)
    logging.info(
      "Completed unsolvable iteration %d/%d",
      i + 1,
      _UNSOLVABLE_ITERATIONS.value,
    )

  logging.info("Benchmark run complete.")


if __name__ == "__main__":
  app.run(main)
