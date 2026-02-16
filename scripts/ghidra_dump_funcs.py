#@category Lang5
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

TARGETS = [
    0x8001D7B4,
    0x8001DB54,
    0x80023324,
    0x80023340,
    0x80023BA4,
    0x80023FAC,
    0x80024138,
    0x800241CC,
    0x80031880,
]

out_path = '/workspace/work/scen_analysis/ghidra_func_dump.txt'
listing = currentProgram.getListing()
fm = currentProgram.getFunctionManager()
monitor = ConsoleTaskMonitor()

ifc = DecompInterface()
ifc.openProgram(currentProgram)

with open(out_path, 'w') as out:
    out.write('Program: %s\n' % currentProgram.getName())
    out.write('Language: %s\n\n' % currentProgram.getLanguageID())

    for ea in TARGETS:
        a = toAddr(ea)
        disassemble(a)
        fn = fm.getFunctionContaining(a)
        if fn is None:
            try:
                fn = createFunction(a, 'FUN_%08X' % ea)
            except:
                fn = fm.getFunctionContaining(a)

        out.write('==== TARGET 0x%08X ====\n' % ea)
        if fn is None:
            out.write('No function object; raw disasm only\n')
        else:
            out.write('Function: %s @ %s\n' % (fn.getName(), fn.getEntryPoint()))
            refs = getReferencesTo(fn.getEntryPoint())
            out.write('Xrefs:\n')
            found = False
            for r in refs:
                found = True
                out.write('  from %s type=%s\n' % (r.getFromAddress(), r.getReferenceType()))
            if not found:
                out.write('  (none)\n')

            try:
                res = ifc.decompileFunction(fn, 20, monitor)
                out.write('-- Decompile --\n')
                if res and res.decompileCompleted():
                    out.write(res.getDecompiledFunction().getC())
                else:
                    out.write('(decompile failed)\n')
            except Exception as ex:
                out.write('(decompile exception: %s)\n' % ex)

        out.write('\n-- Disasm @target+0x120 --\n')
        inst = listing.getInstructionAt(a)
        if inst is None:
            disassemble(a)
            inst = listing.getInstructionAt(a)
        n = 0
        while inst is not None and n < 160:
            out.write('%s\t%s\n' % (inst.getAddress(), inst))
            inst = inst.getNext()
            n += 1
        out.write('\n\n')

print('Wrote', out_path)
