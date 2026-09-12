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


def _allocate_object_id(connection: sqlite3.Connection) -> int:
    """Consume one ID from the retail-style database-wide object sequence."""
    row = connection.execute(
        "UPDATE object_id_sequence SET next_id=next_id+1 WHERE singleton=1 "
        "RETURNING next_id-1"
    ).fetchone()
    if row is None:
        raise RuntimeError("global object-ID sequence is unavailable")
    return int(row[0])


def allocate_object_id(connection: sqlite3.Connection) -> int:
    """Atomically allocate one persistent game-object ID."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        object_id = _allocate_object_id(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return object_id


def shipyard_catalog_ids(
    connection: sqlite3.Connection, *, race: int, count: int
) -> tuple[tuple[int, int], ...]:
    """Return stable globally allocated (auction, item) IDs for one catalog."""
    if count < 0:
        raise ValueError("negative shipyard catalog size")
    connection.execute("BEGIN IMMEDIATE")
    try:
        for index in range(count):
            if connection.execute(
                "SELECT 1 FROM shipyard_catalog "
                "WHERE campaign_id=1 AND race=? AND catalog_index=?",
                (race, index),
            ).fetchone() is None:
                auction_id = _allocate_object_id(connection)
                item_id = _allocate_object_id(connection)
                connection.execute(
                    "INSERT INTO shipyard_catalog(campaign_id,race,catalog_index,"
                    "auction_id,item_id) VALUES(1,?,?,?,?)",
                    (race, index, auction_id, item_id),
                )
        rows = connection.execute(
            "SELECT auction_id,item_id FROM shipyard_catalog "
            "WHERE campaign_id=1 AND race=? AND catalog_index<? "
            "ORDER BY catalog_index",
            (race, count),
        ).fetchall()
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    if len(rows) != count:
        raise RuntimeError("incomplete shipyard catalog identity allocation")
    return tuple((int(row[0]), int(row[1])) for row in rows)


def officer_review_catalog_ids(
    connection: sqlite3.Connection, *, race: int, count: int
) -> tuple[int, ...]:
    """Return stable globally allocated IDs for one race's review candidates."""
    if count < 0:
        raise ValueError("negative officer review catalog size")
    connection.execute("BEGIN IMMEDIATE")
    try:
        for index in range(count):
            row = connection.execute(
                "SELECT officer_id FROM officer_review_catalog "
                "WHERE campaign_id=1 AND race=? AND candidate_index=?",
                (race, index),
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO officer_review_catalog(campaign_id,race,candidate_index,"
                    "officer_id) VALUES(1,?,?,?)",
                    (race, index, _allocate_object_id(connection)),
                )
            elif connection.execute(
                "SELECT 1 FROM officers WHERE id=?", (int(row[0]),)
            ).fetchone() is not None:
                # Review candidates are persistent game objects, but cease to be
                # review objects once assigned to a ship. Replenish that catalog
                # slot with a fresh database-wide identity before advertising it
                # again; otherwise a second character can select an ID already
                # owned by another ship and violate officers.id uniqueness.
                connection.execute(
                    "UPDATE officer_review_catalog SET officer_id=? "
                    "WHERE campaign_id=1 AND race=? AND candidate_index=?",
                    (_allocate_object_id(connection), race, index),
                )
        rows = connection.execute(
            "SELECT officer_id FROM officer_review_catalog "
            "WHERE campaign_id=1 AND race=? AND candidate_index<? "
            "ORDER BY candidate_index",
            (race, count),
        ).fetchall()
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    if len(rows) != count:
        raise RuntimeError("incomplete officer review identity allocation")
    return tuple(int(row[0]) for row in rows)


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


def load_accounts(connection: sqlite3.Connection) -> dict[str, dict[str, str | int]]:
    """Load the GameSpy-compatible account credentials from SQLite."""
    rows = connection.execute(
        "SELECT id, account_name, nickname, legacy_password_hash, gamespy_user_id, "
        "gamespy_profile_id FROM accounts"
    ).fetchall()
    return {
        str(row["account_name"]).casefold(): {
            "nick": str(row["nickname"] or ""),
            "password_hash": str(row["legacy_password_hash"] or ""),
            "userid": int(row["gamespy_user_id"] or row["id"]),
            "profileid": int(row["gamespy_profile_id"] or row["id"]),
        }
        for row in rows
    }


def create_account(
    connection: sqlite3.Connection,
    *,
    account_name: str,
    nickname: str,
    password_hash: str,
) -> dict[str, str | int]:
    """Create one local GameSpy account and allocate stable numeric IDs."""
    key = account_name.casefold()
    connection.execute("BEGIN IMMEDIATE")
    try:
        if connection.execute(
            "SELECT 1 FROM accounts WHERE account_name=? COLLATE NOCASE", (key,)
        ).fetchone():
            raise ValueError("account already exists")
        next_id = int(connection.execute(
            "SELECT COALESCE(MAX(value), 0) + 1 FROM ("
            "SELECT COALESCE(gamespy_user_id, id) AS value FROM accounts UNION ALL "
            "SELECT COALESCE(gamespy_profile_id, id) AS value FROM accounts)"
        ).fetchone()[0] or 1)
        cursor = connection.execute(
            "INSERT INTO accounts(account_name, nickname, legacy_password_hash, "
            "gamespy_user_id, gamespy_profile_id) VALUES(?, ?, ?, ?, ?)",
            (key, nickname, password_hash, next_id, next_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {"nick": nickname, "password_hash": password_hash,
            "userid": next_id, "profileid": next_id, "id": int(cursor.lastrowid)}


def merge_legacy_accounts(connection: sqlite3.Connection, accounts: dict) -> int:
    """One-time migration helper for credentials from accounts.local.json."""
    changed = 0
    connection.execute("BEGIN IMMEDIATE")
    try:
        for name, raw in accounts.items():
            key = str(name).casefold()
            row = connection.execute(
                "SELECT id FROM accounts WHERE account_name=? COLLATE NOCASE", (key,)
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO accounts(account_name, nickname, legacy_password_hash, "
                    "gamespy_user_id, gamespy_profile_id) VALUES(?, ?, ?, ?, ?)",
                    (key, str(raw.get("nick", "")), raw.get("password_hash"),
                     raw.get("userid"), raw.get("profileid")),
                )
            else:
                connection.execute(
                    "UPDATE accounts SET nickname=?, legacy_password_hash=?, "
                    "gamespy_user_id=?, gamespy_profile_id=? WHERE id=?",
                    (str(raw.get("nick", "")), raw.get("password_hash"),
                     raw.get("userid"), raw.get("profileid"), int(row["id"])),
                )
            changed += 1
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return changed


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
        character_id = _allocate_object_id(connection)
        ship_id = _allocate_object_id(connection)
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
        officer_ids = []
        for officer in officers:
            officer_id = _allocate_object_id(connection)
            officer_ids.append(officer_id)
            connection.execute(
                "INSERT INTO officers(id, campaign_id, ship_id, station, name, race, worth, profile_json) "
                "VALUES(?, 1, ?, ?, ?, ?, ?, ?)",
                (
                    officer_id, ship_id, int(officer["station"]), str(officer["name"]),
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


def load_characters(connection: sqlite3.Connection) -> dict[str, dict]:
    """Reconstruct canonical character records from normalized SQL rows."""
    records: dict[str, dict] = {}
    rows = connection.execute(
        "SELECT a.account_name, c.*, s.id AS ship_id, s.race AS ship_race, "
        "s.class_type, s.class_name, s.loadout_name, s.name AS ship_name, "
        "s.epv, s.damage, s.flags AS ship_flags, s.turn_created, "
        "ss.shuttles, ss.marines, ss.mines "
        "FROM characters c JOIN accounts a ON a.id=c.account_id "
        "JOIN ships s ON s.owner_character_id=c.id "
        "JOIN ship_stores ss ON ss.ship_id=s.id "
        "WHERE c.campaign_id=1 ORDER BY c.id, s.id"
    ).fetchall()
    for row in rows:
        ship_id = int(row["ship_id"])
        items = [item["item"] for item in connection.execute(
            "SELECT item FROM ship_loadout_items WHERE ship_id=? ORDER BY slot_index",
            (ship_id,),
        )]
        officers = [
            {
                "id": int(item["id"]), "name": str(item["name"]),
                "station": int(item["station"]), "race": int(item["race"]),
                "worth": int(item["worth"]),
                "profile": json.loads(item["profile_json"] or "{}"),
            }
            for item in connection.execute(
                "SELECT id, station, name, race, worth, profile_json FROM officers "
                "WHERE ship_id=? ORDER BY station", (ship_id,)
            )
        ]
        records[str(row["account_name"])] = {
            "database_id": int(row["id"]),
            "character_name": str(row["character_name"]),
            "client_address": str(row["client_address"]),
            "race": int(row["race"]),
            "rank": int(row["rank"]), "rating": int(row["rating"]),
            "prestige": int(row["prestige"]),
            "lifetime_prestige": int(row["lifetime_prestige"]),
            "disrepute": int(row["disrepute"]),
            "lifetime_disrepute": int(row["lifetime_disrepute"]),
            "position": [int(row["position_x"]), int(row["position_y"])],
            "homeworld": [int(row["homeworld_x"]), int(row["homeworld_y"])],
            "destination": [int(row["destination_x"]), int(row["destination_y"])],
            "flags": int(row["flags"]),
            "verification_id": row["verification_id"],
            "missions": json.loads(row["missions_played_json"] or "[]"),
            "ship": {
                "id": ship_id, "owner_id": int(row["id"]),
                "class_name": str(row["class_name"]),
                "loadout_name": str(row["loadout_name"]),
                "name": str(row["ship_name"]),
                "class_type": int(row["class_type"]), "bpv": int(row["epv"]),
                "damage": float(row["damage"]), "flags": int(row["ship_flags"]),
                "turn_created": int(row["turn_created"]),
                "stores": {"shuttles": int(row["shuttles"]),
                           "marines": int(row["marines"]), "mines": int(row["mines"])},
                "refit": {"loadout_name": str(row["loadout_name"]), "items": items},
                "officers": officers,
            },
        }
    return records


def save_character(connection: sqlite3.Connection, *, account_name: str, record: dict) -> None:
    """Atomically replace the mutable SQL snapshot for one existing character."""
    ship = record["ship"]
    position, homeworld = record["position"], record["homeworld"]
    destination = record.get("destination", (-1, -1))
    connection.execute("BEGIN IMMEDIATE")
    try:
        account = connection.execute(
            "SELECT id FROM accounts WHERE account_name=? COLLATE NOCASE", (account_name,)
        ).fetchone()
        if account is None:
            raise ValueError("unknown account")
        character_id = int(record["database_id"])
        ship_id = int(ship["id"])
        result = connection.execute(
            "UPDATE characters SET character_name=?, client_address=?, race=?, rank=?, "
            "rating=?, prestige=?, lifetime_prestige=?, disrepute=?, lifetime_disrepute=?, "
            "position_x=?, position_y=?, homeworld_x=?, homeworld_y=?, destination_x=?, "
            "destination_y=?, flags=?, verification_id=?, missions_played_json=? "
            "WHERE id=? AND campaign_id=1 AND account_id=?",
            (str(record["character_name"]), str(record.get("client_address", "")),
             int(record["race"]), int(record.get("rank", 0)), int(record.get("rating", 1500)),
             int(record["prestige"]), int(record.get("lifetime_prestige", 0)),
             int(record.get("disrepute", 0)), int(record.get("lifetime_disrepute", 0)),
             int(position[0]), int(position[1]), int(homeworld[0]), int(homeworld[1]),
             int(destination[0]), int(destination[1]), int(record.get("flags", 0)),
             record.get("verification_id"), json.dumps(record.get("missions", []), sort_keys=True),
             character_id, int(account["id"])),
        )
        if result.rowcount != 1:
            raise ValueError("unknown campaign character")
        result = connection.execute(
            "UPDATE ships SET race=?, class_type=?, class_name=?, loadout_name=?, name=?, "
            "epv=?, damage=?, flags=?, turn_created=? WHERE id=? AND owner_character_id=?",
            (int(record["race"]), int(ship["class_type"]), str(ship["class_name"]),
             str(ship["loadout_name"]), str(ship["name"]), int(ship["bpv"]),
             float(ship.get("damage", 1.0)), int(ship.get("flags", 0)),
             int(ship.get("turn_created", 0)), ship_id, character_id),
        )
        if result.rowcount != 1:
            raise ValueError("unknown character ship")
        stores = ship["stores"]
        connection.execute(
            "UPDATE ship_stores SET shuttles=?, marines=?, mines=? WHERE ship_id=?",
            (int(stores["shuttles"]), int(stores["marines"]), int(stores["mines"]), ship_id),
        )
        connection.execute("DELETE FROM ship_loadout_items WHERE ship_id=?", (ship_id,))
        connection.executemany(
            "INSERT INTO ship_loadout_items(ship_id, slot_index, item) VALUES(?, ?, ?)",
            ((ship_id, index, str(item)) for index, item in enumerate(ship["refit"]["items"])),
        )
        connection.execute("DELETE FROM officers WHERE ship_id=?", (ship_id,))
        connection.executemany(
            "INSERT INTO officers(id, campaign_id, ship_id, station, name, race, worth, profile_json) "
            "VALUES(?, 1, ?, ?, ?, ?, ?, ?)",
            ((int(item["id"]), ship_id, int(item["station"]), str(item["name"]),
              int(item.get("race", record["race"])), int(item.get("worth", 0)),
              json.dumps(item.get("profile", {}), sort_keys=True))
             for item in ship["officers"]),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def load_campaign_state(connection: sqlite3.Connection) -> dict:
    """Reconstruct mutable campaign state from normalized SQLite tables."""
    campaign = connection.execute(
        "SELECT epoch_unix, initial_turn, next_news_id, next_mission_id "
        "FROM campaigns WHERE id=1"
    ).fetchone()
    if campaign is None:
        raise ValueError("campaign 1 does not exist")
    state = {
        "epoch_unix": float(campaign["epoch_unix"]),
        "initial_turn": int(campaign["initial_turn"]),
        "next_news_id": int(campaign["next_news_id"]),
        "next_mission_id": int(campaign["next_mission_id"]),
        "auctions": {}, "auction_settlements": [], "news": [], "missions": [],
    }
    for row in connection.execute(
        "SELECT au.*, ac.account_name FROM auctions au "
        "LEFT JOIN characters c ON c.id=au.bid_owner_character_id "
        "LEFT JOIN accounts ac ON ac.id=c.account_id WHERE au.campaign_id=1"
    ):
        state["auctions"][str(int(row["catalog_item_id"]))] = {
            "auction_id": int(row["id"]),
            "current_bid": int(row["current_bid"]),
            "bid_maximum": int(row["bid_maximum"]),
            "escrow": int(row["escrow"]),
            "turn_opened": int(row["turn_opened"]),
            "turn_bid_made": int(row["turn_bid_made"]),
            "turn_to_close": int(row["turn_to_close"]),
            "closing": bool(row["closing"]),
            "bid_owner": str(row["account_name"] or ""),
        }
    state["news"] = [dict(row) for row in connection.execute(
        "SELECT id, turn, timestamp, channel, priority, persistence, sequence, text "
        "FROM news_stories WHERE campaign_id=1 ORDER BY sequence, id"
    )]
    state["missions"] = [json.loads(row["mission_json"]) for row in connection.execute(
        "SELECT mission_json FROM prepared_missions WHERE campaign_id=1 ORDER BY id"
    )]
    state["auction_settlements"] = [
        {"id": int(row["id"]), "account": str(row["account_name"]),
         "ship_id": int(row["catalog_item_id"]),
         "class_name": str(row["class_name"]), "price": int(row["price"]),
         "turn": int(row["turn"])}
        for row in connection.execute(
            "SELECT id, account_name, catalog_item_id, class_name, price, turn "
            "FROM auction_settlements WHERE campaign_id=1 ORDER BY id"
        )
    ]
    return state


def save_campaign_state(connection: sqlite3.Connection, state: dict) -> None:
    """Atomically replace mutable campaign state from its canonical envelope."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            "UPDATE campaigns SET epoch_unix=?, initial_turn=?, next_news_id=?, "
            "next_mission_id=? WHERE id=1",
            (float(state["epoch_unix"]), int(state.get("initial_turn", 0)),
             int(state.get("next_news_id", 1)), int(state.get("next_mission_id", 1))),
        )
        connection.execute("DELETE FROM auctions WHERE campaign_id=1")
        for catalog_id_text, item in state.get("auctions", {}).items():
            owner = None
            if item.get("bid_owner"):
                row = connection.execute(
                    "SELECT c.id FROM characters c JOIN accounts a ON a.id=c.account_id "
                    "WHERE c.campaign_id=1 AND a.account_name=? COLLATE NOCASE",
                    (str(item["bid_owner"]),),
                ).fetchone()
                owner = None if row is None else int(row["id"])
            catalog_id = int(catalog_id_text)
            auction_id = int(item.get("auction_id", catalog_id))
            connection.execute(
                "INSERT INTO auctions(id, campaign_id, catalog_item_id, "
                "bid_owner_character_id, current_bid, bid_maximum, escrow, turn_opened, "
                "turn_bid_made, turn_to_close, closing) VALUES(?,1,?,?,?,?,?,?,?,?,?)",
                (auction_id, catalog_id, owner, int(item.get("current_bid", 0)),
                 int(item.get("bid_maximum", 0)), int(item.get("escrow", 0)),
                 int(item.get("turn_opened", 0)), int(item.get("turn_bid_made", 0)),
                 int(item.get("turn_to_close", 0)), int(bool(item.get("closing", False)))),
            )
        connection.execute("DELETE FROM news_stories WHERE campaign_id=1")
        connection.executemany(
            "INSERT INTO news_stories(id,campaign_id,turn,channel,priority,text,"
            "timestamp,persistence,sequence) VALUES(?,1,?,?,?,?,?,?,?)",
            ((int(item["id"]), int(item.get("turn", 0)),
              str(item.get("channel", "system")), str(item.get("priority", "med")),
              str(item.get("text", "")), int(item.get("timestamp", 0)),
              int(item.get("persistence", 3)), int(item.get("sequence", item["id"])))
             for item in state.get("news", ())),
        )
        connection.execute("DELETE FROM prepared_missions WHERE campaign_id=1")
        for item in state.get("missions", ()):
            owner = connection.execute(
                "SELECT c.id FROM characters c JOIN accounts a ON a.id=c.account_id "
                "WHERE c.campaign_id=1 AND a.account_name=? COLLATE NOCASE",
                (str(item.get("account", "")),),
            ).fetchone()
            if owner is None:
                raise ValueError("mission references an unknown account")
            connection.execute(
                "INSERT INTO prepared_missions(id,campaign_id,character_id,status,mission_json) "
                "VALUES(?,1,?,?,?)",
                (int(item["id"]), int(owner["id"]), str(item.get("status", "offered")),
                 json.dumps(item, sort_keys=True)),
            )
        connection.execute("DELETE FROM auction_settlements WHERE campaign_id=1")
        for item in state.get("auction_settlements", ()):
            settlement_id = int(item.get("id", 0)) or _allocate_object_id(connection)
            item["id"] = settlement_id
            connection.execute(
                "INSERT INTO auction_settlements(id,campaign_id,account_name,catalog_item_id,"
                "class_name,price,turn) VALUES(?,1,?,?,?,?,?)",
                (settlement_id, str(item.get("account", "")),
                 int(item.get("ship_id", 0)), str(item.get("class_name", "")),
                 int(item.get("price", 0)), int(item.get("turn", 0))),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise


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
