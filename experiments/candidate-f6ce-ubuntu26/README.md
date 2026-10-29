# Ubuntu 26.04 候选包定向桌面验收

同一候选 AppImage SHA-256 `f6ceb6311069f85b180bafd446f546247b5e592735ba26035455a571c5eb5164`，在 Ubuntu 26.04 的独立 QEMU `-snapshot` 客机分别以 GNOME 原生 Wayland 和 XFCE X11 执行。原有系统盘及基础镜像只读挂载，XFCE 会话配置仅在临时写层更改；未覆盖 AppImage 中源码。目标是自建 GTK3 输入控件与私有 Fcitx5，转写为固定合成结果，非真实麦克风或云服务。

每个桌面测试自动 Fcitx、手动 Fcitx 的正常及取消，和 simple 输入控件的零前缀键盘回退。两桌面中，自动与手动 Fcitx 正常样本各精确输出 200 字、取消样本各保留 1 字后结束；simple 下 Fcitx 返回 no_target、accepted=0、offset=0、uncertain=false，转键盘后各准确输出 200 字并 succeeded。Wayland 原脚本将回退标记 `passed=false`：旧断言仅检查 X11 KeyboardInput.insert，未识别原生 Wayland 输入；原日志仍显示 hybrid_connect、hybrid_authorize、200 字及 succeeded。该脚本故障没有被改写为通过。X11 通过 logind 检查 Type=x11，Wayland 为 Type=wayland，测试时均为 active 且非锁定。

X11 会话中候选包 `--appimage-mount` 获得挂载目录并找到 AppRun；该结果确认 FUSE 挂载，不单独证明图形应用成功启动。退出时未观察到 appimage 挂载或私有 Fcitx 进程；账户会话配置从临时备份恢复为 ubuntu，输入环境恢复 ibus，客机容器退出 0 并已删除。原始快照盘未以可写方式挂载。

`wayland.log` SHA-256 `40ac69114ff7e8b0ac2edef0815e22684998928a2cd554a6a7add5a90da8b397`；`x11.log` `728527ec097f3c79d90ae2a977043d0c6d4cd4dee65bdb6b7f4496794bc0af75`；`fuse.log` `33428f8c2bfb4e95b9a94d2041b6e8d04908d982f249c7cac9e241256d6e6adc`。`run.sh.txt` SHA-256 `088da10ac1c5e3299ff935ecb830d5c3e9676df892c9782ee5a15f31a6fdd3c4`、`sender.py.txt` `1154f7b8a478b7b788813b1ad47555d02034f1064b10331c7aa4d47c33c74324`、`target-focus.py.txt` `188ad9ac479d2a3369d44259c7f485f511f667aa395dc079b389e8abe4547f85`。三个探针文件增加 `.txt` 后缀以保留运行时原始字节；复制到隔离客机 `probes/` 时去除 `.txt`，将候选 AppImage 放到 `/tmp/inkecho-r4-test/`，在相应实际桌面会话运行 `bash probes/run.sh <上述SHA> wayland` 或 `x11`；准备步骤未独立重跑。

尚未覆盖 IBus 自动/手动支持、真正首次授权弹窗期间取消/超时、焦点切换、Chrome/终端等实际应用、物理快捷键、真实麦克风与云端语音、每个界面与安装路径以及 24.04。上述样本不构成完整项目验收或对所有应用支持的证明；本记录须与同哈希 24.04 实际包验收一并审核。
