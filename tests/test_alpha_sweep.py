"""Tests for the adversarial families of sched_sim/alpha_sweep.py."""

import math

import pytest

from sched_sim import SLF, DelayedSLF, offline_opt, simulate
from sched_sim.alpha_sweep import FAMILIES, batch, ratio, single, trap, trap_batch


@pytest.mark.parametrize("lam", [1.0, 4.0, 16.0])
@pytest.mark.parametrize("make", [SLF, lambda: DelayedSLF(0.5)])
def test_closed_form_optimum_matches_exact_search(lam, make):
    policy = make()
    for inst in (batch(policy, lam, k=2), trap(policy, lam, k=9)):
        assert inst.meta["opt"] == pytest.approx(offline_opt(inst, max_n=19).total_completion)


@pytest.mark.parametrize("lam", [4.0, 64.0])
def test_single_job_costs_one_plus_alpha_lam(lam):
    alpha = lam ** -0.5
    policy = DelayedSLF(alpha)
    assert ratio(single(policy, lam), policy) == pytest.approx(1 + alpha * lam)
    assert ratio(single(SLF(), lam), SLF()) == pytest.approx(1.0)


def test_batch_makes_the_first_started_jobs_long():
    lam, policy = 16.0, SLF()
    inst = batch(policy, lam, k=3)
    s = simulate(inst, policy)
    first = sorted(s.assignments, key=lambda j: s.assignments[j].start)[:3]
    assert all(inst.jobs[j].size == lam for j in first)
    assert sum(j.size == lam for j in inst.jobs) == 3 and inst.n == 3 + 12


def test_trap_hurts_rules_that_never_idle():
    lam = 4.0
    assert ratio(trap(SLF(), lam, k=200), SLF()) > 100
    waiting = DelayedSLF(lam ** -0.5)
    assert ratio(trap(waiting, lam, k=200), waiting) < 1 + math.sqrt(lam) + 1e-6


def test_all_families_build_valid_small_instances():
    policy = DelayedSLF(0.25)
    for name, build in FAMILIES.items():
        inst = build(policy, 16.0)
        inst.check_limits()
        assert inst.m == 1 and inst.name == name
    assert trap_batch(policy, 16.0).n <= 18
