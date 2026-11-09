"""Wrapped narrator: builds Team Wrapped slides from computed stats; Gemini only writes the captions."""
from __future__ import annotations

import json

from .. import llm, metrics
from ..prompts import NARRATOR_INSTRUCTIONS, NARRATOR_SYSTEM
from .twin import first_name


def _hour_label(h: int | None) -> str:
    if h is None:
        return "-"
    return f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}"


def member_slide(m: dict, f: dict, arch: str) -> dict:
    bt = f.get("byType", {})
    big, unit = {
        "night_owl": (f.get("latestNight") or _hour_label(f.get("peakHour")), "latest commit or edit of the project"),
        "closer": (f"{round(f['sprintIndex'] * 100)}%", "of their work landed in the final stretch"),
        "steady": (f"{f['longestStreak']} days", "longest streak of showing up"),
        "architect": (str(bt.get("commit", 0) + bt.get("pr", 0)), "commits and merged PRs"),
        "wordsmith": (str(bt.get("edit", 0)), "doc edits that shaped the report"),
        "glue": (str(bt.get("review", 0) + bt.get("meeting", 0) + bt.get("task", 0)),
                 "reviews, meetings and team tasks"),
        "wildcard": (str(f["events"]), "contributions wherever needed"),
    }[arch]
    return {
        "id": f"m-{m['uid']}",
        "kind": "member",
        "uid": m["uid"],
        "name": m["name"],
        "title": metrics.ARCHETYPES[arch]["name"],
        "archetype": arch,
        "big": big,
        "unit": unit,
        "chips": [
            f"Peak hour {_hour_label(f.get('peakHour'))}",
            f"Busiest day {f.get('busiestWeekday') or '-'}",
            f"{round(f.get('teamShare', 0) * 100)}% of team effort",
        ],
        "caption": f"{first_name(m)}: {metrics.ARCHETYPES[arch]['blurb']}",
    }


def build_slides(team: dict, members: list[dict], stats: dict, archetypes: dict[str, str]) -> list[dict]:
    t = stats["team"]
    bt = t["byType"]
    slides = [
        {"id": "intro", "kind": "intro", "title": f"{team['name']} Wrapped", "big": f"{t['weeks']} weeks",
         "unit": team.get("module") or "one group project",
         "caption": "Your project, your patterns, your people. Let's see how it really went."},
        {"id": "team-total", "kind": "stat", "title": "Together you made", "big": str(t["events"]),
         "unit": "contributions",
         "chips": [f"{bt.get('commit', 0)} commits", f"{bt.get('edit', 0)} doc edits",
                   f"{bt.get('review', 0)} reviews", f"{bt.get('meeting', 0)} meeting check-ins"],
         "caption": "Every one of them counted."},
    ]
    if t.get("busiestWeek"):
        slides.append({"id": "busiest-week", "kind": "stat", "title": "Your busiest week", "big": f"Week {t['busiestWeek']}",
                       "unit": f"of {t['weeks']}", "caption": "The week the group chat never slept."})
    nights = [(f["latestNight"], m) for m in members if (f := stats["members"][m["uid"]]).get("latestNight")]
    if nights:
        def mins(s: str) -> int:
            hm, ap = s.split()
            h, mi = map(int, hm.split(":"))
            return (h % 12 + (12 if ap == "PM" else 0)) * 60 + mi

        latest, who = max(nights, key=lambda x: mins(x[0]))
        slides.append({"id": "latest-night", "kind": "stat", "title": "Latest-night save", "big": latest,
                       "unit": f"by {first_name(who)}", "caption": "Someone had to. Thank you."})
    for m in members:
        slides.append(member_slide(m, stats["members"][m["uid"]], archetypes[m["uid"]]))
    slides.append({
        "id": "mix", "kind": "mix", "title": "Who did what", "unit": "share of team effort, by type",
        "bars": [{"uid": m["uid"], "name": first_name(m),
                  "share": stats["members"][m["uid"]].get("teamShare", 0),
                  "mix": stats["members"][m["uid"]]["mix"]} for m in members],
        "caption": "Different shapes of contribution. All of them needed.",
    })
    slides.append({"id": "outro", "kind": "outro", "title": "That's a wrap", "big": "GG",
                   "unit": team["name"], "caption": "Same team next semester?"})
    return slides


def reflection(m: dict, f: dict, arch: str) -> str:
    n = first_name(m)
    if not f["events"]:
        return f"{n}, there wasn't much activity to read this time. Next project, try linking your tools early so I can learn how you work."
    tip = {
        "night_owl": "Next time, block one daytime hour for teammates who sleep at night.",
        "closer": "Next time, try one small milestone in week two; future you will be grateful.",
        "steady": "Your consistency set the pace. Next time, say out loud when you need help; it's easy to miss.",
        "architect": "You built the core. Next time, pair with someone early so the knowledge isn't only in your head.",
        "wordsmith": "Your writing made the work legible. Next time, ask for review a few days earlier.",
        "glue": "You kept people talking. Next time, take one build task too so the credit matches the effort.",
        "wildcard": "You filled gaps where needed. Next time, claim one area early so you get to go deep.",
    }[arch]
    return f"{n}, you did your best work around {_hour_label(f.get('peakHour'))} and showed up on {f['activeDays']} days. {tip}"


async def wrapped(team: dict, members: list[dict], activity: list[dict]) -> dict:
    stats = metrics.compute(team, members, activity)
    archetypes = metrics.assign_archetypes(stats["members"])
    slides = build_slides(team, members, stats, archetypes)
    reflections = {m["uid"]: reflection(m, stats["members"][m["uid"]], archetypes[m["uid"]]) for m in members}
    if not llm.is_mock():
        facts = {s["id"]: {k: s.get(k) for k in ("title", "big", "unit", "name", "chips")} for s in slides}
        try:
            data = llm.parse_json(await llm.generate("narrator", NARRATOR_SYSTEM,
                                                     NARRATOR_INSTRUCTIONS.format(slides=json.dumps(facts)),
                                                     want_json=True)) or {}
            caps = data.get("captions") or {}
            for s in slides:
                if isinstance(caps.get(s["id"]), str) and caps[s["id"]].strip():
                    s["caption"] = caps[s["id"]].strip()
        except Exception:  # noqa: BLE001
            pass
    return {"slides": slides, "archetypes": archetypes, "reflections": reflections, "stats": stats}
