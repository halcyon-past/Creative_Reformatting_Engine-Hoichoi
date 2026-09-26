import { useState } from "react";
import type { ComplianceReport as Report, RuleResult } from "../api/types";
import { OutcomeChip } from "./common";

function Evidence({ evidence }: { evidence: Record<string, unknown> }) {
  const [open, setOpen] = useState(false);
  if (!evidence || Object.keys(evidence).length === 0) return null;
  return (
    <div className="mt-1">
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-[11px] text-slate-500 underline-offset-2 hover:text-slate-300 hover:underline"
      >
        {open ? "hide evidence" : "show evidence"}
      </button>
      {open && (
        <pre className="mt-1 max-h-56 overflow-auto rounded bg-ink-900 p-2 font-mono text-[11px] leading-relaxed text-slate-400">
          {JSON.stringify(evidence, null, 2)}
        </pre>
      )}
    </div>
  );
}

function Rule({ result }: { result: RuleResult }) {
  return (
    <li className="flex gap-3 border-t border-ink-700 py-2 first:border-t-0">
      <OutcomeChip outcome={result.outcome} />
      <div className="min-w-0 flex-1">
        <p className="text-sm text-slate-200">{result.title}</p>
        <p className="text-xs leading-relaxed text-slate-400">{result.message}</p>
        {(result.expected || result.actual) && (
          <p className="mt-0.5 font-mono text-[11px] text-slate-500">
            expected: {result.expected ?? "—"} · actual: {result.actual ?? "—"}
          </p>
        )}
        <Evidence evidence={result.evidence} />
      </div>
      <code className="shrink-0 self-start text-[10px] text-slate-600">{result.rule_id}</code>
    </li>
  );
}

export default function ComplianceReportView({ report }: { report: Report }) {
  const counts = report.results.reduce<Record<string, number>>((acc, r) => {
    acc[r.outcome] = (acc[r.outcome] ?? 0) + 1;
    return acc;
  }, {});

  // Failures first: the reason an asset was held back should be the first thing read.
  const order = { fail: 0, warn: 1, pass: 2, skip: 3 } as const;
  const sorted = [...report.results].sort((a, b) => order[a.outcome] - order[b.outcome]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
        <span
          className={
            report.verdict === "pass"
              ? "chip bg-emerald-500/15 text-emerald-300"
              : "chip bg-rose-500/15 text-rose-300"
          }
        >
          {report.verdict.toUpperCase()}
        </span>
        <span>
          {counts.pass ?? 0} pass · {counts.fail ?? 0} fail · {counts.warn ?? 0} warn ·{" "}
          {counts.skip ?? 0} skip
        </span>
        <span className="text-slate-600">
          against {report.spec_id} v{report.spec_version}
        </span>
      </div>

      {report.asset_sha256 && (
        <p className="font-mono text-[10px] text-slate-600">
          sha256 {report.asset_sha256.slice(0, 32)}…
        </p>
      )}

      <ul className="card divide-y divide-ink-700 px-3">
        {sorted.map((result) => (
          <Rule key={result.rule_id} result={result} />
        ))}
      </ul>
    </div>
  );
}
