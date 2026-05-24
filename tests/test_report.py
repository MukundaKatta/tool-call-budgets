"""Tests for BudgetReport snapshot behavior."""

import pytest

from tool_call_budgets import ToolBudgets, ToolBudgetExceeded


def test_report_after_clean_run():
    b = ToolBudgets(caps={"search": 5, "fetch": 10, "write": 3})
    with b.run() as ctx:
        ctx.record("search")
        ctx.record("search")
        ctx.record("fetch")
        report = ctx.report()

    assert report.usage == {"search": 2, "fetch": 1, "write": 0}
    assert report.remaining == {"search": 3, "fetch": 9, "write": 3}
    assert report.aborted_on is None
    assert report.breach_count == 0


def test_report_after_breach():
    b = ToolBudgets(caps={"search": 1})
    with b.run() as ctx:
        ctx.record("search")
        try:
            ctx.record("search")
        except ToolBudgetExceeded:
            pass
        report = ctx.report()

    assert report.aborted_on == "search"
    assert report.breach_count == 1


def test_report_remaining_floors_at_zero():
    b = ToolBudgets(caps={"search": 1})
    # Use a swallowing on_breach so we can push past the cap and confirm
    # remaining never goes negative.
    swallowed: list[str] = []
    b2 = ToolBudgets(
        caps={"search": 1},
        on_breach=lambda tool, cap, used: swallowed.append(tool),
    )
    with b2.run() as ctx:
        ctx.record("search")
        ctx.record("search")  # over cap, swallowed
        ctx.record("search")  # over cap, swallowed
        report = ctx.report()

    assert report.usage["search"] == 3
    assert report.remaining["search"] == 0
    assert report.aborted_on == "search"
    assert report.breach_count == 2


def test_report_utilization():
    b = ToolBudgets(caps={"search": 4, "fetch": 10, "noop": 0})
    with b.run() as ctx:
        ctx.record("search")
        ctx.record("search")
        ctx.record("fetch")
        u = ctx.report().utilization()

    assert u["search"] == pytest.approx(0.5)
    assert u["fetch"] == pytest.approx(0.1)
    # cap=0, no usage => 0.0 (not NaN, not inf).
    assert u["noop"] == 0.0


def test_report_as_dict_is_plain_json_friendly():
    b = ToolBudgets(caps={"search": 2})
    with b.run() as ctx:
        ctx.record("search")
        d = ctx.report().as_dict()

    assert d == {
        "usage": {"search": 1},
        "caps": {"search": 2},
        "remaining": {"search": 1},
        "aborted_on": None,
        "breach_count": 0,
    }


def test_report_is_frozen_dataclass():
    b = ToolBudgets(caps={"search": 5})
    with b.run() as ctx:
        report = ctx.report()
    with pytest.raises(Exception):
        report.aborted_on = "search"  # type: ignore[misc]
