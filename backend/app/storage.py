"""Storage: Firestore in the cloud, JSON files locally. Same interface for both.

Layout (Firestore):
  teams/{teamId}                      team document
  teams/{teamId}/members/{uid}        member + quiz + profile
  teams/{teamId}/activity/{id}        one row per commit / PR / review / doc edit / meeting / task
  teams/{teamId}/room/{seq}           twin-room messages
  teams/{teamId}/state/{name}         charter, retro-<week>, wrapped, misc
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any

from . import config


class LocalStore:
    def __init__(self, data_dir: str):
        self.dir = os.path.abspath(data_dir)
        os.makedirs(self.dir, exist_ok=True)
        self._lock = threading.RLock()
        self._cache: dict[str, dict] = {}

    # --- internal -----------------------------------------------------------
    def _path(self, team_id: str) -> str:
        safe = "".join(c for c in team_id if c.isalnum() or c in "-_")
        return os.path.join(self.dir, f"{safe}.json")

    def _load(self, team_id: str) -> dict | None:
        if team_id in self._cache:
            return self._cache[team_id]
        p = self._path(team_id)
        if not os.path.exists(p):
            return None
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        self._cache[team_id] = data
        return data

    def _save(self, team_id: str, data: dict) -> None:
        self._cache[team_id] = data
        tmp = self._path(team_id) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self._path(team_id))

    def _bundle(self, team_id: str) -> dict:
        data = self._load(team_id)
        if data is None:
            raise KeyError(team_id)
        return data

    # --- teams --------------------------------------------------------------
    def get_team(self, team_id: str) -> dict | None:
        with self._lock:
            data = self._load(team_id)
            return dict(data["team"]) if data else None

    def save_team(self, team: dict) -> None:
        with self._lock:
            data = self._load(team["id"]) or {"team": {}, "members": {}, "activity": {}, "room": [], "state": {}}
            data["team"] = team
            self._save(team["id"], data)

    def delete_team(self, team_id: str) -> None:
        with self._lock:
            self._cache.pop(team_id, None)
            p = self._path(team_id)
            if os.path.exists(p):
                os.remove(p)

    # --- members ------------------------------------------------------------
    def list_members(self, team_id: str) -> list[dict]:
        with self._lock:
            return [dict(m) for m in self._bundle(team_id)["members"].values()]

    def get_member(self, team_id: str, uid: str) -> dict | None:
        with self._lock:
            m = self._bundle(team_id)["members"].get(uid)
            return dict(m) if m else None

    def save_member(self, team_id: str, member: dict) -> None:
        with self._lock:
            data = self._bundle(team_id)
            data["members"][member["uid"]] = member
            self._save(team_id, data)

    def delete_member(self, team_id: str, uid: str) -> None:
        with self._lock:
            data = self._bundle(team_id)
            data["members"].pop(uid, None)
            data["activity"] = {k: v for k, v in data["activity"].items() if v.get("uid") != uid}
            self._save(team_id, data)

    # --- activity -----------------------------------------------------------
    def add_activity(self, team_id: str, rows: list[dict]) -> None:
        with self._lock:
            data = self._bundle(team_id)
            for r in rows:
                data["activity"][r["id"]] = r
            self._save(team_id, data)

    def list_activity(self, team_id: str) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._bundle(team_id)["activity"].values()]

    def clear_activity(self, team_id: str, source: str | None = None) -> None:
        with self._lock:
            data = self._bundle(team_id)
            if source is None:
                data["activity"] = {}
            else:
                data["activity"] = {k: v for k, v in data["activity"].items() if v.get("source") != source}
            self._save(team_id, data)

    # --- twin room ----------------------------------------------------------
    def append_room(self, team_id: str, msg: dict) -> None:
        with self._lock:
            data = self._bundle(team_id)
            msg = {**msg, "seq": len(data["room"])}
            data["room"].append(msg)
            self._save(team_id, data)

    def list_room(self, team_id: str) -> list[dict]:
        with self._lock:
            return [dict(m) for m in self._bundle(team_id)["room"]]

    def clear_room(self, team_id: str) -> None:
        with self._lock:
            data = self._bundle(team_id)
            data["room"] = []
            self._save(team_id, data)

    # --- state docs (charter, retros, wrapped) --------------------------------
    def get_state(self, team_id: str, name: str) -> dict | None:
        with self._lock:
            v = self._bundle(team_id)["state"].get(name)
            return json.loads(json.dumps(v)) if v is not None else None

    def save_state(self, team_id: str, name: str, value: dict) -> None:
        with self._lock:
            data = self._bundle(team_id)
            data["state"][name] = value
            self._save(team_id, data)

    def delete_state(self, team_id: str, name: str) -> None:
        with self._lock:
            data = self._bundle(team_id)
            data["state"].pop(name, None)
            self._save(team_id, data)


class FirestoreStore:
    def __init__(self):
        from google.cloud import firestore  # imported lazily so local dev needs no GCP

        self.db = firestore.Client()

    def _team(self, team_id: str):
        return self.db.collection("teams").document(team_id)

    def get_team(self, team_id: str) -> dict | None:
        snap = self._team(team_id).get()
        return snap.to_dict() if snap.exists else None

    def save_team(self, team: dict) -> None:
        self._team(team["id"]).set(team)

    def delete_team(self, team_id: str) -> None:
        ref = self._team(team_id)
        for sub in ("members", "activity", "room", "state"):
            self._delete_collection(ref.collection(sub))
        ref.delete()

    def _delete_collection(self, coll, where=None) -> None:
        query = coll if where is None else coll.where(*where)
        while True:
            docs = list(query.limit(400).stream())
            if not docs:
                return
            batch = self.db.batch()
            for d in docs:
                batch.delete(d.reference)
            batch.commit()

    def list_members(self, team_id: str) -> list[dict]:
        return [d.to_dict() for d in self._team(team_id).collection("members").stream()]

    def get_member(self, team_id: str, uid: str) -> dict | None:
        snap = self._team(team_id).collection("members").document(uid).get()
        return snap.to_dict() if snap.exists else None

    def save_member(self, team_id: str, member: dict) -> None:
        self._team(team_id).collection("members").document(member["uid"]).set(member)

    def delete_member(self, team_id: str, uid: str) -> None:
        self._delete_collection(self._team(team_id).collection("activity"), ("uid", "==", uid))
        self._team(team_id).collection("members").document(uid).delete()

    def add_activity(self, team_id: str, rows: list[dict]) -> None:
        coll = self._team(team_id).collection("activity")
        for i in range(0, len(rows), 400):
            batch = self.db.batch()
            for r in rows[i : i + 400]:
                batch.set(coll.document(r["id"]), r)
            batch.commit()

    def list_activity(self, team_id: str) -> list[dict]:
        return [d.to_dict() for d in self._team(team_id).collection("activity").stream()]

    def clear_activity(self, team_id: str, source: str | None = None) -> None:
        coll = self._team(team_id).collection("activity")
        self._delete_collection(coll, None if source is None else ("source", "==", source))

    def append_room(self, team_id: str, msg: dict) -> None:
        coll = self._team(team_id).collection("room")
        seq = len(list(coll.select([]).stream()))
        coll.document(f"{seq:05d}").set({**msg, "seq": seq})

    def list_room(self, team_id: str) -> list[dict]:
        coll = self._team(team_id).collection("room")
        return [d.to_dict() for d in coll.order_by("seq").stream()]

    def clear_room(self, team_id: str) -> None:
        self._delete_collection(self._team(team_id).collection("room"))

    def get_state(self, team_id: str, name: str) -> dict | None:
        snap = self._team(team_id).collection("state").document(name).get()
        return snap.to_dict() if snap.exists else None

    def save_state(self, team_id: str, name: str, value: dict) -> None:
        self._team(team_id).collection("state").document(name).set(value)

    def delete_state(self, team_id: str, name: str) -> None:
        self._team(team_id).collection("state").document(name).delete()


_store = None


def get_store():
    global _store
    if _store is None:
        _store = FirestoreStore() if config.STORE == "firestore" else LocalStore(config.DATA_DIR)
    return _store
