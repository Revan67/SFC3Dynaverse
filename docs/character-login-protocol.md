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

## Initialization response

The response is `IPL_Character::tConnectPlayerReq::tRep` and its nSwitch destination is the
callback address supplied above. It contains a one-byte interface-response marker, a serialized
`tClientCharacter`, and a four-byte `eFindCharacterResponses` value. The live response was 233
bytes because it contained an existing character and one cached ship. It echoes private account
data and must not be replayed verbatim.

Confirmed result values are `0` (found), `1` (not found), `2` (already logged on), `5` (logons
denied), and `6` (banned). The replacement server emits a sanitized 149-byte response containing
a default character and result `1`, allowing a new account to proceed toward character creation.
