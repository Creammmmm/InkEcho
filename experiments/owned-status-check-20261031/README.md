# GNOME 自动输入扩展状态检查

源码改动使状态检查在已校验文件后，依据 GNOME CLI 唯一的 `State:` 行显示运行、启用、未运行、停用、出错和版本不兼容；缺失、重复或未知状态均显示无法确认。运行状态不证明文字送达或目标兼容。

## 验证

- `pytest -q tests/test_owned_bounded_installation.py`：20 项通过。模拟 CLI 覆盖各种状态、重复状态行、命令缺失、超时和非零退出；同时覆盖旧版和异常文件不被启用或覆盖。
- `ruff check src/inkecho/platform/owned_extension.py tests/test_owned_bounded_installation.py`：通过。
- 本机 Ubuntu GNOME Wayland 中，只读调用 `OwnedExtensionManager().status()` 返回“操作未完成：扩展可能已存在、尚未加载，或当前桌面不支持。”不能据此断言实际安装状态或运行状态；未安装、启用或停用扩展。
- 同一桌面只读查看系统普通扩展 `ubuntu-dock@ubuntu.com` 的 CLI 输出，状态行是 `State: ACTIVE`。临时将状态解析目标替换为此扩展且绕过 InkEcho 文件校验后，解析显示“扩展显示正在运行；自动输出仍须验证当前目标和服务身份”。这只是对真实 CLI 输出格式的只读替身测试，不证明 InkEcho 扩展已安装或已运行，也不证明其他状态已在真实桌面验证。

没有验证实际 Owned 扩展启停、目标输入或双系统组合；这些仍需要独立验收。
