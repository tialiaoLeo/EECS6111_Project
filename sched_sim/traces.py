"""Load Parallel Workloads Archive traces (Standard Workload Format) as declared-limit instances.

SWF reference: https://www.cs.huji.ac.il/labs/parallel/workload/swf.html
Each data line has 18 whitespace-separated fields; lines starting with ';' are header comments.
Fields used here (1-based as in the SWF spec):
    1  job number
    2  submit time (s)
    4  run time (s)                        -> p_j
    5  number of allocated processors
    8  requested number of processors      (used when field 5 is missing)
    9  requested time (s)                  -> u_j, the declared limit
   11  status
Missing values are -1.

Filtering, in this order:
  1. drop records with missing submit / run / requested time or processor count;
  2. keep jobs that use at most `max_procs` processors (single-node jobs);
  3. drop jobs that ran for less than `min_runtime` seconds. Jobs that fail at start-up have
     p_j close to 0 and violate p_j >= u_j / lam; they are left out for now;
  4. clip run time to the requested time. Jobs killed at their limit run slightly past it
     (kill latency) and in the model occupy the worker for exactly u_j;
  5. if `lam` is given, drop jobs with u_j / p_j > lam; otherwise set lam = max u_j / p_j;
  6. sort by submit time and keep jobs `start .. start + max_jobs - 1`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from .model import Instance, Job


@dataclass(frozen=True)
class SWFRecord:
    job_id: int
    submit: float
    run_time: float
    procs: int
    requested_time: float
    status: int


def read_swf(path: str | Path) -> list[SWFRecord]:
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(";"):
                continue
            parts = line.split()
            if len(parts) < 11:
                continue
            alloc, req = int(float(parts[4])), int(float(parts[7]))
            records.append(
                SWFRecord(
                    job_id=int(float(parts[0])),
                    submit=float(parts[1]),
                    run_time=float(parts[3]),
                    procs=alloc if alloc > 0 else req,
                    requested_time=float(parts[8]),
                    status=int(float(parts[10])),
                )
            )
    return records


@dataclass
class TraceStats:
    total: int = 0
    missing_fields: int = 0
    multi_proc: int = 0
    too_short: int = 0
    overrun_clipped: int = 0
    ratio_violations: int = 0
    kept_before_slice: int = 0
    kept: int = 0
    lam: float = 1.0
    ratio_quantiles: dict = field(default_factory=dict)  # u_j / p_j over the kept jobs

    def summary(self) -> str:
        q = ", ".join(f"{k}={v:.2f}" for k, v in self.ratio_quantiles.items())
        return (
            f"{self.total} records: dropped {self.missing_fields} incomplete, {self.multi_proc} multi-processor, "
            f"{self.too_short} too short (failed at start-up), {self.ratio_violations} with u/p > lam; "
            f"clipped {self.overrun_clipped} overruns; kept {self.kept} (of {self.kept_before_slice}); "
            f"lam = {self.lam:.3g}; u/p quantiles: {q}"
        )


def trace_instance(
    source: str | Path | list[SWFRecord],
    m: int,
    *,
    max_procs: int = 1,
    min_runtime: float = 60.0,
    lam: float | None = None,
    start: int = 0,
    max_jobs: int | None = None,
    time_unit: float = 3600.0,
    name: str | None = None,
) -> tuple[Instance, TraceStats]:
    """Build a declared-limit instance on m identical workers from an SWF trace.

    Times are shifted so the first kept job is released at 0 and divided by `time_unit`
    (default: hours).
    """
    records = read_swf(source) if isinstance(source, (str, Path)) else list(source)
    stats = TraceStats(total=len(records))

    kept: list[tuple[float, float, float, int]] = []  # (submit, p, u, original id)
    for r in records:
        if r.submit < 0 or r.run_time < 0 or r.requested_time <= 0 or r.procs <= 0:
            stats.missing_fields += 1
            continue
        if r.procs > max_procs:
            stats.multi_proc += 1
            continue
        if r.run_time < min_runtime:
            stats.too_short += 1
            continue
        p = r.run_time
        if p > r.requested_time:
            p = r.requested_time
            stats.overrun_clipped += 1
        if lam is not None and r.requested_time / p > lam * (1 + 1e-12):
            stats.ratio_violations += 1
            continue
        kept.append((r.submit, p, r.requested_time, r.job_id))

    kept.sort()
    stats.kept_before_slice = len(kept)
    kept = kept[start : None if max_jobs is None else start + max_jobs]
    if not kept:
        raise ValueError("no jobs left after filtering: " + stats.summary())

    ratios = np.array([u / p for _, p, u, _ in kept])
    stats.ratio_quantiles = {q: float(np.quantile(ratios, x)) for q, x in
                             (("p50", 0.5), ("p90", 0.9), ("p99", 0.99), ("max", 1.0))}
    stats.lam = float(lam) if lam is not None else float(ratios.max())
    stats.kept = len(kept)

    t0 = kept[0][0]
    jobs = [
        Job(k, (s - t0) / time_unit, p / time_unit, (1.0,) * m, u / time_unit)
        for k, (s, p, u, _) in enumerate(kept)
    ]
    us = [j.limit for j in jobs]
    inst = Instance(
        jobs,
        m,
        p_min=min(us) / stats.lam,
        p_max=max(us),
        name=name or (Path(source).stem if isinstance(source, (str, Path)) else "trace"),
        meta={
            "source": str(source) if isinstance(source, (str, Path)) else "records",
            "time_unit_seconds": time_unit,
            "swf_job_ids": [jid for *_, jid in kept],
            "filter": {"max_procs": max_procs, "min_runtime": min_runtime, "start": start, "max_jobs": max_jobs},
            "stats": asdict(stats),
        },
        lam=stats.lam,
    )
    return inst, stats
