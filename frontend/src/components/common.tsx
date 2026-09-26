import clsx from "clsx";
import type { RuleOutcome, VariantStatus } from "../api/types";

/* ==========================================================================
   Shared primitives.
   These show up on every screen, so they carry most of the personality.
   Rule of thumb throughout: black border, offset shadow, flat colour, and
   anything interactive physically moves.
   ======================================================================= */

const IN_FLIGHT: VariantStatus[] = ["pending", "rendering", "validating"];

export function VerdictChip({
  verdict,
  status,
}: {
  verdict: "pass" | "fail" | null;
  status?: VariantStatus;
}) {
  if (status && IN_FLIGHT.includes(status)) {
    return (
      <span className="chip bg-pop-cyan text-black">
        <span className="inline-block h-1.5 w-1.5 animate-blink rounded-full bg-black" />
        {status}
      </span>
    );
  }
  if (verdict === "pass") {
    return <span className="chip bg-pop-lime text-black">✓ pass</span>;
  }
  if (verdict === "fail") {
    return <span className="chip animate-wiggle bg-pop-red text-white">✕ fail</span>;
  }
  return <span className="chip bg-ink-950 text-slate-500">— no report</span>;
}

export function OutcomeChip({ outcome }: { outcome: RuleOutcome }) {
  const style: Record<RuleOutcome, string> = {
    pass: "bg-pop-lime text-black",
    fail: "bg-pop-red text-white",
    warn: "bg-pop-yellow text-black",
    skip: "bg-ink-950 text-slate-500",
  };
  const glyph: Record<RuleOutcome, string> = {
    pass: "✓", fail: "✕", warn: "!", skip: "–",
  };
  return (
    <span className={clsx("chip w-16 justify-center", style[outcome])}>
      {glyph[outcome]} {outcome}
    </span>
  );
}

export function RatioBadge({ ratio }: { ratio: string }) {
  // Each ratio gets its own colour so the grid is scannable by hue alone.
  const tint: Record<string, string> = {
    "16:9": "bg-pop-cyan",
    "1:1": "bg-pop-yellow",
    "9:16": "bg-pop-pink text-white",
    "4:5": "bg-pop-lime",
  };
  return (
    <span className={clsx("chip font-mono text-black", tint[ratio] ?? "bg-pop-purple")}>
      {ratio}
    </span>
  );
}

/** Blocky bouncing squares — a spinning ring would be off-language. */
export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex gap-1">
        {["bg-pop-pink", "bg-pop-yellow", "bg-pop-cyan"].map((c, i) => (
          <span
            key={c}
            className={clsx("h-3 w-3 animate-bounce-sm border-2 border-ink-600", c)}
            style={{ animationDelay: `${i * 0.14}s` }}
          />
        ))}
      </div>
      {label && (
        <span className="text-sm font-bold uppercase tracking-wide text-slate-400">
          {label}
        </span>
      )}
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="animate-pop-in rounded-brutal border-3 border-ink-600 bg-pop-red shadow-brutal">
      <div className="flex items-center gap-2 border-b-3 border-ink-600 bg-black px-3 py-1">
        <span className="text-sm">💥</span>
        <span className="text-[11px] font-extrabold uppercase tracking-[0.15em] text-pop-yellow">
          something broke
        </span>
      </div>
      <p className="px-3 py-2.5 font-mono text-sm font-bold text-white">{message}</p>
    </div>
  );
}

export function Empty({
  title,
  hint,
  emoji = "🗂️",
}: {
  title: string;
  hint?: string;
  emoji?: string;
}) {
  return (
    <div className="card halftone flex flex-col items-center px-6 py-12 text-center">
      <div className="mb-3 flex h-16 w-16 rotate-3 items-center justify-center rounded-brutal border-3 border-ink-600 bg-pop-yellow text-3xl shadow-brutal">
        {emoji}
      </div>
      <p className="font-display text-lg text-slate-100">{title}</p>
      {hint && <p className="mt-1 max-w-sm text-sm font-medium text-slate-400">{hint}</p>}
    </div>
  );
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return "—";
  const mb = bytes / (1024 * 1024);
  return mb >= 1 ? `${mb.toFixed(2)} MB` : `${(bytes / 1024).toFixed(0)} KB`;
}

/**
 * Chunky progress bar with moving hazard stripes, so "working" is obvious
 * from across the room and never reads as a stalled solid block.
 */
export function ProgressBar({ value, label }: { value: number; label?: string }) {
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  return (
    <div className="space-y-1">
      {label && (
        <div className="flex items-baseline justify-between">
          <span className="text-[11px] font-extrabold uppercase tracking-wider text-slate-400">
            {label}
          </span>
          <span className="font-mono text-xs font-bold text-slate-200">{pct}%</span>
        </div>
      )}
      <div className="h-5 w-full overflow-hidden rounded-brutal border-3 border-ink-600 bg-ink-950">
        <div
          className="stripes-live h-full animate-stripes border-r-3 border-ink-600 transition-[width] duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/** Black bar with yellow caps — the standard section heading. */
export function SectionTitle({
  children,
  tone = "yellow",
  right,
}: {
  children: React.ReactNode;
  tone?: "yellow" | "pink" | "cyan" | "lime";
  right?: React.ReactNode;
}) {
  const text = {
    yellow: "text-pop-yellow",
    pink: "text-pop-pink",
    cyan: "text-pop-cyan",
    lime: "text-pop-lime",
  }[tone];
  return (
    <div className="flex items-center justify-between gap-3">
      <h3
        className={clsx(
          "inline-block rounded-brutal border-3 border-ink-600 bg-black px-3 py-1",
          "text-xs font-extrabold uppercase tracking-[0.14em] shadow-brutal-sm",
          text,
        )}
      >
        {children}
      </h3>
      {right}
    </div>
  );
}

/** Small key/value pair used across the metadata strips. */
export function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  tone?: string;
}) {
  return (
    <div className="rounded-brutal border-[2.5px] border-ink-600 bg-ink-800 px-2 py-1 shadow-brutal-sm">
      <div className="text-[9px] font-extrabold uppercase tracking-[0.12em] text-slate-500">
        {label}
      </div>
      <div className={clsx("font-mono text-sm font-bold", tone ?? "text-slate-100")}>
        {value}
      </div>
    </div>
  );
}
