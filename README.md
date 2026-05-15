# SFC3 Dynaverse Server Revival

Reverse engineering and reimplementation effort to restore Star Trek: Starfleet Command III Dynaverse multiplayer on private hardware, without any dependency on the original server software or GameSpy infrastructure.

## Background

The official Taldren/Activision Dynaverse servers went offline around 2004–2008. The original `ServerPlatform.exe` server kit was later released, but it cannot be made to work: it requires GameSpy online services (offline since 2014) and contains an unfixable auth dispatch bug. This project builds a clean-room Python replacement that speaks the native SFC3 wire protocol directly.

## The Core Problem

SFC3 multiplayer has two hard dependencies that are both permanently broken:

1. **GameSpy infrastructure** — CD key validation, peerchat, and directory services all ran on `*.gamespy.com`. Those servers shut down in 2014. The server binary phones home at startup; without a substitute, it aborts.

2. **`ServerPlatform.exe` auth dispatch bug** — Even with GameSpy bypassed, the binary has a code bug where `SecurityServer` never claims the `tAccessRelayS` object published by connecting clients. The client gets stuck waiting for `ServerChallengeRequest` and never authenticates. This happens in both single-process and split-process configurations. No config change fixes it; the bug is in compiled code.

The only viable path is a replacement server that owns both layers.

## Status (2026-05-15)

- [x] Official server kit binaries archived (builds 464, 504, 531, 534, 534b)
- [x] Server binary runs on Windows 11 (XP SP3 compat mode)
- [x] All 16 sub-servers initialize and reach "made public" state
- [x] GameSpy Peerchat dependency bypassed (`fake_peerchat.py`)
- [x] GT2 ASCII handshake protocol fully documented and implemented
- [x] GT2 response hash reverse engineered from SFC3.exe (FUN_007e7580) — secret key confirmed
- [x] Full connection sequence captured with Wireshark; all frame formats confirmed
- [x] Client binary hello, nSwitch setup, and relay publications all working
- [x] `ServerChallengeRequest` wire format confirmed; replacement server sends correct packet
- [ ] Server-side `tAccessRelayS` nSwitch claim — format unknown, blocking `VerifyClientRequest`
- [ ] `VerifyClientRequest` parsing and CD key allowlist validation
- [ ] Dynaverse game simulation (economy, AI, missions, hex map, turn system)
- [ ] In-game chat (GameSpy Peerchat / IRC protocol)

## Approach

A Python asyncio server on ports 26100 (auth) and 27100 (nSwitch) that:

- Speaks the GT2 ASCII negotiation handshake natively
- Computes the correct GT2 challenge/response hash
- Handles the nSwitch binary framing used for all post-handshake traffic
- Validates CD keys against a local allowlist (no GameSpy, no WON accounts)
- Will eventually serve the full Dynaverse campaign simulation

## Protocol Reference

### GT2 ASCII Negotiation (port 26100)

Framing: `0x80  uint16_LE(payload_len_including_null)  <ASCII>  0x00`

```
S→C:  \challenge\<32 random chars>\final\
C→S:  \response\<32-char hash>\challenge\<32 random chars>\port\<port>\data\
S→C:  \accept\1\response\<32-char hash>\port\27100\final\
```

The 32-char hash is computed with a custom algorithm (FUN_007e7580 in SFC3.exe) using a key embedded in the binary at `DAT_0099d6b8`. Each side hashes the *other* side's challenge. Extract the key from your own SFC3.exe installation.

### nSwitch Binary Phase (same TCP connection, after accept)

All frames: `uint16_BE(payload_len)  <payload>`

```
C→S:  00 0c  fe ff ff ff ff ff ff ff  02 00 00 00          (client hello)
S→C:  00 14  ff ff ff ff 00 00 00 00  00 00 00 00  04 00 00 00  01 00 00 00   (ASSIGN_SWITCH_ID)
S→C:  00 1c  ff ff ff ff 00 00 00 00  01 00 00 00  0c 00 00 00  ec 9f 00 00  00 00 00 00  01 00 00 00
S→C:  00 0c  fe ff ff ff ff ff ff ff  03 00 00 00          (REGISTERED)
```

### Client Publication Sequence

After nSwitch setup the client publishes two objects:

**Relay name** (GT2-framed nSwitch, chan 0):
```
nSwitch(switch=0, obj=1, chan=0, plen=59)
  uint32_LE(47) + "ClientConnectRelayNameC_<id>_<ip>"  +  [1]  [2]
```

**tAccessRelayS** (GT2-framed nSwitch, chan 2 — the auth trigger):
```
nSwitch(switch=0, obj=1, chan=2, plen=42)
  01  [1]  [1]  [3]  uint32_LE(25)  " *~Server~* tAccessRelayS"
```

On receiving `tAccessRelayS`, the server must (a) publish its own nSwitch claim [format TBD — this is the current blocker] and (b) send `ServerChallengeRequest`.

### ServerChallengeRequest

Raw bytes, no GT2 or nSwitch wrapper:
```
uint32_LE(40)         ← total content length
uint32_LE(timestamp)  ← Unix time
uint32_LE(32)         ← challenge string length
[32 bytes]            ← random challenge
```

### Auth Exchange

```
S→C:  ServerChallengeRequest  (above)
C→S:  VerifyClientRequest     (challenge reply + CD key from registry + WON login name)
S→C:  auth accept / reject
```

The CD key is read from `HKLM\SOFTWARE\WOW6432Node\Activision\Star Trek Starfleet Command III\KEY`. The replacement server checks it against a configured allowlist. The WON login name (typed at the game's login screen) becomes the player's display name.

## Key Ghidra Symbols (SFC3.exe)

| Address | Symbol |
|---------|--------|
| `007e7580` | `FUN_007e7580` — GT2 response hash function |
| `007e54b0` | GT2 challenge handler (client side) |
| `00948c7c` | `tAccessRelayS` string literal |
| `009865e0` | `tServerChallengeRequest` RTTI |
| `00986580` | `tServerChallengeResponse` RTTI |
| `00986620` | `tVerifyClientRequest` RTTI |
| `0099d6b8` | GT2 secret key (32-byte string — extract from binary) |

## Key Ghidra Symbols (ServerPlatform.exe build 534b)

| Address | Symbol |
|---------|--------|
| `0052327d` | `tChallengeClient::OnChallengeClient` — fires on tAccessRelayS publish |
| `005b16fe` | `tServerChallengeResponse::StreamOut` |
| `00521b93` | `tSecurityRelayS::AllocChallengeClient` |
| `0056c60e` | `tInterfacePacket::StreamOut` |

## Repository Structure

```
docs/           Protocol documentation and findings
tools/          Analysis utilities (fake_peerchat.py, tcp_proxy.py)
server/         Replacement server implementation (server.py)
```

## References

- [SFC Launcher by D4v1ks](https://github.com/D4v1ks/SFC-Launcher) — replaces GameSpy directory/Peerchat; still requires ServerPlatform.exe and does not fix the auth dispatch bug
- GameSpy GT2 SDK (circa 2002) — protocol basis for all SFC3 multiplayer transport
