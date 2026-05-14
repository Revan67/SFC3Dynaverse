# SFC3 Dynaverse Server Revival

Reverse engineering and reimplementation effort to get the Star Trek: Starfleet Command III Dynaverse multiplayer campaign server running on modern hardware for private hosting.

## Background

The official Taldren/Activision Dynaverse servers have been offline for ~20 years. This project aims to make private server hosting possible again.

## Status (2026-05-14)

- [x] Official server kit binaries located and archived (builds 464, 504, 531, 534, 534b)
- [x] Server binary runs on Windows 11 (XP SP3 compatibility mode required)
- [x] All 16 sub-servers initialize and reach "made public" state
- [x] GameSpy Peerchat dependency bypassed with fake IRC server
- [x] GT2 handshake protocol fully documented
- [x] Client object publication sequence captured and documented
- [x] Auth dispatch bug (`tAccessRelayS`) confirmed unfixable in original binary
- [x] Split-process architecture tested — bug persists regardless of config
- [ ] Replacement server implementation in progress

## The Core Problem — Why the Original Binary Can't Be Used

`ServerPlatform.exe` has an unfixable auth dispatch bug:

1. Client connects and publishes `tAccessRelayS` to CentralSwitch
2. CentralSwitch places it in the temp queue (observed at T+0:25–T+0:32)
3. SecurityServer **never claims the object** — in either single-process or split-process mode
4. Client never receives `ServerChallengeRequest` — stuck on "starting query process"

This is a code bug inside the binary. No config change can fix it. Community research confirmed no public fix exists. The SFC Launcher tool (D4v1ks) replaces GameSpy directory services but still uses `ServerPlatform.exe` and does not fix the auth dispatch.

## Approach: Replacement Server

Building a Python replacement server that speaks the GT2 transport and SFC3 protocol directly, without `ServerPlatform.exe`. Key simplifications over the original:

- No CD key validation against GameSpy (see Auth section below)
- No WON account system
- Full Dynaverse simulation preserved (economy, AI, missions, hex map, turn system)
- No in-game chat required (Discord used instead)

## Technical Findings

### GameSpy Peerchat Dependency

The server binary connects to `peerchat.gamespy.com:6667` at startup for CD key validation. GameSpy went offline in 2014. Fix: redirect `chat.gf` to `127.0.0.1` and run `fake_peerchat.py`.

**Key finding:** Despite sending `CRYPT des 1 sfc3dv`, the SFC3 binary does NOT actually encrypt its IRC output. All communication is plaintext. The fake server does not need to implement the RC4 cipher.

### GT2 Protocol

GameSpy GT2 SDK (circa 2002). Two phases on port 26100:

**Phase 1 — Plaintext key-value handshake (server speaks first):**
```
Server → Client:  \challenge\<32-char-random>\final\
Client → Server:  \response\<hash>\challenge\<new-challenge>\port\<port>\data\
Server → Client:  \accept\1\response\<hash>\port\27100\final\
```

**Phase 2 — Binary frames** (2-byte big-endian length prefix):
```
C→S: 00 0c  fe ff ff ff ff ff ff ff  02 00 00 00                                           (client hello)
S→C: 00 14  ff ff ff ff 00 00 00 00  00 00 00 00 04 00 00 00 01 00 00 00                   (assign Switch ID)
S→C: 00 1c  ff ff ff ff 00 00 00 00  01 00 00 00 0c 00 00 00 84 96 00 00 00 00 00 00 01 00 00 00
S→C: 00 0c  fe ff ff ff ff ff ff ff  03 00 00 00                                           (RegisteredWithCentralSwitch)
```

### Object Publication Sequence

After the GT2 handshake, the client publishes two objects:

**Relay name** (76-byte frame):
```
00 4a  [4b seq] [4b type=1] [4b=0] [4b total=58] [4b strlen=46] [46b name] [4b switchID=1] [4b objectID=2]
       name = "ClientConnectRelayNameC_XXXXXXXX_<client-ip>"
```

**Access relay** (60-byte frame — the auth trigger):
```
00 3a  [header] ... [4b strlen=25] [25b " *~Server~* tAccessRelayS"]
```

On receiving `tAccessRelayS`, the SecurityServer should send `ServerChallengeRequest`. In the original binary, it never does — this is the bug.

### Auth Handshake

When the replacement server receives `tAccessRelayS`:

1. Server sends `ServerChallengeRequest` — random challenge string + required client version
2. Client sends `VerifyClientRequest` — challenge reply, CD key (from registry), WON login name
3. Server validates CD key against allowlist and authenticates

**Auth without client modification:** The CD key field is read from the Windows registry (`HKLM\SOFTWARE\WOW6432Node\Activision\Star Trek Starfleet Command III\KEY`) and sent verbatim. Players can set it to any string. The replacement server treats it as a pre-shared access token — the admin distributes valid key values and the server checks against a configured allowlist. The WON login name (typed freely at the game's login screen) becomes the player's display name.

### Packet Serialization

`nDataStore::tBuffer` — 4-byte little-endian length prefix followed by payload.

### IPL Packet Types

The game communicates via an Interface Packet Layer (IPL):

| Type | Purpose |
|------|---------|
| `IPL_Database` | Logon, scoring, notifications |
| `IPL_Character` | Character management, faction selection |
| `IPL_Ship` | Ship assignment, repair, stores |
| `IPL_Map` | Hex movement, terrain, political tension |
| `IPL_Goal` | Mission goals |
| `IPL_Clock` | Turn timing |
| `IPL_AI` | AI character management |

### Original Server Architecture

- `ServerPlatform.exe` — monolithic Win32 binary spawning 16 sub-servers
- CentralSwitch pub/sub hub on TCP/UDP 27100
- Client-facing auth on TCP 26100 (portproxy → 27100)
- GameSpy GT2 transport for all connections
- MySQL or flat-file database backend; 16-table schema

## Key Debug Symbols (from ServerPlatform.exe)

```
nStoredProcedureArguments::tServerChallengeRequest
nStoredProcedureArguments::tVerifyClientRequest
nAsyncSecurityProcedures::tVerifyClient::IsCDKeyValid
nAsyncSecurityProcedures::tVerifyClient::SetClientAuthenticated
tVerifyClientRequest::GetChallenge / GetChallengeReply
```

Source paths embedded in binary: `C:\Projects\Taldren\Taldren\Projects\SFCTNG\`

## Server Kit Builds

All archived locally. In order of release: 464, 504, 531, 534, 534b (534b is newest and most stable).

## Repository Structure

```
docs/           Protocol documentation and findings
tools/          Analysis utilities (fake_peerchat.py, tcp_proxy.py)
server/         Replacement server implementation (in progress)
```

## References

- [SFC Launcher by D4v1ks](https://github.com/D4v1ks/SFC-Launcher) — replaces GameSpy directory/Peerchat, still requires ServerPlatform.exe, does not fix auth dispatch
