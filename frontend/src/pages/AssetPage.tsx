import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { api } from "../api/client";
import type { Job, Variant } from "../api/types";
import ComplianceReportView from "../components/ComplianceReport";
import ReframeTrack from "../components/ReframeTrack";
import {
  Empty,
  ErrorBox,
  ProgressBar,
  RatioBadge,
  Spinner,
  VerdictChip,
  formatBytes,
} from "../components/common";

function VariantPreview({ variant }: { variant: Variant }) {
  if (!variant.url) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-slate-600">
        no output
      </div>
    );
  }
  if (variant.kind === "video") {
    return (
      <video
        src={variant.url}
        controls
        loop
        playsInline
        className="h-full w-full object-contain"
      />
    );
  }
  return (
    <img src={variant.url} alt={variant.profile_id} className="h-full w-full object-contain" />
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
        "card overflow-hidden transition-colors",
        selected ? "border-accent/60" : "hover:border-ink-600/80",
        !variant.in_library && "border-rose-500/30",
      )}
    >
      <button onClick={onSelect} className="block w-full text-left">
        <div className="checker flex h-56 items-center justify-center bg-ink-900">
          <VariantPreview variant={variant} />
        </div>
      </button>

      <div className="space-y-2 p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <RatioBadge ratio={variant.ratio_label} />
            <span className="text-sm text-slate-200">
              {variant.profile_label ?? variant.profile_id}
            </span>
          </div>
          <VerdictChip verdict={variant.verdict} status={variant.status} />
        </div>

        <p className="font-mono text-[11px] text-slate-500">
          {variant.width}×{variant.height}
          {variant.duration_s ? ` · ${variant.duration_s.toFixed(1)}s` : ""} ·{" "}
          {formatBytes(variant.size_bytes)}
          {variant.reframe_path_points > 0 &&
            ` · ${variant.reframe_path_points} path pts`}
        </p>

        {!variant.in_library && (
          <p className="text-xs text-rose-300">
            {variant.error ?? "held out of the library"}
          </p>
        )}
        {variant.warning_count > 0 && variant.in_library && (
          <p className="text-xs text-amber-300">
            {variant.warning_count} warning{variant.warning_count > 1 ? "s" : ""}
          </p>
        )}

        <div className="flex gap-2 pt-1">
          <button className="btn-ghost flex-1 justify-center" onClick={onSelect}>
            Report
          </button>
          <button
            className="btn-ghost flex-1 justify-center"
            onClick={onRegenerate}
            disabled={busy}
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

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link to="/" className="text-xs text-slate-500 hover:text-slate-300">
            ← Library
          </Link>
          <h2 className="mt-1 text-lg font-semibold text-white">{a.title}</h2>
          <p className="text-sm text-slate-500">
            {a.kind} · {a.width}×{a.height}
            {a.duration_s ? ` · ${a.duration_s.toFixed(1)}s @ ${a.fps?.toFixed(2)}fps` : ""}
            {a.has_audio ? " · audio" : " · silent"} · {formatBytes(a.size_bytes)}
          </p>
          {a.analysis_notes.length > 0 && (
            <ul className="mt-2 space-y-0.5">
              {a.analysis_notes.map((note) => (
                <li key={note} className="text-xs text-slate-500">
                  · {note}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-400">
            {published}/{variants.data?.length ?? 0} in library
          </span>
          <button
            className="btn-ghost"
            onClick={() => reformatAll.mutate()}
            disabled={!!activeJob}
          >
            Re-render all
          </button>
        </div>
      </div>

      {activeJob && (
        <div className="card space-y-2 p-4">
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-300">
              {job.data?.stage ?? "queued"} · {job.data?.type ?? activeJob.type}
            </span>
            <span className="font-mono text-xs text-slate-500">
              {Math.round((job.data?.progress ?? 0) * 100)}%
            </span>
          </div>
          <ProgressBar value={job.data?.progress ?? 0} />
        </div>
      )}

      {variants.isLoading && <Spinner label="Loading variants…" />}
      {variants.data && variants.data.length === 0 && (
        <Empty title="No variants yet" hint="Trigger a render to generate them." />
      )}

      {variants.data && variants.data.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
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

      {selected && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-white">
              Why this crop — {selected.profile_label ?? selected.profile_id}
            </h3>
            {selected.crop_decision ? (
              <div className="card space-y-2 p-4">
                <p className="font-mono text-[11px] text-slate-500">
                  strategy {selected.crop_decision.strategy} · crop{" "}
                  {Math.round(selected.crop_decision.crop.x1)},
                  {Math.round(selected.crop_decision.crop.y1)} →{" "}
                  {Math.round(selected.crop_decision.crop.x2)},
                  {Math.round(selected.crop_decision.crop.y2)} of{" "}
                  {selected.crop_decision.source_size.join("×")}
                </p>
                <div className="flex flex-wrap gap-3 text-xs text-slate-400">
                  <span>
                    subject retained{" "}
                    <b className="text-slate-200">
                      {(selected.crop_decision.subject_coverage * 100).toFixed(1)}%
                    </b>
                  </span>
                  <span>
                    faces intact{" "}
                    <b className="text-slate-200">
                      {selected.crop_decision.faces_fully_inside}/
                      {selected.crop_decision.faces_considered}
                    </b>
                  </span>
                  <span>
                    clipped{" "}
                    <b
                      className={
                        selected.crop_decision.faces_clipped
                          ? "text-rose-300"
                          : "text-slate-200"
                      }
                    >
                      {selected.crop_decision.faces_clipped}
                    </b>
                  </span>
                </div>
                <ul className="space-y-1 pt-1">
                  {selected.crop_decision.rationale.map((line, i) => (
                    <li key={i} className="text-xs leading-relaxed text-slate-400">
                      · {line}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <Empty title="No crop decision recorded" />
            )}

            {reframe.data && reframe.data.points.length > 0 && (
              <ReframeTrack
                points={reframe.data.points}
                sourceSize={reframe.data.source_size}
              />
            )}
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-white">Compliance report</h3>
            {report.isLoading && <Spinner label="Loading report…" />}
            {report.data ? (
              <ComplianceReportView report={report.data.report} />
            ) : (
              !report.isLoading && <Empty title="This variant has no report yet" />
            )}
          </section>
        </div>
      )}
    </div>
  );
}
