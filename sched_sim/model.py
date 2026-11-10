"""Problem model: jobs, threads, instances and instance generators.

Notation follows the proposal: job j has release time r_j and size p_j;
thread i processes job j at speed s_ij, so its runtime is p_j / s_ij.
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

    def runtime_on(self, thread: int) -> float:
        return self.size / self.speeds[thread]


@dataclass(frozen=True)
class JobView:
    """What an online, non-clairvoyant scheduler is allowed to see."""

    id: int
    release: float
    speeds: tuple[float, ...]


@dataclass
class Instance:
    jobs: list[Job]
    num_threads: int
    p_min: float
    p_max: float
    name: str = "instance"
    meta: dict = field(default_factory=dict)

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

    def to_json(self, path: str | Path) -> None:
        data = asdict(self)
        Path(path).write_text(json.dumps(data, indent=2))

    @classmethod
    def from_json(cls, path: str | Path) -> "Instance":
        data = json.loads(Path(path).read_text())
        data["jobs"] = [Job(j["id"], j["release"], j["size"], tuple(j["speeds"])) for j in data["jobs"]]
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


def lower_bound_instance(n: int, L: float, delta_t: float, m: int = 1, offset: float = 0.0) -> Instance:
    """The example from the proposal: one long job at time 0, then n-1 short jobs of size delta_t
    released at time offset + delta_t.

    Any rule that starts the long job at time `offset` pays Omega(nL); Opt pays O(L + n^2 delta_t).
    With offset = tau this is the adaptive adversary against a delayed rule with threshold tau.
    """
    jobs = [Job(0, 0.0, L, (1.0,) * m)]
    jobs += [Job(j, offset + delta_t, delta_t, (1.0,) * m) for j in range(1, n)]
    return Instance(jobs, m, delta_t, L, name="lower-bound", meta={"L": L, "delta_t": delta_t, "offset": offset})
