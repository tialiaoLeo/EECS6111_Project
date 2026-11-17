"""Command line entry point: python -m sched_sim {simulate,execute,experiment} ..."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .model import (
    SIZE_DISTS, SIZE_MODELS, SPEED_MODELS, Instance, limit_instance, limits_between, lower_bound_instance,
    random_instance,
)
from .policies import DEFAULT_POLICIES, LIMIT_POLICIES, make_policy


def _outdir(base: str, tag: str) -> Path:
    path = Path(base) / f"{time.strftime('%Y%m%d-%H%M%S')}-{tag}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _instance_from_args(a) -> Instance:
    if a.instance:
        return Instance.from_json(a.instance)
    if a.trace:
        from .traces import trace_instance

        inst, stats = trace_instance(
            a.trace, a.m, max_procs=a.trace_max_procs, min_runtime=a.trace_min_runtime,
            lam=a.lam if a.trace_lam_filter else None, start=a.trace_start, max_jobs=a.n,
            time_unit=a.trace_time_unit,
        )
        print("trace: " + stats.summary())
        return inst
    if a.lower_bound:
        return lower_bound_instance(a.n, L=a.p_max, delta_t=a.p_min, m=a.m, with_limits=a.model == "limits")
    if a.model == "limits":
        return limit_instance(
            a.n, a.m, lam=a.lam, limits=limits_between(a.u_min, a.u_max), size_dist=a.size_dist, load=a.load, seed=a.seed,
        )
    return random_instance(
        a.n, a.m, p_min=a.p_min, p_max=a.p_max, H=a.H,
        speed_model=a.speed_model, size_model=a.size_model, seed=a.seed,
    )


def _policies_for(a, inst: Instance) -> list[str]:
    if a.policies:
        return a.policies
    return LIMIT_POLICIES if inst.has_limits else DEFAULT_POLICIES


def _add_instance_args(p: argparse.ArgumentParser, n: int, m: int) -> None:
    g = p.add_argument_group("instance")
    g.add_argument("--instance", help="load an instance JSON instead of generating one")
    g.add_argument("--trace", help="load an SWF trace (Parallel Workloads Archive); -n = number of jobs kept")
    g.add_argument("--lower-bound", action="store_true", help="use the proposal's long-job-then-short-jobs instance")
    g.add_argument("--model", choices=("limits", "speeds"), default="limits",
                   help="limits: declared time limits on identical workers (v3); speeds: heterogeneous speeds")
    g.add_argument("-n", type=int, default=n, help="number of jobs")
    g.add_argument("-m", type=int, default=m, help="number of machines (workers)")
    g.add_argument("--seed", type=int, default=0)
    lim = p.add_argument_group("declared-limit model (--model limits)")
    lim.add_argument("--lam", type=float, default=4.0, help="limits overestimate sizes by at most this factor")
    lim.add_argument("--size-dist", choices=SIZE_DISTS, default="uniform", help="sizes within [u/lam, u]")
    lim.add_argument("--load", type=float, default=0.8, help="arrival rate / capacity of the m workers")
    lim.add_argument("--u-min", type=float, default=1.0, help="smallest declared limit (limits are powers of 2)")
    lim.add_argument("--u-max", type=float, default=32.0, help="largest declared limit")
    tr = p.add_argument_group("trace (--trace)")
    tr.add_argument("--trace-start", type=int, default=0, help="skip this many kept jobs")
    tr.add_argument("--trace-max-procs", type=int, default=1, help="keep jobs using at most this many processors")
    tr.add_argument("--trace-min-runtime", type=float, default=60.0,
                    help="drop jobs shorter than this (s): jobs that fail at start-up")
    tr.add_argument("--trace-lam-filter", action="store_true",
                    help="drop jobs with u/p > --lam (default: set lam to the largest u/p kept)")
    tr.add_argument("--trace-time-unit", type=float, default=3600.0, help="seconds per model time unit")
    sp = p.add_argument_group("speed model (--model speeds)")
    sp.add_argument("--p-min", type=float, default=1.0, help="also the short job size of --lower-bound")
    sp.add_argument("--p-max", type=float, default=16.0, help="also the long job size of --lower-bound")
    sp.add_argument("--H", type=float, default=4.0, help="speed ratio bound")
    sp.add_argument("--speed-model", choices=SPEED_MODELS, default="related")
    sp.add_argument("--size-model", choices=SIZE_MODELS, default="bimodal")


def _print_instance(inst: Instance, limit: int = 40) -> None:
    if inst.has_limits:
        print(f"instance {inst.name}: n={inst.n} m={inst.m} lam={inst.lam:g} "
              f"limits in [{min(j.limit for j in inst.jobs):g}, {max(j.limit for j in inst.jobs):g}]")
    else:
        print(f"instance {inst.name}: n={inst.n} m={inst.m} Delta={inst.delta:g} H={inst.H:.2f}")
    for j in inst.jobs[:limit]:
        if inst.has_limits:
            print(f"  job {j.id:3d}  r={j.release:8.3f}  u={j.limit:7.3f}  p={j.size:7.3f}")
        else:
            speeds = ", ".join(f"{s:.2f}" for s in j.speeds)
            print(f"  job {j.id:3d}  r={j.release:8.3f}  p={j.size:7.3f}  s=[{speeds}]")
    if inst.n > limit:
        print(f"  ... ({inst.n - limit} more)")


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
    for spec in _policies_for(a, inst):
        s = simulate(inst, make_policy(spec), seed=a.seed, speedup=a.speedup)
        s.validate()
        schedules.append(s)

    rel = sum(j.release for j in inst.jobs)
    print(f"\nratios are against {ref_kind}")
    print(f"{'policy':28s} {'sum C_j':>12s} {'ratio':>8s} {'flow time':>12s} {'ratio':>8s}")
    for s in schedules:
        print(f"{s.policy:28s} {s.total_completion:12.3f} {s.total_completion / ref:8.3f} "
              f"{s.total_completion - rel:12.3f} {(s.total_completion - rel) / (ref - rel):8.3f}")
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
    for spec in _policies_for(a, inst):
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
    from .experiments import Scenario, default_grid, limits_grid, run_experiment, summarize, write_csv
    from .plots import plot_experiment_ratios, plot_experiment_tasks

    if a.grid == "limits":
        scenarios = limits_grid(a.n, quick=a.quick, ms=tuple(a.ms) if a.ms else None,
                                lams=tuple(a.lams) if a.lams else None,
                                dists=tuple(a.size_dists) if a.size_dists else None, load=a.load)
    elif a.ms or a.lams or a.size_dists:
        raise SystemExit("--ms, --lams and --size-dists apply to --grid limits only")
    elif a.quick:
        scenarios = [Scenario("random", a.n, m, sm, "bimodal", 1.0, d, 4.0)
                     for m in (1, 2) for sm in ("identical", "unrelated") for d in (4.0, 32.0)]
        scenarios += [Scenario("lower_bound", a.n, 1, "identical", "bimodal", 1.0, L, 1.0) for L in (8.0, 128.0)]
    else:
        scenarios = default_grid(a.n)
    a.policies = a.policies or (LIMIT_POLICIES if a.grid == "limits" else DEFAULT_POLICIES)
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
    plot_experiment_ratios(res.rows, out / "flow_ratios.png", key="flow_ratio")
    plot_experiment_tasks(res.tasks, res.monitor, out / "tasks_and_resources.png")

    kinds = sorted({r["opt_kind"] for r in res.rows})
    ref = "exact OPT" if kinds == ["exact"] else "OPT lower bound" if kinds == ["lower_bound"] else "OPT (exact or lower bound)"
    by_policy: dict[str, list[dict]] = {}
    for r in res.rows:
        by_policy.setdefault(r["policy"], []).append(r)
    print(f"\nfinished in {res.wall_seconds:.1f}s. Ratios against {ref} over all trials:")
    print(f"{'':28s} {'sum C_j':>17s} {'flow time':>17s}")
    print(f"{'policy':28s} {'mean':>8s} {'max':>8s} {'mean':>8s} {'max':>8s}")
    for p, g in by_policy.items():
        v, f = [r["ratio"] for r in g], [r["flow_ratio"] for r in g]
        print(f"{p:28s} {sum(v) / len(v):8.3f} {max(v):8.3f} {sum(f) / len(f):8.3f} {max(f):8.3f}")
    walls = [t["wall_seconds"] for t in res.tasks]
    print(f"\nper-trial wall time: mean {sum(walls) / len(walls):.3f}s, max {max(walls):.3f}s")
    (out / "config.json").write_text(json.dumps(vars(a), indent=2, default=str))
    print(f"wrote results to {out}")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="python -m sched_sim", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("simulate", help="exact discrete-event simulation of one instance, all policies vs OPT")
    _add_instance_args(s, n=8, m=2)
    s.add_argument("--policies", nargs="+", default=None, help="default: the baselines of the instance's model")
    s.add_argument("--max-opt-n", type=int, default=11)
    s.add_argument("--speedup", type=float, default=1.0, help="(1+eps) speed augmentation for online policies")
    s.add_argument("--out", default="results")
    s.set_defaults(func=cmd_simulate)

    e = sub.add_parser("execute", help="run policies on real worker processes with CPU/memory monitoring")
    _add_instance_args(e, n=12, m=3)
    e.add_argument("--policies", nargs="+", default=None, help="default: the baselines of the instance's model")
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
    x.add_argument("--grid", choices=("limits", "speeds"), default="limits",
                   help="limits: declared-limit model (v3); speeds: heterogeneous-speed grid")
    x.add_argument("--ms", type=int, nargs="+", default=None, help="worker counts to sweep (limits grid; default 1 2 3)")
    x.add_argument("--lams", type=float, nargs="+", default=None, help="lam values to sweep (limits grid)")
    x.add_argument("--size-dists", nargs="+", choices=SIZE_DISTS, default=None, help="size distributions to sweep")
    x.add_argument("--load", type=float, default=0.8, help="arrival rate / capacity of the m workers (limits grid)")
    x.add_argument("--policies", nargs="+", default=None, help="default: the baselines of the grid's model")
    x.add_argument("--max-opt-n", type=int, default=10)
    x.add_argument("--interval", type=float, default=0.1)
    x.add_argument("--quick", action="store_true", help="small scenario grid")
    x.add_argument("--out", default="results")
    x.set_defaults(func=cmd_experiment)

    a = p.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
