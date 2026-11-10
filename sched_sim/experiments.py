"""Parallel experiment runner: many simulated trials spread over a process pool."""

from __future__ import annotations

import csv
import itertools
import multiprocessing as mp
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

from .model import Instance, lower_bound_instance, random_instance
from .monitor import ResourceMonitor
from .offline import offline_opt, opt_lower_bound
from .policies import make_policy
from .simulator import simulate


@dataclass(frozen=True)
class Scenario:
    kind: str = "random"  # "random" or "lower_bound"
    n: int = 8
    m: int = 2
    speed_model: str = "related"
    size_model: str = "bimodal"
    p_min: float = 1.0
    p_max: float = 16.0
    H: float = 4.0

    @property
    def delta(self) -> float:
        return self.p_max / self.p_min

    @property
    def label(self) -> str:
        if self.kind == "lower_bound":
            return f"LB n={self.n} m={self.m} L={self.p_max:g}"
        return f"{self.speed_model}/{self.size_model} n={self.n} m={self.m} D={self.delta:g} H={self.H:g}"

    def build(self, seed: int) -> Instance:
        if self.kind == "lower_bound":
            return lower_bound_instance(self.n, L=self.p_max, delta_t=self.p_min, m=self.m)
        return random_instance(
            self.n,
            self.m,
            p_min=self.p_min,
            p_max=self.p_max,
            H=self.H if self.speed_model != "identical" else 1.0,
            speed_model=self.speed_model,
            size_model=self.size_model,
            seed=seed,
        )


def default_grid(n: int = 8) -> list[Scenario]:
    grid = [
        Scenario("random", n, m, speed, size, 1.0, delta, 4.0)
        for m, speed, size, delta in itertools.product(
            (1, 2, 3), ("identical", "related", "unrelated"), ("bimodal", "loguniform"), (4.0, 16.0, 64.0)
        )
        if not (m == 1 and speed == "related")
    ]
    grid += [Scenario("lower_bound", n, 1, "identical", "bimodal", 1.0, L, 1.0) for L in (8.0, 64.0, 512.0)]
    return grid


def run_trial(task_id: int, scenario: Scenario, seed: int, policies: list[str], max_opt_n: int) -> dict:
    """One unit of parallel work. Returns result rows plus timing of the task itself."""
    wall0, cpu0 = time.time(), time.process_time()
    inst = scenario.build(seed)
    t = time.perf_counter()
    if inst.n <= max_opt_n:
        opt, opt_kind = offline_opt(inst).total_completion, "exact"
    else:
        opt, opt_kind = opt_lower_bound(inst), "lower_bound"
    opt_seconds = time.perf_counter() - t

    rows = []
    for spec in policies:
        policy = make_policy(spec)
        t = time.perf_counter()
        sched = simulate(inst, policy, seed=seed)
        rows.append(
            {
                "task_id": task_id,
                "scenario": scenario.label,
                **asdict(scenario),
                "delta": scenario.delta,
                "seed": seed,
                "policy": policy.name,
                "total_completion": sched.total_completion,
                "opt": opt,
                "opt_kind": opt_kind,
                "ratio": sched.total_completion / opt,
                "sim_seconds": time.perf_counter() - t,
            }
        )
    return {
        "rows": rows,
        "task": {
            "task_id": task_id,
            "scenario": scenario.label,
            "seed": seed,
            "pid": os.getpid(),
            "start": wall0,
            "end": time.time(),
            "wall_seconds": time.time() - wall0,
            "cpu_seconds": time.process_time() - cpu0,
            "opt_seconds": opt_seconds,
        },
    }


@dataclass
class ExperimentResult:
    rows: list[dict]
    tasks: list[dict]
    monitor: ResourceMonitor
    wall_seconds: float


def run_experiment(
    scenarios: list[Scenario],
    policies: list[str],
    *,
    trials: int = 10,
    workers: int | None = None,
    max_opt_n: int = 10,
    monitor_interval: float = 0.1,
    progress: bool = True,
) -> ExperimentResult:
    workers = workers or os.cpu_count() or 1
    jobs = [(s, seed) for s in scenarios for seed in range(trials)]
    rows, tasks = [], []
    monitor = ResourceMonitor(interval=monitor_interval, track_children=True)
    t0 = time.time()
    # forkserver: the monitor thread is already running, and forking a threaded process is unsafe.
    method = "forkserver" if "forkserver" in mp.get_all_start_methods() else "spawn"
    with monitor, ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context(method)) as pool:
        futures = [pool.submit(run_trial, i, s, seed, policies, max_opt_n) for i, (s, seed) in enumerate(jobs)]
        for k, fut in enumerate(as_completed(futures), 1):
            out = fut.result()
            rows.extend(out["rows"])
            out["task"]["start"] -= monitor.t0
            out["task"]["end"] -= monitor.t0
            tasks.append(out["task"])
            if progress and (k % max(1, len(futures) // 10) == 0 or k == len(futures)):
                print(f"  {k}/{len(futures)} trials done ({time.time() - t0:.1f}s)", flush=True)
    return ExperimentResult(rows, tasks, monitor, time.time() - t0)


def write_csv(rows: list[dict], path: str | Path) -> None:
    if not rows:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def summarize(rows: list[dict]) -> list[dict]:
    """Mean / max ratio per (scenario, policy)."""
    groups: dict[tuple[str, str], list[float]] = {}
    for r in rows:
        groups.setdefault((r["scenario"], r["policy"]), []).append(r["ratio"])
    return [
        {"scenario": s, "policy": p, "trials": len(v), "mean_ratio": sum(v) / len(v), "max_ratio": max(v)}
        for (s, p), v in groups.items()
    ]
