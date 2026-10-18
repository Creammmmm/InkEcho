# 0.3.2 明文凭据候选包验收

本次交付将认证信息改为当前配置目录中的明文 `credentials.json`，不再使用系统密钥环。源码行为、权限保护与本机项目虚拟环境依赖清理见[源码验证记录](plaintext-credentials-validation.md)。没有读取、迁移或删除用户旧密钥环条目，用户需要重新填写凭据。本次不创建 GitHub release，不改变已发布 0.3.0 的历史资产。

## 固定产物与来源

- 产品源码：`30a4fe19f1f7e308626319471b7d0fc6d0534c24`，实际应用版本 **0.3.2**。
- 构建前 root 精确 clean HEAD 完整检查：Ruff/format 324 文件，1953 passed、3 skipped，64.00 s；receipt 证据为源码报告 SHA `13215bfcecf571fc1068007843ddff884fdc32570da6cc962567fa07f31b7c53`。
- AppImage：`dist/InkEcho-0.3.2-x86_64.AppImage`，104266232 bytes。
- SHA-256：`e9c3d990aabf435807ce6af4177a1461577342a1510535389ef8aa1efd75f02b`。
- sidecar SHA-256：`cc4d4f3bc5ca0c26c118f986cb0aff8328b4aa18af814fd9c39f1edb425d83ad`。
- inventory SHA-256：`1a83f85bee94948864e4fb875cb45964464e4ef79101e2960536535e2afb8bf1`。实际版本 0.3.2，3664 文件、1048 符号链接、55 应用源文件逐项匹配冻结源；没有把旧包改名当新包。

唯一构建及独立提取均由原 Popen 正常 wait 0，外层句柄 94303 正常退出。冻结 417 个 tracked 文件，manifest SHA `cd79fbb54d361ea7d1d996668e5d68f09244774714d419189505da23c0aef106`。构建全过程 61 路径保全，稳定入口当时保持 0.3.0。

## 实际包验证范围

两个系统使用上述同一 SHA 的产物、实际包解释器和包内模块，检查 30 个指定来源与完整 55 源集合/哈希；没有通过源码 overlay 替代实际包。仅使用私有临时配置与合成认证字符串，不调用真实云、麦克风或用户窗口。

专用凭据门检查实际 Session 保存、重读及删除；ProviderPage 的 App/Access 多字段 bundle 保存、重载不显示秘密；不同配置根隔离；切换供应商不复用旧引用；普通 provider 参数无秘密；JSON schema 和明文值一致；目录 0700、文件 0600。九项检查均要求精确成功。两系统均检查 inventory 不含被移除的 11 个专用分发，实际解释器对应模块均不可发现，也没有加载 keyring/SecretStorage/jeepney。

Ubuntu 26.04 主机实际 GNOME Wayland 会话：六项原 owner 顺序执行——凭据门、AppRun 九页、真实 factory 原生 Wayland 100 字/取消8、XWayland 100 字/取消8。外层句柄 55745 正常退出；全部六个原 Popen wait 0、保全不变。正常读回均精确100、按下/释放100/100；取消只读回前8、计数8/8，无尾随；守卫拒绝0、目标正常退出、映射恢复和清理门均通过。root 已实际查看九页，新明文说明与 0.3.2 版本、布局正常。

Ubuntu 24.04.5 / GNOME 46 KVM 客体，实际解锁的 Xorg session 20：独立提取、凭据门、AppRun 九页、真实 factory Xorg 100 字及取消8，共五个模式。原外层句柄 2476 正常退出，五个本地 SSH 原 owner 和客体原进程均 wait 0，无终止信号；同 SHA、55 源和主机保全一致。凭据九门及 11 模块缺失均通过；正常100/100、取消8/8、精确读回、守卫0、恢复和清理通过。root 已实际查看九页，新明文说明与 0.3.2 版本正常。GNOME 46 的原生 Wayland 路线仍不支持；Xorg 成功不能推定 native 支持。

候选私有 FUSE：原句柄 10488 正常退出，实际 `/tmp/.mount_*` 内版本 0.3.2，inventory 3664 文件/1048 链接及 55 冻源逐项核对，九页截图齐全，原 Popen wait 0、63 路径保全。只启动版本化候选的独立 `--config-dir`，未触碰正常用户实例。结果在 `candidate-fuse-r1/result.json`。

## 复现材料

本轮原始材料在 `build/plaintext-credentials-preparation` 与 `build/plaintext-credentials-acceptance-preparation`；不改写旧报告或旧冻结文件。

- build-plan SHA：`da4acbce23892f3017daf9206be7d2bf9ff76b3c7f1ccd2b8c8bd62d1f8b1712`；build/extract 原 owner 收据及 `build-result-r1.json` 在前一目录。
- host preview SHA：`1b9002bd641c5ea111be8bcf4fa274620ecab2de8505bb75354aa49173f9955e`；原始 JSON/owner/terminal 在 `results-r1`，`host-progress-r1.json` 在验收目录根。
- 凭据门 helper SHA：`b0c40506dbc5ae9d00cc03d1786c9acb08e01f4b74b4723f87800d70fa0e04a0`。实际包命令使用 `usr/bin/python3 -I -B`，只显式添加实际 package 路径及冻结诊断 tools；所有配置路径均为新建私有目录。
- guest stage preview SHA：`e3987132f14911a5490ae1936afcdc9c8f39bedc66cdeca3d78b7ac76214e4c4`，422 个输入逐 hash copy2，AppImage 保持 0755，独立新路径提取。

这些探针是受审的 ignored 原始验收材料；持久化存储/Session/UI 测试和合成凭据探针在源码提交中可复现。本轮不重复无变更的 226 项供应商协议或性能分档试验，其历史结果不作为本包新的云认证。

## 交付状态及限制

root 已审双系统、FUSE 原始收据和九页截图。随后按已审白名单单次更新稳定 AppImage 与其 sidecar，原句柄 92577 正常退出；稳定文件 SHA 与上述 0.3.2 候选精确相同。两个旧文件先备份到 `build/plaintext-credentials-acceptance-preparation/deployment-r1/backups`，61 个其它路径保持原哈希，结果在 `deployment-r1/result.json`。配置、旧版本包、launcher、图标、缓存和系统共享密钥环服务保留，不控制或重启用户当前实例。旧凭据条目未删除但新版本不再使用；用户需重新填写。

已发布的 GitHub 0.3.0 资产保持原样，本次只更新本机稳定入口，不创建 release。后继源码报告提交版本为 0.3.3；已验实际包来源仍为 0.3.2 / `30a4fe19f1f7e308626319471b7d0fc6d0534c24`，不把文档版本当成重新打包。

未验证真实云账号权限、真实麦克风、物理快捷键或任意应用兼容性；客体 FUSE 未验证。明文文件只有操作系统权限保护，不等于加密。验收报告属于后继源码版本，产品包仍固定上述 0.3.2 source commit，不因报告提交重新构建。
