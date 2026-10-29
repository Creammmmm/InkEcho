# Ubuntu24 GTK4/Fcitx 焦点恢复对照

日期：2026-10-30。源码身份 d1f4f73694577984defb23c656a13bc98927f7cd / 0.10.6；既有93文件校验副本。不代表当前 AppImage 或全部 GTK4 兼容性。

## 实际结果

隔离 Ubuntu24.04.5 / GNOME46 原生 Wayland，Fcitx5.1.7；复用校验过的官方 GTK4 frontend 5.1.1-1build2 缓存包，无下载。真实 GNOME Text Editor46.3 在空编辑控件中，AT-SPI EDITABLE/SENSITIVE/SHOWING/FOCUSED 为真。初始四个 Fcitx contexts 的 focus 全0；对已核对的自有窗口发送一个普通受控按键后，控件字符数0→1，唯一context变focus1。系统会话真实设置正常 Fcitx hints 后，实际 DefaultAutoOutputRouter 选择 fcitx、返回4、无handoff，控件字符数1→5。AT-SPI 同一窗口出现两份相同可访问对象，两个计数相同，不当作两个接收目标或两倍字符。

最小自有 GTK4 TextView 在真实窗口激活后初始已有一个 Fcitx focus1，说明不是所有 GTK4 均无法提供焦点。该样本后续 VNC 点击造成实际失焦，普通键没有进入目标，因此该点击部分无效，不能作为输入兼容结论。

## 解释及安全限制

官方 Fcitx5.1.7 DBus frontend 的 ProcessKeyEvent/ProcessKeyEventBatch 会在已验证客户端的真实键事件到来时将其 context 置为焦点，吻合普通按键后恢复。此结果消除了“控件不可编辑”的猜测，并证明既有项目路径在真实焦点建立后可用，但尚未证明初始 FocusIn 丢失/随后 FocusOut 的准确来源；不能称底层 GTK4 缺陷已修复。

不能按 PID/program 或最近 context 强制选择；一个进程的四个 contexts 不足以确定控件。不能伪造客户端 FocusIn，也不能发送文字后删除来唤醒，更不能重放未确认正文。

关于无文字的真实键触发：当前尚无已证明通用安全的键。Shift/Control/Alt 等会改变组合状态，可能切换输入法模式、触发单键快捷键或辅助功能；F13–F24 可被应用或全局绑定；方向键等改变光标/选择；释放事件可能破坏用户仍按住的组合。VoidSymbol/未知键即使不产生字符，也可能在到达输入模块前被丢弃，或被应用键处理器接受，未实测就不能宣称可安全恢复。官方 force-focus 只证明已到达的合法客户端键事件有该效果，不证明任意无文字探测事件无副作用。现阶段不加入自动唤醒键。

## 实验失败和环境恢复

原网络启动失败、临时 GRUB 编辑错到 initrd 的失败都保留，未覆盖旧记录。最终复测没有使用修改过的 GRUB；等待原启动网络超时进入自有桌面后，仅在客机内重应用既有 netplan，恢复 enp0s4/10.0.2.15。只读父盘、宿主显示/输入法/系统配置未变。

fixture 曾因 enable 提前 D-Bus 激活 Fcitx 导致重复实例冲突，以及客机仍安装旧测试扩展而缺 PID 方法；保留旧脚本/文件后修正实验顺序和自有扩展，不是产品修改。首轮系统会话 hints 未更新导致 keyboard/session_closed，不作为产品失败；正常 hints 的新样本才验证真实默认 Fcitx 路由。

恢复扩展列表、全局扩展开关、GDM、会话 hints；移除本轮 GTK4 frontend，桥已停用，无测试进程残留。清理首次重复 disable 因桥已停用报错，后续核实配置确已不存在并完成剩余清理。客机 sudo systemctl poweroff，原 docker wait=0，最终 Running=false/Pid0/Exit0/OOMfalse。所有原始记录归档，仅本报告/计数进入补丁，不记录输入正文。

## 官方源码

- https://github.com/fcitx/fcitx5/blob/5.1.7/src/frontend/dbusfrontend/dbusfrontend.cpp （客户端身份检查、300–310/479–491 键事件焦点恢复）
- https://github.com/fcitx/fcitx5-gtk/blob/5.1.1/gtk4/fcitximcontext.cpp （焦点与重连）
- https://github.com/GNOME/gtk/blob/4.14.5/gtk/gtktextview.c （5397–5431 可编辑控件 IM 焦点）
