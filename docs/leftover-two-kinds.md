<!-- Sanitized research copy. Ops/account/card/egress specifics removed. -->

# Play leftover 的两种含义 (交付停续 vs 空账本可写回)

> Rewritten from the 2026-09 operations knowledge card. Account names, card
> numbers and paths redacted; the classification logic is unchanged.

## 触发条件

看见 Play 上 `grok.ultra` leftover (`autoRenewing=false`, `actions=[RESTORE]`),
或要把失效号的 leftover 重新 g(4) 写回, 或要把一个已停续的 dest 当空账本用.

## 前置条件

- GET 已有 `grok.ultra ACTIVE` 时, 禁止 POST sync, 禁止 g(4) 自替换.
- 订阅墙有 Today $ 时禁止 Subscribe. 不要 Pause.
- 外号 leftover 烙着别人的 obfuscatedAccountId (64-hex GID) 时, 直接 destg4 =
  "unable to change your subscription plan". 必须 skipg4 洗空再 destg4
  (见 `docs/leftover-hop-dest.md` 与 `scripts/hop_oracle.py`).

## 两种 leftover

1. **交付 leftover (delivered-and-canceled)**: GET 已经 `grok.ultra ACTIVE` 且
   `cancelAtPeriodEnd=true`, Play 上 `autoRenewing=false`. 这是产线写回后的
   停续费状态, 订阅还挂在原号上. 不要再 g(4) 自替换. 只有用户点名 hop 时才走
   skipg4 + destg4, 转移后旧号立刻 INACTIVE.
2. **空账本 leftover (empty-ledger)**: GET 没有 ACTIVE ultra, 但 Play 侧仍有
   该 SSO GID 的 `grok.ultra` 行. REST sync (`updated:0`) 拉不回来. 同机
   SSO + 自己的 Play, Cancel 成 leftover 后 fire `g4`, 墙上无 Today $ 才
   Subscribe, 重新写回.

判别顺序: 先做一次活的 GET + `GetGoogleObfuscatedId`
(`existingActive`), 再看 Play e2 inspect. 不要只看 Play leftover 行.

## 验证方法

- 交付 leftover: `existingActive` 里有 `grok.ultra`; GET `STATUS_ACTIVE` +
  `cancelAtPeriodEnd`.
- 空账本 leftover: `existingActive` 为空; Play e2 inspect 有 dest GID 的
  `grok.ultra`; GET 无 ACTIVE ultra.
