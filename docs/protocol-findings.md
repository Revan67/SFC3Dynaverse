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
