"""Command-line entry point: `siliconai <command>`."""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from siliconai.config import Settings
from siliconai.data.registry import Registry
from siliconai.eda.collect import execute_and_record, orfs_design_record
from siliconai.eda.orfs import image_digest
from siliconai.eda.runner import gnu_time_available
from siliconai.logging_utils import setup_logging

log = logging.getLogger("siliconai")


def _version(cmd: list[str]) -> str:
    if shutil.which(cmd[0]) is None:
        return "NOT FOUND"
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"error: {exc}"
    text = (out.stdout or out.stderr).strip().splitlines()
    return text[0] if text else "unknown"


def cmd_doctor(settings: Settings) -> int:
    checks = {
        "python": sys.version.split()[0],
        "GNU time": "ok" if gnu_time_available() else "NOT FOUND",
        "docker": _version(["docker", "--version"]),
        "ORFS image": image_digest(settings.orfs_image) or "NOT PULLED / daemon down",
        "yosys (host)": _version(["yosys", "-V"]),
        "iverilog (host)": _version(["iverilog", "-V"]),
        "verilator (host)": _version(["verilator", "--version"]),
        "home": str(settings.home),
    }
    for key, value in checks.items():
        print(f"{key:18s} {value}")
    return 0


def _parse_overrides(pairs: Sequence[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--set expects KEY=VALUE, got {pair!r}")
        key, value = pair.split("=", 1)
        out[key] = value
    return out


def cmd_orfs_run(settings: Settings, args: argparse.Namespace) -> int:
    settings.ensure_dirs()
    overrides = _parse_overrides(args.set or [])
    try:
        record = orfs_design_record(args.design_config, args.design_group)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    failures = 0
    with Registry(settings.db_path) as reg:
        for rep in range(args.repeat_start, args.repeat_start + args.repeat):
            run = execute_and_record(
                reg,
                record,
                args.design_config,
                overrides,
                work_dir=settings.runs_dir,
                image=settings.orfs_image,
                timeout_s=args.timeout or settings.tool_timeout_s,
                repeat_index=rep,
                concurrency=args.concurrency,
                cpuset=args.cpuset,
                skip_existing=not args.force,
            )
            print(f"{run.run_id}\t{run.status}\t{run.wall_s or 0:.1f}s")
            failures += run.status != "success"
    return 1 if failures else 0


def cmd_sweep(settings: Settings, args: argparse.Namespace) -> int:
    from siliconai.sweep.preflight import docker_config_reader
    from siliconai.sweep.runner import run_sweep
    from siliconai.sweep.spec import load_spec

    settings.ensure_dirs()
    spec = load_spec(args.spec)
    with Registry(settings.db_path) as reg:
        report = run_sweep(
            spec,
            reg,
            work_dir=settings.runs_dir,
            image=settings.orfs_image,
            budget_s=args.budget_min * 60,
            config_reader=docker_config_reader(settings.orfs_image),
            prune=not args.no_prune,
            dry_run=args.dry_run,
            gen_root=settings.home / "generated",
        )
    print(f"sweep {spec.name}: {report.summary()}")
    for item in report.rejected_preflight:
        print(f"  preflight rejected {item}")
    return 1 if report.stopped_reason else 0


def cmd_export(settings: Settings, args: argparse.Namespace) -> int:
    from siliconai.data.exchange import export_jsonl

    with Registry(settings.db_path) as reg:
        counts = export_jsonl(reg, args.out)
    print(f"exported {counts} to {args.out}")
    return 0


def cmd_import(settings: Settings, args: argparse.Namespace) -> int:
    from siliconai.data.exchange import import_jsonl

    settings.ensure_dirs()
    with Registry(settings.db_path) as reg:
        counts = import_jsonl(reg, args.src)
    print(f"imported {counts} from {args.src}")
    return 0


def cmd_forget(settings: Settings, args: argparse.Namespace) -> int:
    """Delete a run so the next sweep chunk re-runs it; the reason is appended to a log."""
    import json
    from datetime import UTC, datetime

    with Registry(settings.db_path) as reg:
        if not reg.delete_run(args.run_id):
            raise SystemExit(f"no such run: {args.run_id}")
    args.log.parent.mkdir(parents=True, exist_ok=True)
    entry = {"run_id": args.run_id, "reason": args.reason, "at": datetime.now(UTC).isoformat()}
    with args.log.open("a") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    print(f"forgot {args.run_id}; logged to {args.log}")
    return 0


def cmd_runs(settings: Settings) -> int:
    with Registry(settings.db_path) as reg:
        print(f"{'run_id':40s} {'stage':10s} {'wall_s':>9s} {'cpu_s':>9s} {'peak_MB':>8s}")
        for row in reg.stage_summary():
            print(
                f"{row['run_id']:40s} {row['stage']:10s} {row['wall_s']:9.2f} "
                f"{row['cpu_s'] or 0:9.2f} {row['peak_rss_mb'] or 0:8.0f}"
            )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="siliconai")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="check toolchain and configuration")

    run = sub.add_parser("orfs-run", help="run one ORFS design and record it")
    run.add_argument(
        "--design-config", required=True, help="./designs/<platform>/<design>/config.mk"
    )
    run.add_argument("--set", action="append", metavar="KEY=VALUE", help="flow variable override")
    run.add_argument("--repeat", type=int, default=1)
    run.add_argument("--repeat-start", type=int, default=0)
    run.add_argument("--timeout", type=int, default=None, help="seconds")
    run.add_argument("--cpuset", default=None, help="pin container to CPUs, e.g. 0-1")
    run.add_argument("--concurrency", type=int, default=1, help="number of runs in parallel")
    run.add_argument("--design-group", default=None)
    run.add_argument("--force", action="store_true", help="re-run even if recorded")

    sub.add_parser("runs", help="per-stage summary of recorded runs")

    sweep = sub.add_parser("sweep", help="run one budgeted, resumable chunk of a sweep spec")
    sweep.add_argument("spec", type=Path, help="sweep spec YAML")
    sweep.add_argument("--budget-min", type=float, required=True, help="chunk wall budget")
    sweep.add_argument("--dry-run", action="store_true", help="plan only; run nothing")
    sweep.add_argument("--no-prune", action="store_true", help="keep results/ and objects/")

    exp = sub.add_parser("export", help="export the registry as JSONL")
    exp.add_argument("--out", type=Path, required=True)
    fgt = sub.add_parser("forget", help="delete a run (it will be re-run) and log why")
    fgt.add_argument("run_id")
    fgt.add_argument("--reason", required=True)
    fgt.add_argument("--log", type=Path, required=True, help="JSONL log of removed runs")
    imp = sub.add_parser("import", help="load registry JSONL (e.g. committed data)")
    imp.add_argument("--src", type=Path, required=True)

    args = parser.parse_args(argv)
    settings = Settings.from_env()
    setup_logging(settings.log_level)
    if args.command == "doctor":
        return cmd_doctor(settings)
    if args.command == "orfs-run":
        return cmd_orfs_run(settings, args)
    if args.command == "runs":
        return cmd_runs(settings)
    if args.command == "sweep":
        return cmd_sweep(settings, args)
    if args.command == "export":
        return cmd_export(settings, args)
    if args.command == "forget":
        return cmd_forget(settings, args)
    if args.command == "import":
        return cmd_import(settings, args)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
