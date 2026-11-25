from __future__ import annotations

import os
import shutil

import pytesseract
from PIL import Image


class TesseractEngine:
    name = "tesseract"

    def __init__(self) -> None:
        binary = os.environ.get("TESSERACT_BIN")
        if binary:
            if not os.path.exists(binary):
                raise RuntimeError(f"TESSERACT_BIN not found: {binary}")
            pytesseract.pytesseract.tesseract_cmd = binary
        elif not shutil.which("tesseract"):
            raise RuntimeError("tesseract binary not on PATH")

    def read(self, variants, allowed: str | None, psm: int) -> list:
        cfg = f"--oem 1 --psm {psm}"
        if allowed:
            safe = "".join(c for c in allowed if c not in " \"'\\")
            if safe:
                cfg += f" -c tessedit_char_whitelist={safe}"

        out: list[tuple[str, str, float]] = []
        for name, arr in variants:
            try:
                data = pytesseract.image_to_data(
                    Image.fromarray(arr),
                    config=cfg,
                    output_type=pytesseract.Output.DICT,
                )
            except Exception:  # noqa: BLE001
                out.append((name, "", 0.0))
                continue

            parts: list[str] = []
            confs: list[float] = []
            for i, token in enumerate(data.get("text", [])):
                token = (token or "").strip()
                if not token:
                    continue
                try:
                    conf = float(data["conf"][i])
                except (KeyError, TypeError, ValueError):
                    continue
                if conf < 0:
                    continue
                parts.append(token)
                confs.append(conf)

            text = "".join(parts)
            conf = (sum(confs) / len(confs) / 100.0) if confs else 0.0
            out.append((name, text, conf))
        return out
