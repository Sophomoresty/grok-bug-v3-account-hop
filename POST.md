# leftover 搬家: 洗掉旧 GID 再烙新号, 把 Heavy 在账号间转移的实录

前两篇解决了 "写回", 但写回去的 `obfuscatedAccountId` 是收据上烙的那个 GID--货永远绑在那只号上. 批量做起来之后这是死结: 手上的 leftover 池是弃号(GID 是别人的), 要交付的买家号是另一只. 直接对买家号发起替换, Play 一句 "We are unable to change your subscription plan" 顶回来. 这篇讲怎么把旧 GID 洗掉, 把买家的 GID 烙进去, 以及为了把这件事跑成产线, 值守同学踩过的所有坐标级坑. 文里略去了具体账号和卡信息.

## 0x00 unable 三连: Play 的锁在哪

先定位锁. 同一只烙着外号 GID 的 leftover, 换了三种库状态打 destg4: canceled ultra 库, 活 lite 库, 空 library--**全部 unable**. 对照组合里 proto 对齐, token 真实, 只有 accountId 换成 dest GID 时也 unable. 结论收窄成一句:

> Play 锁: extras.accountId 必须 == oldSku 收据上的 obfuscatedAccountId, 与本机 library 空不空无关.

再补一刀: proto 的 field2(旧 sku)写 grok.pro 配 ultra 的 token → unable; field1(新 sku)写错 → DF-DFERH-01. Play 同时校验 proto 两个 sku 字符串, token 的 productId, d2 的 sku 三者一致.**货在收据里, 不在账号里**--要让货换主人, 得让收据换 GID.

## 0x01 skipg4: 空 accountId 的一跳

观察 d2 extras 的构造时注意到一个自由度: `accountId` 这个 extra 是**可写可不写**的. 不写它发起替换, Play 会把这次当成 "无主升级":

```js
if (SKIP_ACCOUNT_ID) {
  out.accountId = '';
  out.skipAccountId = true;   // 干脆不 putString('accountId', ...)
} else {
  ex.putString('accountId', accountId);
}
```

墙出来还是那张 deferred 墙(无 Today, first charge 在周期末), Subscribe 之后旧 leftover 被替换成一张**没烙任何人 GID** 的停续单--"无主白条". e2 inspect 验证: 新 GPA, `obfuscatedAccountId` 字段整个不存在(不是空串). RESTORE 型 leftover 记得先 p3m 后 p1m 地试 offer(p1m 有时 unable, p3m 过). 这一跳也是 $0: deferred + 停续.

洗的代价要想清楚: 1 leftover = 1 dest. skipg4 会把旧持有人的账期洗掉, 已经交付的号绝对不能再洗, 脚本里 inspect 到空 obf 直接拒绝 fire.

## 0x02 destg4: 从 JWT 里解买家 GID

买家(dest)的 GID 不需要登录买家的 Grok app--拿 dest 的 SSO JWT 直接解 payload 就有. 这个 GID 的形状经过校准: gRPC `GetGoogleObfuscatedId` 返回的 64-hex, 与 Play 收据 JSON 里 `obfuscatedAccountId` 的 64 字符 run **逐字节相等**; 反过来说拿 userId, 邮箱, 任何本地哈希去凑都凑不出来(都试过).

把 `FORCE_ACCOUNT_ID = <dest 64-hex>` 注入 hook 再 fire 一次替换(oldSku 是刚洗白的无主单, old=new=ultra), Subscribe → 新收据的 obf 就是 dest. RTDN 落地后 dest GET 出 `grok.ultra STATUS_ACTIVE + cancelAtPeriodEnd`, 旧持有人的同款行翻 INACTIVE--转移完成. 一跳的落库间隔实测 3 秒量级, 但别急着判, 见下一节.

## 0x03 值守实录: 产线上的坐标级坑

这套链路跑批是**模块 + 人工确认**: 脚本管 fire/判墙/截图, `GROK_HOLD_SUBSCRIBE=1` 卡在最后一步, 人看过墙上没有 Today 全款才放行. 无人值守版本试过, 出过 "已知会出 item 的状态被误点" 的事故, 直接废弃. 值守日志里挖出来的坑, 每一条都是真机撞出来的:

- **密码页的三态坐标**: FLAG_SECURE 下密码页的 dump 经常只有 Verify + Remember me 两个节点. Verify 按钮的 y 坐标在 1760~1785 之间漂--有一次按肌肉记忆点了 1836, 点到的其实是输入法. 后来规则改成: dump 里 cy=1785 按 1785; dump 超时且 OCR 只剩 "ADB Keyboard {ON}" 也当密码页, 填完再按 1760; 打完密码别 break, "No internet" 就再按一次 Verify.
- **OCR 截断的假全款墙**: 一张 "Starting Oct $299" 的墙, OCR 把 "Your first charge will occur on Oct 18" 那行截了, 分类器看不到 first-charge 行就判 CHARGE_FULL. 规则改成: 这种墙必须等到 first-charge 或 Today $ 行出现才准分类.
- **订阅列表转圈**: Play 订阅页第一帧转圈, 等 6 秒还是五边形动画. 别干等也别 pm clear--`am force-stop com.android.vending` 一次重开, 8 秒内就是 Canceled Heavy 详情.
- **Play Points 开屏**: 绑卡超时页是 "Introducing Google Play Points", dump 里没有 Not now 节点. OCR 到标题就点 Not now(540,1509); 隔壁那个 293,1836 会点到 Pause, 禁止.
- **backup 弹窗**: "Want to add this backup payment method?" 一律 No thanks; "Turn on backup payment methods?" 一律 BACK. Turn on 一次都会改变单据形态.
- **destg4 超时 ≠ 失败**: Subscribe 之后墙直接关回 Grok 首页("Ask anything"), 脚本等到超时. 其实这时候已经成了--立刻 GET dest, ACTIVE 就收工, 别再 dump 45 秒, 更别重跑 hop.
- **串号检测**: 写 dest JWT 进池之前必须先查同 JWT 是否已被别的号持有. 真出过一次: A 号拿到了 B 号的 cookie. 一条 SQL 的事, 但漏了就是交付事故.
- **library 同步**: 换 Google 后 Play 的 library.db 还是上一号的购买列表, 此时 inspect 到的行是旧号的, 不要当 mismatch, 跑一次 sync 再对 purchaseToken 前 8 位.

## 0x04 卡与风控

- 同一只 Google 第二张卡 → `OR_MIVEM`, 一号一 PAN 是铁律; 拒付换卡用 `OR_CCREU`, 两段 BIN 连续拒就换号.
- 发卡行硬拒 `OR-PFGVEM`: 换卡, 不对同一 PAN 再 Subscribe.
- `OR-HDT-16` 换卡仍出现: 这只 Google 废了, 换号.
- Play "No internet": 模拟器 DNS/代理的事, 修出口再 fire, 跟账号无关.

## 0x05 批量账本

双机并行, 每跳换 Google, 换 dest, 换卡, 换工作目录, 不同 env 连跑. 09-04 同一只 leftover 连跳四只 dest 全天 $0; 到 09-12 收口, hop-batch-40 记 done 40, 队列清空. 账本只记 dest/来源/时间/状态, `sold=false` 直到真正交付, 已 sold 的 dest 禁止 unmark--重复跳一只已交付的号就是把别人的货洗掉.

## 0x06 工具

脱敏代码在 GitHub: `grok-play-leftover-hop`(private, 审完后公开, 链接补在这).
`skipg4_once.py`(洗)→ `destg4_once.py`(烙)→ `hop.py`(编排)+ `heavy_wall.js` 的 skipg4/destg4 导出 + `docs/dual-attended-hop.md`(值守闸门全表).

下一篇(x.subscription.ultra): 10 月 xAI 换 SKU 之后, 这整套东西怎么一夜作废, 又怎么重来的.

_文里略去了具体账号和卡信息. 仅供 Play Billing 计费机制研究, 请勿用于非自有账号._
