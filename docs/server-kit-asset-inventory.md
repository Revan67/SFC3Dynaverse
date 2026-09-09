# Server-kit asset inventory

Reviewed 2026-09-08. The publicly released server-kit assets are vendored under
`assets/server-kit` and are the server's sole runtime asset source. Commercial retail assets
are neither copied into nor loaded by the project.

## Source precedence

1. Dedicated-server kit files for runtime rules and generated campaign content.
2. Static analysis for behavior not expressed by the distributed server-kit data.
3. Packet captures for wire shape, sequencing, and values unavailable from files or static analysis.
4. Retail files only as external comparison evidence; never as a runtime fallback.

Captured campaign content must not override an available server-kit definition. Runtime loaders
resolve only from `assets/server-kit`; the retail installation is a research and client input.

## Immediately useful structured inputs

| Area | Canonical local path | Likely use |
|---|---|---|
| Strategic maps | `assets/server-kit/Maps/*.mvm` | Map geometry, regions, terrain, economy, defense, planets, and bases |
| Officer names | `assets/server-kit/CommonSettings/OfficerNames.gf` | Race-specific generated officer names |
| Ship names | `assets/server-kit/CommonSettings/ShipNames.gf` | Race-specific generated vessel names |
| Races and ranks | `...\CommonSettings\RaceNames.gf`, `Rank.gf` | Display names and progression labels |
| Item catalogs | `...\CommonSettings\BridgeItems.gf`, `HullItems.gf`, `PowerItems.gf`, `ShieldItem.gf`, `WeaponItems.gf` | Refit, supply, generated loadouts, costs, and item metadata |
| Ship cores/loadouts | `assets/server-kit/Spec/DefaultCore.txt`, `DefaultLoadOut.txt` | Ship inventory, stock configurations, hardpoints, and systems |
| Character rules | `...\ServerProfiles\Character.gf` | Starting ships, officer generation, prestige, and character limits |
| Economy rules | `...\ServerProfiles\Economy.gf` | Supply, repair, refit, officer, and auction pricing/timing |
| Ship rules | `...\ServerProfiles\Ship.gf` | Ship generation and auction timing |
| AI rules | `...\ServerProfiles\AI.gf` | AI populations and behavior settings |
| Map rules | `...\ServerProfiles\MetaMap.gf`, `HexValues.gf` | Movement, political behavior, and client value tiers |
| News rules | `...\ServerProfiles\News.gf` | News retention and publication settings |
| Mission rules | `...\ServerProfiles\MissionMatching.gf`, `MissionGoals.gf`, `Goal.gf` | Mission selection and campaign goals |
| Campaign template | `assets/server-kit/Scripts/Campaigns/Campaign 1.mct` | Default map selection, races, era, and mission list |
| Database schema | `assets/server-kit/SQL/CreateTables.sql` | Original entities, fields, and relationships; source reference for `server/schema.sql` |

The verified clean E: GOG installation remains an external research reference when a controlled
comparison is needed; it is not a runtime dependency. The server-kit `DefaultCore.txt` matches the
retail file byte-for-byte. Its `DefaultLoadOut.txt` differs only in the Scimitar row: retail includes
the `NS` flag after the `scimitar` model name, while the server-kit field is empty.

## Maps

| File | Dimensions | Cells | Notes |
|---|---:|---:|---|
| `Assets\Maps\Multi.mvm` | 51x34 | 1,734 | Stock large multiplayer map; now used by the replacement server |
| `Assets\Maps\MediumMultiMap.mvm` | 40x25 | 1,000 | Default server-kit campaign template map |
| `Assets\Maps\TNGMap.mvm` | 16x16 | 256 | Compact map |
| Client `MetaAssets\Single.mvm` | 34x19 | 646 | Retail single-player map |
| Client `MetaAssets\SingleTNGMap.mvm` | 34x19 | 646 | Alternate single-player map |

The `.mvm` binary cell record is 32 bytes: economic value, impedance, strength, region,
cartel region, terrain index, planet type, and base type. The map converter maps retail regions
to client race IDs, converts terrain indices to client terrain bits, reduces typed planets/bases
to the client presence flags, and preserves economy/strength values.

## Useful but requiring protocol or format work

- `Assets\Scripts\*.scr` and `CampaignScripts.Cache`: compiled mission behavior; useful for hashes,
  static analysis, and compatibility, but not directly executable by the Python server.
- `Saves\Sfc3Spd.sds`: potentially valuable populated database/save evidence. It needs format
  recovery before records can be safely imported.
- `ServerPlatform.exe` and `ghidradump\ServerPlatform.exe.c`: authoritative behavior evidence for
  serializers, request channels, defaults, auction generation, officers, and campaign turns.
- `D3serverManual.html`, `Docs\*.txt`, and `SFC3 Readme v534.rtf`: operator semantics and settings.
- `logfile.log` and LogViewer logs: runtime sequencing and subsystem behavior; inspect with care
  because logs may contain historical addresses or account identifiers.

## Recommended extraction order

1. Parse the `.gf` configuration format into typed Python data with source provenance.
2. Generate officers from `OfficerNames.gf` plus `AI.gf` rules and serialize `tOfficer`. Candidate
   browsing is now implemented and client-validated; purchase/transfer remains.
3. Parse complete ship availability from `DefaultCore.txt`/`DefaultLoadOut.txt` and generate
   auction inventory according to `Ship.gf` and `Economy.gf`. Faction catalogs, bid presentation,
   and selected-hull Vessel Library previews are implemented and client-validated; bid persistence
   and settlement remain.
4. Add item pricing and availability to Supply Dock and Refit from the CommonSettings catalogs.
5. Implement news retention/publication from `News.gf` and recovered request serializers.
6. The SQL schema has now informed the versioned SQLite entity model in
   `server/schema.sql`; analyze the `.sds` save for populated-record evidence.
