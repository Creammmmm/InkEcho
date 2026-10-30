"""Card-based polishing templates with an explicit detailed editor."""

from dataclasses import replace

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QWidget,
)

from inkecho.config import BUILTIN_PROMPT, BUILTIN_PROMPTS, Prompt
from inkecho.ui.widgets import Page, actions, button, card, label


class PromptsPage(Page):
    def __init__(self, session):
        super().__init__("润色风格", "选择适合场景的模板，查看并编辑完整的润色规则。")
        self.session = session
        self.revision = 0
        self.body.addWidget(actions(button("新建模板", lambda: self.safe(self.new))))
        self.cards = QWidget()
        self.cards_layout = QGridLayout(self.cards)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(14)
        self.body.addWidget(self.cards)
        self.editor, body = card()
        form = QFormLayout()
        self.name, self.description = QLineEdit(), QLineEdit()
        form.addRow("名称", self.name)
        form.addRow("简述", self.description)
        body.addLayout(form)
        self.text = QPlainTextEdit()
        self.text.setMinimumHeight(260)
        body.addWidget(self.text)
        body.addWidget(label("编辑内置模板会保存为个人副本。", muted=True))
        body.addWidget(
            actions(
                button("保存模板", lambda: self.safe(self.save), primary=True),
                button("设为当前模板", lambda: self.safe(self.select)),
                button("复制模板", lambda: self.safe(self.copy)),
                button("删除模板", lambda: self.safe(self.delete)),
                button("收起详情", self.editor.hide),
            )
        )
        self.body.addWidget(self.editor)
        self.refresh(session.store.load_settings().prompt)
        self.editor.hide()
        self.finish()

    def refresh(self, identifier=None):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        selected = self.session.store.load_settings().prompt
        self.style_cards = {}
        for index, prompt in enumerate(self.session.store.prompts()):
            panel, body = card()
            active = prompt.id == selected
            panel.setProperty("activeStyle", active)
            panel.setProperty("promptId", prompt.id)
            panel.setAccessibleName(
                prompt.name + ("，当前使用" if active else "，非当前风格")
            )
            self.style_cards[prompt.id] = panel
            heading = QHBoxLayout()
            title = label(prompt.name)
            title.setObjectName("styleTitle")
            title.setMinimumHeight(32)
            heading.addWidget(title, 1)
            if active:
                badge = label("✓ 当前使用")
                badge.setObjectName("activeStyleBadge")
                badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                badge.setFixedWidth(104)
                heading.addWidget(badge)
            body.addLayout(heading)
            body.addWidget(label(prompt.description, muted=True))
            body.addWidget(
                button(
                    "查看与编辑",
                    lambda _checked=False, key=prompt.id: self.safe(
                        lambda: self.open_template(key)
                    ),
                )
            )
            self.cards_layout.addWidget(panel, index // 2, index % 2)
        self.cards_layout.setColumnStretch(0, 1)
        self.cards_layout.setColumnStretch(1, 1)
        self.load(identifier or selected)

    def open_template(self, identifier):
        self.load(identifier)
        self.show_editor()

    def show_editor(self):
        self.editor.show()
        QTimer.singleShot(0, self.scroll_to_editor)

    def scroll_to_editor(self):
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                if parent.widget().layout():
                    parent.widget().layout().activate()
                self.layout().activate()
                top = self.editor.mapTo(parent.widget(), QPoint(0, 0)).y()
                parent.verticalScrollBar().setValue(max(0, top - 18))
                break
            parent = parent.parentWidget()

    def load(self, identifier=None):
        self.revision += 1
        prompt = self.session.store.load_prompt(identifier or self.identifier)
        self.identifier = prompt.id
        self.name.setText(prompt.name)
        self.description.setText(prompt.description)
        self.text.setPlainText(prompt.body)

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
        self.refresh(self.identifier)
        self.message.setText("已设为当前润色模板。")

    def new(self):
        prompt = self.session.store.copy_prompt(BUILTIN_PROMPT.id, "新模板")
        self.refresh(prompt.id)
        self.show_editor()

    def copy(self):
        prompt = self.session.store.copy_prompt(self.identifier)
        self.refresh(prompt.id)
        self.show_editor()

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
        self.editor.hide()

    def refresh_availability(self):
        """Templates remain editable while cloud polishing is disabled."""
