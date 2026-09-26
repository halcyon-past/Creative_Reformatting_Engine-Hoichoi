import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { api } from "../api/client";
import type { Job, Variant } from "../api/types";
import AuditTrail from "../components/AuditTrail";
import ComplianceReportView from "../components/ComplianceReport";
import ReframeTrack from "../components/ReframeTrack";
import { ReformatModal } from "../components/ReformatModal";
import { SafeZoneOverlay } from "../components/SafeZoneOverlay";
import { AVAILABLE_PROFILES } from "../components/RatioSelector";
import {
  Empty,
  ErrorBox,
  ProgressBar,
  RatioBadge,
  Spinner,
  VerdictChip,
  formatBytes,
} from "../components/common";

function VariantPreview({
  variant,
  showSafeZones,
  showPlatformChrome,
}: {
  variant: Variant;
  showSafeZones: boolean;
  showPlatformChrome: boolean;
}) {
  if (!variant.url) {
    return (
      <div className="flex h-full items-center justify-center font-mono text-xs text-slate-500">
        no output rendered
      </div>
    );
  }

  return (
    <div className="relative flex h-full w-full items-center justify-center overflow-hidden">
      {variant.kind === "video" ? (
        <video
          src={variant.url}
          controls
          loop
          playsInline
          className="h-full w-full object-contain"
        />
      ) : (
        <img
          src={variant.url}
          alt={variant.profile_id}
          className="h-full w-full object-contain"
        />
      )}

      {/* Safe-Zone Overlay */}
      <SafeZoneOverlay
        ratio={variant.ratio_label}
        showSafeZones={showSafeZones}
        showPlatformChrome={showPlatformChrome}
      />
    </div>
  );
}

function VariantCard({
  variant,
  onSelect,
  onRegenerate,
  busy,
  selected,
}: {
  variant: Variant;
  onSelect: () => void;
  onRegenerate: () => void;
  busy: boolean;
  selected: boolean;
}) {
  return (
    <div
      className={clsx(
        "card flex flex-col justify-between overflow-hidden transition-all",
        selected
          ? "border-accent ring-1 ring-accent/40 shadow-md bg-ink-800"
          : "border-ink-600/80 hover:border-slate-500 bg-ink-800/90",
        !variant.in_library && "border-rose-500/40",
      )}
    >
      <button
        type="button"
        onClick={onSelect}
        className="block w-full text-left focus:outline-none"
      >
        <div className="checker relative flex h-60 items-center justify-center bg-ink-900 border-b border-ink-600/60">
          <VariantPreview
            variant={variant}
            showSafeZones={false}
            showPlatformChrome={false}
          />
          <div className="absolute top-2 left-2 flex items-center gap-1.5">
            <RatioBadge ratio={variant.ratio_label} />
          </div>
        </div>
      </button>

      <div className="space-y-2.5 p-3.5">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-xs font-semibold text-slate-100">
            {variant.profile_label ?? variant.profile_id}
          </span>
          <VerdictChip verdict={variant.verdict} status={variant.status} />
        </div>

        <p className="font-mono text-[11px] text-slate-400">
          {variant.width}×{variant.height}
          {variant.duration_s ? ` · ${variant.duration_s.toFixed(1)}s` : ""} ·{" "}
          {formatBytes(variant.size_bytes)}
          {variant.reframe_path_points > 0 &&
            ` · ${variant.reframe_path_points} path pts`}
        </p>

        {!variant.in_library && (
          <p className="text-xs text-rose-300">
            {variant.error ?? "Quarantined: held out of library"}
          </p>
        )}
        {variant.warning_count > 0 && variant.in_library && (
          <p className="text-xs text-amber-300">
            {variant.warning_count} warning{variant.warning_count > 1 ? "s" : ""}
          </p>
        )}

        <div className="flex gap-2 pt-1 border-t border-ink-600/60">
          <button
            type="button"
            className={clsx(
              "btn-ghost flex-1 justify-center text-xs",
              selected && "border-accent text-accent",
            )}
            onClick={onSelect}
          >
            Inspect & Report
          </button>
          <button
            type="button"
            className="btn-ghost flex-1 justify-center text-xs"
            onClick={onRegenerate}
            disabled={busy}
            title="Re-render this single variant without touching other variants"
          >
            {busy ? "Working…" : "Regenerate"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AssetPage() {
  const { assetId = "" } = useParams();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const [isReformatModalOpen, setIsReformatModalOpen] = useState(false);

  // Inspector overlay controls
  const [showSafeZones, setShowSafeZones] = useState(true);
  const [showPlatformChrome, setShowPlatformChrome] = useState(true);

  const asset = useQuery({ queryKey: ["asset", assetId], queryFn: () => api.getAsset(assetId) });

  const variants = useQuery({
    queryKey: ["variants", assetId],
    queryFn: () => api.listVariants(assetId),
    refetchInterval: activeJob ? 1500 : false,
  });

  const job = useQuery({
    queryKey: ["job", activeJob?.id],
    queryFn: () => api.getJob(activeJob!.id),
    enabled: !!activeJob,
    refetchInterval: 1000,
  });

  // Once the worker finishes, refresh the variant list and stop polling.
  useEffect(() => {
    const status = job.data?.status;
    if (status === "succeeded" || status === "failed") {
      setActiveJob(null);
      queryClient.invalidateQueries({ queryKey: ["variants", assetId] });
      queryClient.invalidateQueries({ queryKey: ["asset", assetId] });
    }
  }, [job.data?.status, assetId, queryClient]);

  const regenerate = useMutation({
    mutationFn: (profileId: string) => api.regenerate(assetId, profileId),
    onSuccess: setActiveJob,
  });

  const reformatSpecific = useMutation({
    mutationFn: (profileIds: string[]) => api.reformat(assetId, profileIds),
    onSuccess: setActiveJob,
  });

  const reformatAll = useMutation({
    mutationFn: () => api.reformat(assetId),
    onSuccess: setActiveJob,
  });

  const selected =
    variants.data?.find((v) => v.id === selectedId) ?? variants.data?.[0] ?? null;

  const report = useQuery({
    queryKey: ["report", selected?.id],
    queryFn: () => api.report(selected!.id),
    enabled: !!selected && !!selected.verdict,
  });

  const reframe = useQuery({
    queryKey: ["reframe", selected?.id],
    queryFn: () => api.reframePath(selected!.id),
    enabled: !!selected && selected.reframe_path_points > 0,
  });

  if (asset.isLoading) return <Spinner label="Loading asset…" />;
  if (asset.isError) return <ErrorBox error={asset.error} />;
  if (!asset.data) return <Empty title="Asset not found" />;

  const a = asset.data;
  const published = variants.data?.filter((v) => v.in_library).length ?? 0;

  // Check which profiles have not been rendered yet
  const availableOptions = AVAILABLE_PROFILES[a.kind] || [];
  const existingProfileIds = new Set(variants.data?.map((v) => v.profile_id) || []);
  const unrenderedProfiles = availableOptions.filter((o) => !existingProfileIds.has(o.id));

  return (
    <div className="space-y-6">
      {/* Asset Header */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-ink-600/70 pb-5">
        <div>
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors"
          >
            ← Back to Library
          </Link>
          <div className="mt-2 flex items-center gap-3">
            <h2 className="text-xl font-bold tracking-tight text-white">{a.title}</h2>
            <span className="rounded bg-ink-700 px-2 py-0.5 font-mono text-xs text-slate-300 border border-ink-600">
              {a.kind.toUpperCase()}
            </span>
          </div>
          <p className="mt-1 font-mono text-xs text-slate-400">
            {a.width}×{a.height}
            {a.duration_s ? ` · ${a.duration_s.toFixed(1)}s @ ${a.fps?.toFixed(2)}fps` : ""}
            {a.has_audio ? " · ♫ Audio detected" : " · Muted / Silent"} · {formatBytes(a.size_bytes)}
            {a.face_count > 0 ? ` · ${a.face_count} face tracks` : ""}
          </p>

          {a.analysis_notes.length > 0 && (
            <ul className="mt-2.5 space-y-1">
              {a.analysis_notes.map((note) => (
                <li key={note} className="text-xs text-slate-400 flex items-center gap-1.5">
                  <span className="h-1 w-1 rounded-full bg-accent" />
                  <span>{note}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="rounded-lg border border-ink-600/80 bg-ink-800/80 px-3 py-1.5 text-xs text-slate-300">
            Library status:{" "}
            <span className="font-mono font-semibold text-white">
              {published}/{variants.data?.length ?? 0}
            </span>{" "}
            published
          </div>

          <button
            type="button"
            className="btn-primary text-xs"
            onClick={() => setIsReformatModalOpen(true)}
            disabled={!!activeJob}
          >
            Choose Ratios to Render…
          </button>

          <button
            type="button"
            className="btn-ghost text-xs"
            onClick={() => reformatAll.mutate()}
            disabled={!!activeJob}
            title="Re-render all platform profiles for this media type"
          >
            Re-render All Ratios
          </button>
        </div>
      </div>

      {/* Unrendered Ratios Notice */}
      {unrenderedProfiles.length > 0 && !activeJob && (
        <div className="flex items-center justify-between rounded-lg border border-accent/30 bg-accent/5 px-4 py-3">
          <div className="space-y-0.5">
            <p className="text-xs font-semibold text-slate-200">
              Unrendered ratios available ({unrenderedProfiles.length}):
            </p>
            <p className="text-xs text-slate-400">
              {unrenderedProfiles.map((p) => `${p.label} (${p.ratio})`).join(", ")}
            </p>
          </div>
          <button
            type="button"
            onClick={() => reformatSpecific.mutate(unrenderedProfiles.map((p) => p.id))}
            className="btn-primary text-xs shrink-0"
          >
            Render {unrenderedProfiles.length} Missing Ratio{unrenderedProfiles.length > 1 ? "s" : ""}
          </button>
        </div>
      )}

      {/* Active Pipeline Progress */}
      {activeJob && (
        <div className="card space-y-2.5 p-4 border-accent/40 bg-ink-800 shadow-md">
          <div className="flex items-center justify-between text-xs text-slate-200">
            <span className="flex items-center gap-2 font-medium">
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-accent border-t-transparent" />
              Stage: {job.data?.stage ?? "queued"} · {job.data?.type ?? activeJob.type}
            </span>
            <span className="font-mono font-semibold text-accent">
              {Math.round((job.data?.progress ?? 0) * 100)}%
            </span>
          </div>
          <ProgressBar value={job.data?.progress ?? 0} />
        </div>
      )}

      {/* Variants Gallery */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">
            Derived Platform Variants ({variants.data?.length ?? 0})
          </h3>
          <span className="text-xs text-slate-500">
            Click any variant card to inspect crop decision & compliance
          </span>
        </div>

        {variants.isLoading && <Spinner label="Loading variants…" />}
        {variants.data && variants.data.length === 0 && (
          <Empty
            title="No variants generated yet"
            hint="Click 'Choose Ratios to Render' to generate platform variants with smart crop."
          />
        )}

        {variants.data && variants.data.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {variants.data.map((variant) => (
              <VariantCard
                key={variant.id}
                variant={variant}
                selected={selected?.id === variant.id}
                busy={!!activeJob}
                onSelect={() => setSelectedId(variant.id)}
                onRegenerate={() => regenerate.mutate(variant.profile_id)}
              />
            ))}
          </div>
        )}
      </section>

      {/* Selected Variant Inspector */}
      {selected && (
        <div className="space-y-6 border-t border-ink-600/70 pt-6">
          {/* Inspector Header with Safe-Zone Toggles */}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <RatioBadge ratio={selected.ratio_label} />
                <h3 className="text-base font-semibold text-white">
                  Inspector: {selected.profile_label ?? selected.profile_id}
                </h3>
              </div>
              <p className="mt-0.5 text-xs text-slate-400">
                Independent compliance validation against platform delivery spec.
              </p>
            </div>

            {/* Overlays Control Toolbar */}
            <div className="flex items-center gap-2 rounded-lg border border-ink-600/80 bg-ink-800 p-1">
              <span className="px-2 text-xs font-medium text-slate-400">Overlays:</span>
              <button
                type="button"
                onClick={() => setShowSafeZones(!showSafeZones)}
                className={clsx(
                  "rounded px-2.5 py-1 text-xs font-medium transition",
                  showSafeZones
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                    : "text-slate-400 hover:text-white",
                )}
              >
                Safe Zones
              </button>
              {selected.ratio_label === "9:16" && (
                <button
                  type="button"
                  onClick={() => setShowPlatformChrome(!showPlatformChrome)}
                  className={clsx(
                    "rounded px-2.5 py-1 text-xs font-medium transition",
                    showPlatformChrome
                      ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                      : "text-slate-400 hover:text-white",
                  )}
                >
                  Platform UI Chrome
                </button>
              )}
            </div>
          </div>

          {/* Large Live Preview with Overlays */}
          <div className="checker relative flex max-h-[500px] min-h-[320px] w-full items-center justify-center overflow-hidden rounded-xl border border-ink-600 bg-ink-900 shadow-inner">
            <VariantPreview
              variant={selected}
              showSafeZones={showSafeZones}
              showPlatformChrome={showPlatformChrome}
            />
          </div>

          {/* Decision & Compliance Split */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Left: Why this crop & Reframe Track */}
            <section className="space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                  Crop Decision & Framing Strategy
                </h4>
                {selected.crop_decision && (
                  <span className="font-mono text-xs text-accent">
                    {selected.crop_decision.strategy}
                  </span>
                )}
              </div>

              {selected.crop_decision ? (
                <div className="card space-y-3 p-4">
                  <div className="grid grid-cols-3 gap-2 border-b border-ink-600/60 pb-3 text-center">
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase">Subject Coverage</span>
                      <p className="font-mono text-sm font-bold text-white">
                        {(selected.crop_decision.subject_coverage * 100).toFixed(1)}%
                      </p>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase">Faces Preserved</span>
                      <p className="font-mono text-sm font-bold text-emerald-400">
                        {selected.crop_decision.faces_fully_inside}/{selected.crop_decision.faces_considered}
                      </p>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase">Faces Clipped</span>
                      <p
                        className={clsx(
                          "font-mono text-sm font-bold",
                          selected.crop_decision.faces_clipped ? "text-rose-400" : "text-slate-300",
                        )}
                      >
                        {selected.crop_decision.faces_clipped}
                      </p>
                    </div>
                  </div>

                  <p className="font-mono text-[11px] text-slate-400">
                    Source size: {selected.crop_decision.source_size.join("×")} → Output crop: [
                    {Math.round(selected.crop_decision.crop.x1)},{" "}
                    {Math.round(selected.crop_decision.crop.y1)}] to [
                    {Math.round(selected.crop_decision.crop.x2)},{" "}
                    {Math.round(selected.crop_decision.crop.y2)}]
                  </p>

                  <ul className="space-y-1.5 pt-1">
                    {selected.crop_decision.rationale.map((line, i) => (
                      <li key={i} className="text-xs leading-relaxed text-slate-300 flex items-start gap-1.5">
                        <span className="text-accent mt-0.5">·</span>
                        <span>{line}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <Empty title="No crop decision recorded for this variant" />
              )}

              {/* Dynamic Reframe Path (Speaker tracking) */}
              {reframe.data && reframe.data.points.length > 0 && (
                <ReframeTrack
                  points={reframe.data.points}
                  sourceSize={reframe.data.source_size}
                />
              )}
            </section>

            {/* Right: Spec Compliance Report & Audit Trail */}
            <section className="space-y-4">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Compliance Verification & Audit
              </h4>

              {report.isLoading && <Spinner label="Loading compliance report…" />}
              {report.data ? (
                <ComplianceReportView report={report.data.report} />
              ) : (
                !report.isLoading && (
                  <Empty title="This variant has no compliance report yet" />
                )
              )}

              <div className="pt-2">
                <AuditTrail assetId={assetId} />
              </div>
            </section>
          </div>
        </div>
      )}

      {/* Reformat Modal */}
      <ReformatModal
        isOpen={isReformatModalOpen}
        onClose={() => setIsReformatModalOpen(false)}
        mediaKind={a.kind}
        existingVariants={variants.data || []}
        onReformat={async (profileIds) => {
          await reformatSpecific.mutateAsync(profileIds);
        }}
        isProcessing={reformatSpecific.isPending}
      />
    </div>
  );
}
