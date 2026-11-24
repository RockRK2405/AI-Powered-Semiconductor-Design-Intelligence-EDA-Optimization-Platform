"""Preflight: check that flow-variable overrides are compatible with a design's config.

Found in the Phase 1 pilot: ``designs/nangate45/aes/config.mk`` fixes its floorplan with
``FLOORPLAN_DEF``, so overriding ``CORE_UTILIZATION`` makes ORFS stop at floorplan with
"Floorplan initialization methods are mutually exclusive". Six pilot runs were wasted that way.

The config.mk text is read *from the pinned image* (the design files live there), and is
treated as data: we only look for variable assignments with a regex; nothing is evaluated.
Limitation: assignments made through ``include`` or make conditionals are not followed.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Mapping

from siliconai.eda.orfs import DESIGN_CONFIG_RE, ORFS_FLOW

# Variables that fix the die/core outline; any of them makes the floorplan "fixed".
FLOORPLAN_FIXING_VARS = ("FLOORPLAN_DEF", "DIE_AREA", "CORE_AREA")
# Overrides that size the floorplan and therefore conflict with a fixed outline.
FLOORPLAN_SIZING_OVERRIDES = frozenset({"CORE_UTILIZATION", "CORE_ASPECT_RATIO"})

_ASSIGN_RE = re.compile(r"^[ \t]*(?:export[ \t]+)?([A-Z][A-Z0-9_]*)[ \t]*[?:+]?=", re.MULTILINE)
_MAX_CONFIG_BYTES = 256 * 1024

ConfigReader = Callable[[str], str]


def assigned_variables(config_text: str) -> set[str]:
    """Names of variables assigned in a config.mk (comments and indentation-safe)."""
    return set(_ASSIGN_RE.findall(config_text))


def fixes_floorplan(config_text: str) -> bool:
    return bool(assigned_variables(config_text) & set(FLOORPLAN_FIXING_VARS))


def incompatible_overrides(config_text: str, overrides: Mapping[str, str]) -> list[str]:
    """Override names that would conflict with this design's config (sorted)."""
    if not fixes_floorplan(config_text):
        return []
    return sorted(k for k in overrides if k in FLOORPLAN_SIZING_OVERRIDES)


def docker_config_reader(image: str, timeout_s: int = 120) -> ConfigReader:
    """Return a reader that fetches a design config.mk from inside the ORFS image."""
    cache: dict[str, str] = {}

    def read(design_config: str) -> str:
        if not DESIGN_CONFIG_RE.match(design_config):
            raise ValueError(f"design_config not allowed: {design_config!r}")
        if design_config not in cache:
            path = f"{ORFS_FLOW}/{design_config[2:]}"  # strip leading "./"
            proc = subprocess.run(
                ["docker", "run", "--rm", "--network", "none", image, "cat", path],
                capture_output=True,
                timeout=timeout_s,
                check=False,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"cannot read {design_config} from image (exit {proc.returncode})"
                )
            cache[design_config] = proc.stdout[:_MAX_CONFIG_BYTES].decode("utf-8", "replace")
        return cache[design_config]

    return read
