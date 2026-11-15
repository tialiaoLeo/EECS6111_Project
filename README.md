# EECS6111_Project

Simulator for **online non-preemptive scheduling with hidden job sizes** (EECS 6111 project, Liao & Shao).
The current problem definition is [docs/problem_definition.md](docs/problem_definition.md):

- `m` identical workers, fixed; jobs arrive online.
- Job `j` arrives at `r_j` with a **declared time limit** `u_j` (like a requested walltime). Its true size
  `p_j` is hidden, with `u_j / lam <= p_j <= u_j` for a known `lam >= 1`.
- Jobs run without interruption. Objective: minimize `sum_j C_j`, compared with the offline optimum.

The earlier heterogeneous-speed model (thread `i` runs job `j` at speed `s_ij`) is still available with
`--model speeds` / `--grid speeds`.

## Setup

```bash
python3 -m venv .venv            # on Ubuntu you may need: sudo apt install python3-venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest       # 144 tests, incl. OPT vs brute force
```

## Layout

| module | purpose |
| --- | --- |
| `sched_sim/model.py` | `Job` (with optional declared `limit`), `JobView` (what the scheduler sees: release, speeds, limit; never the size), `Instance` (with `lam`), `Schedule`; `limit_instance` (declared-limit model), `random_instance` (speed model), the proposal's lower-bound instance |
| `sched_sim/policies.py` | declared-limit baselines `FCFS`, `SLF` (shortest declared limit first), `Delayed(tau)`, `DelayedSLF` (Hoogeveen-Vestjens delayed SPT on the limits); speed-model rules `RandomIdle`, `OldestFastest`, `SpeedThreshold(alpha)` |
| `sched_sim/traces.py` | Parallel Workloads Archive (SWF) loader: single-node jobs, requested time as `u_j`, run time as `p_j`; drops jobs that fail at start-up |
| `sched_sim/simulator.py` | exact discrete-event simulator (supports `(1+eps)` speed augmentation) |
| `sched_sim/offline.py` | exact offline `Opt` (Pareto DP over subsets, n <= ~12) and a cheap lower bound for larger n |
| `sched_sim/executor.py` | runs a policy on **real worker processes** (one OS process per thread); speed is emulated by duty-cycling the CPU |
| `sched_sim/monitor.py` | background psutil sampler: per-process CPU/RSS, per-core CPU, memory |
| `sched_sim/experiments.py` | parallel sweep of trials over a process pool, timing every trial |
| `sched_sim/plots.py` | Gantt charts, runtime / waiting-time bars, CPU and memory timelines, ratio plots |

## Usage

All outputs go to `results/<timestamp>-<command>/` (change with `--out`).

```bash
# 1. Exact simulation of one declared-limit instance: every baseline vs OPT, stacked Gantt charts
.venv/bin/python -m sched_sim simulate -n 9 -m 2 --lam 8 --size-dist extremes --u-min 1 --u-max 32
#    --size-dist: uniform | loguniform | low (p = u/lam) | high (p = u) | extremes

# the proposal's lower-bound example with uninformative limits (all u_j = L, lam = L / delta)
.venv/bin/python -m sched_sim simulate --lower-bound -n 7 -m 1 --p-min 1 --p-max 64

# a real trace (Parallel Workloads Archive, SWF): first 200 single-node jobs, 4 workers, time in hours
.venv/bin/python -m sched_sim simulate --trace path/to/log.swf -n 200 -m 4
#    --trace-min-runtime 60  : drop jobs shorter than 60 s (failed at start-up)
#    --trace-lam-filter      : drop jobs with u/p > --lam (default: lam = largest u/p kept)

# 2. Real multi-process execution with resource monitoring
.venv/bin/python -m sched_sim execute -n 12 -m 3 --lam 4 --time-scale 0.05 --policies FCFS SLF DelayedSLF

# 3. Parallel experiment sweep over m x lam x size distribution (declared-limit model)
.venv/bin/python -m sched_sim experiment -n 8 --trials 20 --workers 4
.venv/bin/python -m sched_sim experiment --quick --trials 5
.venv/bin/python -m sched_sim experiment --grid speeds --quick     # the earlier speed-model grid
```

Policy strings: `FCFS`, `SLF`, `DelayedSLF` or `DelayedSLF:<alpha>` (eligible once `t >= alpha * u_j`),
`Delayed:<tau>` where `<tau>` is a number or one of `0`, `p_min`, `p_max`, `sqrt` (= sqrt(p_min p_max)),
`p_max/H`; speed model only: `RandomIdle`, `OldestFastest`, `SpeedThreshold:<alpha>`. Without
`--policies`, each command runs the baselines of the instance's model.

## Adding a policy

Subclass `Policy` in `sched_sim/policies.py`, implement
`decide(now, waiting, idle) -> [(job_id, thread), ...]` and, if the policy waits on a timer,
`next_wakeup(now, waiting)`. Register it in `make_policy`. The same object then works in the
simulator, the real executor, and the experiment runner.
