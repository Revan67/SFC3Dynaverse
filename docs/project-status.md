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
- The game-port security exchange is captured through success and the subsequent
  `tCharacterRelayS` publication.
- TCP 28900 compact directory discovery and UDP 27633 status response are decoded and implemented.
- An unmodified local client reached the first `tCharacterRelayS` login request through the full
  replacement discovery and security route.
- Peerchat starts with plaintext `CRYPT des 1 sfc3`, then switches to encrypted traffic after 705.

## Prototype-only

- `server/server.py` is a focused bootstrap implementation.
- `server/probe.py` combines the bootstrap implementation, permissive GPCM/GPSP responders,
  and raw listeners for suspected ports.
- The account responders do not persist accounts or verify credentials.
- The dynamic security wire helpers have focused unit tests; packaging metadata is still absent.

## Current milestone

The 2026-09-02 Ethernet capture resolved the dynamic-port authentication blocker. It contains the
client verification request, the server's successful security response, character authentication,
initial service-relay setup, mission-matching traffic, and encrypted Peerchat startup.

`server/server.py` now implements discovery through the minimal TCP 27632 security path and the
client's `tCharacterRelayS` publication. The controlled unmodified-client test passed through the
first 47-byte character request. The 233-byte live response has been decoded as a character record
plus a find-result code, and the server now generates a sanitized "not found" response. See
`docs/dynamic-security-protocol.md` for the sanitized wire structure.

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
