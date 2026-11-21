#!/usr/bin/env python3
# Sanitized research copy. Ops/account/card/egress specifics removed.
"""Pure hop settle rules. No ADB. Inspect / GET beat Play UI verify."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

BAD_VERIFY = frozenset({"card_declined", "CHARGE_FULL", "charge_full"})


def adb_server_socket_env(platform: str, current: str | None) -> str | None:
    """None = unset ADB_SERVER_SOCKET. Darwin adb 37 cannot use 127.0.0.1 hostname.

    Frozen 2026-09-21 hop-921: `ADB_SERVER_SOCKET=tcp:127.0.0.1:<adb-port>` then
    start-server `cannot start server on remote host` and connect protocol fault.
    Listen is `adb -L tcp:<adb-port>`. Linux keeps tcp:127.0.0.1:<adb-port>.
    """
    if str(platform or "") == "darwin":
        return None
    cur = str(current or "").strip()
    return cur or "tcp:127.0.0.1:5037"


def play_verify_code_from_merchant(text: str) -> str:
    """Play 'Get code' OTP from card-issuer ledger merchant (# ops removed).

    Frozen 2026-09-19 hop-2 acct: Get code then card-issuer <last4> row
    GOOGLE*<x> <otp> US -$1.95. Enter <otp>, Card verification successful.
    """
    import re

    # Suffix is not always NY8. 2026-09-22 hop-3 <last4> ledger: GOOGLE*<x> <otp>.
    m = re.search(r"GOOGLE\*[A-Z0-9]{3}\s+(\d{6})\b", str(text or ""), re.I)
    return m.group(1) if m else ""


def skipg4_has_first_charge(text: str) -> bool:
    """Play dump 'Your first charge will occur on …' / 将于…收取."""
    low = str(text or "").lower()
    return "first charge will occur" in low or "收取" in low


def skipg4_wall_kind(text: str) -> str:
    """skipg4 subscribe wall.

    Today $299 / Starting today $299 is CHARGE_FULL.
    $299 listed with no Today $0, no intro $99.99, and no first-charge copy
    is CHARGE_FULL (frozen 2026-09-19 hop-1 acct skipg4p1m OCR snippet).
    Starting Oct $299.99 plus first-charge copy is deferred restore, not
    CHARGE_FULL (frozen hop-hop1-acct skipg4_once: gate deferred, new GPA
    empty obf AR=true; 2026-09-19 hop-3 acct skipg4-wall.png).
    leftover fromlite intro is $99.99 Starting Oct plus later $299.99.
    """
    low = str(text or "").lower()
    zero = "today $0" in low or "today $0.00" in low or "today  $0" in low
    today_full = (
        ("today $299" in low or "today $299.99" in low or "starting today" in low)
        and ("299.99" in low or "$299" in low)
        and not zero
    )
    if today_full:
        return "CHARGE_FULL"
    has_299 = "299.99" in low or "$299" in low
    intro_99 = "$99.99" in low or "99.99" in low.replace("299.99", "")
    if has_299 and not zero and not intro_99 and not skipg4_has_first_charge(text):
        return "CHARGE_FULL"
    return ""


def skipg4_subscribe_ok(text: str) -> dict[str, Any]:
    """skipg4_once Subscribe: Today $0 or deferred restore (first charge later).

    Frozen hop-hop1-acct skipg4_once: Starting Oct 8 $299.99/month, gate
    deferred, pick last4, typed_once, inspect new GPA empty obf AR=true.
    Frozen 2026-09-19 hop-3 acct skipg4-wall.png: Starting Oct 16 $299.99
    plus Your first charge will occur on Oct 16, 2026.
    Today $299.99 is CHARGE_FULL. skipg4deferred benefits overlay is not
    a subscribe wall (2026-09-19 hop-1 acct).
    """
    blob = str(text or "")
    kind = skipg4_wall_kind(blob)
    if kind == "CHARGE_FULL":
        return {"ok": False, "kind": "CHARGE_FULL", "text": blob[:240]}
    low = blob.lower()
    if "you'll get these benefits" in low or "youll get these benefits" in low:
        return {"ok": False, "kind": "benefits_continue", "text": blob[:240]}
    if skipg4_password_no_internet(blob):
        # 2026-09-23 hop-1 acct h1b: wait_wall landed FLAG_SECURE password
        # + No internet. skipg4_acquire_no_internet ignores password pages,
        # then this fell through to not_today_zero and refused Subscribe.
        return {"ok": False, "kind": "password_no_internet", "text": blob[:240]}
    if skipg4_acquire_no_internet(blob):
        return {"ok": False, "kind": "no_internet", "text": blob[:240]}
    if "unable to change your subscription plan" in low:
        # 2026-10-07 hop5 src43 wall.png: Error + Got it. Not a $0 wall.
        # Classifying it not_today_zero made skip exit 2 without ack.
        return {"ok": False, "kind": "unable_change", "text": blob[:240]}
    if skipg4_play_server_error(blob):
        # Background can be Payments & subscriptions. That page is not the wall.
        return {"ok": False, "kind": "play_server_error", "text": blob[:240]}
    if skipg4_landed_payment_methods(blob):
        return {"ok": False, "kind": "payment_methods", "text": blob[:240]}
    if skipg4_landed_redeem(blob):
        return {"ok": False, "kind": "redeem", "text": blob[:240]}
    if "enter your password" in low or ("remember me" in low and "verify" in low):
        # Subscribe already tapped; wait_wall is the Google password page.
        return {"ok": True, "kind": "password_page", "text": blob[:240]}
    if "today $0" in low or "today $0.00" in low or "today  $0" in low:
        return {"ok": True, "kind": "today_zero", "text": blob[:240]}
    if skipg4_has_first_charge(blob) and "today $299" not in low:
        return {"ok": True, "kind": "deferred_restore", "text": blob[:240]}
    return {"ok": False, "kind": "not_today_zero", "text": blob[:240]}


def skipg4_ask_home(blob: str) -> bool:
    """Ask / Imagine home is ready for another fire. It is not the splash.

    2026-10-07 hop1 src28: three splash refires left Grok on Ask / Imagine
    (Try SuperGrok, Ask anything). skipg4_subscribe_ok called that
    not_today_zero and skip exited 2. Screenshot hop1-skip28.png is that
    home. Fire again. Do not force-stop. Blank OCR and the logo splash
    stay died-home.
    """
    low = (blob or "").lower()
    if destg4_grok_died_home(blob):
        return False
    if "subscribe" in low or "super grok heavy" in low.replace(" ", ""):
        return False
    return ("ask" in low and "imagine" in low) or "ask anything" in low or "try supergrok" in low


P1M_KINDS = frozenset({"item_unavailable", "timeout_continue", "still_wall"})
OWNED_KINDS = frozenset({"already_own", "success", "left_wall", "left_wall_subs", "play_heavy_row", "inspect_hit"})


def _obf(row: dict[str, Any] | None) -> str:
    if not isinstance(row, dict):
        return ""
    return str(row.get("obf_full") or row.get("obf") or row.get("obfuscatedAccountId") or "")


def _order(row: dict[str, Any] | None) -> str:
    if not isinstance(row, dict):
        return ""
    return str(row.get("order") or row.get("orderId") or "")


def _sku(row: dict[str, Any] | None) -> str:
    if not isinstance(row, dict):
        return ""
    return str(row.get("sku") or row.get("productId") or "")


def should_fire_skipg4(ultra: dict[str, Any] | None) -> bool:
    """Fire skipg4 only when leftover ultra still has a GID."""
    if not isinstance(ultra, dict):
        return False
    if _sku(ultra) != "grok.ultra":
        return False
    return bool(_obf(ultra))


def skipg4_success(
    pre: dict[str, Any] | None,
    post: dict[str, Any] | None,
    verify_kind: str = "",
) -> bool:
    """Washed leftover: ultra still there, obfuscatedAccountId empty.

    New GPA is typical. timeout_continue / already_own after a $0 replace
    is success when inspect already shows empty obf. CHARGE_FULL / decline
    never count.
    """
    kind = str(verify_kind or "")
    if kind in BAD_VERIFY:
        return False
    if _sku(post) != "grok.ultra":
        return False
    post_obf = _obf(post)
    if post_obf:
        return False
    pre_obf = _obf(pre)
    new_gpa = bool(_order(post) and _order(post) != _order(pre))
    if new_gpa:
        return True
    if pre_obf and not post_obf:
        return True
    return kind in OWNED_KINDS or kind == "play_error"


def destg4_success(
    *,
    dest_ultra_active: bool,
    inspect_obf: str = "",
    dest_gid: str = "",
    verify_kind: str = "",
    dest_sso_ok: bool = True,
    dest_jwt_is_source: bool = False,
    src_ultra: bool | None = None,
    dest: str = "",
    dest_get_user_email: str = "",
    dest_get_user_status: int = 0,
) -> bool:
    """True when dest holds the moved ultra.

    src_ultra True means the source GET still has grok.ultra ACTIVE.
    2026-09-26 acct: outer dest GET was ultra+cap while the source
    still had a different tok8 from the same skipg4. That is not a hop.
    """
    kind = str(verify_kind or "")
    if kind in BAD_VERIFY:
        return False
    if src_ultra is True:
        return False
    if dest_jwt_is_source:
        return False
    if not dest_sso_ok:
        return False
    dest_e = str(dest or "").strip().lower()
    if dest_e:
        email_err = dest_sso_email_ok(
            dest=dest_e,
            get_user_email=dest_get_user_email,
            get_user_status=dest_get_user_status,
        )
        if email_err:
            return False
    if dest_ultra_active:
        return True
    gid = str(dest_gid or "")
    obf = str(inspect_obf or "")
    return bool(gid and obf and obf == gid)


def destg4_record_hopped(record: dict[str, Any] | None) -> bool:
    """Outer destg4 record decides the hop. A nested verify timeout does not.

    2026-09-27 acct: destg4p1m_verify ok false, timeout_continue, GET True
    False, then cancel2 and cap True True. The outer line is get_user 200,
    src_ultra false, dest ultra and cancelAtPeriodEnd. That row stays hopped.
    The same shape with src_ultra true does not.
    """
    if not isinstance(record, dict):
        return False
    nested = record.get("destg4")
    if not isinstance(nested, dict):
        nested = {}
    stage = str(nested.get("stage") or "")
    if stage == "destg4p1m_verify" and nested.get("ok") is False:
        verify_kind = "timeout_continue"
    elif nested.get("ok") is True:
        verify_kind = "success"
    else:
        verify_kind = stage
    email = str(record.get("get_user_email") or "")
    return destg4_success(
        dest_ultra_active=bool(record.get("has_ultra_active")) and bool(record.get("cancelAtPeriodEnd")),
        verify_kind=verify_kind,
        dest_sso_ok=True,
        src_ultra=True if record.get("src_ultra") is True else False if record.get("src_ultra") is False else None,
        dest=str(record.get("dest") or ""),
        dest_get_user_email=email,
        dest_get_user_status=int(record.get("get_user") or 0),
    )


def dest_sso_email_ok(
    *,
    dest: str,
    get_user_email: str = "",
    get_user_status: int = 0,
) -> str | None:
    """None = grok.com get-user 200 and email==dest.

    2026-09-26 acct: x.ai session email==dest, persisted grok.com
    SSO get-user was acct. sqlite dest_sso_shared missed it.
    Persist and ingest require this gate. get-user 401 is dest_get_user_not_live.
    """
    dest_e = str(dest or "").strip().lower()
    got = str(get_user_email or "").strip().lower()
    st = int(get_user_status or 0)
    if not dest_e:
        return "dest_not_found"
    if st == 200:
        if got == dest_e:
            return None
        return "dest_sso_email_mismatch"
    return "dest_get_user_not_live"


def destg4_get_user_from_login(
    dest: str,
    login_get_user_status: int,
    login_get_user_email: str,
    dest_ultra: bool,
    dest_cap: bool,
    src_ultra: bool | None,
) -> tuple[int, str] | None:
    """Reuse dest_login login.json get-user instead of grok-sso Chrome get_user.

    hop-929 destg4.json n=23: outer sso_refresh.get_user 401/403
    dest_get_user_not_live while grpc GET dest ultra True cap True src_ultra
    False. grok-sso Chrome is not the dest_login grok-sso-N session, and
    that call flocks every destg4 onto one instance. Returning (200, dest)
    lets destg4 persist_play_bind without dest-post dest_login.
    """
    dest_e = str(dest or "").strip().lower()
    if src_ultra is True:
        return None
    if not dest_ultra or not dest_cap:
        return None
    if dest_sso_email_ok(
        dest=dest_e,
        get_user_email=login_get_user_email,
        get_user_status=int(login_get_user_status or 0),
    ):
        return None
    return 200, dest_e


def bound_play_mismatch(notes: str, hop_play: str, live_tok8: str = "") -> str:
    """Empty when this Play is the source's bound play, or notes name none.

    2026-10-07 src 83: destg4 on play-acct bought a new tok8 while acct
    kept <tok8> on play-acct. A second heavy is not a hop. With no live
    tok8, skip and destg4 must use the last `play ...` in the source notes.
    2026-10-07 src 33: the live purchase tok stayed on an earlier Play.
    The last Play's latest tok was a washed token and the source stayed
    ultra. When live_tok8 is set, the Play whose latest tok8 equals it
    is the bind. An older tok8 line on the last Play does not count.
    """
    raw = str(notes or "").lower()
    pairs = re.findall(
        r"play\s+([a-z0-9._+-]+@[a-z0-9.-]+)\s+tok8\s+([a-z0-9]{8})",
        raw,
    )
    plays = re.findall(r"play\s+([a-z0-9._+-]+@[a-z0-9.-]+)", raw)
    if not plays and not pairs:
        return ""
    got = str(hop_play or "").strip().lower()
    live = str(live_tok8 or "").strip().lower()
    if live:
        latest: dict[str, str] = {}
        for play, tok in pairs:
            latest[play] = tok
        owners = [play for play, tok in latest.items() if tok == live]
        if len(owners) == 1 and got == owners[0]:
            return ""
        return "play_not_source_bind"
    if not plays:
        return "play_not_source_bind"
    if got == plays[-1]:
        return ""
    return "play_not_source_bind"


def src_ultra_when_dest_ready(
    fetch,
    *,
    dest_ready: bool,
    attempts: int = 5,
    pause_s: float = 12,
    sleep=None,
):
    """Re-read source ultra only after dest is already ultra and capped.

    2026-10-03 acct hop-4: dest GET was ultra+cap and the wall had
    already been subscribed, but one source GET was still True. Login reuse
    then refused and the shared grok-sso get_user returned -1, so destg4
    exited 2 without persist. The same source GET was False about a minute
    later, and the already_capped path persisted with no second purchase.
    A False or a dest that is not ready returns the first read.
    """
    if sleep is None:
        import time

        sleep = time.sleep
    tries = attempts if dest_ready else 1
    last = None
    for i in range(max(1, int(tries))):
        last = fetch()
        if not isinstance(last, bool):
            return None
        if not dest_ready or last is False:
            return last
        if i + 1 < tries:
            sleep(pause_s)
    return True


def sso_jwt_conflict(*, dest: str, jwt: str, others: list[tuple[str, str]]) -> str | None:
    """None = dest SSO is dest-only. dest_sso_shared if another email has the same jwt."""
    dest_e = str(dest or "").strip().lower()
    token = str(jwt or "").strip()
    if not dest_e:
        return "dest_sso_missing"
    if not token.startswith("eyJ"):
        return "dest_sso_missing"
    for email, other in others:
        if str(email or "").strip().lower() == dest_e:
            continue
        if str(other or "").strip() == token:
            return "dest_sso_shared"
    return None


def should_fallback_p1m(*, verify_kind: str, oracle_ok: bool) -> bool:
    if oracle_ok:
        return False
    kind = str(verify_kind or "")
    if kind in BAD_VERIFY or kind == "play_error":
        return False
    return kind in P1M_KINDS


def after_skipg4_overlay(blob: str) -> str:
    """Classify skipg4 post-pay sheets. Screenshot-proven 2026-09-18 Grok-2/4.

    auth_no_thanks: Payment successful + Require authentication + No, thanks radio.
    play_points_not_now: Play Points sheet with Not now (two-button 293,1836 or stacked 539,1509).
    backup_back: Turn on backup payment methods. Only BACK, never Turn on
    (2026-09-19 hop-4 acct hop4-after-skipg4.png; hop-1 acct).
    backup_add_no_thanks: Want to add this backup payment method? leftover
    Visa last4 + No thanks / Add. Tap No thanks, never Add
    (2026-09-20 hop-3 acct hop3-washed.png Visa-<last4>).
    Empty: no overlay.
    """
    low = (blob or "").lower()
    # 2026-09-29 hop-4 acct-after-skip.png: subscribe already landed, sheet is
    # Something went wrong on our end / Got it on Payments & subscriptions.
    # Tap Got it. Do not treat it as backup or as a declined card.
    if "something went wrong on our end" in low:
        return "play_server_error"
    # 2026-09-29 hop-4 acct after.png / v.png / ui.xml:
    # Error retrieving information from server. DF-DFERH-01. Button OK
    # bounds [63,1789][1017,1884] = tap 540,1836. skipg4_once looped
    # after-inspect 90s on a 9397-byte dump. Tap OK, do not Subscribe,
    # do not Try SuperGrok.
    if "df-dferh-01" in low:
        return "dferh_01"
    if "require authentication" in low and ("no, thanks" in low or "no thanks" in low):
        return "auth_no_thanks"
    if "play points" in low and "not now" in low:
        return "play_points_not_now"
    if "want to add this backup payment method" in low or (
        "backup payment method" in low and "no thanks" in low and "add" in low
    ):
        return "backup_add_no_thanks"
    if "turn on backup payment methods" in low or (
        "backup payment methods" in low and "turn on" in low and "manage" in low
    ):
        return "backup_back"
    # 2026-10-07 hop2 src10: dismiss sat on Win grand prizes / Play Fest.
    # Not now is the left pill. Explore is the right pill.
    if playfest_prize_sheet(low):
        return "playfest_not_now"
    return ""


def bind_pm_needs_scroll(blob: str) -> bool:
    """Payment list is open but Add card is below the fold.

    2026-10-09 hop-4 3k22o1 pay-list3.png and gate-bind-after.png: seven
    cards filled the screen, Add credit or debit card was under Backup.
    open_payment_methods never saw add credit, so both binds returned
    pm_timeout and the new last4 was not listed. One swipe reveals the row.
    """
    low = (blob or "").lower()
    if "add credit" in low or "card number" in low or "debit card" in low:
        return False
    if "payment methods" not in low:
        return False
    return "mastercard" in low or "visa-" in low


def bind_no_internet_retry(blob: str) -> bool:
    """Play No Internet dialog during bind: tap Retry, do not back out.

    2026-10-09 hop-4 718glpme bind_timeout.png: dialog No Internet Connection
    with Cancel and Retry. The timeout path backed out, bind_apply_timeout,
    Payment methods still without the new last4. Ping was up a minute later
    and the same bind listed the card. Tapping Retry keeps the filled form.
    """
    low = (blob or "").lower()
    return "no internet connection" in low and "retry" in low


def bind_timeout_should_tap_save(blob: str, last4: str = "") -> bool:
    """bind_apply_timeout still on filled Add-card form: tap Save card.

    Frozen 2026-09-19 hop-1 acct: dump All fields required + United States +
    Billing zip <zip> + Save card after bind_apply_timeout; Payment methods
    still leftover last4. tap_text Save card then Mastercard-<last4> listed.
    Already-listed last4 on Payment methods is not this.
    2026-09-22 hop-1 acct _ui_bind_timeout.xml: Save card + expiration +
    security code + <zip>, and the phrase All fields required is absent.
    Payment methods screenshot stayed Mastercard-<last4> + Visa-<last4>.
    """
    low = (blob or "").lower()
    want = str(last4 or "").lower()
    if "save card" not in low:
        return False
    if "payment methods" in low and "expiration" not in low and "security code" not in low:
        return False
    if want and (f"mastercard-{want}" in low or f"visa-{want}" in low) and "expiration" not in low:
        return False
    if "all fields required" in low:
        return True
    return "expiration" in low and "security code" in low


def play_points_not_now_center(nodes: list[dict] | None) -> tuple[int, int] | None:
    """Introducing Google Play Points: tap Not now, never Learn more.

    2026-09-22 hop-4 acct bind-miss.png. Dump Not now (539, 1509),
    Learn more (539, 1372). Not now must sit below Learn more.
    """
    not_now = None
    learn = None
    for n in nodes or []:
        text = str(n.get("text") or "").replace("&amp;", "&").strip().lower()
        if text == "not now":
            not_now = n
        elif text == "learn more":
            learn = n
    if not not_now or not learn:
        return None
    ny = int(not_now.get("cy") or 0)
    ly = int(learn.get("cy") or 0)
    if ny <= ly:
        return None
    return int(not_now.get("cx") or 0), ny


def destg4_benefits_continue(blob: str) -> bool:
    """destg4p1m sheet You'll get these benefits if you subscribe. Tap Continue then Subscribe.

    2026-09-18 grok-hop-1/2 destg4p1m_gate unknown with this text, then overlay gone.
    """
    low = (blob or "").lower()
    return "you'll get these benefits if you subscribe" in low or "you will get these benefits if you subscribe" in low


# Sanitized research copy. Ops/account/card/egress specifics removed.
# # ops removed: the original hard-coded the operation's live/explicit card
# last4 sets here (real BIN-issuers' last4). This copy loads them from env
# (comma separated), keeping the preference-order mechanism below intact:
#   HOP_LIVE_LAST4    hop-live cards, weak preference order
#   HOP_FUNDED_LAST4  funded hop-live cards, preferred over the weak set
#   HOP_EXPLICIT_LAST4  operator-verified want last4 that must never be remapped
# History (all card numbers redacted):
# - 2026-09-23 hop-2 acct: wall-list OCR showed two hop-live cards; the remap
#   target had declined, prefer the other hop-live card when both appear.
# - 2026-09-27 acct: two hop-live cards OR_CCREU, one OR_MIVEM; a newly bound
#   card-product card eventually listed and was used.
# - 2026-10-09 hop-5 acct: a clean non-hop-live card on the payment list must
#   stay selected; hop_live_remap_wall_dump must not rewrite an explicit want.
# - 2026-10-11/12: operator-verified want last4 must never be remapped onto a
#   hop-live card even when the wall already shows the hop-live card.
HOP_LIVE_LAST4 = tuple(
    x.strip() for x in os.environ.get("HOP_LIVE_LAST4", "").split(",") if x.strip()
)
HOP_FUNDED_LAST4 = tuple(
    x.strip() for x in os.environ.get("HOP_FUNDED_LAST4", "").split(",") if x.strip()
)
HOP_EXPLICIT_LAST4 = tuple(
    x.strip() for x in os.environ.get("HOP_EXPLICIT_LAST4", "").split(",") if x.strip()
)


def hop_live_last4_on_list(shown: list[str] | None, want: str, avoid: str = "") -> str:
    """Wall leftover dest Play often already carries a hop-live last4, not the want.

    Frozen 2026-09-20 three desks: want <last4>, list Mastercard-<last4>
    (+ leftover <last4-list>). Use the listed hop-live card, do not bind a
    second PAN. Prefer want if already shown.
    2026-09-22 hop-3 acct: want <last4>, wall OCR only <last4>, and that card
    is in HOP_AVOID with a 0 balance. Do not remap onto avoid.
    2026-10-01 hop-929 hop-4 acct: wall showed three hop-live cards; the remap
    prefers funded hop-live over the weak set. Only one hop-live on the list
    still remaps onto it.
    """
    shown = [str(x) for x in (shown or [])]
    want = str(want or "").strip()
    avoids = {a.strip() for a in str(avoid or "").split(",") if a.strip()}
    if want and want in shown and want not in avoids:
        return want
    for live in HOP_FUNDED_LAST4:
        if live in shown and live not in avoids:
            return live
    for live in HOP_LIVE_LAST4:
        if live in shown and live not in avoids:
            return live
    return ""


def hop_live_remap_wall_dump(want: str) -> bool:
    """FLAG_SECURE Subscribe dump may show a declined hop-live last4.

    2026-09-23 hop-2 acct: want <last4>, wall dump shown <last4>, list OCR <last4>.
    Keep an explicit hop-live want; open the payment list instead of remapping.
    Non-live want still remaps via hop_live_last4_on_list.
    2026-10-07 hop-5: want <last4>, dump shown <last4>. <last4> is not in HOP_LIVE_LAST4,
    so the old check remapped and subscribed the declined card.
    """
    want = str(want or "").strip()
    return want not in HOP_LIVE_LAST4 and want not in HOP_EXPLICIT_LAST4


def remap_want_on_open_list(want: str, shown: list[str] | None, avoid: str = "") -> str:
    """Payment-methods list is open and want last4 is missing.

    hop-929 hop-4 acct destg4p1m_wall_card: want <last4> shown
    <last4-list>, wall-list.png Mastercard-<last4>. hop-929 hop-5
    acct destg4p1m_wall_card: want <last4> shown <last4-list>.
    hop_live_remap_wall_dump keeps hop-live want, so destg4 stayed on <last4>.
    Remap to funded hop-live on the open list (<last4> over <last4-list>).
    """
    want = str(want or "").strip()
    shown = [str(x) for x in (shown or [])]
    if want and want in shown:
        return want
    # Verified HOP_PAY_LAST4 stays even when the open-list dump only shows
    # a declined leftover. Substituting <last4> subscribed the wrong card.
    if want in HOP_EXPLICIT_LAST4:
        return want
    live = hop_live_last4_on_list(shown, want, avoid)
    return live or want


def google_account_recovery(blob: str) -> bool:
    """MinuteMaid Account recovery after 2FA chooser Try another way.

    Frozen 2026-09-21 hop-2 acct h2-try-another3.png: Account recovery,
    Get a verification code at the Play <domain> mailbox itself. Hotmail may be absent.
    """
    low = str(blob or "").lower()
    return "account recovery" in low and "verification code" in low


def totp_wrong_code(blob: str) -> bool:
    """MinuteMaid Authenticator 'Wrong code. Try again.'

    Frozen 2026-09-21 hop-2 acct h2-totp3.png / hop-3 acct h3-totp3.png:
    Galaxy TRY ANOTHER WAY Authenticator, totp_fresh, host Date == Google Date,
    still Wrong code = inventory secret rotated. Do not keep submitting.
    """
    low = str(blob or "").lower()
    return "wrong code" in low and "try again" in low


def google_2fa_chooser_try_another_row(blob: str) -> bool:
    """2FA chooser list row 'Try another way', not only bottom 200,1836.

    Frozen 2026-09-21 hop-3 acct h3-try-another.png / h3-chooser.xml:
    Choose how you want to sign in + Authenticator + Try another way
    bounds [168,1086][1021,1147] cy~1116. Bottom TRY ANOTHER WAY is absent
    on this layout. Tap the list row, then Account recovery email.
    """
    low = str(blob or "").lower()
    return "choose how you want to sign in" in low and "try another way" in low


def google_asia_mail_code(payload: dict[str, Any] | None) -> str:
    """Play recovery mailbox 谷歌验证码 panel /api/fetch JSON.

    Frozen 2026-09-21 hop-2 play-acct h2-code-filled.png code <otp>,
    hop-3 play-acct h3-send-code.png then <otp>. Clash fake-ip 198.18
    breaks IMAP; DoH A then HTTPS --resolve mail.<domain>/api/fetch.
    """
    if not isinstance(payload, dict) or payload.get("success") is not True:
        return ""
    code = str(payload.get("code") or "").strip()
    if code.isdigit() and len(code) == 6:
        return code
    emails = payload.get("emails") if isinstance(payload.get("emails"), list) else []
    for mail in emails:
        if not isinstance(mail, dict):
            continue
        c = str(mail.get("code") or "").strip()
        if c.isdigit() and len(c) == 6:
            return c
    return ""


def bind_timeout_listed(blob: str, last4: str) -> bool:
    """bind_apply_timeout JSON but Payment methods already lists want last4.

    Frozen 2026-09-21 hop-2 acct h2-bind-live.png: cmd_bind returned
    bind_apply_timeout, dump Mastercard-<last4> on Payment methods = success.
    Do not retry the same PAN.

    2026-10-09 acct gate-bind-after.png: Mastercard-<last4> was on the list
    with Verification needed and Update. ocr_listed still returned ok.
    That row is not a chargeable bind.
    """
    last4 = str(last4 or "").strip()
    if len(last4) != 4:
        return False
    low = str(blob or "").lower()
    if "payment methods" not in low:
        return False
    tail = last4.lower()
    for label in (f"mastercard-{tail}", f"visa-{tail}"):
        idx = low.find(label)
        if idx < 0:
            continue
        window = low[idx:idx + 900]
        rest = window[len(label):]
        cut = len(rest)
        for mark in ("mastercard-", "visa-"):
            j = rest.find(mark)
            if 0 <= j < cut:
                cut = j
        row = window[: len(label) + cut]
        if "verification needed" in row:
            return False
        return True
    return False


def hop_live_after_ccreu(tried: list[str] | None, live: list[str] | None = None) -> str:
    """After OR_CCREU, try remaining hop-small last4 including same BIN.

    Frozen 2026-09-21 hop-1 acct play-acct: <last4> CCREU then <last4> CCREU,
    Mastercard-<last4> (same BIN as <last4>) listed on Payment methods
    (h1-fu3-pm.png). Do not swap_account until remaining hop-live
    last4 are tried. 2026-09-27 play-acct: <last4> and <last4> OR_CCREU, <last4>
    OR_MIVEM, <last4> not spendable, next listed hop-live is <last4>.
    """
    tried_set = {str(x).strip() for x in (tried or []) if str(x).strip()}
    pool = [str(x).strip() for x in (live or list(HOP_LIVE_LAST4)) if str(x).strip()]
    for last4 in pool:
        if last4 not in tried_set:
            return last4
    return ""


def reset_mail_unreceived_skip(unreceived: int) -> str:
    """Source password reset. One unreceived mail is retry.

    Two consecutive unreceived mails are the only skip. 2026-09-27
    acct-40 did not send a reset, so this gate skipped nobody.
    """
    if int(unreceived or 0) >= 2:
        return "skip"
    return "retry"


def documented_tok_matches_live(doc_tok8: str, live_tok8: str) -> bool:
    """An older 不订 library line is this buyer when tok8 equals the live GET.

    2026-09-27 acct: play-acct <tok8>, play-acct <tok8>, play-acct <tok8>,
    play-acct <tok8>. Switch that Play. A different live tok is not that line.
    """
    doc = str(doc_tok8 or "").strip().lower()
    live = str(live_tok8 or "").strip().lower()
    return len(doc) == 8 and doc == live


def _local_part(email: str) -> str:
    return str(email or "").strip().lower().split("@", 1)[0]


def prior_hop_workdir_buyer(
    *,
    notes: str,
    workdir_play: str,
    library_tok8: str,
    live_tok8: str,
) -> str:
    """Earlier hop work dir is the buyer when notes only say hop dest from.

    2026-09-27 acct: 14 hotmail notes had no play line. The Play logged in
    during the 2026-09-24 hop still held the live GET tok8 after switch and
    sync. play-acct <tok8>, play-acct <tok8>, play-acct <tok8>, play-acct
    <tok8>, play-acct <tok8>, play-acct <tok8>, play-acct <tok8>, play-acct
    <tok8>, play-acct <tok8>, play-acct <tok8>, play-acct <tok8>,
    play-acct <tok8>, play-acct <tok8>, play-acct <tok8>. A tok mismatch
    or a missing work-dir Play is not a buyer.
    """
    notes_l = str(notes or "").lower()
    if "hop dest from" not in notes_l:
        return ""
    if "play " in notes_l and "tok8" in notes_l:
        return ""
    if not _local_part(workdir_play):
        return ""
    if not documented_tok_matches_live(library_tok8, live_tok8):
        return ""
    return "switch"


def library_pull_after_switch(
    *,
    switched_to: str,
    library_account: str,
    library_tok8: str = "",
    live_tok8: str = "",
) -> str:
    """First library pull after switch is often the previous Google.

    2026-09-27 acct first pull was play-acct, acct was play-acct, acct was
    play-acct. sync_play_library, then SQL pull. Do not subscribe that row.
    The current account plus a tok8 that equals the live GET is subscribe_ok.
    """
    want = _local_part(switched_to)
    got = _local_part(library_account)
    if not want or got != want:
        return "sync"
    if documented_tok_matches_live(library_tok8, live_tok8):
        return "subscribe_ok"
    return "hold"


def dest_login_transport_retry(err: str) -> str:
    """chrome-error and unauthenticated_sso stay on the same grok-sso label.

    They are not a password reset. 2026-09-27 acct: two chrome-error, third
    login get_user 200. acct: chrome-error, then grok.com unauthenticated_sso,
    third login get_user 200. acct: one chrome-error, then get_user 200.
    invalid-credentials is the reset path.
    """
    key = str(err or "").strip().lower()
    if "chrome-error" in key or "chromewebdata" in key or key == "unauthenticated_sso":
        return "retry"
    if key == "invalid-credentials":
        return "reset"
    return ""


def destg4_desk_ready(*, desk_account: str, washed_play: str) -> bool:
    """destg4 runs only on the desk that currently holds the washed Play.

    2026-09-27 acct was switched away to play-acct. destg4 ran after the desk
    accounts list was only play-acct. A switch JSON that still names a second
    account does not count; the live account does.
    """
    desk = _local_part(desk_account)
    play = _local_part(washed_play)
    return bool(desk) and desk == play


def no_play_identity_action(*, play_email: str = "", library_hits: int = 0) -> str:
    """No buyer Google means there is nothing to swap.

    2026-09-27 acct-40: 18 still-Heavy toks and 3 sources with no ACTIVE
    ultra had 0 note hits and 0 rows on the four live libraries
    (<serial> play-acct, <serial> play-acct, <serial> play-acct, <serial> play-acct).
    swap_card, did_rotate, and swap_account were not run.
    """
    if str(play_email or "").strip() or int(library_hits or 0) > 0:
        return ""
    return "no_play_identity"


def reject_next(kind: str) -> str:
    """A refusal swaps that one thing. It is not a completed hop.

    card -> swap_card, did -> did_rotate, account -> swap_account.
    2026-09-27 acct-40 used a listed <last4> or <last4>. A list that was only
    <last4> or a leftover Visa was bound to <last4> before subscribe.
    """
    key = str(kind or "").strip().lower().replace(" ", "")
    if key in {"card", "拒卡", "or_ccreu", "or_mivem", "or-pfgvem", "or_pfgvem"}:
        return "swap_card"
    if key in {"did", "拒did", "or-hdt", "or_hdt"}:
        return "did_rotate"
    if key in {"account", "拒号", "google"}:
        return "swap_account"
    return ""


def hop_count_allowed(
    *,
    get_user_status: int,
    get_user_email: str,
    dest: str,
    xai_password: str,
    mail_password: str,
    xai_login_ok: bool,
    src_ultra: bool,
    dest_ultra: bool,
    dest_cap: bool,
) -> bool:
    """True only after dest SSO and grok password worked, then the transfer.

    get-user must be 200 and email==dest. grok password must be split from
    the mailbox password and stamped by dest_login. After destg4 the source
    must not hold ultra and the dest must hold ultra with cancelAtPeriodEnd.
    """
    if int(get_user_status or 0) != 200:
        return False
    if str(get_user_email or "").strip().lower() != str(dest or "").strip().lower():
        return False
    xai = str(xai_password or "").strip()
    if not xai or xai == str(mail_password or ""):
        return False
    if not xai_login_ok:
        return False
    if src_ultra:
        return False
    if not (dest_ultra and dest_cap):
        return False
    return True


def cancel_stale_page_action(low: str, saw: list[str] | None = None) -> str:
    """done, wait, or continue for an already-canceled manage page.

    2026-10-09 hop-5 localhost:<serial>: the sku URL opened the washed GPA
    (Canceled, will end Nov 1, Resubscribe). cancel_grok returned kind
    canceled with an empty saw. The new GPA stayed on Next payment with
    Cancel subscription, and three cap reads stayed True False. That
    manage page then showed the active row. A canceled page is done only
    after this call tapped cancel_right or confirm. Before that, wait.
    Eight waits cover the flip. Any other page continues.
    """
    text = (low or "").lower()
    finished = ("resubscribe" in text) or ("canceled" in text and "will end" in text)
    if not finished:
        return "continue"
    seen = list(saw or [])
    if "cancel_right" in seen or "confirm" in seen:
        return "done"
    if sum(1 for item in seen if item == "stale_canceled") >= 8:
        return "done"
    return "wait"


def cancel_server_error_dialog(blob: str) -> bool:
    """Play Error sheet: Server error. OCR often misses the OK label.

    2026-10-07 hop2 src10 cancel-end.png: Manage subscription still showed
    Next payment Oct 29 and Mastercard-<last4> under Error / Server error / OK.
    cancel_grok had tapped Cancel three times, then kind None.
    """
    low = (blob or "").lower()
    if "server error" not in low:
        return False
    if "no internet" in low or "resubscribe" in low:
        return False
    return "error" in low


def cancel_no_internet_dialog(blob: str) -> bool:
    """Play Error sheet on Manage subscription: No internet connection + OK.

    2026-09-29 hop-1 acct cancel.png. cancel_grok dumped that sheet until
    kind None while Heavy was already active. Dismiss OK and keep canceling.
    A canceled page with Resubscribe is not this sheet.
    """
    low = (blob or "").lower()
    if "no internet" not in low:
        return False
    return "ok" in low or "try again" in low


def cancel_authentication_required(blob: str) -> bool:
    """Play Manage subscription: Authentication is required. Sign in to Google.

    Frozen 2026-10-01 hop-1 hop1-cancel-fail.png / hop1-auth.xml: body
    "Authentication is required. You need to sign in to your Google Account."
    Try again [382,896][697,1001]. Tapping Try again left hop1-after-tryagain.png
    identical. Not cancel_no_internet_dialog (no "no internet"). cancel_grok
    must stop with play_auth_required; re-auth Play (REMOVE+ADD), then cancel_cap.
    """
    low = (blob or "").lower()
    if "no internet" in low:
        return False
    if "authentication is required" not in low:
        return False
    return "google account" in low or "sign in" in low


def dest_attach_pending(dest_ultra: bool, obf: str, gid: str) -> bool:
    """Library purchase already belongs to the fired dest gid, grpc not yet ultra.

    2026-10-09 hop-1 play-acct: Subscribe left the wall onto the previous
    Canceled page. GET and GET2 were false. A later inspect showed a new
    GPA whose obfuscatedAccountId started with the fired gid. A second
    fire returned unable to change your subscription plan. Wait for grpc.
    Do not fire again.
    """
    if dest_ultra:
        return False
    head = str(gid or "").strip().lower()[:16]
    got = str(obf or "").strip().lower()
    if len(head) < 8 or len(got) < 8:
        return False
    return got.startswith(head)


def dest_tok8_from_get_rows(rows: list[dict[str, Any]] | None) -> str:
    """purchaseToken[:8] from dest GET rows. ACTIVE beats INACTIVE.

    Frozen 2026-10-01 hop-1 acct dest-post: row0 INACTIVE tok8
    <tok8> (COUNT 32 wash), row1 ACTIVE tok8 <tok8> (cancel_cap). First
    token would persist the washed GPA. sku may be empty on these rows.
    """
    active = ""
    active_ultra = ""
    first = ""
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        g = row.get("google") if isinstance(row.get("google"), dict) else {}
        tok = str(g.get("purchaseToken") or row.get("purchaseToken") or "")
        if len(tok) < 8:
            continue
        t8 = tok[:8].lower()
        if not first:
            first = t8
        st = str(row.get("status") or row.get("state") or "").upper()
        sku = str(row.get("sku") or row.get("productId") or row.get("product") or "").lower()
        is_active = st == "ACTIVE" or st.endswith("STATUS_ACTIVE") or bool(row.get("active"))
        if not is_active:
            continue
        if "ultra" in sku:
            active_ultra = t8
            break
        if not active:
            active = t8
    return active_ultra or active or first


def skipg4_try_another_payment(blob: str) -> bool:
    """skipg4 Subscribe then Play 'Try another payment method' after hop-live decline.

    Frozen 2026-09-21 hop-4 acct n4-after-skipg4.png: Mastercard-<last4> declined,
    leftover Visa-<last4> Recommended. Do not tap leftover. See more then other hop-live.
    """
    low = str(blob or "").lower()
    return "try another payment method" in low and "declined" in low


def skipg4_declined_last4(blob: str) -> str:
    """Last4 marked declined on the Try another overlay.

    Frozen hop-4 acct: 'Mastercard-<last4> | This payment method has been declined'.
    Do not take leftover Visa-<last4> from 'Try again with Visa-<last4>'.
    """
    import re

    m = re.search(
        r"(?:visa|mastercard)[\s\-–]*(\d{4})\s*(?:\||\n)?\s*this payment method has been declined",
        str(blob or ""),
        re.I,
    )
    return m.group(1) if m else ""


def skipg4_see_more_other_live(
    shown: list[str] | None, declined: str, want: str, avoid: str = ""
) -> str:
    """After hop-live decline, pick another hop-live from See more. Never leftover.

    Frozen 2026-09-21 hop-4 acct n4-see-more.png: <last4> declined, Visa-<last4>
    Recommended, Mastercard-<last4> listed. Pick <last4>.
    """
    shown = [str(x) for x in (shown or [])]
    want = str(want or "").strip()
    banned = set()
    for chunk in (declined, avoid):
        for bit in str(chunk or "").split(","):
            bit = bit.strip()
            if bit:
                banned.add(bit)
    if want and want in shown and want not in banned:
        return want
    for live in HOP_LIVE_LAST4:
        if live in shown and live not in banned:
            return live
    return ""


def skipg4_play_server_error(blob: str) -> bool:
    """Play Error sheet: Something went wrong on our end. Button is Got it.

    Frozen 2026-09-29 hop-4 acct wall.png: Payments & subscriptions behind
    Error / Something went wrong on our end. Please try again. / Got it.
    OCR repeated the same sheet for the whole wait_wall. There is no
    Try again button. Do not Subscribe. Tap Got it and refire.
    """
    low = str(blob or "").lower()
    return "something went wrong on our end" in low


def skipg4_acquire_no_internet(blob: str) -> bool:
    """Acquire Error No internet OK overlay, not the password page.

    Frozen 2026-09-21 hop-4 acct hop4-net0.png dump:
    Error | No internet connection | OK. play_egress was HK until US_EGRESS proxy play.
    """
    low = str(blob or "").lower()
    if "no internet connection" not in low:
        return False
    if "enter your password" in low or "verify" in low:
        return False
    return "error" in low or "ok" in low


def skipg4_landed_payment_methods(blob: str) -> bool:
    """skipg4 fire from Payment methods never opens Starting Oct wall.

    Frozen 2026-09-21 hop-1 acct hop1-wall.png / skipg4_once OCR:
    Payment methods | Mastercard-<last4> | Visa-<last4> | Add credit or debit card.
    BACK + am start Grok then skipg4_once.
    """
    low = str(blob or "").lower()
    if "starting oct" in low or ("subscribe" in low and "super" in low):
        return False
    if skipg4_landed_redeem(blob):
        return False
    if "payments & subscriptions" in low or "payments &amp; subscriptions" in low:
        return True
    if "payment methods" not in low:
        return False
    if "add credit" in low or "add card" in low or "add paypal" in low:
        return True
    # hop-4 2026-10-10 acct hop-4-pm.png: Mastercard-<last4> / <last4> /
    # <last4> / Visa-<last4>, Redeem and Play Credit only. skipg4_subscribe_ok
    # fell through to not_today_zero SKIP_EXIT 2.
    return "mastercard-" in low or "visa-" in low


def skipg4_landed_play_credit(blob: str) -> bool:
    """See more fallback landed Buy Google Play Credit, not a card list.

    Frozen 2026-09-22 hop-2 play-acct see-more.png: Choose amount,
    $10.00 credit selected, Continue. Do not tap Continue. BACK.
    """
    low = str(blob or "").lower()
    if "starting oct" in low and "supergrok" in low:
        return False
    return (
        "choose amount" in low
        or "$10.00 credit" in low
        or "buy google play credit" in low
    )


def skipg4_landed_redeem(blob: str) -> bool:
    """skipg4 fire landed Play Redeem code, not Starting Oct wall.

    Frozen 2026-09-21 hop-4 acct h4-redeem.png dump:
    Back | Redeem code | play-acct@… | Enter code | Scan gift card | Redeem.
    BACK + am start Grok then skipg4_once (h4-after-redeem.png Ask anything).
    """
    low = str(blob or "").lower()
    if "starting oct" in low or ("subscribe" in low and "super" in low):
        return False
    if "you'll get these benefits" in low or "youll get these benefits" in low:
        return False
    if "enter code" not in low:
        return False
    return "redeem code" in low or "scan gift card" in low


def skipg4_password_no_internet(blob: str) -> bool:
    """Play password page Error No internet. Tap Try again then retype.

    Frozen 2026-09-20 hop-2 acct / hop-3 acct dump:
    Enter your password | Error | No internet connection | Verify.
    play_egress US still true. Try again + retype + Verify then Payment successful.
    """
    low = str(blob or "").lower()
    return "no internet connection" in low and (
        "enter your password" in low or "verify" in low
    )


def skipg4_reverify_acquire(typed: bool, verdict: str, focus: str) -> bool:
    """Verify tap left the Play acquire sheet up. Tap Verify once more.

    2026-10-07 hop5 src38: typed_once verify_y 1760 while ADB Keyboard stayed
    ON. inspect kept the old GPA, ar false, obf set, for the whole wait,
    then SKIP_EXIT 4. Focus stayed on LockToPortrait acquire.
    """
    if not typed or verdict != "pending":
        return False
    low = (focus or "").lower()
    return "acquire" in low or "locktoportrait" in low


def skipg4_verify_tap_y(blob: str) -> int:
    """FLAG_SECURE password + ADB Keyboard ON: 1836 hits IME, Verify is y~1760.

    Frozen 2026-09-20 hop-2 acct shot w2h2-after-skipg4.png black +
    ADB Keyboard {ON}; su_tap 540,1836 missed; 1760 after Try again paid.
    Verify bounds y~1738-1833 (2026-09-18 acct). Default 1836 when IME off.
    Frozen 2026-09-21 hop-2 acct h2-skip-7.png + h2-pw.xml: dump Verify
    [63,1738][1017,1833] cy=1785, screenshot ADB Keyboard {ON}, skipg4_once
    typed_once verify_y 1836 missed. remember me + verify still 1760.
    """
    low = str(blob or "").lower()
    if skipg4_flag_secure_ime_only(blob) or "adb keyboard" in low:
        return 1760
    if "remember me" in low and "verify" in low:
        return 1760
    return 1836


def skipg4_flag_secure_ime_only(blob: str) -> bool:
    """After Subscribe, FLAG_SECURE password: dump timeout, OCR only ADB Keyboard.

    2026-09-18 grok-hop-2 acct: wall picked <last4>, dump timeout, ocr
    'ADB Keyboard {ON}', skipg4_once logged no password page. Manual type_text
    + su_tap 540,1836 Verify then inspect new GPA AR true empty obf.
    Do not treat SuperGrok Heavy Subscribe wall as this.
    """
    low = (blob or "").lower()
    if "super grok heavy" in low.replace(" ", "") or "subscribe" in low:
        return False
    return "adb keyboard" in low and "verify" not in low


def destg4_grok_died_home(blob: str) -> bool:
    """destg4 fire then dump is MuMu home or Grok splash, not IAB.

    2026-09-18 grok-hop-2 acct destg4: d2rc 0 then dump 0 / OCR KLINGAI US_EGRESS proxy
    Dreamina Kitsune Mask Grok home. Grok lost focus. am start GrokActivity then
    destg4_once opened deferred wall. Do not treat as dest_get_not_active.
    hop-5 2026-10-02 destg4p1m_gate: dump bytes=0 / OCR A VAi, after dump is
    Grok splash. Treat splash as died-home so fire_home_retry wait_grok_ready.
    """
    low = (blob or "").lower()
    if "super grok heavy" in low.replace(" ", "") or "subscribe" in low:
        return False
    # launcher wallpaper labels (generic proxy-client app name kept verbatim:
    # this check detects the MuMu launcher, not any specific egress vendor)
    if ("klingai" in low and "fclash" in low) or (
        "kitsune mask" in low and "dreamina" in low
    ):
        return True
    # 2026-10-07 hop1: splash OCR is "11:17 A VA". The clock made
    # stripped "1117ava", so the splash was classified not_today_zero
    # and skip exited. Drop a leading status clock, and accept "ava".
    body = low
    i = 0
    while i < len(body) and body[i].isdigit():
        i += 1
    if i and i < len(body) and body[i] == ":":
        j = i + 1
        while j < len(body) and body[j].isdigit():
            j += 1
        if j > i + 1:
            body = body[j:].lstrip()
    stripped = "".join(ch for ch in body if ch.isalnum())
    if stripped in ("", "avai", "ava", "vai", "a"):
        return True
    # 2026-10-09 hop-8 localhost:<serial> acct: logo splash OCR was
    # "7:35G A VAi". Clock strip leaves "g a vai" -> gavai, and skip
    # exited not_today_zero. A short status bar that still contains ava
    # is the same splash. A Subscribe wall is already excluded above.
    if len(stripped) <= 6 and "ava" in stripped:
        return True
    # 2026-10-10 acct localhost:<serial> skip3.png is the logo splash
    # (47999 bytes). OCR was "221A ¢ aU 4u" with no colon, so the clock
    # strip left "221aau4u" and skip exited not_today_zero. Letters only
    # are "aauu" (the status A, aU, and 4u). A Subscribe wall is already
    # excluded above and has far more than four letters.
    letters = "".join(ch for ch in low if ch.isalpha())
    return bool(letters) and len(letters) <= 4


def grok_screen_ready(focus: str, png_bytes: int) -> bool:
    """GrokActivity is showing a content frame, not the logo splash.

    hop-1008p1 acct 2026-10-08 localhost:<serial>. sleep 5 then fire:
    dest-live.png 45724, dest-live2.png 43959, dest-live3.png 44175 were
    the Grok splash at 12:28-12:30, mCurrentFocus null, three destg4 fires
    sent None / fire_timeout. Same desk content frames were dest-now.png
    163673 (Ask) and dest-live4.png 140498 (Manage subscription). 80000
    sits in the gap. A Play page in front is not ready.
    """
    lines = [ln.strip() for ln in (focus or "").splitlines() if "mCurrentFocus" in ln]
    top = lines[-1] if lines else (focus or "")
    if "GrokActivity" not in top:
        return False
    try:
        n = int(png_bytes)
    except (TypeError, ValueError):
        return False
    return n >= 80000


def empty_pm_add_card_xy(ocr: str) -> tuple[int, int] | None:
    """Add-card row when the dump is empty but the list is on screen.

    Grok-2 2026-10-07 12:02, 1080x1920, shots/g2-bind-3.png. Dump timed out,
    bind returned pm_no_add. Tesseract put "credit" at left 278 top 966.
    """
    low = (ocr or "").lower()
    if "payment methods" in low and "make your next purchase" in low:
        return (332, 983)
    return None


def bind_empty_dump_action(ocr: str) -> str:
    """Empty uiautomator dump during bind is not an empty payment list.

    2026-10-07 hop5 localhost:<serial>: gate.py bind returned pm_timeout
    empty_dump. The screenshot during that call was Introducing Google
    Play Points. The next screenshot was Payment methods with
    Add credit or debit card. A 4s dump timeout must not abort that list.
    """
    low = (ocr or "").lower()
    if "introducing google play points" in low:
        return "tap_not_now"
    if "payment methods" in low and (
        "add credit" in low
        or "debit card" in low
        or "make your next purchase" in low
        or "adding a payment method" in low
    ):
        # Grok-2 2026-10-07 15:00Z: dump timed out, OCR stopped at
        # "Make your next purchase fast and easy by adding a". The
        # screenshot still showed Add credit or debit card.
        return "already_open"
    return ""


def bind_ocr_play_points_not_now(blob: str) -> tuple[int, int] | None:
    """Bind timeout OCR of Introducing Google Play Points. Tap Not now, never Learn more.

    2026-09-22 hop-2 acct bind_timeout.png: dialog covered Play home, apply returned
    bind_apply_timeout, Payment methods still only Visa-<last4>. Same dialog as hop-4
    acct, Not now (540, 1509) below Learn more. OCR has the title when the
    dump has no node.
    """
    if "introducing google play points" not in (blob or "").lower():
        return None
    return (540, 1509)


def play_points_not_now_xy(blob: str) -> tuple[int, int]:
    """Stacked Introducing overlay Not now is 540,1509. 293,1836 is Pause payments.

    2026-09-18 grok-hop-1/2 destg4 shots: Introducing Google Play Points + Learn more
    + Not now over Manage subscription. su_tap(293,1836) opened Set pause length.
    """
    low = (blob or "").lower()
    if "introducing google play points" in low:
        return (540, 1509)
    return (293, 1836)


def destg4_already_active_action(
    dest_login_ultra: bool | None,
    dest_get_ultra: bool | None,
    dest_cap: bool | None,
) -> str:
    """What destg4_once does when dest GET is already ACTIVE.

    Frozen 2026-09-20 hop-1 acct: dest_login has_ultra_active true -> refuse destg4p1m.
    Frozen 2026-09-23 hop-1 acct: dest_login ultra false, destg4 already
    transferred, dest GET True cap False -> cancel_cap then ingest.
    dest GET True cap True -> ingest.
    """
    if dest_login_ultra is True:
        return "refuse"
    if dest_get_ultra is True and dest_cap is True:
        return "ingest"
    if dest_get_ultra is True and dest_cap is not True:
        return "cancel_cap"
    return "destg4p1m"


def destg4_before_skipg4(grpc_status: int | None, dest_already: bool) -> str:
    """Dead dest JWT must refresh. It must not fall through to skipg4.

    Frozen 2026-09-27 acct: grpc 16 made has_ultra_active false while Play
    still held the washed token with obf set, and destg4_once printed
    need_skipg4. After dest_login the same token was ACTIVE and capped.
    """
    if not dest_already and grpc_status == 16:
        return "dest_jwt_grpc_16"
    return "continue"


def skip_retry_active(rows: list[dict], ultra_by_email: dict[str, bool]) -> list[str]:
    """Skipped leftover emails whose leftover GET still has ultra.

    Frozen 2026-10-08 hop-small-3 last60 gap 1336s: ingest 21:26:46 then
    21:49:02. dest_jwt_grpc_16 after dest_login of another dest, plus
    <last4> Verification needed bind <last4>. GET-inactive stays skipped.
    """
    out: list[str] = []
    for row in rows or []:
        if str(row.get("status") or "") != "skipped":
            continue
        email = str(row.get("email") or "").strip().lower()
        if email and ultra_by_email.get(email) is True:
            out.append(email)
    return out


def dest_login_cookie_banner(text: str) -> bool:
    """True = x.ai sign-in cookie overlay is up. Click it before turnstile.

    Frozen 2026-09-23 grok-reg look dest-login-etnn: #email form ready,
    button 接受所有 Cookie @e16, dest_login_once no_turnstile ts_len 0.
    OneTrust remove() does not dismiss this Vue banner.
    """
    t = str(text or "")
    return "接受所有 Cookie" in t or (
        "accept all" in t.lower() and "cookie" in t.lower()
    )


def dest_login_no_turnstile(box: dict[str, Any] | None) -> bool:
    """True = this AB label did not POST /api/auth/sign-in. Switch cooled grok-n1/n2/grok-reg.

    Frozen 2026-09-21 extra-4 dest-login-n5 once.log: err no_turnstile, ts_len<=20.
    dest_login_once must return no_turnstile and must not dump leftover grok.com
    cookies as dest sso_len 152 (dest-login-n5/n8 login.json email empty).
    Cooled grok-n1/n2/grok-reg dest_login_once_cdp_xai_email is ok.
    """
    if not isinstance(box, dict):
        return False
    if str(box.get("err") or "") == "no_turnstile":
        return True
    ts = box.get("ts_len")
    try:
        ts_n = int(ts) if ts is not None else None
    except (TypeError, ValueError):
        ts_n = None
    if ts_n is not None and ts_n <= 20 and not box.get("ok"):
        return True
    return False


def keep_prior_dest_login(path: Any, new: dict[str, Any] | None, *, dest: str) -> bool:
    """True when a failing login must not replace a get-user 200 file.

    2026-10-07 hop1 once.log: sign-in ok at 12:27:11, get-user 200 for the
    dest. Nine seconds later a second dest_login on the same HOP_WORK
    logged no_password_field and replaced login.json with ok false.
    """
    try:
        old = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return False
    if not isinstance(old, dict) or not isinstance(new, dict):
        return False
    if new.get("ok") is True:
        return False
    email = str(old.get("email") or "").strip().lower()
    want = (dest or "").strip().lower()
    try:
        status = int(old.get("get_user") or 0)
    except (TypeError, ValueError):
        status = 0
    return bool(old.get("ok") is True and status == 200 and email == want and "@" in email)


def dest_login_signin_stop(box: dict[str, Any] | None) -> str | None:
    """Sign-in errors that must not fall through onto another account's cookie.

    2026-09-26 acct: sign-in returned invalid-credentials, then the
    grok.com cookie still belonged to acct. 2026-09-26
    acct: sign-in returned unauthenticated_sso and the same
    shared cookie, get-user 401. Stop on these errors.
    """
    err = str((box or {}).get("err") or "").strip()
    if err in {
        "invalid-credentials",
        "unauthenticated_sso",
        "no_xai_password",
        "no_password_field",
        "password_signin_unavailable",
        "no_castle",
        "not_signin",
        "flag_chunk_unpatched",
    }:
        return err
    return None


def destg4_empty_inspect_action(rows, src_ultra: bool, src_cap: bool) -> str:
    """Device inspect missed a canceled wash that the source GET still holds.

    2026-10-10 hop-8 acct: the first destg4 canceled the wash, then died
    at gid. The retry inspect was [] while the source GET was ultra with
    cancelAtPeriodEnd and the Play page was Canceled Mastercard-<last4>.
    That is not no_leftover. Fire p1m.
    """
    if any(isinstance(p, dict) and p.get("sku") == "grok.ultra" for p in rows or []):
        return "have_row"
    if src_ultra and src_cap:
        return "fire"
    return "no_leftover"


def dest_login_accept(
    *,
    dest: str,
    session_email: str,
    href: str = "",
    sso: str = "",
    api_status: int = 0,
) -> str | None:
    """None = dest grok-password login ok. SSO cookie / api 200 is not enough."""
    dest_e = str(dest or "").strip().lower()
    sess = str(session_email or "").strip().lower()
    href_l = str(href or "").strip().lower()
    if not dest_e:
        return "dest_grok_login"
    if "sign-in" in href_l:
        return "still_signin"
    # 2026-09-19 acct/acct: x.ai 200 email==dest then grok.com ERR_CONNECTION_CLOSED
    # left href chrome-error://chromewebdata/. That is not dest_login_accept.
    if "chrome-error" in href_l or "chromewebdata" in href_l:
        return "dest_grok_login"
    if sess == dest_e:
        return None
    if sess:
        return "dest_email_mismatch"
    return "dest_grok_login"


def dest_login_record_ok(rec: dict[str, Any] | None, dest: str) -> bool:
    if not isinstance(rec, dict) or not rec.get("ok"):
        return False
    return dest_login_accept(
        dest=dest,
        session_email=str(rec.get("email") or ""),
        href=str(rec.get("href") or ""),
        sso="eyJ" if int(rec.get("sso_len") or 0) >= 20 else "",
        api_status=int((rec.get("api") or {}).get("status") or 0) if isinstance(rec.get("api"), dict) else 0,
    ) is None


def dest_login_may_persist(*, shared: str) -> bool:
    """False = another account already holds this JWT. Do not persist dest.

    2026-09-22 dest_login_once persisted then checked sso_other_holder.
    acct got acct's cookie. Check the incoming JWT first.
    """
    return not str(shared or "").strip()


def dest_login_keep_existing_jwt(
    *,
    accept_err: str | None,
    incoming_shared: str,
    dest_sqlite_other: str,
) -> bool:
    """True = dest_login_accept holds, incoming cookie shared, dest sqlite dest-only.

    Frozen 2026-09-23 hop-2 acct: dest_login email==dest href tos-gate,
    incoming cookie dest_sso_shared play-acct, dest sqlite JWT dest-only.
    destg4 used dest sqlite JWT, dest GET True True ingest.
    Do not persist incoming. destg4 allowed.
    """
    return (
        accept_err is None
        and bool(str(incoming_shared or "").strip())
        and not str(dest_sqlite_other or "").strip()
    )


def sync_heavy_list_ready(blob: str) -> bool:
    """Subscriptions list that already shows Canceled Heavy.

    2026-10-05 hop-1003 manage pages: "Earn Play Points with subscription
    payments" sits above Canceled SuperGrok Heavy. That is the list, not
    the Introducing Google Play Points / Not now sheet. Treating the banner
    as the opt-in makes sync_play_library tap Not now and wait out the timeout.
    """
    b = (blob or "").lower()
    if "supergrok" not in b:
        return False
    if "canceled" not in b and "will end" not in b:
        return False
    if "not now" in b and "introducing" in b:
        return False
    return True


def sync_playfest_sheet(blob: str) -> bool:
    """Play Fest opt-in after pm-clear. Tap No thanks, never Get notified.

    grok-hop-1 2026-10-05 sk-live.png: Don't miss Play Fest October 13-19,
    No thanks / Get notified. The sync loop did not know this sheet, so
    library_sync returned empty and skip logged no leftover while the
    subscriptions page still showed Canceled SuperGrok Heavy.
    """
    b = (blob or "").lower().replace("\u2019", "'")
    return "play fest" in b and "no thanks" in b


def playfest_prize_sheet(blob: str) -> bool:
    """Play Fest prize interstitial. Tap Not now, never Explore.

    hop-4 destg4 2026-10-06 verify.png: Manage subscription stayed dimmed
    under Win grand prizes during Play Fest, Oct 13-19. Buttons were
    Not now and Explore. OCR had play fest / grand prizes and no
    No thanks, so sync_playfest_sheet missed it and verify sat until
    timeout_continue.
    """
    b = (blob or "").lower().replace("\u2019", "'")
    if "play fest" not in b:
        return False
    # 2026-10-10 acct auth3.png and acct skip-overlay2.png: "Get ready
    # for Play Fest: Oct 13-19" with Not now / Explore and no grand prizes.
    # The grand-prizes check left dismiss looping on that sheet.
    return "grand prizes" in b or "get ready for play fest" in b


def sync_welcome_not_now(blob: str) -> bool:
    """Play welcome sheet. Tap Not now, never the right pill.

    2026-10-10 localhost:<serial> play-onboard.png and skip-now.png: the sheet
    is Welcome to Google Play with Not now on the left and Get started on
    the right. OCR returned only "Enjoy millions of the latest Android apps"
    and missed both labels, so the old welcome+not-now gate never tapped.
    The left label sits near (270, 1780) on the 1080x1920 shot. One OCR
    then took 48s and ate the 45s library_sync budget, and skip logged
    no leftover.
    """
    b = (blob or "").lower().replace("\u2019", "'")
    if "enjoy millions of the latest android apps" in b:
        return True
    return "welcome to google play" in b and "not now" in b


def sync_needs_relaunch(blob: str) -> bool:
    """pm clear left the MuMu launcher. Open Play again.

    2026-10-08 hop-6 s15-skip1.png: after pm clear, OCR stayed on
    KLINGAI / US_EGRESS proxy / Dreamina / Kitsune Mask / Grok until the 45s
    budget ended. Subscriptions opened only after that timeout.
    """
    b = (blob or "").lower()
    if not b.strip():
        return False
    if any(
        x in b
        for x in (
            "for you",
            "top charts",
            "subscriptions",
            "welcome to google play",
            "get started",
            "play points",
            "server busy",
            "server error",
            "try again",
        )
    ):
        return False
    return "klingai" in b or "kitsune mask" in b


def sync_onboard_done(blob: str) -> bool:
    """Play home or a store ad after pm-clear. Open subscriptions; do not wait.

    2026-09-22 hop-3 play-acct play-onboard.png OCR stayed on StoryGraph until
    the 90s timeout. The ad is not Get started / Play Points / For you.
    """
    b = (blob or "").lower()
    return any(
        x in b
        for x in (
            "for you",
            "top charts",
            "storygraph",
            "turn over a new page",
        )
    )


def library_ultra_select_sql(*, column: str, current_google: str = "") -> str:
    """sqlite select for the live Play Google's grok.ultra row.

    2026-09-25 hop-4 acct and hop-2 acct: library.db kept the previous
    Google's grok.ultra row first. `limit 1` without account returned that
    row. Filter by the current dumpsys account.
    """
    import re

    col = (column or "").strip()
    if col not in {"inapp_purchase_data", "account"}:
        raise ValueError(col)
    email = (current_google or "").strip().lower()
    if email and not re.fullmatch(r"[a-z0-9._+\-]+@[a-z0-9.\-]+", email):
        email = ""
    where = "doc_id like '%grok.ultra%'"
    if email:
        where += f" and lower(account)='{email}'"
    return f"select {col} from ownership where {where} limit 1"


def bind_decline_is_previous_card(blob: str, want_last4: str) -> bool:
    """True when an OR decline is still showing the previous card number.

    2026-09-25 hop-4 acct: bind <last4> and <last4> returned OR_CCREU in seconds
    because the form still showed the <last4> decline. After back, <last4> bound.
    """
    import re

    want = (want_last4 or "").strip()
    if len(want) != 4 or not want.isdigit():
        return False
    text = blob or ""
    low = text.lower()
    if "or_ccreu" not in low and "or-ccreu" not in low and "or_mivem" not in low and "or-mivem" not in low:
        return False
    pans = re.findall(r"(?:\d{4}\s+){3}(\d{4})", text)
    return bool(pans) and all(p != want for p in pans)


def library_ultra_from_blob(blob: str) -> tuple[dict[str, Any] | None, str]:
    """Parse one ownership inapp_purchase_data. Token is the second value, not in the row."""
    raw = (blob or "").strip()
    if not raw.startswith("{"):
        return None, ""
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None, ""
    if not isinstance(obj, dict) or str(obj.get("productId") or "") != "grok.ultra":
        return None, ""
    token = str(obj.get("purchaseToken") or "")
    obf = str(obj.get("obfuscatedAccountId") or "")
    actions = obj.get("subscriptionClientActions") or []
    if not isinstance(actions, list):
        actions = []
    row = {
        "sku": "grok.ultra",
        "order": str(obj.get("orderId") or "")[:24],
        "ar": obj.get("autoRenewing"),
        "obf": obf[:16],
        "obf_full": obf,
        "tok": token[:8],
        "actions": [str(a) for a in actions],
        "purchaseState": obj.get("purchaseState"),
        "from": "library",
    }
    return row, token


def library_ultra_fireable(row: dict[str, Any] | None, token: str = "") -> bool:
    """Canceled-but-owned library grok.ultra is the wash input when e2 is empty.

    2026-10-05 hop-5 acct tok8 <tok8> and hop-6 acct tok8 <tok8>:
    purchaseState 0, autoRenewing false, obfuscatedAccountId 64 hex,
    subscriptionClientActions RESTORE. inspect purchases stayed [].
    """
    if not isinstance(row, dict) or row.get("from") != "library":
        return False
    if _sku(row) != "grok.ultra":
        return False
    if row.get("purchaseState") not in (0, "0"):
        return False
    if len(_obf(row)) != 64:
        return False
    if row.get("ar") is True:
        return False
    return len(token or "") >= 20


def library_ultra_is_current(*, owner: str, current_google: str, blob: str) -> bool:
    """True only when grok.ultra purchaseToken belongs to the live Play Google.

    A leftover hop after switch can keep the previous Google's ownership row.
    inspect then returns purchases=[] even if Play UI shows SuperGrok Heavy.
    """
    raw = blob or ""
    if "grok.ultra" not in raw or "purchaseToken" not in raw:
        return False
    own = (owner or "").strip().lower()
    cur = (current_google or "").strip().lower()
    return bool(own and cur and own == cur)


def skipg4_wait_play_subs(syn: dict[str, Any] | None) -> bool:
    """inspect [] but library.db already has current Google grok.ultra.

    Frozen 2026-09-19 hop-3 play-acct: library_sync ok owner==dumpsys,
    row_head grok.ultra purchaseToken <token>, inspect still [].
    Do not treat as no leftover. Open Play subscriptions then inspect.
    """
    if not isinstance(syn, dict) or not syn.get("ok"):
        return False
    blob = str(syn.get("row_head") or syn.get("blob") or "")
    if "grok.ultra" in blob and "purchaseToken" in blob:
        return True
    return bool(syn.get("already"))


def dest_xai_ready(row: dict[str, Any] | None) -> str | None:
    """None = dest grok 密码已拆开. 否则 error code."""
    if not isinstance(row, dict):
        return "dest_not_found"
    mail = str(row.get("password") or "")
    xai = str(row.get("xai_password") or "").strip()
    if not xai:
        return "dest_xai_missing"
    if xai == mail:
        return "dest_xai_same_as_mail"
    return None


def dest_xai_login_ok(notes: str = "") -> bool:
    """True if dest_login_once stamped xai_login_ok after password sign-in."""
    return "xai_login_ok" in str(notes or "")


def dest_xai_login_verified(notes: str = "") -> str | None:
    """None = dest grok 密码已 dest_login 实登. GET SSO 不算."""
    if dest_xai_login_ok(notes):
        return None
    return "dest_xai_login_unverified"


def stamp_xai_login_ok_notes(notes: str = "", when: str = "") -> str:
    """Replace or append xai_login_ok <iso> in dest notes."""
    import re

    ts = str(when or "").strip()
    if not ts:
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = re.sub(r"(?:^|\n)xai_login_ok\s+\S+", "", str(notes or "")).strip()
    line = f"xai_login_ok {ts}"
    return f"{body}\n{line}".strip() if body else line


def hop_source_forbidden(sold_rec: dict[str, Any] | None) -> str | None:
    """sold.json hop=false or notes cannot_hop: 长效号 = 质保一个月 leftover, 禁止 skipg4."""
    rec = sold_rec if isinstance(sold_rec, dict) else {}
    if rec.get("hop") is False:
        kind = str(rec.get("kind") or "").strip()
        return kind or "no_hop"
    notes = str(rec.get("notes") or "")
    if "cannot_hop" in notes:
        return "cannot_hop"
    return None


def hop_false_allowed(email: str) -> bool:
    """Operator-named override. Unset env still forbids hop=false."""
    raw = os.environ.get("HOP_ALLOW_HOP_FALSE") or ""
    allowed = {part.strip().lower() for part in raw.split(",") if part.strip()}
    want = str(email or "").strip().lower()
    return bool(want) and want in allowed


def drop_blocked_while_ultra(*, dest_ultra: bool | None, dest_cap: bool | None) -> bool:
    """Uncapped ultra is still the subscription. Do not drop-inventory it.

    2026-10-10 n176: dest_get_not_active (cap false) was written as
    inventory=dropped while GET was still ultra. cancel_cap then ingest.
    """
    return dest_ultra is True and dest_cap is not True


def dest_ingest_ready(
    *,
    dest: str,
    source: str,
    dest_jwt: str,
    source_jwt: str = "",
    others: list[tuple[str, str]] | None = None,
    get_box: dict[str, Any] | None = None,
    dest_row: dict[str, Any] | None = None,
    get_user_email: str = "",
    get_user_status: int = 0,
    source_sold: dict[str, Any] | None = None,
) -> str | None:
    """None = dest-only hop-dest 可入库. leftover JWT GET ACTIVE 禁止写成 dest."""
    dest_e = str(dest or "").strip().lower()
    src_e = str(source or "").strip().lower()
    if not dest_e:
        return "dest_not_found"
    if not src_e:
        return "dest_not_found"
    forbid = hop_source_forbidden(source_sold)
    if forbid and not hop_false_allowed(src_e):
        return "hop_source_forbidden"
    if dest_e == src_e:
        return "dest_is_source"
    xai_err = dest_xai_ready(dest_row)
    if xai_err:
        return xai_err
    token = str(dest_jwt or "").strip()
    src_tok = str(source_jwt or "").strip()
    conflict = sso_jwt_conflict(dest=dest_e, jwt=token, others=others or [])
    if conflict:
        return conflict
    if src_tok.startswith("eyJ") and token == src_tok:
        return "dest_sso_is_source"
    box = get_box if isinstance(get_box, dict) else {}
    if box.get("grpc_status") == 16:
        return "dest_jwt_grpc_16"
    if not (box.get("has_ultra_active") and box.get("cancelAtPeriodEnd")):
        return "dest_get_not_active"
    email_err = dest_sso_email_ok(
        dest=dest_e,
        get_user_email=get_user_email,
        get_user_status=get_user_status,
    )
    if email_err:
        return email_err
    login_err = dest_xai_login_verified(str((dest_row or {}).get("notes") or ""))
    if login_err:
        return login_err
    return None


def hop_ledger_sold_dest_policy(*, leftover_has_ultra_active: object, dest_sold: bool) -> str:
    """Sold dests stay sold. Do not unmark_sold.

    leftover GET already INACTIVE -> cannot_transfer dest empty.
    leftover still ACTIVE -> hop onto a new unsold dest (2026-09-22 acct).
    """
    if not dest_sold:
        return "keep_dest"
    if leftover_has_ultra_active is True:
        return "replace_sold_dest"
    return "cannot_transfer"


def hop_ledger_close_action(
    *,
    leftover_grpc_status: object,
    leftover_has_ultra_active: object,
    dest_sold: bool,
    dest_present: bool = False,
) -> str:
    """Close-out action from leftover GET + dest overlay.

    grpc 16 is unusable SSO, not ultra-false. dest_login then GET
    (`pending` `sso_refresh_then_get` dest empty). Do not cannot_transfer.
    leftover INACTIVE and dest empty (acct) is cannot_transfer.
    Frozen hop-923: three accts' first GET grpc 16 was a
    mistyped JWT; sqlite/operator JWT GET ok True ultra False grpc None.
    """
    if leftover_grpc_status == 16:
        return "pending_sso_refresh_then_get"
    if leftover_has_ultra_active is True:
        return "replace_sold_dest" if dest_sold else "keep_dest"
    if dest_sold or not dest_present:
        return "cannot_transfer"
    return "keep_dest"


def hop_ledger_ok(rows: list[dict[str, Any]] | None) -> bool | str:
    """True = each leftover is unique dest hop or explicit cannot-transfer.

    leftover GET already INACTIVE must be cannot_transfer with dest empty.
    Transferred dests must be unique. Do not reuse another leftover's dest.
    ingest row dest_sold / dest_inventory=dropped / dest_has_ultra_active
    False is not ok (hop-923 acct dropped; sold overlay).
    """
    if not isinstance(rows, list) or not rows:
        return "ledger_empty"
    seen_src: set[str] = set()
    seen_dest: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            return "ledger_bad_row"
        src = str(row.get("src") or row.get("email") or "").strip().lower()
        if not src or "@" not in src:
            return "ledger_src_missing"
        if src in seen_src:
            return "ledger_src_dup"
        seen_src.add(src)
        dest = str(row.get("dest") or "").strip().lower()
        cannot = bool(row.get("cannot_transfer"))
        if cannot:
            if dest:
                return "cannot_transfer_has_dest"
            if row.get("leftover_has_ultra_active") is True:
                return "cannot_transfer_still_active"
            if row.get("leftover_grpc_status") == 16:
                return "cannot_transfer_grpc16"
            continue
        pending = str(row.get("pending") or "")
        if pending == "sso_refresh_then_get":
            # grpc 16 is unusable SSO, not ultra-false. dest_login 401 + skip
            # reset stays pending. Do not mark cannot_transfer.
            if dest:
                return "pending_sso_has_dest"
            if row.get("leftover_grpc_status") != 16:
                return "pending_sso_not_grpc16"
            if row.get("leftover_has_ultra_active") is True:
                return "pending_sso_still_active"
            continue
        if not dest or "@" not in dest:
            return "ledger_dest_missing"
        if dest in seen_dest:
            return "ledger_dest_dup"
        seen_dest.add(dest)
        # ingest row must still be unsold hop-dest with dest GET ACTIVE.
        # leftover inactive + dest sold/dropped -> cannot_transfer dest empty
        # (hop_ledger_sold_dest_policy). Do not unmark sold.
        if row.get("dest_sold") is True:
            return "ledger_dest_sold"
        dest_inv = str(row.get("dest_inventory") or "").strip().lower()
        if dest_inv == "dropped" or row.get("dest_dropped") is True:
            return "ledger_dest_dropped"
        if row.get("dest_has_ultra_active") is False:
            return "ledger_dest_not_active"
        miss = hop_dest_ingested_ok(row)
        if miss:
            return miss
    return True


def hop_dest_ingested_ok(row: dict[str, Any] | None) -> str | None:
    """None = dest is unsold hop-dest. counted without ingest is fail.

    2026-10-05 hop-1003: 45 counted GET ultra+cap, 37 dest_get_user_not_live
    never append_delivered. 关表 counted 不是库存.
    """
    if not isinstance(row, dict):
        return "ledger_bad_row"
    dest = str(row.get("dest") or "").strip().lower()
    if not dest or "@" not in dest:
        return None
    if row.get("cannot_transfer") or str(row.get("pending") or ""):
        return None
    if row.get("dest_sold") is True:
        return "ledger_dest_sold"
    has_fields = any(k in row for k in ("ingested", "dest_inventory", "inventory")) or str(
        row.get("status") or ""
    ) == "counted"
    if not has_fields:
        return None
    inv = str(row.get("dest_inventory") or row.get("inventory") or "").strip().lower()
    ingested = row.get("ingested")
    if ingested is False:
        return "ledger_dest_not_ingested"
    if inv and inv != "hop-dest":
        return "ledger_dest_not_ingested"
    if ingested is not True and inv != "hop-dest":
        return "ledger_dest_not_ingested"
    if row.get("dest_has_ultra_active") is False:
        return "ledger_dest_not_active"
    return None


def parse_source_list(raw: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        email = line.split()[0].strip().lower()
        if "@" not in email or email in seen:
            continue
        seen.add(email)
        out.append(email)
    return out


def _gid64(gid: str) -> str:
    g = str(gid or "").strip().lower()
    if len(g) == 64 and all(c in "0123456789abcdef" for c in g):
        return g
    return ""


def play_bind_fragments(*, dest: str, source: str, play: str, tok8: str, gid: str = "") -> tuple[str, str]:
    """Notes written after destg4. No password, SSO, or PAN.

    dest hotmail note names the Play. Play gmail note names dest + leftover + tok8.
    gid is GetGoogleObfuscatedId. tok8 rotates; gid still finds this Play.
    """
    tok = str(tok8 or "").strip().lower()[:8]
    play_e = str(play or "").strip().lower()
    dest_e = str(dest or "").strip().lower()
    src_e = str(source or "").strip().lower()
    if len(tok) != 8 or "@" not in play_e or "@" not in dest_e or "@" not in src_e:
        return "", ""
    dest_note = f"play {play_e} tok8 {tok}"
    play_note = f"hop dest {dest_e} leftover {src_e} tok8 {tok}"
    g = _gid64(gid)
    if g:
        dest_note += f" gid {g}"
        play_note += f" gid {g}"
    return dest_note, play_note


def leftover_play_bind_fragments(*, leftover: str, play: str, tok8: str, gid: str = "") -> tuple[str, str]:
    """Notes written after leftover GET. No password, SSO, or PAN."""
    tok = str(tok8 or "").strip().lower()[:8]
    play_e = str(play or "").strip().lower()
    left_e = str(leftover or "").strip().lower()
    if len(tok) != 8 or "@" not in play_e or "@" not in left_e:
        return "", ""
    left_note = f"play {play_e} tok8 {tok}"
    play_note = f"leftover {left_e} tok8 {tok}"
    g = _gid64(gid)
    if g:
        left_note += f" gid {g}"
        play_note += f" gid {g}"
    return left_note, play_note


def append_bind_note(existing: str, extra: str) -> str:
    cur = str(existing or "")
    add = str(extra or "").strip()
    if not add or add in cur:
        return cur
    return (cur + "; " + add).strip("; ").strip()


def purchase_tok8(got: dict[str, Any] | None) -> str:
    """First 8 chars of the active grok.ultra purchaseToken. Empty if absent."""
    ua = (got or {}).get("ultra_active") or {}
    if not isinstance(ua, dict):
        return ""
    google = ua.get("google") if isinstance(ua.get("google"), dict) else {}
    token = str(google.get("purchaseToken") or ua.get("purchaseToken") or "")
    return token[:8].lower() if len(token) >= 8 else ""


def tok8_from_notes(notes: str) -> str:
    import re

    match = re.search(r"tok8\s+([a-z0-9]{8})", str(notes or ""), re.I)
    return match.group(1).lower() if match else ""


def preserve_purchase_notes(existing: str, replacement: str) -> str:
    """Keep play / leftover / hop-dest tok8 fragments when a status write replaces notes.

    2026-09-23 produce passed only ``交付 leftover`` into set_paid and set_status.
    That dropped the Play address, so a later hop could not find the purchase.
    """
    out = str(replacement or "")
    for frag in str(existing or "").split(";"):
        piece = frag.strip()
        low = piece.lower()
        if "tok8" not in low:
            continue
        if not any(key in low for key in ("play ", "leftover ", "hop dest ")):
            continue
        out = append_bind_note(out, piece)
    return out


def play_email_for_tok8(notes: str, tok8: str) -> str:
    """Play address from a dest note `play EMAIL tok8 XXXXXXXX`."""
    import re

    tok = str(tok8 or "").strip().lower()[:8]
    text = str(notes or "")
    if len(tok) != 8 or tok not in text.lower():
        return ""
    match = re.search(
        r"play\s+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\s+tok8\s+" + re.escape(tok),
        text,
        re.I,
    )
    return match.group(1).lower() if match else ""


def play_pool_gid_hits(rows, gid: str) -> list[str]:
    """Play emails whose notes contain this GetGoogleObfuscatedId.

    tok8 changes after a new purchase. The gid on the bind note does not.
    A short or non-hex gid is a miss. Do not switch a random Google.
    """
    g = _gid64(gid)
    if not g:
        return []
    out: list[str] = []
    for email, notes in rows or []:
        if g not in str(notes or "").lower():
            continue
        em = str(email or "").strip().lower()
        if em and em not in out:
            out.append(em)
    return out


def play_pool_dest_hits(rows, dest: str) -> list[str]:
    """Play emails whose notes say `hop dest EMAIL`, even when tok8 rotated."""
    dest_e = str(dest or "").strip().lower()
    if "@" not in dest_e:
        return []
    needle = f"hop dest {dest_e}"
    out: list[str] = []
    for email, notes in rows or []:
        if needle not in str(notes or "").lower():
            continue
        em = str(email or "").strip().lower()
        if em and em not in out:
            out.append(em)
    return out


def play_emails_in_note(notes: str) -> list[str]:
    """Play addresses already written on the hotmail note.

    A fragment marked account_dead is not a buyer.
    """
    import re

    out: list[str] = []
    for frag in str(notes or "").split(";"):
        if "account_dead" in frag.lower():
            continue
        match = re.search(
            r"play\s+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
            frag,
            re.I,
        )
        if not match:
            continue
        em = match.group(1).lower()
        if em not in out:
            out.append(em)
    return out


def resolve_play_emails(
    *,
    tok8: str = "",
    gid: str = "",
    dest: str = "",
    hotmail_notes: str = "",
    gmail_rows=(),
) -> list[str]:
    """Buyer Play emails. tok8, then gid, then hop-dest note, then hotmail play line."""
    out: list[str] = []

    def add(items) -> None:
        for em in items:
            em = str(em or "").strip().lower()
            if "@" in em and em not in out:
                out.append(em)

    add([play_email_for_tok8(hotmail_notes, tok8)])
    add(play_pool_tok8_hits(gmail_rows, tok8))
    add(play_pool_gid_hits(gmail_rows, gid))
    add(play_pool_dest_hits(gmail_rows, dest))
    add(play_emails_in_note(hotmail_notes))
    return out


def play_pool_tok8_hits(rows, tok8: str) -> list[str]:
    """Play emails whose notes contain this purchaseToken prefix.

    rows are (email, notes). Fewer than 8 characters, or a prefix absent
    from every note, is a pool-wide miss: an empty list. Do not switch a
    random Google. 2026-09-25 <tok8>, <tok8>, <tok8>, <tok8> and
    <tok8> were absent from the gmail-play notes and from the four live
    libraries.
    """
    tok = str(tok8 or "").strip().lower()[:8]
    if len(tok) != 8:
        return []
    out: list[str] = []
    for email, notes in rows or []:
        if tok not in str(notes or "").lower():
            continue
        em = str(email or "").strip().lower()
        if em and em not in out:
            out.append(em)
    return out


def persist_play_bind(
    hotmail_db,
    gmail_db,
    *,
    dest: str,
    source: str,
    play: str,
    tok8: str,
    now: str,
    gid: str = "",
) -> dict[str, Any]:
    """Append bind notes. Missing row is not success.

    # ops removed: the original opened the account-pool sqlite via
    # grok_hotmail_pool.open_inventory_sqlite and appended `play EMAIL tok8`
    # notes to the dest row and `hop dest DEST leftover SOURCE tok8` notes to
    # the Play row inside BEGIN IMMEDIATE transactions. The pool is not
    # shipped, so this research copy raises instead of faking a persist.
    """
    raise NotImplementedError("persist_play_bind: pool sqlite persistence not shipped (# ops removed)")


# leftover-air (Air produce) vs grok-heavy-line (Pro leftover) vs hop desks.
# Play pool tags like grok-lite-heavy are claim --by for empty Google, not a
# leftover session. G2 2026-10-08 acct claimed_by grok-lite-heavy + GROK_CLAIM_BY
# leftover-air was refused as play_claimed_other_session; GET ultra+cap
# already ready. That is not the Air/Pro race.
try:
    import line_lock as _line_lock
except ImportError:
    # ops removed: line_lock (session-claim ledger) is not shipped. The
    # claim-by constants below are empty and foreign_session_claim raises.
    class _LineLockStub:
        SESSION_CLAIM_BY = frozenset()

        @staticmethod
        def foreign_session_claim(other: str, mine: str) -> bool:
            raise NotImplementedError("line_lock not shipped in this research copy")

    _line_lock = _LineLockStub()

LEFTOVER_SESSION_CLAIM_BY = _line_lock.SESSION_CLAIM_BY


def leftover_notes_match(notes: str, leftover: str) -> bool:
    """True if notes already name this leftover hotmail (full or local-part)."""
    notes_l = str(notes or "").lower()
    left_e = str(leftover or "").strip().lower()
    if not left_e:
        return False
    if left_e in notes_l:
        return True
    local = left_e.split("@", 1)[0]
    if not local:
        return False
    return (
        f"leftover {local} " in notes_l
        or f"leftover {local}@" in notes_l
        or notes_l.rstrip().endswith(f"leftover {local}")
    )


def leftover_play_bind_refuse(
    grow: Any,
    leftover: str,
    *,
    claim_by: str,
    play: str = "",
) -> dict[str, Any] | None:
    """Refuse leftover notes on a Play claimed by another session or already leftover."""
    if grow is None:
        return {"ok": False, "error": "play_not_found", "play": play}
    keys = set(grow.keys()) if hasattr(grow, "keys") else set()
    notes = str((grow["notes"] if "notes" in keys else "") or "")
    status = str((grow["status"] if "status" in keys else "") or "")
    claimed_by = str((grow["claimed_by"] if "claimed_by" in keys else "") or "")
    notes_l = notes.lower()
    if "leftover " in notes_l and not leftover_notes_match(notes_l, leftover):
        return {"ok": False, "error": "play_already_leftover", "play": play}
    if (
        status == "claimed"
        and claimed_by
        and claimed_by != claim_by
        and _line_lock.foreign_session_claim(claimed_by, claim_by)
    ):
        return {
            "ok": False,
            "error": "play_claimed_other_session",
            "play": play,
            "claimed_by": claimed_by,
        }
    if status == "used" and not leftover_notes_match(notes_l, leftover):
        return {"ok": False, "error": "play_already_used", "play": play}
    return None


def persist_leftover_play_bind(
    hotmail_db,
    gmail_db,
    *,
    leftover: str,
    play: str,
    tok8: str,
    now: str,
    gid: str = "",
) -> dict[str, Any]:
    """Append leftover Play tok8 notes. Missing row is not success.

    # ops removed: same pool-sqlite persistence as persist_play_bind, plus a
    # leftover_play_bind_refuse gate on the Play row's status/claimed_by. The
    # pool is not shipped; this research copy raises instead of faking.
    """
    raise NotImplementedError("persist_leftover_play_bind: pool sqlite persistence not shipped (# ops removed)")


def ultra_active_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows or []:
        sku = str(row.get("sku") or row.get("product") or "").lower()
        st = str(row.get("status") or "")
        active = bool(row.get("active")) or st.endswith("STATUS_ACTIVE") or st == "ACTIVE"
        if active and "ultra" in sku:
            out.append(row)
    return out
