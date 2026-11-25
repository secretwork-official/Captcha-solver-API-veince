from __future__ import annotations

import re

from .postprocess import clean, maybe_math


def _plausibility(text: str) -> float:
    if not text:
        return -1.5
    s = 0.0
    n = len(text)
    if 3 <= n <= 8:
        s += 0.6
    elif n > 8:
        s -= 0.4
    else:
        s -= 0.3
    if any(c.isalpha() for c in text) and any(c.isdigit() for c in text):
        s += 0.4
    if maybe_math(text) is not None:
        s += 1.2
    if re.search(r"(.)\1{3,}", text):
        s -= 0.2
    return s


def pick(reads, allowed: str | None, length: int | None) -> dict:
    buckets: dict[str, dict] = {}
    for variant, raw, conf in reads:
        t = clean(raw, allowed, length)
        if not t:
            continue
        b = buckets.setdefault(t, {"text": t, "votes": 0, "conf": 0.0, "methods": []})
        b["votes"] += 1
        b["conf"] = max(b["conf"], float(conf or 0.0))
        if variant not in b["methods"]:
            b["methods"].append(variant)

    if not buckets:
        return {"text": "", "confidence": 0.0, "method": None, "candidates": []}

    ranked = sorted(
        buckets.values(),
        key=lambda b: -(b["votes"] * 2.0 + b["conf"] + _plausibility(b["text"])),
    )
    best = ranked[0]
    agree = best["votes"] / max(1, len(reads))
    out = {
        "text": best["text"],
        "confidence": round(min(1.0, agree * 0.6 + best["conf"] * 0.4), 3),
        "method": best["methods"][0] if best["methods"] else None,
        "candidates": [b["text"] for b in ranked[:5]],
    }
    answer = maybe_math(best["text"])
    if answer is not None:
        out["math"] = {"expression": best["text"], "answer": answer}
    return out
