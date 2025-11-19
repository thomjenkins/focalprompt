# FocalPrompt

A tool to assess the relative focus of attention given to different parts of a prompt in LLM outputs.

## Overview

FocalPrompt uses an LLM to analyze how well an output addresses different aspects (foci) of a given prompt. It breaks down the prompt into distinct focus points and assigns points to each one (totaling 100 points) based on the relative level of attention given in the output. Each focus references specific sections of the prompt.

**Key Features:**
- **Web Interface**: Beautiful browser-based UI for easy interaction
- **Auto-Detect Foci**: Agent automatically breaks down prompts into structural components
- **Manual Foci Tagging**: Option to manually define focus points
- **Agent-generated output**: Optionally generate output using an LLM agent before assessment
- **Prompt section references**: Each focus point references specific sections of the original prompt
- **100-point scoring system**: Points are distributed across foci, totaling exactly 100 points

## Installation

### Option 1: Virtual Environment (Recommended)

```bash
# Create a virtual environment
python3 -m venv venv

# Activate it (macOS/Linux)
source venv/bin/activate

# Or on Windows
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Option 2: Direct Installation

```bash
pip install -r requirements.txt
```

**Note:** On some systems (especially macOS with Homebrew Python), you may need to use a virtual environment or add `--user` flag.

## Web Interface

FocalPrompt includes a modern web interface for easy interaction:

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run the web server
python app.py
```

Then open your browser to `http://127.0.0.1:5000` (or `http://localhost:5000`)

**Web Interface Features:**
1. **Enter Your Prompt**: Paste or type your prompt in the text area
2. **Define Foci**: 
   - Click "Auto-Detect Foci" to have an agent automatically break down your prompt into structural components
   - Or click "Add Focus Manually" to define your own focus points
3. **Enter or Generate Output**: 
   - Paste an existing LLM output, or
   - Click "Generate Output" to have an agent create one based on your prompt
4. **Assess Focus**: Click "Assess Focus" to see how attention is distributed across your foci

## Usage

### Basic Usage

#### With Provided Output

```python
from focal_assessor import assess_focus

prompt = """
Write a comprehensive analysis of climate change that includes:
1. The scientific evidence for climate change
2. Economic impacts on different sectors
3. Policy recommendations for governments
4. Individual actions people can take
"""

output = """
Climate change is a pressing issue. The scientific evidence shows rising temperatures
and sea levels. Governments should implement carbon taxes and invest in renewable energy.
"""

# Assess the focus distribution
assessment = assess_focus(
    prompt=prompt,
    output=output,
    api_key="your-api-key-here",  # Optional if OPENAI_API_KEY env var is set
    model="gpt-4o-mini"  # Optional, defaults to gpt-4o-mini
)

# Print human-readable summary
assessment.print_summary()

# Or get structured data
print(assessment.to_json())
```

#### With Agent-Generated Output

```python
from focal_assessor import assess_focus

prompt = """
Write a comprehensive analysis of climate change that includes:
1. The scientific evidence for climate change
2. Economic impacts on different sectors
3. Policy recommendations for governments
4. Individual actions people can take
"""

# Generate output using an agent and assess it
assessment = assess_focus(
    prompt=prompt,
    generate_output=True,  # Use agent to generate output
    model="gpt-4o-mini",
    agent_model="gpt-4o"  # Optional: different model for generation
)

assessment.print_summary()
```

### Advanced Usage

```python
from focal_assessor import FocalAssessor

assessor = FocalAssessor(model="gpt-4o", agent_model="gpt-4o")

# Generate output
output = assessor.generate_output(prompt, temperature=0.7)

# Limit the number of foci identified
assessment = assessor.assess(
    prompt=prompt,
    output=output,
    max_foci=5  # Limit to 5 focus points
)

# Access individual focus scores
for focus_score in assessment.foci:
    print(f"{focus_score.focus}")
    print(f"  Prompt Section: {focus_score.prompt_section}")
    print(f"  Points: {focus_score.score}/100")
    print(f"  Explanation: {focus_score.explanation}")
```

## API Reference

### `assess_focus(prompt, output=None, api_key=None, model="gpt-4o-mini", agent_model=None, max_foci=None, generate_output=False)`

Convenience function to assess focus distribution.

**Parameters:**
- `prompt` (str): The original prompt/input given to the LLM
- `output` (str, optional): The LLM's output/response. If None and `generate_output=True`, will generate it
- `api_key` (str, optional): OpenAI API key. If None, uses `OPENAI_API_KEY` environment variable
- `model` (str): Model to use for assessment (default: "gpt-4o-mini")
- `agent_model` (str, optional): Model to use for generating output (default: same as `model`)
- `max_foci` (int, optional): Maximum number of foci to identify
- `generate_output` (bool): If True and output is None, generate output using an agent

**Returns:**
- `FocusAssessment`: Object containing foci, scores, and explanations

### `FocalAssessor`

Main class for focus assessment.

**Methods:**
- `assess(prompt, output, max_foci=None)`: Assess focus distribution

### `FocusAssessment`

Result object containing:
- `foci`: List of `FocusScore` objects
- `overall_summary`: Brief overall assessment
- `print_summary()`: Print human-readable summary
- `to_json()`: Convert to JSON string
- `to_dict()`: Convert to dictionary

### `FocusScore`

Individual focus point with:
- `focus`: Description of the focus point
- `prompt_section`: Reference to the specific section of the prompt this focus relates to
- `score`: Points assigned (out of 100 total; all scores sum to 100)
- `explanation`: Brief explanation of the score, referencing specific parts of the output

## Command Line Usage

You can also use FocalPrompt from the command line:

```bash
# Basic usage with provided output
python cli.py "Your prompt here" "LLM output here"

# With files
python cli.py prompt.txt output.txt

# Generate output using agent (omit output argument)
python cli.py prompt.txt --generate-output

# Or simply omit the output argument
python cli.py prompt.txt

# Output as JSON
python cli.py prompt.txt output.txt --json

# Save results to file
python cli.py prompt.txt output.txt --output-file results.json

# Specify model and max foci
python cli.py prompt.txt output.txt --model gpt-4o --max-foci 5

# Use different models for generation and assessment
python cli.py prompt.txt --generate-output --agent-model gpt-4o --model gpt-4o-mini
```

## Environment Variables

Set `OPENAI_API_KEY` to avoid passing the API key in code:

```bash
export OPENAI_API_KEY="your-api-key-here"
```

## Example Output

```
============================================================
FOCUS ASSESSMENT RESULTS
============================================================

Overall Summary: The output addresses some aspects but misses key components...

------------------------------------------------------------
Focus Scores (Total must equal 100 points):
------------------------------------------------------------

1. Focus: Scientific evidence for climate change
   Prompt Section: Section 1: "The scientific evidence for climate change"
   Points: 25.0/100
   Explanation: Briefly mentioned rising temperatures and sea levels but lacks detail on specific evidence

2. Focus: Economic impacts on different sectors
   Prompt Section: Section 2: "Economic impacts on different sectors"
   Points: 0.0/100
   Explanation: Not addressed at all

3. Focus: Policy recommendations for governments
   Prompt Section: Section 3: "Policy recommendations for governments"
   Points: 60.0/100
   Explanation: Provides specific recommendations (carbon taxes, renewable energy investment)

4. Focus: Individual actions people can take
   Prompt Section: Section 4: "Individual actions people can take"
   Points: 15.0/100
   Explanation: Implied but not explicitly addressed

Total Points: 100.0/100

============================================================
```

