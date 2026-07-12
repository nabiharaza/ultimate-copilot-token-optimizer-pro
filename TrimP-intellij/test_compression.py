#!/usr/bin/env python3
"""
Test script for IntelliJ proxy - verifies compression works with various content types.
"""
import json
import sys
sys.path.insert(0, "/Users/nabiharaza/Projects/copilot-token-optimizer")

from TrimP.chat_optimizer import ChatPayloadOptimizer
from TrimP.compression.prompt_compression import PromptCompressor
from TrimP.compression.bash import BashCompressor
from TrimP.compression.search import SearchCompressor
from TrimP.compression.json_table import JsonTableCompressor


def test_prompt_compressor():
    """Test prompt compressor directly."""
    compressor = PromptCompressor()
    text = "You are a helpful assistant. " * 50 + "Please help me with Python asyncio. " * 30
    print(f"Original: {len(text)} chars")
    compressed, saved = compressor.compress(text)
    print(f"Compressed: {len(compressed)} chars, saved: {saved:.1f}%")
    return saved > 0


def test_bash_compressor():
    """Test bash compressor with command output."""
    compressor = BashCompressor()
    # Simulate test output
    text = """=================================== test session starts ===================================
platform linux -- Python 3.11.5, pytest-7.4.2, pluggy-1.3.0
rootdir: /project
collected 150 items

tests/test_module.py ..............                                            [ 10%]
tests/test_api.py ............F....                                            [ 20%]
tests/test_db.py ............                                                  [ 27%]
tests/test_auth.py ..............                                              [ 35%]
tests/test_utils.py ..............                                             [ 43%]
tests/test_models.py .............                                             [ 50%]
tests/test_views.py ..............                                             [ 57%]
tests/test_forms.py ..............                                             [ 64%]
tests/test_serializers.py ............                                         [ 71%]
tests/test_permissions.py ............                                         [ 79%]
tests/test_middleware.py ............                                          [ 86%]
tests/test_signals.py ............                                             [ 93%]
tests/test_migrations.py ............                                          [100%]

======================================= FAILURES =======================================
__________________________ test_user_login ___________________________________________
    def test_user_login():
        client = TestClient(app)
        response = client.post("/login", json={"username": "test", "password": "wrong"})
        assert response.status_code == 200
AssertionError: assert 401 == 200
__________________________ test_api_rate_limit _______________________________________
    def test_api_rate_limit():
        for i in range(100):
            response = client.get("/api/data")
        assert response.status_code == 200
AssertionError: assert 429 == 200

==================================== 2 failed, 148 passed in 12.34s ===================================="""
    print(f"Original: {len(text)} chars")
    compressed, saved = compressor.compress(text)
    print(f"Compressed: {len(compressed)} chars, saved: {saved:.1f}%")
    return saved > 0


def test_search_compressor():
    """Test search compressor with grep-like output."""
    compressor = SearchCompressor()
    text = """src/main.py:10:def process_data(data):
src/main.py:15:    result = transform(data)
src/main.py:20:    return result
src/utils.py:5:def transform(x):
src/utils.py:10:    return x * 2
src/api.py:1:from flask import Flask
src/api.py:50:app = Flask(__name__)
src/api.py:100:@app.route('/api/data')
src/api.py:105:def get_data():
src/api.py:110:    return jsonify({'status': 'ok'})
""" * 50  # Repeat to make it larger
    print(f"Original: {len(text)} chars")
    compressed, saved = compressor.compress(text)
    print(f"Compressed: {len(compressed)} chars, saved: {saved:.1f}%")
    return saved > 0


def test_json_compressor():
    """Test JSON compressor."""
    compressor = JsonTableCompressor()
    data = {
        "users": [
            {"id": i, "name": f"user{i}", "email": f"user{i}@example.com", "active": True, "metadata": {"created": "2024-01-01", "updated": "2024-06-15"}}
            for i in range(100)
        ],
        "pagination": {"page": 1, "per_page": 100, "total": 1000}
    }
    text = json.dumps(data)
    print(f"Original: {len(text)} chars")
    compressed, saved = compressor.compress_json(text)
    print(f"Compressed: {len(compressed)} chars, saved: {saved:.1f}%")
    return saved > 0


def test_full_chat():
    """Test full chat optimization."""
    optimizer = ChatPayloadOptimizer(min_chars=100, min_savings_pct=5.0)

    # Create a realistic chat with long messages
    long_explanation = (
        "Here's a comprehensive explanation of Python's asyncio module. "
        "Asyncio is a library for writing concurrent code using async/await syntax. "
        "It provides event loops, coroutines, tasks, and futures. "
        "The event loop is the core of asyncio - it manages and distributes the execution of different tasks. "
        "Coroutines are special functions that can pause and resume their execution. "
        "You define them with async def and call them with await. "
        "Tasks are used to schedule coroutines concurrently. "
        "Futures represent the result of an asynchronous operation. "
    ) * 30  # ~6000 chars

    long_code = (
        "import asyncio\n\n"
        "async def fetch_data(url):\n"
        "    async with aiohttp.ClientSession() as session:\n"
        "        async with session.get(url) as response:\n"
        "            return await response.json()\n\n"
        "async def main():\n"
        "    urls = [f'https://api.example.com/item/{i}' for i in range(100)]\n"
        "    tasks = [fetch_data(url) for url in urls]\n"
        "    results = await asyncio.gather(*tasks)\n"
        "    return results\n\n"
        "if __name__ == '__main__':\n"
        "    asyncio.run(main())\n"
    ) * 20  # ~5000 chars

    request = {
        "messages": [
            {"role": "system", "content": "You are an expert Python developer specializing in async programming."},
            {"role": "user", "content": "Explain Python asyncio in detail with examples."},
            {"role": "assistant", "content": long_explanation},
            {"role": "user", "content": "Can you show me a practical example with HTTP requests?"},
            {"role": "assistant", "content": long_code},
            {"role": "user", "content": "What about error handling and timeouts?"},
        ],
        "model": "gpt-4",
        "temperature": 0.3,
        "max_tokens": 4000,
    }

    print(f"Original message count: {len(request['messages'])}")
    total_chars = sum(len(m.get('content', '')) for m in request['messages'])
    print(f"Total content size: {total_chars} chars")

    optimized, stats = optimizer.optimize_body(request)

    print(f"\nTokens before: {stats.tokens_before:,}")
    print(f"Tokens after:  {stats.tokens_after:,}")
    print(f"Tokens saved:  {stats.tokens_saved:,} ({stats.savings_pct:.1f}%)")
    print(f"\nChanges ({len(stats.changes)}):")
    for change in stats.changes:
        print(f"  {change.path}: {change.tokens_before:,} -> {change.tokens_after:,} via {change.method}")

    return stats.savings_pct > 0


def main():
    print("=" * 60)
    print("Testing individual compressors")
    print("=" * 60)

    results = []
    results.append(("PromptCompressor", test_prompt_compressor()))
    print()
    results.append(("BashCompressor", test_bash_compressor()))
    print()
    results.append(("SearchCompressor", test_search_compressor()))
    print()
    results.append(("JsonTableCompressor", test_json_compressor()))
    print()

    print("=" * 60)
    print("Testing full chat optimization")
    print("=" * 60)
    results.append(("Full Chat", test_full_chat()))
    print()

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")

    all_passed = all(passed for _, passed in results)
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)