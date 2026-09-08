# Project Status

Reviewed 2026-09-07 after persistent character entry and the first local movement test.

## Evidence levels

- **Confirmed:** observed in a packet capture or reproduced against the client.
- **Static-analysis finding:** supported by Ghidra output but not yet observed end-to-end.
- **Hypothesis:** plausible design or interpretation requiring a controlled test.

## Confirmed

- The port 26100 GT2/nSwitch bootstrap and 18-step factory sequence are understood.
- `server/server.py` reproduces the bootstrap through the client factory response.
- GPSP 29901 and GPCM 29900 request/response shapes are known.
- A live login queries the master service on 28900.
- The master response leads to a second GT2/nSwitch connection on a dynamic game port;
  port 27632 was observed.
- The game-port security exchange is captured through success and the subsequent
  `tCharacterRelayS` publication.
- TCP 28900 compact directory discovery and UDP 27633 status response are decoded and implemented.
- An unmodified local client completed account login, Ethernet directory discovery, GT2 security,
  character lookup and creation, and entered the Dynaverse campaign UI.
- Character records persist in ignored `server/characters.local.json`; a server restart and direct
  re-login with the stored character were verified.
- Channel 6 on `tCharacterRelayS` is `tCreateClientCharacterReq`. Its test request and successful
  client-character response are decoded and generated without replaying private data.
- `CharacterLogOnRelayNameC` publishes the client callback address. The replacement sends its
  character-logon response there and claims `tNotifyRelayS` as object 30.
- The eight captured post-logon service relays are claimed with deterministic object IDs.
- The clock registration, 51x34 map-size, and 1,734-record full-map replies are implemented.
- The compact 11-byte `tClientHex` is decoded as race, planet race, terrain mask, planet flag,
  starbase flag, victory points, economy points, and speed percentage.
- The map now uses the stock 51x34 retail `MetaAssets/Multi.mvm`, converted from its map-editor
  records to compact client records. Region, terrain, planet/base presence, victory, and economy
  come from the retail map; its source and generated-record SHA-256 hashes are recorded in
  `server/campaign_map.py`. The unmodified retail client renders the converted map successfully.
- The captured live character was located at neutral hex `(28,8)`. New local Federation characters
  instead start at the retail Federation homeworld `(24,19)` with destination `(-1,-1)`, allowing the
  initial viewport and Center action to target faction space.
- Character channels 24 and 26 are identified as `tGetClientCharacterReq` and `tGetFleetDataReq`;
  the server generates the local character and a one-ship fleet response. This restores the
  player marker, initial faction-homeworld camera, and Center action. A channel-12 position handler
  is implemented from the live schema and now reports the persisted position rather than always
  returning the faction start.
- The live Ethernet capture contains a movement immediately before combat. The client sends
  `IPL_Map` object 40/channel 41 with callback `(6,6,0)`, character ID, and destination `(28,9)`.
  The live server publishes movement-active and movement-complete records on channel 4 of the
  client `MetaViewPortHandlerNameC` object. Exact sanitized wire bodies are covered by tests.
- The local server validates an adjacent destination, completes it without a reconnect, persists
  it, and returns the character there after reconnect. The player marker and Center action track
  the resulting position.
- The recovered `tShip` serializer is implemented from field-level Ghidra evidence. Supply Dock
  channel 7 generates the race-specific installed starter core/loadout, full damage and stores
  structures, and per-ship repair, trade-in, and item-rate maps without replaying captured player
  data. The unmodified client renders the resulting Supply Dock UI and starter-ship inventory.
- Character channel 20 returns the installed starter `tTNGShip`, economic scalar, and prestige. The
  unmodified client renders the Norway Refit UI with its installed and available systems.
- Economy channel 2 now returns a faction-specific Shipyard catalog generated from the retail
  `DefaultCore.txt` and `DefaultLoadOut.txt`, with auction defaults from the server kit's
  `Economy.gf`. The unmodified client renders all Federation rows, tracks row selection and bid
  increments, and opens the selected hull in Vessel Library. Player-facing class names (for example
  `Norway` and `Sovereign`) must be serialized rather than internal `Fed-*` loadout identifiers.
  Placing and completing bids is not yet implemented. Officers displays eight generated `tOfficer`
  candidates using the server kit's
  `OfficerNames.gf` and `AI.gf` review limit. Names, stations, skills, profiles, and calculated worth
  render correctly in the unmodified client. Officer purchase/transfer is not yet implemented.
  News is also not yet implemented.
- Peerchat starts with plaintext `CRYPT des 1 sfc3`, then switches to encrypted traffic after 705.

## Prototype-only

- `server/server.py` is a focused bootstrap implementation.
- `server/probe.py` combines the bootstrap implementation, permissive GPCM/GPSP responders,
  and raw listeners for suspected ports.
- The account responder persists local accounts and verifies the legacy GameSpy login proof; the
  storage format and permissive protocol handling remain prototype quality.
- The dynamic security wire helpers have focused unit tests; packaging metadata is still absent.

## Current milestone

The 2026-09-02 Ethernet capture resolved the dynamic-port authentication blocker. It contains the
client verification request, the server's successful security response, character authentication,
initial service-relay setup, mission-matching traffic, and encrypted Peerchat startup.

`server/server.py` now carries the unmodified client through discovery, dynamic-port security,
character lookup/creation, persistence, character logon, and entry into the Dynaverse campaign UI.
The client accepts clock initialization, renders the retail 51x34 map, displays a race-specific
starter ship and marker, recenters on the persisted player position, completes adjacent movement,
and renders the generated Supply Dock, Refit, Officers, and Shipyard browsing interfaces. The next
milestone is implementing mutations behind those interfaces—starting with Shipyard bids and officer
transfers—then missions, news, economy, and turn simulation. See
`docs/dynamic-security-protocol.md` and `docs/character-login-protocol.md` for the sanitized wire
structures.

## Recovered research artifacts

- Original server kits: `D:\SFC\sfc3`
- Installed server and profiles: `C:\Utilities\SFC3Server`
- Compatibility tools and helpers: `C:\Utilities\Dev\sfc3-compat`
- Extracted build 504: `C:\Utilities\Dev\sfc3-server-504`
- Ghidra projects/exports: `reference/ghidra` (local evidence; keep out of commits)
- Successful live capture: `live-login-ethernet-20260902.pcapng` (ignored by Git)

Some older raw captures remain on the previous computer. They are useful historical evidence but
do not block the current character-login work.

## Superseded conclusions

- `tAccessRelayS` claim format is no longer unknown.
- Port 26100 is bootstrap, not the complete CD-key authentication service.
- Port 27100 is not established as a fixed simulation port.
- The raw 44-byte challenge inferred from static analysis is superseded by the observed
  nSwitch-framed dynamic-port exchange.

## Intended product scope

- Clean-room Python replacement; no dependency on `ServerPlatform.exe`
- Local accounts and optional CD-key allowlist
- Full Dynaverse simulation: campaigns, economy, AI, missions, hex map, and turns
- In-game Peerchat compatibility
- Simple Windows client/server setup tools
- AMP packaging after the server becomes deployable

## Architecture direction, not yet implementation

The recovered design proposes separate authentication and simulation processes sharing SQLite
in WAL mode. This remains a useful direction, but the process boundary and session/CD-key flow
must be revisited after the dynamic game-port authentication is understood.
