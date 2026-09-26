import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { ErrorBox, RatioBadge, Spinner } from "../components/common";
import type { Profile } from "../api/types";

/**
 * Renders each profile's safe and reserved zones to scale.
 *
 * A reviewer checking our verdicts needs to see the same geometry the
 * validator used, not a prose description of it.
 */
function ZoneDiagram({ profile }: { profile: Profile }) {
  const w = 120;
  const h = (w * profile.height) / profile.width;
  const action = profile.safe_zones.action;
  const title = profile.safe_zones.title;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} className="shrink-0">
      <rect x={0} y={0} width={w} height={h} className="fill-ink-900 stroke-ink-600" />
      {profile.reserved_zones.map((zone) => (
        <rect
          key={zone.name}
          x={zone.rect[0] * w}
          y={zone.rect[1] * h}
          width={(zone.rect[2] - zone.rect[0]) * w}
          height={(zone.rect[3] - zone.rect[1]) * h}
          fill="#f43f5e"
          fillOpacity={0.18}
          stroke="#f43f5e"
          strokeOpacity={0.5}
          strokeWidth={0.5}
        />
      ))}
      {action && (
        <rect
          x={action[0] * w}
          y={action[1] * h}
          width={(action[2] - action[0]) * w}
          height={(action[3] - action[1]) * h}
          fill="none"
          stroke="#5ad18c"
          strokeWidth={1}
          strokeDasharray="3 2"
        />
      )}
      {title && (
        <rect
          x={title[0] * w}
          y={title[1] * h}
          width={(title[2] - title[0]) * w}
          height={(title[3] - title[1]) * h}
          fill="none"
          stroke="#5b9dff"
          strokeWidth={0.7}
          strokeDasharray="2 2"
        />
      )}
    </svg>
  );
}

export default function SpecPage() {
  const spec = useQuery({ queryKey: ["spec"], queryFn: api.spec });

  if (spec.isLoading) return <Spinner label="Loading spec sheet…" />;
  if (spec.isError) return <ErrorBox error={spec.error} />;
  if (!spec.data) return null;

  const s = spec.data;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white">
          {s.spec_id}{" "}
          <span className="font-mono text-sm text-slate-500">v{s.spec_version}</span>
        </h2>
        <p className="max-w-3xl text-sm text-slate-500">{s.description}</p>
        <p className="mt-1 text-xs text-slate-600">
          Every derived asset is validated against this document before it is allowed
          into the library.
        </p>
      </div>

      <div className="flex flex-wrap gap-4 text-[11px] text-slate-500">
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-4 border border-dashed border-[#5ad18c]" />
          action safe (subject must stay inside)
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-4 border border-dashed border-[#5b9dff]" />
          title safe
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-4 bg-rose-500/30" />
          reserved for platform UI
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {s.profiles.map((profile) => (
          <div key={profile.id} className="card flex gap-4 p-4">
            <ZoneDiagram profile={profile} />
            <div className="min-w-0 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <RatioBadge ratio={profile.ratio} />
                <span className="text-sm font-medium text-slate-100">{profile.label}</span>
                <span className="chip bg-ink-700 text-slate-400">{profile.kind}</span>
              </div>
              <p className="font-mono text-[11px] text-slate-500">
                {profile.id} · {profile.width}×{profile.height}
                {profile.source ? ` · source: ${profile.source}` : ""}
              </p>
              {profile.reserved_zones.length > 0 && (
                <p className="text-xs text-slate-500">
                  reserved: {profile.reserved_zones.map((z) => z.name).join(", ")}
                </p>
              )}
              <p className="text-xs text-slate-500">
                composition: {String(profile.composition.rule)}
                {profile.composition.prefer_headroom ? " · headroom" : ""}
                {Number(profile.composition.min_face_height_fraction) > 0 &&
                  ` · min face ${(
                    Number(profile.composition.min_face_height_fraction) * 100
                  ).toFixed(0)}% of height`}
              </p>
            </div>
          </div>
        ))}
      </div>

      <div className="card p-4">
        <h3 className="mb-2 text-sm font-semibold text-white">Render sets</h3>
        {Object.entries(s.render_sets).map(([kind, ids]) => (
          <p key={kind} className="font-mono text-xs text-slate-400">
            <span className="text-slate-500">{kind}:</span> {ids.join(", ")}
          </p>
        ))}
        <h3 className="mb-2 mt-4 text-sm font-semibold text-white">Compliance thresholds</h3>
        <pre className="overflow-auto rounded bg-ink-900 p-3 font-mono text-[11px] text-slate-400">
          {JSON.stringify(s.compliance_defaults, null, 2)}
        </pre>
      </div>
    </div>
  );
}
