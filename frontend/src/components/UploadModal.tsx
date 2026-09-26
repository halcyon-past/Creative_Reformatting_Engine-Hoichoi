import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import type { MediaKind } from "../api/types";
import { formatBytes } from "./common";
import { AVAILABLE_PROFILES, RatioSelector } from "./RatioSelector";

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUpload: (
    file: File,
    title: string,
    profileIds: string[],
    autoReformat: boolean,
  ) => Promise<void>;
  isUploading: boolean;
  uploadProgress?: number;
}

export function UploadModal({
  isOpen,
  onClose,
  onUpload,
  isUploading,
  uploadProgress,
}: UploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [mediaKind, setMediaKind] = useState<MediaKind>("image");
  const [selectedProfileIds, setSelectedProfileIds] = useState<string[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // When a file is chosen, inspect it
  useEffect(() => {
    if (!file) {
      setFilePreview(null);
      return;
    }

    const kind: MediaKind = file.type.startsWith("video/") ? "video" : "image";
    setMediaKind(kind);

    // Default select all available profiles for this media kind
    const available = AVAILABLE_PROFILES[kind] || [];
    setSelectedProfileIds(available.map((p) => p.id));

    // Auto populate clean title from filename
    const cleanName = file.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
    setTitle(cleanName.charAt(0).toUpperCase() + cleanName.slice(1));

    // Local object URL for preview
    const url = URL.createObjectURL(file);
    setFilePreview(url);

    return () => {
      URL.revokeObjectURL(url);
    };
  }, [file]);

  // Handle ESC key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isUploading) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isUploading, onClose]);

  if (!isOpen) return null;

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      setFile(droppedFile);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      setFile(selected);
    }
  };

  const handleSubmit = async (autoReformat: boolean) => {
    if (!file) return;
    await onUpload(
      file,
      title || file.name,
      autoReformat ? selectedProfileIds : [],
      autoReformat && selectedProfileIds.length > 0,
    );
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink-900/80 backdrop-blur-sm animate-in fade-in duration-200"
    >
      <div
        className="w-full max-w-2xl max-h-[92vh] overflow-y-auto rounded-xl border border-ink-600 bg-ink-800 shadow-2xl transition-all"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-ink-600/80 px-6 py-4">
          <div>
            <h2 id="upload-dialog-title" className="text-base font-semibold text-white">
              Ingest Master & Configure Delivery
            </h2>
            <p className="text-xs text-slate-400">
              Deliver platform-ready ratios with subject-aware smart crop and compliance validation.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isUploading}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-ink-700 hover:text-white transition disabled:opacity-40"
            aria-label="Close dialog"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Modal Body */}
        <div className="space-y-6 px-6 py-5">
          {!file ? (
            /* Dropzone when no file selected */
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragOver(true);
              }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={clsx(
                "flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center cursor-pointer transition-colors",
                isDragOver
                  ? "border-accent bg-accent/5"
                  : "border-slate-700 bg-ink-900/50 hover:border-slate-500 hover:bg-ink-900/80",
              )}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*,video/*"
                className="hidden"
                onChange={handleFileChange}
              />
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-ink-700 text-accent mb-3 border border-ink-600">
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.75}
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                  />
                </svg>
              </div>
              <p className="text-sm font-medium text-slate-200">
                Click to browse or drop master media here
              </p>
              <p className="mt-1 text-xs text-slate-400">
                High-resolution image (JPG, PNG) or Master video (MP4, MOV up to 1080p/4K)
              </p>
            </div>
          ) : (
            /* Selected File Inspection & Settings */
            <div className="space-y-5">
              {/* Media File Card */}
              <div className="flex items-center gap-4 rounded-lg border border-ink-600 bg-ink-900/90 p-3">
                <div className="checker relative flex h-16 w-24 shrink-0 items-center justify-center overflow-hidden rounded border border-ink-600 bg-black">
                  {filePreview && (
                    mediaKind === "video" ? (
                      <video
                        src={filePreview}
                        className="h-full w-full object-contain"
                        muted
                        playsInline
                      />
                    ) : (
                      <img
                        src={filePreview}
                        alt="Master preview"
                        className="h-full w-full object-contain"
                      />
                    )
                  )}
                  <span className="absolute bottom-1 right-1 rounded bg-black/80 px-1 py-0.2 font-mono text-[9px] text-slate-300">
                    {mediaKind.toUpperCase()}
                  </span>
                </div>

                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-xs font-semibold text-slate-200">
                      {file.name}
                    </p>
                    <button
                      type="button"
                      disabled={isUploading}
                      onClick={() => setFile(null)}
                      className="text-xs text-rose-400 hover:text-rose-300 transition"
                    >
                      Change
                    </button>
                  </div>
                  <p className="font-mono text-[11px] text-slate-400">
                    {formatBytes(file.size)} · {file.type || "binary"}
                  </p>
                </div>
              </div>

              {/* Title input */}
              <div className="space-y-1.5">
                <label htmlFor="master-title" className="text-xs font-medium text-slate-300">
                  Asset Title
                </label>
                <input
                  id="master-title"
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Mismatched Episode 01 Banner"
                  className="w-full rounded-lg border border-ink-600 bg-ink-900 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                />
              </div>

              {/* Ratio Selector */}
              <div className="border-t border-ink-600/70 pt-4">
                <RatioSelector
                  mediaKind={mediaKind}
                  selectedIds={selectedProfileIds}
                  onChange={setSelectedProfileIds}
                />
              </div>
            </div>
          )}

          {/* Upload & Progress State */}
          {isUploading && (
            <div className="space-y-2 rounded-lg border border-accent/30 bg-accent/5 p-4">
              <div className="flex items-center justify-between text-xs text-slate-300">
                <span className="flex items-center gap-2 font-medium">
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-accent border-t-transparent" />
                  Uploading master and queueing pipeline…
                </span>
                {uploadProgress !== undefined && (
                  <span className="font-mono">{Math.round(uploadProgress * 100)}%</span>
                )}
              </div>
              {uploadProgress !== undefined && (
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-700">
                  <div
                    className="h-full bg-accent transition-all duration-300"
                    style={{ width: `${Math.round(uploadProgress * 100)}%` }}
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer Actions */}
        <div className="flex items-center justify-between border-t border-ink-600/80 px-6 py-4 bg-ink-900/40">
          <button
            type="button"
            onClick={onClose}
            disabled={isUploading}
            className="btn-ghost"
          >
            Cancel
          </button>

          {file && (
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => handleSubmit(false)}
                disabled={isUploading}
                className="btn-ghost text-xs"
                title="Store the master in library without generating any reformats yet"
              >
                Upload Master Only
              </button>

              <button
                type="button"
                onClick={() => handleSubmit(true)}
                disabled={isUploading || selectedProfileIds.length === 0}
                className="btn-primary text-xs"
              >
                {selectedProfileIds.length > 0
                  ? `Ingest & Format (${selectedProfileIds.length} Ratios)`
                  : "Select at least 1 Ratio"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
