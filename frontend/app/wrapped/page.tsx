"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { ErrorBox } from "@/components/ui";
import { api, type Member, type Slide, type TeamView, type Wrapped } from "@/lib/api";
import { colorFor } from "@/lib/people";

const SLIDE_MS = 7000;
const NAVY = "#1A2340";
const COBALT = "#2E46F0";

function colorsFor(slide: Slide, members: Member[]) {
  if (slide.kind === "member" && slide.uid) {
    const c = colorFor(members, slide.uid);
    return { bg: c.solid, fg: c.on };
  }
  if (slide.kind === "intro" || slide.kind === "outro") return { bg: COBALT, fg: "#fff" };
  return { bg: NAVY, fg: "#fff" };
}

function useReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const q = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(q.matches);
  }, []);
  return reduced;
}

function SlideBody({ slide, members, reflections }: { slide: Slide; members: Member[]; reflections: Record<string, string> }) {
  const [open, setOpen] = useState<string | null>(null);
  if (slide.kind === "mix" && slide.bars) {
    const max = Math.max(...slide.bars.map((b) => b.share), 0.01);
    return (
      <>
        <p className="title">{slide.title}</p>
        <p className="unit" style={{ marginTop: 6 }}>{slide.unit}</p>
        <div className="mixbars">
          {slide.bars.map((b) => {
            const c = colorFor(members, b.uid);
            const w = (b.share / max) * 100;
            return (
              <div className="mixbar" key={b.uid}>
                <span>{b.name}</span>
                <div className="track" aria-label={`${b.name}: ${Math.round(b.share * 100)}% of team effort`}>
                  <div style={{ display: "flex", width: `${w}%` }}>
                    <i style={{ flex: b.mix.code, background: c.solid }} />
                    <i style={{ flex: b.mix.writing, background: c.solid, opacity: 0.62 }} />
                    <i style={{ flex: b.mix.coordination, background: c.solid, opacity: 0.32 }} />
                  </div>
                </div>
                <span style={{ textAlign: "right" }}>{Math.round(b.share * 100)}%</span>
              </div>
            );
          })}
        </div>
        <div className="legend" style={{ opacity: 0.85 }}>
          <span>Solid: code</span><span>Lighter: writing</span><span>Faintest: coordination</span>
        </div>
        <p className="caption">{slide.caption}</p>
      </>
    );
  }
  return (
    <>
      {slide.kind === "member" && <p className="unit" style={{ fontWeight: 700 }}>{slide.name}</p>}
      <p className="title">{slide.title}</p>
      {slide.big && <p className="big">{slide.big}</p>}
      {slide.unit && <p className="unit">{slide.unit}</p>}
      {slide.chips && (
        <div className="chips">
          {slide.chips.map((c) => <span key={c}>{c}</span>)}
        </div>
      )}
      <p className="caption">{slide.caption}</p>
      {slide.kind === "outro" && (
        <div style={{ marginTop: 28 }} onClick={(e) => e.stopPropagation()}>
          <p style={{ fontWeight: 700, marginBottom: 10 }}>A private note from your twin</p>
          <div className="row">
            {members.map((m) => (
              <button key={m.uid} className="pill" aria-pressed={open === m.uid} onClick={() => setOpen(open === m.uid ? null : m.uid)}>
                {m.shortName}
              </button>
            ))}
          </div>
          {open && (
            <p style={{ marginTop: 14, maxWidth: "52ch", background: "rgba(255,255,255,0.16)", padding: "14px 18px", borderRadius: 14 }}>
              {reflections[open]}
            </p>
          )}
        </div>
      )}
    </>
  );
}

function WrappedPage() {
  const params = useSearchParams();
  const id = params.get("id") || "";
  const [view, setView] = useState<TeamView | null>(null);
  const [data, setData] = useState<Wrapped | null>(null);
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const reduced = useReducedMotion();

  useEffect(() => {
    if (!id) return;
    Promise.all([api<TeamView>(`/teams/${id}`), api<Wrapped>(`/teams/${id}/wrapped?refresh=true`)])
      .then(([v, w]) => {
        setView(v);
        setData(w);
      })
      .catch((e) => setError(e.message));
  }, [id]);

  const n = data?.slides.length || 0;
  const next = useCallback(() => setI((x) => Math.min(x + 1, n - 1)), [n]);
  const prev = useCallback(() => setI((x) => Math.max(x - 1, 0)), []);

  useEffect(() => {
    if (!data || !playing || reduced || i >= n - 1) return;
    const t = setTimeout(next, SLIDE_MS);
    return () => clearTimeout(t);
  }, [data, playing, reduced, i, n, next]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") next();
      if (e.key === "ArrowLeft") prev();
      if (e.key === " ") {
        e.preventDefault();
        setPlaying((p) => !p);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, prev]);

  if (error) return <main className="wrap page"><ErrorBox error={error} /></main>;
  if (!data || !view) {
    return (
      <div className="wrapped" style={{ background: COBALT, color: "#fff", alignItems: "center", justifyContent: "center" }}>
        <p className="title" style={{ fontFamily: "var(--display)", fontSize: "1.6rem" }}>Counting every commit...</p>
      </div>
    );
  }

  const slide = data.slides[i];
  const { bg, fg } = colorsFor(slide, view.members);
  const autoplay = playing && !reduced;

  return (
    <div className="wrapped" style={{ background: bg, color: fg }}>
      <div className="bars" aria-hidden="true">
        {data.slides.map((s, k) => (
          <span key={s.id}>
            <i
              key={`${k}-${i}-${autoplay}`}
              style={{
                width: k < i ? "100%" : k === i && !autoplay ? "100%" : "0%",
                background: fg,
                animation: k === i && autoplay && i < n - 1 ? `fill ${SLIDE_MS}ms linear forwards` : undefined,
              }}
            />
          </span>
        ))}
      </div>
      <style>{`@keyframes fill { from { width: 0% } to { width: 100% } }`}</style>

      <button className="tap left" aria-label="Previous slide" onClick={prev} />
      <button className="tap right" aria-label="Next slide" onClick={next} />

      <section key={slide.id} className="stage slide-in" aria-live="polite" style={{ position: "relative", zIndex: 1, pointerEvents: "none" }}>
        <div style={{ pointerEvents: "auto", maxWidth: "100%" }}>
          <SlideBody slide={slide} members={view.members} reflections={data.reflections} />
        </div>
      </section>

      <nav className="nav" style={{ position: "relative", zIndex: 2 }}>
        <Link className="btn small" href={`/team/?id=${id}`} style={{ color: fg }}>Close</Link>
        <div className="row">
          {!reduced && (
            <button className="btn small" onClick={() => setPlaying((p) => !p)} style={{ color: fg }}>
              {playing ? "Pause" : "Play"}
            </button>
          )}
          <button className="btn small" onClick={prev} disabled={i === 0} style={{ color: fg }}>Back</button>
          <button className="btn small" onClick={next} disabled={i === n - 1} style={{ color: fg }}>Next</button>
        </div>
      </nav>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense>
      <WrappedPage />
    </Suspense>
  );
}
