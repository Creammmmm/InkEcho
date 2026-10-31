# Ubuntu 24.04 Wayland：Fcitx 首次提交故障注入

在无外网的独立 Ubuntu 24.04 GNOME Wayland 虚拟机、自有 GTK 文本控件、临时配置和私有 Fcitx 进程上进行。录音及转写由固定数据替身提供。运行时来自 0.15.56 候选 AppImage（文件在旧夹具路径下仍命名为 `InkEcho-0.10.2-x86_64.AppImage`），在客机解包后用 8b9a28c 的源码快照覆盖 `packages/inkecho`。两处关键源码哈希及运行时文件哈希见 `receipt.json`。这不是原样 AppImage 测试，也不是双系统包验收。

测试脚本将真实 `MessageBus.call` 包装，并只注入首次 `/inkecho` 的 `Commit` 或 `CommitBatch`：

- `before.log`：在调用传输前终止私有 Fcitx，再执行该调用；目标为空，报 `fcitx_delivery_unknown`，未观察到 `KeyboardInput.insert` 调用。
- `after.log`：真实调用返回状态 `[1]` 后隐藏返回值、终止私有 Fcitx 并抛出异常；目标收到一个“风”，报 `fcitx_delivery_unknown`，未观察到 `KeyboardInput.insert` 调用。
- `aftercancel.log`：真实调用返回状态 `[1]` 后隐藏返回值，先请求 `Session.cancel()` 再终止 Fcitx；目标收到一个“风”，任务为 `cancelled`，未观察到 `KeyboardInput.insert` 调用。夹具在进程退出后等待约 1.3 秒再读取目标。

夹具只包装并记录 `KeyboardInput.insert` 调用，没有独立监听系统键盘事件。三个 `passed` 是脚本针对上述样本的断言，不是服务确认应用已处理输入的通用证明。首例并未把提交请求真正排队；后两例人为在客户端隐藏了已经收到的回复，并非网络链路中途断包。取消时已提交的文字不能撤回。这些样本不能覆盖所有断连竞态、其他客户端、Xorg 或其他系统。

`sender.py.txt`、`target-focus.py.txt` 和 `run.sh.txt` 是客机夹具，依赖先前实验的绝对路径与专用受控桌面，不应直接在用户桌面运行。前两份日志使用同一夹具的早期版本，最终保存版本仅增加 `aftercancel` 条件和相应断言；两个既有模式的注入逻辑不变。`receipt.json` 是本次从日志与执行结果整理的摘要，不是独立审计记录，材料摘要供核对。它不包含客机 SSH 凭据。

第一次从较早基盘启动时，串口显示过 `systemd-networkd-wait-online` 等待，SSH 握手超时后在未确认启动终态时人工停止；现存片段不足以确定停止时的等待时长或具体启动状态，因此不能据此认定网络配置故障。对照既往成功运行，网络等待约两分钟后会失败并继续启动；第二次使用 SHA-256 已核验的既有快照并等待，正常进入 Wayland。`first-boot-excerpt.log` 和 `second-boot-excerpt.log` 是筛选过的串口片段，非完整系统日志。

第二台客机通过电源关闭正常退出，QEMU 等待结果为 0，容器已删除。原镜像和后备链只读挂载；实验用临时目录及磁盘副本仍保存在宿主 `/var/tmp/inkecho-autofault-*`，未删除或更改宿主输入法配置。实验未使用剪贴板、真实麦克风或云端服务。
