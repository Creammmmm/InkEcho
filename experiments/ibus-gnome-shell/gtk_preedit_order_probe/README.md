# 隔离 GTK 控件中 IBus 预编辑与面板提交

2026-10-29 对既有 Ubuntu 26 测试虚拟机镜像创建 `/tmp` 写时复制快照。测试容器无外部网络，原镜像只读；`loginctl` 观察到活动会话为 Wayland，客机已安装 libpinyin。测试前只读观察到输入源为 `[('xkb', 'us')]`、用户扩展列表为空、`disable-user-extensions=false`，引擎为 `xkb:us::eng`。实验使用自建 GTK 输入框与固定合成按键/字符，不读取用户正文、不访问宿主会话，也未接触剪贴板。

临时安装本目录 `metadata.json` 和 `extension.js`，初次安装后 Shell 未识别，正常重启快照后扩展成为 ACTIVE。因 GNOME 最初仍使用 xkb，引擎切换未成功；将隔离会话输入源暂设为仅 libpinyin 后，引擎查询返回 libpinyin。以 `GTK_IM_MODULE=ibus` 在会话内运行 `actor.py.txt` 的原始脚本（执行前复制去除 `.txt` 后缀；该复制步骤本身未经独立复跑）。`actor-result.log` 是第二次成功运行的原始输出，进程退出 0。初次失败是引擎仍为 xkb 时的前置断言，无发送；最初成功一轮的输出未另存。

合成 `n`、`i` 后，第一个文本框正文为空、布局显示预编辑“你”；面板提交“甲”后，正文为“甲”，布局为“甲你”；合成空格后正文为“甲你”。随后焦点切换到第二个自建窗口并提交“乙”，第二个控件收到“乙”，两次查询均显示 libpinyin。仅此顺序和自建 GTK3 控件经过测试：并未覆盖取消、发送与切焦同时发生、其他应用或输入法、Ubuntu 24、实际 AppImage 或完整输入链，也不能用同步方法返回推断目标已处理；不能据此启用自动 IBus 或宣称通用兼容。

实验后恢复前述输入源、扩展列表及禁用开关，引擎复查为 `xkb:us::eng`，扩展 D-Bus 名称无所有者，扩展目录与客机 `/tmp` 测试文件已移除；原始检查在 `restore.log`。原先的 current 输入源索引未在重启前单独记录，无法声称它逐项恢复。快照中的临时备份目录因重启清除，恢复值来自重启前输出而非备份文件。随后通过 QMP 正常关机，容器 `docker wait` 返回 0；原镜像未写入。

实测文件 SHA-256：

- `actor.py.txt`：`c7afe8730a7ec9eb1c49c9678df7e46bc9a5a3724b8ff25881509620af53f181`
- `extension.js`：`9465f5348d39ee830776ca67c0004d251a389139471fe2266557dde2290680c6`
- `metadata.json`：`558769da1c798cbc4bb859cf0a424cb2e1309ea1b9b04f6968fed0c24af0f02f`
- `actor-result.log`：`1fea36fd8eb555364d18d68355f38f399280b35e9b490b211fe0ab6bd80bdf6b`
- `restore.log`：`38460d0be1fb00e951b2db14e774055e9fa33fc956b9bd01ed0bdc0e565f2090`
