from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import psutil

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DISK_PATH = "/" if Path("/").exists() else str(_PROJECT_ROOT)


@dataclass(frozen=True)
class MetricSnapshot:
    percent: float
    used_label: str
    total_label: str


@dataclass(frozen=True)
class SystemMetrics:
    cpu: MetricSnapshot
    memory: MetricSnapshot
    disk: MetricSnapshot


def _format_size(size_bytes: int) -> str:
    gib = size_bytes / (1024**3)
    if gib >= 1:
        return f"{gib:.1f} GB"

    mib = size_bytes / (1024**2)
    return f"{mib:.0f} MB"


def get_system_metrics() -> SystemMetrics:
    cpu_percent = float(psutil.cpu_percent(interval=0.1))
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(_DISK_PATH)
    cpu_count = psutil.cpu_count(logical=True) or 1

    return SystemMetrics(
        cpu=MetricSnapshot(
            percent=round(cpu_percent, 1),
            used_label="—",
            total_label=f"{cpu_count} ядер",
        ),
        memory=MetricSnapshot(
            percent=round(float(memory.percent), 1),
            used_label=_format_size(int(memory.used)),
            total_label=_format_size(int(memory.total)),
        ),
        disk=MetricSnapshot(
            percent=round(float(disk.percent), 1),
            used_label=_format_size(int(disk.used)),
            total_label=_format_size(int(disk.total)),
        ),
    )


def get_system_metrics_dict() -> dict[str, dict[str, str | float]]:
    metrics = get_system_metrics()
    return {
        "cpu": asdict(metrics.cpu),
        "memory": asdict(metrics.memory),
        "disk": asdict(metrics.disk),
    }
