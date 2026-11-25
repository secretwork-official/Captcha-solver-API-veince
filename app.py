from __future__ import annotations

import base64
import binascii
import hashlib
import os
import re
import time
from dataclasses import dataclass
from urllib.parse import unquote

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from captcha_core import cache, ratelimit, scoring
from captcha_core.engines import NoEngineError, get_engine
from captcha_core.postprocess import CHAR_PRESETS
from captcha_core.preprocess import build_variants, decode_image

MAX_BYTES = int(os.environ.get("MAX_BYTES", "3500000"))
DATA_URI = re.compile(r"^data:image/[A-Za-z0-9.+-]+;base64,", re.I)
B64_JUNK = re.compile(r"[\r\n\t]+")

app = FastAPI(title="Captcha Solver API", version="1.0.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=86400,
)


@dataclass
class Opts:
    charset: str | None = None
    length: int | None = None
    psm: int = 7
    fmt: str = "json"


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _norm_b64(raw: str) -> str:
    s = unquote(raw).strip()
    s = DATA_URI.sub("", s)
    # Spaces must become '+' BEFORE any whitespace stripping, because an
    # un-encoded '+' arrives as a space in a query string.
    s = s.replace(" ", "+")
    s = B64_JUNK.sub("", s)
    s = s.replace("-", "+").replace("_", "/")
    return s + ("=" * ((-len(s)) % 4))


def _decode_b64(raw: str) -> bytes:
    if not raw or not raw.strip():
        raise ValueError("empty image")
    try:
        data = base64.b64decode(_norm_b64(raw), validate=False)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("invalid base64") from exc
    if not data:
        raise ValueError("invalid base64")
    return data


def _parse_opts(params) -> Opts:
    opts = Opts()
    preset = (params.get("chars") or params.get("whitelist") or "").strip()
    if preset:
        opts.charset = CHAR_PRESETS.get(
            preset.lower(), "".join(dict.fromkeys(preset))
        )
    raw_len = params.get("length")
    if raw_len and raw_len.isdigit():
        opts.length = max(1, min(20, int(raw_len)))
    raw_psm = params.get("psm")
    if raw_psm and raw_psm.isdigit() and 6 <= int(raw_psm) <= 13:
        opts.psm = int(raw_psm)
    if (params.get("format") or "").lower() in ("text", "plain"):
        opts.fmt = "text"
    return opts


def _respond(payload: dict, opts: Opts, status: int = 200):
    if opts.fmt == "text":
        body = payload.get("text", "")
        if status >= 400 and not body:
            body = payload.get("error", "error")
        return PlainTextResponse(body, status_code=status)
    return JSONResponse({"ok": status < 400, **payload}, status_code=status)


def _solve(data: bytes, opts: Opts) -> dict:
    if not data:
        raise ValueError("empty image")
    if len(data) > MAX_BYTES:
        raise ValueError(f"image too large (max {MAX_BYTES} bytes)")

    key = hashlib.sha256(
        b"|".join(
            (
                data,
                (opts.charset or "").encode(),
                str(opts.length).encode(),
                str(opts.psm).encode(),
            )
        )
    ).hexdigest()

    hit = cache.get(key)
    if hit is not None:
        return {**hit, "cached": True}

    img = decode_image(data)
    variants = build_variants(img)
    engine = get_engine()

    started = time.perf_counter()
    reads = engine.read(variants, opts.charset, opts.psm)
    elapsed = int((time.perf_counter() - started) * 1000)

    result = scoring.pick(reads, opts.charset, opts.length)
    result.update(engine=engine.name, variants=len(variants), ms=elapsed)
    cache.put(key, result)
    return result


def _limited(request: Request):
    ok, retry = ratelimit.check(_client_ip(request))
    if ok:
        return None
    return JSONResponse(
        {"ok": False, "error": "rate_limited", "retry_after": retry},
        status_code=429,
        headers={"Retry-After": str(retry)},
    )


@app.get("/health")
async def health():
    try:
        engine = get_engine()
    except NoEngineError as exc:
        return JSONResponse({"ok": False, "engine": None, "error": str(exc)}, 503)
    return {"ok": True, "engine": engine.name, "version": app.version}


@app.get("/api/image")
@app.get("/api/solve")
async def solve_get(request: Request):
    limited = _limited(request)
    if limited is not None:
        return limited

    params = request.query_params
    opts = _parse_opts(params)

    raw = request.url.query or ""
    encoded = ""
    if raw.startswith("="):
        encoded = raw[1:].split("&", 1)[0]
    if not encoded:
        for alias in ("image", "b64", "base64", "data", "img"):
            if params.get(alias):
                encoded = params[alias]
                break
    if not encoded:
        return _respond(
            {"error": "missing image. Use GET /api/image?=<base64> or ?image=<base64>"},
            opts,
            400,
        )

    try:
        return _respond(_solve(_decode_b64(encoded), opts), opts)
    except ValueError as exc:
        return _respond({"error": str(exc)}, opts, 400)
    except NoEngineError as exc:
        return _respond({"error": f"no OCR engine: {exc}"}, opts, 503)
    except Exception as exc:  # noqa: BLE001
        return _respond(
            {"error": f"solve failed: {type(exc).__name__}: {exc}"}, opts, 500
        )


@app.post("/api/image")
@app.post("/api/solve")
async def solve_post(request: Request):
    limited = _limited(request)
    if limited is not None:
        return limited

    opts = _parse_opts(request.query_params)
    ctype = (request.headers.get("content-type") or "").lower()

    try:
        if "multipart/form-data" in ctype:
            form = await request.form()
            data = b""
            for _, value in form.multi_items():
                if hasattr(value, "read"):
                    data = await value.read()
                    if data:
                        break
            if not data:
                return _respond({"error": "no file field in form"}, opts, 400)

        elif "application/json" in ctype:
            body = await request.json()
            data = b""
            for alias in ("image", "b64", "base64", "data"):
                if body.get(alias):
                    data = _decode_b64(str(body[alias]))
                    break
            if not data:
                return _respond({"error": "missing 'image' in JSON"}, opts, 400)

            merged = dict(request.query_params)
            for alias in ("chars", "whitelist", "length", "psm", "format"):
                if body.get(alias) is not None:
                    merged[alias] = str(body[alias])
            opts = _parse_opts(merged)

        else:
            data = await request.body()
            if not data:
                return _respond({"error": "empty body"}, opts, 400)
            if ctype.startswith("text/") or "base64" in ctype:
                data = _decode_b64(data.decode("utf-8", "ignore"))

        return _respond(_solve(data, opts), opts)

    except ValueError as exc:
        return _respond({"error": str(exc)}, opts, 400)
    except NoEngineError as exc:
        return _respond({"error": f"no OCR engine: {exc}"}, opts, 503)
    except Exception as exc:  # noqa: BLE001
        return _respond(
            {"error": f"solve failed: {type(exc).__name__}: {exc}"}, opts, 500
        )


@app.get("/")
async def root():
    return RedirectResponse("/ui/")


if os.path.isdir("public"):
    app.mount("/ui", StaticFiles(directory="public", html=True), name="ui")
