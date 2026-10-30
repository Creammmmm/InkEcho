# Ubuntu 24 GNOME Wayland 中 XWayland Fcitx 实测

2026-10-30 在隔离 Ubuntu 24.04.5 / GNOME 46 Wayland 客机，Fcitx 5.1.7、拼音 5.1.3，使用 FUSE 挂载的 0.15.0 AppImage（SHA-256 `94a73232871abaca8c91fb5f58e52059be404f10605955562d39bf31ec64354a`，提交 `76aeb33`）和包内插件（SHA-256 `f67c6b5f2cb7ecd7c915c8062efd3b70284c74b97ced4a597d942c4b39594e44`），由安装器安装插件，未改产品。测试使用自有 GTK3 XWayland 控件，确认 GdkX11Display、活动窗口、焦点、加载 Fcitx GTK 前端；会话提示仅临时设置并恢复，QMP 虚拟键盘形成真实拼音，不使用剪贴板。

独立 router 正常样本 auto 选择 fcitx 并收到“甲乙”；真实拼音 `ni` 的预编辑长度为 2 时，语音输出返回 `fcitx_composition_active` 且尝试数 0，控件文字和预编辑未变，用户模拟按空格后上屏“你”。随后在发送首字后取消，返回 `fcitx_cancelled`，已确认尝试 1 次，只收到前缀“己”；约 1.2 秒观察无追加。此项仅是 router 样本，不是活动预编辑下完整 Session。

完整 Session 使用虚拟音频和本地模拟识别、润色服务，auto 选择 fcitx；录音期间切换至自有第二 GTK3 XWayland TextView，正常样本准确接收 22 码点，旧控件为空。取消样本在首字符出现时触发，触发时接收 1 码点，最终收到 2 码点“你好”；第二字可能已在途。Session 进程退出后的 1.3 秒观察窗口无追加。此受控样本不能保证其他取消竞态或跨应用行为。

准备阶段最初客机网络无地址且 SSH 超时，两次过早在约两分钟启动等待前结束，后一次等待结束仍无法连接；独立 cloud-init 地址实验也未成功。最终独立 NoCloud DHCP 配置使客机联通，但新实例重新生成 SSH 主机密钥，依据客机串口公钥及指纹核验后严格校验连接；相关尝试与新配置均在归档中。功能首轮真实 router 和正常完整 Session 通过，但取消后 9p 状态文件短读导致测试夹具 JSON 解析失败；保留该轮结果，给夹具读取增加短读重试后整轮通过。测试后的 Fcitx 退出、会话提示恢复、FUSE 卸载；QEMU 和容器退出 0、无 OOM；容器状态由 `docker inspect inkecho-fcitx-xwayland24-retry4 --format {{json .State}}` 在容器停止后采集，并存入字节归档；停止快照完整解码校验，外部保留在 `dist/fcitx-xwayland-24-audit-20261030/retry4/output/stopped-followup-child.qcow2.gz`，SHA-256 `825b8551875e6374355a7f1b636fbcb3e66babee7dde87245f89984fd93b5194`。音频认证 cookie 等私有认证文件未收录。

`raw-byte-archive.json` 保存原始日志、脚本、命令、包审计及各轮记录，每项有大小与 SHA-256；不包含完整虚拟机或私有凭据。此结果不覆盖真实麦克风和云服务、活动拼音下完整 Session、其他应用、跨后端切换及任意取消竞态，不能据此宣称全部平台组合通过。
