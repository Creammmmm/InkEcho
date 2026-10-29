# IBus 面板转发按键隔离对照

考察 `PanelService.forward_process_key_event` 是否可作为不替换引擎的透明文字桥。在独立 D-Bus 会话、临时 HOME 和私有 IBus daemon 中启动临时内存配置与 libpinyin，在自建上下文设置焦点，仅发送自造按键 `n`；只统计 preedit/commit 事件名，不读取事件文本，也不访问用户会话、用户输入法或用户正文。

运行 `bash experiments/ibus-gnome-shell/forward_key_probe/run.sh`，需要本机 IBus、libpinyin、PyGObject 及创建 Unix socket 的权限。实验结束清理进程与临时目录。

2026-10-28 最终脚本运行退出 0：全局引擎为私有 libpinyin，初始事件 `[preedit]`，转发合成按键后为 `[preedit, preedit]`，新事件为 preedit 而非 commit。运行时出现缺省临时配置文件、Lua 脚本缺失和 GLib `g_object_is_floating` 提示。两个运行均观察到相同事件顺序。脚本 SHA-256：`probe.py` 为 `fdf1ba97e15618c75674d0b6241ba37abdd4cc34c65f9db384f6aec248fe9210`，`run.sh` 为 `a075c81cbfa4b654eea804189b91a25d98c794b3b72d960d8274586915daf2a0`。

该实验表明此具体 libpinyin 情况下转发按键会引起引擎预编辑事件，而不是直接提交指定文字；不能将其当作通用透明字符串提交。不证明所有引擎或所有键都相同，也不证明预编辑的具体内容或改变已有组合输入的具体效果。这里没有实际控件或端到端送达确认，亦未解决焦点关联问题。
