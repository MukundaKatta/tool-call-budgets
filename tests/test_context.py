"""Tests for RunContext record/used/remaining behavior."""

import pytest

from tool_call_budgets import ToolBudgets, ToolBudgetExceeded, UnknownTool


def test_record_increments_usage():
    b = ToolBudgets(caps={"search": 3})
    with b.run() as ctx:
        assert ctx.record("search") == 1
        assert ctx.record("search") == 2
        assert ctx.used("search") == 2


def test_record_at_cap_succeeds():
    b = ToolBudgets(caps={"search": 2})
    with b.run() as ctx:
        ctx.record("search")
        ctx.record("search")
        assert ctx.used("search") == 2
        assert ctx.remaining("search") == 0


def test_record_past_cap_raises():
    b = ToolBudgets(caps={"search": 2})
    with b.run() as ctx:
        ctx.record("search")
        ctx.record("search")
        with pytest.raises(ToolBudgetExceeded) as exc_info:
            ctx.record("search")
        assert exc_info.value.tool == "search"
        assert exc_info.value.cap == 2
        assert exc_info.value.used == 3


def test_cap_zero_first_call_raises():
    b = ToolBudgets(caps={"search": 0})
    with b.run() as ctx:
        with pytest.raises(ToolBudgetExceeded):
            ctx.record("search")


def test_unknown_tool_strict_mode_raises():
    b = ToolBudgets(caps={"search": 5})
    with b.run() as ctx:
        with pytest.raises(UnknownTool):
            ctx.record("undeclared_tool")


def test_unknown_tool_non_strict_mode_silent():
    b = ToolBudgets(caps={"search": 5}, strict=False)
    with b.run() as ctx:
        # No raise; returns 0 since we do not track unknown tools.
        assert ctx.record("undeclared_tool") == 0
        # Known tool is unaffected.
        ctx.record("search")
        assert ctx.used("search") == 1


def test_remaining_decreases():
    b = ToolBudgets(caps={"search": 3})
    with b.run() as ctx:
        assert ctx.remaining("search") == 3
        ctx.record("search")
        assert ctx.remaining("search") == 2
        ctx.record("search")
        ctx.record("search")
        assert ctx.remaining("search") == 0


def test_remaining_for_unknown_tool_is_zero():
    b = ToolBudgets(caps={"search": 5}, strict=False)
    with b.run() as ctx:
        assert ctx.remaining("nope") == 0


def test_record_after_close_raises():
    b = ToolBudgets(caps={"search": 5})
    ctx = b.run()
    ctx.record("search")
    ctx.close()
    with pytest.raises(RuntimeError):
        ctx.record("search")


def test_independent_caps_per_tool():
    b = ToolBudgets(caps={"search": 2, "fetch": 5})
    with b.run() as ctx:
        ctx.record("search")
        ctx.record("search")
        # Search at cap, fetch untouched.
        with pytest.raises(ToolBudgetExceeded):
            ctx.record("search")
        # Fetch is still happy.
        ctx.record("fetch")
        assert ctx.used("fetch") == 1
