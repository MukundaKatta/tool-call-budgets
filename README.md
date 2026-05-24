# tool-call-budgets

[![PyPI](https://img.shields.io/badge/pypi-tool--call--budgets-blue)](https://pypi.org/project/tool-call-budgets/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](tests/)

Per-tool call-count caps for AI agent runs. Set `search` at 5, `fetch_url` at 10, `write_file` at 3, and the 6th `search()` raises before it ever hits your API. Zero runtime dependencies.

Built for the obvious failure mode: an agent gets stuck in a loop, calls the same tool 200 times, and you find out from the invoice.

## Install

```bash
pip install tool-call-budgets
```

Zero runtime dependencies. Python 3.10+.

## 30-second quickstart

```python
from tool_call_budgets import ToolBudgets, ToolBudgetExceeded

budgets = ToolBudgets(caps={
    "search": 5,
    "fetch_url": 10,
    "write_file": 3,
})

with budgets.run() as ctx:
    ctx.record("search")     # 1/5 used
    ctx.record("fetch_url")  # 1/10 used
    # ... agent loop continues ...
    for _ in range(4):
        ctx.record("search") # 5/5 used at the end
    ctx.record("search")     # raises ToolBudgetExceeded

report = ctx.report()
print(report.usage)       # {"search": 5, "fetch_url": 1, "write_file": 0}
print(report.remaining)   # {"search": 0, "fetch_url": 9, "write_file": 3}
print(report.aborted_on)  # "search"
```

Prefer a decorator on the tool itself:

```python
@budgets.guarded("search")
def search(query: str) -> list[str]:
    return real_search_api(query)

with budgets.run() as ctx:
    search("python")  # records one call, then runs
    search("agents")  # records another
```

## What it does

- **Per-tool call-count caps.** One number per tool. No timing logic, no token math.
- **Decorator or manual record.** Wrap your tool function with `@budgets.guarded("name")`, or call `ctx.record("name")` yourself.
- **Pluggable on_breach handler.** Default raises `ToolBudgetExceeded`. Pass `on_breach=my_logger.warn` to log instead of raise, or `on_breach=lambda *_: raise StopAgent()` to throw your own exception type.
- **End-of-run report.** `ctx.report()` returns a `BudgetReport` with `usage`, `remaining`, `aborted_on`, `breach_count`, plus `as_dict()` for JSON logging.
- **Sync + async tools.** Same decorator works on both.
- **Strict by default.** Recording a tool you did not declare in `caps` raises `UnknownTool`. Pass `strict=False` to silently ignore.
- **Short-circuits before the tool runs.** A breach raises before the wrapped function body executes; you do not pay for the breaching call.

## When to use this (vs sibling libs)

Three small libs, three different budget questions:

| Library | What it caps | When to reach for it |
|---|---|---|
| **`tool-call-budgets`** | **Per-tool call count** inside a single agent run | Stop a buggy agent that calls `search()` in an infinite loop. |
| [`token-budget-py`](https://pypi.org/project/token-budget-py/) | **Total tokens or USD** across all calls, no time window | Hard cap on a single job: "this run cannot spend more than $5". |
| [`llm-budget-window`](https://crates.io/crates/llm-budget-window) | **Tokens or USD per sliding window** (per minute, hour, day) | Rate limiting over time: "no more than 10K tokens per minute". |

They compose. A common stack: `llm-budget-window` for hourly rate limits, `token-budget-py` for the per-job dollar cap, `tool-call-budgets` for the per-tool sanity check. Each catches a different failure.

If you want to memoize repeat calls instead of capping them, use [`tool-call-cache`](https://pypi.org/project/tool-call-cache/).

## Sibling libs in the agent-stack family

This is one of a small set of zero-dep Python and Rust libs aimed at AI agent operators:

- [`agentleash`](https://github.com/MukundaKatta/agentleash) - money + egress safety harness
- [`birddog`](https://github.com/MukundaKatta/birddog) - audited Bright Data egress for scrapers
- [`tool-call-cache`](https://github.com/MukundaKatta/tool-call-cache) - memoize repeat tool calls
- [`token-budget-py`](https://github.com/MukundaKatta/token-budget-py) - token + USD budget
- [`agentvet`](https://github.com/MukundaKatta/agentvet) - validate tool args before execution
- [`agenttrace`](https://github.com/MukundaKatta/agenttrace) - cost + latency tracking

Same shape: small, single-purpose, zero deps, BYO-LLM. Pick the ones you need.

## API reference

### `ToolBudgets(caps, on_breach=None, strict=True)`

- `caps: dict[str, int]` - tool name to max calls per run. `0` means "no calls allowed".
- `on_breach: Callable[[str, int, int], None] | None` - handler invoked with `(tool, cap, used)` on every breach. Default raises `ToolBudgetExceeded`.
- `strict: bool` - if `True`, `record()` on an undeclared tool raises `UnknownTool`. If `False`, undeclared tools are silently ignored (not tracked).

### `budgets.run() -> RunContext`

Open a fresh per-run context. Use as a context manager. Only one run can be active per `ToolBudgets` instance at a time.

### `RunContext`

- `record(tool: str) -> int` - record one call. Returns new usage count. Raises on breach (default handler).
- `used(tool: str) -> int` - current call count for tool.
- `remaining(tool: str) -> int` - `max(cap - used, 0)`.
- `report() -> BudgetReport` - snapshot run state.
- `close() -> None` - mark the context closed. Called automatically on `__exit__`.

### `BudgetReport`

Frozen dataclass:

- `usage: dict[str, int]`
- `caps: dict[str, int]`
- `remaining: dict[str, int]`
- `aborted_on: str | None` - tool that triggered the first breach.
- `breach_count: int` - total breaches recorded (relevant with a non-raising `on_breach`).
- `utilization() -> dict[str, float]` - per-tool used / cap.
- `as_dict() -> dict` - plain dict for JSON logging.

### `@budgets.guarded(tool: str)`

Decorator. Wraps a sync or async function so each call records against the currently active run. Raises `RuntimeError` if called with no active run.

### Exceptions

- `ToolBudgetExceeded(tool, cap, used)` - default breach behavior.
- `UnknownTool(tool)` - strict-mode record on an undeclared tool.

## Examples

See `examples/`:

- `examples/basic_usage.py` - three tools, mixed usage, end-of-run report.
- `examples/runaway_agent_demo.py` - an infinite loop stopped by a cap of 5.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Targets a 25+ test suite covering construction, record/used/remaining, the decorator (including async and decorator stacking), the report, custom `on_breach` handlers, and end-to-end agent simulations.

## License

MIT. See [LICENSE](LICENSE).
