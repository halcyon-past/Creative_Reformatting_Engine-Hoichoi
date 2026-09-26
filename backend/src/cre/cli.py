"""Command-line interface.

Runs the whole pipeline headlessly, which is how the end-to-end test harness
exercises it and how a reviewer can reproduce a result without the UI.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from cre.config import get_settings
from cre.container import build_container
from cre.domain.enums import RuleOutcome, Verdict
from cre.domain.models import Variant
from cre.logging_config import configure_logging


def _print_variant(variant: Variant, verbose: bool = False) -> None:
    report = variant.report
    verdict = report.verdict.value.upper() if report else "NO REPORT"
    mark = "PASS" if report and report.verdict is Verdict.PASS else "FAIL"
    size = f"{variant.width}x{variant.height}" if variant.width else "?"

    print(f"\n  [{mark}] {variant.profile_id:<24} {variant.ratio_label:<6} {size:<12} "
          f"{variant.status.value}")

    if variant.crop_decision:
        d = variant.crop_decision
        crop = d.crop
        print(f"        crop  x={crop.x1:.0f} y={crop.y1:.0f} "
              f"w={crop.x2 - crop.x1:.0f} h={crop.y2 - crop.y1:.0f}  "
              f"coverage={d.subject_coverage:.1%} faces_intact={d.faces_fully_inside} "
              f"clipped={d.faces_clipped}")
        for line in d.rationale:
            print(f"        - {line}")

    if report:
        counts = report.summary()
        print(f"        verdict={verdict}  "
              f"pass={counts['pass']} fail={counts['fail']} "
              f"warn={counts['warn']} skip={counts['skip']}")
        for result in report.results:
            if result.outcome is RuleOutcome.PASS and not verbose:
                continue
            symbol = {
                RuleOutcome.FAIL: "FAIL", RuleOutcome.WARN: "WARN",
                RuleOutcome.SKIP: "skip", RuleOutcome.PASS: "ok",
            }[result.outcome]
            print(f"        [{symbol:>4}] {result.rule_id}: {result.message}")
    if variant.error:
        print(f"        error: {variant.error}")


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    if args.data_dir:
        settings.data_dir = Path(args.data_dir)
        settings.ensure_dirs()
    configure_logging(settings.env, debug=args.verbose)

    container = build_container(settings)
    await container.startup(start_worker=False)

    try:
        if args.command == "spec":
            spec = container.spec
            print(f"{spec.spec_id} v{spec.spec_version}")
            for profile in spec.profiles:
                print(f"  {profile.id:<24} {profile.ratio:<6} "
                      f"{profile.width}x{profile.height:<6} {profile.kind.value}")
            for kind, ids in spec.render_sets.items():
                print(f"  render_set[{kind}]: {', '.join(ids)}")
            return 0

        if args.command == "process":
            source = Path(args.path)
            print(f"Ingesting {source.name} ...")
            asset = await container.assets.ingest_path(source, title=args.title)
            media = asset.media
            print(f"  asset {asset.id}  {asset.kind.value}  "
                  f"{media.width}x{media.height}"
                  + (f"  {media.duration_s:.1f}s @ {media.fps:.2f}fps"
                     if media.duration_s else "")
                  + (f"  audio={media.audio_codec}" if media and media.audio_codec else ""))

            print("\nReformatting ...")
            variants = container.reformat.reformat_all(
                asset,
                progress=lambda p, s: print(f"  {p * 100:5.1f}%  {s}", flush=True),
            )
            for variant in variants:
                await container.repo.save_variant(variant)

            print("\n" + "=" * 78)
            print("RESULTS")
            print("=" * 78)
            for variant in variants:
                _print_variant(variant, verbose=args.verbose)

            published = [v for v in variants if v.in_library]
            print("\n" + "=" * 78)
            print(f"{len(published)}/{len(variants)} variants passed validation "
                  f"and entered the library")
            if args.json:
                Path(args.json).write_text(
                    json.dumps([v.model_dump(mode="json") for v in variants], indent=2),
                    encoding="utf-8",
                )
                print(f"wrote {args.json}")
            return 0 if len(published) == len(variants) else 1

        if args.command == "regenerate":
            asset = await container.assets.get_asset(args.asset_id)
            existing = await container.repo.find_variant(asset.id, args.profile_id)
            print(f"Regenerating {args.profile_id} for {asset.id} ...")
            variant = container.reformat.regenerate_one(
                asset, args.profile_id, existing,
                progress=lambda p, s: print(f"  {p * 100:5.1f}%  {s}", flush=True),
            )
            await container.repo.save_variant(variant)
            _print_variant(variant, verbose=True)
            return 0 if variant.in_library else 1

        if args.command == "list":
            assets = await container.assets.list_assets()
            for asset in assets:
                variants = await container.repo.list_variants(asset.id)
                published = sum(1 for v in variants if v.in_library)
                print(f"{asset.id}  {asset.kind.value:<6} {asset.title:<32} "
                      f"{published}/{len(variants)} in library")
            return 0

        raise SystemExit(f"unknown command: {args.command}")
    finally:
        await container.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(prog="cre", description="Creative Reformatting Engine")
    parser.add_argument("--data-dir", help="override the data directory")
    parser.add_argument("-v", "--verbose", action="store_true", help="show passing rules too")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("spec", help="print the loaded platform spec sheet")
    sub.add_parser("list", help="list ingested assets")

    process = sub.add_parser("process", help="ingest a master and render every variant")
    process.add_argument("path", help="path to the master image or video")
    process.add_argument("--title")
    process.add_argument("--json", help="write the variant records to this JSON file")

    regen = sub.add_parser("regenerate", help="re-render a single variant")
    regen.add_argument("asset_id")
    regen.add_argument("profile_id")

    args = parser.parse_args()
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
