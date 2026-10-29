# 私有 IBus 面板提交与 libpinyin 预编辑

在独立私有 session bus、IBus daemon 和临时 HOME 中启动内存配置及 libpinyin，仅在此私有实例选择该引擎。自建 IBus 上下文接收事件，合成按键 `n`、`i` 触发预编辑，再由私有面板提交固定合成字，最后合成空格。只记录事件类型和 preedit 可见布尔值，不读取事件文字或用户正文；无真实桌面、用户输入法或用户会话参与。

运行 `bash experiments/ibus-gnome-shell/panel_preedit_probe/run.sh`，需要 IBus、libpinyin、PyGObject 和 Unix socket 权限。进程及临时目录结束时清理。

2026-10-28 Ubuntu 26.04.1 / IBus 1.5.34-rc2：合成 `n`、`i` 后收到两次 visible preedit、无 commit；面板提交之后收到一次 commit、无额外 preedit 更新；合成空格又收到一次 commit；私有全局引擎仍为 libpinyin。脚本退出 0，Ruff 通过。过程中出现缺省临时配置与 Lua 文件缺失提示及 GI `g_object_is_floating` 警告。SHA-256：`probe.py` `45d30c0c0ebbc5110b7a888404cfb5f975f970a50b26adfd79a04d1bd7706709`，`run.sh` `a075c81cbfa4b654eea804189b91a25d98c794b3b72d960d8274586915daf2a0`。

这是对不切换引擎的一条正向协议级证据：该合成场景下面板提交后 libpinyin 仍可响应空格并生成 commit。没有检查实际文本内容、排列、候选词正确性或显示，也没有真实控件、切窗、其他引擎、其他版本或用户组合输入，不能据此声明完整保持预编辑、真实应用接收或安全自动选路。面板提交仍无目标处理确认，不能对不确定结果重放。
