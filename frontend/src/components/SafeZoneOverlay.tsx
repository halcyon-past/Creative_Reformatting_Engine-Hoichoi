export interface SafeZoneOverlayProps {
  ratio: string;
  showSafeZones: boolean;
  showPlatformChrome: boolean;
}

export function SafeZoneOverlay({
  ratio,
  showSafeZones,
  showPlatformChrome,
}: SafeZoneOverlayProps) {
  if (!showSafeZones && !showPlatformChrome) return null;

  const isVertical = ratio === "9:16";

  return (
    <div className="pointer-events-none absolute inset-0 z-10 overflow-hidden select-none">
      {/* Safe Zones: Action Safe and Title Safe */}
      {showSafeZones && (
        <>
          {/* Action Safe (typically 90% of frame or specified) */}
          <div
            className="absolute border border-emerald-400/80 border-dashed"
            style={{
              top: isVertical ? "14%" : "4%",
              bottom: isVertical ? "16%" : "4%",
              left: isVertical ? "5%" : "4%",
              right: isVertical ? "5%" : "4%",
            }}
          >
            <span className="absolute top-1 left-1.5 rounded bg-emerald-950/80 px-1 py-0.5 font-mono text-[9px] font-medium text-green-700 backdrop-blur-xs">
              Action Safe
            </span>
          </div>

          {/* Title Safe */}
          <div
            className="absolute border border-cyan-400/70 border-dotted"
            style={{
              top: isVertical ? "18%" : "8%",
              bottom: isVertical ? "20%" : "8%",
              left: isVertical ? "8%" : "8%",
              right: isVertical ? "8%" : "8%",
            }}
          >
            <span className="absolute bottom-1 right-1.5 rounded bg-cyan-950/80 px-1 py-0.5 font-mono text-[9px] font-medium text-cyan-300 backdrop-blur-xs">
              Title Safe
            </span>
          </div>
        </>
      )}

      {/* Platform UI Chrome (Only for 9:16 Story / Reel formats) */}
      {showPlatformChrome && isVertical && (
        <>
          {/* Subtle Smartphone Camera Notch */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 h-3.5 w-20 rounded-b-xl bg-black/70 border-b border-x border-white/10 flex items-center justify-center gap-2 z-20">
            <div className="h-1.5 w-1.5 rounded-full bg-slate-900 border border-slate-700" />
            <div className="h-1 w-6 rounded-full bg-slate-800" />
          </div>

          {/* Top Status Bar & Profile header */}
          <div
            className="absolute inset-x-0 top-0 flex items-center justify-between bg-gradient-to-b from-black/80 via-black/40 to-transparent px-3.5 pt-4 pb-6 text-white/90"
            style={{ height: "13%" }}
          >
            <div className="flex items-center gap-1.5">
              <div className="h-4 w-4 rounded-full bg-accent/80 flex items-center justify-center text-[9px] font-bold text-ink-950">
                H
              </div>
              <span className="text-[10px] font-semibold tracking-wide">hoichoi.tv</span>
            </div>
            <span className="rounded bg-rose-500/80 px-1.5 py-0.5 text-[8px] font-bold text-white uppercase tracking-wider shadow-brutal-sm">
              Protected Chrome
            </span>
          </div>

          {/* Bottom Captions & Audio rail */}
          <div
            className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/40 to-transparent px-3 pt-4 pb-2 text-white/90"
            style={{ height: "14%" }}
          >
            <p className="line-clamp-1 text-[10px] font-semibold">@hoichoi · Original Series</p>
            <p className="line-clamp-1 text-[9px] text-white/70">♫ Original Audio · Hoichoi Official</p>
          </div>

          {/* Right Action Rail (Likes, Comments, Share) */}
          <div
            className="absolute right-2 flex flex-col items-center gap-3 text-white/80"
            style={{ top: "55%", bottom: "14%", width: "16%" }}
          >
            <div className="flex flex-col items-center">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-black/40 backdrop-blur-xs text-[10px]">
                ♥
              </div>
              <span className="text-[8px] font-medium">84.2K</span>
            </div>
            <div className="flex flex-col items-center">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-black/40 backdrop-blur-xs text-[10px]">
                💬
              </div>
              <span className="text-[8px] font-medium">1.2K</span>
            </div>
            <div className="flex flex-col items-center">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-black/40 backdrop-blur-xs text-[10px]">
                ↗
              </div>
              <span className="text-[8px] font-medium">Share</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
