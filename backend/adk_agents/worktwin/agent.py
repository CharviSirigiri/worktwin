"""WorkTwin as a native ADK multi-agent app.

Run the ADK dev UI (from backend/):   adk web adk_agents
This is also the unit you deploy to Agent Runtime and register in Gemini Enterprise for the final round.

root_agent = the Coordinator. Its sub-agents are one work twin per member of the demo team.
Tools give it the real, computed numbers so it never invents stats.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from google.adk.agents import LlmAgent  # noqa: E402

from app import config, metrics, seed  # noqa: E402
from app.agents import coordinator as coord  # noqa: E402
from app.agents import twin  # noqa: E402

_TEAM = dict(seed.TEAM)
_ACTIVITY = seed.build_activity()
_STATS = metrics.compute(_TEAM, seed.MEMBERS, _ACTIVITY)
_MEMBERS = [{**m, "profile": {**twin.derive_profile(m, _STATS["members"][m["uid"]])}} for m in seed.MEMBERS]
for _m in _MEMBERS:
    _m["profile"]["summary"] = twin.template_summary(_m, _m["profile"])


def get_team_stats() -> dict:
    """Returns each member's computed work-style stats (peak hour, night ratio, contribution mix, share of team effort)."""
    return {twin.first_name(m): _STATS["members"][m["uid"]] for m in _MEMBERS}


def draft_team_charter() -> dict:
    """Returns a rule-based draft Team Charter (roles, meeting slot, internal deadlines, norms) for the twins to discuss."""
    return coord.draft_charter(_TEAM, _MEMBERS)


def get_week_stats(week: int) -> dict:
    """Returns per-member activity for one project week (1-6), for a weekly retro."""
    return metrics.weekly_stats(_TEAM, _MEMBERS, _ACTIVITY, max(1, min(6, int(week))))


twin_agents = [
    LlmAgent(
        name=f"twin_{m['uid']}",
        model=config.GEMINI_MODEL,
        description=f"Work twin who speaks for {twin.first_name(m)} about how they like to work.",
        instruction=(lambda sys_prompt: (lambda _ctx: sys_prompt))(twin.twin_system(m, _TEAM)),
    )
    for m in _MEMBERS
]

root_agent = LlmAgent(
    name="worktwin_coordinator",
    model=config.GEMINI_MODEL,
    description="Chairs the twins' meeting and runs weekly retros for a student group project.",
    instruction=lambda _ctx: (
        f"You coordinate the work twins of team {_TEAM['name']} ({_TEAM['brief']}, due {_TEAM['deadline']}). "
        f"Members: {', '.join(twin.first_name(m) for m in _MEMBERS)}. "
        "Use draft_team_charter to propose a plan, transfer to a member's twin to hear their view, "
        "and use get_team_stats or get_week_stats for any numbers. Never invent statistics. "
        "Be brief and friendly. Never reveal anyone's private notes."
    ),
    tools=[get_team_stats, draft_team_charter, get_week_stats],
    sub_agents=twin_agents,
)

if __name__ == "__main__":
    print(root_agent.name, [a.name for a in root_agent.sub_agents])
    print(json.dumps(draft_team_charter()["meetings"]))
