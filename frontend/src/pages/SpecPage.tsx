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
    <svg
      viewBox={`0 0 ${w} ${h}`}
      width={w}
      height={h}
      className="shrink-0 rounded-brutal border-3 border-ink-600 bg-white shadow-brutal-sm"
    >
      <rect x={0} y={0} width={w} height={h} fill="#FFFFFF" />
      {profile.reserved_zones.map((zone) => (
        <rect
          key={zone.name}
          x={zone.rect[0] * w}
          y={zone.rect[1] * h}
          width={(zone.rect[2] - zone.rect[0]) * w}
          height={(zone.rect[3] - zone.rect[1]) * h}
          fill="#FF5252"
          fillOpacity={0.55}
          stroke="#000000"
          strokeWidth={1}
        />
      ))}
      {action && (
        <rect
          x={action[0] * w}
          y={action[1] * h}
          width={(action[2] - action[0]) * w}
          height={(action[3] - action[1]) * h}
          fill="none"
          stroke="#16A34A"
          strokeWidth={2}
          strokeDasharray="4 2"
        />
      )}
      {title && (
        <rect
          x={title[0] * w}
          y={title[1] * h}
          width={(title[2] - title[0]) * w}
          height={(title[3] - title[1]) * h}
          fill="none"
          stroke="#2563EB"
          strokeWidth={2}
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
      <div className="relative">
        <div
          aria-hidden="true"
          className="absolute -left-2 -top-2 h-14 w-32 rotate-2 rounded-brutal border-3 border-ink-600 bg-pop-lime"
        />
        <div className="relative">
          <h2 className="font-display text-3xl leading-none text-slate-100">
            PLATFORM
            <span className="ml-2 inline-block rotate-1 rounded-brutal border-3 border-ink-600 bg-pop-purple px-2 shadow-brutal">
              SPEC SHEET
            </span>
          </h2>
          <p className="mt-3 flex flex-wrap items-center gap-2">
            <span className="chip bg-black font-mono text-pop-yellow">{s.spec_id}</span>
            <span className="chip bg-pop-cyan font-mono text-black">v{s.spec_version}</span>
          </p>
          <p className="mt-3 max-w-3xl text-sm font-medium text-slate-400">{s.description}</p>
          <p className="mt-2 inline-block -rotate-1 rounded-brutal border-3 border-ink-600 bg-pop-yellow px-2 py-1 text-xs font-extrabold uppercase text-black shadow-brutal-sm">
            ⚡ every derived asset is validated against this before it enters the library
          </p>
        </div>
      </div>

      <div className="card flex flex-wrap gap-4 p-3 text-[11px] font-bold uppercase tracking-wide text-slate-400">
        <span className="flex items-center gap-1">
          <span className="inline-block h-3 w-5 border-2 border-dashed border-[#16A34A]" />
          action safe (subject must stay inside)
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-3 w-5 border-2 border-dashed border-[#2563EB]" />
          title safe
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-3 w-5 border-2 border-ink-600 bg-[#FF5252]" />
          reserved for platform UI
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {s.profiles.map((profile) => (
          <div key={profile.id} className="card-hover flex gap-4 p-4">
            <ZoneDiagram profile={profile} />
            <div className="min-w-0 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <RatioBadge ratio={profile.ratio} />
                <span className="font-display text-base text-slate-100">{profile.label}</span>
                <span className="chip bg-pop-yellow text-black">{profile.kind}</span>
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
        <h3 className="label mb-3">Render sets</h3>
        {Object.entries(s.render_sets).map(([kind, ids]) => (
          <p key={kind} className="font-mono text-xs text-slate-400">
            <span className="text-slate-500">{kind}:</span> {ids.join(", ")}
          </p>
        ))}
        <h3 className="label mb-3 mt-5">Compliance thresholds</h3>
        <pre className="well overflow-auto p-3 font-mono text-[11px] font-medium text-slate-300">
          {JSON.stringify(s.compliance_defaults, null, 2)}
        </pre>
      </div>
    </div>
  );
}
