import { useEffect, useState } from "react";
import type { MediaKind, Variant } from "../api/types";
import { AVAILABLE_PROFILES, RatioSelector } from "./RatioSelector";

interface ReformatModalProps {
  isOpen: boolean;
  onClose: () => void;
  mediaKind: MediaKind;
  existingVariants: Variant[];
  onReformat: (profileIds: string[]) => Promise<void>;
  isProcessing: boolean;
}

export function ReformatModal({
  isOpen,
  onClose,
  mediaKind,
  existingVariants,
  onReformat,
  isProcessing,
}: ReformatModalProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Build existing status lookup
  const existingStatusMap: Record<string, { status: string; inLibrary: boolean }> = {};
  for (const v of existingVariants) {
    existingStatusMap[v.profile_id] = {
      status: v.status,
      inLibrary: v.in_library,
    };
  }

  // When modal opens, default selectedIds to unrendered profiles or all profiles
  useEffect(() => {
    if (isOpen) {
      const allOptions = AVAILABLE_PROFILES[mediaKind] || [];
      const unrendered = allOptions.filter((o) => !existingStatusMap[o.id]);
      if (unrendered.length > 0) {
        setSelectedIds(unrendered.map((o) => o.id));
      } else {
        setSelectedIds(allOptions.map((o) => o.id));
      }
    }
  }, [isOpen, mediaKind]);

  // Handle ESC key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isProcessing) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isProcessing, onClose]);

  if (!isOpen) return null;

  const handleSubmit = async () => {
    if (selectedIds.length === 0) return;
    await onReformat(selectedIds);
    onClose();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="reformat-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink-900/80 backdrop-blur-sm animate-in fade-in duration-200"
    >
      <div
        className="w-full max-w-2xl max-h-[92vh] overflow-y-auto rounded-xl border border-ink-600 bg-ink-800 shadow-2xl transition-all"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-ink-600/80 px-6 py-4">
          <div>
            <h2 id="reformat-dialog-title" className="text-base font-semibold text-white">
              Choose Ratios to Render
            </h2>
            <p className="text-xs text-slate-400">
              Select one or more delivery ratios to generate or re-render for this asset.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isProcessing}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-ink-700 hover:text-white transition disabled:opacity-40"
            aria-label="Close dialog"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-6 py-5">
          <RatioSelector
            mediaKind={mediaKind}
            selectedIds={selectedIds}
            onChange={setSelectedIds}
            existingStatusMap={existingStatusMap}
          />
        </div>

        <div className="flex items-center justify-between border-t border-ink-600/80 px-6 py-4 bg-ink-900/40">
          <button
            type="button"
            onClick={onClose}
            disabled={isProcessing}
            className="btn-ghost"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={handleSubmit}
            disabled={isProcessing || selectedIds.length === 0}
            className="btn-primary text-xs"
          >
            {isProcessing ? "Queueing…" : `Render Selected (${selectedIds.length} Ratios)`}
          </button>
        </div>
      </div>
    </div>
  );
}
