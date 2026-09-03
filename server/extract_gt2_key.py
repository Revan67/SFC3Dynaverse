"""Extract SFC3's embedded GT2 transport key without displaying it."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


GT2_KEY_VA = 0x0099D6B8
GT2_KEY_LENGTH = 32


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def extract_key(executable: Path) -> str:
    data = executable.read_bytes()
    pe_offset = _u32(data, 0x3C)
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise ValueError("input is not a PE executable")

    section_count = _u16(data, pe_offset + 6)
    optional_header = pe_offset + 24
    image_base = _u32(data, optional_header + 28)
    target_rva = GT2_KEY_VA - image_base
    section_table = optional_header + _u16(data, pe_offset + 20)

    for index in range(section_count):
        section = section_table + index * 40
        virtual_size = _u32(data, section + 8)
        virtual_address = _u32(data, section + 12)
        raw_size = _u32(data, section + 16)
        raw_offset = _u32(data, section + 20)
        if virtual_address <= target_rva < virtual_address + max(virtual_size, raw_size):
            file_offset = raw_offset + target_rva - virtual_address
            raw_key = data[file_offset : file_offset + GT2_KEY_LENGTH]
            key = raw_key.decode("ascii")
            if len(key) != GT2_KEY_LENGTH or not key.isprintable():
                raise ValueError("embedded key failed validation")
            return key

    raise ValueError("GT2 key address is not mapped by a PE section")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    key = extract_key(args.executable)
    args.output.write_text(f"SFC3_GT2_KEY={key}\n", encoding="ascii")
    print(f"Wrote a validated {len(key)}-byte GT2 key to {args.output}")


if __name__ == "__main__":
    main()
