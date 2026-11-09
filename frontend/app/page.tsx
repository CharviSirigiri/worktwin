"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ErrorBox, TopBar } from "@/components/ui";
import { api, type Team } from "@/lib/api";

const PREVIEW = [
  { who: "Aisha's twin", color: "#FF7A3D", soft: "#FFE3D4", text: "I'm at my best after 10 PM, so please don't book me for 9 AM calls." },
  { who: "Wei Jie's twin", color: "#14A39A", soft: "#CDEFEC", text: "Fine by me. I'll review her PRs the next afternoon." },
  { who: "Coordinator", color: "#1A2340", soft: "#1A2340", text: "Agreed: Wednesday evening check-in, and Aisha's internal deadline moves to Sat 7 Nov." },
];

export default function Home() {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", module: "", brief: "", startDate: "", deadline: "", repo: "", driveFolderId: "" });

  async function openDemo() {
    setBusy("demo");
    setError(null);
    try {
      const { teamId } = await api<{ teamId: string }>("/demo/seed", { method: "POST" });
      router.push(`/team/?id=${teamId}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(null);
    }
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy("create");
    setError(null);
    try {
      const body = { ...form, startDate: form.startDate || undefined };
      const { team } = await api<{ team: Team }>("/teams", { method: "POST", json: body });
      router.push(`/join/?team=${team.id}&first=1`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(null);
    }
  }

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: e.target.value });

  return (
    <>
      <TopBar />
      <main className="wrap page stack">
        <section className="stack" style={{ maxWidth: 760 }}>
          <h1>Every group has a night owl, a planner and someone who goes quiet.</h1>
          <p className="lede">
            WorkTwin gives each member an AI twin that learns how they work. The twins agree a plan before anyone
            argues, check in every week, and end the project with your Team Wrapped.
          </p>
          <div className="row">
            <button className="btn" onClick={openDemo} disabled={!!busy}>
              {busy === "demo" ? "Loading the demo team..." : "Try the demo team"}
            </button>
            <a className="btn ghost" href="#create">
              Start your own team
            </a>
          </div>
          <ErrorBox error={error} />
        </section>

        <section className="sheet" aria-label="Example of twins talking" style={{ maxWidth: 760 }}>
          <div className="chat">
            {PREVIEW.map((m, i) => (
              <div key={i} className={`msg${m.who === "Coordinator" ? " coord" : ""}`}>
                <div className="bubble" style={m.who === "Coordinator" ? undefined : { background: m.soft }}>
                  <div className="who" style={{ color: m.who === "Coordinator" ? "#fff" : m.color }}>
                    {m.who}
                  </div>
                  {m.text}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="stack" style={{ marginTop: 56 }}>
          <h2>How it works</h2>
          <ol className="steps">
            <li>
              <div>
                <strong>Everyone joins and takes a 3-minute quiz.</strong>
                <p className="muted">Link GitHub and your Google account if you like. Your twin learns from your real activity too.</p>
              </div>
            </li>
            <li>
              <div>
                <strong>The twins meet and write your Team Charter.</strong>
                <p className="muted">Roles, a meeting time that suits everyone, and internal deadlines that fit how each person works.</p>
              </div>
            </li>
            <li>
              <div>
                <strong>Weekly nudges, then Team Wrapped.</strong>
                <p className="muted">A private nudge from your own twin each week, and a recap at the end that celebrates every kind of contribution.</p>
              </div>
            </li>
          </ol>
        </section>

        <section id="create" className="sheet" style={{ marginTop: 56 }}>
          <form onSubmit={create} className="stack">
            <h2>Start your own team</h2>
            <div className="grid2">
              <div className="field">
                <label htmlFor="name">Team name</label>
                <input id="name" type="text" required value={form.name} onChange={set("name")} placeholder="Team Nebula" />
              </div>
              <div className="field">
                <label htmlFor="module">Module</label>
                <input id="module" type="text" value={form.module} onChange={set("module")} placeholder="CT050-3-3 Project Management" />
              </div>
            </div>
            <div className="field">
              <label htmlFor="brief">What are you building?</label>
              <textarea id="brief" rows={2} value={form.brief} onChange={set("brief")} placeholder="A campus energy-saving web app, a report and a 10-minute pitch" />
            </div>
            <div className="grid2">
              <div className="field">
                <label htmlFor="start">Start date</label>
                <input id="start" type="date" value={form.startDate} onChange={set("startDate")} />
              </div>
              <div className="field">
                <label htmlFor="deadline">Final deadline</label>
                <input id="deadline" type="date" required value={form.deadline} onChange={set("deadline")} />
              </div>
            </div>
            <div className="grid2">
              <div className="field">
                <label htmlFor="repo">
                  GitHub repo <span className="hint">optional, owner/repo</span>
                </label>
                <input id="repo" type="text" value={form.repo} onChange={set("repo")} placeholder="your-team/energy-app" />
              </div>
              <div className="field">
                <label htmlFor="drive">
                  Google Drive folder <span className="hint">optional, link or ID</span>
                </label>
                <input id="drive" type="text" value={form.driveFolderId} onChange={set("driveFolderId")} />
              </div>
            </div>
            <div className="row">
              <button className="btn" disabled={!!busy}>
                {busy === "create" ? "Creating..." : "Create team"}
              </button>
            </div>
          </form>
        </section>
      </main>
    </>
  );
}
