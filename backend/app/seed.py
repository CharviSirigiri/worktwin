"""A realistic fake team so the demo always works, even with no GitHub repo or Drive folder.

Six weeks, four people with clashing styles. Week 3 is the rough week: Aisha goes quiet and
misses the check-in, so the retro has something real to say.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from . import config

DEMO_TEAM_ID = "demo-team"
START = date(2026, 10, 5)      # a Monday
DEADLINE = date(2026, 11, 15)  # 6 weeks later

TEAM = {
    "id": DEMO_TEAM_ID,
    "name": "Team Nebula",
    "module": "CT050-3-3 Project Management",
    "brief": "A campus energy-saving web app with a project report and a 10-minute pitch",
    "startDate": START.isoformat(),
    "deadline": DEADLINE.isoformat(),
    "repo": "",
    "driveFolderId": "",
    "workstreams": ["Backend & data", "Frontend", "Report writing", "Slides & demo video", "Coordination & submission"],
    "demo": True,
}

EVE = [f"{d}-EVE" for d in ["Mon", "Tue", "Wed", "Thu", "Fri"]]

MEMBERS = [
    {
        "uid": "aisha", "name": "Aisha Rahman", "email": "aisha@example.com", "githubLogin": "aisha-dev",
        "quiz": {"best_time": "night", "rhythm": "sprinter", "enjoy": ["coding"], "avoid": ["presenting"],
                 "channel": "discord", "reply": "day", "meetings": "short",
                 "availability": EVE + ["Sat-PM", "Sat-EVE", "Sun-EVE"],
                 "commitments": "Tutoring on Tue and Thu afternoons", "stuck": "quiet",
                 "frustration": "People changing the plan without telling the group."},
    },
    {
        "uid": "weijie", "name": "Tan Wei Jie", "shortName": "Wei Jie", "email": "weijie@example.com", "githubLogin": "weijie-t",
        "quiz": {"best_time": "day", "rhythm": "steady", "enjoy": ["coding", "research"], "avoid": ["writing"],
                 "channel": "whatsapp", "reply": "hour", "meetings": "short",
                 "availability": ["Mon-PM", "Tue-PM", "Wed-PM", "Thu-PM", "Fri-PM", "Wed-EVE", "Sat-PM"],
                 "commitments": "", "stuck": "ask",
                 "frustration": "Last-minute merges that break the build."},
    },
    {
        "uid": "priya", "name": "Priya Nair", "email": "priya@example.com", "githubLogin": "",
        "quiz": {"best_time": "evening", "rhythm": "bursts", "enjoy": ["writing", "research"], "avoid": ["coding"],
                 "channel": "whatsapp", "reply": "day", "meetings": "long",
                 "availability": EVE + ["Sat-AM", "Sat-PM"],
                 "commitments": "", "stuck": "alone",
                 "frustration": "Ending up writing the whole report alone at 3 AM."},
    },
    {
        "uid": "daniel", "name": "Daniel Lim", "email": "daniel@example.com", "githubLogin": "dlim",
        "quiz": {"best_time": "day", "rhythm": "bursts", "enjoy": ["organising", "presenting"], "avoid": ["coding"],
                 "channel": "whatsapp", "reply": "nextday", "meetings": "short",
                 "availability": ["Mon-PM", "Wed-PM", "Fri-PM", "Wed-EVE", "Sat-PM"],
                 "commitments": "Weekend shifts at a cafe", "stuck": "ask",
                 "frustration": "Nobody replying in the group chat."},
    },
]


def _ts(d: date, hour: float) -> str:
    dt = datetime(d.year, d.month, d.day, tzinfo=config.TZ) + timedelta(hours=hour)
    return dt.isoformat()


def build_activity(rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random(42)
    rows: list[dict] = []
    n = 0

    def add(uid, source, typ, d, hour, weight=1.0, meta=None):
        nonlocal n
        n += 1
        rows.append({"id": f"seed-{n:05d}", "uid": uid, "source": source, "type": typ, "ts": _ts(d, hour),
                     "weight": weight, "meta": meta or {}})

    for w in range(1, 7):
        week_start = START + timedelta(days=7 * (w - 1))
        days = [week_start + timedelta(days=i) for i in range(7)]
        weekdays = days[:5]

        # Aisha: night owl, sprinter. Quiet in week 3, flat out in weeks 5-6.
        sessions = {1: 2, 2: 3, 3: 1, 4: 2, 5: 6, 6: 6}[w]
        for d in rng.sample(days, sessions):
            for _ in range(rng.randint(2, 4) if w >= 5 else rng.randint(1, 3)):
                add("aisha", "github", "commit", d, rng.uniform(22, 26.5), round(rng.uniform(1.2, 2.6), 2))
        if w in (2, 5, 6):
            add("aisha", "github", "pr", rng.choice(days[3:]), rng.uniform(23, 25.5), 2.0)
        if w == 6:
            add("aisha", "github", "commit", days[5], 27.2, 2.4, {"message": "fix: final data pipeline"})  # 3:12 AM

        # Wei Jie: steady daytime coder and the main reviewer.
        for d in weekdays:
            if rng.random() < 0.85:
                for _ in range(rng.randint(1, 3)):
                    add("weijie", "github", "commit", d, rng.uniform(10, 17), round(rng.uniform(1.0, 2.0), 2))
        for _ in range(rng.randint(2, 4)):
            add("weijie", "github", "review", rng.choice(weekdays), rng.uniform(13, 18))
        if w in (1, 3, 4):
            add("weijie", "github", "pr", rng.choice(weekdays), rng.uniform(14, 17), 2.0)

        # Priya: evening writer, report edits, more as the deadline nears.
        for d in rng.sample(days, 4 if w < 5 else 6):
            for _ in range(rng.randint(1, 3)):
                add("priya", "drive", "edit", d, rng.uniform(19, 23), meta={"file": "Project Report"})

        # Daniel: organiser. Tasks, a few slide edits late on, rare commits.
        for _ in range(2):
            add("daniel", "task", "task", rng.choice(weekdays), rng.uniform(12, 17),
                meta={"kind": "coordination", "title": "Updated task board"})
        if w >= 5:
            for d in rng.sample(days, 3):
                add("daniel", "drive", "edit", d, rng.uniform(14, 20), meta={"file": "Pitch Slides"})
        if w in (2, 4, 6):
            add("daniel", "github", "commit", rng.choice(weekdays), rng.uniform(15, 18), 1.0)

        # Wednesday 8 PM check-in, logged by NFC tap-in.
        wed = days[2]
        attendance = {"aisha": w in (1, 2, 5, 6), "weijie": w != 5, "priya": True, "daniel": True}
        for uid, came in attendance.items():
            if came:
                add(uid, "tapin", "meeting", wed, 20 + rng.uniform(0, 0.15), meta={"slot": "Wed-EVE"})
    return rows


def seed(store) -> str:
    store.delete_team(DEMO_TEAM_ID)
    store.save_team(dict(TEAM))
    for m in MEMBERS:
        store.save_member(DEMO_TEAM_ID, {**m, "consent": {"github": True, "drive": True}, "profile": None,
                                         "nfcCard": f"DEMO-{m['uid'].upper()}"})
    store.add_activity(DEMO_TEAM_ID, build_activity())
    return DEMO_TEAM_ID
