# SFC3 Dynaverse Server Revival

[![Project status](https://img.shields.io/badge/status-active_development-orange)](docs/project-status.md)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows_11-0078D4?logo=windows11&logoColor=white)](#requirements)
[![Last commit](https://img.shields.io/github/last-commit/Revan67/SFC3Dynaverse)](https://github.com/Revan67/SFC3Dynaverse/commits/main/)
[![Open issues](https://img.shields.io/github/issues/Revan67/SFC3Dynaverse)](https://github.com/Revan67/SFC3Dynaverse/issues)

A clean-room Python replacement for the retired Star Trek: Starfleet Command III
Dynaverse and GameSpy services. The goal is to let an unmodified retail client
host and join persistent private campaigns without the original online services
or `ServerPlatform.exe`.

## Current status

The project has rebuilt most of the non-combat Dynaverse foundation. An
unmodified retail/GOG client can discover the replacement server, create an
account and character, enter the persistent campaign, move around the retail
map, and use its principal ship-management facilities.

### Implemented and retail-client tested

- **Network services:** GameSpy-compatible account/profile services, directory
  listing, browser status, GT2/nSwitch bootstrap, dynamic security, loopback and
  LAN hosting, and configurable permissive/registered/strict CD-key policies.
- **Accounts and characters:** creation, login, reconnect, all four playable
  factions, correct homeworld starts, complete starting crews, and persistent
  character state.
- **Campaign:** stock 51x34 server-kit map, faction territory, player marker,
  Center behavior, immediate homeworld facilities, multi-hex movement, and
  restart-stable position.
- **Campaign clock:** the recovered five-field retail clock, client-visible
  `56200.xx` stardate, movement-independent turns, and restart-stable timing.
- **Ships:** one canonical mutable ship instance shared by login, fleet data,
  Supply Dock, Refit, Officers, Shipyard awards, restart, and relog.
- **Supply Dock:** shuttle, marine, and mine purchases and sales with capacity,
  prestige, UI completion, and persistence.
- **Refit:** valid removal/addition, prestige accounting, overload validation,
  complete loadout saving, and persistence.
- **Officers:** server-kit rosters, transfer in/out, station replacement,
  cancellation, facility restoration, and persistent six-station assignments.
- **Shipyard:** faction inventory, localized names, selection, previews, bids,
  escrow, turn-based settlement, trade-in, and complete winning-ship awards.
- **News:** a working panel and persisted welcome story.
- **SQLite:** authoritative accounts, characters, ships, stores, loadouts,
  officers, clock, auctions, settlements, news, missions, map, and asset
  provenance. First start creates a working campaign from a pristine template;
  later starts never silently reseed it.

### Partially complete

- **Two-player auctions:** single-player settlement is proven; competing bids,
  loser refunds, simultaneous bids, and reconnect behavior need a second client.
- **Multiplayer concurrency:** normal single-client paths work, but concurrent
  movement, notifications, facilities, auctions, and disconnect races need
  broader testing.
- **Failure paths:** insufficient prestige, full capacity, invalid or stale
  requests, and interrupted transactions need systematic retail-client coverage.

### Major gameplay work remaining

1. **Battle-item and mission availability:** publish valid offers and enable the
   Missions panel.
2. **Tactical launch:** match players and AI, serialize the complete mission,
   select a host, complete ready-to-play, and reach a playable battle.
3. **Tactical results:** ingest returned ships, damage, stores, outcomes,
   prestige, rewards, and campaign consequences exactly once.
4. **Mission lifecycle:** selection, acceptance, objectives, rewards, expiry,
   disconnect recovery, and multiplayer participation.
5. **Random encounters and simulation:** generate encounters from campaign
   state, run strategic AI/economy/map changes, and remain deterministic across
   long-running campaigns and restarts.

The replacement is therefore a functional persistent strategic campaign and
ship-management server. The central missing boundary is converting campaign
state into a playable tactical battle and safely reconciling its result.

Later product work includes Peerchat, mod/override layers, expanded host
configuration, password-reset administration, backup/restore, an operator GUI,
deployment packaging, and multi-player stress testing. Client resolution,
scaling, renderer, and GOG-wrapper improvements belong on a separate branch.

Known evidence and open questions are tracked in
[`docs/investigation-evidence-matrix.md`](docs/investigation-evidence-matrix.md).
The dependency-ordered sequence and completion gates are in
[`docs/implementation-roadmap.md`](docs/implementation-roadmap.md).

## Requirements

- Windows 11 is the currently tested host platform.
- Python 3.10 or newer; the server uses only the standard library.
- PowerShell 5.1 or newer for the combined launcher.
- A legitimately owned SFC3 installation containing `SFC3.exe`.
- The GT2 protocol key extracted privately from that executable.
- The publicly released SFC3 server-kit data under `assets/server-kit`.
- Administrator access to configure hostname redirection and, for LAN or
  internet hosting, Windows Firewall and router forwarding.

The game, retail client, serial/CD keys, private account data, captures, and
logs are not distributed. The server does not load assets from a retail
installation at runtime.

## Setup

Copy the released server-kit asset folders into:

```text
assets/server-kit/
  CommonSettings/
  Maps/
  Scripts/
  ServerProfiles/
  Spec/
```

Do not copy or commit the retail executable from `ValidatedClientFiles`.

Extract the GT2 protocol key from your own client into the ignored
`server/.env` file:

```powershell
python .\server\extract_gt2_key.py "E:\Games\GOG\Star Trek SFC3\SFC3.exe" .\server\.env
```

The GT2 protocol key is distinct from an individual serial/CD key. Do not print,
publish, or commit either one.

Redirect these retired hostnames on each client to the replacement server:

```text
127.0.0.1 access1.sfc3.activision.com
127.0.0.1 gpcm.gamespy.com
127.0.0.1 gpsp.gamespy.com
127.0.0.1 master.gamespy.com
```

Use the server's stable LAN address instead of `127.0.0.1` for a different
client computer. The stock GOG executable does not honor SFC Launcher's
`[Gamespy]` INI overrides; those require its modified client.

## Running the server

From the repository root:

```powershell
.\Start-SFC3Server.ps1 -ServerAddress '127.0.0.1'
```

For LAN hosting, pass the server computer's stable Ethernet address:

```powershell
.\Start-SFC3Server.ps1 -ServerAddress '192.168.0.55'
```

The launcher reads `server/.env`, validates the server-kit assets, starts all
components, checks for occupied ports, and writes logs beneath the ignored
`server/logs` directory. Override paths when needed:

```powershell
.\Start-SFC3Server.ps1 `
    -ServerAddress '192.168.0.55' `
    -ServerAssetRoot '.\assets\server-kit' `
    -PythonPath 'C:\Program Files\Python314\python.exe'
```

### Campaign database lifecycle

The pristine `server/default-campaign.sqlite3` template is generated from the
server-kit definitions with:

```powershell
python server/build_default_database.py --force
```

On first start the server atomically copies it to the ignored local
`server/campaign.local.sqlite3` and anchors the campaign clock. Later starts
never replace or reseed the working database. The template contains initialized
campaign/map state and asset provenance, but no player accounts or characters.
Use `SFC3_DATABASE` or `SFC3_DEFAULT_DATABASE` to select alternate paths.

Required listeners:

| Protocol | Port | Role |
|---|---:|---|
| TCP | 29900 | Account login/creation |
| TCP | 29901 | Profile lookup |
| TCP | 28900 | Server directory |
| UDP | 27633 | Server-browser status |
| TCP | 26100 | SFC3 bootstrap relay |
| TCP | 27632 | Security, character, and campaign session |

Client redirection, firewall rules, advertised address, and router forwarding
must agree. The future operator GUI will distinguish local listening, firewall
permission, and externally verified reachability.

## Configuration and data policy

The replacement defaults to permissive CD-key verification because no
authoritative retail-key registry survives. `SFC3_CDKEY_POLICY` supports:

- `permissive` — accept structurally valid clients;
- `registered` — derive and retain server-secret HMAC identifiers;
- `strict` — allow only configured HMAC identifiers.

Non-permissive modes require `SFC3_IDENTITY_HMAC_SECRET`; strict identifiers are
listed in `SFC3_REGISTERED_KEY_IDS`. Raw key material and reusable proofs must
never be logged or stored.

SQLite is authoritative for local accounts, characters, ships, stores, refits,
officers, the campaign clock, auctions, news, and prepared missions. The old
ignored JSON files are accepted only by the explicit one-time migration tool;
normal server operation neither reads nor writes them. Password reset—not
password recovery—and a mod-overlay directory are planned operator features. Baseline
files under `assets/server-kit` should remain unchanged; future overrides will
take precedence by relative path.

## Development

Run the test suite with:

```powershell
python -m unittest discover -s server -p "test_*.py" -v
```

Current documentation:

- [Project status](docs/project-status.md)
- [Investigation evidence matrix](docs/investigation-evidence-matrix.md)
- [Implementation roadmap](docs/implementation-roadmap.md)
- [Protocol findings](docs/protocol-findings.md)
- [Dynamic security protocol](docs/dynamic-security-protocol.md)
- [GameSpy protocol](docs/gamespy-protocol.md)
- [Reverse-engineering notes](docs/reverse-engineering.md)
- [Server-kit asset inventory](docs/server-kit-asset-inventory.md)
- [Architecture plan](docs/architecture-plan.md)
- [Capture procedure](docs/capture-plan.md)

Raw packet captures, Ghidra exports, forum mirrors, credentials, account
databases, and extracted archives are local research inputs and are ignored.

## Legal

This is a clean-room interoperability project under 17 U.S.C. § 1201(f). It is
not affiliated with or endorsed by Taldren, Activision, GameSpy, GOG, or their
successors. Users must supply a legitimately owned game client and assets.

## License

This project is licensed under the **GNU General Public License v3.0** (see [LICENSE](LICENSE.MD)).

This project is an independent reimplementation of server-side functionality.
No original game assets or proprietary code are included. You must supply
your own original game files.
