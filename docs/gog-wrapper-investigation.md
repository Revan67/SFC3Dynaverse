# GOG Client Wrapper Investigation

## Scope

Establish the unmodified GOG release as the authoritative SFC3 client while
making startup and display behavior reproducible on current Windows systems.
This branch does not modify the retail executable or redistribute GOG files.

## Confirmed installation chain

GOG's primary play task and installed shortcut both launch `SFC3.exe` directly
with the installation directory as the working directory. The compatibility
components are installed beside it:

- `ddraw.dll` — GOG.com DirectX 1–7 wrapper 1.1.0.2135
- `x3d8.dll` — GOG.com DirectX 8 wrapper 1.0.0.4183
- `dxcfg.exe` — wrapper configuration UI
- `dxcfg.ini` — wrapper settings

An earlier installation also contained `dgVoodooCpl.exe`. A clean reinstall
removed it, confirming that it was contamination rather than part of the
current GOG baseline. The GOG install script explicitly deletes `d3d8.dll`.

The installed wrapper configuration currently requests desktop display,
application-controlled presentation and VSync, aspect correction, and fit
scaling.

## Evidence

### Startup crash requires a client-and-launch combination

Static inspection showed that FadedSpark's launcher uses
`System.Diagnostics.ProcessStartInfo` with no arguments, the game directory as
`WorkingDirectory`, and `UseShellExecute = false`.

The modified test executable faults when opened through the Windows shell but
reached the main menu when independently started with those direct-process
semantics. It remained responsive and wrote no new exception report. However,
the authoritative clean GOG executable still produced the identical
`USER32.dll!DispatchMessageW` failure under the same direct-process launch.
Therefore neither the launcher nor the modified executable is independently
sufficient: the verified working baseline is the modified client plus direct
process creation. `Start-GogSfc3.ps1` defaults to the verified process-creation
method, while `-UseShellStart` retains the shell path for controlled comparison.

The existing `UnhandledException.log` records an access violation in GOG's
`ddraw.dll`, in `CompleteCreateSysmemSurface`. This makes the wrapper a proven
failure site rather than merely a suspect.

After a clean reinstall, a default launch reported failure to open
`./Assets/Sprites/sprites.q3`, although that file exists, followed by
`fTest3D.mInit() failed` at `shellApp.cpp:538`. Forcing the installation
directory as the process working directory produced the identical failure,
excluding the shortcut working directory as its cause.

The controlled renderer matrix established two distinct failures:

- Stock GOG fullscreen (`windowed=0`) fails inside GOG `ddraw.dll` at
  `CompleteCreateSysmemSurface`.
- Windowed mode gets past that failure but consistently faults through
  `USER32!DispatchMessageW`, with SFC3 frames `0x00407337`, `0x00631b65`, and
  `0x00632653`.

The second failure is unchanged with GOG's `x3d8.dll`, dgVoodoo, and the
Microsoft Direct3D 8 DLL from the archived Windows 10 fix. It is consequently
a client UI/state failure exposed after 3D initialization, not a particular
Direct3D wrapper failure. The GOG wrapper and original INI were restored after
the matrix.

A live x32dbg capture further established that:

- the last registered window message before the first state tick is `0xC0AF`,
  Windows' normal `TaskbarButtonCreated` notification;
- the state callback at `0x00407325` receives the valid global object
  `ECX=0x0099DE20` and returns to the main loop at `0x00631b65`;
- DirectDraw initializes afterward, then USER32 faults while reading address
  `0x00000004`;
- disabling Discord's per-game hook does not change the address, registers, or
  SFC3 stack frames, so Discord is excluded as the cause;
- AMD's `amdihk32.dll` is injected immediately before the fault and remains the
  next third-party overlay variable to exclude.

Fresh Ghidra projects for both executables confirm that the message loop and
code around `0x00407337` are byte-identical. The older working executable is
modified elsewhere: it replaces retail `resmode` handling with arbitrary
`Width`/`Height`, adds direct `[gamespy]` endpoint reads, and changes factional
shuttle-name handling. It is useful evidence for reconstructing compatible
startup state, but it is not a clean retail control or a drop-in proof that a
wrapper alone fixes startup.

The machine-wide 32-bit Activision registry key currently points at the older
installation under the user's Downloads directory, not the GOG installation.
The shortcut's working directory is nevertheless correct. Static analysis
confirms that SFC3 reads the registry `KEY` value for authentication and reads
`InstallDrive` in an old setup-data code path. We have not established that
normal asset loading uses `InstallPath`, so the registry mismatch and graphics
wrapper crash must be tested independently.

The older client has modified CommonSettings data. For example, it assigns a
mass of 200 to `LIGHT CUTTING BEAM`, while clean GOG retail assigns 150. That
difference caused the Borg Diamond refit overload. Tests described as retail
must therefore launch the GOG executable with the GOG directory as its working
directory.

## Confirmed retail-derived compatibility set

Patch isolation against the hash-verified GOG executable produced a minimum
working client configuration. It reached an interactive main menu, started a
campaign, and entered combat with all of the following:

- `StartupDimensions` and `DisplayModeTransition` executable patch groups;
- the corrected `TAL3DEngineR.dll` byte ranges;
- the complete tested dgVoodoo DirectDraw/Direct3D set, with GOG's `x3d8.dll`
  disabled; and
- direct process creation with the game directory as the working directory.

Removing either executable group showed their separate roles. The untouched
retail executable and the startup-dimensions-only candidate both retain the
same `USER32!DispatchMessageW` crash. The display-transition-only candidate
does not crash, but its main menu cannot be interacted with. Both groups
together produce a working UI.

The GOG and corrected `TAL3DEngineR.dll` files differ by 59 bytes across 11
ranges. With the two EXE groups and GOG's original DLL, the client reports that
it cannot load the `TAL3DEngine` component. Applying the recovered ranges
resolves that failure.

The separately tested `DisplayGate` community change is not required. It
activates the obsolete check demanding a 16-bit-color Windows desktop and is
deliberately excluded from the patch.

The reversible installer verifies exact GOG input hashes, generates the two
corrected game files, deploys the tested renderer, disables conflicting
`x3d8.dll`, and can restore every original GOG file. A clean-copy validation
confirmed both the expected patched hashes and exact restoration hashes.

## Non-mutating diagnostic

Run:

```powershell
pwsh -File tools/gog-wrapper/Test-GogSfc3Installation.ps1 -InstallRoot 'C:\path\to\SFC3'
```

The command reports required-file hashes and versions, wrapper configuration,
the relevant registry values, whether the registered install path matches the
tested installation, and the latest SFC3 exception log. It does not launch the
game or change the registry.

To launch with a guaranteed working directory, run:

```powershell
pwsh -File tools/gog-wrapper/Start-GogSfc3.ps1 -InstallRoot 'C:\path\to\SFC3'
```

Add `-Wait` to report the process exit code and whether the exception log was
updated. This launcher does not change the registry or wrapper configuration.

The `-WindowedCompatibility` switch applies only the five renderer settings
shared by the archived Windows 8.1/10 fixes (`BlueLight`, `windowed`,
`resmode`, `driver`, and `Specularity`). It first preserves the complete file
as `sfc.ini.pre-wrapper-test`; it does not copy gameplay, account, sound, or AI
settings from the downloaded fixes.

Use `-WindowedOnly` to change only `windowed=1`, retaining GOG's selected
adapter and resolution mode. Use `-RestoreSettings` to restore the complete
pre-test INI before launching.

## Remaining test matrix

1. Decompile and document the 59-byte `TAL3DEngineR.dll` correction by
   function and behavior.
2. Test whether each dgVoodoo runtime DLL is individually required after the
   client corrections are present.
3. Validate additional resolutions, DPI scales, multi-monitor arrangements,
   Alt-Tab behavior, and longer combat sessions.
4. Test the private package on independent hardware and a second clean GOG
   installation.
5. Replace the temporary PowerShell launcher with a supported end-user launcher
   only after the compatibility set is stable across systems.

No wrapper binaries or retail assets should be committed. Configuration and
diagnostic tooling may be tracked once validated.
