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
  RatioBadge,
  Spinner,
  VerdictChip,
  formatBytes,
} from "../components/common";

function formatStageName(stage: string | null | undefined): string {
  if (!stage) return "Preparing media pipeline…";
  const s = stage.toLowerCase();
  if (s.includes("analysing master")) {
    return "Analysing master image (faces, saliency & layout)…";
  }
  if (s.includes("analysing video")) {
    return "Analysing video (face tracking, shot cuts & active speaker VAD)…";
  }
  if (s.includes("analysis record")) {
    return "Building multi-speaker timeline & reframe trajectories…";
  }
  if (s.includes("rendering reel")) {
    return "Rendering vertical reel with active-speaker camera pan…";
  }
  if (s.includes("validating reel")) {
    return "Validating vertical reel against platform delivery specs…";
  }
  if (s.includes("extracting still")) {
    return "Extracting peak-sharpness still & framing around subjects…";
  }
  if (s.startsWith("rendering ")) {
    return `Rendering ${stage.replace(/rendering /i, "")}…`;
  }
  if (s === "done") {
    return "Pipeline complete · Assets verified and published";
  }
  return stage.charAt(0).toUpperCase() + stage.slice(1);
}

function VariantCardPreview({ variant }: { variant: Variant }) {
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
          controls={false}
          muted
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
    </div>
  );
}

function InspectorPreview({
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
      <div className="flex h-64 items-center justify-center font-mono text-xs text-slate-500">
        no output rendered
      </div>
    );
  }

  const isVertical = variant.ratio_label === "9:16";
  const isSquare = variant.ratio_label === "1:1";
  const isPortrait = variant.ratio_label === "4:5";

  return (
    <div className="flex flex-col items-center">
      {/* Platform & Frame Resolution Badge */}
      <div className="mb-3.5 flex items-center gap-2">
        <div className="flex items-center gap-2 rounded-full border-[2.5px] border-ink-600 bg-ink-800 px-3.5 py-1 text-[11px] font-mono text-slate-200 shadow-brutal-sm backdrop-blur-xs">
          <span
            className={clsx(
              "h-2 w-2 rounded-full",
              isVertical ? "bg-emerald-400 animate-pulse" : "bg-accent"
            )}
          />
          <span className="font-semibold text-slate-100">
            {isVertical
              ? "Smartphone Reel Frame (9:16)"
              : isSquare
              ? "Square Feed Canvas (1:1)"
              : isPortrait
              ? "Portrait Feed Frame (4:5)"
              : "Widescreen OTT Canvas (16:9)"}
          </span>
          <span className="text-slate-500">·</span>
          <span className="text-slate-300">{variant.width}×{variant.height}</span>
          {variant.duration_s ? (
            <>
              <span className="text-slate-500">·</span>
              <span className="text-slate-300">{variant.duration_s.toFixed(1)}s</span>
            </>
          ) : null}
        </div>
      </div>

      {/* Aspect-Locked Viewport Stage */}
      <div
        className={clsx(
          "relative overflow-hidden shadow-brutal-xl bg-black transition-all",
          isVertical &&
            "h-[560px] max-h-[72vh] aspect-[9/16] rounded-[32px] border-[6px] border-slate-700 ring-1 ring-white/10",
          isSquare &&
            "h-[420px] max-h-[65vh] aspect-square rounded-brutal border-2 border-slate-700 ring-1 ring-white/10",
          isPortrait &&
            "h-[490px] max-h-[70vh] aspect-[4/5] rounded-brutal border-2 border-slate-700 ring-1 ring-white/10",
          !isVertical &&
            !isSquare &&
            !isPortrait &&
            "w-full max-w-3xl aspect-video rounded-brutal border-2 border-slate-700 ring-1 ring-white/10"
        )}
      >
        {variant.kind === "video" ? (
          <video
            key={variant.url}
            src={variant.url}
            controls
            loop
            playsInline
            className="h-full w-full object-cover"
          />
        ) : (
          <img
            src={variant.url}
            alt={variant.profile_id}
            className="h-full w-full object-cover"
          />
        )}

        {/* Safe-Zone Overlay accurately bounded to this exact frame! */}
        <SafeZoneOverlay
          ratio={variant.ratio_label}
          showSafeZones={showSafeZones}
          showPlatformChrome={showPlatformChrome}
        />
      </div>
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
          ? "border-accent ring-1 ring-accent/40 shadow-brutal bg-ink-800"
          : "border-ink-600 hover:border-slate-500 bg-ink-800",
        !variant.in_library && "border-rose-500/40",
      )}
    >
      <button
        type="button"
        onClick={onSelect}
        className="block w-full text-left focus:outline-none"
      >
        <div className="checker relative flex h-60 items-center justify-center bg-ink-900 border-b border-ink-600">
          <VariantCardPreview variant={variant} />
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
          <p className="text-xs text-pop-red">
            {variant.error ?? "Quarantined: held out of library"}
          </p>
        )}
        {variant.warning_count > 0 && variant.in_library && (
          <p className="text-xs text-yellow-700">
            {variant.warning_count} warning{variant.warning_count > 1 ? "s" : ""}
          </p>
        )}

        <div className="flex gap-2 pt-1 border-t border-ink-600">
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
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [isReformatModalOpen, setIsReformatModalOpen] = useState(false);

  // Inspector overlay controls
  const [showSafeZones, setShowSafeZones] = useState(true);
  const [showPlatformChrome, setShowPlatformChrome] = useState(true);

  const asset = useQuery({ queryKey: ["asset", assetId], queryFn: () => api.getAsset(assetId) });

  // Query jobs for this asset with automatic polling when active
  const jobs = useQuery({
    queryKey: ["jobs", assetId],
    queryFn: () => api.listJobs(assetId, 10),
    refetchInterval: (query) => {
      const data = query.state.data as Job[] | undefined;
      const hasActive = data?.some((j) => j.status === "queued" || j.status === "running");
      return hasActive || activeJobId ? 1000 : false;
    },
  });

  // Determine current active job
  const activeJob =
    jobs.data?.find((j) => j.status === "queued" || j.status === "running") ??
    (activeJobId ? jobs.data?.find((j) => j.id === activeJobId) : null) ??
    null;

  const variants = useQuery({
    queryKey: ["variants", assetId],
    queryFn: () => api.listVariants(assetId),
    refetchInterval: activeJob ? 1500 : false,
  });

  // When active job finishes, refresh variants and asset data
  useEffect(() => {
    if (jobs.data) {
      const hasActive = jobs.data.some((j) => j.status === "queued" || j.status === "running");
      if (!hasActive && activeJobId) {
        setActiveJobId(null);
        queryClient.invalidateQueries({ queryKey: ["variants", assetId] });
        queryClient.invalidateQueries({ queryKey: ["asset", assetId] });
      }
    }
  }, [jobs.data, activeJobId, assetId, queryClient]);

  const regenerate = useMutation({
    mutationFn: (profileId: string) => api.regenerate(assetId, profileId),
    onSuccess: (job) => {
      setActiveJobId(job.id);
      queryClient.invalidateQueries({ queryKey: ["jobs", assetId] });
    },
  });

  const reformatSpecific = useMutation({
    mutationFn: (profileIds: string[]) => api.reformat(assetId, profileIds),
    onSuccess: (job) => {
      setActiveJobId(job.id);
      queryClient.invalidateQueries({ queryKey: ["jobs", assetId] });
    },
  });

  const reformatAll = useMutation({
    mutationFn: () => api.reformat(assetId),
    onSuccess: (job) => {
      setActiveJobId(job.id);
      queryClient.invalidateQueries({ queryKey: ["jobs", assetId] });
    },
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
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-ink-600 pb-5">
        <div>
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors"
          >
            ← Back to Library
          </Link>
          <div className="mt-2 flex items-center gap-3">
            <h2 className="font-display text-3xl leading-none text-slate-100">{a.title}</h2>
            <span className="rounded bg-ink-700 px-2 py-0.5 font-mono text-xs text-slate-300 border-[2.5px] border-ink-600">
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
          <div className="rounded-brutal border-[2.5px] border-ink-600 bg-ink-800 px-3 py-1.5 text-xs text-slate-300">
            Library status:{" "}
            <span className="font-mono font-semibold text-slate-100">
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
        <div className="flex items-center justify-between rounded-brutal border border-accent/30 bg-accent/5 px-4 py-3">
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
        <div className="animate-pop-in space-y-3 rounded-brutal border-3 border-ink-600 bg-pop-yellow p-5 shadow-brutal-lg">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="relative flex h-3.5 w-3.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-black opacity-60" />
                <span className="relative inline-flex h-3.5 w-3.5 rounded-full border-2 border-ink-600 bg-pop-red" />
              </span>
              <div>
                <span className="font-display text-base text-black">
                  {formatStageName(activeJob.stage)}
                </span>
                <p className="font-mono text-[11px] font-bold text-black/70">
                  Job ID: {activeJob.id.slice(0, 8)} · Type: {activeJob.type} · Status: {activeJob.status}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="rounded-brutal border border-accent/40 bg-accent px-3 py-1 font-mono text-base font-bold text-black shadow-brutal-sm">
                {Math.round((activeJob.progress ?? 0) * 100)}%
              </span>
            </div>
          </div>

          {/* Granular Animated Progress Bar */}
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-ink-950 border-[2.5px] border-ink-600 shadow-inner">
            <div
              className="h-full rounded-full bg-gradient-to-r from-sky-400 via-accent to-emerald-400 transition-all duration-300 shadow-brutal"
              style={{ width: `${Math.max(4, Math.round((activeJob.progress ?? 0) * 100))}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
            <span>Stage: {activeJob.stage ?? "Processing"}</span>
            <span>
              {activeJob.progress >= 1.0
                ? "Finalizing…"
                : `${Math.round((activeJob.progress ?? 0) * 100)}% completed`}
            </span>
          </div>
        </div>
      )}

      {/* Variants Gallery */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="label">
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
        <div className="space-y-6 border-t-3 border-ink-600 pt-6">
          {/* Inspector Header with Safe-Zone Toggles */}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <RatioBadge ratio={selected.ratio_label} />
                <h3 className="font-display text-xl text-slate-100">
                  Inspector: {selected.profile_label ?? selected.profile_id}
                </h3>
              </div>
              <p className="mt-0.5 text-xs text-slate-400">
                Independent compliance validation against platform delivery spec.
              </p>
            </div>

            {/* Overlays Control Toolbar */}
            <div className="flex items-center gap-2 rounded-brutal border-[2.5px] border-ink-600 bg-ink-800 p-1">
              <span className="px-2 text-xs font-medium text-slate-400">Overlays:</span>
              <button
                type="button"
                onClick={() => setShowSafeZones(!showSafeZones)}
                className={clsx(
                  "rounded px-2.5 py-1 text-xs font-medium transition",
                  showSafeZones
                    ? "bg-pop-lime text-black border border-emerald-500/30"
                    : "text-slate-400 hover:text-slate-100",
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
                      ? "bg-pop-red text-white border border-rose-500/30"
                      : "text-slate-400 hover:text-slate-100",
                  )}
                >
                  Platform UI Chrome
                </button>
              )}
            </div>
          </div>

          {/* Workstation Inspection Stage with Device Mockup */}
          <div className="checker relative flex min-h-[580px] w-full items-center justify-center overflow-hidden rounded-brutal border-[2.5px] border-ink-600 bg-ink-950 p-4 sm:p-8 shadow-inner">
            <InspectorPreview
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
                <h4 className="label">Crop Decision &amp; Framing Strategy</h4>
                {selected.crop_decision && (
                  <span className="font-mono text-xs text-accent">
                    {selected.crop_decision.strategy}
                  </span>
                )}
              </div>

              {selected.crop_decision ? (
                <div className="card space-y-3 p-4">
                  <div className="grid grid-cols-3 gap-2 border-b-3 border-ink-600 pb-3 text-center">
                    <div>
                      <span className="text-[10px] font-extrabold uppercase tracking-wide text-slate-500">Subject Coverage</span>
                      <p className="font-display text-xl text-slate-100">
                        {(selected.crop_decision.subject_coverage * 100).toFixed(1)}%
                      </p>
                    </div>
                    <div>
                      <span className="text-[10px] font-extrabold uppercase tracking-wide text-slate-500">Faces Preserved</span>
                      <p className="font-mono text-sm font-bold text-green-700">
                        {selected.crop_decision.faces_fully_inside}/{selected.crop_decision.faces_considered}
                      </p>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase">Faces Clipped</span>
                      <p
                        className={clsx(
                          "font-mono text-sm font-bold",
                          selected.crop_decision.faces_clipped ? "text-pop-red" : "text-slate-300",
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
              <h4 className="label">Compliance Verification &amp; Audit</h4>

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
