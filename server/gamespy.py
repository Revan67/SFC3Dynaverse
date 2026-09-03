"""Legacy GameSpy master-directory and status protocol helpers for SFC3."""

from __future__ import annotations

import ipaddress
import struct


GAME_NAME = "sfc3"
GAME_VERSION = "2"
GAME_KEY = b"Gi7C8s"

# The surviving service's 21-byte reply consists of the enctype-2 key header
# (one encoded length byte plus a seven-byte key) and 13 encrypted bytes: one
# compact endpoint followed by ``\final\``. Reusing that captured key header
# and stream lets us substitute an endpoint without retaining account data.
_COMPACT_HEADER = bytes.fromhex("ebf91fc06862ebea")
_COMPACT_KEYSTREAM = bytes.fromhex("ab536c9fb4a141f61ac91abd5b")


def compact_server_list(host: str, port: int) -> bytes:
    address = ipaddress.ip_address(host)
    if address.version != 4:
        raise ValueError("legacy compact lists require an IPv4 address")
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")

    plaintext = address.packed + struct.pack(">H", port) + b"\\final\\"
    encrypted = bytes(a ^ b for a, b in zip(plaintext, _COMPACT_KEYSTREAM))
    return _COMPACT_HEADER + encrypted


def status_response(hostname: str, game_port: int, query_id: str = "1.1") -> bytes:
    fields = (
        ("gamename", GAME_NAME),
        ("gamever", GAME_VERSION),
        ("location", "0"),
        ("serverver", "1.01"),
        ("validclientver", "1.01"),
        ("hostname", hostname),
        ("hostport", str(game_port)),
        ("mapname", "Local Dynaverse"),
        ("gametype", "SFC3 Dynaverse replacement server"),
        ("maxnumplayers", "5000"),
        ("numplayers", "0"),
        ("maxnumloggedonplayers", "40"),
        ("numplayersindatabase", "0"),
        ("gamemode", "Open"),
        ("racelist", "0 1 2 3 "),
        ("password", ""),
        ("maxloggedonplayers", "40"),
    )
    body = "".join(f"\\{key}\\{value}" for key, value in fields)
    return f"{body}\\final\\\\queryid\\{query_id}".encode("ascii")
