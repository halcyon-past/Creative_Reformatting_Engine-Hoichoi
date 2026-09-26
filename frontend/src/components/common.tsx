import clsx from "clsx";
import type { RuleOutcome, VariantStatus } from "../api/types";

export function VerdictChip({
  verdict,
  status,
}: {
  verdict: "pass" | "fail" | null;
  status?: VariantStatus;
}) {
  if (status && ["pending", "rendering", "validating"].includes(status)) {
    return <span className="chip bg-sky-500/15 text-sky-300">{status}…</span>;
  }
  if (verdict === "pass") {
    return <span className="chip bg-emerald-500/15 text-emerald-300">PASS</span>;
  }
  if (verdict === "fail") {
    return <span className="chip bg-rose-500/15 text-rose-300">FAIL</span>;
  }
  return <span className="chip bg-slate-500/15 text-slate-400">no report</span>;
}

export function OutcomeChip({ outcome }: { outcome: RuleOutcome }) {
  const style: Record<RuleOutcome, string> = {
    pass: "bg-emerald-500/15 text-emerald-300",
    fail: "bg-rose-500/15 text-rose-300",
    warn: "bg-amber-500/15 text-amber-300",
    skip: "bg-slate-500/15 text-slate-400",
  };
  return <span className={clsx("chip w-14 justify-center", style[outcome])}>{outcome}</span>;
}

export function RatioBadge({ ratio }: { ratio: string }) {
  return (
    <span className="chip bg-ink-700 font-mono text-slate-300 ring-1 ring-ink-600">
      {ratio}
    </span>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-sm text-slate-400">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-ink-600 border-t-accent" />
      {label}
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="card border-rose-500/40 bg-rose-500/5 p-4 text-sm text-rose-300">
      {message}
    </div>
  );
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="card border-dashed p-10 text-center">
      <p className="text-slate-300">{title}</p>
      {hint && <p className="mt-1 text-sm text-slate-500">{hint}</p>}
    </div>
  );
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return "—";
  const mb = bytes / (1024 * 1024);
  return mb >= 1 ? `${mb.toFixed(2)} MB` : `${(bytes / 1024).toFixed(0)} KB`;
}

export function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-700">
      <div
        className="h-full rounded-full bg-accent transition-all duration-300"
        style={{ width: `${Math.round(value * 100)}%` }}
      />
    </div>
  );
}
