// Decompile the functions containing the repeatable GOG startup-crash frames.
// @category SFC3

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;

import java.util.LinkedHashSet;
import java.util.Set;

public class InspectStartupCrash extends GhidraScript {
    private static final String[] ADDRESSES = {
        "00407337", "00631b65", "00632653", "00631c20",
        "00406dad", "00406e03", "00461b08", "00479bd9", "00479c16",
        "00479c54", "00479c7e", "005b31b1", "005b3232"
    };

    @Override
    protected void run() throws Exception {
        println("PROGRAM " + currentProgram.getExecutablePath());
        println("SHA256 " + currentProgram.getExecutableSHA256());
        Set<Function> functions = new LinkedHashSet<>();
        for (String value : ADDRESSES) {
            Address address = toAddr(value);
            Function function = getFunctionContaining(address);
            println("FRAME " + address + " FUNCTION " + function);
            if (function != null) {
                functions.add(function);
            }
        }

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

        Address patchCenter = toAddr("00407337");
        println("\n===== INSTRUCTIONS AROUND " + patchCenter + " =====");
        Instruction instruction = currentProgram.getListing().getInstructionContaining(patchCenter.subtract(32));
        if (instruction == null) {
            instruction = currentProgram.getListing().getInstructionAfter(patchCenter.subtract(32));
        }
        while (instruction != null && instruction.getAddress().compareTo(patchCenter.add(32)) <= 0) {
            println(instruction.getAddress() + "  " + instruction);
            instruction = instruction.getNext();
        }
        decompiler.dispose();
    }
}
