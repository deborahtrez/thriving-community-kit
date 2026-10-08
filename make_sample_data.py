"""
Generates the offline sample datasets used by the demos.

All names and numbers are synthetic (made up), so you can show them on stage
without exposing anyone's real data. Re-run any time: output is deterministic.

    python make_sample_data.py
"""

import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(2026)
DATA = Path(__file__).parent / "data"
DATA.mkdir(exist_ok=True)

FIRST = ["amina", "grace", "esther", "joy", "ruth", "faith", "sarah", "mercy", "brenda", "irene",
         "doreen", "patience", "lydia", "hope", "naomi", "agnes", "christine", "diana", "edith",
         "florence", "gloria", "harriet", "ivy", "juliet", "karen", "linda", "maria", "nora",
         "olive", "priscilla", "rachel", "sylvia", "tracy", "vivian", "winnie", "yvonne", "zawadi",
         "brian", "david", "isaac", "john", "kevin", "moses", "peter", "samuel", "timothy"]


def handle(i: int) -> str:
    return f"{FIRST[i % len(FIRST)]}-{i:02d}"


# ---------------------------------------------------------------- demo 1
def repo_snapshot() -> dict:
    start = datetime(2025, 10, 1, tzinfo=timezone.utc)
    maintainers = ["maintainer-anne", "maintainer-ben"]
    pulls, people = [], 0
    # Story: slow trickle of newcomers until the community adds good-first-issues
    # and a welcome bot in month 7, then arrivals pick up.
    newcomers_per_month = [1, 2, 1, 2, 1, 2, 4, 5, 6, 5, 7, 6]
    for month, n_new in enumerate(newcomers_per_month):
        base = start + timedelta(days=30 * month)
        for _ in range(random.randint(10, 14)):  # maintainers carry the load
            pulls.append({"author": random.choice(maintainers), "is_bot": False,
                          "created_at": (base + timedelta(hours=random.randint(0, 700))).isoformat()})
        for _ in range(n_new):
            who = handle(people)
            people += 1
            t = base + timedelta(hours=random.randint(0, 700))
            pulls.append({"author": who, "is_bot": False, "created_at": t.isoformat()})
            if random.random() < 0.22:  # roughly 1 in 5 come back
                pulls.append({"author": who, "is_bot": False,
                              "created_at": (t + timedelta(days=random.randint(5, 40))).isoformat()})
        for _ in range(3):
            pulls.append({"author": "dependabot[bot]", "is_bot": True,
                          "created_at": (base + timedelta(hours=random.randint(0, 700))).isoformat()})

    issues = []
    for k in range(40):
        opened = start + timedelta(days=random.randint(150, 360), hours=random.randint(0, 23))
        roll = random.random()
        if roll < 0.15:
            first = None  # never answered by a human
        else:
            hours = random.choice([3, 8, 20, 30, 45, 60, 70, 90, 120, 200, 300])
            first = (opened + timedelta(hours=hours)).isoformat()
        issues.append({"author": handle(random.randint(0, 60)), "created_at": opened.isoformat(),
                       "first_response_at": first, "state": random.choice(["open", "closed"]),
                       "labels": ["good first issue"] if k % 6 == 0 else []})

    contributors = [{"login": "maintainer-anne", "contributions": 412},
                    {"login": "maintainer-ben", "contributions": 198}]
    contributors += [{"login": handle(i), "contributions": random.randint(1, 25)} for i in range(people)]

    return {"repo": "example-community/python-starter-kit (sample data)",
            "source": "bundled offline sample - synthetic",
            "pulls": pulls, "issues": issues,
            "open_good_first_issues": 3, "contributors": contributors}


# ---------------------------------------------------------------- demo 3
def rsvp_csv(path: Path) -> None:
    # 12 monthly meetups. Story: big launch, then a drop-off "leaky bucket",
    # recovering once the chapter starts follow-ups and a buddy system (meetup 7+).
    events = [("2025-10-18", "Chapter launch: Why Python?"),
              ("2025-11-15", "Git & GitHub for beginners"),
              ("2025-12-13", "Data cleaning with pandas"),
              ("2026-01-17", "Your first open-source PR"),
              ("2026-02-14", "Intro to Django"),
              ("2026-03-14", "Women in Tech panel"),
              ("2026-04-18", "Study jam + buddy pairing"),
              ("2026-05-16", "Automating boring stuff"),
              ("2026-06-13", "Hackathon: civic data"),
              ("2026-07-18", "Lightning talks by members"),
              ("2026-08-15", "Intro to machine learning"),
              ("2026-09-19", "Sprint: contribute to a PyLadies repo")]
    pool, next_id, rows = [], 0, []
    for idx, (date, title) in enumerate(events):
        followups_on = idx >= 6
        new_rsvps = [90, 40, 35, 45, 30, 60, 35, 30, 50, 28, 40, 35][idx]
        # people who have attended before and RSVP again. Without follow-ups most
        # drift away for good; with follow-ups more of them stay in the loop.
        return_prob = 0.40 if followups_on else 0.22
        drift_away = 0.25 if followups_on else 0.45
        for member in list(pool):
            if random.random() < return_prob:
                showed = random.random() < (0.85 if followups_on else 0.70)
                rows.append([date, title, member, "yes" if showed else "no"])
            elif random.random() < drift_away:
                pool.remove(member)
        # brand-new people
        for _ in range(new_rsvps):
            member = f"m{next_id:04d}"
            next_id += 1
            showed = random.random() < (0.62 if followups_on else 0.50)
            rows.append([date, title, member, "yes" if showed else "no"])
            if showed:
                pool.append(member)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["event_date", "event_title", "member_id", "attended"])
        w.writerows(rows)


if __name__ == "__main__":
    (DATA / "sample_repo_snapshot.json").write_text(json.dumps(repo_snapshot(), indent=1))
    rsvp_csv(DATA / "sample_meetup_rsvps.csv")
    print("Wrote data/sample_repo_snapshot.json and data/sample_meetup_rsvps.csv")
