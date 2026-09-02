# Controlled Live Capture Plan

## Objective

Capture one successful session from launcher startup through dynamic game-port authentication and
the first authenticated Dynaverse packets.

## Capture filter

Use a capture filter scoped to the live-server host so the dynamic port is included without
recording unrelated high-volume traffic:

```text
host 70.27.77.102
```

If the live service address changes, resolve and substitute the current address before capture.
Do not restrict the capture to known ports; the assigned game port may vary.

## Test sequence

1. Start capture before launching SFC3.
2. Record the local time of launcher start.
3. Log in using a dedicated test account.
4. Record the time the server list appears.
5. Select the live Dynaverse server.
6. Record the time of character selection, creation, or campaign-map arrival.
7. Remain connected for at least 30 seconds after entering the first authenticated screen.
8. Exit normally and stop the capture.

## Required evidence

- GPSP/GPCM success flow
- 28900 query and returned dynamic endpoint
- Dynamic-port GT2/nSwitch setup
- `tSecurityRelayS` publication and claim
- Server challenge
- Client `VerifyClientRequest`
- Server auth result
- First post-authentication IPL frames

## Handling

- Use a dedicated password not used anywhere else.
- Treat the capture as sensitive because legacy messages may expose credentials or CD-key data.
- Keep the raw capture outside Git.
- Produce a sanitized packet transcript containing only the fields needed for protocol analysis.
