"""tool_call_budgets: per-tool call-count caps for a single AI agent run.

Public surface:
    ToolBudgets, RunContext, BudgetReport, ToolBudgetExceeded, UnknownTool

Quickstart:

    from tool_call_budgets import ToolBudgets, ToolBudgetExceeded

    budgets = ToolBudgets(caps={"search": 5, "fetch_url": 10})

    with budgets.run() as ctx:
        ctx.record("search")
        ctx.record("fetch_url")
        report = ctx.report()
        print(report.remaining)
"""

from .budgets import ToolBudgets
from .context import RunContext
from .exceptions import ToolBudgetExceeded, UnknownTool
from .report import BudgetReport

__all__ = [
    "ToolBudgets",
    "RunContext",
    "BudgetReport",
    "ToolBudgetExceeded",
    "UnknownTool",
]

__version__ = "0.1.0"
