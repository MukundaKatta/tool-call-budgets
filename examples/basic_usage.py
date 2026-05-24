"""Minimal example: cap a tool, run an agent loop, print the report."""

from tool_call_budgets import ToolBudgets, ToolBudgetExceeded


def main() -> None:
    budgets = ToolBudgets(caps={
        "search": 5,
        "fetch_url": 10,
        "write_file": 3,
    })

    @budgets.guarded("search")
    def search(query: str) -> list[str]:
        return [f"result-for-{query}"]

    @budgets.guarded("fetch_url")
    def fetch_url(url: str) -> str:
        return f"<html>body of {url}</html>"

    @budgets.guarded("write_file")
    def write_file(path: str, body: str) -> None:
        print(f"would write {len(body)} bytes to {path}")

    with budgets.run() as ctx:
        try:
            for q in ["agents", "budgets", "python"]:
                hits = search(q)
                for hit in hits:
                    fetch_url(f"https://example.test/{hit}")
            write_file("notes.md", "summary of three queries")
        except ToolBudgetExceeded as e:
            print(f"agent stopped early: {e}")

        report = ctx.report()
        print("\nfinal usage:", report.usage)
        print("remaining:  ", report.remaining)
        print("aborted on: ", report.aborted_on)


if __name__ == "__main__":
    main()
