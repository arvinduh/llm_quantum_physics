"""Benchmark runner for parallel execution of iterations."""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from absl import logging

from src import analysis, llm, loader
from src.analysis.models import (
  SolvableQuestionReport,
  UnsolvableQuestionReport,
)


class BenchmarkRunner:
  """Orchestrates parallel execution of benchmark iterations."""

  def __init__(
    self,
    solver_clients: list[llm.LlmClient],
    evaluator_clients: list[llm.LlmClient],
    theorist_clients: list[llm.LlmClient],
    ranking_clients: list[llm.LlmClient],
    solvable_dataset: loader.KaggleLoader,
    unsolvable_dataset: loader.JsonLoader,
    output_dir: str,
    max_workers: int = 10,
  ):
    """Initialize the benchmark runner.

    Args:
        solver_clients: LLM clients for solving solvable questions.
        evaluator_clients: LLM clients for evaluating solutions.
        theorist_clients: LLM clients for generating hypotheses.
        ranking_clients: LLM clients for ranking hypotheses.
        solvable_dataset: Dataset of solvable questions.
        unsolvable_dataset: Dataset of unsolvable questions.
        output_dir: Directory to save results.
        max_workers: Maximum number of parallel workers.
    """
    self.solver_clients = solver_clients
    self.evaluator_clients = evaluator_clients
    self.theorist_clients = theorist_clients
    self.ranking_clients = ranking_clients
    self.solvable_dataset = solvable_dataset
    self.unsolvable_dataset = unsolvable_dataset
    self.output_dir = output_dir
    self.max_workers = max_workers

  def run_iterations(
    self,
    solvable_iterations: int,
    unsolvable_iterations: int,
  ) -> tuple[list[SolvableQuestionReport], list[UnsolvableQuestionReport]]:
    """Run all benchmark iterations in parallel.

    Args:
        solvable_iterations: Number of solvable question iterations to run.
        unsolvable_iterations: Number of unsolvable question iterations to run.

    Returns:
        Tuple of (solvable_reports, unsolvable_reports).
    """
    logging.info("Running %d solvable iteration(s)", solvable_iterations)
    logging.info("Running %d unsolvable iteration(s)", unsolvable_iterations)

    solvable_reports: list[SolvableQuestionReport] = []
    unsolvable_reports: list[UnsolvableQuestionReport] = []
    reports_lock = threading.Lock()  # Protect list append operations

    total_iterations = solvable_iterations + unsolvable_iterations
    if total_iterations == 0:
      logging.warning("No iterations to run")
      return solvable_reports, unsolvable_reports

    max_workers = min(total_iterations, self.max_workers)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
      futures = {}

      # Submit all solvable iterations
      for i in range(solvable_iterations):
        future = executor.submit(
          self._run_solvable_iteration,
          i + 1,
          solvable_iterations,
        )
        futures[future] = ("solvable", i + 1)

      # Submit all unsolvable iterations
      for i in range(unsolvable_iterations):
        future = executor.submit(
          self._run_unsolvable_iteration,
          i + 1,
          unsolvable_iterations,
        )
        futures[future] = ("unsolvable", i + 1)

      # Collect results as they complete
      try:
        for future in as_completed(futures):
          task_type, iteration = futures[future]
          try:
            report = future.result()
            with reports_lock:
              if task_type == "solvable":
                solvable_reports.append(report)
              else:
                unsolvable_reports.append(report)

            # Log outside the lock to avoid blocking
            if task_type == "solvable":
              logging.info(
                "Completed solvable iteration %d/%d",
                iteration,
                solvable_iterations,
              )
            else:
              logging.info(
                "Completed unsolvable iteration %d/%d",
                iteration,
                unsolvable_iterations,
              )
          except Exception as e:
            logging.error(
              "Error in %s iteration %d: %s", task_type, iteration, e
            )
      except KeyboardInterrupt:
        logging.warning("Keyboard interrupt received, canceling all tasks...")
        for future in futures:
          future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise

    return solvable_reports, unsolvable_reports

  def _run_solvable_iteration(
    self,
    iteration: int,
    total: int,
  ) -> SolvableQuestionReport:
    """Run a single solvable iteration.

    Args:
        iteration: Current iteration number.
        total: Total number of iterations.

    Returns:
        A SolvableQuestionReport.
    """
    logging.info("Starting solvable iteration %d/%d", iteration, total)
    return analysis.analyze_solvable_question(
      solver_clients=self.solver_clients,
      evaluator_clients=self.evaluator_clients,
      dataset=self.solvable_dataset,
      output_dir=self.output_dir,
    )

  def _run_unsolvable_iteration(
    self,
    iteration: int,
    total: int,
  ) -> UnsolvableQuestionReport:
    """Run a single unsolvable iteration.

    Args:
        iteration: Current iteration number.
        total: Total number of iterations.

    Returns:
        An UnsolvableQuestionReport.
    """
    logging.info("Starting unsolvable iteration %d/%d", iteration, total)
    return analysis.analyze_unsolvable_question(
      solver_clients=self.theorist_clients,
      ranking_clients=self.ranking_clients,
      dataset=self.unsolvable_dataset,
      output_dir=self.output_dir,
    )
