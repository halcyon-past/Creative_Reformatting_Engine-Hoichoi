import type { ReframePoint } from "../api/types";

/**
 * Plots the horizontal crop-centre path over time, coloured by which face track
 * was the active speaker.
 *
 * This is the evidence view for the two properties a reviewer most needs to
 * check by eye: that the crop actually moves (rather than being set once at
 * frame 0 and held), and that it moves *when the speaker changes*.
 */
export default function ReframeTrack({
  points,
  sourceSize,
}: {
  points: ReframePoint[];
  sourceSize: [number, number] | null;
}) {
  if (points.length < 2) return null;

  const width = 640;
  const height = 130;
  const padding = { left: 34, right: 10, top: 12, bottom: 20 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  const sourceWidth = sourceSize?.[0] ?? Math.max(...points.map((p) => p.cx)) * 1.2;
  const t0 = points[0].t;
  const t1 = points[points.length - 1].t;
  const span = Math.max(t1 - t0, 1e-6);

  const x = (t: number) => padding.left + ((t - t0) / span) * plotW;
  const y = (cx: number) => padding.top + (cx / sourceWidth) * plotH;

  // Split into runs of constant speaker so each is drawn in its own colour.
  const palette = ["#5b9dff", "#f0883e", "#5ad18c", "#c792ea", "#e5c07b"];
  const runs: { track: number | null; pts: ReframePoint[] }[] = [];
  for (const point of points) {
    const last = runs[runs.length - 1];
    if (last && last.track === point.active_track_id) last.pts.push(point);
    else runs.push({ track: point.active_track_id, pts: [point] });
  }

  const shotCuts = points.filter((p, i) => i > 0 && p.shot_id !== points[i - 1].shot_id);
  const travel = points
    .slice(1)
    .reduce((acc, p, i) => acc + Math.abs(p.cx - points[i].cx), 0);

  const colourFor = (track: number | null) =>
    track === null ? "#4b5563" : palette[track % palette.length];

  const speakers = [...new Set(points.map((p) => p.active_track_id))].filter(
    (t): t is number => t !== null,
  );

  return (
    <div className="card space-y-2 p-4">
      <div className="flex items-baseline justify-between">
        <h4 className="text-sm font-semibold text-white">Reframe path</h4>
        <span className="font-mono text-[11px] text-slate-500">
          {points.length} pts · {Math.round(travel)}px travel · {shotCuts.length} cut
          {shotCuts.length === 1 ? "" : "s"}
        </span>
      </div>

      <svg viewBox={`0 0 ${width} ${height}`} className="w-full">
        <rect
          x={padding.left}
          y={padding.top}
          width={plotW}
          height={plotH}
          className="fill-ink-900"
        />
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={padding.top + f * plotH}
              y2={padding.top + f * plotH}
              stroke="#273043"
              strokeDasharray="3 3"
            />
            <text x={2} y={padding.top + f * plotH + 3} className="fill-slate-600 text-[8px]">
              {Math.round(f * sourceWidth)}
            </text>
          </g>
        ))}

        {shotCuts.map((cut) => (
          <line
            key={cut.t}
            x1={x(cut.t)}
            x2={x(cut.t)}
            y1={padding.top}
            y2={padding.top + plotH}
            stroke="#f0883e"
            strokeWidth={1}
            strokeDasharray="2 2"
          />
        ))}

        {runs.map((run, i) => {
          if (run.pts.length < 2) return null;
          const d = run.pts
            .map((p, j) => `${j === 0 ? "M" : "L"}${x(p.t).toFixed(1)},${y(p.cx).toFixed(1)}`)
            .join(" ");
          return (
            <path
              key={i}
              d={d}
              fill="none"
              stroke={colourFor(run.track)}
              strokeWidth={2}
              strokeLinejoin="round"
            />
          );
        })}

        <text x={padding.left} y={height - 6} className="fill-slate-600 text-[8px]">
          {t0.toFixed(1)}s
        </text>
        <text x={width - padding.right - 22} y={height - 6} className="fill-slate-600 text-[8px]">
          {t1.toFixed(1)}s
        </text>
      </svg>

      <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
        <span>crop centre X over time</span>
        {speakers.map((track) => (
          <span key={track} className="flex items-center gap-1">
            <span
              className="inline-block h-2 w-3 rounded-sm"
              style={{ backgroundColor: colourFor(track) }}
            />
            speaker #{track}
          </span>
        ))}
        {shotCuts.length > 0 && (
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-3 rounded-sm bg-[#f0883e]" />
            shot cut
          </span>
        )}
      </div>
    </div>
  );
}
