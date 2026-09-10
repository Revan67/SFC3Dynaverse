// Locate and decompile retail-client functions that reference Refit validation text.
// @category SFC3

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

import java.util.LinkedHashSet;
import java.util.Set;
import java.nio.charset.StandardCharsets;

public class FindRefitValidation extends GhidraScript {
    private static final String[] NEEDLES = {
        "OverLoaded Shield space",
        "OverLoaded Power space",
        "OverLoaded Hull or Bridge space",
        "OverLoaded weapons space"
    };
    private static final String[] ADDRESSES = {
        "0097cfb4", "0097cfd0", "0097cfe8", "0097d00c"
    };
    private static final String[] CODE_ADDRESSES = {
        "006b6948", "006b692f", "006b6916", "006b68fd"
    };

    @Override
    protected void run() throws Exception {
        println("PROGRAM " + currentProgram.getExecutablePath());
        println("SHA256 " + currentProgram.getExecutableSHA256());
        Set<Function> functions = new LinkedHashSet<>();
        Address validatorEntry = toAddr("006b6811");
        disassemble(validatorEntry);
        Function validator = getFunctionAt(validatorEntry);
        if (validator == null) validator = createFunction(validatorEntry, null);
        println("VALIDATOR " + validator);
        if (validator != null) functions.add(validator);
        for (int index = 0; index < NEEDLES.length; index++) {
            String needle = NEEDLES[index];
            Address address = toAddr(ADDRESSES[index]);
            byte[] actual = new byte[needle.length()];
            currentProgram.getMemory().getBytes(address, actual);
            println("STRING " + address + " " + new String(actual, StandardCharsets.US_ASCII));
            for (Reference reference : getReferencesTo(address)) {
                    Function function = getFunctionContaining(reference.getFromAddress());
                    println("  REF " + reference.getFromAddress() + " FUNCTION " + function);
                    if (function != null) functions.add(function);
            }
            Address codeAddress = toAddr(CODE_ADDRESSES[index]);
            Function directFunction = getFunctionContaining(codeAddress);
            println("  DIRECT " + codeAddress + " FUNCTION " + directFunction);
            if (directFunction != null) functions.add(directFunction);
        }

        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        for (Function function : functions) {
            println("\n===== " + function.getName() + " @ " + function.getEntryPoint() + " =====");
            DecompileResults result = decompiler.decompileFunction(function, 120, monitor);
            if (!result.decompileCompleted()) {
                println("DECOMPILE FAILED: " + result.getErrorMessage());
            } else {
                println(result.getDecompiledFunction().getC());
            }
        }
        decompiler.dispose();
    }
}
