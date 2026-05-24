"""ToolBudgets: the public facade you build a budget config on."""

from __future__ import annotations

from typing import Callable

from .context import BreachHandler, RunContext
from .decorator import make_guarded


class ToolBudgets:
    """Configure per-tool call-count caps and hand out per-run contexts.

    Typical use:

        budgets = ToolBudgets(caps={"search": 5, "fetch_url": 10})
        with budgets.run() as ctx:
            ctx.record("search")
            ...

    The instance is reusable across runs. Each call to run() returns a fresh
    RunContext with usage counters reset to zero.

    Caps are validated at construction time:
        - Each cap must be a non-negative int.
        - Tool names must be non-empty strings.
        - cap=0 means "no calls allowed"; the first record() breaches.
    """

    def __init__(
        self,
        caps: dict[str, int],
        on_breach: BreachHandler | None = None,
        strict: bool = True,
    ):
        if not isinstance(caps, dict):
            raise TypeError("caps must be a dict[str, int]")
        for tool, cap in caps.items():
            if not isinstance(tool, str) or not tool:
                raise ValueError(f"tool name must be a non-empty str, got {tool!r}")
            if not isinstance(cap, int) or isinstance(cap, bool):
                raise TypeError(f"cap for {tool!r} must be int, got {type(cap).__name__}")
            if cap < 0:
                raise ValueError(f"cap for {tool!r} must be >= 0, got {cap}")

        self._caps: dict[str, int] = dict(caps)
        self._on_breach: BreachHandler | None = on_breach
        self._strict = strict
        self._active: RunContext | None = None

    @property
    def caps(self) -> dict[str, int]:
        """Read-only copy of the configured caps."""
        return dict(self._caps)

    def run(self) -> RunContext:
        """Open a fresh RunContext.

        Only one run can be active at a time per ToolBudgets instance. This
        keeps the @guarded decorator routing unambiguous; if you need
        concurrent runs, use one ToolBudgets per run.
        """
        if self._active is not None and not self._active._closed:
            raise RuntimeError(
                "another RunContext is already active on this ToolBudgets; "
                "close it before opening a new one"
            )
        ctx = RunContext(
            caps=self._caps,
            on_breach=self._on_breach,
            strict=self._strict,
        )
        # Wrap close so we clear the active slot when the user's with-block
        # exits. Otherwise a second run() call would still see the old one.
        original_close = ctx.close

        def close_and_clear() -> None:
            original_close()
            if self._active is ctx:
                self._active = None

        ctx.close = close_and_clear  # type: ignore[method-assign]
        self._active = ctx
        return ctx

    def active_context(self) -> RunContext | None:
        """Return the currently active RunContext, or None."""
        if self._active is not None and not self._active._closed:
            return self._active
        return None

    def guarded(self, tool: str) -> Callable:
        """Decorator factory. Bind a tool function to this budget."""
        return make_guarded(self, tool)
