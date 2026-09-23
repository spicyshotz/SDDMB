"""
Embedded interactive CMD-style terminal console for DepotDownloaderMod.
Streams live stdout/stderr and provides an interactive stdin prompt for Steam Guard 2FA codes.
"""

import os
from typing import List, Optional
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QFrame,
)
from PyQt6.QtCore import Qt, QProcess, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor, QCursor


class TerminalWidget(QWidget):
    """Interactive command-line console widget powered by QProcess."""
    process_started = pyqtSignal()
    process_finished = pyqtSignal(int)  # exit_code
    process_error = pyqtSignal(str)     # error_message

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process: Optional[QProcess] = None
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("TerminalWidget")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Terminal Header Bar
        header = QFrame()
        header.setFixedHeight(34)
        header.setStyleSheet("""
            QFrame {
                background-color: #202327;
                border-top: 1px solid #3a3f45;
                border-bottom: 1px solid #111315;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 12, 0)
        header_layout.setSpacing(10)

        title = QLabel("DepotDownloader Console")
        title.setStyleSheet("color: #d5d9dc; font-weight: bold; font-size: 12px;")
        header_layout.addWidget(title)

        self.status_badge = QLabel("Idle")
        self.status_badge.setStyleSheet(
            "background-color: #30353b; color: #aeb4ba; font-size: 11px; padding: 2px 8px; border-radius: 3px;"
        )
        header_layout.addWidget(self.status_badge)

        header_layout.addStretch()

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedSize(50, 22)
        self.clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #30353b;
                color: #c3c8cd;
                border: 1px solid #4a5158;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #444b52;
                color: #ffffff;
            }
        """)
        self.clear_btn.clicked.connect(self.clear_terminal)
        header_layout.addWidget(self.clear_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setFixedSize(50, 22)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d3433;
                color: #d8c2bf;
                border: 1px solid #5e4c49;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #51413f;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #292d31;
                color: #6f767c;
                border-color: #3a4046;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_process)
        header_layout.addWidget(self.stop_btn)

        layout.addWidget(header)

        # 2. Terminal Output Display
        self.output_area = QPlainTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setMaximumBlockCount(5000)
        self.output_area.setStyleSheet("""
            QPlainTextEdit {
                background-color: #151719;
                color: #c8cccf;
                font-family: 'Consolas', 'Lucida Console', 'Courier New', monospace;
                font-size: 12px;
                border: none;
                padding: 8px 12px;
                selection-background-color: #555d65;
            }
        """)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.output_area.setFont(font)
        layout.addWidget(self.output_area, stretch=1)

        # 3. Interactive Input Prompt Bar
        input_bar = QFrame()
        input_bar.setFixedHeight(38)
        input_bar.setStyleSheet("""
            QFrame {
                background-color: #1b1e21;
                border-top: 1px solid #353a3f;
            }
        """)
        input_layout = QHBoxLayout(input_bar)
        input_layout.setContentsMargins(10, 4, 10, 4)
        input_layout.setSpacing(8)

        prompt_lbl = QLabel(">")
        prompt_lbl.setStyleSheet("color: #c7ccd0; font-family: monospace; font-weight: bold; font-size: 14px;")
        input_layout.addWidget(prompt_lbl)

        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Input here and press Enter...")
        self.input_edit.setStyleSheet("""
            QLineEdit {
                background-color: #292d32;
                color: #ffffff;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                padding: 4px 8px;
                border: 1px solid #444b52;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border-color: #7b838b;
            }
        """)
        self.input_edit.returnPressed.connect(self._send_input)
        input_layout.addWidget(self.input_edit, stretch=1)

        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedHeight(26)
        self.send_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c444b;
                color: #d0d5d9;
                font-size: 11px;
                font-weight: bold;
                padding: 2px 12px;
                border-radius: 4px;
                border: 1px solid #59616a;
            }
            QPushButton:hover {
                background-color: #535b63;
                color: #ffffff;
            }
        """)
        self.send_btn.clicked.connect(self._send_input)
        input_layout.addWidget(self.send_btn)

        layout.addWidget(input_bar)

    def start_command(self, program: str, arguments: List[str], cwd: Optional[str] = None):
        """Launch a program in the embedded terminal with live streaming."""
        self.stop_process()

        self.output_area.appendPlainText(f"\n$ {os.path.basename(program)} {' '.join(arguments)}\n")

        # Validate that the program executable exists before attempting to start
        if not os.path.isfile(program):
            err_msg = f"Executable not found at '{program}'"
            self.output_area.appendPlainText(f"\n[Error: {err_msg}]\n")
            self.status_badge.setText("Error")
            self.status_badge.setStyleSheet(
                "background-color: #413635; color: #d9c4c1; font-size: 11px; padding: 2px 8px; border-radius: 3px;"
            )
            self.stop_btn.setEnabled(False)
            self.process_error.emit(err_msg)
            return

        self.status_badge.setText("Running...")
        self.status_badge.setStyleSheet(
            "background-color: #354037; color: #d0d8d1; font-size: 11px; padding: 2px 8px; border-radius: 3px;"
        )
        self.stop_btn.setEnabled(True)

        self.process = QProcess(self)
        if cwd and os.path.isdir(cwd):
            self.process.setWorkingDirectory(cwd)
        elif os.path.isdir(os.path.dirname(program)):
            self.process.setWorkingDirectory(os.path.dirname(program))

        self.process.readyReadStandardOutput.connect(self._on_stdout)
        self.process.readyReadStandardError.connect(self._on_stderr)
        self.process.finished.connect(self._on_finished)
        self.process.errorOccurred.connect(self._on_error)

        self.process.start(program, arguments)
        self.process_started.emit()

    def _on_stdout(self):
        if not self.process:
            return
        data = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        self._append_text(data)

    def _on_stderr(self):
        if not self.process:
            return
        data = self.process.readAllStandardError().data().decode("utf-8", errors="replace")
        self._append_text(data)

    def _append_text(self, text: str):
        cursor = self.output_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.output_area.setTextCursor(cursor)
        self.output_area.ensureCursorVisible()

    def append_stdout(self, text: str):
        self._append_text(text + "\n")

    def append_stderr(self, text: str):
        self._append_text(text + "\n")

    def is_running(self) -> bool:
        return self.process is not None and self.process.state() == QProcess.ProcessState.Running

    def clear(self):
        """Alias for clear_terminal."""
        self.clear_terminal()

    def _send_input(self):
        text = self.input_edit.text()
        if not text:
            return

        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.output_area.appendPlainText(f"> {text}\n")
            self.process.write((text + "\r\n").encode("utf-8"))
            self.input_edit.clear()
        else:
            self.output_area.appendPlainText(f"[Process not running: '{text}']\n")
            self.input_edit.clear()

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        self.status_badge.setText(f"Exited ({exit_code})")
        color = "#d0d8d1" if exit_code == 0 else "#d9c4c1"
        bg = "#354037" if exit_code == 0 else "#413635"
        self.status_badge.setStyleSheet(
            f"background-color: {bg}; color: {color}; font-size: 11px; padding: 2px 8px; border-radius: 3px;"
        )
        self.stop_btn.setEnabled(False)
        self.output_area.appendPlainText(f"\n[Process exited with code {exit_code}]\n")
        self.process_finished.emit(exit_code)

    def _on_error(self, error: QProcess.ProcessError):
        err_msg = f"Process Error: {error}"
        self.output_area.appendPlainText(f"\n[{err_msg}]\n")
        self.status_badge.setText("Error")
        self.status_badge.setStyleSheet(
            "background-color: #413635; color: #d9c4c1; font-size: 11px; padding: 2px 8px; border-radius: 3px;"
        )
        self.stop_btn.setEnabled(False)
        self.process_error.emit(err_msg)

    def stop_process(self):
        """Terminate the running process if active."""
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.output_area.appendPlainText("\n[Stopping process...]\n")
            self.process.kill()
            self.process.waitForFinished(1000)
            self.status_badge.setText("Stopped")
            self.status_badge.setStyleSheet(
                "background-color: #3e3933; color: #d2c9b6; font-size: 11px; padding: 2px 8px; border-radius: 3px;"
            )
            self.stop_btn.setEnabled(False)

    def clear_terminal(self):
        self.output_area.clear()
