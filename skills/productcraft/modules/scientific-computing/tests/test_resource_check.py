"""Offline tests for resource_check.py using fake /proc and /sys trees in temporary directories."""
import contextlib
import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "resource_check.py"
spec = importlib.util.spec_from_file_location("resource_check", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

GIB = 1024 ** 3
MEMINFO = "MemTotal:       16777216 kB\nMemFree:         1000000 kB\nMemAvailable:    8388608 kB\n"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def fake_root(tmp: Path, cgroup: str = "none", meminfo: str = MEMINFO) -> Path:
    root = tmp / "root"
    write(root / "proc" / "meminfo", meminfo)
    base = root / "sys" / "fs" / "cgroup"
    if cgroup == "v2":
        write(root / "proc" / "self" / "cgroup", "0::/job/step\n")
        write(base / "cgroup.controllers", "cpu memory\n")
        write(base / "cpu.max", "max 100000\n")
        write(base / "job" / "cpu.max", "250000 100000\n")      # 2.5 CPUs on the parent
        write(base / "job" / "step" / "cpu.max", "max 100000\n")
        write(base / "job" / "memory.max", str(6 * GIB) + "\n")
        write(base / "job" / "step" / "memory.max", "max\n")
        write(base / "job" / "step" / "memory.current", str(1 * GIB) + "\n")
    elif cgroup == "v1":
        write(root / "proc" / "self" / "cgroup", "4:memory:/\n3:cpu,cpuacct:/\n")
        write(base / "cpu,cpuacct" / "cpu.cfs_quota_us", "-1\n")
        write(base / "cpu,cpuacct" / "cpu.cfs_period_us", "100000\n")
        write(base / "memory" / "memory.limit_in_bytes", "9223372036854771712\n")
        write(base / "memory" / "memory.usage_in_bytes", str(GIB) + "\n")
    else:
        write(root / "proc" / "self" / "cgroup", "")
    return root


def make_tool(directory: Path, name: str, marker: Path) -> None:
    """A fake executable that would leave a marker file if anything ran it."""
    tool = directory / name
    tool.write_text(f"#!/bin/sh\necho ran > '{marker}'\n")
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def run(argv, **kwargs):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = module.main(argv, **kwargs)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class ParserTests(unittest.TestCase):
    def test_meminfo_in_bytes(self):
        info = module.parse_meminfo(MEMINFO)
        self.assertEqual(info["MemTotal"], 16 * GIB)
        self.assertEqual(info["MemAvailable"], 8 * GIB)

    def test_cpu_max(self):
        self.assertIsNone(module.parse_cpu_max("max 100000"))
        self.assertEqual(module.parse_cpu_max("200000 100000"), 2.0)
        self.assertIsNone(module.parse_cpu_max(""))

    def test_cfs_quota(self):
        self.assertIsNone(module.parse_cfs_quota("-1", "100000"))
        self.assertEqual(module.parse_cfs_quota("150000", "100000"), 1.5)

    def test_memory_limit_sentinels(self):
        self.assertIsNone(module.parse_memory_limit("max"))
        self.assertIsNone(module.parse_memory_limit("9223372036854771712"))
        self.assertEqual(module.parse_memory_limit(str(GIB)), GIB)


class ContainerTests(unittest.TestCase):
    def test_v2_takes_tightest_limit_up_the_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            limits = module.container_limits(fake_root(Path(tmp), "v2"))
        self.assertEqual(limits["version"], "v2")
        self.assertEqual(limits["cpu_quota"], 2.5)
        self.assertEqual(limits["memory_limit_bytes"], 6 * GIB)
        self.assertEqual(limits["memory_used_bytes"], GIB)

    def test_v1_unlimited(self):
        with tempfile.TemporaryDirectory() as tmp:
            limits = module.container_limits(fake_root(Path(tmp), "v1"))
        self.assertEqual(limits["version"], "v1")
        self.assertIsNone(limits["cpu_quota"])
        self.assertIsNone(limits["memory_limit_bytes"])

    def test_no_cgroups(self):
        with tempfile.TemporaryDirectory() as tmp:
            limits = module.container_limits(fake_root(Path(tmp), "none"))
        self.assertIsNone(limits["version"])


class ReportTests(unittest.TestCase):
    def collect(self, tmp, cgroup="none", env=None, logical=16, affinity=16, system="Linux", machine="x86_64"):
        root = fake_root(Path(tmp), cgroup)
        env = {"PATH": str(Path(tmp) / "empty-bin")} if env is None else env
        return module.collect(root=root, env=env, path=Path(tmp), logical=logical, affinity=affinity,
                              system=system, machine=machine)

    def test_container_quota_limits_cores_and_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self.collect(tmp, "v2")
        self.assertEqual(report["cpu"]["usable"], 2)
        self.assertIn("quota", report["cpu"]["limited_by"])
        self.assertEqual(report["memory"]["usable_gib"], 5.0)  # 6 GiB limit minus 1 GiB used
        self.assertEqual(report["memory"]["limited_by"], "container memory limit")

    def test_affinity_limits_cores(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self.collect(tmp, logical=64, affinity=8)
        self.assertEqual(report["cpu"]["usable"], 8)
        self.assertEqual(report["cpu"]["limited_by"], "CPU affinity")

    def test_slurm_allocation_limits_cores_memory_and_reports_gpus(self):
        env = {"PATH": "", "SLURM_JOB_ID": "123", "SLURM_CPUS_PER_TASK": "4", "SLURM_CPUS_ON_NODE": "4",
               "SLURM_MEM_PER_CPU": "1024", "SLURM_GPUS_ON_NODE": "2", "SLURM_JOB_PARTITION": "gpu"}
        with tempfile.TemporaryDirectory() as tmp:
            report = self.collect(tmp, env=env)
        self.assertEqual(report["cpu"]["usable"], 4)
        self.assertEqual(report["memory"]["usable_gib"], 4.0)
        self.assertEqual(report["slurm"]["gpus"], 2)
        self.assertTrue(report["gpu"]["gpu_likely"])
        self.assertTrue(report["scheduler"]["inside_job"])

    def test_thread_oversubscription_warned(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self.collect(tmp, env={"PATH": "", "OMP_NUM_THREADS": "32"}, logical=8, affinity=8)
        self.assertTrue(any("OMP_NUM_THREADS=32" in w for w in report["cpu"]["warnings"]))

    def test_gpu_tool_found_but_never_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            marker = Path(tmp) / "executed.txt"
            make_tool(bin_dir, "nvidia-smi", marker)
            report = self.collect(tmp, env={"PATH": str(bin_dir)})
            self.assertEqual(report["gpu"]["tools_on_path"], ["nvidia-smi"])
            self.assertTrue(report["gpu"]["gpu_likely"])
            self.assertFalse(marker.exists(), "the GPU tool must never be executed")

    def test_hidden_gpus(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            make_tool(bin_dir, "nvidia-smi", Path(tmp) / "executed.txt")
            report = self.collect(tmp, env={"PATH": str(bin_dir), "CUDA_VISIBLE_DEVICES": ""})
        self.assertFalse(report["gpu"]["gpu_likely"])
        self.assertEqual(report["gpu"]["hidden_by"], ["CUDA_VISIBLE_DEVICES"])

    def test_apple_silicon_noted(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self.collect(tmp, system="Darwin", machine="arm64")
        self.assertTrue(report["gpu"]["apple_silicon"])

    def test_login_node_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            make_tool(bin_dir, "sbatch", Path(tmp) / "executed.txt")
            report = self.collect(tmp, env={"PATH": str(bin_dir)})
        self.assertEqual(report["scheduler"]["clients_on_path"], ["Slurm"])
        self.assertTrue(any("login" in w for w in report["scheduler"]["warnings"]))


class CliTests(unittest.TestCase):
    def kwargs(self, tmp, cgroup="v2"):
        return {"root": fake_root(Path(tmp), cgroup), "env": {"PATH": ""}, "logical": 16, "affinity": 16,
                "system": "Linux", "machine": "x86_64"}

    def test_needs_met_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = run(["--path", tmp, "--need-cores", "2", "--need-mem-gb", "4", "--json"],
                               **self.kwargs(tmp))
        self.assertEqual(code, 0)
        report = json.loads(out)
        self.assertTrue(all(check["met"] for check in report["checks"]))
        self.assertTrue(report["read_only"])

    def test_need_not_met_exit_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = run(["--path", tmp, "--need-cores", "8", "--need-gpu"], **self.kwargs(tmp))
        self.assertEqual(code, 1)
        self.assertIn("NOT MET", out)

    def test_disk_need_uses_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = run(["--path", tmp, "--need-disk-gb", "1e9", "--json"], **self.kwargs(tmp))
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(out)["checks"][0]["met"])

    def test_usage_errors_exit_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            for argv in (["--need-cores", "0"], ["--need-mem-gb", "-1"], ["--path", os.path.join(tmp, "missing")],
                         ["--unknown-flag"]):
                with self.subTest(argv=argv):
                    code, _, _ = run(argv, **self.kwargs(tmp))
                    self.assertEqual(code, 2)

    def test_help_exits_zero(self):
        code, out, _ = run(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("Read-only", out)

    def test_output_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            kwargs = self.kwargs(tmp)
            first = run(["--path", tmp, "--json"], **kwargs)[1]
            second = run(["--path", tmp, "--json"], **kwargs)[1]
        first_report, second_report = json.loads(first), json.loads(second)
        for report in (first_report, second_report):  # free space can change between calls
            report["disk"].pop("free_bytes")
            report["disk"].pop("free_gib")
        self.assertEqual(first_report, second_report)

    def test_real_host_smoke(self):
        code, out, _ = run(["--json"])
        self.assertIn(code, (0, 1))
        self.assertIn("cpu", json.loads(out))


if __name__ == "__main__":
    unittest.main()
