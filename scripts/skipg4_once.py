#!/usr/bin/env python3
# Sanitized research copy. Ops/account/card/egress specifics removed.
"""One skipg4p1m + one password verify. No retry loop. Empty obf does not fire."""
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
import hop_oracle  # noqa: E402

# billing.py surface beyond billing_core.py is trimmed from this research copy.
# Explicit stubs keep the call sites below readable and fail loud instead of
# returning fake results.
for _name in (
    "pick_wall_card",
    "subscribe_captured",
    "fill_play_password",
    "ack_token",
    "prepare_hooks",
    "hook_with_ultra_token",
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


def sold_hop_forbidden(old: str):
    """# ops removed: sold-ledger lookup (grok_hotmail_pool) is not shipped.

    The original returned a forbid reason for hop=false (warranty) sources.
    """
    return None


WANT = os.environ.get("HOP_PAY_LAST4") or ""
AVOID = os.environ.get("HOP_AVOID_LAST4") or ""
PW = os.environ.get("GOOGLE_PW") or os.environ.get("HOP_GOOGLE_PW") or ""
WORK = Path(os.environ.get("HOP_WORK") or "./work/skip-once")
WORK.mkdir(parents=True, exist_ok=True)


def log(*a: object) -> None:
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    with (WORK / "once.log").open("a", encoding="utf-8") as fh:
        fh.write(time.strftime("%H:%M:%S ") + line + "\n")


def _ultra(rows: list[dict]) -> dict | None:
    return next((p for p in rows if p.get("sku") == "grok.ultra"), None)


def after_inspect_verdict(rows: list[dict], *, adb_text: str) -> str:
    """Empty inspect is a wash only while adb still answers.

    2026-10-05 hop-8 acct: password was typed, then dumps were 0 bytes,
    the desk stopped, inspect was [], and skip returned 0. That is adb_dead,
    not a washed leftover.
    """
    if not rows and "ok" not in (adb_text or ""):
        return "adb_dead"
    ultra = _ultra(rows) or {}
    if not hop_oracle.should_fire_skipg4(ultra):
        return "washed"
    return "pending"


def main() -> int:
    serial = (os.environ.get("ANDROID_SERIAL") or "").strip()
    if not serial:
        sys.stderr.write("need ANDROID_SERIAL\n")
        return 2
    old = (os.environ.get("HOP_OLD") or "").strip().lower()
    if old:
        forbid = sold_hop_forbidden(old)
        if forbid:
            log("hop_source_forbidden", old, forbid)
            sys.stderr.write(f"hop_source_forbidden {old} {forbid}\n")
            return 5
    if not PW:
        sys.stderr.write("need GOOGLE_PW\n")
        return 2
    play = (os.environ.get("HOP_PLAY") or "").strip().lower()
    if not play:
        sys.stderr.write("need HOP_PLAY\n")
        return 2
    device.connect()
    # hop-929 hop-1 wave-6: after-switch-subs.png was Canceled Heavy Oct 26
    # but dumpsys was still dest Play play-acct. skipg4 washed ingested dest leftover.
    ds = (device.shell("dumpsys account") or "").lower()
    if play not in ds:
        log("skipg4_play_mismatch", play)
        sys.stderr.write(f"skipg4_play_mismatch want={play}\n")
        return 4
    device.shell("ime set com.android.adbkeyboard/.AdbIME")
    _box, rows = hop.inspect_p()
    log("inspect", rows)
    log("inspect-box", {"ok": _box.get("ok"), "err": _box.get("err") or _box.get("error"), "e2rc": _box.get("e2rc"), "n": len(rows)})
    ultra = _ultra(rows)
    lib_tok = ""
    # e2 can return ok false / no_json while library.db still owns the canceled row.
    if not ultra and (_box.get("err") or _box.get("error")) != "adb_dead":
        # 2026-10-05 hop-5/6: e2 list empty, library still owns canceled Heavy.
        lib_row, lib_tok = hop.library_ultra_fire_row()
        if hop_oracle.library_ultra_fireable(lib_row, lib_tok):
            log(
                "library leftover",
                {
                    "ar": lib_row.get("ar"),
                    "state": lib_row.get("purchaseState"),
                    "tok8": (lib_tok or "")[:8],
                    "obflen": len(lib_row.get("obf_full") or ""),
                    "actions": lib_row.get("actions"),
                },
            )
            ultra = lib_row
            rows = [lib_row]
        else:
            log(
                "library not fireable",
                {
                    "row": bool(lib_row),
                    "state": None if not lib_row else lib_row.get("purchaseState"),
                    "ar": None if not lib_row else lib_row.get("ar"),
                    "obflen": 0 if not lib_row else len(str(lib_row.get("obf_full") or "")),
                    "toklen": len(lib_tok or ""),
                },
            )
            lib_tok = ""
    syn: dict = {}
    if not ultra:
        syn = hop.sync_play_library()
        log("library_sync", syn)
        device.shell("am start -n ai.x.grok/.main.GrokActivity")
        time.sleep(2.5)
        _box, rows = hop.inspect_p()
        log("inspect-after-sync", rows)
        ultra = _ultra(rows)
        if not ultra and hop_oracle.skipg4_wait_play_subs(syn):
            log("library current, wait Play subscriptions")
            device.shell(
                "am start -a android.intent.action.VIEW "
                "-d https://play.google.com/store/account/subscriptions"
            )
            end = time.time() + 20
            while time.time() < end:
                blob = ((device.ui_blob() or "") + "\n" + (device.screen_text("subs.png") or "")).lower()
                # Grok Ask Try SuperGrok is not Play subscriptions
                # (2026-09-19 hop-3 play-acct skipg4_once landed on Grok home).
                if "subscriptions" in blob and (
                    "will end" in blob or "canceled" in blob or "supergrok heavy" in blob
                ):
                    break
                time.sleep(1.2)
            device.shell("am start -n ai.x.grok/.main.GrokActivity")
            time.sleep(2.0)
            _box, rows = hop.inspect_p()
            log("inspect-after-subs", rows)
            ultra = _ultra(rows)
        if not ultra:
            # 2026-09-26 four desks: library already had grok.ultra but inspect
            # stayed empty until Grok was force-stopped and started again.
            log("restart grok billing cache")
            device.shell("am force-stop ai.x.grok")
            time.sleep(1.0)
            device.shell("am start -n ai.x.grok/.main.GrokActivity")
            time.sleep(3.0)
            _box, rows = hop.inspect_p()
            log("inspect-after-restart", rows)
            ultra = _ultra(rows)
    if not ultra:
        # 2026-10-09 hop-4 acct: Play home stayed on Server busy.
        # hop-5 skip2.log: the same page was OCR'd, then Grok home
        # overwrote play-busy.png and the exit became no leftover.
        # GET was still ultra+cap. Trust the sync flag, not the last frame.
        if isinstance(syn, dict) and syn.get("server_busy"):
            log("play_server_busy")
            return 6
        busy = ((device.ui_blob() or "") + "\n" + (device.screen_text("play-busy.png") or "")).lower()
        if "server busy" in busy or "server error" in busy:
            log("play_server_busy")
            return 6
        log("no leftover")
        return 2
    if not hop_oracle.should_fire_skipg4(ultra):
        log("already_washed")
        print(json.dumps({"ok": True, "typed": False, "skipped": "empty_obf", "rows": rows}, ensure_ascii=False, default=str))
        return 0
    pm_blob = ((device.ui_blob() or "") + "\n" + (device.screen_text("pm-pre.png") or ""))
    if hop_oracle.skipg4_landed_payment_methods(pm_blob) or hop_oracle.skipg4_landed_redeem(pm_blob):
        log("leave overlay before fire", "redeem" if hop_oracle.skipg4_landed_redeem(pm_blob) else "payment_methods")
        device.back(0.4)
        device.back(0.4)
        device.shell("am start -n ai.x.grok/.main.GrokActivity")
        time.sleep(2.0)
    cmd = "skipg4p1m" if "RESTORE" in (ultra.get("actions") or []) else "skipg4"
    hook = str(billing.HOOKS / "heavy_wall.live.compiled.js")
    if ultra.get("from") == "library":
        hooked = billing.hook_with_ultra_token(lib_tok, WORK)
        if hooked is None:
            log("library hook failed")
            return 2
        hook = str(hooked)
    fired = billing.fire(cmd, hook=hook, timeout=80)
    log("fire", {k: fired.get(k) for k in ("ok", "d2rc", "offerId", "err")})
    text = billing.wait_wall(timeout=40.0)
    sg = hop_oracle.skipg4_subscribe_ok(text)
    log("skipg4_gate", sg.get("kind"), (sg.get("text") or "")[:160])

    def _refire() -> None:
        nonlocal fired, text, sg
        fired = billing.fire(cmd, hook=hook, timeout=80)
        log("fire", {k: fired.get(k) for k in ("ok", "d2rc", "offerId", "err")})
        text = billing.wait_wall(timeout=40.0)
        sg = hop_oracle.skipg4_subscribe_ok(text)
        log("skipg4_gate", sg.get("kind"), (sg.get("text") or "")[:160])

    acked_once = False
    for _ in range(3):
        if sg.get("ok"):
            break
        kind = sg.get("kind")
        if kind == "unable_change" and not acked_once:
            # 2026-10-07 hop5 src43: sheet is Error + Got it. Ack the
            # AR=false ultra, then the next fire can be a deferred wall.
            log("unable_change ack then refire")
            device.tap_text("Got it") or device.su_tap(540, 1836, 0.6)
            tok = str((ultra or {}).get("tok") or lib_tok or "")
            if len(tok) >= 20:
                acked = billing.ack_token(tok, WORK)
                log("ack", {k: acked.get(k) for k in ("ok", "acked", "error")})
            acked_once = True
            device.shell("am start -n ai.x.grok/.main.GrokActivity")
            time.sleep(1.2)
            _refire()
            continue
        if kind in ("no_internet", "password_no_internet"):
            # 2026-09-23 hop-3 acct / hop-1 acct: US_EGRESS proxy pink play + HK
            # <ip>, Dashboard 0B/s. FAB (964,1594) starts play
            # only when Dashboard is foreground. Tapping FAB on the Play
            # password overlay does nothing (hop-1 acct h1c).
            eg = device.play_egress()
            us = str((eg or {}).get("country") or "") == "United States"
            if not us:
                log("acquire", kind, "proxy dashboard then play")  # US_EGRESS
                rec = device.recover_proxy_play_foreground()  # ops renamed: proxy egress recovery
                log("proxy_recover", {k: rec.get(k) for k in ("ok", "tun0", "node", "http_proxy")})
                # 2026-09-23 hop-1 acct h1d: opening Dashboard dismisses
                # the FLAG_SECURE password sheet. Re-fire after US play.
                device.shell("am start -n ai.x.grok/.main.GrokActivity")
                time.sleep(1.2)
                _refire()
                continue
            # 2026-09-23 hop-1 acct h1e/h1f: egress already US
            # <ip> / <ip>, lockdown 0, http_proxy true,
            # wait_wall still password + No internet. leftover-hop-dest
            # acct/acct: Try again on the sheet then type. Leaving
            # to Dashboard dismisses acquire and refire keeps No internet.
            log("acquire", kind, "US egress Try again on sheet", (eg or {}).get("ip"))
            device.prepare_play_iap()
            device.recover_play_no_internet()
            device.tap_text("Try again") or device.tap_text("try again")
            time.sleep(1.2)
            text = billing.wait_wall(timeout=20.0)
            sg = hop_oracle.skipg4_subscribe_ok(text)
            if sg.get("kind") == "password_no_internet":
                sg = {"ok": True, "kind": "password_page", "text": sg.get("text")}
            log("skipg4_gate", sg.get("kind"), (sg.get("text") or "")[:160])
            continue
        if kind == "benefits_continue":
            # 2026-09-21 hop-1 acct / hop-4 acct hop1-benefits.xml:
            # No thanks [63,1789][524,1884]. hop-4 acct h4-benefits.png.
            # skipg4deferred forbids Continue/Subscribe.
            log("skipg4deferred No thanks")
            device.tap_text("No thanks") or device.su_tap(293, 1836, 0.8)
            time.sleep(1.5)
            _refire()
            continue
        if kind == "play_server_error":
            # 2026-09-29 hop-4 acct wall.png: Got it, not Try again.
            log("play server error, tap Got it then refire")
            device.tap_text("Got it") or device.back(0.4)
            device.shell("am start -n ai.x.grok/.main.GrokActivity")
            time.sleep(1.2)
            _refire()
            continue
        if kind in ("payment_methods", "redeem"):
            log("leave overlay after fire, re-fire", kind)
            device.back(0.4)
            device.back(0.4)
            device.shell("am start -n ai.x.grok/.main.GrokActivity")
            time.sleep(2.0)
            _refire()
            continue
        if kind == "not_today_zero" and hop_oracle.destg4_grok_died_home(sg.get("text") or ""):
            # 2026-10-07 hop1 twice: fire ok false, OCR "11:11 A VA" /
            # "11:17 A VA", screenshot is the Grok splash. Do not exit.
            log("splash after fire, reopen grok and refire")
            # am start + 2s left the same splash. wait_grok_ready force-stops
            # and waits 5s, which is what destg4 uses for this screen.
            hop.wait_grok_ready()
            _refire()
            continue
        break
    if not sg.get("ok") and hop_oracle.skipg4_ask_home(sg.get("text") or ""):
        # 2026-10-07 hop1 src28: last gate was Ask / Imagine, not the wall.
        # The splash loop had already used its three refires. One more fire
        # from this home. Do not wait_grok_ready.
        log("ask home, fire without restart")
        _refire()
    if not sg.get("ok"):
        log("skipg4 refuse", sg.get("kind"), "do not subscribe")
        return 2
    already_password = sg.get("kind") == "password_page"
    if already_password:
        log("wait_wall already password page, skip Subscribe")
    else:
        gate = billing.gate_heavy(text)
        log("gate", gate.get("kind"), (gate.get("text") or "")[:160])
        if not gate.get("ok"):
            log("gate fail")
            return 2
        picked = billing.pick_wall_card(WANT, AVOID, blob=text)
        if not picked.get("ok"):
            live = hop_oracle.hop_live_last4_on_list(picked.get("shown") or [], WANT, AVOID)
            if live and live != WANT:
                log("remap hop-live last4", WANT, "->", live)
                picked = billing.pick_wall_card(live, AVOID)
        log("wall_card", {k: picked.get(k) for k in ("ok", "kind", "last4", "shown", "via")})
        if not picked.get("ok"):
            log("wall_card fail, do not subscribe leftover last4")
            return 5
        if not billing.subscribe_captured(picked):
            log("subscribe fail")
            return 2
    typed = False
    end = time.time() + 40
    t0 = time.time()
    early_inspect = False
    while time.time() < end:
        ocr = device.screen_text("v.png") or ""
        blob = ((device.ui_blob() or "") + "\n" + ocr).lower()
        if "maximum number of login" in blob:
            log("still locked")
            device.tap_text("OK") or device.tap(540, 1700, 0.4)
            return 3
        if hop_oracle.after_skipg4_overlay(blob) == "dferh_01":
            # 2026-09-29 hop-4 acct v.png DF-DFERH-01 during wait.
            log("df_dferh_01 during wait tap See current subscriptions or OK")
            device.tap_text("See current subscriptions") or device.tap_text("OK") or device.tap(540, 1836, 0.5)
            break
        # FLAG_SECURE password dump often only has Verify + Remember me, no "password".
        # 2026-09-18 grok-hop-2 acct wall: Verify bounds y~1738-1833.
        pw_page = (
            "enter your password" in blob
            or ("password" in blob and "verify" in blob)
            or ("remember me on this device" in blob and "verify" in blob)
            or hop_oracle.skipg4_flag_secure_ime_only(blob)
        )
        if pw_page and not typed:
            billing.fill_play_password(PW)
            device.hide_ime()
            device.shell("am broadcast -a ADB_HIDE_KEYBOARD")
            time.sleep(0.5)
            # FLAG_SECURE password: dump 无 Verify. tap 1785 会点到 IME 条.
            # IME ON: 1836 hits IME (2026-09-20 hop-2 acct w2h2-after-skipg4.png).
            vy = hop_oracle.skipg4_verify_tap_y(blob)
            device.su_tap(540, vy, 1.2)
            typed = True
            log("typed_once", "verify_y", vy)
            # 2026-10-05 hop-8 acct: the next ui dump was 0 bytes and the
            # desk stopped before the library changed. Leave the sheet alone
            # and confirm with inspect only.
            break
        if hop_oracle.skipg4_password_no_internet(blob):
            log("password_no_internet proxy dashboard then Try again")
            rec = device.recover_proxy_play_foreground()  # ops renamed: proxy egress recovery
            log("proxy_recover", {k: rec.get(k) for k in ("ok", "tun0", "node", "http_proxy")})
            device.shell("am start -n ai.x.grok/.main.GrokActivity")
            time.sleep(1.0)
            device.tap_text("Try again") or device.tap_text("try again")
            time.sleep(1.0)
            # 2026-09-21 hop-2 acct h2-pw.xml: error text, no Try again button,
            # only Verify [63,1738][1017,1833]. After typed, hide IME + 1760.
            if typed:
                device.hide_ime()
                device.shell("am broadcast -a ADB_HIDE_KEYBOARD")
                time.sleep(0.3)
                vy = hop_oracle.skipg4_verify_tap_y(blob)
                device.su_tap(540, vy, 1.0)
                log("reverify_after_no_internet", "verify_y", vy)
            continue
        if any(k in blob for k in ("you're subscribed", "thanks for subscribing", "payment successful", "already own")):
            log("subscribed_or_owned")
            break
        # 2026-09-18 acct: no password page, 40s wait then inspect already washed.
        if not early_inspect and time.time() - t0 >= 6:
            early_inspect = True
            _box, rows_early = hop.inspect_p()
            ultra_e = _ultra(rows_early) or {}
            if ultra_e and not hop_oracle.should_fire_skipg4(ultra_e):
                log("inspect_during_pw_wait", rows_early)
                break
        time.sleep(0.8)
    else:
        log("no password page")
    if not typed:
        hop.dismiss_after_skipg4()
    empty = False
    ultra = {}
    rows = []
    end_i = time.time() + 90
    first = True
    reverify_done = False
    while time.time() < end_i:
        if not first:
            time.sleep(8)
        first = False
        _box, rows = hop.inspect_p()
        log("after-inspect", rows)
        verdict = after_inspect_verdict(rows, adb_text=device.shell("echo ok", timeout=6) or "")
        if verdict == "adb_dead":
            log("after-inspect empty adb dead")
            print(json.dumps({"ok": False, "typed": typed, "rows": rows, "error": "adb_dead"}, ensure_ascii=False))
            return 2
        ultra = _ultra(rows) or {}
        empty = verdict == "washed"
        if empty:
            hop.dismiss_after_skipg4()
            break
        if (
            typed
            and not reverify_done
            and hop_oracle.skipg4_reverify_acquire(
                True, verdict, device.current_focus() or ""
            )
        ):
            # 2026-10-07 hop5: 1760 hit the IME. Hide, then the same Verify y.
            device.hide_ime()
            device.shell(
                "am broadcast -a ADB_HIDE -n com.android.adbkeyboard/.AdbReceiver"
            )
            time.sleep(0.4)
            device.su_tap(540, 1760, 1.0)
            reverify_done = True
            log("reverify_acquire_still", 1760)
            continue
        if typed and verdict == "pending":
            continue
        blob = ((device.ui_blob() or "") + "\n" + (device.screen_text("after.png") or ""))
        if hop_oracle.after_skipg4_overlay(blob) == "dferh_01":
            log("df_dferh_01 after-inspect tap OK 540,1836")
            hop.dismiss_after_skipg4()
            break
        if hop_oracle.skipg4_landed_play_credit(blob):
            # 2026-09-22 hop-2 play-acct see-more.png Choose amount $10 credit.
            # Continue would buy Play credit. BACK only.
            log("play credit BACK, do not Continue")
            device.back(0.4)
            device.back(0.4)
            device.shell("am start -n ai.x.grok/.main.GrokActivity")
            break
        if hop_oracle.skipg4_try_another_payment(blob):
            # 2026-09-21 hop-4 acct n4-after-skipg4.png / n4-see-more.png:
            # wall remapped <last4> then declined; leftover Visa-<last4> Recommended.
            # See more then tap other hop-live (<last4>), never leftover.
            # Blind 458,1750 when the row is gone opens Buy Google Play Credit.
            log("try another payment See more")
            if not device.tap_text("See more payment methods"):
                log("see more row missing, BACK")
                device.back(0.4)
                break
            time.sleep(1.2)
            blob2 = ((device.ui_blob() or "") + "\n" + (device.screen_text("see-more.png") or ""))
            if hop_oracle.skipg4_landed_play_credit(blob2):
                log("play credit BACK, do not Continue")
                device.back(0.4)
                device.back(0.4)
                device.shell("am start -n ai.x.grok/.main.GrokActivity")
                break
            import re

            shown = re.findall(r"(?:visa|mastercard)[\s\-–]*(\d{4})", blob2, re.I)
            pick = hop_oracle.skipg4_see_more_other_live(
                shown,
                declined=hop_oracle.skipg4_declined_last4(blob),
                want=WANT,
                avoid=AVOID,
            )
            log("see more pick", pick, "shown", shown)
            if pick:
                device.tap_text(f"Mastercard-{pick}") or device.tap_text(f"Visa-{pick}")
                time.sleep(2.0)
                continue
            log("see more no other live, stop")
            break
        if device.play_billing_focus() and (
            "subscribe" in blob.lower() or "supergrok" in blob.lower()
        ):
            device.su_tap(540, 1836, 0.8)
    print(json.dumps({"ok": empty, "typed": typed, "rows": rows}, ensure_ascii=False, default=str))
    return 0 if empty else 4


if __name__ == "__main__":
    raise SystemExit(main())
