#!/usr/bin/env python3
"""Generate the exhaustive two-location ARM and RISC-V MMIO cycle suites."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARM_DIR, RV_DIR = ROOT / "ARM_MMIO", ROOT / "RISCV_MMIO"
CYCLES = (
    ("WW", "WW"), ("RW", "WW"), ("WW", "WR"),
    ("WW", "RW"), ("RW", "RW"), ("WW", "RR"),
    ("WR", "WW"), ("RR", "WW"), ("WR", "WR"),
)
ARM_DEVICES = ("Device-GRE", "Device-nGRE", "Device-nGnRE", "Device-nGnRnE")
ARM_STRONG = {"Device-nGnRE", "Device-nGnRnE"}
ARM_CPU_DEVICE_SCOPES = (
    "scopes: (system (outer (inner (pe P0)) (inner (pe P1))))"
)
ARM_SAME_ISH_SCOPES = (
    "scopes: (system (outer (inner (pe P0) (pe P1))))"
)


def arm_peer(t):
    return "Device-GRE" if t == "Normal" else "Normal"


def arm_pairs():
    yield "Normal", "Normal"
    for dev in ARM_DEVICES:
        yield "Normal", dev
        yield dev, "Normal"
        yield dev, dev


def condition(arch, p0, p1):
    a, b = p0
    c, d = p1
    regs = (("0:X2", "0:X3", "1:X2", "1:X3") if arch == "ARM"
            else ("0:x5", "0:x7", "1:x5", "1:x7"))
    p0a, p0b, p1c, p1d = regs
    if (b, c) == ("W", "W"):
        xedge = "[x]=2"
    elif (b, c) == ("W", "R"):
        xedge = f"{p1c}=1"
    elif (b, c) == ("R", "W"):
        xedge = f"{p0b}=0"
    else:
        raise AssertionError("B/C is read/read")
    if (d, a) == ("W", "W"):
        yedge = "[y]=1"
    elif (d, a) == ("W", "R"):
        yedge = f"{p0a}=2"
    elif (d, a) == ("R", "W"):
        yedge = f"{p1d}=0"
    else:
        raise AssertionError("D/A is read/read")
    return f"{xedge} /\\ {yedge}"


def columns(p0, p1):
    width = max([2, *(len(x) for x in p0)]) + 2
    rows = [f" {'P0':<{width}}| P1 ;"]
    for i in range(max(len(p0), len(p1))):
        left = p0[i] if i < len(p0) else ""
        right = p1[i] if i < len(p1) else ""
        rows.append(f" {left:<{width}}| {right} ;")
    return "\n".join(rows)


def rb_suffix(procs):
    return "min" if not procs else "min-RB-" + "-".join(f"P{p}" for p in procs)


def arm_needs_rb(pair, types):
    return pair[0] == "W" and types[0] != "Normal" and types[1] == "Normal"


def arm_access(pos, direction, memory_type):
    base, dst = (("X0", "W2") if pos == 0 else ("X1", "W3"))
    return (f"LDR {dst},[{base}] [{memory_type}]" if direction == "R"
            else f"STR W4,[{base}] [{memory_type}]")


def arm_seq(proc, pair, types, with_rb):
    first = arm_access(0, pair[0], types[0])
    second = arm_access(1, pair[1], types[1])
    seq = [f"MOV W4,#{proc + 1}", first]
    if arm_needs_rb(pair, types) and with_rb:
        # The write must reach the readback read.  Strong Device types provide
        # that ordering in program order; reordering types need a first DMB.
        # Any DMB scope orders accesses reaching the same peripheral, so ISH
        # is the weakest currently implemented choice for this endpoint edge.
        if types[0] not in ARM_STRONG:
            seq.append("DMB ISH")
        seq.extend([f"LDR W9,[X10] [{types[0]}]", "DMB OSH", second])
    elif types[0] in ARM_STRONG and types[1] in ARM_STRONG:
        seq.append(second)
    else:
        seq.extend(["DMB OSH", second])
    return seq


def write_arm(p0pair, p1pair, ytype, xtype, with_rb, weak=False):
    p0types = ytype, xtype
    p1types = arm_peer(xtype), arm_peer(ytype)
    rb = [p for p, pair, types in ((0, p0pair, p0types), (1, p1pair, p1types))
          if arm_needs_rb(pair, types)]
    suffix = "no-RB" if weak else rb_suffix(rb)
    name = f"CYCLE+P0-{p0pair}+P1-{p1pair}+Y-{ytype}+X-{xtype}+{suffix}"
    init = ["x=0; y=0;", "0:X0=y; 0:X1=x;", "1:X0=x; 1:X1=y;"]
    if with_rb and 0 in rb:
        init += ["rb0=0;", "0:X10=rb0;"]
    if with_rb and 1 in rb:
        init += ["rb1=0;", "1:X10=rb1;"]
    expected = "Sometimes" if weak else "Never"
    text = (
        f"AArch64 {name}\n\n"
        f"(* Generated two-location cycle. Expected observation: {expected}.\n"
        " * Y and X types are P0's view; P1 uses the agent-relative inverse mapping.\n *)\n"
        "{\n" + "\n".join(init) + "\n}\n\n" +
        columns(arm_seq(0, p0pair, p0types, with_rb),
                arm_seq(1, p1pair, p1types, with_rb)) +
        f"\n\n{ARM_CPU_DEVICE_SCOPES}\n\n"
        f"exists ({condition('ARM', p0pair, p1pair)})\n"
    )
    (ARM_DIR / f"{name}.litmus").write_text(text)


def write_arm_scope_mp(same_ish, barrier):
    domain = "same-ISH" if same_ish else "different-ISH"
    ordering = "no-fence" if barrier is None else f"DMB-{barrier}"
    name = f"SCOPE+MP+Normal-Device-GRE+{domain}+{ordering}"
    expected = "Never" if barrier == "OSH" or (same_ish and barrier == "ISH") else "Sometimes"
    p0 = ["MOV W4,#1", "STR W4,[X0] [Normal]"]
    p1 = ["LDR W2,[X0] [Device-GRE]"]
    if barrier is not None:
        p0.append(f"DMB {barrier}")
        p1.append(f"DMB {barrier}")
    p0.append("STR W4,[X1] [Device-GRE]")
    p1.append("LDR W3,[X1] [Normal]")
    scopes = ARM_SAME_ISH_SCOPES if same_ish else ARM_CPU_DEVICE_SCOPES
    text = (
        f"AArch64 {name}\n\n"
        f"(* CPU-to-CPU scope check over Normal and Device memory.\n"
        f" * Expected observation: {expected}.\n"
        " * Both PEs use the same memory type for each location.\n"
        " *)\n"
        "{\n"
        "x=0; y=0;\n"
        "0:X0=x; 0:X1=y;\n"
        "1:X0=y; 1:X1=x;\n"
        "}\n\n" + columns(p0, p1) +
        f"\n\n{scopes}\n\n"
        "exists (1:X2=1 /\\ 1:X3=0)\n"
    )
    (ARM_DIR / f"{name}.litmus").write_text(text)


def rv_peer(t):
    return "Device" if t == "Main" else "Main"


def rv_needs_rb(pair, types):
    return pair[0] == "W" and types == ("Device", "Main")


def rv_opt(direction, memory_type):
    return {("R", "Main"): "r", ("W", "Main"): "w",
            ("R", "Device"): "i", ("W", "Device"): "o"}[direction, memory_type]


def rv_access(pos, direction, memory_type):
    base, dst = (("x6", "x5") if pos == 0 else ("x8", "x7"))
    return (f"lw {dst},0({base}) [{memory_type}]" if direction == "R"
            else f"sw x11,0({base}) [{memory_type}]")


def rv_seq(proc, pair, types, with_rb):
    first = rv_access(0, pair[0], types[0])
    second = rv_access(1, pair[1], types[1])
    seq = [f"ori x11,x0,{proc + 1}", first]
    if rv_needs_rb(pair, types) and with_rb:
        seq.extend(["fence o,i", "lw x9,0(x10) [Device]",
                    f"fence i,{rv_opt(pair[1], types[1])}", second])
    else:
        seq.extend([f"fence {rv_opt(pair[0], types[0])},{rv_opt(pair[1], types[1])}",
                    second])
    return seq


def write_rv(p0pair, p1pair, ytype, xtype, with_rb, weak=False):
    p0types = ytype, xtype
    p1types = rv_peer(xtype), rv_peer(ytype)
    rb = [p for p, pair, types in ((0, p0pair, p0types), (1, p1pair, p1types))
          if rv_needs_rb(pair, types)]
    suffix = "no-RB" if weak else rb_suffix(rb)
    name = f"CYCLE+P0-{p0pair}+P1-{p1pair}+Y-{ytype}+X-{xtype}+{suffix}"
    init = ["x=0; y=0;", "0:x6=y; 0:x8=x;", "1:x6=x; 1:x8=y;"]
    if with_rb and 0 in rb:
        init += ["rb0=0;", "0:x10=rb0;"]
    if with_rb and 1 in rb:
        init += ["rb1=0;", "1:x10=rb1;"]
    expected = "Sometimes" if weak else "Never"
    text = (
        f"RISCV {name}\n\n"
        f"(* Generated two-location cycle. Expected observation: {expected}.\n"
        " * Y and X types are P0's view; P1 uses the agent-relative inverse mapping.\n *)\n"
        "{\n" + "\n".join(init) + "\n}\n\n" +
        columns(rv_seq(0, p0pair, p0types, with_rb),
                rv_seq(1, p1pair, p1types, with_rb)) +
        f"\n\nexists ({condition('RISCV', p0pair, p1pair)})\n"
    )
    (RV_DIR / f"{name}.litmus").write_text(text)


def main():
    for directory in (ARM_DIR, RV_DIR):
        for path in directory.glob("*.litmus"):
            path.unlink()
    for p0pair, p1pair in CYCLES:
        for ytype, xtype in arm_pairs():
            p0types, p1types = (ytype, xtype), (arm_peer(xtype), arm_peer(ytype))
            needs = arm_needs_rb(p0pair, p0types) or arm_needs_rb(p1pair, p1types)
            write_arm(p0pair, p1pair, ytype, xtype, True)
            if needs:
                write_arm(p0pair, p1pair, ytype, xtype, False, True)
        for ytype in ("Main", "Device"):
            for xtype in ("Main", "Device"):
                p0types, p1types = (ytype, xtype), (rv_peer(xtype), rv_peer(ytype))
                needs = rv_needs_rb(p0pair, p0types) or rv_needs_rb(p1pair, p1types)
                write_rv(p0pair, p1pair, ytype, xtype, True)
                if needs:
                    write_rv(p0pair, p1pair, ytype, xtype, False, True)
    write_arm_scope_mp(True, None)
    write_arm_scope_mp(True, "ISH")
    write_arm_scope_mp(False, "ISH")
    write_arm_scope_mp(False, "OSH")


if __name__ == "__main__":
    main()
