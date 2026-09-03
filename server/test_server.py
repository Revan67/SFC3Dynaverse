import asyncio
import struct
import unittest

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
