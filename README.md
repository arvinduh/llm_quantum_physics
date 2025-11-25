# LLM Quantum Physics Benchmark

A comprehensive benchmarking framework for evaluating Large Language Models (LLMs) on quantum physics problems. This project tests both **solvable** and **unsolvable** physics questions to assess LLM reasoning, creativity, and problem-solving capabilities.

## Overview

This benchmark evaluates state-of-the-art LLMs (GPT-5, Gemini Pro 2.5, Grok 4, Claude Sonnet 4.5, and DeepSeek v3) on two types of quantum physics challenges:

- **Solvable Questions**: Standard physics problems with known solutions from a Kaggle dataset
- **Unsolvable Questions**: Open research questions in physics requiring novel hypotheses

### Key Features

- ✅ **Batch Evaluation**: Efficient parallel evaluation of multiple model responses
- ✅ **Structured JSON Outputs**: Uses JSON schemas for reliable score extraction
- ✅ **Incremental Reporting**: Real-time markdown report generation as analyses complete
- ✅ **Performance Timing**: Tracks execution time for each API call
- ✅ **Cross-Evaluation**: Models evaluate each other's responses for comprehensive assessment
- ✅ **Deterministic Metrics**: F1 scores for objective comparison
- ✅ **LLM-Based Metrics**: Logicality scores (1-5) from judge models

## Project Structure

```
llm_benchmarking/
├── src/
│   ├── loader/          # Dataset loading (Kaggle, JSON)
│   ├── llm/             # LLM client and factory functions
│   ├── evaluation/      # Deterministic and LLM-based evaluation
│   ├── analysis/        # Solvable and unsolvable question analysis
│   ├── reporting/       # Markdown report generation
│   └── prompts.py       # System prompts for different tasks
├── data/
│   └── unsolvable.json  # Unsolvable physics questions
├── main.py              # Main execution script
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (not committed)
└── README.md
```

## Setup

### Prerequisites

- Python 3.10 or higher
- Git
- OpenRouter API key
- Kaggle API credentials

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/arvinduh/llm_quantum_physics.git
   cd llm_quantum_physics/llm_benchmarking
   ```

2. **Create and activate a virtual environment**

   **Windows (PowerShell):**

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **macOS/Linux:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**

   Create a `.env` file in the `llm_benchmarking` directory:

   ```env
   # OpenRouter API Key
   OPENROUTER_API_KEY=your_openrouter_api_key_here

   # Kaggle Credentials
   KAGGLE_USERNAME=your_kaggle_username
   KAGGLE_KEY=your_kaggle_api_key
   ```

   **Getting API Keys:**

   - **OpenRouter**: Sign up at [openrouter.ai](https://openrouter.ai/) and get your API key from the dashboard
   - **Kaggle**: Get your credentials from [kaggle.com/settings/account](https://www.kaggle.com/settings/account) (under API section)

## Usage

### Running the Benchmark

Run the full benchmark with default settings:

```bash
python main.py
```

### Configuration Options

**Specify the number of solvable questions to analyze:**

```bash
python main.py --solvable_iterations=5
```

**Customize models used** (edit `src/llm/factory.py`):

```python
DEFAULT_MODELS = [
  Model.GEMINI_PRO_2_5,
  Model.GPT_5,
  Model.GROK_4,
]
```

### Output

The benchmark generates two markdown reports:

- `solvable_report.md` - Analysis of solvable questions with:

  - Question and ground truth answer
  - Model responses
  - F1 scores and LLM evaluation scores in a comparison table

- `unsolvable_report.md` - Analysis of unsolvable questions with:
  - Question and generated hypotheses from each model
  - Rankings from judge models

## How It Works

### Solvable Questions Pipeline

1. **Load Question**: Randomly select from Kaggle physics dataset
2. **Generate Responses**: All solver models answer the question
3. **Calculate F1 Scores**: Compare responses to ground truth using token-based F1
4. **Batch LLM Evaluation**: Judge models evaluate all responses simultaneously using structured JSON output
5. **Generate Report**: Write results to markdown incrementally

### Unsolvable Questions Pipeline

1. **Load Questions**: Process all unsolvable questions sequentially
2. **Generate Hypotheses**: Models propose novel solutions
3. **Rank Hypotheses**: Judge models rank the creativity and plausibility of each hypothesis
4. **Generate Report**: Document all hypotheses and rankings

## Architecture

The codebase follows clean separation of concerns:

- **Loaders**: Abstract base class with Kaggle and JSON implementations
- **LLM Module**: Client with retry logic, model enums, and factory functions
- **Evaluation**: Separate modules for deterministic and LLM-based evaluation
- **Analysis**: Independent modules for solvable and unsolvable question workflows
- **Reporting**: Centralized markdown generation utilities

## Development

### Adding New Models

Edit `src/llm/models.py` to add new model enums, then update `DEFAULT_MODELS` in `src/llm/factory.py`.

### Adding New Metrics

Implement new evaluation functions in `src/evaluation/deterministic.py` or extend `LlmEvaluator` in `src/evaluation/llm_evaluator.py`.

### Custom System Prompts

Modify prompts in `src/prompts.py` to change model behavior.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License

## Acknowledgments

- Physics dataset from [Kaggle - mohammadbinaftab/physicsqa](https://www.kaggle.com/datasets/mohammadbinaftab/physicsqa)
- LLM APIs provided by [OpenRouter](https://openrouter.ai/)
