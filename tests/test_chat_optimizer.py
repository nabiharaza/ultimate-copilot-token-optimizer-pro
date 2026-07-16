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


def test_chat_history_sequence_compacts_old_context_and_keeps_recent_tail():
    messages = []
    for index in range(12):
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Historical request {index}: inspect services/payment_api.py and keep "
                    "the database constraint names, endpoint paths, retry behavior, and "
                    "deployment notes in mind. This context has repeated setup details. "
                )
                * 5,
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": (
                    f"Historical answer {index}: confirmed the files, noted the migration "
                    "plan, listed noisy logs, and repeated the same operational summary. "
                )
                * 5,
            }
        )
    messages.append({"role": "user", "content": "Latest question: what exact fix should I apply now?"})
    body = {"messages": messages}

    optimized, stats = ChatPayloadOptimizer(min_savings_pct=1).optimize_body(body, enabled=True)

    assert stats.tokens_saved > 0
    assert any(change.path == "messages" for change in stats.changes)
    assert optimized["messages"][-1] == messages[-1]
    assert len(optimized["messages"]) < len(messages)


def test_chat_history_sequence_skips_tool_call_chains():
    body = {
        "messages": [
            {"role": "user", "content": "Read the file."},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "call-1", "type": "function", "function": {"name": "read", "arguments": "{}"}}],
            },
            {"role": "tool", "tool_call_id": "call-1", "content": _large_tool_output()},
        ]
    }

    optimized, stats = ChatPayloadOptimizer(min_savings_pct=1).optimize_body(body, enabled=True)

    assert optimized["messages"][1] == body["messages"][1]
    assert all(change.path != "messages" for change in stats.changes)


def test_chat_history_aliases_repeated_anchors_without_touching_latest_turn():
    repeated_path = "services/payment_api/retry_policy.py"
    repeated_id = "PAYMENT-1042"
    messages = []
    for index in range(10):
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Earlier turn {index}: inspect {repeated_path} for {repeated_id}. "
                    f"The file {repeated_path} controls {repeated_id} fallback behavior. "
                )
                * 4,
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": (
                    f"I checked {repeated_path}; {repeated_id} is still relevant. "
                    "Keep the exact path and ticket available for later reasoning. "
                )
                * 4,
            }
        )
    latest = {"role": "user", "content": f"Latest question: cite {repeated_path} directly."}
    body = {"messages": [*messages, latest]}

    optimized, stats = ChatPayloadOptimizer(min_savings_pct=1).optimize_body(body, enabled=True)

    assert optimized["messages"][-1] == latest
    assert any(change.path == "messages.aliases" for change in stats.changes)
    assert "TrimPy context aliases" in optimized["messages"][0]["content"]
    assert repeated_path in optimized["messages"][0]["content"]
