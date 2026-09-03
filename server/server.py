r"""
SFC3 Dynaverse replacement server — port 26100

Confirmed 18-step protocol (live Wireshark stream 42, 70.27.77.102:26100, 2026-05-17):

 1. S→C: GT2 challenge
 2. C→S: GT2 response
 3. S→C: GT2 accept (port=27100)
 4. C→S: binary hello (14 bytes: 00 0c fe ff ff ff ff ff ff ff 02 00 00 00)
 5. S→C: ASSIGN_SWITCH_ID = (0xFFFFFFFF, 0, 0, uint32LE(sw_id))   [random per session]
 6. S→C: FRAME_3          = (0xFFFFFFFF, 0, 1, [0x714, 0, 1] as uint32LEs)
 7. S→C: REGISTERED       = CTRL(0xFFFFFFFE, 0xFFFFFFFF, 3)
 8. C→S: relay name (0, 1, ch=0) + tAccessRelayS (0, 1, ch=2)
 9. S→C: tAccessRelayS ack → (sw_id, 1, 3)
           payload: uint32LE(25) + b" *~Server~* tAccessRelayS" + b"\x00\x00\x00\x00\x02\x00\x00\x00"
10. C→S: version info → (0, 2, 1)
11. S→C: version ack 1 → (sw_id, 4, 0, b"\x01\x01\x00")
12. S→C: version ack 2 → (sw_id, 4, 1, b"\x01")
13. S→C: CRC validation → (sw_id, 2, 2)  [causes client to register ch=3 handler on obj=2]
14. S→C: MOTD → (sw_id, 2, 8)
15. C→S: registration (0, 2, 2) + relay name 2 (0, 1, 1)  [triggered by step 13]
16. S→C: DATA(plen=0) → (sw_id, 2, 3)   ← FACTORY TRIGGER
17. S→C: IP data → (sw_id, 2, 4)
18. C→S: factory response (0, 1, 1)      [factory fired]
"""

import asyncio
import random
import string
import struct
import logging
import os

from gamespy import compact_server_list, status_response

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sfc3")

PORT          = int(os.environ.get("SFC3_RELAY_PORT", "26100"))
GAME_PORT     = int(os.environ.get("SFC3_GAME_PORT", "27632"))
SERVER_HOST   = os.environ.get("SFC3_SERVER_HOST", "127.0.0.1")
DIRECTORY_PORT = int(os.environ.get("SFC3_DIRECTORY_PORT", "28900"))
STATUS_PORT    = int(os.environ.get("SFC3_STATUS_PORT", "27633"))
ADVERTISE_HOST = os.environ.get("SFC3_ADVERTISE_HOST", SERVER_HOST)
SERVER_NAME    = os.environ.get("SFC3_SERVER_NAME", "Local SFC3 Dynaverse")

# ── Wire helpers ──────────────────────────────────────────────────────────────

def _gt2_frame(payload: bytes) -> bytes:
    return struct.pack(">H", len(payload)) + payload

def _gt2_negotiate(msg: str) -> bytes:
    payload = msg.encode("ascii") + b"\x00"
    return b"\x80" + struct.pack("<H", len(payload)) + payload

def _nswitch_frame(switch_id: int, object_id: int, channel: int, payload: bytes) -> bytes:
    header = struct.pack("<IIII", switch_id, object_id, channel, len(payload))
    return _gt2_frame(header + payload)

def _nswitch_ctrl(switch_id: int, object_id: int, channel: int) -> bytes:
    return _gt2_frame(struct.pack("<III", switch_id, object_id, channel))

def _pack_str(s: str) -> bytes:
    data = s.encode("ascii")
    return struct.pack("<I", len(data)) + data

def _random_str(length: int, chars: str = string.ascii_letters + string.digits) -> str:
    return "".join(random.choices(chars, k=length))

def _gt2_hash(challenge: str) -> str:
    key_text = os.environ.get("SFC3_GT2_KEY", "")
    if not key_text:
        raise RuntimeError(
            "SFC3_GT2_KEY is required; extract it from a legitimately owned client binary"
        )
    key = key_text.encode("ascii")
    key_len = len(key)
    ch = challenge.encode("ascii")
    n = len(ch)
    out = bytearray(32)
    for i in range(32):
        if n == 0 or i == 0 or i == 13:
            out[i] = random.randint(0, 0x7fff_ffff) % 0x5d + ord('!')
            continue
        c = ch[i] if (i == 1 or i == 14) else ch[i - 1]
        ch_i = ch[i] if ch[i] < 128 else ch[i] - 256
        key1  = key[(ch_i + i) % key_len]
        key1s = key1 if key1 < 128 else key1 - 256
        val   = (key1s + ch_i * i) & 0x1f
        c_s   = c if c < 128 else c - 256
        key2  = key[(c_s * i * 0x4647) % key_len]
        xor   = key2 ^ ch[val]
        xors  = xor if xor < 128 else xor - 256
        out[i] = abs(xors) % 0x5d + ord('!')
    return out.decode("ascii")

def _parse_kv(blob: bytes, key: str, fixed_len: int = 0) -> str:
    needle = f"\\{key}\\".encode("ascii")
    idx = blob.find(needle)
    if idx == -1:
        return ""
    start = idx + len(needle)
    if fixed_len:
        return blob[start : start + fixed_len].decode("ascii", errors="replace")
    end = blob.find(b"\\", start)
    return blob[start : end if end != -1 else len(blob)].decode("ascii", errors="replace")

def _parse_nswitch_frames(buf: bytes) -> list:
    frames = []
    pos = 0
    while pos + 2 <= len(buf):
        gt2_len = struct.unpack_from(">H", buf, pos)[0]
        end = pos + 2 + gt2_len
        if end > len(buf):
            break
        inner = buf[pos + 2 : end]
        if len(inner) >= 16:
            sw, obj, ch, plen = struct.unpack_from("<IIII", inner, 0)
            payload = inner[16 : 16 + plen]
            frames.append((sw, obj, ch, payload))
        pos = end
    return frames

def _build_motd() -> bytes:
    msg = "=" * 79 + "\r\nGame Message:\r\n"
    return struct.pack("<I", 2) + _pack_str(msg) + _pack_str(msg)


def _parse_async_return(payload: bytes) -> tuple[int, int, int]:
    """Read the dynamic-port request envelope without touching its private body."""
    if len(payload) < 13 or payload[0] != 1:
        raise ValueError("invalid async return envelope")
    return struct.unpack_from("<III", payload, 1)


def _security_challenge_payload(challenge: str) -> bytes:
    return struct.pack("<I", 1) + _pack_str(challenge)


def _security_success_payload() -> bytes:
    message = b"Successful security check"
    return struct.pack("<II", 1, 0) + struct.pack("<I", len(message)) + message


def _relay_claim_payload(name: bytes, object_id: int) -> bytes:
    return struct.pack("<I", len(name)) + name + struct.pack("<II", 0, object_id)


def _unpack_string(payload: bytes, offset: int) -> tuple[str, int]:
    if offset + 4 > len(payload):
        raise ValueError("truncated packed string length")
    length = struct.unpack_from("<I", payload, offset)[0]
    offset += 4
    if length > len(payload) - offset:
        raise ValueError("truncated packed string")
    try:
        value = payload[offset : offset + length].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("packed string is not ASCII") from exc
    return value, offset + length


def _parse_character_initialize(payload: bytes) -> tuple[tuple[int, int, int], str, str]:
    """Parse the login envelope while allowing callers to keep values private."""
    if len(payload) < 20:
        raise ValueError("truncated character initialize request")
    return_address = struct.unpack_from("<III", payload, 0)
    account, offset = _unpack_string(payload, 12)
    client_address, offset = _unpack_string(payload, offset)
    if offset != len(payload):
        raise ValueError("unexpected character initialize trailing data")
    return return_address, account, client_address


def _default_client_character_payload() -> bytes:
    """Serialize a default tClientCharacter for a character-not-found reply."""
    empty = _pack_str("")
    payload = bytearray(empty + empty)
    payload += struct.pack("<I", 0)  # database ID adjustment
    payload += empty
    payload += struct.pack(
        "<IIIIIIII",
        0,           # race
        0xFFFFFFFF,  # rank
        1500,        # rating
        0, 0, 0, 0, # prestige/disrepute totals
        0xFFFFFFFF,  # mission slot
    )
    payload += struct.pack("<ii", -1, -1) * 3  # current, home, destination hexes
    payload += struct.pack("<I", 0)  # empty ship-cache vector

    # Default tMetaMapHex: database ID/refcount, (0,0), two 0x09 flags,
    # seven integer fields, and two doubles.
    payload += struct.pack("<IIiiBB", 0, 0, 0, 0, 9, 9)
    payload += struct.pack("<IIIIIII", *([0] * 7))
    payload += struct.pack("<dd", 0.0, 0.0)
    payload += struct.pack("<IBB", 0, 0, 0)  # medals, AI, fleet
    return bytes(payload)


def _character_not_found_payload() -> bytes:
    """Build IPL_Character::tConnectPlayerReq::tRep for a new account."""
    return b"\x01" + _default_client_character_payload() + struct.pack("<I", 1)


# ── Client handler ────────────────────────────────────────────────────────────

class SFC3Client:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.addr   = writer.get_extra_info("peername")
        self.sw_id  = random.randint(1, 0xFFFFFFFE)

    def _log(self, level, msg, *args):
        getattr(log, level)(f"{self.addr[0]}:{self.addr[1]} {msg}", *args)

    async def run(self):
        self._log("info", "CONNECT sw_id=0x%08x", self.sw_id)
        try:
            await self._handle()
        except asyncio.IncompleteReadError:
            self._log("info", "DISCONNECTED")
        except asyncio.TimeoutError:
            self._log("warning", "TIMED OUT")
        except Exception as e:
            self._log("error", "error: %s", e, exc_info=True)
        finally:
            self.writer.close()

    async def _handle(self):
        if not await self._gt2_handshake():
            return

        try:
            hello = await asyncio.wait_for(self.reader.read(4096), timeout=10.0)
        except asyncio.TimeoutError:
            self._log("warning", "timeout waiting for binary hello")
            return
        if not hello:
            return
        self._log("info", "<- binary hello: %s", hello.hex())

        sw_id = self.sw_id
        self._log("info", "-> ASSIGN_SWITCH_ID (0x%08x) + FRAME_3 + REGISTERED", sw_id)
        self.writer.write(_nswitch_frame(0xFFFFFFFF, 0, 0, struct.pack("<I", sw_id)))
        self.writer.write(_nswitch_frame(0xFFFFFFFF, 0, 1, struct.pack("<III", 0x714, 0, 1)))
        self.writer.write(_nswitch_ctrl(0xFFFFFFFE, 0xFFFFFFFF, 3))
        await self.writer.drain()

        pub_buf = await self._wait_for_access_relay()
        if not pub_buf:
            return

        await self._auth_exchange()

    async def _gt2_handshake(self) -> bool:
        challenge = _random_str(32)
        self.writer.write(_gt2_negotiate(f"\\challenge\\{challenge}\\final\\"))
        await self.writer.drain()
        self._log("debug", "-> challenge %r", challenge)

        try:
            header = await asyncio.wait_for(self.reader.readexactly(3), timeout=12.0)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError):
            self._log("warning", "GT2 handshake: no response")
            return False

        if header[0] != 0x80:
            self._log("warning", "GT2 unexpected byte 0x%02x", header[0])
            return False

        length = struct.unpack_from("<H", header, 1)[0]
        try:
            payload = await asyncio.wait_for(self.reader.readexactly(length), timeout=12.0)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError):
            self._log("warning", "GT2 truncated response")
            return False

        self._log("info", "<- GT2 response: %r",
                  payload.rstrip(b"\x00").decode("ascii", errors="replace"))

        client_challenge = _parse_kv(payload, "challenge", fixed_len=32)
        client_port      = _parse_kv(payload, "port")
        self._log("debug", "client challenge=%r port=%r", client_challenge, client_port)

        accept_hash = _gt2_hash(client_challenge)
        self.writer.write(_gt2_negotiate(
            f"\\accept\\1\\response\\{accept_hash}\\port\\27100\\final\\"
        ))
        await self.writer.drain()
        self._log("debug", "-> accept hash=%r", accept_hash)
        return True

    async def _wait_for_access_relay(self) -> bytes:
        buf = b""
        while True:
            try:
                chunk = await asyncio.wait_for(self.reader.read(4096), timeout=30.0)
            except asyncio.TimeoutError:
                self._log("warning", "timeout waiting for tAccessRelayS")
                return b""
            if not chunk:
                return b""
            buf += chunk
            self._log("debug", "<- (pub) %s", chunk.hex())
            if b"tAccessRelayS" in buf:
                self._log("info", "tAccessRelayS received (%d bytes)", len(buf))
                return buf

    async def _read_step(self, timeout: float, label: str) -> bytes:
        """Read next non-keepalive data within timeout. Returns b'' on timeout/disconnect."""
        end = asyncio.get_event_loop().time() + timeout
        while True:
            left = end - asyncio.get_event_loop().time()
            if left <= 0:
                self._log("debug", "timeout waiting for %s", label)
                return b""
            try:
                data = await asyncio.wait_for(self.reader.read(4096), timeout=left)
            except asyncio.TimeoutError:
                self._log("debug", "timeout waiting for %s", label)
                return b""
            if not data:
                self._log("info", "disconnect waiting for %s", label)
                return b""
            if data == b"\x80\x00\x01":
                continue
            return data

    async def _auth_exchange(self):
        sw_id = self.sw_id

        # Step 9: tAccessRelayS ack → (sw_id, 1, 3)
        ack = (struct.pack("<I", 25) + b" *~Server~* tAccessRelayS"
               + b"\x00\x00\x00\x00\x02\x00\x00\x00")
        self.writer.write(_nswitch_frame(sw_id, 1, 3, ack))
        await self.writer.drain()
        self._log("info", "-> tAccessRelayS ack (sw_id=0x%08x, obj=1, ch=3)", sw_id)

        # Step 10: wait for version info C→S (0, 2, 1)
        ver = await self._read_step(10.0, "version info")
        if ver:
            self._log("info", "<- version info: %s", ver.hex())

        # Steps 11-12: version acks
        self.writer.write(_nswitch_frame(sw_id, 4, 0, b"\x01\x01\x00"))
        self.writer.write(_nswitch_frame(sw_id, 4, 1, b"\x01"))
        await self.writer.drain()
        self._log("info", "-> version acks (sw_id=0x%08x, obj=4, ch=0+1)", sw_id)

        # Step 13: CRC validation — triggers client to register ch=3 handler on obj=2
        crc = (_pack_str(SERVER_HOST)
               + _pack_str("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
               + _pack_str("abcdefghijklmnopqrstuvwxyz"))
        self.writer.write(_nswitch_frame(sw_id, 2, 2, crc))
        await self.writer.drain()
        self._log("info", "-> CRC validation (sw_id=0x%08x, obj=2, ch=2)", sw_id)

        # Step 14: MOTD
        self.writer.write(_nswitch_frame(sw_id, 2, 8, _build_motd()))
        await self.writer.drain()
        self._log("info", "-> MOTD (sw_id=0x%08x, obj=2, ch=8)", sw_id)

        # Step 15: wait for registration frames from client
        reg = await self._read_step(10.0, "registration")
        if reg:
            self._log("info", "<- registration: %s", reg.hex())

        # Step 16: factory trigger — DATA(plen=0) → (sw_id, 2, 3)
        self.writer.write(_nswitch_frame(sw_id, 2, 3, b""))
        await self.writer.drain()
        self._log("info", "-> FACTORY TRIGGER DATA(plen=0) (sw_id=0x%08x, obj=2, ch=3)", sw_id)

        # Step 17: IP data → (sw_id, 2, 4)
        ip = _pack_str(SERVER_HOST) + b"\x01\x00\x00\x00\x00\x00"
        self.writer.write(_nswitch_frame(sw_id, 2, 4, ip))
        await self.writer.drain()
        self._log("info", "-> IP data (sw_id=0x%08x, obj=2, ch=4)", sw_id)

        # Step 18+: listen for factory response and post-factory traffic (60 s)
        await self._listen_post_factory()

    async def _listen_post_factory(self):
        self._log("info", "=== Listening for factory response ===")
        end = asyncio.get_event_loop().time() + 60.0
        while asyncio.get_event_loop().time() < end:
            left = end - asyncio.get_event_loop().time()
            try:
                data = await asyncio.wait_for(self.reader.read(4096), timeout=min(left, 1.0))
            except asyncio.TimeoutError:
                continue
            if not data:
                self._log("info", "disconnect in post-factory listener")
                return
            if data == b"\x80\x00\x01":
                continue

            self._log("info", "<- post-factory: %s", data.hex())
            for sw, obj, ch, pl in _parse_nswitch_frames(data):
                self._log("info", "  sw=0x%08x obj=0x%08x ch=%d plen=%d: %s",
                          sw, obj, ch, len(pl), pl.hex())

            if len(data) >= 44 and struct.unpack_from("<I", data, 0)[0] == 40:
                ts, str_len = struct.unpack_from("<II", data, 4)
                challenge = data[12 : 12 + str_len]
                self._log("info",
                          "*** tServerChallengeRequest: ts=%d len=%d challenge=%s ***",
                          ts, str_len, challenge.hex())

        self._log("info", "60 s post-factory listen complete")


class DynamicSecurityClient:
    """Minimal live-capture-compatible security service for the dynamic game port."""

    SECURITY_RELAY = b" *~Server~* .?AVtSecurityRelayS@@"
    CHARACTER_RELAY = b" *~Server~* tCharacterRelayS"

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.addr = writer.get_extra_info("peername")
        self.sw_id = random.randint(1, 0xFFFFFFFE)

    def _log(self, level, msg, *args):
        getattr(log, level)(f"[game:{GAME_PORT}] {self.addr[0]}:{self.addr[1]} {msg}", *args)

    async def run(self):
        self._log("info", "CONNECT sw_id=0x%08x", self.sw_id)
        try:
            await self._handle()
        except asyncio.IncompleteReadError:
            self._log("info", "DISCONNECTED")
        except asyncio.TimeoutError:
            self._log("warning", "TIMED OUT")
        except Exception as exc:
            self._log("error", "error: %s", exc, exc_info=True)
        finally:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except (ConnectionError, OSError):
                pass

    async def _handle(self):
        if not await self._gt2_handshake():
            return

        hello = await asyncio.wait_for(self.reader.readexactly(14), timeout=10.0)
        if hello != _nswitch_ctrl(0xFFFFFFFE, 0xFFFFFFFF, 2):
            raise ValueError(f"unexpected binary hello ({len(hello)} bytes)")

        self.writer.write(_nswitch_frame(0xFFFFFFFF, 0, 0, struct.pack("<I", self.sw_id)))
        # The first word is opaque and varied between live sessions. Use the
        # neutral value already proven by the bootstrap path instead of baking
        # a captured process-specific value into server output.
        self.writer.write(_nswitch_frame(0xFFFFFFFF, 0, 1, struct.pack("<III", 0x714, 0, 1)))
        self.writer.write(_nswitch_ctrl(0xFFFFFFFE, 0xFFFFFFFF, 3))
        await self.writer.drain()

        _, _, _, publication = await self._wait_for(
            lambda sw, obj, ch, payload: sw == 0 and obj == 1 and ch == 2
            and b"tSecurityRelayS" in payload,
            "tSecurityRelayS publication",
        )
        self._log("info", "<- tSecurityRelayS publication (%d bytes)", len(publication))

        self.writer.write(b"\x80\x00\x02")
        self.writer.write(_nswitch_frame(
            self.sw_id,
            1,
            3,
            _relay_claim_payload(self.SECURITY_RELAY, 2),
        ))
        await self.writer.drain()
        self._log("info", "-> tSecurityRelayS claim")

        _, _, _, initialize = await self._wait_for(
            lambda sw, obj, ch, payload: sw == 0 and obj in (2, 32) and ch == 3,
            "security initialize request",
        )
        challenge_return = _parse_async_return(initialize)
        if challenge_return != (self.sw_id, 2, 0x00010001):
            raise ValueError(f"unexpected challenge return address {challenge_return!r}")

        challenge = _random_str(29, string.ascii_lowercase)
        self.writer.write(_nswitch_frame(
            challenge_return[0],
            challenge_return[1],
            challenge_return[2],
            _security_challenge_payload(challenge),
        ))
        await self.writer.drain()
        self._log("info", "-> security challenge (value redacted)")

        _, _, _, verification = await self._wait_for(
            lambda sw, obj, ch, payload: sw == 0 and obj in (2, 32) and ch == 2,
            "client verification request",
        )
        verify_return = _parse_async_return(verification)
        if verify_return != (self.sw_id, 2, 0x00010002):
            raise ValueError(f"unexpected verification return address {verify_return!r}")
        if len(verification) < 17:
            raise ValueError("verification request has no manifest count")
        manifest_count = struct.unpack_from("<I", verification, 13)[0]
        self._log(
            "info",
            "<- verification request plen=%d manifest_count=%d (private body not logged)",
            len(verification),
            manifest_count,
        )

        self.writer.write(_nswitch_frame(
            verify_return[0],
            verify_return[1],
            verify_return[2],
            _security_success_payload(),
        ))
        await self.writer.drain()
        self._log("info", "-> Successful security check")

        _, _, _, character = await self._wait_for(
            lambda sw, obj, ch, payload: sw == 0 and obj == 1 and ch == 2
            and b"tCharacterRelayS" in payload,
            "tCharacterRelayS publication",
        )
        self._log("info", "<- tCharacterRelayS publication (%d bytes)", len(character))
        self.writer.write(_nswitch_frame(
            self.sw_id,
            1,
            3,
            _relay_claim_payload(self.CHARACTER_RELAY, 6),
        ))
        await self.writer.drain()
        self._log("info", "-> tCharacterRelayS claim; security milestone complete")

        character_init = await self._read_nswitch_frame(timeout=30.0)
        if character_init[:3] != (0, 6, 3):
            raise ValueError(
                "unexpected first character frame "
                f"{character_init[0:3]!r}"
            )
        return_address, account, client_address = _parse_character_initialize(character_init[3])
        self._log(
            "info",
            "<- character initialize return=%r account_len=%d address_len=%d "
            "(private values not logged)",
            return_address,
            len(account),
            len(client_address),
        )

        self.writer.write(_nswitch_frame(
            return_address[0],
            return_address[1],
            return_address[2],
            _character_not_found_payload(),
        ))
        await self.writer.drain()
        self._log("info", "-> character not found; client may begin character creation")

        # Keep the connection available for the next implementation phase. Log only
        # structural metadata because authenticated payloads contain private fields.
        while True:
            sw, obj, ch, payload = await self._read_nswitch_frame(timeout=120.0)
            self._log("info", "<- frame sw=%d obj=%d ch=%d plen=%d", sw, obj, ch, len(payload))

    async def _gt2_handshake(self) -> bool:
        challenge = _random_str(32)
        self.writer.write(_gt2_negotiate(f"\\challenge\\{challenge}\\final\\"))
        await self.writer.drain()

        header = await asyncio.wait_for(self.reader.readexactly(3), timeout=12.0)
        if header[0] != 0x80:
            raise ValueError("invalid GT2 negotiation header")
        length = struct.unpack_from("<H", header, 1)[0]
        payload = await asyncio.wait_for(self.reader.readexactly(length), timeout=12.0)
        client_challenge = _parse_kv(payload, "challenge", fixed_len=32)
        if len(client_challenge) != 32:
            raise ValueError("missing client GT2 challenge")
        accept_hash = _gt2_hash(client_challenge)
        self.writer.write(_gt2_negotiate(
            f"\\accept\\1\\response\\{accept_hash}\\port\\{GAME_PORT}\\final\\"
        ))
        await self.writer.drain()
        self._log("info", "GT2 accepted (challenge values redacted)")
        return True

    async def _read_nswitch_frame(self, timeout: float) -> tuple[int, int, int, bytes]:
        while True:
            header = await asyncio.wait_for(self.reader.readexactly(2), timeout=timeout)
            if header == b"\x80\x00":
                keepalive = await asyncio.wait_for(self.reader.readexactly(1), timeout=timeout)
                if keepalive not in (b"\x01", b"\x02"):
                    raise ValueError("invalid keepalive")
                continue

            length = struct.unpack(">H", header)[0]
            if length < 16:
                # Control frames are valid but not useful to the dynamic security state.
                await asyncio.wait_for(self.reader.readexactly(length), timeout=timeout)
                continue
            body = await asyncio.wait_for(self.reader.readexactly(length), timeout=timeout)
            sw, obj, ch, payload_length = struct.unpack_from("<IIII", body, 0)
            if payload_length != length - 16:
                raise ValueError(
                    f"nSwitch length mismatch: header={payload_length} actual={length - 16}"
                )
            return sw, obj, ch, body[16:]

    async def _wait_for(self, predicate, label: str) -> tuple[int, int, int, bytes]:
        while True:
            frame = await self._read_nswitch_frame(timeout=30.0)
            if predicate(*frame):
                return frame
            self._log(
                "debug",
                "ignoring frame while waiting for %s: sw=%d obj=%d ch=%d plen=%d",
                label,
                frame[0],
                frame[1],
                frame[2],
                len(frame[3]),
            )


class MasterDirectoryClient:
    """Minimal GameSpy v1 compact-list service on TCP 28900."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.addr = writer.get_extra_info("peername")

    async def run(self):
        log.info("[directory:%d] CONNECT from %s:%d", DIRECTORY_PORT, *self.addr)
        try:
            challenge = _random_str(6)
            self.writer.write(f"\\basic\\\\secure\\{challenge}".encode("ascii"))
            await self.writer.drain()

            request = b""
            while b"\\list\\cmp\\gamename\\sfc3\\final\\" not in request:
                chunk = await asyncio.wait_for(self.reader.read(4096), timeout=15.0)
                if not chunk:
                    return
                request += chunk
                if len(request) > 8192:
                    raise ValueError("directory request exceeds limit")

            if b"\\gamename\\sfc3\\" not in request or b"\\enctype\\2\\" not in request:
                raise ValueError("unsupported directory request")

            response = compact_server_list(ADVERTISE_HOST, STATUS_PORT)
            self.writer.write(response)
            await self.writer.drain()
            log.info(
                "[directory:%d] advertised %s:%d (%d encoded bytes)",
                DIRECTORY_PORT,
                ADVERTISE_HOST,
                STATUS_PORT,
                len(response),
            )
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        except Exception as exc:
            log.error("[directory:%d] error: %s", DIRECTORY_PORT, exc, exc_info=True)
        finally:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except (ConnectionError, OSError):
                pass


class StatusProtocol(asyncio.DatagramProtocol):
    """Answer the client's legacy UDP ``\\status\\`` query."""

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data: bytes, addr):
        if data.strip(b"\0") != b"\\status\\":
            log.debug("[status:%d] ignored %d bytes from %s:%d", STATUS_PORT, len(data), *addr)
            return
        response = status_response(SERVER_NAME, GAME_PORT)
        self.transport.sendto(response, addr)
        log.info("[status:%d] replied to %s:%d (%d bytes)", STATUS_PORT, *addr, len(response))


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    relay_handler = lambda r, w: asyncio.ensure_future(SFC3Client(r, w).run())
    game_handler = lambda r, w: asyncio.ensure_future(DynamicSecurityClient(r, w).run())
    directory_handler = lambda r, w: asyncio.ensure_future(MasterDirectoryClient(r, w).run())
    relay_server = await asyncio.start_server(relay_handler, "0.0.0.0", PORT)
    game_server = await asyncio.start_server(game_handler, "0.0.0.0", GAME_PORT)
    directory_server = await asyncio.start_server(directory_handler, "0.0.0.0", DIRECTORY_PORT)
    loop = asyncio.get_running_loop()
    status_transport, _ = await loop.create_datagram_endpoint(
        StatusProtocol,
        local_addr=("0.0.0.0", STATUS_PORT),
    )
    log.info(
        "Listening on TCP %d/%d/%d and UDP %d; advertising %s:%d",
        PORT,
        GAME_PORT,
        DIRECTORY_PORT,
        STATUS_PORT,
        ADVERTISE_HOST,
        STATUS_PORT,
    )
    async with relay_server, game_server, directory_server:
        try:
            await asyncio.gather(
                relay_server.serve_forever(),
                game_server.serve_forever(),
                directory_server.serve_forever(),
            )
        finally:
            status_transport.close()


if __name__ == "__main__":
    asyncio.run(main())
