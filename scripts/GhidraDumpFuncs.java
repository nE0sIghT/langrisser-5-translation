// Dumps selected functions/xrefs/decompile snippets.
//@category Lang5

import java.io.*;
import java.util.*;

import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;

public class GhidraDumpFuncs extends GhidraScript {
    private static final long[] DEFAULT_TARGETS = new long[] {
        0x8001D7B4L,
        0x8001DB54L,
        0x80023324L,
        0x80023340L,
        0x80023BA4L,
        0x80023FACL,
        0x80024138L,
        0x800241CCL,
        0x80031880L,
    };

    private List<Long> parseTargetsFromFile(String path) throws Exception {
        List<Long> out = new ArrayList<>();
        File f = new File(path);
        if (!f.exists()) {
            return out;
        }
        try (BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(f), "UTF-8"))) {
            String line;
            while ((line = br.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) {
                    continue;
                }
                String s = line.toLowerCase(Locale.ROOT);
                if (s.startsWith("0x")) {
                    s = s.substring(2);
                }
                try {
                    out.add(Long.parseUnsignedLong(s, 16));
                } catch (Exception e) {
                    // ignore malformed line
                }
            }
        }
        return out;
    }

    @Override
    protected void run() throws Exception {
        // args[0]: optional targets file (hex addresses, one per line)
        // args[1]: optional output file path
        String[] args = getScriptArgs();
        String targetsPath = args.length >= 1 ? args[0] : "";
        String outPath = args.length >= 2 ? args[1] : "/workspace/work/scen_analysis/ghidra_func_dump.txt";

        List<Long> targets = parseTargetsFromFile(targetsPath);
        if (targets.isEmpty()) {
            for (long ea : DEFAULT_TARGETS) {
                targets.add(ea);
            }
        }

        File outFile = new File(outPath);
        outFile.getParentFile().mkdirs();

        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        Listing listing = currentProgram.getListing();
        FunctionManager fm = currentProgram.getFunctionManager();

        try (PrintWriter out = new PrintWriter(new OutputStreamWriter(new FileOutputStream(outFile), "UTF-8"))) {
            out.println("Program: " + currentProgram.getName());
            out.println("Language: " + currentProgram.getLanguageID());
            out.println();

            for (long ea : targets) {
                Address a = toAddr(ea);
                disassemble(a);
                Function fn = fm.getFunctionContaining(a);
                if (fn == null) {
                    try {
                        createFunction(a, "FUN_" + Long.toHexString(ea).toUpperCase());
                    } catch (Exception e) {
                        // ignore
                    }
                    fn = fm.getFunctionContaining(a);
                }

                out.printf("==== TARGET 0x%08X ====\n", ea);
                if (fn != null) {
                    out.println("Function: " + fn.getName() + " @ " + fn.getEntryPoint());
                    out.println("Xrefs:");
                    Reference[] refs = getReferencesTo(fn.getEntryPoint());
                    if (refs.length == 0) {
                        out.println("  (none)");
                    } else {
                        for (Reference r : refs) {
                            out.println("  from " + r.getFromAddress() + " type=" + r.getReferenceType());
                        }
                    }

                    out.println("-- Decompile --");
                    try {
                        DecompileResults res = ifc.decompileFunction(fn, 20, monitor);
                        if (res != null && res.decompileCompleted() && res.getDecompiledFunction() != null) {
                            out.println(res.getDecompiledFunction().getC());
                        } else {
                            out.println("(decompile failed)");
                        }
                    } catch (Exception ex) {
                        out.println("(decompile exception: " + ex + ")");
                    }
                } else {
                    out.println("No function object");
                }

                out.println("-- Disasm @target+0x120 --");
                Instruction inst = listing.getInstructionAt(a);
                if (inst == null) {
                    disassemble(a);
                    inst = listing.getInstructionAt(a);
                }
                int n = 0;
                while (inst != null && n < 160) {
                    out.println(inst.getAddress() + "\t" + inst.toString());
                    inst = inst.getNext();
                    n++;
                }
                out.println();
                out.println();
            }
        }

        println("Wrote " + outFile.getAbsolutePath());
    }
}
