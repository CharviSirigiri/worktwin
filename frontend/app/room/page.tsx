"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { ErrorBox, TopBar, TwinMark } from "@/components/ui";
import { api, me, streamRoom, type Charter, type RoomMessage, type TeamView } from "@/lib/api";
import { colorFor, fmtDate } from "@/lib/people";

const ROUNDS: Record<number, string> = {
  1: "Round 1: how everyone works",
  2: "Round 2: the draft plan",
  3: "Round 3: final agreements",
};

function Room() {
  const params = useSearchParams();
  const id = params.get("id") || "";
  const [view, setView] = useState<TeamView | null>(null);
  const [messages, setMessages] = useState<RoomMessage[]>([]);
  const [charter, setCharter] = useState<Charter | null>(null);
  const [live, setLive] = useState(false);
  const [freshFrom, setFreshFrom] = useState(Infinity);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!id) return;
    api<TeamView>(`/teams/${id}`).then(setView).catch((e) => setError(e.message));
    api<{ messages: RoomMessage[]; charter: Charter | null }>(`/teams/${id}/room`)
      .then((r) => {
        setMessages(r.messages);
        setCharter(r.charter);
      })
      .catch(() => {});
  }, [id]);

  useEffect(() => {
    if (live) endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, live]);

  async function start() {
    setError(null);
    setMessages([]);
    setCharter(null);
    setFreshFrom(0);
    setLive(true);
    try {
      await streamRoom(id, (item) => {
        if (item.type === "message") setMessages((prev) => [...prev, item]);
        else if (item.type === "charter") setCharter(item.charter);
        else if (item.type === "error") setError(`The meeting stopped: ${item.error}`);
      });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLive(false);
    }
  }

  async function accept(uid: string) {
    try {
      const r = await api<{ charter: Charter }>(`/teams/${id}/charter/accept`, { method: "POST", json: { uid } });
      setCharter(r.charter);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (!view) {
    return (
      <>
        <TopBar />
        <main className="wrap page"><ErrorBox error={error} />{!error && <p className="muted">Loading...</p>}</main>
      </>
    );
  }

  const members = view.members;
  const nameOf = (uid: string) => members.find((m) => m.uid === uid)?.shortName || uid;
  const mine = me.get(id);
  let lastRound = 0;

  return (
    <>
      <TopBar right={<Link className="btn ghost small" href={`/team/?id=${id}`}>Back to {view.team.name}</Link>} />
      <main className="wrap page stack">
        <section className="stack">
          <h1 style={{ fontSize: "clamp(2.2rem, 5vw, 3.4rem)" }}>The twin room</h1>
          <p className="lede">
            Each twin speaks for its person. They share summaries, never anyone&apos;s private answers, and finish with a Team Charter everyone can accept.
          </p>
          <div className="row">
            <button className="btn" onClick={start} disabled={live}>
              {live ? "The twins are talking..." : messages.length ? "Run the meeting again" : "Start the twins' meeting"}
            </button>
            <div className="row" aria-label="Who is in the room">
              {members.map((m) => (
                <TwinMark key={m.uid} members={members} uid={m.uid} twinOnly />
              ))}
            </div>
          </div>
        </section>

        <ErrorBox error={error} />

        {(messages.length > 0 || live) && (
          <section className="sheet" aria-live="polite" aria-label="Meeting transcript">
            <div className="chat">
              {messages.map((m, i) => {
                const header = m.round !== lastRound ? ROUNDS[m.round] : null;
                lastRound = m.round;
                const isCoord = m.speaker === "coordinator";
                const uid = m.speaker.replace("twin:", "");
                const c = isCoord ? null : colorFor(members, uid);
                return (
                  <div key={i}>
                    {header && <p className="round">{header}</p>}
                    <div className={`msg${isCoord ? " coord" : ""}${i >= freshFrom ? " enter" : ""}`}>
                      {!isCoord && <TwinMark members={members} uid={uid} twinOnly />}
                      <div className="bubble" style={c ? { background: c.soft, color: c.ink } : undefined}>
                        <div className="who" style={{ color: c ? c.ink : "#fff", opacity: c ? 0.8 : 0.75 }}>{m.name}</div>
                        {m.text}
                      </div>
                    </div>
                  </div>
                );
              })}
              {live && (
                <div className="msg" aria-label="Someone is typing">
                  <span className="typing"><i /><i /><i /></span>
                </div>
              )}
              <div ref={endRef} />
            </div>
          </section>
        )}

        {charter && (
          <section className="sheet charter" aria-labelledby="charter-h">
            <div>
              <h2 id="charter-h">Team Charter</h2>
              <p className="muted" style={{ marginTop: 6 }}>{charter.summary}</p>
            </div>

            <div>
              <h3 style={{ marginBottom: 6 }}>Who owns what</h3>
              <table>
                <thead><tr><th>Person</th><th>Owns</th><th>Why</th></tr></thead>
                <tbody>
                  {charter.roles.map((r, i) => (
                    <tr key={i}>
                      <td><span className="dot" style={{ background: colorFor(members, r.uid).solid }} />{nameOf(r.uid)}</td>
                      <td><strong>{r.role}</strong></td>
                      <td className="muted">{r.why}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="grid2">
              <div>
                <h3 style={{ marginBottom: 6 }}>When you meet</h3>
                {charter.meetings.map((m) => (
                  <p key={m.slot} style={{ marginBottom: 8 }}><strong>{m.label}</strong><br /><span className="faint">{m.why}</span></p>
                ))}
              </div>
              <div>
                <h3 style={{ marginBottom: 6 }}>Internal deadlines</h3>
                {charter.internalDeadlines.map((d) => (
                  <p key={d.uid} style={{ marginBottom: 8 }}>
                    <span className="dot" style={{ background: colorFor(members, d.uid).solid }} />
                    <strong>{nameOf(d.uid)}: {fmtDate(d.date)}</strong>
                    <br /><span className="faint">{d.why}</span>
                  </p>
                ))}
              </div>
            </div>

            <div>
              <h3 style={{ marginBottom: 6 }}>How we work together</h3>
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {charter.norms.map((n, i) => <li key={i}>{n}</li>)}
              </ul>
            </div>

            <div>
              <h3 style={{ marginBottom: 10 }}>Accept the charter</h3>
              <div className="row">
                {members.map((m) => {
                  const done = charter.acceptedBy.includes(m.uid);
                  const canClick = view.team.demo || !mine || mine === m.uid;
                  return (
                    <button key={m.uid} className={`btn small${done ? " done" : " ghost"}`} disabled={done || !canClick || live}
                      onClick={() => accept(m.uid)} style={done ? { background: colorFor(members, m.uid).solid } : undefined}>
                      {done ? `${m.shortName} accepted` : `Accept as ${m.shortName}`}
                    </button>
                  );
                })}
              </div>
            </div>
          </section>
        )}
      </main>
    </>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Room />
    </Suspense>
  );
}
