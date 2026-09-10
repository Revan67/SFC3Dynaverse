"""Compare a retail-captured tTNGShip core with a server-generated stock core."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "tools"))

import server  # noqa: E402
from analyze_nswitch_pcap import followed_directions, frames  # noqa: E402


def unpack_string(data: bytes, offset: int) -> tuple[str, int]:
    length = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    return data[offset : offset + length].decode("cp1252"), offset + length


def parse_core(data: bytes, offset: int) -> tuple[dict, int]:
    result: dict[str, object] = {}
    groups = []
    for _ in range(6):
        count = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        groups.append(struct.unpack_from(f"<{count}I", data, offset))
        offset += count * 4
    result["hardpoints"] = tuple(groups)
    result["primary"] = struct.unpack_from("<8I", data, offset)
    offset += 32
    result["class_name"], offset = unpack_string(data, offset)
    result["model_name"], offset = unpack_string(data, offset)
    count = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    attributes = []
    for _ in range(count):
        value, offset = unpack_string(data, offset)
        attributes.append(value)
    result["attributes"] = tuple(attributes)
    result["model"] = struct.unpack_from("<7I", data, offset)
    offset += 28
    result["secondary"] = struct.unpack_from("<4I", data, offset)
    return result, offset + 16


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--stream", type=int, default=1)
    parser.add_argument("--variant", default="Saber")
    parser.add_argument(
        "--tshark", type=Path, default=Path(r"C:\Program Files\Wireshark\tshark.exe")
    )
    args = parser.parse_args()

    captured = None
    for data in followed_directions(args.capture, args.stream, args.tshark):
        for _offset, switch, object_id, channel, payload in frames(data):
            if (
                switch == 7 and object_id == 6 and channel == 0
                and len(payload) > 1000 and payload[5:7] == b"\x01\x01"
            ):
                captured = payload[5:]
                break
        if captured is not None:
            break
    if captured is None:
        raise SystemExit("no Character ship-config response found")

    specs = ROOT / "assets" / "server-kit" / "Spec"
    defaults = server._load_ship_defaults(
        specs / "DefaultCore.txt", specs / "DefaultLoadOut.txt", args.variant
    )
    generated = server._default_ship_core_payload(defaults)
    retail_fields, retail_end = parse_core(captured, 2)
    generated_fields, generated_end = parse_core(b"\x01\x01" + generated, 2)

    for key in retail_fields:
        marker = "=" if retail_fields[key] == generated_fields[key] else "!"
        print(f"{marker} {key}: retail={retail_fields[key]!r} generated={generated_fields[key]!r}")
    retail_core = captured[2:retail_end]
    print(f"core lengths: retail={len(retail_core)} generated={len(generated)}")
    if retail_core != generated:
        first = next(i for i, pair in enumerate(zip(retail_core, generated)) if pair[0] != pair[1])
        print(f"first byte mismatch: offset={first} retail={retail_core[first]:02x} generated={generated[first]:02x}")
    else:
        print("core bytes match exactly")
    assert generated_end == 2 + len(generated)


if __name__ == "__main__":
    main()
