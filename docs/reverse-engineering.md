# Reverse-Engineering Notes

These notes preserve the durable results from the original investigation. Function names are
Ghidra-generated unless a debug symbol supplied a class or method name.

## Client target

The compatibility target is the unmodified GOG SFC3 client. `LiveSFC3.exe` is a reference build
used to study the surviving live service; it is not the target executable.

For the analyzed 32-bit client, the observed flat mapping is:

```text
file offset = virtual address - 0x400000
```

Verify this against the specific binary before applying it to another build.

## Client landmarks

| Address | Finding |
| --- | --- |
| `0x007e7580` | GT2 response-hash routine |
| `0x0057bf9b` | Security child-handler constructor |
| `0x0057c0be` | Child channel-0 callback |
| `0x0057c169` | Child channel-1 callback; leads toward CD-key verification request |
| `0x0057c484` | Child channel-2 auth-result callback |
| `0x0057cea4` | Registers the security factory callback |
| `0x0057cf9c` | Security factory; allocates the child handler |
| `0x0057d11f` | Allocates the parent security handler |
| `0x0057d615` | Registers `SecurityRelayC` with nSwitch |
| `0x0079ed90` | Parent allocation and gated directory registration |
| `0x006b7461` | Client-side initialize sender |
| `0x009865e0` | `tServerChallengeRequest` RTTI |
| `0x00986580` | `tServerChallengeResponse` RTTI |
| `0x00986620` | `tVerifyClientRequest` RTTI |

Early client-side Ghidra work also identified fields named `WonUsername`, `WonPassword`,
`WonNick`, and `MetaNewAccount`. UI observation associated the username field with the email
input and the nickname with the display name. This establishes that the legacy account model
contains distinct login, password, nickname, and account-creation state; it does **not** yet prove
which of those fields appear in the dynamic game-port `VerifyClientRequest`. The controlled live
capture must resolve that boundary.

## Security factory pattern

The client security factory is a chain, not a single callback:

1. Allocate the parent handler.
2. Register the channel-connect factory callback.
3. Receive the nSwitch event that fires the factory.
4. Allocate the child handler.
5. Register child data callbacks and advance state.

This is why sending an isolated guessed trigger failed. On the bootstrap connection, the client
does not register object 2/channel 3 until it processes the CRC/address frame. Sending an empty
data frame to `(assigned_switch_id, 2, 3)` afterward produces the factory response.

Treat this chain as a useful pattern for future relay types, but confirm each handler empirically;
not every relay is guaranteed to use identical events or channels.

## Parent-handler vtable highlights

The vtable at `0x008658ec` was read from the client binary. Important slots:

| Slot | Function | Interpretation |
| ---: | --- | --- |
| 3 | `0x0057ce5e` | Gate using the stored return address |
| 4 | `0x0057cea4` | Unconditional factory registration |
| 8 | `0x0079ea9d` | Gated switch-directory registration |
| 12 | `0x0079de92` | Register connect callbacks |
| 14 | `0x006b7461` | Send initialize to the stored return address |
| 22 | `0x0057d11f` | Parent allocator |

Only the first vtable pointer is named in the exported C file. Later slots must be inspected in
Ghidra's listing or read from the binary; searching the C export for their slot addresses does
not work.

## ServerPlatform landmarks

| Address | Symbol/finding |
| --- | --- |
| `0x0052327d` | `tChallengeClient::OnChallengeClient` |
| `0x005b16fe` | `tServerChallengeResponse::StreamOut` |
| `0x00521b93` | `tSecurityRelayS::AllocChallengeClient` |
| `0x0056c60e` | `tInterfacePacket::StreamOut` |

The server-side `tSecurityRelayS::SetupHandlers` analysis identified separate asynchronous
procedure factories by channel:

| Channel | Factory |
| ---: | --- |
| 0 | `AllocInitialize` |
| 2 | `AllocVerifyClient` |
| 3 | `AllocChallengeClient` |
| 4 | `AllocDisconnectAuthenticatedClient` |

`tRelay::SendInitialize` calls nSwitch `SendData` with the registered return address, channel 0,
and a null buffer. This corroborates the empty-data factory-trigger pattern, although the live
capture remains authoritative for its actual destination and ordering.

Static analysis suggested a raw challenge-request serialization and a three-channel security
child. The live dynamic-port trace must be used to reconcile those routines with the observed
nSwitch frames before implementation.

## Reference tooling

- Ghidra for static analysis and C export
- x32dbg for 32-bit runtime breakpoints
- Wireshark/TShark for controlled packet capture

Binary and decompiler paths are deliberately omitted because they are machine-specific.
