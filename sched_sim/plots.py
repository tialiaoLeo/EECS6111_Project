"""Matplotlib figures for schedules, real executions and experiments."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .executor import ExecutionResult  # noqa: E402
from .model import Schedule  # noqa: E402
from .monitor import ResourceMonitor  # noqa: E402

CMAP = plt.get_cmap("tab20")


def _gantt(ax, bars, m: int, releases=None, title: str = "", xlabel: str = "time (model units)") -> None:
    """bars: iterable of (thread, start, end, job_id)."""
    for thread, start, end, job in bars:
        ax.barh(thread, end - start, left=start, height=0.6, color=CMAP(job % 20), edgecolor="black", lw=0.5)
        if end - start > 0:
            ax.text((start + end) / 2, thread, str(job), ha="center", va="center", fontsize=7)
    if releases is not None:
        for r in releases:
            ax.axvline(r, color="grey", lw=0.5, ls=":", alpha=0.6)
    ax.set_yticks(range(m), [f"T{i}" for i in range(m)])
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    ax.set_title(title, fontsize=10)


def plot_schedules(schedules: list[Schedule], path: str | Path) -> None:
    """Stacked Gantt charts, one per policy, on a shared time axis."""
    fig, axes = plt.subplots(len(schedules), 1, figsize=(12, 1.2 + 1.1 * len(schedules) * schedules[0].instance.m ** 0.5 + 0.6), sharex=True, squeeze=False)
    opt = next((s.total_completion for s in schedules if s.policy == "OPT"), None)
    for ax, s in zip(axes[:, 0], schedules):
        bars = [(a.thread, a.start, a.end, a.job) for a in s.assignments.values()]
        ratio = f"  ratio={s.total_completion / opt:.3f}" if opt else ""
        _gantt(ax, bars, s.instance.m, [j.release for j in s.instance.jobs],
               f"{s.policy}: sum C_j = {s.total_completion:.2f}{ratio}", xlabel="")
    axes[-1, 0].set_xlabel("time (model units); dotted lines = job releases")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _resource_axes(ax_cpu, ax_core, ax_mem, mon: ResourceMonitor, offset: float = 0.0, scale: float = 1.0, proc_labels=None) -> None:
    if not mon.samples:
        return
    t = np.array([s.t for s in mon.samples])
    x = (t - offset) / scale
    labels = proc_labels or sorted({k for s in mon.samples for k in s.procs})
    for k, lbl in enumerate(labels):
        ax_cpu.plot(x, [s.procs.get(lbl, (0, 0))[0] for s in mon.samples], label=lbl, color=CMAP(k * 2 % 20), lw=1)
    ax_cpu.set_ylabel("process CPU %")
    ax_cpu.legend(fontsize=7, ncol=min(6, max(1, len(labels))), loc="upper right")

    cores = np.array([s.cpu_per_core for s in mon.samples]).T
    im = ax_core.imshow(cores, aspect="auto", origin="lower", cmap="magma", vmin=0, vmax=100,
                        extent=[x[0], x[-1], -0.5, cores.shape[0] - 0.5], interpolation="nearest")
    ax_core.set_ylabel("core")
    plt.colorbar(im, ax=ax_core, label="CPU %", pad=0.01)

    ax_mem.plot(x, [s.cpu_total for s in mon.samples], label="system CPU %", color="tab:red")
    ax_mem.plot(x, [s.mem_percent for s in mon.samples], label="system memory %", color="tab:blue")
    rss = [sum(v[1] for v in s.procs.values()) for s in mon.samples]
    ax2 = ax_mem.twinx()
    ax2.plot(x, rss, label="tracked RSS (MB)", color="tab:green", ls="--")
    ax2.set_ylabel("RSS MB")
    ax_mem.set_ylabel("%")
    h1, l1 = ax_mem.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax_mem.legend(h1 + h2, l1 + l2, fontsize=7, loc="upper right")


def plot_execution(res: ExecutionResult, path: str | Path) -> None:
    """Gantt of the measured run, runtimes, per-worker CPU, per-core heatmap, memory."""
    inst, recs = res.instance, sorted(res.records.values(), key=lambda r: r.job)
    fig = plt.figure(figsize=(13, 13))
    gs = fig.add_gridspec(5, 2, height_ratios=[1.2, 1, 1, 0.8, 0.9], width_ratios=[3, 1.3])
    ax_g = fig.add_subplot(gs[0, 0])
    ax_rt = fig.add_subplot(gs[1, 0])
    ax_wait = fig.add_subplot(gs[0, 1])
    ax_err = fig.add_subplot(gs[1, 1])
    ax_cpu = fig.add_subplot(gs[2, :])
    ax_core = fig.add_subplot(gs[3, :], sharex=ax_cpu)
    ax_mem = fig.add_subplot(gs[4, :], sharex=ax_cpu)

    _gantt(ax_g, [(r.thread, r.start, r.end, r.job) for r in recs], inst.m, [j.release for j in inst.jobs],
           f"{res.policy}: measured schedule, sum C_j = {res.total_completion:.2f} "
           f"(wall {res.wall_seconds:.2f}s, {res.time_scale}s per unit)")

    idx = np.arange(len(recs))
    ax_rt.bar(idx - 0.2, [r.planned_runtime for r in recs], 0.4, label="model p_j/s_ij")
    ax_rt.bar(idx + 0.2, [r.measured_runtime for r in recs], 0.4, label="measured")
    ax_rt.set_xticks(idx, [f"{r.job}\nT{r.thread}" for r in recs], fontsize=7)
    ax_rt.set_ylabel("runtime (model units)")
    ax_rt.set_title("per-job runtime (job id / thread)", fontsize=10)
    ax_rt.legend(fontsize=8)

    ax_wait.bar(idx, [r.wait for r in recs], color="tab:orange")
    ax_wait.set_title("waiting time S_j - r_j", fontsize=10)
    ax_wait.set_xlabel("job")

    err = [100 * (r.measured_runtime - r.planned_runtime) / r.planned_runtime for r in recs]
    ax_err.bar(idx, err, color="tab:purple")
    ax_err.set_title("runtime deviation (%)", fontsize=10)
    ax_err.set_xlabel("job")

    labels = [f"T{i}" for i in range(inst.m)] + ["dispatcher"]
    _resource_axes(ax_cpu, ax_core, ax_mem, res.monitor, offset=res.t0_offset, scale=res.time_scale, proc_labels=labels)
    ax_cpu.set_title("CPU usage per worker process (thread speed = duty cycle)", fontsize=10)
    ax_mem.set_xlabel("time (model units)")
    ax_cpu.set_xlim(ax_g.get_xlim())
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_policy_comparison(results: list[ExecutionResult], path: str | Path) -> None:
    """Bar chart of measured total completion time and wall time per policy."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.5))
    names = [r.policy for r in results]
    axes[0].bar(names, [r.total_completion for r in results], color="tab:blue")
    axes[0].set_title("measured sum of completion times")
    axes[1].bar(names, [r.wall_seconds for r in results], color="tab:gray")
    axes[1].set_title("wall-clock seconds")
    for ax in axes:
        ax.tick_params(axis="x", rotation=30, labelsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_experiment_ratios(rows: list[dict], path: str | Path) -> None:
    """Competitive ratio distributions: by policy per speed model, and mean ratio vs Delta."""
    policies = list(dict.fromkeys(r["policy"] for r in rows))
    random_rows = [r for r in rows if r["kind"] == "random"]
    speed_models = list(dict.fromkeys(r["speed_model"] for r in random_rows))
    lb_rows = [r for r in rows if r["kind"] == "lower_bound"]

    ncols = len(speed_models) + (1 if lb_rows else 0)
    fig, axes = plt.subplots(2, max(ncols, 1), figsize=(5 * max(ncols, 1), 8), squeeze=False)
    for c, sm in enumerate(speed_models):
        sub = [r for r in random_rows if r["speed_model"] == sm]
        data = [[r["ratio"] for r in sub if r["policy"] == p] for p in policies]
        axes[0, c].boxplot(data, tick_labels=policies, showfliers=True)
        axes[0, c].set_title(f"{sm} speeds: ALG / OPT", fontsize=10)
        axes[0, c].tick_params(axis="x", rotation=40, labelsize=7)

        deltas = sorted({r["delta"] for r in sub})
        for k, p in enumerate(policies):
            means = [np.mean([r["ratio"] for r in sub if r["policy"] == p and r["delta"] == d]) for d in deltas]
            worst = [np.max([r["ratio"] for r in sub if r["policy"] == p and r["delta"] == d]) for d in deltas]
            axes[1, c].plot(deltas, means, "o-", color=CMAP(k * 2 % 20), label=p)
            axes[1, c].plot(deltas, worst, "x:", color=CMAP(k * 2 % 20))
        axes[1, c].set_xscale("log", base=2)
        axes[1, c].set_xlabel("Delta = p_max / p_min")
        axes[1, c].set_title(f"{sm}: mean (o-) and worst (x:) ratio vs Delta", fontsize=10)
    if lb_rows:
        c = ncols - 1
        Ls = sorted({r["p_max"] for r in lb_rows})
        for k, p in enumerate(policies):
            vals = [np.mean([r["ratio"] for r in lb_rows if r["policy"] == p and r["p_max"] == L]) for L in Ls]
            axes[0, c].plot(Ls, vals, "o-", color=CMAP(k * 2 % 20), label=p)
        axes[0, c].set_xscale("log", base=2)
        axes[0, c].set_xlabel("L (long job size)")
        axes[0, c].set_title("proposal lower-bound instance", fontsize=10)
        axes[1, c].axis("off")
    handles, labels = axes[1, 0].get_legend_handles_labels() if speed_models else axes[0, -1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=min(6, len(labels)), fontsize=8)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_experiment_tasks(tasks: list[dict], mon: ResourceMonitor, path: str | Path) -> None:
    """Timeline of parallel trials per worker process, runtime histogram, and resource usage."""
    pids = sorted({t["pid"] for t in tasks})
    lane = {pid: i for i, pid in enumerate(pids)}
    fig = plt.figure(figsize=(13, 12))
    gs = fig.add_gridspec(4, 2, height_ratios=[1.2, 1, 0.8, 0.9], width_ratios=[3, 1.2])
    ax_t = fig.add_subplot(gs[0, 0])
    ax_h = fig.add_subplot(gs[0, 1])
    ax_cpu = fig.add_subplot(gs[1, :])
    ax_core = fig.add_subplot(gs[2, :], sharex=ax_cpu)
    ax_mem = fig.add_subplot(gs[3, :], sharex=ax_cpu)

    by_scen = defaultdict(int)
    for t in tasks:
        by_scen.setdefault(t["scenario"], len(by_scen))
    for t in tasks:
        ax_t.barh(lane[t["pid"]], t["end"] - t["start"], left=t["start"], height=0.7,
                  color=CMAP(by_scen[t["scenario"]] % 20), edgecolor="black", lw=0.2)
    ax_t.set_yticks(range(len(pids)), [f"pid {p}" for p in pids], fontsize=7)
    ax_t.set_title(f"{len(tasks)} trials on {len(pids)} worker processes (color = scenario)", fontsize=10)
    ax_t.set_xlabel("seconds")

    ax_h.hist([t["wall_seconds"] for t in tasks], bins=30, alpha=0.7, label="wall")
    ax_h.hist([t["cpu_seconds"] for t in tasks], bins=30, alpha=0.7, label="CPU")
    ax_h.set_title("per-trial run time (s)", fontsize=10)
    ax_h.legend(fontsize=8)

    labels = [f"pid{p}" for p in pids]
    _resource_axes(ax_cpu, ax_core, ax_mem, mon, proc_labels=labels)
    ax_cpu.set_title("CPU usage per pool worker", fontsize=10)
    ax_mem.set_xlabel("seconds")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
