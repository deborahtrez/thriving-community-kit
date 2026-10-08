# Talk run-sheet: "Build the room, not just the event"

45 minutes · 24 slides · 4 demos. Times are when each slide should *start*.

## The night before

- [ ] Push this folder to GitHub, then put the link on the Q&A slide (and a QR code if you can).
- [ ] Fresh setup on the laptop you'll present from:
      `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- [ ] Run every command below once, so `output/` exists and nothing surprises you.
- [ ] Create a GitHub token (Settings → Developer settings → fine-grained, public read-only) and
      `export GITHUB_TOKEN=...` in the terminal you'll demo from. Without it GitHub allows 60
      requests/hour, and one live health check uses about 45.
- [ ] Optional: download the deck as PDF from the Slides page (Share › Export) as an offline backup.

## On stage setup (5 min before)

- Terminal: font size 20+ pt, dark theme, `cd` into this folder, venv active, `clear`.
- Second tab: `output/` folder open in the file browser, for showing the PNG charts.
- Wifi down? Every demo works offline. The live health check falls back to sample data on its own.

## Timeline

| Start | Slide(s) | What happens |
|------:|----------|--------------|
| 0:00 | Cover | Show of hands: who runs a community? Who feels it depends on just them? |
| 0:45 | June 2021 | The OSCA Kampala origin story |
| 1:45 | Two hats | Community builder + IT auditor: evidence over vibes |
| 2:30 | Five verbs | The map: Arrive, Stay, Return, Lead, Survive |
| 4:00 | Struggle → Research → Africa gap | Why communities stall (Mahari & Meluso; your 2024 barriers) |
| 7:00 | Measure | Vanity vs health metrics (CHAOSS) |
| 8:15 | **Demo 1** | `python demo1_health_check.py --sample` then live on a repo |
| 12:00 | Demo 1 result | Busy ≠ healthy (backup slide if the demo fails) |
| 13:00 | Arrive | The front door + code is one door of many |
| 14:00 | First response | "Nobody should open their first PR into silence." Pause. |
| 15:00 | **Demo 2** | Three dry runs of the welcome bot |
| 19:00 | Leaky bucket | OSCA 2021 playbook + what brings people back (add your anecdote) |
| 20:30 | **Demo 3** | `python demo3_meetup_retention.py --change-date 2026-04-18` |
| 23:30 | Demo 3 result | 33% → 68% (backup slide) |
| 25:00 | Ladder | Participant → Maintainer; Outreachy is a rung |
| 27:00 | Survive | Design for your own absence |
| 29:00 | Funding | Partners, PSF grants (with care), credibility |
| 31:00 | Purpose | Geonsanga + digital public goods |
| 33:00 | **Demo 4** | `cookiecutter template_welcoming_repo` (skip if behind time) |
| 34:00 | 30-day plan | Measure · Open · Follow up · Share |
| 35:30 | Close | Next billion creators |
| 36:00 | Q&A | Prepared answers are in the slide notes |

**Behind schedule?** Cut in this order: Demo 4 (talk over the slide), the Africa gap slide (one sentence), the
regular_pr_opened dry run in Demo 2.

## Demo commands (copy-paste)

```bash
# Demo 1
python demo1_health_check.py --sample
python demo1_health_check.py pyladies/pyladies.com      # live; needs wifi
open output/health_newcomers.png                         # Windows: start, Linux: xdg-open

# Demo 2
python demo2_welcome_bot/welcome_bot.py --dry-run demo2_welcome_bot/sample_events/first_pr_opened.json
python demo2_welcome_bot/welcome_bot.py --dry-run demo2_welcome_bot/sample_events/first_pr_merged.json
python demo2_welcome_bot/welcome_bot.py --dry-run demo2_welcome_bot/sample_events/regular_pr_opened.json

# Demo 3
python demo3_meetup_retention.py --change-date 2026-04-18
open output/meetup_retention.png
open output/nudge_list.csv

# Demo 4
cookiecutter template_welcoming_repo        # press Enter through the defaults
cat pyladies-kampala-project/GOVERNANCE.md
rm -rf pyladies-kampala-project             # so it doesn't clash on the next rehearsal
```

## If something breaks

| Problem | Do this |
|---------|---------|
| Live GitHub call fails or rate-limits | It falls back to sample data by itself. Say "conference wifi!" and keep going. |
| A script errors | Skip to the matching "result" slide: it shows the same output. |
| cookiecutter says the folder exists | `rm -rf pyladies-kampala-project` and rerun, or skip Demo 4. |
| Projector cuts off the terminal | Zoom the terminal font down one step; the tables are about 110 characters wide. |

## Numbers on the slides (all from the synthetic sample data)

Health check: 17% conversion (7 of 41) · 70 h median first response · 5 of 40 issues unanswered · absence factor 2.
Meetups: 33% → 68% of first-timers return within 3 events · 6 → 34 returning attendees per meetup · 36 to nudge.
If you regenerate the sample data, these stay the same (the generator is seeded).
