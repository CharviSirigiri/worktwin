import type { Member } from "./api";

/** Each member owns a colour; their twin wears the soft echo of it. */
// `on` is the readable text colour on top of `solid`.
export const PALETTE = [
  { solid: "#FF7A3D", soft: "#FFE3D4", ink: "#3A1600", on: "#2B1000" },
  { solid: "#14A39A", soft: "#CDEFEC", ink: "#00302C", on: "#00211E" },
  { solid: "#7B5CFF", soft: "#E3DCFF", ink: "#1C0F5C", on: "#FFFFFF" },
  { solid: "#E5487A", soft: "#FADAE4", ink: "#4A0019", on: "#FFFFFF" },
  { solid: "#2E9BE6", soft: "#D3EAFA", ink: "#002E4D", on: "#001F33" },
  { solid: "#C9A400", soft: "#F5ECC2", ink: "#3A2F00", on: "#2B2300" },
];

export function colorFor(members: Member[], uid: string) {
  const i = Math.max(0, members.findIndex((m) => m.uid === uid));
  return PALETTE[i % PALETTE.length];
}

export function initials(m: Member) {
  const parts = (m.shortName || m.name).split(/\s+/).filter(Boolean);
  return (parts[0]?.[0] || "?") + (parts[1]?.[0] || "");
}

export function fmtDate(iso: string) {
  const d = new Date(iso.slice(0, 10) + "T00:00:00");
  return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
}

export function daysLeft(iso: string) {
  const d = new Date(iso.slice(0, 10) + "T23:59:59").getTime();
  return Math.ceil((d - Date.now()) / 86400000);
}

const SLOT_DAY: Record<string, string> = { AM: "morning", PM: "afternoon", EVE: "evening" };
export function slotLabel(slot: string) {
  const [d, p] = slot.split("-");
  return `${d} ${SLOT_DAY[p] || p}`;
}
