# Ubuntu 26.04 候选包 Chrome 与 VTE 定向实验

候选 AppImage SHA-256 `f6ceb6311069f85b180bafd446f546247b5e592735ba26035455a571c5eb5164`，Ubuntu 26.04.1、GNOME Wayland、Fcitx 5.1.19；使用 QEMU `-snapshot`，系统盘、基础盘和 seed 只读挂载，容器 `--network none`。临时客机内使用专用 Fcitx 配置、专用空浏览器配置、本机 HTTP 服务器及固定合成文本；不使用个人网页或凭据。发送端调用候选包内应用代码及真实输出路由，音频及识别结果由测试替身生成，并非真实麦克风或云端识别。

实验使用宿主已安装 Chrome 154.0.8037.97 的临时副本和空白个人资料，在隔离断网客机启动。前两轮因复制版 sandbox helper 配置和客机命名空间权限无法启动，日志分别为 `browser.log`、`browser-r2.log`，显示初始焦点缺失；手动诊断分别显示沙箱 helper 权限问题和 namespace EPERM。第三轮仅该隔离测试进程使用 `--no-sandbox`，并非产品配置；结果不证明正常安装 Chrome 的沙箱配置。网页在本地监听，仅包含两个自建文本框。

Chrome 原生 Wayland 完整样本精确 200 字；取消样本在接收首字后发送取消，保留 1 字前缀；切换样本在首字后暂停发送，等待第二浏览器窗口报告文本框取得焦点再恢复，第一、第二窗口分别收到 1 和 199 字，总文本精确。三种测试中 Fcitx 返回 `no_target`、已接受 0，随后由键盘后端回退；**不证明 Chrome 的 Fcitx 直输入成功**，也不证明不暂停情况下切换焦点无竞态。日志保留每次提交状态与回退事件。

VTE 0.84.0 自建 GTK3 终端控件通过真实 Fcitx 桥：正常输入 200 字精确，返回成功 200 次；取消样本记录 4 字前缀及 cancelled，取消时已收到 3 次成功响应、另一次提交在途被取消，第四字状态不确定，不可重放。切换样本在检测到前缀后暂停发送，确认第二窗口获得焦点后恢复，两窗口分别接收 4 和 196 字，总文本精确。该客机没有安装独立终端应用，VTE 夹具不能冒充对 GNOME Terminal、Codex CLI 等实际应用的验收。

原始日志为 `browser-r3.log`（SHA-256 `b7a2d9e881884aca2dc3a87188e5444e0679260dc341c3462e8d82f1e26dcbb9`）与 `vte.log`（`1508b7e3793f9e71d2628bfc0acbaf860b32130caae4b4c4416453707b193a87`）。`browser.py.txt`、`vte_driver.py.txt`、`vte_fixture.py.txt`、`sender.py.txt`、`browser-run.sh.txt` 和 `vte-run.sh.txt` 为实测字节；复现需移除 `.txt` 后缀并放入隔离客机 `/tmp/inkecho-r4-test/probes/`，将同 SHA 包放入其父目录，在活跃 Wayland 会话运行 `bash probes/browser-run.sh <SHA> wayland`、`bash probes/vte-run.sh <SHA> wayland`。浏览器副本需放入 `/tmp/inkecho-browser/chrome/`。配置及服务更改只发生在客机快照中。实验结束后客机正常关机，容器 `docker wait` 返回 0，临时容器已删除。

以上不覆盖 X11、Ubuntu 24.04、真实麦克风、真实云端 API、完整 AppImage 界面及真实终端应用，不构成发布验收。
