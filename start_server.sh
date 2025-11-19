#!/bin/bash
# Startup script for FocalPrompt web server

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Check for API key
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Warning: OPENAI_API_KEY not set."
    echo "Please set it with: export OPENAI_API_KEY='your-key-here'"
    echo ""
fi

# Start the server
echo "Starting FocalPrompt web server..."
echo "Open your browser to: http://127.0.0.1:5000"
echo "Press Ctrl+C to stop the server"
echo ""

python app.py

