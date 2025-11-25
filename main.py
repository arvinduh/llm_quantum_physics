"""
Main execution loop for the LLM Physics Benchmark.

This script orchestrates the entire benchmark workflow:
1. Initializes configuration and logging
2. Loads datasets
3. Initializes LLM clients
4. Runs benchmark iterations in parallel
5. Generates CSV reports
"""

from typing import Sequence

from absl import app, logging

from src import config, llm, loader, orchestration, reporting, utils


def main(argv: Sequence[str]) -> None:
  """Main execution function for the benchmark.

  Args:
      argv: Command-line arguments (unused, handled by absl.flags).
  """
  del argv

  # Setup logging
  utils.setup_colored_logging()

  # Load configuration from flags
  cfg = config.BenchmarkConfig.from_flags()

  # Load datasets
  logging.info("Loading solvable questions from Kaggle: %s", cfg.dataset_handle)
  solvable_dataset = loader.KaggleLoader(cfg.dataset_handle)

  logging.info(
    "Loading unsolvable questions from JSON: %s",
    cfg.unsolvable_questions_path,
  )
  unsolvable_dataset = loader.JsonLoader(cfg.unsolvable_questions_path)

  # Initialize LLM clients
  logging.info("Initializing LLM clients")
  solver_clients = llm.get_solvable_models()
  evaluator_clients = llm.get_evaluator_models()
  theorist_clients = llm.get_unsolvable_models()
  ranking_clients = llm.get_ranking_models()

  # Create benchmark runner
  runner = orchestration.BenchmarkRunner(
    solver_clients=solver_clients,
    evaluator_clients=evaluator_clients,
    theorist_clients=theorist_clients,
    ranking_clients=ranking_clients,
    solvable_dataset=solvable_dataset,
    unsolvable_dataset=unsolvable_dataset,
    output_dir=cfg.output_dir,
    max_workers=cfg.max_parallel_workers,
  )

  # Run all iterations in parallel
  solvable_reports, unsolvable_reports = runner.run_iterations(
    solvable_iterations=cfg.solvable_iterations,
    unsolvable_iterations=cfg.unsolvable_iterations,
  )

  # Generate CSV reports
  if solvable_reports or unsolvable_reports:
    logging.info("Generating CSV files")

    if solvable_reports:
      reporting.write_solvable_csv(solvable_reports, cfg.output_dir)
      logging.info("Wrote solvable.csv")

    if unsolvable_reports:
      reporting.write_unsolvable_csv(unsolvable_reports, cfg.output_dir)
      logging.info("Wrote unsolvable.csv")

    reporting.write_evaluations_csv(
      solvable_reports, unsolvable_reports, cfg.output_dir
    )
    logging.info("Wrote evaluations.csv")

  logging.info("Benchmark run complete.")


if __name__ == "__main__":
  app.run(main)
