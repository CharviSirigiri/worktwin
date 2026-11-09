"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ErrorBox, TopBar } from "@/components/ui";
import { api, me, type Member, type TeamView } from "@/lib/api";

function Join() {
  const router = useRouter();
  const params = useSearchParams();
  const teamId = params.get("team") || "";
  const [view, setView] = useState<TeamView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ name: "", shortName: "", email: "", githubLogin: "" });
  const [consent, setConsent] = useState({ github: true, drive: true });

  useEffect(() => {
    if (!teamId) return;
    api<TeamView>(`/teams/${teamId}`).then(setView).catch((e) => setError(e.message));
  }, [teamId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { member } = await api<{ member: Member }>(`/teams/${teamId}/join`, {
        method: "POST",
        json: { ...form, consent },
      });
      me.set(teamId, member.uid);
      router.push(`/quiz/?team=${teamId}&uid=${member.uid}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  return (
    <>
      <TopBar />
      <main className="wrap page stack" style={{ maxWidth: 680 }}>
        <h1 style={{ fontSize: "2.6rem" }}>{view ? `Join ${view.team.name}` : "Join your team"}</h1>
        {view && (
          <p className="lede">
            {params.get("first")
              ? "Your team is ready. Add yourself first, then share the invite link from the team page."
              : `${view.members.length} ${view.members.length === 1 ? "person has" : "people have"} joined so far.`}
          </p>
        )}
        <ErrorBox error={error} />
        <form className="sheet stack" onSubmit={submit}>
          <div className="grid2">
            <div className="field">
              <label htmlFor="name">Full name</label>
              <input id="name" type="text" required value={form.name} onChange={set("name")} />
            </div>
            <div className="field">
              <label htmlFor="short">
                What the team calls you <span className="hint">optional</span>
              </label>
              <input id="short" type="text" value={form.shortName} onChange={set("shortName")} placeholder="Wei Jie" />
            </div>
          </div>
          <div className="grid2">
            <div className="field">
              <label htmlFor="email">
                Google account email <span className="hint">matches your Docs edits</span>
              </label>
              <input id="email" type="email" value={form.email} onChange={set("email")} />
            </div>
            <div className="field">
              <label htmlFor="gh">
                GitHub username <span className="hint">optional</span>
              </label>
              <input id="gh" type="text" value={form.githubLogin} onChange={set("githubLogin")} />
            </div>
          </div>
          <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
            <legend style={{ fontWeight: 700, marginBottom: 8 }}>What may your twin learn from?</legend>
            <label className="check">
              <input type="checkbox" checked={consent.github} onChange={(e) => setConsent({ ...consent, github: e.target.checked })} />
              <span>My commits, pull requests and reviews in the team repo</span>
            </label>
            <label className="check">
              <input type="checkbox" checked={consent.drive} onChange={(e) => setConsent({ ...consent, drive: e.target.checked })} />
              <span>When I edit files in the team&apos;s Google Drive folder</span>
            </label>
            <p className="faint" style={{ marginTop: 8 }}>
              Twins only share summaries with each other, never your raw activity. You can turn either off later.
            </p>
          </fieldset>
          <div className="row">
            <button className="btn" disabled={busy || !teamId}>
              {busy ? "Joining..." : "Join and take the quiz"}
            </button>
          </div>
        </form>
      </main>
    </>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Join />
    </Suspense>
  );
}
