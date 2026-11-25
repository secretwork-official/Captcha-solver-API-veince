from __future__ import annotations

import os


class NoEngineError(RuntimeError):
    pass


_engine = None


def get_engine():
    global _engine
    if _engine is not None:
        return _engine

    choice = os.environ.get("ENGINE", "auto").lower()
    errors: list[str] = []

    if choice in ("auto", "ddddocr"):
        try:
            from .ddddocr_engine import DdddocrEngine

            _engine = DdddocrEngine()
            return _engine
        except Exception as exc:  # noqa: BLE001
            errors.append(f"ddddocr: {exc}")

    if choice in ("auto", "tesseract"):
        try:
            from .tesseract_engine import TesseractEngine

            _engine = TesseractEngine()
            return _engine
        except Exception as exc:  # noqa: BLE001
            errors.append(f"tesseract: {exc}")

    raise NoEngineError("; ".join(errors) or "no OCR engine available")
