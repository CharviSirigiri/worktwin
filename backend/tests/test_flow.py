"""End-to-end test of the demo flow in mock mode (no Gemini, local JSON store)."""
import json
import os
import tempfile

os.environ["MOCK_LLM"] = "true"
os.environ["STORE"] = "local"
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["TAPIN_DEVICE_TOKEN"] = "test-token"
os.environ["GEMINI_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app import metrics, seed  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def _seed_and_build():
    team_id = client.post("/demo/seed").json()["teamId"]
    r = client.post(f"/teams/{team_id}/twins/build")
    assert r.status_code == 200, r.text
    return team_id


def test_health_and_quiz():
    h = client.get("/health").json()
    assert h["mock"] is True
    q = client.get("/quiz").json()["questions"]
    assert {x["id"] for x in q} >= {"best_time", "rhythm", "availability", "frustration"}


def test_profiles_reflect_patterns():
    team_id = _seed_and_build()
    members = {m["uid"]: m for m in client.get(f"/teams/{team_id}").json()["members"]}
    assert members["aisha"]["profile"]["bestTime"] == "night"
    assert members["aisha"]["profile"]["rhythm"] == "sprinter"
    assert members["weijie"]["profile"]["bestTime"] == "day"
    # private answers never leave the backend
    assert "frustration" not in members["aisha"]["quiz"]
    assert "commitments" not in members["aisha"]["quiz"]


def test_room_streams_and_saves_charter():
    team_id = _seed_and_build()
    r = client.post(f"/teams/{team_id}/room/start")
    assert r.status_code == 200
    items = [json.loads(line) for line in r.text.strip().splitlines()]
    assert items[-1]["type"] == "done"
    msgs = [i for i in items if i["type"] == "message"]
    assert len(msgs) == 3 * 4 + 4  # 3 rounds x 4 twins + 4 coordinator lines
    charter = next(i for i in items if i["type"] == "charter")["charter"]
    assert {r["uid"] for r in charter["roles"]} == {"aisha", "weijie", "priya", "daniel"}
    assert charter["meetings"][0]["slot"] == "Wed-EVE"
    dl = {d["uid"]: d["date"] for d in charter["internalDeadlines"]}
    assert dl["aisha"] < dl["weijie"]  # sprinter gets the earlier internal deadline
    # private note is never spoken in the room
    assert not any("changing the plan" in m["text"] for m in msgs)
    saved = client.get(f"/teams/{team_id}/room").json()
    assert len(saved["messages"]) == len(msgs) and saved["charter"]
    acc = client.post(f"/teams/{team_id}/charter/accept", json={"uid": "aisha"}).json()
    assert acc["charter"]["acceptedBy"] == ["aisha"]


def test_retro_week3_flags_quiet_member():
    team_id = _seed_and_build()
    client.post(f"/teams/{team_id}/room/start")
    r = client.post(f"/teams/{team_id}/retro?week=3").json()
    assert set(r["nudges"]) == {"aisha", "weijie", "priya", "daniel"}
    assert "missed" in r["nudges"]["aisha"]
    assert r["teamSuggestion"]
    assert client.get(f"/teams/{team_id}/retro?week=3").status_code == 200


def test_wrapped_archetypes_and_real_numbers():
    team_id = _seed_and_build()
    w = client.get(f"/teams/{team_id}/wrapped?refresh=true").json()
    arch = w["archetypes"]
    assert len(set(arch.values())) == 4  # everyone gets a different, positive archetype
    assert arch["aisha"] in ("night_owl", "closer")
    ids = [s["id"] for s in w["slides"]]
    assert ids[0] == "intro" and ids[-1] == "outro" and "mix" in ids
    total = next(s for s in w["slides"] if s["id"] == "team-total")
    assert int(total["big"]) == len(seed.build_activity())
    late = next(s for s in w["slides"] if s["id"] == "latest-night")
    assert late["big"] == "3:12 AM"
    assert set(w["reflections"]) == set(arch)


def test_hourly_cap_blunts_spam():
    rows = [{"id": str(i), "uid": "x", "type": "commit", "ts": "2026-10-06T10:05:00+08:00", "weight": 1.0}
            for i in range(50)]
    total = sum(w for *_, w in metrics.capped(rows))
    assert abs(total - metrics.HOURLY_CAP) < 1e-6


def test_create_join_quiz_and_tapin():
    t = client.post("/teams", json={"name": "Test Crew", "deadline": "2026-12-20", "startDate": "2026-11-01"}).json()["team"]
    tid = t["id"]
    a = client.post(f"/teams/{tid}/join", json={"name": "Mei", "email": "mei@x.com"}).json()["member"]
    b = client.post(f"/teams/{tid}/join", json={"name": "Raj"}).json()["member"]
    quiz = {"best_time": "night", "rhythm": "steady", "enjoy": ["coding", "design", "writing"],
            "availability": ["Wed-EVE", "BAD-SLOT"], "frustration": "secret", "junk": 1}
    m = client.post(f"/teams/{tid}/members/{a['uid']}/quiz", json={"answers": quiz}).json()["member"]
    assert m["quiz"]["enjoy"] == ["coding", "design"] and m["quiz"]["availability"] == ["Wed-EVE"]
    client.post(f"/teams/{tid}/members/{b['uid']}/quiz", json={"answers": {"best_time": "day", "availability": ["Wed-EVE"]}})
    assert client.post(f"/teams/{tid}/twins/build").status_code == 200
    assert client.post(f"/teams/{tid}/room/start").status_code == 200
    # IoT tap-in
    bad = client.post("/tapin", json={"team": tid, "card": "AA BB", "token": "nope"})
    assert bad.status_code == 401
    unknown = client.post("/tapin", json={"team": tid, "card": "04A1B2C3", "token": "test-token"}).json()
    assert unknown["known"] is False
    assert client.get(f"/teams/{tid}").json()["lastUnknownCard"] == "04A1B2C3"
    client.post(f"/teams/{tid}/members/{a['uid']}/card", json={"card": "04a1b2c3"})
    ok = client.post("/tapin", json={"team": tid, "card": "04A1B2C3", "token": "test-token"}).json()
    assert ok["known"] and ok["name"] == "Mei"
    # ingest with no repo/folder is a no-op, not an error
    ing = client.post(f"/teams/{tid}/ingest").json()
    assert ing["errors"] == [] and ing["github"] == 0


def test_consent_off_and_delete_member():
    team_id = _seed_and_build()
    before = [r for r in client.get(f"/teams/{team_id}/stats").json()["members"]["aisha"]["byType"].items()]
    assert dict(before).get("commit")
    r = client.patch(f"/teams/{team_id}/members/aisha/consent", json={"github": False, "drive": True})
    assert r.status_code == 200
    bt = client.get(f"/teams/{team_id}/stats").json()["members"]["aisha"]["byType"]
    assert "commit" not in bt and "pr" not in bt and bt.get("meeting")  # tap-ins are not GitHub data
    assert client.delete(f"/teams/{team_id}/members/priya").status_code == 200
    uids = {m["uid"] for m in client.get(f"/teams/{team_id}").json()["members"]}
    assert "priya" not in uids
    from app.storage import get_store

    rows = get_store().list_activity(team_id)
    assert rows and not any(r.get("uid") == "priya" for r in rows)
    assert not any(r.get("uid") == "aisha" and r.get("source") == "github" for r in rows)
