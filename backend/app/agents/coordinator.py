"""Coordinator agent: drafts the Team Charter, chairs the twins' meeting, and runs the weekly retro."""
from __future__ import annotations

import json
from collections import Counter
from datetime import timedelta
from typing import AsyncIterator

from .. import llm, metrics
from ..prompts import CHARTER_INSTRUCTIONS, COORDINATOR_SYSTEM, RETRO_INSTRUCTIONS, RETRO_SYSTEM
from ..quiz import SLOT_LABEL, SLOTS
from . import twin

DEFAULT_WORKSTREAMS = ["Backend & data", "Frontend", "Report writing", "Slides & demo video", "Coordination & submission"]

KEYWORDS = [
    ("design", ("design", "ui", "ux", "figma", "poster")),
    ("presenting", ("slide", "demo", "present", "pitch", "video")),
    ("writing", ("report", "writing", "doc", "essay", "readme")),
    ("research", ("research", "survey", "literature", "data collection")),
    ("organising", ("coordination", "manage", "submission", "planning", "lead")),
    ("coding", ("backend", "frontend", "code", "app", "api", "model", "data", "iot", "web")),
]
OFFSET = {"steady": 4, "bursts": 6, "sprinter": 8}
WHY_DEADLINE = {
    "steady": "Steady pace, so a normal buffer is enough.",
    "bursts": "Works in bursts; a slightly earlier date leaves room for one more burst.",
    "sprinter": "Deadline sprinter: an earlier internal date keeps the team's final week calm.",
}


def area_of(workstream: str) -> str:
    w = workstream.lower()
    for area, words in KEYWORDS:
        if any(k in w for k in words):
            return area
    return "organising"


def draft_charter(team: dict, members: list[dict]) -> dict:
    """A rule-based first draft. The twins then discuss it; Gemini may adjust it in real mode."""
    profiles = {m["uid"]: m.get("profile") or {} for m in members}
    deadline = metrics.parse_date(team["deadline"])

    # meeting slot everyone (or most people) can make
    counts = Counter(s for p in profiles.values() for s in p.get("availability", []))
    ranked = sorted(SLOTS, key=lambda s: (-counts[s], SLOTS.index(s)))
    meetings = []
    for s in ranked[:2]:
        if counts[s] == 0:
            break
        who = counts[s]
        meetings.append({
            "slot": s,
            "label": f"{SLOT_LABEL[s]} check-in" if not meetings else f"{SLOT_LABEL[s]} (backup slot)",
            "why": f"{who} of {len(members)} members are free then.",
        })

    # roles: everyone gets at least one thing they enjoy, load spread evenly
    streams = team.get("workstreams") or DEFAULT_WORKSTREAMS
    load = Counter()
    roles = []
    for ws in streams:
        area = area_of(ws)

        def score(m):
            p = profiles[m["uid"]]
            s = 0.0
            s += 2 if area in p.get("strengths", []) else 0
            s -= 3 if area in p.get("avoid", []) else 0
            s -= 1.2 * load[m["uid"]]
            return s

        best = max(members, key=score)
        load[best["uid"]] += 1
        liked = area in profiles[best["uid"]].get("strengths", [])
        roles.append({"uid": best["uid"], "role": ws,
                      "why": f"Enjoys {area}." if liked else f"Spreads the load; {area} is not on their avoid list."})
    for m in members:  # anyone left without a role takes one from the busiest member
        if load[m["uid"]] == 0 and roles:
            busiest = max(load, key=load.get)
            idx = next(i for i, r in enumerate(roles) if r["uid"] == busiest)
            roles[idx] = {**roles[idx], "uid": m["uid"], "why": "Shared out so everyone owns a piece."}
            load[busiest] -= 1
            load[m["uid"]] += 1

    deadlines = []
    for m in members:
        rhythm = profiles[m["uid"]].get("rhythm", "bursts")
        d = deadline - timedelta(days=OFFSET.get(rhythm, 6))
        deadlines.append({"uid": m["uid"], "date": d.isoformat(), "why": WHY_DEADLINE[rhythm]})

    channel = Counter(p.get("channel", "whatsapp") for p in profiles.values()).most_common(1)[0][0]
    slowest = max((p.get("reply", "day") for p in profiles.values()), key=["hour", "day", "nextday"].index, default="day")
    style = Counter(p.get("meetings", "short") for p in profiles.values()).most_common(1)[0][0]
    norms = [
        f"Main channel: {twin.CHANNEL.get(channel, channel)}.",
        {"hour": "Reply within a few hours.", "day": "Reply the same day.", "nextday": "Reply within 24 hours."}[slowest],
        {"short": "Weekly check-in, 30 minutes max.", "long": "One longer working session a week.",
         "async": "Async update every Monday, short call only when needed."}[style],
        "Every Friday, each member posts a 2-line progress update.",
    ]
    if any(p.get("stuck") == "quiet" for p in profiles.values()):
        norms.append("If someone is quiet for 2 days, their own twin nudges them first. No public call-outs.")
    return {"roles": roles, "meetings": meetings, "internalDeadlines": deadlines, "norms": norms,
            "summary": f"{len(roles)} workstreams shared across {len(members)} people, with staggered internal deadlines."}


def normalize_charter(c: dict | None, draft: dict, members: list[dict]) -> dict:
    """Accept the model's charter only where it is well-formed; fall back to the draft field by field."""
    if not c:
        return draft
    uids = {m["uid"] for m in members}
    out = dict(draft)
    roles = [r for r in c.get("roles", []) if isinstance(r, dict) and r.get("uid") in uids and r.get("role")]
    if roles and {r["uid"] for r in roles} == uids:
        out["roles"] = [{"uid": r["uid"], "role": str(r["role"]), "why": str(r.get("why", ""))} for r in roles]
    meets = [m for m in c.get("meetings", []) if isinstance(m, dict) and m.get("slot") in SLOT_LABEL]
    if meets:
        out["meetings"] = [{"slot": m["slot"], "label": str(m.get("label") or SLOT_LABEL[m["slot"]]),
                            "why": str(m.get("why", ""))} for m in meets[:2]]
    dls = [d for d in c.get("internalDeadlines", []) if isinstance(d, dict) and d.get("uid") in uids]
    if len(dls) == len(uids):
        try:
            for d in dls:
                metrics.parse_date(str(d["date"]))
            out["internalDeadlines"] = [{"uid": d["uid"], "date": str(d["date"])[:10], "why": str(d.get("why", ""))}
                                        for d in dls]
        except (ValueError, KeyError):
            pass
    norms = [str(n) for n in c.get("norms", []) if isinstance(n, str) and n.strip()]
    if norms:
        out["norms"] = norms[:7]
    if isinstance(c.get("summary"), str) and c["summary"].strip():
        out["summary"] = c["summary"].strip()
    return out


# ---------------------------------------------------------------- negotiation
COORD_MOCK = {
    "open": "Hi twins! We're planning \"{brief}\", due {deadline}. Round 1: tell us when your human works best and what they want to own.",
    "draft": "Thanks all. Draft plan: {roles}. Weekly check-in on {meeting}. Internal deadlines are staggered so the final week stays calm. Objections?",
    "last": "Nearly there. Last round: any working agreement we should add?",
    "close": "Done! The Team Charter is ready. Each of you can review and accept it.",
}


def _roles_line(draft: dict, members: list[dict]) -> str:
    parts = []
    for m in members:
        roles = [r["role"] for r in draft["roles"] if r["uid"] == m["uid"]]
        if roles:
            parts.append(f"{twin.first_name(m)} on {twin._join(roles)}")
    return "; ".join(parts)


async def _coord_say(team: dict, members: list[dict], key: str, draft: dict, transcript: list[dict]) -> str:
    fill = {
        "brief": team.get("brief") or team["name"],
        "deadline": twin.fmt_date(team["deadline"]),
        "roles": _roles_line(draft, members),
        "meeting": SLOT_LABEL[draft["meetings"][0]["slot"]] if draft["meetings"] else "a time to be agreed",
    }
    if llm.is_mock():
        return COORD_MOCK[key].format(**fill)
    system = COORDINATOR_SYSTEM.format(brief=fill["brief"], deadline=fill["deadline"],
                                       names=", ".join(twin.first_name(m) for m in members))
    lines = "\n".join(f"{m['name']}: {m['text']}" for m in transcript[-14:])
    task = {
        "open": "Open the meeting and ask round 1: when does each human work best, and what do they want to own?",
        "draft": f"Present this draft plan briefly and ask for objections: {json.dumps(draft)}",
        "last": "Ask for any final working agreements.",
        "close": "Close the meeting: say the charter is ready for everyone to accept.",
    }[key]
    try:
        text = await llm.generate("coordinator", system, f"Meeting so far:\n{lines}\n\n{task}")
        return text or COORD_MOCK[key].format(**fill)
    except Exception:  # noqa: BLE001
        return COORD_MOCK[key].format(**fill)


async def _twin_say(team: dict, member: dict, round_no: int, draft: dict, transcript: list[dict]) -> str:
    if llm.is_mock():
        return twin.mock_turn(member, round_no, draft)
    try:
        text = await llm.generate(f"twin_{member['uid']}", twin.twin_system(member, team),
                                  twin.round_prompt(round_no, transcript, draft, member))
        return text or twin.mock_turn(member, round_no, draft)
    except Exception:  # noqa: BLE001
        return twin.mock_turn(member, round_no, draft)


async def negotiate(team: dict, members: list[dict]) -> AsyncIterator[dict]:
    """Yields room messages one by one, then {"type": "charter"}."""
    draft = draft_charter(team, members)
    transcript: list[dict] = []

    def msg(speaker: str, name: str, text: str, round_no: int) -> dict:
        m = {"type": "message", "speaker": speaker, "name": name, "text": text, "round": round_no}
        transcript.append(m)
        return m

    yield msg("coordinator", "Coordinator", await _coord_say(team, members, "open", draft, transcript), 1)
    for m in members:
        yield msg(f"twin:{m['uid']}", f"{twin.first_name(m)}'s twin", await _twin_say(team, m, 1, draft, transcript), 1)
    yield msg("coordinator", "Coordinator", await _coord_say(team, members, "draft", draft, transcript), 2)
    for m in members:
        yield msg(f"twin:{m['uid']}", f"{twin.first_name(m)}'s twin", await _twin_say(team, m, 2, draft, transcript), 2)
    yield msg("coordinator", "Coordinator", await _coord_say(team, members, "last", draft, transcript), 3)
    for m in members:
        yield msg(f"twin:{m['uid']}", f"{twin.first_name(m)}'s twin", await _twin_say(team, m, 3, draft, transcript), 3)

    charter = draft
    if not llm.is_mock():
        system = COORDINATOR_SYSTEM.format(brief=team.get("brief") or team["name"], deadline=team["deadline"],
                                           names=", ".join(twin.first_name(m) for m in members))
        lines = "\n".join(f"{m['name']}: {m['text']}" for m in transcript)
        prompt = f"Transcript:\n{lines}\n\nDraft charter:\n{json.dumps(draft)}\n\n{CHARTER_INSTRUCTIONS}"
        try:
            charter = normalize_charter(llm.parse_json(await llm.generate("coordinator", system, prompt, want_json=True)),
                                        draft, members)
        except Exception:  # noqa: BLE001
            charter = draft
    yield msg("coordinator", "Coordinator", await _coord_say(team, members, "close", charter, transcript), 3)
    yield {"type": "charter", "charter": {**charter, "acceptedBy": []}}


# ---------------------------------------------------------------- weekly retro
def _role_of(charter: dict | None, uid: str) -> str:
    if not charter:
        return "your part"
    roles = [r["role"] for r in charter.get("roles", []) if r["uid"] == uid]
    return twin._join(roles) if roles else "your part"


def _deadline_of(charter: dict | None, uid: str) -> str | None:
    if not charter:
        return None
    return next((d["date"] for d in charter.get("internalDeadlines", []) if d["uid"] == uid), None)


def mock_retro(stats: dict, charter: dict | None, members: list[dict]) -> dict:
    meeting = (f"{SLOT_LABEL[charter['meetings'][0]['slot']]} check-in"
               if charter and charter.get("meetings") else "next check-in")
    channel = next((n.split(": ")[1].rstrip(".") for n in (charter or {}).get("norms", []) if n.startswith("Main channel")), "the group chat")
    nudges = {}
    for m in members:
        s = stats["members"][m["uid"]]
        role, dl = _role_of(charter, m["uid"]), _deadline_of(charter, m["uid"])
        dl = twin.fmt_date(dl) if dl else None
        missed = stats["meetingsHeld"] and s["meetings"] == 0
        if s["events"] == 0 or (s["events"] <= 3 and missed) or s["share"] < 0.06:
            t = f"Quiet week, totally fine if it was planned. One small push on {role} this weekend keeps you ahead"
            t += f" of your {dl} internal deadline." if dl else "."
        elif s["share"] > 0.45:
            t = (f"You carried {round(s['share'] * 100)}% of this week. Brilliant, but hand one small {role} task "
                 f"to a teammate so you don't burn out.")
        elif s["events"] >= 5 and s["nightEvents"] / s["events"] > 0.6:
            t = (f"Strong week: {s['events']} contributions, mostly after 10 PM. {role} is moving; "
                 f"just protect your sleep before the {meeting}.")
        else:
            t = f"Solid week: {s['events']} contributions over {s['activeDays']} days. Next step: one clear milestone on {role}"
            t += f" before {dl}." if dl else "."
        if missed:
            t += f" You missed this week's check-in; a 2-line update in {channel} keeps everyone in sync."
        nudges[m["uid"]] = t
    shares = [stats["members"][m["uid"]]["share"] for m in members]
    if shares and max(shares) > 2 * min(shares) + 0.1:
        team_s = (f"Work was uneven this week: one person did {round(max(shares) * 100)}% of it. "
                  f"At the {meeting}, move one task to whoever has more room next week.")
    else:
        team_s = f"Nicely balanced week. Keep the {meeting} short and confirm next week's tasks in {channel}."
    return {"nudges": nudges, "teamSuggestion": team_s}


async def retro(team: dict, members: list[dict], activity: list[dict], charter: dict | None, week: int) -> dict:
    stats = metrics.weekly_stats(team, members, activity, week)
    base = mock_retro(stats, charter, members)
    result = {"week": week, "from": stats["from"], "to": stats["to"], "stats": stats["members"], **base}
    if llm.is_mock():
        return result
    slim_charter = {k: (charter or {}).get(k) for k in ("roles", "meetings", "internalDeadlines", "norms")}
    prompt = RETRO_INSTRUCTIONS.format(week=week, stats=json.dumps(stats["members"]), charter=json.dumps(slim_charter),
                                       team_facts=json.dumps({"meetingsHeld": stats["meetingsHeld"]}))
    try:
        data = llm.parse_json(await llm.generate("coordinator_retro", RETRO_SYSTEM, prompt, want_json=True)) or {}
        nudges = data.get("nudges") or {}
        result["nudges"] = {m["uid"]: str(nudges.get(m["uid"]) or base["nudges"][m["uid"]]) for m in members}
        if isinstance(data.get("teamSuggestion"), str) and data["teamSuggestion"].strip():
            result["teamSuggestion"] = data["teamSuggestion"].strip()
    except Exception:  # noqa: BLE001
        pass
    return result
