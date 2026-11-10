"""Background CPU / memory sampler built on psutil."""

from __future__ import annotations

import csv
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import psutil


@dataclass
class Sample:
    t: float  # seconds since monitor start
    cpu_total: float  # system-wide %
    cpu_per_core: list[float]
    mem_percent: float
    procs: dict[str, tuple[float, float]] = field(default_factory=dict)  # label -> (cpu %, rss MB)


class ResourceMonitor:
    """Samples system and per-process usage every `interval` seconds on a daemon thread.

    Tracked processes are the explicitly registered ones plus, if
    `track_children` is set, every descendant of the current process
    (useful with process pools whose PIDs are not known in advance).
    """

    def __init__(self, interval: float = 0.1, track_children: bool = True):
        self.interval = interval
        self.track_children = track_children
        self.samples: list[Sample] = []
        self._labels: dict[int, str] = {}
        self._procs: dict[int, psutil.Process] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.t0 = 0.0
        self.t0_perf = 0.0

    def register(self, pid: int, label: str) -> None:
        self._labels[pid] = label

    def _tracked(self) -> dict[int, psutil.Process]:
        me = psutil.Process(os.getpid())
        pids = set(self._labels)
        if self.track_children:
            try:
                pids.update(c.pid for c in me.children(recursive=True))
            except psutil.Error:
                pass
        for pid in pids:
            if pid not in self._procs:
                try:
                    p = psutil.Process(pid)
                    p.cpu_percent(None)  # prime the counter
                    self._procs[pid] = p
                except psutil.Error:
                    pass
        return self._procs

    def _loop(self) -> None:
        psutil.cpu_percent(None, percpu=True)
        while not self._stop.wait(self.interval):
            per_core = psutil.cpu_percent(None, percpu=True)
            procs = {}
            for pid, p in list(self._tracked().items()):
                try:
                    with p.oneshot():
                        procs[self._labels.get(pid, f"pid{pid}")] = (
                            p.cpu_percent(None),
                            p.memory_info().rss / 2**20,
                        )
                except psutil.Error:
                    self._procs.pop(pid, None)
            self.samples.append(
                Sample(
                    t=time.perf_counter() - self.t0_perf,
                    cpu_total=sum(per_core) / len(per_core),
                    cpu_per_core=per_core,
                    mem_percent=psutil.virtual_memory().percent,
                    procs=procs,
                )
            )

    def start(self) -> "ResourceMonitor":
        self.t0 = time.time()
        self.t0_perf = time.perf_counter()
        self._thread = threading.Thread(target=self._loop, name="resource-monitor", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join()

    def __enter__(self) -> "ResourceMonitor":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    def to_csv(self, path: str | Path) -> None:
        cores = len(self.samples[0].cpu_per_core) if self.samples else 0
        labels = sorted({k for s in self.samples for k in s.procs})
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                ["t", "cpu_total", "mem_percent"]
                + [f"core{c}" for c in range(cores)]
                + [f"{lbl}_cpu" for lbl in labels]
                + [f"{lbl}_rss_mb" for lbl in labels]
            )
            for s in self.samples:
                w.writerow(
                    [f"{s.t:.4f}", s.cpu_total, s.mem_percent]
                    + s.cpu_per_core
                    + [s.procs.get(lbl, (0.0, 0.0))[0] for lbl in labels]
                    + [s.procs.get(lbl, (0.0, 0.0))[1] for lbl in labels]
                )
