# Problem Definition

**Online Non-Preemptive Scheduling of Batch Jobs with Declared Time Limits**

EECS 6111 (Online Algorithms) course project — Liao & Shao

> **Scope history.**
> - v1: unrelated speeds, parameters $\Delta, H, m$ — [archive/problem_definition_general_v1.md](archive/problem_definition_general_v1.md)
> - v2: identical workers with one global size range $[p_{\min}, p_{\max}]$ — [archive/problem_definition_v2_bounded_sizes.md](archive/problem_definition_v2_bounded_sizes.md)
> - v3 (this file): each job declares its own time limit.
>
> The reason for each change is in [notes/scoping_findings.md](notes/scoping_findings.md). In short, v2 is
> too symmetric: every job looks the same to the scheduler, so every rule that starts jobs immediately
> has the same worst case and deliberate waiting cannot help by more than a constant. v3 restores
> job-specific information, which is what real batch jobs carry.

---

## 1. Summary

We focus on one kind of task: **batch jobs submitted to an HPC cluster partition, where every job
declares a time limit.** A partition has $m$ identical nodes. Jobs arrive over time. When job $j$
arrives, the scheduler sees its **declared limit $u_j$**: the user's requested walltime, which the system
enforces. The scheduler does not see the true running time $p_j$. It only knows that the limit
overestimates the running time by at most a known factor $\lambda$:

$$
\frac{u_j}{\lambda} \;\le\; p_j \;\le\; u_j .
$$

Jobs run without interruption. The scheduler decides which waiting job to start when a node is free,
and whether to leave a node idle on purpose. The goal is to minimize the total completion time
$\sum_j C_j$. The central question is **how much the declared limits help**, measured by the
competitive ratio as a function of the accuracy $\lambda$ and the number of nodes $m$.

---

## 2. Industry setting

**HPC batch partition (e.g. Slurm), single-node jobs.**

- **Each job declares a limit, and it is enforced.** Users request a time limit (`sbatch --time`). When
  it is reached, the job's tasks are sent SIGTERM and then SIGKILL
  ([sbatch](https://slurm.schedmd.com/sbatch.html)). The partition's `MaxTime` caps every request
  ([slurm.conf](https://slurm.schedmd.com/slurm.conf.html)).
- **Limits are known, true runtimes are not.** Workload studies found that user estimates are
  "extremely unreliable", with actual runtimes spread roughly uniformly below the estimate
  (Mu'alem & Feitelson, IEEE TPDS 12(6), 2001). They are also coarse: about 90% of jobs use the same
  20 values (Tsafrir, Etsion & Feitelson, IEEE TPDS 18(6), 2007). A limit is an upper bound, not a
  prediction.
- **No preemption by default** ([preemption guide](https://slurm.schedmd.com/preempt.html)).
- **Real schedulers use the limits.** Backfilling relies on each job's limit. So "the scheduler sees
  $u_j$" describes real systems better than the global range of v2.
- **Real data exists.** The [Parallel Workloads Archive](https://www.cs.huji.ac.il/labs/parallel/workload/)
  records, for every job, its submit time, its requested time ($u_j$) and its actual run time ($p_j$)
  ([SWF format](https://www.cs.huji.ac.il/labs/parallel/workload/swf.html)). So $\lambda$ can be
  measured directly and rules can be tested on real traces.

| Model element | Real mechanism | Fit |
| --- | --- | --- |
| $m$ identical workers, fixed | the nodes of one homogeneous partition | holds after restricting to single-node jobs |
| jobs arrive online | users submit over time | holds |
| $u_j$ known at arrival | requested walltime (`--time`) | holds |
| $p_j \le u_j$ | enforced limit; a job that hits it is killed and frees its node at exactly $u_j$ | holds: for the schedule, a killed job is a job of size $u_j$ |
| $p_j \ge u_j / \lambda$, $\lambda$ known | no hard floor in reality; many jobs end far below their limit | **stylized**; experiments must measure or filter it (§7) |
| non-preemptive | Slurm's default | holds |
| objective $\sum_j C_j$ | sites track average wait/turnaround (flow time) | close (§3.6) |

**What the model leaves out:** multi-node jobs and backfill reservations; priorities, fair-share and
per-user limits; heterogeneous node types; runtime prediction from user history; jobs that fail
immediately (they have $p_j \approx 0$ and violate $p_j \ge u_j/\lambda$).

---

## 3. Formal model

### 3.1 Input

- **Workers** $\mathcal{M} = \{1, \dots, m\}$, identical (unit speed). The set is **fixed**: it is known
  before time $0$, every worker is available from time $0$ on, and none is added or removed.
- **Jobs** $\mathcal{J} = \{1, \dots, n\}$, **revealed online**. Job $j$ has a release time $r_j \ge 0$,
  a declared limit $u_j > 0$, and a size $p_j$ with
  $$
  \frac{u_j}{\lambda} \;\le\; p_j \;\le\; u_j .
  $$
- **Accuracy parameter** $\lambda \ge 1$, the same for all jobs. The declared limits $u_j$ themselves
  may differ arbitrarily from job to job.

### 3.2 Schedule

A schedule gives each job a worker $a_j \in \mathcal{M}$ and a start time $S_j$; then

$$
C_j = S_j + p_j .
$$

### 3.3 Feasibility

1. **Release:** $S_j \ge r_j$.
2. **One job per worker at a time:** if $j \ne k$ and $a_j = a_k$, then $[S_j, C_j) \cap [S_k, C_k) = \varnothing$.
3. **Non-preemption:** job $j$ runs without interruption on worker $a_j$ during $[S_j, C_j)$. There is
   no pausing, migration, or kill-and-restart.

Workers may stay idle even while jobs are waiting. Jobs wait in one central queue and are bound to a
worker only when they start.

### 3.4 Information

**Known in advance:** $m$ and $\lambda$. **Not known:** $n$, and anything about future jobs.

At time $t$ the scheduler knows

$$
\mathcal{I}(t) = \{m, \lambda\}
\;\cup\; \{\, (r_j,\, u_j) : r_j \le t \,\}
\;\cup\; \{\, (a_j, S_j) : S_j \le t \,\}
\;\cup\; \{\, C_j : C_j \le t \,\}.
$$

- **Online:** the scheduler does not know that job $j$ exists before $r_j$.
- **Non-clairvoyant up to a factor $\lambda$:** after $r_j$ it knows $u_j$, hence
  $p_j \in [u_j/\lambda,\, u_j]$, but not $p_j$ itself until the job finishes.

Every decision at time $t$ must be a function of $\mathcal{I}(t)$.

### 3.5 Objective

$$
\min \;\sum_{j \in \mathcal{J}} C_j .
$$

### 3.6 Remark on flow time

Sites measure turnaround $F_j = C_j - r_j$. Since $\sum_j F_j = \sum_j C_j - \sum_j r_j$, the optimal
schedules are the same, but the competitive ratios differ (the ratio for $\sum C_j$ is never larger).
We study $\sum C_j$, and the report should say so.

---

## 4. Benchmark and competitive ratio

**Offline optimum.** $\mathrm{OPT}(I)$ is the minimum of $\sum_j C_j$ over feasible schedules. It knows
every $r_j$ and $p_j$, uses the same $m$ workers, is non-preemptive, and **may idle**. (Restricting OPT to
schedules that never idle would hide the cost of starting jobs too early.)

**Competitive ratio.** Let $\mathcal{I}(\lambda, m)$ contain all instances with $m$ workers and
$u_j/\lambda \le p_j \le u_j$ for every $j$, with any $n$, release times and limits. For a deterministic
online algorithm,

$$
\rho_{\mathrm{ALG}}(\lambda, m) = \sup_{I \in \mathcal{I}(\lambda, m)} \frac{\mathrm{ALG}(I)}{\mathrm{OPT}(I)},
\qquad
\rho^{*}(\lambda, m) = \inf_{\mathrm{ALG}} \rho_{\mathrm{ALG}}(\lambda, m).
$$

For randomized algorithms, use $\mathbb{E}[\mathrm{ALG}(I)]$ (oblivious adversary).

**Two special cases that anchor the problem.** Both are contained in $\mathcal{I}(\lambda, m)$, so
lower bounds for them carry over to $\rho^*(\lambda, m)$.

| Special case | What it becomes | Status |
| --- | --- | --- |
| $\lambda = 1$ | $p_j = u_j$: **clairvoyant** online $P \mid r_j \mid \sum C_j$ | known constant ratios; on one machine the best deterministic ratio is $2$ (Hoogeveen & Vestjens, IPCO 1996) |
| all $u_j$ equal to $u$ | v2 with $p_{\min} = u/\lambda$, $p_{\max} = u$, so $\Delta = \lambda$ | see [notes](notes/scoping_findings.md) §1–2b (agent-derived, **to be verified**) |

**Observation (why the limits must be used).** A rule that ignores $u_j$, such as FCFS, has a ratio that
grows with the spread of the limits. Already at $\lambda = 1$ on one worker: start a job with
$u = p = L$ at time $0$, then release $k$ jobs with $u = p = 1$ just after. FCFS pays about $(k+1)L$,
while OPT pays $L + O(k^2)$. So a ratio bounded in terms of $\lambda$ alone needs a rule that looks at
$u_j$.

---

## 5. Research questions

1. **How much do declared limits help?** How does $\rho^*(\lambda, m)$ grow between the clairvoyant end
   ($\lambda = 1$, a constant) and the uninformative end (large $\lambda$)? Is it $\Theta(\sqrt{\lambda})$,
   $\Theta(\lambda)$, or something else? Does it depend on $m$?
2. **Order.** How well does starting the job with the smallest declared limit do, compared with FCFS?
3. **Waiting.** In the clairvoyant case, waiting is essential (delayed SPT). Does a delayed rule driven by
   $u_j$ still help when $\lambda > 1$, and how should the delay depend on $u_j$ and $\lambda$?
4. **Experiments.** Measure the distribution of $u_j / p_j$ in real traces. Compare the rules below on
   synthetic instances (with exact OPT for small $n$) and on single-node jobs from Parallel Workloads
   Archive traces.

---

## 6. Baselines (existing rules only)

All rules see only $\mathcal{I}(t)$: for each waiting job, its release time and declared limit.

| Rule | Description | Uses $u_j$? | Idles on purpose? |
| --- | --- | --- | --- |
| **FCFS** | when a worker is idle, start the waiting job that arrived first | no | no |
| **SLF** (shortest declared limit first) | when a worker is idle, start the waiting job with the smallest $u_j$ (SPT on the declared limits) | yes | no |
| **Delayed($\tau$)** | job $j$ becomes eligible only at $t \ge r_j + \tau$; the oldest eligible job starts | no | yes |
| **Delayed-SLF** | the delayed SPT rule of Hoogeveen & Vestjens with $u_j$ in place of $p_j$: an idle worker starts the eligible job with the smallest limit only if $t \ge u_j$, otherwise it waits | yes | yes |

The first three are already in the code. SLF and Delayed-SLF are the classical size-based rules fed with
the declared limits instead of the true sizes. How to adapt them to $\lambda > 1$ (for example, which
value between $u_j/\lambda$ and $u_j$ to use as a job's "size") is part of research question 3, not a
baseline.

---

## 7. Experiments: generating instances and using traces

- **Synthetic:** draw $u_j$ from a coarse set of values (mimicking the modal requests in real traces),
  then draw $p_j \in [u_j/\lambda, u_j]$, for example uniformly or with the mass near $u_j/\lambda$
  (users overestimate).
- **Traces:** take single-node jobs from a Parallel Workloads Archive trace. SWF gives the submit time
  (field 2), the run time (field 4) and the requested time (field 9). Jobs with $p_j < u_j/\lambda$ break
  the model's assumption. Either filter them out for a chosen $\lambda$, or report the ratio $u_j/p_j$
  that is actually observed. Jobs killed at their limit fit the model exactly ($p_j = u_j$).

---

## 8. Optional extensions (later)

| Extension | New parameter | Question |
| --- | --- | --- |
| randomized algorithms | none | does randomizing order or delay beat every deterministic rule? |
| two node generations, speeds $1$ and $H$ | $H$ | use an idle slow node or wait for a fast one? |
| per-job accuracy | $\lambda_j$ | different users estimate with different accuracy |

---

## 9. Mapping to the code

The current simulator implements v2: there is no declared limit. Changes needed for v3:

| Needed | Where |
| --- | --- |
| a declared limit per job, visible to policies | add `limit` to `model.Job` and `model.JobView` |
| instance generator with $p_j \in [u_j/\lambda, u_j]$ | new generator in `model.py` |
| policies SLF and Delayed-SLF | `policies.py` (register in `make_policy`) |
| known parameter $\lambda$ | `policies.Context` |
| Parallel Workloads Archive loader (SWF fields 2, 4, 9; single-node jobs) | new module |
| exact OPT and lower bound | `offline.offline_opt` / `opt_lower_bound` work unchanged (they only use $r_j$ and $p_j$) |
| experiment grid over $\lambda$ and $m$ | `experiments.py` (drop the speed models) |
