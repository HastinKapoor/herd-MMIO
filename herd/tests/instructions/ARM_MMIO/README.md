# AArch64 CPU/MMIO model scaffold

Each memory instruction carries its own memory-type field, for example
`STR W2,[X0] [Device-nGnRnE]`.  This is deliberately attached to
the access, rather than to the location: one agent can see an address as
Device memory while a device/DMA agent sees the same address as Normal memory.
The supported starting types are `Normal`, `Device-GRE`, `Device-nGRE`,
`Device-nGnRE`, and `Device-nGnRnE`.

In this matrix P0 is the CPU and P1 is the PCIe device.  P1 uses
`Device-GRE` for an address that P0 accesses as `Normal`; it uses `Normal` for
an address that P0 accesses as any Device subtype.  The same mapping applies
in the opposite direction when tests add P1 stores and P0 loads.

`aarch64mmio.cat` is a standalone model scaffold.  It constructs the
orderings visible in the outer-shareable domain from the MMIO ordering tables,
non-reordering Device accesses, OSH fences, and PCIe readback.  Its global
axiom is acyclicity of `osh-order` with communication (`rfe | coe | fre`).  It
does not include `aarch64.cat`, because that model's treatment of barriers is
not suitable for agents that can participate in different shareability
domains.

The field is parsed into the instruction, propagated to the memory event, and
exported to CAT as `Normal` or the corresponding `Device-*` set.  This is
intentionally a CPU-side foundation.  A device model still needs an
event syntax for device reads/writes and rules for the particular device's
register state, completion, interrupts, and DMA.

## Generated cycle suite

`../generate_mmio_cycles.py` generates all nine two-operation process pairs
that can close a four-event cycle: `WW/WW`, `RW/WW`, `WW/WR`, `WW/RW`,
`RW/RW`, `WW/RR`, `WR/WW`, `RR/WW`, and `WR/WR`.  Filenames use
`CYCLE+P0-<pair>+P1-<pair>+Y-<type>+X-<type>+<ordering>.litmus`; X and Y types
are P0's view, and P1 uses the inverse mapping above.

Each process uses at most one Device subtype.  The suite therefore uses 13
valid X/Y type pairs per process-shape.  It contains 117 minimally ordered
tests plus 32 matching `no-RB` variants, for 149 tests total.

Minimal ordering is program order for two non-reordering Device accesses and
`DMB OSH` for other directly orderable pairs.  A Device write followed by a
Normal access requires a same-subtype Device readback.  The write must itself
be ordered before that read: program order suffices for `Device-nGnRE` and
`Device-nGnRnE`, while `Device-GRE` and `Device-nGRE` require `DMB OSH` before
the readback.  A second `DMB OSH` orders the readback before the Normal access.
The corresponding `no-RB` test omits the readback and remains allowed.

## Current limitations

- The model treats `DMB OSH` and `DMB SY` as equivalent sources of
  outer-shareable ordering.  It does not distinguish `DMB OSH`, `DMB OSH LD`
  (`DMB OSHLD`), and `DMB OSH ST` (`DMB OSHST`), or model their
  direction-specific read/write effects.
- Acquire and release instructions are not MMIO ordering mechanisms in this
  model.  In particular, their BOB/OB contributions and interactions with
  access type and shareability domain have not been added.
- OB is broader than explicit barriers: architectural address, data, and
  control dependencies can contribute to it.  The current `osh-ob` rule
  approximates OB using DMB only.
- Only the outer-shareable ordering needed by these tests is represented.
  Inner-shareable, non-shareable, and full-system observer/domain relationships
  are not modeled independently.
- Memory-type fields are implemented only for ordinary `LDR` and `STR`.
  Typed atomics, load-acquire/store-release instructions, paired accesses,
  exclusives, and other memory instructions are not yet supported.
- Readback requires an already ordered Device write and Device read, but the
  model does not identify peripherals, so it cannot verify
  that the read targets the same PCIe endpoint or a register that actually
  flushes the relevant posted-write path.
- P1 is represented using an ordinary architectural process.  There are no
  first-class device/DMA events, device-register side effects, interrupts,
  completion events, or device-specific ordering rules.
- Device accesses still use the generic `rf`, `co`, and `fr` machinery.  The
  model does not describe registers whose reads have side effects or whose
  returned values are not determined by coherent memory.
- The model is an MMIO-ordering scaffold, not a complete replacement for the
  architectural AArch64 model or all of its consistency axioms.
