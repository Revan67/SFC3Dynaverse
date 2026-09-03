# Character Login Protocol

This is the sanitized boundary established by the successful live trace and the first local
end-to-end replacement-server test. Account identifiers and network values are omitted.

## Relay initialization request

After security success, the client publishes `tCharacterRelayS`; the server claims it as object 6.
The client's next frame is addressed to `(0, 6, 3)` and carried a 47-byte payload in both the live
and local tests:

```text
uint32_le return_switch
uint32_le return_object
uint32_le return_channel
uint32_le account_length
byte[account_length] account_identifier
uint32_le address_length
byte[address_length] client_ipv4_text
```

Unlike the security procedure envelope, this request has no leading one-byte marker. The parser
must not log either string.

## Live initialization response

The live server replies to the callback address supplied above, using channel 0. The observed
payload is 233 bytes and begins with a one-byte marker followed by packed strings. It echoes the
client IPv4 text and account identifier, then contains three additional strings of observed
lengths 12, 6, and 11 plus binary session/service state.

Those remaining fields are not yet named. Replaying account-specific captured bytes would be
incorrect; the response must be decoded and generated from local session state. This is the
current implementation boundary.
