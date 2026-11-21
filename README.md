# grok-bug-v4-account-hop

Sanitized research copy of the mechanism behind the "Grok Heavy leftover hop"
chain (Google Play Billing, Grok / SuperGrok Heavy `grok.ultra`), built and
frozen around 2026-09.

> Sanitized research copy. Ops/account/card/egress specifics removed.

## One-line mechanism

A canceled, non-renewing Google Play subscription (`grok.ultra`,
`autoRenewing=false`, `subscriptionClientActions=[RESTORE]`) can be moved to a
different Grok account by (1) re-purchasing it *without* an
`obfuscatedAccountId` so Play issues a new deferred order with an empty GID
field ("skipg4 wash"), then (2) firing a second deferred purchase that carries
the *destination* account's 64-hex `obfuscatedAccountId` ("destg4"), which
Play stamps into the new order; the Grok backend then serves Heavy to the
destination account and drops the old one.

## Chain diagram (text)

```
leftover grok.ultra @ account-A          (Play: autoRenewing=false, actions=[RESTORE],
                                          obfuscatedAccountId = someone else's 64-hex GID)
        |
        |  direct destg4  -->  "unable to change your subscription plan"  (cross-GID refuse)
        |
        v
  [1] skipg4 / skipg4p1m                  (frida -> InAppBillingService d2(17,...) with
        |                                  replacementMode proto, accountId EXCLUDED)
        v
  new GPA, obfuscatedAccountId EMPTY      (deferred $0 wall: "Starting <date> $299.99",
        |                                  "Your first charge will occur on <date>")
        |  Cancel -> leftover becomes cap'd/canceled
        v
  [2] destg4p1m(gid)                      (gid = gid_from_jwt(dest SSO JWT) via
        |                                  grok_api_v2 GetGoogleObfuscatedId,
        |                                  patched into hooks/heavy_wall.js -> extras.accountId)
        v
  new deferred order, obf = dest GID  --> Subscribe (wall must NOT say "Today $")
        |
        v
  [3] dest GET (grpc GetSubscriptions)    grok.ultra STATUS_ACTIVE + cancelAtPeriodEnd=true
                                          old account-A GET: INACTIVE
```

## Background (2026-09)

In mid/late September 2026 we ran an attended two/four/eight-desk operation
(Pixel + MuMu emulators, agent-supervised, one gate at a time) that hopped
canceled SuperGrok Heavy leftovers from spent source accounts onto fresh
destination accounts. Every step was gated on live evidence (frida inspect of
the Play purchases, OCR/dump of the FLAG_SECURE purchase wall, and a gRPC
`GetSubscriptions` GET against the dest SSO JWT); the settle rules in
`scripts/hop_oracle.py` refuse to count a hop unless the dest GET shows
`grok.ultra STATUS_ACTIVE` with `cancelAtPeriodEnd` and the source GET has gone
`INACTIVE`. This repo publishes the mechanism only: what the wall text means,
which fire variant washes vs. bakes a GID, how the oracle decides success, and
every stop-condition learned from the 2026-09 runs.

## Repo layout

| Path | What it is |
|---|---|
| `scripts/skipg4_once.py` | one-shot wash of a RESTORE leftover (one password verify, no retry loop) |
| `scripts/hop.py` | full chain driver: inspect -> skipg4 wash -> cancel -> jwt gid -> destg4 -> GET |
| `scripts/destg4_once.py` | one-shot destg4: `gid_from_jwt` -> `patch_gid` -> fire -> dest GET -> cancel cap |
| `scripts/hop_oracle.py` | pure settle rules: wall classification, wash/success verdicts, dest-SSO gates |
| `scripts/billing_core.py` | trimmed fire/wait_wall/gate/GID layer extracted from the original `billing.py` |
| `scripts/fire_heavy.py` | frida attach + rpc fire launcher (`inspect`, `skipg4`, `destg4`, ...) |
| `hooks/package.json` | `frida-java-bridge` dependency manifest (run `npm install` before `frida-compile`) |
| `hooks/heavy_wall.js` | frida hook: e2 inspect, offer parse, replacement-mode buy, all fire variants |
| `hooks/dump_gid.js` | frida hook: on-device `GetGoogleObfuscatedId` (1.2.46 R8 path included) |
| `hooks/ack_27008.js` | frida hook: raw binder `transact(902)` purchase acknowledge |
| `docs/leftover-hop-dest.md` | the module contract: order, gates, stop conditions (sanitized) |
| `docs/dual-attended-hop.md` | attended multi-desk operation notes, per-date patches (sanitized) |
| `docs/leftover-two-kinds.md` | the two kinds of "leftover": delivered-and-canceled vs. empty-ledger |
| `POST.md` | Chinese technical write-up |

## Prerequisites / what is NOT here

- Code is published for **reading**, not running. It is not out-of-the-box
  runnable: the adb/uiautomator/OCR device layer (`device.py`), the gRPC GET
  client (`grpc_subs.py`), the cross-process lock (`line_lock.py`), the account
  pool, the card-binding layer and the browser sign-in layer (`ab_signin.py`)
  were all removed or stubbed. Every stub raises loudly instead of faking a result.
- `hooks/*.js` are frida-compile entrypoints (`import Java from
  'frida-java-bridge'`); run `npm install` inside `hooks/` before compiling,
  as compiled bundles and `node_modules` are not shipped.
- Card / account / proxy specifics are removed. Values come from environment
  variables where the mechanism needs them (`SSO_JWT`, `HOP_DEST`, `HOP_OLD`,
  `GOOGLE_PW`, `CARD_LAST4`-style `HOP_PAY_LAST4`/`HOP_AVOID_LAST4`,
  `HOP_LIVE_LAST4`, `MUMU_SERIAL`/`ANDROID_SERIAL`). Local artifacts write to
  `./work/`.

## Disclaimer

This repository is published for Google Play Billing mechanism research only.
It is sanitized: no accounts, credentials, cards, card-issuer details, or
egress/proxy endpoints are included. Nothing here is affiliated with or
endorsed by Google or xAI. Using any of this against accounts you do not own,
or in violation of any terms of service, is at your own risk; the authors
accept no liability for any consequence of use.

## 系列

- v1 `grok-bug-v1-deferred-upgrade`: 一次 `g(4)` Lite 一付三 deferred replacement (2026-08)
- v2 `grok-bug-v2-delayed-sync`: v1 失效后的延迟首次 sync 番外 (2026-09)
- v3 `grok-bug-v3-double-g4-writeback`: 两次 `g(4)` 停续 leftover 零元写回 (2026-09)
- v4 本仓库: 基于 v3 的 `skipg4`/`destg4` 跨账号转移 (2026-09)
- v5 `grok-bug-v5-x-subscription-ultra`: `x.subscription.ultra` 新 SKU `mode 3` 重建 + 墙分类 (2026-10)
