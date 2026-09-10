# SQL Migration Inventory

This inventory covers durable replacement-server state. The retail SFC3 client
does not connect to SQL: it communicates with the server over GameSpy and
GT2/nSwitch, and the server converts database records into retail wire objects.
Consequently, the replacement schema may differ from Taldren's SQL Server schema
without affecting the client. Stable database IDs, ownership, field semantics,
and wire serialization must still match client expectations.

Compatibility with the original `ServerPlatform.exe` is explicitly out of scope.
Its tables and blob columns are retained only as behavioral and ownership
evidence. The replacement database is free to use normalized tables, foreign-key
constraints, transactions, and versioned migrations suited to the new server.

## Existing state to migrate

| Current source | Current data | SQLite destination | Notes |
|---|---|---|---|
| `accounts.local.json` | Email/account key, nickname, legacy MD5 password proof, GameSpy user ID and profile ID | `accounts` plus an authentication-credential table | Preserve numeric GameSpy IDs. Credentials need algorithm/version metadata and later administrative password reset support. Never store raw passwords or CD keys. |
| `characters.local.json` | Character identity, account association, address, race, map ID, rank/rating defaults, prestige, location, homeworld, destination, flags, verification identifier, mission history | `characters` and character-history tables | Account and character are different identities. Support one character per campaign initially without preventing multiple campaigns later. IP/client address is operational metadata, not identity. |
| Nested character `ship` | Ship/owner IDs, name, hull/loadout identity, class, EPV/BPV, scalar damage, flags, creation turn | `ships` | Ship ID and owner ID must remain stable across login, fleet, facilities, mission launch, tactical return, and relog. A character may eventually own a fleet of up to three ships. |
| Nested ship `refit.items` | Ordered complete loadout item strings and selected loadout name | `ship_loadout_items` and `ships.loadout_name` | Ordering is significant. Server-kit rows are immutable templates; these rows are the mutable instance configuration. |
| Nested ship `stores` | Shuttle, marine, and mine counts | `ship_stores` | Expand for transporter IDs, 25 item-slot current/max values, desired counts, spare parts, and any tactical store fields recovered later. |
| Nested ship `officers` | Officer ID, name, station, worth | `officers` | Expand to the full officer profile, skills, race, base/review location, and transfer state. Enforce one officer per ship station. |
| `campaign.local.json` clock fields | Epoch and initial turn | `campaigns` | Clock configuration remains sourced from `Time.gf`; persisted epoch/turn anchor lives in SQL. |
| `campaign.local.json` auctions | Catalog item ID, owner account, current/max bid, escrow, bid turn, closing state | `auctions` plus auction-settlement history | Reference bidder by character ID and auctioned ship by ship ID. Settlement, prestige debit, ownership transfer, and refund must be one transaction. |
| `campaign.local.json` auction settlements | Winner, ship, class, price, turn | `auction_settlements` | Append-only audit/history table; currently absent from `schema.sql`. |
| `campaign.local.json` news | IDs, next ID, turn/timestamp, channel, priority, persistence, sequence, text | `news_stories` and campaign sequence state | Add all recovered `NewsStory` fields rather than only the current prototype subset. |
| `campaign.local.json` missions | IDs, next ID, account, title/type/reward/status/turn, accepted battle item | `prepared_missions`, mission participants, and mission-event/result tables | The current JSON envelope can remain temporarily in `mission_json`, but launch/result work should normalize ownership, participants, state transitions, and rewards. |
| Per-connection memory | Current character/record, relay addresses, verification handshake, session key, sockets | Usually not durable | Keep live transport state in memory. Persist only explicit reconnect/recovery tokens or active mission reservations if later required. |

## Durable state not yet represented completely

The following comes from Taldren's schema, recovered APIs, or planned server
features and must be added before the corresponding subsystem is considered
complete:

1. **Campaign definition and lifecycle** — template/name/description, difficulty,
   race and mission lists, trigger mission/prestige, versions, player limits,
   game-over state, and current clock snapshot.
2. **Mutable strategic map** — map dimensions and every hex's political owner,
   planet/base type, terrain, base/current economy, victory, and speed values.
3. **Political tension matrix** — matrix dimensions/data plus ally and neutral
   thresholds.
4. **Full character state** — medals, battle result/count, disrepute, mission
   slot, movement completion, hail, personality, goals, language, last logon,
   must-play position, fleet name/leader/members/dismissed ships, open bids, and
   played-mission history.
5. **Full ship state** — system and hardpoint damage arrays, complete stores
   vectors, transporter IDs, raw hull cost, auction state, configuration scalar,
   and multiple-ship fleet ownership.
6. **Full officers** — serialized skill/profile values, race, assigned ship and
   station, at-base location/class/race, review reservation, and market lifecycle.
7. **Notifications and goals** — queued recipient/event/data references and
   durable AI/character goal actors/actions.
8. **Mission and tactical recovery** — prepared profiles, nearby characters,
   battle assignment, teams/participants/ships, launch tokens, results,
   retreat/forfeit/disconnect state, rewards, damage, and post-battle return.
9. **Auction accounting** — losing bidder refunds, escrow ledger, settlement
   events, simultaneous-close safety, and catalog rotation/history.
10. **Moderation and authentication administration** — bans, password-reset
    audit/revocation, credential versions, login audit/rate limiting, and optional
    email verification if that feature is later chosen.
11. **Operator configuration overrides** — definition files remain in
    `server-kit`/future `mods`, while their resolved manifest and all instantiated
    mutable campaign state are recorded in SQL.

## Recovered campaign bootstrap lifecycle

`ServerProfiles/Database.gf` documents the original lifecycle: the server first
loads or generates its flat in-memory campaign and `TransferFromFlat=1` performs
a one-time transfer into empty SQL tables. It explicitly warns that the SQL
tables must be reset and empty. We mirror that behavior without retaining the
original SQL Server binary:

1. `build_default_database.py` reads the effective server-kit assets and builds
   `default-campaign.sqlite3` with schema migrations, campaign clock, strategic
   map records, and an asset manifest.
2. The template contains no accounts, player characters, or player ships.
3. On first start only, the server atomically copies the template to
   `campaign.local.sqlite3` and anchors the working campaign epoch.
4. Later starts migrate and reopen the working database without copying or
   reseeding it.
5. Character creation instantiates the selected starter ship, mutable
   stores/loadout, and all six starting officers from the effective definitions
   in one transaction. SQLite is the authoritative runtime read/write path.

Changing asset files never silently mutates an existing campaign. The stored
manifest hash provides the future operator UI with enough information to warn
about a mismatch and offer an explicit migration or new-campaign operation.

## Migration order

1. **Complete:** add missing credential, settlement, import-ledger, bootstrap
   manifest, map, and clock tables through schema migration 003.
2. **Complete for the one-time importer:** transactionally import the current
   account, campaign, character, ship, store, loadout, officer, settlement, news,
   auction, and mission records. Imports are content-hash tracked, idempotent for
   unchanged files, reject changed sources, and roll back as a unit on failure.
3. **Complete:** repository interfaces now cover accounts, campaigns, characters,
   ships, auctions, news, and missions.
4. **Complete for current fixtures:** verify stable IDs, ownership, prestige,
   loadout order, stores, officers, and campaign state against canonical snapshots.
5. **Complete:** switch production runtime reads and writes to SQLite; JSON is
   available only to explicit migration tooling and unit-test fallbacks.
6. Validate restart, rollback, and interrupted-transaction behavior against the
   retail client before declaring the cutover complete.
7. Validate multi-account auction ownership and settlement before combat work.

The first local import completed at schema version 2 with one account, one
character, one Sovereign A ship, stores `4/3/3`, BOWEN in station 100, 26 ordered
loadout items, and one historical auction settlement. An immediate second import
was a no-op, confirming idempotency. Reconciliation also exposed that only BOWEN
exists in source persistence; the five other client-displayed crew members were
never materialized by the prototype server. That imported fixture is historical
evidence only. Newly created characters now materialize all six starting officers
directly in the authoritative database.

## Data that should not become mutable campaign rows

- Static server-kit and future mod definitions remain files. The template stores
  their hashes/provenance and the mutable state instantiated from them.
- Packet captures, Ghidra projects/decompiles, forum archives, and research notes.
- Logs and private diagnostic captures.
- Raw CD keys, raw passwords, transient GameSpy challenges, session keys, socket
  addresses, or relay object addresses.
