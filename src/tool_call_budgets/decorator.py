"""@guarded decorator: bind a tool function to a budget so every call records."""

from __future__ import annotations

import functools
from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable[..., object])


def make_guarded(budgets, tool: str) -> Callable[[F], F]:
    """Return a decorator that records one call against tool on every invocation.

    The decorator routes through whichever RunContext is currently active on
    the bound ToolBudgets. If no run is active, calling the wrapped function
    raises RuntimeError so a misconfigured agent fails loud rather than
    silently bypassing the cap.

    Sync and async functions are both supported. The check happens before the
    wrapped function runs, so a breach short-circuits the call.
    """
    import inspect

    def decorator(fn: F) -> F:
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                ctx = budgets.active_context()
                if ctx is None:
                    raise RuntimeError(
                        f"@guarded({tool!r}) called with no active run; "
                        "open one with `with budgets.run() as ctx:` first"
                    )
                ctx.record(tool)
                return await fn(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            ctx = budgets.active_context()
            if ctx is None:
                raise RuntimeError(
                    f"@guarded({tool!r}) called with no active run; "
                    "open one with `with budgets.run() as ctx:` first"
                )
            ctx.record(tool)
            return fn(*args, **kwargs)

        return sync_wrapper  # type: ignore[return-value]

    return decorator
