from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple

from .models import (
    LinuxSample,
    PerformanceDataset,
    PerformanceOSType,
    PerformanceParsingResult,
    PerformanceSample,
    WindowsSample,
)


UTF8_BOM = "\ufeff"


WINDOWS_SIGNATURE_PATTERN = re.compile(r"\(pdh-csv\s*4\.0\)", re.IGNORECASE)
LINUX_HEADER_PATTERN = re.compile(r"^procs\s+-+memory", re.IGNORECASE)
LINUX_COLUMN_PATTERN = re.compile(r"\s*r\s+b\s+swpd\s+free\s+buff\s+cache\s+si\s+so\s+bi\s+bo", re.IGNORECASE)


def detect_os_type(filename: str, raw_bytes: bytes) -> Optional[PerformanceOSType]:
    """Attempt to determine the operating-system flavour from raw bytes."""
    sample = raw_bytes[:2048].decode("utf-8", errors="ignore")
    normalized = sample.lower()
    if WINDOWS_SIGNATURE_PATTERN.search(normalized):
        return PerformanceOSType.WINDOWS

    header_lines = normalized.splitlines()
    if header_lines:
        first_line = header_lines[0]
        if LINUX_HEADER_PATTERN.match(first_line) or any(
            LINUX_COLUMN_PATTERN.search(line) for line in header_lines[:3]
        ):
            return PerformanceOSType.LINUX

    # Fall back on filename hints
    if filename:
        lower_name = filename.lower()
        if lower_name.endswith(".csv"):
            if "perfmon" in lower_name or "windows" in lower_name:
                return PerformanceOSType.WINDOWS
        if lower_name.endswith(".txt"):
            if "vmstat" in lower_name or "linux" in lower_name:
                return PerformanceOSType.LINUX

    return None


def parse_performance_file(
    os_type: PerformanceOSType,
    raw_bytes: bytes,
    *,
    source_name: str,
) -> PerformanceParsingResult:
    if os_type == PerformanceOSType.WINDOWS:
        return parse_windows_perfmon(raw_bytes, source_name=source_name)
    if os_type == PerformanceOSType.LINUX:
        return parse_linux_vmstat(raw_bytes, source_name=source_name)
    raise ValueError(f"Unsupported OS type for performance parsing: {os_type!r}")


def parse_windows_perfmon(
    raw_bytes: bytes,
    *,
    source_name: str,
) -> PerformanceParsingResult:
    text = raw_bytes.decode("utf-8", errors="ignore")
    if text.startswith(UTF8_BOM):
        text = text.lstrip(UTF8_BOM)

    stream = io.StringIO(text)
    reader = csv.reader(stream)
    try:
        header = next(reader)
    except StopIteration:
        raise ValueError("빈 Perfmon CSV 파일입니다.")

    if not header:
        raise ValueError("Perfmon CSV 헤더를 읽지 못했습니다.")

    cpu_index = _locate_windows_column(header, {"% processor time", "% processor time "})
    memory_bytes_index = _locate_windows_column(header, {"private bytes", "working set", "private mbytes"})
    if cpu_index is None and memory_bytes_index is None:
        raise ValueError("CPU 또는 메모리 카운터를 찾지 못했습니다.")

    samples: List[WindowsSample] = []
    warnings: List[str] = []
    first_timestamp: Optional[datetime] = None

    for line_number, row in enumerate(reader, start=2):
        if not row or all(not cell.strip() for cell in row):
            continue

        timestamp_raw = row[0].strip() if len(row) > 0 else ""
        if not timestamp_raw:
            warnings.append(f"{line_number}행: 타임스탬프가 비어 있어 건너뜁니다.")
            continue

        timestamp = _parse_windows_timestamp(timestamp_raw)
        if timestamp is None:
            warnings.append(f"{line_number}행: 알 수 없는 타임스탬프 형식 '{timestamp_raw}'")
            continue

        if first_timestamp is None:
            first_timestamp = timestamp

        elapsed_seconds = (timestamp - first_timestamp).total_seconds() if first_timestamp else 0.0

        cpu_percent = _safe_parse_float(row, cpu_index)
        private_bytes: Optional[int]
        if memory_bytes_index is not None:
            memory_raw = _safe_parse_float(row, memory_bytes_index)
            if memory_raw is None:
                private_bytes = None
            else:
                # Perfmon may output MB for certain counters; detect by header text.
                header_label = header[memory_bytes_index].lower()
                if "mbytes" in header_label or "mb" in header_label:
                    private_bytes = int(memory_raw * 1024 * 1024)
                else:
                    private_bytes = int(memory_raw)
        else:
            private_bytes = None

        samples.append(
            WindowsSample(
                timestamp=timestamp,
                elapsed_seconds=elapsed_seconds,
                cpu_percent=cpu_percent,
                private_bytes=private_bytes,
            )
        )

    if not samples:
        raise ValueError("Perfmon CSV에서 유효한 데이터를 찾지 못했습니다.")

    dataset = PerformanceDataset(
        os_type=PerformanceOSType.WINDOWS,
        source_name=source_name,
        samples=samples,
        metadata={
            "cpu_counter": header[cpu_index] if cpu_index is not None else None,
            "memory_counter": header[memory_bytes_index] if memory_bytes_index is not None else None,
        },
    )

    return PerformanceParsingResult(dataset=dataset, warnings=warnings)


def parse_linux_vmstat(
    raw_bytes: bytes,
    *,
    source_name: str,
) -> PerformanceParsingResult:
    text = raw_bytes.decode("utf-8", errors="ignore")
    if text.startswith(UTF8_BOM):
        text = text.lstrip(UTF8_BOM)

    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if len(lines) < 3:
        raise ValueError("vmstat 결과에서 유효한 데이터 행을 찾지 못했습니다.")

    data_lines = _strip_vmstat_headers(lines)
    if not data_lines:
        raise ValueError("vmstat 데이터 본문을 찾지 못했습니다.")

    samples: List[LinuxSample] = []
    warnings: List[str] = []
    first_timestamp: Optional[datetime] = None
    total_memory_kib: Optional[int] = None

    for line_number, row_text in data_lines:
        parts = row_text.split()
        if len(parts) < 19:
            warnings.append(f"{line_number}행: 예상보다 적은 열 수({len(parts)}) - 건너뜀")
            continue

        # Merge date/time tokens at the end
        timestamp_str = f"{parts[17]} {parts[18]}"
        timestamp = _parse_linux_timestamp(timestamp_str)
        if timestamp is None:
            warnings.append(f"{line_number}행: 알 수 없는 타임스탬프 형식 '{timestamp_str}'")
            continue

        if first_timestamp is None:
            first_timestamp = timestamp

        elapsed_seconds = (timestamp - first_timestamp).total_seconds() if first_timestamp else 0.0

        try:
            free_kib = int(parts[3])
            buff_kib = int(parts[4])
            cache_kib = int(parts[5])
        except ValueError:
            warnings.append(f"{line_number}행: 메모리 수치를 정수로 파싱하지 못했습니다.")
            free_kib = buff_kib = cache_kib = 0

        if total_memory_kib is None:
            total_memory_kib = free_kib + buff_kib + cache_kib

        sample = LinuxSample(
            timestamp=timestamp,
            elapsed_seconds=elapsed_seconds,
            cpu_user_percent=_safe_parse_float(parts, 12),
            cpu_system_percent=_safe_parse_float(parts, 13),
            free_kib=free_kib,
            buff_kib=buff_kib,
            cache_kib=cache_kib,
            io_bi=_safe_parse_float(parts, 8),
            io_bo=_safe_parse_float(parts, 9),
        )
        samples.append(sample)

    if not samples:
        raise ValueError("vmstat 로그에서 유효한 샘플을 파싱하지 못했습니다.")

    dataset = PerformanceDataset(
        os_type=PerformanceOSType.LINUX,
        source_name=source_name,
        samples=samples,
        metadata={
            "total_memory_kib": total_memory_kib,
        },
    )
    return PerformanceParsingResult(dataset=dataset, warnings=warnings)


def _locate_windows_column(header: Sequence[str], keywords: Iterable[str]) -> Optional[int]:
    normalized_header = [item.strip().lower() for item in header]
    for index, name in enumerate(normalized_header):
        for keyword in keywords:
            if keyword.strip().lower() in name:
                return index
    # fall back to approximate matching
    for index, name in enumerate(normalized_header):
        if "processor" in name and "%" in name:
            return index
    return None


def _parse_windows_timestamp(value: str) -> Optional[datetime]:
    value = value.strip()
    if not value:
        return None
    candidates = [
        "%m/%d/%Y %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S.%f",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _parse_linux_timestamp(value: str) -> Optional[datetime]:
    value = value.strip()
    if not value:
        return None
    candidates = [
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _safe_parse_float(row: Sequence[str], index: Optional[int]) -> Optional[float]:
    if index is None or index < 0 or index >= len(row):
        return None
    raw = row[index]
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _strip_vmstat_headers(lines: Sequence[str]) -> List[Tuple[int, str]]:
    data_lines: List[Tuple[int, str]] = []
    for idx, line in enumerate(lines, start=1):
        normalized = line.lower()
        if LINUX_HEADER_PATTERN.match(normalized):
            continue
        if LINUX_COLUMN_PATTERN.search(normalized):
            continue
        if set(normalized) == {"-"}:
            continue
        data_lines.append((idx, line))
    return data_lines

