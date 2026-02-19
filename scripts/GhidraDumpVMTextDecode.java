// Dump VM/text-decode related functions from Ghidra headless.
// @category Lang5

import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.Arrays;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;

public class GhidraDumpVMTextDecode extends GhidraScript {

    private static final long[] TARGETS = new long[] {
        0x8001D198L,
        0x8001D354L,
        0x8001D3D4L,
        0x8001D4A8L,
        0x8001D738L,
        0x8001DADCL,
        0x800216C8L,
        0x800216FCL,
        0x80022A84L,
        0x80022B24L,
        0x80022C04L,
        0x80022E2CL,
        0x80023324L,
        0x80023340L,
        0x80023938L,
        0x80023BA4L,
        0x80023FACL,
        0x800241CCL,
        0x800A36B4L,
        0x800A3E24L,
        0x800A87E0L,
        0x800B2638L,
        0x800B27BCL,
    };

    @Override
    public void run() throws Exception {
        File out = new File("/workspace/work/scen_analysis/ghidra_vm_text_decode_dump.txt");
        out.getParentFile().mkdirs();

        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        try (PrintWriter pw = new PrintWriter(new FileWriter(out))) {
            pw.println("Program: " + currentProgram.getName());
            pw.println("Language: " + currentProgram.getLanguageID());
            pw.println();

            for (long ea : TARGETS) {
                Address a = toAddr(ea);
                disassemble(a);
                Function fn = getFunctionContaining(a);
                if (fn == null) {
                    try {
                        fn = createFunction(a, "FUN_" + Long.toHexString(ea).toUpperCase());
                    } catch (Exception ignored) {
                        fn = getFunctionContaining(a);
                    }
                }

                pw.println("==== TARGET 0x" + String.format("%08X", ea) + " ====");
                if (fn == null) {
                    pw.println("No function object; raw disasm only");
                } else {
                    pw.println("Function: " + fn.getName() + " @ " + fn.getEntryPoint());
                    pw.println("Xrefs:");
                    Reference[] refs = getReferencesTo(fn.getEntryPoint());
                    if (refs.length == 0) {
                        pw.println("  (none)");
                    } else {
                        Arrays.sort(refs, (r1, r2) -> r1.getFromAddress().compareTo(r2.getFromAddress()));
                        for (Reference r : refs) {
                            pw.println("  from " + r.getFromAddress() + " type=" + r.getReferenceType());
                        }
                    }

                    pw.println("-- Decompile --");
                    try {
                        DecompileResults dr = ifc.decompileFunction(fn, 120, monitor);
                        if (dr != null && dr.decompileCompleted() && dr.getDecompiledFunction() != null) {
                            pw.println(dr.getDecompiledFunction().getC());
                        } else {
                            pw.println("(decompile failed)");
                        }
                    } catch (Exception ex) {
                        pw.println("(decompile exception: " + ex + ")");
                    }
                }

                pw.println();
                pw.println("-- Disasm @target+0x180 --");
                Instruction inst = getInstructionAt(a);
                if (inst == null) {
                    disassemble(a);
                    inst = getInstructionAt(a);
                }
                int n = 0;
                while (inst != null && n < 384) {
                    pw.println(inst.getAddress() + "\t" + inst);
                    inst = inst.getNext();
                    n++;
                }
                pw.println();
                pw.println();
            }
        }

        println("Wrote " + out.getAbsolutePath());
        ifc.dispose();
    }
}
