# Problem Definition

**Non-Clairvoyant Non-Preemptive Online Job Scheduling Across Heterogeneous Execution Threads**

EECS 6111 (Online Algorithms) course project — Liao & Shao

> This document expands the problem definition from the proposal: what every symbol means,
> what the scheduler knows at each moment, what counts as a valid schedule, how the offline
> optimum $\mathrm{OPT}$ is defined, how the competitive ratio is measured, and why the problem
> is hard. The last section maps each mathematical object to the code in `sched_sim/`.

---

## 0. The one-sentence version

There are $m$ threads with different speeds, and jobs arrive over time. When a job arrives, the scheduler **knows its speed on every thread but not its size** (non-clairvoyant), and once a job starts it **must run to completion on the same thread without interruption** (non-preemptive). The scheduler decides *when* to start *which* job on *which* thread, with the goal of minimizing the total completion time $\sum_j C_j$. We measure an online rule by its competitive ratio — how much worse it is than an offline optimum that knows everything in advance — and study how this ratio depends on the job size spread $\Delta$, the speed spread $H$, and the number of threads $m$.

---

## 1. Intuition and motivation

Picture a multi-threaded runtime engine or a small cluster:

- some threads are fast (performance cores, accelerator streams), others are slow (efficiency cores, utility threads);
- the same job runs for different amounts of time on different threads, and *how much* faster can depend on the job itself (one kind of job is much faster on an accelerator, another kind is not);
- users may submit runtime estimates, but those are often wrong — so we **assume the scheduler does not know job sizes at all**;
- once started, a job cannot be paused, migrated, or killed and restarted (for example because it holds a lock, occupies GPU memory, or has side effects).

In this setting the scheduler faces two fundamental dilemmas:

1. **Start now or wait (time dimension).** There is one waiting job and one idle thread. Start it now? If it turns out to be very long and a batch of short jobs arrives right after, all those short jobs are stuck behind it.
2. **Use a slow thread or wait for a fast one (speed dimension).** Only a slow thread is idle while the fast thread is busy. Put the job on the slow thread, or wait for the fast thread to free up? Since the scheduler does not know how long the job on the fast thread still needs, this is also a guess.

---

## 2. Formal model

### 2.1 Input (an instance $I$)

**Jobs.** $\mathcal{J} = \{1, 2, \dots, n\}$. Each job $j \in \mathcal{J}$ has:

| Symbol | Meaning | When the scheduler learns it |
| --- | --- | --- |
| $r_j \ge 0$ | release time (arrival time) | at time $r_j$ (the job "appears") |
| $p_j > 0$ | work requirement / size | **never in advance**; it can only be inferred after the job completes |
| $s_{ij} > 0$, $i \in \mathcal{T}$ | processing speed of job $j$ on thread $i$ | at time $r_j$, together with the job |

**Threads.** $\mathcal{T} = \{1, 2, \dots, m\}$, the $m$ worker threads.

**Runtime.** If job $j$ runs on thread $i$, it takes

$$
p_{ij} \;=\; \frac{p_j}{s_{ij}} .
$$

So $p_j$ is "how much work the job contains" and $s_{ij}$ is "how fast thread $i$ does this kind of work". Note that although the scheduler knows $s_{ij}$, it does not know $p_j$, so **it does not know any $p_{ij}$ either**. It only knows relative facts such as "job $j$ runs 3 times faster on thread 2 than on thread 1".

### 2.2 Speed models (from simple to general)

Following the standard $P / Q / R$ hierarchy from the scheduling literature:

| Model | Speed structure | Meaning | Name in the code |
| --- | --- | --- | --- |
| Identical ($P$) | $s_{ij} = 1$ | all threads are the same | `identical` |
| Related / uniform ($Q$) | $s_{ij} = s_i$ | each thread has a fixed speed, independent of the job | `related` |
| Unrelated ($R$) | $s_{ij}$ arbitrary | speed depends on both the thread and the job | `unrelated` |

These are nested: $P \subset Q \subset R$. Our general problem is the $R$ model; the plan is to start with $m=1$, then $P$, then $Q$, and finally $R$.

In Graham's three-field notation the problem is

$$
R \;\big|\; r_j,\ \text{online-time},\ \text{non-clairvoyant},\ \text{non-pmtn} \;\big|\; \textstyle\sum_j C_j .
$$

### 2.3 Global parameters known to the scheduler

The scheduler knows **in advance** (before any job arrives):

- the number of threads $m$;
- lower and upper bounds on job sizes $p_{\min}, p_{\max}$, such that for every $j$:
  $$
  0 < p_{\min} \le p_j \le p_{\max};
  $$
- an upper bound $H$ on speed heterogeneity:
  $$
  H \;\ge\; \frac{\max_{i,j} s_{ij}}{\min_{i,j} s_{ij}} .
  $$

From these we define the **job size ratio**

$$
\Delta \;=\; \frac{p_{\max}}{p_{\min}} \;\ge\; 1 .
$$

The scheduler does **not** know in advance: the number of jobs $n$, the release times and speeds of future jobs, or the size $p_j$ of any job.

> Why assume $\Delta$ is bounded? Section 5 shows that if $\Delta$ can be arbitrarily large, every "start immediately" rule can be forced to have a competitive ratio that grows linearly in $n$. $\Delta$ and $H$ are the two knobs we use to describe how hard an instance class is.

### 2.4 Decisions: what a schedule is

A schedule $\sigma$ assigns to every job $j$

- a thread $a_j \in \mathcal{T}$ (the assignment), and
- a start time $S_j$.

The **completion time** of job $j$ is then

$$
C_j \;=\; S_j + \frac{p_j}{s_{a_j j}} .
$$

### 2.5 Feasibility constraints

A schedule $\sigma$ is **feasible** if and only if:

1. **Release constraint**: no job starts before it arrives,
   $$
   S_j \;\ge\; r_j \qquad \forall j \in \mathcal{J}.
   $$
2. **At most one job per thread at a time**: for any two distinct jobs $j \ne k$ on the same thread ($a_j = a_k$), their execution intervals do not overlap,
   $$
   [S_j, C_j) \,\cap\, [S_k, C_k) \;=\; \varnothing .
   $$
3. **Non-preemption**: job $j$ runs **continuously** on the **single** thread $a_j$ throughout $[S_j, C_j)$. It cannot be paused, migrated to another thread, killed and restarted, or split across threads. (This is already built into the representation "one $a_j$, one $S_j$, $C_j = S_j + p_j/s_{a_j j}$".)

Note: **threads may idle on purpose.** Even if a job is waiting and a thread is idle, the scheduler may choose not to dispatch. This is what makes delayed rules possible.

### 2.6 Online and non-clairvoyant: the information constraint

Feasibility only describes what a schedule looks like. An online algorithm must also satisfy an **information constraint**: every decision may depend only on information revealed by the time the decision is made.

Define the **history** $\mathcal{I}(t)$ at time $t$. It contains exactly:

- for every released job ($r_j \le t$): $r_j$ and its speed vector $(s_{1j}, \dots, s_{mj})$;
- for every started job: $(a_j, S_j)$;
- for every completed job ($C_j \le t$): its completion time $C_j$ (so its size $p_j = (C_j - S_j)\, s_{a_j j}$ can be inferred);
- the known global parameters $m, p_{\min}, p_{\max}, H$.

$\mathcal{I}(t)$ does **not** contain: $p_j$ of any unfinished job (including how much work a running job has left), any information about future jobs, or $n$.

An **online algorithm** is a rule that, at every time $t$, uses only $\mathcal{I}(t)$ to decide which (waiting job, idle thread) pairs to start at $t$. Formally, the event "start job $j$ on thread $i$ at time $t$" must be a function of $\mathcal{I}(t)$ (non-anticipativity).

A direct consequence: **the scheduler sees a waiting queue in which each job has only two attributes — when it arrived and how fast it is on each thread — and no "size" attribute.** Two jobs with identical release times and speeds are indistinguishable to the scheduler, even if one has size $p_{\min}$ and the other $p_{\max}$.

### 2.7 Objective

$$
\min \;\; \mathrm{ALG}(I) \;=\; \sum_{j \in \mathcal{J}} C_j .
$$

We use **total completion time** rather than the makespan $\max_j C_j$ because each user cares about when *their own* job finishes, not when the last job finishes.

Two related quantities:

- **Mean completion time** $\frac{1}{n}\sum_j C_j$: differs by the factor $n$, so it is equivalent for optimization.
- **Total flow time** (response time) $\sum_j F_j$ with $F_j = C_j - r_j$:
  $$
  \sum_j F_j \;=\; \sum_j C_j \;-\; \sum_j r_j .
  $$
  On a **fixed instance** the two differ by the algorithm-independent constant $\sum_j r_j$, so they have the same optimal schedules. Their **ratios** differ, however: the competitive ratio for $\sum C_j$ is always $\le$ the one for $\sum F_j$ (the same positive number is added to numerator and denominator). This project studies $\sum C_j$.

---

## 3. The offline optimum $\mathrm{OPT}$

### 3.1 Definition

$\mathrm{OPT}$ is a **clairvoyant offline** scheduler: it knows the whole instance $I$ in advance (all $r_j, p_j, s_{ij}$), but it must obey **exactly the same physical constraints** as the online algorithm — the same $m$ threads, the same speeds, and no preemption.

$$
\mathrm{OPT}(I) \;=\; \min_{\sigma \text{ feasible}} \; \sum_{j\in\mathcal{J}} C_j(\sigma) .
$$

$\mathrm{OPT}$ may also leave threads idle on purpose to wait for an upcoming short job — this is exactly how it beats online algorithms in the examples of Section 5.

### 3.2 Structure: it suffices to enumerate assignments and orders

**Observation.** Once we fix which jobs go to each thread and the order on each thread, starting every job as early as possible is optimal (shifting a job left never increases any $C_j$).

So if the jobs on thread $i$ run in the order $\pi_i(1), \pi_i(2), \dots, \pi_i(n_i)$, the completion times follow the recursion

$$
C_{\pi_i(0)} := 0, \qquad
C_{\pi_i(k)} \;=\; \max\!\big(C_{\pi_i(k-1)},\; r_{\pi_i(k)}\big) \;+\; \frac{p_{\pi_i(k)}}{s_{i\,\pi_i(k)}} ,
$$

and

$$
\mathrm{OPT}(I) \;=\; \min_{\substack{\text{partitions } \mathcal{J} = J_1 \sqcup \dots \sqcup J_m \\ \text{orders } \pi_i \text{ of each } J_i}} \;\; \sum_{i=1}^{m} \sum_{k=1}^{|J_i|} C_{\pi_i(k)} .
$$

Even for $m=1$, the problem $1 \mid r_j \mid \sum C_j$ is strongly NP-hard, so $\mathrm{OPT}$ can only be computed exactly for small instances. `offline.py` solves it exactly (for $n \lesssim 12$) with a two-level subset DP:

1. for each thread $i$ and subset $S \subseteq \mathcal{J}$, keep the Pareto front of (finish time, sum of completion times) over all orders of $S$;
2. a second DP over (thread, subset) splits the jobs among threads.

For large instances we use a simple lower bound: each job finishes no earlier than if it started at its release time on its fastest thread,

$$
\mathrm{OPT}(I) \;\ge\; \sum_{j} \Big( r_j + \frac{p_j}{\max_i s_{ij}} \Big) .
$$

(Ratios computed against this bound **overestimate** the true ratio, i.e., they are pessimistic.)

---

## 4. Competitive ratio

### 4.1 Definition

For a deterministic online algorithm $\mathrm{ALG}$ on the instance class $\mathcal{I}(\Delta, H, m)$, its **competitive ratio** is

$$
\rho_{\mathrm{ALG}}(\Delta, H, m) \;=\; \sup_{I \in \mathcal{I}(\Delta, H, m)} \; \frac{\mathrm{ALG}(I)}{\mathrm{OPT}(I)} ,
$$

where $\mathcal{I}(\Delta, H, m)$ contains all instances with $p_j \in [p_{\min}, p_{\max}]$ (with $p_{\max}/p_{\min} = \Delta$), speed ratio at most $H$, and exactly $m$ threads; $n$ and the release times are arbitrary. $\mathrm{ALG}$ is **$c$-competitive** if $\mathrm{ALG}(I) \le c \cdot \mathrm{OPT}(I)$ for every such $I$.

For a randomized algorithm (e.g., `RandomIdle`) we use the expectation against an oblivious adversary (one that fixes the instance in advance and cannot see the random bits):

$$
\rho_{\mathrm{ALG}} \;=\; \sup_{I} \; \frac{\mathbb{E}[\mathrm{ALG}(I)]}{\mathrm{OPT}(I)} .
$$

The difficulty of the problem itself is captured by the **best achievable competitive ratio**:

$$
\rho^{*}(\Delta, H, m) \;=\; \inf_{\mathrm{ALG} \text{ online, non-clairvoyant, non-preemptive}} \; \rho_{\mathrm{ALG}}(\Delta, H, m) .
$$

### 4.2 The game view

Think of the competitive ratio as a game: an adversary builds the instance, the algorithm makes decisions, and the adversary tries to make $\mathrm{ALG}/\mathrm{OPT}$ as large as possible. Against a deterministic algorithm the adversary can be **adaptive**: it watches what the algorithm does (e.g., "it just started a job on a thread") and then decides which jobs come next and how large the started job really is. Because the algorithm never sees $p_j$, the adversary may fix $p_j$ "after the fact", as long as it lies in $[p_{\min}, p_{\max}]$.

### 4.3 Speed augmentation

In the resource augmentation framework of Kalyanasundaram and Pruhs, each thread of the online algorithm runs $(1+\varepsilon)$ times faster, while $\mathrm{OPT}$ uses the original speeds:

$$
\rho_{\mathrm{ALG}}^{(1+\varepsilon)} \;=\; \sup_I \frac{\mathrm{ALG}_{(1+\varepsilon)s}(I)}{\mathrm{OPT}_{s}(I)},
\qquad \text{where job } j \text{ on thread } i \text{ takes } \frac{p_j}{(1+\varepsilon)\, s_{ij}} \text{ for the online algorithm.}
$$

One research question is whether this small extra speed brings the competitive ratio down from a quantity depending on $\Delta, H$ to a constant (or a smaller order).

---

## 5. Why the problem is hard: two examples

### 5.1 Time dimension: a long job blocks short jobs (the example from the proposal)

**Setup.** $m = 1$, speed $s = 1$.

- At time $0$: job $0$ arrives with size $L$ ($= p_{\max}$);
- At time $\delta$: jobs $1, \dots, n-1$ arrive, each of size $\delta$ ($= p_{\min}$).

**The online algorithm** — any work-conserving rule that starts a job whenever a job and a thread are available, such as FCFS — sees one job and one idle thread at time $0$. It does not know the job has size $L$, so it starts it. The short jobs must queue behind it:

$$
\mathrm{ALG} \;=\; \underbrace{L}_{\text{long job}} \;+\; \sum_{k=1}^{n-1}\big(L + k\delta\big)
\;=\; nL \;+\; \frac{n(n-1)}{2}\,\delta \;=\; \Omega(nL).
$$

**The offline optimum** knows the short jobs are coming. It idles until $\delta$, runs all short jobs, then the long job:

$$
\mathrm{OPT} \;\le\; \sum_{k=1}^{n-1}(k+1)\delta \;+\; \big(n\delta + L\big)
\;=\; L + O(n^2 \delta).
$$

**Ratio.** Writing $L = \Delta\delta$,

$$
\frac{\mathrm{ALG}}{\mathrm{OPT}} \;\gtrsim\; \frac{nL}{L + \tfrac{1}{2}n^2\delta} \;=\; \frac{n\Delta}{\Delta + \tfrac{1}{2}n^2}.
$$

- If $\Delta$ is unrestricted (take $\Delta \ge n^2$), the ratio is $\Omega(n)$ — unbounded in the number of jobs. This is why we must assume bounded $\Delta$.
- If $\Delta$ is fixed, the adversary picks $n \approx \sqrt{2\Delta}$ to maximize the ratio, giving about $\sqrt{\Delta/2}$. So **on $m=1$, every deterministic rule that starts immediately has competitive ratio $\Omega(\sqrt{\Delta})$.**

**"Then just wait a bit?"** A delayed rule (Section 6) waits at least $\tau$ after a job arrives before starting it. But waiting has a cost: if the instance is a single job of size $p_{\min}$,

$$
\frac{\mathrm{ALG}}{\mathrm{OPT}} \;=\; \frac{\tau + p_{\min}}{p_{\min}} \;=\; 1 + \frac{\tau}{p_{\min}} .
$$

And the adversary can wait too: after the algorithm starts the long job at time $\tau$, it releases the $n-1$ short jobs at $\tau + \delta$ (in the code: `lower_bound_instance(..., offset=tau)`), which shifts the example above. A small $\tau$ does not stop this example, while a large $\tau$ wastes time — **how to choose $\tau$ from $p_{\min}, p_{\max}, H, m$** is one of the central questions of the project.

### 5.2 Speed dimension: the slow-thread trap

**Setup.** $m = 2$, related speeds: thread 1 has speed $1$ (slow), thread 2 has speed $H$ (fast).

- At time $0$: job $A$ arrives with both threads idle; the "fastest idle thread" rule puts it on the fast thread. Its size is $p_A = p_{\min}$, so it finishes at $p_{\min}/H$.
- At time $p_{\min}/H - \varepsilon$: job $B$ arrives with size $p_B = p_{\max}$. Only the slow thread is idle, and the scheduler does not know that $A$ is about to finish on the fast thread.

Any rule that dispatches as soon as a thread is idle puts $B$ on the slow thread, so $C_B \approx p_{\min}/H + p_{\max}$. $\mathrm{OPT}$ waits $\varepsilon$ longer and gives $B$ the fast thread, so $C_B = p_{\min}/H + p_{\max}/H$. Letting $\varepsilon \to 0$:

$$
\frac{\mathrm{ALG}}{\mathrm{OPT}} \;\ge\; \frac{2p_{\min}/H + p_{\max}}{2p_{\min}/H + p_{\max}/H}
\;=\; \frac{2 + H\Delta}{2 + \Delta} \;\xrightarrow{\;\Delta\to\infty\;}\; H .
$$

So speed heterogeneity is a second, independent source of difficulty, captured by $H$. The `SpeedThreshold(alpha)` rule targets exactly this trap: it only starts a job on a thread that is fast enough for it ($s_{ij} \ge \max_k s_{kj}/\alpha$), and otherwise waits.

**Together, the two examples show** that a good rule must balance two separate decisions — whether to wait in time, and whether to wait for speed — while knowing neither the size of the current job nor how long the running jobs still need.

---

## 6. The online rules we study

Every rule sees only: the waiting queue (each job's $r_j$ and $s_{\cdot j}$, sorted by $(r_j, j)$), the set of idle threads, the current time $t$, and the global parameters.

| Rule | Formal description | Work-conserving? |
| --- | --- | --- |
| **FCFS** | oldest waiting job → lowest-numbered idle thread (ignores speeds) | yes |
| **RandomIdle** | oldest waiting job → uniformly random idle thread | yes |
| **OldestFastest** | oldest waiting job $j$ → $\arg\max_{i \text{ idle}} s_{ij}$ | yes |
| **Delayed($\tau$)** | job $j$ becomes *eligible* only once $t \ge r_j + \tau$; the oldest eligible job → its fastest idle thread | no (waits $\tau$ on purpose) |
| **SpeedThreshold($\alpha$)** | oldest job $j$ may only start on an idle thread with $s_{ij} \ge \max_k s_{kj} / \alpha$; otherwise it is skipped | no (waits for a fast thread) |

The delayed rule is the main object of study in the proposal:

$$
S_j \;\ge\; r_j + \tau ,
$$

with candidate thresholds (`TAU_RULES` in the code):

$$
\tau \in \Big\{\, 0,\;\; p_{\min},\;\; \sqrt{p_{\min}\,p_{\max}},\;\; p_{\max},\;\; p_{\max}/H \,\Big\}.
$$

With $\tau = 0$, Delayed reduces to OldestFastest. $\tau = \sqrt{p_{\min}p_{\max}}$ is the intuitive choice that takes the geometric mean between the cost of waiting ($\tau/p_{\min}$) and the cost of being blocked.

---

## 7. Research questions

1. **Lower bounds.** How large must $\rho^{*}(\Delta, H, m)$ be for deterministic online algorithms? Which job sequences force bad ratios, and how does the ratio scale with $\Delta$, $H$, and $m$? (Section 5 gives $\Omega(\sqrt{\Delta})$ for immediate-start rules on $m=1$, and about $H$ in the speed dimension.)
2. **Upper bounds in simple cases.** Analyze FCFS and OldestFastest in turn for $m=1$; identical threads ($s_{ij}=1$); related threads ($s_{ij} = s_i$); and unrelated threads.
3. **Delayed rule.** How should $\tau$ be chosen from the known parameters $(p_{\min}, p_{\max}, H, m)$? Prove an upper bound on the competitive ratio of Delayed($\tau$) and check whether it matches the lower bound.
4. **Speed augmentation.** Does $(1+\varepsilon)$-speed augmentation make the competitive ratio independent of $\Delta$ (or $H$)?
5. **Experiments.** In a simulator that hides job sizes, compare the empirical ratios of the rules against the exact $\mathrm{OPT}$ (small $n$), and check scheduling behavior and resource usage on a real multi-process testbed.

---

## 8. How this differs from previous work

| Work | Their setting | Difference from ours |
| --- | --- | --- |
| Motwani, Phillips, Torng (1994) | non-clairvoyant; Round-Robin is 2-competitive | relies on preemption / time slicing; we forbid preemption |
| Jäger, Sagnol, Schmidt gen. Waldschmidt, Warode (2025) | no constant ratio without pausing | allows kill-and-restart; we do not even allow that, hence the bounded $\Delta$ |
| Gupta, Moseley, Uetz, Xie (2020) | non-preemptive, job size **distributions** known (stochastic scheduling) | we only know the bounds $[p_{\min}, p_{\max}]$ |
| Jäger, Lindermayr, Megow (2025) | Proportional Fairness on heterogeneous machines | allows processing rates to be shared among jobs |
| Lindermayr, Megow, Rapp (2023) | speeds unknown (predictions, or only the speed order known) | we know the exact $s_{ij}$ when a job arrives |
| Kalyanasundaram, Pruhs (2000) | speed augmentation framework | we use it as one of our analysis tools |

---

## 9. Mathematical objects ↔ code

| Mathematical object | Location in code |
| --- | --- |
| job $j$: $(r_j, p_j, s_{\cdot j})$ | `model.Job(id, release, size, speeds)` |
| the job as seen by the scheduler (no $p_j$) | `model.JobView(id, release, speeds)` |
| $p_j / s_{ij}$ | `Job.runtime_on(thread)` |
| instance $I$, with $\Delta$ and $H$ | `model.Instance`, `.delta`, `.H` (computed from the instance's speeds as $\max s / \min s$) |
| known parameters $(m, p_{\min}, p_{\max}, H)$ | `policies.Context` |
| schedule $\sigma = \{(a_j, S_j, C_j)\}$ and the feasibility check | `model.Schedule`, `Schedule.validate()` |
| $\sum_j C_j$ | `Schedule.total_completion` |
| an online rule | `policies.Policy.decide(now, waiting, idle)`; rules with timers also implement `next_wakeup` |
| online execution (discrete-event; $p_j$ is used only to decide when a job finishes) | `simulator.simulate(instance, policy, speedup=1+ε)` |
| $\mathrm{OPT}$ (exact, $n \lesssim 12$) / lower bound | `offline.offline_opt`, `offline.opt_lower_bound` |
| the Section 5.1 example (including the shifted version with offset $=\tau$) | `model.lower_bound_instance(n, L, delta_t, m, offset)` |
| speed models $P/Q/R$ | `model.make_speeds(..., model="identical"/"related"/"unrelated")` |
| size distributions | `model.make_sizes`: `uniform`, `loguniform`, `bimodal` (85% of jobs have size $p_{\min}$, 15% have $p_{\max}$) |
| arrival process | Poisson arrivals, default load about 80%: $\lambda = 0.8\, m \,/\, \overline{p_j/s_{ij}}$ |
| empirical competitive ratio | `experiments.py`: mean and max of $\mathrm{ALG}/\mathrm{OPT}$ for each scenario and rule |
| real multi-process execution | `executor.py`: one OS process per thread; speed $s_{ij}$ is emulated with a CPU duty cycle of $s_{ij}/s_{\max}$ |

**An implementation note:** in the theory, $H$ is an *upper bound* the scheduler knows in advance. In the code, `Instance.H` is computed from the instance's actual speeds as $\max_{i,j}s_{ij}/\min_{i,j}s_{ij}$ and passed to the rules through `Context`. For rules that depend on $H$, such as Delayed($p_{\max}/H$), this hands the scheduler the tightest possible $H$. Likewise, $p_{\min}$ and $p_{\max}$ are the bounds given to the instance generator, not the smallest and largest sizes that actually occur.
