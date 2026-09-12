"""Legacy GameSpy master-directory and status protocol helpers for SFC3."""

from __future__ import annotations

import ipaddress
import struct


# The unmodified 1.01 Build 534 client identifies Dynaverse as ``sfc3dv``.
# Community launchers/patches commonly rewrite that identifier to ``sfc3``.
GAME_NAME = "sfc3dv"
COMPATIBLE_GAME_NAMES = ("sfc3dv", "sfc3")
GAME_VERSION = "2"
GAME_KEY = b"Gi7C8s"
_SFC3_CAPTURED_CRYPT_KEY = bytes.fromhex("be76f72b5a98ea")

# The surviving service's 21-byte reply consists of the enctype-2 key header
# (one encoded length byte plus a seven-byte key) and 13 encrypted bytes: one
# compact endpoint followed by ``\final\``. Reusing that captured key header
# and stream lets us substitute an endpoint without retaining account data.
def _enctype2_stream(key: bytes, length: int) -> bytes:
    """Generate the GameSpy SDK enctype-2 stream used by SFC3."""
    mask = 0xFFFFFFFF
    table = [0] * 256
    for pass_index in range(4):
        table = [((value * 256) + index) & mask for index, value in enumerate(table)]
        swap_index = pass_index
        for _ in range(2):
            for index in range(256):
                swap_index = (swap_index + key[index % len(key)] + table[index]) & 0xFF
                table[index], table[swap_index] = table[swap_index], table[index]
    table = [value ^ index for index, value in enumerate(table)]

    def rot8(value: int) -> int:
        return ((value << 8) | (value >> 24)) & mask

    def rot24(value: int) -> int:
        return ((value << 24) | (value >> 8)) & mask

    def descend(x: int, y: int, z: int) -> tuple[int, int, int]:
        x = (x + z) & mask
        y = (y + x) & mask
        return (x + y) & mask, y, z

    def left(x: int, y: int, z: int) -> tuple[int, int, int]:
        y = rot24(y)
        x ^= table[x & 0xFF]
        y ^= table[y & 0xFF]
        y = rot24(y)
        x = rot8(x)
        x ^= table[x & 0xFF]
        y ^= table[y & 0xFF]
        return rot8(x), y, (z + z) & mask

    def right(x: int, y: int, z: int) -> tuple[int, int, int]:
        x = rot24((~x) & mask)
        x ^= table[x & 0xFF]
        y ^= table[y & 0xFF]
        x = rot24(x)
        y = rot8(y)
        x ^= table[x & 0xFF]
        y ^= table[y & 0xFF]
        return x, rot8(y), (z + z + 1) & mask

    x_stack, y_stack, z_stack = [0] * 16, [0] * 16, [0] * 16
    x, y, z, stack_index = 0, 0, 1, 0
    bit = 1 << 15
    while bit:
        x, y, z = descend(x, y, z)
        x_stack[stack_index], y_stack[stack_index], z_stack[stack_index] = x, y, z
        stack_index += 1
        x, y, z = left(x, y, z)
        bit >>= 1

    stream = bytearray()
    while len(stream) < length:
        words: list[int] = []
        for _ in range(16):
            while z < (1 << 16):
                x, y, z = descend(x, y, z)
                x_stack[stack_index], y_stack[stack_index], z_stack[stack_index] = x, y, z
                stack_index += 1
                x, y, z = left(x, y, z)
            words.append((x ^ y) & mask)
            stack_index = max(stack_index - 1, 0)
            x, y, z = x_stack[stack_index], y_stack[stack_index], z_stack[stack_index]
            x, y, z = right(x, y, z)
        # The SDK deliberately regenerates with one byte still unused.
        stream.extend(b"".join(struct.pack("<I", word) for word in words)[:63])
    return bytes(stream[:length])


def compact_server_list(host: str, port: int, *, crypt_key: bytes | None = None) -> bytes:
    address = ipaddress.ip_address(host)
    if address.version != 4:
        raise ValueError("legacy compact lists require an IPv4 address")
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")

    # Use the key from a known-good retail-compatible directory response. The
    # protocol permits arbitrary keys, but this removes old-client sensitivity
    # to randomized binary header bytes (especially embedded NULs).
    clear_key = crypt_key if crypt_key is not None else _SFC3_CAPTURED_CRYPT_KEY
    if len(clear_key) != 7:
        raise ValueError("SFC3 enctype-2 keys must contain seven bytes")
    wire_key = bytearray(clear_key)
    for index, value in enumerate(GAME_KEY):
        wire_key[index] ^= value

    plaintext = address.packed + struct.pack(">H", port) + b"\\final\\"
    stream = _enctype2_stream(clear_key, len(plaintext))
    encrypted = bytes(value ^ stream[index] for index, value in enumerate(plaintext))
    return bytes((len(clear_key) ^ 0xEC,)) + bytes(wire_key) + encrypted


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
