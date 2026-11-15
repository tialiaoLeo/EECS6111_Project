"""Tests for the declared-limit model (docs/problem_definition.md, v3)."""

import pytest

from sched_sim import (
    FCFS,
    SLF,
    DelayedSLF,
    Instance,
    Job,
    JobView,
    limit_instance,
    lower_bound_instance,
    offline_opt,
    simulate,
    trace_instance,
)
from sched_sim.experiments import Scenario, limits_grid, run_trial
from sched_sim.model import SIZE_DISTS, limits_between
from sched_sim.policies import LIMIT_POLICIES, make_policy


def _inst(jobs, m=1, lam=1.0):
    """jobs: list of (release, size, limit)."""
    js = [Job(k, r, p, (1.0,) * m, u) for k, (r, p, u) in enumerate(jobs)]
    return Instance(js, m, min(u for *_, u in jobs) / lam, max(u for *_, u in jobs), lam=lam)


# --------------------------------------------------------------------------- generator


@pytest.mark.parametrize("dist", SIZE_DISTS)
@pytest.mark.parametrize("lam", [1.0, 2.0, 16.0])
def test_limit_instance_respects_bounds(dist, lam):
    inst = limit_instance(50, 3, lam=lam, limits=(1.0, 4.0, 16.0), size_dist=dist, seed=1)
    inst.check_limits()
    assert inst.lam == lam and inst.has_limits
    assert all(j.speeds == (1.0, 1.0, 1.0) for j in inst.jobs)
    assert {j.limit for j in inst.jobs} <= {1.0, 4.0, 16.0}
    if dist == "high" or lam == 1.0:
        assert all(j.size == pytest.approx(j.limit) for j in inst.jobs)
    if dist == "low":
        assert all(j.size == pytest.approx(j.limit / lam) for j in inst.jobs)


def test_limits_between_is_powers_of_two():
    assert limits_between(1, 32) == (1.0, 2.0, 4.0, 8.0, 16.0, 32.0)
    assert limits_between(0.5, 3) == (0.5, 1.0, 2.0)


def test_instance_json_roundtrip_keeps_limits(tmp_path):
    inst = limit_instance(6, 2, lam=3.0, seed=4)
    inst.to_json(tmp_path / "i.json")
    back = Instance.from_json(tmp_path / "i.json")
    assert back.lam == 3.0
    assert [j.limit for j in back.jobs] == [j.limit for j in inst.jobs]
    assert [j.size for j in back.jobs] == [j.size for j in inst.jobs]


def test_lower_bound_with_limits_is_uninformative():
    inst = lower_bound_instance(6, L=64.0, delta_t=1.0, with_limits=True)
    assert {j.limit for j in inst.jobs} == {64.0} and inst.lam == 64.0
    inst.check_limits()


# --------------------------------------------------------------------------- policies


def test_policies_see_limits_but_not_sizes():
    seen = []

    class Spy(SLF):
        def decide(self, now, waiting, idle):
            seen.extend(waiting)
            return super().decide(now, waiting, idle)

    inst = limit_instance(10, 2, seed=1)
    simulate(inst, Spy())
    assert seen and all(type(v) is JobView and not hasattr(v, "size") for v in seen)
    limits = {j.id: j.limit for j in inst.jobs}
    assert all(v.limit == limits[v.id] for v in seen)


def test_slf_starts_smallest_limit_first():
    # all released at 0 on one worker; sizes equal limits
    inst = _inst([(0.0, 8.0, 8.0), (0.0, 2.0, 2.0), (0.0, 4.0, 4.0)])
    s = simulate(inst, SLF())
    starts = {j: a.start for j, a in s.assignments.items()}
    assert starts[1] == 0.0 and starts[2] == pytest.approx(2.0) and starts[0] == pytest.approx(6.0)
    # FCFS ignores limits and keeps the release / id order
    f = simulate(inst, FCFS())
    assert f.assignments[0].start == 0.0


def test_slf_needs_limits():
    inst = Instance([Job(0, 0.0, 1.0, (1.0,))], 1, 1.0, 1.0)
    with pytest.raises(ValueError, match="declared limit"):
        simulate(inst, SLF())


def test_delayed_slf_waits_until_limit():
    inst = _inst([(0.0, 3.0, 3.0), (5.0, 1.0, 3.0)], lam=3.0)
    s = simulate(inst, DelayedSLF())
    assert s.assignments[0].start == pytest.approx(3.0)  # waits until t = u_j
    assert s.assignments[1].start == pytest.approx(6.0)  # eligible at 5, worker busy until 6
    half = simulate(inst, DelayedSLF(0.5))
    assert half.assignments[0].start == pytest.approx(1.5)


@pytest.mark.parametrize("seed", range(40))
def test_delayed_slf_with_exact_limits_is_2_competitive_on_one_machine(seed):
    """lam = 1: limits are the true sizes and DelayedSLF is Hoogeveen-Vestjens' delayed SPT,
    which is 2-competitive for 1 | r_j | sum C_j."""
    inst = limit_instance(7, 1, lam=1.0, limits=(1.0, 2.0, 4.0, 8.0, 16.0), seed=seed, load=1.2)
    ratio = simulate(inst, DelayedSLF()).total_completion / offline_opt(inst).total_completion
    assert ratio <= 2.0 + 1e-9


@pytest.mark.parametrize("spec", LIMIT_POLICIES + ["DelayedSLF:0.5", "RandomIdle"])
@pytest.mark.parametrize("seed", range(4))
def test_limit_policies_feasible_and_no_better_than_opt(spec, seed):
    inst = limit_instance(8, 2, lam=4.0, size_dist="extremes", seed=seed)
    s = simulate(inst, make_policy(spec), seed=seed)
    s.validate()
    assert s.total_completion >= offline_opt(inst).total_completion - 1e-6


# --------------------------------------------------------------------------- traces

SWF = """\
; Version: 2.2
; Note: synthetic test trace
1   100  5  3600  1 -1 -1  1  7200 -1 1 1 1 1 1 1 -1 -1
2   200  0  4000  8 -1 -1  8  7200 -1 1 1 1 1 1 1 -1 -1
3   300  0     5  1 -1 -1  1  3600 -1 0 1 1 1 1 1 -1 -1
4   400  0  3700  1 -1 -1  1  3600 -1 0 1 1 1 1 1 -1 -1
5   500  0  1000  1 -1 -1  1    -1 -1 1 1 1 1 1 1 -1 -1
6   700  0   600  1 -1 -1  1 36000 -1 1 1 1 1 1 1 -1 -1
7   900  0  1800 -1 -1 -1  1  3600 -1 1 1 1 1 1 1 -1 -1
"""


def test_trace_filters_and_converts(tmp_path):
    path = tmp_path / "t.swf"
    path.write_text(SWF)
    inst, st = trace_instance(path, m=2)
    assert st.total == 7
    assert st.missing_fields == 1  # job 5: no requested time
    assert st.multi_proc == 1  # job 2: 8 processors
    assert st.too_short == 1  # job 3: failed at start-up (5 s)
    assert st.overrun_clipped == 1  # job 4: ran 3700 s with a 3600 s limit
    assert st.kept == 4  # jobs 1, 4, 6, 7 (7 uses the requested processor count)
    assert [j.release for j in inst.jobs] == pytest.approx([0.0, 300 / 3600, 600 / 3600, 800 / 3600])
    assert inst.jobs[1].size == pytest.approx(inst.jobs[1].limit)  # clipped to its limit
    assert inst.lam == pytest.approx(60.0)  # job 6: 36000 / 600
    inst.check_limits()
    assert inst.meta["swf_job_ids"] == [1, 4, 6, 7]


def test_trace_lam_filter_and_slice(tmp_path):
    path = tmp_path / "t.swf"
    path.write_text(SWF)
    inst, st = trace_instance(path, m=1, lam=4.0, max_jobs=2)
    assert st.ratio_violations == 1  # job 6
    assert st.kept_before_slice == 3 and st.kept == 2
    assert inst.lam == 4.0
    inst.check_limits()
    s = simulate(inst, SLF())
    s.validate()


# --------------------------------------------------------------------------- experiments


def test_limits_grid_and_trial():
    grid = limits_grid(5, quick=True)
    assert grid and all(s.kind == "limits" for s in grid)
    out = run_trial(0, Scenario("limits", 5, 2, "identical", "uniform", 1.0, 8.0, 1.0, 4.0, "low"),
                    seed=0, policies=LIMIT_POLICIES, max_opt_n=8)
    assert len(out["rows"]) == len(LIMIT_POLICIES)
    assert all(r["ratio"] >= 1 - 1e-9 and r["opt_kind"] == "exact" for r in out["rows"])
    assert all(r["lam"] == 4.0 for r in out["rows"])
