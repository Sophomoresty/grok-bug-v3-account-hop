#!/usr/bin/env python3
# Sanitized research copy. Ops/account/card/egress specifics removed.
"""skipg4 wash leftover then destg4 hop N dests. Abort on Today $. No POST sync."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault(
    "ADB_SERVER_SOCKET", "tcp:127.0.0.1:" + (os.environ.get("ADB_PORT") or "5037")
)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import billing_core as billing  # noqa: E402
import hop_oracle as ho  # noqa: E402

# billing.py surface beyond billing_core.py is trimmed from this research copy.
for _name in (
    "pick_wall_card",
    "tap_subscribe",
    "verify_google_password",
    "dismiss_pay_sheets",
    "prepare_hooks",
    "cancel_grok",
    "get_subs",
    "inspect",
):
    if not hasattr(billing, _name):
        setattr(
            billing,
            _name,
            lambda *a, _n=_name, **k: (_ for _ in ()).throw(
                NotImplementedError(f"billing.{_n}: not shipped in this research copy")
            ),
        )

class _DeviceStub:
    def __getattr__(self, attr: str):
        raise NotImplementedError(f"device.{attr}: not shipped in this research copy")


try:
    import device  # noqa: E402  (adb / uiautomator / OCR layer; not shipped)
except ImportError:
    device = _DeviceStub()  # research-copy stub; fails loud on call


# ---- # ops removed: account-pool / sold-ledger (grok_hotmail_pool) is not
# ---- shipped. Hop records and dest JWT lookups go through local JSON stubs
# ---- under ./work/ instead of the pool sqlite.
WORK = Path(os.environ.get("HOP_WORK") or "./work/hop-chain")
WORK.mkdir(parents=True, exist_ok=True)
HOP_LOG = WORK / "hop_dest_log.json"


def _log_write(rec: dict) -> None:
    HOP_LOG.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if HOP_LOG.exists():
        try:
            rows = json.loads(HOP_LOG.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            rows = []
    if not isinstance(rows, list):
        rows = []
    rows.append(rec)
    HOP_LOG.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def ingest_hop_dest(dest: str, prev: str, claimed_by: str = "leftover-hop") -> dict:
    """# ops removed: pool ingest replaced by a local JSON record."""
    _log_write(
        {
            "dest": dest,
            "from": prev,
            "claimed_by": claimed_by,
            "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )
    return {"ok": True, "stub": "local_json"}


GOOGLE_PW = os.environ.get("GOOGLE_PW") or os.environ.get("HOP_GOOGLE_PW") or ""
DESTS = [e.strip() for e in os.environ.get("HOP_DEST", "").split(",") if e.strip()]
OLD = os.environ.get("HOP_OLD") or ""
# ops removed: no default want/avoid last4. Card specifics come from env only.
WANT_LAST4 = os.environ.get("HOP_PAY_LAST4") or ""
AVOID_LAST4 = os.environ.get("HOP_AVOID_LAST4") or ""
GID_RE = re.compile(r"[0-9a-f]{64}")


def pick_wall_card(want: str, avoid: str) -> dict:
    """Subscribe 墙必须是 want last4. want missing 禁止 keep leftover 拒卡."""
    box = billing.pick_wall_card(want, avoid)
    log("wall_card", {k: box.get(k) for k in ("ok", "kind", "last4", "shown")})
    return box


def dismiss_play_points() -> None:
    blob = (device.ui_blob() or "") + "\n" + (device.screen_text("points.png") or "")
    low = blob.lower()
    if "play points" not in low and "not now" not in low:
        return
    if device.tap_text("Not now", "Not Now"):
        time.sleep(0.8)
        return
    x, y = ho.play_points_not_now_xy(blob)
    device.su_tap(x, y, 0.8)
    time.sleep(0.8)


def dismiss_after_skipg4() -> str:
    """Auth radio then Play Points. Coords from 2026-09-18 Grok-2/4 shots."""
    blob = (device.ui_blob() or "") + "\n" + (device.screen_text("skip-overlay.png") or "")
    kind = ho.after_skipg4_overlay(blob)
    if kind == "play_server_error":
        # 2026-09-29 hop-4 acct-after-skip.png then acct-after-gotit.png.
        device.tap_text("Got it") or device.back(0.6)
        blob = (device.ui_blob() or "") + "\n" + (device.screen_text("skip-overlay-gotit.png") or "")
        kind = ho.after_skipg4_overlay(blob)
    if kind == "dferh_01":
        # 2026-09-29 hop-4 acct after.png. OK [63,1789][1017,1884].
        # hop-929 hop-1 destg4 cancel.png: DF-DFERH-01 button is
        # See current subscriptions, not OK. tap OK 540,1836 missed it
        # and cancel2 kind None left dest cap False (GET True False).
        device.tap_text("See current subscriptions") or device.tap_text("OK") or device.tap(540, 1836, 0.5)
        blob = (device.ui_blob() or "") + "\n" + (device.screen_text("skip-overlay-dferh.png") or "")
        kind = ho.after_skipg4_overlay(blob)
    if kind == "auth_no_thanks":
        device.su_tap(540, 1639, 0.8)
        device.su_tap(540, 1836, 1.0)
        blob = (device.ui_blob() or "") + "\n" + (device.screen_text("skip-overlay2.png") or "")
        kind = ho.after_skipg4_overlay(blob)
    if kind == "play_points_not_now" or "not now" in blob.lower():
        dismiss_play_points()
        blob = (device.ui_blob() or "") + "\n" + (device.screen_text("skip-overlay3.png") or "")
        kind = ho.after_skipg4_overlay(blob)
    if kind == "backup_add_no_thanks":
        # 2026-09-20 hop-3 acct hop3-washed.png. Never Add leftover Visa.
        device.tap_text("No thanks") or device.tap_text("No, thanks")
        blob = (device.ui_blob() or "") + "\n" + (device.screen_text("skip-overlay3b.png") or "")
        kind = ho.after_skipg4_overlay(blob)
    if kind == "backup_back":
        # 2026-09-19 hop-4 acct hop4-after-skipg4.png. Never Turn on.
        device.back(0.6)
        blob = (device.ui_blob() or "") + "\n" + (device.screen_text("skip-overlay4.png") or "")
        kind = ho.after_skipg4_overlay(blob)
    if kind == "playfest_not_now":
        # 2026-10-07 hop2 skip-overlay3.png: left pill only. Never the right pill.
        device.tap_text("Not now") or device.tap(270, 1780, 0.8)
        blob = (device.ui_blob() or "") + "\n" + (device.screen_text("skip-overlay-fest.png") or "")
        kind = ho.after_skipg4_overlay(blob)
    return kind


def log(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    with (WORK / "hop.log").open("a", encoding="utf-8") as fh:
        fh.write(time.strftime("%H:%M:%S ") + line + "\n")


def open_hotmail_sqlite():
    """# ops removed: the real account pool is not shipped.

    Stand-in: an in-memory sqlite with the same `accounts` schema,
    seeded from the HOP_JWT_MAP env var (JSON {email: jwt}).
    """
    import sqlite3

    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute(
        "CREATE TABLE accounts (email TEXT PRIMARY KEY, sso_jwt TEXT, has_sso INTEGER DEFAULT 0, notes TEXT DEFAULT '', updated_at TEXT)"
    )
    seed = json.loads(os.environ.get("HOP_JWT_MAP", "{}"))
    for mail, tok in seed.items():
        con.execute("INSERT INTO accounts (email, sso_jwt, has_sso) VALUES (?, ?, 1)", (mail, tok))
    con.commit()
    return con


def jwt_of(email: str) -> str:
    dest = str(email or "").strip().lower()
    con = open_hotmail_sqlite()
    try:
        row = con.execute("SELECT sso_jwt FROM accounts WHERE lower(email)=?", (dest,)).fetchone()
    finally:
        con.close()
    if row and row[0]:
        return str(row[0])
    env_dest = (os.environ.get("HOP_DEST") or "").split(",")
    if dest and dest in [e.strip().lower() for e in env_dest if e.strip()]:
        return os.environ.get("SSO_JWT") or ""
    if dest and dest == (os.environ.get("HOP_OLD") or "").strip().lower():
        return os.environ.get("SSO_JWT") or ""
    return ""


def sso_other_holder(email: str, jwt: str = "") -> str:
    token = str(jwt or jwt_of(email) or "").strip()
    dest = str(email or "").strip().lower()
    if not dest or not token.startswith("eyJ"):
        return ""
    con = open_hotmail_sqlite()
    try:
        row = con.execute(
            "SELECT email FROM accounts WHERE sso_jwt=? AND lower(email)!=? LIMIT 1",
            (token, dest),
        ).fetchone()
    finally:
        con.close()
    return str(row[0] or "") if row else ""


def get_rows(email: str) -> dict:
    jwt = jwt_of(email)
    other = sso_other_holder(email, jwt)
    if other:
        log("dest_sso_shared", email, "also", other)
        return {"ok": False, "rows": [], "error": "dest_sso_shared", "other": other}
    return billing.get_subs(jwt)


def summarize(gs: dict) -> list[dict]:
    out = []
    for row in gs.get("rows") or []:
        g = row.get("google") or {}
        st = str(row.get("status") or "")
        out.append(
            {
                "sku": g.get("productId") or row.get("sku"),
                "status": st,
                "cap": row.get("cancelAtPeriodEnd"),
                "end": row.get("billingPeriodEnd") or g.get("expiryTime"),
                "create": row.get("createTime"),
                "active": st.endswith("STATUS_ACTIVE") or st == "ACTIVE",
            }
        )
    return out


def _library_sqlite(sql: str) -> str:
    """Read Play library.db. This MuMu adb shell is uid 0 and the su wrapper exits 1.

    2026-10-05 acct play-acct: stdin `select count(*) from ownership` returned
    11 and the su wrapper exited 1 with an empty body. sync_play_library
    treated that as no grok.ultra row and pm-cleared vending, then sat on
    Play onboard, even though the same db already held tok <tok8>.
    """
    text = sql if sql.endswith("\n") else sql + "\n"
    return (
        device.shell(
            "sqlite3 /data/data/com.android.vending/databases/library.db",
            input_text=text,
        )
        or ""
    ).strip()


def _library_ultra_json(current_google: str = "") -> str:
    return _library_sqlite(
        ho.library_ultra_select_sql(column="inapp_purchase_data", current_google=current_google)
    )


def _library_ultra_owner(current_google: str = "") -> str:
    return _library_sqlite(
        ho.library_ultra_select_sql(column="account", current_google=current_google)
    )


def library_ultra_fire_row() -> tuple[dict | None, str]:
    """Current Play Google's grok.ultra row. Do not log the token."""
    goog = [x.lower() for x in device.google_accounts()]
    current = goog[0] if goog else ""
    return ho.library_ultra_from_blob(_library_ultra_json(current))


def sync_play_library(timeout: float = 45.0) -> dict:
    """Clone 盘的 library.db 会留着源机 Google. inspect 空时 pm clear vending 再拉当前号."""
    goog = [x.lower() for x in device.google_accounts()]
    current = goog[0] if goog else ""
    existing = _library_ultra_json(current)
    owner = _library_ultra_owner(current)
    if ho.library_ultra_is_current(owner=owner, current_google=current, blob=existing):
        return {"ok": True, "already": True, "owner": owner}
    log("library_sync pm-clear vending")
    busy_taps = 0
    relaunch = 0
    device.shell("am force-stop com.android.vending")
    device.shell("am force-stop ai.x.grok")
    device.shell("pm clear com.android.vending")
    time.sleep(1.0)
    device.shell(
        "am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER "
        "-n com.android.vending/com.android.vending.AssetBrowserActivity"
    )
    time.sleep(3.0)
    end = time.time() + timeout
    while time.time() < end:
        blob = ((device.ui_blob() or "") + "\n" + (device.screen_text("play-onboard.png") or "")).lower()
        # 2026-10-07 hop1 play-onboard.png and 2026-10-10 acct
        # skip-now.png: welcome to google play. Left pill dismisses it.
        # OCR can omit both labels and keep the enjoy-millions sentence.
        if ho.sync_welcome_not_now(blob):
            device.tap_text("Not now") or device.tap(270, 1780, 1.0)
            time.sleep(1.2)
            end = max(end, time.time() + 30.0)
            continue
        if "get started" in blob:
            device.tap_text("Get started", "GET STARTED") or device.tap(810, 1780, 1.0)
            time.sleep(1.6)
            continue
        if "i'm in" in blob or "im in" in blob:
            device.tap_text("Not now", "NOT NOW") or device.tap(270, 1780, 1.0)
            time.sleep(1.6)
            continue
        # 2026-10-05 hop-1003: Earn Play Points banner above Canceled Heavy
        # is the subscriptions list. Break instead of dismissing Not now.
        if ho.sync_heavy_list_ready(blob):
            break
        # 2026-09-22 hop-4 play-acct: sync loop OCR stayed on Introducing Google Play
        # Points and never reached For you. Same Not now as destg4 (540,1509).
        if "play points" in blob and "not now" in blob:
            dismiss_play_points()
            time.sleep(1.0)
            continue
        if ho.sync_playfest_sheet(blob):
            device.tap_text("No thanks") or device.tap_text("No, thanks")
            time.sleep(1.2)
            continue
        # 2026-09-22 hop-1 now-h1.xml: sentence y=763, button exact
        # "Try again" bounds [382,843][697,948]. tap_text hits the sentence.
        # plain input tap 539,895 stayed on the page (shot-h1-busy2).
        # su input tap 539,895 left it (aftertap-h1.png spinner).
        # su tap leaves once, then the same page returns (now2-h1.png).
        # looping the button after pm clear stays busy and library stays empty
        # (2026-09-22 hop-1 syncshot, rows 0). second sighting: force-stop
        # and open subscriptions, which restored Heavy without another clear.
        # reopen2-h1.png is "Server error" with the same Try again button.
        # 2026-10-09 hop-5 acct subs-moved.png: the satellite page
        # dropped the "Server busy" sentence and only said Try again,
        # with Play while you wait underneath. Same stuck store.
        if (
            "server busy" in blob
            or "server error" in blob
            or ("play while you wait" in blob and "try again" in blob)
        ):
            busy_taps += 1
            if busy_taps >= 2:
                device.shell("am force-stop com.android.vending")
                device.shell(
                    "am start -a android.intent.action.VIEW "
                    "-d https://play.google.com/store/account/subscriptions "
                    "com.android.vending"
                )
                time.sleep(3.0)
                break
            hit = device.find_exact_text("Try again")
            if hit:
                device.su_tap(int(hit["cx"]), int(hit["cy"]), 1.2)
            else:
                device.su_tap(539, 895, 1.2)
            time.sleep(2.0)
            continue
        if ho.sync_onboard_done(blob):
            break
        # 2026-10-08 hop-6: launcher OCR burned the 45s budget.
        if ho.sync_needs_relaunch(blob):
            relaunch += 1
            if relaunch <= 2:
                device.shell(
                    "am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER "
                    "-n com.android.vending/com.android.vending.AssetBrowserActivity"
                )
                time.sleep(1.2)
                continue
        time.sleep(1.0)
    device.shell(
        "am start -a android.intent.action.VIEW "
        "-d https://play.google.com/store/account/subscriptions com.android.vending"
    )
    # 2026-10-09 hop-4 acct subs-now.png: the subscriptions intent
    # was still "Server busy, please try again later." library.db stayed
    # empty and skipg4 logged no leftover while GET was still ultra.
    # Tap the button before reading library.db. Do not tap the game Play pills.
    for _ in range(3):
        blob = ((device.ui_blob() or "") + "\n" + (device.screen_text("play-busy.png") or "")).lower()
        if (
            "server busy" not in blob
            and "server error" not in blob
            and not ("play while you wait" in blob and "try again" in blob)
        ):
            break
        hit = device.find_exact_text("Try again")
        if hit:
            device.su_tap(int(hit["cx"]), int(hit["cy"]), 1.2)
        else:
            device.su_tap(539, 895, 1.2)
        time.sleep(2.5)
    wait_end = time.time() + 20
    row = ""
    owner = ""
    while time.time() < wait_end:
        row = _library_ultra_json(current)
        owner = _library_ultra_owner(current)
        if ho.library_ultra_is_current(owner=owner, current_google=current, blob=row):
            break
        time.sleep(1.5)
    ok = ho.library_ultra_is_current(owner=owner, current_google=current, blob=row)
    # 2026-10-09 hop-5 acct skip2.log: sync OCR was Server busy, then
    # Grok home replaced play-busy.png and skipg4 logged no leftover.
    # Keep the busy sighting on the return so the caller does not treat
    # an empty library as no leftover. GET was still ultra.
    return {
        "ok": ok,
        "already": False,
        "owner": owner,
        "row_head": row[:180],
        "server_busy": busy_taps > 0,
    }


def ensure_grok() -> None:
    """Sideload Grok dies when Play overlay steals focus. Relaunch before IAB."""
    if device.grok_pid():
        return
    device.shell("am force-stop com.android.vending")
    device.shell("monkey -p ai.x.grok -c android.intent.category.LAUNCHER 1")
    time.sleep(1.0)


def _png_bytes(raw: str) -> int:
    for part in (raw or "").split():
        if part.isdigit():
            return int(part)
    return 0


def wait_grok_ready() -> None:
    """Leave Grok splash before destg4p1m. pid-up is not enough.

    hop-5 2026-10-02 destg4p1m_gate: fire no_json, dump bytes=0, after
    dump hop-5-after-destg4.png still Grok splash 11:38. am start 1.2s
    left splash; ensure_grok returned early because pid existed.
    hop-1008p1 acct 2026-10-08: sleep 5 returned on a 44KB splash.
    Poll up to 40s. Do not force-stop again inside the poll.
    """
    def _ready_png_bytes() -> str:
        # hop-3 2026-10-10 destg4: overlapping destg4 dump made
        # screencap+wc timeout=12 raise TimeoutExpired and DESTG4_EXIT 1
        # with missing destg4.json while Ask home was already ready.
        try:
            return device.shell(
                "screencap -p /data/local/tmp/_grok_ready.png >/dev/null; wc -c < /data/local/tmp/_grok_ready.png",
                timeout=20,
            )
        except subprocess.TimeoutExpired:
            log("grok_ready_screencap_timeout")
            return ""

    focus = device.shell("dumpsys window | grep mCurrentFocus", timeout=8) or ""
    raw = _ready_png_bytes()
    n = _png_bytes(raw or "")
    if ho.grok_screen_ready(focus, n):
        log("grok_ready", True, n, "already")
        return
    # Play in front: one force-stop. Grok already top but still the small
    # splash: do not force-stop, that reset acct 12:28-12:30.
    top = focus
    lines = [ln for ln in focus.splitlines() if "mCurrentFocus" in ln]
    if lines:
        top = lines[-1]
    if "GrokActivity" not in top:
        device.shell("am force-stop ai.x.grok")
        time.sleep(0.5)
    device.shell("am start -n ai.x.grok/.main.GrokActivity")
    deadline = time.time() + 40
    ready = False
    while time.time() < deadline:
        time.sleep(2.0)
        raw = _ready_png_bytes()
        n = _png_bytes(raw or "")
        focus = device.shell("dumpsys window | grep mCurrentFocus", timeout=8) or ""
        if ho.grok_screen_ready(focus, n):
            ready = True
            break
        lines = [ln for ln in focus.splitlines() if "mCurrentFocus" in ln]
        top = lines[-1] if lines else focus
        if "GrokActivity" not in top:
            device.shell("am start -n ai.x.grok/.main.GrokActivity")
    log("grok_ready", ready, n)


def ensure_frida_server() -> bool:
    """e2 inspect is no_json while frida-server is down. Start the desk binary.

    2026-10-05 hop-5: pidof empty, attach ServerNotRunningError, skip logged
    inspect [] and returned 2. setsid /data/local/tmp/frida-server, then e2
    returned the canceled grok.ultra and skipg4p1m washed it.
    """
    pid = (device.shell("pidof frida-server", timeout=8) or "").strip().split()
    if pid and pid[0].isdigit():
        return True
    device.shell(
        "setsid /data/local/tmp/frida-server >/data/local/tmp/frida-server.log 2>&1 < /dev/null &",
        timeout=8,
    )
    time.sleep(0.5)
    pid = (device.shell("pidof frida-server", timeout=8) or "").strip().split()
    return bool(pid and pid[0].isdigit())


def inspect_p():
    ensure_frida_server()
    ensure_grok()
    hook = billing.HOOKS / "heavy_wall.live.compiled.js"
    if hook.exists():
        box = billing.fire("inspect", hook=str(hook))
    else:
        box = billing.inspect()
    if not box.get("ok"):
        box = billing.inspect()
    rows = []
    for p in box.get("purchases") or []:
        raw = p.get("raw") or ""
        actions: list[str] = []
        try:
            if raw.startswith("{"):
                actions = list(json.loads(raw).get("subscriptionClientActions") or [])
        except json.JSONDecodeError:
            actions = []
        rows.append(
            {
                "sku": p.get("productId"),
                "order": p.get("orderId"),
                "ar": p.get("autoRenewing"),
                "obf": (p.get("obfuscatedAccountId") or "")[:16],
                "obf_full": p.get("obfuscatedAccountId") or "",
                "tok": (p.get("purchaseToken") or "")[:24],
                "actions": actions,
            }
        )
    return box, rows


def persist_jwt(email: str, jwt: str) -> None:
    if not str(jwt or "").startswith("eyJ"):
        return
    dest = str(email or "").strip().lower()
    con = open_hotmail_sqlite()
    try:
        con.execute(
            "UPDATE accounts SET sso_jwt=?, has_sso=1, updated_at=datetime('now') WHERE lower(email)=?",
            (jwt, dest),
        )
        con.commit()
    finally:
        con.close()


def stamp_xai_login_ok(email: str) -> None:
    """Mark dest grok password as dest_login verified. GET SSO is not enough."""
    dest = str(email or "").strip().lower()
    if not dest:
        return
    con = open_hotmail_sqlite()
    try:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT notes FROM accounts WHERE lower(email)=?",
            (dest,),
        ).fetchone()
        if not row:
            con.rollback()
            return
        notes = ho.stamp_xai_login_ok_notes(str(row[0] or ""))
        con.execute(
            "UPDATE accounts SET notes=?, updated_at=datetime('now') WHERE lower(email)=?",
            (notes, dest),
        )
        con.commit()
    finally:
        con.close()


def get_gid(jwt: str = "") -> str:
    if jwt:
        box = billing.gid_from_jwt(jwt)
        gid = str(box.get("gid") or "")
        if GID_RE.fullmatch(gid) and box.get("ok"):
            return gid
        log("gid_from_jwt", box.get("err"), box.get("grpc_status"), box.get("http"))
    if not billing.DUMP_GID_COMPILED.exists():
        billing.compile_js(billing.DUMP_GID, billing.DUMP_GID_COMPILED)
    ensure_grok()
    if not device.grok_pid():
        device.shell("am start -n ai.x.grok/.main.GrokActivity")
        time.sleep(2.2)
    r = __import__("subprocess").run(
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
        timeout=50,
        env=billing._uv_env({"JS": str(billing.DUMP_GID_COMPILED)}),
        check=False,
    )
    box = billing.last_json((r.stdout or "") + "\n" + (r.stderr or ""))
    blob = json.dumps(box, default=str)
    m = GID_RE.search(blob)
    gid = m.group(0) if m else ""
    return gid


def buy(cmd: str, arg: str | None = None) -> dict:
    if cmd.startswith("destg4"):
        wait_grok_ready()
    else:
        ensure_grok()
    hook = str(billing.HOOKS / "heavy_wall.live.compiled.js")
    fired = billing.fire(cmd, hook=hook, arg=arg, timeout=80)
    (WORK / f"{cmd}-fire.json").write_text(json.dumps(fired, ensure_ascii=False, default=str, indent=2))
    log("fire", cmd, {k: fired.get(k) for k in ("ok", "d2rc", "offerId", "err", "error", "sent", "hasPI")})
    if cmd.startswith("destg4") and (
        "DeadObjectException" in str(fired.get("err") or "")
        or fired.get("ok") is False
    ):
        log("destg4 fire dead, relaunch grok")
        wait_grok_ready()
        fired = billing.fire(cmd, hook=hook, arg=arg, timeout=80)
        (WORK / f"{cmd}-fire.json").write_text(json.dumps(fired, ensure_ascii=False, default=str, indent=2))
        log("fire_retry", cmd, {k: fired.get(k) for k in ("ok", "d2rc", "offerId", "err")})
    text = billing.wait_wall(timeout=40.0)
    end_load = time.time() + 20
    while time.time() < end_load and "loading" in text.lower():
        time.sleep(1.2)
        text = billing.wall_text("wall.png")
    (WORK / f"{cmd}-wall.txt").write_text(text)
    if cmd.startswith("skipg4"):
        sg = ho.skipg4_subscribe_ok(text)
        log("skipg4_gate", cmd, sg.get("kind"), (sg.get("text") or "")[:180])
        if not sg.get("ok"):
            device.back(0.6)
            return {"ok": False, "stage": f"{cmd}_gate", "gate": sg, "fire": fired}
    gate = billing.gate_heavy(text)
    log("gate", cmd, gate.get("kind"), (gate.get("text") or "")[:180])
    if ho.destg4_benefits_continue(gate.get("text") or text or ""):
        if not device.tap_text("Continue", "CONTINUE"):
            device.su_tap(540, 1700, 0.8)
        time.sleep(1.0)
        text = billing.wait_wall(timeout=20.0)
        gate = billing.gate_heavy(text)
        log("gate_after_benefits", cmd, gate.get("kind"), (gate.get("text") or "")[:180])
    if not gate.get("ok"):
        if cmd.startswith("destg4") and ho.destg4_grok_died_home(text):
            log("destg4 wall is home, relaunch grok")
            wait_grok_ready()
            fired = billing.fire(cmd, hook=hook, arg=arg, timeout=80)
            log("fire_home_retry", cmd, {k: fired.get(k) for k in ("ok", "d2rc", "offerId", "err")})
            text = billing.wait_wall(timeout=40.0)
            gate = billing.gate_heavy(text)
            log("gate_home_retry", cmd, gate.get("kind"), (gate.get("text") or "")[:180])
        if (
            cmd.startswith("destg4")
            and not gate.get("ok")
            and "ask" in (text or "").lower()
            and not ho.destg4_grok_died_home(text)
        ):
            # 2026-10-07 hop8 src21: fire outer was Permission denied and the
            # next OCR was Ask / Imagine, not the splash. Do not force-stop.
            log("destg4 ask home, fire without restart")
            fired = billing.fire(cmd, hook=hook, arg=arg, timeout=80)
            log(
                "fire_ask_retry",
                cmd,
                {k: fired.get(k) for k in ("ok", "d2rc", "offerId", "err", "outer")},
            )
            text = billing.wait_wall(timeout=40.0)
            gate = billing.gate_heavy(text)
            log("gate_ask_retry", cmd, gate.get("kind"), (gate.get("text") or "")[:180])
        if not gate.get("ok"):
            device.back(0.6)
            return {"ok": False, "stage": f"{cmd}_gate", "gate": gate, "fire": fired}
    picked = pick_wall_card(WANT_LAST4, AVOID_LAST4)
    if WANT_LAST4 and not picked.get("ok"):
        return {"ok": False, "stage": f"{cmd}_wall_card", "gate": gate, "fire": fired, "wall_card": picked}
    if not billing.tap_subscribe():
        return {"ok": False, "stage": f"{cmd}_subscribe", "gate": gate, "fire": fired}
    if cmd.startswith("destg4"):
        # 2026-10-12 hop-3/5 leftover-hop-small-3: Subscribe then Play Points
        # overlay dump ~11564 OCR verify.png ~40s (shots-1000/hop-3-sub.png).
        # Not now is su_tap(293,1836). Dismiss immediately then verify.
        time.sleep(0.8)
        blob = (device.ui_blob() or "") + "\n" + (device.screen_text("post-sub.png") or "")
        if ho.after_skipg4_overlay(blob) == "play_points_not_now" or "play points" in blob.lower():
            log("destg4 play_points after subscribe")
            dismiss_play_points()
    ver = billing.verify_google_password(GOOGLE_PW, timeout=45.0)
    billing.dismiss_pay_sheets()
    log("verify", cmd, ver.get("kind"), ver.get("ok"))
    # timeout_continue / still_wall: 墙关了或还停在 Subscribe, 都不是买成.
    # card_declined 必须换卡, 不要当 p1m fallback.
    bad = ("play_error", "item_unavailable", "timeout_continue", "still_wall", "card_declined")
    if not ver.get("ok") or ver.get("kind") in bad:
        return {"ok": False, "stage": f"{cmd}_verify", "gate": gate, "verify": ver, "fire": fired}
    return {"ok": True, "stage": cmd, "fire": fired, "gate": gate, "verify": ver}


def buy_or_p1m(cmd: str, arg: str | None = None, dest_email: str = "") -> dict:
    first = buy(cmd, arg=arg)
    if first.get("ok"):
        return first
    kind = (first.get("verify") or {}).get("kind")
    if cmd.startswith("skipg4") and kind in ("timeout_continue", "still_wall", "item_unavailable"):
        _, rows = inspect_p()
        ultra = next((p for p in rows if p.get("sku") == "grok.ultra"), None)
        if ultra and not (ultra.get("obf_full") or ultra.get("obf")):
            log("skipg4 inspect washed, skip retry", ultra.get("order"))
            first["ok"] = True
            first["rows"] = rows
            first["inspect_wash"] = True
            return first
    if cmd.startswith("destg4") and dest_email and kind in ("timeout_continue", "item_unavailable", "still_wall"):
        raw = get_rows(dest_email)
        if raw.get("error") == "dest_sso_shared":
            log("destg4 GET dest_sso_shared", dest_email, raw.get("other"))
            first["ok"] = False
            first["err"] = "dest_sso_shared"
            return first
        gs = summarize(raw)
        dest_ultra = any(r.get("active") and "ultra" in str(r.get("sku") or "").lower() for r in gs)
        if dest_ultra and ho.destg4_success(
            dest_ultra_active=True,
            verify_kind=kind,
            dest_sso_ok=True,
        ):
            log("destg4 GET already ACTIVE, skip p1m")
            first["ok"] = True
            first["verify_miss"] = True
            first["dest_get"] = gs
            return first
    alt = {"skipg4": "skipg4p1m", "destg4": "destg4p1m"}.get(cmd)
    if not alt:
        return first
    if kind not in ("item_unavailable", "timeout_continue", "still_wall"):
        return first
    log("verify fallback p1m", cmd, kind, "->", alt)
    device.back(0.6)
    time.sleep(0.8)
    return buy(alt, arg=arg)


def dest_pool_row(email: str) -> dict:
    con = open_hotmail_sqlite()
    try:
        row = con.execute("SELECT * FROM accounts WHERE email=?", (email.strip().lower(),)).fetchone()
    finally:
        con.close()
    return dict(row) if row else {}


def dest_grok_login(email: str, *, _retried: bool = False) -> dict:
    """Must login with dest grok password. SSO GET is not enough."""
    try:
        import ab_signin  # noqa: PLC0415  (browser sign-in; not shipped)
    except ImportError:
        raise NotImplementedError("ab_signin not shipped in this research copy (# ops removed)")

    box = ab_signin.signin(email)
    sess = str(box.get("email") or "").strip().lower()
    href = str(box.get("href") or "")
    dest_e = str(email or "").strip().lower()
    via = str(box.get("via") or "")
    if (not box.get("ok")) and sess != dest_e:
        sess = str(ab_signin._session_email() or sess).strip().lower()
        href = str(ab_signin._ev("location.href") or href)
    if (not box.get("ok") or "sign-in" in href) and sess == dest_e:
        ab_signin._ev("window.location.assign('https://grok.com/')")
        for _ in range(12):
            time.sleep(1.0)
            href = str(ab_signin._ev("location.href") or "")
            if "sign-in" not in href:
                break
        time.sleep(1.0)
        sess = str(ab_signin._session_email() or sess).strip().lower()
        via = "nav_after_still_signin"
    if (not sess or sess != dest_e) and not _retried:
        ab_signin._ev(
            "window.location.assign('https://accounts.x.ai/sign-in?email=true')"
        )
        time.sleep(2.2)
        return dest_grok_login(email, _retried=True)
    err = ho.dest_login_accept(
        dest=email,
        session_email=sess,
        href=href,
        sso="eyJ" if int(box.get("sso_len") or 0) >= 20 else "",
    )
    ok = err is None
    return {
        "ok": ok,
        "err": None if ok else (err or box.get("err") or "dest_grok_login"),
        "sso_len": box.get("sso_len"),
        "href": href[:80],
        "via": via or box.get("via"),
        "email": sess,
    }


def hop_one(dest: str, prev: str) -> dict:
    rec: dict = {"dest": dest, "prev": prev, "t0": time.time()}
    xai_err = ho.dest_xai_ready(dest_pool_row(dest))
    if xai_err:
        rec["ok"] = False
        rec["err"] = xai_err
        log("STOP", xai_err, dest)
        return rec
    jwt_before = jwt_of(dest)
    other = sso_other_holder(dest, jwt_before)
    if other:
        rec["ok"] = False
        rec["err"] = "dest_sso_shared"
        rec["other"] = other
        log("STOP dest_sso_shared", dest, "also", other)
        return rec
    dest_gs = summarize(get_rows(dest))
    rec["dest_get_pre"] = dest_gs
    if any(r.get("active") and "ultra" in str(r.get("sku") or "").lower() for r in dest_gs):
        rec["ok"] = False
        rec["err"] = "dest_already_active"
        log("STOP dest_already_active", dest)
        return rec
    login_pre = dest_grok_login(dest)
    rec["dest_login_pre"] = login_pre
    log("dest_login_pre", dest, login_pre.get("ok"), login_pre.get("err"), login_pre.get("sso_len"))
    rec["_jwt_before"] = jwt_before
    if not login_pre.get("ok"):
        rec["ok"] = False
        rec["err"] = "dest_grok_login"
        return rec
    box, rows = inspect_p()
    rec["pre"] = rows
    log("pre-inspect", rows)
    ultra = next((p for p in rows if p.get("sku") == "grok.ultra"), None)
    if not ultra:
        syn = sync_play_library()
        rec["library_sync"] = syn
        log("library_sync", syn)
        device.shell("am start -n ai.x.grok/.main.GrokActivity")
        time.sleep(2.5)
        box, rows = inspect_p()
        rec["pre_after_sync"] = rows
        log("pre-inspect-after-sync", rows)
        ultra = next((p for p in rows if p.get("sku") == "grok.ultra"), None)
    if not ultra:
        rec["ok"] = False
        rec["err"] = "no_leftover"
        return rec
    empty_obf = not (ultra.get("obf_full") or ultra.get("obf"))
    if ultra.get("ar") is True:
        dismiss_play_points()
        c0 = billing.cancel_grok()
        rec["cancel_before"] = c0
        log("cancel_before", c0.get("ok"), c0.get("kind"))
        if not c0.get("ok"):
            rec["ok"] = False
            rec["err"] = "cancel_before"
            return rec
        box, rows = inspect_p()
        ultra = next((p for p in rows if p.get("sku") == "grok.ultra"), None) or ultra
        empty_obf = not (ultra.get("obf_full") or ultra.get("obf"))
    restore = "RESTORE" in (ultra.get("actions") or [])
    if empty_obf:
        log("skipg4 already washed, leftover empty obf")
        rec["skipg4"] = {"ok": True, "stage": "already_empty_obf"}
        sk = {"ok": True}
    elif restore:
        log("RESTORE leftover, skipg4p1m first")
        rec["restore"] = True
        sk = buy("skipg4p1m")
        rec["skipg4"] = {k: sk.get(k) for k in ("ok", "stage") if k in sk}
        rec["skipg4_gate"] = (sk.get("gate") or {}).get("kind")
        kind = (sk.get("verify") or {}).get("kind")
        if not sk.get("ok") and kind not in ("card_declined", "CHARGE_FULL", "play_error"):
            _, rows = inspect_p()
            washed = next((p for p in rows if p.get("sku") == "grok.ultra"), None)
            if washed and not (washed.get("obf_full") or washed.get("obf")):
                log("skipg4p1m inspect washed, skip p3m", washed.get("order"))
                sk["ok"] = True
                rec["skipg4_inspect_wash"] = True
            else:
                log("skipg4p1m failed, try skipg4 p3m")
                sk = buy_or_p1m("skipg4")
                rec["skipg4_retry"] = {k: sk.get(k) for k in ("ok", "stage") if k in sk}
    else:
        sk = buy_or_p1m("skipg4")
        rec["skipg4"] = {k: sk.get(k) for k in ("ok", "stage") if k in sk}
        rec["skipg4_gate"] = (sk.get("gate") or {}).get("kind")
    if not sk.get("ok"):
        rec["ok"] = False
        rec["err"] = "skipg4"
        rec["skip"] = sk
        return rec
    time.sleep(2.0)
    box, rows = inspect_p()
    rec["after_skip"] = rows
    log("after-skip", rows)
    ultra_wash = next((p for p in rows if p.get("sku") == "grok.ultra"), None)
    if ultra_wash and (ultra_wash.get("obf_full") or ultra_wash.get("obf")):
        if (sk.get("stage") or "") != "skipg4p1m":
            log("obf still set after skipg4, retry skipg4p1m")
            device.back(0.6)
            sk = buy("skipg4p1m")
            rec["skipg4_obf_retry"] = {k: sk.get(k) for k in ("ok", "stage") if k in sk}
            time.sleep(2.0)
            box, rows = inspect_p()
            rec["after_skip"] = rows
            log("after-skip-p1m", rows)
            ultra_wash = next((p for p in rows if p.get("sku") == "grok.ultra"), None)
        if ultra_wash and (ultra_wash.get("obf_full") or ultra_wash.get("obf")):
            rec["ok"] = False
            rec["err"] = "skipg4_obf_not_empty"
            return rec
    dismiss_play_points()
    ultra2 = next((p for p in rows if p.get("sku") == "grok.ultra"), None)
    if ultra2 and ultra2.get("ar") is False:
        log("already canceled leftover")
        c1 = {"ok": True, "kind": "already_canceled"}
    else:
        c1 = billing.cancel_grok()
    rec["cancel_skip"] = {k: c1.get(k) for k in ("ok", "kind")}
    log("cancel_skip", c1.get("ok"), c1.get("kind"))
    if not c1.get("ok"):
        rec["ok"] = False
        rec["err"] = "cancel_skip"
        return rec
    box, rows = inspect_p()
    rec["after_cancel_skip"] = rows
    log("leftover after cancel", rows)

    jwt = jwt_of(dest)
    src_jwt = jwt_of(prev)
    if jwt.startswith("eyJ") and src_jwt.startswith("eyJ") and jwt == src_jwt:
        rec["ok"] = False
        rec["err"] = "dest_sso_is_source"
        log("STOP dest_sso_is_source", dest, "from", prev)
        return rec
    gbox = billing.ensure_jwt_gid(jwt, dest) if jwt or dest else {"ok": False, "err": "no_jwt"}
    rec["gid_jwt"] = {k: gbox.get(k) for k in ("ok", "err", "grpc_status", "http", "from", "refreshed")}
    if gbox.get("refreshed") and str(gbox.get("jwt") or "").startswith("eyJ"):
        persist_jwt(dest, str(gbox.get("jwt")))
        jwt = str(gbox.get("jwt"))
    gid = str(gbox.get("gid") or "")
    rec["gid"] = gid
    rec["login"] = {"ok": True, "skip": "jwt_gid"}
    log("gid", gid, "skip dest Pixel grok app (jwt gid)")
    if not (gbox.get("ok") and GID_RE.fullmatch(gid)):
        rec["ok"] = False
        rec["err"] = str(gbox.get("err") or "ab_signin")
        rec["ab_signin"] = gbox.get("signin")
        return rec
    billing.prepare_hooks(gid, WORK)
    dg = buy_or_p1m("destg4", arg=gid, dest_email=dest)
    rec["destg4"] = {k: dg.get(k) for k in ("ok", "stage")}
    rec["destg4_gate"] = (dg.get("gate") or {}).get("kind")
    time.sleep(3.0)
    gs_d = get_rows(dest)
    rec["dest_get"] = summarize(gs_d)
    dest_ok_early = any(r.get("active") and "ultra" in str(r.get("sku") or "").lower() for r in rec["dest_get"])
    if not dg.get("ok") and not dest_ok_early:
        rec["ok"] = False
        rec["err"] = "destg4"
        rec["destg4_full"] = dg
        return rec
    if not dg.get("ok") and dest_ok_early:
        log("destg4 verify missed, GET dest already ACTIVE")
        rec["destg4_verify_miss"] = True
    gs_d = get_rows(dest)
    gs_p = get_rows(prev)
    rec["dest_get"] = summarize(gs_d)
    rec["prev_get"] = summarize(gs_p)
    log("GET dest", rec["dest_get"])
    log("GET prev", rec["prev_get"])
    dest_ok = any(r.get("active") and "ultra" in str(r.get("sku") or "").lower() for r in rec["dest_get"])
    if not dest_ok:
        rec["ok"] = False
        rec["err"] = "dest_get_empty"
        return rec
    dismiss_play_points()
    c2 = billing.cancel_grok()
    rec["cancel_dest"] = {k: c2.get(k) for k in ("ok", "kind")}
    log("cancel_dest", c2.get("ok"), c2.get("kind"))
    time.sleep(2.0)
    gs_d2 = get_rows(dest)
    rec["dest_get_after_cancel"] = summarize(gs_d2)
    dest_cap = any(
        r.get("active") and "ultra" in str(r.get("sku") or "").lower() and r.get("cap")
        for r in rec["dest_get_after_cancel"]
    )
    rec["ok"] = bool(dest_ok and dest_cap)
    if not dest_cap:
        rec["err"] = "dest_cap_false"
    rec["dt"] = round(time.time() - rec["t0"], 1)
    return rec


def main() -> int:
    if not os.environ.get("ANDROID_SERIAL"):
        sys.stderr.write("need ANDROID_SERIAL\n")
        return 2
    if not DESTS or not OLD:
        sys.stderr.write("need HOP_DEST and HOP_OLD\n")
        return 2
    device.connect()
    device.shell("ime set com.android.adbkeyboard/.AdbIME")
    log("google", device.google_accounts(), "grok", device.grok_accounts())
    box, rows = inspect_p()
    gid0 = (rows[0].get("obf_full") if rows else "") or "0" * 64
    if not GID_RE.fullmatch(gid0):
        gid0 = "deadbeef" * 8  # placeholder; real fallback GID removed
    prep = billing.prepare_hooks(gid0, WORK)
    log("prep", prep.get("ok"), prep.get("gid"))
    chain = []
    prev = OLD
    for i, dest in enumerate(DESTS, 1):
        log("==== hop", i, dest, "from", prev)
        rec = hop_one(dest, prev)
        chain.append(rec)
        (WORK / f"hop{i}.json").write_text(json.dumps(rec, ensure_ascii=False, default=str, indent=2))
        if not rec.get("ok"):
            log("STOP", rec.get("err"))
            (WORK / "chain.json").write_text(json.dumps(chain, ensure_ascii=False, default=str, indent=2))
            return 2
        login = dest_grok_login(dest)
        rec["dest_login"] = login
        log("dest_login", dest, login.get("ok"), login.get("err"), login.get("sso_len"))
        rec.pop("_jwt_before", "")
        if not login.get("ok"):
            rec["ok"] = False
            rec["err"] = "dest_grok_login"
            (WORK / f"hop{i}.json").write_text(json.dumps(rec, ensure_ascii=False, default=str, indent=2))
            (WORK / "chain.json").write_text(json.dumps(chain, ensure_ascii=False, default=str, indent=2))
            return 2
        other = sso_other_holder(dest)
        if other:
            rec["ok"] = False
            rec["err"] = "dest_sso_shared"
            rec["other"] = other
            log("STOP dest_sso_shared", dest, "also", other)
            (WORK / f"hop{i}.json").write_text(json.dumps(rec, ensure_ascii=False, default=str, indent=2))
            (WORK / "chain.json").write_text(json.dumps(chain, ensure_ascii=False, default=str, indent=2))
            return 2
        ing = ingest_hop_dest(dest, prev, claimed_by="leftover-hop")
        rec["ingest"] = ing
        log("ingest", dest, ing.get("ok"), ing.get("error"))
        (WORK / f"hop{i}.json").write_text(json.dumps(rec, ensure_ascii=False, default=str, indent=2))
        if not ing.get("ok"):
            rec["ok"] = False
            rec["err"] = "ingest_hop_dest"
            (WORK / f"hop{i}.json").write_text(json.dumps(rec, ensure_ascii=False, default=str, indent=2))
            (WORK / "chain.json").write_text(json.dumps(chain, ensure_ascii=False, default=str, indent=2))
            return 2
        prev = dest
    (WORK / "chain.json").write_text(json.dumps(chain, ensure_ascii=False, default=str, indent=2))
    log("DONE hops", len(chain))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
