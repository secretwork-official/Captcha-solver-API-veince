from __future__ import annotations

import re

PRINTABLE = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
    "!@#$%^&*()-_=+[]{}<>?/\\|~`'\";:,. "
)

MATH_RE = re.compile(r"^(\d{1,3})\s*([+\-*/xX×÷])\s*(\d{1,3})\s*=?$")

CHAR_PRESETS = {
    "digits": "0123456789",
    "lower": "abcdefghijklmnopqrstuvwxyz",
    "upper": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "alpha": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    "alnum": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
    "all": PRINTABLE,
}


def clean(text: str, allowed: str | None, length: int | None) -> str:
    t = (text or "").strip()
    t = re.sub(r"\s+", "", t)
    if allowed:
        t = "".join(c for c in t if c in allowed)
    if length and len(t) > length:
        t = t[:length]
    return t


def maybe_math(text: str) -> int | None:
    m = MATH_RE.match((text or "").strip())
    if not m:
        return None
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op in "xX×*":
        return a * b
    if b == 0:
        return None
    return a // b
