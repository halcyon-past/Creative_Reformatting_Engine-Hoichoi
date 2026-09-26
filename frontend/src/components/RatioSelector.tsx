import clsx from "clsx";
import type { MediaKind } from "../api/types";

export interface ProfileOption {
  id: string;
  ratio: string;
  label: string;
  width: number;
  height: number;
  platform: string;
  description: string;
  kind: MediaKind;
  isSpeakerAware?: boolean;
}

export const AVAILABLE_PROFILES: Record<MediaKind, ProfileOption[]> = {
  image: [
    {
      id: "hero_landscape_16x9",
      ratio: "16:9",
      label: "Hero Landscape",
      width: 1920,
      height: 1080,
      platform: "OTT Desktop & TV Banner",
      description: "Rule-of-thirds composition composing around subjects with balanced headroom.",
      kind: "image",
    },
    {
      id: "social_square_1x1",
      ratio: "1:1",
      label: "Social Square",
      width: 1080,
      height: 1080,
      platform: "Instagram & Feed Square",
      description: "Composes around focal subjects with safe margins to avoid Naive center cuts.",
      kind: "image",
    },
    {
      id: "story_vertical_9x16",
      ratio: "9:16",
      label: "Story / Vertical",
      width: 1080,
      height: 1920,
      platform: "Instagram Stories & TikTok",
      description: "Subject composition respecting IG/TikTok top & bottom UI chrome safe zones.",
      kind: "image",
    },
    {
      id: "feed_portrait_4x5",
      ratio: "4:5",
      label: "Feed Portrait",
      width: 1080,
      height: 1350,
      platform: "Instagram Feed Portrait",
      description: "Maximized vertical feed engagement without clipping significant subjects.",
      kind: "image",
    },
  ],
  video: [
    {
      id: "reel_vertical_9x16",
      ratio: "9:16",
      label: "Vertical Reel (Speaker-Aware)",
      width: 1080,
      height: 1920,
      platform: "Reels / Shorts / TikTok",
      description: "Dynamic active-speaker tracking in sync with speech audio and smooth pans.",
      kind: "video",
      isSpeakerAware: true,
    },
    {
      id: "video_still_16x9",
      ratio: "16:9",
      label: "Key Still (from Video)",
      width: 1920,
      height: 1080,
      platform: "High-Clarity Thumbnail",
      description: "Peak-sharpness frame extraction composed around detected subjects.",
      kind: "image",
    },
  ],
};

function RatioSilhouette({ ratio }: { ratio: string }) {
  // Proportional box visualization
  switch (ratio) {
    case "16:9":
      return (
        <div className="relative flex h-8 w-14 items-center justify-center rounded border border-slate-600 bg-ink-900/90 shadow-inner">
          <div className="h-6 w-11 rounded-sm border border-dashed border-accent/40" />
          <span className="absolute text-[9px] font-mono text-slate-300">16:9</span>
        </div>
      );
    case "1:1":
      return (
        <div className="relative flex h-9 w-9 items-center justify-center rounded border border-slate-600 bg-ink-900/90 shadow-inner">
          <div className="h-7 w-7 rounded-sm border border-dashed border-accent/40" />
          <span className="absolute text-[9px] font-mono text-slate-300">1:1</span>
        </div>
      );
    case "9:16":
      return (
        <div className="relative flex h-11 w-7 items-center justify-center rounded border border-slate-600 bg-ink-900/90 shadow-inner">
          <div className="h-8 w-5 rounded-sm border border-dashed border-accent/40" />
          <span className="absolute text-[8px] font-mono text-slate-300">9:16</span>
        </div>
      );
    case "4:5":
      return (
        <div className="relative flex h-10 w-8 items-center justify-center rounded border border-slate-600 bg-ink-900/90 shadow-inner">
          <div className="h-8 w-6 rounded-sm border border-dashed border-accent/40" />
          <span className="absolute text-[8px] font-mono text-slate-300">4:5</span>
        </div>
      );
    default:
      return null;
  }
}

export function RatioSelector({
  mediaKind,
  selectedIds,
  onChange,
  existingStatusMap,
}: {
  mediaKind: MediaKind;
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  existingStatusMap?: Record<string, { status: string; inLibrary: boolean }>;
}) {
  const options = AVAILABLE_PROFILES[mediaKind] || [];

  const toggle = (id: string) => {
    if (selectedIds.includes(id)) {
      onChange(selectedIds.filter((x) => x !== id));
    } else {
      onChange([...selectedIds, id]);
    }
  };

  const selectAll = () => {
    onChange(options.map((o) => o.id));
  };

  const clearAll = () => {
    onChange([]);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-slate-300">
          Target Ratios ({selectedIds.length} of {options.length} selected)
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={selectAll}
            className="text-xs text-accent hover:underline underline-offset-2"
          >
            Select All
          </button>
          <span className="text-slate-600">·</span>
          <button
            type="button"
            onClick={clearAll}
            className="text-xs text-slate-400 hover:text-slate-200"
          >
            Clear
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
        {options.map((option) => {
          const isSelected = selectedIds.includes(option.id);
          const existing = existingStatusMap?.[option.id];

          return (
            <div
              key={option.id}
              role="button"
              tabIndex={0}
              onClick={() => toggle(option.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  toggle(option.id);
                }
              }}
              className={clsx(
                "group relative flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-left transition-all select-none",
                isSelected
                  ? "border-accent bg-ink-700/80 ring-1 ring-accent/30 shadow-sm"
                  : "border-ink-600 bg-ink-800/80 hover:border-slate-500 hover:bg-ink-700/40",
              )}
            >
              <div className="shrink-0 pt-0.5">
                <RatioSilhouette ratio={option.ratio} />
              </div>

              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center justify-between gap-1.5">
                  <span className="truncate text-xs font-semibold text-slate-100">
                    {option.label}
                  </span>
                  <span className="shrink-0 rounded bg-ink-900 px-1.5 py-0.5 font-mono text-[10px] text-slate-400 border border-ink-600">
                    {option.width}×{option.height}
                  </span>
                </div>

                <p className="text-[11px] font-medium text-accent/90">
                  {option.platform}
                </p>
                <p className="line-clamp-2 text-[11px] leading-relaxed text-slate-400">
                  {option.description}
                </p>

                {existing && (
                  <div className="pt-1">
                    <span
                      className={clsx(
                        "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium",
                        existing.inLibrary
                          ? "bg-emerald-500/15 text-emerald-300"
                          : "bg-rose-500/15 text-rose-300",
                      )}
                    >
                      {existing.inLibrary ? "Already in Library" : "Quarantined / Failed"}
                    </span>
                  </div>
                )}
              </div>

              <div className="shrink-0 pt-0.5">
                <div
                  className={clsx(
                    "flex h-4 w-4 items-center justify-center rounded border transition-colors",
                    isSelected
                      ? "border-accent bg-accent text-ink-900"
                      : "border-slate-500 bg-ink-900 group-hover:border-slate-400",
                  )}
                >
                  {isSelected && (
                    <svg
                      className="h-3 w-3 stroke-[3]"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
