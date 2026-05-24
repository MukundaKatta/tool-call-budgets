"""RunContext: per-run accounting for tool call budgets."""

from __future__ import annotations

from typing import Callable

from .exceptions import ToolBudgetExceeded, UnknownTool
from .report import BudgetReport


# A breach handler receives (tool, cap, attempted_use_count). Default raises.
BreachHandler = Callable[[str, int, int], None]


def _default_on_breach(tool: str, cap: int, used: int) -> None:
    raise ToolBudgetExceeded(tool=tool, cap=cap, used=used)


class RunContext:
    """Tracks per-tool usage for a single agent run.

    Created by ToolBudgets.run(). Not thread safe; one context per run.

    Behavior:
        record(tool) increments the call count for tool. If the new count
        exceeds the cap, on_breach is invoked. The default handler raises
        ToolBudgetExceeded. A custom handler can log and swallow, in which
        case the breach is counted but record() returns normally.

        strict mode controls what happens when tool is not in caps:
            strict=True (default): raise UnknownTool.
            strict=False: silently allow (treat as unlimited).
    """

    def __init__(
        self,
        caps: dict[str, int],
        on_breach: BreachHandler | None = None,
        strict: bool = True,
    ):
        # Defensive copy so a caller's later mutation of caps does not affect
        # an in-flight run.
        self._caps: dict[str, int] = dict(caps)
        self._usage: dict[str, int] = {tool: 0 for tool in self._caps}
        self._on_breach: BreachHandler = on_breach or _default_on_breach
        self._strict = strict
        self._aborted_on: str | None = None
        self._breach_count = 0
        self._closed = False

    def record(self, tool: str) -> int:
        """Record one call to tool. Returns the new usage count.

        Raises ToolBudgetExceeded by default if the cap is hit. With a custom
        on_breach handler that does not raise, returns the post-increment
        count even when over cap.
        """
        if self._closed:
            raise RuntimeError("RunContext is already closed")

        if tool not in self._caps:
            if self._strict:
                raise UnknownTool(tool)
            # Non-strict: do not track unknown tools at all so they cannot
            # quietly bloat the usage dict.
            return 0

        new_count = self._usage[tool] + 1
        cap = self._caps[tool]

        # Cap of 0 means "no calls allowed". Any call is a breach.
        if new_count > cap:
            self._breach_count += 1
            if self._aborted_on is None:
                self._aborted_on = tool
            # Hand off to the breach handler. Default raises and never
            # increments _usage past cap. A swallowing handler will let
            # control return here.
            self._on_breach(tool, cap, new_count)
            # If we get here, handler suppressed. Still count the attempt.
            self._usage[tool] = new_count
            return new_count

        self._usage[tool] = new_count
        return new_count

    def used(self, tool: str) -> int:
        """How many calls have been recorded for tool."""
        return self._usage.get(tool, 0)

    def remaining(self, tool: str) -> int:
        """Calls left before tool would breach. Floors at 0."""
        if tool not in self._caps:
            # Unknown tool in non-strict mode: effectively unbounded but we
            # surface 0 to avoid lying about an unconfigured tool.
            return 0
        return max(self._caps[tool] - self._usage[tool], 0)

    def report(self) -> BudgetReport:
        """Snapshot the current run state into an immutable BudgetReport."""
        remaining = {
            tool: max(self._caps[tool] - self._usage[tool], 0)
            for tool in self._caps
        }
        return BudgetReport(
            usage=dict(self._usage),
            caps=dict(self._caps),
            remaining=remaining,
            aborted_on=self._aborted_on,
            breach_count=self._breach_count,
        )

    def close(self) -> None:
        """Mark the context closed. Further record() calls will raise."""
        self._closed = True

    # Context manager protocol so callers can write `with budgets.run() as ctx`.
    def __enter__(self) -> "RunContext":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # We close on exit, including on exception, so a swallowed breach
        # cannot leak past the run boundary.
        self.close()
