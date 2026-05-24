"""BudgetReport dataclass: end-of-run usage summary."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BudgetReport:
    """End-of-run summary of a single agent run.

    Attributes:
        usage: tool name -> calls recorded.
        caps: tool name -> configured cap.
        remaining: tool name -> max(cap - usage, 0). For tools never recorded,
            usage is 0 and remaining equals cap.
        aborted_on: name of the tool that triggered ToolBudgetExceeded, or
            None if the run finished without breaching any cap.
        breach_count: how many breach attempts happened during the run.
            With the default raising behavior this is 0 or 1, but a custom
            on_breach handler can suppress raising and let multiple breaches
            accumulate.
    """

    usage: dict[str, int]
    caps: dict[str, int]
    remaining: dict[str, int] = field(default_factory=dict)
    aborted_on: str | None = None
    breach_count: int = 0

    def utilization(self) -> dict[str, float]:
        """Return per-tool utilization as a fraction in [0.0, +inf).

        cap of 0 maps to inf when there is any usage, else 0.0. This keeps
        the value defined for the edge case where a tool is locked off.
        """
        out: dict[str, float] = {}
        for tool, cap in self.caps.items():
            used = self.usage.get(tool, 0)
            if cap == 0:
                out[tool] = float("inf") if used > 0 else 0.0
            else:
                out[tool] = used / cap
        return out

    def as_dict(self) -> dict[str, object]:
        """Plain dict form for logging or JSON serialization."""
        return {
            "usage": dict(self.usage),
            "caps": dict(self.caps),
            "remaining": dict(self.remaining),
            "aborted_on": self.aborted_on,
            "breach_count": self.breach_count,
        }
