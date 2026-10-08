"""
Demo 2 - First-Timer Welcome Bot
================================
"Nobody should open their first PR into silence."

A single Python file that runs as a GitHub Action. When someone opens
their FIRST issue or pull request in your repo, it:

  * greets them by name within seconds (time-to-first-response drops to ~0)
  * points them to your contributing guide and community chat
  * suggests 3 more "good first issue" tasks so they have a next step
  * labels the item "first-timer" so maintainers can prioritise reviewing it
  * when a first-timer's PR is MERGED, celebrates and invites them back
    (this is what moves the conversion-rate needle from Demo 1)

Note: an automated greeting is a welcome mat, not a review. CHAOSS recommends
filtering bot replies out of response-time metrics, which Demo 1 does, so a
human still needs to follow up.

Run locally (no GitHub needed):
  python welcome_bot.py --dry-run sample_events/first_pr_opened.json
  python welcome_bot.py --dry-run sample_events/first_pr_merged.json
  python welcome_bot.py --dry-run sample_events/regular_pr_opened.json

In a repo: copy this file to .github/scripts/ and the workflow to
.github/workflows/welcome.yml. GitHub provides GITHUB_TOKEN automatically.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

FIRST_TIME = {"FIRST_TIMER", "FIRST_TIME_CONTRIBUTOR"}

# ---- Customise these for your community (or set them as env vars) ----------
COMMUNITY = os.getenv("COMMUNITY_NAME", "PyLadies Kampala")
CHAT_LINK = os.getenv("CHAT_LINK", "https://example.org/join-our-chat")
CONTRIBUTING = os.getenv("CONTRIBUTING_PATH", "CONTRIBUTING.md")  # path inside your repo
LABEL = "first-timer"


# ---- Tiny GitHub REST helper -------------------------------------------------
class GitHub:
    def __init__(self, repo: str, token: str | None, dry_run: bool):
        self.repo, self.dry_run = repo, dry_run
        self.headers = {"Accept": "application/vnd.github+json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def _call(self, method: str, path: str, **kw):
        import requests

        r = requests.request(method, f"https://api.github.com{path}", headers=self.headers, timeout=20, **kw)
        r.raise_for_status()
        return r.json() if r.content else {}

    def count(self, query: str) -> int:
        """How many issues/PRs in this repo match a search, e.g. 'type:issue author:amina'."""
        if self.dry_run:
            return 1
        q = f"repo:{self.repo} {query}"
        return self._call("GET", "/search/issues", params={"q": q})["total_count"]

    def good_first_issues(self, limit: int = 3) -> list[dict]:
        if self.dry_run:
            return [
                {"number": 42, "title": "Fix typo in installation guide", "html_url": "#42"},
                {"number": 57, "title": "Add alt text to homepage images", "html_url": "#57"},
                {"number": 63, "title": "Write a test for the date helper", "html_url": "#63"},
            ]
        items = self._call(
            "GET", f"/repos/{self.repo}/issues",
            params={"labels": "good first issue", "state": "open", "per_page": limit},
        )
        return [i for i in items if "pull_request" not in i][:limit]

    def comment(self, number: int, body: str) -> None:
        if not self.dry_run:
            self._call("POST", f"/repos/{self.repo}/issues/{number}/comments", json={"body": body})

    def add_label(self, number: int, label: str) -> None:
        if not self.dry_run:
            self._call("POST", f"/repos/{self.repo}/issues/{number}/labels", json={"labels": [label]})


# ---- The messages --------------------------------------------------------------
def next_steps(gh: GitHub) -> str:
    lines = [f"- [#{i['number']} {i['title']}]({i['html_url']})" for i in gh.good_first_issues()]
    return "\n".join(lines) or "- Browse issues labelled `good first issue`"


def welcome_message(author: str, kind: str, gh: GitHub) -> str:
    return f"""👋 Welcome to {COMMUNITY}, @{author}, and thank you for your first {kind}!

A maintainer will take a look soon. While you wait:

- 📖 Read our [contributing guide](https://github.com/{gh.repo}/blob/HEAD/{CONTRIBUTING}), it answers most first-time questions
- 💬 Say hi in our [community chat]({CHAT_LINK}), there's a #first-timers channel just for you
- 🙋🏾‍♀️ Stuck? Comment here and tag `@maintainers`. No question is too small.

Looking for what to do next? These are open and beginner-friendly:
{next_steps(gh)}
"""


def merged_message(author: str, gh: GitHub) -> str:
    return f"""🎉 @{author}, your first contribution to {COMMUNITY} has been merged. You're officially a contributor!

Ready for round two? Pick one of these:
{next_steps(gh)}

See you in the [community chat]({CHAT_LINK}) 💜
"""


# ---- Decide what to do with this event ------------------------------------------
def handle(event: dict, gh: GitHub) -> list[str]:
    actions: list[str] = []
    if "pull_request" in event:
        item, kind = event["pull_request"], "pull request"
    elif "issue" in event:
        item, kind = event["issue"], "issue"
    else:
        return ["Ignored: not an issue or pull request event."]

    author = item["user"]["login"]
    if item["user"].get("type") == "Bot":
        return [f"Ignored: @{author} is a bot."]

    association = item.get("author_association", "NONE")
    action, number = event.get("action"), item["number"]

    if action == "opened":
        if kind == "pull request":
            first_timer = association in FIRST_TIME
        else:  # GitHub's flag only tracks commits, so for issues count their issues instead
            first_timer = association in FIRST_TIME or gh.count(f"type:issue author:{author}") <= 1
    elif action == "closed" and item.get("merged"):
        # After a merge GitHub may already call them a CONTRIBUTOR, so ask directly:
        # is this the only merged PR they have in this repo?
        first_timer = gh.count(f"type:pr is:merged author:{author}") <= 1
    else:
        first_timer = False

    if action == "opened" and first_timer:
        body = welcome_message(author, kind, gh)
        gh.comment(number, body)
        gh.add_label(number, LABEL)
        actions += [f"Commented on #{number}:\n\n{body}", f"Added label '{LABEL}' to #{number}"]
    elif action == "closed" and first_timer:
        body = merged_message(author, gh)
        gh.comment(number, body)
        actions.append(f"Commented on #{number}:\n\n{body}")
    else:
        actions.append(f"No action: @{author} ({association}) is not a first-timer, or event is '{action}'.")
    return actions


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", metavar="EVENT_JSON", help="simulate with a saved event payload")
    args = ap.parse_args()

    if args.dry_run:
        event = json.load(open(args.dry_run))
        gh = GitHub(event["repository"]["full_name"], None, dry_run=True)
    else:
        event = json.load(open(os.environ["GITHUB_EVENT_PATH"]))
        gh = GitHub(os.environ["GITHUB_REPOSITORY"], os.environ.get("GITHUB_TOKEN"), dry_run=False)

    for line in handle(event, gh):
        if args.dry_run:
            try:
                from rich.console import Console
                from rich.markdown import Markdown
                from rich.panel import Panel

                c = Console()
                if "\n\n" in line:
                    head, body = line.split("\n\n", 1)
                    c.print(f"[bold magenta]{head}[/]")
                    c.print(Panel(Markdown(body), title="What the newcomer sees", border_style="magenta"))
                else:
                    c.print(f"[bold]{line}[/]")
                continue
            except ImportError:
                pass
        print(line)


if __name__ == "__main__":
    sys.exit(main())
