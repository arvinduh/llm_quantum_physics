"""
Main execution loop for the LLM Physics Benchmark.

This script initializes LLM clients, loads datasets, runs analyses for
both solvable and unsolvable questions, and saves the results to
markdown files.
"""

import logging
from typing import Sequence

from absl import app, flags

from src import analysis, llm, loader

# --- Constants ---
DATASET_HANDLE: str = "mohammadbinaftab/physicsqa"
UNSOLVABLE_QUESTIONS_PATH: str = "data/unsolvable.json"
SOLVABLE_REPORT_PATH: str = "solvable_report.md"
UNSOLVABLE_REPORT_PATH: str = "unsolvable_report.md"

# Define a flag for how many solvable questions to run
_SOLVABLE_ITERATIONS = flags.DEFINE_integer(
  "solvable_iterations",
  1,
  "The number of random solvable questions to run.",
)


# --- Main Execution ---


def main(argv: Sequence[str]) -> None:
  """Main execution function for the benchmark."""
  del argv

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
  logging.info("Initializing LLM clients...")
  solver_clients = llm.get_solvable_models()
  evaluator_clients = llm.get_evaluator_models()
  theorist_clients = llm.get_unsolvable_models()
  ranking_clients = llm.get_ranking_models()

  # --- 3. Run Solvable Question Analysis ---
  logging.info(
    "Running %d solvable question iteration(s)...",
    _SOLVABLE_ITERATIONS.value,
  )
  solvable_reports: list[analysis.SolvableQuestionReport] = []
  for i in range(_SOLVABLE_ITERATIONS.value):
    logging.info("--- Solvable Iteration %d ---", i + 1)
    report = analysis.analyze_solvable_question(
      solver_clients=solver_clients,
      evaluator_clients=evaluator_clients,
      dataset=solvable_dataset,
      markdown_path=SOLVABLE_REPORT_PATH,
    )
    solvable_reports.append(report)
    logging.info("--- Finished Iteration %d ---", i + 1)
    logging.info("Solvable analysis report saved to: %s", SOLVABLE_REPORT_PATH)

  # --- 4. Run Unsolvable Question Analysis ---
  logging.info("Running unsolvable question analysis...")
  analysis.analyze_unsolvable_questions(
    solver_clients=theorist_clients,
    ranking_clients=ranking_clients,
    dataset=unsolvable_dataset,
    markdown_path=UNSOLVABLE_REPORT_PATH,
  )

  logging.info(
    "Unsolvable analysis report saved to: %s", UNSOLVABLE_REPORT_PATH
  )

  logging.info("Benchmark run complete.")


if __name__ == "__main__":
  app.run(main)
