"""Verification that SECRET_KEY is persisted rather than regenerated per process.

create_app() falls back to secrets.token_hex(32) when no config file supplies a
key. That fallback runs on every call, so two create_app() calls return
different keys -- which is exactly why every app restart and PythonAnywhere
reload invalidates all sessions. Once instance/config.py supplies a real key,
both calls must return the same one.

Never prints the key itself.

Run: server/.venv/Scripts/python.exe scripts/verify_secret_key.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app

CONFIG = os.path.join(SERVER, "instance", "config.py")

failures = []

present = os.path.exists(CONFIG)
if not present:
    failures.append(f"missing {CONFIG} -- the persisted key lives there")

first = create_app().config["SECRET_KEY"]
second = create_app().config["SECRET_KEY"]

if not first:
    failures.append("SECRET_KEY is empty")
if first != second:
    failures.append("SECRET_KEY differs between two create_app() calls -- "
                    "still using the per-process fallback")

print(f"instance/config.py present : {present}")
print(f"key stable across boots    : {first == second}")
print(f"key length                 : {len(first)}")

if failures:
    for line in failures:
        print("FAIL:", line)
    sys.exit(1)
print("PASS")
