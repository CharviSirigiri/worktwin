"""Pulls commits, merged PRs and reviews from the team repo via the GitHub REST API.

Only members who consented to GitHub and gave their login are included.
"""
from __future__ import annotations

import math

import httpx

from .. import config

API = "https://api.github.com"
MAX_COMMITS_PER_MEMBER = 150
MAX_PRS = 60


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "worktwin"}
    if config.GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"
    return h


async def _paged(client: httpx.AsyncClient, url: str, params: dict, limit: int) -> list[dict]:
    out, page = [], 1
    while len(out) < limit:
        r = await client.get(url, params={**params, "per_page": 100, "page": page})
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        out += batch
        if len(batch) < 100:
            break
        page += 1
    return out[:limit]


def commit_weight(additions: int, deletions: int) -> float:
    """1 for any commit, up to 3 for big ones; log-scaled so one huge commit can't dominate."""
    net = additions + deletions
    return round(min(3.0, 1.0 + math.log1p(net) / 4), 2)


async def ingest(team: dict, members: list[dict]) -> list[dict]:
    repo = (team.get("repo") or "").strip().removeprefix("https://github.com/").strip("/")
    if not repo or "/" not in repo:
        return []
    by_login = {
        m["githubLogin"].lower(): m["uid"]
        for m in members
        if m.get("githubLogin") and (m.get("consent") or {}).get("github", True)
    }
    if not by_login:
        return []
    since = f"{team['startDate']}T00:00:00Z"
    rows: list[dict] = []
    async with httpx.AsyncClient(headers=_headers(), timeout=30) as client:
        for login, uid in by_login.items():
            commits = await _paged(client, f"{API}/repos/{repo}/commits", {"author": login, "since": since},
                                   MAX_COMMITS_PER_MEMBER)
            for c in commits:
                sha = c["sha"]
                d = await client.get(f"{API}/repos/{repo}/commits/{sha}")
                stats = d.json().get("stats", {}) if d.status_code == 200 else {}
                rows.append({
                    "id": f"gh-commit-{sha[:12]}", "uid": uid, "source": "github", "type": "commit",
                    "ts": c["commit"]["author"]["date"],
                    "weight": commit_weight(stats.get("additions", 0), stats.get("deletions", 0)),
                    "meta": {"message": c["commit"]["message"].split("\n")[0][:120]},
                })
        prs = await _paged(client, f"{API}/repos/{repo}/pulls", {"state": "all"}, MAX_PRS)
        for pr in prs:
            author = (pr.get("user") or {}).get("login", "").lower()
            if pr.get("merged_at") and author in by_login:
                rows.append({
                    "id": f"gh-pr-{pr['number']}", "uid": by_login[author], "source": "github", "type": "pr",
                    "ts": pr["merged_at"], "weight": 2.0, "meta": {"title": pr["title"][:120]},
                })
            reviews = await client.get(f"{API}/repos/{repo}/pulls/{pr['number']}/reviews")
            if reviews.status_code != 200:
                continue
            for rv in reviews.json():
                who = (rv.get("user") or {}).get("login", "").lower()
                if who in by_login and who != author and rv.get("submitted_at"):
                    rows.append({
                        "id": f"gh-review-{rv['id']}", "uid": by_login[who], "source": "github", "type": "review",
                        "ts": rv["submitted_at"], "weight": 1.0, "meta": {"pr": pr["number"]},
                    })
    return rows
