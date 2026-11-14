# Problem Definition (simplified scope)

**Non-Clairvoyant Non-Preemptive Online Scheduling on a Pool of Identical Workers with Bounded Job Sizes**

EECS 6111 (Online Algorithms) course project — Liao & Shao

> This version replaces the general model of the proposal (unrelated speeds $s_{ij}$, parameters
> $\Delta, H, m$) with a smaller model that maps onto a real system and is small enough to finish.
> The general version is kept in [archive/problem_definition_general_v1.md](archive/problem_definition_general_v1.md).
> Why this scope was chosen, and what is already known, is in
> [notes/scoping_findings.md](notes/scoping_findings.md).

---

## 1. Summary

A cluster partition has $m$ identical workers. Jobs arrive over time. Each job runs on one worker, and
once it starts it must run to completion: no pausing, migration, or restart. The scheduler does **not**
know how long a job will run. It only knows that every job takes between $p_{\min}$ and $p_{\max}$,
because the system enforces a time limit $p_{\max}$ and we only consider jobs of at least $p_{\min}$.
The scheduler decides which waiting job to start when a worker is free, and whether to leave a worker
idle on purpose. The goal is to minimize the total completion time $\sum_j C_j$. We measure an online
rule by its competitive ratio against the offline optimum, as a function of the two parameters

$$
\Delta = \frac{p_{\max}}{p_{\min}} \quad (\text{size uncertainty}), \qquad m \quad (\text{number of workers}).
$$

---

## 2. Industry setting

**Main example: a partition of a shared batch cluster (e.g. Slurm), restricted to single-node jobs.**

Users submit jobs to a partition over time. Each job runs on one node until it finishes. Slurm
enforces a time limit per job: when the limit is reached, the job's tasks are sent SIGTERM and then
SIGKILL ([sbatch](https://slurm.schedmd.com/sbatch.html)), and the partition's `MaxTime` caps every
request ([slurm.conf](https://slurm.schedmd.com/slurm.conf.html)). Preemption is disabled by default
([preemption guide](https://slurm.schedmd.com/preempt.html)). Users do give runtime estimates, but
workload studies found them "extremely unreliable", with actual runtimes spread roughly uniformly
below the estimate (Mu'alem & Feitelson, IEEE TPDS 2001); see also Tsafrir, Etsion & Feitelson
(IEEE TPDS 2007). What users experience is their average wait or turnaround time.

| Model assumption | Mechanism in the real system | Fit |
| --- | --- | --- |
| Jobs arrive online | users submit over time | holds |
| $m$ identical workers | the nodes of one homogeneous partition | holds after restricting to single-node jobs |
| Size $p_j$ unknown | user estimates are unreliable (Mu'alem & Feitelson 2001) | holds |
| $p_j \le p_{\max}$, known | the enforced time limit / partition `MaxTime` | holds |
| $p_j \ge p_{\min}$, known | no physical floor; $p_{\min}$ is "the shortest job we care about" (workload studies filter out jobs that fail at start-up, e.g. under 90 s) | by convention |
| Non-preemptive | Slurm's default: preemption off | holds |
| Scheduler may idle on purpose | a custom dispatcher can hold a node | allowed by the model, not used by default schedulers |
| Objective $\sum_j C_j$ | sites track average wait/turnaround, i.e. flow time | close (see §3.6) |

Realistic values are large: for example $p_{\min} = 90\text{ s}$ and $p_{\max} = 4\text{ h}$ give
$\Delta = 160$.

**Second example (one sentence in the report): a capped serverless worker pool.** An AWS Lambda
function with a concurrency cap of $m$ runs at most $m$ invocations at once, each environment runs one
invocation at a time, and every invocation is cut off at a configured timeout
([timeout](https://docs.aws.amazon.com/lambda/latest/dg/configuration-timeout.html),
[concurrency](https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html)). A dispatcher in
front of the pool faces the same problem.

**What the model deliberately leaves out:** multi-node jobs and backfilling; priorities and fair-share;
per-job time limits (we use one global $p_{\max}$); predicting runtimes from a user's history;
kill-and-requeue when a job hits its limit; heterogeneous node types (see the optional extension in §6).
Our results therefore measure the cost of *one job per worker, no preemption, unknown sizes*. They are
not a model of a production scheduler end to end.

---

## 3. Formal model

In standard notation the problem is

$$
P \;\big|\; r_j,\ \text{online},\ \text{non-clairvoyant},\ \text{non-pmtn},\ p_j \in [p_{\min}, p_{\max}] \;\big|\; \textstyle\sum_j C_j .
$$

### 3.1 Input

- Workers $\mathcal{M} = \{1, \dots, m\}$, all identical (unit speed).
- Jobs $\mathcal{J} = \{1, \dots, n\}$. Job $j$ has a release time $r_j \ge 0$ and a size $p_j$ with
  $$
  p_{\min} \le p_j \le p_{\max}.
  $$
  The size is the job's running time on any worker.

### 3.2 Schedule

A schedule assigns each job $j$ a worker $a_j \in \mathcal{M}$ and a start time $S_j$. Its completion
time is

$$
C_j = S_j + p_j .
$$

### 3.3 Feasibility

1. **Release:** $S_j \ge r_j$ for all $j$.
2. **One job per worker at a time:** if $j \ne k$ and $a_j = a_k$, then $[S_j, C_j) \cap [S_k, C_k) = \varnothing$.
3. **Non-preemption:** job $j$ runs without interruption on worker $a_j$ during $[S_j, C_j)$. There is
   no pausing, migration, or kill-and-restart.

Workers may stay idle even while jobs are waiting.

### 3.4 Information (online, non-clairvoyant)

**Known in advance:** $m$, $p_{\min}$, $p_{\max}$. **Not known:** $n$, and anything about future jobs.

At time $t$ the scheduler knows

$$
\mathcal{I}(t) = \{m, p_{\min}, p_{\max}\}
\;\cup\; \{\, r_j : r_j \le t \,\}
\;\cup\; \{\, (a_j, S_j) : S_j \le t \,\}
\;\cup\; \{\, C_j : C_j \le t \,\}.
$$

It does **not** know $p_j$ for any job that has not finished. A job is placed on a worker only when it
starts (jobs wait in one central queue). Every decision at time $t$ (which waiting job to start on which
idle worker, if any) must be a function of $\mathcal{I}(t)$.

So the scheduler knows each job's running time only up to a factor $\Delta$: $p_j \in [p_{\min}, p_{\max}]$.
At $\Delta = 1$ the problem is clairvoyant; as $\Delta \to \infty$ the scheduler knows nothing about sizes.

### 3.5 Objective

$$
\min \; \mathrm{ALG}(I) = \sum_{j \in \mathcal{J}} C_j .
$$

### 3.6 Remark on flow time

Practitioners measure turnaround (flow) time $F_j = C_j - r_j$. Since
$\sum_j F_j = \sum_j C_j - \sum_j r_j$, both objectives have the same optimal schedules, but their
competitive ratios differ: the ratio for $\sum C_j$ is never larger. We study $\sum C_j$, as in the
proposal, and the report should say so explicitly.

---

## 4. Benchmark and competitive ratio

**Offline optimum.** $\mathrm{OPT}(I)$ is the minimum of $\sum_j C_j$ over all feasible schedules of
instance $I$. It knows every $r_j$ and $p_j$ in advance, but uses the same $m$ workers and is also
non-preemptive.

**Competitive ratio.** Let $\mathcal{I}(\Delta, m)$ be all instances with $m$ workers and sizes in
$[p_{\min}, p_{\max}]$, where $p_{\max}/p_{\min} = \Delta$, with any $n$ and any release times. For a
deterministic online algorithm,

$$
\rho_{\mathrm{ALG}}(\Delta, m) = \sup_{I \in \mathcal{I}(\Delta, m)} \frac{\mathrm{ALG}(I)}{\mathrm{OPT}(I)},
\qquad
\rho^{*}(\Delta, m) = \inf_{\mathrm{ALG}} \rho_{\mathrm{ALG}}(\Delta, m).
$$

For a randomized algorithm, replace $\mathrm{ALG}(I)$ by $\mathbb{E}[\mathrm{ALG}(I)]$ (oblivious
adversary).

**Scale invariance.** Multiplying all release times and sizes by the same constant multiplies both
$\mathrm{ALG}$ and $\mathrm{OPT}$ by it (for rules whose waiting times scale with $p_{\min}$). So only
the ratio $\Delta$ matters, and we may normalize $p_{\min} = 1$, $p_{\max} = \Delta$.

---

## 5. Research questions

1. **How does $\rho^{*}(\Delta, m)$ depend on $\Delta$ and $m$?** Lower bounds for every deterministic
   algorithm, and upper bounds for concrete rules.
2. **Does waiting help?** Is there a choice of $\tau$ for which the delayed rule below beats FCFS, and
   does the answer change between $m = 1$ and $m \ge 2$?
3. **Randomization.** Can a randomized rule (random order, random delay) do better than every
   deterministic rule?
4. **Experiments.** Empirical ratios against the exact $\mathrm{OPT}$ on small instances, on synthetic
   workloads and on single-node jobs from public HPC traces
   ([Parallel Workloads Archive](https://www.cs.huji.ac.il/labs/parallel/workload/)).

## 5.1 Baselines (existing rules, no new algorithm yet)

All rules see only the waiting queue (release times, sorted by $(r_j, j)$), the idle workers, the
current time $t$, and $m, p_{\min}, p_{\max}$.

| Rule | Description | Idles on purpose? | Code |
| --- | --- | --- | --- |
| **FCFS** | when a worker is idle, start the oldest waiting job on it | no | `FCFS` |
| **RandomIdle** | oldest waiting job on a uniformly random idle worker (randomized) | no | `RandomIdle` |
| **Delayed($\tau$)** | job $j$ becomes eligible only at $t \ge r_j + \tau$; the oldest eligible job starts on an idle worker | yes | `Delayed:<tau>` |

Candidate thresholds (already in the code):

$$
\tau \in \Big\{\, 0,\;\; p_{\min},\;\; \sqrt{p_{\min} p_{\max}},\;\; p_{\max} \,\Big\}.
$$

$\mathrm{Delayed}(0)$ is FCFS. On identical workers, `OldestFastest` is the same rule as FCFS (ties go
to the lowest-numbered worker), and `SpeedThreshold` only matters once speeds differ (§6).

---

## 6. How to add parameters later (optional)

Each extension adds one parameter and keeps the rest of the model unchanged.

| Order | Extension | New parameter | What changes | Industry hook |
| --- | --- | --- | --- | --- |
| 1 | randomized algorithms | none | $\mathbb{E}[\mathrm{ALG}]$ instead of $\mathrm{ALG}$ | random tie-breaking is cheap |
| 2 | **two related workers**, speeds $1$ and $H$ | $H \ge 1$ | runtime of $j$ is $p_j$ on the slow worker and $p_j/H$ on the fast one; new dilemma: use the idle slow worker or wait for the fast one | a partition mixing two node generations |
| — | general related or unrelated speeds | many | out of scope; experiments only | — |

If unrelated speeds $s_{ij}$ are ever used again, define speed heterogeneity per job,
$H = \max_j \frac{\max_i s_{ij}}{\min_i s_{ij}}$, not globally over all $(i, j)$; the global
definition also counts differences in job scale (see [notes/scoping_findings.md](notes/scoping_findings.md)).

---

## 7. Mapping to the code

| Object | Code |
| --- | --- |
| instance with identical workers | `model.random_instance(n, m, speed_model="identical", p_min=..., p_max=..., size_model=...)` |
| what the scheduler sees (no size) | `model.JobView` |
| known parameters | `policies.Context` (`m`, `p_min`, `p_max`; `H = 1` on identical workers) |
| online execution | `simulator.simulate(instance, policy)` |
| $\mathrm{OPT}$ (exact, $n \lesssim 12$) / lower bound | `offline.offline_opt`, `offline.opt_lower_bound` |
| long-job-then-short-jobs instance | `model.lower_bound_instance(n, L, delta_t, m, offset)` |
| experiment sweep | `experiments.py`; for this scope, restrict the grid to `speed_model="identical"` |

Known gaps in the current code relative to this definition:

- `experiments.default_grid` still sweeps related and unrelated speeds.
- Lower-bound scenarios are built with `offset=0`, so they do not adapt to a delayed rule's $\tau$.
- Scenario labels print `H=4` for identical-speed scenarios even though they are built with $H = 1$.
- There is no loader for Parallel Workloads Archive traces yet.
