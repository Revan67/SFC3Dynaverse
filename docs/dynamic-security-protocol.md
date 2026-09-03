# Dynamic-Port Security Protocol

This specification is derived from the successful live-server exchange in TCP stream 15 of the
2026-09-02 Ethernet capture. Account identifiers, credentials, challenges, proofs, session tokens,
and CD-key-derived data are deliberately omitted.

## Connection setup

The server-list and status responses advertised TCP port 27632. That port begins with the same GT2
negotiation and nSwitch setup used by the bootstrap service, but it publishes a different relay.

1. Complete the GT2 challenge/response negotiation and advertise the dynamic port in the accept.
2. Receive the 14-byte binary hello.
3. Assign a per-connection switch ID and complete the standard nSwitch registration.
4. Receive the client's `tSecurityRelayS` publication at `(0, 1, 2)`.
5. Claim it by sending the decorated relay name to `(assigned_switch_id, 1, 3)`. The claim assigns
   server object ID 2.

The observed decorated security name is 33 bytes:

```text
 *~Server~* .?AVtSecurityRelayS@@
```

The claim payload is:

```text
uint32_le name_length
byte[name_length] decorated_name
uint32_le 0
uint32_le server_object_id       # 2 for security
```

## Asynchronous return envelope

Both client security requests begin with the same 13-byte envelope:

```text
uint8     marker                 # 1
uint32_le return_switch_id
uint32_le return_object_id
uint32_le return_channel
```

The return address must be read from each request rather than inferred from the outer nSwitch
header.

## Challenge

The client sends its initialize request to outer address `(0, 32, 3)`. In the successful capture,
its return address was `(assigned_switch_id, 2, 0x00010001)`.

The server response payload is 37 bytes:

```text
uint32_le 1
uint32_le challenge_length       # 29 observed
byte[challenge_length] challenge
```

The challenge value is session-specific and must not be logged.

## Verification

The client then sends `tVerifyClientRequest` to outer address `(0, 32, 2)`. Its return channel was
`0x00010002`. The observed request payload was 3,353 bytes and began with:

```text
async_return_envelope
uint32_le manifest_entry_count  # 106 observed
... private verification body ...
```

The remaining body contains a file/CRC manifest plus identity and challenge-response fields. A
server may validate its structure without logging or retaining those private fields.

The observed success response is 37 bytes:

```text
uint32_le success                # 1
uint32_le error_code             # 0
uint32_le message_length         # 25
byte[message_length] message     # "Successful security check"
```

It is sent to the return address supplied by the verification request.

## Transition to character services

After accepting the security result, the client publishes `tCharacterRelayS` at `(0, 1, 2)`. The
server claims it with the same claim format, assigning server object ID 6. Character login and the
remaining authenticated IPL messages are the next implementation phase.

## Related live-service observations

- TCP 28900 returns an encoded compact server list.
- UDP 27633 answers `\status\` with GameSpy key/value server metadata and advertises TCP 27632.
- TCP 6667 begins with `CRYPT des 1 sfc3`; traffic after the server's numeric 705 response is
  encrypted, superseding the earlier plaintext-chat hypothesis.
- The captured shutdown was forced with Alt+F4 and ended in TCP resets, so it is not evidence for
  the graceful logout sequence.
