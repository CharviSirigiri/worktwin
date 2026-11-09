import type { Member } from "./api";

/**
 * Each member owns a soft pastel; their twin wears the paler echo of it.
 * solid: avatar / accent, soft: twin background, ink: readable text on either.
 */
export const PALETTE = [
  { solid: "#A895F7", soft: "#EFEBFF", ink: "#2E2170" }, // lavender
  { solid: "#EFA7BC", soft: "#FCEAF0", ink: "#5A1E33" }, // rose
  { solid: "#95B9E8", soft: "#E8F0FA", ink: "#1E3557" }, // sky
  { solid: "#93CDBA", soft: "#E5F5F0", ink: "#173F35" }, // sage
  { solid: "#EDCB80", soft: "#FDF4E0", ink: "#4A3510" }, // butter
  { solid: "#BCB0D3", soft: "#F1EEF7", ink: "#352B4A" }, // lilac grey
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
