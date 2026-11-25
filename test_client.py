#!/usr/bin/env python3
"""CLI tester. Usage: python test_client.py URL path/to/captcha.png [chars] [length]"""
from __future__ import annotations

import base64
import json
import sys

import requests

url = sys.argv[1].rstrip("/")
path = sys.argv[2]
chars = sys.argv[3] if len(sys.argv) > 3 else ""
length = sys.argv[4] if len(sys.argv) > 4 else ""

with open(path, "rb") as fh:
    raw = fh.read()

print("--- POST multipart ---")
with open(path, "rb") as fh:
    r = requests.post(f"{url}/api/image", files={"file": fh}, timeout=90)
print(r.status_code, r.text)

print("--- POST raw bytes ---")
r = requests.post(f"{url}/api/image", data=raw,
                  headers={"Content-Type": "application/octet-stream"}, timeout=90)
print(r.status_code, r.text)

print("--- POST JSON base64 ---")
r = requests.post(f"{url}/api/image", json={"image": base64.b64encode(raw).decode()}, timeout=90)
print(r.status_code, r.text)

print("--- GET base64 ---")
params = {"": base64.b64encode(raw).decode()}
if chars:
    params["chars"] = chars
if length:
    params["length"] = length
r = requests.get(f"{url}/api/image", params=params, timeout=90)
print(r.status_code, r.text)

print("--- health ---")
print(requests.get(f"{url}/health", timeout=30).text)
