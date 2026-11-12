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

`aarch64mmio.cat` is a standalone model scaffold.  It constructs `ish-order`
and `osh-order` from the MMIO ordering tables, non-reordering Device accesses,
scoped DMBs, and PCIe readback.  `aarch64mmio.bell` supplies a nested
`pe < inner < outer < system` process topology.  Separate axioms require
acyclicity of each ordering relation with communication (`rfe | coe | fre`),
restricted to processes in the same instance of the corresponding domain.
The model does not include `aarch64.cat`, because that model assumes a common
shareability domain for the participating PEs.

## Running the tests

First install the herdtools7 prerequisites and opam dependencies described in
the repository's [`INSTALL.md`](../../../../INSTALL.md).  Then, from the
repository root, build `herd7` and run one test with the standalone MMIO model:

    opam exec -- dune build herd/herd.exe
    _build/default/herd/herd.exe -conf herd/tests/instructions/ARM_MMIO/mmio.cfg herd/tests/instructions/ARM_MMIO/CYCLE+P0-RR+P1-WW+Y-Device-GRE+X-Normal+min-RB-P1.litmus

Run the complete ARM MMIO suite with:

    _build/default/herd/herd.exe -conf herd/tests/instructions/ARM_MMIO/mmio.cfg herd/tests/instructions/ARM_MMIO/*.litmus

Generated filenames ending in `+min.litmus` or containing `+min-RB-` should
report `Never`.  Files ending in `+no-RB.litmus` omit a required PCIe readback
and should report `Sometimes`.  Use this model only for the annotated MMIO
tests; ordinary AArch64 tests should continue to use the standard
`aarch64.cat` model.

The `-conf` option is required: `mmio.cfg` loads both the CAT model and its
Bell scope hierarchy.  Running `aarch64mmio.cat` alone does not define the
`inner` and `outer` scope relations used by the consistency axioms.

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

Every generated CPU/device cycle places P0 and P1 in different Inner
Shareable domains inside the same Outer Shareable domain:

    scopes: (system (outer (inner (pe P0)) (inner (pe P1))))

The generator also emits four `SCOPE+MP` CPU/CPU tests, for 153 ARM tests in
total.  These use the same memory type for a location on both PEs and show:

- `DMB ISH` forbids the MP outcome when both PEs share an Inner Shareable
  domain.
- The same `DMB ISH` permits the outcome when the PEs are in different Inner
  Shareable domains.
- `DMB OSH` forbids it when those PEs share an Outer Shareable domain.
- Without fences, the outcome remains permitted even within one Inner
  Shareable domain.

Minimal ordering is program order for two non-reordering Device accesses and
`DMB OSH` for other directly orderable CPU/device pairs.  A Device write followed by a
Normal access requires a same-subtype Device readback.  The write must itself
be ordered before that read: program order suffices for `Device-nGnRE` and
`Device-nGnRnE`, while `Device-GRE` and `Device-nGRE` require a DMB before the
readback.  Any DMB domain orders accesses reaching the assumed same peripheral;
the second DMB must cover the observer domain in which the readback-to-Normal
ordering is used.  The corresponding `no-RB` test omits the readback and
remains allowed.

## Scope topology

Scope membership is hierarchical, not an access memory type.  A process is a
`pe` inside one `inner` domain, which is inside one `outer` domain and the
`system` domain.  Tests provide a `scopes:` tree after their instruction table.
The CAT expressions `tag2scope('inner)` and `tag2scope('outer)` relate events
whose processes occupy the same particular domain.  Intersecting both PPO and
communication with those relations prevents an ISH ordering from constraining
a process in a different Inner Shareable domain.

`DMB ISH`, `DMB OSH`, and `DMB SY` contribute to `ish-order`; only `DMB OSH`
and `DMB SY` contribute to `osh-order`.  Non-reordering Device order and the
same-peripheral readback relation can contribute to both.

## Pre-ISH backup

The complete implementation immediately before scope support is archived as
[`../ARM_MMIO_pre_ISH_2026-11-12.tar.gz`](../ARM_MMIO_pre_ISH_2026-11-12.tar.gz).
It contains the model, 149 tests, documentation, generator, and supporting
AArch64 annotation/parser/semantics files.  Its SHA-256 is
`71715cbe76125054c591da7b27c76f807b84b5382bc443f40eed011e211cb39c`.

## Current limitations

- The model distinguishes full `DMB ISH`, `DMB OSH`, and `DMB SY` by observer
  scope.  It does not yet distinguish their LD and ST variants or model their
  direction-specific read/write effects.  `DMB SY` contributes to the inner
  and outer axioms, but there is no separate full-system ordering axiom yet.
- Acquire and release instructions are not MMIO ordering mechanisms in this
  model.  In particular, their BOB/OB contributions and interactions with
  access type and shareability domain have not been added.
- OB is broader than explicit barriers: architectural address, data, and
  control dependencies can contribute to it.  The current `ish-ob` and
  `osh-ob` rules approximate OB using DMB only.
- Inner and outer domains are modeled, but non-shareable and independent
  full-system consistency checks are not.
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
