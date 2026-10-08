"""
Demo 3 - Meetup Retention Analyzer
==================================
"Big launch numbers feel great. Returning members are what keep a chapter alive."

Feed it the attendance export from Meetup, Luma, Eventbrite, or a Google Form
(one row per person per event) and it answers:

  * How many people show up vs RSVP? (no-show rate)
  * How many attendees are brand new vs returning?
  * The leaky bucket: what % of first-timers come back within the next 3 events?
  * Did a change we made (buddy system, follow-up messages...) actually help?
  * Who should we personally nudge to come back? (exports a list)

Usage
-----
  python demo3_meetup_retention.py                                    # bundled sample
  python demo3_meetup_retention.py --change-date 2026-04-18           # compare before/after
  python demo3_meetup_retention.py my_export.csv \
      --date-col "Event Date" --id-col "Email" --attended-col "Checked In"

Privacy: hash or pseudonymise emails before sharing results. The nudge list is
for the organising team only.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

HERE = Path(__file__).parent
console = Console(width=max(Console().width, 110))
YES = {"yes", "y", "true", "1", "checked in", "attended", "x"}


def load(path: Path, date_col: str, id_col: str, attended_col: str, title_col: str | None) -> pd.DataFrame:
    df = pd.read_csv(path)
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col]).dt.date,
            # pseudonymise whatever ID we were given (emails, names...) so nothing personal is printed
            "member": df[id_col].astype(str).str.strip().str.lower().map(
                lambda s: hashlib.sha1(s.encode()).hexdigest()[:8]
            ),
            "attended": df[attended_col].astype(str).str.strip().str.lower().isin(YES),
        }
    )
    out["title"] = df[title_col] if title_col and title_col in df else out["date"].astype(str)
    return out


def analyse(df: pd.DataFrame, lookahead: int = 3) -> pd.DataFrame:
    events = sorted(df["date"].unique())
    shown = df[df["attended"]]
    first_visit = shown.groupby("member")["date"].min()

    rows = []
    for i, ev in enumerate(events):
        here = df[df["date"] == ev]
        att = here[here["attended"]]["member"]
        new = att[att.map(first_visit) == ev]
        upcoming = set(events[i + 1 : i + 1 + lookahead])
        came_back = shown[shown["date"].isin(upcoming) & shown["member"].isin(new)]["member"].nunique()
        rows.append(
            {
                "date": ev,
                "title": here["title"].iloc[0],
                "rsvps": len(here),
                "attended": len(att),
                "no_show": 1 - len(att) / len(here) if len(here) else 0,
                "first_timers": len(new),
                "returning": len(att) - len(new),
                # only meaningful once `lookahead` later events have happened
                "return_rate": came_back / len(new) if len(new) and len(upcoming) == lookahead else None,
            }
        )
    return pd.DataFrame(rows)


def report(stats: pd.DataFrame, change_date, chart: Path) -> None:
    t = Table(title="Meetup health, event by event")
    for col, j in [("Date", "left"), ("Event", "left"), ("RSVP", "right"), ("Came", "right"),
                   ("No-show", "right"), ("New", "right"), ("Returning", "right"),
                   ("New → back within 3", "right")]:
        t.add_column(col, justify=j, no_wrap=True)
    for r in stats.itertuples():
        done = not pd.isna(r.return_rate)
        rr = f"{r.return_rate:.0%}" if done else "too soon"
        style = "" if not done else ("bold green" if r.return_rate >= 0.4 else ("red" if r.return_rate < 0.25 else ""))
        t.add_row(str(r.date), str(r.title)[:28], str(r.rsvps), str(r.attended),
                  f"{r.no_show:.0%}", str(r.first_timers), str(r.returning), f"[{style}]{rr}[/]" if style else rr)
    console.print(t)

    if change_date:
        cd = pd.to_datetime(change_date).date()
        known = stats.dropna(subset=["return_rate"])
        before = known[known["date"] < cd]
        after = known[known["date"] >= cd]

        def rate(part):  # weighted by number of first-timers
            return (part["return_rate"] * part["first_timers"]).sum() / part["first_timers"].sum()

        if len(before) and len(after):
            console.print(
                f"\n[bold]Before {cd}:[/] {rate(before):.0%} of first-timers came back   "
                f"[bold]After:[/] [green]{rate(after):.0%}[/]"
            )
        console.print(
            f"[bold]Returning attendees per event:[/] {stats[stats['date'] < cd]['returning'].mean():.0f} before → "
            f"[green]{stats[stats['date'] >= cd]['returning'].mean():.0f}[/] after"
        )

    # Chart: who is in the room, new vs returning
    fig, ax = plt.subplots(figsize=(10, 4.6))
    x = [str(d)[:7] for d in stats["date"]]
    ax.bar(x, stats["returning"], color="#7B3FA0", label="Returning")
    ax.bar(x, stats["first_timers"], bottom=stats["returning"], color="#D9C2E8", label="First-timers")
    if change_date:
        idx = next((i for i, d in enumerate(stats["date"]) if d >= pd.to_datetime(change_date).date()), None)
        if idx is not None:
            ax.axvline(idx - 0.5, color="#333", ls="--", lw=1)
            ax.annotate("  follow-ups + buddy system start", (idx - 0.5, ax.get_ylim()[1] * 0.92), fontsize=9)
    ax.set_title("Who is in the room? New vs returning attendees per meetup", loc="left", fontsize=13)
    ax.set_ylabel("Attendees")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="lower right", bbox_to_anchor=(1, 1.0), ncol=2)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.08)
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    fig.tight_layout()
    fig.savefig(chart, dpi=150)
    console.print(f"\n[dim]Chart saved to {chart}[/]")


def nudge_list(df: pd.DataFrame, out: Path, last_n: int = 2) -> None:
    """First-timers from the last few events who haven't been back yet."""
    shown = df[df["attended"]]
    events = sorted(df["date"].unique())
    first_visit = shown.groupby("member")["date"].min()
    visits = shown.groupby("member")["date"].nunique()
    recent = set(events[-last_n:])
    nudge = sorted(m for m, d in first_visit.items() if d in recent and visits[m] == 1)
    pd.DataFrame({"member": nudge, "first_event": [first_visit[m] for m in nudge]}).to_csv(out, index=False)
    console.print(f"[bold]{len(nudge)} first-timers from the last {last_n} meetups haven't returned yet.[/] "
                  f"Send them a personal hello → {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?", default=str(HERE / "data" / "sample_meetup_rsvps.csv"))
    ap.add_argument("--date-col", default="event_date")
    ap.add_argument("--id-col", default="member_id")
    ap.add_argument("--attended-col", default="attended")
    ap.add_argument("--title-col", default="event_title")
    ap.add_argument("--change-date", help="date you changed something, to compare before vs after")
    args = ap.parse_args()

    df = load(Path(args.csv), args.date_col, args.id_col, args.attended_col, args.title_col)
    out = HERE / "output"
    out.mkdir(exist_ok=True)
    stats = analyse(df)
    report(stats, args.change_date, out / "meetup_retention.png")
    nudge_list(df, out / "nudge_list.csv")


if __name__ == "__main__":
    main()
