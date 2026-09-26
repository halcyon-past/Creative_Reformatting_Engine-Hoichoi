import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { api } from "../api/client";
import { Empty, ErrorBox, Spinner } from "./common";
import type { AuditEvent } from "../api/types";

const ACTION_STYLE: Record<string, string> = {
  "asset.uploaded": "bg-sky-500/15 text-sky-300",
  "asset.deleted": "bg-slate-500/15 text-slate-400",
  "job.submitted": "bg-slate-500/15 text-slate-400",
  "job.succeeded": "bg-emerald-500/15 text-emerald-300",
  "job.failed": "bg-rose-500/15 text-rose-300",
  "variant.published": "bg-emerald-500/15 text-emerald-300",
  "variant.quarantined": "bg-rose-500/15 text-rose-300",
  "variant.regenerated": "bg-amber-500/15 text-amber-300",
  "variant.revalidated": "bg-amber-500/15 text-amber-300",
};

function Row({ event }: { event: AuditEvent }) {
  const failed = Array.isArray(event.detail?.failed_rules)
    ? (event.detail.failed_rules as string[])
    : [];
  return (
    <li className="border-t border-ink-700 py-2 first:border-t-0">
      <div className="flex flex-wrap items-baseline gap-2">
        <span
          className={clsx(
            "chip font-mono",
            ACTION_STYLE[event.action] ?? "bg-slate-500/15 text-slate-400",
          )}
        >
          {event.action}
        </span>
        <span className="text-xs text-slate-300">{event.message}</span>
        <span className="ml-auto font-mono text-[10px] text-slate-600">
          {new Date(event.at).toLocaleString()}
        </span>
      </div>

      <div className="mt-1 flex flex-wrap gap-3 font-mono text-[10px] text-slate-500">
        {event.actor_ip ? (
          <span title={event.actor_ip_forwarded ? "from a trusted proxy header" : "socket peer"}>
            ip {event.actor_ip}
            {event.actor_ip_forwarded && <span className="text-slate-600"> (fwd)</span>}
          </span>
        ) : (
          <span className="text-slate-600">no request context (worker)</span>
        )}
        {event.user_agent && <span>ua {event.user_agent.slice(0, 40)}</span>}
        {event.profile_id && <span>profile {event.profile_id}</span>}
      </div>

      {failed.length > 0 && (
        <p className="mt-1 text-[11px] text-rose-300">failed: {failed.join(", ")}</p>
      )}
    </li>
  );
}

export default function AuditTrail({ assetId }: { assetId: string }) {
  const audit = useQuery({
    queryKey: ["audit", assetId],
    queryFn: () => api.assetAudit(assetId),
  });

  if (audit.isLoading) return <Spinner label="Loading audit trail…" />;
  if (audit.isError) return <ErrorBox error={audit.error} />;
  if (!audit.data || audit.data.events.length === 0) {
    return <Empty title="No audit events yet" />;
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-500">
        {audit.data.count} event{audit.data.count === 1 ? "" : "s"} · append-only ·
        IP addresses are purged on a retention schedule
      </p>
      <ul className="card px-3">
        {audit.data.events.map((event) => (
          <Row key={event.id} event={event} />
        ))}
      </ul>
    </div>
  );
}
