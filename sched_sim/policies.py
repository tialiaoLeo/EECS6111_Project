"""Online non-clairvoyant, non-preemptive scheduling policies.

A policy only ever sees `JobView`s (release time and speeds, never the size).
The same policy objects drive both the discrete-event simulator and the real
multi-process executor.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .model import JobView

EPS = 1e-9


@dataclass
class Context:
    """Parameters the scheduler is allowed to know in advance."""

    m: int
    p_min: float
    p_max: float
    H: float

    @property
    def delta(self) -> float:
        return self.p_max / self.p_min


class Policy:
    name = "policy"

    def reset(self, ctx: Context, seed: int | None = None) -> None:
        self.ctx = ctx
        self.rng = np.random.default_rng(seed)

    def decide(self, now: float, waiting: list[JobView], idle: list[int]) -> list[tuple[int, int]]:
        """Return (job_id, thread) pairs to start now.

        `waiting` is sorted by (release, id); `idle` lists idle thread ids.
        """
        raise NotImplementedError

    def next_wakeup(self, now: float, waiting: list[JobView]) -> float | None:
        """Earliest future time the policy wants to be called even without an event."""
        return None

    def __repr__(self) -> str:
        return self.name


def _fastest(job: JobView, threads: list[int]) -> int:
    return max(threads, key=lambda i: (job.speeds[i], -i))


class FCFS(Policy):
    """Oldest waiting job goes to the lowest-numbered idle thread (speed-oblivious)."""

    name = "FCFS"

    def decide(self, now, waiting, idle):
        return [(job.id, thread) for job, thread in zip(waiting, sorted(idle))]


class RandomIdle(Policy):
    """Oldest waiting job goes to a uniformly random idle thread."""

    name = "RandomIdle"

    def decide(self, now, waiting, idle):
        threads = list(idle)
        self.rng.shuffle(threads)
        return [(job.id, thread) for job, thread in zip(waiting, threads)]


class OldestFastest(Policy):
    """Oldest waiting job goes to the idle thread that is fastest for it."""

    name = "OldestFastest"

    def decide(self, now, waiting, idle):
        free = list(idle)
        out = []
        for job in waiting:
            if not free:
                break
            thread = _fastest(job, free)
            free.remove(thread)
            out.append((job.id, thread))
        return out


class Delayed(Policy):
    """Delayed rule: job j is eligible only once now >= r_j + tau.

    The eligible job that has waited longest runs on the fastest idle thread.
    `tau` may be a number or a callable of the Context.
    """

    def __init__(self, tau: float | str = "p_min", label: str | None = None):
        self.tau_spec = tau
        self.label = label

    @property
    def name(self) -> str:
        return self.label or f"Delayed(tau={self.tau_spec})"

    def reset(self, ctx, seed=None):
        super().reset(ctx, seed)
        self.tau = resolve_tau(self.tau_spec, ctx)

    def decide(self, now, waiting, idle):
        eligible = [j for j in waiting if j.release + self.tau <= now + EPS]
        return OldestFastest.decide(self, now, eligible, idle)

    def next_wakeup(self, now, waiting):
        future = [j.release + self.tau for j in waiting if j.release + self.tau > now + EPS]
        return min(future) if future else None


class SpeedThreshold(Policy):
    """Oldest-first, but job j only starts on thread i if s_ij >= max_k s_kj / alpha.

    Waits for a fast-enough thread instead of committing to a slow one.
    """

    def __init__(self, alpha: float = 2.0):
        self.alpha = alpha

    @property
    def name(self) -> str:
        return f"SpeedThreshold(alpha={self.alpha})"

    def decide(self, now, waiting, idle):
        free = list(idle)
        out = []
        for job in waiting:
            if not free:
                break
            best = max(job.speeds)
            ok = [i for i in free if job.speeds[i] * self.alpha >= best - EPS]
            if ok:
                thread = _fastest(job, ok)
                free.remove(thread)
                out.append((job.id, thread))
        return out


TAU_RULES = {
    "0": lambda c: 0.0,
    "p_min": lambda c: c.p_min,
    "p_max": lambda c: c.p_max,
    "sqrt": lambda c: math.sqrt(c.p_min * c.p_max),
    "p_max/H": lambda c: c.p_max / c.H,
}


def resolve_tau(spec: float | str, ctx: Context) -> float:
    if callable(spec):
        return float(spec(ctx))
    if isinstance(spec, str):
        if spec in TAU_RULES:
            return float(TAU_RULES[spec](ctx))
        return float(spec)
    return float(spec)


def make_policy(spec: str) -> Policy:
    """Build a policy from a CLI string, e.g. 'FCFS', 'Delayed:sqrt', 'Delayed:2.5', 'SpeedThreshold:2'."""
    name, _, arg = spec.partition(":")
    key = name.lower()
    if key == "fcfs":
        return FCFS()
    if key in ("random", "randomidle"):
        return RandomIdle()
    if key in ("oldestfastest", "fastest"):
        return OldestFastest()
    if key == "delayed":
        return Delayed(arg or "p_min")
    if key in ("speedthreshold", "threshold"):
        return SpeedThreshold(float(arg or 2.0))
    raise ValueError(f"unknown policy {spec!r}")


DEFAULT_POLICIES = ["FCFS", "RandomIdle", "OldestFastest", "Delayed:p_min", "Delayed:sqrt", "SpeedThreshold:2"]
