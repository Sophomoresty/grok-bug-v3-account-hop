# leftover 搬家: 洗掉旧 GID 再烙新号, 把 Heavy 从 A 号转移到 B 号

前两篇解决了 "写回" — 但写回去的 `obfuscatedAccountId` 是收据上烙的那个 GID, 货永远绑在那只号上. 9 月中旬做批量的时候需求变了: 手上的 leftover 池是卖家弃号 (GID 是卖家的), 买家的号是另一只. 直接对买家号发起替换, Play 一句 "unable to change your subscription plan" 顶回来. 这篇讲怎么把旧 GID 洗掉, 再把买家的 GID 烙进去 — leftover 从此可以在账号间搬家, 我们内部叫 **hop**. 文里略去了具体账号和卡信息.

## 0x00 问题: 替换是认 GID 的

d2 替换的 extras 里 `accountId` 和收据 `obfuscatedAccountId` 必须对齐. leftover 收据上烙的是卖家 GID; 你拿买家号的 JWT 去写回, xAI 侧认领时对不上号, GET 永远是空. 换句话说: **货在收据里, 不在账号里**.

要把货给买家号 B, 需要两步:

1. 把 leftover 收据上的旧 GID **洗掉** (skipg4)
2. 发起一次**新的**替换, 把 B 的 GID 烙进新收据 (destg4)

## 0x01 skipg4: 空 accountId 的一跳

hook 里有个开关 `SKIP_ACCOUNT_ID`: 发 d2 时**不带** `accountId`. 这时候 Play 会把这次替换当成 "无主升级", 出一张不带 obf 的墙; Subscribe 之后, 旧 leftover 被替换成一张**没有烙任何人 GID** 的停续单 (仍然是 deferred, today $0, 订完停续).

```js
if (SKIP_ACCOUNT_ID) {
  out.accountId = '';
  out.skipAccountId = true;      // 不 putString('accountId', ...)
} else {
  ex.putString('accountId', accountId);
}
```

对已停续 (RESTORE) 的 leftover, 走 `skipg4p1m` 变体 (p1m offer + skip). 洗完后 e2 inspect: 新 GPA, `obfuscatedAccountId` 为空 — 这张单就是 "无主白条".

## 0x02 destg4: 烙买家 GID

B 的 GID 不用登 B 的 Grok app — 拿 B 的 SSO JWT 直接解:

```python
def gid_from_jwt(jwt: str) -> dict:
    # JWT payload 里 xAI 签发的 obfuscated id 就是 64-hex GID
    payload = jwt.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    data = json.loads(base64.urlsafe_b64decode(payload))
    ...
```

然后把 `FORCE_ACCOUNT_ID = <B 的 64-hex GID>` 注入 hook, 再 fire 一次替换 (`destg4`): d2 的 `accountId` 带上 B 的 GID, oldSku 是刚洗白的无主单. Subscribe → 新收据的 `obfuscatedAccountId` 就是 B. RTDN 到达后 B 的 GET 出 `grok.ultra STATUS_ACTIVE + cancelAtPeriodEnd`, 同时 A/卖家侧的旧行翻 INACTIVE — 货完成转移.

## 0x03 有人值守: 每一跳都是人在点 Subscribe

这套链路跑批时是**模块 + 人工确认**: 脚本负责 fire/判墙/截图, `GROK_HOLD_SUBSCRIBE=1` 卡在最后一步, 人看一眼墙上没有 Today 全款, 再放行点 Subscribe. 两台设备并行, 每跳换 Google, 换 dest, 换卡. 无人值守版本试过, 出过 "会出 item 的状态被误点" 的事故, 废弃.

## 0x04 踩坑

- **destg4 超时不等于失败**: Subscribe 后墙直接关回 app 首页, 脚本超时. 先等几秒 GET dest — ACTIVE 就成了, 别重跑 hop
- **旧 dest 立刻 INACTIVE**: 一跳完成后原持有人侧同步失效, 转移前想清楚
- **已 hop 过的 dest 不能再 skipg4**: 无主单再洗一次会把已交付的货打散, 直接事故
- **同一 Google 第二张卡**: Play 风控 `OR_MIVEM`, 一只 Google 只绑一张新 PAN; 两段 BIN 连续 CCREU 就换号
- **leftover 烙的是自己 GID**: 不需要 hop, 直接走上一篇的 g4 写回
- **Today $ 墙**: skipg4 出全款墙说明它按全新首购计价了, BACK, 不 Pause, 不付款

## 0x05 批量与账本

双机并行一晚上稳定 40 跳 (hop-batch-40): 每跳 = skipg4 洗白 + destg4 烙新 + GET 验证 + 入账 (dest, 来源, 时间, 状态). 账本里 dest 只记 `sold=false` 直到交付, 防止重复跳.

## 0x06 工具

脱敏代码在 GitHub: `grok-play-leftover-hop` (private, 审完后公开, 链接补在这).
`skipg4_once.py` (洗) → `destg4_once.py` (烙) → `hop.py` (编排) + `heavy_wall.js` 的 skipg4/destg4 导出.

下一篇 (x.subscription.ultra): 10 月 xAI 换 SKU 之后这套东西怎么全部推倒重来.

仅供 Play Billing 计费机制研究, 请勿用于非自有账号.
