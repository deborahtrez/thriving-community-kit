"""
Demo 1 - Community Health Check
================================
"Is our community actually thriving, or does it just feel busy?"

Computes five CHAOSS-inspired health signals for any GitHub repository:

  1. New contributors per month      (are new people arriving?)
  2. Conversion rate                 (do first-timers come back for a 2nd contribution?)
  3. Time to first response          (how long does a newcomer wait to hear from a human?)
  4. Contributor absence factor      (how many people hold up 50% of the work? a.k.a. bus factor)
  5. Open "good first issue" count   (is there a front door for newcomers?)

Usage
-----
  python demo1_health_check.py --sample                 # offline, bundled sample data
  python demo1_health_check.py pyladies/pyladies.com    # live, any public repo
  GITHUB_TOKEN=ghp_xxx python demo1_health_check.py owner/repo   # live, higher rate limit

Metric definitions follow CHAOSS (chaoss.community): Time to First Response,
Conversion Rate, Contributor Absence Factor, Newcomer Experience.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402

HERE = Path(__file__).parent
SAMPLE = HERE / "data" / "sample_repo_snapshot.json"
console = Console()
API = "https://api.github.com"


# --------------------------------------------------------------------------
# 1. Get the data (live from GitHub, or from the bundled snapshot)
# --------------------------------------------------------------------------
def _is_bot(login: str, user_type: str = "User") -> bool:
    return user_type == "Bot" or login.endswith("[bot]") or login.endswith("-bot")


def fetch_live(repo: str, max_pages: int = 3, max_issue_lookups: int = 40) -> dict:
    """Pull a small, demo-friendly slice of a repo's history from the GitHub REST API."""
    import requests

    session = requests.Session()
    session.headers["Accept"] = "application/vnd.github+json"
    if token := os.getenv("GITHUB_TOKEN"):
        session.headers["Authorization"] = f"Bearer {token}"

    def get(path, **params):
        r = session.get(f"{API}{path}", params=params, timeout=20)
        if r.status_code == 403 and "rate limit" in r.text.lower():
            sys.exit("GitHub rate limit hit. Set GITHUB_TOKEN or run with --sample.")
        r.raise_for_status()
        return r.json()

    with console.status(f"Fetching pull requests for {repo}..."):
        prs = []
        for page in range(1, max_pages + 1):
            batch = get(f"/repos/{repo}/pulls", state="all", per_page=100, page=page)
            prs += [
                {
                    "author": p["user"]["login"],
                    "is_bot": _is_bot(p["user"]["login"], p["user"]["type"]),
                    "created_at": p["created_at"],
                }
                for p in batch
            ]
            if len(batch) < 100:
                break

    with console.status("Fetching issues and first responses..."):
        raw_issues = get(f"/repos/{repo}/issues", state="all", per_page=100)
        raw_issues = [i for i in raw_issues if "pull_request" not in i][:max_issue_lookups]
        issues = []
        for i in raw_issues:
            first_response = None
            if i["comments"]:
                for c in get(f"/repos/{repo}/issues/{i['number']}/comments", per_page=30):
                    who = c["user"]["login"]
                    if who != i["user"]["login"] and not _is_bot(who, c["user"]["type"]):
                        first_response = c["created_at"]
                        break
            issues.append(
                {
                    "author": i["user"]["login"],
                    "created_at": i["created_at"],
                    "first_response_at": first_response,
                    "state": i["state"],
                    "labels": [lbl["name"] for lbl in i["labels"]],
                }
            )
        gfi = get(f"/repos/{repo}/issues", state="open", labels="good first issue", per_page=100)

    with console.status("Fetching contributors..."):
        contributors = [
            {"login": c["login"], "contributions": c["contributions"]}
            for c in get(f"/repos/{repo}/contributors", per_page=100)
            if not _is_bot(c["login"], c.get("type", "User"))
        ]

    return {
        "repo": repo,
        "source": "live GitHub API",
        "pulls": prs,
        "issues": issues,
        "open_good_first_issues": len(gfi),
        "contributors": contributors,
    }


# --------------------------------------------------------------------------
# 2. Compute the health signals
# --------------------------------------------------------------------------
def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def analyse(data: dict) -> dict:
    human_prs = sorted(
        (p for p in data["pulls"] if not p["is_bot"]), key=lambda p: p["created_at"]
    )

    # New contributors per month + conversion (did they come back?)
    first_seen: dict[str, datetime] = {}
    pr_count: Counter = Counter()
    for p in human_prs:
        pr_count[p["author"]] += 1
        first_seen.setdefault(p["author"], _ts(p["created_at"]))

    # Everyone looks "new" in the first month of data, so the first month is the
    # baseline: only people whose first PR comes after it count as newcomers.
    baseline = min(first_seen.values()).strftime("%Y-%m") if first_seen else ""
    newcomers = {a: w for a, w in first_seen.items() if w.strftime("%Y-%m") > baseline}
    newcomers_by_month: dict[str, int] = defaultdict(int)
    for when in newcomers.values():
        newcomers_by_month[when.strftime("%Y-%m")] += 1
    if newcomers_by_month:  # show quiet months as zero instead of skipping them
        y, mo = map(int, min(newcomers_by_month).split("-"))
        last = max(newcomers_by_month)
        while f"{y:04d}-{mo:02d}" <= last:
            newcomers_by_month.setdefault(f"{y:04d}-{mo:02d}", 0)
            y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
    returned = sum(1 for a in newcomers if pr_count[a] >= 2)
    conversion = returned / len(newcomers) if newcomers else 0.0

    # Time to first human response on issues (hours)
    waits, unanswered = [], 0
    for i in data["issues"]:
        if i["first_response_at"]:
            waits.append((_ts(i["first_response_at"]) - _ts(i["created_at"])).total_seconds() / 3600)
        else:
            unanswered += 1
    median_wait = statistics.median(waits) if waits else None

    # Contributor absence factor: fewest people who account for 50% of contributions
    contribs = sorted((c["contributions"] for c in data["contributors"]), reverse=True)
    total, running, absence_factor = sum(contribs), 0, 0
    for n in contribs:
        running += n
        absence_factor += 1
        if running >= total / 2:
            break

    return {
        "contributors_total": len(newcomers),
        "newcomers_by_month": dict(sorted(newcomers_by_month.items())),
        "conversion": conversion,
        "returned": returned,
        "median_wait_hours": median_wait,
        "issues_checked": len(data["issues"]),
        "unanswered": unanswered,
        "absence_factor": absence_factor,
        "good_first_issues": data["open_good_first_issues"],
    }


# --------------------------------------------------------------------------
# 3. Tell the story (terminal report + chart)
# --------------------------------------------------------------------------
def verdict(ok: bool, warn: bool) -> str:
    return "[green]Healthy[/]" if ok else ("[yellow]Watch[/]" if warn else "[red]Act now[/]")


def report(data: dict, m: dict, chart_path: Path) -> None:
    console.print(
        Panel.fit(
            f"[bold]{data['repo']}[/]\nSource: {data['source']}",
            title="Community Health Check",
            border_style="magenta",
        )
    )
    t = Table(show_lines=True)
    t.add_column("Signal", style="bold")
    t.add_column("Result", justify="right")
    t.add_column("Status")
    t.add_column("What it tells you")

    recent = list(m["newcomers_by_month"].values())[-3:]
    avg_new = sum(recent) / len(recent) if recent else 0
    t.add_row(
        "New contributors / month",
        f"{avg_new:.1f}",
        verdict(avg_new >= 3, avg_new >= 1),
        "Avg over the last 3 months. Is the front door open?",
    )
    t.add_row(
        "Conversion rate",
        f"{m['conversion']:.0%}  ({m['returned']}/{m['contributors_total']})",
        verdict(m["conversion"] >= 0.30, m["conversion"] >= 0.15),
        "First-timers who came back for a 2nd PR.",
    )
    wait = m["median_wait_hours"]
    t.add_row(
        "Time to first response",
        f"{wait:.0f} h median" if wait is not None else "n/a",
        verdict(wait is not None and wait <= 48, wait is not None and wait <= 168),
        f"{m['unanswered']} of {m['issues_checked']} recent issues never got a human reply.",
    )
    t.add_row(
        "Contributor absence factor",
        str(m["absence_factor"]),
        verdict(m["absence_factor"] >= 4, m["absence_factor"] >= 2),
        "People doing 50% of the work. Low = burnout risk.",
    )
    t.add_row(
        "Open good-first-issues",
        str(m["good_first_issues"]),
        verdict(m["good_first_issues"] >= 5, m["good_first_issues"] >= 1),
        "Ready-made on-ramps for newcomers.",
    )
    console.print(t)

    # Chart: newcomers per month
    months = list(m["newcomers_by_month"].keys())
    counts = list(m["newcomers_by_month"].values())
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar(months, counts, color="#7B3FA0")
    ax.set_title(f"New contributors per month - {data['repo']}", loc="left", fontsize=13)
    ax.set_ylabel("First-time PR authors")
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    for x, y in zip(months, counts):
        ax.annotate(str(y), (x, y), ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    fig.savefig(chart_path, dpi=150)
    console.print(f"\n[dim]Chart saved to {chart_path}[/]")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", nargs="?", help="owner/repo, e.g. pyladies/pyladies.com")
    ap.add_argument("--sample", action="store_true", help="use bundled offline sample data")
    args = ap.parse_args()

    if args.sample or not args.repo:
        data = json.loads(SAMPLE.read_text())
    else:
        try:
            data = fetch_live(args.repo)
        except Exception as exc:  # wifi died on stage? fall back gracefully
            console.print(f"[yellow]Live fetch failed ({exc}). Falling back to sample data.[/]")
            data = json.loads(SAMPLE.read_text())

    out = HERE / "output"
    out.mkdir(exist_ok=True)
    report(data, analyse(data), out / "health_newcomers.png")


if __name__ == "__main__":
    main()
