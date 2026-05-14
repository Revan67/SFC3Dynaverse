# Protocol Findings

## Transport Layer

All connections use GameSpy GT2 SDK (circa 2002) as transport. Connections are TCP on the client-facing ports.

## Packet Serialization

`nDataStore::tBuffer` format — 4-byte little-endian length prefix followed by payload.

Confirmed by behavioral probing:
- `00 00 00 00` → instant client disconnect (length=0, invalid)
- `01 00 00 00` → client waits ~10s (length=1, waits for body)
- `04 00 00 00 xx xx xx xx` → client waits ~10s (length=4, body present but wrong content)

## Client Auth Handshake (Port 26100)

Server speaks first. Sequence:

```
Client → TCP connect
Server → ServerChallengeRequest packet
             [uint32 length]
             [packet type enum]
             [challenge string (random)]
             [validclientver string]
Client → VerifyClientRequest packet
             [uint32 length]
             [packet type enum]
             [challenge reply (CD-key HMAC)]
             [CD key]
             [WON login name]
Server → auth result
```

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
