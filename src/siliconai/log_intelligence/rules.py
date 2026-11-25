"""Keyword baseline, error-line evidence baseline, and gold root-cause patterns (E5).

Written **only** from the development-design probe logs (gcd on nangate45, yosys and slang
frontends; ``data/d2/probe/dev_logs.tar.gz``) and committed before any D2 run was collected
(docs/experiments.md §11). Nothing here is tuned on D2.

- ``keyword_predict``: what an engineer who has read the dev logs would write. Rules are tried
  in priority order; the first rule with any matching line wins; no match -> ``"unknown"``.
- ``error_line_evidence``: the generic "grep for error, read the last few lines" heuristic.
- ``GOLD``: per class, the line(s) that state the root cause. Used only to *score* evidence.
"""

from __future__ import annotations

import re

from siliconai.log_intelligence.logs import Line

UNKNOWN = "unknown"
FAILURE_CLASSES = (
    "syntax_error",
    "elaboration_error",
    "missing_file",
    "sdc_error",
    "floorplan_capacity",
    "routing_resources",
    "out_of_memory",
    "timeout",
)

# Priority order matters: a timed-out or OOM-killed run can contain any earlier message.
KEYWORD_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("timeout", re.compile(r"\] Terminated\s*$|wait: No child processes")),
    ("out_of_memory", re.compile(r"\] Error (137|247)\s*$|\bKilled\b|bad_alloc|[Oo]ut of memory")),
    ("missing_file", re.compile(r"No rule to make target|Can't open include file")),
    ("syntax_error", re.compile(r"ERROR: syntax error")),
    (
        "elaboration_error",
        re.compile(
            r"is not part of the design|Re-definition of module|ERROR: Module .* not found"
            r"|is implicitly declared"
        ),
    ),
    ("sdc_error", re.compile(r"^invalid command name|\[ERROR STA-\d+\]")),
    ("routing_resources", re.compile(r"\[ERROR GRT-\d+\]|\[ERROR DRT-\d+\]|FlexDR|initMazeIdx")),
    ("floorplan_capacity", re.compile(r"\[ERROR (FLW|PDN|DPL|GPL|IFP)-\d+\]")),
)

ERROR_RE = re.compile(r"error", re.IGNORECASE)

GOLD: dict[str, re.Pattern[str]] = {
    "syntax_error": re.compile(r"ERROR: syntax error|ERROR: Design elaboration failed"),
    "elaboration_error": re.compile(
        r"is not part of the design|Re-definition of module|ERROR: Module .* not found"
        r"|is implicitly declared|ERROR: Design elaboration failed"
    ),
    "missing_file": re.compile(r"No rule to make target|Can't open include file|No such file"),
    "sdc_error": re.compile(r"^invalid command name|\[ERROR STA-\d+\]"),
    "floorplan_capacity": re.compile(r"\[ERROR (FLW|PDN|DPL|GPL|IFP)-\d+\]"),
    "routing_resources": re.compile(
        r"\[ERROR (GRT|DRT)-\d+\]|[Cc]ongestion too high|initMazeIdx|\[CRITICAL ORD-\d+\]"
    ),
    "out_of_memory": re.compile(r"\] Error (137|247)\s*$|\bKilled\b|bad_alloc|[Oo]ut of memory"),
    "timeout": re.compile(r"\] Terminated\s*$|wait: No child processes"),
}


def keyword_predict(lines: list[Line]) -> tuple[str, Line | None]:
    """Predicted class and the (last) line that triggered the winning rule."""
    for cls, rx in KEYWORD_RULES:
        hit = None
        for ln in lines:
            if rx.search(ln.text):
                hit = ln
        if hit is not None:
            return cls, hit
    return UNKNOWN, None


def error_line_evidence(lines: list[Line], k: int = 3) -> list[Line]:
    """The last ``k`` distinct lines containing "error" (case-insensitive)."""
    out: list[Line] = []
    seen: set[str] = set()
    for ln in reversed(lines):
        t = ln.text.strip()
        if ERROR_RE.search(t) and t not in seen:
            out.append(ln)
            seen.add(t)
            if len(out) == k:
                break
    return out


def is_gold(cls: str, line: Line) -> bool:
    rx = GOLD.get(cls)
    return bool(rx and rx.search(line.text))


def has_gold(cls: str, lines: list[Line]) -> bool:
    return any(is_gold(cls, ln) for ln in lines)
