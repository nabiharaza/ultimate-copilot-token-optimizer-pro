"""Tests for structured chat and Responses API request optimization."""

from copy import deepcopy

from TrimP.byok_proxy import _extract_user_prompt
from TrimP.chat_optimizer import ChatPayloadOptimizer
from TrimP.db import set_config


def _large_tool_output() -> str:
    return "\n".join(
        f"FAILED tests/test_api.py::test_case_{index} - AssertionError: expected 200 got 504"
        for index in range(160)
    )


def test_responses_api_compresses_function_output_only():
    body = {
        "model": "gpt-5-mini",
        "instructions": "Keep this system instruction unchanged. " * 20,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Please diagnose the failures."}],
            },
            {
                "type": "reasoning",
                "encrypted_content": "opaque-state" * 100,
            },
            {
                "type": "function_call",
                "name": "view",
                "arguments": '{"path":"README.md"}',
                "call_id": "call-1",
            },
            {
                "type": "function_call_output",
                "call_id": "call-1",
                "output": _large_tool_output(),
            },
        ],
        "tools": [{"type": "function", "name": "view", "description": "Read a file."}],
    }
    original = deepcopy(body)

    optimized, stats = ChatPayloadOptimizer().optimize_body(body, enabled=True)

    assert stats.tokens_saved > 0
    assert any(change.path == "input[3].output" for change in stats.changes)
    assert optimized["input"][3]["output"] != original["input"][3]["output"]
    assert optimized["instructions"] == original["instructions"]
    assert optimized["input"][1] == original["input"][1]
    assert optimized["input"][2] == original["input"][2]
    assert optimized["tools"] == original["tools"]


def test_responses_api_extracts_latest_user_prompt():
    body = {
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "First question"}],
            },
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "First answer"}],
            },
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Latest question"}],
            },
        ]
    }

    assert _extract_user_prompt(body) == "Latest question"


def test_global_trim_switch_forwards_original_body_when_disabled():
    body = {"messages": [{"role": "user", "content": _large_tool_output()}]}
    original = deepcopy(body)
    set_config("compression.enabled", "false")
    try:
        optimized, stats = ChatPayloadOptimizer().optimize_body(body)
        assert optimized == original
        assert stats.tokens_saved == 0
        assert stats.tokens_before == stats.tokens_after
    finally:
        set_config("compression.enabled", "true")
