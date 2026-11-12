This is herdtools7, a tool suite to test weak memory models.

MMIO litmus tests
=================

Before building, install the herdtools7 prerequisites and opam dependencies as
described in [INSTALL.md](INSTALL.md).  Then build `herd7` and run the ARM and
RISC-V MMIO suites with their standalone models from the repository root:

    opam exec -- dune build herd/herd.exe
    _build/default/herd/herd.exe -conf herd/tests/instructions/ARM_MMIO/mmio.cfg herd/tests/instructions/ARM_MMIO/*.litmus
    _build/default/herd/herd.exe -cat herd/libdir/riscvmmio.cat herd/tests/instructions/RISCV_MMIO/*.litmus

The generated `+min` tests contain the minimum implemented ordering needed to
forbid the specified cycle and should report `Never`.  The matching `+no-RB`
tests deliberately omit a required PCIe readback and should report
`Sometimes`.  The ARM configuration also loads its Bell shareability topology;
the `SCOPE+` tests check same-ISH and different-ISH behavior explicitly.

See the [ARM MMIO guide](herd/tests/instructions/ARM_MMIO/README.md) and the
[RISC-V MMIO guide](herd/tests/instructions/RISCV_MMIO/README.md) for access
annotations, memory-type mappings, fence and readback rules, individual-test
commands, suite structure, and current model limitations.

We provide the following tools:

 - herd7: a generic simulator for weak memory models
 - litmus7: run litmus tests (given as assembler programs for
   Power, ARM, AArch64 or X86) to test the memory model of the
   executing machine
 - diy7: produce litmus tests from concise specifications
 - some additional tools
   In particular,
    * mcompare7 to analyse run logs of both herd and litmus.
    * klitmus7, an experimental tool, similar to litmus7 that runs kernel
      memory model tests as kernel modules. The tool klitmus7 is inspired
      from a python script by Andrea Parri,.
      <http://retis.sssup.it/~a.parri/lkmm/run.py>


herdtools7 is the successor of the diy tool suite.

Home
====

http://diy.inria.fr/

diy-devel@inria.fr

Compilation and installation
============================

See file [INSTALL.md](INSTALL.md).

Contributing
============

This repository uses the [Pre-Commit tool](https://pre-commit.com) to manage
pre-commit validation, to check for formatting, test regressions, etc.

Pre-Commit can be installed on macOS with [Homebrew](https://brew.sh), or on
all platforms with Python's `pip`:

    # macOS with Homebrew.
    % brew install pre-commit

    # All other OS (including macOS without Homebrew).
    % pip install pre-commit

To make Pre-Commit run automatically when you `git commit`, add it to your Git
repository's local `pre-commit` hooks. From within this repository, run:

    % pre-commit install

When adding a new pre-commit check, please run Pre-Commit manually first:

    % pre-commit run --all-files

License
=======

The authors of the diy7 tool suite are Jade Alglave and Luc Maranget.


Copyright 2010 -- present: Institut National de Recherche en Informatique et
en Automatique, and the authors.

Diy7 is released under the terms of the CeCILL-B free software license agreement.
See file [LICENSE.txt](LICENSE.txt).
