# SFC Programming APIs Y2020 inventory

## Provenance and local storage

- Source archive: `reference/SFC_programing_APIs_Y2020.rar`
- SHA-256: `531367CAC31A4BCC6E8F3A18D3CCE0E7D4EDBA753C103C4ADF2006567FA4D547`
- Expanded directory: `reference/SFC_programing_APIs_Y2020/`
- Both the archive and expanded tree are intentionally excluded from Git.
- The package was linked from the Hot & Spicy forum thread
  `c-sfc-mission-scripting-t30264` and hosted on Mod DB.

## Extraction summary

- 31,849 files in 1,041 folders
- 10,198,706,180 expanded bytes
- The `1/` working tree contains 14,043 files / 4.67 GB.
- `preset up slt_and_projects/` is a second, largely duplicate prepared tree with
  14,077 files / 4.63 GB.
- The bundled Visual C++ 6 installation occupies 3,718 files / 269 MB.
- Within the main SFC3 Scripts tree, approximately 8,833 source/project files
  occupy only 27.6 MB; 4,817 compiled/intermediate files occupy 4.58 GB.

The useful research material is therefore small compared with the binaries,
debug databases, object files, and duplicate prepared tree.

## Main SFC3 source tree

`1/Projects/Taldren/Projects/SFCTNG/Scripts/` contains:

- `ScriptInterface/`: C++ wrapper classes for missions, teams, ships, states,
  victory conditions, maps, events, and player management.
- `Shared/Source/`: public interfaces, mission specifications, ship-system
  declarations, scripting structures, and supporting libraries.
- Original-looking mission project groups: Borg (9), Federation (15), Klingon
  (16), Romulan (19), Meta/Dynaverse (11), Multiplayer (11), Single-player
  (13), Tutorial (6), and sample projects (9).
- Additional Typhon mod trees: TyphonMeta (25) and TyphonMulti (27), including
  experiments, copies, bonus variants, and compiled outputs.
- Visual C++ 6 `.dsp`/`.dsw` projects and many already-built `.dll` files.

## High-value protocol and gameplay contracts

### Dynaverse mission input/output

`Shared/Source/Include/DynaverseScriptInfo.h` defines
`tDynaverseScriptInfo`, the semantic handoff between the campaign/Meta engine
and a tactical mission.

Campaign-provided fields include:

- mission name, location, day/year, mission type, and campaign year;
- player team/race, allied and enemy races, previous victory and system;
- a player fleet of up to three ships, including Meta database IDs and starting
  position offset;
- preferred map, team descriptions, hosting flag, campaign status, and a set of
  script values.

Mission-provided fields include:

- all ships instantiated in the tactical game (up to 60);
- allied/enemy race, primary enemy, tagged ship, and end-game pause;
- map name, mission title, selected map, system, menu state, and technical
  success result.

This is not the Dynaverse TCP packet layout, but it gives us a concrete target
model for decoding the mission-assignment payload.

### Mission completion results

`ScriptInterface/TeamInfo.h` defines a mission scheduler result containing:

- victory level;
- prestige and bonus prestige;
- next-mission score and title;
- medal;
- campaign event (`none`, `retire`, or `lost`).

`MissionInfo.h` exposes campaign hooks including prestige configuration,
mission scheduling, career totals, hex/system queries, mission date/location,
and `mAdjustDynaverse(type, modifier, race)`. These declarations should guide
our mission-result model and later hex-control updates.

### Stores and post-combat state

`ScriptInterface/ShipInfo` exposes get/add/remove/set operations for ship stores
and a bulk `mSetShipLoadout` covering marines, spare parts, mines, shuttles,
fighters, and missile variants. Store reads are explicitly feedback requests.

This supports the forum observation that tactical mission results reconcile
remaining supplies back into campaign state. It does not define the separate
Supply Dock request/response protocol currently producing our black screen.

### Ship validation and refit clues

`Shared/Source/shipsys/tTNGShip.h` identifies distinct validation failures:

- overloaded weapons space;
- overloaded hull space;
- overloaded power space;
- overloaded shield space;
- invalid power setup, hull setup, hardpoints, BPV, or race restrictions.

It also declares loadout string/stream serialization, editable loadout access,
power/mass/maneuverability calculations, and officer replacement methods.
However, key definitions such as `tTNGShipLoadOut.h`, `tTNGShipCoreData.h`, and
`Officeritem.h` are absent from the extracted package, and the implementation of
`tTNGShip` itself is not included. The package therefore reveals the validation
model but not the exact overload formula or serialized loadout layout.

### Mission kinds and examples

`missionspec.h` enumerates campaign, unique campaign, tutorial, technical,
historical, multiplayer, skirmish, voice-over skirmish, debug, and bonus mission
types. The eleven stock-looking `Meta/` projects all mark themselves as campaign
missions and provide concrete examples for mission matching, initialization,
team population, victory evaluation, and Dynaverse-facing results.

## Relevance to the remaining work

- **Mission button/combat:** high value. This is the first substantial SFC3
  tactical mission source we have and defines what data a mission expects.
- **Post-combat persistence:** high value. It exposes stores, damage-related ship
  objects, victory/prestige results, medals, and campaign adjustment hooks.
- **Refit, Officers, Supply Dock, and stardate:** historical supporting evidence.
  Those replacement paths are now implemented and client-validated; this package
  remains useful for regression interpretation rather than active protocol gaps.
- **GameSpy/login/server browser:** no useful implementation; this is a mission
  scripting package, not a replacement server or retail client source tree.

## Recommended next use

1. Model our mission-assignment domain object after `tDynaverseScriptInfo`.
2. Compare captured mission-assignment bytes against its ordered fields and the
   nested `tTeamScriptDescription` / `tShipInGame` declarations.
3. Inventory the eleven stock `Meta/` missions and match their expected filenames
   against the retail `Assets/Scripts` directory.
4. Derive a mission-result model from `tMissionScheduler`, victory-condition
   code, and ship/store accessors before implementing combat persistence.
5. Keep this package as supporting mission/combat evidence, not as a wire
   specification for already completed campaign facilities.
