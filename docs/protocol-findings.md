# Protocol Findings

## Transport Layer

All connections use GameSpy GT2 SDK (circa 2002) as transport. Connections are TCP on the client-facing ports.

## Packet Serialization

`nDataStore::tBuffer` format — 4-byte little-endian length prefix followed by payload.

Confirmed by behavioral probing:
- `00 00 00 00` → instant client disconnect (length=0, invalid)
- `01 00 00 00` → client waits ~10s (length=1, waits for body)
- `04 00 00 00 xx xx xx xx` → client waits ~10s (length=4, body present but wrong content)

## Bootstrap Relay (Port 26100)

The replacement prototype reproduces the live server through the client factory response:

```
1. GT2 challenge, response, and accept
2. Client binary hello
3. Server assigns a random switch ID and completes registration
4. Client publishes relay name and tAccessRelayS
5. Server claims tAccessRelayS
6. Client and server exchange version information
7. Server sends CRC/address information and MOTD records
8. Client registers object 2/channel 3
9. Server sends DATA(plen=0) to (assigned_switch_id, 2, 3)
10. Client returns the factory-response relay frame
```

The factory trigger in step 9 was confirmed both against the client and in live TCP stream 42.
The `(switch, object)` tuple is the destination address.

## Legacy Account and Directory Services

- TCP 29901: GPSP account-existence lookup
- TCP 29900: GPCM account creation and login
- TCP 28900: GameSpy server-list query

See `gamespy-protocol.md` for the captured message formats. Account creation transmits its
password in plaintext; raw logs and packet captures are sensitive.

## Dynamic Game-Port Security Exchange

The existing live capture routes the client to TCP port 27632. That connection performs a
second GT2 and nSwitch setup, followed by:

1. Client publication of `tSecurityRelayS`
2. Server claim of that relay
3. Client registration frame
4. Server sends a 55-byte nSwitch-framed challenge
5. Client closes before sending a successful verification response

This supersedes the earlier assumption that CD-key verification occurs directly on port 26100.
The exact challenge schema, `VerifyClientRequest`, and auth result are the current protocol
blockers.

## Key Classes (from ServerPlatform.exe debug symbols)

- `nStoredProcedureArguments::tServerChallengeRequest`
- `nStoredProcedureArguments::tVerifyClientRequest`
- `nAsyncSecurityProcedures::tVerifyClient::IsCDKeyValid`
- `nAsyncSecurityProcedures::tVerifyClient::SetClientAuthenticated`
- `tVerifyClientRequest::GetChallenge` / `GetChallengeReply`

## Source Paths (from debug symbols)

```
C:\Projects\Taldren\Taldren\Projects\SFCTNG\Meta\Servers\Database\StoredProcedures\SECURITYPROCEDURES\ServerChallengeRequest.cpp
C:\Projects\Taldren\Taldren\Projects\SFCTNG\Meta\Servers\Database\StoredProcedures\SECURITYPROCEDURES\VerifyClientRequest.cpp
C:\Projects\Taldren\Taldren\Projects\SFCTNG\Meta\SERVERS\SECURITY\AsyncSecurityProcedures\AsyncSecurityProcedures_ChallengeClient.cpp
C:\Projects\Taldren\Taldren\Projects\SFCTNG\Meta\SERVERS\SECURITY\AsyncSecurityProcedures\AsyncSecurityProcedures_VerifyClient.cpp
```

## IPL Packet Types

The game uses an Interface Packet Layer (IPL) with namespaced packet types:
- `IPL_Character` — player connection, character management
- `IPL_Ship` — ship assignment, repair, stores
- `IPL_Map` — hex movement, terrain, political tension
- `IPL_Database` — logon, scoring, notifications
- `IPL_Goal` — mission goals
- `IPL_Clock` — turn timing
- `IPL_AI` — AI character management

## Campaign movement (capture-confirmed)

The successful live session in `live-login-ethernet-20260902.pcapng` includes a move immediately
before the client entered combat. Raw captures remain local and ignored; the sanitized shapes are:

- Client request: server object 40, channel 41; 12-byte callback, character database ID, signed
  destination X, and signed destination Y.
- Observed request callback: `(switch=6, object=6, channel=0)`; destination `(28,9)`.
- Viewport notifications: client-published `MetaViewPortHandlerNameC`, channel 4.
- Notification body: movement state, character ID, destination X/Y, duration in seconds, packed
  string, and an `at friendly base or planet` byte.
- The live server sent state `1` followed by state `0`. Both captured durations were zero because
  combat followed the move immediately; ordinary movement timing remains to be validated.

Sending these notifications to `PlayerRelayC` was an earlier hypothesis and is superseded by the
capture. The local direct callback response is accepted by the client and starts its movement bar;
the viewport completion notification is what should end that state. Final confirmation requires one
client move after restarting onto the current code.

## Supply Dock and character refresh (capture-confirmed)

The same session provides a complete initial Supply Dock transaction:

- Client request: `tShipRelayS` object 22, channel 7, with callback `(6,6,2)` and character ID.
- Server reply: callback object 6/channel 2 with a 2,654-byte payload.
- The reply begins with success and the live player's full serialized `tShip`, then contains the
  captured store/rate collections. This agrees with the static `tGetSupplyDockInfoReq::tRep`
  serializer in the recovered Ghidra export.

This is not safe to implement as an opaque replay: it embeds live character, ship, officer, and item
state. The next offline step is to finish a field-level `tShip` serializer from the static export and
installed ship profiles, then generate a fresh local response and cover its invariant structure with
tests.

The field-level vector, core/loadout, damage, stores, and rate encoders are now implemented. A
profile parser reads both `Assets\Specs` from a client install and `Assets\Spec` from the dedicated
server kit. It resolves all four local starter defaults, including loadout-to-core aliases such as
`Falcon`/`RomulanFrigate` and `Diamond`/`BorgDiamond`.

Ghidra's `tTNGShipCoreData::ConvertSubStringToWeaponArc` proves that firing arcs are indices into a
44-entry, case-insensitive string table—not computed geometry or weapon-specific values. The table
was recovered directly from `ServerPlatform.exe`; examples include `0_360 = 3`, `300_360 = 9`,
`330_30 = 15`, and `165_195 = 17`. The generated core mapper now converts every installed starter
arc and encodes the six hardpoint vectors, class enumeration, attributes, capacities, and base
numeric fields without replay data.

The top-level `tShip` order is also capture-aligned: database ID/reference count, owner ID, auction
flag, race, class, EPV, class name, ship name, creation turn, `tTNGShip`, damage state, stores state,
flags, and raw hull cost. Channel 7 now returns a wholly generated ship followed by three empty rate
maps. Missing or invalid local specs produce a normal failure response rather than terminating the
session.

The 2026-09-08 controlled live mutation capture adds the complete post-purchase sequence:

- `tShipRelayS` object 22/channel 13 carries a plain 12-byte callback, character ID, ship name,
  and the desired absolute `tStoresState`.
- Its reply is success, a complete updated `tShip`, and the final update-success byte.
- The client then requests Character object 6/channel 13 and Ship object 22/channel 7 again.
- Character channel 13 is `tGetCharacterPrestigeReq`; its nine-byte reply is success, current
  prestige, and lifetime prestige. Ignoring this refresh leaves the client on its intermediary
  black screen even though the purchase has already persisted.
- Retail itself briefly shows that black transition while applying a purchase, so only a transition
  that does not return is erroneous.

Replacement-server validation subsequently confirmed that shuttle, marine, and mine counts and
prestige changes persist across the transaction/re-entry path. The remaining defect is UI completion:
the local client can remain on the black intermediary screen after either buying or selling. In the
observed failing local sequence it re-requested Ship object 22/channel 7 but did not issue the live
server's Character object 6/channel 13 prestige request. One marine purchase also ended in abnormal
client termination. This distinguishes a response/state-transition defect from an economy mutation
or persistence defect.

The generated response now uses the installed capacities and server-kit rates. Damage maxima and
the full economy remain prototype values.

## Refit and Officers mutations (capture-confirmed)

The same 2026-09-08 capture establishes the non-mission mutation envelopes:

- Refit save is Character object 6/channel 38. Unlike asynchronous requests with a marker byte,
  this request begins directly with the 12-byte callback, followed by character ID, ship ID, and
  `tTNGShip`. Retail replies with two success bytes (`01 01`), then services the normal prestige and ship
  refresh requests. The final `tTNGShip` scalar is a float and was `1.0` in the live request.
- Freeing/cancelling an officer review is Character channel 8 and returns one success byte.
- Purchasing/transferring reviewed officers is Character channel 39: a plain 12-byte callback,
  character ID, then a map of officer database IDs to station enums. There is no leading async
  marker; a single assignment is exactly 28 bytes. It returns two success bytes (`01 01`) before the
  prestige/full-ship refresh sequence.

The replacement implements these envelopes and persistence models, but the 2026-09-08 client run did
not validate the mutation paths. The replacement now uses the captured two-byte replies and commits
officer exchanges atomically with outgoing-officer credit. The separate officer-review cancel/free
path is client-validated: it returns to the campaign view without disabling the facility buttons.

News object 27/channel 2 carries a requested story ID after its callback, not a character ID. The
reply is a four-byte success value followed directly by one `tNewsStory`; there is no list-count word.

MissionMatcher object 24/channel 11 returns a four-byte success value followed by the one-byte
`eCanChooseMissionResponses` enum (`01 00 00 00 00` for the observed allowed case). Channel 12's
callback completes with one success byte. Before that completion, retail publishes an approximately
2.8 KiB mission assignment on the client relay at object 15/channel 2; it embeds the selected battle,
current character, and ship state. That publication—not merely the channel 11 eligibility reply—is
the remaining requirement for enabling the Missions button. Captured database IDs must be rebuilt
from the active session rather than replayed.

## Campaign clock and Shipyard settlement observations

Local Shipyard selection, preview, bid increments, bid persistence, closing, and hull award are now
client-observed. A bid on the Sovereign survived relogging and settled after further campaign moves;
the character then loaded with the Sovereign and the updated trade-in value. Settlement therefore
works even though the client-facing clock is suspect. The stardate initially appeared not to advance
and later rendered as `219.1342177` instead of the expected `56200.xx`, indicating a clock serializer
or numeric-format mismatch rather than proof that turns failed to advance.

Multi-hex movement also needs regression coverage. One two-hex diagonal attempt appeared to stall,
while a later three-hex move completed after a short calculation delay. Treat this as intermittent or
path-dependent until packet logs identify whether completion publication was omitted.
