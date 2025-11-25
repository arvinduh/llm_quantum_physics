"""Configuration management for the benchmark."""

from dataclasses import dataclass

from absl import flags

# Dataset configuration
DATASET_HANDLE: str = "mohammadbinaftab/physicsqa"
UNSOLVABLE_QUESTIONS_PATH: str = "data/unsolvable.json"
OUTPUT_DIR: str = "outputs/v3"

# Parallel execution configuration
MAX_PARALLEL_WORKERS: int = 10

# Define command-line flags
_SOLVABLE_ITERATIONS = flags.DEFINE_integer(
  "solvable_iterations",
  1,
  "The number of random solvable questions to run.",
)

_UNSOLVABLE_ITERATIONS = flags.DEFINE_integer(
  "unsolvable_iterations",
  0,
  "The number of unsolvable questions to run.",
)


@dataclass
class BenchmarkConfig:
  """Configuration for a benchmark run."""

  dataset_handle: str
  unsolvable_questions_path: str
  output_dir: str
  solvable_iterations: int
  unsolvable_iterations: int
  max_parallel_workers: int

  @classmethod
  def from_flags(cls) -> "BenchmarkConfig":
    """Create configuration from command-line flags.

    Returns:
        BenchmarkConfig instance with values from flags and constants.
    """
    return cls(
      dataset_handle=DATASET_HANDLE,
      unsolvable_questions_path=UNSOLVABLE_QUESTIONS_PATH,
      output_dir=OUTPUT_DIR,
      solvable_iterations=_SOLVABLE_ITERATIONS.value,
      unsolvable_iterations=_UNSOLVABLE_ITERATIONS.value,
      max_parallel_workers=MAX_PARALLEL_WORKERS,
    )
