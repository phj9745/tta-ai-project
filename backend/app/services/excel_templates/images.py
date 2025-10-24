from __future__ import annotations

import re
from typing import Dict, Iterable, Sequence, Tuple

from .models import EMU_PER_PIXEL

__all__ = [
    "column_width_to_pixels",
    "row_height_to_pixels",
    "pixels_to_emu",
    "image_dimensions",
    "scale_image_dimensions",
    "normalized_image_filename",
]


def column_width_to_pixels(width: float) -> int:
    if width <= 0:
        return 64
    return max(1, int(round(width * 7.0 + 5)))


def row_height_to_pixels(height_points: float) -> float:
    if height_points <= 0:
        height_points = 15.0
    return height_points * 96.0 / 72.0


def pixels_to_emu(pixels: float) -> int:
    if pixels <= 0:
        pixels = 1
    return int(round(pixels * EMU_PER_PIXEL))


def image_dimensions(content: bytes) -> Tuple[int, int]:
    if len(content) >= 24 and content.startswith(b"\x89PNG\r\n\x1a\n"):
        width = int.from_bytes(content[16:20], "big")
        height = int.from_bytes(content[20:24], "big")
        return width, height

    if len(content) > 4 and content.startswith(b"\xff\xd8"):
        index = 2
        length = len(content)
        while index + 9 < length:
            if content[index] != 0xFF:
                break
            marker = content[index + 1]
            if marker == 0xD9:
                break
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                block_length = int.from_bytes(content[index + 2 : index + 4], "big")
                start = index + 4
                if start + 5 < length:
                    height = int.from_bytes(content[start + 1 : start + 3], "big")
                    width = int.from_bytes(content[start + 3 : start + 5], "big")
                    return width, height
                break
            block_length = int.from_bytes(content[index + 2 : index + 4], "big")
            if block_length <= 0:
                break
            index += 2 + block_length

    return 0, 0


def scale_image_dimensions(content: bytes, max_width_px: int) -> Tuple[int, int]:
    width, height = image_dimensions(content)
    if width <= 0 or height <= 0:
        width = max_width_px
        height = int(round(max_width_px * 0.75))
    scale = 1.0
    if width > max_width_px > 0:
        scale = max_width_px / float(width)
    scaled_width = max(1, int(round(width * scale)))
    scaled_height = max(1, int(round(height * scale)))
    return scaled_width, scaled_height


def normalized_image_filename(name: str, used: Dict[str, int]) -> str:
    base = (name or "defect-image").strip()
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base) or "defect-image"
    if "." not in base:
        base = f"{base}.png"
    root, dot, ext = base.rpartition(".")
    if not root:
        root = ext
        ext = "png"
    ext = ext.lower()
    key = f"{root}.{ext}" if dot else f"{root}.{ext}"
    count = used.get(key, 0)
    if count:
        key = f"{root}_{count}.{ext}"
    used[f"{root}.{ext}"] = count + 1
    return key
