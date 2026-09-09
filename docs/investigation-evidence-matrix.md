# Protocol Investigation Evidence Matrix

This document is the investigation-only reconciliation pass begun after the
2026-09-08 retail reference run. It separates confirmed retail behavior from
static executable evidence, cross-title forum leads, and replacement-server
observations. Historical implementation notes elsewhere in the repository may
describe superseded hypotheses; the evidence below takes precedence.

No implementation decisions should be made from a forum analogy alone. The
priority order is retail/server-kit data, controlled SFC3 captures, matching
SFC3 executable behavior, SFC3 API declarations, and finally cross-title leads.

## Evidence sources

| Source | Scope | Evidentiary weight |
|---|---|---|
| `captures/live-clock-supply-reference-20260908-125700.pcapng` | Retail server session covering Supply Dock, Shipyard, Refit, Officers, and mission selection | Primary wire reference |
| `reference/ghidra/ServerPlatform.exe.c` | Original SFC3 server platform serializers and handlers | Primary static reference |
| `reference/ghidra/SFC3.exe.c` | Retail client behavior and data consumers | Primary static reference |
| `assets/server-kit` | Released SFC3 server profiles, maps, specs, loadouts, and settings | Primary data reference |
| `reference/SFC_programing_APIs_Y2020/` | SFC3 scripting interfaces and mission source | Semantic/API reference; not campaign wire source |
| `reference/forum-archive/hotandspicy/` | SFCLauncher, SFC3, and cross-title development history | Supporting leads only |
| Replacement client tests reported in this task | Current externally visible behavior | Regression evidence |

The retail capture's Dynaverse stream is TCP
`192.168.0.55:65455 <-> 70.27.77.102:27632`. Its nSwitch stream was reassembled
before interpreting application frames; individual TCP packet boundaries are
not application-message boundaries.

## Current findings

| Area | Retail/capture evidence | Static/API evidence | Current replacement observation | Finding and next proof |
|---|---|---|---|---|
| Campaign clock | Retail publishes five little-endian integers: turn `93528`, current year `9`, turns/year `10000`, milliseconds/turn `120000`, base year `56200`. The same snapshot is sent to two registered clock callbacks. | `tCurrentTime::StreamOut` writes offsets `+0x0c,+0x10,+0x14,+0x18,+0x1c`. Database fields name them `CurrentTurn`, `CurrentYear`, `CurrentTurnsPerYear`, `CurrentMilliSecondsPerTurn`, and `CurrentBaseYear`. `GetYear()` computes turn divided by turns/year. `Time.gf` supplies `10000`, `120000`, and `56200`. | Auctions settled under the old provisional tuple, while the client displayed malformed values such as `219.1` and `219.1342177`. The replacement now derives the complete tuple from persisted state and `Time.gf`; client validation displayed `56200.824` and the server published the next turn normally. | **Implemented and client validated.** Automated tests cover the exact recovered retail tuple, rollover, restart stability, next-turn scheduling, and auction settlement boundaries. |
| Supply transaction | Client sends Ship object 22/channel 13 with callback, character ID, ship name, and absolute stores. On success it requests Character channel 13 (prestige) and Ship channel 7 (full ship). Retail briefly shows black while this completes, then restores Supply Dock. | `tUpdateStoresReq::tRep` is response status, full `tShip`, then one-byte `updated` flag. The original server clamps absolute counts to capacity, calculates the net prestige delta at item-specific rates, persists character and ship, and notifies prestige changes. | Counts/persistence have sometimes updated, but buy/sell can remain black; a marine purchase once crashed. In a failing low-prestige test, a mine costing four was correctly unaffordable. | **Likely malformed/inconsistent update reply, not missing UI command.** The client initiates the two refreshes only after accepting the channel-13 response. Compare the returned `tShip` byte-for-byte by field with the requested absolute stores and with the subsequent channel-7 ship. Capture one local transaction from click through restored/stuck UI. |
| Refit | Client sends Character object 6/channel 38: callback, character ID, ship ID, complete client-produced `tTNGShip`. Retail responds `01 01`, then the client requests prestige and full ship. A retail remove/add/save completed. | Original `PurchaseConfigChanges` checks ship ownership, computes the submitted-versus-current BPV delta, charges prestige, copies the submitted `tTNGShip` into the persisted `tShip`, calls `ShipRefitted`, and updates the character ship. There is no separate server overload test in this handler. API headers enumerate overload validation categories but omit the validating implementation. | Every local mutation produces overload, including removal. The awarded Sovereign template/loadout has also been suspected of an invalid power budget. | **Overload is most likely client validation of an inconsistent returned/refreshed `tTNGShip`, not a retail server rejection.** Preserve the client-submitted structure as the canonical refit result and ensure the follow-up full ship is semantically identical. A local capture should include one removal-only save and its refreshed ship. |
| Officer review and transfer | Opening review uses Character channels 27/12/26 and a review relay. Free/cancel uses channel 8 and returns one success byte. Purchase uses channel 39; one assignment is 28 bytes and receives `01 01`, a user message, prestige refresh, and full-ship refresh. | The original handler treats the request map as selected reviewed officer IDs mapped to station enums. Unselected reviewed officers are released. It computes incoming worth minus outgoing officer value, updates prestige, replaces officer slots in the actual `tShip`, and persists that ship. | Cancel no longer disables facilities and transfers no longer crash, but replacing Bair/Harrison or assigning Bowen did not survive relog. | **Persistence must live in the serialized ship officer slots.** A detached roster or review-pool update is insufficient if channel 7 regenerates officers from stock loadout data. Compare the post-transfer ship response and relog ship at each officer item field. |
| Shipyard | Retail inventory, selection, preview, bid, and award were observed. The reference server settled a test bid immediately; that timing is not a retail-baseline requirement. | Server-kit ship specs/loadouts are authoritative inventory data. Original economy handlers expose auction ships, bids, close-bids, scrap, and award flows. | Rows highlight, preview selects the right hull, bids persist, and a settled bid awarded a Sovereign. Losing/outbid behavior is untested. | Core single-player path is working. Remaining proof needs two clients: outbid notification, loser refund/accounting, winner charge/trade-in, and simultaneous settlement. |
| News | Retail uses News object 27/channel 2 with a requested story ID and one story response. | Static serializer returns one `tNewsStory`, not a counted list. | Welcome story now renders. | Functionally confirmed for one story. Later test paging, missing IDs, and retained campaign feed. |
| Movement | Retail and local traffic use direct move response plus viewport state publication/completion. | Original server distinguishes automatic move, must-head-to-hex, movement completion, and battle-trigger paths. | One-, three-, and six-hex moves have completed; a two-hex diagonal move once stalled. | Treat as intermittent until a failing local capture proves whether callback, viewport completion, or battle matching is absent. Add deterministic path tests before changing logic. |
| Mission availability | Retail client claims MissionMatcher, sends channel 11 eligibility, receives five bytes `01 00 00 00 00`, sends channel 12 choice, receives an object 15/channel 2 assignment of 2,824 bytes, acknowledges object 21/channel 0, and receives completion. | The channel-2 object is confirmed as `nStoredProcedureArguments::tPushMatchedMission`, whose payload is a complete `tMatchedMission`. `ChooseMission` builds teams and AI, refreshes ships and characters, marks them tactically playing, increments battles played, pushes the assignment, waits for `tPushMatchedMission::tResponse`, commits the match, optionally updates the clock, then sends channel 5 `tReadyToPlayRequest(0)`. `tDynaverseScriptInfo` describes the corresponding script-facing handoff. | Missions button remains disabled because eligibility alone does not publish an assignment. | **Confirmed missing assignment/launch state machine.** This is not one missing success flag: the replacement must construct a valid `tMatchedMission`, process the client's response, maintain tactical-playing state, and send the final go-play message. Captured database IDs cannot be replayed. One clean retail launch capture is still needed to validate dynamic address/return-ID semantics. |
| Tactical completion/combat | Retail reference run accepted a mission and the client then crashed; it did not capture a completed battle report. | Tactical completion is a `tReadyToPlayRequest::tResponse` sent to DataValidator channel 2. It contains reporter ID, mission name, three booleans (host, mission-complete, reporter/dead-team state), and `tMissionCompleteResults`. Those results contain the battle hex and a vector of `tTeamMissionCompleteResults`; each team result serializes team slot, character ID, returned ships, victory/prestige/bonus values, next-mission title/score, medal/campaign-event values, and death/status flags. DataValidator validates host scope, reloads characters, applies ship/character results, rank/prestige, medals, campaign events, post-mission team state and hex control, then notifies MissionMatcher. `BattleResultsReported(characterID)` is only the later lightweight lifecycle notification, not the result body. | Not implemented/validated as a complete loop. Random encounters are a later milestone. | **Static architecture is recovered; wire values are not yet capture-validated.** After launch works, capture one clean completed battle from assignment through campaign return. Then add separate retreat/forfeit and damaged/stores-used cases. Do not conflate the DataValidator result document with MissionMatcher's completion notification. |

## Exact retail workflow ordering

The following ordering is capture-confirmed. Callback object/channel numbers are
session-selected; service object/channel numbers are stable within the observed
retail protocol.

## Client-side decision points

The retail client decompile closes several gaps that were ambiguous from server
code and captures alone:

- Facility availability is a shared client state. Refit, Officers, Supply Dock,
  and Shipyard are enabled from the same facility-eligibility flag and are
  disabled together during an outstanding transition. A completion/cancel path
  must restore that state; returning a success byte without completing the
  client callback can leave every facility disabled until movement republishes
  location state.
- The Missions button is different. `FUN_0058180a` searches the client's
  published battle-item collection and returns no selectable item when that
  collection is empty. Mission eligibility by itself therefore cannot light the
  button; the client must receive a real battle item before selection and the
  matched-mission handshake after selection.
- Refit entry (`FUN_00581c57` / `FUN_00581e46`) requests the current ship ID and
  validates the database identifier at response offset `+0x10` before copying
  the returned `tTNGShip` at `+0x20`. An invalid identity produces "Ship config
  information not available" without opening a usable editor. The decompile
  does not yet prove which specific local design validator raises the later
  overload dialog, so that part still needs either a focused debugger trace or
  comparison against a known-good retail `tTNGShip`.
- Officer review (`FUN_00581f60` / `FUN_005821ce`) only marks the review data
  ready when the response contains at least one complete `0x198`-byte officer
  record. An empty vector deliberately produces "There were no officers
  available." Once accepted, persistence still depends on the refreshed ship's
  actual officer slots.
- Supply Dock first validates the returned full ship's internal valid flag
  (observed at response-relative offset `+0x464`). Only the valid path extracts
  the three absolute store counts and constructs the dock state. The update
  callback then closes/restores the active panel and relies on the normal full
  ship refresh. A malformed full ship can therefore explain both "Could not get
  ship stores information" and a permanent intermediary black screen even when
  the database counts changed correctly.
- Tactical completion is also checked on the client: the result vector must be
  non-empty, and a non-host report must contain exactly one team result. This
  independently confirms the server-side host/non-host trimming rule and rules
  out a lightweight battle-complete flag as an adequate result message.

### Supply Dock

1. Client -> Ship `22/13`: update absolute stores.
2. Server -> request callback: status + updated full ship + updated flag.
3. Client -> Character `6/13`: request current and lifetime prestige.
4. Server -> callback: success + two prestige values.
5. Client -> Ship `22/7`: request Supply Dock/full ship information.
6. Server -> callback: success + full ship + item/rate collections.

The temporary black screen lies between steps 1 and 6. A permanent black screen
means the client rejected or never completed this state machine.

### Refit

1. Client -> Character `6/38`: character ID, ship ID, submitted `tTNGShip`.
2. Server -> callback: `01 01`.
3. Client requests prestige and full ship using the normal refresh paths.
4. Server returns the persisted refitted ship.

### Officers

1. Client obtains officers in review and current ship/officers.
2. Optional client -> Character `6/8`: release/cancel review; server returns `01`.
3. Client -> Character `6/39`: map of reviewed officer IDs to target stations.
4. Server -> callback: `01 01`, then sends the assignment message.
5. Client requests prestige and full ship; the new officer must already occupy
   the target slot in that returned ship.

### Mission selection

1. Claim the MissionMatcher relay.
2. Client -> MissionMatcher `24/11`: verify eligibility.
3. Server -> callback: four-byte success plus one-byte response enum.
4. Client -> MissionMatcher `24/12`: selected `tBattleItem`.
5. Server builds `tMatchedMission`, marks all participants tactically playing,
   increments battles played, and persists those character updates.
6. Server -> client relay `15/2`: `tPushMatchedMission` request containing the
   generated `tMatchedMission` and a delayed-response address/ID.
7. Client -> relay `21/0`: `tPushMatchedMission::tResponse`, including the
   tactical host address and mission return ID.
8. Server stores the matched mission, optionally refreshes the campaign clock,
   then -> client relay `15/5`: `tReadyToPlayRequest(0)`, the final go-play
   message.
9. Server clears the temporary prepared-mission state and completes the choice
   request.

The captured `tMatchedMission` field order is serializer-confirmed as: date and
time, mission name, mission type/state, campaign clock, hex point, map filename,
four mission strings, three integer settings, two mission-location structures,
playing-team vector, three additional integer settings, and the final location
specification. Some field names inside the decompiler remain ambiguous, but the
container order and types are no longer speculative.

### Tactical result return

1. Tactical host produces a `tReadyToPlayRequest::tResponse` for DataValidator
   channel 2. Non-host reports are trimmed to their own team; only the host may
   report multiple teams.
2. The response identifies the reporting character and mission, carries three
   status booleans, and embeds `tMissionCompleteResults`.
3. `tMissionCompleteResults` carries the battle hex and a vector of team
   results. Each team result includes the character ID, complete returned ship
   vector, victory/economy/continuation values, and terminal-state flags.
4. DataValidator reloads the affected characters, reconciles returned ships,
   updates next mission, prestige, rank, medals, last-battle rating and campaign
   events, persists the characters, applies post-mission team and hex updates,
   and emits client notifications.
5. DataValidator informs MissionMatcher that processing is complete;
   `BattleResultsReported(characterID)` advances/removes engagement state but
   does not carry tactical results itself.

## Investigation gaps and targeted captures

No new broad capture is needed. The remaining useful captures are narrow and
should each begin before opening the relevant facility and end after returning
to the campaign view or reproducing the failure:

1. Local Supply Dock: buy one affordable item, then separately sell one item.
2. Local Refit: remove one item only, accept, relog; later add it back.
3. Local Officers: record the outgoing officer, incoming review ID and station,
   accept, return to map, and relog.
4. Local movement only if a multi-hex stall reproduces.
5. Retail mission launch, from clicking Accept through tactical loading and the
   first playable frame. This validates the dynamic host address, return ID,
   channel-5 go-play message, and any secondary tactical connection.
6. Retail mission completion, from a known pre-battle character/ship state
   through return to the campaign. Record victory level, damage, expended
   stores, prestige, medal/event, and resulting hex ownership.
7. Retail retreat or forfeit as a separate result case; it follows different
   server policy and must not be inferred from a normal victory.
8. Two-client auction only when a second tester is available.

For Supply, Refit, and Officers, the decisive comparison is not merely response
length or success bytes. It is semantic equality between the mutation request,
the immediate returned ship (where applicable), the follow-up channel-7 ship,
and the ship returned after relog.

## Working conclusions before reassessment

- Clock display has a confirmed five-field semantic mismatch.
- Supply Dock is primarily a response/refresh consistency defect; economy
  persistence has already worked in several runs.
- Refit overload is most plausibly caused by invalid regenerated ship state.
- Officer transfers were stored outside the ship instance, while other paths
  regenerated the stock loadout. Stores, refit items, and officer assignments
  now migrate into and persist under one owned ship; automated cross-path and
  restart equality tests pass, and a BOWEN transfer survived client relog.
- Mission availability requires a generated assignment publication, not another
  eligibility flag. The original launch is a request/response/final-go sequence.
- The tactical result schema and server-side consequences are statically known,
  but exact live values and the tactical connection transition require one clean
  launch-and-completion capture.
- Random encounters use the same assignment/result foundation and should follow
  a deterministic accepted mission rather than being investigated in parallel.

## Reassessed implementation order

This is an investigation conclusion, not authorization to change code:

1. Correct the five-field campaign clock so every later time-dependent feature
   (auctions, mission timing, UI stardate) shares one valid model.
2. Validate the newly canonical serialized `tShip` across Supply Dock, Refit,
   Officers, channel-7 refresh, persistence, and relog. The three current
   facility defects may still expose transaction-specific wire mismatches.
3. Re-run the three narrow local mutation captures and compare request,
   immediate response, refresh response, and relog state field-by-field.
4. Implement the complete `tPushMatchedMission` assignment handshake and prove
   a deterministic mission reaches tactical play.
5. Capture and implement `tReadyToPlayRequest::tResponse` ingestion through
   DataValidator, initially for a single human and AI opposition.
6. Add retreat/forfeit, disconnect recovery, fleets/multiple humans, and only
   then random encounter generation.
