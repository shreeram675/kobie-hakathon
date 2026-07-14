"use client";

import { cn } from "@/lib/format";
import {
  CATEGORY_ORDER,
  CATEGORY_LABELS,
  FOCUSED_SCHEMA_FIELD_PATHS,
  type Category,
} from "@/lib/schema";
import type { FieldReport, FieldReportEntry } from "@/lib/types";

interface Props {
  programName: string | null;
  fieldReport?: FieldReport | null;
}

export function SingleProgramBriefPanel({ programName, fieldReport }: Props) {
  const entries: FieldReportEntry[] = fieldReport?.entries ?? [];

  // Per-category coverage stats (focused schema fields only)
  const categoryStats = CATEGORY_ORDER.map((cat) => {
    const focused = entries.filter(
      (e) => e.field_path.startsWith(cat + ".") && FOCUSED_SCHEMA_FIELD_PATHS.has(e.field_path),
    );
    const extracted = focused.filter((e) => e.status === "extracted").length;
    const total = focused.length;
    const pct = total > 0 ? Math.round((extracted / total) * 100) : 0;
    return { cat, label: CATEGORY_LABELS[cat as Category], extracted, total, pct };
  }).filter((s) => s.total > 0);

  return (
    <div className="space-y-4">
      {/* ── Category coverage grid ───────────────────────────────────────────── */}
      {categoryStats.length > 0 && (
        <div>
          <h2 className="mb-3 text-base font-semibold text-navy">Coverage by category</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {categoryStats.map(({ cat, label, extracted, total, pct }) => (
              <div key={cat} className="rounded-card border border-line bg-white p-3 shadow-sm">
                <p className="text-[10px] font-medium uppercase tracking-wide text-ink/45 truncate">
                  {label}
                </p>
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-soft-grey">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all duration-500",
                      pct >= 80 ? "bg-green" : pct >= 50 ? "bg-teal" : "bg-amber",
                    )}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="mt-1.5 flex items-center justify-between">
                  <span className="text-[11px] text-ink/50 tabular-nums">
                    {extracted}/{total}
                  </span>
                  <span
                    className={cn(
                      "text-[11px] font-semibold tabular-nums",
                      pct >= 80 ? "text-green" : pct >= 50 ? "text-teal" : "text-amber",
                    )}
                  >
                    {pct}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
