"""End-to-end tests: simulated agent loops."""

import pytest

from tool_call_budgets import ToolBudgets, ToolBudgetExceeded


def test_simulated_research_agent_within_budget():
    """A well-behaved agent that finishes inside its caps."""
    b = ToolBudgets(caps={"search": 5, "fetch_url": 10, "write_file": 3})

    @b.guarded("search")
    def search(q: str) -> list[str]:
        return [f"hit-{q}-1", f"hit-{q}-2"]

    @b.guarded("fetch_url")
    def fetch_url(url: str) -> str:
        return f"body of {url}"

    @b.guarded("write_file")
    def write_file(path: str, body: str) -> None:
        return None

    with b.run() as ctx:
        results = search("agents")
        for hit in results:
            fetch_url(f"https://example.test/{hit}")
        write_file("notes.md", "summary")
        report = ctx.report()

    assert report.aborted_on is None
    assert report.usage == {"search": 1, "fetch_url": 2, "write_file": 1}
    assert report.remaining == {"search": 4, "fetch_url": 8, "write_file": 2}


def test_simulated_runaway_agent_is_stopped():
    """A buggy agent in an infinite loop is halted by the cap."""
    b = ToolBudgets(caps={"search": 5})

    @b.guarded("search")
    def search(q: str) -> str:
        return "stuck"

    iterations = 0
    with b.run() as ctx:
        with pytest.raises(ToolBudgetExceeded):
            # Mimic an LLM that keeps deciding to call search forever.
            while True:
                search("same query")
                iterations += 1

    # 5 successful calls, then the 6th breaches.
    assert iterations == 5
    assert ctx.used("search") == 5
    report = ctx.report()
    assert report.aborted_on == "search"


def test_breach_handler_used_for_logging():
    """A real-world pattern: log breaches but let the agent finish."""
    logs: list[str] = []

    def log_breach(tool: str, cap: int, used: int) -> None:
        logs.append(f"WARN: {tool} over cap ({used}/{cap})")

    b = ToolBudgets(caps={"search": 2}, on_breach=log_breach)

    @b.guarded("search")
    def search(q: str) -> str:
        return q

    with b.run() as ctx:
        for q in ["a", "b", "c", "d"]:
            search(q)
        report = ctx.report()

    assert report.usage["search"] == 4
    assert len(logs) == 2  # calls 3 and 4 were both breaches
    assert "WARN: search over cap (3/2)" in logs[0]
    assert "WARN: search over cap (4/2)" in logs[1]


def test_multiple_runs_isolated():
    """Each run is fresh; usage from a previous run does not leak."""
    b = ToolBudgets(caps={"search": 2})

    with b.run() as ctx1:
        ctx1.record("search")
        ctx1.record("search")
        with pytest.raises(ToolBudgetExceeded):
            ctx1.record("search")

    # New run starts at zero.
    with b.run() as ctx2:
        ctx2.record("search")
        assert ctx2.used("search") == 1
        assert ctx2.remaining("search") == 1
