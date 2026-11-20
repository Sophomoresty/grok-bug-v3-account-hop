#!/usr/bin/env python3
# Sanitized research copy. Ops/account/card/egress specifics removed.
"""Trimmed fire / wall / GID core for the leftover hop chain.

Extracted from the original billing.py. Only the functions the hop chain needs
for its mechanism are kept:

  fire / _fire_run / compile_js / patch_gid / _gid_from_box
  dump_gid series (dump_gid, _dump_gid_frida, dump_gid_from_vending,
  pick_dump_gid) / gid_from_jwt / ensure_jwt_gid
  wait_wall / gate_heavy / wall_is_ready (+ wall_text, wall_dump_is_spinner,
  item_unavailable_text, oct25_item_wall, purchases, last_json, _uv_env)

Deliberately NOT shipped (see README): device.py (adb/uiautomator/OCR layer),
grpc_subs.py (gRPC GET client), fire_heavy.py (frida launcher), line_lock.py
(frida/file locks), ab_signin.py (browser sign-in), and the rest of billing.py
(pick_wall_card, verify_google_password, cancel_grok, ack_token,
prepare_hooks, get_subs, buy_* ...). Missing modules are stubbed with objects
that raise instead of returning fake results.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hop_oracle as ho  # noqa: E402


class _NotShipped:
    """Explicit stub for a module trimmed from this research copy (# ops removed)."""

    def __init__(self, name: str) -> None:
        self._name = name

    def __getattr__(self, attr: str):
        raise NotImplementedError(f"{self._name}.{attr}: not shipped in this research copy")


try:
    import device  # noqa: E402  (adb / uiautomator / OCR layer; not shipped)
except ImportError:
    device = _NotShipped("device")

try:
    import line_lock as ll  # noqa: E402  (frida-serial / flock helpers; not shipped)
except ImportError:
    ll = None

try:
    import grpc_subs  # noqa: E402  (gRPC GetSubscriptions / GetGoogleObfuscatedId client; not shipped)
except ImportError:
    grpc_subs = _NotShipped("grpc_subs")

SCRIPTS = Path(__file__).resolve().parent
# Research-copy layout: hooks/ is a sibling of scripts/ (original had scripts/hooks/).
HOOK_SRC = SCRIPTS.parent / "hooks"
HOOKS = Path(os.environ.get("GROK_HOOKS_CACHE") or "./work/hooks")
# fire_heavy.py (same sanitized launcher as the sibling repos) drives the frida attach.
FIRE = SCRIPTS / "fire_heavy.py"
DUMP_GID = HOOK_SRC / "dump_gid.js"
DUMP_GID_COMPILED = HOOKS / "dump_gid.compiled.js"
HEAVY_JS = HOOK_SRC / "heavy_wall.js"
FRIDA_COMPILE = os.environ.get("FRIDA_COMPILE") or shutil.which("frida-compile") or "frida-compile"
TODAY_RE = re.compile(r"starting today|today\s*\$|今天\s*\$", re.I)
FIRST_RE = re.compile(r"first charge will occur|将于.{0,40}收取", re.I)
GID_RE = re.compile(r"[0-9a-f]{64}")


def last_json(text: str) -> dict[str, Any]:
    for line in reversed((text or "").splitlines()):
        line = line.strip()
        if line.startswith("{") or line.startswith("["):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    return {"ok": False, "error": "no_json", "raw": (text or "")[-500:]}


def _uv_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["ANDROID_SERIAL"] = device.serial()
    env["ADB_SERVER_SOCKET"] = os.environ.get("ADB_SERVER_SOCKET") or "tcp:127.0.0.1:" + (
        os.environ.get("ADB_PORT") or "5037"
    )
    if extra:
        env.update(extra)
    return env


def _run_fire(
    argv: list[str], extra: dict[str, str], timeout: int
) -> subprocess.CompletedProcess[str]:
    """Run fire_heavy.py in its own process group.

    G1 2026-09-24 leftover-acct: subprocess.run TimeoutExpired left
    fire_heavy.py fromlite PID alive 2+ min, screenshot still Ask
    anything, next attach hung. Kill the group, return fire_timeout.
    """
    p = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(HOOKS),
        env=_uv_env(extra),
        start_new_session=True,
    )
    try:
        stdout, stderr = p.communicate(timeout=timeout)
        return subprocess.CompletedProcess(argv, p.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            p.kill()
        except OSError:
            pass
        try:
            stdout, stderr = p.communicate(timeout=3)
        except Exception:
            stdout, stderr = "", ""
        err = ((stderr or "") + "\n" + (stdout or "") + "\nfire_timeout")[-800:]
        return subprocess.CompletedProcess(argv, -9, stdout or "", err)


def fire(cmd: str, hook: str | None = None, timeout: int = 70, arg: str | None = None) -> dict[str, Any]:
    if cmd == "g4":
        if ll is None:
            raise NotImplementedError("line_lock not shipped in this research copy (# ops removed)")
        with ll.frida_serial("g4"):
            return _fire_run(cmd, hook=hook, timeout=timeout, arg=arg)
    return _fire_run(cmd, hook=hook, timeout=timeout, arg=arg)


def _fire_run(cmd: str, hook: str | None = None, timeout: int = 70, arg: str | None = None) -> dict[str, Any]:
    import hop as hopmod  # noqa: PLC0415

    # G2 2026-10-08 acct: pidof frida-server empty, fire p1m returned
    # in 0.33s with no JSON while Ask stayed up. inspect() already starts
    # /data/local/tmp/frida-server; leftover lite/fromlite/g4 must too.
    hopmod.ensure_frida_server()
    if not device.grok_pid():
        device.shell("am start -n ai.x.grok/.main.GrokActivity")
        time.sleep(2.0)
        if not device.grok_pid():
            return {"ok": False, "err": "grok_not_running"}
    extra = {}
    if hook:
        extra["HOOK_JS"] = hook
    argv = ["uv", "run", "--with", "frida-tools", "python3", str(FIRE), cmd]
    if arg:
        argv.append(arg)
    r = _run_fire(argv, extra, timeout)
    err = (r.stderr or "") + "\n" + (r.stdout or "")
    if r.returncode != 0 and ("timeout was reached" in err or "TransportError" in err):
        device.shell("am force-stop ai.x.grok")
        time.sleep(1.2)
        device.shell("am start -n ai.x.grok/.main.GrokActivity")
        time.sleep(3.0)
        r = _run_fire(argv, extra, timeout)
        err = (r.stderr or "") + "\n" + (r.stdout or "")
    box = last_json(err)
    box["_rc"] = r.returncode
    if r.returncode == -9 or "fire_timeout" in err:
        box.setdefault("ok", False)
        box.setdefault("err", "fire_timeout")
        box["cmd"] = cmd
        return box
    if r.returncode != 0 and box.get("ok") is not False:
        box.setdefault("ok", False)
        box.setdefault("error", err[-240:])
    return box


def compile_js(src: Path, dest: Path) -> dict[str, Any]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [str(FRIDA_COMPILE), str(src), "-o", str(dest)],
        capture_output=True,
        text=True,
        timeout=40,
        cwd=str(HOOKS),
        check=False,
    )
    ok = dest.exists() and dest.stat().st_size > 100 and r.returncode == 0
    return {"ok": ok, "src": str(src), "dest": str(dest), "stderr": (r.stderr or "")[-200:]}


def patch_gid(src: Path, dest: Path, gid: str, lite_token: str = "") -> None:
    text = src.read_text(encoding="utf-8")
    text = re.sub(r"var GID = '[0-9a-f]{64}'", f"var GID = '{gid}'", text)
    text = re.sub(r"var gid = '[0-9a-f]{64}'", f"var gid = '{gid}'", text)
    if "FALLBACK_LITE_TOKEN" in text:
        tok = re.sub(r"[^A-Za-z0-9._\-]", "", str(lite_token or ""))
        text = re.sub(r"var FALLBACK_LITE_TOKEN = '[^']*'", f"var FALLBACK_LITE_TOKEN = '{tok}'", text)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")


def _gid_from_box(box: dict[str, Any]) -> str:
    gid = str(box.get("gid") or "")
    if GID_RE.fullmatch(gid):
        return gid
    blob = json.dumps(box, default=str)
    m = re.search(r"obfuscated(?:Account)?Id[=:]([0-9a-f]{64})", blob, re.I)
    if m:
        return m.group(1)
    m = GID_RE.search(blob)
    return m.group(0) if m else ""


def dump_gid_from_vending() -> dict[str, Any]:
    # adb shell is already root. Wrapping sqlite3 returns an empty string.
    raw = device.shell(
        "sqlite3 /data/data/com.android.vending/databases/library.db "
        "\"SELECT inapp_purchase_data FROM ownership WHERE doc_id LIKE '%grok%' "
        "ORDER BY purchase_time DESC;\"",
        timeout=8,
    )
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        gid = ""
        sku = ""
        order = ""
        try:
            jo = json.loads(line)
            gid = str(jo.get("obfuscatedAccountId") or "")
            sku = str(jo.get("productId") or "")
            order = str(jo.get("orderId") or "")
        except json.JSONDecodeError:
            m = re.search(r'"obfuscatedAccountId"\s*:\s*"([0-9a-f]{64})"', line)
            gid = m.group(1) if m else ""
            sm = re.search(r'"productId"\s*:\s*"([^"]+)"', line)
            sku = sm.group(1) if sm else ""
        if GID_RE.fullmatch(gid):
            return {"ok": True, "gid": gid, "from": "vending", "sku": sku, "order": order}
    return {"ok": False, "err": "no_vending_gid"}


def gid_from_jwt(jwt: str) -> dict[str, Any]:
    """64-hex GetGoogleObfuscatedId from SSO JWT. No dest Pixel Grok login."""
    if not str(jwt or "").startswith("eyJ"):
        return {"ok": False, "err": "no_jwt", "from": "jwt_grpc"}
    box = grpc_subs.get_gid_grpc(jwt)
    gid = str(box.get("gid") or "")
    if GID_RE.fullmatch(gid) and box.get("ok"):
        return {
            "ok": True,
            "gid": gid,
            "from": "jwt_grpc",
            "http": box.get("http"),
            "grpc_status": box.get("grpc_status"),
        }
    return {
        "ok": False,
        "err": box.get("error") or "no_jwt_gid",
        "from": "jwt_grpc",
        "http": box.get("http"),
        "grpc_status": box.get("grpc_status"),
    }


def ensure_jwt_gid(jwt: str, email: str = "") -> dict[str, Any]:
    """Hop dest path: jwt grpc GID, skip Grok login. Stale jwt -> sign-in retry.

    # ops removed: the stale-jwt refresh path used ab_signin.py (browser
    # sign-in), which is not shipped. When the jwt is stale and email is set,
    # this research copy returns err=ab_signin_not_shipped instead of
    # refreshing.
    """
    box = gid_from_jwt(jwt)
    if box.get("ok") and GID_RE.fullmatch(str(box.get("gid") or "")):
        box["jwt"] = jwt
        return box
    if not str(email or "").strip():
        return box
    try:
        import ab_signin  # noqa: PLC0415  (browser sign-in; not shipped)
    except ImportError:
        return {"ok": False, "err": "ab_signin_not_shipped", "from": "jwt_grpc"}
    signed = ab_signin.signin(str(email).strip().lower())
    if not signed.get("ok"):
        return {
            "ok": False,
            "err": "ab_signin",
            "from": "jwt_grpc",
            "signin": {k: signed.get(k) for k in ("ok", "err", "http") if k in signed},
        }
    jwt2 = str(signed.get("sso") or "")
    box = gid_from_jwt(jwt2)
    box["jwt"] = jwt2
    box["refreshed"] = True
    box["userId"] = signed.get("userId")
    box["sessionId"] = signed.get("sessionId")
    return box


def pick_dump_gid(
    vending: dict[str, Any] | None,
    inspect: dict[str, Any] | None,
    *,
    allow_vending: bool,
) -> dict[str, Any]:
    """Empty-library Lite must not reuse another Google's grok row in vending."""
    vend = vending or {}
    vg = str(vend.get("gid") or "")
    if allow_vending and vend.get("ok") and GID_RE.fullmatch(vg):
        out = dict(vend)
        out.setdefault("from", "vending")
        return out
    insp = inspect or {}
    ig = str(insp.get("gid") or "")
    if insp.get("ok") and GID_RE.fullmatch(ig):
        return insp
    return {"ok": False, "err": "no_gid"}


def dump_gid(*, allow_vending: bool = False) -> dict[str, Any]:
    if allow_vending:
        vend = dump_gid_from_vending()
        if vend.get("ok"):
            return vend
    if ll is None:
        raise NotImplementedError("line_lock not shipped in this research copy (# ops removed)")
    with ll.frida_dump():
        return _dump_gid_frida()


def _dump_gid_frida() -> dict[str, Any]:
    if ll is None:
        raise NotImplementedError("line_lock not shipped in this research copy (# ops removed)")
    with ll.flock("frida-dump-compile.lock"):
        # frida-compile rejects an entrypoint outside the hooks cache dir.
        staged = HOOKS / "dump_gid.js"
        src = DUMP_GID.read_text(encoding="utf-8")
        stale = (not staged.exists()) or staged.read_text(encoding="utf-8") != src
        if stale or not DUMP_GID_COMPILED.exists():
            staged.write_text(src, encoding="utf-8")
            compiled = compile_js(staged, DUMP_GID_COMPILED)
            if not compiled.get("ok"):
                return {"ok": False, "err": "dump_gid_compile", "stderr": compiled.get("stderr")}
    if not device.grok_pid():
        device.shell("am start -n ai.x.grok/.main.GrokActivity")
        time.sleep(2.8)
    else:
        time.sleep(0.6)
    box: dict[str, Any] = {"ok": False}
    try:
        r = subprocess.run(
            [
                "uv",
                "run",
                "--with",
                "frida-tools",
                "python3",
                "-c",
                (
                    "import frida,os,json,sys;"
                    "s=os.environ['ANDROID_SERIAL'];"
                    "js=open(os.environ['JS']).read();"
                    "dm=frida.get_device_manager();"
                    "dev=next((d for d in dm.enumerate_devices() if s in d.id), None) or frida.get_device(s, timeout=8);"
                    "pid=next((p.pid for p in dev.enumerate_processes() if p.name in ('Grok','ai.x.grok')), None);"
                    "print(json.dumps({'ok':False,'err':'grok_not_running'})) if pid is None else None;"
                    "sys.exit(2) if pid is None else None;"
                    "sess=dev.attach(pid); sc=sess.create_script(js); sc.load();"
                    "box=sc.exports_sync.inspect(); print(json.dumps(box, default=str)); sess.detach()"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=22,
            env=_uv_env({"JS": str(DUMP_GID_COMPILED)}),
            check=False,
        )
        box = last_json((r.stdout or "") + "\n" + (r.stderr or ""))
    except subprocess.TimeoutExpired:
        box = {"ok": False, "err": "dump_gid_timeout"}
    gid = _gid_from_box(box)
    if not GID_RE.fullmatch(gid):
        compiled = HOOKS / "heavy_wall.compiled.js"
        hook = str(compiled) if compiled.exists() else None
        insp = fire("inspect", hook=hook, timeout=35)
        gid = _gid_from_box(insp)
        if not GID_RE.fullmatch(gid):
            for p in purchases(insp):
                obf = str(p.get("obfuscatedAccountId") or "")
                if GID_RE.fullmatch(obf):
                    gid = obf
                    break
        box = {"ok": bool(GID_RE.fullmatch(gid)), "from": "inspect", "inspect": {"ok": insp.get("ok")}, "err": box.get("err")}
    box["gid"] = gid
    box["ok"] = bool(GID_RE.fullmatch(gid))
    return box


def purchases(box: dict[str, Any]) -> list[dict[str, Any]]:
    rows = box.get("purchases") if isinstance(box, dict) else None
    return list(rows) if isinstance(rows, list) else []


def wall_text(name: str = "wall.png") -> str:
    dump = device.ui_blob() or ""
    ocr = device.screen_text(name) or ""
    return f"{dump}\n{ocr}"


def wall_dump_is_spinner(raw: str, ocr: str = "") -> bool:
    """Play billing sheet is the ProgressBar spinner, not a Subscribe wall.

    G2 2026-10-08 leftover-acct: dump with android:id/progress,
    OCR garbage. Keep waiting. Do not treat OCR garbage as the wall.
    """
    blob = f"{raw or ''}\n{ocr or ''}".lower()
    if any(
        k in blob
        for k in (
            "subscribe",
            "supergrok",
            "add a payment",
            "starting today",
            "mastercard-",
            "visa-",
        )
    ):
        return False
    return "android:id/progress" in (raw or "") or "progressbar" in blob


_OCT25_2026 = re.compile(r"oct\s*25,?\s*2026", re.I)
_INTRO_99 = re.compile(r"(?<![\d.])\$99\.99")


def item_unavailable_text(text: str) -> bool:
    """Acquire dialog after Subscribe. Wall-left is not a paid upgrade.

    G3 2026-09-26 gate-sub-after.png: deferred Oct 25 $299.99/month wall,
    dump 10449 bytes, Error The item you requested is not available for
    purchase. cmd_sub treated the dialog as fromlite_subscribe ok.
    """
    return "the item you requested is not available" in (text or "").lower()


def oct25_item_wall(text: str) -> bool:
    """fromlite intro that Subscribe turns into item.

    G3/G4 2026-09-26 hold_fromlite.png: Starting Oct 25, 2026 $99.99,
    first charge Oct 25, no Today $. <last4-list> all returned item.
    A $299.99-only g4 wall is not this.
    """
    raw = text or ""
    if not _OCT25_2026.search(raw):
        return False
    if _INTRO_99.search(raw):
        return True
    # G4 2026-09-26 hold_fromlite.png after skipping may2026: same Oct 25
    # first-charge date, priced as a 3-month $299.99 period. Subscribe item.
    low = raw.lower()
    return "3-month" in low and "$299.99" in raw


def gate_heavy(text: str) -> dict[str, Any]:
    low = text.lower()
    kind = ho.skipg4_wall_kind(text)
    # leftover g4: $299.99 Starting Oct + first charge later is deferred $0 today.
    # skipg4 full-price restore has no first-charge copy.
    if kind == "CHARGE_FULL" and not FIRST_RE.search(text):
        return {"ok": False, "kind": "CHARGE_FULL", "text": text[:240]}
    if oct25_item_wall(text):
        return {"ok": False, "kind": "oct25_item_wall", "text": text[:240]}
    if "unable to change your subscription plan" in low:
        return {"ok": False, "kind": "unable_change", "text": text[:240]}
    if TODAY_RE.search(text):
        if "today $0" in low or "today $0.00" in low:
            return {"ok": True, "kind": "deferred", "text": text[:240]}
        if "9.99" in low and "lite" in low:
            return {"ok": False, "kind": "wrong_sku_lite", "text": text[:240]}
        if any(k in low for k in ("99.99", "299.99", "$99", "$299", "today $")):
            return {"ok": False, "kind": "CHARGE_FULL", "text": text[:240]}
    if FIRST_RE.search(text) and not TODAY_RE.search(text):
        return {"ok": True, "kind": "deferred", "text": text[:240]}
    if FIRST_RE.search(text) and "today" not in low:
        return {"ok": True, "kind": "deferred", "text": text[:240]}
    return {"ok": False, "kind": "unknown", "text": text[:240]}


def wall_is_ready(text: str) -> bool:
    """Subscribe wall is up. FLAG_SECURE dump may omit Subscribe; Starting Oct is deferred Heavy.

    Starting Oct $299 without first-charge / Today $ is not ready: hop-2 acct
    2026-09-20 hop2-skip2.png already showed Your first charge will occur on
    Oct 18 while wait_wall OCR truncated before that line and skipg4_once
    classified CHARGE_FULL.
    """
    low = (text or "").lower()
    if not ("supergrok" in low or "grok ai" in low or "grok al" in low):
        return False
    if "starting oct" in low and ("299.99" in low or "$299" in low):
        if ho.skipg4_has_first_charge(text) or "today $0" in low or "today $299" in low or "starting today" in low:
            return True
        return False
    return bool(
        "subscribe" in low
        or TODAY_RE.search(text or "")
        or FIRST_RE.search(text or "")
    )


def wait_wall(timeout: float = 40.0) -> str:
    end = time.time() + timeout
    text = ""
    empty_n = 0
    while time.time() < end:
        foc = device.play_billing_focus()
        raw = device.ui_blob() or ""
        if not raw.strip():
            empty_n += 1
            # 2026-10-05 G1 leftover: lite_wall 0B dumps after Visa-<last4> listed
            # killed the desk (hold-lite.png 0). OCR instead of looping dump.
            if empty_n >= 2:
                return device.screen_text("wall-empty.png") or ""
            time.sleep(0.8)
            continue
        empty_n = 0
        blob = raw.lower()
        if "no internet" in blob:
            device.recover_play_no_internet()
            time.sleep(0.8)
            continue
        if "something went wrong on our end" in blob:
            # 2026-09-29 hop-4 acct: same Got it sheet for the whole 40s.
            return blob
        if wall_dump_is_spinner(raw):
            # G2 2026-10-08: 6659 ProgressBar. Extra dumps starve the
            # sheet. Sleep, do not wall_text, do not return OCR garbage.
            time.sleep(1.5)
            continue
        if foc or "subscribe" in blob or "supergrok" in blob or "want to pay with cash" in blob:
            text = wall_text("wall.png")
            low = text.lower()
            if "something went wrong on our end" in low:
                return text
            if "no internet" in low:
                device.recover_play_no_internet()
                time.sleep(0.8)
                continue
            if "want to pay with cash" in low:
                # G1 2026-09-19 leftover-acct need-bind.png:
                # cash overlay sat on Add card until OK. Dismiss, keep wall.
                device.tap_text("OK")
                time.sleep(0.4)
                continue
            if "loading" in low and "subscribe" not in low and not TODAY_RE.search(text) and not FIRST_RE.search(text):
                time.sleep(0.8)
                continue
            if "unable to change your subscription plan" in low:
                return text
            # G1 2026-09-19 leftover-acct wall.png: Add payment
            # method OCR repeated ~40s. Return so agent bind from the wall.
            if "start by adding a payment method" in low or "add a payment method" in low:
                return text
            # G3 2026-09-25 g4: OCR repeated "Turn on backup payment methods?"
            # for the whole 40s wait. Return so the caller BACK. Do not Turn on.
            if "turn on backup payment methods" in low:
                return text
            if wall_is_ready(text):
                return text
        time.sleep(0.6)
    return wall_text("wall-late.png")
