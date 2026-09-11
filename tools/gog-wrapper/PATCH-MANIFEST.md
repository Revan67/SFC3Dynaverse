# SFC3 GOG compatibility patch manifest

Experimental tester build: `0.1`

This private test package does not contain the game executable or game DLLs.
It includes the exact dgVoodoo binaries and configuration used in the
successful compatibility test.

## Supported GOG inputs

| File | SHA-256 |
| --- | --- |
| `SFC3.exe` | `1717552A3033356BB3BAE095F9CBD358658BEE8839FA94895EE06B4A33A274ED` |
| `Components/TAL3DEngineR.dll` | `064ACB22EF62876F2A19B215E5872F40D68233A60C935A64900C155445A1902D` |

## Verified patched outputs

| File | SHA-256 |
| --- | --- |
| `SFC3.exe` | `418BBC17C044096C5727307E14AC5302211EAA4834065B6324891FAFACCD04D3` |
| `Components/TAL3DEngineR.dll` | `44CBAB768106CE68BA8AA780533F14C274EE8E3864EE13337665B93905D80DCE` |

The EXE output includes only the confirmed `StartupDimensions` and
`DisplayModeTransition` groups. It does not include the rejected legacy
`DisplayGate` change.
