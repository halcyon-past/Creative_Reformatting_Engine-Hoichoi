import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Empty, ErrorBox, Spinner, formatBytes } from "../components/common";
import type { Asset } from "../api/types";

function AssetCard({ asset, onDelete }: { asset: Asset; onDelete: (id: string) => void }) {
  const complete = asset.variant_count > 0;
  const allPassed = complete && asset.published_count === asset.variant_count;

  return (
    <div className="card group overflow-hidden transition-colors hover:border-ink-600/80">
      <Link to={`/assets/${asset.id}`}>
        <div className="checker relative aspect-video overflow-hidden bg-ink-900">
          {asset.thumbnail_url ? (
            <img
              src={asset.thumbnail_url}
              alt={asset.title}
              className="h-full w-full object-contain"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-slate-600">
              no preview
            </div>
          )}
          <span className="absolute left-2 top-2 chip bg-ink-900/80 text-slate-300">
            {asset.kind}
          </span>
        </div>
      </Link>

      <div className="space-y-2 p-3">
        <div className="flex items-start justify-between gap-2">
          <Link to={`/assets/${asset.id}`} className="min-w-0">
            <p className="truncate text-sm font-medium text-slate-100">{asset.title}</p>
            <p className="truncate text-xs text-slate-500">
              {asset.width}×{asset.height}
              {asset.duration_s ? ` · ${asset.duration_s.toFixed(1)}s` : ""}
              {` · ${formatBytes(asset.size_bytes)}`}
            </p>
          </Link>
          <button
            onClick={() => onDelete(asset.id)}
            className="shrink-0 text-xs text-slate-600 opacity-0 transition hover:text-rose-400 group-hover:opacity-100"
            title="Delete asset"
          >
            delete
          </button>
        </div>

        <div className="flex items-center gap-2 text-xs">
          {complete ? (
            <span
              className={
                allPassed
                  ? "chip bg-emerald-500/15 text-emerald-300"
                  : "chip bg-amber-500/15 text-amber-300"
              }
            >
              {asset.published_count}/{asset.variant_count} in library
            </span>
          ) : (
            <span className="chip bg-sky-500/15 text-sky-300">processing…</span>
          )}
          {asset.status === "failed" && (
            <span className="chip bg-rose-500/15 text-rose-300">failed</span>
          )}
        </div>
      </div>
    </div>
  );
}

export default function LibraryPage() {
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const assets = useQuery({
    queryKey: ["assets"],
    queryFn: api.listAssets,
    // Poll while anything is still being processed, so progress appears
    // without the user reloading.
    refetchInterval: (query) => {
      const data = query.state.data as Asset[] | undefined;
      const busy = data?.some((a) => a.status !== "ready" && a.status !== "failed");
      return busy ? 2000 : false;
    },
  });

  const upload = useMutation({
    mutationFn: (file: File) => api.upload(file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets"] }),
    onError: (error: Error) => setUploadError(error.message),
  });

  const remove = useMutation({
    mutationFn: api.deleteAsset,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets"] }),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Library</h2>
          <p className="text-sm text-slate-500">
            Upload a master image or video; every platform ratio is derived, validated
            and published automatically.
          </p>
        </div>
        <div>
          <input
            ref={fileInput}
            type="file"
            accept="image/*,video/*"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              setUploadError(null);
              if (file) upload.mutate(file);
              event.target.value = "";
            }}
          />
          <button
            className="btn-primary"
            disabled={upload.isPending}
            onClick={() => fileInput.current?.click()}
          >
            {upload.isPending ? "Uploading…" : "Upload master"}
          </button>
        </div>
      </div>

      {uploadError && <ErrorBox error={uploadError} />}
      {assets.isLoading && <Spinner label="Loading library…" />}
      {assets.isError && <ErrorBox error={assets.error} />}

      {assets.data && assets.data.length === 0 && (
        <Empty
          title="Nothing in the library yet"
          hint="Upload a master image or video to generate its platform variants."
        />
      )}

      {assets.data && assets.data.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {assets.data.map((asset) => (
            <AssetCard key={asset.id} asset={asset} onDelete={remove.mutate} />
          ))}
        </div>
      )}
    </div>
  );
}
