from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterable, List, Optional, Sequence


class PerformanceOSType(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"

    @classmethod
    def from_label(cls, label: str | None) -> Optional["PerformanceOSType"]:
        if not label:
            return None
        normalized = label.strip().lower()
        for member in cls:
            if normalized == member.value:
                return member
        return None


@dataclass(frozen=True)
class PerformanceSample:
    timestamp: datetime
    elapsed_seconds: float


@dataclass(frozen=True)
class WindowsSample(PerformanceSample):
    cpu_percent: Optional[float]
    private_bytes: Optional[int]


@dataclass(frozen=True)
class LinuxSample(PerformanceSample):
    cpu_user_percent: Optional[float]
    cpu_system_percent: Optional[float]
    free_kib: Optional[int]
    buff_kib: Optional[int]
    cache_kib: Optional[int]
    io_bi: Optional[float]
    io_bo: Optional[float]


@dataclass
class PerformanceDataset:
    os_type: PerformanceOSType
    source_name: str
    samples: Sequence[PerformanceSample] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def require_windows_samples(self) -> Sequence[WindowsSample]:
        if self.os_type != PerformanceOSType.WINDOWS:
            raise TypeError("Windows dataset requested from non-Windows performance data.")
        return self.samples  # type: ignore[return-value]

    def require_linux_samples(self) -> Sequence[LinuxSample]:
        if self.os_type != PerformanceOSType.LINUX:
            raise TypeError("Linux dataset requested from non-Linux performance data.")
        return self.samples  # type: ignore[return-value]


@dataclass
class PerformanceParsingResult:
    dataset: PerformanceDataset
    warnings: Sequence[str] = field(default_factory=list)

