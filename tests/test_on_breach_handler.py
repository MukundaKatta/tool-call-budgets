"""Tests for custom on_breach handlers."""

import pytest

from tool_call_budgets import ToolBudgets, ToolBudgetExceeded


def test_default_handler_raises():
    b = ToolBudgets(caps={"search": 1})
    with b.run() as ctx:
        ctx.record("search")
        with pytest.raises(ToolBudgetExceeded):
            ctx.record("search")


def test_custom_handler_called_with_tool_cap_used():
    seen: list[tuple[str, int, int]] = []

    def handler(tool: str, cap: int, used: int) -> None:
        seen.append((tool, cap, used))

    b = ToolBudgets(caps={"search": 2}, on_breach=handler)
    with b.run() as ctx:
        ctx.record("search")
        ctx.record("search")
        ctx.record("search")  # breach

    assert seen == [("search", 2, 3)]


def test_swallowing_handler_lets_run_continue():
    """A handler that does not raise allows the agent to keep going."""
    breaches: list[str] = []
    b = ToolBudgets(
        caps={"search": 1},
        on_breach=lambda tool, cap, used: breaches.append(tool),
    )
    with b.run() as ctx:
        ctx.record("search")
        ctx.record("search")  # breach 1, swallowed
        ctx.record("search")  # breach 2, swallowed
        assert ctx.used("search") == 3

    assert breaches == ["search", "search"]


def test_handler_can_raise_custom_exception():
    class StopAgent(RuntimeError):
        pass

    def handler(tool: str, cap: int, used: int) -> None:
        raise StopAgent(f"abort: {tool}")

    b = ToolBudgets(caps={"search": 1}, on_breach=handler)
    with b.run() as ctx:
        ctx.record("search")
        with pytest.raises(StopAgent):
            ctx.record("search")


def test_breach_count_accumulates_with_swallowing_handler():
    b = ToolBudgets(
        caps={"search": 1, "fetch": 1},
        on_breach=lambda *_: None,
    )
    with b.run() as ctx:
        ctx.record("search")
        ctx.record("search")  # breach
        ctx.record("fetch")
        ctx.record("fetch")  # breach
        ctx.record("search")  # breach
        report = ctx.report()

    assert report.breach_count == 3
    # aborted_on records the first breach.
    assert report.aborted_on == "search"
