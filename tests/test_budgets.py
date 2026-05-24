"""Tests for ToolBudgets construction and validation."""

import pytest

from tool_call_budgets import ToolBudgets


def test_caps_round_trip():
    b = ToolBudgets(caps={"search": 5, "fetch": 10})
    assert b.caps == {"search": 5, "fetch": 10}


def test_caps_property_returns_copy():
    b = ToolBudgets(caps={"search": 5})
    snapshot = b.caps
    snapshot["search"] = 999
    # Internal state is untouched.
    assert b.caps == {"search": 5}


def test_caps_must_be_dict():
    with pytest.raises(TypeError):
        ToolBudgets(caps=[("search", 5)])  # type: ignore[arg-type]


def test_cap_must_be_int_not_float():
    with pytest.raises(TypeError):
        ToolBudgets(caps={"search": 5.0})  # type: ignore[dict-item]


def test_cap_must_not_be_bool():
    # bool is a subclass of int in Python, but a bool cap is almost certainly
    # a typo.
    with pytest.raises(TypeError):
        ToolBudgets(caps={"search": True})  # type: ignore[dict-item]


def test_cap_must_be_non_negative():
    with pytest.raises(ValueError):
        ToolBudgets(caps={"search": -1})


def test_cap_of_zero_is_allowed():
    # cap=0 means "tool exists but no calls allowed". This is useful for
    # disabling a tool dynamically.
    b = ToolBudgets(caps={"search": 0})
    assert b.caps["search"] == 0


def test_tool_name_must_be_non_empty():
    with pytest.raises(ValueError):
        ToolBudgets(caps={"": 5})


def test_only_one_active_run_at_a_time():
    b = ToolBudgets(caps={"search": 5})
    ctx1 = b.run()
    with pytest.raises(RuntimeError):
        b.run()
    ctx1.close()
    # After closing, a new run is fine.
    ctx2 = b.run()
    assert ctx2 is not ctx1


def test_run_returns_fresh_context_each_time():
    b = ToolBudgets(caps={"search": 5})
    with b.run() as ctx1:
        ctx1.record("search")
        ctx1.record("search")
    with b.run() as ctx2:
        # Second run starts at zero, independent of first.
        assert ctx2.used("search") == 0
