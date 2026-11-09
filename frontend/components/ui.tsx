"use client";

import Link from "next/link";
import type { Member } from "@/lib/api";
import { colorFor, initials } from "@/lib/people";

export function Logo({ size = 26 }: { size?: number }) {
  return (
    <svg width={size * 1.4} height={size} viewBox="0 0 42 30" aria-hidden="true">
      <circle cx="15" cy="15" r="13" fill="#2E46F0" />
      <circle cx="27" cy="15" r="13" fill="none" stroke="#2E46F0" strokeWidth="3" strokeDasharray="4 3" />
    </svg>
  );
}

export function TopBar({ right }: { right?: React.ReactNode }) {
  return (
    <header className="wrap topbar">
      <Link href="/" className="brand">
        <Logo /> WorkTwin
      </Link>
      <div className="row">{right}</div>
    </header>
  );
}

/** A member and their twin: solid circle with initials, softer echo behind it. */
export function TwinMark({ members, uid, twinOnly = false }: { members: Member[]; uid: string; twinOnly?: boolean }) {
  const m = members.find((x) => x.uid === uid);
  const c = colorFor(members, uid);
  if (!m) return null;
  return (
    <span className="twin-mark" aria-hidden="true">
      <span style={{ background: twinOnly ? c.soft : c.solid, color: twinOnly ? c.ink : "#fff" }}>{initials(m)}</span>
      <span style={{ background: c.soft, border: `2px dashed ${c.solid}` }} />
    </span>
  );
}

export function ErrorBox({ error }: { error: string | null }) {
  if (!error) return null;
  return (
    <p className="error" role="alert">
      {error}
    </p>
  );
}
