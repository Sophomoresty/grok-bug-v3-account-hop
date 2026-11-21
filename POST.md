# Grok Heavy 跨账号转移: 洗除旧 GID 并重新绑定目标账号

前两版及番外 (v1 一次 `g(4)`, v1-番外 延迟首次 sync, v2 两次 `g(4)` 自替换写回) 解决了单账号内的获取与写回问题, 但写回后的订阅受到收据 `obfuscatedAccountId` 的绑定限制, 权限始终固定在原 xAI 账号上. 当持有来自废弃账号的停续旧单 (收据中记录着原持有者的 GID), 而需要将该权益转移至另一个目标账号时, 直接替换会触发 Play 的 `"We are unable to change your subscription plan"` 拒绝.

本文记录如何定位 Play 侧的 GID 校验锁, 通过省略 `accountId` 参数洗除原持有者绑定 (`skipg4`), 再将目标账号 GID 写入新收据 (`destg4`), 以及批量半自动执行过程中的界面与风控处理规则.

## 0x00 定位 Google Play 账号校验锁

为确认校验拒绝的触发层, 针对同一张绑定着外部 GID 的停续旧单, 分别在三种 Play 购买库状态下发起了 `destg4` 替换: 本地持有已取消的 `grok.ultra`, 持有有效的 `grok.lite`, 以及完全空白的购买库. 三种环境全部返回 `"We are unable to change your subscription plan"`.

进一步的对照实验显示: 保持 proto 与 token 一致, 仅将 `extras.accountId` 替换为目标账号 GID 同样报错 `unable`; 若将 proto 的 `field2` (旧 SKU) 伪造为 `grok.pro` 搭配 `ultra` token 也会报 `unable`; 若改动 `field1` (新 SKU) 则直接触发 `DF-DFERH-01`.

由此可以确认 Play 侧的校验逻辑: `extras.accountId` 必须严格等于 `oldSku` 收据上原有的 `obfuscatedAccountId`, 与本机购买库是否为空无关; 同时服务端会交叉校验 proto 中的两个 SKU 字符串, token 所属商品与 `d2` 参数中的目标 SKU 是否一致. 权益归属记录在 Play 收据内部, 要转移权益就必须重新签发一张不含旧 GID 的收据.

## 0x01 skipg4: 省略 accountId 生成无主收据

检查 `d2` 参数构造时发现 `accountId` 并非必传项. 在发起 `grok.ultra` 自替换时如果跳过 `putString('accountId', ...)` 调用, Play 依然会受理该替换请求:

```js
if (SKIP_ACCOUNT_ID) {
  out.accountId = '';
  out.skipAccountId = true;   // 跳过 ex.putString('accountId', ...)
} else {
  ex.putString('accountId', accountId);
}
```

支付弹窗出现后依然是不含 `Today` 扣款行的纯延期墙. 完成一次 Subscribe 后通过 `e2` (`getPurchases`) 读取购买库, 可以看到旧单已被替换为一张全新的 `GPA` 订单, 且 JSON 中 `obfuscatedAccountId` 字段完全缺失 (并非空字符串), 即成为一张无主凭据. 随后取消续订将其重新转为停续状态, 这一跳的实付同样为 `$0`.

执行该步骤需注意两个约束: 当原收据的 `subscriptionClientActions` 为 `RESTORE` 时, offer 选择需按先 `p3m` 后 `p1m` 的顺序尝试 (`p1m` 在部分场景会报 `unable`); 此外一张旧单只能对应一次转移, `skipg4` 会覆盖并清除前任持有者的绑定关系, 因此脚本在 `inspect` 阶段一旦检测到 `obfuscatedAccountId` 为空, 会直接拒绝再次执行 `skipg4`, 防止误洗已交付账号.

## 0x02 destg4: 解析目标 GID 并完成绑定

洗除旧 GID 后, 下一步是将目标账号 (B 号) 的 GID 写入新收据.

目标账号的 GID 无需在设备上登录 Grok App 获取, 可直接通过 B 号的 SSO JWT 解析或带着 cookie 调用 gRPC `GetGoogleObfuscatedId` 取得. 经校准比对, 该接口返回的 64 位 hex 字符串与 Play 收据 JSON 中的 `obfuscatedAccountId` 逐字节相等, 无法通过 `userId` 或邮箱的本地哈希推导.

将提取出的 B 号 64 位 GID 注入 `FORCE_ACCOUNT_ID`, 对着刚洗白的停续无主单再次发起 `grok.ultra` 自替换. Subscribe 成交后, 新生成的 Play 收据即绑定了 B 号的 GID. 待 RTDN 通知落地 (干净环境下约 3 秒建行), B 号在 xAI 侧的查询结果变为 `grok.ultra STATUS_ACTIVE + cancelAtPeriodEnd`, 原持有者 A 号的同款记录同步翻转为 `INACTIVE`, 权限转移完成.

## 0x03 半自动运行中的界面与风控处理

9 月中旬将该流程投入多机并行时, 全自动无人值守方案曾因系统弹窗样式异常出现过误点其他订阅项的事故, 随后全部废弃, 改为模块配合人工确认的模式: 脚本自动完成参数注入, 等待弹窗与 OCR 识别, 并在最后一步通过 `GROK_HOLD_SUBSCRIBE=1` 挂起, 确认画面中不存在 `Today` 全款扣费后再放行点击.

实际运行中积累了以下几类界面与环境异常处理规则:

**1. 密码页 `FLAG_SECURE` 与坐标漂移**: Google 验证页开启 `FLAG_SECURE` 后, `uiautomator dump` 通常仅能抓到 `Verify` 与 `Remember me` 两个节点, 其中 `Verify` 的纵坐标在 `1760` 至 `1785` 之间波动, 固定点击 `1836` 会误触下方输入法键盘. 脚本规则修正为: 若 dump 存在中心点则按实际 `cy` 点击; 若 dump 超时且 OCR 仅识别到 `"ADB Keyboard {ON}"`, 也视作密码页处理, 填密后点击 `y=1760`; 若遇到 `"No internet"` 则重复点击 Verify.

**2. OCR 截断导致的误分类**: 针对 `"Starting Oct ... $299"` 弹窗, 曾出现 OCR 遗漏底部 `"Your first charge will occur on Oct 18"` 行的情况, 导致分类器因缺失首扣行而误判为 `CHARGE_FULL`. 规则调整为必须在识别到完整的 `first charge` 或 `Today $` 特征行后才允许输出分类结果.

**3. 订阅列表加载卡顿**: 切换账号后打开 Play 订阅页, 首帧经常停留在五边形加载动画超过 6 秒. 遇到该情况不采用等待或 `pm clear` 清数据, 而是执行一次 `am force-stop com.android.vending` 后重开页面, 8 秒内即可正常渲染 `Canceled Heavy` 详情.

**4. 附加推广弹窗与备份提示**: 绑卡超时出现的 `"Introducing Google Play Points"` 开屏页无法通过节点树定位 `Not now`, 需在 OCR 识别标题后固定点击 `(540, 1509)`, 避开旁边的 `(293, 1836)` 暂停按钮. 换单后的 `"Want to add this backup payment method?"` 固定选择 `No thanks`, `"Turn on backup payment methods?"` 固定执行 `BACK` 退出, 避免改变单据状态.

**5. `destg4` 超时后的假失败处理**: 部分设备在 `destg4` 点击 Subscribe 后支付弹窗直接关闭并退回 Grok 首页 (`"Ask anything"`), 导致等待确认页的脚本超时. 实际上退回首页通常意味着下单已完成, 脚本遇到超时应立刻查询目标账号的 `GET` 状态, 若已 `ACTIVE` 则直接结束本轮, 不得重跑 `hop`.

**6. 账号同步与支付卡风控**: 切换 Google 账号后 Play 本地的 `library.db` 可能残留上一账号的购买缓存, 需先同步列表再比对 `purchaseToken` 前 8 位. 目标账号 JWT 入库前必须执行去重检查, 防止不同账号混用同一 cookie. 卡控方面遵循一号一卡原则: 同一个 Google 账号绑定第二张卡会触发 `OR_MIVEM`; 遇到 `OR_CCREU` 换卡, 连续两段 BIN 被拒则更换 Google 账号; 遇到发卡行硬拒 `OR-PFGVEM` 不再对同一 PAN 重试; 换卡后依然出现 `OR-HDT-16` 说明当前 Google 账号已被风控废置, 直接弃用.

## 0x04 批量执行情况与工具仓库

9 月 4 日使用单张旧单连续完成了 4 次跨账号转移, 当天全程实付 `$0`; 至 9 月 12 日, 40 单规模的转移批次队列全部清空. 账本严格记录来源, 目标与交付状态, 交付前保持 `sold=false`, 已标记售出的目标账号禁止撤回或复用.

脱敏代码位于 GitHub 仓库 `grok-bug-v3-account-hop` (目前为 private), 包含洗白脚本 `skipg4_once.py`, 绑定脚本 `destg4_once.py`, 编排入口 `hop.py`, 对应 Frida hook 以及值守检查文档 `docs/dual-attended-hop.md`.

10 月份 xAI 切换了整套订阅 SKU 体系, 上述三条链路随旧 SKU 一起失效. 下一篇将介绍如何在新 SKU 上重建 `mode 3`, 以及 10 月份的封堵与反制细节.

_本文略去了具体账号与支付卡信息, 仅用于 Google Play Billing 计费机制研究, 请勿用于非自有账号._
