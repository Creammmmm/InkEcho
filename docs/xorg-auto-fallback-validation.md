# Xorg 自动路由：残留扩展目录隔离验收

2026-11-09。Ubuntu 24.04.5 LTS / GNOME Shell 46.0，`loginctl` 确认 `x11`。
独立客机使用只读原始基盘和临时写盘，保持同一实例等待超过两分钟网络初始化；
没有切换或安装输入法、没有安装或启用扩展、没有操作宿主配置。

## 代码与运行时

使用旧 InkEcho 0.15.0 AppImage 的 Python/Qt 运行时，优先加载工作树
0.16.8 源码。基于提交 `b06cac73309369da1250ec80058bcfd677c53ade`，
包含未提交路由修复。这是单系统源码覆盖验证，不是旧包本身或最终包验收。

| 对象 | SHA-256 |
| --- | --- |
| 0.15.0 AppImage 运行时 | `94a73232871abaca8c91fb5f58e52059be404f10605955562d39bf31ec64354a` |
| 工作树 `app.py` | `7ff9087f6c629c5becfd291eec4f71253ff4c24cce90a90cca1b7e54d0bd531a` |
| 工作树 `platform/ibus_owned_default.py` | `040b389f6685d343f23001ef3de8f8045220ee04aa2c25736a60fd7cc1f0d01b` |
| HEAD 对照 `platform/ibus_owned_default.py` | `f4cd43742270c9d354f639ed22f971b14902ea39bfe4b887ba780e309601e80b` |

## 实际操作与结果

自建真实 GTK3 Entry，使用 stock IBus；每次确认窗口激活、输入框聚焦、内容为空，
且最近预编辑事件为空或不存在。在私有 `XDG_DATA_HOME` 创建无效 owned 扩展目录，
只放无效 `metadata.json`；真实安装探测返回 `input_capability_unknown`。
没有伪造系统探测器、输入后端或发送函数。

新代码的两个样本均调用 `Session(store=私有 ConfigStore)` 默认构造，未注入
`inputs`；确认默认 router 获得实际桌面环境且 `_xorg_session=True`。
旧代码只替换为上述 HEAD router 类，其他环境及真实键盘实现相同，不尝试补发。

| 样本 | 路由结果 | GTK 实际内容 | 结论 |
| --- | --- | --- | --- |
| HEAD 对照，拟发送“甲乙丙” | `input_capability_unknown`，无首字回调 | 空 | 残留目录错误在发送前阻断 |
| 工作树默认 Session，发送“甲乙丙” | 返回 3；首字及发送阶段 `selected=keyboard` | `甲乙丙` | Xorg 不再被原生 Wayland 扩展状态阻断 |
| 工作树默认 Session，首字回调立即取消 | `input_cancelled`；首字 `selected=keyboard` | `甲` | 剩余两字没有继续发送 |

三个样本结束均验证键盘连接关闭、输出 scope 清空、router owner 释放。
GTK 的实际变化事件和最终内容独立记录；不能只用发送返回值当作接收证明。
客机原桌面环境中 IBus 前后引擎均为 `xkb:us::eng`，实际进程是
`/usr/bin/ibus-daemon --panel disable --xim`。未测试中文输入法正在组词的情况，
不宣称此键盘回退能保护任意组词，也不宣称实现无扩展 IBus 直接提交。

## 失败记录、复现与清理

首轮脚本的三个输入样本均完成，但最后 `ibus engine` 查询仍携带私有 XDG 路径，
无法找到原 IBus bus，显示“No engine is set”并以 1 退出。随后在新的 SSH 会话，
使用原桌面环境只读查询成功，确认前后引擎一致；没有重启或切换引擎来修补结果。

临时夹具和证据保留于 `/tmp/inkecho-route-vm24`：
`input/route_probe.py`、`input/run-route.sh`、`input/target.py`、
`output/run.log`、`output/route-{old,new,cancel}.json`、
`output/route-target-{old,new,cancel}.json`、`output/session-proof.txt`、
`output/assertions.json`、`output/source.sha256` 和 `output/evidence.tar.gz`。
这些是临时证据，不是持久发布附件。复现最后的引擎查询时，应使用原桌面环境，
不能继承为实验隔离所设的 `XDG_CONFIG_HOME`/`XDG_DATA_HOME`/`XDG_CACHE_HOME`。

客机已正常 poweroff，QEMU 返回 0；专用容器 `inkecho-route-vm24` 已删除。
本轮没有修改产品源码、版本或提交，仅添加此验收记录。
