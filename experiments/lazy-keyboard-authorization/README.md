# 延迟键盘授权原型：隔离桌面定向实验

本记录为源码覆盖实验，不是产品发布包验收。基包是 r4 AppImage，SHA-256 `852a9e53efd66c7a19806e2473726d1ae5cdae5306804992fbf7d925eb583a48`；解包后只将 `platform/output_router.py` 和 `app.py` 覆盖为原型，其 SHA-256 分别为 `e3f8e993566d996eabc43345f94956af821dec0ae071a8d632bbd62c36ff61e0` 和 `69cad54fee6b70bef05a5110289133aa819a33ebb4f0ba35d10f1d784fbf8600`。目标是隔离客机自建 GTK 控件，使用私有 Fcitx 和固定合成文字；未使用真实用户桌面、云端或真实凭据。日志包含完整合成测试文字。

## Ubuntu 24.04 Xorg

两轮测试的 Fcitx 目标和 simple 目标均在没有焦点时提前退出，未发送文字。第二轮增加对自有窗口 `xdotool windowactivate --sync` 后仍未聚焦；不能据此判断产品是否可用。`ubuntu24.log` 保存两轮失败输出，SHA-256 `f6ef4f040edc9442550eb2273938d4b6210bf2c7d5f4b7ba4bc96d24439cd41a`。客机实际会话 Xorg 且 active；测试服务退出，输入环境恢复 `XMODIFIERS=@im=ibus` 与 `QT_IM_MODULE=ibus`，临时 9p 只读挂载已卸载、测试文件已删除，容器退出码 0。测试时未记录第一轮脚本哈希，附件脚本为最后的 26 轮版本，不能声称逐字复现第一轮 24 运行。

## Ubuntu 26.04 GNOME Wayland

三个连续运行见 `ubuntu26.log`，SHA-256 `af9b12f94d937f9bbdd3d1fa0bfef1c62ad50c420c3cad961704b82a559da525`。前两轮 SSH 测试环境遗漏 `XDG_CURRENT_DESKTOP`，不能用来推断正常 GNOME Wayland 的键盘回退：首轮自建 Fcitx 控件完整收到 200 字，simple 目标在 Fcitx 明确 no_target 后走纯 X11 键盘，报告 unsupported_target、收到 0 字；第二轮 Fcitx 取消保留 1 字并结束，simple 目标仍同样失败。两轮均保留在日志中。

第三轮设置 `XDG_CURRENT_DESKTOP=ubuntu:GNOME`、确认会话 Wayland active 后，Fcitx 取消样本保留 1 字且结束，未出现 hybrid_connect 或 hybrid_authorize；自建 simple 目标下 Fcitx 返回 no_target、accepted=0、offset=0、uncertain=false，之后出现 hybrid_connect、keyboard_connect、hybrid_authorize，目标准确收到 200 字且任务 succeeded。原脚本标记该行 `passed=false`，因为旧断言只识别 X11 的 KeyboardInput.insert，不认识实际原生 Wayland 键盘输出；不改写原日志。原生 Fcitx 正常 200 字样本来自遗漏 GNOME 会话变量的首轮，不能称为该修正环境的正常样本。

最终运行的 `run.sh`、`sender.py.txt` 和 `target-focus.py.txt`（后两者只增加 `.txt` 后缀，字节不变）SHA-256 分别为 `6d38996f819f3cfb2230987ab08b51ba9cfd5f7c48f317ae0a3110fcd85de6ec`、`1154f7b8a478b7b788813b1ad47555d02034f1064b10331c7aa4d47c33c74324`、`188ad9ac479d2a3369d44259c7f485f511f667aa395dc079b389e8abe4547f85`。这些脚本依赖已解包的 r4 AppImage 与上述源码覆盖、隔离桌面和私有 Fcitx；具体环境依赖见 `docs/runtime-candidate-r4-validation.md`。退出后私有服务已停、输入环境恢复 ibus、临时文件删除，客机容器退出码 0。

本实验没有验证首次系统授权弹窗出现时的取消、超时、焦点切换或远端授权会话清理，也没有验证物理输入、完整语音、其他应用、IBus 自动选择及最终同一 AppImage 双系统验收。调用 hybrid_authorize 不证明当时系统确实展示首次授权弹窗。单元测试与真实桌面结果不能代替以上未验证项。

## 重建实验脚本

将本目录中的 `run.sh`、`sender.py.txt` 和 `target-focus.py.txt` 复制到隔离客机：

```sh
mkdir -p /tmp/inkecho-r4-test/probes
cp run.sh /tmp/inkecho-r4-test/probes/run.sh
cp sender.py.txt /tmp/inkecho-r4-test/probes/sender.py
cp target-focus.py.txt /tmp/inkecho-r4-test/probes/target-focus.py
```

两个 `.txt` 文件是最终实验脚本的原始字节；复制时仅去除 `.txt` 后缀，供 `run.sh` 调用。随后按上述记录提供相同的包和源码覆盖，核对会话及私有输入服务，再运行该脚本。此准备步骤本身未经客机重新运行，不能作为新的实测结果。
