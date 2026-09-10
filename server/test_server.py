import asyncio
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import gamespy
import server
from campaign_map import CLIENT_HEX_RECORDS, HEIGHT, SHA256, SOURCE_SHA256, WIDTH


class DynamicSecurityWireTests(unittest.TestCase):
    def test_campaign_idle_timeout_is_fifteen_minutes(self):
        self.assertEqual(server.SESSION_IDLE_TIMEOUT, 15 * 60)

    def test_async_return_envelope(self):
        payload = b"\x01" + struct.pack("<III", 6, 2, 0x00010002) + b"private"
        self.assertEqual(server._parse_async_return(payload), (6, 2, 0x00010002))

    def test_async_return_rejects_wrong_marker(self):
        with self.assertRaises(ValueError):
            server._parse_async_return(b"\x00" + struct.pack("<III", 6, 2, 1))

    def test_campaign_callback_shape(self):
        payload = struct.pack("<III", 6, 6, 4) + b"request fields"
        self.assertEqual(server._parse_callback(payload), (6, 6, 4))

    def test_get_auction_ships_request_shape(self):
        payload = (
            b"\x01"
            + struct.pack("<III", 9, 8, 7)
            + struct.pack("<IfI", server.CHARACTER_DATABASE_ID, 1.0, 0)
        )
        self.assertEqual(len(payload), 25)
        self.assertEqual(
            server._parse_get_auction_ships_request(payload),
            ((9, 8, 7), server.CHARACTER_DATABASE_ID, 1.0, ()),
        )

    def test_auction_catalog_is_keyed_by_item_id(self):
        defaults = {
            "hull_cost": 825,
            "loadout_class_name": "Fed-Frigate",
            "ui_name": "Saber",
            "class_code": "FF",
        }
        item = server._auction_item_payload(
            defaults,
            auction_id=2000,
            ship_id=3000,
            bid_factor=1.0,
            turns_until_close=3,
        )
        self.assertEqual(struct.unpack_from("<I", item, 0)[0], 2000)
        description_length = struct.unpack_from("<I", item, 9)[0]
        self.assertEqual(item[13 : 13 + description_length], b"Saber")
        item_id_offset = 13 + description_length
        self.assertEqual(struct.unpack_from("<I", item, item_id_offset)[0], 3000)

    def test_bid_request_shape(self):
        payload = (
            b"\x01"
            + struct.pack("<III", 9, 8, 7)
            + struct.pack("<IIII", 3002, server.CHARACTER_DATABASE_ID, 1, 0)
            + struct.pack("<dI", 1300.0, 2)
            + struct.pack("<ff", 1.0, 0.5)
        )
        self.assertEqual(
            server._parse_bid_request(payload),
            ((9, 8, 7), 3002, server.CHARACTER_DATABASE_ID, 1, 0, 1300.0, (1.0, 0.5)),
        )

    def test_shipyard_bid_buttons_compute_retail_increments(self):
        self.assertEqual(server._shipyard_bid_maximum(2800, 2), 2805)
        self.assertEqual(server._shipyard_bid_maximum(2800, 3), 2810)
        self.assertEqual(server._shipyard_bid_maximum(2800, 9), 2940)
        self.assertEqual(server._shipyard_bid_maximum(2800, 10), 3080)

    def test_romulan_ship_uses_variant_as_player_facing_name(self):
        defaults = server._starter_ship_defaults(server.RACE_ROMULAN)
        self.assertEqual(defaults["sub_name"], "Falcon")
        self.assertEqual(defaults["ui_name"], "Falcon")
        self.assertEqual(defaults["model_name"], "RomulanFrigate")

    def test_shipyard_bid_persists_and_accepts_initial_minimum(self):
        defaults = {
            "hull_cost": 1250,
            "loadout_class_name": "Fed-Destroyer",
            "ui_name": "Norway",
            "class_code": "DD",
        }
        old_path = server.CAMPAIGN_STATE_PATH
        try:
            with tempfile.TemporaryDirectory() as directory:
                server.CAMPAIGN_STATE_PATH = Path(directory) / "campaign.json"
                with (
                    mock.patch.object(server, "_shipyard_defaults", return_value=(defaults,)),
                    mock.patch.object(server, "_economy_ship_auction_settings", return_value=(1.0, 3, 40)),
                    mock.patch.object(server, "_campaign_turn", return_value=7),
                ):
                    response, result = server._place_shipyard_bid(
                        server.RACE_FEDERATION, "captain@example", 3000, 1250, now=1000.0
                    )
                self.assertEqual(result, 2)
                self.assertEqual(struct.unpack_from("<I", response)[0], 1)
                saved = json.loads(server.CAMPAIGN_STATE_PATH.read_text(encoding="utf-8"))
                self.assertEqual(saved["auctions"]["3000"]["bid_owner"], "captain@example")
                self.assertEqual(saved["auctions"]["3000"]["bid_maximum"], 1250)
                self.assertEqual(saved["auctions"]["3000"]["turn_bid_made"], 7)
        finally:
            server.CAMPAIGN_STATE_PATH = old_path

    def test_competing_proxy_bid_is_persisted(self):
        defaults = {"hull_cost": 100, "ui_name": "Test", "class_code": "DD"}
        old_path = server.CAMPAIGN_STATE_PATH
        try:
            with tempfile.TemporaryDirectory() as directory:
                server.CAMPAIGN_STATE_PATH = Path(directory) / "campaign.json"
                server.CAMPAIGN_STATE_PATH.write_text(json.dumps({
                    "epoch_unix": 1.0, "initial_turn": 0,
                    "auctions": {"3000": {"current_bid": 100, "bid_owner": "leader", "bid_maximum": 200, "turn_bid_made": 2, "escrow": 200}},
                }), encoding="utf-8")
                with (mock.patch.object(server, "_shipyard_defaults", return_value=(defaults,)), mock.patch.object(server, "_economy_ship_auction_settings", return_value=(1.0, 3, 40)), mock.patch.object(server, "_campaign_turn", return_value=3)):
                    _response, result = server._place_shipyard_bid(server.RACE_FEDERATION, "challenger", 3000, 150, now=2.0)
                self.assertEqual(result, 1)
                saved = json.loads(server.CAMPAIGN_STATE_PATH.read_text(encoding="utf-8"))
                self.assertEqual(saved["auctions"]["3000"]["current_bid"], 151)
                self.assertEqual(saved["auctions"]["3000"]["bid_owner"], "leader")
        finally:
            server.CAMPAIGN_STATE_PATH = old_path

    def test_auction_settlement_uses_restart_stable_clock_boundary(self):
        old_campaign = server.CAMPAIGN_STATE_PATH
        old_characters = server.CHARACTER_STORE_PATH
        old_server_root = server.SERVER_ASSET_ROOT
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                profile = root / "ServerProfiles"
                profile.mkdir()
                (profile / "Time.gf").write_text(
                    "[Clock]\nTurnsPerYear=10000\nMilliSecondsPerTurn=1000\n"
                    "[Clock/StartingDate]\nBaseYear=56200\n",
                    encoding="ascii",
                )
                server.CAMPAIGN_STATE_PATH = root / "campaign.json"
                server.CHARACTER_STORE_PATH = root / "characters.json"
                server.SERVER_ASSET_ROOT = root
                server.CAMPAIGN_STATE_PATH.write_text(json.dumps({
                    "epoch_unix": 100.0,
                    "initial_turn": 0,
                    "auctions": {"3000": {
                        "current_bid": 100,
                        "bid_owner": "captain",
                        "bid_maximum": 100,
                        "turn_bid_made": 0,
                        "escrow": 100,
                    }},
                }), encoding="utf-8")
                server.CHARACTER_STORE_PATH.write_text(json.dumps({
                    "captain": {
                        "race": server.RACE_FEDERATION,
                        "character_name": "Test",
                        "client_address": "local",
                        "prestige": 200,
                    },
                }), encoding="utf-8")
                catalog = ({"hull_cost": 100, "ui_name": "Test Hull", "class_code": "DD"},)
                award = {
                    "hull_cost": 100,
                    "ui_name": "Test Hull",
                    "sub_name": "Test Loadout",
                    "class_code": "DD",
                    "shuttles": (1, 2, 1),
                    "marines": (1, 2, 1),
                    "mines": (1, 2, 1),
                    "items": ("PHASER IX:1",),
                }
                with (
                    mock.patch.object(server, "_economy_ship_auction_settings", return_value=(1.0, 3, 40)),
                    mock.patch.object(server, "_shipyard_defaults", return_value=catalog),
                    mock.patch.object(server, "_shipyard_award_defaults", return_value=award),
                ):
                    self.assertEqual(server._settle_shipyard_bids(now=102.999), ())
                    settlements = server._settle_shipyard_bids(now=103.0)

                self.assertEqual(len(settlements), 1)
                self.assertEqual(settlements[0]["turn"], 3)
                self.assertEqual(settlements[0]["class_name"], "Test Hull")
                saved = json.loads(server.CAMPAIGN_STATE_PATH.read_text(encoding="utf-8"))
                self.assertEqual(saved["epoch_unix"], 100.0)
                self.assertEqual(saved["auctions"], {})
                character = json.loads(
                    server.CHARACTER_STORE_PATH.read_text(encoding="utf-8")
                )["captain"]
                self.assertEqual(character["prestige"], 100)
                self.assertEqual(character["ship"]["class_name"], "Test Hull")
        finally:
            server.CAMPAIGN_STATE_PATH = old_campaign
            server.CHARACTER_STORE_PATH = old_characters
            server.SERVER_ASSET_ROOT = old_server_root

    def test_verification_policies_do_not_require_raw_key_storage(self):
        with mock.patch.dict(server.os.environ, {"SFC3_CDKEY_POLICY": "permissive"}, clear=False):
            self.assertTrue(server._verification_allowed(b"opaque-private-proof"))
        with mock.patch.dict(server.os.environ, {"SFC3_CDKEY_POLICY": "strict", "SFC3_IDENTITY_HMAC_SECRET": "local-secret"}, clear=False):
            identifier = server._verification_identifier(b"identity")
            with mock.patch.dict(server.os.environ, {"SFC3_REGISTERED_KEY_IDS": identifier}, clear=False):
                self.assertTrue(server._verification_allowed(b"identity"))
                self.assertFalse(server._verification_allowed(b"different"))

    def test_verification_identity_excludes_challenges(self):
        envelope = b"\x01" + struct.pack("<III", 9, 8, 7)
        character = server._default_client_character_payload(include_ship=False)
        def request(challenge: str) -> bytes:
            blob = b"stable-private-proof"
            return (
                envelope + struct.pack("<I", 0) + server._pack_str("reply-" + challenge)
                + character + server._pack_str(challenge) + server._pack_str("login")
                + b"\x01\x00" + struct.pack("<I", len(blob)) + blob
            )
        first = server._parse_verification_request(request("one"))
        self.assertEqual(first["access_name"], "login")
        self.assertEqual(first["access_blob"], b"stable-private-proof")
        with mock.patch.dict(server.os.environ, {"SFC3_CDKEY_POLICY": "registered"}, clear=False):
            self.assertEqual(
                server._verification_identity_bytes(request("one")),
                server._verification_identity_bytes(request("two")),
            )

    def test_mission_lifecycle_is_persistent(self):
        old_campaign = server.CAMPAIGN_STATE_PATH
        old_characters = server.CHARACTER_STORE_PATH
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                server.CAMPAIGN_STATE_PATH = root / "campaign.json"
                server.CHARACTER_STORE_PATH = root / "characters.json"
                server.CHARACTER_STORE_PATH.write_text(json.dumps({"captain": {"race": 0, "character_name": "Test", "client_address": "local", "prestige": 200}}), encoding="utf-8")
                with mock.patch.object(server, "_campaign_turn", return_value=4):
                    mission = server._offer_mission("captain", "Patrol sector")
                self.assertEqual(server._set_mission_status("captain", mission["id"], "accepted")["status"], "accepted")
                self.assertEqual(server._set_mission_status("captain", mission["id"], "launched")["status"], "launched")
                self.assertEqual(server._set_mission_status("captain", mission["id"], "completed")["status"], "completed")
                character = json.loads(server.CHARACTER_STORE_PATH.read_text(encoding="utf-8"))["captain"]
                self.assertEqual(character["prestige"], 210)
        finally:
            server.CAMPAIGN_STATE_PATH = old_campaign
            server.CHARACTER_STORE_PATH = old_characters

    def test_purchase_officers_request_shape(self):
        payload = (
            struct.pack("<III", 9, 8, 7)
            + struct.pack("<II", server.CHARACTER_DATABASE_ID, 2)
            + struct.pack("<IIII", 1000, 0x60, 1001, 0x61)
        )
        self.assertEqual(
            server._parse_purchase_officers_request(payload),
            ((9, 8, 7), server.CHARACTER_DATABASE_ID, {1000: 0x60, 1001: 0x61}),
        )

    def test_purchase_officers_single_assignment_is_retail_28_byte_shape(self):
        payload = (
            struct.pack("<III", 9, 8, 7)
            + struct.pack("<II", server.CHARACTER_DATABASE_ID, 1)
            + struct.pack("<II", 1000, 0x60)
        )
        self.assertEqual(len(payload), 28)
        self.assertEqual(
            server._parse_purchase_officers_request(payload),
            ((9, 8, 7), server.CHARACTER_DATABASE_ID, {1000: 0x60}),
        )

    def test_purchase_officers_rejects_marker_prefixed_or_truncated_shape(self):
        retail_payload = (
            struct.pack("<III", 9, 8, 7)
            + struct.pack("<II", server.CHARACTER_DATABASE_ID, 1)
            + struct.pack("<II", 1000, 0x60)
        )
        with self.assertRaises(ValueError):
            server._parse_purchase_officers_request(b"\x01" + retail_payload)
        with self.assertRaises(ValueError):
            server._parse_purchase_officers_request(retail_payload[:-1])

    def test_purchased_officer_replaces_station_and_is_removed_from_review(self):
        old_characters = server.CHARACTER_STORE_PATH
        try:
            with tempfile.TemporaryDirectory() as directory:
                server.CHARACTER_STORE_PATH = Path(directory) / "characters.json"
                server.CHARACTER_STORE_PATH.write_text(json.dumps({
                    "captain": {
                        "race": server.RACE_FEDERATION,
                        "character_name": "Test",
                        "client_address": "local",
                        "prestige": 20,
                        "officers": [],
                    }
                }), encoding="utf-8")
                defaults = {
                    "sub_name": "Norway",
                    "items": (
                        "OFFICER:HELM:",
                        "PHASER IX:1",
                    ),
                }
                with (
                    mock.patch.object(server, "_officer_names", return_value=("INCOMING",)),
                    mock.patch.object(server, "_officer_review_limit", return_value=1),
                    mock.patch.object(server, "_character_ship_defaults", return_value=defaults),
                ):
                    record = server._purchase_officer(
                        "captain", 1000, station=server.OFFICER_STATIONS[0]
                    )
                self.assertEqual(record["prestige"], 120)
                self.assertEqual(record["ship"]["officers"][0]["name"], "INCOMING")
                self.assertTrue(record["ship"]["refit"]["items"][0].startswith("OFFICER:HELM:INCOMING:"))
                with (
                    mock.patch.object(
                        server, "_officer_names", return_value=("INCOMING", "SECOND")
                    ),
                    mock.patch.object(server, "_officer_review_limit", return_value=2),
                ):
                    remaining = server._generated_officers(
                        server.RACE_FEDERATION, (1000,)
                    )
                self.assertTrue(remaining)
                self.assertNotIn(1000, {
                    struct.unpack_from("<I", officer)[0] for officer in remaining
                })
        finally:
            server.CHARACTER_STORE_PATH = old_characters

    def test_free_officers_request_shape(self):
        payload = struct.pack("<IIII", 9, 8, 7, server.CHARACTER_DATABASE_ID)
        self.assertEqual(
            server._parse_free_officers_request(payload),
            ((9, 8, 7), server.CHARACTER_DATABASE_ID),
        )

    def test_update_stores_request_shape(self):
        stores = server._stores_state_payload(
            shuttle_counts=(3, 4, 2), misc_maximum=(2, 4, 4),
            misc_current=(1, 4, 4), misc_desired=(0, 0, 1),
        )
        payload = struct.pack("<III", 9, 8, 7) + struct.pack("<I", server.CHARACTER_DATABASE_ID) + server._pack_str("USS Venture") + stores
        callback, character_id, ship_name, decoded = server._parse_update_stores_request(payload)
        self.assertEqual((callback, character_id, ship_name), ((9, 8, 7), server.CHARACTER_DATABASE_ID, "USS Venture"))
        self.assertEqual(len(payload), 147)
        self.assertEqual(decoded["shuttles"], (3, 4, 2))
        self.assertEqual(decoded["misc_maximum"], (2, 4, 4))
        self.assertEqual(decoded["misc_current"], (1, 4, 4))
        self.assertEqual(decoded["misc_desired"], (0, 0, 1))
        self.assertEqual(len(decoded["items"]), 25)
        self.assertEqual(decoded["items"][0], (-1, 0))

    def test_supply_update_charges_buys_and_credits_sales(self):
        old_characters = server.CHARACTER_STORE_PATH
        try:
            with tempfile.TemporaryDirectory() as directory:
                server.CHARACTER_STORE_PATH = Path(directory) / "characters.json"
                server.CHARACTER_STORE_PATH.write_text(json.dumps({
                    "captain": {
                        "race": 0, "character_name": "Test", "client_address": "local",
                        "prestige": 20, "stores": {"shuttles": 2, "marines": 2, "mines": 2},
                    }
                }), encoding="utf-8")
                with mock.patch.object(server, "_character_ship_defaults", return_value={
                    "shuttles": (2, 2, 4), "marines": (2, 4, 4), "mines": (2, 4, 4),
                }):
                    record = server._update_supplies(
                        "captain", {"shuttles": 3, "marines": 1, "mines": 2}
                    )
                self.assertEqual(record["ship"]["stores"], {"shuttles": 3, "marines": 1, "mines": 2})
                self.assertEqual(record["prestige"], 20)
        finally:
            server.CHARACTER_STORE_PATH = old_characters

    def test_logon_payload_includes_persistent_prestige(self):
        with mock.patch.object(server, "_starting_prestige", return_value=200):
            record = server._normalize_character_record({"race": 0, "prestige": 77})
            payload = server._character_logon_payload("captain", "Test", "local", 0, record)
        offset = 4
        _address, offset = server._unpack_string(payload, offset)
        _account, offset = server._unpack_string(payload, offset)
        offset += 4
        _name, offset = server._unpack_string(payload, offset)
        values = struct.unpack_from("<IIIIIIII", payload, offset)
        self.assertEqual(values[3:5], (77, 77))

    def test_purchase_config_request_round_trip(self):
        core = server._ship_core_payload(
            ((1,), (4,), (2,), (5,), (3,), (6,)),
            (1,) * 8, "Fed-Destroyer", "Norway", (2,) * 7, (3,) * 4,
            ("cloak",),
        )
        tng = server._tng_ship_payload(
            core,
            ("Federation", "Fed-Destroyer", "Norway", "Norway", "1", "", "Phaser IX"),
            4,
        )
        payload = struct.pack("<III", 9, 8, 7) + struct.pack("<II", server.CHARACTER_DATABASE_ID, server.SHIP_DATABASE_ID) + tng
        callback, character_id, ship_id, config = server._parse_purchase_config_request(payload)
        self.assertEqual((callback, character_id, ship_id), ((9, 8, 7), 1, 2))
        self.assertEqual(config["loadout_fields"][2], "Norway")
        self.assertEqual(config["configuration_scalar"], 4.0)

    def test_character_prestige_reply_matches_live_channel_13_shape(self):
        self.assertEqual(
            server._character_prestige_payload(
                {"prestige": 199, "lifetime_prestige": 12}
            ),
            struct.pack("<BII", 1, 199, 12),
        )
        self.assertEqual(
            server._character_prestige_payload(None),
            struct.pack("<BII", 0, 0, 0),
        )

    def test_news_request_and_empty_response_shapes(self):
        request = b"\x01" + struct.pack("<III", 9, 8, 7) + struct.pack("<I", 1)
        self.assertEqual(server._parse_news_request(request), ((9, 8, 7), 1))
        self.assertEqual(server._news_response_payload(), struct.pack("<I", 0))

    def test_news_story_response_uses_server_profile_color(self):
        old_server_root = server.SERVER_ASSET_ROOT
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                profile = root / "ServerProfiles"
                profile.mkdir()
                (profile / "News.gf").write_text(
                    "[General]\nMaximumItemsAtOnce=30\n"
                    "[Channel/Color/System/Med]\nRed=0.5\nGreen=0.25\nBlue=1.0\n",
                    encoding="ascii",
                )
                server.SERVER_ASSET_ROOT = root
                item = {
                    "id": 12, "text": "Campaign online", "channel": "system",
                    "priority": "med", "timestamp": 100, "sequence": 4,
                }
                payload = server._news_response_payload(item)
                self.assertEqual(struct.unpack_from("<I", payload), (1,))
                self.assertEqual(struct.unpack_from("<II", payload, 4), (12, 0))
                self.assertEqual(payload[12:15], bytes((3, 3, 0)))
                count = struct.unpack_from("<I", payload, 15)[0]
                self.assertEqual(count, 1)
                text_length = struct.unpack_from("<I", payload, 19)[0]
                self.assertEqual(payload[23 : 23 + text_length], b"Campaign online")
                tail = 23 + text_length
                self.assertEqual(struct.unpack_from("<iiI", payload, tail), (100, 4, 0xFF4080))
        finally:
            server.SERVER_ASSET_ROOT = old_server_root

    def test_mission_match_request_shapes(self):
        envelope = b"\x01" + struct.pack("<III", 9, 8, 7)
        self.assertEqual(
            server._parse_mission_match_request(envelope + struct.pack("<II", 1, 3)),
            ((9, 8, 7), 1, 3),
        )
        self.assertEqual(
            server._parse_verify_mission_request(envelope + struct.pack("<I", 1)),
            ((9, 8, 7), 1),
        )

    def test_choose_mission_request_shape(self):
        envelope = b"\x01" + struct.pack("<III", 9, 8, 7)
        hail = server._pack_str_vector(("Patrol this sector",)) + struct.pack("<II", 44, 2) + b"\x01"
        battle = struct.pack("<I", 3) + hail + struct.pack("<IIIIII", 10, 11, 12, 13, 14, 15) + struct.pack("<d", 2.5) + b"\x01"
        callback, character_id, decoded = server._parse_choose_mission_request(
            envelope + struct.pack("<I", server.CHARACTER_DATABASE_ID) + battle
        )
        self.assertEqual((callback, character_id), ((9, 8, 7), server.CHARACTER_DATABASE_ID))
        self.assertEqual(decoded["state"], 3)
        self.assertEqual(decoded["hail"]["texts"], ["Patrol this sector"])
        self.assertEqual(decoded["fields"], (10, 11, 12, 13, 14, 15))
        self.assertEqual(decoded["rating"], 2.5)
        self.assertTrue(decoded["enabled"])

    def test_clock_snapshot_shape(self):
        old_path = server.CAMPAIGN_STATE_PATH
        old_server_root = server.SERVER_ASSET_ROOT
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                profile = root / "ServerProfiles"
                profile.mkdir()
                (profile / "Time.gf").write_text(
                    "[Clock]\nTurnsPerYear=10000\nMilliSecondsPerTurn=120000\n"
                    "[Clock/StartingDate]\nBaseYear=56200\n",
                    encoding="ascii",
                )
                server.CAMPAIGN_STATE_PATH = root / "campaign.json"
                server.SERVER_ASSET_ROOT = root
                payload = server._clock_snapshot_payload(now=1_000.0)
                self.assertEqual(len(payload), 21)
                self.assertEqual(payload[0], 1)
                self.assertEqual(
                    struct.unpack_from("<IIIII", payload, 1),
                    (0, 0, 10_000, 120_000, 56_200),
                )
                self.assertEqual(server._campaign_turn(now=1_239.999), 1)
                self.assertEqual(server._campaign_turn(now=1_240.0), 2)
        finally:
            server.CAMPAIGN_STATE_PATH = old_path
            server.SERVER_ASSET_ROOT = old_server_root

    def test_clock_snapshot_matches_recovered_retail_semantics(self):
        old_path = server.CAMPAIGN_STATE_PATH
        old_server_root = server.SERVER_ASSET_ROOT
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                profile = root / "ServerProfiles"
                profile.mkdir()
                (profile / "Time.gf").write_text(
                    "[Clock]\nTurnsPerYear=10000\nMilliSecondsPerTurn=120000\n"
                    "[Clock/StartingDate]\nBaseYear=56200\n",
                    encoding="ascii",
                )
                server.CAMPAIGN_STATE_PATH = root / "campaign.json"
                server.SERVER_ASSET_ROOT = root
                server.CAMPAIGN_STATE_PATH.write_text(json.dumps({
                    "epoch_unix": 1_000.0,
                    "initial_turn": 93_528,
                    "auctions": {},
                }), encoding="utf-8")

                snapshot = server._clock_snapshot(now=1_000.0)
                self.assertEqual(
                    snapshot,
                    server.CampaignClockSnapshot(93_528, 9, 10_000, 120_000, 56_200),
                )
                self.assertEqual(
                    struct.unpack_from("<IIIII", snapshot.payload(), 1),
                    (93_528, 9, 10_000, 120_000, 56_200),
                )
        finally:
            server.CAMPAIGN_STATE_PATH = old_path
            server.SERVER_ASSET_ROOT = old_server_root

    def test_clock_year_rollover_and_restart_use_persisted_epoch(self):
        old_path = server.CAMPAIGN_STATE_PATH
        old_server_root = server.SERVER_ASSET_ROOT
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                profile = root / "ServerProfiles"
                profile.mkdir()
                (profile / "Time.gf").write_text(
                    "[Clock]\nTurnsPerYear=10\nMilliSecondsPerTurn=1000\n"
                    "[Clock/StartingDate]\nBaseYear=56200\n",
                    encoding="ascii",
                )
                server.CAMPAIGN_STATE_PATH = root / "campaign.json"
                server.SERVER_ASSET_ROOT = root
                server.CAMPAIGN_STATE_PATH.write_text(json.dumps({
                    "epoch_unix": 100.0,
                    "initial_turn": 8,
                    "auctions": {"3000": {"turn_bid_made": 8}},
                }), encoding="utf-8")

                self.assertEqual(server._clock_snapshot(now=101.999).current_year, 0)
                self.assertEqual(server._clock_snapshot(now=102.0).current_turn, 10)
                self.assertEqual(server._clock_snapshot(now=102.0).current_year, 1)
                self.assertEqual(server._milliseconds_until_next_turn(now=102.25), 750.0)

                reloaded = server._load_campaign_clock(now=200.0)
                self.assertEqual(reloaded["epoch_unix"], 100.0)
                self.assertEqual(reloaded["initial_turn"], 8)
                self.assertEqual(server._campaign_turn(now=200.0), 108)
                self.assertIn("3000", reloaded["auctions"])
        finally:
            server.CAMPAIGN_STATE_PATH = old_path
            server.SERVER_ASSET_ROOT = old_server_root

    def test_clock_snapshot_rejects_unsigned_overflow(self):
        with self.assertRaises(ValueError):
            server.CampaignClockSnapshot(0x1_0000_0000, 0, 1, 1, 0).payload()

    def test_map_size_shape_matches_retail_map(self):
        payload = server._map_size_payload()
        self.assertEqual(payload, b"\x01" + struct.pack("<II", WIDTH, HEIGHT))

    def test_client_hex_field_layout_matches_live_capture(self):
        self.assertEqual(
            server._client_hex_payload(server.RACE_NEUTRAL),
            bytes.fromhex("0909000000040000140a64"),
        )
        self.assertEqual(
            server._client_hex_payload(
                server.RACE_FEDERATION,
                has_planet=True,
                victory_points=50,
                economy_points=100,
            ),
            bytes.fromhex("0000000000040100326464"),
        )

    def test_campaign_map_snapshot_matches_retail_baseline(self):
        payload = server._map_snapshot_payload()
        count = WIDTH * HEIGHT
        self.assertEqual(len(payload), 1 + 12 + count * 11 + 8)
        self.assertEqual(struct.unpack_from("<iiI", payload, 1), (-1, -1, count))
        self.assertEqual(payload[13:-8], CLIENT_HEX_RECORDS)
        self.assertEqual(hashlib.sha256(payload[13:-8]).hexdigest(), SHA256)
        self.assertEqual(struct.unpack_from("<II", payload, len(payload) - 8), (WIDTH, HEIGHT))
        self.assertEqual(SOURCE_SHA256, "b1de93eff01c6570a25e36eebead1f09c0c4fd0ab26affaba764b00a351c1f52")

        home_x, home_y = server.CAMPAIGN_HOMEWORLDS[server.RACE_FEDERATION]
        home_index = home_y * WIDTH + home_x
        start_offset = 13 + home_index * 11
        self.assertEqual(
            payload[start_offset : start_offset + 11],
            bytes.fromhex("0000000000040101646464"),
        )

    def test_meta_map_hex_and_character_position_shapes(self):
        meta_hex = server._meta_map_hex_payload(17, 14, server.RACE_FEDERATION)
        self.assertEqual(len(meta_hex), 62)
        self.assertEqual(struct.unpack_from("<ii", meta_hex, 8), (17, 14))
        self.assertEqual(meta_hex[16:18], b"\x00\x00")
        self.assertEqual(struct.unpack_from("<I", meta_hex, 18)[0], 0x04000000)

        response = server._character_position_payload(server.RACE_FEDERATION)
        self.assertEqual(len(response), 71)
        self.assertEqual(response[0], 1)
        self.assertEqual(
            struct.unpack_from("<ii", response, 9),
            server.CAMPAIGN_STARTS[server.RACE_FEDERATION],
        )
        self.assertEqual(struct.unpack_from("<ii", response, 63), (-1, -1))

    def test_each_playable_race_has_a_distinct_start(self):
        self.assertEqual(len(set(server.CAMPAIGN_STARTS.values())), 4)
        for race, expected in server.CAMPAIGN_STARTS.items():
            response = server._character_position_payload(race)
            self.assertEqual(struct.unpack_from("<ii", response, 9), expected)

    def test_character_position_can_report_persisted_movement_state(self):
        response = server._character_position_payload(
            server.RACE_FEDERATION, (31, 2), (32, 3)
        )
        self.assertEqual(struct.unpack_from("<ii", response, 9), (31, 2))
        self.assertEqual(struct.unpack_from("<ii", response, 63), (32, 3))

    def test_federation_character_starts_at_homeworld_with_no_destination(self):
        payload = server._default_client_character_payload(race=server.RACE_FEDERATION)
        _, offset = server._unpack_string(payload, 0)
        _, offset = server._unpack_string(payload, offset)
        _, offset = server._unpack_string(payload, offset + 4)
        positions_offset = offset + 8 * 4
        self.assertEqual(struct.unpack_from("<ii", payload, positions_offset), (24, 19))
        self.assertEqual(struct.unpack_from("<ii", payload, positions_offset + 8), (24, 19))
        self.assertEqual(struct.unpack_from("<ii", payload, positions_offset + 16), (-1, -1))

    def test_get_client_character_response_contains_local_character(self):
        payload = server._get_client_character_payload(
            "user@example", "Captain Test", "192.0.2.10", server.RACE_FEDERATION
        )
        self.assertEqual(payload[0], 1)
        address, offset = server._unpack_string(payload, 1)
        account, offset = server._unpack_string(payload, offset)
        self.assertEqual((address, account), ("192.0.2.10", "user@example"))
        self.assertEqual(payload[-1], 1)

    def test_starting_ship_cache_uses_installed_profile_choice(self):
        payload = server._ship_cache_payload(server.RACE_FEDERATION)
        self.assertEqual(struct.unpack_from("<III", payload), (2, 250, 3))
        class_name, offset = server._unpack_string(payload, 12)
        self.assertEqual(class_name, "Norway")
        self.assertEqual(struct.unpack_from("<f", payload, offset)[0], 1.0)
        ship_name, offset = server._unpack_string(payload, offset + 4)
        self.assertEqual(ship_name, "USS Venture")
        self.assertEqual(struct.unpack_from("<I", payload, offset)[0], 0)

    def test_fleet_data_contains_starter_ship_at_homeworld(self):
        payload = server._fleet_data_payload(server.RACE_FEDERATION)
        self.assertEqual(payload[:5], b"\x01\x01\x00\x00\x00")
        self.assertEqual(
            struct.unpack_from("<IIiiIBI", payload, 5),
            (1, 2, 24, 19, 3, 1, 0),
        )

    def test_move_request_and_response_shapes(self):
        request = struct.pack("<IIIIii", 6, 6, 4, 1, 31, 1)
        self.assertEqual(
            server._parse_move_request(request),
            ((6, 6, 4), 1, (31, 1)),
        )
        self.assertEqual(
            server._move_response_payload(True),
            b"\x01" + struct.pack("<II", 1, 1),
        )
        self.assertEqual(
            server._move_response_payload(True, duration_seconds=15),
            b"\x01" + struct.pack("<II", 15, 1),
        )
        self.assertEqual(
            server._move_response_payload(False),
            b"\x01" + struct.pack("<II", 0, 0),
        )
        self.assertEqual(
            server._meta_map_move_payload(1, (32, 3), 1, 1),
            struct.pack("<IIiiII", 1, 1, 32, 3, 1, 0) + b"\x00",
        )
        self.assertEqual(
            server._meta_map_move_payload(1, (33, 5), 0, 0, True)[-1],
            1,
        )

    def test_captured_live_move_request_and_viewport_notifications(self):
        # live-login-ethernet-20260902.pcapng frames 531, 538, and 539.
        request = bytes.fromhex(
            "0600000006000000000000001aa20d001c00000009000000"
        )
        self.assertEqual(
            server._parse_move_request(request),
            ((6, 6, 0), 0x000DA21A, (28, 9)),
        )
        self.assertEqual(
            server._meta_map_move_payload(0x000DA21A, (28, 9), 0, 1),
            bytes.fromhex(
                "010000001aa20d001c00000009000000000000000000000000"
            ),
        )
        self.assertEqual(
            server._meta_map_move_payload(0x000DA21A, (28, 9), 0, 0),
            bytes.fromhex(
                "000000001aa20d001c00000009000000000000000000000000"
            ),
        )

    def test_hex_adjacency_uses_odd_column_offsets(self):
        for destination in ((10, 9), (11, 9), (11, 10), (10, 11), (9, 10), (9, 9)):
            self.assertTrue(server._is_adjacent_hex((10, 10), destination))
        for destination in ((11, 9), (12, 10), (12, 11), (11, 11), (10, 10), (10, 11)):
            self.assertTrue(server._is_adjacent_hex((11, 10), destination))
        for destination in ((10, 10), (11, 11), (9, 11), (12, 10)):
            self.assertFalse(server._is_adjacent_hex((10, 10), destination))

    def test_hex_distance_supports_multi_hex_destinations(self):
        self.assertEqual(server._hex_distance((25, 19), (26, 20)), 1)
        self.assertEqual(server._hex_distance((26, 20), (27, 20)), 1)
        self.assertEqual(server._hex_distance((27, 20), (25, 19)), 2)
        self.assertEqual(server._hex_distance((27, 20), (27, 20)), 0)

    def test_federation_start_region_enables_friendly_facilities(self):
        homeworld = server.CAMPAIGN_HOMEWORLDS[server.RACE_FEDERATION]
        fields = server._campaign_hex_fields(homeworld)
        self.assertEqual(fields[:2], (server.RACE_FEDERATION,) * 2)
        self.assertTrue(fields[3])
        self.assertTrue(fields[4])
        self.assertTrue(
            server._at_friendly_base_or_planet(homeworld, server.RACE_FEDERATION)
        )
        self.assertFalse(
            server._at_friendly_base_or_planet(homeworld, server.RACE_KLINGON)
        )

    def test_supply_dock_nested_serializer_shapes(self):
        self.assertEqual(
            server._pack_u32_vector((1, 2, 3)),
            struct.pack("<IIII", 3, 1, 2, 3),
        )
        damage = server._damage_state_payload()
        self.assertEqual(len(damage), 385)
        self.assertEqual(damage[0], 1)
        self.assertEqual(struct.unpack_from("<ii", damage, 1), (-1, -1))

        stores = server._stores_state_payload()
        self.assertEqual(len(stores), 116)
        self.assertEqual(stores[:7], bytes((2, 4, 2)) + struct.pack("<I", 0))
        self.assertEqual(struct.unpack_from("<hh", stores, 7), (-1, 0))
        self.assertEqual(stores[-9:], bytes((4, 2, 2)) * 3)

        self.assertEqual(
            server._item_rates_payload(),
            struct.pack("<dddd", 1.0, 2.0, 4.0, 4.0),
        )

    def test_supply_dock_nested_serializers_validate_cardinality(self):
        with self.assertRaises(ValueError):
            server._damage_state_payload(system_current=(1,))
        with self.assertRaises(ValueError):
            server._stores_state_payload(item_current=(1,))
        with self.assertRaises(ValueError):
            server._item_rates_payload(misc_rates=(1.0,))

    def test_tng_ship_core_and_loadout_serializer_order(self):
        core = server._ship_core_payload(
            ((1, 2), (30, 31), (12,), (21,), (1, 2, 3), (1, 2)),
            tuple(range(10, 18)),
            "Fed-Destroyer",
            "Norway",
            tuple(range(20, 27)),
            tuple(range(30, 34)),
        )
        self.assertEqual(struct.unpack_from("<III", core), (2, 1, 2))
        class_offset = sum(4 + 4 * size for size in (2, 2, 1, 1, 3, 2)) + 32
        class_name, offset = server._unpack_string(core, class_offset)
        model_name, offset = server._unpack_string(core, offset)
        self.assertEqual((class_name, model_name), ("Fed-Destroyer", "Norway"))
        self.assertEqual(struct.unpack_from("<I", core, offset)[0], 0)

        ship = server._tng_ship_payload(core, ("Federation", "Norway", "USS Venture"), 7.0)
        self.assertEqual(ship[:2], b"\x01\x01")
        loadout, offset = server._unpack_string(ship, 2 + len(core))
        self.assertEqual(loadout, "Federation\tNorway\tUSS Venture\t")
        self.assertEqual(ship[offset - 1 : offset + 4], b"\t" + struct.pack("<f", 7.0))
        self.assertEqual(struct.unpack_from("<f", ship, offset)[0], 7.0)

    def test_installed_default_parser_maps_all_starter_ships(self):
        assets = Path(r"D:\Games\GOG\Star Trek SFC3\Assets")
        if not assets.is_dir():
            self.skipTest("local SFC3 asset install is unavailable")
        expected = {
            server.RACE_FEDERATION: ("Federation", "Norway", (2, 8, 2)),
            server.RACE_KLINGON: ("Klingon", "K'Vort", (2, 8, 2)),
            server.RACE_ROMULAN: ("Romulan", "Falcon", (2, 8, 2)),
            server.RACE_BORG: ("Borg", "Diamond", (3, 12, 3)),
        }
        for race, (political_base, model_name, mines) in expected.items():
            defaults = server._starter_ship_defaults(race, assets)
            self.assertEqual(defaults["political_base"], political_base)
            self.assertEqual(defaults["starter_name"], model_name)
            self.assertEqual(defaults["mines"], mines)
            self.assertEqual(len(defaults["primary_hardpoints"]) > 0, True)
            self.assertEqual(len(defaults["items"]) > 0, True)
            vectors = server._core_hardpoint_vectors(defaults)
            self.assertEqual(len(vectors), 6)
            self.assertEqual(len(vectors[0]), len(vectors[1]))
            self.assertEqual(len(vectors[2]), len(vectors[3]))

    def test_persisted_refit_items_override_stock_loadout_without_changing_baseline(self):
        assets = Path(r"D:\Games\GOG\Star Trek SFC3\Assets")
        if not assets.is_dir():
            self.skipTest("local SFC3 asset install is unavailable")
        record = server._normalize_character_record({
            "race": server.RACE_FEDERATION,
            "ship": {
                "id": server.SHIP_DATABASE_ID,
                "class_name": "Norway",
                "loadout_name": "Norway",
                "name": "USS Venture",
                "class_type": 3,
                "bpv": 250,
                "damage": 1.0,
                "flags": 0,
            },
            "refit": {"loadout_name": "Norway", "items": ["PHASER IX:1"]},
        })
        stock = server._load_ship_defaults(
            assets / "Specs" / "DefaultCore.txt",
            assets / "Specs" / "DefaultLoadOut.txt",
            "Norway",
        )
        customized = server._character_ship_defaults(record, assets)
        self.assertEqual(customized["items"], ("PHASER IX:1",))
        self.assertEqual(customized["loadout_fields"][6:], ("PHASER IX:1",))
        self.assertNotEqual(stock["items"], customized["items"])

    def test_weapon_arc_table_matches_executable_order(self):
        self.assertEqual(len(server.WEAPON_ARCS), 44)
        self.assertEqual(server._weapon_arc_id("0_360"), 3)
        self.assertEqual(server._weapon_arc_id("300_360"), 9)
        self.assertEqual(server._weapon_arc_id("330_30"), 15)
        self.assertEqual(server._weapon_arc_id("165_195"), 17)
        self.assertEqual(server._weapon_arc_id("120_300"), 43)
        with self.assertRaises(ValueError):
            server._weapon_arc_id("12_34")

    def test_server_kit_norway_core_matches_retail_stream_order(self):
        assets = Path(__file__).resolve().parent.parent / "assets" / "server-kit"
        defaults = server._starter_ship_defaults(server.RACE_FEDERATION, assets)
        self.assertEqual(
            server._core_hardpoint_vectors(defaults),
            ((1, 2, 3), (9, 4, 15), (12, 13, 14), (15, 15, 17), (1, 2, 3), (1, 2)),
        )
        core = server._default_ship_core_payload(defaults)
        self.assertIn(server._pack_str_vector(("ship",)), core)
        self.assertIn(server._pack_str("Fed-Destroyer"), core)
        self.assertIn(server._pack_str("Norway"), core)
        vectors_length = sum(4 + 4 * size for size in (3, 3, 3, 3, 3, 2))
        self.assertEqual(
            struct.unpack_from("<8I", core, vectors_length),
            (1000, 2300, 2550, 10, 3, 1250, 1021, 8500),
        )
        # StreamOut places cargo and hull cost after the interleaved supply
        # fields, not in the first numeric group.
        self.assertEqual(struct.unpack_from("<4I", core, len(core) - 16), (1, 2, 0, 1250))

    def test_shared_romulan_model_resolves_the_selected_loadout_class(self):
        specs = Path(__file__).resolve().parent.parent / "assets" / "server-kit" / "Spec"
        falcon = server._load_ship_defaults(
            specs / "DefaultCore.txt", specs / "DefaultLoadOut.txt", "Falcon"
        )
        self.assertEqual(falcon["class_name"], "Romulan-Destroyer")
        self.assertEqual(falcon["class_code"], "DD")
        self.assertEqual(falcon["power_space"], 2775)
        self.assertEqual(falcon["weapon_space"], 1000)
        self.assertEqual(falcon["hull_space"], 2300)
        self.assertEqual(falcon["heavy_hardpoints"], ((12, "330_30"), (13, "330_30")))

    def test_representative_faction_cores_use_validated_wire_capacities(self):
        root = Path(__file__).resolve().parent.parent / "assets" / "server-kit"
        specs = root / "Spec"
        expected = {
            "Norway": (1000, 2300, 2550, 10, 3, 1250, 1021, 8500),
            "K'Vort": (1000, 2300, 2425, 10, 3, 1125, 795, 8500),
            "Falcon": (1000, 2300, 2775, 10, 3, 1125, 548, 8000),
            "Diamond": (1450, 3700, 4800, 40, 4, 3775, 1206, 0),
        }
        for name, capacities in expected.items():
            defaults = server._load_ship_defaults(
                specs / "DefaultCore.txt", specs / "DefaultLoadOut.txt", name
            )
            core = server._default_ship_core_payload(defaults)
            vectors_length = sum(
                4 + 4 * len(group) for group in server._core_hardpoint_vectors(defaults)
            )
            self.assertEqual(struct.unpack_from("<8I", core, vectors_length), capacities)
            config = server._character_ship_config_payload(
                next(
                    race for race, base in server.SHIP_POLITICAL_BASES.items()
                    if base == defaults["political_base"]
                ),
                root,
                prestige=500,
                record=server._normalize_character_record({
                    "race": next(
                        race for race, base in server.SHIP_POLITICAL_BASES.items()
                        if base == defaults["political_base"]
                    ),
                    "ship": {"class_name": name, "loadout_name": name},
                }),
            )
            parsed, end = server._parse_tng_ship(config, 5)
            self.assertEqual(end, len(config) - 8)
            self.assertEqual(parsed["model_name"], defaults["model_name"])

    def test_ship_class_table_matches_executable_order(self):
        self.assertEqual(server._ship_class_id("SH"), 0)
        self.assertEqual(server._ship_class_id("DD"), 3)
        self.assertEqual(server._ship_class_id("BIO"), 14)
        self.assertEqual(server._ship_class_id("SPECIAL"), 16)

    def test_generated_supply_dock_ship_uses_local_identity_and_defaults(self):
        assets = Path(r"D:\Games\GOG\Star Trek SFC3\Assets")
        if not assets.is_dir():
            self.skipTest("local SFC3 asset install is unavailable")
        defaults = server._starter_ship_defaults(server.RACE_FEDERATION, assets)
        ship = server._full_ship_payload(
            race=server.RACE_FEDERATION,
            ship_name="USS Venture",
            defaults=defaults,
        )
        self.assertEqual(
            struct.unpack_from("<IIIBIII", ship),
            (2, 0, 1, 0, server.RACE_FEDERATION, 3, 250),
        )
        class_name, offset = server._unpack_string(ship, 25)
        ship_name, offset = server._unpack_string(ship, offset)
        self.assertEqual((class_name, ship_name), ("Norway", "USS Venture"))
        self.assertEqual(struct.unpack_from("<I", ship, offset)[0], 0)
        self.assertEqual(struct.unpack_from("<II", ship, len(ship) - 8), (0, 1250))

        response = server._supply_dock_payload(server.RACE_FEDERATION, assets)
        self.assertEqual(response[0], 1)
        maps = (
            server._id_double_map_payload(((server.SHIP_DATABASE_ID, 1.0),))
            + server._id_double_map_payload(((server.SHIP_DATABASE_ID, 0.5),))
            + server._id_item_rates_map_payload(
                ((server.SHIP_DATABASE_ID, (1.0, (2.0, 4.0, 4.0))),)
            )
        )
        self.assertEqual(response[1:-len(maps)], ship)
        self.assertEqual(response[-len(maps):], maps)
        for race in (
            server.RACE_FEDERATION,
            server.RACE_KLINGON,
            server.RACE_ROMULAN,
            server.RACE_BORG,
        ):
            generated = server._supply_dock_payload(race, assets)
            self.assertGreater(len(generated), 700)
            self.assertEqual(generated[0], 1)
            self.assertEqual(generated[-len(maps):], maps)

    def test_character_ship_config_and_server_kit_officer_review_payloads(self):
        assets = Path(r"D:\Games\GOG\Star Trek SFC3\Assets")
        if not assets.is_dir():
            self.skipTest("local SFC3 asset install is unavailable")
        callback = (6, 20, 2)
        config_request = struct.pack("<IIII", *callback, server.CHARACTER_DATABASE_ID) + b"\x01"
        self.assertEqual(
            server._parse_character_ship_config_request(config_request),
            (callback, server.CHARACTER_DATABASE_ID, True),
        )
        officer_request = struct.pack("<IIII", *callback, server.CHARACTER_DATABASE_ID)
        self.assertEqual(
            server._parse_officers_to_review_request(officer_request),
            (callback, server.CHARACTER_DATABASE_ID),
        )

        defaults = server._starter_ship_defaults(server.RACE_FEDERATION, assets)
        expected_tng = server._tng_ship_payload(
            server._default_ship_core_payload(defaults), defaults["loadout_fields"]
        )
        config = server._character_ship_config_payload(
            server.RACE_FEDERATION, assets, prestige=1500
        )
        self.assertEqual(config[:5], b"\x01" + struct.pack("<I", server.SHIP_DATABASE_ID))
        self.assertEqual(config[5:-8], expected_tng)
        self.assertEqual(struct.unpack("<fI", config[-8:]), (1.0, 1500))

        old_kit_root = server.SERVER_ASSET_ROOT
        server.SERVER_ASSET_ROOT = (
            Path(__file__).resolve().parent.parent / "assets" / "server-kit"
        )
        try:
            names = server._officer_names(server.RACE_FEDERATION)[:8]
            officers = server._officers_to_review_payload(
                server.RACE_FEDERATION, assets, prestige=1500
            )
        finally:
            server.SERVER_ASSET_ROOT = old_kit_root
        self.assertEqual(officers[:5], b"\x01" + struct.pack("<I", 8))
        first_name_offset = 5 + 8 + 1 + 16
        first_name, _ = server._unpack_string(officers, first_name_offset)
        self.assertEqual(first_name, "KLEIMAN")
        officer_size = 8 + 1 + 16 + 4 + len("KLEIMAN") + 80 + 20
        officer_bytes = sum(
            8 + 1 + 16 + 4 + len(name) + 80 + 20
            for name in names
        )
        self.assertGreater(officer_size, 0)
        self.assertEqual(officers[5 + officer_bytes:-8], expected_tng)
        self.assertEqual(struct.unpack("<fI", officers[-8:]), (1.0, 1500))

    def test_generated_officer_item_uses_recovered_field_order(self):
        payload = server._officer_item_payload("KLEIMAN", server.RACE_FEDERATION, 0x60)
        self.assertEqual(payload[0], 0)
        self.assertEqual(struct.unpack_from("<4I", payload, 1), (10, 20, 10, 2))
        name, offset = server._unpack_string(payload, 17)
        self.assertEqual(name, "KLEIMAN")
        fields = struct.unpack_from("<20I", payload, offset)
        self.assertEqual(fields[0], 0x60)
        self.assertEqual(fields[1:4], (1, 1, 1))
        self.assertEqual(fields[-1], server.RACE_FEDERATION)

    def test_security_challenge_shape(self):
        challenge = "a" * 29
        payload = server._security_challenge_payload(challenge)
        self.assertEqual(len(payload), 37)
        self.assertEqual(struct.unpack_from("<II", payload), (1, 29))
        self.assertEqual(payload[8:], challenge.encode("ascii"))

    def test_security_success_shape(self):
        payload = server._security_success_payload()
        self.assertEqual(len(payload), 37)
        self.assertEqual(struct.unpack_from("<III", payload), (1, 0, 25))
        self.assertEqual(payload[12:], b"Successful security check")

    def test_security_relay_claim_shape(self):
        name = b" *~Server~* .?AVtSecurityRelayS@@"
        payload = server._relay_claim_payload(name, 2)
        self.assertEqual(len(payload), 45)
        self.assertEqual(struct.unpack_from("<I", payload), (33,))
        self.assertEqual(payload[4:37], name)
        self.assertEqual(struct.unpack_from("<II", payload, 37), (0, 2))

    def test_character_initialize_shape(self):
        account = b"user@example"
        address = b"192.0.2.10"
        payload = (
            struct.pack("<III", 6, 6, 0)
            + struct.pack("<I", len(account))
            + account
            + struct.pack("<I", len(address))
            + address
        )
        self.assertEqual(
            server._parse_character_initialize(payload),
            ((6, 6, 0), "user@example", "192.0.2.10"),
        )

    def test_character_initialize_rejects_trailing_data(self):
        payload = struct.pack("<III", 6, 6, 0) + struct.pack("<I", 1) + b"a"
        payload += struct.pack("<I", 1) + b"b" + b"extra"
        with self.assertRaisesRegex(ValueError, "trailing"):
            server._parse_character_initialize(payload)

    def test_character_not_found_response_shape(self):
        payload = server._character_not_found_payload()

        self.assertEqual(len(payload), 149)
        self.assertEqual(payload[0], 1)
        self.assertEqual(struct.unpack_from("<I", payload, 1)[0], 0)
        self.assertEqual(struct.unpack_from("<I", payload, 5)[0], 0)
        self.assertEqual(struct.unpack_from("<I", payload, 9)[0], 0)
        self.assertEqual(struct.unpack_from("<I", payload, 17)[0], 0)
        self.assertEqual(struct.unpack_from("<I", payload, 21)[0], 0xFFFFFFFF)
        self.assertEqual(struct.unpack_from("<I", payload, 25)[0], 1500)
        self.assertEqual(payload[-10:-8], b"\x00\x00")
        self.assertEqual(struct.unpack_from("<I", payload, len(payload) - 4)[0], 1)

    def test_create_client_character_request_shape(self):
        request = (
            struct.pack("<III", 23, 6, 0)
            + server._pack_str("")
            + server._pack_str("user@example")
            + struct.pack("<I", 2)
            + server._pack_str("Captain Test")
            + server._pack_str("192.0.2.10")
            + struct.pack("<I", 1)
        )
        self.assertEqual(
            server._parse_create_client_character(request),
            (
                (23, 6, 0),
                "",
                "user@example",
                2,
                "Captain Test",
                "192.0.2.10",
                1,
            ),
        )

    def test_character_created_response_shape(self):
        payload = server._character_created_payload(
            "user@example", "Captain Test", "192.0.2.10", 2
        )
        self.assertEqual(payload[0], 1)
        address, offset = server._unpack_string(payload, 1)
        account, offset = server._unpack_string(payload, offset)
        self.assertEqual((address, account), ("192.0.2.10", "user@example"))
        self.assertEqual(struct.unpack_from("<I", payload, offset)[0], 1)
        name, offset = server._unpack_string(payload, offset + 4)
        self.assertEqual(name, "Captain Test")
        self.assertEqual(struct.unpack_from("<I", payload, offset)[0], 2)
        self.assertEqual(struct.unpack_from("<I", payload, len(payload) - 4)[0], 0)

    def test_relay_publication_shape(self):
        name = b"accountCharacterLogOnRelayNameC"
        payload = struct.pack("<I", len(name)) + name + struct.pack("<II", 77, 4)
        self.assertEqual(server._parse_relay_publication(payload), (name, (77, 4)))

    def test_relay_request_shape(self):
        name = b" *~Server~* tMapRelayS"
        payload = b"\x01" + struct.pack("<III", 77, 1, 3) + server._pack_str(
            name.decode("ascii")
        )
        self.assertEqual(
            server._parse_relay_request(payload), ((77, 1, 3), name)
        )

    def test_post_logon_relay_object_assignments_match_live_capture(self):
        self.assertEqual(
            server.DynamicSecurityClient.RELAY_OBJECTS,
            {
                b" *~Server~* .?AVtNotifyRelayS@@": 30,
                b" *~Server~* .?AVtEconomyRelayS@@": 19,
                b" *~Server~* tShipRelayS": 22,
                b" *~Server~* tClockRelayS": 4,
                b" *~Server~* .?AVtChatRelayS@@": 29,
                b" *~Server~* tMapRelayS": 40,
                b" *~Server~* .?AVtNewsRelayS@@": 27,
                b" *~Server~* tMissionMatcherRelayS": 24,
            },
        )

    def test_character_logon_response_shape(self):
        payload = server._character_logon_payload(
            "user@example", "Captain Test", "192.0.2.10", 2
        )
        self.assertEqual(struct.unpack_from("<I", payload)[0], 0)
        address, offset = server._unpack_string(payload, 4)
        account, offset = server._unpack_string(payload, offset)
        self.assertEqual((address, account), ("192.0.2.10", "user@example"))
        self.assertEqual(struct.unpack_from("<I", payload, offset)[0], 1)

    def test_character_store_round_trip(self):
        old_path = server.CHARACTER_STORE_PATH
        old_persistence = server.PERSISTENCE
        try:
            with tempfile.TemporaryDirectory() as directory:
                server.CHARACTER_STORE_PATH = Path(directory) / "characters.json"
                server.PERSISTENCE = server.database.initialize(
                    Path(directory) / "campaign.sqlite3"
                )
                server.PERSISTENCE.execute(
                    "INSERT INTO campaigns(id, map_id, epoch_unix, initial_turn) "
                    "VALUES(1, 'retail', 0, 0)"
                )
                server.PERSISTENCE.commit()
                server._save_character(
                    "user@example", "Captain Test", "192.0.2.10", 2
                )
                record = server._load_characters()["user@example"]
                self.assertEqual(record["character_name"], "Captain Test")
                self.assertEqual(record["position"], [36, 29])
                self.assertEqual(record["homeworld"], [36, 29])
                self.assertEqual(record["destination"], [-1, -1])
                self.assertEqual(record["map_id"], server.CAMPAIGN_MAP_ID)
                self.assertEqual(record["ship"]["class_name"], "Falcon")
                self.assertEqual(record["ship"]["id"], 2)
                self.assertEqual(len(record["ship"]["officers"]), 6)
                self.assertEqual(
                    {item["station"] for item in record["ship"]["officers"]},
                    set(server.OFFICER_STATIONS),
                )
                officer_items = [
                    item for item in record["ship"]["refit"]["items"]
                    if item.startswith("OFFICER:")
                ]
                self.assertEqual(len(officer_items), 6)
                self.assertTrue(all(item.split(":")[2] for item in officer_items))
                self.assertEqual(server.PERSISTENCE.execute(
                    "SELECT COUNT(*) FROM officers WHERE ship_id=2"
                ).fetchone()[0], 6)
                payload = server._stored_character_payload("user@example", record)
                self.assertEqual(struct.unpack_from("<I", payload, len(payload) - 4)[0], 0)
                server.PERSISTENCE.close()
                server.PERSISTENCE = old_persistence
        finally:
            if server.PERSISTENCE is not None and server.PERSISTENCE is not old_persistence:
                server.PERSISTENCE.close()
            server.PERSISTENCE = old_persistence
            server.CHARACTER_STORE_PATH = old_path

    def test_old_character_coordinates_reset_when_campaign_map_changes(self):
        record = server._normalize_character_record({
            "character_name": "Legacy Captain",
            "race": server.RACE_FEDERATION,
            "position": [33, 5],
            "homeworld": [32, 1],
            "destination": [34, 5],
        })
        self.assertEqual(record["position"], [24, 19])
        self.assertEqual(record["homeworld"], [24, 19])
        self.assertEqual(record["destination"], [-1, -1])
        self.assertEqual(record["map_id"], server.CAMPAIGN_MAP_ID)

    def test_legacy_split_ship_state_migrates_into_one_persisted_instance(self):
        legacy = server._normalize_character_record({
            "race": server.RACE_FEDERATION,
            "stores": {"shuttles": 3, "marines": 1, "mines": 2},
            "refit": {"loadout_name": "Norway", "items": ["PHASER IX:1"]},
            "officers": [{"id": 1000, "name": "KLEIMAN", "station": 96, "worth": 14}],
        })
        self.assertNotIn("stores", legacy)
        self.assertNotIn("refit", legacy)
        self.assertNotIn("officers", legacy)
        self.assertEqual(legacy["ship"]["stores"]["shuttles"], 3)
        self.assertEqual(legacy["ship"]["refit"]["items"], ["PHASER IX:1"])
        self.assertEqual(legacy["ship"]["officers"][0]["name"], "KLEIMAN")

    def test_canonical_ship_snapshot_survives_json_restart(self):
        assets = Path(__file__).resolve().parent.parent / "assets" / "server-kit"
        record = server._normalize_character_record({
            "race": server.RACE_FEDERATION,
            "ship": {
                "id": 2, "owner_id": 1, "class_name": "Norway",
                "loadout_name": "Norway", "name": "USS Persistent",
                "class_type": 3, "bpv": 1250, "damage": 0.75, "flags": 3,
                "turn_created": 42,
                "stores": {"shuttles": 3, "marines": 1, "mines": 2},
                "refit": {"loadout_name": "Norway", "items": ["PHASER IX:1"]},
                "officers": [{"id": 1000, "name": "KLEIMAN", "station": 96, "worth": 14}],
            },
        })
        before = server._canonical_ship_snapshot(record, assets)
        restarted = json.loads(json.dumps(record))
        self.assertEqual(server._canonical_ship_snapshot(restarted, assets), before)

    def test_fleet_data_uses_persisted_ship_identity_class_and_position(self):
        record = server._normalize_character_record({
            "race": server.RACE_FEDERATION,
            "map_id": server.CAMPAIGN_MAP_ID,
            "position": [25, 20],
            "ship": {
                "id": 77, "class_name": "Sovereign", "loadout_name": "Sovereign A",
                "name": "USS Venture", "class_type": 8, "bpv": 2800,
                "damage": 1.0, "flags": 0,
            },
        })
        payload = server._fleet_data_payload(server.RACE_FEDERATION, record)
        self.assertEqual(
            struct.unpack_from("<IIiiIBI", payload, 5),
            (server.CHARACTER_DATABASE_ID, 77, 25, 20, 8, 1, 0),
        )

    def test_facility_payloads_share_exact_canonical_tng_configuration(self):
        assets = Path(__file__).resolve().parent.parent / "assets" / "server-kit"
        record = server._normalize_character_record({
            "race": server.RACE_FEDERATION,
            "ship": {
                "id": 2, "class_name": "Norway", "loadout_name": "Norway",
                "name": "USS Venture", "class_type": 3, "bpv": 1250,
                "damage": 1.0, "flags": 0,
                "refit": {"loadout_name": "Norway", "items": ["PHASER IX:1"]},
            },
        })
        defaults = server._character_ship_defaults(record, assets)
        expected = server._tng_ship_payload(
            server._default_ship_core_payload(defaults), defaults["loadout_fields"]
        )
        self.assertIn(expected, server._supply_dock_payload(
            server.RACE_FEDERATION, assets, record=record
        ))
        self.assertIn(expected, server._character_ship_config_payload(
            server.RACE_FEDERATION, assets, record=record
        ))
        with mock.patch.object(server, "_generated_officers", return_value=()):
            self.assertIn(expected, server._officers_to_review_payload(
                server.RACE_FEDERATION, assets, record=record
            ))


class DynamicSecurityReaderTests(unittest.IsolatedAsyncioTestCase):
    async def test_reader_skips_keepalive_and_reassembles_frame(self):
        reader = asyncio.StreamReader()
        client = object.__new__(server.DynamicSecurityClient)
        client.reader = reader
        frame = server._nswitch_frame(6, 2, 0x10002, b"payload")

        reader.feed_data(b"\x80\x00\x02" + frame[:7])
        reader.feed_data(frame[7:])
        reader.feed_eof()

        self.assertEqual(
            await client._read_nswitch_frame(timeout=1.0),
            (6, 2, 0x10002, b"payload"),
        )

    async def test_reader_rejects_payload_length_mismatch(self):
        reader = asyncio.StreamReader()
        client = object.__new__(server.DynamicSecurityClient)
        client.reader = reader
        body = struct.pack("<IIII", 6, 2, 3, 99) + b"x"
        reader.feed_data(struct.pack(">H", len(body)) + body)
        reader.feed_eof()

        with self.assertRaisesRegex(ValueError, "length mismatch"):
            await client._read_nswitch_frame(timeout=1.0)


class GameSpyDiscoveryTests(unittest.TestCase):
    def test_compact_list_matches_live_capture(self):
        self.assertEqual(
            gamespy.compact_server_list("70.27.77.102", 27633).hex(),
            "ebf91fc06862ebeaed4821f9df501d9073a77bd107",
        )

    def test_compact_list_rejects_ipv6(self):
        with self.assertRaisesRegex(ValueError, "IPv4"):
            gamespy.compact_server_list("::1", 27633)

    def test_compact_list_substitutes_only_encrypted_endpoint(self):
        response = gamespy.compact_server_list("127.0.0.1", 27633)

        self.assertEqual(len(response), 21)
        self.assertEqual(response[:8], bytes.fromhex("ebf91fc06862ebea"))
        self.assertEqual(response[8:].hex(), "d4536c9edf501d9073a77bd107")

    def test_status_response_advertises_game_port(self):
        response = gamespy.status_response("Test Dynaverse", 27632, "17.1")
        self.assertIn(b"\\gamename\\sfc3", response)
        self.assertIn(b"\\hostname\\Test Dynaverse", response)
        self.assertIn(b"\\hostport\\27632", response)
        self.assertTrue(response.endswith(b"\\final\\\\queryid\\17.1"))


class MasterDirectoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_directory_flow(self):
        listener = await asyncio.start_server(
            lambda reader, writer: server.MasterDirectoryClient(reader, writer).run(),
            "127.0.0.1",
            0,
        )
        port = listener.sockets[0].getsockname()[1]
        old_host = server.ADVERTISE_HOST
        old_port = server.STATUS_PORT
        server.ADVERTISE_HOST = "127.0.0.1"
        server.STATUS_PORT = 27633
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            greeting = await asyncio.wait_for(reader.readexactly(21), timeout=1.0)
            self.assertTrue(greeting.startswith(b"\\basic\\\\secure\\"))
            writer.write(
                b"\\gamename\\sfc3\\gamever\\2\\location\\0\\validate\\ignored"
                b"\\enctype\\2\\final\\\\queryid\\1.1\\"
                b"\\list\\cmp\\gamename\\sfc3\\final\\"
            )
            await writer.drain()
            response = await asyncio.wait_for(reader.read(), timeout=1.0)
            self.assertEqual(response, gamespy.compact_server_list("127.0.0.1", 27633))
            writer.close()
            await writer.wait_closed()
        finally:
            server.ADVERTISE_HOST = old_host
            server.STATUS_PORT = old_port
            listener.close()
            await listener.wait_closed()


if __name__ == "__main__":
    unittest.main()
