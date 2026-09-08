# Implementation Roadmap

Ordered after the client-validated retail Shipyard browsing milestone.

1. **Implemented:** Persist the campaign clock and advance turns using `Time.gf`.
2. **Implemented; client validation pending:** Shipyard proxy bidding, persistence, turn-based closing,
   settlement, prestige deduction, and award of the selected retail loadout.
3. **Partially wired:** Officer purchase/transfer persistence is implemented and recovered channel 39
   purchase requests are handled. Exact client mutation-response validation remains.
4. **Wired; client validation pending:** Supply Dock channel 13 capacity checks, purchases, prestige
   deduction, persistence, and updated-ship response.
5. **Wired; client validation pending:** Refit channel 38 parsing, validation against retail specs,
   same-hull enforcement, and persistent ship configuration.
6. **Wired; client validation pending:** News retention/publication uses `News.gf` limits and colors;
   channel 2 serializes the retained feed as recovered `tNewsStory` records.
7. **Implemented; client validation pending:** configurable CD-key handling:
   `permissive` by default, with optional `registered` and `strict` policies. Never log or store raw
   keys or reusable proofs. Where stable key material is available, retain only a server-secret HMAC
   identifier unless an operator explicitly enables reversible storage.
   The recovered structural parser isolates the stable access package from both session challenges
   before calculating the identifier. Manual offset/length overrides remain available for variants.
   Raw verification bytes are never logged or stored.
8. **Partially wired:** First mission offer, acceptance, launch, completion, and reward path has
   guarded persistent transitions. Channels 10 and 11 create/acknowledge matching and eligibility;
   channel 12 parses the recovered `tBattleItem`, persists the chosen battle, and acknowledges it.
   Publishing the actual mission assignment to the client remains.

Server-kit and retail data take precedence over packet-derived values. Each state-changing feature
requires serializer tests and persistent-state tests before client validation.
