#!/usr/bin/env python3
"""
Command-line interface for FocalPrompt
"""

import argparse
import sys
import os
from pathlib import Path
from focal_assessor import assess_focus, FocalAssessor


def main():
    parser = argparse.ArgumentParser(
        description="Assess the relative focus of attention in LLM outputs"
    )
    parser.add_argument(
        "prompt",
        type=str,
        help="The original prompt/input (or path to file containing it)"
    )
    parser.add_argument(
        "output",
        type=str,
        nargs="?",
        default=None,
        help="The LLM output to assess (or path to file containing it). Omit to generate using agent."
    )
    parser.add_argument(
        "--generate-output",
        action="store_true",
        help="Generate output using an agent instead of providing it"
    )
    parser.add_argument(
        "--agent-model",
        type=str,
        default=None,
        help="Model to use for generating output (default: same as --model)"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="OpenAI API key (or set OPENAI_API_KEY env var)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="Model to use for assessment (default: gpt-4o-mini)"
    )
    parser.add_argument(
        "--max-foci",
        type=int,
        default=None,
        help="Maximum number of foci to identify"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON instead of human-readable format"
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Save results to a file"
    )
    
    args = parser.parse_args()
    
    # Read prompt (file or direct text)
    if os.path.isfile(args.prompt):
        with open(args.prompt, 'r') as f:
            prompt = f.read()
    else:
        prompt = args.prompt
    
    # Read output (file or direct text) or generate it
    if args.generate_output or args.output is None:
        output = None  # Will be generated
    elif os.path.isfile(args.output):
        with open(args.output, 'r') as f:
            output = f.read()
    else:
        output = args.output
    
    # Check for API key
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OpenAI API key required.", file=sys.stderr)
        print("Set OPENAI_API_KEY environment variable or use --api-key flag.", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Perform assessment
        assessment = assess_focus(
            prompt=prompt,
            output=output,
            api_key=api_key,
            model=args.model,
            agent_model=args.agent_model,
            max_foci=args.max_foci,
            generate_output=args.generate_output or (output is None)
        )
        
        # Output results
        if args.json:
            result = assessment.to_json()
            print(result)
        else:
            assessment.print_summary()
        
        # Save to file if requested
        if args.output_file:
            with open(args.output_file, 'w') as f:
                f.write(assessment.to_json())
            print(f"\nResults saved to {args.output_file}")
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

