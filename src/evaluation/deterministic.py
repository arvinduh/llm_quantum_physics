"""Deterministic evaluation functions."""

import re
from collections import Counter

import nltk
from nltk import word_tokenize
from nltk.translate.meteor_score import meteor_score
from rouge_score import rouge_scorer

from src.evaluation.models import EvaluationScore

# Download required NLTK data (will only download once)
try:
  nltk.data.find("tokenizers/punkt")
except LookupError:
  nltk.download("punkt", quiet=True)
try:
  nltk.data.find("corpora/wordnet")
except LookupError:
  nltk.download("wordnet", quiet=True)


def _tokenize(text: str) -> Counter:
  """A simple tokenizer for F1 calculation."""
  tokens = re.findall(r"\b\w+\b", text.lower())
  return Counter(tokens)


def _extract_symbols_and_numbers(text: str) -> set:
  """Extract mathematical symbols, equations, and numbers from text."""
  # Extract mathematical expressions, symbols, and numbers
  patterns = [
    r"\$[^$]+\$",  # LaTeX inline math
    r"\$\$[^$]+\$\$",  # LaTeX display math
    r"\\[a-zA-Z]+(?:\{[^}]*\})?",  # LaTeX commands
    r"[=≈≠<>≤≥±∓×÷∞∂∇∫∑∏√]",  # Math operators
    r"\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?:\s*[a-zA-Z]+)?\b",  # Numbers with optional units
    r"[α-ωΑ-Ω]",  # Greek letters
    r"\^[\d\w]+",  # Superscripts
    r"_[\d\w]+",  # Subscripts
  ]

  symbols = set()
  for pattern in patterns:
    matches = re.findall(pattern, text)
    symbols.update(matches)

  return symbols


def f1_score(generated_response: str, true_answer: str) -> EvaluationScore:
  """Calculates the F1 score between token sets."""
  gen_tokens = _tokenize(generated_response)
  true_tokens = _tokenize(true_answer)

  if not true_tokens and not gen_tokens:
    return EvaluationScore(
      metric_name="token_f1", score=1.0, reasoning="Both empty."
    )
  if not true_tokens or not gen_tokens:
    return EvaluationScore(
      metric_name="token_f1", score=0.0, reasoning="One is empty."
    )

  common = gen_tokens & true_tokens
  num_common = sum(common.values())

  precision = num_common / sum(gen_tokens.values())
  recall = num_common / sum(true_tokens.values())

  f1 = 0.0
  if (precision + recall) > 0:
    f1 = 2 * (precision * recall) / (precision + recall)

  return EvaluationScore(
    metric_name="token_f1",
    score=f1,
    reasoning=f"Precision: {precision:.3f}, Recall: {recall:.3f}",
  )


def meteor_score_eval(
  generated_response: str, true_answer: str
) -> EvaluationScore:
  """Calculates METEOR score (accounts for synonyms and stemming)."""

  try:
    # Tokenize
    reference = word_tokenize(true_answer.lower())
    hypothesis = word_tokenize(generated_response.lower())

    if not reference and not hypothesis:
      score = 1.0
    elif not reference or not hypothesis:
      score = 0.0
    else:
      score = meteor_score([reference], hypothesis)

    return EvaluationScore(
      metric_name="meteor",
      score=score,
      reasoning=f"METEOR: {score:.3f}",
    )
  except Exception as e:
    return EvaluationScore(
      metric_name="meteor",
      score=None,
      reasoning=f"METEOR calculation failed: {e}",
    )


def rouge_l_score(generated_response: str, true_answer: str) -> EvaluationScore:
  """Calculates ROUGE-L score (longest common subsequence)."""

  try:
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    scores = scorer.score(true_answer, generated_response)

    rouge_l = scores["rougeL"].fmeasure

    return EvaluationScore(
      metric_name="rouge_l",
      score=rouge_l,
      reasoning=f"P: {scores['rougeL'].precision:.3f}, R: {scores['rougeL'].recall:.3f}",
    )
  except Exception as e:
    return EvaluationScore(
      metric_name="rouge_l",
      score=None,
      reasoning=f"ROUGE-L calculation failed: {e}",
    )


def symbol_precision(
  generated_response: str, true_answer: str
) -> EvaluationScore:
  """Calculates precision/recall for mathematical symbols and numbers."""
  gen_symbols = _extract_symbols_and_numbers(generated_response)
  true_symbols = _extract_symbols_and_numbers(true_answer)

  if not true_symbols and not gen_symbols:
    return EvaluationScore(
      metric_name="symbol_f1",
      score=1.0,
      reasoning="No symbols in either text",
    )

  if not true_symbols or not gen_symbols:
    return EvaluationScore(
      metric_name="symbol_f1",
      score=0.0,
      reasoning="Symbols present in only one text",
    )

  common_symbols = gen_symbols & true_symbols

  precision = len(common_symbols) / len(gen_symbols) if gen_symbols else 0
  recall = len(common_symbols) / len(true_symbols) if true_symbols else 0

  f1 = 0.0
  if (precision + recall) > 0:
    f1 = 2 * (precision * recall) / (precision + recall)

  return EvaluationScore(
    metric_name="symbol_f1",
    score=f1,
    reasoning=f"Symbols - P: {precision:.3f}, R: {recall:.3f}, Common: {len(common_symbols)}/{len(true_symbols)}",
  )
