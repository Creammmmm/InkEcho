"""Independent provider editors; network protocols stay in ProviderClient."""

import json
import uuid
from dataclasses import replace

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
)

from inkecho.config import ConfigError, Provider
from inkecho.providers import ProviderError, validate_provider_protocol
from inkecho.realtime import PROTOCOL, RealtimeConfig
from inkecho.ui.widgets import Page, actions, button, card, label


class ProviderPage(Page):
    def __init__(self, session, role):
        polishing = role == "polishing"
        super().__init__(
            "文字润色" if polishing else "语音转写",
            "服务配置独立保存；API 密钥只进入系统密钥环。",
        )
        self.session, self.role = session, role
        self.revision = 0
        self.selector = QComboBox()
        self.selector.currentIndexChanged.connect(lambda: self.safe(self.load))
        self.body.addWidget(actions(self.selector, button("新建供应商", self.new)))
        panel, body = card()
        form = QFormLayout()
        self.name, self.url = QLineEdit(), QLineEdit()
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setPlaceholderText("输入模型 ID，或尝试发现模型")
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("留空保留现有密钥；不会显示已保存密钥")
        self.parameters = QPlainTextEdit("{}")
        self.parameters.setMaximumHeight(100)
        if not polishing:
            self.protocol = QComboBox()
            self.protocol.addItem("录音结束后上传 · HTTP", "http")
            self.protocol.addItem("边录边识别 · Qwen 实时 WebSocket", PROTOCOL)
            self.protocol.setPlaceholderText("请修正请求参数中的转写方式")
            self.realtime_url = QLineEdit()
            self.realtime_url.setPlaceholderText(
                "官方服务可留空；自定义服务请填写 wss:// 地址"
            )
            self.realtime_url.setEnabled(False)
        self.timeout = QSpinBox()
        self.timeout.setRange(5, 120)
        self.timeout.setSuffix(" 秒")
        self.timeout.setValue(
            getattr(session.store.load_settings(), role + "_timeout_seconds")
        )
        rows = [("显示名称", self.name), ("Base URL", self.url)]
        if not polishing:
            rows.extend(
                [
                    ("转写方式", self.protocol),
                    ("实时服务地址 · 可选", self.realtime_url),
                ]
            )
        rows.extend(
            [
                ("模型 ID", self.model),
                ("API 密钥", self.key),
                ("请求参数 · JSON", self.parameters),
                ("请求超时", self.timeout),
            ]
        )
        for title, widget in rows:
            form.addRow(title, widget)
        body.addLayout(form)
        self.model_hint = label("", muted=True)
        body.addWidget(self.model_hint)
        self.current = QCheckBox("设为当前服务")
        self.current.setChecked(True)
        body.addWidget(self.current)
        if polishing:
            settings = session.store.load_settings()
            self.enabled = QCheckBox("识别后使用云端润色")
            self.enabled.setChecked(settings.polishing_enabled)
            self.fallback = QCheckBox("润色失败时使用原始识别文本")
            self.fallback.setChecked(settings.polishing_fallback)
            self.streaming = QCheckBox("边润色边输入")
            self.streaming.setChecked(settings.polishing_streaming)
            body.addWidget(self.enabled)
            body.addWidget(self.streaming)
            body.addWidget(self.fallback)
            body.addWidget(
                label(
                    "边润色边输入可提前开始输出；已经开始输入后若失败，"
                    "将停止剩余文字，不会整段回退原文或重复输入。",
                    muted=True,
                )
            )
        self.body.addWidget(panel)
        self.body.addWidget(
            actions(
                button("保存配置与密钥", lambda: self.run(self.save()), primary=True),
                button("删除密钥", lambda: self.run(self.delete_key())),
                button("删除供应商", lambda: self.safe(self.delete)),
            )
        )
        self.body.addWidget(
            actions(
                button("发现模型 / 测试连接", lambda: self.run(self.discover())),
                button(
                    "测试模型能力 · 会调用云端", lambda: self.run(self.capability())
                ),
            )
        )
        self.body.addWidget(
            label(
                "云端处理会上传录音或转写文字。模型列表可用不代表模型支持所需能力；"
                "能力测试可能产生费用。请先保存配置与密钥。",
                muted=True,
            )
        )
        self.refresh()
        self.finish()
        self.model.currentTextChanged.connect(self.model_changed)
        self.url.textChanged.connect(self.model_changed)
        self.parameters.textChanged.connect(self.parameters_changed)
        if polishing:
            self.streaming.toggled.connect(self.model_changed)
        else:
            self.protocol.currentIndexChanged.connect(self.protocol_changed)
            self.realtime_url.textChanged.connect(self.protocol_changed)
            self.parameters_changed()
        self.update_model_hint()

    def model_changed(self):
        self.revision += 1
        self.update_model_hint()

    def parameter_values(self):
        try:
            values = json.loads(self.parameters.toPlainText())
        except json.JSONDecodeError:
            raise ConfigError(
                "请求参数必须是有效的 JSON 对象；原内容已保留。"
            ) from None
        if not isinstance(values, dict):
            raise ConfigError("请求参数必须是 JSON 对象；原内容已保留。")
        return values

    def parameters_changed(self):
        self.revision += 1
        if self.role == "transcription":
            try:
                values = self.parameter_values()
            except ConfigError:
                self.update_model_hint()
                return
            mode = values.get("asr_protocol", "http")
            endpoint = values.get("realtime_url", "")
            with QSignalBlocker(self.protocol), QSignalBlocker(self.realtime_url):
                self.protocol.setCurrentIndex(self.protocol.findData(mode))
                displayed_endpoint = endpoint if isinstance(endpoint, str) else ""
                if self.realtime_url.text() != displayed_endpoint:
                    self.realtime_url.setText(displayed_endpoint)
                self.realtime_url.setEnabled(mode == PROTOCOL)
        self.update_model_hint()

    def protocol_changed(self):
        self.revision += 1
        self.realtime_url.setEnabled(self.protocol.currentData() == PROTOCOL)
        try:
            values = self.parameter_values()
        except ConfigError:
            self.update_model_hint()
            return
        mode = self.protocol.currentData()
        if mode == "http":
            values.pop("asr_protocol", None)
            values.pop("realtime_url", None)
        elif mode == PROTOCOL:
            values["asr_protocol"] = PROTOCOL
            endpoint = self.realtime_url.text().strip()
            if endpoint:
                values["realtime_url"] = endpoint
            else:
                values.pop("realtime_url", None)
        else:
            self.update_model_hint()
            return
        self.parameters.setPlainText(json.dumps(values, ensure_ascii=False, indent=2))
        self.update_model_hint()

    def validate_protocol(self, provider):
        validate_provider_protocol(provider)
        if provider.parameters.get("asr_protocol") == PROTOCOL:
            sample_rate = self.session.store.load_settings().sample_rate
            if sample_rate != 16000:
                raise ConfigError(
                    "Qwen 实时需要 16 kHz 录音；请在录音设置中手动选择。"
                    "当前采样率未被修改。"
                )
            RealtimeConfig.from_provider(provider, sample_rate=sample_rate)

    def update_model_hint(self):
        from inkecho.app import PROVIDER_LABELS

        try:
            provider = self.provider()
            self.validate_protocol(provider)
        except ProviderError as error:
            self.model_hint.setText(PROVIDER_LABELS[error.code])
        except ConfigError as error:
            self.model_hint.setText(str(error))
        except (ValueError, AttributeError):
            self.model_hint.setText("请填写有效的服务配置，再检查模型协议。")
        else:
            if self.role == "polishing":
                hint = "模型列表不等于能力验证；请测试当前模型能否完成润色。"
            elif provider.parameters.get("asr_protocol") == PROTOCOL:
                hint = (
                    "已选择边录边识别；需 16 kHz 录音。请测试所选服务和模型的实时能力。"
                )
            else:
                hint = (
                    "录音结束后通过 HTTP 上传；实时模型请切换转写方式。"
                    "模型列表不等于能力验证。"
                )
            self.model_hint.setText(hint)

    def refresh(self, identifier=None):
        self.selector.blockSignals(True)
        self.selector.clear()
        for provider in self.session.store.providers():
            if provider.role == self.role:
                self.selector.addItem(provider.name, provider.id)
        if identifier:
            self.selector.setCurrentIndex(self.selector.findData(identifier))
        self.selector.blockSignals(False)
        self.load()

    def load(self, _index=None):
        self.revision += 1
        identifier = self.selector.currentData()
        if not identifier:
            self.new()
            return
        provider = self.session.store.load_provider(identifier)
        self.identifier = provider.id
        self.reference = provider.key_ref or f"provider/{provider.id}"
        self.name.setText(provider.name)
        self.url.setText(provider.base_url)
        self.model.setCurrentText(provider.model)
        self.parameters.setPlainText(
            json.dumps(provider.parameters, ensure_ascii=False, indent=2)
        )
        self.key.clear()
        settings = self.session.store.load_settings()
        if self.role == "polishing":
            self.streaming.setChecked(settings.polishing_streaming)
        selected = (
            settings.polishing_provider
            if self.role == "polishing"
            else settings.transcription_provider
        )
        self.current.setChecked(selected == provider.id)
        self.update_model_hint()

    def new(self):
        self.revision += 1
        self.identifier = "provider-" + uuid.uuid4().hex
        self.reference = f"provider/{self.identifier}"
        self.name.setText(
            "自定义润色服务" if self.role == "polishing" else "自定义转写服务"
        )
        self.url.setText(
            "https://api.deepseek.com"
            if self.role == "polishing"
            else "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.model.setCurrentText("")
        self.parameters.setPlainText("{}")
        self.key.clear()
        self.current.setChecked(True)
        self.update_model_hint()

    def provider(self):
        return Provider(
            self.identifier,
            self.name.text().strip(),
            self.role,
            "openai" if self.role == "polishing" else "qwen",
            self.url.text().strip(),
            self.model.currentText().strip(),
            self.reference,
            self.parameter_values(),
        )

    async def save(self):
        provider = self.provider()
        # Reject secret-bearing/invalid endpoints before touching credentials or
        # persisting any parameter string, including an unselected URL draft.
        if "asr_protocol" in provider.parameters:
            self.validate_protocol(provider)
        if "realtime_url" in provider.parameters:
            RealtimeConfig(provider.parameters["realtime_url"], provider.model)
        revision = self.revision
        value = self.key.text()
        self.key.clear()
        updates = {self.role + "_timeout_seconds": self.timeout.value()}
        if self.current.isChecked():
            updates[self.role + "_provider"] = provider.id
        if self.role == "polishing":
            updates.update(
                polishing_enabled=self.enabled.isChecked(),
                polishing_fallback=self.fallback.isChecked(),
                polishing_streaming=self.streaming.isChecked(),
            )
        if value:
            await self.session.save_key(provider.key_ref, value)
        self.session.store.save_provider(provider)
        settings = self.session.store.load_settings()
        self.session.store.save_settings(replace(settings, **updates))
        if revision != self.revision:
            return
        self.refresh(provider.id)
        self.message.setText("服务配置已保存；密钥保存在系统密钥环。")

    async def delete_key(self):
        revision = self.revision
        await self.session.save_key(self.reference, None)
        if revision != self.revision:
            return
        self.key.clear()
        self.message.setText("此供应商的密钥已从系统密钥环删除。")

    def delete(self):
        providers = [
            p
            for p in self.session.store.providers()
            if p.role == self.role and p.id != self.identifier
        ]
        if not providers:
            self.message.setText("请至少保留一个服务配置。")
            return
        settings = self.session.store.load_settings()
        field = self.role + "_provider"
        if getattr(settings, field) == self.identifier:
            self.session.store.save_settings(
                replace(settings, **{field: providers[0].id})
            )
        self.session.store.delete_provider(self.identifier)
        self.refresh()
        self.message.setText("供应商配置已删除。密钥可在删除前单独移除。")

    async def discover(self):
        provider = self.provider()
        revision = self.revision
        self.message.setText("正在连接服务并获取模型列表……")
        key = await self.session.key(provider.key_ref)
        if revision != self.revision:
            return
        models = await self.session.provider_client(self.role).models(provider, key)
        if revision != self.revision:
            return
        selected = self.model.currentText()
        self.model.clear()
        self.model.addItems(models)
        unsupported = 0
        for index, model in enumerate(models):
            try:
                validate_provider_protocol(replace(provider, model=model))
            except ProviderError:
                unsupported += 1
                self.model.setItemData(
                    index,
                    "当前配置或转写方式与此模型协议不匹配",
                    Qt.ItemDataRole.ToolTipRole,
                )
                self.model.setItemData(
                    index, QColor("#aa3434"), Qt.ItemDataRole.ForegroundRole
                )
        self.model.setCurrentText(selected)
        self.message.setText(
            f"连接成功，发现 {len(models)} 个模型；尚未验证模型能力。"
            + (
                f"其中 {unsupported} 个模型的协议尚不支持，已标红。"
                if unsupported
                else ""
            )
        )

    async def capability(self):
        provider = self.provider()
        revision = self.revision
        self.validate_protocol(provider)
        settings = self.session.store.load_settings()
        streaming = self.role == "polishing" and settings.polishing_streaming
        key = await self.session.key(provider.key_ref)
        if revision != self.revision:
            return
        audio = None
        if self.role == "transcription":
            self.message.setText("请说一句话：录制 3 秒后上传进行能力测试……")
            audio = await self.session.sample_audio()
            if revision != self.revision:
                return
        else:
            self.message.setText(
                "正在发送一次简短流式润色测试……"
                if streaming
                else "正在发送一次简短润色测试……"
            )
        result = await self.session.provider_client(self.role).test_capability(
            provider, key, audio=audio, streaming=streaming
        )
        if revision != self.revision:
            return
        self.message.setText(
            f"模型能力测试成功，收到 {len(result.text)} 个字符；未向其他窗口输入。"
        )
