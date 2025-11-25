from absl import app

from src import analysis, llm, loader

DATASET_HANDLE = "mohammadbinaftab/physicsqa"
UNSOLVABLE_QUESTIONS_PATH = "data/unsolvable.json"


def main(argv) -> None:
  del argv  # Unused

  # Load solvable questions
  dataset = loader.KaggleLoader(DATASET_HANDLE)
  # unsolvable = loader.JsonLoader(UNSOLVABLE_QUESTIONS_PATH)

  models = llm.get_solvable_models()

  print(analysis.one_solvable_question(models, dataset))


if __name__ == "__main__":
  app.run(main)
