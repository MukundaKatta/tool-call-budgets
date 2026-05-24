"""Demo: a buggy agent in an infinite loop is stopped by the cap.

Without tool_call_budgets, this loop would call search() forever and burn
your API quota. With a cap of 5, the 6th call raises and the agent stops.
"""

from tool_call_budgets import ToolBudgets, ToolBudgetExceeded


def main() -> None:
    budgets = ToolBudgets(caps={"search": 5})

    @budgets.guarded("search")
    def search(query: str) -> str:
        # Imagine this hitting a real search API and costing money on every call.
        return f"result for {query}"

    print("starting runaway agent simulation. cap = 5 search calls.")
    iterations = 0

    with budgets.run() as ctx:
        try:
            # An LLM that keeps deciding to call search no matter what.
            while True:
                iterations += 1
                search("same broken query")
                print(f"  iteration {iterations}: search succeeded")
        except ToolBudgetExceeded as e:
            print(f"\nSTOPPED: {e}")
            print(f"  total iterations attempted: {iterations}")

        report = ctx.report()
        print("\nreport:")
        print(f"  usage:      {report.usage}")
        print(f"  remaining:  {report.remaining}")
        print(f"  aborted_on: {report.aborted_on}")


if __name__ == "__main__":
    main()
