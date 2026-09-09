"""One-time, idempotent importer for the prototype JSON persistence files."""

from __future__ import annotations

import argparse
from pathlib import Path

import database
import server


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parent
    parser.add_argument("--database", type=Path, default=server.DATABASE_PATH)
    parser.add_argument("--accounts", type=Path, default=root / "accounts.local.json")
    parser.add_argument("--characters", type=Path, default=server.CHARACTER_STORE_PATH)
    parser.add_argument("--campaign", type=Path, default=server.CAMPAIGN_STATE_PATH)
    args = parser.parse_args()

    connection = database.initialize(args.database)
    try:
        counts = database.import_legacy_json(
            connection,
            accounts_path=args.accounts,
            characters_path=args.characters,
            campaign_path=args.campaign,
            normalize_character=server._normalize_character_record,
        )
        print(f"Database: {args.database.resolve()}")
        print(f"Schema version: {database.schema_version(connection)}")
        print("Imported: " + ", ".join(f"{name}={count}" for name, count in counts.items()))
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
