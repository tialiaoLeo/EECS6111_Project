"""Problem model: jobs, threads, instances and instance generators.

Notation follows docs/problem_definition.md: job j has release time r_j, size p_j and
(in the declared-limit model) a declared time limit u_j with u_j / lambda <= p_j <= u_j.
Thread i processes job j at speed s_ij, so its runtime is p_j / s_ij; in the
declared-limit model all speeds are 1.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class Job:
    id: int
    release: float
    size: float
    speeds: tuple[float, ...]
    limit: float | None = None  # declared time limit u_j (None outside the declared-limit model)

    def runtime_on(self, thread: int) -> float:
        return self.size / self.speeds[thread]


@dataclass(frozen=True)
class JobView:
    """What an online, non-clairvoyant scheduler is allowed to see."""

    id: int
    release: float
    speeds: tuple[float, ...]
    limit: float | None = None  # declared time limit u_j, visible at release


@dataclass
class Instance:
    jobs: list[Job]
    num_threads: int
    p_min: float
    p_max: float
    name: str = "instance"
    meta: dict = field(default_factory=dict)
    lam: float = 1.0  # known accuracy of the declared limits: u_j / lam <= p_j <= u_j

    @property
    def n(self) -> int:
        return len(self.jobs)

    @property
    def m(self) -> int:
        return self.num_threads

    @property
    def delta(self) -> float:
        return self.p_max / self.p_min

    @property
    def H(self) -> float:
        speeds = [s for j in self.jobs for s in j.speeds]
        return max(speeds) / min(speeds)

    @property
    def has_limits(self) -> bool:
        return bool(self.jobs) and all(j.limit is not None for j in self.jobs)

    def check_limits(self, tol: float = 1e-9) -> None:
        """Assert u_j / lam <= p_j <= u_j for every job."""
        assert self.has_limits, "instance has no declared limits"
        for j in self.jobs:
            assert j.limit / self.lam - tol * j.limit <= j.size <= j.limit * (1 + tol), (
                f"job {j.id}: size {j.size} outside [{j.limit / self.lam}, {j.limit}]"
            )

    def to_json(self, path: str | Path) -> None:
        data = asdict(self)
        Path(path).write_text(json.dumps(data, indent=2))

    @classmethod
    def from_json(cls, path: str | Path) -> "Instance":
        data = json.loads(Path(path).read_text())
        data["jobs"] = [
            Job(j["id"], j["release"], j["size"], tuple(j["speeds"]), j.get("limit")) for j in data["jobs"]
        ]
        return cls(**data)


@dataclass
class Assignment:
    job: int
    thread: int
    start: float
    end: float


@dataclass
class Schedule:
    instance: Instance
    assignments: dict[int, Assignment]
    policy: str

    @property
    def total_completion(self) -> float:
        return sum(a.end for a in self.assignments.values())

    @property
    def makespan(self) -> float:
        return max(a.end for a in self.assignments.values())

    def validate(self, tol: float = 1e-9) -> None:
        """Check feasibility: release times, non-overlap, correct runtimes."""
        inst = self.instance
        assert set(self.assignments) == {j.id for j in inst.jobs}, "not every job was scheduled"
        by_thread: dict[int, list[Assignment]] = {}
        for job in inst.jobs:
            a = self.assignments[job.id]
            assert a.start >= job.release - tol, f"job {job.id} started before release"
            assert abs((a.end - a.start) - job.runtime_on(a.thread)) <= 1e-6 * max(1.0, a.end), (
                f"job {job.id} has wrong runtime"
            )
            by_thread.setdefault(a.thread, []).append(a)
        for thread, items in by_thread.items():
            items.sort(key=lambda a: a.start)
            for prev, nxt in zip(items, items[1:]):
                assert nxt.start >= prev.end - tol, f"overlap on thread {thread}"


# --------------------------------------------------------------------------- #
# Instance generators
# --------------------------------------------------------------------------- #

SPEED_MODELS = ("identical", "related", "unrelated")
SIZE_MODELS = ("uniform", "loguniform", "bimodal")


def make_speeds(rng: np.random.Generator, n: int, m: int, model: str, H: float) -> np.ndarray:
    """Return an n x m speed matrix with max/min ratio at most H.

    identical: s_ij = 1; related: s_ij = s_i; unrelated: s_ij arbitrary.
    """
    if model == "identical":
        return np.ones((n, m))
    if model == "related":
        per_thread = np.exp(rng.uniform(0.0, np.log(H), size=m))
        per_thread[0], per_thread[-1] = 1.0, H  # make the speed ratio exactly H
        if m == 1:
            per_thread[0] = 1.0
        return np.tile(per_thread, (n, 1))
    if model == "unrelated":
        return np.exp(rng.uniform(0.0, np.log(H), size=(n, m)))
    raise ValueError(f"unknown speed model {model!r}; choose from {SPEED_MODELS}")


def make_sizes(rng: np.random.Generator, n: int, p_min: float, p_max: float, model: str) -> np.ndarray:
    if model == "uniform":
        return rng.uniform(p_min, p_max, size=n)
    if model == "loguniform":
        return np.exp(rng.uniform(np.log(p_min), np.log(p_max), size=n))
    if model == "bimodal":
        # Mostly short jobs with a few long ones: the pattern that hurts non-preemptive rules.
        return np.where(rng.random(n) < 0.15, p_max, p_min)
    raise ValueError(f"unknown size model {model!r}; choose from {SIZE_MODELS}")


def random_instance(
    n: int,
    m: int,
    *,
    p_min: float = 1.0,
    p_max: float = 10.0,
    H: float = 4.0,
    speed_model: str = "related",
    size_model: str = "loguniform",
    arrival_rate: float | None = None,
    seed: int | None = None,
) -> Instance:
    """Poisson arrivals with the given rate (default: roughly 80% load)."""
    rng = np.random.default_rng(seed)
    sizes = make_sizes(rng, n, p_min, p_max, size_model)
    speeds = make_speeds(rng, n, m, speed_model, H)
    if arrival_rate is None:
        mean_runtime = float(np.mean(sizes[:, None] / speeds))
        arrival_rate = 0.8 * m / mean_runtime
    releases = np.concatenate([[0.0], np.cumsum(rng.exponential(1.0 / arrival_rate, size=n - 1))])
    jobs = [Job(j, float(releases[j]), float(sizes[j]), tuple(map(float, speeds[j]))) for j in range(n)]
    return Instance(
        jobs,
        m,
        p_min,
        p_max,
        name=f"random-{speed_model}-{size_model}",
        meta={"seed": seed, "H": H, "arrival_rate": arrival_rate},
    )


def lower_bound_instance(
    n: int, L: float, delta_t: float, m: int = 1, offset: float = 0.0, with_limits: bool = False
) -> Instance:
    """The example from the proposal: one long job at time 0, then n-1 short jobs of size delta_t
    released at time offset + delta_t.

    Any rule that starts the long job at time `offset` pays Omega(nL); Opt pays O(L + n^2 delta_t).
    With offset = tau this is the adaptive adversary against a delayed rule with threshold tau.

    with_limits=True gives every job the same declared limit u = L, so the limits carry no information
    and lam = L / delta_t (the special case "all u_j equal" of the declared-limit model).
    """
    limit = L if with_limits else None
    jobs = [Job(0, 0.0, L, (1.0,) * m, limit)]
    jobs += [Job(j, offset + delta_t, delta_t, (1.0,) * m, limit) for j in range(1, n)]
    return Instance(
        jobs, m, delta_t, L, name="lower-bound",
        meta={"L": L, "delta_t": delta_t, "offset": offset},
        lam=L / delta_t if with_limits else 1.0,
    )


# --------------------------------------------------------------------------- #
# Declared-limit model (docs/problem_definition.md, v3)
# --------------------------------------------------------------------------- #

SIZE_DISTS = ("uniform", "loguniform", "low", "high", "extremes")
DEFAULT_LIMITS = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0)


def limits_between(u_min: float, u_max: float) -> tuple[float, ...]:
    """Powers of two from u_min up to u_max: a coarse menu like users' modal walltime requests."""
    out, u = [], float(u_min)
    while u <= u_max * (1 + 1e-12):
        out.append(u)
        u *= 2
    return tuple(out)


def sizes_within_limits(rng: np.random.Generator, limits: np.ndarray, lam: float, dist: str) -> np.ndarray:
    """Draw p_j in [u_j / lam, u_j].

    uniform / loguniform: spread over the interval; low: p_j = u_j / lam (every limit overestimates
    by exactly lam); high: p_j = u_j (exact limits); extremes: one endpoint or the other, 50/50.
    """
    lo = limits / lam
    if dist == "uniform":
        p = rng.uniform(lo, limits)
    elif dist == "loguniform":
        p = np.exp(rng.uniform(np.log(lo), np.log(limits)))
    elif dist == "low":
        p = lo.copy()
    elif dist == "high":
        p = limits.copy()
    elif dist == "extremes":
        p = np.where(rng.random(len(limits)) < 0.5, lo, limits)
    else:
        raise ValueError(f"unknown size distribution {dist!r}; choose from {SIZE_DISTS}")
    return np.clip(p, lo, limits)


def limit_instance(
    n: int,
    m: int,
    *,
    lam: float = 4.0,
    limits: tuple[float, ...] = DEFAULT_LIMITS,
    size_dist: str = "uniform",
    arrival_rate: float | None = None,
    load: float = 0.8,
    seed: int | None = None,
) -> Instance:
    """m identical workers; each job declares a limit u_j drawn from `limits` and has a hidden size
    p_j in [u_j / lam, u_j]. Poisson arrivals, by default at the given load."""
    if lam < 1:
        raise ValueError("lam must be >= 1")
    rng = np.random.default_rng(seed)
    u = rng.choice(np.asarray(limits, dtype=float), size=n)
    p = sizes_within_limits(rng, u, lam, size_dist)
    if arrival_rate is None:
        arrival_rate = load * m / float(np.mean(p))
    releases = np.concatenate([[0.0], np.cumsum(rng.exponential(1.0 / arrival_rate, size=n - 1))])
    jobs = [Job(j, float(releases[j]), float(p[j]), (1.0,) * m, float(u[j])) for j in range(n)]
    return Instance(
        jobs,
        m,
        p_min=float(min(u)) / lam,
        p_max=float(max(u)),
        name=f"limits-{size_dist}",
        meta={"seed": seed, "limits": list(map(float, limits)), "size_dist": size_dist, "arrival_rate": arrival_rate},
        lam=float(lam),
    )
