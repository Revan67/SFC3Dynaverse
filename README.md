# SFC3 Dynaverse Server Revival

Reverse engineering and reimplementation effort to restore Star Trek: Starfleet Command III Dynaverse multiplayer on private hardware, without any dependency on the original server software or GameSpy infrastructure.

## Background

The official Taldren/Activision Dynaverse servers went offline around 2004–2008. The original `ServerPlatform.exe` server kit was later released, but it cannot be made to work: it requires GameSpy online services (offline since 2014) and contains an unfixable auth dispatch bug. This project builds a clean-room Python replacement that speaks the native SFC3 wire protocol directly.

## The Core Problem

SFC3 multiplayer has two hard dependencies that are both permanently broken:

1. **GameSpy infrastructure** — CD key validation, peerchat, and directory services all ran on `*.gamespy.com`. Those servers shut down in 2014. The server binary phones home at startup; without a substitute, it aborts.

2. **`ServerPlatform.exe` auth dispatch bug** — Even with GameSpy bypassed, the binary has a code bug where `SecurityServer` never claims the `tAccessRelayS` object published by connecting clients. The client gets stuck waiting for `ServerChallengeRequest` and never authenticates. This happens in both single-process and split-process configurations. No config change fixes it; the bug is in compiled code.

The only viable path is a replacement server that owns both layers.

## Status (reviewed 2026-09-02)

- [x] Official server kit binaries archived (builds 464, 504, 531, 534, 534b)
- [x] Server binary runs on Windows 11 (XP SP3 compat mode)
- [x] All 16 sub-servers initialize and reach "made public" state
- [x] GameSpy account/profile request formats captured
- [x] GT2 ASCII handshake protocol fully documented and implemented
- [x] GT2 response hash reverse engineered from SFC3.exe (FUN_007e7580) — secret key confirmed
- [x] Full connection sequence captured with Wireshark; all frame formats confirmed
- [x] Client binary hello, nSwitch setup, and relay publications all working
- [x] Server-side `tAccessRelayS` claim and factory trigger confirmed
- [x] Live directory flow observed through a dynamically assigned game port
- [ ] Capture a successful `tSecurityRelayS` challenge/response on the dynamic game port
- [ ] `VerifyClientRequest` parsing and CD key allowlist validation
- [ ] Dynaverse game simulation (economy, AI, missions, hex map, turn system)
- [ ] In-game chat (GameSpy Peerchat / IRC protocol)

## Approach

A Python asyncio replacement that currently prototypes the bootstrap relay on port 26100 and
the legacy GameSpy account services. The live service assigns a separate game port dynamically;
port 27632 was observed in the existing capture.

The implementation will:

- Speak the GT2 ASCII negotiation handshake natively
- Compute the correct GT2 challenge/response hash
- Handle the nSwitch binary framing used for all post-handshake traffic
- Validate CD keys against a local allowlist (no GameSpy or WON dependency)
- Eventually serve the full Dynaverse campaign simulation

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

The server-side claim format and subsequent factory trigger are confirmed. See
[`docs/protocol-findings.md`](docs/protocol-findings.md) for the complete bootstrap sequence.

### Historical ServerChallengeRequest hypothesis

Static analysis originally suggested this raw serialization:
```
uint32_LE(40)         ← total content length
uint32_LE(timestamp)  ← Unix time
uint32_LE(32)         ← challenge string length
[32 bytes]            ← random challenge
```

The live capture instead shows a security exchange on a dynamically assigned game port,
including `tSecurityRelayS` publication and a 55-byte nSwitch-framed challenge. Its exact
semantic layout and successful client response remain under investigation.

### Intended Auth Exchange

```
S→C:  ServerChallengeRequest
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
server/         Experimental replacement server and multi-port probe
```

Current status and capture procedure:

- [`docs/project-status.md`](docs/project-status.md)
- [`docs/capture-plan.md`](docs/capture-plan.md)
- [`docs/gamespy-protocol.md`](docs/gamespy-protocol.md)
- [`docs/reverse-engineering.md`](docs/reverse-engineering.md)
- [`docs/architecture-plan.md`](docs/architecture-plan.md)
- [`docs/original-server-findings.md`](docs/original-server-findings.md)

## Legal

This project is a clean-room interoperability implementation under **17 U.S.C. § 1201(f)** (DMCA interoperability exception). Reverse engineering was performed solely to achieve interoperability with the SFC3 client for the purpose of private server hosting. No game assets, executable code, or proprietary data are distributed. A legitimate purchase of Star Trek: Starfleet Command III is required to run the client.

The original game and server kit are the property of their respective rights holders (Taldren/Activision/current successors). This project is not affiliated with or endorsed by any of them.

## References

- [SFC Launcher by D4v1ks](https://github.com/D4v1ks/SFC-Launcher) — replaces GameSpy directory/Peerchat; still requires ServerPlatform.exe and does not fix the auth dispatch bug
- GameSpy GT2 SDK (circa 2002) — protocol basis for all SFC3 multiplayer transport
