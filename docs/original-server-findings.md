# Original Server Kit Findings

These are sanitized historical findings from experiments with `ServerPlatform.exe` build 534b.
The binaries, profiles, and helper tools referenced by the original session have now been
recovered. Details not corroborated by current captures should still be treated as historical.

## Why the replacement path was chosen

With a local Peerchat substitute, the original server initialized its CentralSwitch and service
relays. During client connection, however, `tAccessRelayS` remained unclaimed and the expected
security dispatch did not occur. The same result was observed in both the all-in-one profile and a
split CentralSwitch/all-servers configuration. No configuration-only correction was identified.

This evidence motivated the clean-room replacement. It does not prove that patching the binary is
impossible, only that the available server profiles did not produce a working authentication path.

## Observed server architecture

The original platform hosted CentralSwitch plus services for database, clock, character, economy,
ship, mission matching, news, chat, notification, messaging, security, data validation, information,
AI, goals, and the campaign map.

Historical profiles used CentralSwitch on 27100 and a local forwarding rule from client-facing
26100. This is original-kit topology and must not be confused with the replacement service or the
dynamic game port observed in the surviving live capture.

## Peerchat dependency

The original server attempted to connect to GameSpy Peerchat on TCP 6667 during startup. Pointing
its chat profile at a local substitute allowed blocked relays to initialize and become public.

The new client-side live capture begins with `CRYPT des 1 sfc3`; after numeric 705 the traffic is
encrypted. This supersedes the earlier assumption that subsequent IRC traffic remained plaintext.

Historical channel patterns included faction, global, and system-broadcast channels under the
SFC3 Dynaverse namespace. CD-key validation appeared to use Peerchat callbacks in the original
server. The replacement is not required to reproduce that internal architecture as long as it is
wire-compatible with the client.

## Server-kit versions recorded

The recovered archive at `D:\SFC\sfc3` contains builds 464, 504, 531, 534, and 534b, with 534b used
for the most recent investigation. Build 504 included SQL support and a map editor.

## Recovered tools and evidence

- Original server kits and active profiles: `D:\SFC\sfc3` and `C:\Utilities\SFC3Server`
- Compatibility helpers: `C:\Utilities\Dev\sfc3-compat`
- Extracted build 504: `C:\Utilities\Dev\sfc3-server-504`
- Client/server Ghidra projects and exports: `reference/ghidra`
- Current live capture: `live-login-ethernet-20260902.pcapng`

Older raw Peerchat and split-process captures may still exist only on the previous computer. Keep
proprietary binaries, Ghidra databases/exports, and raw captures out of Git; commit only clean-room
notes and independently written analysis utilities.

## Superseded product decisions

Early notes proposed accepting every login and omitting in-game chat. Later project decisions
reversed both points: local account/CD-key policy and Peerchat-compatible in-game chat are in scope.
