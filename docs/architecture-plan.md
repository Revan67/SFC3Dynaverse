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
