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

- **Canonical ship state:** Supply Dock, Refit, Officers, channel-7 refresh, and
  relog can serialize different versions of the same ship. This is the likely
  shared boundary behind the next three defects.
- **Supply Dock:** counts and prestige persisted in some runs, but buy/sell may
  remain on the intermediary black screen or report that stores could not be
  obtained. One marine test crashed the client.
- **Refit:** every tested mutation reports overload, including removal. The
  client accepts a retail remove/add/save, so the local configuration needs a
  field-level comparison and client-validator trace.
- **Officers:** transfers no longer crash, but replacement slots do not survive
  relog.
- **Clock:** internal turns advance and settle auctions, but the client has
  displayed stale or malformed stardates. The recovered five-field structure
  needs client validation.
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
Facility work should converge on one canonical persisted `tShip`; success bytes
cannot compensate for disagreement between an immediate mutation reply, the
channel-7 refresh, and the ship returned after relog.

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
