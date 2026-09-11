// Map every executable-code difference between the retail GOG and modified
// SFC3 clients to its owning function.
// @category SFC3

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;

public class ClassifyClientExecutableDiffs extends GhidraScript {
    private static final String[] ADDRESSES = {
        "004010ec", "004052a7", "004052b2", "0040691b", "0040694d",
        "00406960", "00406963", "00406a32", "00406a37", "00406dab",
        "00406dad", "00406dd8", "00406ddb", "00406dec", "00406def",
        "00406e03", "00461ad4", "00461b03", "00461b08", "00461b21",
        "00461b28", "00461b2f", "00461b36", "00461b3d", "00479bd9",
        "00479be9", "00479bff", "00479c03", "00479c0b", "00479c11",
        "00479c16", "00479c47", "00479c54", "00479c7e", "0048e42d",
        "0048e437", "0048e64c", "0048e7d5", "0049001b", "004904bd",
        "00491074", "00491164", "0049116f", "004a6855", "004a693f",
        "004a69fc", "004a6ab8", "0053ebf4", "00598fe0", "00598fe5",
        "005b31b1", "005b3201", "005b3232", "005b3254", "006202d8",
        "007e7723"
    };

    @Override
    protected void run() throws Exception {
        println("PROGRAM\t" + currentProgram.getExecutablePath());
        println("SHA256\t" + currentProgram.getExecutableSHA256());
        println("ADDRESS\tFUNCTION_ENTRY\tFUNCTION\tINSTRUCTION");
        for (String value : ADDRESSES) {
            Address address = toAddr(value);
            Function function = getFunctionContaining(address);
            Instruction instruction = currentProgram.getListing().getInstructionContaining(address);
            String entry = function == null ? "-" : function.getEntryPoint().toString();
            String name = function == null ? "<no function>" : function.getName();
            String operation = instruction == null ? "<no instruction>" : instruction.toString();
            println(address + "\t" + entry + "\t" + name + "\t" + operation);
        }
    }
}
