"""Pulls document edit history from the team's shared Google Drive folder.

Prototype approach: share the team folder (view access) with the backend's service account,
then read each file's revision list (who saved a version, and when). The final version can
switch to the Drive Activity API with per-user OAuth.
"""
from __future__ import annotations

import asyncio

DRIVE = "https://www.googleapis.com/drive/v3"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
MAX_FILES = 60


def _session():
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    creds, _ = google.auth.default(scopes=SCOPES)
    return AuthorizedSession(creds)


def _ingest_sync(folder_id: str, by_email: dict[str, str]) -> list[dict]:
    s = _session()
    files = s.get(f"{DRIVE}/files", params={
        "q": f"'{folder_id}' in parents and trashed = false",
        "fields": "files(id,name,mimeType)",
        "pageSize": MAX_FILES,
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
    })
    files.raise_for_status()
    rows: list[dict] = []
    for f in files.json().get("files", []):
        if f["mimeType"] == "application/vnd.google-apps.folder":
            continue
        r = s.get(f"{DRIVE}/files/{f['id']}/revisions", params={
            "fields": "revisions(id,modifiedTime,lastModifyingUser(emailAddress,displayName))",
            "pageSize": 1000,
        })
        if r.status_code != 200:
            continue
        for rev in r.json().get("revisions", []):
            email = ((rev.get("lastModifyingUser") or {}).get("emailAddress") or "").lower()
            if email in by_email:
                rows.append({
                    "id": f"drive-{f['id'][:16]}-{rev['id']}", "uid": by_email[email], "source": "drive",
                    "type": "edit", "ts": rev["modifiedTime"], "weight": 1.0, "meta": {"file": f["name"][:80]},
                })
    return rows


async def ingest(team: dict, members: list[dict]) -> list[dict]:
    folder = (team.get("driveFolderId") or "").strip()
    if "folders/" in folder:  # accept a full folder URL
        folder = folder.split("folders/")[1].split("?")[0].split("/")[0]
    if not folder:
        return []
    by_email = {
        m["email"].lower(): m["uid"]
        for m in members
        if m.get("email") and (m.get("consent") or {}).get("drive", True)
    }
    if not by_email:
        return []
    return await asyncio.to_thread(_ingest_sync, folder, by_email)
