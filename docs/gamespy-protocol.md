# GameSpy Account Protocol Findings

These formats were captured from SFC3 and reproduced by the experimental probe. Examples omit
real account values.

## GPSP: TCP 29901

The client checks whether an email is registered before beginning login:

```text
C -> S: \valid\\email\<email>\final\
S -> C: \vr\1\final\       account exists / identity is valid
S -> C: \vr\0\final\       account does not exist
```

## GPCM: TCP 29900

The server speaks first:

```text
S -> C: \lc\1\challenge\<10 characters>\id\1\final\
```

Account creation:

```text
C -> S: \newuser\\email\<email>\nick\<nick>\password\<plaintext>\productid\10132\id\1\final\
S -> C: \nur\\userid\<uid>\profileid\<pid>\id\1\final\
```

Login:

```text
C -> S: \login\\challenge\<client challenge>\user\<nick>@<email>\response\<proof>\firewall\1\port\0\id\1\final\
S -> C: \lc\2\sesskey\<n>\proof\<server proof>\userid\<uid>\profileid\<pid>\uniquenick\<nick>\id\1\final\
```

The login proofs are lowercase hexadecimal MD5. The SFC3 client uses 48 spaces and the full
`nick@email` identity. In the account-creation follow-up observed locally, its proof places the
client challenge first; the server proof reverses that order:

```text
password_digest = MD5(password).hexdigest()
proof = MD5(
    password_digest
    + 48 spaces
    + user
    + client_challenge
    + server_challenge
    + password_digest
).hexdigest()

server_proof = MD5(
    password_digest
    + 48 spaces
    + user
    + server_challenge
    + client_challenge
    + password_digest
).hexdigest()
```

After login success, TCP 29900 remains open as the GameSpy presence connection. Closing it
immediately causes SFC3 to report login failure. The replacement responds to `\ka\` keepalives and
keeps the session open while the client proceeds to server discovery.

The prototype persists local accounts in ignored `server/accounts.local.json`. It stores the
nickname, numeric IDs, and MD5 password digest required by the legacy proof exchange, never the
plaintext password.

This legacy protocol requires the server to reproduce the password digest. A production account
design must clearly isolate this compatibility constraint and never log passwords or proof data.

## Directory: TCP 28900

The live exchange repeats consistently:

```text
S -> C: \basic\\secure\<6-character challenge>
C -> S: \gamename\sfc3\gamever\2\location\0\validate\<proof>\enctype\2\final\\queryid\1.1\
C -> S: \list\cmp\gamename\sfc3\final\
S -> C: <21-byte enctype-2 compact endpoint record>
```

The compact record decodes to an IPv4 address and UDP query port. The 2026-09-02 trace advertised
the live host's UDP 27633 endpoint. Its captured seven-byte record and stable enctype-2 stream are
implemented in `server/gamespy.py`; the server can substitute a configured IPv4 address without
retaining the original endpoint. The local directory accepts the legacy validation field for
compatibility but does not use it as an authorization boundary.

## Status: UDP 27633

The client sends exactly `\status\`. The server returns plaintext GameSpy key/value metadata,
including `gamename=sfc3`, `gamever=2`, display name, population fields, and `hostport=27632`.
That `hostport` causes the subsequent GT2/nSwitch security connection.

## Security

Raw captures may contain account identifiers, plaintext account-creation passwords, login proofs,
and potentially CD-key material. They are intentionally excluded from version control.
