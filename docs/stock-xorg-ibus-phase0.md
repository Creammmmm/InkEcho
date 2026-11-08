# Ubuntu 24.04 Xorg：IBus 公共接口边界与接收端保护实验

2026-11-09，阶段 0 决策记录。**目前不能把“不安装扩展、只选择 IBus 即完成
配置”作为 stock Ubuntu 24.04 的已实现能力。**现有公开接口没有同时提供跨应用
提交权限、当前输入目标绑定、活动组词保护和明确的未发送结果。私有实验已验证
一组需要修改 daemon、输入引擎及 GTK 接收模块的合同。它不是可直接随 AppImage
交付的适配，也没有改变产品路由。

## Stock 接口究竟提供什么

源码审查固定为 IBus 1.5.29 系列，使用本地 `ibus-1.5.29-rc2` 源树。桌面客机
发行版包为 `1.5.29-2`。两者不能当作逐字相同的二进制。以下链接固定到上游
[1.5.29 源码](https://github.com/ibus/ibus/tree/1.5.29)，不以主分支未来变化作为
当前系统能力。

| 接口 | 能力与本任务的边界 |
| --- | --- |
| 活动 Engine | `commit_text` 经所属 engine proxy 输出。注册自有引擎是受支持扩展点，但激活它会改变当前输入引擎。它不是第三方任意提交到现有 libpinyin 的入口，也不提供跨引擎组词事务。 |
| InputContext | `CommitText` 是发给客户端的信号，不是普通第三方可调用的提交方法。`CreateInputContext` 创建调用方自己的上下文。`FocusIn`、`SetCapabilities` 是改变状态的操作。CurrentInputContext 路径不等于跨应用授权，也不证明 GUI 焦点通知已处理。 |
| Panel / Emoji 扩展 | daemon 为特定面板服务 owner 建立代理并接收其 CommitText。不能把接管已有服务名包装成普通应用调用。既有 panel 提交不携带接收方焦点代际、组词前置条件或目标回执。 |
| IBus Portal | 为调用方创建和转发其自己的上下文，按 session-bus owner 授权。没有据此取得其他应用的上下文。portal-local 路径与 private IBus 路径不可按编号对应。 |
| XDG RemoteDesktop Portal | 是授权的键盘/输入事件途径，不是本文所需的任意 Unicode IBus 文本提交或目标接收确认。 |

具体代码见 [InputContext](https://github.com/ibus/ibus/blob/1.5.29/bus/inputcontext.c)、
[daemon 服务与面板管理](https://github.com/ibus/ibus/blob/1.5.29/bus/ibusimpl.c)、
[panel 信号处理](https://github.com/ibus/ibus/blob/1.5.29/bus/panelproxy.c)、
[引擎接口](https://github.com/ibus/ibus/blob/1.5.29/src/ibusengine.c)及
[IBus Portal](https://github.com/ibus/ibus/blob/1.5.29/portal/portal.c)。
既有 [portal 隔离客机观察](ibus-portal-owner-network-isolated-vm.md)记录了真实
owner 归属及路径不同，也保留了重复 FocusIn 断言失败。不能引用为完整通过。

### 焦点身份不是一个 PID

[GTK 客户端](https://github.com/ibus/ibus/blob/1.5.29/client/gtk2/ibusimcontext.c)
在处理 GUI 焦点事件后异步向 daemon 通知。创建上下文传客户端名称，并不公开
“该 InputContext 对应哪个 XID/控件”的绑定。
[XIM 代理](https://github.com/ibus/ibus/blob/1.5.29/client/x11/main.c)在自己的
X11IC 中保存 client/focus window，却通过共享 IBus 连接创建 `xim` 上下文。
因此 daemon 的 peer 是 `ibus-x11`，不是实际 X 窗口进程。两个直连 GTK 进程的
PID/XID 对照不能推广到 XIM，Qt/Chrome 也必须按实际选用的输入模块区分。
同进程多窗口、同窗口多控件还可能共享 PID 或 XID。

XRes 的本地 PID 可以帮助拒绝明显不匹配，不能作为安全提交的充分证明。
X server 焦点查询与 IBus/GUI 消息处理分属不同事件链。发送前重查也不构成
“未来不会再切焦点”的原子保证。因此本轮专门把最后一道拒绝放在接收端，
并明确区分拒绝、调用信号返回和回复丢失。

## 旧 panel 路径的实际反例

[Ubuntu 24.04 Xorg 旧 panel 实验](ibus-xorg-panel-focus-validation.md)已有
跟踪的脚本及合成结果。普通 Chrome 输入成功并不能覆盖切焦点。页面内切换的
样本缺失一个字符。活动 libpinyin 组词被提前触发 `compositionend`。跨窗口 GTK
样本没有充分证明其输入模块已就绪，不能把失败原因确定为一种机制。
这些限制不因安装入口简化而消失，未确认提交也不能回退重放。

## 专用 daemon / GTK 接收方法的实际证明

隔离 Ubuntu 24.04.5 / GNOME Shell 46 / Xorg / GTK 3.24.41 客机使用只读基盘、
临时写盘、私有 D-Bus/IBus 地址和两个独立进程的自有 Gtk.Entry。
legacy 组使用发行版 GTK 模块。guarded 组用仅子进程可见的 IM module cache
加载实验模块。模块映射和启动哈希均核对。daemon 与 libpinyin 为既有私有
修改版，**不能将下面结果称为 stock IBus 或任意 GTK 应用已支持**。

| 固定组件 | SHA-256 |
| --- | --- |
| 实验 daemon | `a259ed97f357d5052c572858c2730f381eff96014728afa2557158683a845419` |
| 实验 GTK3 模块 | `277940acf72a929baeb2c09fb84d2f077639b96ea8b20028c97acafa9f92581e` |
| 实验 libpinyin，引擎含空预编辑清理修正 | `1c3456092bd447833224927ce940a6ba0f8f9d90b1ab0aeaf67885c8850c7ad1` |
| 对照发行版 GTK3 模块 | `437adf4f38b355d8bfe2df7271d1edb61bd6cad77d72fb1782251184f3ce4a66` |
| daemon 相对 peer-liveness 源树的补丁 | `b302ea6ebe425b13c58d834e717785264f2888732bd81313e381861a2b9f9faf` |

### 最小专用合同

私有模式启用 `INKECHO_PRIVATE_GUARDED_WIRE=1`。原始请求者连接存活、任务序号、
取消、期限、焦点/状态代际和引擎 Prepare 检查全部保留。daemon 在接收者自己的
连接和原 InputContext 对象路径上调用独立接口
`org.inkecho.Phase0.GuardedReceiver1`，不指定其他 destination 名称。

- `Negotiate(s) -> s` 必须返回 `inkecho-gtk3-guarded-v1`。协商不发送正文。
- 协商后重验原保护与组词状态，再调用 `CommitGuarded(txs) -> s`，参数为序号、
  单调时钟期限和文字。旧接收者不得收到普通 CommitText 作为降级替代。
- 明确不支持为 `unsupported-not-sent`。接收端未调用 commit 信号的拒绝为
  `rejected-not-emitted`。信号同步返回仅记 `signal-returned`。丢回复/传输异常
  为 `unknown`，不得重放或切换输出后端补发。

GTK commit 信号没有“已插入/已显示”的布尔返回。独立目标事件可验证本次样本
确实收到文字，但不能把 `signal-returned` 本身改写为应用接收确认。

### 已观察到的合成结果（持久摘要）

以下只保存复核必要的合成内容和计数，不包含令牌、用户正文或周边文本。

| 样本 | 结果 | 独立目标观察 |
| --- | --- | --- |
| legacy seq 1，稳定 B | `unsupported-not-sent` | A/B 均空，changed 事件 0。 |
| guarded seq 2，daemon 仍指 A 而 X 焦点已到 B | `rejected-not-emitted` | A/B 均空，changed 事件 0。 |
| guarded seq 3，稳定 B，新请求 | `signal-returned` | B 为 `甲A🙂`，恰好一次 changed。 |
| B 普通输入 `ni` 后空格 | 普通 libpinyin 路径 | 预编辑出现“你”。空格后 B 为 `甲A🙂你`，预编辑清空。 |
| guarded seq 4，接收后故意不回复 | `unknown` | B 在调用尚未返回时已为 `甲A🙂你乙Ω🌙`。后缀只产生一次 changed。 |

seq 2 在真实 Negotiate 完成后的私有 400 ms 暂停内将两个 actor 停止，随后将
X 焦点移至 B。实际 `guarded-enqueued seq=2` 前后都确认 X 焦点为 B，而 daemon
仍为 A 上下文、seq 2 pending，两个 actor 仍停止。恢复 actor 后 A 记录
`allowed=0, local_focus=0, xid_match=0`。该样本没有把本地焦点检查和 XID 检查
的贡献分别隔离，也不测自然竞态发生率。

guarded 控制器只发送 `[2, 3, 4]`，未知结果没有重发。B 的 changed 值序列为
`[甲A🙂, 甲A🙂你, 甲A🙂你乙Ω🌙]`，安静观察期后不变。A 始终为空。
接收端 GObject hook 只数 retrieve-surrounding 通知，不读取参数。专用提交前后
计数为 0，但普通输入样本也是 0，因此不构成专用路径优于普通输入的实测证明。

## 同一任务的 A → B 续写验证

后续在相同系统、同一组三个冻结实验组件上分别运行 handoff、unknown、cancel。
每轮保持一个控制器 peer、一个固定期限和一个逻辑任务游标，游标以 Unicode
码点计数。该控制器是夹具，不是产品输出路由。

| 顺序 | 目标与合成片段 | 结果 | 游标 |
| --- | --- | --- | --- |
| seq 1 | A 收到 `甲A🙂` | 独立 changed 恰好一次 | 0 → 3 |
| seq 2 | X 已指 B、daemon 仍指 A，提交 `乙Ω🌙` | `rejected-not-emitted`，两端均无变化 | 3 → 3 |
| seq 3 | B 已确认聚焦，以新序号发送明确未发出的 `乙Ω🌙` | B 恰好收到一次 | 3 → 6 |
| seq 4 | B 收到 `丙Z` | B 为 `乙Ω🌙丙Z` | 6 → 8 |

seq 2 使用协商后的 400 ms 实验暂停。实际 enqueue 前后均观测到 X=B、
daemon=A、两个 actor 暂停。恢复后接收端拒绝。B 的焦点通知处理后才发送
seq 3。最终 A=`甲A🙂`，B=`乙Ω🌙丙Z`，没有回退。续写只重试明确未发送的
逻辑片段，并分配新序号，没有重放已确认或结果未知的片段。

unknown 轮令 seq 3 在实际写入 B 后丢回复。独立观察 B 已收到 `乙Ω🌙` 一次，
控制器随后得到 `unknown`，游标停在 3，没有 seq 4、重发或回退。
cancel 轮在 A 首片实际 changed 后、seq 2 发送前暂停期间取消任务，返回
`cancelled-not-sent`，没有 seq 2 enqueue。A 保留首片，B 为空，无后续尝试。
三轮精确 changed 序列断言均通过。这证明本夹具可在明确拒绝后续写、未知
结果停止、主动取消停止，不能将信号返回升级为通用应用确认。

原始报告、脚本及观察位于 `/tmp/inkecho-ibus-task24.z1txr5/`。
以该目录的 `input` 挂载到相同私有客机 `/work`，运行其 `guest-setup.sh` 后，
使用下面命令重现。它核对同一冻结组件，不使用剪贴板或键盘文字注入。

```sh
for mode in handoff unknown cancel; do
  INKECHO_PRIVATE_COMBINED_PROBE=1 TEST_VARIANT="$mode" LC_ALL=C.UTF-8 \
    timeout --kill-after=2 30 dbus-run-session -- bash /work/run-combined.sh
done
```

三轮结束后私有进程清空、客机正常关机、QEMU/容器退出 0，容器与写盘删除。
这仍不测自然竞态发生率、性能或正常桌面部署。

## 复现边界与交付决定

临时原始报告和夹具在 `/tmp/inkecho-ibus-dedicated24.daPfQG/`。C 补丁与构建
记录在 `/tmp/inkecho-guarded-daemon/`，GTK 模块补丁在
`/tmp/ibus-guarded-wire-receiver/`。这些临时目录可能消失，不是完整可分发套件。
上面的固定组件哈希、合同及观察摘要是本次持久记录。复现需要相应源补丁和
冻结组件，不能只凭系统包运行以下命令期待相同效果。

在独立 Ubuntu 24.04 Xorg 客机挂载只读夹具 `/work`、证据目录 `/mnt/output`，
执行 `guest-setup.sh` 核对会话、依赖和模块哈希，再分别新建私有 bus。

```sh
INKECHO_PRIVATE_COMBINED_PROBE=1 TEST_VARIANT=legacy LC_ALL=C.UTF-8 \
  timeout --kill-after=2 30 dbus-run-session -- bash /work/run-combined.sh
INKECHO_PRIVATE_COMBINED_PROBE=1 TEST_VARIANT=guarded LC_ALL=C.UTF-8 \
  timeout --kill-after=2 30 dbus-run-session -- bash /work/run-combined.sh
```

actor/controller 的前置检查拒绝非私有环境。GTK actor 不接收测试令牌。
停进程的 watchdog 只恢复夹具的两个子进程。首次 legacy 启动在发送前因窗口
尚未 viewable 失败，保留记录。增加 IsViewable 等待并保留同样严格焦点条件后，
最终两组通过。客机原输入源 `[('xkb', 'us')]` 和系统 IBus 未被替换。私有进程
已退出，客机正常关机，QEMU/容器返回 0，容器删除、临时写盘丢弃。

第一组的 stable seq 3 是独立新请求。同一任务续写只由后续三轮夹具证明。
两组均不证明任意多窗口、控件、Qt/Chrome/XIM、正常桌面模块发现或最终
AppImage 可用。X11 本地核查与 GTK 信号之间仍不对未来焦点变化原子化。后续设计必须保留
明确能力协商、接收端最后检查及未知不重放。需单独解决部署、授权与跨工具包
合同，不能静默替换用户现有系统组件。没有新的已验证产品路径前，保持现有
真实可用后端与明确限制，不将本阶段原型标为完整交付。
