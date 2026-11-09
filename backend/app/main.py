"""WorkTwin API (FastAPI). Run locally: uvicorn app.main:app --reload --port 8080"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import config, llm, metrics, quiz, seed
from .agents import coordinator, narrator, twin
from .ingest import github, google_drive
from .storage import get_store

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("worktwin")

app = FastAPI(title="WorkTwin API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- request bodies
class TeamIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    module: str = ""
    brief: str = ""
    startDate: str | None = None
    deadline: str
    repo: str = ""
    driveFolderId: str = ""
    workstreams: list[str] = []


class TeamPatch(BaseModel):
    name: str | None = None
    module: str | None = None
    brief: str | None = None
    startDate: str | None = None
    deadline: str | None = None
    repo: str | None = None
    driveFolderId: str | None = None
    workstreams: list[str] | None = None


class Consent(BaseModel):
    github: bool = True
    drive: bool = True


class JoinIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    shortName: str = Field("", max_length=30)  # what teammates call you, e.g. "Wei Jie"
    email: str = ""
    githubLogin: str = ""
    consent: Consent = Consent()


class QuizIn(BaseModel):
    answers: dict


class CardIn(BaseModel):
    card: str


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    kind: str = "coordination"  # code | writing | design | research | coordination


class AcceptIn(BaseModel):
    uid: str


class TapIn(BaseModel):
    team: str
    card: str
    token: str


# ---------------------------------------------------------------- helpers
def store():
    return get_store()


def need_team(team_id: str) -> dict:
    t = store().get_team(team_id)
    if not t:
        raise HTTPException(404, "Team not found")
    return t


def need_member(team_id: str, uid: str) -> dict:
    m = store().get_member(team_id, uid)
    if not m:
        raise HTTPException(404, "Member not found")
    return m


def _check_date(v: str, field: str) -> str:
    try:
        return date.fromisoformat(v[:10]).isoformat()
    except ValueError:
        raise HTTPException(422, f"{field} must be YYYY-MM-DD")


def public_member(m: dict) -> dict:
    """Never expose private quiz answers or the free-text commitments to teammates."""
    q = {k: v for k, v in (m.get("quiz") or {}).items() if k not in quiz.PRIVATE_KEYS and k != "commitments"}
    return {
        "uid": m["uid"], "name": m["name"], "shortName": twin.first_name(m), "githubLogin": m.get("githubLogin", ""),
        "hasEmail": bool(m.get("email")), "consent": m.get("consent", {}),
        "quizDone": bool(m.get("quiz")), "quiz": q,
        "profile": twin.public_profile(m["profile"]) if m.get("profile") else None,
        "nfcCard": bool(m.get("nfcCard")),
    }


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24] or "team"
    return f"{s}-{llm.new_id()[:5]}"


# ---------------------------------------------------------------- basics
@app.get("/health")
def health():
    return {"ok": True, "mock": llm.is_mock(), "runtime": "mock" if llm.is_mock() else config.AGENT_RUNTIME,
            "model": config.GEMINI_MODEL, "store": config.STORE}


@app.get("/quiz")
def get_quiz():
    return {"questions": quiz.QUESTIONS}


@app.post("/demo/seed")
def demo_seed():
    return {"teamId": seed.seed(store())}


# ---------------------------------------------------------------- teams and members
@app.post("/teams")
def create_team(body: TeamIn):
    team = body.model_dump()
    team["deadline"] = _check_date(body.deadline, "deadline")
    team["startDate"] = _check_date(body.startDate, "startDate") if body.startDate else date.today().isoformat()
    if team["startDate"] >= team["deadline"]:
        raise HTTPException(422, "deadline must be after startDate")
    team["workstreams"] = [w.strip() for w in body.workstreams if w.strip()] or coordinator.DEFAULT_WORKSTREAMS
    team["id"] = _slug(body.name)
    team["createdAt"] = datetime.now(config.TZ).isoformat()
    store().save_team(team)
    return {"team": team}


@app.get("/teams/{team_id}")
def get_team(team_id: str):
    team = need_team(team_id)
    members = store().list_members(team_id)
    charter = store().get_state(team_id, "charter")
    return {
        "team": team,
        "members": [public_member(m) for m in members],
        "charter": charter,
        "activityCount": len(store().list_activity(team_id)),
        "currentWeek": metrics.current_week(team),
        "lastUnknownCard": (store().get_state(team_id, "misc") or {}).get("lastUnknownCard"),
    }


@app.patch("/teams/{team_id}")
def patch_team(team_id: str, body: TeamPatch):
    team = need_team(team_id)
    for k, v in body.model_dump(exclude_none=True).items():
        team[k] = _check_date(v, k) if k in ("startDate", "deadline") else v
    store().save_team(team)
    return {"team": team}


@app.post("/teams/{team_id}/join")
def join(team_id: str, body: JoinIn):
    need_team(team_id)
    uid = re.sub(r"[^a-z0-9]", "", body.name.lower())[:12] or "member"
    existing = {m["uid"] for m in store().list_members(team_id)}
    if uid in existing:
        uid = f"{uid}{llm.new_id()[:3]}"
    member = {"uid": uid, "name": body.name.strip(), "shortName": body.shortName.strip(), "email": body.email.strip().lower(),
              "githubLogin": body.githubLogin.strip().lstrip("@"), "consent": body.consent.model_dump(),
              "quiz": None, "profile": None, "nfcCard": ""}
    store().save_member(team_id, member)
    return {"member": public_member(member)}


@app.post("/teams/{team_id}/members/{uid}/quiz")
def submit_quiz(team_id: str, uid: str, body: QuizIn):
    member = need_member(team_id, uid)
    valid = {q["id"]: q for q in quiz.QUESTIONS}
    clean = {}
    for k, v in body.answers.items():
        q = valid.get(k)
        if not q:
            continue
        allowed = {o["value"] for o in q.get("options", [])}
        if q["type"] == "single" and v in allowed:
            clean[k] = v
        elif q["type"] in ("multi", "slots") and isinstance(v, list):
            vals = [x for x in v if x in allowed]
            clean[k] = vals[: q.get("max", len(vals))]
        elif q["type"] == "text" and isinstance(v, str):
            clean[k] = v.strip()[:300]
    member["quiz"] = clean
    store().save_member(team_id, member)
    return {"member": public_member(member)}


@app.patch("/teams/{team_id}/members/{uid}/consent")
def update_consent(team_id: str, uid: str, body: Consent):
    """Turning a source off also deletes the activity already pulled from it for this member."""
    member = need_member(team_id, uid)
    member["consent"] = body.model_dump()
    store().save_member(team_id, member)
    for source, allowed in member["consent"].items():
        if not allowed:
            rows = [r for r in store().list_activity(team_id) if r.get("uid") == uid and r.get("source") == source]
            if rows:
                keep = [r for r in store().list_activity(team_id) if r not in rows]
                store().clear_activity(team_id)
                store().add_activity(team_id, keep)
    return {"member": public_member(member)}


@app.delete("/teams/{team_id}/members/{uid}")
def delete_member(team_id: str, uid: str):
    """Right to be forgotten: removes the member, their quiz, profile and all their activity."""
    need_member(team_id, uid)
    store().delete_member(team_id, uid)
    store().delete_state(team_id, "wrapped")
    return {"ok": True}


@app.post("/teams/{team_id}/members/{uid}/card")
def set_card(team_id: str, uid: str, body: CardIn):
    member = need_member(team_id, uid)
    member["nfcCard"] = body.card.strip().upper()
    store().save_member(team_id, member)
    misc = store().get_state(team_id, "misc") or {}
    if misc.get("lastUnknownCard") == member["nfcCard"]:
        misc["lastUnknownCard"] = None
        store().save_state(team_id, "misc", misc)
    return {"ok": True}


@app.post("/teams/{team_id}/members/{uid}/tasks")
def log_task(team_id: str, uid: str, body: TaskIn):
    need_member(team_id, uid)
    row = {"id": f"task-{llm.new_id()}", "uid": uid, "source": "task", "type": "task",
           "ts": datetime.now(config.TZ).isoformat(), "weight": 1.0, "meta": {"kind": body.kind, "title": body.title}}
    store().add_activity(team_id, [row])
    return {"activity": row}


# ---------------------------------------------------------------- data
@app.post("/teams/{team_id}/ingest")
async def ingest(team_id: str):
    team = need_team(team_id)
    members = store().list_members(team_id)
    result = {"github": 0, "drive": 0, "errors": []}
    for name, fn in (("github", github.ingest), ("drive", google_drive.ingest)):
        try:
            rows = await fn(team, members)
            if rows:
                store().clear_activity(team_id, source=name)
                store().add_activity(team_id, rows)
            result[name] = len(rows)
        except Exception as e:  # noqa: BLE001 - report, don't crash the demo
            log.exception("ingest %s failed", name)
            result["errors"].append(f"{name}: {e}")
    result["total"] = len(store().list_activity(team_id))
    return result


@app.get("/teams/{team_id}/stats")
def stats(team_id: str):
    team = need_team(team_id)
    members = store().list_members(team_id)
    return metrics.compute(team, members, store().list_activity(team_id))


# ---------------------------------------------------------------- twins
@app.post("/teams/{team_id}/twins/build")
async def build_twins(team_id: str):
    team = need_team(team_id)
    members = store().list_members(team_id)
    if not members:
        raise HTTPException(400, "No members yet")
    feats = metrics.compute(team, members, store().list_activity(team_id))["members"]
    out = []
    for m in members:
        m["profile"] = await twin.build_profile(m, feats.get(m["uid"]))
        store().save_member(team_id, m)
        out.append(public_member(m))
    return {"members": out}


@app.get("/teams/{team_id}/room")
def get_room(team_id: str):
    need_team(team_id)
    return {"messages": store().list_room(team_id), "charter": store().get_state(team_id, "charter")}


@app.post("/teams/{team_id}/room/start")
async def start_room(team_id: str):
    """Streams the twins' meeting as newline-delimited JSON, saving each message as it goes."""
    team = need_team(team_id)
    members = store().list_members(team_id)
    if len(members) < 2:
        raise HTTPException(400, "Need at least 2 members")
    if any(not m.get("profile") for m in members):
        raise HTTPException(400, "Build the twins first")
    store().clear_room(team_id)

    async def gen():
        try:
            async for item in coordinator.negotiate(team, members):
                if item["type"] == "message":
                    store().append_room(team_id, item)
                elif item["type"] == "charter":
                    store().save_state(team_id, "charter", item["charter"])
                yield json.dumps(item, ensure_ascii=False) + "\n"
            yield json.dumps({"type": "done"}) + "\n"
        except Exception as e:  # noqa: BLE001
            log.exception("negotiation failed")
            yield json.dumps({"type": "error", "error": str(e)}) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/teams/{team_id}/charter")
def get_charter(team_id: str):
    need_team(team_id)
    return {"charter": store().get_state(team_id, "charter")}


@app.post("/teams/{team_id}/charter/accept")
def accept_charter(team_id: str, body: AcceptIn):
    need_member(team_id, body.uid)
    charter = store().get_state(team_id, "charter")
    if not charter:
        raise HTTPException(400, "No charter yet")
    accepted = set(charter.get("acceptedBy", []))
    accepted.add(body.uid)
    charter["acceptedBy"] = sorted(accepted)
    store().save_state(team_id, "charter", charter)
    return {"charter": charter}


# ---------------------------------------------------------------- retro and wrapped
@app.post("/teams/{team_id}/retro")
async def run_retro(team_id: str, week: int | None = Query(None, ge=1, le=52)):
    team = need_team(team_id)
    members = store().list_members(team_id)
    week = week or metrics.current_week(team)
    result = await coordinator.retro(team, members, store().list_activity(team_id),
                                     store().get_state(team_id, "charter"), week)
    result["createdAt"] = datetime.now(config.TZ).isoformat()
    store().save_state(team_id, f"retro-{week}", result)
    return result


@app.get("/teams/{team_id}/retro")
def get_retro(team_id: str, week: int = Query(..., ge=1, le=52)):
    need_team(team_id)
    r = store().get_state(team_id, f"retro-{week}")
    if not r:
        raise HTTPException(404, "No retro for that week yet")
    return r


@app.get("/teams/{team_id}/wrapped")
async def get_wrapped(team_id: str, refresh: bool = False):
    team = need_team(team_id)
    cached = None if refresh else store().get_state(team_id, "wrapped")
    if cached:
        return cached
    members = store().list_members(team_id)
    if not members:
        raise HTTPException(400, "No members yet")
    result = await narrator.wrapped(team, members, store().list_activity(team_id))
    result.pop("stats", None)
    store().save_state(team_id, "wrapped", result)
    return result


# ---------------------------------------------------------------- IoT
@app.post("/tapin")
def tapin(body: TapIn):
    """Called by the ESP32 NFC reader at team meetings."""
    if not config.TAPIN_DEVICE_TOKEN or body.token != config.TAPIN_DEVICE_TOKEN:
        raise HTTPException(401, "Bad device token")
    need_team(body.team)
    card = body.card.strip().upper()
    member = next((m for m in store().list_members(body.team) if (m.get("nfcCard") or "").upper() == card), None)
    if not member:
        misc = store().get_state(body.team, "misc") or {}
        misc["lastUnknownCard"] = card
        store().save_state(body.team, "misc", misc)
        return {"ok": False, "known": False, "message": "Unknown card. Assign it in the app."}
    now = datetime.now(config.TZ)
    row = {"id": f"tap-{member['uid']}-{now:%Y%m%d%H}", "uid": member["uid"], "source": "tapin",
           "type": "meeting", "ts": now.isoformat(), "weight": 1.0, "meta": {}}
    store().add_activity(body.team, [row])  # one per member per hour, re-taps are ignored
    return {"ok": True, "known": True, "name": twin.first_name(member)}
