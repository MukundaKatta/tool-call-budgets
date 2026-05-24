"""Tests for the @guarded decorator."""

import asyncio

import pytest

from tool_call_budgets import ToolBudgets, ToolBudgetExceeded


def test_guarded_records_each_call():
    b = ToolBudgets(caps={"search": 5})

    @b.guarded("search")
    def search(q: str) -> str:
        return f"result for {q}"

    with b.run() as ctx:
        search("a")
        search("b")
        assert ctx.used("search") == 2


def test_guarded_blocks_past_cap():
    b = ToolBudgets(caps={"search": 2})

    @b.guarded("search")
    def search(q: str) -> str:
        return q

    with b.run():
        search("a")
        search("b")
        with pytest.raises(ToolBudgetExceeded):
            search("c")


def test_guarded_outside_run_raises():
    b = ToolBudgets(caps={"search": 5})

    @b.guarded("search")
    def search(q: str) -> str:
        return q

    # Calling the guarded function with no active run is a config error.
    with pytest.raises(RuntimeError):
        search("a")


def test_guarded_short_circuits_on_breach():
    """A breach must not let the wrapped function run."""
    b = ToolBudgets(caps={"search": 1})
    calls: list[str] = []

    @b.guarded("search")
    def search(q: str) -> str:
        calls.append(q)
        return q

    with b.run():
        search("first")
        with pytest.raises(ToolBudgetExceeded):
            search("second")

    # Only the first call ran; the second was blocked before fn body.
    assert calls == ["first"]


def test_guarded_preserves_return_value():
    b = ToolBudgets(caps={"search": 5})

    @b.guarded("search")
    def search(q: str) -> dict:
        return {"q": q, "hits": 3}

    with b.run():
        out = search("python")
        assert out == {"q": "python", "hits": 3}


def test_guarded_preserves_function_metadata():
    b = ToolBudgets(caps={"search": 5})

    @b.guarded("search")
    def search(q: str) -> str:
        """search docstring stays."""
        return q

    assert search.__name__ == "search"
    assert search.__doc__ == "search docstring stays."


def test_guarded_multiple_tools_independent():
    b = ToolBudgets(caps={"search": 2, "fetch": 2})

    @b.guarded("search")
    def search(q: str) -> str:
        return q

    @b.guarded("fetch")
    def fetch(url: str) -> str:
        return url

    with b.run() as ctx:
        search("a")
        fetch("u1")
        search("b")
        fetch("u2")
        assert ctx.used("search") == 2
        assert ctx.used("fetch") == 2
        with pytest.raises(ToolBudgetExceeded):
            search("c")


def test_guarded_async():
    b = ToolBudgets(caps={"search": 2})

    @b.guarded("search")
    async def search(q: str) -> str:
        await asyncio.sleep(0)
        return f"async-{q}"

    async def driver():
        with b.run() as ctx:
            out = await search("a")
            assert out == "async-a"
            await search("b")
            assert ctx.used("search") == 2
            with pytest.raises(ToolBudgetExceeded):
                await search("c")

    asyncio.run(driver())


def test_guarded_stacks_with_other_decorators():
    """Apply @guarded on top of a plain decorator. Both must run."""
    b = ToolBudgets(caps={"search": 5})

    def add_prefix(fn):
        def wrapper(q):
            return "PRE:" + fn(q)
        return wrapper

    @b.guarded("search")
    @add_prefix
    def search(q: str) -> str:
        return q

    with b.run() as ctx:
        assert search("hi") == "PRE:hi"
        assert ctx.used("search") == 1
