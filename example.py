"""
Example usage of FocalPrompt
"""

from focal_assessor import assess_focus
import os

# Example 1: Academic writing prompt
academic_prompt = """
Write a research paper on machine learning that covers:
1. Historical development of the field
2. Current state-of-the-art techniques
3. Applications in healthcare
4. Ethical considerations
5. Future directions
"""

academic_output = """
Machine learning has evolved significantly since its inception. Today, deep learning
and neural networks dominate the field. In healthcare, ML is used for diagnostic
imaging and drug discovery. However, we must consider bias and privacy concerns.
"""

# Example 2: Product review prompt
review_prompt = """
Write a product review that evaluates:
- Build quality and materials
- Performance and functionality
- Value for money
- Comparison with competitors
- Overall recommendation
"""

review_output = """
This product is well-built with premium materials. It performs excellently and
offers great value at its price point. I highly recommend it.
"""

def run_example(prompt, output=None, title="", generate_output=False):
    """Run an assessment example."""
    print(f"\n{'='*70}")
    print(f"EXAMPLE: {title}")
    print(f"{'='*70}")
    print(f"\nPROMPT:\n{prompt}")
    if output:
        print(f"\nOUTPUT:\n{output}")
    print(f"\n{'='*70}")
    print("ASSESSMENT:")
    print(f"{'='*70}")
    
    try:
        assessment = assess_focus(
            prompt=prompt,
            output=output,
            model="gpt-4o-mini",
            generate_output=generate_output
        )
        assessment.print_summary()
    except Exception as e:
        print(f"\nError: {e}")
        print("\nNote: Make sure OPENAI_API_KEY is set in your environment.")

if __name__ == "__main__":
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY not set. Set it to run examples:")
        print("  export OPENAI_API_KEY='your-key-here'")
        print("\nRunning examples anyway (they will fail without the key)...\n")
    
    # Example 1: With provided output
    run_example(academic_prompt, academic_output, "Academic Research Paper (with provided output)")
    
    # Example 2: With provided output
    run_example(review_prompt, review_output, "Product Review (with provided output)")
    
    # Example 3: Generate output using agent
    print("\n\n" + "="*70)
    print("Now demonstrating agent-generated output...")
    print("="*70)
    run_example(
        academic_prompt,
        title="Academic Research Paper (agent-generated output)",
        generate_output=True
    )

