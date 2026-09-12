# Project Status

Reviewed 2026-09-11 after retail-client clock validation through turns
1049, 1050, and 1051. The stardate and progress bar advanced with successful
character refreshes and no observed crash or disconnect. This closes the idle
clock test; auction and officer activity across these corrected boundaries
still has separate regression coverage to complete.

Evidence labels used in project documentation:

- **Confirmed:** captured on the wire or reproduced with the retail client.
- **Static finding:** supported by matching SFC3 executable code or serializers.
- **Hypothesis:** plausible but still requiring a focused test.

## Working end to end

- GameSpy-compatible account creation, login, profile lookup, directory/status
  discovery, GT2/nSwitch bootstrap, and dynamic-port security.
- Character creation for all four factions, persistence, login, reconnect, and
  campaign entry.
- Stock 51x34 server-kit map, faction starts, player marker, Center, campaign
  clock, adjacent/multi-hex movement, and restart-stable position.
- Canonical persisted ship identity and configuration shared by every facility.
- Supply Dock buy/sell with capacity, prestige, UI completion, and persistence.
- Refit removal/addition with valid overload behavior, prestige, and persistence.
- Officer review, transfer, cancellation, six-station assignment, and persistence.
- Shipyard catalog, selection, preview, bid, single-player settlement, trade-in,
  and complete winning-ship award.
- Welcome news publication.
- SQLite-authoritative accounts, characters, ships, stores, loadouts, officers,
  campaign clock, auctions, settlements, news, prepared missions, map, and asset
  provenance. First start creates a working campaign from a pristine template.

## Remaining validation

- Two-player auctions: outbid notification, loser refund/accounting,
  simultaneous bids, disconnect/restart, and same-turn settlements.
- Same-template Shipyard bidding needs retail/server-kit validation. Rebuying
  the current hull/loadout can presently turn the trade-in spread into
  repeatable prestige; do not finalize the rule without checking original
  behavior.
- Concurrent players and cross-player notifications.
- Systematic failure paths for insufficient prestige, full capacity, invalid or
  stale requests, timeouts, interrupted transactions, and reconnects.
- Movement needs investigation only if the earlier intermittent multi-hex stall
  becomes reproducible.

## Major missing gameplay

- **Mission availability:** publish a real `tBattleItem`; eligibility alone does
  not enable the Missions button.
- **Tactical launch:** construct `tMatchedMission`, form teams and AI opposition,
  select the host/endpoint, process the client response, and send ready-to-play.
- **Tactical completion:** ingest `tMissionCompleteResults`, returned ships,
  damage, stores, outcome, prestige, rewards, and map consequences exactly once.
- **Recovery:** handle retreat, destruction, tactical disconnect, host loss,
  stale/duplicate results, and campaign restart without trapping a character.
- **Random encounters and simulation:** build these only after one deterministic
  mission can launch, complete, and return safely.
- **Peerchat and multiplayer completeness:** channels, player list, private
  messages, reconnect, rate limiting, and broader concurrency tests.

## Runtime and product direction

- Runtime definitions come from `assets/server-kit`; retail installations remain
  external research/client inputs.
- Future mod layers will override baseline files by relative path without editing
  the released server kit.
- CD-key verification is permissive by default. Before public hosting, move HMAC
  identity binding from characters to accounts and add safe clear/rebind,
  revocation, strict-allowlist management, session revocation, and audit history.
- Add reset-only password administration, backup/restore, schema-driven campaign
  settings, and an operator GUI for health, addresses, ports, reachability, logs,
  accounts, and mods.
- Client resolution/renderer/wrapper work belongs on a separate branch.

## Local-only evidence

Ghidra exports, packet captures, forum raw pages, extracted API archives,
credentials, working databases, and logs remain ignored. Sanitized conclusions
and reproducible archive/search tooling are tracked instead.
