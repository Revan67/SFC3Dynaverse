# SFC3 GOG compatibility test package

This experimental patch targets only the GOG release of *Star Trek: Starfleet
Command III*, version 1.01 build 534. It does not contain or distribute the
game's executable or component DLL. The installer verifies the original GOG
files before applying the tested byte-level corrections and preserves backups.

## Prerequisites

1. Start from a clean GOG installation.
2. Close SFC3. The included installer deploys the tested dgVoodoo files and
   disables GOG's conflicting `x3d8.dll` automatically.

The validated renderer file hashes were:

| File | SHA-256 |
| --- | --- |
| `DDraw.dll` | `838EE34F17309CA4CD515407883A247DB5FA90FE58261C6615FF5CC74FE71E4D` |
| `D3D8.dll` | `4E17A6C7DB146B13A873C09BF56C74DC5D92C252A2A122F01C1FA1B327BC1396` |
| `D3DImm.dll` | `5F93B9FB7A77ACAFC259A57D3294A0EE70125A8AF8A0A1975AF4CBA818229947` |

## Install and launch

Open PowerShell in this package directory and run:

```powershell
.\Install-Sfc3CompatibilityPatch.ps1 -InstallRoot 'C:\path\to\your\GOG\SFC3'
.\Start-GogSfc3.ps1 -InstallRoot 'C:\path\to\your\GOG\SFC3'
```

Always use `Start-GogSfc3.ps1` for this test. Directly opening `SFC3.exe` uses
different Windows launch semantics and is known to crash.

The confirmed test path reached an interactive main menu, created/loaded a
campaign, and entered combat.

## Restore original GOG files

```powershell
.\Install-Sfc3CompatibilityPatch.ps1 -InstallRoot 'C:\path\to\your\GOG\SFC3' -Restore
```

Restoration also removes the installed dgVoodoo files and restores GOG's
original `ddraw.dll` and `x3d8.dll`.

## Report results

Record whether the test reached each stage: cinematics, main menu, campaign,
and combat. Include any `UnhandledException.log` generated in the game folder,
your Windows version, GPU model, and driver version.
