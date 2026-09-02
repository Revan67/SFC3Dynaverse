# Original Server Kit Findings

These are sanitized historical findings from experiments with `ServerPlatform.exe` build 534b.
The binaries, profiles, and helper tools referenced by the original session have not yet been
migrated to this machine, so treat details not corroborated by current captures as historical.

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

The captured server traffic reportedly issued a `CRYPT des 1 sfc3dv` negotiation while subsequent
IRC traffic remained plaintext. This should be reconfirmed before implementing Peerchat because the
helper and its capture were not transferred.

Historical channel patterns included faction, global, and system-broadcast channels under the
SFC3 Dynaverse namespace. CD-key validation appeared to use Peerchat callbacks in the original
server. The replacement is not required to reproduce that internal architecture as long as it is
wire-compatible with the client.

## Server-kit versions recorded

The former archive reportedly contained builds 464, 504, 531, 534, and 534b, with 534b used for
the most recent investigation. Build 504 included SQL support and a map editor. The archive path
recorded by Claude is no longer present.

## Missing tools and evidence

- Original server kits and active build-534b profile
- `fake_peerchat.py`
- `tcp_proxy.py`
- PE/CD-key analysis helper
- Client and server Ghidra C exports
- Original Peerchat and split-process logs/captures

If recovered, store proprietary binaries and raw captures outside Git. Commit only clean-room
notes and independently written analysis utilities.

## Superseded product decisions

Early notes proposed accepting every login and omitting in-game chat. Later project decisions
reversed both points: local account/CD-key policy and Peerchat-compatible in-game chat are in scope.
