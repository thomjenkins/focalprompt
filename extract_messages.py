#!/usr/bin/env python3
"""
Extract message content from prompt column in query_result CSV files.

This script:
1. Reads a query_result_*.csv file
2. Extracts message content from the 'prompt' column (removes timestamps and sender info)
3. Uses the 'message' column as output
4. Creates a new CSV with 'input' and 'output' columns for FocalPrompt batch analysis
"""

import csv
import re
import sys
import os
from pathlib import Path


def extract_message_content(prompt_text):
    """
    Extract just the message content from prompt text.
    
    The prompt contains system instructions, then chat content with timestamps like:
        (19:33 2025/11/08) system: Hi there, how can we help
        (21:00 2025/11/08) {{clientName}}: HI - you keep sending me vaccination reminders...
    
    Output: All chat messages joined together (the input for FocalPrompt)
    """
    if not prompt_text or not isinstance(prompt_text, str):
        return ""
    
    lines = prompt_text.strip().split('\n')
    messages = []
    
    # Pattern to match timestamp and sender: (HH:MM YYYY/MM/DD) sender: message
    # More flexible pattern to handle various timestamp formats
    timestamp_pattern = r'^\((\d{2}:\d{2} \d{4}/\d{2}/\d{2})\)\s+([^:]+):\s*(.+)$'
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Try to match the timestamp pattern
        match = re.match(timestamp_pattern, line)
        if match:
            # Extract the full line as it represents one message in the chat
            # This includes timestamp, sender, and message content
            messages.append(line)
        else:
            # Check if this line is a continuation of the previous message
            # (indented or part of a multi-line message)
            if messages and (line.startswith('    ') or not line.startswith('(')):
                # This might be a continuation - but for now, we'll keep it simple
                # and only capture lines with timestamps
                pass
    
    # Join all chat messages with newlines to preserve the conversation structure
    return '\n'.join(messages).strip()


def process_csv(input_file, output_file=None):
    """
    Process the CSV file and extract messages.
    
    Args:
        input_file: Path to input CSV file
        output_file: Path to output CSV file (default: input_file with _extracted suffix)
    """
    if not os.path.exists(input_file):
        print(f"Error: File not found: {input_file}")
        return False
    
    if output_file is None:
        input_path = Path(input_file)
        output_file = input_path.parent / f"{input_path.stem}_extracted{input_path.suffix}"
    
    print(f"Reading from: {input_file}")
    print(f"Writing to: {output_file}")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as infile:
            # Try to detect delimiter, with fallback to comma
            sample = infile.read(1024)
            infile.seek(0)
            try:
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
            except:
                # Fallback: try comma first, then tab
                if ',' in sample:
                    delimiter = ','
                elif '\t' in sample:
                    delimiter = '\t'
                else:
                    delimiter = ','  # Default to comma
            
            reader = csv.DictReader(infile, delimiter=delimiter)
            fieldnames = reader.fieldnames
            
            if not fieldnames:
                print("Error: CSV file appears to be empty or invalid")
                return False
            
            # Check for required columns
            prompt_col = None
            message_col = None
            
            # Try to find prompt column (case-insensitive, exact match first)
            for col in fieldnames:
                col_lower = col.lower()
                if col_lower == 'prompt' or col_lower in ['input', 'system_prompt', 'instruction']:
                    if not prompt_col:  # Prefer exact 'prompt' match, then 'input'
                        prompt_col = col
                elif col_lower == 'message' or col_lower in ['output', 'suggested_message', 'response']:
                    if not message_col:  # Prefer exact 'message' match
                        message_col = col
            
            if not prompt_col:
                print(f"Error: Could not find 'prompt' column in CSV")
                print(f"Available columns: {', '.join(fieldnames)}")
                return False
            
            if not message_col:
                print(f"Warning: Could not find 'message' column, will use empty strings for output")
                print(f"Available columns: {', '.join(fieldnames)}")
            
            # Process rows
            rows_processed = 0
            rows_with_errors = 0
            extracted_data = []
            
            for row in reader:
                prompt_text = row.get(prompt_col, '')
                message_text = row.get(message_col, '') if message_col else ''
                
                # Extract message content from prompt
                extracted_input = extract_message_content(prompt_text)
                
                if not extracted_input:
                    rows_with_errors += 1
                    print(f"Warning: Row {rows_processed + 1} - No message content extracted from prompt")
                
                extracted_data.append({
                    'input': extracted_input,
                    'output': message_text.strip()
                })
                rows_processed += 1
            
            # Write output CSV
            with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=['input', 'output'])
                writer.writeheader()
                writer.writerows(extracted_data)
            
            print(f"\n✓ Successfully processed {rows_processed} rows")
            if rows_with_errors > 0:
                print(f"⚠ {rows_with_errors} rows had warnings (no content extracted)")
            print(f"✓ Output written to: {output_file}")
            return True
            
    except Exception as e:
        print(f"Error processing file: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python extract_messages.py <input_csv_file> [output_csv_file]")
        print("\nExample:")
        print("  python extract_messages.py query_result_123.csv")
        print("  python extract_messages.py query_result_123.csv output.csv")
        print("\nThis will:")
        print("  1. Extract message content from the 'prompt' column")
        print("  2. Use the 'message' column as output")
        print("  3. Create a CSV with 'input' and 'output' columns for FocalPrompt")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = process_csv(input_file, output_file)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

