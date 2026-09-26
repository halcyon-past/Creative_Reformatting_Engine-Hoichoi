import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { ErrorBox, Spinner, formatBytes } from "../components/common";
import { UploadModal } from "../components/UploadModal";
import type { Asset } from "../api/types";

function AssetCard({ asset, onDelete }: { asset: Asset; onDelete: (id: string) => void }) {
  const complete = asset.variant_count > 0;
  const allPassed = complete && asset.published_count === asset.variant_count;

  return (
    <div className="card group flex flex-col justify-between overflow-hidden border-ink-600/80 bg-ink-800 transition-all hover:border-slate-500 hover:shadow-lg">
      <Link to={`/assets/${asset.id}`} className="block">
        <div className="checker relative aspect-video w-full overflow-hidden bg-ink-900 border-b border-ink-600/60">
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
            <span className="rounded bg-black/75 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-white uppercase backdrop-blur-xs border border-white/10">
              {asset.kind}
            </span>
            {asset.has_audio && (
              <span className="rounded bg-black/75 px-1.5 py-0.5 font-mono text-[10px] text-slate-300 backdrop-blur-xs border border-white/10">
                ♫ Audio
              </span>
            )}
          </div>
        </div>
      </Link>

      <div className="flex flex-1 flex-col justify-between p-3.5 space-y-3">
        <div className="space-y-1">
          <div className="flex items-start justify-between gap-2">
            <Link to={`/assets/${asset.id}`} className="min-w-0 flex-1">
              <h3 className="truncate text-sm font-semibold text-slate-100 hover:text-accent transition-colors">
                {asset.title}
              </h3>
            </Link>
            <button
              onClick={() => onDelete(asset.id)}
              className="shrink-0 text-slate-500 opacity-0 transition-opacity hover:text-rose-400 group-hover:opacity-100"
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

        <div className="flex items-center justify-between border-t border-ink-600/60 pt-2.5 text-xs">
          <div className="flex items-center gap-1.5">
            {complete ? (
              <span
                className={
                  allPassed
                    ? "inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/20"
                    : "inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-medium bg-amber-500/15 text-amber-300 border border-amber-500/20"
                }
              >
                <span className="font-mono font-semibold">{asset.published_count}/{asset.variant_count}</span>
                <span>in library</span>
              </span>
            ) : asset.status === "failed" ? (
              <span className="inline-flex items-center rounded px-1.5 py-0.5 font-medium bg-rose-500/15 text-rose-300 border border-rose-500/20">
                Failed
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-medium bg-sky-500/15 text-sky-300 border border-sky-500/20">
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
    onSuccess: () => {
      setIsUploadOpen(false);
      queryClient.invalidateQueries({ queryKey: ["assets"] });
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
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-ink-600/70 pb-5">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white">Media Library</h2>
          <p className="mt-1 text-xs text-slate-400 max-w-2xl">
            Ingest master assets and deliver platform-ready ratios (16:9, 1:1, 9:16, 4:5) with subject-aware smart crop, key still extraction, and active-speaker tracked vertical reels.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            className="btn-primary flex items-center gap-2 shadow-sm"
            onClick={() => {
              setUploadError(null);
              setIsUploadOpen(true);
            }}
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            <span>Ingest Master</span>
          </button>
        </div>
      </div>

      {/* KPI Stats Bar */}
      {assets.data && assets.data.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg border border-ink-600/80 bg-ink-800/60 p-3">
            <span className="text-[11px] font-medium text-slate-400">Master Assets</span>
            <p className="mt-0.5 text-lg font-bold font-mono text-white">{totalMasters}</p>
          </div>
          <div className="rounded-lg border border-ink-600/80 bg-ink-800/60 p-3">
            <span className="text-[11px] font-medium text-slate-400">Rendered Variants</span>
            <p className="mt-0.5 text-lg font-bold font-mono text-white">{totalVariants}</p>
          </div>
          <div className="rounded-lg border border-ink-600/80 bg-ink-800/60 p-3">
            <span className="text-[11px] font-medium text-slate-400">Published in Library</span>
            <p className="mt-0.5 text-lg font-bold font-mono text-emerald-400">{totalPublished}</p>
          </div>
          <div className="rounded-lg border border-ink-600/80 bg-ink-800/60 p-3">
            <span className="text-[11px] font-medium text-slate-400">Compliance Rate</span>
            <p className="mt-0.5 text-lg font-bold font-mono text-accent">
              {totalVariants > 0 ? `${Math.round((totalPublished / totalVariants) * 100)}%` : "—"}
            </p>
          </div>
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
          className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-ink-600 bg-ink-800/40 p-12 text-center cursor-pointer transition hover:border-slate-500 hover:bg-ink-800/70"
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-ink-700 text-accent mb-4 border border-ink-600">
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
            <AssetCard key={asset.id} asset={asset} onDelete={remove.mutate} />
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
