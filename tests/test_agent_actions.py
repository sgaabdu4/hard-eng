"""What the agent checks read from a client's recorded events."""

import json
from pathlib import Path

from agent_actions import event_usage


def test_usage_counts_tokens_and_tool_calls_of_each_client(tmp_path: Path) -> None:
    claude = [
        {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use"}, {"type": "text"}]},
        },
        {"type": "assistant", "message": {"content": [{"type": "tool_use"}]}},
        {
            "type": "result",
            "usage": {"input_tokens": 7, "output_tokens": 3, "service_tier": "x"},
        },
    ]
    codex = [
        {"type": "item.completed", "item": {"type": "command_execution"}},
        {"type": "item.completed", "item": {"type": "agent_message"}},
        {"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 5}},
    ]
    for name, events, tokens, steps in (
        ("claude", claude, {"input_tokens": 7, "output_tokens": 3}, 2),
        ("codex", codex, {"input_tokens": 100, "output_tokens": 5}, 1),
    ):
        path = tmp_path / f"{name}.jsonl"
        path.write_text("\n".join(json.dumps(event) for event in events))
        assert event_usage(path) == {"tokens": tokens, "steps": steps}
    assert event_usage(tmp_path / "none.jsonl") == {"tokens": {}, "steps": 0}
