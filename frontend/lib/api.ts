export const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080").replace(/\/$/, "");

export type Profile = {
  summary: string;
  bestTime: string;
  rhythm: string;
  peakHours: number[];
  strengths: string[];
  avoid: string[];
  channel: string;
  reply: string;
  meetings: string;
  availability: string[];
  stuck: string;
  traits: string[];
  evidence: string;
  dataBacked: boolean;
};

export type Member = {
  uid: string;
  name: string;
  shortName: string;
  githubLogin: string;
  hasEmail: boolean;
  quizDone: boolean;
  profile: Profile | null;
  nfcCard: boolean;
};

export type Charter = {
  roles: { uid: string; role: string; why: string }[];
  meetings: { slot: string; label: string; why: string }[];
  internalDeadlines: { uid: string; date: string; why: string }[];
  norms: string[];
  summary: string;
  acceptedBy: string[];
};

export type Team = {
  id: string;
  name: string;
  module: string;
  brief: string;
  startDate: string;
  deadline: string;
  repo: string;
  driveFolderId: string;
  workstreams: string[];
  demo?: boolean;
};

export type TeamView = {
  team: Team;
  members: Member[];
  charter: Charter | null;
  activityCount: number;
  currentWeek: number;
  lastUnknownCard: string | null;
};

export type RoomMessage = { type: "message"; speaker: string; name: string; text: string; round: number };

export type Question = {
  id: string;
  text: string;
  type: "single" | "multi" | "slots" | "text";
  max?: number;
  private?: boolean;
  options?: { value: string; label: string }[];
};

export type Retro = {
  week: number;
  from: string;
  to: string;
  stats: Record<string, { name: string; events: number; share: number; activeDays: number; meetings: number }>;
  nudges: Record<string, string>;
  teamSuggestion: string;
};

export type Slide = {
  id: string;
  kind: "intro" | "stat" | "member" | "mix" | "outro";
  title: string;
  big?: string;
  unit?: string;
  chips?: string[];
  caption: string;
  uid?: string;
  name?: string;
  archetype?: string;
  bars?: { uid: string; name: string; share: number; mix: { code: number; writing: number; coordination: number } }[];
};

export type Wrapped = { slides: Slide[]; archetypes: Record<string, string>; reflections: Record<string, string> };

export class ApiError extends Error {}

export async function api<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init || {};
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, {
      ...rest,
      headers: { ...(json !== undefined ? { "Content-Type": "application/json" } : {}), ...(rest.headers || {}) },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });
  } catch {
    throw new ApiError(`Can't reach the WorkTwin server at ${API}. Check it is running.`);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {}
    throw new ApiError(detail);
  }
  return res.json() as Promise<T>;
}

/** Streams the twins' meeting. Calls onItem for each message, the charter, and done/error. */
export async function streamRoom(teamId: string, onItem: (item: any) => void): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API}/teams/${teamId}/room/start`, { method: "POST" });
  } catch {
    throw new ApiError(`Can't reach the WorkTwin server at ${API}.`);
  }
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail;
    } catch {}
    throw new ApiError(detail);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let nl;
    while ((nl = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, nl).trim();
      buffer = buffer.slice(nl + 1);
      if (line) onItem(JSON.parse(line));
    }
  }
  if (buffer.trim()) onItem(JSON.parse(buffer));
}

/** Remembers which member this browser is, per team. Falls back silently if storage is blocked. */
export const me = {
  get(teamId: string): string | null {
    try {
      return localStorage.getItem(`worktwin:${teamId}`);
    } catch {
      return null;
    }
  },
  set(teamId: string, uid: string) {
    try {
      localStorage.setItem(`worktwin:${teamId}`, uid);
    } catch {}
  },
};
