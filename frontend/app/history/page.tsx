"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  Database,
  GitCompareArrows,
  History,
  LayoutList,
  Loader2,
  Search,
  SlidersHorizontal,
  Sparkles,
  X,
} from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { Badge, type Tone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/textarea";
import { useRunHistory } from "@/lib/hooks";
import { cn, pct, relativeTime, truncate, formatDateTime } from "@/lib/format";
import type { RunHistoryEntry, RunMode } from "@/lib/types";

type TypeFilter = "all" | "normal" | "compare";
type StatusFilter = "all" | RunHistoryEntry["status"];
type QualityFilter = "all" | "high" | "medium" | "low" | "unknown";
type SourceFilter = "all" | "db" | "live";
type SortKey = "newest" | "oldest" | "quality_desc" | "quality_asc" | "name_asc" | "mode";

const MODE_TONE: Record<RunMode, Tone> = {
  single: "teal",
  compare: "blue",
  converse: "teal",
};

const STATUS_TONE: Record<RunHistoryEntry["status"], Tone> = {
  done: "green",
  running: "teal",
  error: "red",
  clarification_needed: "blue",
  cancelled: "amber",
};

const STATUS_LABEL: Record<RunHistoryEntry["status"], string> = {
  done: "Complete",
  running: "Running",
  error: "Error",
  clarification_needed: "Needs clarification",
  cancelled: "Stopped",
};

function analysisType(mode: RunMode): TypeFilter {
  return mode === "compare" ? "compare" : "normal";
}

function modeLabel(mode: RunMode): string {
  return mode === "compare" ? "Compare" : "Normal Analyse";
}

function displayName(run: RunHistoryEntry): string {
  return run.program_name || run.user_input || "Untitled analysis";
}

function detailHref(run: RunHistoryEntry): string {
  return run.mode === "compare" ? `/run/${run.run_id}/compare` : `/run/${run.run_id}`;
}

function qualityBucket(value: number): QualityFilter {
  if (!value) return "unknown";
  if (value >= 0.7) return "high";
  if (value >= 0.4) return "medium";
  return "low";
}

function qualityClass(value: number): string {
  if (!value) return "bg-soft-grey text-ink/45";
  if (value >= 0.7) return "bg-soft-green text-green";
  if (value >= 0.4) return "bg-soft-amber text-amber";
  return "bg-soft-red text-red";
}

export default function HistoryPage() {
  const { data: runs = [], isLoading, isError, refetch } = useRunHistory();
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [qualityFilter, setQualityFilter] = useState<QualityFilter>("all");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [sortKey, setSortKey] = useState<SortKey>("newest");

  const stats = useMemo(() => {
    const normal = runs.filter((run) => analysisType(run.mode) === "normal").length;
    const compare = runs.filter((run) => run.mode === "compare").length;
    const complete = runs.filter((run) => run.status === "done").length;
    const avgQuality =
      complete > 0
        ? runs
            .filter((run) => run.status === "done")
            .reduce((sum, run) => sum + (run.data_quality || 0), 0) / complete
        : 0;
    return { total: runs.length, normal, compare, complete, avgQuality };
  }, [runs]);

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return runs
      .filter((run) => {
        const haystack = [
          run.run_id,
          run.user_input,
          run.program_name ?? "",
          modeLabel(run.mode),
          run.status,
        ]
          .join(" ")
          .toLowerCase();
        if (normalizedQuery && !haystack.includes(normalizedQuery)) return false;
        if (typeFilter !== "all" && analysisType(run.mode) !== typeFilter) return false;
        if (statusFilter !== "all" && run.status !== statusFilter) return false;
        if (qualityFilter !== "all" && qualityBucket(run.data_quality) !== qualityFilter) return false;
        if (sourceFilter !== "all" && run.source !== sourceFilter) return false;
        return true;
      })
      .sort((a, b) => {
        if (sortKey === "oldest") {
          return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        }
        if (sortKey === "quality_desc") return (b.data_quality || 0) - (a.data_quality || 0);
        if (sortKey === "quality_asc") return (a.data_quality || 0) - (b.data_quality || 0);
        if (sortKey === "name_asc") return displayName(a).localeCompare(displayName(b));
        if (sortKey === "mode") return modeLabel(a.mode).localeCompare(modeLabel(b.mode));
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      });
  }, [qualityFilter, query, runs, sortKey, sourceFilter, statusFilter, typeFilter]);

  const hasFilters =
    query ||
    typeFilter !== "all" ||
    statusFilter !== "all" ||
    qualityFilter !== "all" ||
    sourceFilter !== "all" ||
    sortKey !== "newest";

  function clearFilters() {
    setQuery("");
    setTypeFilter("all");
    setStatusFilter("all");
    setQualityFilter("all");
    setSourceFilter("all");
    setSortKey("newest");
  }

  return (
    <div className="min-h-screen bg-canvas">
      <Topbar>
        <Link href="/">
          <Button size="sm" variant="outline">
            <ArrowLeft className="h-4 w-4" />
            New analysis
          </Button>
        </Link>
      </Topbar>

      <main className="mx-auto max-w-7xl px-5 py-7">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-teal">
              <History className="h-3.5 w-3.5" />
              Analysis Library
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-navy">
              Previous analyses
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-ink/55">
              Search, filter, sort, and reopen completed loyalty intelligence runs.
            </p>
          </div>
          <Button size="sm" variant="outline" onClick={() => refetch()} disabled={isLoading}>
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />}
            Refresh
          </Button>
        </div>

        <section className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard icon={LayoutList} label="Total analyses" value={String(stats.total)} />
          <StatCard icon={Sparkles} label="Normal analyses" value={String(stats.normal)} />
          <StatCard icon={GitCompareArrows} label="Compare analyses" value={String(stats.compare)} />
          <StatCard icon={CheckCircle2} label="Avg. quality" value={stats.complete ? pct(stats.avgQuality) : "-"} />
        </section>

        <section className="mb-5 rounded-[12px] border border-line bg-white p-4 shadow-panel">
          <div className="grid gap-3 lg:grid-cols-[minmax(220px,1fr)_auto_auto_auto_auto]">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink/30" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search program, input, run id..."
                className="pl-9"
              />
            </label>

            <Select label="Type" value={typeFilter} onChange={(value) => setTypeFilter(value as TypeFilter)}>
              <option value="all">All types</option>
              <option value="normal">Normal Analyse</option>
              <option value="compare">Compare</option>
            </Select>

            <Select label="Status" value={statusFilter} onChange={(value) => setStatusFilter(value as StatusFilter)}>
              <option value="all">All statuses</option>
              <option value="done">Complete</option>
              <option value="running">Running</option>
              <option value="error">Error</option>
              <option value="clarification_needed">Needs clarification</option>
              <option value="cancelled">Stopped</option>
            </Select>

            <Select label="Quality" value={qualityFilter} onChange={(value) => setQualityFilter(value as QualityFilter)}>
              <option value="all">All quality</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="unknown">Unknown</option>
            </Select>

            <Select label="Sort" value={sortKey} onChange={(value) => setSortKey(value as SortKey)}>
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="quality_desc">Quality high to low</option>
              <option value="quality_asc">Quality low to high</option>
              <option value="name_asc">Name A-Z</option>
              <option value="mode">Type</option>
            </Select>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-ink/45">
              <SlidersHorizontal className="h-3.5 w-3.5" />
              Showing {filtered.length} of {runs.length}
            </span>
            <Select
              label="Source"
              value={sourceFilter}
              onChange={(value) => setSourceFilter(value as SourceFilter)}
              compact
            >
              <option value="all">All sources</option>
              <option value="db">Database</option>
              <option value="live">Live session</option>
            </Select>
            {hasFilters && (
              <button
                onClick={clearFilters}
                className="ml-auto inline-flex items-center gap-1.5 rounded-pill border border-line bg-white px-3 py-1.5 text-xs font-medium text-ink/55 transition hover:bg-soft-grey hover:text-navy"
              >
                <X className="h-3.5 w-3.5" />
                Clear
              </button>
            )}
          </div>
        </section>

        <section className="overflow-hidden rounded-[12px] border border-line bg-white shadow-panel">
          <div className="hidden grid-cols-[1.5fr_150px_140px_130px_100px] gap-4 border-b border-line bg-soft-grey/50 px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wide text-ink/45 lg:grid">
            <span>Analysis</span>
            <span>Type</span>
            <span>Status</span>
            <span>Quality</span>
            <span />
          </div>

          {isLoading ? (
            <StateBlock icon={Loader2} title="Loading analyses..." spinning />
          ) : isError ? (
            <StateBlock icon={Database} title="History is unavailable" text="The backend history endpoint could not be reached." />
          ) : filtered.length === 0 ? (
            <StateBlock
              icon={Search}
              title={runs.length === 0 ? "No analyses yet" : "No matching analyses"}
              text={runs.length === 0 ? "Run a normal analysis or comparison and it will appear here." : "Try adjusting the search or filters."}
            />
          ) : (
            <ul className="divide-y divide-line">
              {filtered.map((run) => (
                <HistoryRow key={`${run.source ?? "db"}-${run.run_id}`} run={run} />
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}

function HistoryRow({ run }: { run: RunHistoryEntry }) {
  const isCompare = run.mode === "compare";
  const Icon = isCompare ? GitCompareArrows : Sparkles;
  return (
    <li>
      <Link
        href={detailHref(run)}
        className="group grid gap-3 px-4 py-4 transition hover:bg-soft-grey/35 lg:grid-cols-[1.5fr_150px_140px_130px_100px] lg:items-center"
      >
        <div className="flex min-w-0 items-start gap-3">
          <span
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
              isCompare ? "bg-blue/10 text-blue" : "bg-teal/10 text-teal",
            )}
          >
            <Icon className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-navy">
              {truncate(displayName(run), 90)}
            </p>
            {run.program_name && run.program_name !== run.user_input && (
              <p className="mt-0.5 truncate text-xs text-ink/45">
                {truncate(run.user_input, 80)}
              </p>
            )}
            <div className="mt-1 space-y-0.5 text-[10px] text-ink/35">
              <p className="font-mono">{run.run_id.replace(/^run_/, "").slice(0, 12)}</p>
              <p className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-navy">
                  {formatDateTime(run.created_at)}
                </span>
                <span className="font-sans">.</span>
                <span className="inline-flex items-center gap-1 font-sans">
                  <Clock className="h-3 w-3" />
                  {relativeTime(run.created_at)}
                </span>
                {run.source && (
                  <>
                    <span className="font-sans">.</span>
                    <span className="font-sans capitalize">{run.source}</span>
                  </>
                )}
              </p>
            </div>
          </div>
        </div>

        <Badge tone={MODE_TONE[run.mode]} className="w-fit text-[10px]">
          {modeLabel(run.mode)}
        </Badge>

        <Badge tone={STATUS_TONE[run.status]} dot className="w-fit text-[10px]">
          {STATUS_LABEL[run.status]}
        </Badge>

        <span className={cn("inline-flex w-fit items-center rounded-pill px-2.5 py-1 text-[11px] font-semibold", qualityClass(run.data_quality))}>
          {run.data_quality ? pct(run.data_quality) : "No score"}
        </span>

        <span className="inline-flex items-center gap-1 text-xs font-semibold text-teal lg:justify-end">
          View details
          <ArrowUpRight className="h-4 w-4 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
        </span>
      </Link>
    </li>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof History;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-[10px] border border-line bg-white px-4 py-3 shadow-sm">
      <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-ink/45">
        <Icon className="h-3.5 w-3.5 text-teal" />
        {label}
      </div>
      <p className="mt-2 font-mono text-2xl font-semibold tabular-nums text-navy">{value}</p>
    </div>
  );
}

function Select({
  label,
  value,
  onChange,
  children,
  compact = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: React.ReactNode;
  compact?: boolean;
}) {
  return (
    <label className={cn("block", compact ? "w-auto" : "min-w-[150px]")}>
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={cn(
          "h-10 rounded-card border border-line bg-white px-3 text-sm text-ink shadow-sm transition focus:border-teal focus:outline-none focus:ring-2 focus:ring-teal/30",
          compact ? "w-auto text-xs" : "w-full",
        )}
      >
        {children}
      </select>
    </label>
  );
}

function StateBlock({
  icon: Icon,
  title,
  text,
  spinning = false,
}: {
  icon: typeof History;
  title: string;
  text?: string;
  spinning?: boolean;
}) {
  return (
    <div className="flex min-h-[280px] flex-col items-center justify-center px-5 text-center">
      <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-soft-grey">
        <Icon className={cn("h-5 w-5 text-ink/35", spinning && "animate-spin")} />
      </div>
      <p className="text-sm font-semibold text-navy">{title}</p>
      {text && <p className="mt-1 max-w-sm text-xs text-ink/45">{text}</p>}
    </div>
  );
}
