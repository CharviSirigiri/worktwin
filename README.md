# WorkTwin

**AI work twins that make university group projects actually work.**
APU Cloud Innovation Hackathon 2026, Smart Campus & Student Experience track.

Every member of a group gets an AI twin that learns how they work, from a short quiz plus their real GitHub and Google Drive activity. The twins meet, negotiate a Team Charter (roles, a meeting time that suits everyone, internal deadlines that fit each person's rhythm), nudge each person privately every week, and end the project with a Spotify-style **Team Wrapped**.

> Demo video: _add unlisted YouTube link_  ·  Pitch deck: [`docs/deck.pdf`](docs/deck.pdf)  ·  Live app: _add Firebase Hosting URL_

---

## 1. The problem

Group projects rarely fail because people are lazy. They fail because working styles collide and nobody notices until the last week: a night owl and an early bird can't find a meeting time, a deadline sprinter makes the steady worker panic, someone goes quiet because they're stuck, not slacking.

- Research on IT group projects names social loafing (free-riding) as the key challenge in group-based work ([SCITEPRESS, 2021](https://www.scitepress.org/Papers/2021/104497/104497.pdf)).
- Students value teamwork even when it is assessed, and appreciate any method that moderates free-riding ([Maiden & Perry, 2011](https://doi.org/10.1080/02602930903429302)).
- The usual fix, peer evaluation, only judges students at the end. It never helps a team plan together in week one.

**APU evidence** _(fill in)_: our poll of _N_ APU students found _X%_ had a group project go wrong this semester and _Y%_ said uneven contribution was the main cause.

## 2. The solution

| Feature | What students see |
| --- | --- |
| **Work-style twin** | A profile in plain words: "Night owl, deadline sprinter, prefers Discord", built from the quiz and real activity |
| **Twin room + Team Charter** | The twins negotiate live, in three rounds, then produce a charter everyone accepts |
| **Weekly retro** | One private, kind nudge from your own twin, and one suggestion for the team |
| **Team Wrapped** | Story slides: everyone gets a positive archetype (Night Owl, Closer, Architect, Wordsmith, Glue...), real stats, and a private reflection |
| **Meeting tap-in (IoT)** | An ESP32 NFC reader logs who showed up to meetings with their student card |

## 3. Architecture

```
 GitHub API ──┐      Google Drive API ──┐     Quiz (web) ──┐     ESP32 + RC522 NFC ──┐ HTTPS
              ▼                         ▼                  ▼                         ▼
        ┌──────────────────────── Cloud Run: FastAPI backend ─────────────────────────┐
        │  ingest · metrics (computed in code) · Google ADK agents on Gemini          │
        │     Coordinator agent ──► Twin agents (one per member)                      │
        │     Wrapped narrator agent                                                  │
        └──────────────┬──────────────────────────────────────────────┬──────────────┘
                       ▼                                              ▼
                  Firestore                               Web app (Next.js) on Firebase Hosting
        profiles · activity · room · charter            twin room (streamed live) · retro · Wrapped
```

| Theme pillar | In WorkTwin |
| --- | --- |
| Cloud | Cloud Run, Firestore, Secret Manager, Cloud Scheduler, Firebase Hosting |
| IoT | ESP32 + RC522 NFC meeting tap-in ([`iot/`](iot/tapin_esp32/tapin_esp32.ino)) |
| Network | OAuth APIs to GitHub and Google, HTTPS from the ESP32, twins talking to each other |
| Gemini | Twin profiles, the negotiation, retro nudges, Wrapped captions |
| Built with Antigravity | _add screenshots of parallel agents building frontend / backend / database_ |

## 4. How Gemini and the agents are used

- Every agent is a **Google ADK** `LlmAgent` running Gemini ([`backend/app/llm.py`](backend/app/llm.py)). A native ADK multi-agent app (coordinator with one twin sub-agent per member) lives in [`backend/adk_agents`](backend/adk_agents/worktwin/agent.py).
- **Numbers never come from the model.** Peak hours, streaks, contribution mix and archetypes are computed in [`metrics.py`](backend/app/metrics.py); Gemini only writes the words around them.
- A rule-based draft charter is always computed first, and the model's final charter is validated field by field against it, so a bad model reply can't break the plan.
- **Mock mode:** with no API key the whole app still runs with template-written agent output. The demo never fails on stage.
- **Final round (Gemini Enterprise):** the ADK app deploys to Agent Runtime and is registered in Gemini Enterprise, where Gemini Enterprise admins can register ADK agents hosted on Agent Runtime, or A2A agents ([Google Cloud docs](https://docs.cloud.google.com/gemini/enterprise/docs/agents-overview)). The weekly retro becomes a scheduled workflow agent emailing nudges via Gmail.

## 5. Privacy and fairness by design

- **Opt-in per source.** Each member chooses whether their twin may read GitHub and Drive.
- **Twins share summaries, never raw data.** The private quiz answer and personal commitments never leave the backend (enforced in `public_member()` and `twin.public_profile()`; covered by tests).
- **No leaderboard.** Wrapped shows contribution by *type* (code, writing, coordination) and gives everyone one distinct, positive archetype.
- **No public call-outs.** Nudges are private and never name other members.
- **Anti-gaming.** Commit weight is log-scaled and each member's weight is capped per hour, so commit spam doesn't count.
- Aligned with Malaysia's Personal Data Protection Act (PDPA) 2010 principles: consent, purpose limitation, deletion on request.

## 6. Run it

See **[DEPLOY.md](DEPLOY.md)** for local setup and Google Cloud deployment. Quick local start:

```bash
# backend (mock mode, no key needed)
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && uvicorn app.main:app --reload --port 8080

# frontend
cd frontend && npm install && npm run dev        # http://localhost:3000, click "Try the demo team"

# tests
cd backend && pip install pytest && python -m pytest -q
```

## 7. Team

| Member | Role | Built |
| --- | --- | --- |
| _Name_ | Agents lead | Twin + coordinator agents, prompts, Gemini Enterprise port |
| _Name_ | Data and backend | GitHub/Drive ingestion, Firestore, metrics, Cloud Run |
| _Name_ | Frontend | Web app, twin room, Team Wrapped |
| _Name_ | Pitch, IoT and data | Poll, ESP32 tap-in, deck, video |

## 8. Impact and roadmap

**Metrics we would track in an APU pilot:** share of teams whose charter is accepted by everyone in week 1, number of members missing two check-ins in a row, how evenly work is spread (Gini of contribution weight), and post-project satisfaction vs. a control group.

**Roadmap:** Gemini Enterprise agents with Gmail/Calendar workflows → Microsoft Teams/OneDrive connectors (APU's own stack) → per-user OAuth and Drive Activity API → lecturer view showing only what teams choose to share.

## Repository

```
backend/    FastAPI + ADK agents + metrics + ingestion (Cloud Run)
  app/agents/   twin.py, coordinator.py, narrator.py
  app/ingest/   github.py, google_drive.py
  adk_agents/   native ADK app for `adk web` and Gemini Enterprise
  tests/        end-to-end tests (mock mode)
frontend/   Next.js static site (Firebase Hosting)
iot/        ESP32 + RC522 meeting tap-in sketch
docs/       deck, screenshots, poll results
```
