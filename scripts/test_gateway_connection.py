#!/usr/bin/env python3
"""
Test script to verify AI Gateway connection.

Run this to diagnose AI Gateway setup issues.
"""

import os
import sys

def test_gateway():
    """Test AI Gateway connection."""
    print("=" * 60)
    print("AI Gateway Connection Test")
    print("=" * 60)
    print()
    
    # Check for API key
    api_key = os.getenv("AI_GATEWAY_API_KEY")
    if not api_key:
        print("❌ ERROR: AI_GATEWAY_API_KEY not set")
        print()
        print("Please set it in your environment:")
        print("  export AI_GATEWAY_API_KEY='your_key_here'")
        print()
        print("Or in Vercel:")
        print("  Settings → Environment Variables → Add AI_GATEWAY_API_KEY")
        return False
    
    print(f"✅ AI_GATEWAY_API_KEY found (first 20 chars: {api_key[:20]}...)")
    print()
    
    # Check gateway URL
    gateway_url = os.getenv("AI_GATEWAY_URL", "https://gateway.vercel.ai/v1")
    print(f"📍 Gateway URL: {gateway_url}")
    print()
    
    # Try to import and test
    try:
        from core.ai_gateway_provider import AIGatewayProvider
        print("✅ AIGatewayProvider imported successfully")
        print()
        
        print("Initializing gateway provider...")
        provider = AIGatewayProvider(api_key)
        print("✅ Gateway provider initialized")
        print()
        
        print("Testing connection with a simple request...")
        print("Model: openai/gpt-4o-mini")
        print("Prompt: 'Say hello'")
        print()
        
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say hello"}],
            model="gpt-4o-mini",
            provider="openai"
        )
        
        print("✅ SUCCESS! Gateway connection works!")
        print()
        print(f"Response: {response['content']}")
        print(f"Tokens used: {response['usage']['total_tokens']}")
        print()
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running from the project root directory")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print()
        print("Common issues:")
        print("1. Gateway not created in Vercel dashboard")
        print("2. Wrong API key (should start with 'gateway_')")
        print("3. Gateway in different Vercel project")
        print("4. Gateway not enabled")
        print()
        print("Check the error message above for more details.")
        return False

if __name__ == "__main__":
    success = test_gateway()
    sys.exit(0 if success else 1)

