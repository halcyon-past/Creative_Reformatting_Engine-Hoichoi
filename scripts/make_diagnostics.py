"""Build an inspectable evidence bundle from the current library.

Produces, under ``diagnostics/``:

* ``index.html``          -- open this; every variant, its verdict and its report
* ``contact_<asset>.jpg`` -- all image variants side by side
* ``strip_<variant>.jpg`` -- a filmstrip of each rendered reel
* ``report_<variant>.json``
* ``audit_<asset>.json``
* ``summary.md``

The point is that the system's own verdicts can be checked against the actual
pixels without running anything.

    python scripts/make_diagnostics.py
"""

from __future__ import annotations

import asyncio
import html
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "src"))

from cre.config import get_settings
from cre.container import build_container

OUT = REPO / "diagnostics"


def _write_jpeg(image: np.ndarray, dest: Path, quality: int = 88) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if ok:
        buf.tofile(str(dest))


def contact_sheet(paths: list[tuple[str, Path]], dest: Path, height: int = 420) -> bool:
    tiles: list[np.ndarray] = []
    for label, path in paths:
        img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            continue
        h, w = img.shape[:2]
        tile = cv2.resize(img, (max(1, int(w * height / h)), height), interpolation=cv2.INTER_AREA)
        cv2.rectangle(tile, (0, 0), (tile.shape[1] - 1, 22), (20, 20, 20), -1)
        cv2.putText(tile, label[:34], (5, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (90, 230, 120), 1)
        tiles.append(tile)
        tiles.append(np.full((height, 6, 3), 255, np.uint8))
    if not tiles:
        return False
    _write_jpeg(np.hstack(tiles[:-1]), dest)
    return True


def filmstrip(video: Path, dest: Path, count: int = 10, height: int = 400) -> bool:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return False
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    tiles: list[np.ndarray] = []
    try:
        if total <= 2:
            return False
        for idx in np.linspace(2, total - 3, count).astype(int):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ok, frame = cap.read()
            if not ok:
                continue
            h, w = frame.shape[:2]
            tile = cv2.resize(
                frame, (max(1, int(w * height / h)), height), interpolation=cv2.INTER_AREA
            )
            cv2.putText(
                tile, f"{idx / fps:.1f}s", (6, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 255), 2,
            )
            tiles.append(tile)
            tiles.append(np.full((height, 4, 3), 255, np.uint8))
    finally:
        cap.release()
    if not tiles:
        return False
    _write_jpeg(np.hstack(tiles[:-1]), dest)
    return True


async def main() -> int:
    settings = get_settings()
    container = build_container(settings)
    await container.startup(start_worker=False)

    OUT.mkdir(parents=True, exist_ok=True)
    summary: list[str] = ["# Diagnostics\n"]
    cards: list[str] = []

    try:
        assets = await container.assets.list_assets()
        if not assets:
            print("No assets in the library. Run the pipeline first.")
            return 1

        for asset in assets:
            variants = await container.repo.list_variants(asset.id)
            published = [v for v in variants if v.in_library]
            summary.append(
                f"\n## {asset.title} (`{asset.id}`)\n\n"
                f"- kind: {asset.kind.value}, {asset.width if hasattr(asset, 'width') else ''}\n"
                f"- **{len(published)}/{len(variants)} variants published**\n"
            )

            # audit trail
            events = await container.audit.list(asset_id=asset.id, limit=500)
            (OUT / f"audit_{asset.id}.json").write_text(
                json.dumps([e.model_dump(mode="json") for e in events], indent=2),
                encoding="utf-8",
            )

            stills: list[tuple[str, Path]] = []
            for variant in variants:
                verdict = (
                    variant.report.verdict.value.upper() if variant.report else "NO REPORT"
                )
                summary.append(
                    f"  - `{variant.profile_id}` {variant.ratio_label} "
                    f"{variant.width}x{variant.height} -> **{verdict}**"
                )
                if variant.report:
                    for r in variant.report.results:
                        if r.outcome.value in ("fail", "warn"):
                            summary.append(f"      - {r.outcome.value.upper()} {r.rule_id}: {r.message}")
                    (OUT / f"report_{variant.id}.json").write_text(
                        json.dumps(variant.report.model_dump(mode="json"), indent=2),
                        encoding="utf-8",
                    )

                if not variant.storage_key:
                    continue
                try:
                    src = container.storage.local_path(variant.storage_key)
                except Exception as exc:  # noqa: BLE001 - a missing file is expected
                    print(f"  skipped {variant.id}: {exc}")
                    continue

                media_rel = f"media/{variant.id}{src.suffix}"
                (OUT / "media").mkdir(exist_ok=True)
                shutil.copy2(src, OUT / media_rel)

                extra = ""
                if variant.kind.value == "video":
                    strip = OUT / f"strip_{variant.id}.jpg"
                    if filmstrip(src, strip):
                        extra = f'<img src="{strip.name}" class="strip">'
                else:
                    stills.append((variant.profile_id, src))

                rationale = "".join(
                    f"<li>{html.escape(line)}</li>"
                    for line in (variant.crop_decision.rationale if variant.crop_decision else [])
                )
                rules = "".join(
                    f'<li class="{r.outcome.value}"><b>{r.outcome.value.upper()}</b> '
                    f"{html.escape(r.rule_id)} — {html.escape(r.message)}</li>"
                    for r in (variant.report.results if variant.report else [])
                    if r.outcome.value in ("fail", "warn")
                )
                player = (
                    f'<video src="{media_rel}" controls loop></video>'
                    if variant.kind.value == "video"
                    else f'<img src="{media_rel}" class="var">'
                )
                cards.append(f"""
<div class="card {'pass' if variant.in_library else 'fail'}">
  <h3>{html.escape(variant.profile_id)}
      <span class="badge">{variant.ratio_label}</span>
      <span class="verdict">{verdict}</span></h3>
  <p class="meta">{variant.width}x{variant.height}
     {f'· {variant.duration_s:.1f}s' if variant.duration_s else ''}
     · asset {html.escape(asset.title)}</p>
  {player}{extra}
  <details open><summary>Why this crop</summary><ul>{rationale}</ul></details>
  {f'<details open><summary>Findings</summary><ul class="rules">{rules}</ul></details>' if rules else '<p class="clean">No findings.</p>'}
</div>""")

            if stills:
                sheet = OUT / f"contact_{asset.id}.jpg"
                if contact_sheet(stills, sheet):
                    cards.insert(0, f'<div class="card wide"><h3>All ratios — '
                                    f'{html.escape(asset.title)}</h3>'
                                    f'<img src="{sheet.name}" class="var"></div>')

        (OUT / "summary.md").write_text("\n".join(summary), encoding="utf-8")
        (OUT / "index.html").write_text(_page("".join(cards)), encoding="utf-8")
        print(f"Wrote {OUT}")
        print(f"Open: {OUT / 'index.html'}")
        return 0
    finally:
        await container.shutdown()


def _page(body: str) -> str:
    return f"""<!doctype html>
<meta charset="utf-8"><title>CRE diagnostics</title>
<style>
 body{{background:#0b0f17;color:#cbd5e1;font:14px system-ui,sans-serif;margin:0;padding:24px}}
 h1{{color:#fff;font-size:18px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:16px}}
 .card{{background:#111827;border:1px solid #273043;border-radius:8px;padding:12px}}
 .card.fail{{border-color:#7f1d3a}} .card.pass{{border-color:#14532d}}
 .card.wide{{grid-column:1/-1}}
 h3{{margin:0 0 4px;color:#e2e8f0;font-size:14px}}
 .badge{{background:#1b2333;border-radius:10px;padding:1px 7px;font-size:11px;font-family:monospace}}
 .verdict{{float:right;font-size:11px;font-weight:700}}
 .card.pass .verdict{{color:#4ade80}} .card.fail .verdict{{color:#fb7185}}
 .meta{{color:#64748b;font-size:11px;margin:0 0 8px;font-family:monospace}}
 img.var,video{{width:100%;background:#000;border-radius:4px;max-height:460px;object-fit:contain}}
 img.strip{{width:100%;border-radius:4px;margin-top:8px}}
 details{{margin-top:8px}} summary{{cursor:pointer;color:#94a3b8;font-size:12px}}
 ul{{margin:6px 0 0;padding-left:18px;font-size:12px;line-height:1.6}}
 .rules .fail{{color:#fb7185}} .rules .warn{{color:#fbbf24}}
 .clean{{color:#4ade80;font-size:12px}}
</style>
<h1>Creative Reformatting Engine — evidence bundle</h1>
<p style="color:#64748b;font-size:12px">Every derived variant, the crop rationale
that produced it, and the compliance findings. Green = published, red = quarantined.</p>
<div class="grid">{body}</div>
"""


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
