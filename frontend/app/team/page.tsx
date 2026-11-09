"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { ErrorBox, TopBar } from "@/components/ui";
import { api, me, type TeamView } from "@/lib/api";
import { colorFor, daysLeft, fmtDate } from "@/lib/people";

function TeamPage() {
  const params = useSearchParams();
  const id = params.get("id") || "";
  const [view, setView] = useState<TeamView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [cardOwner, setCardOwner] = useState("");

  const load = useCallback(() => {
    if (!id) return;
    api<TeamView>(`/teams/${id}`).then(setView).catch((e) => setError(e.message));
  }, [id]);
  useEffect(load, [load]);

  async function run(key: string, fn: () => Promise<string | void>) {
    setBusy(key);
    setError(null);
    setNote(null);
    try {
      const msg = await fn();
      if (msg) setNote(msg);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const pull = () =>
    run("pull", async () => {
      const r = await api<{ github: number; drive: number; total: number; errors: string[] }>(`/teams/${id}/ingest`, { method: "POST" });
      if (r.errors.length) throw new Error(`Some sources failed: ${r.errors.join("; ")}`);
      return `Pulled ${r.github} GitHub events and ${r.drive} Drive edits. ${r.total} activities in total.`;
    });
  const build = () =>
    run("build", async () => {
      await api(`/teams/${id}/twins/build`, { method: "POST" });
      return "Every twin has read their person's quiz and activity.";
    });
  const linkCard = () =>
    run("card", async () => {
      await api(`/teams/${id}/members/${cardOwner}/card`, { method: "POST", json: { card: view!.lastUnknownCard } });
      return "Card linked. Future taps will count as meeting check-ins.";
    });

  function copyInvite() {
    const url = `${window.location.origin}/join/?team=${id}`;
    navigator.clipboard?.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  if (!view) {
    return (
      <>
        <TopBar />
        <main className="wrap page">
          <ErrorBox error={error} />
          {!error && <p className="muted">Loading team...</p>}
        </main>
      </>
    );
  }

  const { team, members, charter } = view;
  const mine = me.get(id);
  const hasTwins = members.length > 0 && members.every((m) => m.profile);
  const quizLeft = members.filter((m) => !m.quizDone);
  const left = daysLeft(team.deadline);

  return (
    <>
      <TopBar
        right={
          <button className="btn ghost small" onClick={copyInvite}>
            {copied ? "Invite link copied" : "Copy invite link"}
          </button>
        }
      />
      <main className="wrap page stack">
        <section className="stack">
          <p className="muted">{team.module || "Group project"}</p>
          <h1>{team.name}</h1>
          {team.brief && <p className="lede">{team.brief}</p>}
          <div className="row">
            <span className="tag">Due {fmtDate(team.deadline)}</span>
            <span className="tag">{left > 0 ? `${left} days left` : left === 0 ? "Due today" : "Finished"}</span>
            <span className="tag">Week {view.currentWeek}</span>
            <span className="tag">{view.activityCount} activities tracked</span>
          </div>
        </section>

        <ErrorBox error={error} />
        {note && <p className="notice" role="status">{note}</p>}

        {view.lastUnknownCard && (
          <div className="notice row" style={{ justifyContent: "space-between" }}>
            <span>A student card was tapped at the meeting reader but isn&apos;t linked to anyone yet.</span>
            <div className="row">
              <select aria-label="Who does this card belong to?" value={cardOwner} onChange={(e) => setCardOwner(e.target.value)} style={{ width: "auto" }}>
                <option value="">Choose who</option>
                {members.map((m) => (
                  <option key={m.uid} value={m.uid}>{m.shortName}</option>
                ))}
              </select>
              <button className="btn small" disabled={!cardOwner || !!busy} onClick={linkCard}>Link card</button>
            </div>
          </div>
        )}

        <section className="stack" aria-labelledby="steps-h">
          <h2 id="steps-h">Run the project</h2>
          <ol className="steps">
            <li className={members.length >= 2 && !quizLeft.length ? "done" : ""}>
              <div>
                <strong>Everyone joins and takes the quiz</strong>
                <p className="faint">
                  {members.length} joined
                  {quizLeft.length ? `, waiting on ${quizLeft.map((m) => m.shortName).join(", ")}` : ", all quizzes done"}
                </p>
              </div>
              {!mine && !team.demo ? <Link className="btn small" href={`/join/?team=${id}`}>Join</Link> : <span />}
            </li>
            <li className={view.activityCount > 0 ? "done" : ""}>
              <div>
                <strong>Pull activity from GitHub and Google Drive</strong>
                <p className="faint">
                  {team.demo ? "The demo team comes with six weeks of activity already." : team.repo || team.driveFolderId ? "Reads only what each member agreed to share." : "No repo or Drive folder linked yet; twins will use the quiz only."}
                </p>
              </div>
              <button className="btn small ghost" onClick={pull} disabled={!!busy || team.demo}>
                {busy === "pull" ? "Pulling..." : "Pull activity"}
              </button>
            </li>
            <li className={hasTwins ? "done" : ""}>
              <div>
                <strong>Build the twins</strong>
                <p className="faint">Each twin reads its person&apos;s quiz and activity.</p>
              </div>
              <button className="btn small" onClick={build} disabled={!!busy || members.length < 1}>
                {busy === "build" ? "Building..." : hasTwins ? "Rebuild twins" : "Build twins"}
              </button>
            </li>
            <li className={charter ? "done" : ""}>
              <div>
                <strong>Let the twins meet</strong>
                <p className="faint">{charter ? `${charter.acceptedBy.length} of ${members.length} accepted the charter` : "They negotiate roles, a meeting time and internal deadlines."}</p>
              </div>
              {hasTwins ? <Link className="btn small" href={`/room/?id=${id}`}>Open the twin room</Link> : <span className="faint">Build twins first</span>}
            </li>
            <li>
              <div>
                <strong>Weekly retro</strong>
                <p className="faint">One private nudge per person and one suggestion for the team.</p>
              </div>
              <Link className="btn small ghost" href={`/retro/?id=${id}`}>Open retro</Link>
            </li>
            <li>
              <div>
                <strong>Team Wrapped</strong>
                <p className="faint">The end-of-project recap.</p>
              </div>
              <Link className="btn small ghost" href={`/wrapped/?id=${id}`}>Play Wrapped</Link>
            </li>
          </ol>
        </section>

        <section className="stack" aria-labelledby="twins-h" style={{ marginTop: 40 }}>
          <h2 id="twins-h">The team and their twins</h2>
          {members.length === 0 && (
            <div className="sheet flat">
              <p>Nobody has joined yet. Copy the invite link above and send it to your group.</p>
            </div>
          )}
          <div>
            {members.map((m) => {
              const c = colorFor(members, m.uid);
              const role = charter?.roles.filter((r) => r.uid === m.uid).map((r) => r.role).join(", ");
              return (
                <article key={m.uid} className="pair">
                  <div className="pair-person">
                    <span className="avatar" style={{ background: c.solid, color: c.ink }}>{m.shortName.slice(0, 1)}</span>
                    <h3>{m.shortName}</h3>
                    <p style={{ opacity: 0.75, fontSize: "0.92rem" }}>{m.name}</p>
                    {role && <p style={{ marginTop: 10, fontWeight: 700, color: c.solid }}>{role}</p>}
                    {mine === m.uid && <p style={{ marginTop: 8, fontSize: "0.85rem" }}>This is you</p>}
                  </div>
                  <div className="pair-twin" style={{ background: c.soft, color: c.ink }}>
                    {m.profile ? (
                      <>
                        <p style={{ fontWeight: 700, marginBottom: 4 }}>{m.shortName}&apos;s twin</p>
                        <p>{m.profile.summary}</p>
                        <div className="traits">
                          {m.profile.traits.map((t) => (
                            <span key={t}>{t}</span>
                          ))}
                        </div>
                        <p style={{ fontSize: "0.85rem", marginTop: 10, opacity: 0.75 }}>{m.profile.evidence}</p>
                      </>
                    ) : (
                      <p style={{ opacity: 0.8 }}>
                        {m.quizDone ? "Quiz done. The twin wakes up when you build the twins." : "Waiting for the quiz."}
                        {!m.quizDone && mine === m.uid && (
                          <>
                            {" "}
                            <Link href={`/quiz/?team=${id}&uid=${m.uid}`}>Take it now</Link>
                          </>
                        )}
                      </p>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      </main>
    </>
  );
}

export default function Page() {
  return (
    <Suspense>
      <TeamPage />
    </Suspense>
  );
}
