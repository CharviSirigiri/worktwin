"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ErrorBox, TopBar } from "@/components/ui";
import { api, type Question } from "@/lib/api";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const PARTS: [string, string][] = [["AM", "Morning"], ["PM", "Afternoon"], ["EVE", "Evening"]];

function Quiz() {
  const router = useRouter();
  const params = useSearchParams();
  const teamId = params.get("team") || "";
  const uid = params.get("uid") || "";
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<{ questions: Question[] }>("/quiz").then((r) => setQuestions(r.questions)).catch((e) => setError(e.message));
  }, []);

  function toggle(q: Question, value: string) {
    const cur: string[] = answers[q.id] || [];
    let next = cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value];
    if (q.max && next.length > q.max) next = next.slice(next.length - q.max);
    setAnswers({ ...answers, [q.id]: next });
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api(`/teams/${teamId}/members/${uid}/quiz`, { method: "POST", json: { answers } });
      router.push(`/team/?id=${teamId}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  const answered = questions.filter((q) => {
    const a = answers[q.id];
    return q.type === "text" ? true : Array.isArray(a) ? a.length > 0 : !!a;
  }).length;

  return (
    <>
      <TopBar right={<span className="faint">{questions.length ? `${answered} of ${questions.length} answered` : ""}</span>} />
      <main className="wrap page stack" style={{ maxWidth: 720 }}>
        <h1 style={{ fontSize: "2.6rem" }}>How do you work?</h1>
        <p className="lede">Your twin starts from these answers and learns the rest from what you actually do. There are no wrong answers.</p>
        <ErrorBox error={error} />
        <form onSubmit={submit} className="stack">
          {questions.map((q) => (
            <fieldset key={q.id} className="sheet" style={{ border: 0, margin: 0 }}>
              <legend style={{ fontFamily: "var(--display)", fontWeight: 650, fontSize: "1.2rem", float: "left", width: "100%", marginBottom: 14 }}>
                {q.text}
              </legend>
              {q.type === "single" && (
                <div className="row" style={{ clear: "both" }}>
                  {q.options!.map((o) => (
                    <button type="button" key={o.value} className="pill" aria-pressed={answers[q.id] === o.value}
                      onClick={() => setAnswers({ ...answers, [q.id]: o.value })}>
                      {o.label}
                    </button>
                  ))}
                </div>
              )}
              {q.type === "multi" && (
                <div className="row" style={{ clear: "both" }}>
                  {q.options!.map((o) => (
                    <button type="button" key={o.value} className="pill" aria-pressed={(answers[q.id] || []).includes(o.value)}
                      onClick={() => toggle(q, o.value)}>
                      {o.label}
                    </button>
                  ))}
                </div>
              )}
              {q.type === "slots" && (
                <div className="slots" style={{ clear: "both" }}>
                  <span />
                  {PARTS.map(([, label]) => (
                    <span key={label} className="head">{label}</span>
                  ))}
                  {DAYS.map((d) => (
                    <div key={d} style={{ display: "contents" }}>
                      <span className="day">{d}</span>
                      {PARTS.map(([p, label]) => {
                        const slot = `${d}-${p}`;
                        return (
                          <button type="button" key={slot} aria-label={`${d} ${label}`}
                            aria-pressed={(answers[q.id] || []).includes(slot)} onClick={() => toggle(q, slot)} />
                        );
                      })}
                    </div>
                  ))}
                </div>
              )}
              {q.type === "text" && (
                <textarea style={{ clear: "both" }} rows={2} value={answers[q.id] || ""} maxLength={300}
                  onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })} />
              )}
            </fieldset>
          ))}
          {questions.length > 0 && (
            <div className="row">
              <button className="btn" disabled={busy}>
                {busy ? "Saving..." : "Save my answers"}
              </button>
            </div>
          )}
        </form>
      </main>
    </>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Quiz />
    </Suspense>
  );
}
