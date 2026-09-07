"""Structured retail/server-kit asset loading with explicit provenance."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AssetSource:
    path: Path
    tier: str


def _without_comment(line: str) -> str:
    quoted = False
    for index, character in enumerate(line):
        if character == '"':
            quoted = not quoted
        if character == "/" and not quoted and line[index:index + 2] == "//":
            return line[:index]
    return line


def _typed_value(value: str) -> Any:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    if re.fullmatch(r"[-+]?0[xX][0-9a-fA-F]+", value):
        return int(value, 16)
    if re.fullmatch(r"[-+]?\d+", value):
        return int(value, 10)
    if re.fullmatch(r"[-+]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][-+]?\d+)?", value):
        return float(value)
    return value


def parse_gf(path: Path) -> dict[str, dict[str, Any]]:
    """Parse the INI-like Game Framework format used by SFC3 profiles."""
    sections: dict[str, dict[str, Any]] = {"": {}}
    section = ""
    for number, raw_line in enumerate(path.read_text(encoding="cp1252").splitlines(), 1):
        line = _without_comment(raw_line).strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            sections.setdefault(section, {})
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{number}: expected key=value")
        key, value = line.split("=", 1)
        sections[section][key.strip()] = _typed_value(value)
    return sections


def find_structured_asset(
    relative_path: str,
    *,
    server_asset_root: Path | None = None,
    retail_asset_root: Path | None = None,
) -> AssetSource:
    """Resolve structured data using server kit before retail installation."""
    kit = server_asset_root
    if kit is None and os.environ.get("SFC3_SERVER_ASSET_ROOT"):
        kit = Path(os.environ["SFC3_SERVER_ASSET_ROOT"])
    retail = retail_asset_root
    if retail is None and os.environ.get("SFC3_ASSET_ROOT"):
        retail = Path(os.environ["SFC3_ASSET_ROOT"])
    for tier, root in (("server-kit", kit), ("retail", retail)):
        if root is not None:
            candidate = root / relative_path
            if candidate.is_file():
                return AssetSource(candidate, tier)
    raise FileNotFoundError(f"structured SFC3 asset not found: {relative_path}")
