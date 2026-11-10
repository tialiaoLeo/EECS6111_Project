# EECS6111_Project

Simulator for **non-clairvoyant, non-preemptive online job scheduling across heterogeneous
execution threads** (EECS 6111 project proposal, Liao & Shao).

Job `j` arrives at `r_j` with hidden size `p_j`; thread `i` runs it at speed `s_ij`
(runtime `p_j / s_ij`). Policies see only `r_j` and the speeds, never `p_j`, and can never
pause a started job. Objective: minimize `sum_j C_j`.

## Setup

```bash
python3 -m venv .venv            # on Ubuntu you may need: sudo apt install python3-venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest       # 55 tests, incl. OPT vs brute force
```

## Layout

| module | purpose |
| --- | --- |
| `sched_sim/model.py` | `Job`, `JobView` (what the scheduler sees), `Instance`, `Schedule`; random instances (identical / related / unrelated speeds, uniform / log-uniform / bimodal sizes, Poisson arrivals) and the proposal's lower-bound instance |
| `sched_sim/policies.py` | `FCFS`, `RandomIdle`, `OldestFastest`, `Delayed(tau)`, `SpeedThreshold(alpha)` |
| `sched_sim/simulator.py` | exact discrete-event simulator (supports `(1+eps)` speed augmentation) |
| `sched_sim/offline.py` | exact offline `Opt` (Pareto DP over subsets, n <= ~12) and a cheap lower bound for larger n |
| `sched_sim/executor.py` | runs a policy on **real worker processes** (one OS process per thread); speed is emulated by duty-cycling the CPU |
| `sched_sim/monitor.py` | background psutil sampler: per-process CPU/RSS, per-core CPU, memory |
| `sched_sim/experiments.py` | parallel sweep of trials over a process pool, timing every trial |
| `sched_sim/plots.py` | Gantt charts, runtime / waiting-time bars, CPU and memory timelines, ratio plots |

## Usage

All outputs go to `results/<timestamp>-<command>/`.

```bash
# 1. Exact simulation of one instance: every policy vs Opt, stacked Gantt charts
.venv/bin/python -m sched_sim simulate -n 8 -m 2 --speed-model related --size-model bimodal --p-max 32

# the proposal's lower-bound example (one long job at 0, n-1 short jobs at delta)
.venv/bin/python -m sched_sim simulate --lower-bound -n 8 -m 1 --p-min 1 --p-max 256

# 2. Real multi-process execution with resource monitoring
#    -> execution_<policy>.png (Gantt, runtimes, CPU per worker, per-core heatmap, memory)
#    -> jobs_<policy>.csv, resources_<policy>.csv
.venv/bin/python -m sched_sim execute -n 12 -m 3 --time-scale 0.1 --policies FCFS OldestFastest Delayed:sqrt
#    --workload compute : real hash work, runtime drifts with contention
#    --pin              : pin worker i to core i

# 3. Parallel experiment sweep (speed model x size model x Delta x m, plus lower-bound family)
#    -> results.csv, summary.csv, tasks.csv, resources.csv, ratios.png, tasks_and_resources.png
.venv/bin/python -m sched_sim experiment -n 10 --trials 20 --workers 4
.venv/bin/python -m sched_sim experiment --quick --trials 5
```

Policy strings: `FCFS`, `RandomIdle`, `OldestFastest`, `Delayed:<tau>` where `<tau>` is a number
or one of `0`, `p_min`, `p_max`, `sqrt` (= sqrt(p_min p_max)), `p_max/H`, and `SpeedThreshold:<alpha>`.

## Adding a policy

Subclass `Policy` in `sched_sim/policies.py`, implement
`decide(now, waiting, idle) -> [(job_id, thread), ...]` and, if the policy waits on a timer,
`next_wakeup(now, waiting)`. Register it in `make_policy`. The same object then works in the
simulator, the real executor, and the experiment runner.
