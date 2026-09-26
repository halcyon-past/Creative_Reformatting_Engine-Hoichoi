import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { ErrorBox, RatioBadge, Spinner, formatBytes } from "../components/common";
import { UploadModal } from "../components/UploadModal";
import type { Asset, Job } from "../api/types";

function AssetCard({
  asset,
  activeJob,
  onDelete,
}: {
  asset: Asset;
  activeJob?: Job;
  onDelete: (id: string) => void;
}) {
  const complete = asset.variant_count > 0;
  const allPassed = complete && asset.published_count === asset.variant_count;

  return (
    <div className="group flex flex-col justify-between overflow-hidden rounded-brutal border-3 border-ink-600 bg-ink-800 shadow-brutal transition-all duration-150 hover:-translate-x-1 hover:-translate-y-1 hover:shadow-brutal-xl">
      <Link to={`/assets/${asset.id}`} className="block">
        <div className="checker relative aspect-video w-full overflow-hidden border-b-3 border-ink-600">
          {asset.thumbnail_url ? (
            <img
              src={asset.thumbnail_url}
              alt={asset.title}
              className="h-full w-full object-contain transition-transform duration-300 group-hover:scale-[1.02]"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-slate-500 font-mono">
              no preview available
            </div>
          )}
          <div className="absolute top-2 left-2 flex items-center gap-1.5">
            <span className="rounded-brutal border-[2.5px] border-ink-600 bg-black px-1.5 py-0.5 font-mono text-[10px] font-extrabold uppercase text-pop-yellow shadow-brutal-sm">
              {asset.kind}
            </span>
            {asset.has_audio && (
              <span className="rounded-brutal border-[2.5px] border-ink-600 bg-pop-cyan px-1.5 py-0.5 font-mono text-[10px] font-extrabold text-black shadow-brutal-sm">
                ♫ Audio
              </span>
            )}
          </div>

          {/* Active Processing Overlay on Thumbnail */}
          {activeJob && (
            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/95 via-black/70 to-transparent p-2.5">
              <div className="flex items-center justify-between text-[11px] text-white">
                <span className="flex items-center gap-1.5 font-medium truncate">
                  <span className="h-2 w-2 animate-spin rounded-full border border-sky-400 border-t-transparent shrink-0" />
                  <span className="truncate">{activeJob.stage ?? "Processing…"}</span>
                </span>
                <span className="font-mono font-bold text-accent shrink-0 ml-1">
                  {Math.round(activeJob.progress * 100)}%
                </span>
              </div>
              <div className="mt-1 h-3 w-full overflow-hidden rounded-brutal border-2 border-white bg-black">
                <div
                  className="stripes-live h-full animate-stripes transition-[width] duration-300"
                  style={{ width: `${Math.max(5, Math.round(activeJob.progress * 100))}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </Link>

      <div className="flex flex-1 flex-col justify-between p-3.5 space-y-3">
        <div className="space-y-1">
          <div className="flex items-start justify-between gap-2">
            <Link to={`/assets/${asset.id}`} className="min-w-0 flex-1">
              <h3 className="truncate font-display text-base text-slate-100 transition-colors group-hover:text-accent">
                {asset.title}
              </h3>
            </Link>
            <button
              onClick={() => onDelete(asset.id)}
              className="shrink-0 rounded-brutal border-[2.5px] border-ink-600 bg-ink-800 p-1 text-slate-500 shadow-brutal-sm transition-all hover:-translate-y-0.5 hover:bg-pop-red hover:text-white"
              title="Delete asset"
              aria-label={`Delete ${asset.title}`}
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>

          <p className="font-mono text-[11px] text-slate-400">
            {asset.width && asset.height ? `${asset.width}×${asset.height}` : "probed"}
            {asset.duration_s ? ` · ${asset.duration_s.toFixed(1)}s` : ""}
            {asset.size_bytes ? ` · ${formatBytes(asset.size_bytes)}` : ""}
          </p>
        </div>

        <div className="flex items-center justify-between border-t-3 border-ink-600 pt-2.5 text-xs">
          <div className="flex items-center gap-1.5">
            {complete ? (
              <span
                className={
                  allPassed
                    ? "chip bg-pop-lime text-black"
                    : "chip bg-pop-yellow text-black"
                }
              >
                <span className="font-mono font-semibold">{asset.published_count}/{asset.variant_count}</span>
                <span>in library</span>
              </span>
            ) : asset.status === "failed" ? (
              <span className="inline-flex items-center rounded px-1.5 py-0.5 font-medium bg-pop-red text-white border border-rose-500/20">
                Failed
              </span>
            ) : activeJob ? (
              <span className="inline-flex items-center gap-1.5 rounded px-2 py-0.5 font-medium bg-pop-cyan text-black border border-sky-500/20">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-400" />
                <span>Processing</span>
                <span className="font-mono font-bold text-accent">
                  {Math.round(activeJob.progress * 100)}%
                </span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-medium bg-pop-cyan text-black border border-sky-500/20">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-400" />
                Processing…
              </span>
            )}
          </div>

          <Link
            to={`/assets/${asset.id}`}
            className="text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors"
          >
            Inspect →
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function LibraryPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const assets = useQuery({
    queryKey: ["assets"],
    queryFn: api.listAssets,
    refetchInterval: (query) => {
      const data = query.state.data as Asset[] | undefined;
      const busy = data?.some((a) => a.status !== "ready" && a.status !== "failed");
      return busy ? 2000 : false;
    },
  });

  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api.listJobs(undefined, 50),
    refetchInterval: (query) => {
      const data = query.state.data as Job[] | undefined;
      const hasActive = data?.some((j) => j.status === "queued" || j.status === "running");
      return hasActive ? 1200 : 3000;
    },
  });

  const activeJobsByAssetId = useMemo(() => {
    const map = new Map<string, Job>();
    if (!jobs.data) return map;
    for (const j of jobs.data) {
      if ((j.status === "queued" || j.status === "running") && !map.has(j.asset_id)) {
        map.set(j.asset_id, j);
      }
    }
    return map;
  }, [jobs.data]);

  const upload = useMutation({
    mutationFn: async ({
      file,
      title,
      profileIds,
      autoReformat,
    }: {
      file: File;
      title: string;
      profileIds: string[];
      autoReformat: boolean;
    }) => {
      return api.upload(file, title, profileIds, autoReformat);
    },
    onSuccess: (res) => {
      setIsUploadOpen(false);
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      if (res?.asset?.id) {
        navigate(`/assets/${res.asset.id}`);
      }
    },
    onError: (error: Error) => setUploadError(error.message),
  });

  const remove = useMutation({
    mutationFn: api.deleteAsset,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets"] }),
  });

  const totalMasters = assets.data?.length ?? 0;
  const totalVariants = assets.data?.reduce((acc, a) => acc + a.variant_count, 0) ?? 0;
  const totalPublished = assets.data?.reduce((acc, a) => acc + a.published_count, 0) ?? 0;

  return (
    <div className="space-y-6">
      {/* Page Header ----------------------------------------------------- */}
      <div className="relative">
        {/* Offset colour block behind the title. Pure decoration, but it stops
            the page opening on a flat wall of cream. */}
        <div
          aria-hidden="true"
          className="absolute -left-2 -top-2 h-14 w-40 -rotate-2 rounded-brutal border-3 border-ink-600 bg-pop-cyan"
        />
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="font-display text-4xl leading-none text-slate-100">
              MEDIA
              <span className="ml-2 inline-block -rotate-1 rounded-brutal border-3 border-ink-600 bg-pop-yellow px-2 shadow-brutal">
                LIBRARY
              </span>
            </h2>
            <p className="mt-3 max-w-2xl text-sm font-medium text-slate-400">
              Ingest master assets and deliver platform-ready ratios with subject-aware
              smart crop, key still extraction, and active-speaker tracked vertical reels.
            </p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {["16:9", "1:1", "9:16", "4:5"].map((r) => (
                <RatioBadge key={r} ratio={r} />
              ))}
            </div>
          </div>

          <button
            type="button"
            className="btn-primary shrink-0 text-base"
            onClick={() => {
              setUploadError(null);
              setIsUploadOpen(true);
            }}
          >
            <span className="text-lg leading-none">＋</span>
            <span>Ingest Master</span>
          </button>
        </div>
      </div>

      <div className="h-1 w-full border-y-3 border-ink-600 stripes-warn" aria-hidden="true" />

      {/* KPI Stats Bar */}
      {assets.data && assets.data.length > 0 && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {(
            [
              { label: "Master Assets", value: totalMasters, bg: "bg-pop-cyan", tilt: "-rotate-1" },
              { label: "Rendered Variants", value: totalVariants, bg: "bg-pop-purple", tilt: "rotate-1" },
              { label: "Published", value: totalPublished, bg: "bg-pop-lime", tilt: "-rotate-1" },
              {
                label: "Compliance",
                value:
                  totalVariants > 0
                    ? `${Math.round((totalPublished / totalVariants) * 100)}%`
                    : "—",
                bg: "bg-pop-yellow",
                tilt: "rotate-1",
              },
            ] as const
          ).map((kpi) => (
            <div
              key={kpi.label}
              className={`${kpi.tilt} rounded-brutal border-3 border-ink-600 ${kpi.bg} p-3 shadow-brutal
                          transition-transform duration-150 hover:rotate-0 hover:scale-[1.03]`}
            >
              <span className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-black/70">
                {kpi.label}
              </span>
              <p className="font-display text-3xl leading-tight text-black">{kpi.value}</p>
            </div>
          ))}
        </div>
      )}

      {uploadError && <ErrorBox error={uploadError} />}
      {assets.isLoading && <Spinner label="Loading library assets…" />}
      {assets.isError && <ErrorBox error={assets.error} />}

      {/* Empty State */}
      {assets.data && assets.data.length === 0 && (
        <div
          onClick={() => {
            setUploadError(null);
            setIsUploadOpen(true);
          }}
          className="flex flex-col items-center justify-center rounded-brutal border-2 border-dashed border-ink-600 bg-ink-800 p-12 text-center cursor-pointer transition hover:border-slate-500 hover:bg-ink-800"
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-ink-700 text-accent mb-4 border-[2.5px] border-ink-600">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
          <h3 className="text-base font-semibold text-slate-100">No assets in library yet</h3>
          <p className="mt-1 max-w-sm text-xs text-slate-400">
            Click here to ingest a master image or video. You can choose specific delivery ratios (16:9, 1:1, 9:16, 4:5) to reformat and validate.
          </p>
          <button type="button" className="btn-primary mt-4 text-xs">
            Ingest First Master
          </button>
        </div>
      )}

      {/* Asset Cards Grid */}
      {assets.data && assets.data.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {assets.data.map((asset) => (
            <AssetCard
              key={asset.id}
              asset={asset}
              activeJob={activeJobsByAssetId.get(asset.id)}
              onDelete={remove.mutate}
            />
          ))}
        </div>
      )}

      {/* Ingest & Delivery Modal */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUpload={async (file, title, profileIds, autoReformat) => {
          await upload.mutateAsync({ file, title, profileIds, autoReformat });
        }}
        isUploading={upload.isPending}
      />
    </div>
  );
}
