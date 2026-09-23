"""
Interactive dialog for entering, validating, and saving the HubcapDB API Key.
Provides direct link to https://hubcapmanifest.com/api-keys.
"""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QCursor

from hubcap_api import (
    get_stored_api_key,
    set_stored_api_key,
    clear_stored_api_key,
    HubcapClient,
    HubcapAuthError,
    HubcapAPIError,
    API_KEYS_URL,
)


class ApiKeyDialog(QDialog):
    def __init__(self, parent=None, expired_notice: bool = False):
        super().__init__(parent)
        self.setWindowTitle("HubcapDB API Key")
        self.setMinimumSize(540, 380)
        self.resize(540, 390)
        self.setModal(True)
        self.expired_notice = expired_notice

        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #202327;
                color: #d8d8d8;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
            QLabel {
                color: #c8cdd1;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #30343a;
                color: #ffffff;
                font-size: 14px;
                padding: 10px 14px;
                border: 1px solid #484e55;
                border-radius: 3px;
            }
            QLineEdit:focus {
                border-color: #828a92;
            }
            QPushButton#PrimaryBtn {
                background-color: #454c53;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                padding: 9px 20px;
                border-radius: 3px;
                border: 1px solid #626a72;
            }
            QPushButton#PrimaryBtn:hover {
                background-color: #596169;
            }
            QPushButton#SecondaryBtn {
                background-color: #34393f;
                color: #cbd0d4;
                font-size: 13px;
                padding: 9px 18px;
                border-radius: 3px;
                border: 1px solid #4b5259;
            }
            QPushButton#SecondaryBtn:hover {
                background-color: #464d54;
                color: #ffffff;
            }
            QPushButton#DangerBtn {
                background-color: #3f3533;
                color: #d7c2be;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 3px;
                border: 1px solid #614f4b;
            }
            QPushButton#DangerBtn:hover {
                background-color: #51413f;
                color: #ffffff;
            }
            QFrame#NoticeBox {
                background-color: #2a2e33;
                border: 1px solid #454c53;
                border-radius: 4px;
            }
            QFrame#WarningBox {
                background-color: #38312e;
                border: 1px solid #5b4b43;
                border-radius: 4px;
            }
            QFrame#NoticeBox QLabel, QFrame#WarningBox QLabel {
                padding: 0px;
                margin: 0px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # Title
        title_lbl = QLabel("HubcapDB API Authentication")
        title_lbl.setStyleSheet("color: #e1e4e7; font-size: 18px; font-weight: bold;")
        layout.addWidget(title_lbl)

        # Notice or Expiration Warning Box
        if self.expired_notice:
            box = QFrame()
            box.setObjectName("WarningBox")
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(16, 14, 16, 14)
            box_layout.setSpacing(6)

            warn_lbl = QLabel("Your Hubcap API key has expired or is invalid.")
            warn_lbl.setStyleSheet("color: #ddc4b7; font-weight: bold; font-size: 13px;")
            warn_lbl.setWordWrap(True)
            box_layout.addWidget(warn_lbl)

            exp_info = QLabel("HubcapDB API keys expire every 7 days. Please generate a fresh key below.")
            exp_info.setStyleSheet("color: #cbbab0; font-size: 12px;")
            exp_info.setWordWrap(True)
            box_layout.addWidget(exp_info)
            layout.addWidget(box)
        else:
            box = QFrame()
            box.setObjectName("NoticeBox")
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(16, 14, 16, 14)
            box_layout.setSpacing(6)

            info_lbl = QLabel("Manifest downloads require an active Hubcap API key.")
            info_lbl.setStyleSheet("color: #d2d6d9; font-size: 13px;")
            info_lbl.setWordWrap(True)
            box_layout.addWidget(info_lbl)

            exp_lbl = QLabel("Hubcap API keys expire after 7 days.")
            exp_lbl.setStyleSheet("color: #a9afb5; font-size: 12px;")
            exp_lbl.setWordWrap(True)
            box_layout.addWidget(exp_lbl)
            layout.addWidget(box)

        # Link row
        link_layout = QHBoxLayout()
        link_lbl = QLabel(
            f'Get your API key at: <a href="{API_KEYS_URL}" style="color: #b9c0c6; text-decoration: underline;">{API_KEYS_URL}</a>'
        )
        link_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        link_lbl.setOpenExternalLinks(True)
        link_lbl.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        link_layout.addWidget(link_lbl, stretch=1)
        layout.addLayout(link_layout)

        # Input row
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Paste your API key here (e.g., smm_...)")
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        current_key = get_stored_api_key()
        if current_key:
            self.key_input.setText(current_key)
        layout.addWidget(self.key_input)

        # Show / Hide toggle
        toggle_row = QHBoxLayout()
        self.toggle_btn = QPushButton("Show Key")
        self.toggle_btn.setObjectName("SecondaryBtn")
        self.toggle_btn.setFixedWidth(90)
        self.toggle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle_btn.clicked.connect(self._toggle_echo)
        toggle_row.addWidget(self.toggle_btn)

        if current_key:
            self.clear_btn = QPushButton("Clear Key")
            self.clear_btn.setObjectName("DangerBtn")
            self.clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.clear_btn.clicked.connect(self._clear_key)
            toggle_row.addWidget(self.clear_btn)

        toggle_row.addStretch()
        layout.addLayout(toggle_row)

        layout.addStretch()

        # Status / Feedback label
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #ff6b6b; font-size: 12px;")
        layout.addWidget(self.status_lbl)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self.save_btn = QPushButton("Test && Save")
        self.save_btn.setObjectName("PrimaryBtn")
        self.save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.save_btn.clicked.connect(self._test_and_save)
        btn_row.addWidget(self.save_btn)

        layout.addLayout(btn_row)

    def _toggle_echo(self):
        if self.key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_btn.setText("Hide Key")
        else:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_btn.setText("Show Key")

    def _clear_key(self):
        clear_stored_api_key()
        self.key_input.clear()
        self.status_lbl.setStyleSheet("color: #8da4ba; font-size: 12px;")
        self.status_lbl.setText("Stored key cleared.")

    def _test_and_save(self):
        key = self.key_input.text().strip()
        if not key:
            self.status_lbl.setStyleSheet("color: #ff6b6b; font-size: 12px;")
            self.status_lbl.setText("Please enter an API key.")
            return

        self.status_lbl.setStyleSheet("color: #c7ccd1; font-size: 12px;")
        self.status_lbl.setText("Verifying key with HubcapDB...")
        self.save_btn.setEnabled(False)
        self.repaint()

        client = HubcapClient(key)
        try:
            stats = client.fetch_user_stats()
            set_stored_api_key(key)
            self.accept()
        except HubcapAuthError as e:
            self.status_lbl.setStyleSheet("color: #ff6b6b; font-size: 12px;")
            self.status_lbl.setText("Authentication failed: Key is invalid or expired.")
            self.save_btn.setEnabled(True)
        except Exception as e:
            # Network error or unexpected response: allow saving anyway with warning
            ret = QMessageBox.question(
                self,
                "Connection Warning",
                f"Could not verify key online:\n{e}\n\nDo you want to save this key anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ret == QMessageBox.StandardButton.Yes:
                set_stored_api_key(key)
                self.accept()
            else:
                self.status_lbl.setStyleSheet("color: #ffaa55; font-size: 12px;")
                self.status_lbl.setText("Key not saved.")
                self.save_btn.setEnabled(True)


HUBCAP_SITE_URL = "https://hubcapmanifest.com/"


class ManifestNotFoundDialog(QDialog):
    """
    Styled modal dialog displayed when a game's manifest is missing on HubcapDB (HTTP 404).
    Explains the situation clearly and provides direct links to the HubcapDB website.
    """
    def __init__(self, game_name: str, app_id: int, parent=None):
        super().__init__(parent)
        self.game_name = game_name
        self.app_id = app_id
        self.setWindowTitle("Game Manifest Not Available")
        self.setMinimumSize(500, 320)
        self.resize(520, 330)
        self.setModal(True)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #202327;
                color: #d8d8d8;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
            QLabel {
                color: #c8cdd1;
                font-size: 13px;
            }
            QPushButton#PrimaryBtn {
                background-color: #454c53;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                padding: 9px 24px;
                border-radius: 3px;
                border: 1px solid #626a72;
            }
            QPushButton#PrimaryBtn:hover {
                background-color: #596169;
            }
            QPushButton#SecondaryBtn {
                background-color: #34393f;
                color: #cbd0d4;
                font-size: 13px;
                padding: 9px 18px;
                border-radius: 3px;
                border: 1px solid #4b5259;
            }
            QPushButton#SecondaryBtn:hover {
                background-color: #464d54;
                color: #ffffff;
            }
            QFrame#GameCardBox {
                background-color: #2a2e33;
                border: 1px solid #454c53;
                border-radius: 4px;
            }
            QFrame#WarningBox {
                background-color: #38312e;
                border: 1px solid #5b4b43;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # Header Title
        title_lbl = QLabel("Manifest Not Found")
        title_lbl.setStyleSheet("color: #e1e4e7; font-size: 18px; font-weight: bold;")
        layout.addWidget(title_lbl)

        # Game Info Box
        card_box = QFrame()
        card_box.setObjectName("GameCardBox")
        card_layout = QVBoxLayout(card_box)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(4)

        name_lbl = QLabel(self.game_name)
        name_lbl.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: bold;")
        name_lbl.setWordWrap(True)
        card_layout.addWidget(name_lbl)

        id_lbl = QLabel(f"Steam App ID: {self.app_id}")
        id_lbl.setStyleSheet("color: #a0a7ae; font-size: 12px;")
        card_layout.addWidget(id_lbl)
        layout.addWidget(card_box)

        # Explanation Box
        warn_box = QFrame()
        warn_box.setObjectName("WarningBox")
        warn_layout = QVBoxLayout(warn_box)
        warn_layout.setContentsMargins(16, 12, 16, 12)
        warn_layout.setSpacing(6)

        msg_heading = QLabel("HubcapDB returned HTTP 404 (Not Found)")
        msg_heading.setStyleSheet("color: #ddc4b7; font-weight: bold; font-size: 13px;")
        warn_layout.addWidget(msg_heading)

        msg_desc = QLabel(
            "HubcapDB does not currently have manifests or depot keys cached for this game.\n"
            "This usually means the game hasn't been indexed yet, is newly released, or has restricted manifest data."
        )
        msg_desc.setStyleSheet("color: #cbbab0; font-size: 12px; line-height: 1.4;")
        msg_desc.setWordWrap(True)
        warn_layout.addWidget(msg_desc)
        layout.addWidget(warn_box)

        # Link row to Hubcap website
        link_lbl = QLabel(
            f'You can check availability or request manifests directly on HubcapDB: '
            f'<a href="{HUBCAP_SITE_URL}" style="color: #b9c0c6; text-decoration: underline;">{HUBCAP_SITE_URL}</a>'
        )
        link_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        link_lbl.setOpenExternalLinks(True)
        link_lbl.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        link_lbl.setWordWrap(True)
        layout.addWidget(link_lbl)

        layout.addStretch()

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        web_btn = QPushButton("Open HubcapDB")
        web_btn.setObjectName("SecondaryBtn")
        web_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        web_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(HUBCAP_SITE_URL)))
        btn_row.addWidget(web_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("PrimaryBtn")
        ok_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)
