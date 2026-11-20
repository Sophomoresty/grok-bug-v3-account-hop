<!-- Sanitized research copy. Ops/account/card/egress specifics removed. -->
<!-- Source: grok-heavy-pixel/workflows/leftover-hop-dest.md (2026-09/10).
     Mechanism, gate rules, wall-text classification, coordinates and error
     codes are preserved verbatim where possible. Account emails, purchase
     token prefixes, card last4/BINs/issuers, egress nodes and device ports
     are replaced with placeholders (<acct>, <play>, <tok8>, <last4>, <bin>,
     <card-issuer>, US_EGRESS, $MUMU_SERIAL). Pure per-account run ledgers
     were omitted; every omission is marked. -->

# leftover skipg4 洗 GID 再 destg4 跳 dest

用户点名「转移 leftover / 跳 dest / A 额度用完换 B / skipg4 destg4」才走这条.
不是产线默认收尾. 旧 dest GET 会立刻 INACTIVE.

默认 **模块 + agent 值守**, 不是全部自动化. 不要一键连跳. 多机配置和值守顺序见
`dual-attended-hop.md`.

2026-09-22 四机值守补丁 (机制保留): 绑卡线程池 `shutdown(wait=False)`, 否则填完
PAN 后主线程卡死. Save card 前禁止 `key 111` (会掉进 Add PayPal). 卡验证码匹配
`GOOGLE*<3位> <6位>`. 墙上先勾的默认卡要改成已验证 last4 再 Subscribe.
`dest_login_accept` 必须在 destg4 前. `sso_other_holder(DEST, sso)` 必须在
`persist_jwt` 之前, 串号 JWT 禁止写库. 换号后 `library.db` 仍是上一号时只
`sync_play_library`, 不要把旧 tok 当 mismatch. GET `purchaseToken` 前 8 位对上
当前 Google 的 library 再 skipg4. `sync_play_library` OCR 停在应用广告直接开
subscriptions (`sync_onboard_done`). destg4p1m_verify `timeout_continue` 且 outer
GET dest ultra+cap, src ultra false 算成功. 墙上已列出且无 Verification needed 的
hop-live 卡才 Subscribe. 同一波最多三台 switch, 两台 skipg4 可以并行.

## 固定入口

一跳 env 必须齐, 无默认 dest. skipg4 用 `skipg4_once.py` (密码只打一次). 空 obf
之后 destg4 用 destg4 外壳脚本 (内部 `destg4_once.py`), 入库成功才算 Exit 0.
destg4_once 不入库, 禁止当 hop 完成. dest grok 密码登录走 CDP sign-in.
cookie dump 用 `Storage.getCookies`, 禁止 `Network.getCookies` urls 过滤 (会 0 条).

```
export ANDROID_SERIAL=$MUMU_SERIAL        # e.g. localhost:<mumu-port>
# Darwin: env -u ADB_SERVER_SOCKET (adb 37 cannot bind remote-server style)
export HOP_OLD=account-A@example.com      # leftover source
export HOP_DEST=dest@example.com          # fresh dest
export GOOGLE_PW='<leftover Play password>'
export HOP_PAY_LAST4=<verified-live-last4>   # CARD_LAST4-style env; no default
export HOP_AVOID_LAST4=<leftover-declined-last4>[,...]
export HOP_WORK=./work/hop-<src>-<machine>
```

(# ops removed: 原 env 示例带真实 serial 端口, 默认 want/avoid last4 与
work-dir 绝对路径, 已占位.)

1. inspect 仍有 GID: 跑 `skipg4_once.py` (FLAG_SECURE 密码页 IME ON 时 Verify
   `su_tap 540,1760`, IME 关才 `540,1836`; 不要 `tap 1785`). skipg4 前
   `dumpsys account` 必须含 `HOP_PLAY`, 否则 `skipg4_play_mismatch` 退出 4
   (截图 Canceled Heavy 不够, dumpsys 仍是 dest Play 时会假阳性洗掉已入库 dest
   leftover). 密码页 dump `No internet connection` 先 Try again 再填密. 无密码页
   约 6s 就 inspect, 不要空等 40s. skipg4p1m RESTORE 墙 `Starting Oct $299.99`
   **且** `Your first charge will occur on Oct …` 是 deferred restore, 要
   Subscribe (`skipg4_subscribe_ok` `deferred_restore`; 洗出新 GPA 空 obf
   AR=true). `Today $299.99` / `Starting today` 才是 CHARGE_FULL, 禁止
   Subscribe. skipg4 p3m `$99.99` intro 不是 p1m restore, 禁止当 skipg4.
   skipg4deferred `You'll get these benefits if you subscribe` 点 **No thanks**
   (`293,1836`), 禁止 Continue. destg4 GID 还在是 unable_change. skipg4 从
   Payment methods / Payments & subscriptions 出墙是 `payment_methods`, BACK +
   `am start` Grok 再 fire. Acquire `Error | No internet | OK` 的 OK 按钮
   `[63,1789][1017,1884]` cy=1836, `recover_play_no_internet` 不要 clamp 1780.
   出口国已 US 时密码页 No internet 就在页上 Try again 再 type, 不要离开去代理
   面板 (开 Dashboard 会拆掉 acquire, 回来必须 refire).
2. inspect 新 GPA + obf 空: 鉴权弹窗 `Require authentication` 点 No thanks 再
   OK (`su_tap 540,1639` 然后 `540,1836`). Play Points `Not now` 双钮
   `293,1836` 或居中 `539,1509`. Play Fest 同样点左钮 Not now, 禁止 Explore,
   禁止 Resubscribe. skipg4 后 `Turn on backup payment methods?` 只 BACK
   (`backup_back`). `hop.dismiss_after_skipg4` / destg4_once 会点.
3. 跑 destg4 外壳 (空 obf Cancel + jwt destg4p1m; 必填 `HOP_PAY_LAST4`, 禁止默
   认值). dest_get_user_not_live 先 dest_login 再入库, 否则退出 2. destg4 p3m 墙
   $99.99 intro 不要订. destg4p1m deferred_restore + wall last4 是已验证卡才
   Subscribe (GPA 新单 obf=dest GID). destg4 outer get_user 200 + play_bind
   tok8 + src_ultra false + cap True: 立刻入库, 不要 dest-post (~60s). destg4
   outer 401/403 `dest_get_user_not_live` 且同进程 GET True False cancel2 cap
   True: dest-post `dest_login_once` 再入库. ingest `dest_get_not_active` 时再
   `dest_login_once` 刷新 dest JWT, 不要当 destg4 失败. destg4 Subscribe 后墙关
   到 Grok `Ask anything`: `verify_google_password` 立刻 `timeout_continue`
   `left=grok_home`, destg4_once GET dest, 不要空等 45s. dest_login 只用一个
   sign-in 实例 (脚本复用, 每号新 tab, 登完关 tab). 新开实例常 `no_turnstile`
   (`ts_len<=20`, 不 POST `/api/auth/sign-in`); 立刻返回, 禁止把 leftover
   cookie 当 dest SSO. skipg4 可并行, `dest_login_accept` 仍必须在 destg4 前.
4. skipg4 `timeout_continue`: **不要重跑 skipg4**. inspect 已洗空则 destg4.
   墙 last4 不是 `HOP_PAY_LAST4`: BACK 出墙, Payment methods bind,
   `bind_apply_timeout` 且列表已有 want last4 = 绑成功. 墙 leftover 拒卡 last4
   必须 pick `HOP_PAY_LAST4`. Play Points 后 `Choose amount` Play Credit 只
   BACK. skipg4 后 `Turn on backup payment methods?` 只 BACK, 禁止 Turn on.

禁止连跑 skipg4: `billing.verify_google_password` 每圈重打密码, 会打到
`maximum number of login attempts`. `GOOGLE_PW` 空时不输入. 没有内置密码.
destg4 必须带这台 Play 的 `GOOGLE_PW`. `verify_fail_kind` 返回
`login_attempt_limit` 后点 OK, 禁止 Forgot password, 禁止再输入.

## 模块

每步看 inspect / GET 再下一步.

0. dest grok 密码登录 (`dest_login_once`). 先打开
   `accounts.x.ai/sign-in`, 页标题是登录页且能看到邮箱登录, 再跑. incoming
   cookie `dest_sso_shared` 且 dest sqlite JWT dest-only 且 GET 不是 grpc 16:
   `dest_login_keep_existing_jwt` destg4 用 dest sqlite JWT. dest JWT grpc 16
   换冷却 label. 预开页后再登约 16s. x.ai sign-in 200 且 email==dest 且 href
   不在 sign-in 即 `dest_login_accept` ok. href `grok.com/tos-gate` 且
   email==dest 是 accept. persist 还要 grok.com get-user 200 且 email==dest
   (`dest_sso_email_ok`). get-user 401 禁止 persist
   (`dest_get_user_not_live`). get-user 200 但 email 不是 dest 是
   `dest_sso_email_mismatch`. href `chrome-error://chromewebdata/` 是连接失败,
   不是 accept. persist 后 GET grpc 16 记 `dest_jwt_grpc_16` 禁止当 dest-only.
   Pixel 禁止登 dest Grok app.
1. `fire_heavy.py inspect` (空则 `pm clear vending`, 禁止 GET token 伪造)
2. RESTORE leftover: `skipg4p1m`; 否则 `skipg4`, `item_unavailable` 再 p1m.
   已空 obf 禁止再 fire (`already own`)
3. inspect: 新 GPA + obf 空 = 洗完. timeout / already own 也先 inspect
4. Cancel 右边, 不要 Pause
5. dest GID: `billing.gid_from_jwt` (grpc-status 0) 成功则直接 destg4. 禁止先
   登 dest Grok / writeA1 / pm clear grok. JWT 过期才 sign-in 刷新
6. destg4 外壳内部 `destg4_once.py` (`destg4p1m`, 不要先 destg4 p3m). 墙
   `Starting Oct $299.99` + first-charge copy 是 deferred destg4,
   `HOP_PAY_LAST4` 必须在墙上. GET dest 用的 SSO 必须只属于 dest
   (`dest_sso_shared` 禁止入库). benefits overlay 禁止 Continue.
7. GET dest `grok.ultra STATUS_ACTIVE`, 旧 dest 无 ACTIVE ultra. Cancel 到
   `cancelAtPeriodEnd`. Play Points 挡住 Cancel 时先 Not now.
8. GET dest ACTIVE 后必须再实登一次: x.ai 200 且 email==dest, 且 grok.com
   get-user 200 且 email==dest.
9. 去伪存真四关全过才入库: (a) 会话邮箱 == dest 且 href 不在 sign-in
   (`dest_login_accept`); (b) grok.com get-user 200 且 email==dest
   (`dest_sso_email_ok`); (c) dest JWT 不是 leftover JWT (`dest_sso_is_source`)
   且不挂任何别的邮箱 (`dest_sso_shared`); (d) **用这把 dest-only SSO** GET
   `grok.ultra ACTIVE+cap`. destg4 墙 deferred / verify missed 时拿 leftover
   JWT 看到 ACTIVE 不算 hop 成功. `dest_ingest_ready` 非 dest-only ACTIVE 返回
   `dest_get_not_active` / `dest_sso_is_source` / `dest_sso_email_mismatch` /
   `dest_jwt_grpc_16`. 同一 leftover 同时只 hop 1 个 dest.

## 前置 (机制闸, 运营细节已脱敏)

- 用户点名 hop. 不要对未点名的交付 leftover 做 skipg4. sold 记录 `hop:false`
  (长效 / 质保) 禁止 skipg4 / destg4 / ingest (`hop_source_forbidden`).
  同一 leftover 同时只挂 1 个 dest.
- leftover GET `has_ultra_active` 已 false: 记 `cannot_transfer`, dest 留空.
  leftover GET `grpc_status` 16 不是 ultra-false, 先 dest_login 刷 SSO 再 GET
  (`pending` `sso_refresh_then_get`). dest 已 sold 禁止 unmark. leftover
  inactive + dest sold 同样 cannot_transfer dest 空
  (`hop_ledger_sold_dest_policy`). leftover 仍 ACTIVE 才换新 unsold dest.
  关表 `hop_ledger_ok` True: 每个 unique leftover 要么独立 dest hop, 要么
  cannot_transfer dest 空, dest 邮箱不双计.
- dest GET includeInactive 必须空 (无 ACTIVE ultra). dest 有 SSO. dest grok
  密码必须能登录, 不能只靠 dest SSO GET. skipg4/destg4 之前就要确认.
- (# ops removed: dest 池领取 / xai 密码拆分 / 入库 CLI 细节属运营层, 已删;
  保留的判定是 `dest_xai_ready` / `dest_ingest_ready` 的规则: dest grok 密码
  必须已从邮箱密码拆开, 否则 `dest_xai_missing` / `dest_xai_same_as_mail`.)
- Play inspect: `grok.ultra` 且 `autoRenewing=false`. leftover 烙着旧 dest GID
  时直接 destg4 = unable. 空 obf + `autoRenewing=true` = 已洗到 leftover 自
  己, 禁止再 skipg4, 直接 Cancel + destg4.
- Heavy 墙有 Today $ 禁止 Subscribe. 不要 Pause. 禁止 POST
  `/rest/subscriptions/sync`.
- (# ops removed: 代理 / 出口节点固定与面板操作属运营层, 已泛化为 US_EGRESS.
  机制结论保留: Play `Try again` / IAB `No internet` 先修隧道再 fire, 不要盲订.)
- (# ops removed: 卡台 / 绑卡 / 换卡细节属运营层. 机制结论保留: 拒卡
  OR_CCREU / OR_MIVEM / OR-PFGVEM 换不同 live last4; 同一 Google 禁止同 PAN
  再绑; `bind_apply_timeout` 后 dump 仍是 Add-card 表就点 Save; 列表已有
  want last4 即绑成功 `bind_timeout_listed`; `Verification needed` 的行不可订.)
- 换 Google / clone 后: `dumpsys account` 必须是 leftover Google.
  `library.db` ownership 若还是源机账号, inspect 一定空. inspect n=0 但订阅
  页有 SuperGrok Heavy: `sync_play_library` 再 inspect. sync 卡在 Play Points
  点 Not now `540,1509`. sync OCR 停在 `Server busy` / `Server error` 用 `su`
  tap 精确按钮 Try again `[382,843][697,948]` (plain `input tap` 不离开).
  第二次还在同一页就 `am force-stop` vending 再开 subscriptions, 不要循环点,
  不要再 `pm clear`. 页面已经是 Heavy 但 library 仍空时再等. 多台同时
  `pm clear` 会一起 Server busy. inspect [] 但 library 已是当前 Google
  grok.ultra: 开 Play subscriptions 等到 SuperGrok Heavy 再 inspect
  (`skipg4_wait_play_subs`).
- 2FA / TOTP (机制结论): FLAG_SECURE dump 无 Enter code 时 `totp_fresh` 后
  keyevent 数字, 框 y≈960 (1080x1920), hide IME (不要 BACK), `su` tap NEXT
  `911,1825`. I Agree 点 `~870,1280`, 禁止 `add --resume` 停在 I Agree. 2FA
  chooser 的 `Try another way` 是列表行 cy~1116, 不是底栏 `200,1836`.
  `Wrong code` 且主机 Date 已对齐 = 库存 secret 已转, 不要连打.
  Account recovery 发码到 Play 自身邮箱时走 DoH A 记录取码, 不要 IMAP /
  fake-ip.
- (# ops removed: leftover Play 映射按 GET tok8 对当场 library / 备注, 禁止
  只用领取时间戳配对 —— 规则保留, 逐账号对账记录已删.)
- skipg4 墙只显示 leftover 拒卡 last4: `want_not_on_list` 禁止 Subscribe.
  BACK 出墙, Payment methods 有已验证 live last4 再 fire.
- skipg4 拒卡后 See more 没有另一张可订的卡: 停, 不要盲点 `458,1750` 或
  `540,1836`. 落到 `Choose amount` / Play Credit 只 BACK, 禁止 Continue
  (`skipg4_landed_play_credit`).
- `HOP_AVOID_LAST4` 是逗号分隔. See more 必须拆开再禁, 不能把整串当成一个
  last4.
- 多台并行: 每台独立 serial, 独立 dest, 独立登录 label. bind 一把
  serial 锁. 同一波最多三台 switch.

## 验证

- dest GET `grok.ultra STATUS_ACTIVE` (不要用 ACTIVE 子串). 旧 dest 无 ACTIVE
  ultra.
- dest grok 密码登录 ok (会话 email==dest). grok.com get-user 200 且
  email==dest. get-user 401 禁止 persist.
- 入库记录 `ok:true` 且 dest 未标 sold. hop 完成 ≠ 已卖.
- destg4 GET dest `grok.ultra ACTIVE+cap` 当场入库. 洗单 tok (skipg4 自己那笔)
  不计入.
- 换号后 `library.db` 里上一号的 grok.ultra 行还在时, `limit 1` 会读到旧行.
  `library_ultra_select_sql` 按当前 Google 过滤.
- dest create ≈ destg4 秒. 到期几乎等于旧单周期末.
- Play leftover `obfuscatedAccountId` == 新 dest GID, autoRenewing=false.
- 当天墙无 Today. 未 POST sync.

失败即停: Today $; dest GET 非空还 skipg4; destg4 unable 且 GET 仍空; Play 墙
No internet; skipg4 后 inspect obf 仍在; inspect 空却用 GET token 出墙;
`maximum number of login attempts` 后连 fire; dest_xai_missing /
dest_xai_same_as_mail; dest_grok_login; dest_sso_shared; dest_sso_is_source;
dest_sso_email_mismatch; dest_get_user_not_live; dest_sso_mismatch;
dest_jwt_grpc_16; dest_get_not_active.

## 不要当成

- 不是工厂速刷. 不是用量配额重置已证. 不是无人全自动.
- 周期一到 leftover 没了, 不能再 $0 跳.

## 2026-10-01 之后多机补丁 (机制结论)

- 八机并行: dest_login 各自 label; skipg4 与 SWITCH 可叠 dump; destg4 dump
  per-serial, 八台可叠; SWITCH_BUSY 只挡同一 serial. destg4 外层优先
  `destg4_get_user_from_login` (login.json get_user 200 email==dest + grpc
  dest ultra+cap + src_ultra 不是 True), 不要再占共享 get_user. 空 tok8 的
  destg4.json 不改写, dest-post 后再入库.
- skipg4 墙 leftover Visa-only: bind 已验证 live last4 再 skipg4. 列表已有
  live 卡用墙上的 (`picked_list` / `already_on_wall`). 已 hop 的 dest Play 禁止
  skipg4.
- Play 只按 tok8 备注. totp 缺失第一次 SWITCH `need_totp` 后可重试.
- 洗单 tok 不入库. 入库 tok8 用 dest GET 的 `google.purchaseToken` 前 8, 设备
  库同一行 ar false, actions RESTORE. 同一 Google 洗单一笔加 destg4 一笔之后
  禁止第三笔 Subscribe. 同一 last4 同时只一笔 Subscribe.
- cancel 相关: sku URL 先打开洗单的 Canceled / Resubscribe 页时, 本次还没点过
  Cancel 不能当成新单已取消; 等页面翻到 Next payment 再点右边 Cancel
  (`786,1857`), 确认页点右侧蓝色 Cancel (`676,1836`), 不点 Pause / Keep.
  取消页 OCR 截成 `will be cancele` 仍是确认页. Canceled + Resubscribe 后下一
  帧变 Next payment 时再点, 不要把前一帧当已取消.
- verify 相关: Subscribe 后每秒读到 `Turn on backup payment methods` 只 BACK,
  不点 Turn on, 立刻返回. dump 只有转圈 (ProgressBar, ~6KB) 连续两帧就返回再
  BACK + force-stop vending + 重开 Grok 再 fire, 不点 Continue with Google /
  Email. `Error / We are unable to change your subscription plan / Got it`
  不是 not_today_zero: 点 Got it, `ack_token` 当前 AR=false 的 ultra, 再 fire
  一次; 第二次仍是同一张 Error 就不要再 Subscribe.
- `grok_screen_ready`: 最后一条 `mCurrentFocus` 含 `GrokActivity` 且当次 png
  字节 `>= 80000`. splash 白底 logo 44-46KB / 黑屏 12KB 不是 ready. 登录页
  Continue with Email (~193KB) 会被当成 ready, 在这页 fire 也能过, 不要把这页
  force-stop 回 splash.
- `su_tap`: `su -c input tap` 只试一次 timeout 8s, `TimeoutExpired` 或 rc 非 0
  再 `input tap` 一次. 未捕获的 TimeoutExpired 会杀掉 destg4, Subscribe 还留
  在墙上.
- Subscribe 后 `No internet connection` 点 OK 回到登录页, inspect 仍是洗单:
  这笔没落地. 进程还活着不要再开 destg4; 进程已死且 inspect 仍是洗单才允许再
  fire 一次.

(# ops removed: 2026-10-01 至 10-11 的逐账号 run ledger, 卡台余额流水, 开卡
与退款记录, 各时段速率对账 — 全部与账号/卡绑定, 无法脱敏保留, 已整段省略.
以上仅保留可复用的机制结论.)
