"""Offline optimum (clairvoyant, non-preemptive, same threads) for small inputs.

For a fixed assignment of jobs to threads and a fixed order on each thread,
starting every job as early as possible is optimal. So:

1. For each thread i and job subset S, a DP over subsets keeps the Pareto
   front of (finish time, sum of completion times) over all orders of S.
   Both coordinates are monotone, so dominated prefixes can be dropped.
2. A second DP over (thread, subset) splits the jobs among threads.

Cost is O(m * 3^n + m * 2^n * n * front), which is fine up to n ~ 12.
"""

from __future__ import annotations

import heapq

from .model import Assignment, Instance, Schedule

# Pareto entry: (finish, total, job, parent_entry)
Entry = tuple


def _insert(front: list[Entry], cand: Entry) -> None:
    for e in front:
        if e[0] <= cand[0] and e[1] <= cand[1]:
            return
    front[:] = [e for e in front if not (cand[0] <= e[0] and cand[1] <= e[1])]
    front.append(cand)


def _single_thread_fronts(instance: Instance, thread: int) -> list[Entry | None]:
    n = instance.n
    jobs = instance.jobs
    fronts: list[list[Entry]] = [[] for _ in range(1 << n)]
    fronts[0] = [(0.0, 0.0, -1, None)]
    for mask in range(1 << n):
        front = fronts[mask]
        if not front:
            continue
        for j in range(n):
            if mask >> j & 1:
                continue
            job = jobs[j]
            rt = job.runtime_on(thread)
            target = fronts[mask | 1 << j]
            for e in front:
                c = max(e[0], job.release) + rt
                _insert(target, (c, e[1] + c, j, e))
    return [min(f, key=lambda e: e[1]) if f else None for f in fronts]


def offline_opt(instance: Instance, max_n: int = 12) -> Schedule:
    n, m = instance.n, instance.m
    if n > max_n:
        raise ValueError(f"offline_opt is exponential; n={n} exceeds max_n={max_n}")
    best = [_single_thread_fronts(instance, i) for i in range(m)]
    full = (1 << n) - 1
    inf = float("inf")

    # g[i][S]: best cost scheduling S on threads 0..i; choice[i][S]: subset given to thread i.
    g = [[inf] * (1 << n) for _ in range(m)]
    choice = [[0] * (1 << n) for _ in range(m)]
    for S in range(1 << n):
        g[0][S] = best[0][S][1]
        choice[0][S] = S
    for i in range(1, m):
        for S in range(1 << n):
            sub = S
            while True:
                cost = g[i - 1][S ^ sub] + best[i][sub][1]
                if cost < g[i][S]:
                    g[i][S], choice[i][S] = cost, sub
                if sub == 0:
                    break
                sub = (sub - 1) & S

    assignments: dict[int, Assignment] = {}
    S = full
    for i in range(m - 1, -1, -1):
        sub = choice[i][S]
        e = best[i][sub]
        while e is not None and e[2] >= 0:
            job = instance.jobs[e[2]]
            assignments[job.id] = Assignment(job.id, i, e[0] - job.runtime_on(i), e[0])
            e = e[3]
        S ^= sub
    return Schedule(instance, assignments, "OPT")


def srpt_lower_bound(instance: Instance) -> float | None:
    """Lower bound on Opt for identical workers: preemptive SRPT on one machine of speed m.

    One machine that is m times faster can time-share any schedule of the m workers without
    delaying a completion, and SRPT minimizes sum C_j on a single machine with preemption.
    Returns None when the workers are not identical.
    """
    speeds = {s for j in instance.jobs for s in j.speeds}
    if len(speeds) != 1:
        return None
    rate = instance.m * speeds.pop()
    jobs = sorted(instance.jobs, key=lambda j: j.release)
    heap: list[float] = []  # remaining work
    now, total, k = 0.0, 0.0, 0
    while k < len(jobs) or heap:
        if not heap:
            now = max(now, jobs[k].release)
        while k < len(jobs) and jobs[k].release <= now:
            heapq.heappush(heap, jobs[k].size)
            k += 1
        rem = heapq.heappop(heap)
        finish = now + rem / rate
        if k < len(jobs) and jobs[k].release < finish:
            heapq.heappush(heap, rem - (jobs[k].release - now) * rate)
            now = jobs[k].release
        else:
            now = finish
            total += now
    return total


def opt_lower_bound(instance: Instance) -> float:
    """Lower bound on Opt for large instances: the larger of
    (a) sum of r_j + p_j / max_i s_ij (no job finishes earlier), and
    (b) `srpt_lower_bound` when the workers are identical.
    """
    trivial = sum(j.release + j.size / max(j.speeds) for j in instance.jobs)
    srpt = srpt_lower_bound(instance)
    return trivial if srpt is None else max(trivial, srpt)
