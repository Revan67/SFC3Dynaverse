"""SQLite lifecycle helpers for the replacement Dynaverse persistence layer."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Callable


SCHEMA_PATH = Path(__file__).with_name("schema.sql")
MIGRATIONS_PATH = Path(__file__).with_name("migrations")


def connect(path: Path) -> sqlite3.Connection:
    """Open a database with the integrity settings required by the schema."""
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def initialize(path: Path) -> sqlite3.Connection:
    """Create or upgrade a database and return its open connection."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(path)
    try:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        current = schema_version(connection)
        for migration in sorted(MIGRATIONS_PATH.glob("[0-9][0-9][0-9]_*.sql")):
            version = int(migration.name[:3])
            if version <= current:
                continue
            connection.executescript(
                "BEGIN IMMEDIATE;\n"
                + migration.read_text(encoding="utf-8")
                + "\nCOMMIT;"
            )
            current = version
        connection.commit()
    except Exception:
        connection.close()
        raise
    return connection


def schema_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT MAX(version) AS version FROM schema_version").fetchone()
    return int(row["version"] or 0)


def asset_manifest(asset_root: Path) -> tuple[list[dict], str]:
    """Return a deterministic manifest for the effective campaign assets."""
    entries = []
    digest = hashlib.sha256()
    for path in sorted(
        (
            item for item in asset_root.rglob("*")
            if item.is_file()
            and "ValidatedClientFiles" not in item.relative_to(asset_root).parts
            and item.suffix.casefold() not in {".exe", ".dll", ".pdb", ".log"}
        ),
        key=lambda item: item.relative_to(asset_root).as_posix().casefold(),
    ):
        relative_path = path.relative_to(asset_root).as_posix()
        content = path.read_bytes()
        sha256 = hashlib.sha256(content).hexdigest()
        entry = {
            "relative_path": relative_path,
            "source_tier": "server-kit",
            "size": len(content),
            "sha256": sha256,
        }
        entries.append(entry)
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256))
    if not entries:
        raise ValueError(f"asset root is empty: {asset_root}")
    return entries, digest.hexdigest()


def build_default_database(
    path: Path,
    *,
    asset_root: Path,
    map_id: str,
    map_width: int,
    map_height: int,
    map_record_size: int,
    map_records: bytes,
    epoch_unix: float,
    initial_turn: int,
    turns_per_year: int,
    milliseconds_per_turn: int,
    base_year: int,
) -> str:
    """Build a pristine, populated campaign template from server-kit assets."""
    if path.exists():
        raise FileExistsError(f"default campaign database already exists: {path}")
    expected = map_width * map_height * map_record_size
    if len(map_records) != expected:
        raise ValueError(f"map payload has {len(map_records)} bytes; expected {expected}")
    entries, manifest_sha256 = asset_manifest(asset_root)
    connection = initialize(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT INTO campaigns(id, map_id, epoch_unix, initial_turn, next_news_id, "
            "next_mission_id, turns_per_year, milliseconds_per_turn, base_year, "
            "asset_manifest_sha256) VALUES(1, ?, ?, ?, 1, 1, ?, ?, ?, ?)",
            (map_id, epoch_unix, initial_turn, turns_per_year,
             milliseconds_per_turn, base_year, manifest_sha256),
        )
        connection.executemany(
            "INSERT INTO asset_manifest(campaign_id, relative_path, source_tier, size, sha256) "
            "VALUES(1, ?, ?, ?, ?)",
            ((item["relative_path"], item["source_tier"], item["size"], item["sha256"])
             for item in entries),
        )
        connection.executemany(
            "INSERT INTO map_hexes(campaign_id, x, y, client_record) VALUES(1, ?, ?, ?)",
            (
                (x, y, map_records[(y * map_width + x) * map_record_size:
                                   (y * map_width + x + 1) * map_record_size])
                for y in range(map_height)
                for x in range(map_width)
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        connection.close()
        path.unlink(missing_ok=True)
        raise
    connection.close()
    return manifest_sha256


def create_working_database(
    default_path: Path, working_path: Path, *, epoch_unix: float | None = None
) -> bool:
    """Copy the pristine template on first start; never replace live state."""
    if working_path.exists():
        return False
    if not default_path.is_file():
        raise FileNotFoundError(f"default campaign database not found: {default_path}")
    working_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = working_path.with_name(working_path.name + ".tmp")
    if temporary_path.exists():
        temporary_path.unlink()
    try:
        shutil.copy2(default_path, temporary_path)
        temporary_path.replace(working_path)
        if epoch_unix is not None:
            connection = connect(working_path)
            try:
                connection.execute(
                    "UPDATE campaigns SET epoch_unix = ? WHERE id = 1", (epoch_unix,)
                )
                connection.commit()
            finally:
                connection.close()
    finally:
        temporary_path.unlink(missing_ok=True)
    return True


def stored_asset_manifest_sha256(connection: sqlite3.Connection) -> str | None:
    row = connection.execute(
        "SELECT asset_manifest_sha256 FROM campaigns WHERE id = 1"
    ).fetchone()
    return None if row is None else row[0]


def bootstrap_character(
    connection: sqlite3.Connection, *, account_name: str, record: dict
) -> dict[str, int | list[int]]:
    """Create a complete player, ship, stores, loadout, and crew atomically."""
    ship = dict(record["ship"])
    position = record["position"]
    homeworld = record["homeworld"]
    destination = record.get("destination", (-1, -1))
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            "INSERT OR IGNORE INTO accounts(account_name) VALUES(?)", (account_name,)
        )
        account_id = int(connection.execute(
            "SELECT id FROM accounts WHERE account_name = ? COLLATE NOCASE",
            (account_name,),
        ).fetchone()[0])
        if connection.execute(
            "SELECT 1 FROM characters WHERE campaign_id=1 AND account_id=?",
            (account_id,),
        ).fetchone():
            raise ValueError("account already has a campaign character")
        requested_character_id = int(record.get("database_id", 0))
        character_id = requested_character_id
        if character_id <= 0 or connection.execute(
            "SELECT 1 FROM characters WHERE id=?", (character_id,)
        ).fetchone():
            character_id = int(connection.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 FROM characters"
            ).fetchone()[0])
        requested_ship_id = int(ship.get("id", 0))
        ship_id = requested_ship_id
        if ship_id <= 0 or connection.execute(
            "SELECT 1 FROM ships WHERE id=?", (ship_id,)
        ).fetchone():
            ship_id = int(connection.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 FROM ships"
            ).fetchone()[0])
        connection.execute(
            "INSERT INTO characters(id, campaign_id, account_id, character_name, "
            "client_address, race, rank, rating, prestige, lifetime_prestige, "
            "disrepute, lifetime_disrepute, position_x, position_y, homeworld_x, "
            "homeworld_y, destination_x, destination_y, flags, verification_id, "
            "missions_played_json) VALUES(?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                character_id, account_id, str(record["character_name"]),
                str(record.get("client_address", "")), int(record["race"]),
                int(record.get("rank", 0)), int(record.get("rating", 1500)),
                int(record.get("prestige", 0)), int(record.get("lifetime_prestige", 0)),
                int(record.get("disrepute", 0)), int(record.get("lifetime_disrepute", 0)),
                int(position[0]), int(position[1]), int(homeworld[0]), int(homeworld[1]),
                int(destination[0]), int(destination[1]), int(record.get("flags", 0)),
                record.get("verification_id"),
                json.dumps(record.get("missions", []), sort_keys=True),
            ),
        )
        connection.execute(
            "INSERT INTO ships(id, campaign_id, owner_character_id, race, class_type, "
            "class_name, loadout_name, name, epv, damage, flags, turn_created, in_auction) "
            "VALUES(?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
            (
                ship_id, character_id, int(record["race"]), int(ship["class_type"]),
                str(ship["class_name"]), str(ship["loadout_name"]), str(ship["name"]),
                int(ship["bpv"]), float(ship.get("damage", 1.0)),
                int(ship.get("flags", 0)), int(ship.get("turn_created", 0)),
            ),
        )
        stores = ship["stores"]
        connection.execute(
            "INSERT INTO ship_stores(ship_id, shuttles, marines, mines) VALUES(?, ?, ?, ?)",
            (ship_id, int(stores["shuttles"]), int(stores["marines"]), int(stores["mines"])),
        )
        items = ship["refit"]["items"]
        connection.executemany(
            "INSERT INTO ship_loadout_items(ship_id, slot_index, item) VALUES(?, ?, ?)",
            ((ship_id, index, str(item)) for index, item in enumerate(items)),
        )
        officers = list(ship["officers"])
        if len(officers) != 6 or len({int(item["station"]) for item in officers}) != 6:
            raise ValueError("a starting ship must have six unique officer stations")
        next_officer_id = int(connection.execute(
            "SELECT COALESCE(MAX(id), 9999) + 1 FROM officers"
        ).fetchone()[0])
        officer_ids = []
        for officer in officers:
            requested_id = int(officer.get("id", 0))
            if requested_id <= 0 or connection.execute(
                "SELECT 1 FROM officers WHERE id=?", (requested_id,)
            ).fetchone():
                requested_id = next_officer_id
                next_officer_id += 1
            officer_ids.append(requested_id)
            connection.execute(
                "INSERT INTO officers(id, campaign_id, ship_id, station, name, race, worth, profile_json) "
                "VALUES(?, 1, ?, ?, ?, ?, ?, ?)",
                (
                    requested_id, ship_id, int(officer["station"]), str(officer["name"]),
                    int(officer.get("race", record["race"])), int(officer.get("worth", 0)),
                    json.dumps(officer.get("profile", {}), sort_keys=True),
                ),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {"account_id": account_id, "character_id": character_id,
            "ship_id": ship_id, "officer_ids": officer_ids}


def _json_source(path: Path) -> tuple[object, str] | None:
    if not path.exists():
        return None
    content = path.read_bytes()
    return json.loads(content.decode("utf-8")), hashlib.sha256(content).hexdigest()


def _record_import(
    connection: sqlite3.Connection, source_kind: str, path: Path, digest: str
) -> None:
    connection.execute(
        "INSERT INTO import_history(source_kind, source_path, source_sha256) VALUES(?, ?, ?)",
        (source_kind, str(path.resolve()), digest),
    )


def _already_imported(
    connection: sqlite3.Connection, sources: dict[str, tuple[Path, str]]
) -> bool:
    if not sources:
        return False
    imported = {
        (row["source_kind"], row["source_sha256"])
        for row in connection.execute(
            "SELECT source_kind, source_sha256 FROM import_history"
        )
    }
    if all((kind, digest) in imported for kind, (_path, digest) in sources.items()):
        return True
    prior_kinds = {row["source_kind"] for row in connection.execute(
        "SELECT DISTINCT source_kind FROM import_history"
    )}
    changed = prior_kinds.intersection(sources)
    if changed:
        raise ValueError(
            "legacy source changed after import: " + ", ".join(sorted(changed))
        )
    return False


def import_legacy_json(
    connection: sqlite3.Connection,
    *,
    accounts_path: Path,
    characters_path: Path,
    campaign_path: Path,
    normalize_character: Callable[[dict], dict] | None = None,
) -> dict[str, int]:
    """Import the prototype JSON stores exactly once in one SQL transaction."""
    loaded = {
        "accounts": (accounts_path, _json_source(accounts_path)),
        "characters": (characters_path, _json_source(characters_path)),
        "campaign": (campaign_path, _json_source(campaign_path)),
    }
    sources = {
        kind: (path, value[1])
        for kind, (path, value) in loaded.items()
        if value is not None
    }
    if _already_imported(connection, sources):
        return {"accounts": 0, "characters": 0, "ships": 0, "auctions": 0, "news": 0, "missions": 0, "settlements": 0}

    accounts = loaded["accounts"][1][0] if loaded["accounts"][1] else {}
    characters = loaded["characters"][1][0] if loaded["characters"][1] else {}
    campaign = loaded["campaign"][1][0] if loaded["campaign"][1] else {}
    if not all(isinstance(value, dict) for value in (accounts, characters, campaign)):
        raise ValueError("legacy JSON roots must be objects")

    counts = {"accounts": 0, "characters": 0, "ships": 0, "auctions": 0, "news": 0, "missions": 0, "settlements": 0}
    connection.execute("BEGIN IMMEDIATE")
    try:
        map_id = next(
            (str(item.get("map_id")) for item in characters.values() if item.get("map_id")),
            "retail-multiplayer",
        )
        connection.execute(
            "INSERT OR IGNORE INTO campaigns(id, map_id, epoch_unix, initial_turn, next_news_id, next_mission_id) "
            "VALUES(1, ?, ?, ?, ?, ?)",
            (
                map_id,
                float(campaign.get("epoch_unix", 0.0)),
                int(campaign.get("initial_turn", 0)),
                int(campaign.get("next_news_id", 1)),
                int(campaign.get("next_mission_id", 1)),
            ),
        )

        account_ids: dict[str, int] = {}
        all_account_names = sorted(
            set(str(name).casefold() for name in accounts)
            | set(str(name).casefold() for name in characters)
        )
        for account_id, account_name in enumerate(all_account_names, 1):
            auth = dict(accounts.get(account_name, {}))
            connection.execute(
                "INSERT INTO accounts(id, account_name, nickname, legacy_password_hash, gamespy_user_id, gamespy_profile_id, verification_id) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                (
                    account_id,
                    account_name,
                    str(auth.get("nick", "")),
                    auth.get("password_hash"),
                    auth.get("userid"),
                    auth.get("profileid"),
                    (characters.get(account_name) or {}).get("verification_id"),
                ),
            )
            account_ids[account_name] = account_id
            counts["accounts"] += 1

        character_ids: dict[str, int] = {}
        used_ship_ids: set[int] = set()
        next_ship_id = 1
        for character_id, account_name in enumerate(sorted(characters), 1):
            raw = dict(characters[account_name])
            record = normalize_character(raw) if normalize_character else raw
            ship = dict(record.get("ship") or {})
            if not ship:
                raise ValueError(f"character {account_name!r} has no ship")
            requested_ship_id = int(ship.get("id", 0))
            ship_id = requested_ship_id
            if ship_id <= 0 or ship_id in used_ship_ids:
                while next_ship_id in used_ship_ids:
                    next_ship_id += 1
                ship_id = next_ship_id
            used_ship_ids.add(ship_id)
            next_ship_id = max(next_ship_id, ship_id + 1)
            position = record.get("position", (0, 0))
            homeworld = record.get("homeworld", position)
            destination = record.get("destination", (-1, -1))
            connection.execute(
                "INSERT INTO characters(id, campaign_id, account_id, character_name, client_address, race, rank, rating, prestige, lifetime_prestige, disrepute, lifetime_disrepute, position_x, position_y, homeworld_x, homeworld_y, destination_x, destination_y, flags, verification_id, missions_played_json) "
                "VALUES(?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    character_id, account_ids[str(account_name).casefold()],
                    str(record.get("character_name", "")), str(record.get("client_address", "")),
                    int(record.get("race", 0)), int(record.get("rank", 0)), int(record.get("rating", 1500)),
                    int(record.get("prestige", 0)), int(record.get("lifetime_prestige", 0)),
                    int(record.get("disrepute", 0)), int(record.get("lifetime_disrepute", 0)),
                    int(position[0]), int(position[1]), int(homeworld[0]), int(homeworld[1]),
                    int(destination[0]), int(destination[1]), int(record.get("flags", 0)),
                    record.get("verification_id"), json.dumps(record.get("missions", []), sort_keys=True),
                ),
            )
            character_ids[str(account_name).casefold()] = character_id
            counts["characters"] += 1
            connection.execute(
                "INSERT INTO ships(id, campaign_id, owner_character_id, race, class_type, class_name, loadout_name, name, epv, damage, flags, turn_created, in_auction) "
                "VALUES(?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (
                    ship_id, character_id, int(record.get("race", 0)), int(ship.get("class_type", 0)),
                    str(ship.get("class_name", "")), str(ship.get("loadout_name", ship.get("class_name", ""))),
                    str(ship.get("name", "")), int(ship.get("bpv", 0)), float(ship.get("damage", 1.0)),
                    int(ship.get("flags", 0)), int(ship.get("turn_created", 0)),
                ),
            )
            counts["ships"] += 1
            stores = ship.get("stores", {})
            connection.execute(
                "INSERT INTO ship_stores(ship_id, shuttles, marines, mines) VALUES(?, ?, ?, ?)",
                (ship_id, int(stores.get("shuttles", 0)), int(stores.get("marines", 0)), int(stores.get("mines", 0))),
            )
            items = (ship.get("refit") or {}).get("items", ())
            connection.executemany(
                "INSERT INTO ship_loadout_items(ship_id, slot_index, item) VALUES(?, ?, ?)",
                ((ship_id, index, str(item)) for index, item in enumerate(items)),
            )
            for officer in ship.get("officers", ()):
                connection.execute(
                    "INSERT INTO officers(id, campaign_id, ship_id, station, name, race, worth, profile_json) VALUES(?, 1, ?, ?, ?, ?, ?, ?)",
                    (
                        int(officer["id"]), ship_id, int(officer["station"]), str(officer["name"]),
                        int(officer.get("race", record.get("race", 0))), int(officer.get("worth", 0)),
                        json.dumps(officer.get("profile", {}), sort_keys=True),
                    ),
                )

        for catalog_id_text, bid in campaign.get("auctions", {}).items():
            catalog_id = int(catalog_id_text)
            owner = character_ids.get(str(bid.get("bid_owner", "")).casefold())
            connection.execute(
                "INSERT INTO auctions(id, campaign_id, catalog_item_id, bid_owner_character_id, current_bid, bid_maximum, escrow, turn_opened, turn_bid_made, turn_to_close, closing) VALUES(?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    catalog_id, catalog_id, owner, int(bid.get("current_bid", 0)),
                    int(bid.get("bid_maximum", 0)), int(bid.get("escrow", 0)),
                    int(bid.get("turn_opened", 0)), int(bid.get("turn_bid_made", 0)),
                    int(bid.get("turn_to_close", 0)), int(bool(bid.get("closing", False))),
                ),
            )
            counts["auctions"] += 1

        for item in campaign.get("news", ()):
            connection.execute(
                "INSERT INTO news_stories(id, campaign_id, turn, channel, priority, text, timestamp, persistence, sequence) VALUES(?, 1, ?, ?, ?, ?, ?, ?, ?)",
                (
                    int(item["id"]), int(item.get("turn", 0)), str(item.get("channel", "system")),
                    str(item.get("priority", "med")), str(item.get("text", "")),
                    int(item.get("timestamp", 0)), int(item.get("persistence", 3)), int(item.get("sequence", item["id"])),
                ),
            )
            counts["news"] += 1

        for item in campaign.get("missions", ()):
            owner = character_ids.get(str(item.get("account", "")).casefold())
            if owner is None:
                raise ValueError("mission references an unknown account")
            connection.execute(
                "INSERT INTO prepared_missions(id, campaign_id, character_id, status, mission_json) VALUES(?, 1, ?, ?, ?)",
                (int(item["id"]), owner, str(item.get("status", "offered")), json.dumps(item, sort_keys=True)),
            )
            counts["missions"] += 1

        for settlement_id, item in enumerate(campaign.get("auction_settlements", ()), 1):
            connection.execute(
                "INSERT INTO auction_settlements(id, campaign_id, account_name, catalog_item_id, class_name, price, turn) VALUES(?, 1, ?, ?, ?, ?, ?)",
                (
                    settlement_id, str(item.get("account", "")), int(item.get("ship_id", 0)),
                    str(item.get("class_name", "")), int(item.get("price", 0)), int(item.get("turn", 0)),
                ),
            )
            counts["settlements"] += 1

        for kind, (path, digest) in sources.items():
            _record_import(connection, kind, path, digest)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return counts
