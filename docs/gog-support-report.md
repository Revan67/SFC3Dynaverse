# Star Trek: Starfleet Command III — GOG compatibility report

## Executive summary

The current GOG release of *Star Trek: Starfleet Command III* version 1.01,
build 534, does not start reliably on the tested current Windows system. A
clean reinstall exhibits two repeatable startup failures: a fullscreen access
violation in GOG's DirectDraw wrapper, or a later windowed access violation in
`USER32!DispatchMessageW`.

We isolated a retail-derived compatibility set that reaches an interactive
main menu, starts a campaign, and enters combat. It requires:

1. two small display-initialization corrections to the verified GOG
   `SFC3.exe`;
2. a 59-byte correction to GOG's `Components/TAL3DEngineR.dll`;
3. the tested dgVoodoo DirectDraw/Direct3D wrapper files, with GOG's
   `x3d8.dll` disabled; and
4. direct process creation with the game folder as the working directory.

The enclosed reversible patcher generates the corrected game files from a
clean GOG installation. It verifies every input and output hash and preserves
the original files. No replacement game executable or game DLL is included.

## Test environment

- Windows NT version: `10.0.26200.9168` (64-bit)
- Game: version 1.01, build 534
- GOG game ID: `1156468375`
- Authoritative installation: clean GOG reinstall
- Testing date: September 10, 2026

Hardware details can be supplied separately if required.

## Verified GOG inputs

| File | Version | SHA-256 |
| --- | --- | --- |
| `SFC3.exe` | 1.01 | `1717552A3033356BB3BAE095F9CBD358658BEE8839FA94895EE06B4A33A274ED` |
| `Components/TAL3DEngineR.dll` | — | `064ACB22EF62876F2A19B215E5872F40D68233A60C935A64900C155445A1902D` |
| `ddraw.dll` | GOG 1.1.0.2135 | `20C3FA4A1B23B6C287DBF04E92C0364F2088D0F605148F365937AE3429702F6F` |
| `x3d8.dll` | GOG 1.0.0.4183 | `120880B76BAB31DF02790E76E74E33D719DA465D66ED3730125079A88E7C9CE0` |

## Clean-install failures

### Fullscreen wrapper failure

With the stock fullscreen configuration, `SFC3.exe` raises an access violation
in GOG's `ddraw.dll`, in or below `CompleteCreateSysmemSurface`.

### Windowed message-dispatch failure

Windowed mode gets beyond initial surface creation but repeatedly fails with:

```text
Unhandled Exception! in Version 1.01 Build 534
SFC3.exe caused an EXCEPTION_ACCESS_VIOLATION in module USER32.dll
at DispatchMessageW()+0100 byte(s)

EAX=001AFE24 EBX=FFFFFFFF ECX=00000000 EDX=00000001
ESI=FFFFFFFF EDI=00000000 EBP=001AFE34 ESP=001AFDE4

USER32.dll  DispatchMessageW()+0100
USER32.dll  DispatchMessageA()+0017
SFC3.exe    00407337
SFC3.exe    00631B65
SFC3.exe    00632653
```

Live debugging recorded a null-adjacent read at `0x00000004`. The SFC3 message
loop at `0x00407337` is byte-identical in retail and the working comparison,
indicating that earlier display initialization leaves invalid state for the
message dispatch rather than `USER32.dll` being the underlying defect.

## Controls that did not fix the retail client

- Explicitly setting the game directory as the working directory.
- Direct-process launch by itself.
- Disabling Discord's SFC3 overlay/hook.
- GOG wrapper configuration changes.
- Replacing only DirectDraw with dgVoodoo.
- Using the complete dgVoodoo set without the executable corrections.
- Using the complete dgVoodoo set with GOG's `x3d8.dll` removed.
- Substituting the corrected `TAL3DEngineR.dll` without the EXE corrections.
- Applying only the `StartupDimensions` EXE correction.

## Isolated executable corrections

The patcher applies two groups to the exact verified GOG executable:

- `StartupDimensions`: replaces fixed 768/1024 initialization with the client
  functions used by the known-working build.
- `DisplayModeTransition`: restores the post-cinematic display transition
  logic used before entering the main UI.

Controlled tests established their separate roles:

| Candidate | Result |
| --- | --- |
| Untouched retail EXE + corrected engine DLL | Same USER32 crash |
| `StartupDimensions` only | Same USER32 crash |
| `DisplayModeTransition` only | No crash, but main menu cannot be interacted with |
| Both groups | Interactive main menu; campaign and combat succeed |

A third community change called `DisplayGate` was tested and rejected. It
causes the obsolete dialog requiring the Windows desktop to use 16-bit color.
It is not part of the compatibility patch.

Corrected EXE SHA-256:
`418BBC17C044096C5727307E14AC5302211EAA4834065B6324891FAFACCD04D3`

## TAL3DEngine correction

With both EXE corrections but GOG's original `TAL3DEngineR.dll`, startup fails
with an explicit component-load error for `TAL3DEngine`. The independently
recovered working DLL differs by only 59 bytes in 11 ranges. Applying those
same verified changes to GOG's DLL resolves the component failure.

Corrected DLL SHA-256:
`44CBAB768106CE68BA8AA780533F14C274EE8E3864EE13337665B93905D80DCE`

The package does not distribute that game DLL; the installer generates it from
the exact GOG input.

## Renderer and launch requirements

The successful test used these included dgVoodoo files:

| File | SHA-256 |
| --- | --- |
| `DDraw.dll` | `838EE34F17309CA4CD515407883A247DB5FA90FE58261C6615FF5CC74FE71E4D` |
| `D3D8.dll` | `4E17A6C7DB146B13A873C09BF56C74DC5D92C252A2A122F01C1FA1B327BC1396` |
| `D3DImm.dll` | `5F93B9FB7A77ACAFC259A57D3294A0EE70125A8AF8A0A1975AF4CBA818229947` |
| `dgVoodoo.conf` | `145C41683B6E5B52CA739993629BDB5A8703153B9025A7277E4B2481AB6BA140` |

GOG's `x3d8.dll` is disabled for this configuration. The game must be launched
using `ProcessStartInfo.UseShellExecute = false` with the installation folder
as `WorkingDirectory`. Directly opening the same working executable through
the Windows shell reproduced the USER32 crash.

## Validation performed

The complete compatibility set was tested through cinematics, an interactive
main menu, campaign creation/loading, and entering combat.

The patcher was separately validated against clean copies of all affected GOG
files. Installation produced every expected hash, and restoration returned the
EXE, engine DLL, GOG `ddraw.dll`, and GOG `x3d8.dll` to their exact original
hashes while removing the added dgVoodoo files.

## Requested GOG action

1. Reproduce the clean-install fullscreen and windowed failures on current
   Windows builds.
2. Review the enclosed `StartupDimensions` and `DisplayModeTransition` byte
   corrections against the retail source/build history.
3. Review the 59-byte `TAL3DEngineR.dll` difference and replace the affected
   GOG component with the correct build.
4. Replace or update the existing GOG DirectDraw/Direct3D wrapper profile.
5. Change the GOG launch task to direct process creation with the installation
   directory as the working directory.
6. Regression-test cinematics, menus, campaign startup, combat, Alt-Tab,
   multiple resolutions, display scaling, and multi-monitor systems.

## Bundle contents

- This report and the detailed investigation notes.
- A reversible, hash-verified compatibility installer and launcher.
- Exact tested dgVoodoo runtime files and configuration.
- Patch manifest with supported input and expected output hashes.
- Installation diagnostic script.
- Exception reports and debugger transcript.
- Representative screenshots of the observed failures.
- Ghidra comparison scripts used to classify the relevant executable changes.
