"""Independent provider editors; network protocols stay in ProviderClient."""

import json
import uuid
from dataclasses import replace

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
)

from inkecho.config import Provider
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
        self.timeout = QSpinBox()
        self.timeout.setRange(5, 120)
        self.timeout.setSuffix(" 秒")
        self.timeout.setValue(
            getattr(session.store.load_settings(), role + "_timeout_seconds")
        )
        for title, widget in (
            ("显示名称", self.name),
            ("Base URL", self.url),
            ("模型 ID", self.model),
            ("API 密钥", self.key),
            ("请求参数 · JSON", self.parameters),
            ("请求超时", self.timeout),
        ):
            form.addRow(title, widget)
        body.addLayout(form)
        self.current = QCheckBox("设为当前服务")
        self.current.setChecked(True)
        body.addWidget(self.current)
        if polishing:
            settings = session.store.load_settings()
            self.enabled = QCheckBox("识别后使用云端润色")
            self.enabled.setChecked(settings.polishing_enabled)
            self.fallback = QCheckBox("润色失败时使用原始识别文本")
            self.fallback.setChecked(settings.polishing_fallback)
            body.addWidget(self.enabled)
            body.addWidget(self.fallback)
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
        selected = (
            settings.polishing_provider
            if self.role == "polishing"
            else settings.transcription_provider
        )
        self.current.setChecked(selected == provider.id)

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

    def provider(self):
        return Provider(
            self.identifier,
            self.name.text().strip(),
            self.role,
            "openai" if self.role == "polishing" else "qwen",
            self.url.text().strip(),
            self.model.currentText().strip(),
            self.reference,
            json.loads(self.parameters.toPlainText()),
        )

    async def save(self):
        provider = self.provider()
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
        models = await self.session.provider_client(self.role).models(
            provider, await self.session.key(provider.key_ref)
        )
        if revision != self.revision:
            return
        selected = self.model.currentText()
        self.model.clear()
        self.model.addItems(models)
        self.model.setCurrentText(selected)
        self.message.setText(f"连接成功，发现 {len(models)} 个模型；尚未验证模型能力。")

    async def capability(self):
        provider = self.provider()
        revision = self.revision
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
            self.message.setText("正在发送一次简短润色测试……")
        result = await self.session.provider_client(self.role).test_capability(
            provider, key, audio=audio
        )
        if revision != self.revision:
            return
        self.message.setText(
            f"模型能力测试成功，收到 {len(result.text)} 个字符；未向其他窗口输入。"
        )
