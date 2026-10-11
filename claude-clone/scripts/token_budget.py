#!/usr/bin/env python3
"""Report token counts for the clone files against the budgets in the guide.

Uses tiktoken when it is installed and its encoding is cached. Otherwise it
falls back to an estimate, the larger of words * 1.33 and characters / 4,
which runs a little high for English prose. Exit code 1 means a budget is
over.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

# (file, soft floor, soft ceiling, hard ceiling)
# The guide sets the about-me and my-company numbers and the 6000 total.
# The anti-ai ceiling is what is left of the total after the other two.
BUDGETS = [
    ("about-me.md", 2000, 4000, 5000),
    ("anti-ai-writing-style.md", 0, 1800, 2000),
    ("my-company.md", 0, 1000, 1200),
]
TOTAL_CEILING = 6000


def counter():
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return "tiktoken cl100k_base", lambda s: len(enc.encode(s))
    except Exception:
        return "estimate", lambda s: max(int(len(s.split()) * 1.33), len(s) // 4)


def main() -> int:
    method, count = counter()
    rows, total, over = [], 0, False
    for name, floor, ceiling, hard in BUDGETS:
        path = HERE / name
        if not path.exists():
            rows.append((name, "missing", ""))
            over = True
            continue
        n = count(path.read_text(encoding="utf-8"))
        total += n
        if n > hard:
            status, over = "OVER HARD CEILING", True
        elif n > ceiling:
            status, over = "over soft ceiling", True
        elif n < floor:
            status = "under floor"
        else:
            status = "ok"
        rows.append((name, str(n), status))

    rows.append(("total", str(total), "ok" if total <= TOTAL_CEILING else "OVER 6000"))
    over = over or total > TOTAL_CEILING

    width = max(len(r[0]) for r in rows)
    print(f"method: {method}")
    for name, n, status in rows:
        print(f"{name:<{width}}  {n:>6}  {status}")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
