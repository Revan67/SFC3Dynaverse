# Architecture Plan

This is a design direction, not implemented behavior. Dynamic game-port authentication must be
understood before the boundary is finalized.

## Proposed components

- Authentication/bootstrap service: relay bootstrap, GPSP, GPCM, directory, and Peerchat
- Simulation service: campaign state and dynamically advertised game endpoint(s)
- SQLite database as the small-community persistence layer
- One top-level launcher/watchdog for both services

Separating authentication from simulation allows the campaign loop to restart independently, but
Windows subprocess behavior and clean shutdown need explicit testing.

## Initial data model

Suggested entities:

- Accounts: user ID, unique nickname, unique email, legacy password digest, creation time
- Sessions: random session key, account ID, nickname, expiry
- Campaigns: name, state, turn, capacity, creation time
- Campaign players: campaign/account relationship, faction, join time, later ship and score state

Use foreign keys and WAL mode on every SQLite connection. Add migrations before the schema is
considered stable.

## Legacy credential constraint

The GPCM proof requires a reproducible MD5 password digest. A compatibility implementation cannot
replace that value with a one-way modern password hash and still validate the original proof.
Minimize exposure by isolating the account service, restricting database access, never logging the
digest or proof, and documenting the legacy risk to operators.

These are locally managed replacement-server accounts, not accounts administered by GameSpy. The
server therefore needs a **password reset**, never password recovery, workflow. Neither operators nor
users should be able to reveal an existing password or digest. An operator reset should set a new
temporary password (or issue a short-lived, single-use reset token), revoke all active sessions for
the account, require replacement at the next supported login flow, and record a sanitized audit event.
The GUI must identify the account unambiguously, require explicit confirmation, and never place the
new password, legacy digest, or reusable proof in logs. Self-service email recovery is out of scope
until a trusted mail and identity-verification system exists.

## Sessions and CD keys

The recovered design proposed 90-day sessions and one CD key per account, with an optional
allow-all development mode. Those are product decisions, not protocol facts.

An earlier plan correlated CD-key authentication with GPCM by client IP. That is unsafe behind
shared NAT and was based on the now-superseded assumption that verification happened on port
26100. Do not implement that correlation until the dynamic-port auth exchange exposes its actual
session or account linkage.

## Deployment backlog

- Windows client setup utility for reversible hosts-file mappings
- Windows server setup utility for firewall and database initialization
- MOTD file with bounded size and a safe local fallback
- AMP Generic Module template after the service is stable

## Immutable assets and mod overlays

Treat the original server kit—and any external retail installation consulted for research—as
immutable baselines. Operators should never need to edit either tree in place. Resolve every runtime
structured asset by relative path using this order:

1. Server-instance mod overrides, in explicit load order
2. Shared mod overrides, in explicit load order
3. Original server-kit assets
4. Built-in safe defaults, only where the server provides one

An enabled mod mirrors the project asset layout, so a mod containing
`ServerProfiles/Economy.gf` replaces that file without copying or damaging the baseline.
Startup validation should reject path traversal, report conflicts, and generate an effective manifest
containing the enabled mods, load order, file hashes, and selected source for every important asset.
Campaign state should record the effective mod manifest so a changed or missing mod set can be
reported before loading incompatible persistent data.

The future GUI should support adding, enabling, disabling, and ordering mods; show conflicts and the
effective source of a file; validate a mod; and copy a baseline file into a new mod for safe editing.

## GUI status and configuration

The GUI is the intended operator-facing launcher and configuration editor. It should present plain
labels and validation rather than requiring environment-variable knowledge. At minimum it should show:

- Bind/listen addresses, detected local addresses, and the advertised host IP
- Each required TCP/UDP port, whether the local service is listening, Windows Firewall status, and
  whether an external probe can reach it
- A clear distinction between **locally listening**, **firewall allowed**, and **confirmed externally
  reachable**; port forwarding cannot be proven reliably without an outside probe
- Current service health, process IDs, uptime, connected players, and links to sanitized logs
- Effective asset and mod sources, validation problems, and the active mod-manifest hash

Settings should be schema-driven so additional options can be added without redesigning the GUI.
Each setting needs a friendly name, explanation, type, valid range or choices, default, effective
value, source, restart requirement, and optional advanced environment-variable name. Initial settings
include:

- Idle-kick timeout and an option to disable it
- Shipyard auction turns-to-close
- Starting prestige
- Starting ship class/loadout for each faction
- Campaign name, capacity, turn duration, and other server-profile variables
- Bind address, advertised host IP, service ports, and external probe target
- CD-key policy and secret/registration status without ever displaying stored secret material
- Local account administration, including session revocation and reset-only password management

Configuration overrides should live in a server-instance file or mod overlay. The GUI must not rewrite
retail or server-kit files. It should provide reset-to-inherited behavior and preview the effective
value before saving.

The first implementation should add a project-local sibling such as `assets/overrides` beside
`assets/server-kit`. It mirrors the server-kit directory layout and takes precedence without changing
the baseline. For example, host-defined ship additions or replacements can live in
`assets/overrides/Spec/DefaultCore.txt` and `DefaultLoadOut.txt`, while the original released files
remain intact under `assets/server-kit/Spec`. The loader must report which layer supplied each file,
validate ship core/loadout references together, and provide a clean way to disable or remove an
override to return to the bundled default.
