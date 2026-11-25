from __future__ import annotations

import io

import ddddocr
from PIL import Image


class DdddocrEngine:
    name = "ddddocr"

    def __init__(self) -> None:
        self._ocr = ddddocr.DdddOcr(show_ad=False)

    def read(self, variants, allowed: str | None, psm: int) -> list:
        out: list[tuple[str, str, float]] = []
        for name, arr in variants:
            try:
                buf = io.BytesIO()
                Image.fromarray(arr).save(buf, format="PNG")
                text = self._ocr.classification(buf.getvalue()) or ""
            except Exception:  # noqa: BLE001
                text = ""
            out.append((name, text, 0.0))
        return out
