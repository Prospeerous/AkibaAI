"""
Quick Setup Test
================

Verifies that your environment is configured correctly before running the main pipeline.

Usage:
    python test_setup.py
"""

import os
import sys
from pathlib import Path

def test_python_version():
    """Check Python version"""
    print("[*] Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        print(f"    [OK] Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"    [FAIL] Python {version.major}.{version.minor}.{version.micro} (Need 3.10+)")
        return False

def test_imports():
    """Check if required packages are installed"""
    print("\n[*] Checking required packages...")

    required = {
        'openai': 'OpenAI API',
        'langchain': 'LangChain',
        'faiss': 'FAISS',
        'fitz': 'PyMuPDF',
        'bs4': 'BeautifulSoup4',
        'requests': 'Requests',
        'dotenv': 'python-dotenv'
    }

    all_ok = True
    for module, name in required.items():
        try:
            __import__(module)
            print(f"    [OK] {name}")
        except ImportError:
            print(f"    [FAIL] {name} (Not installed)")
            all_ok = False

    return all_ok

def test_env_file():
    """Check if .env file exists"""
    print("\n[*] Checking environment file...")
    env_path = Path(".env")

    if env_path.exists():
        print(f"    [OK] .env file found")
        return True
    else:
        print(f"    [FAIL] .env file not found")
        print(f"           Please create .env from .env.example")
        return False

def test_api_key():
    """Check if OpenAI API key is set"""
    print("\n[*] Checking OpenAI API key...")

    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print(f"    [FAIL] OPENAI_API_KEY not found in .env")
        return False

    if api_key == "your_openai_api_key_here":
        print(f"    [FAIL] OPENAI_API_KEY not set (still placeholder)")
        return False

    if api_key.startswith("sk-"):
        print(f"    [OK] API key found (starts with sk-)")

        # Test the API key
        print("\n[*] Testing API connection...")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)

            # Simple test - list models
            models = client.models.list()
            print(f"    [OK] API key is valid (connected successfully)")
            return True

        except Exception as e:
            print(f"    [FAIL] API key test failed: {e}")
            return False
    else:
        print(f"    [FAIL] API key format looks incorrect (should start with 'sk-')")
        return False

def test_folders():
    """Check if required folders exist"""
    print("\n[*] Checking folder structure...")

    folders = ['data', 'data/raw', 'data/processed', 'data/indices', 'scripts']
    all_ok = True

    for folder in folders:
        if Path(folder).exists():
            print(f"    [OK] {folder}/")
        else:
            print(f"    [FAIL] {folder}/ (Missing)")
            all_ok = False

    return all_ok

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("FINANCE COACH - SETUP TEST")
    print("="*60)

    results = []

    # Run tests
    results.append(("Python Version", test_python_version()))
    results.append(("Required Packages", test_imports()))
    results.append(("Environment File", test_env_file()))
    results.append(("Folder Structure", test_folders()))
    results.append(("OpenAI API Key", test_api_key()))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {test_name}")

    print(f"\n  {passed}/{total} tests passed")

    if passed == total:
        print("\n[SUCCESS] All tests passed! You're ready to run:")
        print("          python scripts/1_scrape_cbk.py")
    else:
        print("\n[WARNING] Please fix the issues above before proceeding.")
        print("\nCommon fixes:")
        print("  - Install packages: pip install -r requirements.txt")
        print("  - Create .env file: copy .env.example .env")
        print("  - Add your API key to .env file")

    print()

if __name__ == "__main__":
    main()
