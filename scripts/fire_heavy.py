#!/usr/bin/env python3
"""Attach heavy_wall.js to the Grok app and fire inspect / p1m / p3m / g4.

# Sanitized research copy. Ops/account/card/egress specifics removed.

Usage: python3 fire_heavy.py <inspect|p1m|p3m|g4|fire> [arg]

Env:  MUMU_SERIAL  adb serial of the MuMu / Pixel device
      HOOK_JS      path to the compiled hook (default hooks/heavy_wall.compiled.js)
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import frida  # pip install frida-tools

SERIAL = os.environ.get("MUMU_SERIAL", "127.0.0.1:16384")
DEFAULT_JS = Path(__file__).resolve().parent.parent / "hooks" / "heavy_wall.compiled.js"
JS = os.environ.get("HOOK_JS", str(DEFAULT_JS))
CMD = sys.argv[1] if len(sys.argv) > 1 else "inspect"
ARG = sys.argv[2] if len(sys.argv) > 2 else ""
CMDS_WITH_ARG = {
    "destg4", "destg4p1m", "firstg4extras", "hopprofile", "hopxtid",
    "hopxtidonly", "hopoldidonly", "hopoldidtok", "hopprofilealign",
    "destfromlite",
}


def main() -> None:
    js = open(JS, encoding="utf-8").read()
    dm = frida.get_device_manager()
    dev = None
    for d in dm.enumerate_devices():
        if d.id == SERIAL or SERIAL in d.id:
            dev = d
            break
    if dev is None:
        try:
            dev = frida.get_device(SERIAL, timeout=8)
        except Exception:  # noqa: BLE001
            dev = frida.get_usb_device(timeout=8)
    pid = None
    for p in dev.enumerate_processes():
        if p.name in ("Grok", "ai.x.grok"):
            pid = p.pid
            break
    if pid is None:
        print(json.dumps({"ok": False, "err": "grok_not_running"}))
        sys.exit(2)
    session = dev.attach(pid)
    script = session.create_script(js)
    script.on("message", lambda m, d: print("MSG", m.get("payload") or m, flush=True))
    script.load()
    fn = getattr(script.exports_sync, CMD, None)
    if fn is None:
        print(json.dumps({"ok": False, "err": f"unknown_cmd:{CMD}"}))
        session.detach()
        sys.exit(2)
    box = fn(ARG) if CMD in CMDS_WITH_ARG and ARG else fn()
    print(json.dumps(box, ensure_ascii=False, default=str))
    time.sleep(1.2)
    session.detach()


if __name__ == "__main__":
    main()
