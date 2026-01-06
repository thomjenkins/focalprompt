#!/bin/bash
# Simple script to test Vercel AI Gateway

cd "$(dirname "$0")"

# Check if .env exists in parent directory
if [ -f "../.env" ]; then
    echo "Found .env in parent directory"
    export $(cat ../.env | grep AI_GATEWAY_API_KEY | xargs)
elif [ -f ".env" ]; then
    echo "Found .env in current directory"
    export $(cat .env | grep AI_GATEWAY_API_KEY | xargs)
fi

# Check if API key is set
if [ -z "$AI_GATEWAY_API_KEY" ]; then
    echo "❌ Error: AI_GATEWAY_API_KEY not found in .env file"
    echo ""
    echo "Please create a .env file in the root directory with:"
    echo "AI_GATEWAY_API_KEY=your_gateway_key_here"
    echo ""
    echo "You can get your gateway key from:"
    echo "Vercel Dashboard → Your Project → Settings → AI Gateway"
    exit 1
fi

echo "✅ Found AI_GATEWAY_API_KEY"
echo "Running gateway test..."
echo ""

pnpm tsx gateway.ts

