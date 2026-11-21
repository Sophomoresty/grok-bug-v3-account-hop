<!-- Sanitized research copy. Ops/account/card/egress specifics removed. -->
<!-- Mechanism, gate rules and coordinates preserved; account emails, token
     prefixes, card last4/BINs/issuers, egress nodes and device ports are
     placeholders. Pure per-account run ledgers are omitted. -->

# 多机有人值守 leftover hop

用户说「多台并行 hop」= MuMu 多实例并行, agent 值守. 不是无人连跳. 模块契约仍是
`leftover-hop-dest.md`; 本文件记值守配置与各日期实跑补丁.

## 配置 (脱敏)

| 项 | 值 |
|---|---|
| g4 核 | `hooks/heavy_wall.js` + frida-compile (源). cache 只放 compiled/live |
| 设备 | 每台独立 `ANDROID_SERIAL=$MUMU_SERIAL` (vmindex ↔ 端口映射, 端口已脱敏) |
| ADB | Darwin adb 37 listen `-L tcp:<adb-port>`, connect `localhost`. 禁止 `ADB_SERVER_SOCKET=tcp:127.0.0.1:<adb-port>` (`adb_server_socket_env`) |
| 出口 | US_EGRESS (节点已脱敏). 出口国与 tun 状态先确认再 fire |
| 卡 | (# ops removed: 卡台/uid/last4 池已脱敏) 墙上已有已验证 live last4 就用墙上的, 禁止同 Google 第二 PAN |
| dest | `sold=false` `inventory=hop-dest` (# ops removed: 池/账本层未随仓库发布) |

env 必填: `HOP_OLD` `HOP_DEST` `GOOGLE_PW` `HOP_PAY_LAST4`
`HOP_AVOID_LAST4` `HOP_WORK`. 无默认 dest.

## 谁做什么

agent 值守:

- 选 leftover + 空 dest (GET 无 ACTIVE ultra, xai 拆开, jwt gid 64-hex).
  leftover GET 已 INACTIVE 记 cannot_transfer, dest 空, 不要复用别的
  leftover dest. leftover GET grpc 16 禁止 cannot_transfer, dest_login 刷 SSO
  再 GET. dest 已 sold 禁止 unmark. 关表 `hop_ledger_ok` True.
- 写 env, 换 Play, TOTP / I Agree / last4 / 拒卡换卡
- 每步看 inspect / 墙文案 / GET, 再决定下一步
- 失败修一处: 出口隧道, 拒卡换 PAN, 密码锁等待
- 入库后核账, dest 保持 unsold

脚本只跑当前这一闸:

- skipg4: `scripts/skipg4_once.py` (密码一次; 空 obf 不 fire; 无密码页 6s 后
  inspect)
- destg4: 空 obf 后 destg4 外壳 (内部 `destg4_once.py`). Exit 0 只在入库成功.
- 禁止连跑 skipg4

## 一跳顺序 (多机各走一套, 可并行)

一号一 dest. 一号一 PAN. 不要一台连跳, 另一台空转当全自动.

1. accounts 必须只有该 leftover Google
2. 出口隧道 + US 确认. Play `Try again` / IAB `No internet` 先修隧道, 不要
   fire
3. `play-google last4 --prefer WANT`. 没有则 bind (mm/yy+zip). 拒因同一
   Google 禁止同 PAN. `bind_apply_timeout` 后 dump 仍是 Save card 表: 点 Save
   再看列表
4. inspect. Play `Server busy` 先 Try again 直到 For you 首页, 再开 Play
   subscriptions 直到 UI 有 SuperGrok Heavy, 再 inspect. e2rc 6 / purchases=[]
   不要 GET token 出墙. 禁止 `pm clear` 当 Server busy 的第一步. 订阅页已有
   SuperGrok Heavy 但 inspect 空: `library.db` ownership 还是上一号 Google
   (`sync_play_library` 必须 account==当前 dumpsys Google, 不能只看
   grok.ultra 行存在)
5. 有 GID: `skipg4_once.py`. 空 obf + ar True: 禁止 skipg4, Cancel + destg4
6. skipg4 墙无 Today. `HOP_PAY_LAST4` 必须在墙上. 没有则 BACK 出墙 bind. 墙上
   已有已验证 live last4 用墙上的 (`hop_live_last4_on_list`), 禁止同 Google 第
   二 PAN. leftover 产线卡不要 Subscribe. 密码页 No internet: Try again 再
   type, Verify y=1760 当 ADB Keyboard ON (1836 点到 IME)
7. FLAG_SECURE 密码页 dump 只有 Verify + Remember me: 当密码页,
   `su_tap 540,1760` Verify (`skipg4_verify_tap_y`; dump Verify
   `[63,1738][1017,1833]` cy=1785, 1836 点到 IME). dump timeout 且 OCR 只有
   `ADB Keyboard {ON}` (无 SuperGrok Heavy): 也当密码页, type + Verify 1760.
   打完密不要 break, No internet 再 Verify
8. inspect 新 GPA + obf 空. Play Points Introducing: Not now `540,1509`,
   禁止 `293,1836` (会点到 Pause). skipg4 后 Turn on backup 只 BACK
   (`backup_back`). `Want to add this backup payment method?` leftover Visa
   点 No thanks, 禁止 Add (`backup_add_no_thanks`). `wait_wall` Starting Oct
   $299 等到 first-charge 或 Today $ 才分类, 截断 OCR 会假 CHARGE_FULL
9. destg4 外壳. 先 `am start` Grok. fire DeadObjectException 或 dump OCR 是
   桌面: 再 `am start` Grok 然后重 fire. 墙 `You'll get these benefits if you
   subscribe` 点 Continue 再 Subscribe. timeout / item_unavailable 先 GET
   dest; ACTIVE 则 skip p1m. item_unavailable Got it 后再 destg4p1m.
   Subscribe 后 Grok `Ask anything` 是墙已关, 立刻 GET dest, 不要再 dump 45s
10. GET dest `grok.ultra STATUS_ACTIVE`, 旧号无 ACTIVE ultra. Cancel dest 到
    cap
11. dest_login_accept 过, GET dest-only 后再入库. dest 必须 `--require-xai-split`.
    dest `sold=false`. dest 已 sold 禁止 unmark. 聊天不报 Play.

下一跳: 换 Google, 换 dest, 换 `HOP_WORK`. 不要同 env 连跑.

## 值守闸门 (停, 不要黑盒重试)

- Today $ / Starting today $299 (`skipg4_subscribe_ok` CHARGE_FULL).
  skipg4p1m RESTORE `Starting Oct $299.99` + first-charge copy 是 deferred
  restore, 要 Subscribe. skipg4 p3m $99.99 intro 和 skipg4deferred benefits
  overlay 禁止 Subscribe
- destg4 GID 还在: `unable to change your subscription plan`, 先 skipg4 洗空
  obf, 不要 Subscribe $299 当洗 GID
- dest GET 已有 ACTIVE ultra: `dest_already_active` 禁止 destg4p1m; 更不能还
  skipg4
- `maximum number of login attempts` (连打密码). 等几分钟, 改用
  `skipg4_once.py`
- OR_CCREU / OR_MIVEM / OR-PFGVEM: 换 PAN, 不要同卡同 Google. OR_CCREU 后
  `hop_live_after_ccreu` 试剩下 live last4 (含同 BIN 不同 last4); 空才换
  Google
- 2FA: TRY ANOTHER WAY → Authenticator. 不要把手机 Security code 当 TOTP.
  `totp_wrong_code` 且主机 Date 已对齐: secret 已转, 不要连打. chooser
  `Choose how you want to sign in` 的 Try another way 是列表行 cy~1116
- skipg4 Subscribe 后 `Try another payment method` live declined: See more
  点另一张 live, 禁止 leftover Recommended
- `bind_apply_timeout` JSON 且 Payment methods 已有 want last4 = 成功
  (`bind_timeout_listed`)
- skipg4 fire 落到 Payment methods / Payments & subscriptions: BACK +
  `am start` Grok 再 fire (`skipg4_landed_payment_methods`)
- skipg4deferred benefits overlay: No thanks `293,1836`, 禁止 Continue
- Acquire No internet OK dump cy=1836 不是 1780. 出口先修再 fire
- dest_login 只用一个实例. `no_turnstile` 立刻返回, 不要 dump leftover cookie.
  skipg4 可并行, dest_login 串行, dest_login_accept 仍在 destg4 前
- leftover GET purchaseToken 对 inspect tok 才 skipg4. 墙上只有 leftover 拒卡
  last4 先 bind live 再 skipg4
- skipg4 fire 落到 Redeem code: BACK + `am start` Grok 再 fire
  (`skipg4_landed_redeem`)
- I Agree 页禁止 `add --resume`
- 出口面板粉 play: 先修隧道再继续
- skipg4 `timeout_continue`: 不要重跑, 先 inspect
- dest JWT `dest_sso_shared` / `dest_sso_is_source` / GET dest 非 dest-only
  ACTIVE: 不当 hop-dest 交付. `ingest` 必须 `dest_ingest_ready`
- dest_login_once get-user 401 但 x.ai email==dest: 不是失败, 不要 restore
  `jwt_before`
- 对用户不要报 Play 邮箱/密码

## 日期补丁 (机制结论)

### 2026-09-22

- 绑卡线程池 `shutdown(wait=False)`. Save card 前禁止 `key 111` (会掉进 Add
  PayPal). 验证码 `GOOGLE*<3位> <6位>` (# ops removed: 卡产品/流水细节).
  验证通过后该行不再写 Verification needed, 才能 Subscribe.
- 订阅列表第一帧是转圈时 `am force-stop com.android.vending` 一次, 再开
  subscriptions. 不要干等, 也不要 pm clear.
- 绑卡超时截图是 Play Points: OCR 有标题就点 Not now `(540, 1509)`, 禁止
  Learn more.

### 2026-09-23/24

- 前一轮 `Couldn't find this account` 的 Play 下一轮可以 switch/add 成功. 不
  要把 play-dead 写成 leftover GET inactive.
- adb `protocol fault`: 先查是否有占住 adb server 的长连接泄漏 (规则: 值守机
  不要挂常驻 keepalive 到 vending), 杀泄漏进程后 `adb devices` 恢复.
- 并行: 两台 skipg4 或 dest_login 可并行. 同一波最多三台 switch. 四台同时
  dump 会空号.

### 2026-09-25 及之后 (规则收敛)

- 墙必须 Starting 日期等于 first charge, 才 Subscribe. (# ops removed:
  逐账号截图/日期清单.)
- `library.db` 上一号的 grok.ultra 行还在前面时, `limit 1` 会读到旧行.
  `library_ultra_select_sql` 按当前 Google 过滤. 过滤或删掉旧行后再 skipg4.
- 源号还有第二笔 ACTIVE: 换到持有那笔的 Play 再跳.
- destg4 `gid` `not_signin` 是浏览器没落到 sign-in. 库里 RESTORE 行还在就再
  destg4, 不要重订.
- dest GET 仍空时的 `need_skipg4` 不要入库. 登录时 ultra false, 稍后 dest GET
  已是 ultra 且 cap true, 再跑 destg4 得到 `already_capped` 且源 ultra false,
  才入库.
- 备注里没有 tok8 的源: 用池内 SSO 重新 GET 对账 (# ops removed: 对账流水).
  空列表是 pool-wide miss, 不要换一个无关 Google.
- ingest 合并备注, 保留 `play EMAIL tok8`. 之后被标 sold 的 dest 禁止 unmark.
- destg4p1m_verify `timeout_continue` 且 outer GET dest ultra+cap, src ultra
  false 算成功.
- `destg4_success` 在 `src_ultra` true 时返回 false, 不入库. outer dest GET
  ultra+cap 而源仍 ACTIVE 不是 hop.

### 2026-09-30 / 10-01 多机高速

- dest_login 并行多 label; skipg4 + SWITCH 可叠 dump; destg4 dump per-serial
  可叠. destg4 外层优先 `destg4_get_user_from_login`, 跳过共享 get_user.
- destg4 外层 401/403 且同进程 GET True False cancel2 cap True 且 login.json
  不可复用: dest-post 再入库, 空 tok8 destg4.json 不改写.
- leftover Visa-only 时 bind 已验证 live last4 再 skipg4; 列表已有 live 卡用
  墙上的. 已 hop 的 dest Play 禁止 skipg4.
- GET 取 ACTIVE 那行的 tok8 (`get-dest-tok8` 逻辑, `dest_tok8_from_get_rows`),
  INACTIVE 行在前也不取.

### 2026-10-05..11 显示着的桌 (机制结论)

- 窗口保持显示 (# ops removed: hide/show 与实例管理细节属运营层).
- 2FA chooser 的 Authenticator 行用 OCR 单词中心点, 不要固定坐标 (短列表/长
  列表 y 差异大).
- `hop._library_sqlite` 把 SQL 从 stdin 送给 `sqlite3 library.db`, 不用 su
  包装 (su 包装退出 1 且正文空).
- 验证码在卡发行方流水, 不在 Play 黑屏 (# ops removed: 卡产品名). 成功流水是
  `GOOGLE*` 加 6 位才填进 Verify; 失败/临时授权行没有码. 同一张已验证卡换到下
  一台 Google, 列表没有 Verification needed 就直接 `already_on_wall`.
- `inspect_p` 开头先 `ensure_frida_server`. `pidof frida-server` 空时 e2 是
  `ServerNotRunningError`. `setsid /data/local/tmp/frida-server ...` 拉起后
  再 inspect. library token fallback 只在 e2 真的空且 err 不是 adb_dead 时
  用. 空 obf 的已洗单不要拿去 fallback.
- `patch_ultra_token_js` 写进 frida-compile 的 `📦` 包时, 必须把
  `heavy_wall.live.js` 那一行的字节数加上 token 增长, 否则
  `InvalidArgumentError: malformed package`.
- 密码页 ADB Keyboard 还在, Play acquire 焦点还在, inspect 仍是旧 GPA 时,
  再 `su_tap 540,1760` 一次 (`skipg4_reverify_acquire`).
- `Error / We are unable to change your subscription plan / Got it`: 点 Got
  it, `ack_token` 当前 AR=false 的 ultra, 再 fire 一次; 仍是同一张 Error 就停.
- 登录页 Continue with Email 约 193KB 会被 `grok_screen_ready` 当 ready, 在这
  页 fire 也能过. 不要把这页 force-stop 回 splash.
- `su_tap` 超时要回退 `input tap` (见 leftover-hop-dest.md).
- 洗单 tok 不入库. 入库 tok8 用 dest GET `google.purchaseToken` 前 8. 同一
  Google 洗单一笔加 destg4 一笔之后禁止第三笔 Subscribe. 同一 last4 同时只一
  笔 Subscribe.
- 已售 hop-dest 只要现 GET 仍是 Heavy, 就可以当源再 hop. 源 GET 已没有 ultra
  但这笔 dest GET 仍是 ultra 且 cap 不是 true: 不要另领 dest, 沿用原 dest 做
  cancel_cap.
- 取消页: 管理页右边 Cancel `(786,1857)`, 确认页 `(676,1836)`; 70s 循环最后
  一帧已是确认页时再等 8s 看到 Canceled, 不要立刻当 timeout 再 fire.
- 洗单后停在 Grok 登录页 / Ask anything / 订阅页: 见 leftover-hop-dest.md
  2026-10 补丁.
- 客机 CPU 0 且 shell offline: 不要 kill adb server, 不要重启播放器; 只重启该
  实例的 qemu 进程 (# ops removed: 实例管理细节).

(# ops removed: 2026-09-26 至 10-11 的逐账号 run ledger (源→dest→tok8→卡→
截图对账), 卡台余额/开卡/退款流水, 各时段速率与波次对账 — 与账号和卡一一绑
定, 无法脱敏保留, 已整段省略. 以上仅保留可复用的机制结论.)
