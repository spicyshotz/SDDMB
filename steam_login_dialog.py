"""
Modal dialog prompting for Steam account credentials to run DepotDownloaderMod.
"""

from typing import Tuple, Optional
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor

from ddm_manager import get_steam_credentials


class SteamLoginDialog(QDialog):
    def __init__(self, parent=None, saved_username: Optional[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Steam Login - Depot Downloader")
        self.setMinimumSize(480, 360)
        self.resize(480, 370)
        self.setModal(True)

        self._init_ui(saved_username=saved_username)

    def _init_ui(self, saved_username: Optional[str] = None):
        self.setStyleSheet("""
            QDialog {
                background-color: #121822;
                color: #e1e7ee;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
            QLabel {
                color: #c7d5e0;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #1b2838;
                color: #ffffff;
                font-size: 14px;
                padding: 10px 14px;
                border: 1px solid #2a475e;
                border-radius: 6px;
            }
            QLineEdit:focus {
                border-color: #66c0f4;
            }
            QCheckBox {
                color: #c7d5e0;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #2a475e;
                border-radius: 4px;
                background-color: #1b2838;
            }
            QCheckBox::indicator:checked {
                background-color: #214b6b;
                border-color: #66c0f4;
            }
            QPushButton#PrimaryBtn {
                background-color: #214b6b;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                padding: 9px 20px;
                border-radius: 6px;
                border: none;
            }
            QPushButton#PrimaryBtn:hover {
                background-color: #296089;
            }
            QPushButton#SecondaryBtn {
                background-color: #222b35;
                color: #c5d3df;
                font-size: 13px;
                padding: 9px 18px;
                border-radius: 6px;
                border: 1px solid #313e4d;
            }
            QPushButton#SecondaryBtn:hover {
                background-color: #2c3947;
                color: #ffffff;
            }
            QFrame#InfoBox {
                background-color: #182433;
                border: 1px solid #2a475e;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # Title
        title_lbl = QLabel("Steam Account Authentication")
        title_lbl.setStyleSheet("color: #66c0f4; font-size: 18px; font-weight: bold;")
        layout.addWidget(title_lbl)

        # Info Box
        info_box = QFrame()
        info_box.setObjectName("InfoBox")
        box_layout = QVBoxLayout(info_box)
        box_layout.setContentsMargins(16, 12, 16, 12)
        box_layout.setSpacing(6)

        desc_lbl = QLabel(
            "DepotDownloaderMod requires your Steam account to download game files.\n"
            "If your account has Steam Guard (2FA) enabled, you will be prompted for your code in the CMD terminal window below."
        )
        desc_lbl.setStyleSheet("color: #a4c2dc; font-size: 12px;")
        desc_lbl.setWordWrap(True)
        box_layout.addWidget(desc_lbl)
        layout.addWidget(info_box)

        # Username Input
        user_lbl = QLabel("Steam Username:")
        user_lbl.setStyleSheet("font-weight: bold; color: #ffffff;")
        layout.addWidget(user_lbl)

        self.user_input = QLineEdit()
        self.username_input = self.user_input  # convenient alias
        self.user_input.setPlaceholderText("Enter Steam account username...")
        stored_user, _ = get_steam_credentials()
        initial_user = saved_username if saved_username is not None else stored_user
        if initial_user:
            self.user_input.setText(initial_user)
        layout.addWidget(self.user_input)

        # Password Input
        pass_lbl = QLabel("Steam Password:")
        pass_lbl.setStyleSheet("font-weight: bold; color: #ffffff;")
        layout.addWidget(pass_lbl)

        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Enter Steam account password...")
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.pass_input)

        # Show / Hide password & Remember Password checkbox
        opts_layout = QHBoxLayout()
        self.toggle_pass_btn = QPushButton("Show Password")
        self.toggle_pass_btn.setObjectName("SecondaryBtn")
        self.toggle_pass_btn.setFixedWidth(120)
        self.toggle_pass_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle_pass_btn.clicked.connect(self._toggle_pass_visibility)
        opts_layout.addWidget(self.toggle_pass_btn)

        self.remember_cb = QCheckBox("Remember credentials for future runs")
        self.remember_cb.setChecked(True)
        opts_layout.addWidget(self.remember_cb)
        opts_layout.addStretch()
        layout.addLayout(opts_layout)

        # Error label
        self.error_lbl = QLabel("")
        self.error_lbl.setStyleSheet("color: #ff6b6b; font-size: 12px;")
        layout.addWidget(self.error_lbl)

        layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        submit_btn = QPushButton("Login && Download")
        submit_btn.setObjectName("PrimaryBtn")
        submit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        submit_btn.clicked.connect(self._on_submit)
        btn_layout.addWidget(submit_btn)

        layout.addLayout(btn_layout)

    def _toggle_pass_visibility(self):
        if self.pass_input.echoMode() == QLineEdit.EchoMode.Password:
            self.pass_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_pass_btn.setText("Hide Password")
        else:
            self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_pass_btn.setText("Show Password")

    def _on_submit(self):
        username = self.user_input.text().strip()
        password = self.pass_input.text()

        if not username:
            self.error_lbl.setText("Please enter your Steam username.")
            return

        if not password:
            self.error_lbl.setText("Please enter your Steam password.")
            return

        self.accept()

    def get_login_data(self) -> Tuple[str, str, bool]:
        """Returns (username, password, remember_password)."""
        return (
            self.user_input.text().strip(),
            self.pass_input.text(),
            self.remember_cb.isChecked(),
        )
