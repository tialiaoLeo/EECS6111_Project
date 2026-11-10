"""Command line entry point: python -m sched_sim {simulate,execute,experiment} ..."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .model import SIZE_MODELS, SPEED_MODELS, Instance, lower_bound_instance, random_instance
from .policies import DEFAULT_POLICIES, make_policy


def _outdir(base: str, tag: str) -> Path:
    path = Path(base) / f"{time.strftime('%Y%m%d-%H%M%S')}-{tag}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _instance_from_args(a) -> Instance:
    if a.instance:
        return Instance.from_json(a.instance)
    if a.lower_bound:
        return lower_bound_instance(a.n, L=a.p_max, delta_t=a.p_min, m=a.m)
    return random_instance(
        a.n, a.m, p_min=a.p_min, p_max=a.p_max, H=a.H,
        speed_model=a.speed_model, size_model=a.size_model, seed=a.seed,
    )


def _add_instance_args(p: argparse.ArgumentParser, n: int, m: int) -> None:
    g = p.add_argument_group("instance")
    g.add_argument("--instance", help="load an instance JSON instead of generating one")
    g.add_argument("--lower-bound", action="store_true", help="use the proposal's long-job-then-short-jobs instance")
    g.add_argument("-n", type=int, default=n, help="number of jobs")
    g.add_argument("-m", type=int, default=m, help="number of worker threads")
    g.add_argument("--p-min", type=float, default=1.0)
    g.add_argument("--p-max", type=float, default=16.0)
    g.add_argument("--H", type=float, default=4.0, help="speed ratio bound")
    g.add_argument("--speed-model", choices=SPEED_MODELS, default="related")
    g.add_argument("--size-model", choices=SIZE_MODELS, default="bimodal")
    g.add_argument("--seed", type=int, default=0)


def _print_instance(inst: Instance) -> None:
    print(f"instance {inst.name}: n={inst.n} m={inst.m} Delta={inst.delta:g} H={inst.H:.2f}")
    for j in inst.jobs:
        speeds = ", ".join(f"{s:.2f}" for s in j.speeds)
        print(f"  job {j.id:3d}  r={j.release:8.3f}  p={j.size:7.3f}  s=[{speeds}]")


def cmd_simulate(a) -> None:
    from .offline import offline_opt, opt_lower_bound
    from .plots import plot_schedules
    from .simulator import simulate

    inst = _instance_from_args(a)
    out = _outdir(a.out, "simulate")
    inst.to_json(out / "instance.json")
    _print_instance(inst)

    schedules = []
    if inst.n <= a.max_opt_n:
        t = time.perf_counter()
        opt = offline_opt(inst)
        opt.validate()
        print(f"\nOPT (exact) computed in {time.perf_counter() - t:.2f}s")
        schedules.append(opt)
        ref, ref_kind = opt.total_completion, "OPT"
    else:
        ref, ref_kind = opt_lower_bound(inst), "OPT lower bound"
    for spec in a.policies:
        s = simulate(inst, make_policy(spec), seed=a.seed, speedup=a.speedup)
        s.validate()
        schedules.append(s)

    print(f"\n{'policy':28s} {'sum C_j':>10s} {'ratio vs ' + ref_kind:>22s}")
    for s in schedules:
        print(f"{s.policy:28s} {s.total_completion:10.3f} {s.total_completion / ref:22.3f}")
    plot_schedules(schedules, out / "schedules.png")
    print(f"\nwrote {out}/schedules.png and instance.json")


def cmd_execute(a) -> None:
    from .executor import execute
    from .experiments import write_csv
    from .plots import plot_execution, plot_policy_comparison

    inst = _instance_from_args(a)
    out = _outdir(a.out, "execute")
    inst.to_json(out / "instance.json")
    _print_instance(inst)

    results = []
    for spec in a.policies:
        policy = make_policy(spec)
        print(f"\nrunning {policy.name} on {inst.m} worker processes ...", flush=True)
        res = execute(inst, policy, time_scale=a.time_scale, workload=a.workload,
                      monitor_interval=a.interval, pin=a.pin, seed=a.seed)
        results.append(res)
        safe = "".join(c if c.isalnum() else "_" for c in policy.name)
        plot_execution(res, out / f"execution_{safe}.png")
        res.monitor.to_csv(out / f"resources_{safe}.csv")
        write_csv([{**r.__dict__, "wait": r.wait} for r in sorted(res.records.values(), key=lambda r: r.job)],
                  out / f"jobs_{safe}.csv")
        print(f"  measured sum C_j = {res.total_completion:.3f}  wall = {res.wall_seconds:.2f}s")
        for r in sorted(res.records.values(), key=lambda r: r.job):
            print(f"  job {r.job:3d} T{r.thread}  wait={r.wait:7.3f}  runtime planned={r.planned_runtime:7.3f} "
                  f"measured={r.measured_runtime:7.3f}  cpu={r.cpu_seconds:6.3f}s")
    if len(results) > 1:
        plot_policy_comparison(results, out / "policy_comparison.png")
    print(f"\nwrote plots and CSVs to {out}")


def cmd_experiment(a) -> None:
    from .experiments import Scenario, default_grid, run_experiment, summarize, write_csv
    from .plots import plot_experiment_ratios, plot_experiment_tasks

    if a.quick:
        scenarios = [Scenario("random", a.n, m, sm, "bimodal", 1.0, d, 4.0)
                     for m in (1, 2) for sm in ("identical", "unrelated") for d in (4.0, 32.0)]
        scenarios += [Scenario("lower_bound", a.n, 1, "identical", "bimodal", 1.0, L, 1.0) for L in (8.0, 128.0)]
    else:
        scenarios = default_grid(a.n)
    out = _outdir(a.out, "experiment")
    print(f"{len(scenarios)} scenarios x {a.trials} trials, policies: {', '.join(a.policies)}")
    res = run_experiment(scenarios, a.policies, trials=a.trials, workers=a.workers,
                         max_opt_n=a.max_opt_n, monitor_interval=a.interval)
    write_csv(res.rows, out / "results.csv")
    write_csv(res.tasks, out / "tasks.csv")
    summary = summarize(res.rows)
    write_csv(summary, out / "summary.csv")
    res.monitor.to_csv(out / "resources.csv")
    plot_experiment_ratios(res.rows, out / "ratios.png")
    plot_experiment_tasks(res.tasks, res.monitor, out / "tasks_and_resources.png")

    by_policy: dict[str, list[float]] = {}
    for r in res.rows:
        by_policy.setdefault(r["policy"], []).append(r["ratio"])
    print(f"\nfinished in {res.wall_seconds:.1f}s. ALG/OPT over all trials:")
    print(f"{'policy':28s} {'mean':>8s} {'max':>8s}")
    for p, v in by_policy.items():
        print(f"{p:28s} {sum(v) / len(v):8.3f} {max(v):8.3f}")
    walls = [t["wall_seconds"] for t in res.tasks]
    print(f"\nper-trial wall time: mean {sum(walls) / len(walls):.3f}s, max {max(walls):.3f}s")
    (out / "config.json").write_text(json.dumps(vars(a), indent=2, default=str))
    print(f"wrote results to {out}")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="python -m sched_sim", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("simulate", help="exact discrete-event simulation of one instance, all policies vs OPT")
    _add_instance_args(s, n=8, m=2)
    s.add_argument("--policies", nargs="+", default=DEFAULT_POLICIES)
    s.add_argument("--max-opt-n", type=int, default=11)
    s.add_argument("--speedup", type=float, default=1.0, help="(1+eps) speed augmentation for online policies")
    s.add_argument("--out", default="results")
    s.set_defaults(func=cmd_simulate)

    e = sub.add_parser("execute", help="run policies on real worker processes with CPU/memory monitoring")
    _add_instance_args(e, n=12, m=3)
    e.add_argument("--policies", nargs="+", default=["FCFS", "OldestFastest", "Delayed:sqrt"])
    e.add_argument("--time-scale", type=float, default=0.05, help="wall seconds per model time unit")
    e.add_argument("--workload", choices=("duty", "compute"), default="duty")
    e.add_argument("--interval", type=float, default=0.05, help="monitor sampling interval (s)")
    e.add_argument("--pin", action="store_true", help="pin worker i to CPU core i")
    e.add_argument("--out", default="results")
    e.set_defaults(func=cmd_execute)

    x = sub.add_parser("experiment", help="parallel sweep of random/adversarial instances vs OPT")
    x.add_argument("-n", type=int, default=8)
    x.add_argument("--trials", type=int, default=20)
    x.add_argument("--workers", type=int, default=None, help="pool size (default: CPU count)")
    x.add_argument("--policies", nargs="+", default=DEFAULT_POLICIES)
    x.add_argument("--max-opt-n", type=int, default=10)
    x.add_argument("--interval", type=float, default=0.1)
    x.add_argument("--quick", action="store_true", help="small scenario grid")
    x.add_argument("--out", default="results")
    x.set_defaults(func=cmd_experiment)

    a = p.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
