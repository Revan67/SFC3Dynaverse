# Initial Hot & Spicy archive findings

This is a targeted first pass over the local forum snapshot, focused on issues
currently encountered by the SFC3 Dynaverse replacement. Treat cross-title
findings as leads rather than proof of SFC3 wire behavior.

## Supply dock and persistence

- In D4v1ks's public SFC2OP server-development thread, supply support required
  reproducing the client's exact cost formulas for shuttles, missiles, fighters,
  marines, mines, and spare parts.
- The same account explicitly says purchases are rejected when the character
  lacks sufficient prestige ("No prestige, no supplies"). This agrees with our
  observed rejection when buying a mine with only one prestige point.
- Mission reports update ship damage and remaining supplies after a mission.
  We must therefore keep campaign supply transactions and post-combat state
  reconciliation as separate protocol paths.

## Missions and combat

- D4v1ks's later SFC2OP design generated mission configuration on the server and
  sent it to SFCLauncher, which wrote a shared INI consumed by two generic mission
  scripts. The game client was then instructed to load the appropriate script.
- This is not evidence that an unmodified SFC3 client uses the same auxiliary
  channel. It is, however, a credible fallback architecture if the stock SFC3
  mission-assignment protocol cannot express the desired missions reliably.
- A forum release named **SFC Programming APIs Y2020** claims to include the APIs
  needed to build missions for all three SFC games. The archived post links to:
  https://www.moddb.com/mods/sfciii-typhon-pact-mod/downloads/sfc-programing-apis-y2020
- A local copy of that package is retained for research at
  `reference/SFC_programing_APIs_Y2020.rar`. The large third-party archive and its
  extraction directory are intentionally excluded from Git.

## Refit and officers

- The first pass found no documented SFC3 packet structures for refit acceptance,
  overload validation, or officer transfer persistence.
- An SFC3 disassembly thread confirms that reopening the recruitment screen can
  refresh the available-officer list. That supports treating the available pool
  as a fresh server response, but it does not document mutation acknowledgements.
- Current refit and officer fixes still need to be driven by captures, executable
  analysis, and server-kit data rather than assumptions from other SFC titles.

## SFCLauncher and client patching

- The launcher author reports replacing two functions in the SFC3 executable to
  add INI-driven GameSpy hosts and custom HD resolution handling. The documented
  keys include `master`, `gpcm`, and `gpsp`; this confirms these are patched-client
  mechanics, not reliable evidence of stock-retail support.
- The launcher also updates `sfc.ini`, registry entries, and firewall rules. These
  are useful references for a future GUI/client-compatibility branch, but should
  remain separate from the server's wire-protocol implementation.

## Other operational clues

- Forum reports describe intermittent Dynaverse server visibility even when the
  server was otherwise running. This reinforces the need for explicit directory
  heartbeat/registration diagnostics in the future GUI.
- The archive did not produce a useful technical description of SFC3 stardate or
  turn-clock serialization in this first pass.

## High-value follow-up references

- Public SFC2OP replacement-server source: https://github.com/D4v1ks/SfcOpServer_Public
- SFC programming APIs for all three games: the Mod DB link above
- `sfc-launcher-a-replacement-for-dynaverse-net-and-g-t19331*`
- `writing-a-new-sfc2op-server-from-scratch-t29568*`
- `disassembly-and-hex-editing-sfc3-t46010*`
- `c-sfc-mission-scripting-t30264*`
