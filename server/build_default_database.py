"""Build the distributable default campaign database from server-kit assets."""

from __future__ import annotations

import argparse
from pathlib import Path

import database
from asset_sources import find_structured_asset, parse_gf
from campaign_map import CLIENT_HEX_RECORDS, HEIGHT, RECORD_SIZE, SOURCE_NAME, WIDTH


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build(path: Path, asset_root: Path) -> str:
    source = find_structured_asset("ServerProfiles/Time.gf", server_asset_root=asset_root)
    profile = parse_gf(source.path)
    clock = profile.get("Clock", {})
    starting = profile.get("Clock/StartingDate", {})
    return database.build_default_database(
        path,
        asset_root=asset_root,
        map_id=SOURCE_NAME,
        map_width=WIDTH,
        map_height=HEIGHT,
        map_record_size=RECORD_SIZE,
        map_records=CLIENT_HEX_RECORDS,
        epoch_unix=0.0,
        initial_turn=0,
        turns_per_year=int(clock.get("TurnsPerYear", 10_000)),
        milliseconds_per_turn=int(clock.get("MilliSecondsPerTurn", 120_000)),
        base_year=int(starting.get("BaseYear", 56_200)),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).with_name("default-campaign.sqlite3"))
    parser.add_argument("--assets", type=Path,
                        default=PROJECT_ROOT / "assets" / "server-kit")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        if not args.force:
            parser.error(f"output already exists: {args.output} (use --force to rebuild)")
        args.output.unlink()
    digest = build(args.output, args.assets)
    print(f"Built {args.output} from asset manifest {digest}")


if __name__ == "__main__":
    main()
