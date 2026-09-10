import sqlite3
import json
import hashlib
import tempfile
import unittest
from pathlib import Path

import database


class DatabaseSchemaTests(unittest.TestCase):
    def test_initialize_creates_missing_parent_and_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "new" / "campaign.sqlite3"
            self.assertFalse(path.exists())
            connection = database.initialize(path)
            connection.close()
            self.assertTrue(path.is_file())

    def test_schema_initializes_with_foreign_keys_and_version(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = database.initialize(Path(directory) / "campaign.sqlite3")
            try:
                self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
                self.assertEqual(database.schema_version(connection), 3)
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                self.assertTrue({
                    "campaigns", "accounts", "characters", "ships", "ship_stores",
                    "ship_loadout_items", "officers", "auctions",
                }.issubset(tables))
            finally:
                connection.close()

    def test_build_default_database_populates_campaign_map_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / "assets"
            (assets / "ServerProfiles").mkdir(parents=True)
            asset = assets / "ServerProfiles" / "Time.gf"
            asset.write_text("[Clock]\nTurnsPerYear=10000\n", encoding="ascii")
            output = root / "default.sqlite3"
            records = bytes(range(22))
            digest = database.build_default_database(
                output, asset_root=assets, map_id="test.mvm", map_width=2,
                map_height=1, map_record_size=11, map_records=records,
                epoch_unix=0.0, initial_turn=0, turns_per_year=10000,
                milliseconds_per_turn=120000, base_year=56200,
            )
            connection = database.connect(output)
            try:
                campaign = connection.execute(
                    "SELECT map_id, turns_per_year, milliseconds_per_turn, base_year, "
                    "asset_manifest_sha256 FROM campaigns WHERE id=1"
                ).fetchone()
                self.assertEqual(tuple(campaign[:4]), ("test.mvm", 10000, 120000, 56200))
                self.assertEqual(campaign[4], digest)
                self.assertEqual(connection.execute(
                    "SELECT COUNT(*) FROM map_hexes"
                ).fetchone()[0], 2)
                self.assertEqual(connection.execute(
                    "SELECT client_record FROM map_hexes WHERE x=1 AND y=0"
                ).fetchone()[0], records[11:])
                manifest = connection.execute(
                    "SELECT relative_path, size, sha256 FROM asset_manifest"
                ).fetchone()
                self.assertEqual(manifest[0], "ServerProfiles/Time.gf")
                self.assertEqual(manifest[1], asset.stat().st_size)
                self.assertEqual(manifest[2], hashlib.sha256(asset.read_bytes()).hexdigest())
            finally:
                connection.close()

    def test_first_start_copies_template_and_never_overwrites_live_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "default.sqlite3"
            live = root / "state" / "campaign.sqlite3"
            connection = database.initialize(template)
            connection.execute(
                "INSERT INTO campaigns(id, map_id, epoch_unix, initial_turn) "
                "VALUES(1, 'retail', 0, 0)"
            )
            connection.commit()
            connection.close()
            self.assertTrue(database.create_working_database(
                template, live, epoch_unix=123.5
            ))
            connection = database.connect(live)
            self.assertEqual(connection.execute(
                "SELECT epoch_unix FROM campaigns WHERE id=1"
            ).fetchone()[0], 123.5)
            connection.execute("UPDATE campaigns SET initial_turn=77 WHERE id=1")
            connection.commit()
            connection.close()
            self.assertFalse(database.create_working_database(
                template, live, epoch_unix=999.0
            ))
            connection = database.connect(live)
            self.assertEqual(tuple(connection.execute(
                "SELECT epoch_unix, initial_turn FROM campaigns WHERE id=1"
            ).fetchone()), (123.5, 77))
            connection.close()

    def test_character_bootstrap_persists_complete_owned_ship_and_crew(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = database.initialize(Path(directory) / "campaign.sqlite3")
            connection.execute(
                "INSERT INTO campaigns(id, map_id, epoch_unix, initial_turn) "
                "VALUES(1, 'retail', 0, 0)"
            )
            connection.commit()
            stations = range(96, 102)
            items = ["PHASER IX:1"] + [f"OFFICER:S{station}:Crew{station}" for station in stations]
            record = {
                "database_id": 1, "character_name": "Captain", "client_address": "local",
                "race": 0, "position": [24, 19], "homeworld": [24, 19],
                "destination": [-1, -1], "prestige": 200,
                "ship": {
                    "id": 2, "class_type": 3, "class_name": "Norway",
                    "loadout_name": "Norway", "name": "USS Test", "bpv": 1250,
                    "stores": {"shuttles": 2, "marines": 2, "mines": 2},
                    "refit": {"items": items},
                    "officers": [
                        {"id": 10000 + index, "station": station,
                         "name": f"Crew{station}", "race": 0, "worth": 114}
                        for index, station in enumerate(stations)
                    ],
                },
            }
            ids = database.bootstrap_character(
                connection, account_name="pilot@example", record=record
            )
            self.assertEqual(ids["account_id"], 1)
            self.assertEqual(ids["character_id"], 1)
            self.assertEqual(ids["ship_id"], 2)
            self.assertEqual(ids["officer_ids"], list(range(10000, 10006)))
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM officers WHERE ship_id=2"
            ).fetchone()[0], 6)
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM ship_loadout_items WHERE ship_id=2"
            ).fetchone()[0], 7)
            self.assertEqual(tuple(connection.execute(
                "SELECT shuttles, marines, mines FROM ship_stores WHERE ship_id=2"
            ).fetchone()), (2, 2, 2))
            with self.assertRaisesRegex(ValueError, "already has"):
                database.bootstrap_character(
                    connection, account_name="pilot@example", record=record
                )
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM characters"
            ).fetchone()[0], 1)
            connection.close()

    def test_character_repository_round_trips_facility_mutations(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = database.initialize(Path(directory) / "campaign.sqlite3")
            connection.execute(
                "INSERT INTO campaigns(id, map_id, epoch_unix, initial_turn) "
                "VALUES(1, 'retail', 0, 0)"
            )
            connection.commit()
            record = {
                "database_id": 1, "character_name": "Captain", "client_address": "local",
                "race": 2, "rank": 0, "rating": 1500, "prestige": 200,
                "position": [36, 29], "homeworld": [36, 29], "destination": [-1, -1],
                "ship": {
                    "id": 2, "class_type": 3, "class_name": "Falcon",
                    "loadout_name": "Falcon", "name": "IRW Test", "bpv": 1125,
                    "stores": {"shuttles": 2, "marines": 5, "mines": 2},
                    "refit": {"items": ["R-DISRUPTOR II:1", "R-DISRUPTOR II:2"]},
                    "officers": [
                        {"id": 10000 + index, "station": station,
                         "name": f"Crew{station}", "race": 2, "worth": 114}
                        for index, station in enumerate(range(96, 102))
                    ],
                },
            }
            database.bootstrap_character(connection, account_name="romulan", record=record)
            loaded = database.load_characters(connection)["romulan"]
            loaded["prestige"] = 193
            loaded["ship"]["stores"] = {"shuttles": 3, "marines": 4, "mines": 3}
            loaded["ship"]["refit"]["items"] = ["R-DISRUPTOR II:2"]
            loaded["ship"]["officers"][0]["name"] = "BOWEN"
            database.save_character(connection, account_name="romulan", record=loaded)
            restarted = database.load_characters(connection)["romulan"]
            self.assertEqual(restarted["prestige"], 193)
            self.assertEqual(restarted["ship"]["stores"], {
                "shuttles": 3, "marines": 4, "mines": 3,
            })
            self.assertEqual(restarted["ship"]["refit"]["items"], ["R-DISRUPTOR II:2"])
            self.assertEqual(restarted["ship"]["officers"][0]["name"], "BOWEN")
            connection.close()

    def test_ship_state_is_owned_and_rejects_orphans(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = database.initialize(Path(directory) / "campaign.sqlite3")
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO ship_stores(ship_id, shuttles, marines, mines) VALUES(2, 1, 1, 1)"
                    )
            finally:
                connection.close()

    def test_one_officer_station_cannot_have_two_assignments(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = database.initialize(Path(directory) / "campaign.sqlite3")
            try:
                connection.execute(
                    "INSERT INTO campaigns(id, map_id, epoch_unix, initial_turn) VALUES(1, 'retail', 0, 0)"
                )
                connection.execute(
                    "INSERT INTO ships(id, campaign_id, race, class_type, class_name, loadout_name, name, epv) "
                    "VALUES(2, 1, 0, 3, 'Norway', 'Norway', 'USS Venture', 1250)"
                )
                connection.execute(
                    "INSERT INTO officers(id, campaign_id, ship_id, station, name, race) "
                    "VALUES(1000, 1, 2, 96, 'A', 0)"
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO officers(id, campaign_id, ship_id, station, name, race) "
                        "VALUES(1001, 1, 2, 96, 'B', 0)"
                    )
            finally:
                connection.close()

    def test_legacy_import_is_complete_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            accounts = root / "accounts.json"
            characters = root / "characters.json"
            campaign = root / "campaign.json"
            accounts.write_text(json.dumps({"pilot@example": {
                "nick": "Pilot", "password_hash": "abc", "userid": 7, "profileid": 8,
            }}), encoding="utf-8")
            characters.write_text(json.dumps({"pilot@example": {
                "character_name": "Captain", "client_address": "local", "race": 0,
                "map_id": "retail", "position": [24, 19], "homeworld": [24, 19],
                "destination": [-1, -1], "prestige": 101,
                "ship": {"id": 2, "owner_id": 1, "class_name": "Sovereign",
                    "loadout_name": "Sovereign A", "name": "USS Test", "class_type": 7,
                    "bpv": 2800, "damage": 1.0, "flags": 0, "turn_created": 10,
                    "stores": {"shuttles": 4, "marines": 3, "mines": 3},
                    "refit": {"items": ["PHASER XIF:1", "OFFICER:ENGINEER:BOWEN"]},
                    "officers": [{"id": 1003, "name": "BOWEN", "station": 99, "worth": 14}]},
            }}), encoding="utf-8")
            campaign.write_text(json.dumps({
                "epoch_unix": 100.0, "initial_turn": 824, "next_news_id": 2,
                "next_mission_id": 2,
                "auctions": {"3000": {"current_bid": 5, "bid_owner": "pilot@example",
                    "bid_maximum": 10, "escrow": 10, "turn_bid_made": 824}},
                "news": [{"id": 1, "turn": 824, "text": "Welcome"}],
                "missions": [{"id": 1, "account": "pilot@example", "status": "offered"}],
                "auction_settlements": [{"account": "pilot@example", "ship_id": 3001,
                    "class_name": "Sovereign", "price": 2800, "turn": 800}],
            }), encoding="utf-8")
            connection = database.initialize(root / "campaign.sqlite3")
            try:
                counts = database.import_legacy_json(
                    connection, accounts_path=accounts, characters_path=characters,
                    campaign_path=campaign,
                )
                self.assertEqual(counts, {
                    "accounts": 1, "characters": 1, "ships": 1, "auctions": 1,
                    "news": 1, "missions": 1, "settlements": 1,
                })
                self.assertEqual(tuple(connection.execute(
                    "SELECT class_name, loadout_name, name FROM ships"
                ).fetchone()), ("Sovereign", "Sovereign A", "USS Test"))
                self.assertEqual(tuple(connection.execute(
                    "SELECT shuttles, marines, mines FROM ship_stores"
                ).fetchone()), (4, 3, 3))
                self.assertEqual(connection.execute(
                    "SELECT name FROM officers"
                ).fetchone()[0], "BOWEN")
                self.assertEqual(database.import_legacy_json(
                    connection, accounts_path=accounts, characters_path=characters,
                    campaign_path=campaign,
                )["characters"], 0)
            finally:
                connection.close()

    def test_failed_legacy_import_rolls_back_every_table(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            accounts = root / "accounts.json"
            characters = root / "characters.json"
            campaign = root / "campaign.json"
            accounts.write_text("{}", encoding="utf-8")
            characters.write_text(json.dumps({"pilot@example": {
                "character_name": "Captain", "race": 0, "ship": {"id": 2,
                    "class_name": "Norway", "name": "USS Test"},
            }}), encoding="utf-8")
            campaign.write_text(json.dumps({"missions": [{
                "id": 1, "account": "missing@example", "status": "offered",
            }]}), encoding="utf-8")
            connection = database.initialize(root / "campaign.sqlite3")
            try:
                with self.assertRaisesRegex(ValueError, "unknown account"):
                    database.import_legacy_json(
                        connection, accounts_path=accounts, characters_path=characters,
                        campaign_path=campaign,
                    )
                for table in ("accounts", "characters", "ships", "prepared_missions", "import_history"):
                    self.assertEqual(connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0], 0)
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
