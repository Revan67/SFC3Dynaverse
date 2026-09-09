# SFC3 Dynaverse Server Revival

A clean-room Python replacement for the retired Star Trek: Starfleet Command III
Dynaverse and GameSpy services. The goal is to let an unmodified retail client
host and join persistent private campaigns without the original online services
or `ServerPlatform.exe`.

## Current status

The unmodified GOG client can currently:

- create and log into a local account;
- create, persist, and rejoin a character;
- discover the server and enter the campaign;
- render the stock 51x34 server-kit map and faction homeworld;
- display and recenter on the player marker;
- move and retain position across reconnects;
- browse Supply Dock, Refit, Officers, and the server-kit Shipyard catalog;
- select and preview Shipyard vessels, place persistent bids, and receive a
  winning vessel;
- display the welcome news item.

Current work is focused on one authoritative serialized `tShip` across Supply
Dock, Refit, Officers, persistence, and relog; the five-field campaign clock;
and the mission launch/result lifecycle. Known client-visible defects and their
evidence are tracked in
[`docs/investigation-evidence-matrix.md`](docs/investigation-evidence-matrix.md).
The dependency-ordered work sequence and completion gates are in
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

Local accounts and campaign state are written to ignored JSON files beneath
`server/`. Password reset—not password recovery—and a mod-overlay directory are
planned operator features. Baseline files under `assets/server-kit` should remain
unchanged; future overrides will take precedence by relative path.

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
successors. Users must supply a legitimately owned game client and the publicly
released server-kit inputs themselves.
