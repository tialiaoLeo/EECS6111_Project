"""Run a policy on real OS worker processes and measure what happens.

Each model thread i is a separate worker process (so the GIL is not a
factor). The dispatcher in the parent process plays the online scheduler:
it releases jobs at wall-clock time r_j * time_scale, asks the policy for
decisions (the policy never sees sizes), and sends jobs to idle workers.

Thread speed s_ij is emulated by duty-cycling: within every slice the worker
burns CPU for a fraction s_ij / s_max and sleeps for the rest, so a slow
thread really does use less CPU per wall-clock second.

Workloads:
  duty    - stop when the wall-clock target p_j / s_ij * time_scale is reached
            (runtimes match the model closely).
  compute - perform p_j * calibrated hash iterations at the duty-cycled rate
            (runtimes drift with real CPU contention, like a real cluster).
"""

from __future__ import annotations

import hashlib
import multiprocessing as mp
import os
import queue
import time
from dataclasses import dataclass, field

from .model import Instance, JobView
from .monitor import ResourceMonitor
from .policies import EPS, Policy
from .simulator import context_for

SLICE = 0.01  # seconds per duty cycle


def _spin_hash(n_iter: int, seed: bytes = b"x") -> bytes:
    h = seed
    for _ in range(n_iter):
        h = hashlib.sha256(h).digest()
    return h


def calibrate_hash_rate(duration: float = 0.2) -> float:
    """Hash iterations per second on one core at full speed."""
    n, t0 = 0, time.perf_counter()
    while time.perf_counter() - t0 < duration:
        _spin_hash(1000)
        n += 1000
    return n / (time.perf_counter() - t0)


def _run_duty(target_s: float, frac: float) -> None:
    end = time.perf_counter() + target_s
    while True:
        now = time.perf_counter()
        if now >= end:
            return
        busy_until = min(now + SLICE * frac, end)
        while time.perf_counter() < busy_until:
            _spin_hash(50)
        rest = min(SLICE * (1 - frac), end - time.perf_counter())
        if rest > 0:
            time.sleep(rest)


def _run_compute(n_iter: int, frac: float) -> None:
    chunk = 2000
    done = 0
    while done < n_iter:
        k = min(chunk, n_iter - done)
        t = time.perf_counter()
        _spin_hash(k)
        done += k
        if frac < 1.0:
            time.sleep((time.perf_counter() - t) * (1 / frac - 1))


def _worker_main(thread_id: int, tasks: mp.Queue, results: mp.Queue, cpu: int | None) -> None:
    if cpu is not None and hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {cpu})
    results.put(("ready", thread_id, os.getpid()))
    while True:
        task = tasks.get()
        if task is None:
            return
        job_id, kind, amount, frac = task
        t_start, c_start = time.perf_counter(), time.process_time()
        if kind == "duty":
            _run_duty(amount, frac)
        else:
            _run_compute(int(amount), frac)
        results.put(("done", thread_id, job_id, t_start, time.perf_counter(), time.process_time() - c_start))


@dataclass
class JobRecord:
    job: int
    thread: int
    release: float  # model time units
    dispatch: float
    start: float
    end: float
    planned_runtime: float
    measured_runtime: float
    cpu_seconds: float

    @property
    def wait(self) -> float:
        return self.start - self.release


@dataclass
class ExecutionResult:
    instance: Instance
    policy: str
    records: dict[int, JobRecord]
    time_scale: float
    wall_seconds: float
    monitor: ResourceMonitor
    worker_pids: dict[int, int] = field(default_factory=dict)
    t0_offset: float = 0.0  # seconds from monitor start to dispatcher t=0

    @property
    def total_completion(self) -> float:
        return sum(r.end for r in self.records.values())


def execute(
    instance: Instance,
    policy: Policy,
    *,
    time_scale: float = 0.05,
    workload: str = "duty",
    monitor_interval: float = 0.05,
    pin: bool = False,
    seed: int | None = None,
) -> ExecutionResult:
    """Run `policy` on `instance` using `instance.m` real worker processes.

    `time_scale` is wall-clock seconds per model time unit.
    """
    if workload not in ("duty", "compute"):
        raise ValueError("workload must be 'duty' or 'compute'")
    policy.reset(context_for(instance), seed)
    s_max = max(s for j in instance.jobs for s in j.speeds)
    hash_rate = calibrate_hash_rate() if workload == "compute" else 0.0

    ctx = mp.get_context("fork" if hasattr(os, "fork") else "spawn")
    results: mp.Queue = ctx.Queue()
    task_qs = [ctx.Queue() for _ in range(instance.m)]
    ncpu = os.cpu_count() or 1
    workers = [
        ctx.Process(
            target=_worker_main,
            args=(i, task_qs[i], results, (i % ncpu) if pin else None),
            name=f"worker-{i}",
            daemon=True,
        )
        for i in range(instance.m)
    ]
    for w in workers:
        w.start()
    pids = {}
    while len(pids) < instance.m:
        _, tid, pid = results.get(timeout=30)
        pids[tid] = pid

    monitor = ResourceMonitor(interval=monitor_interval, track_children=False)
    for tid, pid in pids.items():
        monitor.register(pid, f"T{tid}")
    monitor.register(os.getpid(), "dispatcher")
    monitor.start()
    time.sleep(2 * monitor_interval)  # baseline samples before any work

    jobs = {j.id: j for j in instance.jobs}
    arrivals = sorted(instance.jobs, key=lambda j: (j.release, j.id))
    next_arrival = 0
    waiting: dict[int, JobView] = {}
    idle = set(range(instance.m))
    dispatched: dict[int, tuple[int, float]] = {}
    records: dict[int, JobRecord] = {}

    t0 = time.perf_counter()
    model_now = lambda: (time.perf_counter() - t0) / time_scale  # noqa: E731

    try:
        while len(records) < len(jobs):
            now = model_now()
            while next_arrival < len(arrivals) and arrivals[next_arrival].release <= now + EPS:
                j = arrivals[next_arrival]
                waiting[j.id] = JobView(j.id, j.release, j.speeds)
                next_arrival += 1

            queue_view = sorted(waiting.values(), key=lambda v: (v.release, v.id))
            for job_id, thread in policy.decide(now, queue_view, sorted(idle)):
                if job_id not in waiting or thread not in idle:
                    raise RuntimeError(f"{policy.name} made an invalid decision ({job_id}, {thread})")
                del waiting[job_id]
                idle.discard(thread)
                job = jobs[job_id]
                frac = job.speeds[thread] / s_max
                if workload == "duty":
                    amount = job.runtime_on(thread) * time_scale
                else:
                    # n iterations at duty fraction s_ij/s_max take n / hash_rate * s_max / s_ij seconds.
                    amount = job.size / s_max * time_scale * hash_rate
                task_qs[thread].put((job_id, workload, amount, frac))
                dispatched[job_id] = (thread, now)

            deadlines = []
            if next_arrival < len(arrivals):
                deadlines.append(arrivals[next_arrival].release)
            wake = policy.next_wakeup(now, sorted(waiting.values(), key=lambda v: (v.release, v.id)))
            if wake is not None:
                deadlines.append(wake)
            timeout = None
            if deadlines:
                timeout = max(0.0, (min(deadlines) - model_now()) * time_scale)
            elif not dispatched.keys() - records.keys():
                raise RuntimeError(f"{policy.name} deadlocked with {len(waiting)} waiting jobs")

            try:
                msg = results.get(timeout=timeout)
            except queue.Empty:
                continue
            while True:
                _, thread, job_id, ts, te, cpu = msg
                job = jobs[job_id]
                records[job_id] = JobRecord(
                    job=job_id,
                    thread=thread,
                    release=job.release,
                    dispatch=dispatched[job_id][1],
                    start=(ts - t0) / time_scale,
                    end=(te - t0) / time_scale,
                    planned_runtime=job.runtime_on(thread),
                    measured_runtime=(te - ts) / time_scale,
                    cpu_seconds=cpu,
                )
                idle.add(thread)
                try:
                    msg = results.get_nowait()
                except queue.Empty:
                    break
        wall = time.perf_counter() - t0
        time.sleep(2 * monitor_interval)
    finally:
        monitor.stop()
        for q in task_qs:
            q.put(None)
        for w in workers:
            w.join(timeout=5)
            if w.is_alive():
                w.terminate()

    return ExecutionResult(
        instance=instance,
        policy=policy.name,
        records=records,
        time_scale=time_scale,
        wall_seconds=wall,
        monitor=monitor,
        worker_pids=pids,
        t0_offset=t0 - monitor.t0_perf,
    )
