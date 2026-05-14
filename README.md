# SFC3 Dynaverse Server Revival

Reverse engineering and reimplementation effort to get the Star Trek: Starfleet Command III Dynaverse multiplayer campaign server running on modern hardware.

## Background

The official Taldren/Activision Dynaverse servers have been offline for ~20 years. This project aims to make private server hosting possible again.

## Status

- [x] Official server kit binaries located and archived
- [x] Server binary runs on Windows 11 (XP SP3 compatibility mode required)
- [x] Protocol analysis in progress — auth handshake structure identified
- [ ] Server initialization failure under investigation
- [ ] Client connection protocol implementation

## Repository Structure

```
docs/           Protocol documentation and findings
server/         Python server implementation (probe harness + future reimplementation)
tools/          Utilities for analysis
```

## Technical Findings

### Server Architecture
- `ServerPlatform.exe` — monolithic Win32 binary launching 16 sub-servers
- CentralSwitch on TCP/UDP 27100, client-facing servers on TCP 26100–26110
- GameSpy GT2 transport layer for all connections
- MySQL or flat-file database backend

### Client Auth Handshake (port 26100)
1. Client connects — server speaks first
2. Server sends `ServerChallengeRequest` (challenge string + required client version)
3. Client responds with `VerifyClientRequest` (CD-key HMAC + WON login)
4. Server validates and authenticates

### Packet Format
`nDataStore` serialization with 4-byte little-endian length prefix confirmed by behavioral testing.

## References

- Server kit builds: 464, 504, 531, 534, 534b (archived)
- Source symbol paths embedded in binary: `C:\Projects\Taldren\Taldren\Projects\SFCTNG\`
