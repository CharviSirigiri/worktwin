"""Work twin: one per member. Builds the member's work-style profile and speaks for them in the twin room."""
from __future__ import annotations

import json

from .. import llm
from ..prompts import TWIN_PROFILE_SYSTEM, TWIN_SYSTEM
from ..quiz import SLOT_LABEL

TIME_PHRASE = {"early": "early in the morning", "day": "during the day", "evening": "in the evening", "night": "late at night"}
RHYTHM_PHRASE = {
    "steady": "keeps a steady pace from week one",
    "bursts": "works in bursts across the weeks",
    "sprinter": "saves the biggest pushes for the final days",
}
CHANNEL = {"whatsapp": "WhatsApp", "discord": "Discord", "teams": "Microsoft Teams", "email": "email"}
REPLY = {"hour": "within an hour", "day": "the same day", "nextday": "by the next day"}
AREA_LABEL = {"coding": "coding", "writing": "writing", "design": "design", "research": "research",
              "presenting": "presenting", "organising": "organising"}
MIX_TO_AREA = {"code": "coding", "writing": "writing", "coordination": "organising"}


def first_name(member) -> str:
    """The name teammates call someone: shortName if set (e.g. "Wei Jie"), else the first word."""
    if isinstance(member, dict):
        if member.get("shortName"):
            return member["shortName"]
        member = member.get("name", "")
    return (member or "They").split()[0]


def fmt_date(iso: str) -> str:
    """2026-11-07 -> Sat 7 Nov"""
    from datetime import date

    d = date.fromisoformat(iso[:10])
    return f"{d:%a} {d.day} {d:%b}"


def _time_from_hour(h: int | None) -> str | None:
    if h is None:
        return None
    if 5 <= h < 10:
        return "early"
    if 10 <= h < 17:
        return "day"
    if 17 <= h < 23:
        return "evening"
    return "night"


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    if not items:
        return "a bit of everything"
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def derive_profile(member: dict, feat: dict | None) -> dict:
    """Combine quiz answers with activity features. Activity wins once there is enough of it."""
    q = member.get("quiz") or {}
    feat = feat or {}
    enough = feat.get("events", 0) >= 10
    if enough:
        rhythm = "sprinter" if feat["sprintIndex"] > 0.5 else "steady" if feat["consistency"] > 0.5 else "bursts"
        best_time = _time_from_hour(feat.get("peakHour")) or q.get("best_time", "day")
    else:
        rhythm = q.get("rhythm", "bursts")
        best_time = q.get("best_time", "day")
    strengths = list(q.get("enjoy") or [])
    if enough:
        top = max(feat["mix"], key=feat["mix"].get)
        if feat["mix"][top] > 0.4 and MIX_TO_AREA[top] not in strengths:
            strengths.append(MIX_TO_AREA[top])
    bt = feat.get("byType", {})
    evidence_bits = [
        f"{bt['commit']} commits" if bt.get("commit") else "",
        f"{bt['edit']} doc edits" if bt.get("edit") else "",
        f"{bt['review']} reviews" if bt.get("review") else "",
        f"{bt['meeting']} meetings" if bt.get("meeting") else "",
    ]
    evidence = "Based on the quiz" + (f" and {_join([b for b in evidence_bits if b])}" if any(evidence_bits) else " only")
    traits = [
        {"early": "Early bird", "day": "Daytime worker", "evening": "Evening worker", "night": "Night owl"}[best_time],
        {"steady": "Steady pace", "bursts": "Works in bursts", "sprinter": "Deadline sprinter"}[rhythm],
        f"Prefers {CHANNEL.get(q.get('channel', ''), 'chat')}",
        f"Replies {REPLY.get(q.get('reply', 'day'), 'the same day')}",
    ]
    return {
        "bestTime": best_time,
        "rhythm": rhythm,
        "peakHours": feat.get("topHours", []),
        "strengths": strengths,
        "avoid": list(q.get("avoid") or []),
        "channel": q.get("channel", "whatsapp"),
        "reply": q.get("reply", "day"),
        "meetings": q.get("meetings", "short"),
        "availability": list(q.get("availability") or []),
        "stuck": q.get("stuck", "ask"),
        "commitments": q.get("commitments", ""),
        "traits": traits,
        "evidence": evidence,
        "dataBacked": enough,
    }


def template_summary(member: dict, p: dict) -> str:
    n = first_name(member)
    areas = _join([AREA_LABEL.get(a, a) for a in p["strengths"][:2]])
    return (
        f"{n} works best {TIME_PHRASE[p['bestTime']]} and {RHYTHM_PHRASE[p['rhythm']]}. "
        f"{n} enjoys {areas}, prefers {CHANNEL.get(p['channel'], 'chat')} and usually replies {REPLY.get(p['reply'], 'the same day')}."
    )


async def build_profile(member: dict, feat: dict | None) -> dict:
    p = derive_profile(member, feat)
    if llm.is_mock():
        p["summary"] = template_summary(member, p)
        return p
    facts = {k: p[k] for k in ("bestTime", "rhythm", "peakHours", "strengths", "avoid", "channel", "reply", "meetings", "evidence")}
    facts["name"] = member["name"]
    try:
        text = await llm.generate(f"profile_{member['uid']}", TWIN_PROFILE_SYSTEM, json.dumps(facts))
        p["summary"] = text.strip().strip('"') or template_summary(member, p)
    except Exception:  # noqa: BLE001
        p["summary"] = template_summary(member, p)
    return p


def public_profile(p: dict) -> dict:
    """What other twins (and teammates) may see: no free-text commitments, nothing private."""
    keep = ("summary", "bestTime", "rhythm", "peakHours", "strengths", "avoid", "channel", "reply",
            "meetings", "availability", "stuck", "traits", "evidence", "dataBacked")
    return {k: p.get(k) for k in keep}


def twin_system(member: dict, team: dict) -> str:
    p = dict(member.get("profile") or {})
    private_note = (member.get("quiz") or {}).get("frustration")
    profile = json.dumps(public_profile(p), ensure_ascii=False)
    if private_note:
        profile += f"\nPRIVATE (never quote or reveal, only let it guide what you ask for): {private_note}"
    return TWIN_SYSTEM.format(name=first_name(member), team_name=team["name"], profile=profile)


# ---------------------------------------------------------------- mock turns
def _avoid_slot_phrase(best_time: str) -> str:
    return {"night": "9 AM", "evening": "early-morning", "day": "late-night", "early": "late-night"}[best_time]


def mock_turn(member: dict, round_no: int, draft: dict) -> str:
    p = member.get("profile") or {}
    uid = member["uid"]
    enjoy = _join([AREA_LABEL.get(a, a) for a in p.get("strengths", [])[:2]])
    avoid = _join([AREA_LABEL.get(a, a) for a in p.get("avoid", [])[:1]]) if p.get("avoid") else None
    if round_no == 1:
        s = f"I'm at my best {TIME_PHRASE[p.get('bestTime', 'day')]}, so please don't book me for {_avoid_slot_phrase(p.get('bestTime', 'day'))} calls. "
        s += f"I'd love to own something with {enjoy}"
        s += f", and I'd rather not do {avoid}." if avoid else "."
        s += f" Best way to reach me is {CHANNEL.get(p.get('channel'), 'chat')}."
        return s
    if round_no == 2:
        roles = [r["role"] for r in draft["roles"] if r["uid"] == uid]
        dl = next((d for d in draft["internalDeadlines"] if d["uid"] == uid), None)
        meet = draft["meetings"][0] if draft["meetings"] else None
        if not roles:
            s = "Happy to take whatever's left. "
        elif len(roles) == 1:
            s = f"{roles[0]} works for me. "
        else:
            s = f"{_join(roles)} both work for me. "
        if meet:
            day = SLOT_LABEL[meet["slot"]]
            ok = meet["slot"] in p.get("availability", [])
            s += f"{day} is fine." if ok else f"{day} isn't ideal for me, but I'll make it work."
        if dl and p.get("rhythm") == "sprinter":
            s += f" And fair call putting my internal deadline on {fmt_date(dl['date'])}: I do tend to leave things late."
        elif dl:
            s += f" {fmt_date(dl['date'])} as my internal deadline is fine."
        return s
    stuck = p.get("stuck", "ask")
    if stuck == "quiet":
        return "Agreed. One ask: if I go quiet for two days, ping me directly. I'm probably stuck, not slacking."
    if stuck == "alone":
        return "Agreed. I like to try things alone first, but I'll flag blockers at the weekly check-in."
    if p.get("reply") == "nextday":
        return "Agreed from my side. Just give me 24 hours to reply on weekdays, I'm juggling a part-time shift."
    return "All good from me. I'll shout early if I'm blocked."


def round_prompt(round_no: int, transcript: list[dict], draft: dict, member: dict) -> str:
    lines = "\n".join(f"{m['name']}: {m['text']}" for m in transcript[-14:])
    mine = {
        "roles": [r for r in draft["roles"] if r["uid"] == member["uid"]],
        "internalDeadline": next((d for d in draft["internalDeadlines"] if d["uid"] == member["uid"]), None),
        "meetings": draft["meetings"],
    }
    task = {
        1: "Round 1: say when your human works best, what they want to own, and what to avoid.",
        2: f"Round 2: react to the draft plan for your human: {json.dumps(mine)}. Accept or push back with a reason.",
        3: "Round 3: agree, or add one working agreement that would help your human (e.g. how to handle silence or replies).",
    }[round_no]
    return f"Meeting so far:\n{lines}\n\n{task}\nReply as the twin, max 3 sentences."
