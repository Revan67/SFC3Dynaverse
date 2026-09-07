import tempfile
import unittest
from pathlib import Path

from asset_sources import find_structured_asset, parse_gf


class AssetSourceTests(unittest.TestCase):
    def test_gf_parser_preserves_slashes_in_quotes_and_types_scalars(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.gf"
            path.write_text(
                'Name="A // B" // comment\n[Rules]\nCount=025\nRatio=0.5\nHex=0x40\n',
                encoding="cp1252",
            )
            parsed = parse_gf(path)
        self.assertEqual(parsed[""]["Name"], "A // B")
        self.assertEqual(parsed["Rules"], {"Count": 25, "Ratio": 0.5, "Hex": 64})

    def test_server_kit_precedes_retail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            kit = root / "kit"
            retail = root / "retail"
            (kit / "CommonSettings").mkdir(parents=True)
            (retail / "CommonSettings").mkdir(parents=True)
            relative = "CommonSettings/OfficerNames.gf"
            (kit / relative).write_text("Name=kit", encoding="ascii")
            (retail / relative).write_text("Name=retail", encoding="ascii")
            source = find_structured_asset(
                relative, server_asset_root=kit, retail_asset_root=retail
            )
        self.assertEqual(source.tier, "server-kit")
        self.assertEqual(source.path.name, "OfficerNames.gf")
