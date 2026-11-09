"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ErrorBox, TopBar, TwinMark } from "@/components/ui";
import { api, me, type Retro, type TeamView } from "@/lib/api";
import { colorFor, fmtDate } from "@/lib/people";

function RetroPage() {
  const params = useSearchParams();
  const id = params.get("id") || "";
  const [view, setView] = useState<TeamView | null>(null);
  const [week, setWeek] = useState<number>(0);
  const [retro, setRetro] = useState<Retro | null>(null);
  const [viewer, setViewer] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api<TeamView>(`/teams/${id}`)
      .then((v) => {
        setView(v);
        setWeek(v.team.demo ? 3 : v.currentWeek);
        setViewer(me.get(id) || v.members[0]?.uid || "");
      })
      .catch((e) => setError(e.message));
  }, [id]);

  useEffect(() => {
    if (!id || !week) return;
    setRetro(null);
    api<Retro>(`/teams/${id}/retro?week=${week}`).then(setRetro).catch(() => {});
  }, [id, week]);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setRetro(await api<Retro>(`/teams/${id}/retro?week=${week}`, { method: "POST" }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!view) {
    return (<><TopBar /><main className="wrap page"><ErrorBox error={error} />{!error && <p className="muted">Loading...</p>}</main></>);
  }

  const { team, members } = view;
  const totalWeeks = Math.max(1, Math.ceil((new Date(team.deadline).getTime() - new Date(team.startDate).getTime()) / (7 * 86400000)));
  const person = members.find((m) => m.uid === viewer);
  const c = person ? colorFor(members, person.uid) : null;
  const mine = me.get(id);

  return (
    <>
      <TopBar right={<Link className="btn ghost small" href={`/team/?id=${id}`}>Back to {team.name}</Link>} />
      <main className="wrap page stack">
        <h1 style={{ fontSize: "clamp(2.2rem, 5vw, 3.4rem)" }}>Weekly retro</h1>
        <p className="lede">The coordinator reads the week&apos;s activity. Each person gets a private nudge from their own twin; the team gets one shared suggestion.</p>

        <div className="row" role="group" aria-label="Choose a week">
          {Array.from({ length: totalWeeks }, (_, i) => i + 1).map((w) => (
            <button key={w} className="pill" aria-pressed={w === week} onClick={() => setWeek(w)}>Week {w}</button>
          ))}
        </div>

        <div className="row">
          <button className="btn" onClick={run} disabled={busy || !members.length}>
            {busy ? "Running the retro..." : retro ? `Run week ${week} again` : `Run week ${week} retro`}
          </button>
          {retro && <span className="faint">{fmtDate(retro.from)} to {fmtDate(retro.to)}</span>}
        </div>
        <ErrorBox error={error} />

        {retro && (
          <>
            <section className="sheet" style={{ background: "var(--ink)", color: "#fff" }}>
              <p style={{ opacity: 0.7, marginBottom: 6 }}>For the whole team</p>
              <p style={{ fontFamily: "var(--display)", fontSize: "1.45rem", fontWeight: 600, lineHeight: 1.3 }}>{retro.teamSuggestion}</p>
            </section>

            <section className="stack">
              <h2>Private nudges</h2>
              <p className="muted">
                {team.demo || !mine
                  ? "In the real app each person only sees their own. For the demo, switch between people."
                  : "Only you can see your nudge."}
              </p>
              {(team.demo || !mine) && (
                <div className="row" role="group" aria-label="View as">
                  {members.map((m) => (
                    <button key={m.uid} className="pill" aria-pressed={m.uid === viewer} onClick={() => setViewer(m.uid)}>{m.shortName}</button>
                  ))}
                </div>
              )}
              {person && c && (
                <div className="msg">
                  <TwinMark members={members} uid={person.uid} twinOnly />
                  <div className="bubble" style={{ background: c.soft, color: c.ink, fontSize: "1.1rem" }}>
                    <div className="who">From {person.shortName}&apos;s twin, just to {person.shortName}</div>
                    {retro.nudges[person.uid]}
                  </div>
                </div>
              )}
            </section>

            <section className="sheet">
              <h3 style={{ marginBottom: 8 }}>Week {week} at a glance</h3>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ textAlign: "left", color: "var(--ink-2)", fontSize: "0.92rem" }}>
                    <th style={{ padding: 8 }}>Person</th><th style={{ padding: 8 }}>Contributions</th><th style={{ padding: 8 }}>Active days</th><th style={{ padding: 8 }}>Check-in</th>
                  </tr>
                </thead>
                <tbody>
                  {members.map((m) => {
                    const s = retro.stats[m.uid];
                    if (!s) return null;
                    return (
                      <tr key={m.uid} style={{ borderTop: "1px solid var(--line)" }}>
                        <td style={{ padding: 8 }}><span className="dot" style={{ background: colorFor(members, m.uid).solid }} />{m.shortName}</td>
                        <td style={{ padding: 8 }}>{s.events}</td>
                        <td style={{ padding: 8 }}>{s.activeDays} of 7</td>
                        <td style={{ padding: 8 }}>{s.meetings ? "Attended" : "Missed"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p className="faint" style={{ marginTop: 10 }}>Shown as counts, not rankings. The retro never names anyone in another person&apos;s nudge.</p>
            </section>
          </>
        )}
      </main>
    </>
  );
}

export default function Page() {
  return (
    <Suspense>
      <RetroPage />
    </Suspense>
  );
}
