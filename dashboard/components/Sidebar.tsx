"use client";

import { NavGlyph, UiGlyph } from "@/components/Icons";
import { NAV, NavId } from "@/lib/language";

/**
 * Primary navigation, pinned left, expanded by default.
 *
 * The emoji that used to sit here made an otherwise serious interface read as a
 * demo. A consistent stroke glyph system plus a lit active rail makes the whole
 * shell look built rather than assembled.
 */
export function Sidebar({
  active,
  onSelect,
  open,
  onToggle,
  badge,
  live,
  simTime,
}: {
  active: NavId;
  onSelect: (n: NavId) => void;
  open: boolean;
  onToggle: () => void;
  badge?: number;
  live?: boolean;
  simTime?: string;
}) {
  return (
    <nav
      aria-label="Main"
      className={`fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-white/[0.06] bg-ink-1000/92 backdrop-blur-xl transition-[width] duration-300 ${
        open ? "w-[248px]" : "w-[68px]"
      }`}
    >
      {/* brand */}
      <div className="flex items-center gap-2.5 border-b border-white/[0.06] px-4 py-3.5">
        <span
          className="grid h-7 w-7 shrink-0 place-items-center rounded-md border border-sig-500/40 bg-sig-500/12 font-mono text-[10px] font-bold tracking-tight text-sig-400"
          style={{ boxShadow: "0 0 18px -6px rgba(45,212,191,0.7)" }}
        >
          AD
        </span>
        {open && (
          <div className="min-w-0 flex-1">
            <div className="truncate text-[12.5px] font-semibold tracking-tight text-slate-100">
              Adrar Farm
            </div>
            <div className="truncate text-[9.5px] text-slate-600">Adrar, Algeria</div>
          </div>
        )}
        {open && (
          <span
            className="flex shrink-0 items-center gap-1 text-[9px] font-bold uppercase tracking-[0.12em] text-sig-400"
            title={live ? "Receiving live data" : "Not connected"}
          >
            <span className="relative flex h-1.5 w-1.5">
              <span
                className={`absolute inline-flex h-full w-full animate-ping rounded-full ${
                  live ? "bg-sig-400" : "bg-slate-600"
                } opacity-70`}
              />
              <span
                className={`relative inline-flex h-1.5 w-1.5 rounded-full ${
                  live ? "bg-sig-400" : "bg-slate-600"
                }`}
              />
            </span>
            {live ? "live" : "off"}
          </span>
        )}
      </div>

      {/* destinations */}
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {NAV.map((n) => {
          const isActive = active === n.id;
          return (
            <button
              key={n.id}
              onClick={() => onSelect(n.id)}
              aria-current={isActive ? "page" : undefined}
              title={open ? undefined : n.label}
              className={`group relative mb-0.5 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition ${
                isActive
                  ? "bg-sig-500/10 text-slate-50"
                  : "text-slate-400 hover:bg-white/[0.03] hover:text-slate-200"
              }`}
            >
              {/* lit active rail */}
              {isActive && (
                <span
                  className="absolute inset-y-1.5 left-0 w-[2px] rounded-full bg-sig-400"
                  style={{ boxShadow: "0 0 12px rgba(45,212,191,0.8)" }}
                  aria-hidden
                />
              )}
              <span
                className={`w-5 shrink-0 transition ${
                  isActive ? "text-sig-400" : "text-slate-600 group-hover:text-slate-400"
                }`}
                aria-hidden
              >
                <NavGlyph id={n.id} className="h-[17px] w-[17px]" />
              </span>
              {open && (
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[12.5px] font-medium leading-tight">
                    {n.label}
                  </span>
                  <span className="block truncate text-[9.5px] text-slate-600">{n.sub}</span>
                </span>
              )}
              {n.id === "decisions" && badge && badge > 0 && (
                <span
                  className="absolute right-2 top-2 h-2 w-2 animate-pulse-dot rounded-full bg-fuchsia-400"
                  style={{ boxShadow: "0 0 8px #e879f9" }}
                />
              )}
            </button>
          );
        })}
      </div>

      {/* footer: live sim clock + collapse */}
      <div className="border-t border-white/[0.06]">
        {open && simTime && (
          <div className="flex items-center justify-between px-4 py-2 text-[9.5px] text-slate-600">
            <span className="font-semibold uppercase tracking-[0.12em]">sim clock</span>
            <span className="metric text-slate-500">{simTime}</span>
          </div>
        )}
        <button
          onClick={onToggle}
          aria-label={open ? "Collapse the menu" : "Expand the menu"}
          className="flex w-full items-center gap-3 px-4 py-3 text-slate-600 transition hover:bg-white/[0.03] hover:text-slate-300"
        >
          <span className="w-5 shrink-0 text-center" aria-hidden>
            <UiGlyph
              name={open ? "chevronLeft" : "chevronRight"}
              className="mx-auto h-3.5 w-3.5"
              strokeWidth={2}
            />
          </span>
          {open && <span className="text-[11px]">Collapse</span>}
        </button>
      </div>
    </nav>
  );
}
