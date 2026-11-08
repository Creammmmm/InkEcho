# Ubuntu 24.04 Xorg 设置页源码覆盖验收


2026-11-09，在独立 Ubuntu 24.04.5 / GNOME Shell 46.0 客机执行。
`loginctl` 确认真实会话为 `x11`，Qt 实际平台为 `xcb`，不是 offscreen。
复用 0.15.0 AppImage 的 Python/Qt 运行时（SHA-256：
`94a73232871abaca8c91fb5f58e52059be404f10605955562d39bf31ec64354a`），
优先加载当前工作树 0.16.8 源码（基于提交 `b06cac7`，包含未提交改动）。
实际载入的 `ui/information.py` SHA-256 为
`849de477a886ba7fc65d0f7bd1cb72943cdf1f60e9e961ef3282cbda48969c9b`。

对 `auto`、`ibus`、`ibus-owned` 三组全新私有配置分别打开真实兼容性页面：
旧选择保留；打开前后配置字节与修改时间不变；默认等待值为 40 ms；
不构造 IBus 扩展管理器，也不显示其安装、启用和卸载按钮。
使用客机 `xdotool` 向已聚焦的等待值控件实际键入 80，验证文件自动保存，
关闭并重新构造页面后仍为 80，原输出选择不变。共 24 项断言通过。
Fcitx5 输入桥控件仍保留。已检查页面截图，文字清晰，完整页面没有裁切。

临时证据：[报告与复现说明](/tmp/inkecho-ui-vm24/output/README.md)、
[原始结果](/tmp/inkecho-ui-vm24/output/ui-proof/report.json)、
[旧 IBus 页面截图](/tmp/inkecho-ui-vm24/output/ui-proof/ibus-visible.png)、
[新版 IBus 配置的完整页面](/tmp/inkecho-ui-vm24/output/ui-proof/ibus-owned-page.png)。
这些 `/tmp` 文件不是持久发布附件。夹具的输入后端对象未连接实际服务；
本次不验证授权、实际文字输出、音频或云端功能，也不表示无扩展 IBus 已可用。
这是单系统、源码覆盖的页面验收，不能作为旧包本身、最终候选包或双系统发布验收。

测试只使用只读基盘上的临时子盘及私有配置，未操作本机用户输入法配置。
首次基盘启动因过早结束而未完成；另一次历史快照因 backing 链不匹配放弃，
均不计为验收结果。最终使用已知基盘等待超过两分钟后完成测试。
客机已正常关机，QEMU 返回 0；专用容器 `inkecho-ui-vm24` 已移除，
临时测试报告、截图及复现夹具保留在上述目录。

本提交仅将上述已验收的页面与测试整理入独立分支；页面源码哈希保持一致。
开发版本由 0.16.9 递增至 0.16.10，不代表生成或发布了新包。
