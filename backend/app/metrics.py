"""Turns raw activity into work-style features, contribution mix, weekly stats and archetypes.

Activity row: {"id", "uid", "source", "type", "ts" (ISO 8601 with offset), "weight", "meta"}
  type: commit | pr | review | edit | meeting | task
Numbers here are computed in code, never by the LLM, so Wrapped stats are always real.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from . import config

NIGHT_HOURS = {22, 23, 0, 1, 2, 3}
HOURLY_CAP = 4.0  # max weight one member can earn in one hour (blunts commit spamming)
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

ARCHETYPES = {
    "night_owl": {"name": "The Night Owl", "blurb": "Does their best work while the rest of the team sleeps."},
    "closer": {"name": "The Closer", "blurb": "Brings it home in the final stretch."},
    "steady": {"name": "The Steady Builder", "blurb": "Shows up and ships, week after week."},
    "architect": {"name": "The Architect", "blurb": "Built the backbone of the project."},
    "wordsmith": {"name": "The Wordsmith", "blurb": "Turned the work into words people can read."},
    "glue": {"name": "The Glue", "blurb": "Kept everyone talking, reviewed and on track."},
    "wildcard": {"name": "The Wildcard", "blurb": "Showed up where they were needed most."},
}


def parse_ts(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=config.TZ)
    return dt.astimezone(config.TZ)


def parse_date(d: str) -> date:
    return date.fromisoformat(d[:10])


def category(row: dict) -> str:
    t = row.get("type")
    if t in ("commit", "pr"):
        return "code"
    if t == "edit":
        return "writing"
    if t == "task":
        kind = (row.get("meta") or {}).get("kind", "coordination")
        if kind in ("code", "coding"):
            return "code"
        if kind in ("writing", "design", "research"):
            return "writing"
        return "coordination"
    return "coordination"  # review, meeting


def capped(rows: list[dict]) -> list[tuple[dict, datetime, float]]:
    """Attach local time and a weight scaled so no member exceeds HOURLY_CAP in any hour."""
    buckets: dict[tuple, list] = defaultdict(list)
    for r in rows:
        t = parse_ts(r["ts"])
        buckets[(r["uid"], t.date(), t.hour)].append((r, t))
    out = []
    for items in buckets.values():
        total = sum(float(r.get("weight", 1)) for r, _ in items)
        scale = min(1.0, HOURLY_CAP / total) if total else 1.0
        for r, t in items:
            out.append((r, t, float(r.get("weight", 1)) * scale))
    return out


def team_window(team: dict) -> tuple[date, date]:
    return parse_date(team["startDate"]), parse_date(team["deadline"])


def _streak(days: set[date]) -> int:
    best = cur = 0
    prev = None
    for d in sorted(days):
        cur = cur + 1 if prev and (d - prev).days == 1 else 1
        best = max(best, cur)
        prev = d
    return best


def _fmt_time(t: datetime) -> str:
    h = t.hour % 12 or 12
    return f"{h}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"


def member_features(items: list[tuple[dict, datetime, float]], start: date, end: date, today: date) -> dict:
    if not items:
        return {
            "events": 0, "weight": 0.0, "byType": {}, "mix": {"code": 0, "writing": 0, "coordination": 0},
            "peakHour": None, "topHours": [], "nightRatio": 0.0, "sprintIndex": 0.0, "consistency": 0.0,
            "longestStreak": 0, "busiestWeekday": None, "latestNight": None, "activeDays": 0,
        }
    weight = sum(w for *_, w in items)
    by_type = Counter(r["type"] for r, _, _ in items)
    mix_w = Counter()
    for r, _, w in items:
        mix_w[category(r)] += w
    # meetings happen at a fixed slot, so they say nothing about someone's own working hours
    own = [it for it in items if it[0]["type"] != "meeting"] or items
    hours = Counter(t.hour for _, t, _ in own)
    span_days = max(1, (end - start).days)
    sprint_from = start + timedelta(days=span_days * 0.8)
    sprint_w = sum(w for _, t, w in items if t.date() >= sprint_from)
    days = {t.date() for _, t, _ in items}
    last_day = max(min(end, today), max(days))
    elapsed = max(1, (last_day - start).days + 1)
    weekday = Counter(t.weekday() for _, t, _ in own).most_common(1)[0][0]
    late = [t for _, t, _ in own if t.hour in (0, 1, 2, 3, 4)]
    latest = max(late, key=lambda t: (t.hour, t.minute)) if late else None
    return {
        "events": len(items),
        "weight": round(weight, 2),
        "byType": dict(by_type),
        "mix": {k: round(mix_w[k] / weight, 3) for k in ("code", "writing", "coordination")},
        "peakHour": hours.most_common(1)[0][0],
        "topHours": [h for h, _ in hours.most_common(3)],
        "nightRatio": round(sum(1 for _, t, _ in own if t.hour in NIGHT_HOURS) / len(own), 3),
        "sprintIndex": round(sprint_w / weight, 3),
        "consistency": round(min(1.0, len(days) / elapsed), 3),
        "longestStreak": _streak(days),
        "busiestWeekday": WEEKDAYS[weekday],
        "latestNight": _fmt_time(latest) if latest else None,
        "activeDays": len(days),
    }


def compute(team: dict, members: list[dict], activity: list[dict], today: date | None = None) -> dict:
    """Features per member plus team totals and each member's share of the team's weighted work."""
    today = today or datetime.now(config.TZ).date()
    start, end = team_window(team)
    items = capped([r for r in activity if r.get("uid")])
    per: dict[str, list] = defaultdict(list)
    for it in items:
        per[it[0]["uid"]].append(it)
    feats = {m["uid"]: member_features(per.get(m["uid"], []), start, end, today) for m in members}
    team_w = sum(f["weight"] for f in feats.values()) or 1.0
    cat_tot = Counter()
    for f in feats.values():
        for k, v in f["mix"].items():
            cat_tot[k] += v * f["weight"]
    for f in feats.values():
        f["teamShare"] = round(f["weight"] / team_w, 3)
        f["catShare"] = {k: round((f["mix"][k] * f["weight"]) / cat_tot[k], 3) if cat_tot[k] else 0 for k in cat_tot}
    week_w = Counter()
    for _, t, w in items:
        week_w[min(max(1, (t.date() - start).days // 7 + 1), max(1, (end - start).days // 7 + 1))] += w
    all_types = Counter(r["type"] for r, _, _ in items)
    return {
        "members": feats,
        "team": {
            "events": len(items),
            "byType": dict(all_types),
            "busiestWeek": week_w.most_common(1)[0][0] if week_w else None,
            "weeks": max(1, -(-((end - start).days) // 7)),
        },
    }


def archetype_scores(f: dict, n: int) -> dict[str, float]:
    """How strongly a member fits each archetype. Only clear fits count (0 = not eligible)."""
    if not f["events"]:
        return {}
    cs = f.get("catShare", {})
    s = {
        "night_owl": f["nightRatio"] / 0.4 if f["nightRatio"] > 0.4 else 0,
        "closer": f["sprintIndex"] / 0.5 if f["sprintIndex"] > 0.5 else 0,
        "steady": f["consistency"] / 0.6 if f["consistency"] > 0.6 else 0,
    }
    # share-based archetypes need at least half a fair share of that kind of work
    for arch, cat in (("architect", "code"), ("wordsmith", "writing"), ("glue", "coordination")):
        v = cs.get(cat, 0) * n
        s[arch] = v if v >= 0.5 else 0
    return {k: v for k, v in s.items() if v > 0}


def assign_archetypes(feats: dict[str, dict]) -> dict[str, str]:
    """Give every member exactly one distinct, positive archetype, maximising the total fit.

    Small teams (up to 6) are solved exactly by trying every assignment; bigger ones greedily.
    Anyone with no clear fit becomes The Wildcard.
    """
    uids = list(feats)
    n = max(1, len(uids))
    scores = {u: archetype_scores(feats[u], n) for u in uids}
    result: dict[str, str] = {}
    if len(uids) <= 6:
        best = {"total": -1.0, "pick": None}

        def search(i: int, used: frozenset, total: float, pick: tuple):
            if i == len(uids):
                if total > best["total"]:
                    best["total"], best["pick"] = total, pick
                return
            u = uids[i]
            for a, v in scores[u].items():
                if a not in used:
                    search(i + 1, used | {a}, total + v, pick + (a,))
            search(i + 1, used, total, pick + ("wildcard",))

        search(0, frozenset(), 0.0, ())
        result = dict(zip(uids, best["pick"]))
    else:
        used: set[str] = set()
        pairs = sorted(((v, u, a) for u in uids for a, v in scores[u].items()), reverse=True)
        for _, u, a in pairs:
            if u not in result and a not in used:
                result[u], _ = a, used.add(a)
    for u in uids:
        result.setdefault(u, "wildcard")
    return result


def week_bounds(team: dict, week: int) -> tuple[date, date]:
    start, _ = team_window(team)
    ws = start + timedelta(days=7 * (week - 1))
    return ws, ws + timedelta(days=6)


def current_week(team: dict, today: date | None = None) -> int:
    today = today or datetime.now(config.TZ).date()
    start, end = team_window(team)
    weeks = max(1, -(-((end - start).days) // 7))
    return min(max(1, (today - start).days // 7 + 1), weeks)


def weekly_stats(team: dict, members: list[dict], activity: list[dict], week: int) -> dict:
    ws, we = week_bounds(team, week)
    items = [it for it in capped([r for r in activity if r.get("uid")]) if ws <= it[1].date() <= we]
    out = {}
    team_w = sum(w for *_, w in items) or 1.0
    for m in members:
        mine = [it for it in items if it[0]["uid"] == m["uid"]]
        w = sum(x for *_, x in mine)
        out[m["uid"]] = {
            "name": m["name"],
            "events": len(mine),
            "share": round(w / team_w, 3),
            "byType": dict(Counter(r["type"] for r, _, _ in mine)),
            "activeDays": len({t.date() for _, t, _ in mine}),
            "nightEvents": sum(1 for _, t, _ in mine if t.hour in NIGHT_HOURS),
            "meetings": sum(1 for r, _, _ in mine if r["type"] == "meeting"),
        }
    return {"week": week, "from": ws.isoformat(), "to": we.isoformat(), "members": out,
            "meetingsHeld": max((v["meetings"] for v in out.values()), default=0)}
