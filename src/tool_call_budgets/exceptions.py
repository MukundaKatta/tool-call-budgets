"""Exceptions raised by tool_call_budgets."""

from __future__ import annotations


class ToolBudgetExceeded(Exception):
    """Raised when a tool's call-count cap is hit.

    Attributes:
        tool: Name of the tool that hit its cap.
        cap: The configured cap for that tool.
        used: How many calls have been recorded for that tool, including the
            attempted call that triggered this exception.
    """

    def __init__(self, tool: str, cap: int, used: int):
        self.tool = tool
        self.cap = cap
        self.used = used
        super().__init__(f"{tool} hit cap of {cap}")


class UnknownTool(KeyError):
    """Raised when strict mode is on and a record() targets an undefined tool."""

    def __init__(self, tool: str):
        self.tool = tool
        super().__init__(tool)

    def __str__(self) -> str:
        return f"tool {self.tool!r} is not in caps and strict=True"
