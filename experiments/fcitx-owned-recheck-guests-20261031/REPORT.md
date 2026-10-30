# Fcitx 到 owned IBus 交接：双客机源码覆盖实验

2026-10-31 在隔离客机顺序执行：Ubuntu 24.04 GNOME Wayland 与 Ubuntu 26.04 GNOME Wayland。两者使用同一 0.15.0 AppImage（SHA-256 `94a73232871abaca8c91fb5f58e52059be404f10605955562d39bf31ec64354a`）提供解释器及依赖，使用 `git archive` 提取提交 `f730922` 的 InkEcho Python 源码并置于包依赖之前；运行时仅由启动器验证 `ibus_owned_default.py` 的哈希；实验结束后分别将两份源码副本与提交 `f730922` 的 94 项逐文件比对，未发现缺失、多余或内容不一致。该路由文件 SHA-256 `668a90ed479aaad85cc355f7c2b91f9dcac7fc7df926734590cc6fb0257e2ba4`。客机中临时安装该提交的 owned 扩展资产，GNOME 重载使其 ACTIVE，并以原包中固定的 Fcitx 插件运行真实服务。实验为源码与扩展覆盖，**不是 0.15.28 AppImage 验收**。报告的桌面环境来自用户服务管理器；没有单独保存本轮 logind 图形会话状态。

实际默认路由使用真实 Fcitx 检测、真实 owned Probe、真实桥连接和自有原生 GTK Wayland 控件。两系统正常样本中，Fcitx 返回 `no_target`、accepted=0 且 uncertain=false；随后 owned 交接，控件观察到固定测试字“甲”，调用结束报告 `ibus_delivery_unknown`，这不是通用客户端确认。在另一样本，测试子类先等待真实 Fcitx `aclose()` 完成，然后在子类的 `aclose()` 返回前实际调用 GNOME 扩展停用；新路由返回 `input_capability_unknown`，0.8 秒后同一自有控件仍只有“甲”，没有第二个测试字。该控制动作发生在真实清理完成之后、路由恢复之前，并非在关闭内部任意时刻的测试。未证明所有取消、状态变化或服务 owner 切换竞态均安全；检查和发送仍不具原子性。

24 首轮及手动启动 IBus 后的第二轮，真实 Fcitx 检测成功、自有 GTK 控件获得焦点，但 owned Probe 返回无目标，均在发字前停止；原始失败记录保留。随后在隔离客机启动 IBus、选择已安装的 libpinyin，并仅对测试 Fcitx 禁用其 `ibusfrontend` 兼容前端后，使用修改后的 24 测试脚本得到上述正常与停用样本。26 使用默认原生控件条件；不能据此认定 24 失败的唯一原因，也不能推广到所有输入法配置。

26 的启动器、探针及控件脚本 SHA-256 分别为 `aadcde12fc7542b848d11109c8d7f4951eed308911c4ebef0bc6b0e7b37e24b6`、`cc0bebb5daaf028ba4596a4032dcaa76e52e5ddd03652d2209a97b3d4ad0f217`、`2ca8f0896a9eb729a48a8c86c1168630ede8711a1743743591aa0953436ef041`；24 最终启动器、探针、控件分别为 `e4cbcf37e43bce02863311446c17f3ed6be84a4e32e7be0d44a0b3d31bdc9497`、`e469a5589894d4a722e41aeb58858254451f7f218a3ea76a84cbeca2c02b3997`、`2ca8f0896a9eb729a48a8c86c1168630ede8711a1743743591aa0953436ef041`。最终 26 与 24 原始结果日志 SHA-256 分别为 `aab344a9dbdea821e0f8d34d3d7faf71eff6d7fe333bbda6af2a698517fa7688`、`c1fad4000ce4e6353199da303f7495d42cc32560e8705d122148526d7eea652d`。24 两次失败日志哈希为 `4ae3bca308e9aff62eb6bfdd56efdcb865e9964b883714a397595430a9827154`、`72ddcfc9a0e275316476fd496b439b8642e1ce6567dff041764969cfca4cb5b2`。实验脚本和日志留在本地 `dist/fcitx-owned-recheck-guests-20261031/`；本摘要不含客机原始归档、SSH 密钥、云初始化数据或内部地址。

两客机测试结束恢复原 owned 资产和设置、移除 Fcitx 插件描述与临时目标目录、卸载 AppImage；24 的清理复合命令包含恢复原输入源、核对恢复值及向本次启动的 IBus 进程发送退出信号，但未单独保存恢复后的输入源值、信号结果或独立进程退出记录；现有本地材料不足以独立核验这两项。客机 QEMU 与容器均退出 0、未 OOM，停止快照完整流校验通过。24 依据客机串口生成公钥进行严格 SSH 校验，连接命令及其独立退出记录未单独归档，本地材料不足以独立核验该连接过程。

未验证实际录音、云转写、完整 Session、真实拼音预编辑、实际跨窗口切换、owner 切换、其他桌面/输入框或两系统的正式包；不得扩大兼容范围或用于发布验收。
