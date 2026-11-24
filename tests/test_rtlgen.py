"""RTL generators: parameter validation, lint cleanliness and functional correctness.

Lint uses Verilator and simulation uses Icarus Verilog (host tools); those tests skip when the
tools are missing (e.g. in CI).
"""

from __future__ import annotations

import random
import shutil
import subprocess

import pytest

from siliconai.rtlgen.generators import FAMILIES, crc32_step_equations, generate
from siliconai.rtlgen.orfs_design import write_orfs_design

CASES = [
    ("mult", {"width": 8}),
    ("mult", {"width": 32}),
    ("addtree", {"inputs": 8, "width": 8}),
    ("mac", {"lanes": 4, "width": 8}),
    ("fifo", {"depth": 16, "width": 8}),
    ("fsm", {"states": 12, "inputs": 2, "outputs": 4, "seed": 3}),
    ("crc", {"width": 8}),
    ("crc", {"width": 64}),
    ("alu", {"width": 16}),
]

needs_verilator = pytest.mark.skipif(shutil.which("verilator") is None, reason="no verilator")
needs_iverilog = pytest.mark.skipif(shutil.which("iverilog") is None, reason="no iverilog")


def test_every_family_has_a_case():
    assert {f for f, _ in CASES} == set(FAMILIES)


@pytest.mark.parametrize(
    "family,params",
    [
        ("nope", {}),
        ("mult", {}),
        ("mult", {"width": 1000}),
        ("mult", {"width": "8; $finish"}),
        ("mult", {"width": True}),
        ("mult", {"width": 8, "extra": 1}),
        ("addtree", {"inputs": 6, "width": 8}),  # not a power of two
    ],
)
def test_generate_rejects_bad_parameters(family, params):
    with pytest.raises(ValueError):
        generate(family, params)


def test_names_are_unique_and_deterministic():
    names = [generate(f, p).name for f, p in CASES]
    assert len(set(names)) == len(names)
    assert all(n.startswith("sai_") for n in names)
    assert generate(*CASES[5]).verilog == generate(*CASES[5]).verilog


@needs_verilator
@pytest.mark.parametrize("family,params", CASES)
def test_generated_rtl_is_lint_clean(tmp_path, family, params):
    d = generate(family, params)
    src = tmp_path / "rtl.v"
    src.write_text(d.verilog)
    proc = subprocess.run(
        [
            "verilator",
            "--lint-only",
            "-Wall",
            "-Wno-DECLFILENAME",
            "--top-module",
            d.name,
            str(src),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def _simulate(tmp_path, dut_verilog: str, tb: str) -> str:
    (tmp_path / "dut.v").write_text(dut_verilog)
    (tmp_path / "tb.v").write_text(tb)
    exe = tmp_path / "sim"
    subprocess.run(
        ["iverilog", "-o", str(exe), str(tmp_path / "tb.v"), str(tmp_path / "dut.v")],
        check=True,
        capture_output=True,
        timeout=120,
    )
    out = subprocess.run(
        ["vvp", "-n", str(exe)], check=True, capture_output=True, text=True, timeout=120
    )
    # drop the simulator's own "$finish called at ..." line
    return "\n".join(ln for ln in out.stdout.splitlines() if "$finish" not in ln)


def crc32_reference(words: list[int], width: int) -> int:
    crc = 0xFFFFFFFF
    for w in words:
        for k in range(width - 1, -1, -1):
            fb = ((crc >> 31) ^ (w >> k)) & 1
            crc = ((crc << 1) & 0xFFFFFFFF) ^ (0x04C11DB7 if fb else 0)
    return crc


def test_crc_equations_match_bitwise_reference():
    rng = random.Random(1)
    for width in (1, 8, 13):
        eqs = crc32_step_equations(width)
        for _ in range(20):
            crc, data = rng.getrandbits(32), rng.getrandbits(width)
            nxt = 0
            for bit, (c, d) in enumerate(eqs):
                v = 0
                for b in c:
                    v ^= (crc >> b) & 1
                for b in d:
                    v ^= (data >> b) & 1
                nxt |= v << bit
            ref = crc
            for k in range(width - 1, -1, -1):
                fb = ((ref >> 31) ^ (data >> k)) & 1
                ref = ((ref << 1) & 0xFFFFFFFF) ^ (0x04C11DB7 if fb else 0)
            assert nxt == ref


@needs_iverilog
@pytest.mark.parametrize("width", [8, 32])
def test_crc_rtl_matches_reference(tmp_path, width):
    d = generate("crc", {"width": width})
    words = [random.Random(width).getrandbits(width) for _ in range(6)]
    feed = "\n".join(f"    data = {width}'h{w:x}; @(negedge clk);" for w in words)
    tb = f"""module tb;
  reg clk = 0, rst = 1, en = 0;
  reg [{width - 1}:0] data = 0;
  wire [31:0] crc;
  {d.name} dut(.clk(clk), .rst(rst), .en(en), .data(data), .crc(crc));
  always #5 clk = ~clk;
  initial begin
    @(negedge clk); rst = 0; en = 1;
{feed}
    en = 0; @(negedge clk); @(negedge clk);
    $display("%08h", crc); $finish;
  end
endmodule
"""
    assert int(_simulate(tmp_path, d.verilog, tb).strip(), 16) == crc32_reference(words, width)


@needs_iverilog
def test_mult_rtl_multiplies(tmp_path):
    d = generate("mult", {"width": 12})
    pairs = [(4095, 4095), (1234, 77), (0, 99), (2048, 3)]
    body = "\n".join(
        f'    a = {a}; b = {b}; @(negedge clk); @(negedge clk); $display("%0d", p);'
        for a, b in pairs
    )
    tb = f"""module tb;
  reg clk = 0; reg [11:0] a = 0, b = 0; wire [23:0] p;
  {d.name} dut(.clk(clk), .a(a), .b(b), .p(p));
  always #5 clk = ~clk;
  initial begin
{body}
    $finish;
  end
endmodule
"""
    got = [int(x) for x in _simulate(tmp_path, d.verilog, tb).split()]
    assert got == [a * b for a, b in pairs]


@needs_iverilog
def test_fifo_rtl_preserves_order_and_flags(tmp_path):
    d = generate("fifo", {"depth": 4, "width": 8})
    tb = f"""module tb;
  reg clk = 0, rst = 1, push = 0, pop = 0; reg [7:0] din = 0;
  wire [7:0] dout; wire full, empty;
  {d.name} dut(.clk(clk), .rst(rst), .push(push), .pop(pop), .din(din), .dout(dout),
               .full(full), .empty(empty));
  always #5 clk = ~clk;
  integer i;
  initial begin
    @(negedge clk); rst = 0;
    $display("E%0d", empty);
    push = 1;
    for (i = 0; i < 5; i = i + 1) begin din = 8'd10 + i; @(negedge clk); end
    push = 0; $display("F%0d", full);
    pop = 1;
    for (i = 0; i < 4; i = i + 1) begin @(negedge clk); $display("%0d", dout); end
    pop = 0; $display("E%0d", empty); $finish;
  end
endmodule
"""
    out = _simulate(tmp_path, d.verilog, tb).split()
    # 5th push is dropped because the 4-deep FIFO is full
    assert out == ["E1", "F1", "10", "11", "12", "13", "E1"]


def test_write_orfs_design_layout_and_idempotence(tmp_path):
    d = generate("alu", {"width": 8})
    out = write_orfs_design(d, "nangate45", tmp_path)
    assert out == tmp_path / "nangate45" / d.name
    cfg = (out / "config.mk").read_text()
    assert f"export DESIGN_NAME = {d.name}" in cfg
    assert "VERILOG_FILES = $(DESIGN_HOME)/nangate45/" in cfg
    assert "set clk_period 1.5" in (out / "constraint.sdc").read_text()
    mtime = (out / "rtl.v").stat().st_mtime_ns
    write_orfs_design(d, "nangate45", tmp_path)
    assert (out / "rtl.v").stat().st_mtime_ns == mtime
    with pytest.raises(ValueError):
        write_orfs_design(d, "asap7", tmp_path)
