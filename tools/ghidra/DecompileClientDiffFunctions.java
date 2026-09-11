// Decompile the functions which own executable-code differences between the
// retail GOG and modified SFC3 clients. Optional script arguments select entry
// addresses; the default set focuses on startup and renderer initialization.
// @category SFC3

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

import java.util.LinkedHashSet;
import java.util.Set;

public class DecompileClientDiffFunctions extends GhidraScript {
    private static final String[] DEFAULT_ENTRIES = {
        "004010ad", "004051fd", "004068a6", "004069b4", "00406da2",
        "00479bc7", "00479bfc", "0053ebb3", "00598f80", "006202d0",
        "007e7700"
    };

    @Override
    protected void run() throws Exception {
        String[] requested = getScriptArgs();
        String[] entries = requested.length == 0 ? DEFAULT_ENTRIES : requested;
        Set<Function> functions = new LinkedHashSet<>();
        for (String value : entries) {
            Address address = toAddr(value);
            Function function = getFunctionAt(address);
            if (function == null) {
                function = getFunctionContaining(address);
            }
            if (function != null) {
                functions.add(function);
            } else {
                println("NO_FUNCTION " + address);
            }
        }

        println("PROGRAM " + currentProgram.getExecutablePath());
        println("SHA256 " + currentProgram.getExecutableSHA256());
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        for (Function function : functions) {
            println("\n===== " + function.getName() + " @ " + function.getEntryPoint() + " =====");
            DecompileResults result = decompiler.decompileFunction(function, 120, monitor);
            if (result.decompileCompleted()) {
                println(result.getDecompiledFunction().getC());
            } else {
                println("DECOMPILE FAILED: " + result.getErrorMessage());
            }
        }
        decompiler.dispose();
    }
}
