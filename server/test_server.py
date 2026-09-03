import asyncio
import struct
import tempfile
import unittest
from pathlib import Path

import gamespy
import server


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

    def test_clock_snapshot_shape(self):
        payload = server._clock_snapshot_payload()
        self.assertEqual(len(payload), 21)
        self.assertEqual(
            struct.unpack_from("<IIIII", payload, 1),
            (0, 8, 10_000, 120_000, 2159),
        )

    def test_map_size_shape_matches_live_capture(self):
        payload = server._map_size_payload()
        self.assertEqual(payload, b"\x01" + struct.pack("<II", 35, 29))

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

    def test_campaign_map_snapshot_shape_and_starting_region(self):
        payload = server._map_snapshot_payload()
        count = 35 * 29
        self.assertEqual(len(payload), 1 + 12 + count * 11 + 8)
        self.assertEqual(struct.unpack_from("<iiI", payload, 1), (-1, -1, count))
        self.assertEqual(payload[13:24], bytes.fromhex("0909000000040000140a64"))
        self.assertEqual(struct.unpack_from("<II", payload, len(payload) - 8), (35, 29))

        start_x, start_y = server.CAMPAIGN_STARTS[server.RACE_FEDERATION]
        start_index = start_y * 35 + start_x
        start_offset = 13 + start_index * 11
        self.assertEqual(
            payload[start_offset : start_offset + 11],
            bytes.fromhex("0000000000040100326464"),
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
        try:
            with tempfile.TemporaryDirectory() as directory:
                server.CHARACTER_STORE_PATH = Path(directory) / "characters.json"
                server._save_character(
                    "user@example", "Captain Test", "192.0.2.10", 2
                )
                record = server._load_characters()["user@example"]
                self.assertEqual(record["character_name"], "Captain Test")
                payload = server._stored_character_payload("user@example", record)
                self.assertEqual(struct.unpack_from("<I", payload, len(payload) - 4)[0], 0)
        finally:
            server.CHARACTER_STORE_PATH = old_path


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
