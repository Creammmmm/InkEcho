"""Prompt editing and explicit cloud preview without persistence of results."""

from dataclasses import replace

from PySide6.QtWidgets import QComboBox, QFormLayout, QLineEdit, QPlainTextEdit

from inkecho.config import BUILTIN_PROMPT, BUILTIN_PROMPTS, Prompt
from inkecho.ui.widgets import Page, actions, button, card, label


class PromptsPage(Page):
    def __init__(self, session):
        super().__init__("风格", "保留你的表达方式，让润色遵循明确的规则。")
        self.session = session
        self.revision = 0
        self.selector = QComboBox()
        self.selector.currentIndexChanged.connect(lambda: self.safe(self.load))
        self.body.addWidget(
            actions(
                self.selector,
                button("新建", lambda: self.safe(self.new)),
                button("复制", lambda: self.safe(self.copy)),
            )
        )
        panel, body = card()
        form = QFormLayout()
        self.name, self.description = QLineEdit(), QLineEdit()
        form.addRow("名称", self.name)
        form.addRow("说明", self.description)
        body.addLayout(form)
        self.text = QPlainTextEdit()
        self.text.setMinimumHeight(140)
        body.addWidget(self.text)
        body.addWidget(
            label("编辑内置模板时会自动保存为用户副本，原始模板保持不变。", muted=True)
        )
        self.body.addWidget(panel)
        self.body.addWidget(
            actions(
                button("保存模板", lambda: self.safe(self.save), primary=True),
                button("设为当前模板", lambda: self.safe(self.select)),
                button("删除", lambda: self.safe(self.delete)),
            )
        )
        self.sample = QLineEdit()
        self.sample.setPlaceholderText("输入一小段示例文字进行预览（只在点击后上传）")
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(90)
        self.preview.setPlaceholderText("测试结果仅在本页显示，不持久保存")
        self.body.addWidget(self.sample)
        self.test_button = button(
            "云端测试润色 · 可能计费", lambda: self.run(self.test())
        )
        self.body.addWidget(actions(self.test_button))
        self.refresh_availability()
        self.body.addWidget(self.preview)
        self.refresh(session.store.load_settings().prompt)
        self.finish()

    def refresh(self, identifier=None):
        self.selector.blockSignals(True)
        self.selector.clear()
        for prompt in self.session.store.prompts():
            self.selector.addItem(
                prompt.name
                + (
                    " · 内置"
                    if prompt.id in {item.id for item in BUILTIN_PROMPTS}
                    else ""
                ),
                prompt.id,
            )
        if identifier:
            self.selector.setCurrentIndex(max(0, self.selector.findData(identifier)))
        self.selector.blockSignals(False)
        self.load()

    def load(self):
        self.revision += 1
        prompt = self.session.store.load_prompt(self.selector.currentData())
        self.identifier = prompt.id
        self.name.setText(prompt.name)
        self.description.setText(prompt.description)
        self.text.setPlainText(prompt.body)
        self.preview.clear()

    def save(self):
        prompt = self.session.store.save_prompt(
            Prompt(
                self.identifier,
                self.name.text(),
                self.description.text(),
                self.text.toPlainText(),
            )
        )
        self.refresh(prompt.id)
        self.message.setText("模板已保存。")

    def select(self):
        self.session.store.save_settings(
            replace(self.session.store.load_settings(), prompt=self.identifier)
        )
        self.message.setText("已设为当前润色模板。")

    def new(self):
        prompt = self.session.store.copy_prompt(BUILTIN_PROMPT.id, "新模板")
        self.refresh(prompt.id)

    def copy(self):
        prompt = self.session.store.copy_prompt(self.identifier)
        self.refresh(prompt.id)

    def delete(self):
        if self.identifier in {item.id for item in BUILTIN_PROMPTS}:
            self.message.setText("内置模板不能删除，可复制后编辑。")
            return
        settings = self.session.store.load_settings()
        if settings.prompt == self.identifier:
            self.session.store.save_settings(
                replace(settings, prompt=BUILTIN_PROMPT.id)
            )
        self.session.store.delete_prompt(self.identifier)
        self.refresh()

    def refresh_availability(self):
        self.test_button.setEnabled(
            self.session.store.load_settings().polishing_enabled
        )

    async def test(self):
        if not self.session.store.load_settings().polishing_enabled:
            self.message.setText("云端润色已关闭，请先在设置或概览中启用。")
            return
        revision = self.revision
        text, prompt = self.sample.text().strip(), self.text.toPlainText()
        if not text:
            self.message.setText("请先输入示例文字。")
            return
        settings = self.session.store.load_settings()
        provider = self.session.store.load_provider(settings.polishing_provider)
        result = await self.session.provider_client("polishing").polish(
            provider, await self.session.key(provider.key_ref), text, prompt
        )
        if revision == self.revision:
            self.preview.setPlainText(result.text)
            self.message.setText("测试完成。结果未保存、未向其他窗口输入。")
