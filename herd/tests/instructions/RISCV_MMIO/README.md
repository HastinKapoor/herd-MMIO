# RISC-V CPU/MMIO tests

Memory type is an access field: `lw x5,0(x6) [Main]` or
`sw x5,0(x6) [Device]`.  P0 is the CPU and P1 is the PCIe device.  A
CPU-local Main location is therefore Device memory to P1, while a
device-local Device location is Main memory to P1.

Fence options select four access classes: `r` is a Main read, `w` is a Main
write, `i` is a Device read, and `o` is a Device write.  Combined option sets
such as `iorw` are also accepted.  Standard unannotated RISC-V litmus syntax
continues to use the existing RISC-V model unchanged.

PCIe Device writes are posted.  A fence does not directly order a Device
write before a Main access.  Such a sequence requires a Device readback to
flush the write, followed by a fence whose predecessor set contains `i`.

## Generated cycle suite

`../generate_mmio_cycles.py` generates all nine two-operation process pairs
that can close a four-event cycle: `WW/WW`, `RW/WW`, `WW/WR`, `WW/RW`,
`RW/RW`, `WW/RR`, `WR/WW`, `RR/WW`, and `WR/WR`.  Filenames use
`CYCLE+P0-<pair>+P1-<pair>+Y-<type>+X-<type>+<ordering>.litmus`; X and Y types
are P0's view, and P1 uses the inverse Main/Device mapping.

All four X/Y type pairs are generated for each process-shape.  The suite
contains 36 minimally ordered tests plus eight matching `no-RB` variants, for
44 tests total.  Directly orderable pairs use the narrowest predecessor and
successor fence bits.  A Device write followed by a Main access uses
`fence o,i`, performs a Device readback, and then uses `fence i,r` or
`fence i,w`.  The corresponding `no-RB` test omits the readback and remains
allowed.

## Current limitations

- The model distinguishes only Main and Device accesses.  It does not model
  the complete set of PMAs, including cacheability, idempotency, coherence,
  relaxed versus strongly ordered I/O regions, or page-based overrides.
- RISC-V I/O ordering channels are not represented.  Consequently, the model
  omits implicit program-order guarantees for overlapping I/O addresses, the
  same strongly ordered I/O region, channel 0 point-to-point ordering,
  channel 1 global ordering, and accesses assigned to the same nonzero
  channel.  It currently obtains Device ordering only from explicit fences or
  the PCIe readback rule.
- Acquire and release operations are not fully modeled for MMIO.  The copied
  RVWMO PPO rules recognize the existing `AQ` and `RL` event sets, but they do
  not yet enforce the architectural distinction that acquire/release ordering
  applies Main-to-Main and I/O-to-I/O, rather than directly bridging Main and
  Device accesses.
- Memory-type fields are implemented only for ordinary loads and stores.
  Typed LR/SC, AMOs, vector accesses, implicit accesses, and other memory
  instructions are not supported.
- Readback requires `fence o,i` between the Device write and Device read.
  Peripheral identity and PCIe topology are absent, so the model
  cannot verify that the read flushes the posted-write path used by the write.
- `FENCE.I`, `FENCE.TSO`, CSR ordering, instruction fetches, and the
  ordering-versus-completion consequences of different fence uses are outside
  the current MMIO rules.
- P1 is represented using an ordinary architectural process.  There are no
  first-class device/DMA events, device-register side effects, interrupts,
  completion events, or platform-specific coherency mechanisms.
- Device accesses still use generic coherent-memory `rf`, `co`, and `fr`.
  This does not capture I/O reads and writes with device-specific side effects
  or values that are not supplied by coherent memory.
- The PCIe readback restriction is a platform assumption layered on RISC-V.
  Architectural I/O ordering may stop at a platform boundary and does not by
  itself describe ordering through an external PCIe fabric.
- The model uses a simplified global acyclicity axiom and is not a complete
  replacement for `riscv.cat`, including all coherence and atomicity checks.

The architectural channel rules summarized above are described in the
[RISC-V I/O ordering specification](https://docs.riscv.org/reference/isa/v20240411/_attachments/riscv-unprivileged.pdf),
Appendix A.4.2.
