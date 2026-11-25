from __future__ import annotations

import os

import cv2
import numpy as np

MAX_SIDE = 1400
MAX_VARIANTS = int(os.environ.get("MAX_VARIANTS", "6"))
UPSCALE_TARGET = 220


def decode_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("could not decode image (png/jpg/webp/bmp only)")
    h, w = img.shape[:2]
    if max(h, w) > MAX_SIDE:
        s = MAX_SIDE / max(h, w)
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return img


def _gray(img: np.ndarray) -> np.ndarray:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if float(np.mean(g)) < 127.0:
        g = cv2.bitwise_not(g)
    return g


def _upscale(g: np.ndarray) -> np.ndarray:
    h, w = g.shape[:2]
    scale = int(round(UPSCALE_TARGET / max(1, min(h, w))))
    scale = max(1, min(scale, 4))
    if scale == 1:
        return g
    return cv2.resize(g, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)


def _despeckle(g: np.ndarray) -> np.ndarray:
    return cv2.medianBlur(g, 3)


def _otsu(g: np.ndarray) -> np.ndarray:
    _, b = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    return b


def _adaptive(g: np.ndarray) -> np.ndarray:
    return cv2.adaptiveThreshold(
        g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 12
    )


def _open(b: np.ndarray) -> np.ndarray:
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    return cv2.morphologyEx(b, cv2.MORPH_OPEN, k)


def _strip_lines(b: np.ndarray) -> np.ndarray:
    inv = 255 - b
    h, w = b.shape[:2]
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(12, w // 12), 1))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(12, h // 12)))
    horiz = cv2.morphologyEx(inv, cv2.MORPH_OPEN, hk)
    vert = cv2.morphologyEx(inv, cv2.MORPH_OPEN, vk)
    cleaned = cv2.subtract(inv, cv2.add(horiz, vert))
    return 255 - cleaned


def _deskew(b: np.ndarray) -> np.ndarray:
    coords = cv2.findNonZero(255 - b)
    if coords is None:
        return b
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.6 or abs(angle) > 20:
        return b
    h, w = b.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
    return cv2.warpAffine(
        b, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def build_variants(img: np.ndarray) -> list[tuple[str, np.ndarray]]:
    g = _despeckle(_upscale(_gray(img)))
    plain = g
    otsu = _otsu(plain)

    out: list[tuple[str, np.ndarray]] = [
        ("plain", plain),
        ("otsu", otsu),
        ("otsu_open", _open(otsu)),
        ("adaptive", _adaptive(plain)),
        ("lines", _otsu(_strip_lines(otsu))),
        ("deskew", _deskew(otsu)),
    ]
    return out[: max(1, MAX_VARIANTS)]
