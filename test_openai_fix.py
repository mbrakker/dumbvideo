#!/usr/bin/env python3
"""
Test script to reproduce and fix the OpenAI proxies issue
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_openai_client():
    """Test OpenAI client initialization"""
    try:
        from openai import OpenAI

        # Test basic initialization
        print("Testing basic OpenAI client initialization...")
        client = OpenAI()
        print("✓ Basic client initialization successful")

        # Test with explicit API key
        print("Testing with explicit API key...")
        client_with_key = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        print("✓ Client with API key successful")

        return True

    except Exception as e:
        print(f"✗ OpenAI client initialization failed: {e}")
        return False

def test_with_http_client():
    """Test OpenAI client with custom HTTP client"""
    try:
        import httpx
        from openai import OpenAI

        print("Testing with custom HTTP client...")

        # Create HTTPX client without proxies
        http_client = httpx.Client()

        # Test OpenAI client with custom HTTP client
        client = OpenAI(http_client=http_client)
        print("✓ Client with custom HTTP client successful")

        return True

    except Exception as e:
        print(f"✗ Client with custom HTTP client failed: {e}")
        return False

if __name__ == "__main__":
    print("OpenAI Client Test")
    print("=" * 30)

    success1 = test_openai_client()
    print()
    success2 = test_with_http_client()

    if success1 and success2:
        print("\n✓ All tests passed!")
    else:
        print("\n✗ Some tests failed!")
