# Implementation Roadmap

Ordered after the client-validated retail Shipyard browsing milestone.

1. **Implemented internally; wire correction and client revalidation pending:** Persist the campaign
   clock and advance turns using `Time.gf`. Auctions advance and settle. Static analysis recovered
   the five client fields as current turn, current year, turns/year, milliseconds/turn, and encoded
   base year. The current replacement tuple is not yet considered client-valid; malformed displays
   such as `219.1342177` must be resolved against the retail values in the evidence matrix.
2. **Client-validated with follow-up needed:** Shipyard proxy bids persist, close after campaign
   movement/turn advancement, and award the selected retail loadout. A Sovereign bid completed and
   the character subsequently loaded with the Sovereign. The UI does not make settlement timing
   obvious, and clock-display correctness remains part of item 1. The bare Sovereign catalog
   template is already over its power budget, so awards now resolve to the stock configured
   `Sovereign A` variant while retaining the Sovereign hull identity.
3. **Partially corrected; canonical-ship persistence still failing:** Officer purchase/transfer uses the
   captured channel 39 request and its two-byte success response. Exchanges now credit outgoing
   officers, charge incoming officers, and commit all assignments atomically. Channel 8 cancel/free
   retains its captured one-byte response.
4. **Partially corrected; response/refresh consistency still failing:** Supply Dock channel 13 capacity checks,
   purchases, prestige deduction, persistence, and updated-ship response are followed by the
   captured Character channel 13 prestige refresh needed to leave the intermediary screen. Purchases
   and sales are evaluated as one net transaction, and half-price shuttle sales no longer round to
   zero. The live server's brief black transition remains the expected baseline.
5. **Partially corrected; client still reports overload:** Refit channel 38 now uses the captured plain
   callback envelope, validates against server-kit specs, enforces the same hull, and persists custom
   items as an overlay on the stock loadout. Its success reply now matches the live two-byte response
   rather than the incomplete one-byte reply associated with the false overload result.
6. **Client-validated for one story:** News channel 2 requests one story ID and returns one
   `tNewsStory`; it is not a character-ID request or a counted story list. The server supplies a
   welcome item when the retained campaign feed is empty.
7. **Implemented; client validation pending:** configurable CD-key handling:
   `permissive` by default, with optional `registered` and `strict` policies. Never log or store raw
   keys or reusable proofs. Where stable key material is available, retain only a server-secret HMAC
   identifier unless an operator explicitly enables reversible storage.
   The recovered structural parser isolates the stable access package from both session challenges
   before calculating the identifier. Manual offset/length overrides remain available for variants.
   Raw verification bytes are never logged or stored.
8. **Partially wired; intentionally last:** First mission offer, acceptance, launch, completion, and reward path has
   guarded persistent transitions. Channels 10 and 11 create/acknowledge matching and eligibility;
   channel 12 parses the recovered `tBattleItem`, persists the chosen battle, and acknowledges it.
   Eligibility and choice replies now match the captured five-byte and one-byte response shapes.
   Publishing the actual mission assignment to the client remains. The local Missions button was
   not enabled. On retail, the controlled reference run opened Missions and accepted an offer before
   the client crashed; that capture is the baseline for later reconciliation.

Server-kit data takes precedence over packet-derived values. Each state-changing feature
requires serializer tests and persistent-state tests before client validation.

## Later platform work

- Add immutable mod overlays with explicit load order, conflict reporting, provenance, hashes, and
  campaign compatibility checks. Begin with a project-local `assets/overrides` layer above
  `assets/server-kit`, using the same relative directory structure. This must support host-added ship
  cores/loadouts without editing the released server-kit files. Never modify the server-kit baseline
  in place.
- Build a non-technical server GUI for service health, host/bind IPs, local listeners, firewall state,
  externally verified port reachability, mods, logs, and schema-driven campaign settings.
- Expose idle kick, auction duration, starting prestige, faction starting ships, turn duration,
  capacity, and future server variables through inherited per-instance overrides.
- After mission assignment is functional, recover combat launch, random-encounter generation,
  battle-result ingestion, and campaign consequence updates as the next gameplay milestone.
- Add local-account administration with password reset (never recovery), active-session revocation,
  temporary/single-use credentials, forced replacement where the client flow permits it, and
  sanitized audit events.
