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
import contextlib
import hashlib
import hmac
import json
import random
import string
import struct
import logging
import os
import time
from dataclasses import dataclass

import database
from pathlib import Path

from asset_sources import find_structured_asset, parse_gf
from campaign_map import (
    CLIENT_HEX_RECORDS,
    HEIGHT as CAMPAIGN_MAP_HEIGHT,
    SOURCE_SHA256 as CAMPAIGN_MAP_ID,
    WIDTH as CAMPAIGN_MAP_WIDTH,
)
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
BIND_HOSTS = tuple(
    dict.fromkeys(
        host.strip()
        for host in os.environ.get("SFC3_BIND_HOSTS", SERVER_HOST).split(",")
        if host.strip()
    )
)
DIRECTORY_PORT = int(os.environ.get("SFC3_DIRECTORY_PORT", "28900"))
STATUS_PORT    = int(os.environ.get("SFC3_STATUS_PORT", "27633"))
ADVERTISE_HOST = os.environ.get("SFC3_ADVERTISE_HOST", SERVER_HOST)
SERVER_NAME    = os.environ.get("SFC3_SERVER_NAME", "Local SFC3 Dynaverse")
PRIVATE_CAPTURE_PATH = os.environ.get("SFC3_PRIVATE_CAPTURE_PATH", "")
# Temporary fixed default. Expose this as a user-configurable setting when the
# server UI/configuration layer is built.
SESSION_IDLE_TIMEOUT = 15 * 60
RACE_FEDERATION = 0
RACE_KLINGON = 1
RACE_ROMULAN = 2
RACE_BORG = 3
RACE_NEUTRAL = 9
TERRAIN_OPEN_SPACE = 0x04000000
CAMPAIGN_STARTS = {
    RACE_FEDERATION: (24, 19),
    RACE_KLINGON: (7, 16),
    RACE_ROMULAN: (36, 29),
    RACE_BORG: (38, 0),
}
CAMPAIGN_HOMEWORLDS = {
    RACE_FEDERATION: (24, 19),
    RACE_KLINGON: (7, 16),
    RACE_ROMULAN: (36, 29),
    RACE_BORG: (38, 0),
}
STARTING_SHIPS = {
    RACE_FEDERATION: ("Norway", "USS Venture", 3),
    RACE_KLINGON: ("K'Vort", "IKS Qapla'", 3),
    RACE_ROMULAN: ("Falcon", "IRW Decius", 3),
    RACE_BORG: ("Diamond", "Designation 01", 6),
}
WEAPON_ARCS = (
    "PLANET", "SPECIAL", "NONE", "0_360", "0_60", "60_120", "120_180",
    "180_240", "240_300", "300_360", "30_90", "90_150", "150_210",
    "210_270", "270_330", "330_30", "345_15", "165_195", "0_120",
    "120_240", "240_360", "60_180", "180_300", "300_60", "0_90",
    "90_180", "180_270", "270_360", "0_180", "180_360", "270_90",
    "90_270", "240_120", "60_300", "330_150", "210_30", "300_120",
    "240_60", "270_120", "240_90", "0_240", "120_360", "60_240",
    "120_300",
)
WEAPON_ARC_IDS = {name.casefold(): index for index, name in enumerate(WEAPON_ARCS)}
SHIP_CLASS_CODES = (
    "SH", "F", "FF", "DD", "CL", "CA", "BCH", "DN", "BB", "LP", "SY",
    "BS", "BT", "SB", "BIO", "PLANET", "SPECIAL",
)
SHIP_CLASS_IDS = {name.casefold(): index for index, name in enumerate(SHIP_CLASS_CODES)}
CHARACTER_DATABASE_ID = 1
SHIP_DATABASE_ID = 2
AUCTION_DATABASE_ID_BASE = 2000
CHARACTER_STORE_PATH = Path(
    os.environ.get(
        "SFC3_CHARACTER_STORE",
        str(Path(__file__).with_name("characters.local.json")),
    )
)
CAMPAIGN_STATE_PATH = Path(
    os.environ.get(
        "SFC3_CAMPAIGN_STATE",
        str(Path(__file__).with_name("campaign.local.json")),
    )
)
DATABASE_PATH = Path(
    os.environ.get("SFC3_DATABASE", "").strip()
    or str(Path(__file__).with_name("campaign.local.sqlite3"))
)
DEFAULT_DATABASE_PATH = Path(
    os.environ.get("SFC3_DEFAULT_DATABASE", "").strip()
    or str(Path(__file__).with_name("default-campaign.sqlite3"))
)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVER_ASSET_ROOT = Path(
    os.environ.get(
        "SFC3_SERVER_ASSET_ROOT", PROJECT_ROOT / "assets" / "server-kit"
    )
)
# Ship definitions are part of the publicly released server kit. Keep this
# alias while the ship serializers still accept the older generic asset-root
# argument, but do not load commercial retail installation assets at runtime.
ASSET_ROOT = SERVER_ASSET_ROOT
PERSISTENCE = None

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


def _parse_callback(payload: bytes) -> tuple[int, int, int]:
    """Read the unmarked callback address used by campaign relay requests."""
    if len(payload) < 12:
        raise ValueError("truncated callback address")
    return struct.unpack_from("<III", payload)


def _security_challenge_payload(challenge: str) -> bytes:
    return struct.pack("<I", 1) + _pack_str(challenge)


def _security_success_payload() -> bytes:
    message = b"Successful security check"
    return struct.pack("<II", 1, 0) + struct.pack("<I", len(message)) + message


@dataclass(frozen=True)
class CampaignClockConfig:
    turns_per_year: int
    milliseconds_per_turn: int
    base_year: int


@dataclass(frozen=True)
class CampaignClockSnapshot:
    current_turn: int
    current_year: int
    turns_per_year: int
    milliseconds_per_turn: int
    base_year: int

    def payload(self) -> bytes:
        values = (
            self.current_turn,
            self.current_year,
            self.turns_per_year,
            self.milliseconds_per_turn,
            self.base_year,
        )
        if any(not 0 <= value <= 0xFFFFFFFF for value in values):
            raise ValueError("campaign clock fields must fit unsigned 32-bit values")
        return b"\x01" + struct.pack("<IIIII", *values)


def _clock_config() -> CampaignClockConfig:
    """Load the complete client-facing clock configuration from Time.gf."""
    source = find_structured_asset(
        "ServerProfiles/Time.gf",
        server_asset_root=SERVER_ASSET_ROOT,
        retail_asset_root=ASSET_ROOT,
    )
    profile = parse_gf(source.path)
    values = profile.get("Clock", {})
    starting_date = profile.get("Clock/StartingDate", {})
    turns_per_year = int(values.get("TurnsPerYear", 10_000))
    milliseconds_per_turn = int(values.get("MilliSecondsPerTurn", 120_000))
    base_year = int(starting_date.get("BaseYear", 56_200))
    if turns_per_year <= 0 or milliseconds_per_turn <= 0 or base_year < 0:
        raise ValueError("Time.gf clock values must be positive")
    return CampaignClockConfig(turns_per_year, milliseconds_per_turn, base_year)


def _load_campaign_clock(now: float | None = None) -> dict:
    """Load or initialize the restart-stable wall-clock campaign epoch."""
    current_time = time.time() if now is None else float(now)
    if CAMPAIGN_STATE_PATH.exists():
        state = json.loads(CAMPAIGN_STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            raise ValueError("campaign state must contain an object")
        epoch = float(state["epoch_unix"])
        initial_turn = int(state.get("initial_turn", 0))
        if epoch < 0 or initial_turn < 0:
            raise ValueError("campaign clock values cannot be negative")
        state["epoch_unix"] = epoch
        state["initial_turn"] = initial_turn
        state.setdefault("auctions", {})
        return state
    state = {"epoch_unix": current_time, "initial_turn": 0, "auctions": {}}
    CAMPAIGN_STATE_PATH.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return state


def _write_campaign_state(state: dict) -> None:
    CAMPAIGN_STATE_PATH.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _campaign_turn(now: float | None = None) -> int:
    """Calculate the current turn while preserving the epoch across restarts."""
    current_time = time.time() if now is None else float(now)
    state = _load_campaign_clock(current_time)
    config = _clock_config()
    elapsed_ms = max(0.0, (current_time - state["epoch_unix"]) * 1000.0)
    return state["initial_turn"] + int(elapsed_ms // config.milliseconds_per_turn)


def _clock_snapshot(now: float | None = None) -> CampaignClockSnapshot:
    """Return one canonical tCurrentTime snapshot with retail field semantics."""
    config = _clock_config()
    current_turn = _campaign_turn(now)
    return CampaignClockSnapshot(
        current_turn=current_turn,
        current_year=current_turn // config.turns_per_year,
        turns_per_year=config.turns_per_year,
        milliseconds_per_turn=config.milliseconds_per_turn,
        base_year=config.base_year,
    )


def _clock_snapshot_payload(now: float | None = None) -> bytes:
    """Build tCurrentTime using persistent time and server-kit cadence."""
    return _clock_snapshot(now).payload()


def _milliseconds_until_next_turn(now: float | None = None) -> float:
    """Return the wall-clock delay to the next persisted campaign turn."""
    current_time = time.time() if now is None else float(now)
    state = _load_campaign_clock(current_time)
    config = _clock_config()
    elapsed_ms = max(0.0, (current_time - state["epoch_unix"]) * 1000.0)
    remainder = elapsed_ms % config.milliseconds_per_turn
    return config.milliseconds_per_turn - remainder


def _map_size_payload() -> bytes:
    """Build IPL_Map::tRequestMapSizeReq::tRep."""
    return b"\x01" + struct.pack("<II", CAMPAIGN_MAP_WIDTH, CAMPAIGN_MAP_HEIGHT)


def _client_hex_payload(
    race: int,
    *,
    planet_race: int | None = None,
    terrain: int = TERRAIN_OPEN_SPACE,
    has_planet: bool = False,
    has_starbase: bool = False,
    victory_points: int = 20,
    economy_points: int = 10,
    speed_percent: int = 100,
) -> bytes:
    """Serialize the compact 11-byte tClientHex record."""
    if planet_race is None:
        planet_race = race
    byte_fields = (
        race,
        planet_race,
        int(has_planet),
        int(has_starbase),
        victory_points,
        economy_points,
        speed_percent,
    )
    if any(not 0 <= value <= 0xFF for value in byte_fields):
        raise ValueError("tClientHex byte field outside 0..255")
    return struct.pack(
        "<BBIBBBBB",
        race,
        planet_race,
        terrain,
        int(has_planet),
        int(has_starbase),
        victory_points,
        economy_points,
        speed_percent,
    )


def _meta_map_hex_payload(
    x: int,
    y: int,
    race: int,
    *,
    database_id: int = 1,
    has_planet: bool = False,
    has_starbase: bool = False,
    victory_points: int = 20,
    economy_points: int = 20,
) -> bytes:
    """Serialize the 62-byte tMetaMapHex used in character position state."""
    return (
        struct.pack("<IIiiBB", database_id, 0, x, y, race, race)
        + struct.pack(
            "<IIIIIII",
            TERRAIN_OPEN_SPACE,
            int(has_planet),
            int(has_starbase),
            victory_points,
            economy_points,
            0,
            0,
        )
        + struct.pack("<dd", 1.0, 1.0)
    )


def _campaign_start_for_race(race: int) -> tuple[int, int]:
    return CAMPAIGN_STARTS.get(
        race, (CAMPAIGN_MAP_WIDTH // 2, CAMPAIGN_MAP_HEIGHT // 2)
    )


def _campaign_homeworld_for_race(race: int) -> tuple[int, int]:
    return CAMPAIGN_HOMEWORLDS.get(race, _campaign_start_for_race(race))


def _character_position_payload(
    race: int,
    position: tuple[int, int] | None = None,
    destination: tuple[int, int] = (-1, -1),
) -> bytes:
    """Build IPL_Character::tGetCharacterPositionReq::tRep."""
    position_x, position_y = position or _campaign_start_for_race(race)
    return (
        b"\x01"
        + _meta_map_hex_payload(
            position_x,
            position_y,
            race,
            has_planet=True,
            victory_points=50,
            economy_points=100,
        )
        + struct.pack("<ii", *destination)
    )


def _get_client_character_payload(
    account: str,
    character_name: str,
    client_address: str,
    race: int,
    record: dict | None = None,
) -> bytes:
    """Build IPL_Character::tGetClientCharacterReq::tRep."""
    record = _normalize_character_record(record or {"race": race})
    return (
        b"\x01"
        + _default_client_character_payload(
            client_address=client_address,
            account=account,
            character_name=character_name,
            race=race,
            database_id=1,
            rank=0,
            current_position=tuple(record["position"]),
            homeworld=tuple(record["homeworld"]),
            destination=tuple(record["destination"]),
            prestige=int(record["prestige"]),
            ship=record["ship"],
        )
        + b"\x01"
    )


def _starting_ship_for_race(race: int) -> tuple[str, str, int]:
    return STARTING_SHIPS.get(race, STARTING_SHIPS[RACE_FEDERATION])


def _ship_cache_payload(race: int, ship: dict | None = None) -> bytes:
    """Serialize tServCharacter::tShipCache for the race's starter ship."""
    class_name, ship_name, class_type = _starting_ship_for_race(race)
    ship = ship or {}
    return (
        struct.pack(
            "<III",
            int(ship.get("id", SHIP_DATABASE_ID)),
            int(ship.get("bpv", 250)),
            int(ship.get("class_type", class_type)),
        )
        + _pack_str(str(ship.get("class_name", class_name)))
        + struct.pack("<f", float(ship.get("damage", 1.0)))
        + _pack_str(str(ship.get("name", ship_name)))
        + struct.pack("<I", int(ship.get("flags", 0)))
    )


def _fleet_data_payload(race: int, record: dict | None = None) -> bytes:
    """Build tGetFleetDataReq::tRep from the authoritative ship instance."""
    if record is None:
        x, y = _campaign_start_for_race(race)
        _class_name, _ship_name, class_type = _starting_ship_for_race(race)
        character_id = CHARACTER_DATABASE_ID
        ship_id = SHIP_DATABASE_ID
    else:
        record = _normalize_character_record(record)
        x, y = record["position"]
        ship = record["ship"]
        class_type = int(ship["class_type"])
        character_id = int(record.get("database_id", CHARACTER_DATABASE_ID))
        ship_id = int(ship["id"])
    fleet_icon = struct.pack(
        "<IIiiIBI",
        character_id,
        ship_id,
        x,
        y,
        class_type,
        1,  # belongs to the requesting character
        0,  # icon flags
    )
    return b"\x01" + struct.pack("<I", 1) + fleet_icon


def _map_snapshot_payload() -> bytes:
    """Build the stock retail multiplayer campaign-map snapshot."""
    count = CAMPAIGN_MAP_WIDTH * CAMPAIGN_MAP_HEIGHT
    return (
        b"\x01"
        + struct.pack("<iiI", -1, -1, count)
        + CLIENT_HEX_RECORDS
        + struct.pack("<II", CAMPAIGN_MAP_WIDTH, CAMPAIGN_MAP_HEIGHT)
    )


def _campaign_hex_fields(position: tuple[int, int]) -> tuple[int, int, int, bool, bool, int, int, int]:
    """Decode one compact tClientHex from the retail campaign baseline."""
    x, y = position
    if not (0 <= x < CAMPAIGN_MAP_WIDTH and 0 <= y < CAMPAIGN_MAP_HEIGHT):
        raise ValueError("campaign position outside map")
    offset = (y * CAMPAIGN_MAP_WIDTH + x) * 11
    race, planet_race, terrain, has_planet, has_starbase, victory, economy, speed = (
        struct.unpack_from("<BBIBBBBB", CLIENT_HEX_RECORDS, offset)
    )
    return race, planet_race, terrain, bool(has_planet), bool(has_starbase), victory, economy, speed


def _at_friendly_base_or_planet(position: tuple[int, int], race: int) -> bool:
    political_race, planet_race, _terrain, has_planet, has_starbase, *_ = (
        _campaign_hex_fields(position)
    )
    return has_starbase and political_race == race or has_planet and planet_race == race


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


def _default_client_character_payload(
    *,
    client_address: str = "",
    account: str = "",
    character_name: str = "",
    race: int = 0,
    database_id: int = 0,
    rank: int = 0xFFFFFFFF,
    include_ship: bool = True,
    current_position: tuple[int, int] | None = None,
    homeworld: tuple[int, int] | None = None,
    destination: tuple[int, int] = (-1, -1),
    prestige: int = 0,
    ship: dict | None = None,
) -> bytes:
    """Serialize the wire-visible fields of a minimal tClientCharacter."""
    payload = bytearray(_pack_str(client_address) + _pack_str(account))
    payload += struct.pack("<I", database_id)
    payload += _pack_str(character_name)
    payload += struct.pack(
        "<IIIIIIII",
        race,
        rank,
        1500,        # rating
        prestige, prestige, 0, 0, # current/total prestige and disrepute
        0xFFFFFFFF,  # mission slot
    )
    start_x, start_y = current_position or _campaign_start_for_race(race)
    home_x, home_y = homeworld or _campaign_homeworld_for_race(race)
    payload += struct.pack("<ii", start_x, start_y)  # current hex
    payload += struct.pack("<ii", home_x, home_y)    # homeworld hex
    payload += struct.pack("<ii", *destination)
    if include_ship:
        payload += struct.pack("<I", 1) + _ship_cache_payload(race, ship)
    else:
        payload += struct.pack("<I", 0)

    payload += _meta_map_hex_payload(
        start_x,
        start_y,
        race,
        has_planet=True,
        victory_points=50,
        economy_points=100,
    )
    payload += struct.pack("<IBB", 0, 0, 0)  # medals, AI, fleet
    return bytes(payload)


def _character_not_found_payload() -> bytes:
    """Build IPL_Character::tConnectPlayerReq::tRep for a new account."""
    return (
        b"\x01"
        + _default_client_character_payload(include_ship=False)
        + struct.pack("<I", 1)
    )


def _parse_create_client_character(
    payload: bytes,
) -> tuple[tuple[int, int, int], str, str, int, str, str, int]:
    """Parse IPL_Character::tCreateClientCharacterReq (handler channel 6)."""
    if len(payload) < 12:
        raise ValueError("truncated create-client-character request")
    return_address = struct.unpack_from("<III", payload, 0)
    first, offset = _unpack_string(payload, 12)
    account, offset = _unpack_string(payload, offset)
    if offset + 4 > len(payload):
        raise ValueError("truncated create-client-character race")
    race = struct.unpack_from("<I", payload, offset)[0]
    character_name, offset = _unpack_string(payload, offset + 4)
    client_address, offset = _unpack_string(payload, offset)
    if offset + 4 != len(payload):
        raise ValueError("unexpected create-client-character trailing data")
    language = struct.unpack_from("<I", payload, offset)[0]
    return return_address, first, account, race, character_name, client_address, language


def _character_created_payload(
    account: str, character_name: str, client_address: str, race: int
) -> bytes:
    """Build a minimal successful tCreateClientCharacterReq::tRep."""
    character = _default_client_character_payload(
        client_address=client_address,
        account=account,
        character_name=character_name,
        race=race,
        database_id=1,
        rank=0,
    )
    return b"\x01" + character + struct.pack("<I", 0)


def _parse_relay_publication(payload: bytes) -> tuple[bytes, tuple[int, int]]:
    """Parse a client unique-name publication and its local callback address."""
    if len(payload) < 12:
        raise ValueError("truncated relay publication")
    name_length = struct.unpack_from("<I", payload, 0)[0]
    if 4 + name_length + 8 != len(payload):
        raise ValueError("invalid relay publication length")
    name = payload[4 : 4 + name_length]
    address = struct.unpack_from("<II", payload, 4 + name_length)
    return name, address


def _parse_relay_request(payload: bytes) -> tuple[tuple[int, int, int], bytes]:
    """Parse an interface request asking the server to claim a named relay."""
    if len(payload) < 17 or payload[0] != 1:
        raise ValueError("invalid relay request")
    return_address = struct.unpack_from("<III", payload, 1)
    name_length = struct.unpack_from("<I", payload, 13)[0]
    if 17 + name_length != len(payload):
        raise ValueError("invalid relay request name length")
    return return_address, payload[17:]


def _character_logon_payload(
    account: str, character_name: str, client_address: str, race: int,
    record: dict | None = None,
) -> bytes:
    """Build tCharacterRequest::tCharacterResponse for channel 2."""
    record = _normalize_character_record(record or {"race": race})
    return struct.pack("<I", 0) + _default_client_character_payload(
        client_address=client_address,
        account=account,
        character_name=character_name,
        race=race,
        database_id=1,
        rank=0,
        current_position=tuple(record["position"]),
        homeworld=tuple(record["homeworld"]),
        destination=tuple(record["destination"]),
        prestige=int(record["prestige"]),
        ship=record["ship"],
    )


def _load_characters() -> dict[str, dict]:
    if not CHARACTER_STORE_PATH.exists():
        return {}
    data = json.loads(CHARACTER_STORE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("character store must contain an object")
    return {account: _normalize_character_record(record) for account, record in data.items()}


def _normalize_character_record(record: dict) -> dict:
    """Add deterministic campaign defaults to old prototype character records."""
    normalized = dict(record)
    race = int(normalized.get("race", RACE_FEDERATION))
    class_name, ship_name, class_type = _starting_ship_for_race(race)
    if normalized.get("map_id") != CAMPAIGN_MAP_ID:
        # Coordinates from another map have no stable meaning on this topology.
        normalized["position"] = list(_campaign_start_for_race(race))
        normalized["homeworld"] = list(_campaign_homeworld_for_race(race))
        normalized["destination"] = [-1, -1]
        normalized["map_id"] = CAMPAIGN_MAP_ID
    else:
        normalized.setdefault("position", list(_campaign_start_for_race(race)))
        normalized.setdefault("homeworld", list(_campaign_homeworld_for_race(race)))
        normalized.setdefault("destination", [-1, -1])
    ship = dict(normalized.get("ship") or {})
    ship.setdefault("id", SHIP_DATABASE_ID)
    ship.setdefault("owner_id", int(normalized.get("database_id", CHARACTER_DATABASE_ID)))
    ship.setdefault("class_name", class_name)
    ship.setdefault("loadout_name", ship["class_name"])
    ship.setdefault("name", ship_name)
    ship.setdefault("class_type", class_type)
    ship.setdefault("bpv", 250)
    ship.setdefault("damage", 1.0)
    ship.setdefault("flags", 0)
    ship.setdefault("turn_created", 0)
    # Migrate the prototype's split mutable fields into the ship they describe.
    ship.setdefault("stores", dict(normalized.pop("stores", {}) or {}))
    ship.setdefault("refit", dict(normalized.pop("refit", {}) or {}))
    ship.setdefault("officers", list(normalized.pop("officers", []) or []))
    normalized["ship"] = ship
    if "prestige" not in normalized:
        normalized["prestige"] = _starting_prestige()
    normalized.setdefault("missions", [])
    return normalized


def _starting_prestige(difficulty: int = 0) -> int:
    """Load the server-kit starting balance; difficulty zero is the retail default."""
    try:
        source = find_structured_asset(
            "ServerProfiles/Character.gf",
            server_asset_root=SERVER_ASSET_ROOT,
            retail_asset_root=ASSET_ROOT,
        )
    except FileNotFoundError:
        return 200
    values = parse_gf(source.path).get(f"Create/{difficulty}", {})
    return max(0, int(values.get("StartingPrestige", 200)))


def _save_character(
    account: str, character_name: str, client_address: str, race: int,
    verification_id: str = "",
) -> dict:
    characters = _load_characters()
    record = _new_character_record(
        character_name, client_address, race, verification_id
    )
    if PERSISTENCE is not None:
        ids = database.bootstrap_character(
            PERSISTENCE, account_name=account, record=record
        )
        record["database_id"] = ids["character_id"]
        record["ship"]["id"] = ids["ship_id"]
        record["ship"]["owner_id"] = ids["character_id"]
        for officer, officer_id in zip(record["ship"]["officers"], ids["officer_ids"]):
            officer["id"] = officer_id
    characters[account] = record
    CHARACTER_STORE_PATH.write_text(
        json.dumps(characters, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return record


def _new_character_record(
    character_name: str, client_address: str, race: int, verification_id: str = ""
) -> dict:
    """Instantiate all mutable state defined by the campaign starter templates."""
    defaults = _starter_ship_defaults(race)
    class_name, ship_name, class_type = _starting_ship_for_race(race)
    names = _officer_names(race)
    first_name = min(_officer_review_limit(), max(0, len(names) - 6))
    crew_names = names[first_name:first_name + 6]
    if len(crew_names) != 6:
        raise ValueError(f"race {race} does not define six starting officer names")
    officers = [
        {
            "id": 10_000 + race * 100 + index,
            "name": name,
            "station": station,
            "race": race,
            "worth": 114,
        }
        for index, (name, station) in enumerate(zip(crew_names, OFFICER_STATIONS))
    ]
    officer_names_by_station = {
        OFFICER_STATION_NAMES[int(item["station"])]: str(item["name"])
        for item in officers
    }
    items = []
    for item in defaults["items"]:
        fields = item.split(":")
        if len(fields) >= 3 and fields[0] == "OFFICER" and fields[1] in officer_names_by_station:
            item = _officer_loadout_item(officer_names_by_station[fields[1]],
                                         OFFICER_STATIONS[list(OFFICER_STATION_NAMES.values()).index(fields[1])])
        items.append(item)
    position = list(_campaign_start_for_race(race))
    record = {
        "database_id": CHARACTER_DATABASE_ID,
        "character_name": character_name,
        "client_address": client_address,
        "race": race,
        "map_id": CAMPAIGN_MAP_ID,
        "position": position,
        "homeworld": list(_campaign_homeworld_for_race(race)),
        "destination": [-1, -1],
        "prestige": _starting_prestige(),
        "missions": [],
        "ship": {
            "id": SHIP_DATABASE_ID,
            "owner_id": CHARACTER_DATABASE_ID,
            "class_name": class_name,
            "loadout_name": defaults["sub_name"],
            "name": ship_name,
            "class_type": class_type,
            "bpv": int(defaults["hull_cost"]),
            "damage": 1.0,
            "flags": 0,
            "turn_created": _campaign_turn(),
            "stores": {
                name: int(defaults[name][2]) for name in ("shuttles", "marines", "mines")
            },
            "refit": {"loadout_name": defaults["sub_name"], "items": items},
            "officers": officers,
        },
    }
    if verification_id:
        record["verification_id"] = verification_id
    return _normalize_character_record(record)


def _write_character_record(account: str, record: dict) -> dict:
    characters = _load_characters()
    normalized = _normalize_character_record(record)
    characters[account] = normalized
    CHARACTER_STORE_PATH.write_text(
        json.dumps(characters, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return normalized


def _update_character(account: str, mutate) -> dict:
    """Apply one validated campaign mutation and persist the normalized result."""
    characters = _load_characters()
    if account not in characters:
        raise ValueError("unknown character account")
    record = _normalize_character_record(characters[account])
    mutate(record)
    return _write_character_record(account, record)


def _purchase_officers(
    account: str,
    assignments: dict[int, int],
    *,
    incoming_cost: int = 14,
    default_outgoing_worth: int = 114,
) -> dict:
    """Atomically exchange officers and persist the resulting ship roster."""
    if incoming_cost < 0 or default_outgoing_worth < 0:
        raise ValueError("officer costs cannot be negative")
    if not assignments:
        raise ValueError("officer assignment is empty")

    def mutate(record: dict) -> None:
        race = int(record["race"])
        names = _officer_names(race)[:_officer_review_limit()]
        defaults = _character_ship_defaults(record)
        items = list(defaults["items"])
        ship = record["ship"]
        existing_by_station = {int(item["station"]): item for item in ship["officers"]}
        prepared = []
        seen_ids = set()
        outgoing_credit = 0
        for officer_id, assigned_station in assignments.items():
            officer_id = int(officer_id)
            assigned_station = int(assigned_station)
            index = officer_id - 1000
            if not 0 <= index < len(names):
                raise ValueError("officer is not in review")
            if officer_id in seen_ids or any(
                int(item["id"]) == officer_id for item in ship["officers"]
            ):
                raise ValueError("officer is already assigned")
            if assigned_station not in OFFICER_STATIONS:
                raise ValueError("invalid officer station")
            station_name = OFFICER_STATION_NAMES[assigned_station]
            prefix = f"OFFICER:{station_name}:"
            replacement_index = next(
                (item_index for item_index, item in enumerate(items) if item.startswith(prefix)), None
            )
            if replacement_index is None:
                raise ValueError("ship has no officer slot for station")
            fields = items[replacement_index].split(":")
            # Stock player loadouts intentionally use empty three-field slots,
            # e.g. OFFICER:ENGINEER:. Populated officers carry the longer
            # profile tail, but replacing the name only requires field 2.
            if len(fields) < 3:
                raise ValueError("invalid officer loadout item")
            outgoing = existing_by_station.get(assigned_station)
            outgoing_credit += int(outgoing.get("worth", default_outgoing_worth)) if outgoing else default_outgoing_worth
            prepared.append((officer_id, assigned_station, names[index], replacement_index, fields))
            seen_ids.add(officer_id)

        new_prestige = int(record["prestige"]) + outgoing_credit - incoming_cost * len(prepared)
        if new_prestige < 0:
            raise ValueError("insufficient prestige")
        replaced_stations = {item[1] for item in prepared}
        record["prestige"] = new_prestige
        ship["officers"] = [
            item for item in ship["officers"]
            if int(item.get("station", -1)) not in replaced_stations
        ]
        for officer_id, assigned_station, name, replacement_index, fields in prepared:
            items[replacement_index] = _officer_loadout_item(name, assigned_station)
            ship["officers"].append({
                "id": officer_id, "name": name, "station": assigned_station,
                "worth": incoming_cost,
            })
        ship["refit"] = {
            "loadout_name": defaults["sub_name"],
            "items": items,
        }
    return _update_character(account, mutate)


def _purchase_officer(account: str, officer_id: int, *, station: int | None = None, cost: int = 14) -> dict:
    """Compatibility wrapper for a single officer exchange."""
    index = officer_id - 1000
    assigned_station = int(
        station if station is not None else OFFICER_STATIONS[index % len(OFFICER_STATIONS)]
    )
    return _purchase_officers(account, {officer_id: assigned_station}, incoming_cost=cost)


def _purchase_supplies(account: str, *, shuttles: int = 0, marines: int = 0, mines: int = 0) -> dict:
    """Persist Supply Dock quantities and deduct the server-kit unit prices."""
    requested = {"shuttles": shuttles, "marines": marines, "mines": mines}
    if any(not isinstance(value, int) or value < 0 for value in requested.values()):
        raise ValueError("supply quantities must be non-negative integers")
    def mutate(record: dict) -> None:
        defaults = _character_ship_defaults(record)
        maxima = {"shuttles": defaults["shuttles"][2], "marines": defaults["marines"][2], "mines": defaults["mines"][2]}
        costs = {"shuttles": 4, "marines": 4, "mines": 4}
        total = sum(requested[name] * costs[name] for name in requested)
        if int(record["prestige"]) < total:
            raise ValueError("insufficient prestige")
        stores = record["ship"].setdefault("stores", {})
        for name, amount in requested.items():
            current = int(stores.get(name, defaults[name][0]))
            if current + amount > maxima[name]:
                raise ValueError(f"{name} exceeds ship capacity")
        record["prestige"] -= total
        for name, amount in requested.items():
            stores[name] = int(stores.get(name, defaults[name][0])) + amount
    return _update_character(account, mutate)


def _update_supplies(account: str, desired: dict[str, int]) -> dict:
    """Apply absolute Supply Dock counts, charging buys and crediting sales."""
    if set(desired) != {"shuttles", "marines", "mines"}:
        raise ValueError("incomplete supply state")
    if any(not isinstance(value, int) or value < 0 for value in desired.values()):
        raise ValueError("invalid supply count")
    buy_rates = {"shuttles": 1, "marines": 2, "mines": 4}
    sell_factor = 0.5

    def mutate(record: dict) -> None:
        defaults = _character_ship_defaults(record)
        current = {
            name: int(record["ship"].setdefault("stores", {}).get(name, defaults[name][2]))
            for name in desired
        }
        for name, count in desired.items():
            if count > int(defaults[name][1]) + 1:
                raise ValueError(f"{name} exceeds ship capacity")
        buys = sum(max(0, desired[name] - current[name]) * buy_rates[name] for name in desired)
        sales = sum(
            max(0, current[name] - desired[name])
            * max(1, int(buy_rates[name] * sell_factor))
            for name in desired
        )
        if int(record["prestige"]) + sales < buys:
            raise ValueError("insufficient prestige")
        record["prestige"] = int(record["prestige"]) - buys + sales
        record["ship"]["stores"].update(desired)

    return _update_character(account, mutate)


def _save_refit(account: str, loadout_name: str, items: list[str], *, cost: int = 0) -> dict:
    """Persist a client-selected retail loadout after resolving it from stock specs."""
    if cost < 0 or not loadout_name or any(not isinstance(item, str) for item in items):
        raise ValueError("invalid refit")
    def mutate(record: dict) -> None:
        if int(record["prestige"]) < cost:
            raise ValueError("insufficient prestige")
        root = ASSET_ROOT
        if root is None:
            raise RuntimeError("server-kit asset root is required")
        specs = root / "Specs"
        if not specs.is_dir():
            specs = root / "Spec"
        defaults = _load_ship_defaults(specs / "DefaultCore.txt", specs / "DefaultLoadOut.txt", loadout_name)
        current_defaults = _character_ship_defaults(record, root)
        if defaults["ui_name"] != current_defaults["ui_name"]:
            raise ValueError("refit cannot change hull class")
        record["prestige"] -= cost
        record["ship"]["class_name"] = defaults["ui_name"]
        record["ship"]["loadout_name"] = defaults["sub_name"]
        record["ship"]["class_type"] = _ship_class_id(defaults["class_code"])
        record["ship"]["refit"] = {"loadout_name": defaults["sub_name"], "items": list(items)}
    return _update_character(account, mutate)


def _publish_news(text: str, *, channel: str = "system", priority: str = "med", turn: int | None = None) -> dict:
    """Retain a bounded, persistent campaign news feed using News.gf's limit."""
    if not text or len(text) > 2048:
        raise ValueError("invalid news text")
    source = find_structured_asset("ServerProfiles/News.gf", server_asset_root=SERVER_ASSET_ROOT, retail_asset_root=ASSET_ROOT)
    limit = max(1, int(parse_gf(source.path).get("General", {}).get("MaximumItemsAtOnce", 30)))
    state = _load_campaign_clock()
    items = state.setdefault("news", [])
    item = {
        "id": int(state.get("next_news_id", 1)),
        "turn": _campaign_turn() if turn is None else int(turn),
        "timestamp": int(time.time()),
        "channel": channel,
        "priority": priority,
        "text": text,
    }
    state["next_news_id"] = item["id"] + 1
    items.append(item)
    del items[:-limit]
    _write_campaign_state(state)
    return item


def _parse_news_request(payload: bytes) -> tuple[tuple[int, int, int], int]:
    """Parse News relay channel 2 (request-with-response plus character ID)."""
    if len(payload) != 17 or payload[0] != 1:
        raise ValueError("invalid news request")
    return _parse_async_return(payload), struct.unpack_from("<I", payload, 13)[0]


NEWS_CATEGORIES = {"system": 0, "empire": 1, "player": 2, "playerspecific": 2}
NEWS_PRIORITIES = {"ultra": 0, "top": 1, "high": 2, "med": 3, "low": 4, "verylow": 5}


def _news_color(channel: str, priority: str) -> int:
    source = find_structured_asset(
        "ServerProfiles/News.gf",
        server_asset_root=SERVER_ASSET_ROOT,
        retail_asset_root=ASSET_ROOT,
    )
    channel_name = {"system": "System", "empire": "Empire", "player": "PlayerSpecific", "playerspecific": "PlayerSpecific"}.get(channel.casefold(), "System")
    priority_name = {"ultra": "Ultra", "top": "Top", "high": "High", "med": "Med", "low": "Low", "verylow": "VeryLow"}.get(priority.casefold(), "Med")
    values = parse_gf(source.path).get(f"Channel/Color/{channel_name}/{priority_name}", {})
    components = [max(0, min(255, round(float(values.get(name, 0.75)) * 255))) for name in ("Red", "Green", "Blue")]
    return components[0] | components[1] << 8 | components[2] << 16


def _news_story_payload(item: dict) -> bytes:
    """Serialize tNewsStory in recovered field order."""
    timestamp = int(item.get("timestamp", item.get("turn", 0)))
    sequence = int(item.get("sequence", item["id"]))
    channel = str(item.get("channel", "system")).casefold()
    priority = str(item.get("priority", "med")).casefold()
    return (
        struct.pack("<II", int(item["id"]), 0)
        + bytes((int(item.get("persistence", 3)), NEWS_PRIORITIES.get(priority, 3), NEWS_CATEGORIES.get(channel, 0)))
        + _pack_str_vector((str(item["text"]),))
        + struct.pack("<iiI", timestamp, sequence, _news_color(channel, priority))
    )


def _news_response_payload(item: dict | None = None) -> bytes:
    """Serialize one live-compatible tGetNewsResponse story."""
    if item is None:
        return struct.pack("<I", 0)
    return struct.pack("<I", 1) + _news_story_payload(item)


def _welcome_news_story(story_id: int) -> dict:
    return {
        "id": max(1, int(story_id)),
        "text": "Welcome to the SFC3 Dynaverse campaign server.",
        "channel": "system",
        "priority": "med",
        "persistence": 3,
        "turn": _campaign_turn(),
        "sequence": 1,
    }


def _offer_mission(account: str, title: str, *, mission_type: str = "patrol", reward: int = 10) -> dict:
    """Create the first persistent mission lifecycle independently of wire routing."""
    if not title or reward < 0:
        raise ValueError("invalid mission")
    state = _load_campaign_clock()
    mission = {"id": int(state.get("next_mission_id", 1)), "account": account, "title": title, "type": mission_type, "reward": reward, "status": "offered", "turn": _campaign_turn()}
    state["next_mission_id"] = mission["id"] + 1
    state.setdefault("missions", []).append(mission)
    _write_campaign_state(state)
    return mission


def _parse_mission_match_request(payload: bytes) -> tuple[tuple[int, int, int], int, int]:
    """Parse MissionMatcher channel 10: callback, character ID, match mode."""
    if len(payload) != 21 or payload[0] != 1:
        raise ValueError("invalid mission-match request")
    return _parse_async_return(payload), *struct.unpack_from("<II", payload, 13)


def _parse_verify_mission_request(payload: bytes) -> tuple[tuple[int, int, int], int]:
    """Parse MissionMatcher channel 11: callback and character ID."""
    if len(payload) != 17 or payload[0] != 1:
        raise ValueError("invalid verify-mission request")
    return _parse_async_return(payload), struct.unpack_from("<I", payload, 13)[0]


def _parse_battle_item(payload: bytes, offset: int) -> tuple[dict, int]:
    """Parse tBattleItem using the recovered retail StreamIn field order."""
    if offset + 4 > len(payload):
        raise ValueError("truncated battle state")
    state = struct.unpack_from("<I", payload, offset)[0]
    offset += 4
    if offset + 4 > len(payload):
        raise ValueError("truncated hail idiom")
    text_count = struct.unpack_from("<I", payload, offset)[0]
    offset += 4
    texts = []
    for _ in range(text_count):
        value, offset = _unpack_string(payload, offset)
        texts.append(value)
    # tHail: tIdiom, tID, unsigned long, bool.
    if offset + 9 > len(payload):
        raise ValueError("truncated hail")
    hail_id, hail_type = struct.unpack_from("<II", payload, offset)
    hail_human = payload[offset + 8] != 0
    offset += 9
    # Remaining tBattleItem fields: six unsigned longs, double, bool.
    if offset + 33 > len(payload):
        raise ValueError("truncated battle item")
    fields = struct.unpack_from("<IIIIII", payload, offset)
    offset += 24
    rating = struct.unpack_from("<d", payload, offset)[0]
    offset += 8
    enabled = payload[offset] != 0
    offset += 1
    return {
        "state": state,
        "hail": {"texts": texts, "id": hail_id, "type": hail_type, "human": hail_human},
        "fields": fields,
        "rating": rating,
        "enabled": enabled,
    }, offset


def _parse_choose_mission_request(payload: bytes) -> tuple[tuple[int, int, int], int, dict]:
    """Parse MissionMatcher channel 12: callback, character ID, tBattleItem."""
    if len(payload) < 17 or payload[0] != 1:
        raise ValueError("invalid choose-mission request")
    character_id = struct.unpack_from("<I", payload, 13)[0]
    battle, offset = _parse_battle_item(payload, 17)
    if offset != len(payload):
        raise ValueError("trailing choose-mission data")
    return _parse_async_return(payload), character_id, battle


def _set_mission_status(account: str, mission_id: int, status: str) -> dict:
    allowed = {"accepted", "launched", "completed", "declined"}
    if status not in allowed:
        raise ValueError("invalid mission status")
    state = _load_campaign_clock()
    mission = next((item for item in state.setdefault("missions", []) if int(item["id"]) == mission_id and item["account"] == account), None)
    if mission is None:
        raise ValueError("unknown mission")
    transitions = {"offered": {"accepted", "declined"}, "accepted": {"launched"}, "launched": {"completed"}}
    if status not in transitions.get(mission["status"], set()):
        raise ValueError("invalid mission transition")
    mission["status"] = status
    if status == "completed":
        _update_character(account, lambda record: record.__setitem__("prestige", int(record["prestige"]) + int(mission["reward"])))
    _write_campaign_state(state)
    return dict(mission)


def _verification_policy() -> str:
    policy = os.environ.get("SFC3_CDKEY_POLICY", "permissive").strip().casefold()
    if policy not in {"permissive", "registered", "strict"}:
        raise ValueError("SFC3_CDKEY_POLICY must be permissive, registered, or strict")
    return policy


def _verification_identifier(private_identity: bytes) -> str:
    """Return a non-reversible operator-local identity; never persist its source bytes."""
    secret = os.environ.get("SFC3_IDENTITY_HMAC_SECRET", "")
    if not secret:
        raise RuntimeError("SFC3_IDENTITY_HMAC_SECRET is required outside permissive mode")
    return hmac.new(secret.encode("utf-8"), private_identity, hashlib.sha256).hexdigest()


def _verification_identity_bytes(request: bytes) -> bytes:
    """Select the stable access package, excluding per-session challenges."""
    offset_text = os.environ.get("SFC3_CDKEY_ID_OFFSET", "")
    length_text = os.environ.get("SFC3_CDKEY_ID_LENGTH", "")
    if offset_text and length_text:
        offset, length = int(offset_text), int(length_text)
        if offset < 13 or length <= 0 or offset + length > len(request):
            raise ValueError("configured CD-key identity field is outside the verification request")
        return request[offset : offset + length]
    try:
        parsed = _parse_verification_request(request)
    except ValueError:
        if _verification_policy() == "permissive":
            return request[13:]
        raise
    return (
        parsed["access_name"].encode("ascii")
        + bytes((parsed["access_success"], parsed["access_flag"]))
        + parsed["access_blob"]
    )


def _skip_client_character(payload: bytes, offset: int) -> int:
    """Skip the tClientCharacter embedded in a verification request."""
    _value, offset = _unpack_string(payload, offset)  # client address
    _value, offset = _unpack_string(payload, offset)  # account
    if offset + 4 > len(payload):
        raise ValueError("truncated verification character ID")
    offset += 4
    _value, offset = _unpack_string(payload, offset)  # character name
    offset += 8 * 4 + 6 * 4
    if offset + 4 > len(payload):
        raise ValueError("truncated verification ship-cache count")
    ship_count = struct.unpack_from("<I", payload, offset)[0]
    offset += 4
    for _ in range(ship_count):
        offset += 3 * 4
        _value, offset = _unpack_string(payload, offset)
        offset += 4
        _value, offset = _unpack_string(payload, offset)
        offset += 4
    # tMetaMapHex plus vector<medal>, AI flag, fleet flag.
    offset += 62
    if offset + 4 > len(payload):
        raise ValueError("truncated verification medal count")
    medal_count = struct.unpack_from("<I", payload, offset)[0]
    offset += 4 + medal_count * 4 + 2
    if offset > len(payload):
        raise ValueError("truncated verification character")
    return offset


def _parse_verification_request(request: bytes) -> dict:
    """Parse tVerifyClientRequest using the recovered StreamOut member order."""
    if len(request) < 17 or request[0] != 1:
        raise ValueError("invalid verification request")
    callback = _parse_async_return(request)
    offset = 13
    manifest_count = struct.unpack_from("<I", request, offset)[0]
    offset += 4
    for _ in range(manifest_count):
        _path, offset = _unpack_string(request, offset)
        if offset + 4 > len(request):
            raise ValueError("truncated verification checksum vector")
        checksum_count = struct.unpack_from("<I", request, offset)[0]
        offset += 4 + checksum_count * 4
        if offset > len(request):
            raise ValueError("truncated verification checksums")
    challenge_reply, offset = _unpack_string(request, offset)
    offset = _skip_client_character(request, offset)
    challenge, offset = _unpack_string(request, offset)
    access_name, offset = _unpack_string(request, offset)
    if offset + 6 > len(request):
        raise ValueError("truncated access package")
    access_success, access_flag = request[offset], request[offset + 1]
    blob_length = struct.unpack_from("<I", request, offset + 2)[0]
    offset += 6
    if offset + blob_length != len(request):
        raise ValueError("invalid access-package blob length")
    return {
        "callback": callback,
        "manifest_count": manifest_count,
        "challenge_reply": challenge_reply,
        "challenge": challenge,
        "access_name": access_name,
        "access_success": access_success,
        "access_flag": access_flag,
        "access_blob": request[offset:],
    }


def _verification_allowed(private_identity: bytes) -> bool:
    policy = _verification_policy()
    if policy == "permissive":
        return bool(private_identity)
    identifier = _verification_identifier(private_identity)
    registered = {value.strip().casefold() for value in os.environ.get("SFC3_REGISTERED_KEY_IDS", "").split(",") if value.strip()}
    if policy == "registered":
        return bool(identifier)
    return identifier in registered


def _parse_move_request(payload: bytes) -> tuple[tuple[int, int, int], int, tuple[int, int]]:
    """Parse IPL_Map::tMoveRequestReq (channel 41)."""
    if len(payload) != 24:
        raise ValueError("invalid move-request length")
    callback = struct.unpack_from("<III", payload, 0)
    character_id, x, y = struct.unpack_from("<Iii", payload, 12)
    return callback, character_id, (x, y)


def _is_adjacent_hex(current: tuple[int, int], destination: tuple[int, int]) -> bool:
    dx = destination[0] - current[0]
    dy = destination[1] - current[1]
    # Multi.mvm uses odd-column offset coordinates. The diagonal Y offsets
    # alternate by column; treating them as axial coordinates rejects every
    # other visually adjacent diagonal move.
    diagonals = {(1, 0), (1, 1), (-1, 0), (-1, 1)} if current[0] & 1 else {
        (1, -1), (1, 0), (-1, -1), (-1, 0)
    }
    return (dx, dy) in diagonals | {(0, -1), (0, 1)}


def _hex_distance(current: tuple[int, int], destination: tuple[int, int]) -> int:
    """Return distance between odd-column offset coordinates from Multi.mvm."""
    def cube(position: tuple[int, int]) -> tuple[int, int, int]:
        column, row = position
        x = column
        z = row - (column - (column & 1)) // 2
        return x, -x - z, z

    start = cube(current)
    end = cube(destination)
    return max(abs(end[index] - start[index]) for index in range(3))


def _move_response_payload(accepted: bool, duration_seconds: int = 1) -> bytes:
    """Build tMoveRequestReq::tRep with duration (seconds) and result code."""
    return b"\x01" + struct.pack(
        "<II", duration_seconds if accepted else 0, 1 if accepted else 0
    )


def _meta_map_move_payload(
    character_id: int,
    destination: tuple[int, int],
    duration_seconds: int,
    movement_state: int,
    at_friendly_base_or_planet: bool = False,
) -> bytes:
    """Build the viewport channel-4 tMetaMapMoveResponse body."""
    return (
        struct.pack(
            "<IIiiI",
            movement_state,
            character_id,
            destination[0],
            destination[1],
            duration_seconds,
        )
        + _pack_str("")
        + bytes((at_friendly_base_or_planet,))
    )


def _pack_u32_vector(values) -> bytes:
    """Serialize the VC6 nDataStore representation of vector<unsigned long>."""
    values = tuple(values)
    return struct.pack("<I", len(values)) + b"".join(
        struct.pack("<I", value) for value in values
    )


def _pack_str_vector(values) -> bytes:
    values = tuple(values)
    return struct.pack("<I", len(values)) + b"".join(_pack_str(value) for value in values)


def _damage_state_payload(
    system_current=(),
    system_maximum=(),
    hardpoint_current=(),
    hardpoint_maximum=(),
    initialized: bool = True,
) -> bytes:
    """Serialize tDamageState without copying state from a captured character."""
    current_systems = tuple(system_current) or (-1,) * 23
    maximum_systems = tuple(system_maximum) or (-1,) * 23
    current_hardpoints = tuple(hardpoint_current) or (-1,) * 25
    maximum_hardpoints = tuple(hardpoint_maximum) or (-1,) * 25
    if not (
        len(current_systems) == len(maximum_systems) == 23
        and len(current_hardpoints) == len(maximum_hardpoints) == 25
    ):
        raise ValueError("tDamageState requires 23 systems and 25 hardpoints")
    payload = bytearray((int(initialized),))
    for current, maximum in zip(current_systems, maximum_systems):
        payload += struct.pack("<ii", current, maximum)
    for current, maximum in zip(current_hardpoints, maximum_hardpoints):
        payload += struct.pack("<ii", current, maximum)
    return bytes(payload)


def _stores_state_payload(
    shuttle_counts=(2, 4, 2),
    transporter_ids=(),
    item_current=(),
    item_maximum=(),
    misc_maximum=(4, 4, 4),
    misc_current=(2, 2, 2),
    misc_desired=(2, 2, 2),
) -> bytes:
    """Serialize tStoresState using its recovered field-level StreamOut order."""
    if not all(len(values) == 3 for values in (
        shuttle_counts, misc_maximum, misc_current, misc_desired
    )):
        raise ValueError("store count groups require three values")
    current = tuple(item_current) or (-1,) * 25
    maximum = tuple(item_maximum) or (0,) * 25
    if len(current) != 25 or len(maximum) != 25:
        raise ValueError("tStoresState requires 25 item slots")
    payload = bytearray(bytes(shuttle_counts))
    payload += _pack_u32_vector(transporter_ids)
    for current_value, maximum_value in zip(current, maximum):
        payload += struct.pack("<hh", current_value, maximum_value)
    for index in range(3):
        payload += bytes((misc_maximum[index], misc_current[index], misc_desired[index]))
    return bytes(payload)


def _item_rates_payload(item_rate=1.0, misc_rates=(2.0, 4.0, 4.0)) -> bytes:
    """Serialize tStoresState::tItemRates."""
    if len(misc_rates) != 3:
        raise ValueError("item rates require three miscellaneous rates")
    return struct.pack("<dddd", item_rate, *misc_rates)


def _id_double_map_payload(values) -> bytes:
    """Serialize map<nDatabase::tID, double> in nDataStore order."""
    entries = tuple(values)
    return struct.pack("<I", len(entries)) + b"".join(
        struct.pack("<Id", database_id, value) for database_id, value in entries
    )


def _id_item_rates_map_payload(values) -> bytes:
    """Serialize map<nDatabase::tID, tStoresState::tItemRates>."""
    entries = tuple(values)
    return struct.pack("<I", len(entries)) + b"".join(
        struct.pack("<I", database_id) + _item_rates_payload(*rates)
        for database_id, rates in entries
    )


def _ship_core_payload(
    hardpoint_groups,
    primary_values,
    class_name: str,
    model_name: str,
    model_values,
    secondary_values,
    attributes=(),
) -> bytes:
    """Serialize tTNGShipCoreData in its recovered StreamOut order.

    The six hardpoint groups and numeric fields intentionally remain explicit: their
    meanings come from DefaultCore.txt, while this routine owns only wire encoding.
    """
    groups = tuple(tuple(group) for group in hardpoint_groups)
    primary = tuple(primary_values)
    model = tuple(model_values)
    secondary = tuple(secondary_values)
    if len(groups) != 6:
        raise ValueError("ship core requires six hardpoint vectors")
    if len(primary) != 8 or len(model) != 7 or len(secondary) != 4:
        raise ValueError("ship core numeric groups require 8, 7, and 4 values")
    return (
        b"".join(_pack_u32_vector(group) for group in groups)
        + struct.pack("<8I", *primary)
        + _pack_str(class_name)
        + _pack_str(model_name)
        + _pack_str_vector(attributes)
        + struct.pack("<7I", *model)
        + struct.pack("<4I", *secondary)
    )


def _tng_ship_payload(
    core_payload: bytes,
    loadout_fields,
    configuration_scalar: float = 1.0,
) -> bytes:
    """Serialize tTNGShip from generated core and DefaultLoadOut fields."""
    # Retail tTNGShip::StreamOut always terminates the tab-delimited loadout
    # with one final tab.  This is not cosmetic: the client feeds the string
    # back through its loadout parser, which expects the last item to be
    # delimited before the following binary configuration scalar.
    loadout = "\t".join(str(field) for field in loadout_fields) + "\t"
    return b"\x01\x01" + core_payload + _pack_str(loadout) + struct.pack(
        "<f", configuration_scalar
    )


def _spec_rows(path: Path):
    """Yield tab-separated SFC3 spec rows between [BEGIN] and [END]."""
    active = False
    with path.open("r", encoding="cp1252") as stream:
        for raw_line in stream:
            line = raw_line.rstrip("\r\n")
            if line.startswith("[BEGIN]"):
                active = True
                continue
            if line.startswith("[END]"):
                break
            if active and line.strip():
                yield line.rstrip("\t").split("\t")


def _parse_triplet(value: str, prefix: str) -> tuple[int, int, int]:
    fields = value.split(":")
    if len(fields) != 4 or fields[0] != prefix:
        raise ValueError(f"invalid {prefix} field: {value!r}")
    return tuple(int(field) for field in fields[1:])


def _parse_hardpoints(value: str, prefix: str) -> tuple[tuple[int, str], ...]:
    fields = value.split(":")
    if not fields or fields[0] != prefix or (len(fields) - 1) % 2:
        raise ValueError(f"invalid {prefix} field: {value!r}")
    return tuple(
        (int(fields[index]), fields[index + 1])
        for index in range(1, len(fields), 2)
    )


def _weapon_arc_id(value: str) -> int:
    """Convert a DefaultCore firing arc using the executable's WeaponArcs table."""
    try:
        return WEAPON_ARC_IDS[value.casefold()]
    except KeyError as exc:
        raise ValueError(f"unknown SFC3 weapon arc: {value!r}") from exc


def _core_hardpoint_vectors(defaults: dict) -> tuple[tuple[int, ...], ...]:
    primary = defaults["primary_hardpoints"]
    heavy = defaults["heavy_hardpoints"]
    return (
        tuple(hardpoint for hardpoint, _arc in primary),
        tuple(_weapon_arc_id(arc) for _hardpoint, arc in primary),
        tuple(hardpoint for hardpoint, _arc in heavy),
        tuple(_weapon_arc_id(arc) for _hardpoint, arc in heavy),
        tuple(defaults["hull_hardpoints"]),
        tuple(defaults["bridge_hardpoints"]),
    )


def _ship_class_id(value: str) -> int:
    try:
        return SHIP_CLASS_IDS[value.casefold()]
    except KeyError as exc:
        raise ValueError(f"unknown SFC3 ship class: {value!r}") from exc


def _default_ship_core_payload(defaults: dict) -> bytes:
    """Map a parsed DefaultCore row into the recovered field serialization order."""
    mines = defaults["mines"]
    marines = defaults["marines"]
    shuttles = defaults["shuttles"]
    primary_values = (
        defaults["power_space"],
        defaults["weapon_space"],
        defaults["hull_space"],
        defaults["size_class"],
        _ship_class_id(defaults["class_code"]),
        defaults["base_weight"],
        defaults["cargo_space"],
        defaults["hull_cost"],
    )
    model_values = (
        mines[1],
        mines[0],
        mines[2],
        marines[1],
        marines[0],
        marines[2],
        shuttles[1],
    )
    secondary_values = (
        shuttles[0],
        shuttles[2],
        defaults["shield_space"],
        defaults["ship_size"],
    )
    core = _ship_core_payload(
        _core_hardpoint_vectors(defaults),
        primary_values,
        defaults["class_name"],
        defaults["model_name"],
        model_values,
        secondary_values,
        defaults["attributes"],
    )
    return core


def _full_ship_payload(
    *,
    race: int,
    ship_name: str,
    defaults: dict,
    database_id: int = SHIP_DATABASE_ID,
    owner_id: int = CHARACTER_DATABASE_ID,
    epv: int = 250,
    turn_created: int = 0,
    stores: dict | None = None,
) -> bytes:
    """Serialize the complete top-level tShip in recovered StreamOut order."""
    core = _default_ship_core_payload(defaults)
    tng_ship = _tng_ship_payload(core, defaults["loadout_fields"])
    class_type = _ship_class_id(defaults["class_code"])
    database_object = struct.pack("<II", database_id, 0)
    ship_header = (
        struct.pack("<I", owner_id)
        + b"\x00"
        + struct.pack("<III", race, class_type, epv)
        # tShip::GetShipClassName is the player-facing hull/variant name from
        # DefaultLoadOut (for example "Norway" or "Sovereign"), not the
        # internal core key ("Fed-Destroyer" / "Fed-Dreadnaught2").  The
        # Vessel Library resolves this string locally.
        + _pack_str(defaults["ui_name"])
        + _pack_str(ship_name)
        + struct.pack("<I", turn_created)
    )
    return (
        database_object
        + ship_header
        + tng_ship
        + _damage_state_payload(
            system_current=(100,) * 23,
            system_maximum=(100,) * 23,
            hardpoint_current=(100,) * 25,
            hardpoint_maximum=(100,) * 25,
        )
        + _stores_state_payload(
            shuttle_counts=(
                int((stores or {}).get("shuttles", defaults["shuttles"][2])),
                defaults["shuttles"][1] + 1,
                int((stores or {}).get("shuttles", defaults["shuttles"][2])),
            ),
            misc_maximum=(defaults["marines"][1] + 1, defaults["mines"][1] + 1, 4),
            misc_current=(
                int((stores or {}).get("marines", defaults["marines"][2])),
                int((stores or {}).get("mines", defaults["mines"][2])),
                2,
            ),
            misc_desired=(
                int((stores or {}).get("marines", defaults["marines"][2])),
                int((stores or {}).get("mines", defaults["mines"][2])),
                2,
            ),
        )
        + struct.pack("<II", 0, defaults["hull_cost"])
    )


def _supply_dock_payload(race: int, asset_root: Path | None = None, *, record: dict | None = None) -> bytes:
    """Build tGetSupplyDockInfoReq::tRep from installed defaults, never capture data."""
    defaults = _character_ship_defaults(record, asset_root) if record else _starter_ship_defaults(race, asset_root)
    _class_name, starter_name, _class_type = _starting_ship_for_race(race)
    ship_name = str(record["ship"].get("name", starter_name)) if record else starter_name
    ship = _full_ship_payload(
        race=race,
        ship_name=ship_name,
        defaults=defaults,
        stores=(record or {}).get("ship", {}).get("stores"),
        database_id=int((record or {}).get("ship", {}).get("id", SHIP_DATABASE_ID)),
        owner_id=int((record or {}).get("ship", {}).get("owner_id", CHARACTER_DATABASE_ID)),
        epv=int((record or {}).get("ship", {}).get("bpv", 250)),
        turn_created=int((record or {}).get("ship", {}).get("turn_created", 0)),
    )
    return (
        b"\x01"
        + ship
        + _id_double_map_payload(((SHIP_DATABASE_ID, 1.0),))
        + _id_double_map_payload(((SHIP_DATABASE_ID, 0.5),))
        + _id_item_rates_map_payload(((SHIP_DATABASE_ID, (1.0, (2.0, 4.0, 4.0))),))
    )


def _parse_update_stores_request(payload: bytes) -> tuple[tuple[int, int, int], int, str, dict]:
    """Parse Ship channel 13: callback, character ID, ship name, and tStoresState."""
    if len(payload) < 20:
        raise ValueError("truncated update-stores request")
    callback = _parse_callback(payload)
    character_id = struct.unpack_from("<I", payload, 12)[0]
    ship_name, offset = _unpack_string(payload, 16)
    if offset + 7 > len(payload):
        raise ValueError("truncated stores state")
    shuttles = tuple(payload[offset : offset + 3])
    transporter_count = struct.unpack_from("<I", payload, offset + 3)[0]
    items_offset = offset + 7 + transporter_count * 4
    tail = items_offset + 25 * 4
    if tail + 9 != len(payload):
        raise ValueError("invalid stores-state length")
    item_pairs = tuple(
        struct.unpack_from("<hh", payload, items_offset + index * 4)
        for index in range(25)
    )
    final = payload[tail : tail + 9]
    return callback, character_id, ship_name, {
        "shuttles": shuttles,
        "items": item_pairs,
        "misc_maximum": (final[0], final[3], final[6]),
        "misc_current": (final[1], final[4], final[7]),
        "misc_desired": (final[2], final[5], final[8]),
    }


def _updated_ship_payload(record: dict) -> bytes:
    defaults = _character_ship_defaults(record)
    ship = record["ship"]
    return _full_ship_payload(
        race=int(record["race"]),
        ship_name=str(ship["name"]),
        defaults=defaults,
        stores=ship.get("stores"),
        database_id=int(ship["id"]),
        owner_id=int(ship.get("owner_id", CHARACTER_DATABASE_ID)),
        epv=int(ship.get("bpv", 250)),
        turn_created=int(ship.get("turn_created", 0)),
    )


def _parse_character_ship_config_request(
    payload: bytes,
) -> tuple[tuple[int, int, int], int, bool]:
    """Parse IPL_Character::tGetCharacterShipConfigReq (channel 20)."""
    if len(payload) != 17:
        raise ValueError("invalid character ship-config request length")
    return _parse_callback(payload), struct.unpack_from("<I", payload, 12)[0], bool(payload[16])


def _character_prestige_payload(record: dict | None) -> bytes:
    """Build tGetCharacterPrestigeReq::tRep(current, lifetime, success)."""
    if record is None:
        return struct.pack("<BII", 0, 0, 0)
    return struct.pack(
        "<BII",
        1,
        int(record.get("prestige", 0)),
        int(record.get("lifetime_prestige", 0)),
    )


def _character_ship_config_payload(
    race: int,
    asset_root: Path | None = None,
    *,
    ship_id: int = SHIP_DATABASE_ID,
    economic_scalar: float = 1.0,
    prestige: int = 0,
    record: dict | None = None,
) -> bytes:
    """Build tGetCharacterShipConfigReq::tRep from installed starter defaults."""
    defaults = _character_ship_defaults(record, asset_root) if record else _starter_ship_defaults(race, asset_root)
    tng_ship = _tng_ship_payload(
        _default_ship_core_payload(defaults), defaults["loadout_fields"]
    )
    return (
        b"\x01"
        + struct.pack("<I", ship_id)
        + tng_ship
        + struct.pack("<If", prestige, economic_scalar)
    )


def _parse_tng_ship(payload: bytes, offset: int = 0) -> tuple[dict, int]:
    """Parse the recovered tTNGShip envelope sufficiently to validate a refit."""
    if offset + 2 > len(payload) or payload[offset : offset + 2] != b"\x01\x01":
        raise ValueError("invalid tTNGShip initialization markers")
    cursor = offset + 2
    for _ in range(6):
        if cursor + 4 > len(payload):
            raise ValueError("truncated tTNGShip hardpoint vector")
        count = struct.unpack_from("<I", payload, cursor)[0]
        cursor += 4 + count * 4
        if cursor > len(payload):
            raise ValueError("truncated tTNGShip hardpoint data")
    cursor += 8 * 4
    class_name, cursor = _unpack_string(payload, cursor)
    model_name, cursor = _unpack_string(payload, cursor)
    if cursor + 4 > len(payload):
        raise ValueError("truncated tTNGShip attributes")
    attribute_count = struct.unpack_from("<I", payload, cursor)[0]
    cursor += 4
    attributes = []
    for _ in range(attribute_count):
        value, cursor = _unpack_string(payload, cursor)
        attributes.append(value)
    cursor += (7 + 4) * 4
    loadout, cursor = _unpack_string(payload, cursor)
    if cursor + 4 > len(payload):
        raise ValueError("truncated tTNGShip revision")
    configuration_scalar = struct.unpack_from("<f", payload, cursor)[0]
    return {
        "class_name": class_name,
        "model_name": model_name,
        "attributes": tuple(attributes),
        "loadout_fields": tuple(loadout.split("\t")),
        "configuration_scalar": configuration_scalar,
    }, cursor + 4


def _parse_purchase_config_request(payload: bytes) -> tuple[tuple[int, int, int], int, int, dict]:
    """Parse Character relay channel 38: character, ship, and replacement tTNGShip."""
    # Unlike several other Character mutations this request uses a plain
    # 12-byte callback envelope; the tTNGShip's own two initialization bytes
    # immediately follow the character and ship IDs.  This layout is confirmed
    # by the retail server's channel-38 request.
    if len(payload) < 22:
        raise ValueError("truncated purchase-config request")
    callback = _parse_callback(payload)
    character_id, ship_id = struct.unpack_from("<II", payload, 12)
    config, end = _parse_tng_ship(payload, 20)
    if end != len(payload):
        raise ValueError("unexpected purchase-config trailing data")
    return callback, character_id, ship_id, config


def _parse_officers_to_review_request(
    payload: bytes,
) -> tuple[tuple[int, int, int], int]:
    """Parse IPL_Character::tGetOfficersToReviewReq (channel 27)."""
    if len(payload) != 16:
        raise ValueError("invalid officers-to-review request length")
    return _parse_callback(payload), struct.unpack_from("<I", payload, 12)[0]


def _parse_free_officers_request(
    payload: bytes,
) -> tuple[tuple[int, int, int], int]:
    """Parse Character channel 8 (FreeOfficersInReview)."""
    if len(payload) != 16:
        raise ValueError("invalid free-officers request length")
    return _parse_callback(payload), struct.unpack_from("<I", payload, 12)[0]


def _parse_purchase_officers_request(
    payload: bytes,
) -> tuple[tuple[int, int, int], int, dict[int, int]]:
    """Parse channel 39: callback, character ID, map<officer ID, station>."""
    # Retail uses the same plain 12-byte callback envelope as channel 38;
    # there is no leading asynchronous-return marker. A one-officer transfer
    # is therefore exactly 28 bytes: callback (12), character/count (8), and
    # one officer/station map entry (8).
    if len(payload) < 20:
        raise ValueError("truncated purchase-officers request")
    callback = _parse_callback(payload)
    character_id, count = struct.unpack_from("<II", payload, 12)
    if len(payload) != 20 + count * 8:
        raise ValueError("invalid purchase-officers map length")
    assignments = {
        officer_id: station
        for officer_id, station in struct.iter_unpack("<II", payload[20:])
    }
    if len(assignments) != count:
        raise ValueError("duplicate officer ID")
    return callback, character_id, assignments


def _officers_to_review_payload(
    race: int,
    asset_root: Path | None = None,
    *,
    prestige: int = 0,
    economic_scalar: float = 1.0,
    record: dict | None = None,
) -> bytes:
    """Build tGetOfficersToReviewReq::tRep from server-kit officer rules."""
    defaults = _character_ship_defaults(record, asset_root) if record else _starter_ship_defaults(race, asset_root)
    tng_ship = _tng_ship_payload(
        _default_ship_core_payload(defaults), defaults["loadout_fields"]
    )
    officers = _generated_officers(
        race,
        (
            item.get("id")
            for item in (record or {}).get("ship", {}).get("officers", ())
            if isinstance(item, dict) and "id" in item
        ),
    )
    return b"\x01" + struct.pack("<I", len(officers)) + b"".join(officers) + tng_ship + struct.pack(
        "<If", prestige, economic_scalar
    )


OFFICER_NAME_SECTIONS = {
    RACE_FEDERATION: "Federation",
    RACE_KLINGON: "Klingon",
    RACE_ROMULAN: "Romulan",
}
OFFICER_STATIONS = tuple(range(0x60, 0x66))
OFFICER_STATION_NAMES = dict(zip(
    OFFICER_STATIONS,
    ("HELM", "OPS", "MEDICAL", "ENGINEER", "SECURITY", "TACTICAL"),
))


def _officer_names(race: int) -> tuple[str, ...]:
    source = find_structured_asset(
        "CommonSettings/OfficerNames.gf",
        server_asset_root=SERVER_ASSET_ROOT,
        retail_asset_root=ASSET_ROOT,
    )
    section = OFFICER_NAME_SECTIONS.get(race)
    if section is None:
        # The original executable generates Borg designations rather than loading a list.
        return tuple(f"{index + 2} OF 8" for index in range(32))
    values = parse_gf(source.path).get(section, {})
    return tuple(str(values[key]) for key in sorted(values, key=lambda key: int(key)))


def _officer_review_limit() -> int:
    source = find_structured_asset(
        "ServerProfiles/AI.gf",
        server_asset_root=SERVER_ASSET_ROOT,
        retail_asset_root=ASSET_ROOT,
    )
    value = parse_gf(source.path).get("Officers", {}).get("MaxInReviewByClient", 8)
    return max(0, min(32, int(value)))


def _officer_loadout_item(name: str, station: int) -> str:
    """Build the textual DefaultLoadOut officer form for a generated candidate."""
    station_index = station - OFFICER_STATIONS[0]
    skills = ["1. Basic"] * 18
    for index in range(station_index * 3, station_index * 3 + 3):
        skills[index] = "2. Trained"
    return ":".join((
        "OFFICER", OFFICER_STATION_NAMES[station], name,
        "10", "10", "20", "Rookie", *skills, "",
    ))


def _officer_item_payload(name: str, race: int, station: int) -> bytes:
    """Serialize tOfficerItem through its adjusted tStreamable base."""
    skills = [0] * 18
    station_index = station - OFFICER_STATIONS[0]
    for index in range(station_index * 3, station_index * 3 + 3):
        skills[index] = 1
    return (
        b"\x00"
        + struct.pack("<4I", 10, 20, 10, 2)
        + _pack_str(name)
        + struct.pack("<20I", station, *skills, race)
    )


def _officer_payload(database_id: int, name: str, race: int, station: int) -> bytes:
    """Serialize tOfficer in its recovered database-field order."""
    return (
        struct.pack("<II", database_id, 0)
        + _officer_item_payload(name, race, station)
        + struct.pack("<IIIII", 0, CHARACTER_DATABASE_ID, 0xFFFFFFFF, race, race)
    )


def _generated_officers(race: int, excluded_ids=()) -> tuple[bytes, ...]:
    names = _officer_names(race)
    limit = min(_officer_review_limit(), len(names))
    excluded = {int(officer_id) for officer_id in excluded_ids}
    return tuple(
        _officer_payload(1000 + index, names[index], race, OFFICER_STATIONS[index % 6])
        for index in range(limit)
        if 1000 + index not in excluded
    )


SHIP_POLITICAL_BASES = {
    RACE_FEDERATION: "Federation",
    RACE_KLINGON: "Klingon",
    RACE_ROMULAN: "Romulan",
    RACE_BORG: "Borg",
}

# Bare player-facing templates are suitable catalog identities but a few are
# not usable configurations. Award a known stock configured variant while
# preserving the displayed hull class and auction row.
SHIPYARD_AWARD_VARIANTS = {
    "Sovereign": "Sovereign A",
}


def _shipyard_award_defaults(defaults: dict, asset_root: Path | None = None) -> dict:
    variant = SHIPYARD_AWARD_VARIANTS.get(str(defaults["sub_name"]))
    if variant is None:
        return defaults
    root = asset_root or ASSET_ROOT
    if root is None:
        return defaults
    specs = root / "Specs"
    if not specs.is_dir():
        specs = root / "Spec"
    return _load_ship_defaults(
        specs / "DefaultCore.txt", specs / "DefaultLoadOut.txt", variant
    )


def _shipyard_defaults(race: int, asset_root: Path | None = None) -> tuple[dict, ...]:
    """Load the stock, player-facing ship classes for one empire."""
    root = asset_root or ASSET_ROOT
    if root is None:
        raise RuntimeError("server-kit asset root is required for ship definitions")
    specs = root / "Specs"
    if not specs.is_dir():
        specs = root / "Spec"
    political_base = SHIP_POLITICAL_BASES[race]
    rows = tuple(_spec_rows(specs / "DefaultLoadOut.txt"))
    model_names = []
    for row in rows:
        if len(row) < 7 or row[0].strip() != political_base or not row[2].strip():
            continue
        # Each stock empire begins with one contiguous block of player
        # loadouts, followed by its AI variants and scenario definitions.
        if row[5].strip().casefold() == "ai":
            break
        model_names.append(row[2].strip())
    ships = []
    for name in model_names:
        try:
            defaults = _load_ship_defaults(
                specs / "DefaultCore.txt", specs / "DefaultLoadOut.txt", name
            )
            class_id = _ship_class_id(defaults["class_code"])
        except ValueError:
            # Stock loadouts also contain installations and aliases without a
            # corresponding player-ship core row.
            continue
        if class_id <= SHIP_CLASS_IDS["bb"]:
            ships.append(defaults)
    return tuple(ships)


def _economy_ship_auction_settings() -> tuple[float, int, int]:
    source = find_structured_asset(
        "ServerProfiles/Economy.gf",
        server_asset_root=SERVER_ASSET_ROOT,
        retail_asset_root=ASSET_ROOT,
    )
    values = parse_gf(source.path).get("Auction/Ship", {})
    return (
        float(values.get("MinimumBidFactor", "1.0")),
        int(values.get("TurnsUntilClose", "3")),
        int(values.get("MaximumInReviewByEmpire", "40")),
    )


def _auction_item_payload(
    defaults: dict,
    *,
    auction_id: int,
    ship_id: int,
    bid_factor: float,
    turns_until_close: int,
    current_turn: int = 0,
    current_bid: int | None = None,
    bid_owner_id: int = 0,
    turn_bid_made: int = 0,
    bid_maximum: int = 0,
    escrow: int = 0,
    bidding_started: bool = False,
    closing: bool = False,
) -> bytes:
    """Serialize tAuctionItem in the recovered ServerPlatform StreamOut order."""
    rating = int(defaults["hull_cost"])
    minimum_bid = max(1, int(rating * bid_factor))
    displayed_bid = minimum_bid if current_bid is None else int(current_bid)
    turn_to_close = (turn_bid_made + turns_until_close) if bidding_started else (current_turn + turns_until_close)
    return (
        struct.pack("<II", auction_id, 0)       # tDatabaseObject
        + bytes((int(bidding_started),))
        # The client passes this description directly to Vessel Library.
        + _pack_str(defaults["ui_name"])
        + struct.pack("<I", ship_id)           # item ID
        + struct.pack("<II", rating, rating)
        + struct.pack("<dII", bid_factor, current_turn, turn_to_close)
        + bytes((int(closing),))
        + struct.pack("<I", displayed_bid)
        + struct.pack("<I", bid_owner_id)
        + struct.pack("<III", turn_bid_made, bid_maximum, escrow)
        + struct.pack("<I", 1)                 # item-detail map
        + _pack_str("IsBase")
        + _pack_str("No")
    )


def _parse_get_auction_ships_request(
    payload: bytes,
) -> tuple[tuple[int, int, int], int, float, tuple[float, ...]]:
    """Parse tGetAuctionShipsRequest (callback, character, scalar, modifiers)."""
    if len(payload) < 25 or payload[0] != 1:
        raise ValueError("truncated get-auction-ships request")
    callback = _parse_async_return(payload)
    character_id, scalar, count = struct.unpack_from("<IfI", payload, 13)
    expected = 25 + count * 4
    if len(payload) != expected:
        raise ValueError("invalid get-auction-ships request length")
    modifiers = struct.unpack_from(f"<{count}f", payload, 25) if count else ()
    return callback, character_id, scalar, modifiers


def _auction_ships_payload(
    race: int,
    asset_root: Path | None = None,
    *,
    now: float | None = None,
) -> bytes:
    """Build the client shipyard catalog from stock specs and kit economy rules."""
    bid_factor, turns_until_close, limit = _economy_ship_auction_settings()
    ships = _shipyard_defaults(race, asset_root)[:limit]
    _settle_shipyard_bids(now=now)
    current_turn = _campaign_turn(now)
    state = _load_campaign_clock(now)
    auctions = state.get("auctions", {})
    entries = []
    for index, defaults in enumerate(ships):
        auction_id = AUCTION_DATABASE_ID_BASE + index
        ship_id = AUCTION_DATABASE_ID_BASE + 1000 + index
        saved = auctions.get(str(ship_id), {})
        entries.append(
            # The stock database routine indexes this map by GetItemID(), not
            # by the tAuctionItem database object's own ID. The client uses
            # this key to resolve the selected row for View Ship.
            struct.pack("<I", ship_id)
            + _auction_item_payload(
                defaults,
                auction_id=auction_id,
                ship_id=ship_id,
                bid_factor=bid_factor,
                turns_until_close=turns_until_close,
                current_turn=current_turn,
                current_bid=saved.get("current_bid"),
                bid_owner_id=CHARACTER_DATABASE_ID if saved.get("bid_owner") else 0,
                turn_bid_made=int(saved.get("turn_bid_made", 0)),
                bid_maximum=int(saved.get("bid_maximum", 0)),
                escrow=int(saved.get("escrow", 0)),
                bidding_started=bool(saved.get("bid_owner")),
                closing=bool(saved.get("closing", False)),
            )
        )
    # Unlike the IPL panel replies, this stored-procedure response inherits
    # nSwitch::tResponse, whose success value is serialized as an unsigned long.
    return struct.pack("<II", 1, len(entries)) + b"".join(entries)


def _parse_bid_request(
    payload: bytes,
) -> tuple[tuple[int, int, int], int, int, int, int, float, tuple[float, ...]]:
    """Parse nStoredProcedureArguments::tBidRequest for Economy channel 3."""
    if len(payload) < 41 or payload[0] != 1:
        raise ValueError("truncated Shipyard bid request")
    callback = _parse_async_return(payload)
    auction_item_id, bidder_id, auction_type, bid_mode = struct.unpack_from("<IIII", payload, 13)
    scalar, modifier_count = struct.unpack_from("<dI", payload, 29)
    expected = 41 + modifier_count * 4
    if len(payload) != expected:
        raise ValueError("invalid Shipyard bid request length")
    modifiers = (
        struct.unpack_from(f"<{modifier_count}f", payload, 41) if modifier_count else ()
    )
    return callback, auction_item_id, bidder_id, auction_type, bid_mode, scalar, modifiers


def _shipyard_bid_maximum(current_bid: int, bid_mode: int) -> int:
    """Apply the retail tAuctionItem bid-button increment to a displayed bid."""
    # The stock GetBidModeValue routine uses enum values 2 and 3 for the two
    # fixed ship-auction buttons and 9 and 10 for their percentage partners.
    # __ftol truncates the percentage result before it is added to the bid.
    if bid_mode == 2:
        increment = 5
    elif bid_mode in {3, 4, 5, 6, 7}:
        increment = 10
    elif bid_mode == 9:
        increment = max(1, int(current_bid * 0.05))
    elif bid_mode == 10:
        increment = max(1, int(current_bid * 0.10))
    else:
        increment = 1
    return current_bid + increment


def _place_shipyard_bid(
    race: int,
    account: str,
    ship_id: int,
    maximum_bid: int,
    *,
    now: float | None = None,
) -> tuple[bytes, int]:
    """Persist one proxy-style maximum bid and return updated item/result."""
    ships = _shipyard_defaults(race)
    index = ship_id - (AUCTION_DATABASE_ID_BASE + 1000)
    if index < 0 or index >= len(ships):
        raise ValueError("unknown Shipyard item ID")
    defaults = ships[index]
    bid_factor, turns_until_close, _limit = _economy_ship_auction_settings()
    current_turn = _campaign_turn(now)
    state = _load_campaign_clock(now)
    auctions = state.setdefault("auctions", {})
    saved = dict(auctions.get(str(ship_id), {}))
    minimum = max(1, int(defaults["hull_cost"] * bid_factor))
    current = int(saved.get("current_bid", minimum))
    prior_owner = str(saved.get("bid_owner", ""))
    prior_maximum = int(saved.get("bid_maximum", 0))
    if (prior_owner and maximum_bid <= current) or (not prior_owner and maximum_bid < minimum):
        result = 0
    elif prior_owner and prior_owner != account and maximum_bid < prior_maximum:
        saved["current_bid"] = maximum_bid + 1
        auctions[str(ship_id)] = saved
        _write_campaign_state(state)
        result = 1
    else:
        displaced_maximum = prior_maximum if prior_owner and prior_owner != account else 0
        saved.update(
            current_bid=(
                minimum
                if not prior_owner
                else min(maximum_bid, max(current + 1, prior_maximum + 1))
            ),
            bid_owner=account,
            turn_bid_made=current_turn,
            bid_maximum=maximum_bid,
            escrow=maximum_bid,
            closing=False,
        )
        auctions[str(ship_id)] = saved
        _write_campaign_state(state)
        prior_maximum = displaced_maximum
        result = 2
    item = _auction_item_payload(
        defaults,
        auction_id=AUCTION_DATABASE_ID_BASE + index,
        ship_id=ship_id,
        bid_factor=bid_factor,
        turns_until_close=turns_until_close,
        current_turn=current_turn,
        current_bid=saved.get("current_bid", current),
        bid_owner_id=CHARACTER_DATABASE_ID if saved.get("bid_owner") else 0,
        turn_bid_made=int(saved.get("turn_bid_made", 0)),
        bid_maximum=int(saved.get("bid_maximum", 0)),
        escrow=int(saved.get("escrow", 0)),
        bidding_started=bool(saved.get("bid_owner")),
    )
    # success, updated auction, displaced bidder, bid result, released escrow
    return struct.pack("<I", 1) + item + struct.pack("<III", 0, result, prior_maximum), result


def _settle_shipyard_bids(*, now: float | None = None) -> tuple[dict, ...]:
    """Close due auctions and atomically award their ships to stored characters."""
    current_turn = _campaign_turn(now)
    _factor, turns_until_close, _limit = _economy_ship_auction_settings()
    state = _load_campaign_clock(now)
    auctions = state.setdefault("auctions", {})
    characters = _load_characters()
    settlements = state.setdefault("auction_settlements", [])
    completed = []
    for ship_id_text, bid in list(auctions.items()):
        owner = str(bid.get("bid_owner", ""))
        if not owner or current_turn < int(bid.get("turn_bid_made", 0)) + turns_until_close:
            continue
        record = characters.get(owner)
        if record is None:
            del auctions[ship_id_text]
            continue
        ship_id = int(ship_id_text)
        catalog = _shipyard_defaults(int(record["race"]))
        index = ship_id - (AUCTION_DATABASE_ID_BASE + 1000)
        if not 0 <= index < len(catalog):
            del auctions[ship_id_text]
            continue
        defaults = _shipyard_award_defaults(catalog[index])
        price = int(bid.get("current_bid", defaults["hull_cost"]))
        record["prestige"] = max(0, int(record.get("prestige", 0)) - price)
        record["ship"] = {
            "id": SHIP_DATABASE_ID,
            "owner_id": int(record.get("database_id", CHARACTER_DATABASE_ID)),
            "class_name": defaults["ui_name"],
            "loadout_name": defaults["sub_name"],
            "name": str(record.get("ship", {}).get("name", "USS Venture")),
            "class_type": _ship_class_id(defaults["class_code"]),
            "bpv": int(defaults["hull_cost"]),
            "damage": 1.0,
            "flags": 0,
            "turn_created": current_turn,
            "stores": {
                "shuttles": int(defaults["shuttles"][2]),
                "marines": int(defaults["marines"][2]),
                "mines": int(defaults["mines"][2]),
            },
            "refit": {
                "loadout_name": defaults["sub_name"],
                "items": list(defaults["items"]),
            },
            "officers": [],
        }
        characters[owner] = _normalize_character_record(record)
        settlement = {
            "account": owner,
            "ship_id": ship_id,
            "class_name": defaults["ui_name"],
            "price": price,
            "turn": current_turn,
        }
        settlements.append(settlement)
        completed.append(settlement)
        del auctions[ship_id_text]
    if completed:
        CHARACTER_STORE_PATH.write_text(
            json.dumps(characters, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _write_campaign_state(state)
    return tuple(completed)


def _parse_ids(value: str, prefix: str) -> tuple[int, ...]:
    fields = value.split(":")
    if not fields or fields[0] != prefix:
        raise ValueError(f"invalid {prefix} field: {value!r}")
    return tuple(int(field) for field in fields[1:])


def _load_ship_defaults(core_path: Path, loadout_path: Path, model_name: str) -> dict:
    """Load one base ship from the user's installed, unmodified SFC3 specs."""
    loadout_row = next(
        (row for row in _spec_rows(loadout_path) if len(row) >= 7 and row[2].strip() == model_name),
        None,
    )
    core_model_name = loadout_row[3] if loadout_row is not None else model_name
    core_row = next(
        (
            row
            for row in _spec_rows(core_path)
            if len(row) >= 20 and row[11] == core_model_name
        ),
        None,
    )
    if core_row is None or loadout_row is None:
        raise ValueError(f"starter ship {model_name!r} is absent from installed specs")
    return {
        "size_class": int(core_row[0]),
        "class_code": core_row[1],
        "base_weight": int(core_row[2]),
        "cargo_space": int(core_row[3]),
        "hull_cost": int(core_row[4]),
        "power_space": int(core_row[5]),
        "weapon_space": int(core_row[6]),
        "hull_space": int(core_row[7]),
        "shield_space": int(core_row[8]),
        "ship_size": int(core_row[9]),
        "class_name": core_row[10],
        "model_name": core_row[11],
        "starter_name": model_name,
        "primary_hardpoints": _parse_hardpoints(core_row[12], "PrimaryHP"),
        "heavy_hardpoints": _parse_hardpoints(core_row[13], "HeavyHP"),
        "hull_hardpoints": _parse_ids(core_row[14], "HullHP"),
        "bridge_hardpoints": _parse_ids(core_row[15], "BridgeHP"),
        "attributes": tuple(filter(None, core_row[16].split(":"))),
        "mines": _parse_triplet(core_row[17], "Mines"),
        "marines": _parse_triplet(core_row[18], "Marines"),
        "shuttles": _parse_triplet(core_row[19], "Shuttles"),
        "political_base": loadout_row[0],
        "loadout_class_name": loadout_row[1],
        "sub_name": loadout_row[2],
        # tShip's player-facing class name and tAuctionItem's description are
        # the selected DefaultLoadOut variant (Talon/Falcon/Warbird), not the
        # internal model key in column 4 (RomulanFrigate/romulan_warbird).
        # Federation hid this distinction because many of its two values are
        # identical (for example Norway and Sovereign).
        "ui_name": loadout_row[2],
        "default": loadout_row[4],
        "special": loadout_row[5],
        "items": tuple(field for field in loadout_row[6:] if field),
        "loadout_fields": tuple(loadout_row),
    }


def _starter_ship_defaults(race: int, asset_root: Path | None = None) -> dict:
    root = asset_root or ASSET_ROOT
    if root is None:
        raise RuntimeError("server-kit asset root is required for ship definitions")
    model_name, _ship_name, _class_type = _starting_ship_for_race(race)
    specs = root / "Specs"
    if not specs.is_dir():
        # The recovered dedicated-server kit uses the singular directory name.
        specs = root / "Spec"
    return _load_ship_defaults(
        specs / "DefaultCore.txt", specs / "DefaultLoadOut.txt", model_name
    )


def _character_ship_defaults(record: dict, asset_root: Path | None = None) -> dict:
    """Resolve the persisted loadout, falling back to the race's starter ship."""
    record = _normalize_character_record(record)
    root = asset_root or ASSET_ROOT
    if root is None:
        raise RuntimeError("server-kit asset root is required for ship definitions")
    specs = root / "Specs"
    if not specs.is_dir():
        specs = root / "Spec"
    ship = record["ship"]
    refit = ship.get("refit", {})
    model_name = str(
        (refit.get("loadout_name") if isinstance(refit, dict) else "")
        or ship.get("loadout_name")
        or ship["class_name"]
    )
    try:
        defaults = _load_ship_defaults(
            specs / "DefaultCore.txt", specs / "DefaultLoadOut.txt", model_name
        )
    except ValueError:
        defaults = _starter_ship_defaults(int(record["race"]), root)
    items = refit.get("items") if isinstance(refit, dict) else None
    if isinstance(items, list) and all(isinstance(item, str) for item in items):
        defaults = dict(defaults)
        defaults["items"] = tuple(item for item in items if item)
        defaults["loadout_fields"] = tuple(defaults["loadout_fields"][:6]) + tuple(items)
    return defaults


def _canonical_ship_snapshot(record: dict, asset_root: Path | None = None) -> dict:
    """Return the complete mutable ship state consumed by every read path.

    Spec rows remain immutable templates.  Character JSON owns identity and all
    mutable instance data; resolving a template must never replace those values.
    """
    record = _normalize_character_record(record)
    ship = record["ship"]
    defaults = _character_ship_defaults(record, asset_root)
    return {
        "id": int(ship["id"]),
        "owner_id": int(ship.get("owner_id", CHARACTER_DATABASE_ID)),
        "race": int(record["race"]),
        "class_name": str(ship["class_name"]),
        "loadout_name": str(defaults["sub_name"]),
        "name": str(ship["name"]),
        "class_type": int(ship["class_type"]),
        "bpv": int(ship["bpv"]),
        "damage": float(ship["damage"]),
        "flags": int(ship["flags"]),
        "turn_created": int(ship.get("turn_created", 0)),
        "items": tuple(defaults["items"]),
        "stores": {
            name: int(ship.get("stores", {}).get(name, defaults[name][2]))
            for name in ("shuttles", "marines", "mines")
        },
        "officers": tuple(
            (int(item["id"]), str(item["name"]), int(item["station"]), int(item["worth"]))
            for item in ship.get("officers", ())
        ),
    }


def _stored_character_payload(account: str, record: dict) -> bytes:
    record = _normalize_character_record(record)
    return b"\x01" + _default_client_character_payload(
        client_address=str(record["client_address"]),
        account=account,
        character_name=str(record["character_name"]),
        race=int(record["race"]),
        database_id=1,
        rank=0,
        current_position=tuple(record["position"]),
        homeworld=tuple(record["homeworld"]),
        destination=tuple(record["destination"]),
        prestige=int(record["prestige"]),
        ship=record["ship"],
    ) + struct.pack("<I", 0)


# ── Client handler ────────────────────────────────────────────────────────────

class SFC3Client:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.addr   = writer.get_extra_info("peername")
        self.sw_id  = random.randint(1, 0xFFFFFFFE)

    def _log(self, level, msg, *args, **kwargs):
        getattr(log, level)(f"{self.addr[0]}:{self.addr[1]} {msg}", *args, **kwargs)

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
    RELAY_OBJECTS = {
        b" *~Server~* .?AVtNotifyRelayS@@": 30,
        b" *~Server~* .?AVtEconomyRelayS@@": 19,
        b" *~Server~* tShipRelayS": 22,
        b" *~Server~* tClockRelayS": 4,
        b" *~Server~* .?AVtChatRelayS@@": 29,
        b" *~Server~* tMapRelayS": 40,
        b" *~Server~* .?AVtNewsRelayS@@": 27,
        b" *~Server~* tMissionMatcherRelayS": 24,
    }

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.addr = writer.get_extra_info("peername")
        self.sw_id = random.randint(1, 0xFFFFFFFE)
        self.current_character = None
        self.current_record = None
        self.verification_id = ""
        self.player_relay_address = None
        self.viewport_relay_address = None
        self.clock_subscribers: set[tuple[int, int, int]] = set()
        self.clock_task: asyncio.Task | None = None

    def _log(self, level, msg, *args, **kwargs):
        getattr(log, level)(
            f"[game:{GAME_PORT}] {self.addr[0]}:{self.addr[1]} {msg}",
            *args,
            **kwargs,
        )

    async def run(self):
        self._log("info", "CONNECT sw_id=0x%08x", self.sw_id)
        self.clock_task = asyncio.create_task(self._clock_loop())
        try:
            await self._handle()
        except asyncio.IncompleteReadError:
            self._log("info", "DISCONNECTED")
        except asyncio.TimeoutError:
            self._log("warning", "TIMED OUT")
        except Exception as exc:
            self._log("error", "error: %s", exc, exc_info=True)
        finally:
            if self.clock_task is not None:
                self.clock_task.cancel()
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except (ConnectionError, OSError):
                pass

    async def _clock_loop(self):
        """Deliver the retail clock relay's asynchronous turn-break updates."""
        while True:
            remaining_ms = _milliseconds_until_next_turn()
            await asyncio.sleep(max(0.05, remaining_ms / 1000.0))
            if not self.clock_subscribers:
                continue
            payload = _clock_snapshot_payload()
            for callback in tuple(self.clock_subscribers):
                self.writer.write(_nswitch_frame(*callback, payload))
            await self.writer.drain()
            self._log(
                "info",
                "-> campaign turn break turn=%d subscribers=%d",
                _campaign_turn(),
                len(self.clock_subscribers),
            )

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

        identity = _verification_identity_bytes(verification)
        if not _verification_allowed(identity):
            self.writer.write(_nswitch_frame(
                verify_return[0], verify_return[1], verify_return[2], struct.pack("<I", 0)
            ))
            await self.writer.drain()
            self._log("warning", "-> security check rejected by configured CD-key policy")
            return
        if _verification_policy() != "permissive":
            self.verification_id = _verification_identifier(identity)

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

        stored_character = _load_characters().get(account)
        if (
            stored_character is not None
            and self.verification_id
            and stored_character.get("verification_id") not in (None, self.verification_id)
        ):
            self._log("warning", "verification identity does not match account binding")
            return
        if stored_character is not None and self.verification_id and not stored_character.get("verification_id"):
            stored_character["verification_id"] = self.verification_id
            stored_character = _write_character_record(account, stored_character)
        if stored_character is None:
            character_reply = _character_not_found_payload()
        else:
            character_reply = _stored_character_payload(account, stored_character)
            self.current_record = stored_character
            self.current_character = (
                account,
                str(stored_character["character_name"]),
                str(stored_character["client_address"]),
                int(stored_character["race"]),
            )
        self.writer.write(_nswitch_frame(
            return_address[0],
            return_address[1],
            return_address[2],
            character_reply,
        ))
        await self.writer.drain()
        if stored_character is None:
            self._log("info", "-> character not found; client may begin character creation")
        else:
            self._log("info", "-> stored character found (private values not logged)")

        # Keep the connection available for the next implementation phase. Log only
        # structural metadata because authenticated payloads contain private fields.
        while True:
            sw, obj, ch, payload = await self._read_nswitch_frame(
                timeout=SESSION_IDLE_TIMEOUT
            )
            self._log("info", "<- frame sw=%d obj=%d ch=%d plen=%d", sw, obj, ch, len(payload))
            if (sw, obj, ch) == (0, 1, 0):
                try:
                    relay_name, relay_address = _parse_relay_publication(payload)
                except ValueError:
                    pass
                else:
                    # Relay names and numeric callback addresses are protocol metadata,
                    # and recording them lets us route asynchronous player updates.
                    self._log(
                        "info",
                        "<- client relay publication name=%r address=%r",
                        relay_name,
                        relay_address,
                    )
                    if relay_name.endswith(b"PlayerRelayC"):
                        self.player_relay_address = relay_address
                    if relay_name.endswith(b"MetaViewPortHandlerNameC"):
                        self.viewport_relay_address = relay_address
                        if self.current_character is not None and self.current_record is not None:
                            position = tuple(self.current_record["position"])
                            at_friendly_facility = _at_friendly_base_or_planet(
                                position, self.current_character[3]
                            )
                            self.writer.write(_nswitch_frame(
                                relay_address[0],
                                relay_address[1],
                                4,
                                _meta_map_move_payload(
                                    CHARACTER_DATABASE_ID,
                                    position,
                                    0,
                                    0,
                                    at_friendly_facility,
                                ),
                            ))
                            await self.writer.drain()
                            self._log(
                                "info",
                                "-> initial viewport position/facility state",
                            )
            if (sw, obj, ch) == (0, 1, 0) and b"CharacterLogOnRelayNameC" in payload:
                if self.current_character is None:
                    raise ValueError("character logon publication preceded character creation")
                _relay_name, callback = _parse_relay_publication(payload)
                self.writer.write(_nswitch_frame(
                    callback[0],
                    callback[1],
                    2,
                    _character_logon_payload(*self.current_character, self.current_record),
                ))
                await self.writer.drain()
                self._log(
                    "info",
                    "-> character logon response",
                )
                continue
            if (sw, obj, ch) == (0, 1, 2):
                relay_return, relay_name = _parse_relay_request(payload)
                relay_object = self.RELAY_OBJECTS.get(relay_name)
                if relay_object is not None:
                    self.writer.write(_nswitch_frame(
                        relay_return[0],
                        relay_return[1],
                        relay_return[2],
                        _relay_claim_payload(relay_name, relay_object),
                    ))
                    await self.writer.drain()
                    self._log(
                        "info",
                        "-> claimed requested relay object=%d",
                        relay_object,
                    )
                    continue
                self._log("warning", "unknown relay request name_len=%d", len(relay_name))
            if (sw, obj, ch) == (0, 4, 2):
                callback = _parse_callback(payload)
                self.clock_subscribers.add(callback)
                self.writer.write(_nswitch_frame(
                    callback[0], callback[1], callback[2], _clock_snapshot_payload()
                ))
                await self.writer.drain()
                self._log("info", "-> initial campaign clock snapshot")
                continue
            if (sw, obj, ch) == (0, 40, 46):
                callback = _parse_callback(payload)
                self.writer.write(_nswitch_frame(
                    callback[0], callback[1], callback[2], _map_size_payload()
                ))
                await self.writer.drain()
                self._log(
                    "info",
                    "-> campaign map size %dx%d",
                    CAMPAIGN_MAP_WIDTH,
                    CAMPAIGN_MAP_HEIGHT,
                )
                continue
            if (sw, obj, ch) == (0, 40, 45):
                callback = _parse_callback(payload)
                self.writer.write(_nswitch_frame(
                    callback[0], callback[1], callback[2], _map_snapshot_payload()
                ))
                await self.writer.drain()
                self._log(
                    "info",
                    "-> stock retail multiplayer campaign map %dx%d",
                    CAMPAIGN_MAP_WIDTH,
                    CAMPAIGN_MAP_HEIGHT,
                )
                continue
            if (sw, obj, ch) == (0, 22, 7):
                callback = _parse_callback(payload)
                if len(payload) != 16:
                    raise ValueError("invalid supply-dock request length")
                character_id = struct.unpack_from("<I", payload, 12)[0]
                if character_id != CHARACTER_DATABASE_ID or self.current_character is None:
                    response = b"\x00"
                else:
                    try:
                        response = _supply_dock_payload(
                            self.current_character[3], record=self.current_record
                        )
                    except (OSError, RuntimeError, ValueError) as exc:
                        self._log("warning", "Supply Dock defaults unavailable: %s", exc)
                        response = b"\x00"
                self.writer.write(_nswitch_frame(
                    callback[0], callback[1], callback[2], response
                ))
                await self.writer.drain()
                self._log("info", "-> generated Supply Dock ship state")
                continue
            if (sw, obj, ch) == (0, 22, 13):
                callback = _parse_callback(payload)
                response = (
                    b"\x01" + _updated_ship_payload(self.current_record) + b"\x00"
                    if self.current_record is not None else b"\x00"
                )
                try:
                    _callback, character_id, ship_name, desired = _parse_update_stores_request(payload)
                    if (
                        self.current_character is not None
                        and character_id == CHARACTER_DATABASE_ID
                        and ship_name == str(self.current_record["ship"]["name"])
                    ):
                        defaults = _character_ship_defaults(self.current_record)
                        requested = {
                            "shuttles": int(desired["shuttles"][2]),
                            "marines": int(desired["misc_desired"][0]),
                            "mines": int(desired["misc_desired"][1]),
                        }
                        self._log(
                            "info",
                            "Supply Dock decoded groups=%s requested counts=%s current=%s maxima=%s",
                            desired,
                            requested,
                            {
                                name: int(self.current_record["ship"].get("stores", {}).get(name, defaults[name][2]))
                                for name in requested
                            },
                            {name: int(defaults[name][1]) + 1 for name in requested},
                        )
                        self.current_record = _update_supplies(
                            self.current_character[0], requested
                        )
                        response = b"\x01" + _updated_ship_payload(self.current_record) + b"\x01"
                except (KeyError, OSError, RuntimeError, ValueError) as exc:
                    self._log("warning", "Supply Dock update rejected: %s", exc)
                self.writer.write(_nswitch_frame(*callback, response))
                await self.writer.drain()
                self._log("info", "-> Supply Dock update result=%d", response[0])
                continue
            if (sw, obj, ch) == (0, 19, 2):
                callback, character_id, _scalar, _modifiers = (
                    _parse_get_auction_ships_request(payload)
                )
                if character_id != CHARACTER_DATABASE_ID or self.current_character is None:
                    response = struct.pack("<I", 0)
                else:
                    try:
                        response = _auction_ships_payload(self.current_character[3])
                    except (KeyError, OSError, RuntimeError, ValueError) as exc:
                        self._log("warning", "Shipyard defaults unavailable: %s", exc)
                        response = b"\x00"
                self.writer.write(_nswitch_frame(*callback, response))
                await self.writer.drain()
                self._log("info", "-> retail shipyard auction catalog")
                continue
            if (sw, obj, ch) == (0, 19, 3):
                (
                    callback,
                    ship_id,
                    bidder_id,
                    auction_type,
                    bid_mode,
                    scalar,
                    _modifiers,
                ) = _parse_bid_request(payload)
                self._log(
                    "info",
                    "Shipyard bid decoded item=%d bidder=%d type=%d mode=%d scalar=%s",
                    ship_id,
                    bidder_id,
                    auction_type,
                    bid_mode,
                    scalar,
                )
                if (
                    bidder_id != CHARACTER_DATABASE_ID
                    or self.current_character is None
                ):
                    response = struct.pack("<I", 0)
                else:
                    try:
                        bid_factor, _turns, _limit = _economy_ship_auction_settings()
                        defaults = _shipyard_defaults(self.current_character[3])
                        index = ship_id - (AUCTION_DATABASE_ID_BASE + 1000)
                        if not 0 <= index < len(defaults):
                            raise ValueError("unknown Shipyard item ID")
                        state = _load_campaign_clock()
                        saved = state.get("auctions", {}).get(str(ship_id), {})
                        displayed_bid = int(
                            saved.get(
                                "current_bid",
                                max(1, int(defaults[index]["hull_cost"] * bid_factor * scalar)),
                            )
                        )
                        maximum_bid = _shipyard_bid_maximum(displayed_bid, bid_mode)
                        response, result = _place_shipyard_bid(
                            self.current_character[3],
                            self.current_character[0],
                            ship_id,
                            int(maximum_bid),
                        )
                    except (KeyError, OSError, RuntimeError, ValueError) as exc:
                        self._log("warning", "Shipyard bid rejected: %s", exc)
                        response = struct.pack("<I", 0)
                        result = 0
                self.writer.write(_nswitch_frame(*callback, response))
                await self.writer.drain()
                self._log("info", "-> Shipyard bid result=%d", result)
                continue
            if (sw, obj, ch) == (0, 6, 11):
                callback = _parse_callback(payload)
                if len(payload) != 16:
                    raise ValueError("invalid open-Shipyard-bids request length")
                # tGetCharacterOpenBidShipIDsReq::tRep: success plus vector<tID>.
                account = self.current_character[0] if self.current_character else ""
                state = _load_campaign_clock()
                open_ids = tuple(
                    int(ship_id)
                    for ship_id, bid in state.get("auctions", {}).items()
                    if bid.get("bid_owner") == account and not bid.get("closing", False)
                )
                response = b"\x01" + struct.pack("<I", len(open_ids)) + b"".join(
                    struct.pack("<I", ship_id) for ship_id in open_ids
                )
                self.writer.write(_nswitch_frame(*callback, response))
                await self.writer.drain()
                self._log("info", "-> %d open Shipyard bid IDs", len(open_ids))
                continue
            if (sw, obj, ch) == (0, 6, 28):
                callback = _parse_callback(payload)
                if len(payload) != 16:
                    raise ValueError("invalid friendly-base request length")
                character_id = struct.unpack_from("<I", payload, 12)[0]
                at_friendly_base = False
                if character_id == CHARACTER_DATABASE_ID and self.current_record is not None:
                    at_friendly_base = _at_friendly_base_or_planet(
                        tuple(self.current_record["position"]),
                        int(self.current_record["race"]),
                    )
                # tIsCharacterAtFriendlyBaseReq::tRep(atBase, success, reason).
                response = bytes((int(at_friendly_base), 1, 0))
                self.writer.write(_nswitch_frame(*callback, response))
                await self.writer.drain()
                self._log("info", "-> friendly-base status=%d", at_friendly_base)
                continue
            if (sw, obj, ch) == (0, 6, 20):
                callback, character_id, _for_update = (
                    _parse_character_ship_config_request(payload)
                )
                if character_id != CHARACTER_DATABASE_ID or self.current_character is None:
                    response = b"\x00"
                else:
                    try:
                        response = _character_ship_config_payload(
                            self.current_character[3],
                            prestige=int(self.current_record.get("prestige", 0)),
                            record=self.current_record,
                        )
                    except (OSError, RuntimeError, ValueError) as exc:
                        self._log("warning", "Ship config defaults unavailable: %s", exc)
                        response = b"\x00"
                self.writer.write(_nswitch_frame(*callback, response))
                await self.writer.drain()
                self._log("info", "-> current character ship config")
                continue
            if (sw, obj, ch) == (0, 6, 27):
                callback, character_id = _parse_officers_to_review_request(payload)
                if character_id != CHARACTER_DATABASE_ID or self.current_character is None:
                    response = b"\x00"
                else:
                    try:
                        response = _officers_to_review_payload(
                            self.current_character[3],
                            prestige=int(self.current_record.get("prestige", 0)),
                            record=self.current_record,
                        )
                    except (OSError, RuntimeError, ValueError) as exc:
                        self._log("warning", "Officer-review defaults unavailable: %s", exc)
                        response = b"\x00"
                self.writer.write(_nswitch_frame(*callback, response))
                await self.writer.drain()
                self._log("info", "-> server-kit officer review with current ship config")
                continue
            if (sw, obj, ch) == (0, 6, 8):
                callback, character_id = _parse_free_officers_request(payload)
                # tFreeOfficersInReviewReq::tRep is a single success byte.
                response = b"\x01" if (
                    character_id == CHARACTER_DATABASE_ID
                    and self.current_character is not None
                ) else b"\x00"
                self.writer.write(_nswitch_frame(*callback, response))
                await self.writer.drain()
                self._log("info", "-> freed officer-review reservation")
                continue
            if (sw, obj, ch) == (0, 6, 13):
                callback = _parse_callback(payload)
                if len(payload) != 16:
                    raise ValueError("invalid character-prestige request length")
                character_id = struct.unpack_from("<I", payload, 12)[0]
                response = _character_prestige_payload(
                    self.current_record
                    if character_id == CHARACTER_DATABASE_ID else None
                )
                self.writer.write(_nswitch_frame(*callback, response))
                await self.writer.drain()
                self._log("info", "-> current and lifetime character prestige")
                continue
            if (sw, obj, ch) == (0, 6, 39):
                callback, character_id, assignments = _parse_purchase_officers_request(payload)
                response = b"\x00\x00"
                if character_id == CHARACTER_DATABASE_ID and self.current_character is not None:
                    try:
                        self.current_record = _purchase_officers(
                            self.current_character[0], assignments
                        )
                        response = b"\x01\x01"
                    except (OSError, RuntimeError, ValueError) as exc:
                        self._log("warning", "Officer purchase rejected: %s", exc)
                self.writer.write(_nswitch_frame(*callback, response))
                await self.writer.drain()
                self._log("info", "-> officer purchase result=%d", response[0])
                continue
            if (sw, obj, ch) == (0, 6, 38):
                callback, character_id, ship_id, config = _parse_purchase_config_request(payload)
                response = b"\x00\x00"
                if (
                    character_id == CHARACTER_DATABASE_ID
                    and ship_id == SHIP_DATABASE_ID
                    and self.current_character is not None
                ):
                    try:
                        fields = config["loadout_fields"]
                        if len(fields) < 7:
                            raise ValueError("refit loadout has too few fields")
                        self.current_record = _save_refit(
                            self.current_character[0], fields[2], list(fields[6:])
                        )
                        response = b"\x01\x01"
                    except (OSError, RuntimeError, ValueError) as exc:
                        self._log("warning", "Refit purchase rejected: %s", exc)
                self.writer.write(_nswitch_frame(*callback, response))
                await self.writer.drain()
                self._log("info", "-> Refit purchase result=%d", response[0])
                continue
            if (sw, obj, ch) == (0, 27, 2):
                callback, requested_story_id = _parse_news_request(payload)
                story = None
                if self.current_character is not None:
                    stories = tuple(_load_campaign_clock().get("news", ()))
                    story = next(
                        (item for item in stories if int(item.get("id", -1)) == requested_story_id),
                        stories[0] if stories else _welcome_news_story(requested_story_id),
                    )
                    response = _news_response_payload(story)
                else:
                    response = struct.pack("<I", 0)
                self.writer.write(_nswitch_frame(*callback, response))
                await self.writer.drain()
                self._log("info", "-> News request story=%s", story and story["id"])
                continue
            if (sw, obj, ch) == (0, 24, 10):
                callback, character_id, match_mode = _parse_mission_match_request(payload)
                response = b"\x00"
                if character_id == CHARACTER_DATABASE_ID and self.current_character is not None:
                    state = _load_campaign_clock()
                    active = next(
                        (
                            mission for mission in state.get("missions", [])
                            if mission.get("account") == self.current_character[0]
                            and mission.get("status") in {"offered", "accepted", "launched"}
                        ),
                        None,
                    )
                    if active is None:
                        _offer_mission(
                            self.current_character[0],
                            "Patrol the current sector",
                            mission_type=f"patrol:{match_mode}",
                        )
                    response = b"\x01"
                self.writer.write(_nswitch_frame(*callback, response))
                await self.writer.drain()
                self._log("info", "-> mission-match request acknowledged")
                continue
            if (sw, obj, ch) == (0, 24, 11):
                callback, character_id = _parse_verify_mission_request(payload)
                # eCanChooseMissionResponses value zero is the successful/default enum.
                response = struct.pack("<IB", 1, 0) if (
                    character_id == CHARACTER_DATABASE_ID and self.current_character is not None
                ) else struct.pack("<I", 0)
                self.writer.write(_nswitch_frame(*callback, response))
                await self.writer.drain()
                self._log("info", "-> mission-choice eligibility response")
                continue
            if (sw, obj, ch) == (0, 24, 12):
                callback, character_id, battle = _parse_choose_mission_request(payload)
                response = b"\x00"
                if character_id == CHARACTER_DATABASE_ID and self.current_character is not None:
                    state = _load_campaign_clock()
                    offered = next(
                        (
                            mission for mission in state.get("missions", [])
                            if mission.get("account") == self.current_character[0]
                            and mission.get("status") == "offered"
                        ),
                        None,
                    )
                    if offered is not None:
                        offered["battle"] = battle
                        offered["status"] = "accepted"
                        _write_campaign_state(state)
                        response = b"\x01"
                self.writer.write(_nswitch_frame(*callback, response))
                await self.writer.drain()
                self._log("info", "-> mission-choice result=%d", response[0])
                continue
            if (sw, obj, ch) == (0, 40, 41):
                callback, _character_id, destination = _parse_move_request(payload)
                if self.current_character is None or self.current_record is None:
                    raise ValueError("move request preceded character logon")
                current = tuple(self.current_record["position"])
                distance = _hex_distance(current, destination)
                accepted = (
                    _character_id == CHARACTER_DATABASE_ID
                    and self.viewport_relay_address is not None
                    and 0 <= destination[0] < CAMPAIGN_MAP_WIDTH
                    and 0 <= destination[1] < CAMPAIGN_MAP_HEIGHT
                    and distance > 0
                )
                if accepted:
                    self.current_record["position"] = list(destination)
                    self.current_record["destination"] = [-1, -1]
                    self.current_record = _write_character_record(
                        self.current_character[0], self.current_record
                    )
                self.writer.write(_nswitch_frame(
                    callback[0], callback[1], callback[2],
                    _move_response_payload(accepted, max(1, distance))
                ))
                await self.writer.drain()
                if accepted and self.viewport_relay_address is not None:
                    viewport_switch, viewport_object = self.viewport_relay_address
                    at_friendly_facility = _at_friendly_base_or_planet(
                        destination, self.current_character[3]
                    )
                    self.writer.write(_nswitch_frame(
                        viewport_switch,
                        viewport_object,
                        4,
                        _meta_map_move_payload(
                            _character_id, destination, 1, 1, at_friendly_facility
                        ),
                    ))
                    await self.writer.drain()
                    await asyncio.sleep(max(1, distance))
                    self.writer.write(_nswitch_frame(
                        viewport_switch,
                        viewport_object,
                        4,
                        _meta_map_move_payload(
                            _character_id, destination, 0, 0, at_friendly_facility
                        ),
                    ))
                    await self.writer.drain()
                    self._log("info", "-> viewport movement start/completion")
                self._log(
                    "info",
                    "-> movement %s destination=(%d,%d) distance=%d",
                    "accepted" if accepted else "rejected",
                    destination[0],
                    destination[1],
                    distance,
                )
                continue
            if (sw, obj, ch) == (0, 6, 12):
                callback = _parse_callback(payload)
                race = self.current_character[3] if self.current_character else RACE_NEUTRAL
                position = None
                destination = (-1, -1)
                if self.current_record is not None:
                    position = tuple(self.current_record["position"])
                    destination = tuple(self.current_record["destination"])
                self.writer.write(_nswitch_frame(
                    callback[0],
                    callback[1],
                    callback[2],
                    _character_position_payload(race, position, destination),
                ))
                await self.writer.drain()
                self._log("info", "-> persisted character position")
                continue
            if (sw, obj, ch) == (0, 6, 24):
                callback = _parse_callback(payload)
                if self.current_character is None:
                    raise ValueError("client-character request preceded character logon")
                self.writer.write(_nswitch_frame(
                    callback[0],
                    callback[1],
                    callback[2],
                    _get_client_character_payload(
                        *self.current_character, record=self.current_record
                    ),
                ))
                await self.writer.drain()
                self._log("info", "-> current client character")
                continue
            if (sw, obj, ch) == (0, 6, 26):
                callback = _parse_callback(payload)
                self.writer.write(_nswitch_frame(
                    callback[0], callback[1], callback[2], _fleet_data_payload(
                        self.current_character[3] if self.current_character else RACE_NEUTRAL,
                        self.current_record,
                    )
                ))
                await self.writer.drain()
                self._log("info", "-> authoritative character fleet data")
                continue
            if (sw, obj, ch) == (0, 6, 6):
                (
                    return_address,
                    _first,
                    create_account,
                    race,
                    character_name,
                    create_address,
                    _language,
                ) = _parse_create_client_character(payload)
                self.writer.write(_nswitch_frame(
                    return_address[0],
                    return_address[1],
                    return_address[2],
                    _character_created_payload(
                        create_account, character_name, create_address, race
                    ),
                ))
                await self.writer.drain()
                self.current_character = (
                    create_account,
                    character_name,
                    create_address,
                    race,
                )
                self.current_record = _save_character(
                    create_account,
                    character_name,
                    create_address,
                    race,
                    self.verification_id,
                )
                self._log(
                    "info",
                    "-> character created race=%d name_len=%d (private values not logged)",
                    race,
                    len(character_name),
                )
                continue
            if PRIVATE_CAPTURE_PATH:
                # Opt-in diagnostic capture. The payload may contain account and
                # character values, so the configured destination must stay ignored.
                with open(PRIVATE_CAPTURE_PATH, "ab") as capture:
                    capture.write(struct.pack("<IIII", sw, obj, ch, len(payload)))
                    capture.write(payload)
                self._log("info", "saved private frame for offline protocol analysis")

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
    global PERSISTENCE
    if not DEFAULT_DATABASE_PATH.exists():
        from build_default_database import build as build_default_database
        manifest = build_default_database(DEFAULT_DATABASE_PATH, SERVER_ASSET_ROOT)
        log.info(
            "Built default campaign database at %s (asset manifest %s)",
            DEFAULT_DATABASE_PATH,
            manifest,
        )
    created = database.create_working_database(
        DEFAULT_DATABASE_PATH, DATABASE_PATH, epoch_unix=time.time()
    )
    persistence = database.initialize(DATABASE_PATH)
    PERSISTENCE = persistence
    log.info(
        "SQLite persistence schema ready at %s (version %d, first_start=%s); JSON compatibility storage remains active",
        DATABASE_PATH,
        database.schema_version(persistence),
        created,
    )
    relay_handler = lambda r, w: asyncio.ensure_future(SFC3Client(r, w).run())
    game_handler = lambda r, w: asyncio.ensure_future(DynamicSecurityClient(r, w).run())
    directory_handler = lambda r, w: asyncio.ensure_future(MasterDirectoryClient(r, w).run())
    relay_servers = [
        await asyncio.start_server(relay_handler, host, PORT) for host in BIND_HOSTS
    ]
    game_servers = [
        await asyncio.start_server(game_handler, host, GAME_PORT) for host in BIND_HOSTS
    ]
    directory_servers = [
        await asyncio.start_server(directory_handler, host, DIRECTORY_PORT) for host in BIND_HOSTS
    ]
    loop = asyncio.get_running_loop()
    status_transports = []
    for host in BIND_HOSTS:
        transport, _ = await loop.create_datagram_endpoint(
            StatusProtocol,
            local_addr=(host, STATUS_PORT),
        )
        status_transports.append(transport)
    log.info(
        "Listening on %s TCP %d/%d/%d and UDP %d; advertising %s:%d",
        ",".join(BIND_HOSTS),
        PORT,
        GAME_PORT,
        DIRECTORY_PORT,
        STATUS_PORT,
        ADVERTISE_HOST,
        STATUS_PORT,
    )
    servers = relay_servers + game_servers + directory_servers
    async with contextlib.AsyncExitStack() as stack:
        for listening_server in servers:
            await stack.enter_async_context(listening_server)
        try:
            await asyncio.gather(*(server.serve_forever() for server in servers))
        finally:
            for transport in status_transports:
                transport.close()
            persistence.close()
            PERSISTENCE = None


if __name__ == "__main__":
    asyncio.run(main())
