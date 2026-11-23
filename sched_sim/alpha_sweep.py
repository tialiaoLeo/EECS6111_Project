"""Worst-case experiment for the waiting threshold alpha of DelayedSLF (one machine).

DelayedSLF(alpha) starts the waiting job with the smallest limit u_j, but only once t >= alpha * u_j.
The conjecture is that alpha = 1 / sqrt(lam) is the right choice and gives ratio O(sqrt(lam)).

Random instances are too mild to show worst cases, so each policy is run against adversarial
families that are built *against that policy* (the adversary may look at what a deterministic
policy does). Every ratio is against the exact offline optimum: a closed form for the two large
families (see `batch` and `trap`), the exponential search of offline.py for the small ones.

Families (m = 1):
  single      one job with p = u / lam. Waiting for it is pure loss.
  batch       k long and s = k * sqrt(lam) short jobs, all at time 0 with the same limit. The jobs
              the policy starts first are the long ones (the sqrt(lam) lower bound). Large.
  trap        one long job; many short jobs arrive just after the policy starts it. Large.
  trap+batch  a long job, then a same-limit batch just after the policy starts it. At most 18
              jobs, so its ratios are below what a larger instance would give.
  random      the largest ratio over random instances with extreme sizes.

Run:  python -m sched_sim.alpha_sweep [--lams 1 4 16 64 256] [--out results]
"""

from __future__ import annotations

import argparse
import csv
import math
import time
from pathlib import Path

from .model import Instance, Job, limit_instance
from .offline import offline_opt
from .policies import FCFS, SLF, DelayedSLF, Policy
from .simulator import simulate

EPS_ARRIVAL = 1e-3  # "just after"
MAX_N = 18          # exact OPT on one machine is fast up to here


def _instance(rows: list[tuple[float, float, float]], lam: float, name: str, opt: float | None = None) -> Instance:
    """rows: (release, size, limit). `opt`: the exact optimum when a closed form is known."""
    jobs = [Job(k, r, p, (1.0,), u) for k, (r, p, u) in enumerate(rows)]
    us = [u for *_, u in rows]
    inst = Instance(jobs, 1, min(us) / lam, max(us), name=name, lam=lam,
                    meta={} if opt is None else {"opt": opt})
    inst.check_limits()
    return inst


def _start_order(inst: Instance, policy: Policy) -> list[int]:
    s = simulate(inst, policy)
    return sorted(s.assignments, key=lambda j: s.assignments[j].start)


def single(policy: Policy, lam: float) -> Instance:
    return _instance([(0.0, 1.0, lam)], lam, "single")


def _spt(sizes: list[float]) -> float:
    """Optimum when all jobs are available at time 0: shortest processing time first."""
    total = now = 0.0
    for p in sorted(sizes):
        now += p
        total += now
    return total


def batch(policy: Policy, lam: float, k: int = 10) -> Instance:
    """k long and round(k sqrt(lam)) short jobs at time 0 with one limit; the first k started are long."""
    n = k + max(1, round(k * math.sqrt(lam)))
    order = _start_order(_instance([(0.0, 1.0, lam)] * n, lam, "batch"), policy)
    long_ids = set(order[:k])
    sizes = [lam if i in long_ids else 1.0 for i in range(n)]
    return _instance([(0.0, p, lam) for p in sizes], lam, "batch", opt=_spt(sizes))


def _long_start(policy: Policy, lam: float, big: float) -> float:
    alone = _instance([(0.0, big, big)], lam, "probe")
    return simulate(alone, policy).assignments[0].start


def trap(policy: Policy, lam: float, k: int = 2000) -> Instance:
    """A long job (u = p = big); k unit jobs arrive just after the policy starts it.

    Exact optimum: the long job starts at 0, or after exactly i of the unit jobs (no idling once
    they are all released, and they are identical)."""
    big = 1000.0 * k * lam
    t = _long_start(policy, lam, big) + EPS_ARRIVAL
    tri = lambda a: a * (a + 1) / 2.0
    opt = big + k * max(big, t) + tri(k)                      # long job first, at time 0
    for i in range(k + 1):                                    # i unit jobs, long job, the rest
        opt = min(opt, i * t + tri(i) + (t + i + big) + (k - i) * (t + big) + tri(k) - tri(i))
    return _instance([(0.0, big, big)] + [(t, 1.0, 1.0)] * k, lam, "trap", opt=opt)


def trap_batch(policy: Policy, lam: float) -> Instance:
    """A long job, then a same-limit batch just after the policy starts it (at most MAX_N jobs)."""
    root = math.sqrt(lam)
    k = max(1, int((MAX_N - 1) // (1 + root)))
    n = k + max(1, round(k * root))
    big = 20.0 * (k * lam + n)
    t = _long_start(policy, lam, big) + EPS_ARRIVAL
    head = [(0.0, big, big)]
    order = _start_order(_instance(head + [(t, 1.0, lam)] * n, lam, "trap+batch"), policy)
    long_ids = set([j for j in order if j > 0][:k])
    return _instance(head + [(t, lam if 1 + i in long_ids else 1.0, lam) for i in range(n)], lam, "trap+batch")


FAMILIES = {"single": single, "batch": batch, "trap": trap, "trap+batch": trap_batch}


def ratio(inst: Instance, policy: Policy) -> float:
    alg = simulate(inst, policy)
    alg.validate()
    opt = inst.meta["opt"] if "opt" in inst.meta else offline_opt(inst, max_n=MAX_N + 1).total_completion
    return alg.total_completion / opt


def random_worst(policy: Policy, lam: float, trials: int = 150, n: int = 9) -> float:
    worst = 1.0
    for seed in range(trials):
        inst = limit_instance(n, 1, lam=lam, limits=(1.0, 4.0, 16.0, 64.0),
                              size_dist=("extremes", "low", "uniform")[seed % 3],
                              load=(0.6, 1.0, 1.6)[(seed // 3) % 3], seed=seed)
        worst = max(worst, ratio(inst, policy))
    return worst


def policies_for(lam: float) -> list[tuple[str, Policy]]:
    """Never-idle baselines and DelayedSLF with alpha = lam^(-x) for x = 0, 1/4, 1/2, 3/4, 1."""
    out: list[tuple[str, Policy]] = [("FCFS", FCFS()), ("SLF", SLF())]
    for x in (0.0, 0.25, 0.5, 0.75, 1.0):
        out.append((f"alpha=lam^-{x:g}", DelayedSLF(lam ** (-x))))
    return out


def run(lams: list[float], random_trials: int = 150) -> list[dict]:
    rows = []
    for lam in lams:
        for label, policy in policies_for(lam):
            res = {name: ratio(build(policy, lam), policy) for name, build in FAMILIES.items()}
            res["random"] = random_worst(policy, lam, random_trials)
            worst = max(res, key=res.get)
            rows.append({"lam": lam, "policy": label,
                         "alpha": getattr(policy, "alpha", float("nan")),
                         **{k: round(v, 4) for k, v in res.items()},
                         "worst": round(res[worst], 4), "worst_family": worst,
                         "sqrt_lam": round(math.sqrt(lam), 4)})
    return rows


def plot(rows: list[dict], path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    lams = sorted({r["lam"] for r in rows})
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.2))
    xs = [0.0, 0.25, 0.5, 0.75, 1.0]
    for lam in lams:
        if lam == 1:
            continue
        ys = [next(r["worst"] for r in rows if r["lam"] == lam and r["policy"] == f"alpha=lam^-{x:g}") for x in xs]
        a.plot(xs, ys, "o-", label=f"lam = {lam:g}")
    a.set_yscale("log")
    a.set_xlabel("x, where alpha = lam^(-x)")
    a.set_ylabel("worst ratio found (log scale)")
    a.set_title("Worst ratio against the waiting threshold")
    a.axvline(0.5, color="gray", ls=":")
    a.legend()

    for label, style in (("FCFS", "s--"), ("SLF", "^--"), ("alpha=lam^-0", "x-"), ("alpha=lam^-0.5", "o-"), ("alpha=lam^-1", "d-")):
        b.plot(lams, [next(r["worst"] for r in rows if r["lam"] == lam and r["policy"] == label) for lam in lams],
               style, label=label)
    b.plot(lams, [math.sqrt(v) for v in lams], "k:", label="sqrt(lam)")
    b.plot(lams, [1 + math.sqrt(v) for v in lams], "k-.", label="1 + sqrt(lam)")
    b.set_xscale("log", base=2)
    b.set_yscale("log")
    b.set_xlabel("lam")
    b.set_ylabel("worst ratio found (log scale)")
    b.set_title("Worst ratio against lam")
    b.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lams", type=float, nargs="+", default=[1, 4, 16, 64, 256])
    ap.add_argument("--random-trials", type=int, default=150)
    ap.add_argument("--out", default="results")
    a = ap.parse_args()

    t0 = time.time()
    rows = run(a.lams, a.random_trials)
    out = Path(a.out) / (time.strftime("%Y%m%d-%H%M%S") + "-alpha-sweep")
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "alpha_sweep.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    plot(rows, out / "alpha_sweep.png")

    names = list(FAMILIES) + ["random"]
    print(f"{'lam':>5} {'policy':<16} " + " ".join(f"{n:>10}" for n in names) + f" {'WORST':>9}  family")
    for r in rows:
        print(f"{r['lam']:>5g} {r['policy']:<16} " + " ".join(f"{r[n]:>10.2f}" for n in names)
              + f" {r['worst']:>9.2f}  {r['worst_family']}")
        if r["policy"] == "alpha=lam^-1":
            print(f"{'':>5} sqrt(lam) = {r['sqrt_lam']:.2f}, 1 + sqrt(lam) = {1 + r['sqrt_lam']:.2f}\n")
    print(f"done in {time.time() - t0:.1f}s; wrote {out}")


if __name__ == "__main__":
    main()
