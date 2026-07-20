"use client";

import { estimateTokens } from "@/lib/format";
import type { SemanticChunk } from "@/lib/types";

function tokensOf(chunk: SemanticChunk): number {
  return chunk.token_count ?? estimateTokens(chunk.chunk_text);
}

function quantile(sorted: number[], q: number): number {
  if (!sorted.length) return 0;
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return Math.round(sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo));
}

/**
 * What the chunker selected, and whether its output was evenly sized.
 *
 * The size stats collapse to one line when chunks are uniform (the common
 * case — the splitter targets a fixed token budget), and only expand into a
 * range track when there is real spread to look at.
 */
export function ChunkSummary({
  chunks,
  semanticCount,
  skippedCount,
}: {
  chunks: SemanticChunk[];
  semanticCount: number;
  skippedCount: number;
}) {
  if (!chunks.length) {
    return <p className="text-xs italic text-ink/40">No extraction chunks yet.</p>;
  }

  const sizes = chunks.map(tokensOf).sort((a, b) => a - b);
  const min = sizes[0];
  const max = sizes[sizes.length - 1];
  const median = quantile(sizes, 0.5);
  const avg = Math.round(sizes.reduce((s, n) => s + n, 0) / sizes.length);
  // Coefficient of variation: below ~15% the chunks are effectively one size
  // and a distribution plot would just be a flat line.
  const sd = Math.sqrt(sizes.reduce((s, n) => s + (n - avg) ** 2, 0) / sizes.length);
  const uniform = !avg || sd / avg < 0.15 || max === min;

  const selectedPct = semanticCount ? (chunks.length / semanticCount) * 100 : 0;

  return (
    <div className="space-y-4">
      {/* Which chunks survived the low-signal filter — the one real
          relationship in this stage. */}
      <div>
        <div className="flex h-2.5 overflow-hidden rounded-full bg-ink/8">
          <div
            className="bg-teal"
            style={{ width: `${selectedPct}%` }}
            title={`${chunks.length} chunks sent to extraction`}
          />
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-teal" aria-hidden />
            <span className="tabular-nums font-semibold text-ink/75">{chunks.length}</span>
            <span className="text-ink/50">sent to extraction</span>
            <span className="tabular-nums text-ink/35">({Math.round(selectedPct)}%)</span>
          </span>
          {skippedCount > 0 && (
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-ink/15" aria-hidden />
              <span className="tabular-nums font-semibold text-ink/75">{skippedCount}</span>
              <span className="text-ink/50">skipped as low-signal</span>
            </span>
          )}
        </div>
      </div>

      {uniform ? (
        <p className="border-t border-line pt-3 text-xs text-ink/50">
          Uniform sizing —{" "}
          <span className="tabular-nums font-semibold text-ink/75">
            {min === max ? `${min}` : `${min}–${max}`} tokens
          </span>{" "}
          per chunk.
        </p>
      ) : (
        <div className="border-t border-line pt-3">
          <div className="relative h-2 rounded-full bg-ink/8">
            <div
              className="absolute inset-y-0 rounded-full bg-teal/25"
              style={{
                left: `${((quantile(sizes, 0.25) - min) / (max - min)) * 100}%`,
                right: `${100 - ((quantile(sizes, 0.75) - min) / (max - min)) * 100}%`,
              }}
            />
            <span
              className="absolute top-1/2 h-3.5 w-[2px] -translate-y-1/2 rounded-full bg-teal"
              style={{ left: `${((median - min) / (max - min)) * 100}%` }}
              title={`median ${median} tokens`}
            />
          </div>
          <div className="mt-1.5 flex justify-between text-[10.5px] tabular-nums text-ink/45">
            <span>{min}</span>
            <span className="text-ink/60">median {median} tokens</span>
            <span>{max}</span>
          </div>
        </div>
      )}
    </div>
  );
}
