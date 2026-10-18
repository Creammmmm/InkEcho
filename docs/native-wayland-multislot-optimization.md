# 原生 Wayland 四槽及后续容量验证

本页记录 a16 双槽实现之后的源码试验。稳定 a16 的产物与用户配置不由这些源码试验修改；本页不构成新的包或 Ubuntu 双系统验收。先前双槽机制见 [双槽优化](native-wayland-batch-optimization.md)。

## 阶段 0：新增槽不能只凭名称采用

以 clean HEAD `6bc6767c6faeac1173de5929c2abc91f766c8968` 为双槽源码对照，使用实际 a16 AppImage（SHA `5e0c39a8a77faf8d846b0cb915cf4345b619dbd205504498496ec8fa590ec320`）的 Python/依赖。每个候选冻结 44 产品文件、四个后端 pin，独立 registry pin，审计全依赖 inventory 和 19 个来源。单槽变体只把 primary/optional 常量均设为被测槽，排除额外槽干扰；这是源码试验，不能称实际包已经支持新容量。

`build/native-slots4-r1/empty-slots-r1.json` 只读枚举 libxkbcommon 实际 keycode 9..708，逐 group/level 检查。原图 SHA `6b19630e18f35206efdf196a5a5a36c9768b1b838e7862ff157610b02216c192`，2 groups、group0、depressed0、latched0、locked16。空槽名字仅是 XKB/内核标识，不能证明 Chrome 接受输入。

| 候选 XKB / evdev | 实际结果 | 决定 |
| --- | --- | --- |
| 103 JPCM / 95 | 首 Chrome 普通100读回不精确；100press/100release、guard0、compile100/SetMap101 ACK，worker和target原wait0、映射恢复、cleanup空 | 停止该六例组，其余5未运行，不采用、不重试；旧失败路径未保存收到长度，不能声称0字 |
| 197 FK19 / 189 | Chrome、GTK、VTE各100及cancel8，共6例全部通过 | 新增兼容槽 |
| 202 FK24 / 194 | Chrome、GTK、VTE各100及cancel8，共6例全部通过 | 新增兼容槽 |

证据、固定 argv/environment/hash 及原 Popen wait 位于 `build/native-slots4-r1/preview-slot{103,197,202}-r1.json`、对应 runner、`*-result.json` 和 `phase0-summary-r1.json`。197/202均按单一实际 evdev code 输出，取消从完整100字请求实际停止，非预切样本。既有132/97兼容记录保留，不把新试验倒填到旧包报告。

## 四槽实现及纯测试

仅三个产品模块改变：父进程发送当前一个字符及最多三个相邻后续普通 BMP 字符的非发出 hint；不越过 newline、没有后台正文队列。worker 在任何新发送之前严格验证 hint 类型/长度/字符。Keymap 使用 mandatory132 及 optional97/197/202，所有 optional 必须在原图全部 group/level 为空；占用或缺失槽跳过，不能覆盖非空键。当前字符与 hint 去重后最多四项，只发送当前字符，每次仍 ACK1；hint失配只重新准备当前及本次可选hint，不发送旧提示。

每字 source/map/group/modifier/task/取消检查与原 first50/rest30/release30ms 等待保持。prepared 表命中也保留实际状态查询；取消、finish、跨后端关闭仍清空并恢复。focused 三模块测试 163 passed（5.13秒）；root独立关联组合231 passed（6.25秒）。测试包含所有真实 keycode 边界的其它键 group/level 不变、去重、缺失/非空槽退化、invalid hint预检、1/2/3个未发出hint被取消、newline边界及逐字ACK。

## 四槽源码实际门

`build/native-four-batch-r1/` 冻结两槽baseline及四槽candidate，真实 a16 依赖、44源及19来源；运行前两份 fresh focus 稳定采样及写入 formal baseline，不激活用户窗口。三种自有目标只自然启动并正常关闭，保留原 owner 等待终态。

| 普通100字 | 两槽(ms) | 四槽(ms) |
| --- | ---: | ---: |
| 第1轮 | 7046.827 | 5431.855 |
| 第2轮 | 7086.821 | 5318.483 |
| 第3轮 | 6938.970 | 5443.445 |
| 均值 | 7024.206 | 5397.927 |

平均 scope 减少 **23.152%**。两槽每轮compile50、SetMap ACK51（含恢复），四槽compile25、ACK26；四槽实发codes为124/89/189/194。首字四槽约97.404..104.326ms；这是三次自有Chrome源码样本，含守卫开销，不是任意应用或实际新包的统计。SetMap ACK包含合成器处理和D-Bus往返，不归为纯总线延迟。

20项实际有效门：普通对照6、非相邻重复控制2、Chrome cancel8、GTK/VTE各混合Unicode100+cancel8共4、Chrome contenteditable100+cancel8、完整100请求cancel5留3个未发出hint，以及受控native/X双方向normal/cancel14共4。全部精确读回、press/release平衡、guard0、scope及最终映射恢复、无尾随、cleanup空，原worker/target退出0，stable/a16/config哈希保全。GTK/VTE读回socket本身有约5ms成本，不能用其scope直接比较Chrome速度。

四个mixed门仍是已确认前缀10字暂停、新目标ready后的受控边界；证明该边界下关闭旧scope、恢复和不重放，不能称无暂停原子切换或切换吞吐。首个mixed实际raw已通过/exit0，但外层runner遗漏替换旧candidate manifest硬pin而误判false；保留原runner失败，独立只读核新manifest及全部门后，获审新subset R2只运行剩3，未重复首例正文。

固定入口为 `preview-first-r1.json` / `run-first-r1.py`、`preview-remaining-r1.json` / `run-remaining-r1.py`、原 `preview-mixed-r1.json` 及修正后的 `preview-mixed-rest-r2.json` / `run-mixed-rest-r2.py`。`source-gate-summary-r1.json`、`ordinary-aggregate-r1.json` 绑定全部raw与实际计数。重跑必须创建新的路径并先审模板，不覆盖本次证据。

## 八槽后续边界

八槽探索先从未验证的其它空槽开始：将官方 Chromium physical-code 数据的正确 XKB 列与 fresh 空槽交集，再有限逐槽验证；upstream main 资料需要与已安装版本区分。只读筛选与真实兼容试验分开，不能因空槽数量足够就声明八槽可行。未经八槽自己的纯测试、三目标、取消、恢复和至少三轮性能对照，不扩大生产allowlist或hint上限。

这些源码试验不读取密钥、不访问云端/麦克风，不用剪贴板/系统输入法，不控制用户程序。本页的源码证据不代替后续版本的构建、部署和包验收记录。

八槽只读筛选的实际结果：安装 Chrome `154.0.8037.97`；[官方 Chromium main physical-code 表](https://raw.githubusercontent.com/chromium/chromium/main/ui/events/keycodes/dom/dom_code_data.inc) 固定为 SHA `841e2c58e6388f14736717eb6e365c8b8e9767788e36339bf1d35a37ab48e5b2`（35960字节）。严格解析246条 active `DOM_CODE`，使用第三个 XKB 列并验证非零 XKB=evdev+8，不把其它列数值误当匹配。与重新只读确认的55个全层空槽交集，仅有已实测4槽及217/BASS_BOOST、413/MEDIA_LAST；后二者是NULL code字符串的非标准枚举，随后另行有限实测。没有找到补足八槽所需的另外四个已知普通physical-code候选。随后只尝试一次获取官方 `refs/tags/154.0.8037.97` 同文件，成功且 SHA 与 main 完全一致；标签结果记录于 `installed-tag-source-r1.json`。这仍是源码表筛选而非浏览器实际兼容证明。这个静态结果只限定本次原图及这份版本资料，不是所有平台均不可能支持八槽的证明。完整来源、fresh状态和交集保存在 `build/native-eight-phase0-r1/{source.json,empty-slots-r1.json,intersection-r1.json}`。


217（evdev209）与413（evdev405）的独立单槽有限门已完成：分别Chrome普通100/cancel8通过后，再GTK/VTE各普通100/cancel8，共12个有效case全部精确、guard0、无尾随、完整恢复、worker/target原wait0、保全不变。实际只发各自单一evdev码；证据位于 `build/native-eight-phase0-r1/preview-slot{217,413}-{chrome,native}-r1.json`、对应runner/raw与 `phase0-summary-r1.json`。这说明NULL code字符串不等于不能输入；但目前总计仅六个经过三目标单槽验证的安全候选，仍不足八个。本次不扩大四槽allowlist、不实现“假八槽”，不覆盖原有非空键。六槽组合也未做组合/性能验收，不能由单槽成功宣称六槽产品支持；八槽在当前原图和约束下仍受候选不足限制。

root独立工作树完整回归：Ruff通过、292文件格式检查通过；提权同树pytest **1582 passed / 3 skipped，40.61秒**。首次普通沙箱运行因本地socket/TLS权限EPERM出现38项环境失败（737passed/2skipped），root对唯一自有pytest进程正常SIGINT结束exit2；原失败保留，未修改测试绕过。之后按已有提权方式同树执行成功。这是工作树回归，不是clean HEAD收据，后续提交仍须正式workflow。a17构建计划仅涉及三处版号及51个旧路径保全；其构建、部署及同包双系统门须另行审核记录，本页不作包验收结论。
