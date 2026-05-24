# Submissions

## Hermes Agent Challenge (dev.to write track)

Paste-ready post draft below. Word count ~1000.

---

### Title: I capped my agent at 5 search calls and it stopped costing me $40 a day

Last month I left an agent loop running overnight. It was a small research bot that was supposed to read one paper and summarize it. When I woke up, it had called `search()` 847 times. The same query, over and over, because some parsing step kept failing and the LLM kept deciding the right next move was another search.

The fix is obvious in hindsight: cap the call count. Hard. Per tool. Inside one run.

I checked what was already on PyPI and the existing budget libraries cap tokens, USD, or rate limits over time. None of them cap "max 5 search calls in this single agent run". So I wrote `tool-call-budgets`.

#### What it does

You declare a cap per tool. The library tracks usage inside one run and raises when a tool hits its cap. That is the whole library.

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
    for _ in range(4):
        ctx.record("search") # 5/5 used at the end
    ctx.record("search")     # raises ToolBudgetExceeded
```

If you would rather decorate the tool function and forget about it, there is a decorator form:

```python
@budgets.guarded("search")
def search(query: str) -> list[str]:
    return real_search_api(query)
```

Inside a `with budgets.run()` block, every `search()` call records one tick. Outside a run, calling a guarded function raises a `RuntimeError`. I made that loud on purpose. A "guarded" function silently bypassing its guard because no run was active would be the worst kind of bug.

#### Why this matters for agents specifically

Token caps catch one failure mode: the model writes a 100K-token response. USD caps catch another: the whole job costs more than it should. Neither catches a tight loop where the same cheap tool gets called a thousand times.

A `search()` call might cost 200 tokens and a tenth of a cent. A hundred of them costs you $10 if you are paying for the search API too. A thousand costs you a hundred. Your token budget never trips because each call is small. Your USD budget might not trip until you are already in the hole.

Per-tool call counts are a different axis. They catch loops directly. And they let you set a different bar per tool. `search` at 5 is fine. `write_file` at 3 keeps a misbehaving agent from blasting a thousand files into your filesystem. `dangerous_external_api` at 1 says "you get exactly one shot, do not screw it up".

#### The decision I had to make: raise or log

The default `on_breach` handler raises `ToolBudgetExceeded`. That is the safe default. The agent stops, you find out, you fix the loop.

But sometimes you want to log the breach and keep going. Say you are running an eval and you want to see all the things the agent tried to do, even after it should have been stopped. So `on_breach` is pluggable:

```python
breaches = []
budgets = ToolBudgets(
    caps={"search": 2},
    on_breach=lambda tool, cap, used: breaches.append((tool, used)),
)
```

If the handler does not raise, the run keeps going. `report.breach_count` tracks how many times the cap was exceeded. `report.aborted_on` records the first tool that breached (since that is usually the interesting one). A swallowing handler still gets counted, so when you grep your logs at the end of the day you can see "this run breached its search cap 12 times" even though nothing crashed.

#### Composes with other budget libraries

I keep these libraries small on purpose. Each one caps one axis:

- `token-budget-py` caps total tokens or USD across the whole run.
- `llm-budget-window` caps tokens or USD per sliding time window (per minute, per hour, per day).
- `tool-call-budgets` caps per-tool call count inside one run.

A common stack: `llm-budget-window` for the per-minute rate limit, `token-budget-py` for the per-job dollar cap, `tool-call-budgets` for the per-tool sanity check. Each catches a different failure. None of them try to be all three.

#### The end-of-run report

After the run, `ctx.report()` returns a frozen dataclass. I use this for logging:

```python
report = ctx.report()
print(report.as_dict())
# {
#   "usage": {"search": 5, "fetch_url": 1, "write_file": 0},
#   "caps": {"search": 5, "fetch_url": 10, "write_file": 3},
#   "remaining": {"search": 0, "fetch_url": 9, "write_file": 3},
#   "aborted_on": "search",
#   "breach_count": 1
# }
```

This is the thing I actually look at when an agent run finishes. Usage tells me what got called. Remaining tells me what headroom I had left. `aborted_on` tells me which cap was the binding constraint. If I see `aborted_on` consistently for the same tool across runs, that is a sign the cap is too low for the work the agent is being asked to do, or that the tool is buggy. Either way, useful signal.

#### Things I cut from v0.1

I almost added a "warn at 80%" hook. Then I asked myself when I would ever want that, and the honest answer was "never, the breach tells me everything". So it is not in there.

I almost added per-call cost tracking. But `agenttrace` already does that and combining them is one line. Smaller libraries are easier to combine than big ones to dismantle.

I almost added retry-with-backoff semantics. Then I realized `llm-retry` exists and you should compose them. Same answer.

#### Try it

It is on GitHub at MukundaKatta/tool-call-budgets. MIT, zero dependencies, Python 3.10 and up. Pip install when published.

There are two examples in the repo. `basic_usage.py` runs a small simulated research agent with three tools and prints the report. `runaway_agent_demo.py` simulates the overnight loop that started this whole library and shows it getting stopped at five.

I ship one library a week in this family now. Same shape every time: small, single purpose, zero deps, BYO LLM. If you want the others, the sibling list is in the README.

Twenty-six tests, all passing. Async tools work. Decorator stacking works. cap=0 means "no calls allowed" and the first call raises. Done.

---

## Future submissions

Open AI-governance hackathon slot if one shows up in May 2026. Reuse the post above with a one-paragraph governance framing on top.
