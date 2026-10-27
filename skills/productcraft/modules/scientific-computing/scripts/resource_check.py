#!/usr/bin/env python3
"""ProductCraft Scientific Computing: read-only check of usable compute resources.

Reports what this process can actually use before heavy work starts:

- CPU cores after CPU affinity, a container CPU quota (cgroup v1 or v2) and a
  Slurm allocation, plus thread variables that would oversubscribe them;
- memory after container and Slurm limits;
- free disk space at a path and whether that path is writable;
- whether common GPU management tools are on PATH and which GPU visibility
  variables are set;
- whether a batch scheduler client is present and whether this process runs
  inside a job (a scheduler client outside a job usually means a login node).

It reads files under /proc and /sys, environment variables and PATH. It never
runs another program, writes files, changes settings or uses the network. GPU
tools are looked up on PATH, never executed, so the number and health of GPUs
stay unknown; confirm them with the framework that will use them.

Exit codes: 0 = report printed and every --need-* requirement met;
1 = at least one requirement not met; 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional

VERSION = "1.0.0"
GIB = 1024 ** 3
MIB = 1024 ** 2
UNLIMITED_SENTINEL = 2 ** 60  # cgroup v1 reports "no limit" as a huge number

GPU_TOOLS = ("nvidia-smi", "rocm-smi", "amd-smi", "xpu-smi")
GPU_VISIBILITY_VARS = ("CUDA_VISIBLE_DEVICES", "HIP_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES",
                       "ZE_AFFINITY_MASK")
SCHEDULER_TOOLS = (("sbatch", "Slurm"), ("qsub", "PBS or Grid Engine"), ("bsub", "LSF"))
JOB_ID_VARS = ("SLURM_JOB_ID", "PBS_JOBID", "JOB_ID", "LSB_JOBID")
THREAD_VARS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
               "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")
HIDDEN_GPU_VALUES = {"", "-1", "none", "nodevfiles"}


# --- small readers and parsers ------------------------------------------------

def read_text(path: Path) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def to_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_meminfo(text: str) -> Dict[str, int]:
    """Parse /proc/meminfo into bytes per field."""
    result: Dict[str, int] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        parts = rest.split()
        if not parts:
            continue
        number = to_int(parts[0])
        if number is None:
            continue
        unit = parts[1].lower() if len(parts) > 1 else ""
        result[key.strip()] = number * 1024 if unit == "kb" else number
    return result


def parse_cpu_max(text: Optional[str]) -> Optional[float]:
    """cgroup v2 cpu.max: 'max 100000' means no quota, '200000 100000' means 2 CPUs."""
    if not text:
        return None
    parts = text.split()
    if not parts or parts[0] == "max":
        return None
    quota = to_int(parts[0])
    period = to_int(parts[1]) if len(parts) > 1 else 100000
    if not quota or not period or quota <= 0 or period <= 0:
        return None
    return quota / period


def parse_cfs_quota(quota_text: Optional[str], period_text: Optional[str]) -> Optional[float]:
    """cgroup v1 cpu.cfs_quota_us and cpu.cfs_period_us; a quota of -1 means no limit."""
    quota = to_int(quota_text)
    period = to_int(period_text)
    if quota is None or period is None or quota <= 0 or period <= 0:
        return None
    return quota / period


def parse_memory_limit(text: Optional[str]) -> Optional[int]:
    if text is None:
        return None
    stripped = text.strip()
    if not stripped or stripped == "max":
        return None
    value = to_int(stripped)
    if value is None or value <= 0 or value >= UNLIMITED_SENTINEL:
        return None
    return value


def gib(value: Optional[int]) -> Optional[float]:
    return None if value is None else round(value / GIB, 2)


# --- containers (cgroups) -----------------------------------------------------

def _ancestors(base: Path, relative: str) -> List[Path]:
    """The process's cgroup directory and every parent up to the hierarchy root."""
    parts = [p for p in relative.strip().split("/") if p]
    dirs = [base.joinpath(*parts[:i]) for i in range(len(parts), 0, -1)]
    dirs.append(base)
    return dirs


def _min(values: List[Optional[float]]) -> Optional[float]:
    present = [v for v in values if v is not None]
    return min(present) if present else None


def container_limits(root: Path) -> Dict[str, object]:
    """CPU quota and memory limit from cgroups, taking the tightest limit up the tree."""
    base = root / "sys" / "fs" / "cgroup"
    membership = read_text(root / "proc" / "self" / "cgroup") or ""
    v2_path: Optional[str] = None
    v1_paths: Dict[str, str] = {}
    for line in membership.splitlines():
        fields = line.split(":", 2)
        if len(fields) != 3:
            continue
        hierarchy, controllers, path = fields
        if hierarchy == "0" and controllers == "":
            v2_path = path
        else:
            for controller in controllers.split(","):
                v1_paths[controller] = path

    result: Dict[str, object] = {"version": None, "cpu_quota": None,
                                 "memory_limit_bytes": None, "memory_used_bytes": None}
    if (base / "cgroup.controllers").exists():
        dirs = _ancestors(base, v2_path or "/")
        quotas = [parse_cpu_max(read_text(d / "cpu.max")) for d in dirs]
        limits = [parse_memory_limit(read_text(d / "memory.max")) for d in dirs]
        used = next((to_int(read_text(d / "memory.current")) for d in dirs
                     if read_text(d / "memory.current") is not None), None)
        result.update(version="v2", cpu_quota=_min(quotas), memory_limit_bytes=_min(limits),
                      memory_used_bytes=used)
        return result

    cpu_dirs: List[Path] = []
    for name in ("cpu,cpuacct", "cpu"):
        if (base / name).is_dir():
            cpu_dirs = _ancestors(base / name, v1_paths.get("cpu", "/"))
            break
    mem_dirs = _ancestors(base / "memory", v1_paths.get("memory", "/")) if (base / "memory").is_dir() else []
    if cpu_dirs or mem_dirs:
        quotas = [parse_cfs_quota(read_text(d / "cpu.cfs_quota_us"), read_text(d / "cpu.cfs_period_us"))
                  for d in cpu_dirs]
        limits = [parse_memory_limit(read_text(d / "memory.limit_in_bytes")) for d in mem_dirs]
        used = next((to_int(read_text(d / "memory.usage_in_bytes")) for d in mem_dirs
                     if read_text(d / "memory.usage_in_bytes") is not None), None)
        result.update(version="v1", cpu_quota=_min(quotas), memory_limit_bytes=_min(limits),
                      memory_used_bytes=used)
    return result


# --- schedulers ---------------------------------------------------------------

def slurm_allocation(env: Mapping[str, str]) -> Optional[Dict[str, object]]:
    if not env.get("SLURM_JOB_ID"):
        return None
    cpus_per_task = to_int(env.get("SLURM_CPUS_PER_TASK"))
    cpus_on_node = to_int(env.get("SLURM_CPUS_ON_NODE"))
    memory = None
    per_node = to_int(env.get("SLURM_MEM_PER_NODE"))
    per_cpu = to_int(env.get("SLURM_MEM_PER_CPU"))
    if per_node:
        memory = per_node * MIB
    elif per_cpu and (cpus_on_node or cpus_per_task):
        memory = per_cpu * MIB * (cpus_on_node or cpus_per_task)
    gpus = to_int(env.get("SLURM_GPUS_ON_NODE"))
    if gpus is None:
        listed = env.get("SLURM_JOB_GPUS") or env.get("SLURM_STEP_GPUS")
        if listed:
            gpus = len([g for g in listed.split(",") if g.strip()])
    return {
        "job_id": env.get("SLURM_JOB_ID"),
        "partition": env.get("SLURM_JOB_PARTITION"),
        "cpus": cpus_per_task or cpus_on_node,
        "memory_bytes": memory,
        "gpus": gpus,
    }


def scheduler_report(env: Mapping[str, str], search_path: Optional[str]) -> Dict[str, object]:
    clients = sorted(name for tool, name in SCHEDULER_TOOLS if shutil.which(tool, path=search_path))
    inside = sorted(var for var in JOB_ID_VARS if env.get(var))
    report: Dict[str, object] = {"clients_on_path": clients, "inside_job": bool(inside),
                                 "job_variables": inside, "warnings": []}
    if clients and not inside:
        report["warnings"].append(
            "a scheduler client is on PATH but this process is not inside a job: this is probably a "
            "login or submit node, so submit heavy work through the scheduler instead of running it here")
    return report


# --- CPU, memory, disk, GPU ---------------------------------------------------

def logical_cpu_count() -> Optional[int]:
    return os.cpu_count()


def affinity_cpu_count() -> Optional[int]:
    getter = getattr(os, "sched_getaffinity", None)
    if getter is None:
        return None
    try:
        return len(getter(0))
    except OSError:
        return None


def cpu_report(env: Mapping[str, str], logical: Optional[int], affinity: Optional[int],
               limits: Mapping[str, object], slurm: Optional[Mapping[str, object]]) -> Dict[str, object]:
    candidates = []
    if logical:
        candidates.append((logical, "logical CPUs"))
    if affinity:
        candidates.append((affinity, "CPU affinity"))
    quota = limits.get("cpu_quota")
    if isinstance(quota, (int, float)) and quota > 0:
        candidates.append((max(1, math.floor(quota)), f"container CPU quota {quota:g}"))
    if slurm and slurm.get("cpus"):
        candidates.append((int(slurm["cpus"]), "Slurm allocation"))
    usable, limited_by = (min(candidates, key=lambda c: c[0]) if candidates else (None, "unknown"))
    threads: Dict[str, str] = {var: env[var] for var in THREAD_VARS if env.get(var)}
    warnings: List[str] = []
    for var, value in threads.items():
        number = to_int(value)
        if usable and number and number > usable:
            warnings.append(f"{var}={number} exceeds the {usable} usable cores; threads will contend")
    if usable and not threads and usable > 1:
        warnings.append("no thread variables set: BLAS and OpenMP libraries may start one thread per "
                        "logical CPU in every worker process; set them when running several processes")
    return {"logical": logical, "affinity": affinity, "container_quota": quota,
            "usable": usable, "limited_by": limited_by, "thread_variables": threads,
            "warnings": warnings}


def windows_memory() -> Dict[str, Optional[int]]:  # pragma: no cover - exercised only on Windows
    import ctypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return {"total": None, "available": None}
    return {"total": int(status.ullTotalPhys), "available": int(status.ullAvailPhys)}


def host_memory(root: Path) -> Dict[str, Optional[int]]:
    text = read_text(root / "proc" / "meminfo")
    if text:
        info = parse_meminfo(text)
        return {"total": info.get("MemTotal"), "available": info.get("MemAvailable")}
    if sys.platform == "win32":  # pragma: no cover
        try:
            return windows_memory()
        except Exception:
            return {"total": None, "available": None}
    try:
        total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        total = None
    return {"total": total, "available": None}


def memory_report(host: Mapping[str, Optional[int]], limits: Mapping[str, object],
                  slurm: Optional[Mapping[str, object]]) -> Dict[str, object]:
    candidates = []
    if host.get("available"):
        candidates.append((host["available"], "host available memory"))
    elif host.get("total"):
        candidates.append((host["total"], "host total memory (available unknown)"))
    limit = limits.get("memory_limit_bytes")
    used = limits.get("memory_used_bytes")
    if isinstance(limit, int):
        headroom = max(0, limit - used) if isinstance(used, int) else limit
        candidates.append((headroom, "container memory limit"))
    if slurm and slurm.get("memory_bytes"):
        candidates.append((int(slurm["memory_bytes"]), "Slurm allocation"))
    usable, limited_by = (min(candidates, key=lambda c: c[0]) if candidates else (None, "unknown"))
    return {"host_total_gib": gib(host.get("total")), "host_available_gib": gib(host.get("available")),
            "container_limit_gib": gib(limit if isinstance(limit, int) else None),
            "container_used_gib": gib(used if isinstance(used, int) else None),
            "usable_gib": gib(usable), "usable_bytes": usable, "limited_by": limited_by}


def disk_report(path: Path) -> Dict[str, object]:
    usage = shutil.disk_usage(path)
    return {"path": str(path), "total_gib": gib(usage.total), "free_gib": gib(usage.free),
            "free_bytes": usage.free, "writable": os.access(path, os.W_OK)}


def gpu_report(env: Mapping[str, str], search_path: Optional[str],
               system: str, machine: str, slurm: Optional[Mapping[str, object]]) -> Dict[str, object]:
    tools = {tool: shutil.which(tool, path=search_path) for tool in GPU_TOOLS}
    found = sorted(tool for tool, location in tools.items() if location)
    visibility = {var: env[var] for var in GPU_VISIBILITY_VARS if var in env}
    hidden = sorted(var for var, value in visibility.items() if value.strip().lower() in HIDDEN_GPU_VALUES)
    apple = system == "Darwin" and machine == "arm64"
    slurm_gpus = slurm.get("gpus") if slurm else None
    likely = bool(found or apple or (slurm_gpus and slurm_gpus > 0)) and not hidden
    notes = ["GPU tools were looked up on PATH but not executed; device count, memory and driver health "
             "are unverified. Confirm with the framework that will use the GPU."]
    if hidden:
        notes.append("GPUs are hidden from this process by " + ", ".join(hidden))
    if apple:
        notes.append("Apple silicon: an integrated GPU is present (Metal); CUDA is not available")
    return {"tools_on_path": found, "visibility_variables": visibility, "hidden_by": hidden,
            "apple_silicon": apple, "slurm_gpus": slurm_gpus, "gpu_likely": likely, "notes": notes}


# --- assembling and judging ---------------------------------------------------

def collect(root: Path = Path("/"), env: Optional[Mapping[str, str]] = None, path: Path = Path("."),
            logical: Optional[int] = None, affinity: Optional[int] = None,
            system: Optional[str] = None, machine: Optional[str] = None) -> Dict[str, object]:
    env = dict(os.environ) if env is None else dict(env)
    search_path = env.get("PATH", "")
    limits = container_limits(root)
    slurm = slurm_allocation(env)
    return {
        "tool": "resource_check", "version": VERSION, "read_only": True,
        "cpu": cpu_report(env, logical if logical is not None else logical_cpu_count(),
                          affinity if affinity is not None else affinity_cpu_count(), limits, slurm),
        "memory": memory_report(host_memory(root), limits, slurm),
        "disk": disk_report(path),
        "gpu": gpu_report(env, search_path, system or platform.system(), machine or platform.machine(), slurm),
        "container": limits,
        "slurm": slurm,
        "scheduler": scheduler_report(env, search_path),
    }


def evaluate(report: Mapping[str, object], need_cores: Optional[int], need_mem_gb: Optional[float],
             need_disk_gb: Optional[float], need_gpu: bool) -> List[Dict[str, object]]:
    checks: List[Dict[str, object]] = []
    cpu = report["cpu"]
    memory = report["memory"]
    disk = report["disk"]
    gpu = report["gpu"]
    if need_cores is not None:
        usable = cpu["usable"]
        checks.append({"need": f"cores >= {need_cores}", "have": usable,
                       "met": bool(usable is not None and usable >= need_cores)})
    if need_mem_gb is not None:
        usable_gib = memory["usable_gib"]
        checks.append({"need": f"memory >= {need_mem_gb:g} GiB", "have": usable_gib,
                       "met": bool(usable_gib is not None and usable_gib >= need_mem_gb)})
    if need_disk_gb is not None:
        free = disk["free_gib"]
        checks.append({"need": f"free disk >= {need_disk_gb:g} GiB at {disk['path']}", "have": free,
                       "met": bool(free is not None and free >= need_disk_gb and disk["writable"])})
    if need_gpu:
        checks.append({"need": "a GPU", "have": "likely" if gpu["gpu_likely"] else "no sign of one",
                       "met": bool(gpu["gpu_likely"])})
    return checks


def render_text(report: Mapping[str, object], checks: List[Mapping[str, object]]) -> str:
    cpu, memory, disk, gpu = report["cpu"], report["memory"], report["disk"], report["gpu"]
    scheduler, slurm = report["scheduler"], report["slurm"]
    lines = ["Resource check (read-only; no program was executed)"]
    lines.append(f"CPU     usable {cpu['usable']} (logical {cpu['logical']}, affinity {cpu['affinity']}; "
                 f"limited by {cpu['limited_by']})")
    if cpu["thread_variables"]:
        lines.append("        thread variables: " + ", ".join(f"{k}={v}" for k, v in cpu["thread_variables"].items()))
    lines.append(f"Memory  usable {memory['usable_gib']} GiB (host total {memory['host_total_gib']}, "
                 f"available {memory['host_available_gib']}; limited by {memory['limited_by']})")
    if memory["container_limit_gib"] is not None:
        lines.append(f"        container limit {memory['container_limit_gib']} GiB, "
                     f"used {memory['container_used_gib']} GiB")
    lines.append(f"Disk    {disk['path']}: {disk['free_gib']} GiB free of {disk['total_gib']} GiB "
                 f"(writable: {'yes' if disk['writable'] else 'no'})")
    tools = ", ".join(gpu["tools_on_path"]) or "none"
    lines.append(f"GPU     tools on PATH: {tools}; GPU likely: {'yes' if gpu['gpu_likely'] else 'no'}")
    if gpu["visibility_variables"]:
        lines.append("        " + ", ".join(f"{k}={v!r}" for k, v in gpu["visibility_variables"].items()))
    clients = ", ".join(scheduler["clients_on_path"]) or "none"
    where = "inside a job" if scheduler["inside_job"] else "not inside a job"
    lines.append(f"Sched   clients: {clients}; {where}")
    if slurm:
        lines.append(f"        Slurm job {slurm['job_id']}: cpus {slurm['cpus']}, "
                     f"memory {gib(slurm['memory_bytes'])} GiB, gpus {slurm['gpus']}")
    notes = list(cpu["warnings"]) + list(scheduler["warnings"]) + list(gpu["notes"])
    for note in notes:
        lines.append(f"NOTE    {note}")
    for check in checks:
        lines.append(f"NEED    {check['need']}: {'met' if check['met'] else 'NOT MET'} (have {check['have']})")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only report of usable CPU cores, memory, disk space and GPU signs. "
                    "Runs no other program and changes nothing.")
    parser.add_argument("--path", default=".", help="directory whose disk space to report (default: .)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    parser.add_argument("--need-cores", type=int, metavar="N", help="exit 1 unless at least N cores are usable")
    parser.add_argument("--need-mem-gb", type=float, metavar="GIB", help="exit 1 unless this much memory is usable")
    parser.add_argument("--need-disk-gb", type=float, metavar="GIB",
                        help="exit 1 unless this much disk is free and writable at --path")
    parser.add_argument("--need-gpu", action="store_true", help="exit 1 unless there is a sign of a usable GPU")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main(argv: Optional[List[str]] = None, root: Path = Path("/"),
         env: Optional[Mapping[str, str]] = None, **overrides: object) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    for name in ("need_cores", "need_mem_gb", "need_disk_gb"):
        value = getattr(args, name)
        if value is not None and value <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    path = Path(args.path)
    if not path.is_dir():
        parser.error(f"--path is not a directory: {path}")
    report = collect(root=root, env=env, path=path, **overrides)
    checks = evaluate(report, args.need_cores, args.need_mem_gb, args.need_disk_gb, args.need_gpu)
    report["checks"] = checks
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report, checks))
    return 0 if all(check["met"] for check in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
