# GOG handoff bundle

Start with `Report/gog-support-report.md`. It summarizes the clean-install
failures, controlled test matrix, isolated corrections, verified hashes, and
requested GOG action.

`Compatibility-Test/` is the complete private reproduction package. On a clean
GOG install, run its installer and always launch through the included launcher.
The installer is reversible and refuses files that do not match the supported
GOG hashes.

`Evidence/` contains the clean-install exception report, debugger transcript,
and representative screenshots. `Analysis-Tools/` contains the Ghidra scripts
used to classify and decompile the executable differences.

No replacement SFC3 executable or SFC3 component DLL is included. The patcher
generates the two corrected game files from the recipient's verified GOG
installation. The included dgVoodoo files are the exact private-test renderer
set used for the successful campaign and combat validation.
