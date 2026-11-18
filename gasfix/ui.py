"""Compact Russian desktop UI. All device I/O lives in Engine's worker."""
import time
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
                              QFormLayout, QHBoxLayout, QLabel, QMainWindow,
                              QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget)

from .core import Settings
from .engine import Engine
from .settings import default_path, load, save


def choices(items):
    widget = QComboBox()
    for label, value in items:
        widget.addItem(label, value)
    return widget


def number(minimum, maximum, value, suffix, decimals=1):
    widget = QDoubleSpinBox()
    widget.setRange(minimum, maximum)
    widget.setDecimals(decimals)
    widget.setValue(value)
    widget.setSuffix(suffix)
    widget.setKeyboardTracking(False)
    return widget


class App(QMainWindow):
    def __init__(self, settings_path=None):
        super().__init__()
        self.path = Path(settings_path) if settings_path else default_path()
        settings, self.level, warning = load(self.path)
        self.engine = None
        self.last_save = time.monotonic()
        self.save_error = ''
        self.setWindowTitle('VirtualGasFixer')
        self.resize(570, 730)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel('Газ с удержанием')
        title.setStyleSheet('font-size: 24px; font-weight: 600;')
        layout.addWidget(title)
        subtitle = QLabel('DJI RC RM330 и Xbox • AeroFly Professional Deluxe')
        subtitle.setStyleSheet('color: #606875; margin-bottom: 12px;')
        layout.addWidget(subtitle)
        form = QFormLayout()
        form.setSpacing(12)
        self.source = choices([('DJI RC — напрямую USB', 'dji'), ('Xbox / выход DJI RC Emulator', 'xbox')])
        self.slot = choices([(f'Xbox {i + 1}', i) for i in range(4)])
        self.axis = choices([('Левый стик — горизонталь (LX)', 'lx'), ('Левый стик — вертикаль (LY)', 'ly'),
                             ('Правый стик — горизонталь (RX)', 'rx'), ('Правый стик — вертикаль (RY)', 'ry')])
        self.invert = QCheckBox('Поменять увеличение и уменьшение')
        self.mode = choices([('Пропорциональный', 'proportional'), ('Возле упора', 'edge')])
        self.speed = number(.1, 1000, settings.speed, ' %/с')
        self.deadzone = number(0, 95, settings.deadzone * 100, ' %')
        self.threshold = number(.1, 100, settings.threshold * 100, ' %')
        policies = [('Сбросить в 0%', 'zero'), ('Сохранить уровень', 'hold')]
        self.on_start = choices(policies)
        self.on_loss = choices(policies)
        for widget, value in ((self.source, settings.source), (self.slot, settings.xbox_index),
                              (self.axis, settings.axis), (self.mode, settings.mode),
                              (self.on_start, settings.on_start), (self.on_loss, settings.on_loss)):
            widget.setCurrentIndex(widget.findData(value))
        self.invert.setChecked(settings.invert)
        self.editors = (self.source, self.slot, self.axis, self.invert, self.mode, self.speed,
                        self.deadzone, self.threshold, self.on_start, self.on_loss)
        for label, widget in [('Источник', self.source), ('Номер Xbox', self.slot), ('Ось газа', self.axis),
                              ('Направление', self.invert), ('Режим', self.mode), ('Скорость', self.speed),
                              ('Зона центра', self.deadzone), ('Порог возле упора', self.threshold),
                              ('При запуске', self.on_start), ('При потере связи', self.on_loss)]:
            form.addRow(label, widget)
        layout.addLayout(form)
        self.xbox_note = QLabel('В Aerofly выбери только выход программы. Исходный Xbox тоже виден Windows: '
                               'проверь отсутствие двойного ввода. После смены устройств подключись заново.')
        self.xbox_note.setWordWrap(True)
        self.xbox_note.setStyleSheet('color: #8a5800; padding: 8px 0;')
        layout.addWidget(self.xbox_note)
        self.enabled = QCheckBox('Обработка газа включена')
        self.enabled.setChecked(True)
        self.enabled.setToolTip('Когда выключено, выбранная ось передаётся напрямую. Её значение может измениться резко.')
        layout.addWidget(self.enabled)
        self.direct_note = QLabel('Обработка выключена: выбранная ось передаётся напрямую.')
        self.direct_note.setStyleSheet('color: #8a5800;')
        self.direct_note.hide()
        layout.addWidget(self.direct_note)
        controls = QHBoxLayout()
        self.connect_button = QPushButton('Подключить выход')
        self.connect_button.setMinimumHeight(36)
        self.zero_button = QPushButton('Газ 0%')
        self.scan_button = QPushButton('Найти Xbox')
        controls.addWidget(self.connect_button)
        controls.addWidget(self.zero_button)
        controls.addWidget(self.scan_button)
        layout.addLayout(controls)
        self.level_label = QLabel(f'Газ: {self.level * 100:.1f}%')
        self.level_label.setStyleSheet('font-size: 22px; font-weight: 600; margin-top: 10px;')
        layout.addWidget(self.level_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        self.input_label = QLabel('Стик: —')
        self.status = QLabel('Выход отключён')
        self.status.setWordWrap(True)
        self.message = QLabel(warning)
        self.message.setWordWrap(True)
        self.message.setStyleSheet('color: #995500;')
        layout.addWidget(self.input_label)
        layout.addWidget(self.status)
        layout.addWidget(self.message)
        layout.addStretch()
        self.setCentralWidget(panel)
        self.connect_button.clicked.connect(self.toggle_connection)
        self.zero_button.clicked.connect(self.zero)
        self.scan_button.clicked.connect(self.scan)
        self.enabled.toggled.connect(self.toggle_enabled)
        self.source.currentIndexChanged.connect(self.changed_source)
        self.axis.currentIndexChanged.connect(lambda: self.enabled.setChecked(False))
        self.changed_source(initial=True)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(75)
        self.refresh()

    def read_settings(self):
        return Settings(source=self.source.currentData(), xbox_index=self.slot.currentData(),
                        axis=self.axis.currentData(), invert=self.invert.isChecked(), mode=self.mode.currentData(),
                        speed=self.speed.value(), deadzone=self.deadzone.value() / 100,
                        threshold=self.threshold.value() / 100, on_start=self.on_start.currentData(),
                        on_loss=self.on_loss.currentData()).validate()

    def changed_source(self, index=None, initial=False):
        xbox = self.source.currentData() == 'xbox'
        self.slot.setEnabled(xbox and self.engine is None)
        self.xbox_note.setVisible(xbox)
        self.scan_button.setEnabled(xbox and self.engine is None)
        if not initial:
            self.enabled.setChecked(False)

    def toggle_enabled(self, enabled):
        self.direct_note.setVisible(not enabled)
        if self.engine:
            self.engine.set_enabled(enabled)

    def toggle_connection(self):
        if self.engine:
            try:
                self.engine.stop()
                self.level = self.engine.snapshot()['level']
            except RuntimeError as error:
                self.message.setText(str(error))
                return
            self.engine = None
            self.connect_button.setText('Подключить выход')
            for widget in self.editors:
                widget.setEnabled(True)
            self.changed_source(initial=True)
            self.status.setText('Выход отключён')
        else:
            try:
                settings = self.read_settings()
            except ValueError as error:
                QMessageBox.warning(self, 'Проверь настройки', str(error))
                return
            self.engine = Engine(settings, self.level)
            self.engine.set_enabled(self.enabled.isChecked())
            self.engine.start()
            self.connect_button.setText('Отключить выход')
            for widget in self.editors:
                widget.setEnabled(False)
            self.scan_button.setEnabled(False)
            self.message.setText('')
        self.persist()

    def zero(self):
        if self.engine:
            self.engine.zero()
        self.level = 0
        self.refresh()

    def scan(self):
        try:
            from .windows import XInput
            slots = XInput().connected()
            self.message.setText('Доступны: ' + ', '.join(f'Xbox {i + 1}' for i in slots) if slots else 'Исходные Xbox не найдены.')
        except Exception as error:
            self.message.setText(str(error))

    def persist(self):
        try:
            save(self.path, self.read_settings(), self.level)
            self.save_error = ''
        except (OSError, ValueError) as error:
            self.save_error = f'Настройки не сохранены: {error}'
            self.message.setText(self.save_error)
        self.last_save = time.monotonic()

    def refresh(self):
        if self.engine:
            state = self.engine.snapshot()
            self.level = state['level']
            slot = state['output_index']
            suffix = f' • выход Xbox {slot + 1}' if slot is not None else ''
            self.status.setText(state['status'] + suffix)
            self.input_label.setText(f"Стик: {state['input'] * 100:+.1f}%" if state['connected'] else 'Стик: нет свежих данных')
            if not state['running'] and self.engine.thread and not self.engine.thread.is_alive():
                self.connect_button.setText('Сбросить подключение')
        self.level_label.setText(f'Газ: {self.level * 100:.1f}%')
        self.progress.setValue(round(self.level * 1000))
        self.zero_button.setEnabled(self.engine is not None)
        if time.monotonic() - self.last_save >= 2:
            self.persist()

    def closeEvent(self, event):
        if self.engine:
            try:
                self.engine.stop()
                self.level = self.engine.snapshot()['level']
            except RuntimeError as error:
                self.message.setText(str(error))
                event.ignore()
                return
        self.timer.stop()
        self.persist()
        if self.save_error:
            QMessageBox.warning(self, 'Не удалось сохранить настройки', self.save_error)
        event.accept()
