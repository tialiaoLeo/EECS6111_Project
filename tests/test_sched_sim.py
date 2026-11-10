import itertools

import pytest

from sched_sim import (
    Delayed,
    FCFS,
    OldestFastest,
    lower_bound_instance,
    offline_opt,
    opt_lower_bound,
    random_instance,
    simulate,
)
from sched_sim.executor import execute
from sched_sim.model import Instance, Job, JobView
from sched_sim.policies import DEFAULT_POLICIES, make_policy


def brute_force_opt(inst: Instance) -> float:
    """Enumerate every thread assignment and every per-thread order (left-shifted)."""
    best = float("inf")
    for assign in itertools.product(range(inst.m), repeat=inst.n):
        total = 0.0
        for i in range(inst.m):
            mine = [j for j in inst.jobs if assign[j.id] == i]
            best_thread = float("inf")
            for order in itertools.permutations(mine):
                t = s = 0.0
                for j in order:
                    t = max(t, j.release) + j.runtime_on(i)
                    s += t
                best_thread = min(best_thread, s)
            total += best_thread if mine else 0.0
        best = min(best, total)
    return best


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("speed_model", ["identical", "related", "unrelated"])
def test_offline_opt_matches_brute_force(seed, speed_model):
    inst = random_instance(5, 2, p_min=1, p_max=8, H=3, speed_model=speed_model, size_model="loguniform", seed=seed)
    opt = offline_opt(inst)
    opt.validate()
    assert opt.total_completion == pytest.approx(brute_force_opt(inst))
    assert opt.total_completion >= opt_lower_bound(inst) - 1e-9


@pytest.mark.parametrize("spec", DEFAULT_POLICIES)
@pytest.mark.parametrize("seed", range(5))
def test_policies_produce_feasible_schedules_no_better_than_opt(spec, seed):
    inst = random_instance(8, 3, p_min=1, p_max=32, H=4, speed_model="unrelated", size_model="bimodal", seed=seed)
    s = simulate(inst, make_policy(spec), seed=seed)
    s.validate()
    assert s.total_completion >= offline_opt(inst).total_completion - 1e-6


def test_policies_never_see_sizes():
    seen = []

    class Spy(FCFS):
        def decide(self, now, waiting, idle):
            seen.extend(waiting)
            return super().decide(now, waiting, idle)

    simulate(random_instance(10, 2, seed=1), Spy())
    assert seen and all(type(v) is JobView and not hasattr(v, "size") for v in seen)


def test_lower_bound_example_hurts_greedy():
    n, L, d = 8, 512.0, 1.0
    inst = lower_bound_instance(n, L=L, delta_t=d)
    opt = offline_opt(inst).total_completion
    greedy = simulate(inst, FCFS()).total_completion
    assert greedy == pytest.approx(L + sum(L + k * d for k in range(1, n)))
    assert greedy / opt > 4


def test_adaptive_adversary_hurts_delayed_rule():
    n, L, d, tau = 8, 512.0, 1.0, 3.0
    inst = lower_bound_instance(n, L=L, delta_t=d, offset=tau)
    s = simulate(inst, Delayed(tau=tau))
    assert s.assignments[0].start == pytest.approx(tau)
    assert s.total_completion / offline_opt(inst).total_completion > 4


def test_delayed_respects_threshold():
    inst = random_instance(10, 2, seed=3)
    tau = 2.5
    s = simulate(inst, Delayed(tau=tau))
    for j in inst.jobs:
        assert s.assignments[j.id].start >= j.release + tau - 1e-9


def test_oldest_fastest_picks_fastest_idle_thread():
    jobs = [Job(0, 0.0, 4.0, (1.0, 4.0, 2.0))]
    inst = Instance(jobs, 3, 1.0, 4.0)
    s = simulate(inst, OldestFastest())
    assert s.assignments[0].thread == 1
    assert s.total_completion == pytest.approx(1.0)


def test_speed_augmentation_never_hurts_on_fixed_assignment():
    inst = random_instance(8, 2, seed=2)
    assert simulate(inst, FCFS(), speedup=1.5).total_completion <= simulate(inst, FCFS()).total_completion


def test_real_execution_matches_model():
    inst = random_instance(5, 2, p_min=1, p_max=4, H=2, seed=0)
    res = execute(inst, OldestFastest(), time_scale=0.02, monitor_interval=0.02)
    assert len(res.records) == inst.n
    assert len(res.monitor.samples) > 0
    for r in res.records.values():
        assert r.start >= r.release - 1e-6
        assert r.measured_runtime == pytest.approx(r.planned_runtime, rel=0.25, abs=0.5)
