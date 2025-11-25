"""Markdown report writing utilities."""


def write_solvable_header(
  filepath: str, q_id: str, question: str, true_answer: str
) -> None:
  """Writes the question header to a markdown file.

  Args:
      filepath: Path to the markdown file.
      q_id: Question identifier.
      question: The question text.
      true_answer: The correct answer.
  """
  with open(filepath, "w", encoding="utf-8") as f:
    f.write(f"# Solvable Question Analysis (ID: {q_id})\n\n")
    f.write(f"## Question\n{question}\n\n")
    f.write(f"## True Answer\n{true_answer}\n\n")
    f.write("## Model Responses\n\n")


def append_response(filepath: str, model_name: str, response: str) -> None:
  """Appends a model's response to the markdown file.

  Args:
      filepath: Path to the markdown file.
      model_name: Name of the model.
      response: The response text from the model.
  """
  with open(filepath, "a", encoding="utf-8") as f:
    f.write(f"### {model_name}\n")
    if response.startswith("API Error:"):
      f.write(f"**Error:** {response}\n\n")
    else:
      f.write(f"{response}\n\n")


def start_analysis_table(
  filepath: str, model_names: list[str], evaluator_names: list[str]
) -> None:
  """Starts the analysis table in the markdown file.

  Args:
      filepath: Path to the markdown file.
      model_names: List of model names that generated responses.
      evaluator_names: List of evaluator model names.
  """
  with open(filepath, "a", encoding="utf-8") as f:
    f.write("## Analysis Table\n\n")
    # Header row
    header = "| Response | Token F1 | METEOR | ROUGE-L | Symbol F1 |"
    for evaluator in evaluator_names:
      header += f" {evaluator} |"
    f.write(header + "\n")
    # Separator row
    separator = "| --- | --- | --- | --- | --- |"
    for _ in evaluator_names:
      separator += " --- |"
    f.write(separator + "\n")


def write_analysis_table_row(
  filepath: str,
  model_name: str,
  token_f1: str,
  meteor: str,
  rouge_l: str,
  symbol_f1: str,
  evaluator_scores: list[str],
) -> None:
  """Writes a single row to the analysis table.

  Args:
      filepath: Path to the markdown file.
      model_name: Name of the model.
      token_f1: The token F1 score as a formatted string.
      meteor: The METEOR score as a formatted string.
      rouge_l: The ROUGE-L score as a formatted string.
      symbol_f1: The symbol F1 score as a formatted string.
      evaluator_scores: List of scores from each evaluator.
  """
  with open(filepath, "a", encoding="utf-8") as f:
    row = f"| {model_name} | {token_f1} | {meteor} | {rouge_l} | {symbol_f1} |"
    for score in evaluator_scores:
      row += f" {score} |"
    f.write(row + "\n")


def start_evaluator_reasoning_section(filepath: str) -> None:
  """Starts the evaluator reasoning section in the markdown file.

  Args:
      filepath: Path to the markdown file.
  """
  with open(filepath, "a", encoding="utf-8") as f:
    f.write("\n## Evaluator Reasoning\n\n")


def write_evaluator_reasoning(
  filepath: str,
  evaluator_name: str,
  model_name: str,
  score: str,
  reasoning: str,
) -> None:
  """Writes an evaluator's reasoning for a specific model response.

  Args:
      filepath: Path to the markdown file.
      evaluator_name: Name of the evaluator model.
      model_name: Name of the model being evaluated.
      score: The score given.
      reasoning: The reasoning for the score.
  """
  with open(filepath, "a", encoding="utf-8") as f:
    f.write(f"### {evaluator_name} → {model_name} ({score})\n\n")
    f.write(f"{reasoning}\n\n")


def write_timing_summary(
  filepath: str,
  generation_times: dict[str, float],
  evaluation_times: dict[str, float],
) -> None:
  """Writes a timing summary section to the markdown file.

  Args:
      filepath: Path to the markdown file.
      generation_times: Dict mapping model names to generation times in seconds.
      evaluation_times: Dict mapping evaluator names to evaluation times in seconds.
  """
  with open(filepath, "a", encoding="utf-8") as f:
    f.write("\n## Timing Summary\n\n")
    f.write("| Model | Generation Time | Evaluation Time |\n")
    f.write("| --- | --- | --- |\n")

    # Get all unique model names from both dicts
    all_models = sorted(
      set(generation_times.keys()) | set(evaluation_times.keys())
    )

    for model_name in all_models:
      gen_time = generation_times.get(model_name)
      eval_time = evaluation_times.get(model_name)

      gen_str = f"{gen_time:.2f}s" if gen_time is not None else "N/A"
      eval_str = f"{eval_time:.2f}s" if eval_time is not None else "N/A"

      f.write(f"| {model_name} | {gen_str} | {eval_str} |\n")


def write_unsolvable_timing_summary(
  filepath: str,
  generation_times: dict[str, float],
  ranking_times: dict[str, float],
) -> None:
  """Writes a timing summary for unsolvable question analysis.

  Args:
      filepath: Path to the markdown file.
      generation_times: Dict mapping model names to hypothesis generation times.
      ranking_times: Dict mapping ranker names to ranking times in seconds.
  """
  with open(filepath, "a", encoding="utf-8") as f:
    f.write("\n## Timing Summary\n\n")
    f.write("| Model | Generation Time | Ranking Time |\n")
    f.write("| --- | --- | --- |\n")

    # Get all unique model names from both dicts
    all_models = sorted(
      set(generation_times.keys()) | set(ranking_times.keys())
    )

    for model_name in all_models:
      gen_time = generation_times.get(model_name)
      rank_time = ranking_times.get(model_name)

      gen_str = f"{gen_time:.2f}s" if gen_time is not None else "N/A"
      rank_str = f"{rank_time:.2f}s" if rank_time is not None else "N/A"

      f.write(f"| {model_name} | {gen_str} | {rank_str} |\n")


def write_unsolvable_header(filepath: str) -> None:
  """Initializes the unsolvable question markdown file.

  Args:
      filepath: Path to the markdown file.
  """
  with open(filepath, "w", encoding="utf-8") as f:
    f.write("# Unsolvable Question Analysis\n\n")


def write_unsolvable_question_header(
  filepath: str, q_id: str, question: str
) -> None:
  """Writes a question header for an unsolvable question.

  Args:
      filepath: Path to the markdown file.
      q_id: Question identifier.
      question: The question text.
  """
  with open(filepath, "a", encoding="utf-8") as f:
    f.write(f"## Question {q_id}\n{question}\n\n")
    f.write("### Hypotheses\n\n")


def append_hypothesis(filepath: str, model_name: str, hypothesis: str) -> None:
  """Appends a hypothesis to the markdown file.

  Args:
      filepath: Path to the markdown file.
      model_name: Name of the model.
      hypothesis: The hypothesis text or error message.
  """
  with open(filepath, "a", encoding="utf-8") as f:
    f.write(f"#### {model_name}\n")
    if hypothesis.startswith("API Error:"):
      f.write(f"**Error:** {hypothesis}\n\n")
    else:
      f.write(f"{hypothesis}\n\n")


def start_rankings_section(filepath: str) -> None:
  """Starts the rankings section in the markdown file.

  Args:
      filepath: Path to the markdown file.
  """
  with open(filepath, "a", encoding="utf-8") as f:
    f.write("### Rankings\n\n")


def append_ranking(filepath: str, ranker_name: str, ranking_text: str) -> None:
  """Appends a ranking to the markdown file.

  Args:
      filepath: Path to the markdown file.
      ranker_name: Name of the ranking model.
      ranking_text: The ranking text.
  """
  with open(filepath, "a", encoding="utf-8") as f:
    f.write(f"#### Judge: {ranker_name}\n")
    f.write(f"{ranking_text}\n\n")


def append_no_hypotheses_message(filepath: str) -> None:
  """Appends a message when no valid hypotheses were generated.

  Args:
      filepath: Path to the markdown file.
  """
  with open(filepath, "a", encoding="utf-8") as f:
    f.write("_No valid hypotheses generated for ranking._\n\n")


def append_question_separator(filepath: str) -> None:
  """Appends a separator between questions.

  Args:
      filepath: Path to the markdown file.
  """
  with open(filepath, "a", encoding="utf-8") as f:
    f.write("---\n\n")
