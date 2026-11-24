"""Parameterized RTL generators (TODO P2-02).

Why: the runtime model is evaluated on *unseen designs* (GroupKFold by design lineage), so the
dataset needs many structurally different designs, not just the ~10 small ORFS designs. Each
family below is one design group; its parameters change size and structure.

Every design: one clock ``clk``, registered inputs and outputs (so timing paths are
register-to-register), synthesizable Verilog-2001. Generated RTL is tagged ``origin =
"generated"`` in the registry (ADR-009); all labels still come from real tool runs.

Parameters are integers with explicit bounds. Nothing user-supplied is pasted into Verilog
except validated integers.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable
from dataclasses import dataclass

NAME_PREFIX = "sai_"  # never collides with an ORFS design directory
_NAME_RE = re.compile(r"^sai_[a-z0-9_]{1,40}$")


@dataclass(frozen=True)
class GeneratedDesign:
    name: str  # also the Verilog top module and ORFS DESIGN_NAME
    family: str
    params: dict[str, int]
    verilog: str
    clock_period_ns: float


def _check(params: dict[str, int], bounds: dict[str, tuple[int, int]]) -> dict[str, int]:
    unknown = set(params) - set(bounds)
    if unknown:
        raise ValueError(f"unknown parameters: {sorted(unknown)}")
    out = {}
    for key, (lo, hi) in bounds.items():
        if key not in params:
            raise ValueError(f"missing parameter {key!r}")
        value = params[key]
        if not isinstance(value, int) or isinstance(value, bool) or not lo <= value <= hi:
            raise ValueError(f"{key} must be an int in [{lo}, {hi}], got {value!r}")
        out[key] = value
    return out


def _pow2(n: int, what: str) -> None:
    if n & (n - 1):
        raise ValueError(f"{what} must be a power of two")


def _name(family: str, params: dict[str, int]) -> str:
    name = NAME_PREFIX + family + "".join(f"_{k[0]}{v}" for k, v in sorted(params.items()))
    if not _NAME_RE.match(name):
        raise ValueError(f"generated name invalid: {name!r}")
    return name


# ------------------------------------------------------------------------------ families
def gen_mult(p: dict[str, int]) -> tuple[str, float]:
    """Registered W x W unsigned multiplier."""
    w = p["width"]
    body = f"""  input clk,
  input [{w - 1}:0] a,
  input [{w - 1}:0] b,
  output reg [{2 * w - 1}:0] p
);
  reg [{w - 1}:0] ra, rb;
  always @(posedge clk) begin
    ra <= a;
    rb <= b;
    p <= ra * rb;
  end"""
    return body, 2.0


def gen_addtree(p: dict[str, int]) -> tuple[str, float]:
    """Pipelined binary adder tree: N inputs of W bits, one register level per tree level."""
    n, w = p["inputs"], p["width"]
    _pow2(n, "inputs")
    levels = n.bit_length() - 1
    ow = w + levels
    lines = [
        "  input clk,",
        f"  input [{n * w - 1}:0] x,",
        f"  output [{ow - 1}:0] sum",
        ");",
    ]
    for i in range(n):
        lines.append(f"  reg [{ow - 1}:0] l0_{i};")
    for lvl in range(1, levels + 1):
        for i in range(n >> lvl):
            lines.append(f"  reg [{ow - 1}:0] l{lvl}_{i};")
    lines.append("  always @(posedge clk) begin")
    for i in range(n):
        lines.append(f"    l0_{i} <= {{{{{levels}{{1'b0}}}}, x[{i * w + w - 1}:{i * w}]}};")
    for lvl in range(1, levels + 1):
        for i in range(n >> lvl):
            lines.append(f"    l{lvl}_{i} <= l{lvl - 1}_{2 * i} + l{lvl - 1}_{2 * i + 1};")
    lines.append("  end")
    lines.append(f"  assign sum = l{levels}_0;")
    return "\n".join(lines), 1.5


def gen_mac(p: dict[str, int]) -> tuple[str, float]:
    """L parallel multiply-accumulate lanes of W-bit operands, synchronous clear."""
    lanes, w = p["lanes"], p["width"]
    aw = 2 * w + 8
    lines = [
        "  input clk,",
        "  input clr,",
        f"  input [{lanes * w - 1}:0] a,",
        f"  input [{lanes * w - 1}:0] b,",
        f"  output [{lanes * aw - 1}:0] acc",
        ");",
        "  reg rclr;",
    ]
    for i in range(lanes):
        lines += [f"  reg [{w - 1}:0] ra{i}, rb{i};", f"  reg [{aw - 1}:0] acc{i};"]
        lines.append(f"  assign acc[{i * aw + aw - 1}:{i * aw}] = acc{i};")
    lines.append("  always @(posedge clk) begin")
    lines.append("    rclr <= clr;")
    for i in range(lanes):
        lines += [
            f"    ra{i} <= a[{i * w + w - 1}:{i * w}];",
            f"    rb{i} <= b[{i * w + w - 1}:{i * w}];",
            f"    acc{i} <= rclr ? {aw}'d0 : acc{i} + ra{i} * rb{i};",
        ]
    lines.append("  end")
    return "\n".join(lines), 2.5


def gen_fifo(p: dict[str, int]) -> tuple[str, float]:
    """Synchronous register-based FIFO (depth D, width W): flop-dominated design."""
    d, w = p["depth"], p["width"]
    _pow2(d, "depth")
    aw = d.bit_length() - 1
    body = f"""  input clk,
  input rst,
  input push,
  input pop,
  input [{w - 1}:0] din,
  output reg [{w - 1}:0] dout,
  output full,
  output empty
);
  reg [{w - 1}:0] mem [0:{d - 1}];
  reg [{aw}:0] wptr, rptr;
  assign empty = (wptr == rptr);
  assign full = (wptr[{aw - 1}:0] == rptr[{aw - 1}:0]) && (wptr[{aw}] != rptr[{aw}]);
  always @(posedge clk) begin
    if (rst) begin
      wptr <= 0;
      rptr <= 0;
      dout <= 0;
    end else begin
      if (push && !full) begin
        mem[wptr[{aw - 1}:0]] <= din;
        wptr <= wptr + 1'b1;
      end
      if (pop && !empty) begin
        dout <= mem[rptr[{aw - 1}:0]];
        rptr <= rptr + 1'b1;
      end
    end
  end"""
    return body, 1.0


def gen_fsm(p: dict[str, int]) -> tuple[str, float]:
    """Random Moore FSM: S states, I-bit input, O-bit output, transitions seeded by ``seed``."""
    s, i_bits, o_bits, seed = p["states"], p["inputs"], p["outputs"], p["seed"]
    rng = random.Random(seed * 1_000_003 + s)  # noqa: S311 (design generation, not crypto)
    sw = max(1, (s - 1).bit_length())
    lines = [
        "  input clk,",
        "  input rst,",
        f"  input [{i_bits - 1}:0] in,",
        f"  output reg [{o_bits - 1}:0] out",
        ");",
        f"  reg [{sw - 1}:0] state, nxt;",
        f"  reg [{i_bits - 1}:0] rin;",
        "  always @(*) begin",
        "    nxt = state;",
        "    case (state)",
    ]
    for st in range(s):
        lines.append(f"      {sw}'d{st}: case (rin)")
        for v in range(1 << i_bits):
            lines.append(f"        {i_bits}'d{v}: nxt = {sw}'d{rng.randrange(s)};")
        lines.append("        default: nxt = state;")
        lines.append("      endcase")
    lines += ["      default: nxt = 0;", "    endcase", "  end"]
    lines += ["  always @(posedge clk) begin", "    rin <= in;", "    if (rst) begin"]
    lines += ["      state <= 0;", "      out <= 0;", "    end else begin", "      state <= nxt;"]
    lines.append("      case (state)")
    for st in range(s):
        lines.append(f"        {sw}'d{st}: out <= {o_bits}'d{rng.randrange(1 << o_bits)};")
    lines += ["        default: out <= 0;", "      endcase", "    end", "  end"]
    return "\n".join(lines), 1.0


CRC32_POLY = 0x04C11DB7


def crc32_step_equations(width: int) -> list[tuple[set[int], set[int]]]:
    """For each next-state bit, the sets of (crc bits, data bits) it XORs together.

    Models processing ``width`` data bits per cycle, MSB first, no reflection.
    """
    # each state bit is a pair (crc-set, data-set); XOR is symmetric difference
    state = [({b}, set()) for b in range(32)]
    for k in range(width - 1, -1, -1):
        fb_c, fb_d = state[31][0] ^ set(), state[31][1] ^ {k}
        new = []
        for bit in range(32):
            c, d = (set(), set()) if bit == 0 else (set(state[bit - 1][0]), set(state[bit - 1][1]))
            if (CRC32_POLY >> bit) & 1:
                c ^= fb_c
                d ^= fb_d
            new.append((c, d))
        state = new
    return state


def gen_crc(p: dict[str, int]) -> tuple[str, float]:
    """Parallel CRC-32 over W data bits per cycle (XOR-tree dominated)."""
    w = p["width"]
    eqs = crc32_step_equations(w)
    lines = [
        "  input clk,",
        "  input rst,",
        "  input en,",
        f"  input [{w - 1}:0] data,",
        "  output reg [31:0] crc",
        ");",
        f"  reg [{w - 1}:0] rdata;",
        "  reg ren;",
        "  wire [31:0] nxt;",
    ]
    for bit, (c, d) in enumerate(eqs):
        terms = [f"crc[{b}]" for b in sorted(c)] + [f"rdata[{b}]" for b in sorted(d)]
        expr = " ^ ".join(terms) if terms else "1'b0"
        lines.append(f"  assign nxt[{bit}] = {expr};")
    lines += [
        "  always @(posedge clk) begin",
        "    rdata <= data;",
        "    ren <= en;",
        "    if (rst) crc <= 32'hFFFFFFFF;",
        "    else if (ren) crc <= nxt;",
        "  end",
    ]
    return "\n".join(lines), 1.0


def gen_alu(p: dict[str, int]) -> tuple[str, float]:
    """Registered W-bit ALU with 8 operations."""
    w = p["width"]
    sh = max(1, (w - 1).bit_length())
    body = f"""  input clk,
  input [2:0] op,
  input [{w - 1}:0] a,
  input [{w - 1}:0] b,
  output reg [{w - 1}:0] y
);
  reg [2:0] rop;
  reg [{w - 1}:0] ra, rb;
  always @(posedge clk) begin
    rop <= op;
    ra <= a;
    rb <= b;
    case (rop)
      3'd0: y <= ra + rb;
      3'd1: y <= ra - rb;
      3'd2: y <= ra & rb;
      3'd3: y <= ra | rb;
      3'd4: y <= ra ^ rb;
      3'd5: y <= ra << rb[{sh - 1}:0];
      3'd6: y <= ra >> rb[{sh - 1}:0];
      default: y <= {{{{{w - 1}{{1'b0}}}}, (ra < rb)}};
    endcase
  end"""
    return body, 1.5


FAMILIES: dict[str, tuple[Callable, dict[str, tuple[int, int]]]] = {
    "mult": (gen_mult, {"width": (4, 32)}),
    "addtree": (gen_addtree, {"inputs": (2, 64), "width": (4, 32)}),
    "mac": (gen_mac, {"lanes": (1, 16), "width": (4, 16)}),
    "fifo": (gen_fifo, {"depth": (2, 128), "width": (1, 64)}),
    "fsm": (gen_fsm, {"states": (2, 256), "inputs": (1, 4), "outputs": (1, 16), "seed": (0, 999)}),
    "crc": (gen_crc, {"width": (1, 128)}),
    "alu": (gen_alu, {"width": (4, 64)}),
}


def generate(family: str, params: dict[str, int]) -> GeneratedDesign:
    if family not in FAMILIES:
        raise ValueError(f"unknown generator family: {family!r}")
    fn, bounds = FAMILIES[family]
    params = _check(dict(params), bounds)
    name = _name(family, params)
    body, period = fn(params)
    verilog = (
        f"// Generated by siliconai.rtlgen: family={family} params={params}\n"
        f"// origin=generated (synthetic RTL; labels come from real tool runs)\n"
        f"module {name} (\n{body}\nendmodule\n"
    )
    return GeneratedDesign(name, family, params, verilog, period)
