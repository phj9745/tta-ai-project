"""Video capture utilities for extracting configuration images.

This module implements the sensitive scene-change detection algorithm described
in the specification. The implementation keeps the original Python script's
behaviour while exposing a clean function API that can be reused from the
web application.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import math
from dataclasses import dataclass
from pathlib import Path
from typing import List

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim


TARGET_FPS = 10.0
LONG_SIDE = 1080
GRID_COLS = 32
GRID_ROWS = 32
SSIM_FULL_THRESHOLD = 0.95
BLOCK_THRESHOLD = 0.90
BLOCK_TRIGGER_COUNT = 3
EDGE_DIFF_PERCENT = 0.05
PERSIST_FRAMES = 2
MIN_GAP_SECONDS = 1.0
CURSOR_MIN = 8
CURSOR_MAX = 80
CURSOR_DILATE = 28
COVER_SKIP_RATIO = 0.5


@dataclass(slots=True)
class CaptureEvent:
    """Represents a row in the capture event log."""

    time_sec: float
    ssim_full: float | None
    min_block_ssim: float | None
    low_blocks: int | None
    edge_ratio: float | None
    phash_distance: int | None
    note: str
    filename: str


@dataclass(slots=True)
class CapturedImage:
    """Represents a saved image from the capture process."""

    path: Path
    filename: str
    time_sec: float
    is_start: bool


@dataclass(slots=True)
class CaptureResult:
    """Return value for the capture routine."""

    images: List[CapturedImage]
    events_csv: str


def _to_gray_small(frame: np.ndarray, *, long_side: int) -> tuple[np.ndarray, np.ndarray]:
    height, width = frame.shape[:2]
    scale = float(long_side) / float(max(height, width))
    if scale < 1.0:
        resized = cv2.resize(frame, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
    else:
        resized = frame
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    return blurred, resized


def _make_cursor_mask(
    prev_gray: np.ndarray,
    gray: np.ndarray,
    *,
    min_size: int,
    max_size: int,
    dilate_px: int,
) -> np.ndarray:
    mask = np.ones_like(gray, dtype=np.uint8)
    diff = cv2.absdiff(prev_gray, gray)

    thr0, _ = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    threshold = max(15, int(thr0 * 0.6))
    binary = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)[1]

    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    cursor_regions: List[tuple[int, int, int, int]] = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if width < min_size or height < min_size or width > max_size or height > max_size:
            continue
        aspect_ratio = width / float(height)
        if aspect_ratio < 0.4 or aspect_ratio > 2.5:
            continue
        cursor_regions.append((x, y, width, height))

    if cursor_regions:
        cursor_mask = np.zeros_like(mask, dtype=np.uint8)
        for x, y, width, height in cursor_regions:
            cv2.rectangle(cursor_mask, (x, y), (x + width, y + height), 1, -1)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_px, dilate_px))
        dilated = cv2.dilate(cursor_mask, kernel)
        mask = (mask & (1 - dilated)).astype(np.uint8)

    return mask


def _ssim_with_mask(prev_gray: np.ndarray, gray: np.ndarray, mask: np.ndarray) -> float:
    score, s_map = ssim(prev_gray, gray, data_range=255, full=True)
    valid = mask == 1
    if np.count_nonzero(valid) < 100:
        return float(score)
    return float(s_map[valid].mean())


def _block_ssim_with_mask(
    prev_gray: np.ndarray,
    gray: np.ndarray,
    mask: np.ndarray,
    *,
    grid_cols: int,
    grid_rows: int,
    block_threshold: float,
    cover_skip: float,
) -> tuple[float, int]:
    height, width = gray.shape[:2]
    block_width, block_height = width // grid_cols, height // grid_rows
    low_count = 0
    min_block_ssim = 1.0

    for row in range(grid_rows):
        for col in range(grid_cols):
            x0, y0 = col * block_width, row * block_height
            x1, y1 = x0 + block_width, y0 + block_height
            if block_width < 6 or block_height < 6:
                continue
            sub_mask = mask[y0:y1, x0:x1]
            if np.mean(sub_mask == 0) > cover_skip:
                continue
            score = ssim(prev_gray[y0:y1, x0:x1], gray[y0:y1, x0:x1], data_range=255)
            min_block_ssim = min(min_block_ssim, float(score))
            if score < block_threshold:
                low_count += 1

    return float(min_block_ssim), low_count


def _edge_change_ratio(prev_gray: np.ndarray, gray: np.ndarray, mask: np.ndarray) -> float:
    edges_prev = cv2.Canny(prev_gray, 60, 120) * mask
    edges_cur = cv2.Canny(gray, 60, 120) * mask
    count_prev = int(np.count_nonzero(edges_prev))
    count_cur = int(np.count_nonzero(edges_cur))
    if count_prev == 0:
        return 1.0 if count_cur > 0 else 0.0
    return (count_cur - count_prev) / float(count_prev)


def _phash(gray: np.ndarray, hash_size: int = 8, highfreq_factor: int = 4) -> np.ndarray:
    resized = cv2.resize(
        gray,
        (hash_size * highfreq_factor, hash_size * highfreq_factor),
        interpolation=cv2.INTER_AREA,
    ).astype(np.float32)
    dct = cv2.dct(resized)
    dct_low = dct[:hash_size, :hash_size]
    median = np.median(dct_low[1:, 1:])
    return (dct_low > median).flatten()


def _hamming(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.count_nonzero(a != b))


def _format_filename(prefix: str, suffix: str = "") -> str:
    sanitized = prefix.strip()
    if not sanitized:
        sanitized = "0"
    return f"{sanitized}{suffix}.png"


def capture_video_changes(source_path: Path, output_dir: Path) -> CaptureResult:
    """Extract scene changes from *source_path* into *output_dir*.

    Parameters
    ----------
    source_path:
        Path to the input video file.
    output_dir:
        Directory where PNG captures should be written.

    Returns
    -------
    CaptureResult
        Contains information about saved images and the CSV event log.
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(source_path))
    if not capture.isOpened():
        raise RuntimeError(f"동영상을 열 수 없습니다: {source_path}")

    src_fps = capture.get(cv2.CAP_PROP_FPS)
    if not src_fps or math.isclose(src_fps, 0.0):
        src_fps = 30.0
    step = max(1, int(round(src_fps / TARGET_FPS)))

    events: List[CaptureEvent] = []
    images: List[CapturedImage] = []

    last_gray: np.ndarray | None = None
    last_hash: np.ndarray | None = None
    pending = 0
    last_capture_time = -1e9
    frame_index = 0

    base_time = dt.datetime.fromtimestamp(source_path.stat().st_mtime, tz=dt.timezone.utc)
    name_counters: dict[str, int] = {}

    def build_filename(timestamp: float, *, suffix: str = "") -> str:
        capture_time = base_time + dt.timedelta(seconds=timestamp)
        capture_time = capture_time.replace(microsecond=0)
        label = capture_time.strftime("%Y-%m-%d %H %M %S")

        counter_key = f"{label}{suffix}"
        counter = name_counters.get(counter_key, 0)
        name_counters[counter_key] = counter + 1

        if counter:
            label = f"{label}_{counter:02d}"

        return _format_filename(label, suffix=suffix)

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break

            if frame_index % step != 0:
                frame_index += 1
                continue

            timestamp = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            gray_small, _ = _to_gray_small(frame, long_side=LONG_SIDE)

            if last_gray is None:
                filename = build_filename(timestamp, suffix="_start")
                file_path = output_dir / filename
                if not cv2.imwrite(str(file_path), frame):
                    raise RuntimeError(f"이미지를 저장하지 못했습니다: {file_path}")
                events.append(
                    CaptureEvent(
                        time_sec=timestamp,
                        ssim_full=None,
                        min_block_ssim=None,
                        low_blocks=None,
                        edge_ratio=None,
                        phash_distance=None,
                        note="start",
                        filename=filename,
                    )
                )
                images.append(
                    CapturedImage(path=file_path, filename=filename, time_sec=timestamp, is_start=True)
                )
                last_gray = gray_small
                last_hash = _phash(gray_small)
                frame_index += 1
                continue

            mask = _make_cursor_mask(
                last_gray,
                gray_small,
                min_size=CURSOR_MIN,
                max_size=CURSOR_MAX,
                dilate_px=CURSOR_DILATE,
            )

            ssim_full = _ssim_with_mask(last_gray, gray_small, mask)
            block_min, block_low = _block_ssim_with_mask(
                last_gray,
                gray_small,
                mask,
                grid_cols=GRID_COLS,
                grid_rows=GRID_ROWS,
                block_threshold=BLOCK_THRESHOLD,
                cover_skip=COVER_SKIP_RATIO,
            )
            edge_ratio = _edge_change_ratio(last_gray, gray_small, mask)

            current_hash = _phash(gray_small)
            phash_distance = _hamming(last_hash, current_hash) if last_hash is not None else 0

            changed = (
                ssim_full < SSIM_FULL_THRESHOLD
                or block_low >= BLOCK_TRIGGER_COUNT
                or edge_ratio >= EDGE_DIFF_PERCENT
            )

            if changed:
                pending += 1
            else:
                pending = 0

            should_capture = pending >= PERSIST_FRAMES and (timestamp - last_capture_time) >= MIN_GAP_SECONDS
            if should_capture:
                filename = build_filename(timestamp)
                file_path = output_dir / filename
                if not cv2.imwrite(str(file_path), frame):
                    raise RuntimeError(f"이미지를 저장하지 못했습니다: {file_path}")
                events.append(
                    CaptureEvent(
                        time_sec=timestamp,
                        ssim_full=ssim_full,
                        min_block_ssim=block_min,
                        low_blocks=block_low,
                        edge_ratio=edge_ratio,
                        phash_distance=phash_distance,
                        note="captured",
                        filename=filename,
                    )
                )
                images.append(
                    CapturedImage(path=file_path, filename=filename, time_sec=timestamp, is_start=False)
                )
                last_capture_time = timestamp
                last_gray = gray_small
                last_hash = current_hash
                pending = 0

            frame_index += 1
    finally:
        capture.release()

    if not images:
        raise RuntimeError("장면 전환을 감지하지 못했습니다. 동영상 내용을 확인해 주세요.")

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "time_sec",
            "ssim_full",
            "min_block_ssim",
            "low_blocks",
            "edge_ratio",
            "phash_dist",
            "note",
            "filename",
        ]
    )
    for event in events:
        writer.writerow(
            [
                f"{event.time_sec:.3f}",
                "" if event.ssim_full is None else f"{event.ssim_full:.4f}",
                "" if event.min_block_ssim is None else f"{event.min_block_ssim:.4f}",
                "" if event.low_blocks is None else event.low_blocks,
                "" if event.edge_ratio is None else f"{event.edge_ratio:.4f}",
                "" if event.phash_distance is None else event.phash_distance,
                event.note,
                event.filename,
            ]
        )

    return CaptureResult(images=images, events_csv=buffer.getvalue())


__all__ = [
    "CaptureEvent",
    "CapturedImage",
    "CaptureResult",
    "capture_video_changes",
]
