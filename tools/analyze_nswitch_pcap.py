"""Extract framed nSwitch traffic from one TCP stream in a Wireshark capture."""

from __future__ import annotations

import argparse
import re
import struct
import subprocess
from pathlib import Path


def followed_directions(capture: Path, stream: int, tshark: Path) -> tuple[bytes, bytes]:
    output = subprocess.check_output(
        [str(tshark), "-r", str(capture), "-q", "-z", f"follow,tcp,raw,{stream}"],
        text=True,
    )
    directions = [bytearray(), bytearray()]
    for line in output.splitlines():
        direction = 1 if line.startswith("\t") else 0
        value = line.strip()
        if re.fullmatch(r"[0-9a-fA-F]+", value) and len(value) % 2 == 0:
            directions[direction].extend(bytes.fromhex(value))
    return bytes(directions[0]), bytes(directions[1])


def frames(data: bytes):
    """Find valid length-prefixed nSwitch frames after any GT2 negotiation bytes."""
    offset = 0
    while offset + 18 <= len(data):
        length = struct.unpack_from(">H", data, offset)[0]
        end = offset + 2 + length
        if length >= 16 and end <= len(data):
            switch, object_id, channel, payload_length = struct.unpack_from(
                "<IIII", data, offset + 2
            )
            if payload_length == length - 16:
                yield offset, switch, object_id, channel, data[offset + 18 : end]
                offset = end
                continue
        offset += 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--stream", type=int, default=1)
    parser.add_argument("--object", type=int)
    parser.add_argument("--channel", type=int)
    parser.add_argument(
        "--tshark", type=Path, default=Path(r"C:\Program Files\Wireshark\tshark.exe")
    )
    args = parser.parse_args()
    for direction, data in enumerate(followed_directions(args.capture, args.stream, args.tshark)):
        for offset, switch, object_id, channel, payload in frames(data):
            if args.object is not None and object_id != args.object:
                continue
            if args.channel is not None and channel != args.channel:
                continue
            print(
                f"direction={direction} offset={offset} switch={switch} "
                f"object={object_id} channel={channel} payload={len(payload)} "
                f"hex={payload.hex()}"
            )


if __name__ == "__main__":
    main()
