#!/usr/bin/env python3
# Sanitized research copy. Ops/account/card/egress specifics removed.
"""Empty-obf leftover destg4 + GET dest + cancel cap. No skipg4. No dest Pixel login.

Internal to destg4-run.py. dest_grok_login + ingest stay with destg4-run.
Direct destg4_once is not hop complete. destg4-run Exit 0 only if ingest COUNT True.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault(
    "ADB_SERVER_SOCKET", "tcp:127.0.0.1:" + (os.environ.get("ADB_PORT") or "5037")
)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import billing_core as billing  # noqa: E402
import hop  # noqa: E402
import hop_oracle as ho  # noqa: E402

# billing.py surface beyond billing_core.py is trimmed from this research copy.
for _name in (
    "cancel_grok",
    "leftover_ingest_ready",
    "prepare_hooks",
):
    if not hasattr(billing, _name):
        setattr(
            billing,
            _name,
            lambda *a, _n=_name, **k: (_ for _ in ()).throw(
                NotImplementedError(f"billing.{_n}: not shipped in this research copy")
            ),
        )

try:
    import device  # noqa: E402  (adb / uiautomator / OCR layer; not shipped)
except ImportError:
    device = None  # research-copy stub; mechanism call sites kept verbatim


class _GrpcSubsStub:
    """# ops removed: grpc_subs.py (gRPC GetSubscriptions / GetGoogleObfuscatedId
    client, protobuf-over-curl) is not shipped. The dest-GET oracle below keeps
    its call sites; every call fails loud."""

    def __getattr__(self, attr: str):
        raise NotImplementedError(f"grpc_subs.{attr}: not shipped in this research copy")


try:
    import grpc_subs  # noqa: E402
except ImportError:
    grpc_subs = _GrpcSubsStub()


def sold_hop_forbidden(old: str):
    """# ops removed: sold-ledger lookup (grok_hotmail_pool) is not shipped."""
    return None


DEST = (os.environ.get("HOP_DEST") or "").strip()
OLD = (os.environ.get("HOP_OLD") or "").strip()
WORK = Path(os.environ.get("HOP_WORK") or "./work/destg4-once")
WORK.mkdir(parents=True, exist_ok=True)
HOP_LOG = WORK / "hop_dest_log.json"


def _log_write(rec: dict) -> None:
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


def finish_counted(code_ok: bool) -> int:
    """Direct destg4_once must ingest. Exit 0 only if COUNT True.

    destg4-run sets DESTG4_WRAPPED=1 and ingests after this process.

    # ops removed: the original ran ingest-run.py / dest-login-run.py
    # subprocesses against the account pool. This research copy records the
    # hop to ./work/hop_dest_log.json and keeps the COUNT contract.
    """
    if not code_ok:
        return 2
    if os.environ.get("DESTG4_WRAPPED") == "1":
        return 0

    def _once() -> bool:
        try:
            box = json.loads((WORK / "destg4.json").read_text(encoding="utf-8"))
        except Exception:
            box = {}
        if not isinstance(box, dict):
            box = {}
        dest = str(box.get("dest") or DEST or "").strip().lower()
        src = str(box.get("from") or OLD or "").strip().lower()
        play = str(box.get("play") or os.environ.get("HOP_PLAY") or "").strip().lower()
        tok8 = str(box.get("tok8") or "").strip().lower()
        if not dest or not src or len(tok8) != 8 or not tok8.isalnum():
            log("INGEST_COUNT False tok8_or_email")
            return False
        _log_write(
            {
                "dest": dest,
                "from": src,
                "play": play,
                "tok8": tok8,
                "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        )
        log("INGEST_COUNT True (local json stub)")
        return True

    return 0 if _once() else 2


def log(*a: object) -> None:
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    with (WORK / "once.log").open("a", encoding="utf-8") as fh:
        fh.write(time.strftime("%H:%M:%S ") + line + "\n")


def live_dest_get_user(jwt: str) -> tuple[int, str]:
    """grok.com get-user for this dest JWT. Shared Chrome, so sso_refresh locks it.

    # ops removed: sso_refresh (grok-register-sso Chrome get-user) is not
    # shipped, so this returns (0, "") instead of a live lookup. Callers fall
    # back to the login.json reuse path (destg4_get_user_from_login).
    """
    if not str(jwt or "").startswith("eyJ"):
        return 0, ""
    log("get_user sso_refresh_not_shipped")
    return 0, ""


def dest_get_user_status_email(
    jwt: str,
    *,
    dest_ultra: bool,
    dest_cap: bool,
    src_ultra: bool | None,
    login_box: dict | None = None,
) -> tuple[int, str]:
    """Prefer dest_login login.json get_user 200. Skip grok-sso flock."""
    box = login_box if isinstance(login_box, dict) else {}
    if not box:
        try:
            box = json.loads((WORK / "login.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            box = {}
    reused = ho.destg4_get_user_from_login(
        dest=DEST,
        login_get_user_status=int(box.get("get_user") or 0),
        login_get_user_email=str(box.get("get_user_email") or box.get("email") or ""),
        dest_ultra=bool(dest_ultra),
        dest_cap=bool(dest_cap),
        src_ultra=src_ultra if isinstance(src_ultra, bool) else None,
    )
    if reused:
        log("get_user_from_login", reused[0], reused[1])
        return reused
    return live_dest_get_user(jwt)


def persist_current_play(gs: dict) -> tuple[str, str, dict]:
    """Write dest+Play tok8 and gid on every destg4 success, including cancel_cap."""
    wanted = (os.environ.get("HOP_PLAY") or "").strip().lower()
    goog: list[str] = []
    try:
        goog = [str(a).strip().lower() for a in device.google_accounts() if str(a).strip()]
    except Exception as exc:
        log("play_accounts", type(exc).__name__)
    play = ""
    if wanted and wanted in goog:
        play = wanted
    elif wanted and wanted not in goog:
        log("play_bind_mismatch", wanted.split("@", 1)[0], [g.split("@", 1)[0] for g in goog[:3]])
    elif len(goog) == 1:
        play = goog[0]
    elif goog:
        log("play_bind_ambiguous", [g.split("@", 1)[0] for g in goog[:3]])
    ultra_row = (gs or {}).get("ultra_active") or {}
    tok8 = str(((ultra_row.get("google") or {}).get("purchaseToken")) or "")[:8]
    gid = ""
    jwt = hop.jwt_of(DEST)
    if str(jwt).startswith("eyJ"):
        try:
            gid = str((grpc_subs.get_gid_grpc(jwt) or {}).get("gid") or "")
        except Exception as exc:
            log("play_gid", type(exc).__name__)
    persisted: dict = {"ok": False, "error": "skipped"}
    if play and len(tok8) == 8:
        # ops removed: the original retried ho.persist_play_bind against the
        # inventory sqlite (grok-hotmail / gmail-play). This research copy
        # appends the bind record (dest/source/play/tok8/gid) to
        # ./work/hop_dest_log.json instead.
        _log_write(
            {
                "play_bind": {
                    "dest": DEST,
                    "source": OLD,
                    "play": play,
                    "tok8": tok8,
                    "gid": gid,
                },
                "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        )
        persisted = {"ok": True, "stub": "local_json"}
        log("play_bind", play.split("@", 1)[0], tok8, gid[:16], persisted.get("ok"))
    elif not play or len(tok8) != 8:
        log("play_bind_skipped", bool(play), tok8)
    return play, tok8, persisted


def inspect_rows_verdict(rows: list, adb_text: str) -> str:
    """Empty frida inspect is not a missing leftover when adb is already dead.

    2026-10-05 hop-8 acct: sqlite still had the washed GPA with obf empty,
    then destg4 logged inspect [] and no_leftover as the desk stopped.
    """
    if any(isinstance(p, dict) and p.get("sku") == "grok.ultra" for p in rows or []):
        return "have_ultra"
    if "ok" not in (adb_text or ""):
        return "adb_dead"
    return "no_leftover"


def main() -> int:
    if not os.environ.get("ANDROID_SERIAL"):
        sys.stderr.write("need ANDROID_SERIAL\n")
        return 2
    if not DEST or not OLD:
        sys.stderr.write("need HOP_DEST and HOP_OLD\n")
        return 2
    forbid = sold_hop_forbidden(OLD)
    if forbid:
        log("hop_source_forbidden", OLD, forbid)
        sys.stderr.write(f"hop_source_forbidden {OLD} {forbid}\n")
        return 5
    device.connect()
    hop.dismiss_after_skipg4()
    device.back(0.4)
    box, rows = hop.inspect_p()
    log("inspect", rows)
    verdict = inspect_rows_verdict(rows, device.shell("echo ok", timeout=6) or "")
    if verdict == "adb_dead":
        log("inspect empty adb dead")
        print(json.dumps({"ok": False, "stage": "adb_dead", "rows": rows}, ensure_ascii=False))
        return 2
    ultra = next((p for p in rows if p.get("sku") == "grok.ultra"), None) or {}
    jwt_early = hop.jwt_of(DEST)
    dest_gs_early = grpc_subs.get_subs_grpc(jwt_early) if str(jwt_early).startswith("eyJ") else {}
    dest_already = bool(dest_gs_early.get("has_ultra_active"))
    login_ultra = None
    login_box: dict = {}
    try:
        login_box = json.loads((WORK / "login.json").read_text(encoding="utf-8"))
        if not isinstance(login_box, dict):
            login_box = {}
        if "has_ultra_active" in login_box:
            login_ultra = login_box.get("has_ultra_active")
    except (OSError, json.JSONDecodeError):
        login_box = {}
    already_act = ho.destg4_already_active_action(
        login_ultra,
        dest_gs_early.get("has_ultra_active"),
        dest_gs_early.get("cancelAtPeriodEnd"),
    )
    if dest_already and already_act == "refuse":
        # 2026-09-20 hop-1 acct destg4 sourced acct who already had ultra
        # (dest_login has_ultra_active true). Do not destg4p1m onto occupied dest.
        log("dest GET already ACTIVE, refuse destg4p1m")
        print(
            json.dumps(
                {
                    "ok": False,
                    "stage": "dest_already_active",
                    "dest": DEST,
                    "from": OLD,
                    "has_ultra_active": True,
                    "cancelAtPeriodEnd": dest_gs_early.get("cancelAtPeriodEnd"),
                },
                ensure_ascii=False,
                default=str,
            )
        )
        return 2
    if dest_already and already_act == "cancel_cap":
        # 2026-09-23 hop-1 acct: destg4 already transferred, dest GET
        # True cap False. dest_login ultra was false. Cancel on-device.
        log("dest GET ACTIVE uncapped, cancel_cap")
        hop.dismiss_after_skipg4()
        c2 = billing.cancel_grok()
        log("cancel2", c2.get("kind"))
        if c2.get("kind") == "play_auth_required":
            out = {
                "ok": False,
                "stage": "play_auth_required",
                "cancel": c2,
                "dest": DEST,
                "from": OLD,
            }
            (WORK / "destg4.json").write_text(json.dumps(out, ensure_ascii=False, default=str, indent=2))
            print(json.dumps(out, ensure_ascii=False, default=str))
            return 2
        time.sleep(2)
        gs = grpc_subs.get_subs_grpc(jwt_early)
        dest_ok = bool(gs.get("has_ultra_active"))
        cap = bool(gs.get("cancelAtPeriodEnd"))
        log("cap", dest_ok, cap)

        def _src_read():
            val = grpc_subs.get_subs_grpc(hop.jwt_of(OLD)).get("has_ultra_active")
            log("src_ultra_read", val)
            return val

        src_ultra = ho.src_ultra_when_dest_ready(
            _src_read, dest_ready=bool(dest_ok and cap), attempts=8
        )
        play, tok8, persisted = persist_current_play(gs)
        gu_status, gu_email = dest_get_user_status_email(
            jwt_early,
            dest_ultra=dest_ok,
            dest_cap=cap,
            src_ultra=src_ultra if isinstance(src_ultra, bool) else None,
            login_box=login_box if isinstance(login_box, dict) else {},
        )
        email_err = ho.dest_sso_email_ok(
            dest=DEST, get_user_email=gu_email, get_user_status=gu_status
        )
        log("src_ultra", src_ultra)
        ok = bool(
            dest_ok and cap and src_ultra is False and not email_err and persisted.get("ok") and len(tok8) == 8
        )
        out = {
            "ok": ok,
            "stage": "destg4" if ok else (email_err or "dest_get_not_active"),
            "get_user": gu_status,
            "get_user_email": gu_email,
            "dest": DEST,
            "from": OLD,
            "play": play,
            "tok8": tok8,
            "play_persisted": bool(persisted.get("ok")),
            "has_ultra_active": dest_ok,
            "cancelAtPeriodEnd": cap,
            "src_ultra": src_ultra,
            "destg4": {"ok": True, "stage": "cancel_cap"},
        }
        (WORK / "destg4.json").write_text(json.dumps(out, ensure_ascii=False, default=str, indent=2))
        print(json.dumps(out, ensure_ascii=False, default=str))
        return finish_counted(bool(out.get("ok")))
    if dest_already and already_act == "ingest":
        def _src_read():
            val = grpc_subs.get_subs_grpc(hop.jwt_of(OLD)).get("has_ultra_active")
            log("src_ultra_read", val)
            return val

        src_ultra = ho.src_ultra_when_dest_ready(
            _src_read, dest_ready=True, attempts=8
        )
        play, tok8, persisted = persist_current_play(dest_gs_early)
        dest_ok_early = bool(dest_gs_early.get("has_ultra_active"))
        cap_early = bool(dest_gs_early.get("cancelAtPeriodEnd"))
        gu_status, gu_email = dest_get_user_status_email(
            jwt_early,
            dest_ultra=dest_ok_early,
            dest_cap=cap_early,
            src_ultra=src_ultra if isinstance(src_ultra, bool) else None,
            login_box=login_box if isinstance(login_box, dict) else {},
        )
        email_err = ho.dest_sso_email_ok(
            dest=DEST, get_user_email=gu_email, get_user_status=gu_status
        )
        log("src_ultra", src_ultra)
        dest_ready = billing.leftover_ingest_ready(dest_gs_early)
        ok = bool(
            dest_ready
            and src_ultra is False
            and not email_err
            and persisted.get("ok")
            and len(tok8) == 8
        )
        out = {
            "ok": ok,
            "stage": "destg4" if ok else (email_err or "dest_get_not_active"),
            "get_user": gu_status,
            "get_user_email": gu_email,
            "dest": DEST,
            "from": OLD,
            "play": play,
            "tok8": tok8,
            "play_persisted": bool(persisted.get("ok")),
            "has_ultra_active": bool(dest_gs_early.get("has_ultra_active")),
            "cancelAtPeriodEnd": dest_gs_early.get("cancelAtPeriodEnd"),
            "src_ultra": src_ultra,
            "destg4": {"ok": True, "stage": "already_capped"},
        }
        (WORK / "destg4.json").write_text(json.dumps(out, ensure_ascii=False, default=str, indent=2))
        print(json.dumps(out, ensure_ascii=False, default=str))
        return finish_counted(bool(out.get("ok")))
    if ho.destg4_before_skipg4(dest_gs_early.get("grpc_status"), dest_already) == "dest_jwt_grpc_16":
        log("dest JWT grpc 16, refresh before skipg4")
        print(
            json.dumps(
                {
                    "ok": False,
                    "stage": "dest_jwt_grpc_16",
                    "dest": DEST,
                    "from": OLD,
                },
                ensure_ascii=False,
            )
        )
        return 2
    if ho.should_fire_skipg4(ultra) and not dest_already:
        log("not washed")
        print(json.dumps({"ok": False, "stage": "need_skipg4", "rows": rows}, ensure_ascii=False, default=str))
        return 2
    if not ultra:
        src_now = grpc_subs.get_subs_grpc(hop.jwt_of(OLD))
        empty_act = ho.destg4_empty_inspect_action(
            rows,
            bool(src_now.get("has_ultra_active")),
            bool(src_now.get("cancelAtPeriodEnd")),
        )
        log("empty_inspect", empty_act)
        if empty_act != "fire":
            log("no leftover")
            print(json.dumps({"ok": False, "stage": "no_leftover", "rows": rows}, ensure_ascii=False, default=str))
            return 2
    # 2026-09-26 acct: cancel ran, then returned need_hop_pay_last4.
    # Check the env before cancel so a missing last4 does not wash twice.
    if not (os.environ.get("HOP_PAY_LAST4") or "").strip():
        print(json.dumps({"ok": False, "stage": "need_hop_pay_last4"}, ensure_ascii=False))
        return 2
    if ultra.get("ar") is True:
        hop.dismiss_after_skipg4()
        c0 = billing.cancel_grok()
        log("cancel", c0.get("kind"))
        ui = str((c0 or {}).get("ui") or "")
        if not c0.get("ok") and ho.after_skipg4_overlay(ui) == "play_points_not_now":
            hop.dismiss_play_points()
            c0 = billing.cancel_grok()
            log("cancel_retry", c0.get("kind"))
        if not c0.get("ok"):
            print(json.dumps({"ok": False, "stage": "cancel_before", "cancel": c0}, ensure_ascii=False, default=str))
            return 2
    other = hop.sso_other_holder(DEST)
    if other:
        print(json.dumps({"ok": False, "stage": "dest_sso_shared", "other": other}, ensure_ascii=False))
        return 2
    jwt = hop.jwt_of(DEST)
    src_jwt = hop.jwt_of(OLD)
    dest_jwt_is_source = bool(jwt.startswith("eyJ") and src_jwt.startswith("eyJ") and jwt == src_jwt)
    if dest_jwt_is_source:
        print(json.dumps({"ok": False, "stage": "dest_sso_is_source", "dest": DEST, "from": OLD}, ensure_ascii=False))
        return 2
    gbox = billing.ensure_jwt_gid(jwt, DEST)
    gid = str(gbox.get("gid") or "")
    log("gid", gid[:16], gbox.get("ok"))
    if not (gbox.get("ok") and hop.GID_RE.fullmatch(gid)):
        print(json.dumps({"ok": False, "stage": "gid", "gid": gbox}, ensure_ascii=False, default=str))
        return 2
    billing.prepare_hooks(gid, WORK)
    # hop-929 hop-1 2026-10-02 leftover destg4p1m first fire DeadObjectException
    # then destg4 fire dead, relaunch, fire_retry. hop-5 destg4p1m_gate dump
    # bytes=0 / after-destg4.png Grok splash 11:38: pid-up + am start 1.2s
    # left splash. wait_grok_ready force-stops then waits past splash.
    hop.wait_grok_ready()
    # p1m leftover destg4 is destg4p1m. destg4 (p3m) wall is $99.99 intro
    # (2026-09-19 hop-1 acct after skipg4 wash).
    dg = hop.buy("destg4p1m", arg=gid)
    log("destg4p1m", {k: dg.get(k) for k in ("ok", "stage")}, (dg.get("verify") or {}).get("kind"))
    if not dg.get("ok"):
        # 2026-09-20 billing: grok home after Subscribe is timeout_continue
        # so destg4 can GET. hop.py already continues when GET is ACTIVE.
        # 2026-09-29 acct/acct: the same timeout still landed a new GPA,
        # and returning here forced a second destg4. Card decline and gate
        # misses stay failures. acct: do not treat the inner fail as success
        # until the GET below shows ultra and cancel_cap sticks.
        verify_kind = str((dg.get("verify") or {}).get("kind") or "")
        if verify_kind != "timeout_continue":
            out = {
                "ok": False,
                "stage": str(dg.get("stage") or "destg4p1m_verify"),
                "dest": DEST,
                "from": OLD,
                "has_ultra_active": False,
                "cancelAtPeriodEnd": None,
                "destg4": {k: dg.get(k) for k in ("ok", "stage")},
            }
            (WORK / "destg4.json").write_text(json.dumps(out, ensure_ascii=False, default=str, indent=2))
            print(json.dumps(out, ensure_ascii=False, default=str))
            return 2
        log("verify timeout_continue, same-process GET")
    time.sleep(3)
    gs = grpc_subs.get_subs_grpc(jwt)
    dest_ok = bool(gs.get("has_ultra_active"))
    cap = bool(gs.get("cancelAtPeriodEnd"))
    log("GET", dest_ok, cap)
    if not dest_ok:
        # 2026-09-27 acct: verify timeout then a single GET missed the attach.
        time.sleep(4)
        gs = grpc_subs.get_subs_grpc(jwt)
        dest_ok = bool(gs.get("has_ultra_active"))
        cap = bool(gs.get("cancelAtPeriodEnd"))
        log("GET2", dest_ok, cap)
    if not dest_ok:
        # 2026-10-09 hop-1: the new GPA was already on the dest gid while
        # both GETs were still false. Refiring that Google is unable_change.
        try:
            _box, rows = hop.inspect_p()
        except Exception as exc:
            log("attach_inspect", type(exc).__name__)
            rows = []
        ultra_row = next((p for p in rows or [] if p.get("sku") == "grok.ultra"), None)
        obf = str((ultra_row or {}).get("obf_full") or (ultra_row or {}).get("obf") or "")
        if ho.dest_attach_pending(False, obf, gid):
            log("attach_pending", (ultra_row or {}).get("order"))
            for nth in (1, 2, 3):
                time.sleep(8)
                gs = grpc_subs.get_subs_grpc(jwt)
                dest_ok = bool(gs.get("has_ultra_active"))
                cap = bool(gs.get("cancelAtPeriodEnd"))
                log("GET_pending", nth, dest_ok, cap)
                if dest_ok:
                    break
    if dest_ok and not cap:
        hop.dismiss_after_skipg4()
        c2 = billing.cancel_grok()
        log("cancel2", c2.get("kind"))
        if c2.get("kind") == "play_auth_required":
            out = {
                "ok": False,
                "stage": "play_auth_required",
                "cancel": c2,
                "dest": DEST,
                "from": OLD,
            }
            (WORK / "destg4.json").write_text(json.dumps(out, ensure_ascii=False, default=str, indent=2))
            print(json.dumps(out, ensure_ascii=False, default=str))
            return 2
        for nth in (1, 2, 3):
            time.sleep(3)
            gs = grpc_subs.get_subs_grpc(jwt)
            dest_ok = bool(gs.get("has_ultra_active"))
            cap = bool(gs.get("cancelAtPeriodEnd"))
            log("cap", nth, dest_ok, cap)
            if dest_ok and cap:
                break
    def _src_read():
        if not src_jwt.startswith("eyJ"):
            return None
        val = grpc_subs.get_subs_grpc(src_jwt).get("has_ultra_active")
        log("src_ultra_read", val)
        return val

    # 2026-10-06 acct: five reads 12s apart were still True. The next
    # independent GET was False and Play had only the dest token. Eight
    # reads cover that lag without a second purchase.
    src_ultra = ho.src_ultra_when_dest_ready(
        _src_read, dest_ready=bool(dest_ok and cap), attempts=8
    )
    gu_status, gu_email = dest_get_user_status_email(
        jwt,
        dest_ultra=dest_ok,
        dest_cap=cap,
        src_ultra=src_ultra if isinstance(src_ultra, bool) else None,
        login_box=login_box if isinstance(login_box, dict) else {},
    )
    email_err = ho.dest_sso_email_ok(
        dest=DEST,
        get_user_email=gu_email,
        get_user_status=int(gu_status or 0),
    )
    if email_err:
        log("dest_sso_email", email_err, gu_email)
    ok = bool(
        dest_ok
        and cap
        and not email_err
        and ho.destg4_success(
            dest_ultra_active=dest_ok,
            dest_sso_ok=not hop.sso_other_holder(DEST),
            dest_jwt_is_source=dest_jwt_is_source,
            src_ultra=src_ultra if isinstance(src_ultra, bool) else None,
            dest=DEST,
            dest_get_user_email=gu_email,
            dest_get_user_status=int(gu_status or 0),
        )
    )
    play, tok8, persisted = ("", "", {"ok": False, "error": "skipped"})
    if ok:
        play, tok8, persisted = persist_current_play(gs)
    out = {
        "ok": ok,
        "stage": (
            "destg4"
            if ok
            else (email_err or "dest_get_not_active")
        ),
        "get_user_email": gu_email,
        "get_user": int(gu_status or 0),
        "dest": DEST,
        "from": OLD,
        "play": play,
        "tok8": tok8,
        "play_persisted": bool(persisted.get("ok")),
        "has_ultra_active": dest_ok,
        "cancelAtPeriodEnd": cap,
        "src_ultra": src_ultra,
        "destg4": {k: dg.get(k) for k in ("ok", "stage")},
    }
    (WORK / "destg4.json").write_text(json.dumps(out, ensure_ascii=False, default=str, indent=2))
    print(json.dumps(out, ensure_ascii=False, default=str))
    return finish_counted(bool(ok))


if __name__ == "__main__":
    raise SystemExit(main())
