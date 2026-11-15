# Scoping Findings (2026-11-14)

Background notes behind [../problem_definition.md](../problem_definition.md): why the scope was
narrowed, and what a literature and feasibility check turned up.

> **Update 2026-11-15.** The definition is now v3: HPC batch jobs with declared time limits $u_j$, with
> $u_j/\lambda \le p_j \le u_j$. Sections 1–2b below analyze v2 (one global range, $\Delta = \lambda$),
> which is the special case of v3 in which all $u_j$ are equal. They explain why v2 was too symmetric
> (§2b: every work-conserving rule has the same worst case, and waiting gains at most a constant).
> v3 restores per-job information, so ordering and waiting matter again.

> **Status of these notes.** Everything below comes from AI research agents. The math was derived by
> one agent and then re-checked by a second agent, independently and numerically (brute-force exact OPT
> on thousands of small random instances). None of it has been peer reviewed, and none of it has been
> checked by us yet. Treat every claim as **to be verified** before it goes into the report. Several
> classic citations were only confirmed from secondary sources (marked below).

Units: $p_{\min} = 1$, $p_{\max} = \Delta$. "Deterministic ratio" means the best competitive ratio of a
deterministic online non-clairvoyant non-preemptive algorithm for $\sum C_j$.

---

## 1. Why the core is $m$ identical workers rather than $m = 1$

The proposal's first step was a single machine. The check suggests that the deterministic single-machine
case has a short, complete answer, so it is better used as a warm-up than as the main question.

**Claim 1 (single machine, lower bound).** Every deterministic algorithm has ratio at least
$\sqrt{\Delta}$ (as a supremum over $n$).
*Argument:* release $N$ jobs at time $0$. They look identical, so the adversary gives size $\Delta$ to
the first $a$ jobs the algorithm starts and size $1$ to the rest. The algorithm pays at least the
longest-first order; OPT pays shortest-first. With $a/N \to 1/(1+\sqrt{\Delta})$ the ratio tends to
$\sqrt{\Delta}$. Idling only adds cost.

**Claim 2 (single machine, upper bound).** Every rule that never idles while a job waits (FCFS, or any
order) has ratio at most $\sqrt{\Delta}$.
*Argument:* split the schedule into busy periods. All jobs of a busy period starting at $b$ have
$r_j \ge b$, so $\mathrm{ALG}_B = |B|\,b + L_B$ (cost of the order used) while
$\mathrm{OPT}_B \ge |B|\,b + \mathrm{SPT}(B)$, even with preemption. For any order,
$L_B / \mathrm{SPT}(B) \le \sqrt{\Delta}$ by the batch bound.

**Consequence.** On one machine the deterministic ratio is exactly $\sqrt{\Delta}$ and FCFS attains
it. Waiting never helps in the worst case. For $\Delta \ge 4$ the delayed rule has ratio exactly
$\max(\sqrt{\Delta},\, 1+\tau)$. So the proposal's motivating instance (one long job, then many short
ones) only costs FCFS about $\sqrt{\Delta/2}$ once $\Delta$ is bounded; the batch instance is the real
worst case.

**Related literature.** The batch bound for non-preemptive lists matches Prop. 2.4 of L. Bridges,
*Single-machine scheduling with interval predictions and costly preemption*, arXiv:2609.15492 (Sept 2026,
unreviewed preprint, no release dates). No paper was found that states Claims 1–2 with release dates.

---

## 2. What is open for $m$ identical workers (the chosen core)

No published result was found for non-clairvoyant non-preemptive $\sum C_j$ with bounded $\Delta$ on
$m \ge 2$ machines.

**Claim 3 (lower bound, every $m$).** Every deterministic algorithm, including ones that idle, has
ratio at least $\sup_k \frac{k\Delta}{k^2/2 + k/2 + \Delta} = \sqrt{\Delta/2}\,(1 - O(\Delta^{-1/2}))$,
independent of $m$.
*Argument:* release $n = mk$ jobs at time $0$; the first job started on each machine gets size
$\Delta$ and every later job size $1$. Then every job has $C_j \ge \Delta$, so $\mathrm{ALG} \ge n\Delta$,
while OPT puts each machine's long job last.
*Note:* "$m$ copies of the single-machine gadget" does **not** work, because the algorithm can hedge by
holding one job back.

**Claim 4 (upper bound, every $m$).** FCFS has ratio at most $\Delta$ on $m$ identical machines.
(Proof by monotonicity, optimality of greedy for equal sizes, and time scaling; checked by the
verifier.)

**Open (the natural main question).** *(Superseded by §2b below, 2026-11-15.)*
- Is FCFS $O(\sqrt{\Delta})$ on $m$ machines? Searches up to $\Delta = 36$ found no counterexample, but
  there is no proof. The busy-period argument of Claim 2 breaks for $m \ge 2$, because a job can start on
  a free machine while the others are busy.
- Can deliberate waiting help once $m \ge 2$?
- Randomized algorithms. In the batch case the ratio is $(1+\sqrt{\Delta})/2$ (Yao lower bound, met by
  random order), so the open gap is about $[(1+\sqrt{\Delta})/2,\ \sqrt{\Delta}]$, already for $m = 1$
  with release dates. Matching the lower bound seems to require a *randomized delay*.

---

## 2b. Work-conserving ("start immediately") rules — added 2026-11-15

Prompted by the question "real clusters don't wait; should the model force immediate start?". Same
status as above: one agent derived each claim and a second agent tried to refute it. No mathematical
error was found, but nothing has been checked by us.

A rule is **work-conserving (WC)** if, whenever a worker is idle and a job is waiting, it starts some
waiting job. On identical workers its only freedom is *which* waiting job to start.

**Claim 8 (order invariance).** For every $m$, $\Delta$ and $n$, every deterministic WC rule (FCFS,
LCFS, or any rule using the revealed history) has exactly the same worst-case ratio as FCFS.
*Idea:* (A) given rule $X$ on instance $I$, move release times earlier, to the suffix minimum along $X$'s
start order. FCFS then reproduces $X$'s schedule, and OPT can only get smaller. (B) Conversely, set the
release times inside each "queue period" of FCFS to the period start; an adaptive adversary then forces
any WC rule into FCFS's busy pattern.
Checked on 1200 small instances with exact OPT: no failure.

**Claim 9 (lower bound, improves Claim 3).** Every deterministic algorithm, including ones that idle,
has ratio at least $\sqrt{\Delta}$ for every $m$ (as a supremum).
*Idea:* a batch at time $0$. The adversary makes the first $Lm$ jobs started, counted *globally* in time
order, long and the rest short; then $\mathrm{ALG} \ge m\cdot\mathrm{LPT}$ while
$\mathrm{OPT} = m\cdot\mathrm{SPT}$, and the ratio tends to $\sqrt{\Delta}$ as (short jobs)/(long jobs)
$\to \sqrt{\Delta}$.

**Claim 10 (upper bound for every WC rule).** For $\Delta \ge 4$,
$$
\mathrm{ALG} \le \big(1 + \sqrt{2(1 - 1/m)}\big)\sqrt{\Delta}\cdot\mathrm{OPT} \;<\; 2.415\,\sqrt{\Delta}\cdot\mathrm{OPT}.
$$
*Idea:* split time into maximal intervals in which all $m$ workers are busy. Within one interval, the
order costs at most $\sqrt{\Delta}$ times SPT (the single-machine batch bound), combined with the
Eastman–Even–Isaacs lower bound for $m$ machines. The extra term pays for the at most $m-1$ jobs that
are already running when the interval starts. This "carry-in" is exactly where the $m=1$ proof breaks,
and it costs the $\sqrt{2(1-1/m)}$.

**Consequences.**
- $\sqrt{\Delta} \le \rho^*(\Delta, m) \le \rho_{\mathrm{WC}}(\Delta, m) \le 2.415\sqrt{\Delta}$. On identical
  workers, deliberate waiting can improve the worst case by at most a constant factor
  ($\le 2$ for $m=2$, $< 2.415$ in general). "Clusters start immediately" is justified by a theorem, not
  just assumed.
- If the model *forced* immediate start, Claim 8 would leave only one algorithm (FCFS, up to worst
  case), and the remaining question would be a constant between $\sqrt{\Delta}$ and $2.415\sqrt{\Delta}$.
- Benchmark: OPT must stay the unrestricted optimum (which may idle). A WC-restricted OPT would hide the
  cost of not waiting: the "burst" instance would have ratio 1 instead of about $\sqrt{\Delta/2}$.

**Still open:** whether $\rho_{\mathrm{WC}}(\Delta, m) = \sqrt{\Delta}$ exactly for $m \ge 2$ (no
counterexample in small searches); randomized algorithms; heterogeneous speeds, where WC rules fall
into the slow-worker trap (§3).

**Industry check (sourced, reviewed).** For one anonymous stream of single-node jobs on identical,
always-available workers, documented dispatchers start a waiting job whenever a worker is free, apart
from scheduler latency: Slurm's main loop and backfill (a width-1 head job always fits), kube-scheduler,
YARN with a single queue, Celery with late binding. Deliberate idling does exist in production, but
every documented case relies on something the model leaves out:
- multi-node jobs (backfill reservations);
- data locality (Spark delay scheduling);
- maintenance reservations (machines leaving service);
- per-user or per-tenant limits;
- small dedicated short-job pools, about 1–3% of nodes, where shortness is *declared* through an enforced
  walltime: LLNL Dane `pdebug` (40 of 1500 nodes, 1 h limit), ALCF Polaris debug, Moab's "shortpool"
  standing reservation, older NERSC debug nodes.

## 3. Optional extension: two related workers (speeds $1$ and $H$)

**Claim 5 (slow-worker trap).** Any work-conserving rule that starts job A (size $1$) on the fast
worker at time $0$, then puts job B (size $\Delta$, arriving at $1/H - \varepsilon$) on the idle slow
worker, has ratio $\frac{2 + H\Delta}{2 + \Delta} - O(\varepsilon) \to H$. Valid for $H > 1$ and
$\varepsilon < 1 - 1/H$.

**Claim 6.** Running a scale-invariant single-machine rule only on the fast worker gives ratio at most
$(2 + 1/H)\,\rho_1(\Delta) \le 3\rho_1(\Delta)$.

**Claim 7.** Every deterministic algorithm on two related workers has ratio at least
$\sqrt{\Delta/6}\,(1 - o(1))$, for every $H$.

**Consequence.** For $m = 2$, $\sqrt{\Delta/6} \lesssim \rho^*(H, \Delta) \le 3\rho_1^*(\Delta)$. So $H$
changes the optimal ratio by at most a constant factor, while naive work-conserving rules pay an extra
factor of about $H$. (The verifier corrected an earlier "never using the slow worker costs only
$1 + 1/H$"; that is **not** shown.)

---

## 4. Problem with the global $H$ of the general model

With $H = \max_{i,j} s_{ij} / \min_{i,j} s_{ij}$, jobs whose speeds are equal on every thread but
differ across jobs (e.g. $(1,1)$ and $(H,H)$) give $H > 1$ on identical threads. Speed-oblivious FCFS
then has ratio about $\sqrt{H\Delta/2}$. Fix: per-job $H_j = \max_i s_{ij}/\min_i s_{ij}$ and
$H = \max_j H_j$ (equal to $s_{\max}/s_{\min}$ in the related model), with any job-scale spread kept as
a separate known parameter.

---

## 5. Literature map

✓ = claim checked against the source text or abstract; ~ = only via secondary sources.

**Clairvoyant single machine (sizes known), $1 \mid r_j \mid \sum C_j$ online:**
- Hoogeveen & Vestjens, *Optimal on-line algorithms for single-machine scheduling*, IPCO 1996:
  delayed SPT is 2-competitive, which is best possible deterministic (~, abstract level). The lower bound
  needs tiny jobs, i.e. $\Delta \to \infty$.
- Phillips, Stein & Wein, Math. Programming 82 (1998): ratio 2 online (~).
- Lu, Sitters & Stougie, Oper. Res. Lett. 31 (2003): a class of 2-competitive delayed rules (✓).
- Chekuri, Motwani, Natarajan & Stein, SIAM J. Comput. 31 (2001): randomized $e/(e-1)$ (✓);
  Stougie & Vestjens, Oper. Res. Lett. 30 (2002): matching randomized lower bound (✓).
- Goemans, Queyranne, Schulz, Skutella & Wang, SIAM J. Discrete Math. 15 (2002): survey of the above (✓).
- Tao, Chao & Xi, J. Ind. Manag. Optim. 6(2) (2010): with known bound $\gamma = p_{\max}/p_{\min}$,
  ratio $1 + \frac{\gamma - 1}{1 + \sqrt{1 + \gamma(\gamma - 1)}} < 2$ (✓ abstract; the release-date /
  clairvoyant setting is inferred). This is the clairvoyant counterpart of our problem: about $2$ vs.
  $\sqrt{\Delta}$ is the "price of not knowing sizes".

**Non-clairvoyant / neighbouring models:**
- Motwani, Phillips & Torng, TCS 130 (1994): flow-time version on one machine is $\Theta(\Delta)$ for
  run-to-completion (~; theorem numbers not rechecked).
- Jäger, Sagnol, Schmidt genannt Waldschmidt & Warode, Math. Programming (2025): kill-and-restart.
- Jäger, Lindermayr & Megow, SODA 2025: Thm 6, $\Omega(\sqrt{n})$ for non-migratory non-clairvoyant on
  related machines (unbounded $\Delta$, $n$ machines).
- Dürr, Erlebach, Megow & Meißner, *An adversarial model for scheduling with testing*, Algorithmica
  (2020): different information model (testing).
- Geng, Sun, Yang & Zhang, arXiv:2511.03485: non-preemptive online **flow time**, bounds in $n$ and $m$,
  not $\Delta$ (✓ abstract).
- Chen, Ye & Zhou, arXiv:2508.14544: LLM scheduling with output length in an interval $[l, u]$, all jobs
  at time $0$, batching and cancellation. This is the closest formal cousin, from the industry side.
- Kellerer, Tautenhahn & Woeginger, SIAM J. Comput. 28(4) (1999): offline non-preemptive total flow time
  is hard to approximate, which is a reason to keep $\sum C_j$ rather than flow time.

**Citation corrections found by the verifier:**
- Tao et al., IPL 110 (2010) 325–330: the author order is J. Tao, Z. Chao, Ye Tao, Y. Xi, and the paper
  is about *weighted* completion time.
- The learning-augmented paper from NeurIPS 2018 is Purohit, Svitkina & Kumar, *Improving online
  algorithms via ML predictions*. "arXiv:2407.17712" is not its identifier.

---

## 6. Industry mapping (summary)

Ten candidate systems were checked, each reviewed adversarially. Scores are after review, out of 5:

| System | Score | Verdict |
| --- | --- | --- |
| HPC batch partition (Slurm), single-node jobs | 3.5 | **main story**: unknown runtimes under an enforced time limit, no preemption by default, public traces |
| Capped serverless pool (AWS Lambda) | 3.5 | good second example; needs a custom dispatcher |
| Render farm (Deadline) | 3.5 | literal min/max task time, but timeouts requeue and sizes are learnable within a job |
| CI runners (GitHub Actions) | 2.5 | elastic pools, predictable durations, makespan objective |
| LLM serving (vLLM), heterogeneous GPU routing | 2 | batching and preemption; motivation only |
| Bazel test timeout classes | 2 | only the upper limits are real |
| GPU kernels, P/E-core CPUs, Spark | 1–1.5 | preemptive, or sizes predictable, or no bounds |

Caveats for the write-up:
- $p_{\min}$ has no physical meaning in HPC; it is "the shortest job we care about".
- Real schedulers use per-job limits rather than one global $p_{\max}$.
- No real system gives the scheduler per-job speeds; the two-speed extension is a stylized version of a
  mixed-generation partition.

Detailed raw outputs (with all URLs) are in the session scratchpad, not in the repo.
