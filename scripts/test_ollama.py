"""
Test Ollama Installation
=========================

Quick test to verify Ollama is installed and working before running the full RAG system.

Usage:
    python scripts/test_ollama.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_ollama():
    """Test Ollama installation and model availability"""

    print("\n" + "="*60)
    print("OLLAMA INSTALLATION TEST")
    print("="*60 + "\n")

    # Test 1: Import langchain-ollama
    print("[1/4] Testing langchain-ollama import...")
    try:
        from langchain_ollama import OllamaLLM
        print("[OK] langchain-ollama installed")
    except ImportError as e:
        print(f"[FAIL] langchain-ollama not found: {e}")
        print("\nFix: pip install langchain-ollama")
        return False

    # Test 2: Try to connect to Ollama
    print("\n[2/4] Connecting to Ollama service...")
    try:
        llm = OllamaLLM(
            model="llama3:8b-instruct-q4_K_M",
            base_url="http://localhost:11434"
        )
        print("[OK] Connected to Ollama at http://localhost:11434")
    except Exception as e:
        print(f"[FAIL] Cannot connect to Ollama: {e}")
        print("\nFix:")
        print("1. Install Ollama: https://ollama.com/download")
        print("2. Make sure Ollama service is running")
        print("3. Try: ollama list")
        return False

    # Test 3: Check if model is available
    print("\n[3/4] Checking if 'llama3:8b-instruct-q4_K_M' model is available...")
    try:
        # Try a simple test query
        response = llm.invoke("Say 'test successful' if you can read this.")
        print(f"[OK] Model 'llama3:8b-instruct-q4_K_M' is available")
        print(f"     Response preview: {response[:100]}...")
    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower() or "model" in error_msg.lower():
            print(f"[FAIL] Model 'llama3:8b-instruct-q4_K_M' not found")
            print("\nFix: Download the model:")
            print("  ollama pull llama3:8b-instruct-q4_K_M")
        else:
            print(f"[FAIL] Error testing model: {e}")
        return False

    # Test 4: Test a financial question
    print("\n[4/4] Testing with a financial question...")
    try:
        question = "What is a Central Bank?"
        response = llm.invoke(question)
        print(f"[OK] Model can answer questions")
        print(f"\n     Question: {question}")
        print(f"     Answer (first 200 chars): {response[:200]}...")
    except Exception as e:
        print(f"[FAIL] Error generating response: {e}")
        return False

    # All tests passed!
    print("\n" + "="*60)
    print("ALL TESTS PASSED!")
    print("="*60)
    print("\n[OK] Ollama is ready to use!")
    print("[OK] You can now run: python scripts/3_query_rag_local.py")
    print("\nModels available:")
    print("  - llama3:8b-instruct-q4_K_M (current)")
    print("  - To use a different model, edit OLLAMA_MODEL in 3_query_rag_local.py\n")
    return True


def main():
    """Run tests"""
    try:
        success = test_ollama()
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
