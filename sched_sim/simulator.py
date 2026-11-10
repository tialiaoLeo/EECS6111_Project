"""Exact discrete-event simulator of the cluster.

Job sizes are hidden from the policy: the simulator alone uses them to decide
when a running job finishes.
"""

from __future__ import annotations

import heapq

from .model import Assignment, Instance, JobView, Schedule
from .policies import EPS, Context, Policy


def context_for(instance: Instance) -> Context:
    return Context(m=instance.m, p_min=instance.p_min, p_max=instance.p_max, H=instance.H)


def simulate(instance: Instance, policy: Policy, seed: int | None = None, speedup: float = 1.0) -> Schedule:
    """Run `policy` on `instance`. `speedup` > 1 models (1+eps)-speed augmentation."""
    policy.reset(context_for(instance), seed)
    jobs = {j.id: j for j in instance.jobs}
    arrivals = sorted(instance.jobs, key=lambda j: (j.release, j.id))
    next_arrival = 0
    waiting: dict[int, JobView] = {}
    idle = set(range(instance.m))
    running: list[tuple[float, int, int]] = []  # (end, thread, job)
    done: dict[int, Assignment] = {}

    t = arrivals[0].release if arrivals else 0.0
    while len(done) < len(jobs):
        while next_arrival < len(arrivals) and arrivals[next_arrival].release <= t + EPS:
            j = arrivals[next_arrival]
            waiting[j.id] = JobView(j.id, j.release, j.speeds)
            next_arrival += 1
        while running and running[0][0] <= t + EPS:
            _, thread, _ = heapq.heappop(running)
            idle.add(thread)

        queue = sorted(waiting.values(), key=lambda v: (v.release, v.id))
        for job_id, thread in policy.decide(t, queue, sorted(idle)):
            if job_id not in waiting or thread not in idle:
                raise RuntimeError(f"{policy.name} made an invalid decision ({job_id}, {thread}) at t={t}")
            del waiting[job_id]
            idle.discard(thread)
            end = t + jobs[job_id].runtime_on(thread) / speedup
            done[job_id] = Assignment(job_id, thread, t, end)
            heapq.heappush(running, (end, thread, job_id))

        candidates = []
        if next_arrival < len(arrivals):
            candidates.append(arrivals[next_arrival].release)
        if running:
            candidates.append(running[0][0])
        wake = policy.next_wakeup(t, sorted(waiting.values(), key=lambda v: (v.release, v.id)))
        if wake is not None and wake > t + EPS:
            candidates.append(wake)
        if not candidates:
            if len(done) < len(jobs):
                raise RuntimeError(f"{policy.name} deadlocked at t={t} with {len(waiting)} waiting jobs")
            break
        t = max(t, min(candidates))

    return Schedule(instance, done, policy.name)
