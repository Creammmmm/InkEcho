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
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from inkecho.config import ConfigError, Provider
from inkecho.provider_catalog import (
    PRESETS,
    STATIC_MODEL_ADAPTERS,
    asr_capability,
)
from inkecho.provider_credentials import encode_credentials
from inkecho.provider_guidance import setup_guidance
from inkecho.providers import ProviderError, validate_provider_protocol
from inkecho.realtime import PROTOCOL, RealtimeConfig
from inkecho.security import CredentialError
from inkecho.ui.widgets import Page, actions, button, card, label


class ProviderPage(Page):
    def __init__(self, session, role):
        polishing = role == "polishing"
        super().__init__(
            "文字润色" if polishing else "语音转写",
            "管理服务地址、模型与访问凭据。",
        )
        self.session, self.role = session, role
        self.revision = 0
        self.available_models = ()
        self.selector = QComboBox()
        self.selector.currentIndexChanged.connect(lambda: self.safe(self.load))
        self.selector.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.selector.setMinimumContentsLength(28)
        self.selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        selector_row = QWidget()
        selector_layout = QHBoxLayout(selector_row)
        selector_layout.setContentsMargins(0, 0, 0, 0)
        selector_layout.addWidget(self.selector, 1)
        selector_layout.addWidget(button("新建模型配置", self.new))
        self.body.addWidget(selector_row)
        self.body.addWidget(
            actions(
                button("保存配置", lambda: self.run(self.save()), primary=True),
                button("删除配置", lambda: self.safe(self.delete)),
            )
        )
        panel, body = card()
        form = QFormLayout()
        self.preset = QComboBox()
        for item in PRESETS:
            if item.role == role:
                self.preset.addItem(item.label, item.id)
        self.adapter = "openai" if polishing else "qwen"
        self.name, self.url = QLineEdit(), QLineEdit()
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setPlaceholderText("选择内置模型，或输入模型 ID")
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("留空保留现有密钥；不会显示已保存密钥")
        self.credential_inputs = {"api_key": self.key}
        for field in (
            "app_id",
            "api_secret",
            "secret_id",
            "secret_key",
            "app_key",
            "access_key",
        ):
            widget = QLineEdit()
            widget.setEchoMode(QLineEdit.EchoMode.Password)
            widget.setPlaceholderText("全部留空保留；修改时须完整填写本组凭据")
            self.credential_inputs[field] = widget
        self.resource_id = QLineEdit()
        self.resource_id.setPlaceholderText("按控制台授权填写，不自动猜测资源")
        self.credential_labels = {}
        self.parameters = QPlainTextEdit("{}")
        self.parameters.setMaximumHeight(100)
        if not polishing:
            self.protocol = QComboBox()
            self.protocol.addItem("录音结束后上传 · HTTP", "http")
            self.protocol.addItem("边录边识别 · Qwen 实时 WebSocket", PROTOCOL)
            self.protocol.addItem("边录边识别 · 阶跃 ASR WebSocket", "stepfun_realtime")
            self.protocol.addItem("边录边识别 · 百炼任务 WebSocket", "dashscope_task")
            self.protocol.addItem("边录边识别 · 讯飞听写", "xfyun_iat")
            self.protocol.addItem("边录边识别 · 腾讯云识别", "tencent_asr")
            self.protocol.addItem("边录边识别 · 火山识别", "volc_binary")
            self.protocol.setPlaceholderText("请修正请求参数中的转写方式")
            self.realtime_url = QLineEdit()
            self.realtime_url.setPlaceholderText(
                "官方服务可留空；自定义服务请填写 wss:// 地址"
            )
            self.realtime_url.setEnabled(False)
        rows = [
            ("服务平台", self.preset),
            ("显示名称", self.name),
            ("Base URL", self.url),
        ]
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
            ]
        )
        for title, widget in rows:
            form.addRow(title, widget)
        self.credential_labels["api_key"] = form.labelForField(self.key)
        for field, widget in self.credential_inputs.items():
            if field != "api_key":
                form.addRow(field.replace("_", " ").title(), widget)
                self.credential_labels[field] = form.labelForField(widget)
        form.addRow("资源 ID · 火山授权资源", self.resource_id)
        self.resource_label = form.labelForField(self.resource_id)
        self.parameters.hide()
        form.labelForField(self.parameters).hide()
        if not polishing:
            self.realtime_url.hide()
            form.labelForField(self.realtime_url).hide()
        body.addLayout(form)
        self.model_hint = label("", muted=True)
        body.addWidget(self.model_hint)
        self.current = QCheckBox("使用此配置")
        self.current.setChecked(True)
        body.addWidget(self.current)
        self.body.addWidget(panel)
        guide_panel, guide_body = card()
        self.guide_summary = label("", muted=True)
        self.guide_toggle = QPushButton("查看 API 配置步骤")
        self.guide_toggle.setCheckable(True)
        guide_header = QHBoxLayout()
        guide_header.addWidget(self.guide_summary, 1)
        guide_header.addWidget(self.guide_toggle)
        guide_body.addLayout(guide_header)
        self.guide_links = label("")
        self.guide_links.setTextFormat(Qt.TextFormat.RichText)
        self.guide_links.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        self.guide_links.setOpenExternalLinks(True)
        guide_body.addWidget(self.guide_links)
        self.guide_details = label("")
        self.guide_details.setTextFormat(Qt.TextFormat.RichText)
        self.guide_details.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        self.guide_details.setOpenExternalLinks(True)
        self.guide_details.hide()
        self.guide_toggle.toggled.connect(self.toggle_guidance)
        guide_body.addWidget(self.guide_details)
        self.body.insertWidget(self.body.indexOf(panel), guide_panel)
        self.body.addWidget(
            actions(
                button("测试连接", lambda: self.run(self.discover())),
            )
        )
        self.refresh()
        self.finish()
        self.preset.activated.connect(self.apply_preset)
        self.model.currentTextChanged.connect(self.model_changed)
        self.url.textChanged.connect(self.model_changed)
        self.name.textChanged.connect(self.model_changed)
        self.parameters.textChanged.connect(self.parameters_changed)
        self.resource_id.textChanged.connect(self.model_changed)
        if not polishing:
            self.protocol.currentIndexChanged.connect(self.protocol_changed)
            self.realtime_url.textChanged.connect(self.protocol_changed)
            self.parameters_changed()
        self.update_model_hint()

    def apply_preset(self, index):
        self.preset.setCurrentIndex(index)
        preset = next(
            item for item in PRESETS if item.id == self.preset.itemData(index)
        )
        self.identifier = "provider-" + uuid.uuid4().hex
        self.reference = f"provider/{self.identifier}"
        self.adapter = preset.adapter
        if self.role == "transcription":
            with QSignalBlocker(self.protocol), QSignalBlocker(self.realtime_url):
                self.protocol.setCurrentIndex(self.protocol.findData(preset.protocol))
                self.realtime_url.clear()
                self.realtime_url.setEnabled(preset.protocol != "http")
                self.protocol.setEnabled(self.adapter == "qwen")
        self.name.clear()
        self.url.setText(preset.base_url)
        values = {} if preset.protocol == "http" else {"asr_protocol": preset.protocol}
        if self.adapter == "volcengine":
            values["credential_mode"] = (
                "app_access" if preset.id == "volcengine-app" else "api_key"
            )
        self.resource_id.clear()
        self.parameters.setPlainText(json.dumps(values))
        self.configure_credentials()
        self.clear_credentials()
        with QSignalBlocker(self.model):
            self.model.clear()
            self.model.addItems(preset.models)
            self.model.setCurrentText(preset.models[0] if preset.models else "")
        self.available_models = preset.models
        self.filter_models()
        self.model_changed()
        self.message.setText("预设已填入草稿；尚未保存或联网验证，现有密钥未更改。")

    def filter_models(self):
        if self.role != "transcription":
            return
        try:
            values = self.parameter_values()
        except ConfigError:
            return
        selected = self.model.currentText()
        with QSignalBlocker(self.model):
            self.model.clear()
            self.model.addItems(
                [
                    m
                    for m in self.available_models
                    if asr_capability(m, self.adapter, values) == "supported"
                ]
            )
            self.model.setCurrentText(selected)

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

    def configure_protocol_options(self):
        if self.role != "transcription":
            return
        allowed = {
            preset.protocol
            for preset in PRESETS
            if preset.role == "transcription" and preset.adapter == self.adapter
        }
        if self.adapter == "qwen":
            allowed.add(PROTOCOL)
        mode = self.parameter_values().get("asr_protocol", "http")
        labels = {
            "http": "录音结束后上传 · HTTP",
            PROTOCOL: "边录边识别 · Qwen 实时 WebSocket",
            "stepfun_realtime": "边录边识别 · 阶跃 ASR WebSocket",
            "dashscope_task": "边录边识别 · 百炼任务 WebSocket",
            "xfyun_iat": "边录边识别 · 讯飞听写",
            "tencent_asr": "边录边识别 · 腾讯云识别",
            "volc_binary": "边录边识别 · 火山识别",
        }
        with QSignalBlocker(self.protocol):
            self.protocol.clear()
            for protocol, title in labels.items():
                if protocol in allowed:
                    self.protocol.addItem(title, protocol)
            self.protocol.setCurrentIndex(self.protocol.findData(mode))
            self.protocol.setEnabled(len(allowed) > 1)

    def parameters_changed(self):
        self.revision += 1
        self.filter_models()
        if self.role == "transcription":
            try:
                values = self.parameter_values()
            except ConfigError:
                self.update_model_hint()
                return
            self.configure_credentials()
            self.configure_protocol_options()
            mode = values.get("asr_protocol", "http")
            endpoint = values.get("realtime_url", "")
            with QSignalBlocker(self.protocol), QSignalBlocker(self.realtime_url):
                self.protocol.setCurrentIndex(self.protocol.findData(mode))
                displayed_endpoint = endpoint if isinstance(endpoint, str) else ""
                if self.realtime_url.text() != displayed_endpoint:
                    self.realtime_url.setText(displayed_endpoint)
                self.realtime_url.setEnabled(
                    mode
                    in {
                        PROTOCOL,
                        "stepfun_realtime",
                        "dashscope_task",
                        "xfyun_iat",
                        "tencent_asr",
                        "volc_binary",
                    }
                )
        if self.preset.currentIndex() < 0 and not self.url.text().strip():
            with QSignalBlocker(self.protocol):
                self.protocol.setCurrentIndex(-1)
                self.protocol.setEnabled(False)
                self.protocol.setPlaceholderText("请先选择服务平台")
        self.update_model_hint()

    def protocol_changed(self):
        self.revision += 1
        self.realtime_url.setEnabled(
            self.protocol.currentData()
            in {
                PROTOCOL,
                "stepfun_realtime",
                "dashscope_task",
                "xfyun_iat",
                "tencent_asr",
                "volc_binary",
            }
        )
        try:
            values = self.parameter_values()
        except ConfigError:
            self.update_model_hint()
            return
        mode = self.protocol.currentData()
        if mode == "http":
            values.pop("asr_protocol", None)
            values.pop("realtime_url", None)
        elif mode in {
            PROTOCOL,
            "stepfun_realtime",
            "dashscope_task",
            "xfyun_iat",
            "tencent_asr",
            "volc_binary",
        }:
            values["asr_protocol"] = mode
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
        if provider.parameters.get("asr_protocol") is not None:
            from inkecho.asr_streaming import streaming_config

            sample_rate = self.session.store.load_settings().sample_rate
            if sample_rate != 16000:
                raise ConfigError(
                    "实时识别需要 16 kHz 录音；请在录音设置中手动选择。"
                    "当前采样率未被修改。"
                )
            streaming_config(provider, sample_rate=sample_rate)

    def toggle_guidance(self, expanded):
        self.guide_details.setVisible(expanded)
        self.guide_toggle.setText(
            "收起 API 配置步骤" if expanded else "查看 API 配置步骤"
        )

    def update_guidance(self):
        if not hasattr(self, "guide_details"):
            return
        try:
            fields = self.credential_fields()
        except ConfigError:
            fields = ("api_key",)
        protocol = (
            self.protocol.currentData() if self.role == "transcription" else "http"
        )
        summary, details = setup_guidance(
            self.preset.currentData(),
            self.url.text().strip(),
            fields,
            role=self.role,
            protocol=protocol,
            adapter=self.adapter,
        )
        self.guide_summary.setText(summary)
        if details.startswith("<p>"):
            links, _, steps = details.partition("</p>")
            self.guide_links.setText(links + "</p>")
            self.guide_links.show()
            self.guide_details.setText(steps)
        else:
            self.guide_links.clear()
            self.guide_links.hide()
            self.guide_details.setText(details)

    def update_model_hint(self):
        self.update_guidance()
        from inkecho.app import PROVIDER_LABELS

        if not self.name.text().strip():
            self.model_hint.setText(
                "请选择服务平台，为模型配置命名，再填写模型和凭据并保存。"
            )
            self.update_model_annotations(None)
            return
        provider = None
        try:
            provider = self.provider()
            self.validate_protocol(provider)
        except ProviderError as error:
            self.model_hint.setText(PROVIDER_LABELS[error.code])
            if error.code != "protocol":
                provider = None
        except ConfigError as error:
            self.model_hint.setText(str(error))
            provider = None
        except (ValueError, AttributeError):
            self.model_hint.setText("请填写有效的服务配置，再检查模型协议。")
            provider = None
        else:
            if self.role == "polishing":
                family = {
                    "openai": "Chat Completions",
                    "responses": "Responses",
                    "messages": "Messages",
                    "gemini": "Gemini 原生",
                }.get(provider.adapter, "未知")
                hint = f"当前协议：{family}。"
            elif provider.parameters.get("asr_protocol") in {
                PROTOCOL,
                "stepfun_realtime",
                "dashscope_task",
                "xfyun_iat",
                "tencent_asr",
                "volc_binary",
            }:
                hint = "边录边识别 · 16 kHz 录音。"
            else:
                hint = (
                    "录音结束后通过 HTTP 上传；实时模型请切换转写方式。"
                    "模型列表不等于能力验证。"
                )
            if (
                self.role == "transcription"
                and asr_capability(
                    provider.model, provider.adapter, provider.parameters
                )
                == "unknown"
            ):
                hint = (
                    "此自定义模型的转写能力未知；请显式测试，模型名称不代表验证通过。"
                )
            self.model_hint.setText(hint)
        self.update_model_annotations(provider)

    def update_model_annotations(self, provider: Provider | None) -> None:
        """Refresh local compatibility only; never infer verified cloud ability."""
        for index in range(self.model.count()):
            self.model.setItemData(index, None, Qt.ItemDataRole.ToolTipRole)
            self.model.setItemData(index, None, Qt.ItemDataRole.ForegroundRole)
            if provider is None:
                continue
            model = self.model.itemText(index)
            try:
                validate_provider_protocol(replace(provider, model=model))
            except ProviderError as error:
                if error.code != "protocol":
                    # A bad URL/JSON configuration isn't a model capability.
                    continue
                parts = model.strip().lower().split("-")
                if "filetrans" in parts:
                    hint = "文件转写任务协议尚未实现，请选择其他模型。"
                elif "streaming" in parts:
                    hint = "此流式协议尚未实现，请选择其他模型。"
                elif provider.parameters.get("asr_protocol") in {
                    PROTOCOL,
                    "stepfun_realtime",
                }:
                    hint = (
                        "此模型与当前转写协议不匹配，请选择对应语音模型或服务平台预设。"
                    )
                else:
                    hint = (
                        "此模型与当前转写协议不匹配，请选择对应语音模型或服务平台预设。"
                        "模型列表不等于能力验证。"
                    )
                self.model.setItemData(index, hint, Qt.ItemDataRole.ToolTipRole)
                self.model.setItemData(
                    index, QColor("#aa3434"), Qt.ItemDataRole.ForegroundRole
                )

    def refresh(self, identifier=None):
        if identifier is None:
            identifier = getattr(
                self.session.store.load_settings(), self.role + "_provider"
            )
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
        self.available_models = ()
        self.adapter = provider.adapter
        if self.role == "transcription":
            self.protocol.setEnabled(self.adapter == "qwen")
        preset = next(
            (
                p
                for p in PRESETS
                if p.role == self.role
                and p.adapter == provider.adapter
                and p.base_url == provider.base_url
                and (
                    p.protocol == provider.parameters.get("asr_protocol", "http")
                    or (
                        p.adapter == "qwen"
                        and provider.parameters.get("asr_protocol") == PROTOCOL
                    )
                )
                and (not p.models or provider.model in p.models)
                and (
                    provider.adapter != "volcengine"
                    or (p.id == "volcengine-app")
                    == (
                        provider.parameters.get("credential_mode", "api_key")
                        == "app_access"
                    )
                )
            ),
            None,
        )
        self.available_models = tuple(
            model
            for model in (preset.models if preset else ())
            if self.role != "transcription"
            or asr_capability(model, provider.adapter, provider.parameters)
            == "supported"
        )
        self.preset.setCurrentIndex(self.preset.findData(preset.id) if preset else -1)
        self.name.setText(provider.name)
        self.url.setText(provider.base_url)
        self.model.clear()
        self.model.addItems(self.available_models)
        self.model.setCurrentText(provider.model)
        self.parameters.setPlainText(
            json.dumps(provider.parameters, ensure_ascii=False, indent=2)
        )
        self.clear_credentials()
        self.resource_id.setText(provider.parameters.get("resource_id", ""))
        self.configure_credentials()
        settings = self.session.store.load_settings()
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
        self.available_models = ()
        self.adapter = "openai" if self.role == "polishing" else "qwen"
        if self.role == "transcription":
            self.protocol.setEnabled(True)
        self.preset.setCurrentIndex(-1)
        self.preset.setPlaceholderText("请选择服务平台")
        self.name.clear()
        self.name.setPlaceholderText("请为此模型配置命名")
        self.url.clear()
        self.model.clear()
        self.model.setCurrentText("")
        self.parameters.setPlainText("{}")
        self.clear_credentials()
        self.resource_id.clear()
        self.configure_credentials()
        self.current.setChecked(True)
        if self.role == "transcription":
            with QSignalBlocker(self.protocol):
                self.protocol.setCurrentIndex(-1)
                self.protocol.setEnabled(False)
                self.protocol.setPlaceholderText("请先选择服务平台")
        self.update_model_hint()

    def credential_fields(self):
        if self.adapter == "xfyun":
            return ("app_id", "api_key", "api_secret")
        if self.adapter == "tencent-asr":
            return ("app_id", "secret_id", "secret_key")
        if (
            self.adapter == "volcengine"
            and self.parameter_values().get("credential_mode") == "app_access"
        ):
            return ("app_key", "access_key")
        return ("api_key",)

    def clear_credentials(self):
        for widget in self.credential_inputs.values():
            widget.clear()

    def configure_credentials(self):
        fields = self.credential_fields()
        if getattr(self, "_visible_credential_fields", fields) != fields:
            self.clear_credentials()
        self._visible_credential_fields = fields
        for field, widget in self.credential_inputs.items():
            widget.setVisible(field in fields)
            if field in self.credential_labels:
                self.credential_labels[field].setVisible(field in fields)
        self.resource_id.setVisible(self.adapter == "volcengine")
        self.resource_label.setVisible(self.adapter == "volcengine")

    def credential_value(self):
        fields = self.credential_fields()
        values = {field: self.credential_inputs[field].text() for field in fields}
        if not any(values.values()):
            return ""
        if fields == ("api_key",):
            return values["api_key"]
        try:
            return encode_credentials(values, fields)
        except CredentialError:
            raise ConfigError("请完整填写本组凭据，或全部留空保留现有凭据。") from None

    def provider(self):
        values = self.parameter_values()
        if self.adapter == "volcengine":
            values["resource_id"] = self.resource_id.text().strip()
        return Provider(
            self.identifier,
            self.name.text().strip(),
            self.role,
            self.adapter,
            self.url.text().strip(),
            self.model.currentText().strip(),
            self.reference,
            values,
        )

    async def save(self):
        if self.preset.currentIndex() < 0 and not self.url.text().strip():
            raise ConfigError("请先选择服务平台，并填写名称、模型与凭据后保存。")
        provider = self.provider()
        if not provider.base_url or not provider.model:
            raise ConfigError("请填写服务地址与模型 ID 后保存配置。")
        # Reject secret-bearing/invalid endpoints before touching credentials or
        # persisting any parameter string, including an unselected URL draft.
        if "realtime_url" in provider.parameters:
            if provider.adapter == "qwen":
                RealtimeConfig(provider.parameters["realtime_url"], provider.model)
            else:
                from inkecho.asr_wire import validate_endpoint

                validate_endpoint(provider.parameters["realtime_url"])
        self.validate_protocol(provider)
        revision = self.revision
        value = self.credential_value()
        if not value and not any(
            item.id == provider.id for item in self.session.store.providers()
        ):
            raise ConfigError("首次保存模型配置时，请填写完整凭据。")
        if provider.adapter == "volcengine":
            previous = next(
                (
                    item
                    for item in self.session.store.providers()
                    if item.id == provider.id
                ),
                None,
            )
            if previous and previous.parameters.get(
                "credential_mode", "api_key"
            ) != provider.parameters.get("credential_mode", "api_key"):
                if not value:
                    raise ConfigError("切换凭据模式须完整填写新凭据；原服务保持不变。")
                identifier = "provider-" + uuid.uuid4().hex
                provider = replace(
                    provider, id=identifier, key_ref=f"provider/{identifier}"
                )
        self.clear_credentials()
        updates = {}
        if self.current.isChecked():
            updates[self.role + "_provider"] = provider.id
        if value:
            await self.session.save_key(provider.key_ref, value)
        self.session.store.save_provider(provider)
        settings = self.session.store.load_settings()
        self.session.store.save_settings(replace(settings, **updates))
        if revision != self.revision:
            return
        self.refresh(provider.id)
        self.message.setText("服务配置已保存；凭据明文保存在 credentials.json。")

    def delete(self):
        providers = [
            p
            for p in self.session.store.providers()
            if p.role == self.role and p.id != self.identifier
        ]
        settings = self.session.store.load_settings()
        field = self.role + "_provider"
        if getattr(settings, field) == self.identifier:
            self.session.store.save_settings(
                replace(settings, **{field: providers[0].id if providers else ""})
            )
        self.session.store.delete_provider(self.identifier)
        self.refresh()
        self.message.setText("模型配置已删除。")

    async def discover(self):
        provider = self.provider()
        revision = self.revision
        if provider.adapter in STATIC_MODEL_ADAPTERS:
            models = tuple(
                dict.fromkeys(
                    model
                    for preset in PRESETS
                    if preset.role == provider.role
                    and preset.adapter == provider.adapter
                    and preset.protocol
                    == provider.parameters.get("asr_protocol", "http")
                    for model in preset.models
                    if provider.role != "transcription"
                    or asr_capability(model, provider.adapter, provider.parameters)
                    == "supported"
                )
            )
            self.available_models = models
            selected = self.model.currentText()
            with QSignalBlocker(self.model):
                self.model.clear()
                self.model.addItems(models)
                self.model.setCurrentText(selected)
            self.update_model_hint()
            self.message.setText(
                "该服务无通用模型发现接口；显示内置可选模型，尚未联网验证。"
            )
            return
        self.message.setText("正在连接服务并获取模型列表……")
        key = await self.session.key(provider.key_ref)
        if revision != self.revision:
            return
        models = await self.session.provider_client(self.role).models(provider, key)
        if revision != self.revision:
            return
        self.available_models = tuple(models)
        if self.role == "transcription":
            models = [
                m
                for m in models
                if asr_capability(m, provider.adapter, provider.parameters)
                == "supported"
            ]
        selected = self.model.currentText()
        with QSignalBlocker(self.model):
            self.model.clear()
            self.model.addItems(models)
            self.model.setCurrentText(selected)
        self.update_model_hint()
        self.message.setText(
            f"连接成功，发现 {len(models)} 个模型；尚未验证模型能力。"
            + (
                "已按转写能力和协议过滤；可手动填写未知模型，但未验证其能力。"
                if self.role == "transcription"
                else ""
            )
        )
