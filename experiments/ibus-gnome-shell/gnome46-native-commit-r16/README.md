# GNOME 46 原生 Wayland 的 Shell 提交探针

这是 Ubuntu 24.04 隔离虚拟机上的研究，不是产品实现或 AppImage 验收。测试使用 GNOME Shell 私有 `Main.inputMethod.currentFocus` 和 `commit()`，不更改输入法引擎，不使用剪贴板。探针只提交固定字符「甲」，窗口及内容均由测试创建。

**仅限隔离虚拟机：**此扩展暴露没有认证的会话 D-Bus 接口，采用私有 Shell API 和简化的取消门控，不可安装到实际用户桌面，也不可用于生产。调用返回不证明目标收到字符，无法安全重放结果不确定的提交。

## 实测结果

`wayland24-shell-r17-probe.log` 为增加焦点就绪检查后的原始结果，进程退出码 0：

| 场景 | 结果 |
| --- | --- |
| 已确认 A 有输入焦点后先取消 | Send 返回拒绝，A、B、X 均为空。 |
| A 正常提交 | Send 返回成功，A 收到一个「甲」。 |
| 提交并立即取消 | 已排队字符仍进入 A；取消后的下一次 Send 被拒绝。取消无法撤回已经提交的字符。 |
| 同一 Shell 回调提交后立即切到 B | Send 返回成功且 B 获得焦点，但 A、B 均未收到该次字符。存在无接收确认的丢字窗口。 |
| XWayland GTK simple 目标 | 目标活动时 `currentFocus` 为 false，提交被拒绝。 |

初次 `wayland24-shell-r16-probe.log` 的取消前样本虽然拒绝发送，但当时 A 的输入焦点尚未就绪，不能作为有效取消对照；原件保留。r17 的取消是测试门控调用，并非物理 Esc；没有测试 Chrome、终端或普遍应用兼容性。单次受控实验不能量化发生概率。该路线不能满足跨焦点可靠连续输出，也不能据此宣称 Ubuntu 24 原生 Wayland 通用支持。

## 复现与恢复

在一次性隔离 Ubuntu 24.04 GNOME Wayland 会话中，将 `extension.js`、`metadata.json` 放入 UUID 为 `inkecho-isolated-commit-r16@local.invalid` 的用户扩展目录；将 `actor.py.txt`、`probe-r17.py.txt`、`settings.py.txt` 分别复制为 `/tmp/inkecho-shell-r16/actor.py`、`probe-r17.py`、`settings.py`。在该会话的 D-Bus 环境运行 `python3 /tmp/inkecho-shell-r16/settings.py install`，其会先备份扩展设置，然后启用测试扩展。登录后可能重新禁用用户扩展：确认后仅在隔离会话将 `disable-user-extensions` 设为 false 并启用此扩展。确认扩展 ACTIVE，再在同一会话运行 `python3 /tmp/inkecho-shell-r16/probe-r17.py`；保存 stdout 与退出码。测试脚本启动并关闭三个自有窗口。

运行 `python3 /tmp/inkecho-shell-r16/settings.py restore`，核对保存和恢复的设置完全相同；删除扩展和临时文件。若为切换到 Wayland 修改 GDM 或 AccountsService 配置，先备份，结束时按原权限恢复并逐项 `cmp`。本次恢复日志记录扩展列表 `[]`、禁用用户扩展 `true` 与原值相同，扩展为 INACTIVE；配置文件已比较一致、临时文件已删除，虚拟机正常关机，容器退出码 0。

## 原始文件 SHA-256

```text
b22f4fe3e878ce5152f8952cbaf5267b6417c2b96c9a648f1513ce4dda334cea  extension.js
f03bbee3b10dd3c62872d7f2777d8aa9b9486e7cdb21838e1a7a0049c1947f9c  metadata.json
19a155b4a43ef1bee826b4e6b7bd284132ac9c6bb16dfba586bf4da4dbd2f103  actor.py.txt
07da91d3b953157cb83275b98d285f4032f25081bf8c23ce759c3b5f41adbfd0  probe.py.txt
a8f967dc1333ef96ebcb34215f163694e9a6067e8da71757408d4e1c04baaca7  probe-r17.py.txt
d6c8dfa206f4f033b55ef7b7114dac27fb2caf081b00821d46aa8bd3ed95d995  settings.py.txt
c8f649053f1700c36963014bc7fd83e2b333a020c15a5818bab1814b1f6efbc2  wayland24-shell-r16-probe.log
539a97723ebe006f423c356032350da19d60b63dff5a5891e936213969d28039  wayland24-shell-r17-probe.log
001371b00aad58c11864c13e1c9d6029969c87b5617d33d06e0db5fea0c21792  wayland24-shell-r16-restore.log
```
