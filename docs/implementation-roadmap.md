# Ordered Milestone Roadmap

Reviewed 2026-09-10. This is the authoritative work order derived from client
tests, retail captures, SFC3 client/server static analysis, server-kit data, and
the archived programming/forum research.

Milestones are dependency-ordered. A milestone is complete only when its exit
criteria pass automated tests and, where specified, the unmodified retail
client. Later work should not hide or work around a failed earlier contract.

## Completed foundation

The project already has a working foundation:

- GameSpy-compatible account/profile services and server discovery.
- GT2/nSwitch bootstrap, dynamic-port security, and configurable CD-key policy.
- Persistent account and character creation/login/reconnect.
- Server-kit map, faction starts, camera, marker, Center, and normal movement.
- Starter-ship generation and facility browsing.
- Shipyard inventory, selection, preview, persistent bids, settlement, and a
  confirmed winning ship award.
- Officer review cancellation and one-story News display.
- Project-local released server-kit runtime assets and a combined launcher.

## Milestone 1 — Canonical campaign clock

**Status: implemented and retail-client validated.**

Build one clock model used by UI snapshots, auctions, missions, persistence, and
simulation. Serialize the recovered five fields with retail semantics:

1. current turn;
2. current year;
3. turns per year;
4. milliseconds per turn;
5. encoded base year.

Work:

- Replace the provisional tuple with values derived from persisted campaign
  state and `ServerProfiles/Time.gf`.
- Define clock publication points and restart behavior.
- Keep auction closing and future mission timing on this same clock.
- Add boundary tests for year rollover and restart elapsed time.

Exit criteria:

- The client displays the expected `56200.xx` progression without malformed or
  stale values.
- Turns advance consistently without requiring player movement.
- An auction closes on the configured turn and remains correct after restart.

Automated validation covers the recovered retail tuple, year rollover,
unsigned field bounds, restart-stable epoch/turn state, next-turn scheduling,
and an auction settlement exactly on its configured turn boundary. Client
validation confirmed a correct `56200.824` display and turn publication.

## Milestone 2 — Canonical `tShip` model and serializer

**Status: implemented and retail-client validated.**

Make one persisted ship representation authoritative for character login,
fleet data, Supply Dock, Refit, Officers, Shipyard awards, channel-7 refresh,
mission launch, tactical return, and relog.

Work:

- Inventory every `tShip`, `tTNGShip`, stores, damage, and officer field.
- Preserve stable database/owner/ship identities across every response.
- Separate immutable server-kit templates from mutable ship instances.
- Stop regenerating mutated state from the stock loadout.
- Add semantic equality tests across every serializer entry point.
- Validate awarded ships as complete configured variants, not bare hull rows.

Exit criteria:

- A ship serialized through every read path has identical identity and mutable
  state.
- Save/restart/relog round trips do not change loadout, stores, damage, name,
  officers, or capacities.
- Existing starter and awarded ships still render correctly.

The persistence boundary now migrates the prototype's detached stores, refit,
and officer fields into the owned ship instance. Fleet data follows the persisted
ship identity, class, and position; facility serializers resolve the same mutable
loadout; and Shipyard awards create a complete configured instance. Automated
tests cover legacy migration, restart equality, cross-facility configuration
equality, and non-starter fleet identity. Client validation passed the exit gate.

Client validation confirms the awarded Sovereign identity, Sovereign A mutable
loadout selection, map marker/Center behavior, and stores `4/3/3` with capacities
`7/21/25`. An officer exchange committed as BOWEN in station 100, updated the
loadout slot, and survived relog. SQL reconciliation exposed an older incomplete
character whose five synthesized crew members had never been materialized. New
characters now receive all six server-owned officer records, and officer/refit
mutations persist through relog.

The released kit's `SQL/CreateTables.sql` confirms that characters, ships,
officers, auctions, and campaign state are separate database entities and that a
ship owns its TNG configuration, damage, and stores. A versioned SQLite schema now
captures those relationships for the replacement server. Runtime migration from
the prototype JSON stores is now an explicit, one-time operator action. SQLite is
the runtime authority for accounts, characters, ships, officers, and campaign
state; production startup no longer reads or maintains JSON shadow state.
The complete migration scope and ordering are tracked in
`sql-migration-inventory.md`.

The recovered `Database.gf` process refined the cutover: schema migration 003
adds campaign bootstrap metadata, the asset manifest, and persisted map records.
`default-campaign.sqlite3` is now built from the server kit and copied atomically
only when a working database does not exist. Legacy JSON stores can be imported
transactionally when explicitly requested, but are not consulted during normal
runtime. Complete validation of every persisted transaction remains an exit gate.

New-character bootstrap is now implemented directly in SQLite. One canonical factory
resolves the faction start and server-kit starter hull, creates mutable stores and
the ordered loadout, materializes all six named officer stations, and inserts the
account, character, ship, stores, items, and officers in one SQLite transaction.
Existing incomplete prototype characters are deliberately not changed by this
path; they require an explicit backfill operation.

## Milestone 3 — Supply Dock transaction loop

**Status: implemented and retail-client validated.**

Complete the retail channel-13 mutation, prestige refresh, and channel-7 ship
refresh sequence.

Investigation gate:

- Capture one affordable local purchase and one local sale from click through
  restored/stuck UI.
- Compare requested absolute counts, immediate returned ship, channel-7 ship,
  persisted record, and relogged ship.
- Identify the exact returned-ship validity or identity field currently rejected
  by the client.

Implementation and exit criteria:

- Buying and selling shuttles, marines, and mines applies capacity, pricing, and
  prestige rules atomically.
- The normal brief black transition returns to Supply Dock without an error,
  disconnect, or crash.
- Counts and prestige agree immediately and after relog.
- Rejected and unaffordable transactions restore usable UI state unchanged.

Client validation confirmed purchases, prestige and absolute counts, the normal
brief black transition back to Supply Dock, and persistence through relog.

## Milestone 4 — Refit validation and persistence

**Status: implemented and retail-client validated.**

Resolve the false overload before expanding configuration features.

Investigation gate:

- Determine whether the client raises overload before sending channel 38.
- Compare a local removal-only attempt with the known-good retail
  remove/add/save capture.
- Trace the client validator when no request is transmitted, including power,
  mass, hardpoints, arcs, installed-item identity, and the final `tTNGShip`
  scalar.
- Use the starter Norway first; test awarded ships separately.

Implementation and exit criteria:

- Remove one valid item, save, relog, add it back, save, and relog.
- The server persists the complete client-produced `tTNGShip` for the same hull.
- Prestige/BPV accounting and the refreshed full ship remain consistent.
- Genuine invalid configurations are rejected without corrupting the ship or
  leaving the UI blocked.

The false overload was traced to incomplete ship serialization. The canonical
ship response now preserves the submitted retail structure; remove/save/relog and
subsequent facility persistence passed client validation.

## Milestone 5 — Officer transfer persistence

**Status: implemented and retail-client validated.**

Persist officer assignments in the canonical ship slots rather than a detached
review roster.

Work:

- Compare the accepted assignment, immediate refresh, channel-7 ship, and
  relogged officer slots.
- Apply outgoing credit, incoming cost, reviewed-candidate release, and target
  station replacement atomically.
- Preserve cancel/free behavior and shared facility-state restoration.

Exit criteria:

- Transfer an officer out and another into a selected station without a crash or
  disconnect.
- The new officer is visible immediately and after restart/relog.
- Prestige and the review pool are correct; cancel leaves all facilities usable.

Transfer, cancellation, six-station assignment, SQLite persistence, and relog
were validated with the retail client.

## Milestone 6 — Facility regression checkpoint

**Status: core single-client paths passed; failure-path and multiplayer breadth remain ongoing.**

Before missions, prove the shared character/ship boundary is stable.

Test matrix:

- Starter and Shipyard-awarded ships.
- All four playable factions and faction homeworlds.
- Supply buy/sell, Refit remove/add, Officer replace/cancel, Shipyard preview/bid,
  repair entry, movement away from and back to a base, restart, and relog.
- Failure paths: insufficient prestige, full capacity, invalid item, stale ship
  ID, timeout, and reconnect.

Exit criteria:

- No transaction crashes, disconnects, permanent black screens, or disabled UI.
- Every mutation has automated serializer/persistence coverage and a recorded
  retail-client result.

## Milestone 7 — Two-player Shipyard auctions

Finish the auction behavior that cannot be proven with one account.

Work and exit criteria:

- Two clients bid on the same ship; current bid and closing state propagate.
- The winner is charged correctly with trade-in treatment.
- The loser is not charged or is refunded according to recovered rules.
- Outbid notification, simultaneous bids, disconnect, restart, and multiple
  same-turn settlements behave deterministically.

This milestone may move after Milestone 10 if a second tester is unavailable; it
must not block single-player mission work.

## Milestone 8 — Battle-item publication and mission availability

Populate the client's real battle-item collection. Eligibility alone does not
enable the Missions button.

Work:

- Generate a deterministic single-player patrol offer from server-kit campaign
  and mission data.
- Publish the complete `tBattleItem` with current session identities.
- Support refresh, selection, decline/expiry, and duplicate-request handling.

Exit criteria:

- Missions lights without movement or relogging.
- The client displays a valid offer and can select it repeatedly without stale
  IDs, blocked controls, or corrupt persistent state.

## Milestone 9 — Matched mission and tactical launch

Implement the complete original launch handshake rather than a success flag.

Investigation gate:

- Capture retail from Accept through the first playable tactical frame.
- Resolve the dynamic host address, port, delayed response/return ID, channel-5
  ready-to-play message, and any secondary tactical connection.

Implementation:

- Build teams and minimal AI opposition.
- Refresh participating ships/characters and mark them tactically playing.
- Push the complete `tMatchedMission` on the client relay.
- Process `tPushMatchedMission::tResponse`, commit the match, publish any clock
  update, and send the final ready-to-play request.
- Recover cleanly from decline, launch failure, timeout, and disconnect.

Exit criteria:

- One deterministic human-versus-AI mission reaches a playable tactical frame
  from the unmodified campaign client.
- Campaign state survives a failed launch and prevents duplicate active battles.

## Milestone 10 — Tactical result ingestion and campaign return

Implement the structured DataValidator result path.

Investigation gate:

- Capture a complete retail battle with recorded pre/post ship, stores,
  prestige, outcome, medal/event, and hex state.

Implementation:

- Parse `tReadyToPlayRequest::tResponse` and `tMissionCompleteResults`.
- Enforce the recovered rule that non-host reports contain exactly one team;
  only the host may report multiple teams.
- Reconcile complete returned ships, damage, stores, prestige, rank, medals,
  campaign events, next mission, team state, and hex consequences.
- Complete the later MissionMatcher lifecycle notification separately.

Exit criteria:

- A completed battle returns the player to a usable campaign UI with correct
  persistent ship and character state.
- Restart/relog preserves the result and cannot apply it twice.

## Milestone 11 — Mission outcomes and recovery

Extend the proven launch/result loop before introducing randomness.

Work and exit criteria:

- Retreat, forfeit, player death, ship destruction, and AI-only survivors.
- Tactical disconnect, host loss, campaign-server restart, stale result, and
  duplicate result handling.
- Fleets, multiple human participants, host/non-host reports, and team rewards.
- Every terminal path clears or advances engagement state without trapping a
  character as tactically active.

## Milestone 12 — Random encounters and campaign simulation

Build random encounters on the deterministic mission foundation.

Work:

- Encounter generation from hex, faction, terrain, economy, and server-kit
  mission matching rules.
- AI population, strategic movement, economy, defense, repairs, ship generation,
  news/events, goals, map control, and regeneration.
- Deterministic seeds or replayable event logs for debugging.

Exit criteria:

- Moving through the map can produce valid encounters that launch, complete,
  and alter persistent campaign state.
- A long-running automated campaign remains internally consistent across
  restart and multiple connected players.

## Milestone 13 — Chat and multiplayer completeness

- Implement compatible Peerchat/IRC behavior, player list, channels, private
  messages, and reconnect handling.
- Validate concurrent movement, facilities, auctions, missions, and campaign
  notifications with several accounts.
- Add rate limits and bounded message/history storage.

## Milestone 14 — Configuration, mods, and administration

- Add `assets/overrides` and later ordered mod layers above immutable
  `assets/server-kit` files.
- Validate paths, paired core/loadout references, conflicts, effective sources,
  hashes, and campaign/mod compatibility.
- Move idle kick, auction duration, starting prestige, faction starting ships,
  turn duration, capacity, ports, and related variables into schema-driven
  instance configuration.
- Move CD-key identity binding from campaign characters to accounts before
  public hosting. Support multiple replaceable HMAC identifiers per account,
  active/revoked state, and no raw-key storage.
- Add operator actions to clear an account's key binding for reinstall/recovery,
  rebind it after the next successful verification, revoke a compromised
  identifier, and explicitly replace a strict-mode allowlist entry. Clearing a
  binding must not modify or bypass the strict allowlist.
- Revoke active sessions after password or key-identity changes and retain only
  sanitized audit data: account, operator, timestamp, action, and reason.
- Add reset-only account password administration and backup/restore/migration
  tooling. Password and key recovery must never expose the original secret.

## Milestone 15 — Operator GUI and deployment

- Start/stop and health for every component, connected players, uptime, and
  sanitized logs.
- Bind, detected local, advertised, and public IP presentation.
- Separate local listener, Windows Firewall, router/NAT, and externally verified
  port status.
- Configuration and mod management without rewriting baseline files.
- Reversible client hostname setup, Windows packaging, service installation,
  backup workflow, and later AMP module support.

## Separate client-compatibility branch

Resolution, scaling, renderer, and GOG-wrapper improvements are deliberately
separate from the server milestones. When started, branch from a stable server
checkpoint and keep binary patching/wrapper research isolated from protocol and
campaign implementation.

## Rules for working the roadmap

- Server-kit data outranks captured content; captures define wire behavior and
  sequencing when distributed files do not.
- Matching SFC3 client/server analysis outranks cross-title forum analogies.
- Raw captures, executables, secrets, and extracted archives stay untracked.
- Each state-changing feature needs parser/serializer, persistence, failure, and
  restart tests before client validation.
- Record the exact client build, server commit, starting state, action, expected
  result, and observed result for every manual validation.
- Do not advance past a failed dependency by adding UI-specific workarounds.
