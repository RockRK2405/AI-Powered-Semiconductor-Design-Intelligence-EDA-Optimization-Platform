"""Fault injection for the D2 failure-log corpus (Phase 3, TODO P3-01).

A *faulted design* is an ORFS design directory named ``sai_fi_<hash>`` that is bind-mounted
read-only into the container, exactly like a generated design (``eda/orfs.py``). It holds:

- ``config.mk``: the base design's config text, unchanged, followed by an injection block of
  ``export`` lines (later assignments win in make);
- a mutated copy of the RTL top file and/or the SDC, when the fault touches them.

Bundled ORFS designs are not copied: their unmodified sources stay where they are in the image,
and the config refers to them by ``$(DESIGN_HOME)`` paths.

Every injector is a deterministic text transform from a fixed template: no user-supplied text,
nothing evaluated. The label of a run is the injected (class, variant), recorded *before* the
run. Whether the fault actually makes the flow fail is an outcome, recorded after.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from siliconai.rtlgen.generators import generate
from siliconai.rtlgen.orfs_design import orfs_design_files

FI_PREFIX = "sai_fi_"
_PATH_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./\-]{0,200}$")
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

# The lowest three signal-routing layers per platform (MIN_ROUTING_LAYER first), from the platform
# configs in the pinned image. nangate45 assigns MAX_ROUTING_LAYER and MIN_CLK_ROUTING_LAYER with
# "=" in its platform config, which is read after the design config, so the injection uses make's
# ``override``. The clock layer range is capped too (else ODB-0137, a configuration error).
ROUTING_LAYERS = {
    "nangate45": ("metal2", "metal3", "metal4"),
    "sky130hd": ("met1", "met2", "met3"),
    "asap7": ("M2", "M3", "M4"),
    "gf180": ("Metal2", "Metal3", "Metal4"),
    "ihp-sg13g2": ("Metal2", "Metal3", "Metal4"),
}


@dataclass(frozen=True)
class BaseDesign:
    """A design to inject faults into.

    ``sources`` are paths relative to ``flow/designs`` (bundled) or file names inside the fault
    directory (generated). ``top_file`` is the one RTL mutations are applied to.
    """

    name: str  # DESIGN_NAME (top module)
    platform: str
    group: str
    origin: str  # "orfs" | "generated"
    config_text: str
    sources: tuple[str, ...]
    top_file: str
    sdc: str
    files: dict[str, str] = field(default_factory=dict)  # texts we may mutate: top + sdc
    fixed_floorplan: bool = False
    generated: tuple[str, str] | None = None  # (family, params-json) for generated bases
    # Measured on a clean run of this design (D1): resource faults are scaled to them.
    ref_wall_s: float | None = None
    ref_peak_mb: float | None = None

    def __post_init__(self) -> None:
        if not _IDENT_RE.match(self.name):
            raise ValueError(f"bad design name: {self.name!r}")
        if self.platform not in ROUTING_LAYERS:
            raise ValueError(f"unsupported platform: {self.platform!r}")
        for p in (*self.sources, self.top_file, self.sdc):
            if not _PATH_RE.match(p) or ".." in p.split("/"):
                raise ValueError(f"bad path: {p!r}")
        if self.top_file not in self.sources:
            raise ValueError("top_file must be one of sources")


@dataclass(frozen=True)
class Injection:
    rtl: str | None = None  # mutated text of the top file
    sdc: str | None = None  # mutated SDC text
    config: tuple[str, ...] = ()  # extra config.mk lines
    memory_mb: int | None = None
    timeout_s: int | None = None


Injector = Callable[[BaseDesign], Injection]


# ---------------------------------------------------------------- RTL text transforms
def _last_endmodule(text: str) -> int:
    i = text.rfind("endmodule")
    if i < 0:
        raise ValueError("no endmodule")
    return i


def _module_header_end(text: str, top: str) -> int:
    """Index just after the ``);`` closing the port list of module ``top``."""
    m = re.search(rf"\bmodule\s+{re.escape(top)}\b", text)
    if not m:
        raise ValueError(f"module {top} not found")
    j = text.find(");", m.end())
    if j < 0:
        raise ValueError("module header not closed")
    return j + 2


def drop_semicolon(text: str) -> str:
    """Remove the ';' of the last assignment-like statement."""
    lines = text.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        s = lines[i].rstrip()
        if s.endswith(";") and ("=" in s) and not s.lstrip().startswith(("//", "parameter")):
            lines[i] = s[:-1]
            return "\n".join(lines)
    raise ValueError("no statement ending in ';'")


def misspell_endmodule(text: str) -> str:
    i = _last_endmodule(text)
    return text[:i] + "endmodul" + text[i + len("endmodule") :]


def stray_token(text: str, top: str) -> str:
    j = _module_header_end(text, top)
    return text[:j] + "\n  @@ sai_stray_token @@\n" + text[j:]


def drop_end(text: str) -> str:
    """Remove the last block-closing ``end`` (begin/end becomes unbalanced)."""
    ms = list(re.finditer(r"^[ \t]*end[ \t]*(//[^\n]*)?$", text, re.MULTILINE))
    if not ms:
        raise ValueError("no standalone 'end' line")
    m = ms[-1]
    return text[: m.start()] + text[m.end() :]


def insert_before_endmodule(text: str, line: str) -> str:
    i = _last_endmodule(text)
    return text[:i] + line + "\n" + text[i:]


# ---------------------------------------------------------------- injectors
def _syntax_missing_semicolon(b: BaseDesign) -> Injection:
    return Injection(rtl=drop_semicolon(b.files[b.top_file]))


def _syntax_misspelled_keyword(b: BaseDesign) -> Injection:
    return Injection(rtl=misspell_endmodule(b.files[b.top_file]))


def _syntax_stray_token(b: BaseDesign) -> Injection:
    return Injection(rtl=stray_token(b.files[b.top_file], b.name))


def _syntax_unbalanced_end(b: BaseDesign) -> Injection:
    return Injection(rtl=drop_end(b.files[b.top_file]))


def _elab_undefined_module(b: BaseDesign) -> Injection:
    return Injection(
        rtl=insert_before_endmodule(b.files[b.top_file], "  sai_missing_block u_sai_missing ();")
    )


def _elab_duplicate_module(b: BaseDesign) -> Injection:
    return Injection(rtl=b.files[b.top_file] + f"\nmodule {b.name} ();\nendmodule\n")


def _elab_wrong_top(b: BaseDesign) -> Injection:
    return Injection(config=(f"export DESIGN_NAME = {b.name}_sai_missing_top",))


def _elab_undeclared_identifier(b: BaseDesign) -> Injection:
    text = "`default_nettype none\n" + insert_before_endmodule(
        b.files[b.top_file], "  assign sai_undeclared_net = 1'b0;"
    )
    return Injection(rtl=text)


def _missing_verilog(b: BaseDesign) -> Injection:
    return Injection(config=("export VERILOG_FILES += $(SAI_FI_DIR)/sai_missing_block.v",))


def _missing_sdc(b: BaseDesign) -> Injection:
    return Injection(config=("export SDC_FILE = $(SAI_FI_DIR)/sai_missing_constraints.sdc",))


def _missing_include(b: BaseDesign) -> Injection:
    return Injection(rtl='`include "sai_missing_defs.vh"\n' + b.files[b.top_file])


def _missing_pdn(b: BaseDesign) -> Injection:
    return Injection(config=("export PDN_TCL = $(SAI_FI_DIR)/sai_missing_pdn.tcl",))


def _sdc_unknown_command(b: BaseDesign) -> Injection:
    return Injection(sdc=b.files[b.sdc] + "\nsai_set_bogus_constraint 1.0\n")


def _sdc_unknown_clock(b: BaseDesign) -> Injection:
    # (A create_clock on a missing port only warns, STA-0366: masked in the dev probe.)
    return Injection(
        sdc=b.files[b.sdc] + "\nset_input_delay 1.0 -clock sai_no_clock [all_inputs]\n"
    )


def _sdc_bad_value(b: BaseDesign) -> Injection:
    return Injection(sdc=b.files[b.sdc] + "\ncreate_clock -name sai_clk3 -period abc\n")


def _sdc_unbalanced_bracket(b: BaseDesign) -> Injection:
    return Injection(sdc=b.files[b.sdc] + "\nset sai_x [expr 1 + 2\n")


def _floorplan_lines(b: BaseDesign, util: str) -> tuple[str, ...]:
    if b.fixed_floorplan:  # cannot size by utilization: shrink the fixed outline instead
        return ("export FLOORPLAN_DEF =", "export DIE_AREA = 0 0 6 6", "export CORE_AREA = 1 1 5 5")
    return (f"export CORE_UTILIZATION = {util}",)


def _util_core_util_high(b: BaseDesign) -> Injection:
    return Injection(config=_floorplan_lines(b, "120"))


def _util_near_full(b: BaseDesign) -> Injection:
    # (PLACE_DENSITY far below utilization is silently raised by ORFS: masked in the probe.)
    return Injection(config=(*_floorplan_lines(b, "99"), "export PLACE_DENSITY_LB_ADDON = 0"))


def _util_die_too_small(b: BaseDesign) -> Injection:
    return Injection(
        config=(
            "export CORE_UTILIZATION =",
            "export FLOORPLAN_DEF =",
            "export DIE_AREA = 0 0 6 6",
            "export CORE_AREA = 1 1 5 5",
        )
    )


def _congestion_layers(n: int) -> Injector:
    """Signal and clock routing limited to the lowest ``n`` routing layers."""

    def inj(b: BaseDesign) -> Injection:
        layers = ROUTING_LAYERS[b.platform]
        return Injection(
            config=(
                f"override export MAX_ROUTING_LAYER = {layers[n - 1]}",
                f"override export MIN_CLK_ROUTING_LAYER = {layers[0]}",
            )
        )

    return inj


def _util_no_whitespace(b: BaseDesign) -> Injection:
    # Placement density equal to utilization: no room to legalize (DPL-0033 in the dev probe,
    # where it was first tried as a congestion recipe).
    lines = () if b.fixed_floorplan else (*_floorplan_lines(b, "70"),)
    return Injection(
        config=(*lines, "export PLACE_DENSITY_LB_ADDON = 0", "export GPL_ROUTABILITY_DRIVEN = 0")
    )


def _timing_impossible_clock(b: BaseDesign) -> Injection:
    sdc = re.sub(r"(set\s+clk_period\s+)([0-9.eE+-]+)", r"\g<1>0.001", b.files[b.sdc], count=1)
    if sdc == b.files[b.sdc]:
        sdc = re.sub(r"(-period\s+)([0-9.eE+-]+)", r"\g<1>0.001", sdc, count=1)
    if sdc == b.files[b.sdc]:
        raise ValueError("no clock period found in SDC")
    return Injection(sdc=sdc)


MIN_FAULT_MEMORY_MB = 128
MIN_FAULT_TIMEOUT_S = 5


def _oom(frac: float) -> Injector:
    """Container memory capped at ``frac`` of the design's clean peak RSS."""

    def inj(b: BaseDesign) -> Injection:
        if not b.ref_peak_mb:
            raise ValueError(f"{b.name}: out_of_memory needs ref_peak_mb")
        return Injection(memory_mb=max(MIN_FAULT_MEMORY_MB, round(frac * b.ref_peak_mb)))

    return inj


def _timeout(frac: float) -> Injector:
    """Flow timeout at ``frac`` of the design's clean wall time."""

    def inj(b: BaseDesign) -> Injection:
        if not b.ref_wall_s:
            raise ValueError(f"{b.name}: timeout needs ref_wall_s")
        return Injection(timeout_s=max(MIN_FAULT_TIMEOUT_S, round(frac * b.ref_wall_s)))

    return inj


# Masked in the dev probe (ORFS completes with negative slack; failing on timing is an
# outcome-risk question, Phase 7), so it is not part of the D2 taxonomy.
MASKED_FAULTS: dict[tuple[str, str], Injector] = {
    ("timing_infeasible", "impossible_clock"): _timing_impossible_clock,
    ("sdc_error", "unknown_clock"): _sdc_unknown_clock,  # STA-0138 warning only
    ("floorplan_capacity", "near_full"): _util_near_full,  # same FLW-0024 as core_util_high
    ("routing_congestion", "one_layer"): _congestion_layers(1),  # ODB-0137 config error
}

# (class, variant) -> injector. The taxonomy follows research/03 G3; which of these actually
# make the flow fail is measured by the dev-design probe (docs/experiments.md §11).
FAULTS: dict[tuple[str, str], Injector] = {
    ("syntax_error", "missing_semicolon"): _syntax_missing_semicolon,
    ("syntax_error", "misspelled_keyword"): _syntax_misspelled_keyword,
    ("syntax_error", "stray_token"): _syntax_stray_token,
    ("syntax_error", "unbalanced_end"): _syntax_unbalanced_end,
    ("elaboration_error", "undefined_module"): _elab_undefined_module,
    ("elaboration_error", "duplicate_module"): _elab_duplicate_module,
    ("elaboration_error", "wrong_top"): _elab_wrong_top,
    ("elaboration_error", "undeclared_identifier"): _elab_undeclared_identifier,
    ("missing_file", "verilog"): _missing_verilog,
    ("missing_file", "sdc"): _missing_sdc,
    ("missing_file", "include"): _missing_include,
    ("missing_file", "pdn_script"): _missing_pdn,
    ("sdc_error", "unknown_command"): _sdc_unknown_command,
    ("sdc_error", "bad_value"): _sdc_bad_value,
    ("sdc_error", "unbalanced_bracket"): _sdc_unbalanced_bracket,
    ("floorplan_capacity", "core_util_high"): _util_core_util_high,
    ("floorplan_capacity", "no_whitespace"): _util_no_whitespace,
    ("floorplan_capacity", "die_too_small"): _util_die_too_small,
    ("routing_congestion", "two_layers"): _congestion_layers(2),
    ("routing_congestion", "three_layers"): _congestion_layers(3),
    ("out_of_memory", "mem_30pct"): _oom(0.30),
    ("out_of_memory", "mem_55pct"): _oom(0.55),
    ("out_of_memory", "mem_80pct"): _oom(0.80),
    ("timeout", "t_25pct"): _timeout(0.25),
    ("timeout", "t_50pct"): _timeout(0.50),
    ("timeout", "t_80pct"): _timeout(0.80),
    ("none", "clean"): lambda b: Injection(),
}


@dataclass(frozen=True)
class FaultedDesign:
    dir_name: str
    platform: str
    design_config: str  # ./designs/<platform>/<dir_name>/config.mk
    files: dict[str, str]
    fault_class: str
    variant: str
    memory_mb: int | None
    timeout_s: int | None


def fault_dir_name(base: BaseDesign, fault_class: str, variant: str) -> str:
    key = json.dumps([base.platform, base.name, base.group, fault_class, variant])
    digest = hashlib.sha256(key.encode()).hexdigest()[:10]
    return f"{FI_PREFIX}{base.name[:24]}_{digest}"


def build_faulted(base: BaseDesign, fault_class: str, variant: str) -> FaultedDesign:
    """Apply one fault to a base design; returns the files of the faulted design dir."""
    injector = FAULTS.get((fault_class, variant))
    if injector is None:
        raise KeyError(f"unknown fault {fault_class}/{variant}")
    inj = injector(base)
    dir_name = fault_dir_name(base, fault_class, variant)
    here = f"$(DESIGN_HOME)/{base.platform}/{dir_name}"

    def src_path(p: str) -> str:
        return f"{here}/{p}" if base.origin == "generated" else f"$(DESIGN_HOME)/{p}"

    files: dict[str, str] = {}
    lines = [
        "",
        f"# ---- SiliconAI fault injection: {fault_class}/{variant} (base {base.name}) ----",
        f"SAI_FI_DIR = {here}",
    ]
    if base.origin == "generated":  # its sources live in the fault dir itself
        files.update({p: t for p, t in base.files.items()})
    nick = _nickname(base)
    lines.append(f"export DESIGN_NICKNAME = {nick}")
    top_name = Path(base.top_file).name
    srcs = [
        f"{here}/{top_name}" if (p == base.top_file and inj.rtl is not None) else src_path(p)
        for p in base.sources
    ]
    lines.append("export VERILOG_FILES = " + " ".join(srcs))
    sdc_name = Path(base.sdc).name
    lines.append(
        f"export SDC_FILE = {here}/{sdc_name}"
        if inj.sdc is not None
        else f"export SDC_FILE = {src_path(base.sdc)}"
    )
    if inj.rtl is not None:
        files[top_name] = inj.rtl
    if inj.sdc is not None:
        files[sdc_name] = inj.sdc
    lines += list(inj.config)
    files["config.mk"] = base.config_text.rstrip("\n") + "\n" + "\n".join(lines) + "\n"
    return FaultedDesign(
        dir_name=dir_name,
        platform=base.platform,
        design_config=f"./designs/{base.platform}/{dir_name}/config.mk",
        files=files,
        fault_class=fault_class,
        variant=variant,
        memory_mb=inj.memory_mb,
        timeout_s=inj.timeout_s,
    )


_NICK_RE = re.compile(r"^[ \t]*(?:export[ \t]+)?DESIGN_NICKNAME[ \t]*[:?]?=[ \t]*(\S+)", re.M)


def _nickname(base: BaseDesign) -> str:
    m = _NICK_RE.search(base.config_text)
    nick = m.group(1) if m else base.name
    return nick if _IDENT_RE.match(nick) else base.name


def write_faulted(fd: FaultedDesign, root: Path) -> Path:
    """Write the faulted design to ``root/<platform>/<dir_name>/`` (idempotent)."""
    out = Path(root) / fd.platform / fd.dir_name
    out.mkdir(parents=True, exist_ok=True)
    for name, text in fd.files.items():
        if "/" in name or not _PATH_RE.match(name):
            raise ValueError(f"bad file name {name!r}")
        p = out / name
        if not p.exists() or p.read_text() != text:
            p.write_text(text)
    return out


def generated_base(family: str, params: dict[str, int], platform: str, group: str) -> BaseDesign:
    """A generated design as a fault base. Its files are rewritten into each fault dir."""
    design = generate(family, params)
    files = orfs_design_files(design, platform, dir_name="SAI_DIR_PLACEHOLDER")
    config = files.pop("config.mk")
    # Drop the generator's own VERILOG_FILES/SDC_FILE: the injection block sets them.
    config = "\n".join(
        ln for ln in config.splitlines() if not re.match(r"export (VERILOG_FILES|SDC_FILE)\b", ln)
    )
    config = config.replace("$(DESIGN_HOME)/" + platform + "/SAI_DIR_PLACEHOLDER", "$(SAI_FI_DIR)")
    return BaseDesign(
        name=design.name,
        platform=platform,
        group=group,
        origin="generated",
        config_text=config + "\n",
        sources=("rtl.v",),
        top_file="rtl.v",
        sdc="constraint.sdc",
        files=files,
        generated=(family, json.dumps(params, sort_keys=True)),
    )


_MAX_SOURCE_BYTES = 2 * 1024 * 1024
FileReader = Callable[[str], str]


def image_file_reader(image: str, timeout_s: int = 120) -> FileReader:
    """Read a text file under ``flow/designs`` from the pinned ORFS image (cached).

    The path is validated against a strict pattern; the container has no network.
    """
    import subprocess

    from siliconai.eda.orfs import ORFS_FLOW

    cache: dict[str, str] = {}

    def read(rel: str) -> str:
        if not _PATH_RE.match(rel) or ".." in rel.split("/"):
            raise ValueError(f"bad path: {rel!r}")
        if rel not in cache:
            proc = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    image,
                    "cat",
                    f"{ORFS_FLOW}/designs/{rel}",
                ],
                capture_output=True,
                timeout=timeout_s,
                check=False,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"cannot read designs/{rel} from image")
            cache[rel] = proc.stdout[:_MAX_SOURCE_BYTES].decode("utf-8", "replace")
        return cache[rel]

    return read


def bundled_base(
    name: str,
    platform: str,
    group: str,
    sources: tuple[str, ...],
    top_file: str,
    sdc: str,
    reader: FileReader,
    config: str | None = None,
) -> BaseDesign:
    """A bundled ORFS design as a fault base (``config`` defaults to ``<platform>/<group>``)."""
    from siliconai.sweep.preflight import fixes_floorplan

    cfg_rel = config or f"{platform}/{group}/config.mk"
    config_text = reader(cfg_rel)
    return BaseDesign(
        name=name,
        platform=platform,
        group=group,
        origin="orfs",
        config_text=config_text,
        sources=sources,
        top_file=top_file,
        sdc=sdc,
        files={top_file: reader(top_file), sdc: reader(sdc)},
        fixed_floorplan=fixes_floorplan(config_text),
    )
