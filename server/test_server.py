import asyncio
import struct
import tempfile
import unittest
from pathlib import Path

import gamespy
import server


class DynamicSecurityWireTests(unittest.TestCase):
    def test_async_return_envelope(self):
        payload = b"\x01" + struct.pack("<III", 6, 2, 0x00010002) + b"private"
        self.assertEqual(server._parse_async_return(payload), (6, 2, 0x00010002))

    def test_async_return_rejects_wrong_marker(self):
        with self.assertRaises(ValueError):
            server._parse_async_return(b"\x00" + struct.pack("<III", 6, 2, 1))

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
