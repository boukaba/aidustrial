"use client";

import { NAV, NavId } from "@/lib/language";

export function Sidebar({
  active,
  onSelect,
  open,
  onToggle,
  badge,
}: {
  active: NavId;
  onSelect: (n: NavId) => void;
  open: boolean;
  onToggle: () => void;
  badge?: number;
}) {
  return (
    <>
      {/* Rail / expanded, pinned to the LEFT as the primary navigation. */}
      <nav
        aria-label="Main"
        className={`fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-ink-700 bg-ink-950/95 backdrop-blur transition-[width] duration-300 ${
          open ? "w-[248px]" : "w-[68px]"
        }`}
      >
        <div className="flex items-center gap-2.5 border-b border-ink-800 px-4 py-3.5">
          <span className="rounded bg-sig-600/15 px-1.5 py-0.5 text-[9px] font-bold tracking-widest text-sig-400">
            AID
          </span>
          {open && (
            <div className="min-w-0">
              <div className="truncate text-xs font-semibold text-slate-200">Adrar Farm</div>
              <div className="truncate text-[9px] text-slate-500">Algeria</div>
            </div>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-2">
          {NAV.map((n) => {
            const isActive = active === n.id;
            return (
              <button
                key={n.id}
                onClick={() => onSelect(n.id)}
                aria-current={isActive ? "page" : undefined}
                title={open ? undefined : n.label}
                className={`relative mb-0.5 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition ${
                  isActive
                    ? "bg-sig-500/12 text-sig-300"
                    : "text-slate-400 hover:bg-ink-900 hover:text-slate-200"
                }`}
              >
                <span className="w-5 shrink-0 text-center text-base" aria-hidden>
                  {n.icon}
                </span>
                {open && (
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-medium leading-tight">
                      {n.label}
                    </span>
                    <span className="block truncate text-[10px] text-slate-600">{n.sub}</span>
                  </span>
                )}
                {n.id === "decisions" && badge && badge > 0 && (
                  <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-fuchsia-500" />
                )}
              </button>
            );
          })}
        </div>

        <button
          onClick={onToggle}
          aria-label={open ? "Collapse the menu" : "Expand the menu"}
          className="flex items-center gap-3 border-t border-ink-800 px-4 py-3 text-slate-500 transition hover:text-slate-300"
        >
          <span className="w-5 shrink-0 text-center text-sm" aria-hidden>
            {open ? "«" : "»"}
          </span>
          {open && <span className="text-[11px]">Collapse</span>}
        </button>
      </nav>
    </>
  );
}