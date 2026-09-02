r"""
Multi-port probe — listens on all known Dynaverse ports simultaneously.

Purpose: verify the full 18-step auth exchange and factory trigger on port 26100;
         confirm no other ports are contacted by the SFC3 client.

Port roles:
  26100 — GT2 + nSwitch relay auth    (full SFC3Client protocol)
  27100 — secondary switch port       (raw capture)
  15101 — possible MetaServer         (raw capture)
  15300 — possible MetaServer         (raw capture)
  27400 — SFC3 game server            (raw capture)
  29900 — GameSpy auth / NNServer     (raw capture)
  28900 — GameSpy server list         (raw capture)
  29901 — GameSpy profile             (raw capture)

Usage:
  python probe.py          # default — all five ports
  python probe.py 26100    # only selected ports (space-separated)

Output prefix: [PORT:XXXXX] so you can grep per port if needed.
"""

import asyncio
import random
import string
import struct
import sys
import logging
import os

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("probe")

SERVER_HOST = os.environ.get("SFC3_SERVER_HOST", "127.0.0.1")

# ── Wire helpers ──────────────────────────────────────────────────────────────

def _gt2_frame(payload: bytes) -> bytes:
    return struct.pack(">H", len(payload)) + payload

def _gt2_negotiate(msg: str) -> bytes:
    payload = msg.encode("ascii") + b"\x00"
    return b"\x80" + struct.pack("<H", len(payload)) + payload

def _nswitch_frame(sw: int, obj: int, ch: int, payload: bytes) -> bytes:
    hdr = struct.pack("<IIII", sw, obj, ch, len(payload))
    return _gt2_frame(hdr + payload)

def _nswitch_ctrl(sw: int, obj: int, ch: int) -> bytes:
    return _gt2_frame(struct.pack("<III", sw, obj, ch))

def _pack_str(s: str) -> bytes:
    data = s.encode("ascii")
    return struct.pack("<I", len(data)) + data

def _random_str(n: int, chars: str = string.ascii_letters + string.digits) -> str:
    return "".join(random.choices(chars, k=n))

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


# ── GameSpy key-value helpers ────────────────────────────────────────────────

def _gs_parse(data: bytes) -> dict:
    r"""Parse \key\value\key\value\...\final\ into a dict."""
    text = data.decode("ascii", errors="replace").strip("\x00")
    parts = text.split("\\")
    # parts[0] is empty (leading \), then key, value, key, value, ...
    result = {}
    parts = [p for p in parts]
    i = 1
    while i + 1 < len(parts):
        result[parts[i]] = parts[i + 1]
        i += 2
    return result

def _gs_build(**kv) -> bytes:
    r"""Build \key\value\...\final\ packet."""
    out = ""
    for k, v in kv.items():
        out += f"\\{k}\\{v}"
    out += "\\final\\"
    return out.encode("ascii")


# ── GPCM handler (port 29900 — GameSpy Connection Manager) ───────────────────

class GPCMProbe:
    """Send the GPCM challenge so the client responds with its newuser/login payload."""
    TAG = "[PORT:29900]"

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.addr   = writer.get_extra_info("peername")

    async def run(self):
        log.info("%s CONNECT from %s:%d", self.TAG, *self.addr)
        try:
            await self._handle()
        except Exception as e:
            log.error("%s error: %s", self.TAG, e, exc_info=True)
        finally:
            self.writer.close()
            log.info("%s CLOSED", self.TAG)

    async def _handle(self):
        challenge = _random_str(10)
        greeting = _gs_build(lc="1", challenge=challenge, id="1")
        self.writer.write(greeting)
        await self.writer.drain()
        log.info("%s -> challenge %r", self.TAG, challenge)

        # Read client response (newuser or login command)
        end = asyncio.get_event_loop().time() + 30.0
        buf = b""
        while asyncio.get_event_loop().time() < end:
            left = end - asyncio.get_event_loop().time()
            try:
                chunk = await asyncio.wait_for(self.reader.read(4096), timeout=left)
            except asyncio.TimeoutError:
                break
            if not chunk:
                break
            buf += chunk
            if b"\\final\\" in buf:
                break

        if not buf:
            log.info("%s no response after challenge", self.TAG)
            return

        log.info("%s <- %d bytes: %s", self.TAG, len(buf), buf.hex())
        kv = _gs_parse(buf)
        # Account identifiers and proof material are sensitive even in a test probe.
        sensitive = {"password", "email", "user", "response", "challenge"}
        safe = {k: ("***" if k in sensitive else v) for k, v in kv.items()}
        log.info("%s parsed: %s", self.TAG, safe)

        sesskey = random.randint(1, 0x7fffffff)
        uid     = 1
        pid     = 1

        if "newuser" in kv:
            log.info("%s *** CREATE ACCOUNT — nick=%r ***",
                     self.TAG, kv.get("nick", ""))
            resp = _gs_build(lc="2", sesskey=str(sesskey),
                             userid=str(uid), profileid=str(pid), id="1")
            self.writer.write(resp)
            await self.writer.drain()
            log.info("%s -> newuser success (sesskey=%d uid=%d pid=%d)", self.TAG, sesskey, uid, pid)

        elif "login" in kv:
            nick = kv.get("user", "").split("@")[0]
            log.info("%s *** LOGIN request received ***", self.TAG)
            resp = _gs_build(lc="2", sesskey=str(sesskey),
                             userid=str(uid), profileid=str(pid),
                             uniquenick=nick, id="1")
            self.writer.write(resp)
            await self.writer.drain()
            log.info("%s -> login success (sesskey=%d uid=%d pid=%d)", self.TAG, sesskey, uid, pid)

        else:
            log.info("%s unknown GPCM command", self.TAG)
            return

        # Stay open and capture whatever the client sends next
        end2 = asyncio.get_event_loop().time() + 30.0
        buf2 = b""
        while asyncio.get_event_loop().time() < end2:
            left = end2 - asyncio.get_event_loop().time()
            try:
                chunk = await asyncio.wait_for(self.reader.read(4096), timeout=left)
            except asyncio.TimeoutError:
                break
            if not chunk:
                break
            buf2 += chunk
            log.info("%s <- post-auth %d bytes: %s", self.TAG, len(chunk), chunk.hex())
            kv2 = _gs_parse(chunk)
            if kv2:
                log.info("%s    parsed: %s", self.TAG, kv2)


# ── GPSP handler (port 29901 — GameSpy Profile Search) ───────────────────────

class GPSPProbe:
    """Respond to \\valid\\ so the login flow advances to GPCM."""
    TAG = "[PORT:29901]"

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.addr   = writer.get_extra_info("peername")

    async def run(self):
        log.info("%s CONNECT from %s:%d", self.TAG, *self.addr)
        try:
            await self._handle()
        except Exception as e:
            log.error("%s error: %s", self.TAG, e, exc_info=True)
        finally:
            self.writer.close()
            log.info("%s CLOSED", self.TAG)

    async def _handle(self):
        end = asyncio.get_event_loop().time() + 15.0
        buf = b""
        while asyncio.get_event_loop().time() < end:
            left = end - asyncio.get_event_loop().time()
            try:
                chunk = await asyncio.wait_for(self.reader.read(4096), timeout=left)
            except asyncio.TimeoutError:
                break
            if not chunk:
                break
            buf += chunk
            if b"\\final\\" in buf:
                break

        if not buf:
            log.info("%s no data", self.TAG)
            return

        log.info("%s <- %d bytes: %s", self.TAG, len(buf), buf.hex())
        kv = _gs_parse(buf)
        log.info("%s parsed: %s", self.TAG, kv)

        if "valid" in kv:
            email = kv.get("email", "")
            log.info("%s *** \\valid\\ account-existence check ***", self.TAG)
            # Respond: account exists → client will proceed to GPCM login
            resp = b"\\vr\\1\\final\\"
            self.writer.write(resp)
            await self.writer.drain()
            log.info("%s -> \\vr\\1\\final\\ (account exists)", self.TAG)
        elif "search" in kv or "nick" in kv:
            log.info("%s *** profile search ***", self.TAG)
        else:
            log.info("%s unknown command: %s", self.TAG, kv)


# ── Raw-capture handler (all remaining ports) ─────────────────────────────────

class RawCapture:
    HOLD_OPEN = 120.0

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                 port: int):
        self.reader = reader
        self.writer = writer
        self.port   = port
        self.tag    = f"[PORT:{port:5d}]"
        self.addr   = writer.get_extra_info("peername")

    async def run(self):
        log.info("%s CONNECT from %s:%d", self.tag, *self.addr)
        try:
            await self._capture()
        except asyncio.IncompleteReadError:
            pass
        except Exception as e:
            log.error("%s error: %s", self.tag, e, exc_info=True)
        finally:
            self.writer.close()
            log.info("%s CLOSED", self.tag)

    async def _capture(self):
        total = 0
        while True:
            try:
                chunk = await asyncio.wait_for(
                    self.reader.read(4096), timeout=self.HOLD_OPEN
                )
            except asyncio.TimeoutError:
                log.info("%s no data for %.0fs — closing", self.tag, self.HOLD_OPEN)
                return
            if not chunk:
                log.info("%s EOF after %d bytes", self.tag, total)
                return
            total += len(chunk)
            log.info("%s <- %d bytes: %s", self.tag, len(chunk), chunk.hex())


# ── Full SFC3 relay-auth handler (port 26100) ─────────────────────────────────

class SFC3Client:
    TAG = "[PORT:26100]"

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.addr   = writer.get_extra_info("peername")
        self.sw_id  = random.randint(1, 0xFFFFFFFE)

    def _log(self, level, msg, *args):
        getattr(log, level)(f"{self.TAG} {msg}", *args)

    async def run(self):
        self._log("info", "CONNECT from %s:%d sw_id=0x%08x", *self.addr, self.sw_id)
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
            self._log("warning", "timed out waiting for binary hello")
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

        # Step 10: wait for version info C→S
        ver = await self._read_step(10.0, "version info")
        if ver:
            self._log("info", "<- version info (%d bytes): %s", len(ver), ver.hex())
            for sw, obj, ch, pl in _parse_nswitch_frames(ver):
                self._log("info", "  sw=0x%08x obj=0x%08x ch=%d plen=%d: %s",
                          sw, obj, ch, len(pl), pl.hex())

        # Steps 11-12: version acks
        self.writer.write(_nswitch_frame(sw_id, 4, 0, b"\x01\x01\x00"))
        self.writer.write(_nswitch_frame(sw_id, 4, 1, b"\x01"))
        await self.writer.drain()
        self._log("info", "-> version acks (sw_id=0x%08x, obj=4, ch=0+1)", sw_id)

        # Step 13: CRC validation — causes client to register ch=3 handler on obj=2
        crc = (_pack_str(SERVER_HOST)
               + _pack_str("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
               + _pack_str("abcdefghijklmnopqrstuvwxyz"))
        self.writer.write(_nswitch_frame(sw_id, 2, 2, crc))
        await self.writer.drain()
        self._log("info", "-> CRC validation (sw_id=0x%08x, obj=2, ch=2, plen=%d)",
                  sw_id, len(crc))

        # Step 14: MOTD
        motd = _build_motd()
        self.writer.write(_nswitch_frame(sw_id, 2, 8, motd))
        await self.writer.drain()
        self._log("info", "-> MOTD (sw_id=0x%08x, obj=2, ch=8, plen=%d)", sw_id, len(motd))

        # Step 15: wait for registration (0,2,2) + relay name 2 (0,1,1)
        reg = await self._read_step(10.0, "registration")
        if reg:
            self._log("info", "<- registration (%d bytes): %s", len(reg), reg.hex())
            for sw, obj, ch, pl in _parse_nswitch_frames(reg):
                self._log("info", "  sw=0x%08x obj=0x%08x ch=%d plen=%d: %s",
                          sw, obj, ch, len(pl), pl.hex())
        else:
            self._log("warning", "registration not received — continuing anyway")

        # Step 16: factory trigger — DATA(plen=0) → (sw_id, 2, 3)
        self.writer.write(_nswitch_frame(sw_id, 2, 3, b""))
        await self.writer.drain()
        self._log("info", "*** FACTORY TRIGGER DATA(plen=0) → (sw_id=0x%08x, obj=2, ch=3) ***",
                  sw_id)

        # Step 17: IP data
        ip = _pack_str(SERVER_HOST) + b"\x01\x00\x00\x00\x00\x00"
        self.writer.write(_nswitch_frame(sw_id, 2, 4, ip))
        await self.writer.drain()
        self._log("info", "-> IP data (sw_id=0x%08x, obj=2, ch=4)", sw_id)

        # Step 18+: listen for factory response
        self._log("info", "=== Listening for factory response (60 s) ===")
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
                          "*** tServerChallengeRequest DETECTED — factory fired! ***")
                self._log("info", "    ts=%d len=%d challenge=%s", ts, str_len, challenge.hex())
                return

            if _parse_nswitch_frames(data):
                self._log("info", "*** Factory response frames received ***")

        self._log("info", "60 s elapsed — no factory response received")


# ── Entry point ───────────────────────────────────────────────────────────────

ALL_PORTS = [26100, 27100, 15101, 15300, 27400, 29900, 28900, 29901]

async def main(ports: list[int]):
    servers = []

    _handler_names = {26100: "SFC3Client", 29900: "GPCMProbe", 29901: "GPSPProbe"}

    def _make_handler(port: int):
        if port == 26100:
            return lambda r, w: asyncio.ensure_future(SFC3Client(r, w).run())
        elif port == 29900:
            return lambda r, w: asyncio.ensure_future(GPCMProbe(r, w).run())
        elif port == 29901:
            return lambda r, w: asyncio.ensure_future(GPSPProbe(r, w).run())
        else:
            return lambda r, w: asyncio.ensure_future(
                RawCapture(r, w, port).run()
            )

    for port in ports:
        srv = await asyncio.start_server(_make_handler(port), "0.0.0.0", port)
        servers.append(srv)
        log.info("[PROBE] Listening on port %d (%s)",
                 port, _handler_names.get(port, "RawCapture"))

    log.info("[PROBE] All %d ports open. Hit Connect in SFC3.", len(servers))
    async with asyncio.TaskGroup() as tg:
        for srv in servers:
            tg.create_task(srv.serve_forever())


if __name__ == "__main__":
    selected = [int(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else ALL_PORTS
    asyncio.run(main(selected))
