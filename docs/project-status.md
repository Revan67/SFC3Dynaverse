# Project Status

Reviewed 2026-09-09 after reconciling local tests, the controlled retail
capture, both executable decompiles, the released server kit, and archived
community/API material.

Evidence labels used in project documentation:

- **Confirmed:** captured on the wire or reproduced with the retail client.
- **Static finding:** supported by matching SFC3 executable code or serializers.
- **Hypothesis:** plausible but still requiring a focused test.

## Working end to end

- Account creation, login, profile lookup, and local persistence.
- Directory/status discovery, GT2/nSwitch bootstrap, and dynamic-port security.
- Character creation, persistence, login, reconnect, and campaign entry.
- Stock 51x34 server-kit map, faction homeworld start, player marker, and Center.
- Immediate homeworld facility availability.
- Persistent adjacent and multi-hex movement in normal tests.
- Generated starter ship and rendering of Supply Dock, Refit, and Officers.
- Server-kit Shipyard catalog, selection, vessel preview, persistent bids,
  settlement, and award of the selected hull.
- One requested news story and the welcome item.
- Officer review cancellation without disabling the facility buttons.

## Current defects

- **Canonical ship state:** the replacement persists identity, stores, refit, and
  transferred officers in one owned ship instance. SQL reconciliation exposed
  that the other five client-displayed starting officers are synthesized from
  empty template slots and have no server-owned records yet. Complete crew
  materialization remains before this boundary is final.
- **Supply Dock:** counts and prestige persisted in some runs, but buy/sell may
  remain on the intermediary black screen or report that stores could not be
  obtained. One marine test crashed the client.
- **Refit:** every tested mutation reports overload, including removal. The
  client accepts a retail remove/add/save. Matching the retail response tail as
  `prestige:uint32` followed by `economy:float` corrected the wire layout but did
  not clear the overload, so the remaining configuration needs a field-level
  comparison and client-validator trace in Ghidra.
- **Officers:** the latest transfer committed BOWEN to the canonical ship,
  rewrote its station slot, and survived relog. The client later crashed after a
  subsequent review/cancel cycle, which still needs a focused reproduction.
- **Clock:** the replacement derives the recovered five-field structure from
  persisted campaign state and `Time.gf`. Rollover, restart, scheduling, and
  auction-boundary tests pass; the retail client displayed the correct
  `56200.824` stardate and received the next turn publication.
- **Missions:** eligibility and choice replies are insufficient. The client
  requires a published battle item, full matched-mission exchange, and final
  ready-to-play message, so the button remains disabled.
- **Combat:** the static tactical-result schema is recovered, but tactical
  hosting, launch, result ingestion, and campaign consequences are not complete.
- **Movement:** one two-hex diagonal test stalled; later three- and six-hex moves
  succeeded. Investigate only if a focused reproduction captures it.
- **Multiplayer auctions:** winner behavior works for one player. Outbid, loser
  refund, and simultaneous settlement require a second tester.
- **Peerchat:** encrypted in-game chat remains unimplemented.

## Main conclusions

The project is no longer blocked on general connection or serializer discovery.
Facility work now shares one canonical persisted ship instance; the next gates
are verifying its wire representation in the retail client and then completing
each transaction-specific request/refresh sequence.

Mission availability is not an unknown boolean. It requires a real battle item
and the complete assignment/launch state machine. Tactical completion is a
structured DataValidator result containing returned ships and team outcomes,
not the lightweight `BattleResultsReported` lifecycle notification.

See `investigation-evidence-matrix.md` for exact packet ordering, recovered
structures, client decisions, and targeted captures.

## Investigation order

1. Trace whether Refit overload occurs before its network request.
2. Compare facility mutation requests against the immediate, channel-7,
   persisted, and relogged ship representations.
3. Revalidate the complete five-field clock and display update timing.
4. Capture a retail mission from acceptance through the first tactical frame.
5. Reproduce one deterministic local mission launch.
6. Capture and implement one complete tactical result and campaign return.
7. Test the two-player auction loser/refund path.
8. Revisit movement only with a reproducible failing capture.
9. Build random encounters after the deterministic mission loop works.

## Runtime and product direction

- Runtime data comes only from `assets/server-kit`; retail installations remain
  external research/client inputs.
- Future mod overlays will override baseline assets without editing them.
- Persistence will use a normalized, versioned SQLite schema. Retail-client wire
  compatibility is required; compatibility with the original server binary or
  its SQL Server schema is explicitly out of scope.
- The pristine SQLite campaign template is generated from the effective
  server-kit assets. First start copies it atomically to local working state;
  subsequent starts never silently reseed an existing campaign.
- CD-key verification remains permissive by default, with optional HMAC identity
  policies and no raw-key storage.
- The operator GUI should cover service health, addresses, ports, firewall and
  external reachability, campaign variables, mods, logs, and reset-only account
  administration.
- Client resolution/wrapper work belongs on a separate branch.

## Local-only evidence

Ghidra exports, packet captures, forum mirrors, extracted API archives,
credentials, account databases, and logs remain ignored. Sanitized conclusions
and reproducible archive/search tooling are tracked instead.
