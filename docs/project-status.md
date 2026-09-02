# Project Status

Reviewed 2026-09-02 after migrating the repository and Claude research notes to Codex.

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
- The game-port client publishes `tSecurityRelayS`; the live server claims it and sends a
  55-byte challenge frame.

## Prototype-only

- `server/server.py` is a focused bootstrap implementation.
- `server/probe.py` combines the bootstrap implementation, permissive GPCM/GPSP responders,
  and raw listeners for suspected ports.
- The account responders do not persist accounts or verify credentials.
- The source has no automated tests or packaging metadata yet.

## Current blocker

Capture a successful game-port authentication exchange after the server challenge. We need the
client verification packet, server accept/reject packet, and first authenticated IPL messages.

## Superseded conclusions

- `tAccessRelayS` claim format is no longer unknown.
- Port 26100 is bootstrap, not the complete CD-key authentication service.
- Port 27100 is not established as a fixed simulation port.
- The raw 44-byte challenge inferred from static analysis is not yet reconciled with the
  nSwitch-framed challenge observed on the dynamic port.

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
