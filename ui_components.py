"""
Custom UI components and styling for the Steam Game Search desktop app.
Features dark Steam/Windows 11 modern theme, responsive card layouts,
and copy-to-clipboard interactions.
"""

from typing import Optional
import os
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QFrame,
    QApplication,
    QMessageBox,
    QDialog,
    QFileDialog,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QDesktopServices, QCursor, QPainter, QPainterPath, QColor

from steam_api import SteamGame
from image_loader import ImageCache
from hubcap_api import (
    get_stored_api_key,
    ManifestDownloadWorker,
    get_game_documents_dir,
    HubcapClient,
    HubcapNotFoundError,
)
from hubcap_dialog import ApiKeyDialog, ManifestNotFoundDialog
from ddm_manager import (
    BASE_DIR,
    DDM_DIR,
    DDM_EXE,
    parse_lua_file,
    get_steam_credentials,
    save_steam_credentials,
    get_last_download_dir,
    save_last_download_dir,
    sanitize_folder_name,
    find_manifest_file,
    build_ddm_command,
    generate_depotkeys_file_from_lua,
)
from steam_login_dialog import SteamLoginDialog

DARK_THEME_QSS = """
/* Main Window & Core Colors */
QMainWindow, QWidget#CentralWidget {
    background-color: #1b1d20;
    color: #d8d8d8;
    font-family: 'Arial', 'Segoe UI', sans-serif;
}

QWidget#CentralWidget {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #292d32, stop: 0.18 #22262a, stop: 0.6 #1b1e22, stop: 1 #16181b);
}

/* Header & Search Bar */
QFrame#HeaderBar {
    background-color: #202327;
    border-bottom: 1px solid #101113;
}

QLineEdit#SearchInput {
    background-color: #30343a;
    color: #ffffff;
    font-size: 13px;
    padding: 9px 12px;
    border: 1px solid #454a51;
    border-radius: 3px;
    selection-background-color: #5b8aa8;
}
QLineEdit#SearchInput::placeholder { color: #91979e; }
QLineEdit#SearchInput:focus {
    border: 1px solid #83909a;
    background-color: #363b41;
}

QPushButton#SearchButton {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #59616a, stop: 1 #42484f);
    color: #ffffff;
    font-size: 12px;
    font-weight: bold;
    padding: 9px 18px;
    border-radius: 2px;
    border: 1px solid #6b737b;
}
QPushButton#SearchButton:hover {
    background: #666f78;
}
QPushButton#SearchButton:pressed {
    background: #353a40;
}

/* Scroll Area & Container */
QScrollArea {
    border: none;
    background-color: transparent;
}
QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

/* Scrollbars */
QScrollBar:vertical {
    background: #17191c;
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #454b51;
    min-height: 25px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #70777e;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Status Bar */
QStatusBar {
    background-color: #1c1f22;
    color: #8f98a0;
    font-size: 12px;
    border-top: 1px solid #34383d;
    padding: 4px 12px;
}

/* Game Card */
QFrame#GameCard {
    background-color: rgba(37, 40, 45, 245);
    border: 1px solid #3b4046;
    border-radius: 4px;
}
QFrame#GameCard:hover {
    background-color: #30343a;
    border: 1px solid #70777e;
}

/* App ID Badge */
QLabel#AppIdBadge {
    background-color: #2d3136;
    color: #b8bec4;
    font-weight: bold;
    font-size: 12px;
    padding: 4px 8px;
    border-radius: 2px;
    border: 1px solid #474d53;
}

/* Copy Button */
QPushButton#CopyIdButton {
    background-color: #3a4046;
    color: #c7ccd0;
    font-size: 12px;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 2px;
    border: 1px solid #535a61;
}
QPushButton#CopyIdButton:hover {
    background-color: #4d555c;
    color: #ffffff;
    border: 1px solid #747c84;
}
QPushButton#CopyIdButton:pressed {
    background-color: #2e3338;
}

/* Action Buttons */
QPushButton#SteamActionBtn {
    background-color: #3c444b;
    color: #d2d7dc;
    font-size: 12px;
    font-weight: bold;
    padding: 6px 14px;
    border-radius: 2px;
    border: 1px solid #575f67;
}
QPushButton#SteamActionBtn:hover {
    background-color: #505860;
    color: #ffffff;
    border-color: #747c84;
}

QPushButton#WebActionBtn {
    background-color: #363b41;
    color: #ccd1d6;
    font-size: 12px;
    padding: 6px 14px;
    border-radius: 2px;
    border: 1px solid #4b5259;
}
QPushButton#WebActionBtn:hover {
    background-color: #484f56;
    color: #ffffff;
}

/* DDM Clean Files Button */
QPushButton#DdmActionBtn {
    background-color: #303b34;
    color: #d1ded4;
    font-size: 12px;
    font-weight: bold;
    padding: 6px 14px;
    border-radius: 3px;
    border: 1px solid #536259;
}
QPushButton#DdmActionBtn:hover {
    background-color: #435147;
    color: #ffffff;
    border-color: #79877e;
}
QPushButton#DdmActionBtn:disabled {
    background-color: #292d31;
    color: #737a80;
    border-color: #3b4147;
}

/* Hubcap Manifest Action Button */
QPushButton#ManifestActionBtn {
    background-color: #3c444b;
    color: #d7dce0;
    font-size: 12px;
    font-weight: bold;
    padding: 6px 14px;
    border-radius: 3px;
    border: 1px solid #59626b;
}
QPushButton#ManifestActionBtn:hover {
    background-color: #515a63;
    color: #ffffff;
    border-color: #858e96;
}
QPushButton#ManifestActionBtn:disabled {
    background-color: #292d31;
    color: #737a80;
    border-color: #3b4147;
}

QPushButton#OpenFolderBtn {
    background-color: #363b41;
    color: #ccd1d6;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 3px;
    border: 1px solid #535a62;
}
QPushButton#OpenFolderBtn:hover {
    background-color: #4a5158;
    color: #ffffff;
    border-color: #7d858d;
}

/* Hubcap Header Stats Button */
QPushButton#HubcapStatsBtn {
    background-color: #2b3036;
    color: #c6cbd0;
    font-size: 13px;
    font-weight: 600;
    padding: 9px 16px;
    border-radius: 3px;
    border: 1px solid #464d54;
}
QPushButton#HubcapStatsBtn:hover {
    background-color: #383e45;
    border-color: #6e767e;
    color: #ffffff;
}

QPushButton#HubcapStatsBtnExpired {
    background-color: #3a302b;
    color: #d7c1b4;
    font-size: 13px;
    font-weight: 600;
    padding: 9px 16px;
    border-radius: 3px;
    border: 1px solid #5d4d43;
}
QPushButton#HubcapStatsBtnExpired:hover {
    background-color: #4b403b;
    color: #ffffff;
}

/* Pill Badges */
QLabel#PriceBadge {
    background-color: #3a4234;
    color: #c6d0bd;
    font-weight: bold;
    font-size: 12px;
    padding: 3px 8px;
    border-radius: 4px;
}
QLabel#PriceBadgeDiscount {
    background-color: #3a4234;
    color: #d0dac7;
    font-weight: bold;
    font-size: 12px;
    padding: 3px 8px;
    border-radius: 4px;
}
QLabel#MetascoreBadge {
    background-color: #4a5056;
    color: #e2e5e7;
    font-weight: bold;
    font-size: 12px;
    padding: 3px 8px;
    border-radius: 4px;
}
QLabel#PlatformTag {
    color: #aab0b5;
    font-size: 12px;
    margin-right: 4px;
}
"""


class BannerLabel(QLabel):
    """Custom banner display label that supports rounded corner rendering and aspect scaling."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(220, 103)  # Standard Steam 460x215 aspect ratio (~2.14:1)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "background-color: #121922; border-radius: 6px; border: 1px solid #233142;"
        )
        self.raw_pixmap = None

    def set_banner_pixmap(self, pixmap: QPixmap):
        if not pixmap or pixmap.isNull():
            return

        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            w, h = 220, 103

        self.raw_pixmap = pixmap
        try:
            scaled = pixmap.scaled(
                w,
                h,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )

            rounded = QPixmap(w, h)
            rounded.fill(Qt.GlobalColor.transparent)

            painter = QPainter(rounded)
            if painter.isActive():
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                path = QPainterPath()
                path.addRoundedRect(0, 0, w, h, 6, 6)
                painter.setClipPath(path)

                x = (w - scaled.width()) // 2
                y = (h - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
                painter.end()

            self.setPixmap(rounded)
            self.setText("")
        except Exception:
            self.setPixmap(pixmap)


class GameCardWidget(QFrame):
    """Interactive card representation for a Steam Game result."""
    manifest_downloaded = pyqtSignal(int, str)  # app_id, target_dir
    request_run_ddm = pyqtSignal(list, str)      # cmd_args, cwd

    def __init__(self, game: SteamGame, parent=None):
        super().__init__(parent)
        self.game = game
        self.setObjectName("GameCard")
        self.setMinimumHeight(148)
        self.download_worker = None
        self.target_dir = get_game_documents_dir(self.game.id)

        self._init_ui()
        self._load_banner()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 14, 10)
        layout.setSpacing(14)

        # 1. Game Banner
        self.banner = BannerLabel()
        self.banner.setText("Loading banner...")
        self.banner.setStyleSheet(
            "background-color: #10161f; color: #5b6f84; font-size: 11px; border-radius: 6px;"
        )
        layout.addWidget(self.banner)

        # 2. Main Details Column
        details_layout = QVBoxLayout()
        details_layout.setSpacing(4)
        details_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Title
        title_label = QLabel(self.game.name)
        title_label.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: 700;")
        title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        details_layout.addWidget(title_label)

        # App ID Row with Copy button
        id_row = QHBoxLayout()
        id_row.setSpacing(8)

        id_badge = QLabel(f"App ID: {self.game.id}")
        id_badge.setObjectName("AppIdBadge")
        id_badge.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        id_row.addWidget(id_badge)

        self.copy_btn = QPushButton("Copy ID")
        self.copy_btn.setObjectName("CopyIdButton")
        self.copy_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.copy_btn.clicked.connect(self._copy_app_id)
        id_row.addWidget(self.copy_btn)

        # Metascore (if present)
        if self.game.metascore:
            score_badge = QLabel(f"Score: {self.game.metascore}")
            score_badge.setObjectName("MetascoreBadge")
            id_row.addWidget(score_badge)

        id_row.addStretch()
        details_layout.addLayout(id_row)

        # Price and Platform info row
        meta_row = QHBoxLayout()
        meta_row.setSpacing(10)

        # Price
        price_badge = QLabel(self.game.price_formatted)
        if "-" in self.game.price_formatted:
            price_badge.setObjectName("PriceBadgeDiscount")
        else:
            price_badge.setObjectName("PriceBadge")
        meta_row.addWidget(price_badge)

        # Platforms
        platforms_text = []
        if self.game.platforms.get("windows"):
            platforms_text.append("Win")
        if self.game.platforms.get("mac"):
            platforms_text.append("Mac")
        if self.game.platforms.get("linux"):
            platforms_text.append("Linux")
        
        if platforms_text:
            platform_lbl = QLabel(f"Platforms: {', '.join(platforms_text)}")
            platform_lbl.setObjectName("PlatformTag")
            meta_row.addWidget(platform_lbl)

        meta_row.addStretch()
        details_layout.addLayout(meta_row)

        layout.addLayout(details_layout, stretch=1)

        # 3. Actions Column (Right)
        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(5)
        actions_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # DDM Clean Files Download Button
        self.clean_files_btn = QPushButton("Download Game")
        self.clean_files_btn.setObjectName("DdmActionBtn")
        self.clean_files_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clean_files_btn.setToolTip("Download clean game files using DepotDownloaderMod into a folder of your choice")
        self.clean_files_btn.clicked.connect(self._on_download_clean_files)
        actions_layout.addWidget(self.clean_files_btn)

        # Hubcap Manifest Download Button
        has_existing_files = os.path.exists(self.target_dir) and len(os.listdir(self.target_dir)) > 0
        btn_text = "Re-download Manifest" if has_existing_files else "Download Manifest"

        self.manifest_btn = QPushButton(btn_text)
        self.manifest_btn.setObjectName("ManifestActionBtn")
        self.manifest_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.manifest_btn.setToolTip("Download manifests to Documents\\GameManifests\\<AppID> via HubcapDB")
        self.manifest_btn.clicked.connect(self._on_download_manifest_clicked)
        actions_layout.addWidget(self.manifest_btn)

        # Quick store links row
        links_row = QHBoxLayout()
        links_row.setSpacing(6)

        steam_btn = QPushButton("Steam")
        steam_btn.setObjectName("SteamActionBtn")
        steam_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        steam_btn.setToolTip(f"Launch Steam client store for App ID {self.game.id}")
        steam_btn.clicked.connect(self._open_in_steam)
        links_row.addWidget(steam_btn)

        web_btn = QPushButton("Store Page")
        web_btn.setObjectName("WebActionBtn")
        web_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        web_btn.setToolTip("Open in default web browser")
        web_btn.clicked.connect(self._open_in_browser)
        links_row.addWidget(web_btn)
        actions_layout.addLayout(links_row)

        # Open Folder button (shown if files exist or after download)
        self.open_folder_btn = QPushButton("Open Manifests")
        self.open_folder_btn.setObjectName("OpenFolderBtn")
        self.open_folder_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.open_folder_btn.setToolTip(f"Open {self.target_dir} in File Explorer")
        self.open_folder_btn.clicked.connect(self._open_game_folder)
        if not has_existing_files:
            self.open_folder_btn.hide()
        actions_layout.addWidget(self.open_folder_btn)

        layout.addLayout(actions_layout)

    def _load_banner(self):
        """Asynchronously load the game banner image."""
        cache = ImageCache.get_instance()
        cache.load_image(
            primary_url=self.game.header_image,
            fallback_url=self.game.tiny_image,
            callback=self._safe_set_banner,
            err_callback=self._on_banner_error,
        )

    def _safe_set_banner(self, pixmap: QPixmap):
        try:
            self.banner.set_banner_pixmap(pixmap)
        except (RuntimeError, AttributeError):
            pass

    def _on_banner_error(self):
        try:
            self.banner.setText("No Image")
        except (RuntimeError, AttributeError):
            pass

    def _copy_app_id(self):
        """Copy the App ID to the Windows clipboard and show instant visual confirmation."""
        clipboard = QApplication.clipboard()
        clipboard.setText(str(self.game.id))

        self.copy_btn.setText("Copied!")
        self.copy_btn.setStyleSheet("background-color: #2e6930; color: #ffffff; border-color: #4caf50;")
        
        # Reset after 1.5 seconds
        QTimer.singleShot(1500, self._reset_copy_btn)

    def _reset_copy_btn(self):
        self.copy_btn.setText("Copy ID")
        self.copy_btn.setStyleSheet("")

    def _open_in_steam(self):
        """Trigger steam:// protocol URL."""
        QDesktopServices.openUrl(QUrl(self.game.steam_client_url))

    def _open_in_browser(self):
        """Open web browser to Steam store."""
        QDesktopServices.openUrl(QUrl(self.game.store_url))

    def _open_game_folder(self):
        """Open the target Documents\\GameManifests\\<AppID> folder in Windows File Explorer."""
        if os.path.exists(self.target_dir):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.target_dir))
        else:
            os.makedirs(self.target_dir, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.target_dir))

    def _find_downloaded_lua(self) -> Optional[str]:
        """Check for .lua script in Documents\\GameManifests\\<AppID> or references."""
        if os.path.isdir(self.target_dir):
            for f in os.listdir(self.target_dir):
                if f.lower().endswith(".lua"):
                    return os.path.join(self.target_dir, f)

        # Fallback check in references folder next to application
        ref_file = os.path.join(BASE_DIR, "references", f"{self.game.id}.lua")
        if os.path.isfile(ref_file):
            return ref_file
        return None

    def _on_download_clean_files(self):
        """Handle 'Download Clean Files' with DepotDownloaderMod."""
        # 1. Ensure manifest and .lua are downloaded
        lua_file = self._find_downloaded_lua()
        if not lua_file:
            ret = QMessageBox.question(
                self,
                "Download Manifest First",
                f"Clean file downloads require manifest data from HubcapDB for {self.game.name}.\n\n"
                "Would you like to download the manifest now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ret != QMessageBox.StandardButton.Yes:
                return

            api_key = get_stored_api_key()
            if not api_key:
                dialog = ApiKeyDialog(self, expired_notice=False)
                if dialog.exec() != QDialog.DialogCode.Accepted:
                    return

            try:
                client = HubcapClient()
                client.download_and_save(self.game.id, self.game.name)
                self.open_folder_btn.show()
                self.manifest_downloaded.emit(self.game.id, self.target_dir)
            except HubcapNotFoundError:
                dlg = ManifestNotFoundDialog(self.game.name, self.game.id, self)
                dlg.exec()
                return
            except Exception as e:
                if "404" in str(e):
                    dlg = ManifestNotFoundDialog(self.game.name, self.game.id, self)
                    dlg.exec()
                    return
                QMessageBox.warning(
                    self,
                    "Manifest Download Failed",
                    f"Could not download manifest from HubcapDB:\n{e}"
                )
                return

            lua_file = self._find_downloaded_lua()

        # 2. Parse .lua to extract primary depot ID and manifest IDs
        depot_id = None
        manifest_id = None
        manifest_file = None
        depotkeys_file = None

        if lua_file:
            lua_info = parse_lua_file(lua_file, self.game.id)
            depot_id = lua_info.get("primary_depot")
            if depot_id:
                manifest_id = lua_info["manifests"].get(depot_id)
                manifest_file = find_manifest_file(self.target_dir, depot_id, manifest_id)

            # Generate depot keys file from .lua (format: depotID;hexKey)
            keys_target = os.path.join(self.target_dir, "depotkeys.txt")
            depotkeys_file = generate_depotkeys_file_from_lua(lua_file, keys_target)

        if not depot_id:
            QMessageBox.warning(
                self,
                "Depot Not Found",
                f"Could not extract a valid Depot ID from the manifest for {self.game.name} (App ID: {self.game.id}).",
            )
            return

        # 3. Prompt user for download directory
        base_dir = QFileDialog.getExistingDirectory(
            self,
            f"Select Download Folder for {self.game.name}",
            get_last_download_dir(),
        )
        if not base_dir:
            return

        save_last_download_dir(base_dir)
        game_folder = sanitize_folder_name(self.game.name)
        install_dir = os.path.join(base_dir, game_folder)
        os.makedirs(install_dir, exist_ok=True)

        # 4. Check Steam Credentials
        username, creds_saved = get_steam_credentials()
        password = None
        remember = True

        if not username or not creds_saved:
            login_dialog = SteamLoginDialog(self)
            if login_dialog.exec() != QDialog.DialogCode.Accepted:
                return
            username, password, remember = login_dialog.get_login_data()
            save_steam_credentials(username, creds_saved=remember)

        # 5. Build DDM command
        cmd_args = build_ddm_command(
            app_id=self.game.id,
            depot_id=depot_id,
            install_dir=install_dir,
            username=username,
            password=password,
            remember_password=remember,
            manifest_id=manifest_id,
            manifest_file=manifest_file,
            depotkeys_file=depotkeys_file,
        )

        # 6. Request parent window to launch DDM in TerminalWidget
        self.request_run_ddm.emit(cmd_args, DDM_DIR)

    def _on_download_manifest_clicked(self):
        """Handle Download Manifest click: verify API key and trigger async download."""
        api_key = get_stored_api_key()
        if not api_key:
            dialog = ApiKeyDialog(self, expired_notice=False)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

        self.manifest_btn.setEnabled(False)
        self.manifest_btn.setText("Downloading...")

        self.download_worker = ManifestDownloadWorker(self.game.id, self.game.name)
        self.download_worker.finished.connect(self._on_download_finished)
        self.download_worker.auth_error.connect(self._on_download_auth_error)
        self.download_worker.not_found.connect(self._on_download_not_found)
        self.download_worker.error.connect(self._on_download_error)
        self.download_worker.start()

    def _on_download_finished(self, target_dir: str, file_count: int):
        self.manifest_btn.setEnabled(True)
        self.manifest_btn.setText("Downloaded")
        self.manifest_btn.setStyleSheet("background-color: #235c32; color: #a4f5b5; border-color: #43b565;")
        self.open_folder_btn.show()

        self.manifest_downloaded.emit(self.game.id, target_dir)

        QTimer.singleShot(
            3500,
            lambda: self.manifest_btn.setText("Re-download Manifest") or self.manifest_btn.setStyleSheet("")
        )

    def _on_download_auth_error(self, err_msg: str):
        self.manifest_btn.setEnabled(True)
        self.manifest_btn.setText("Download Manifest")

        dialog = ApiKeyDialog(self, expired_notice=True)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # User provided a new key, auto-retry download
            self._on_download_manifest_clicked()

    def _on_download_not_found(self, err_msg: str):
        self.manifest_btn.setEnabled(True)
        self.manifest_btn.setText("Download Manifest")
        dlg = ManifestNotFoundDialog(self.game.name, self.game.id, self)
        dlg.exec()

    def _on_download_error(self, err_msg: str):
        if "404" in str(err_msg):
            self._on_download_not_found(err_msg)
            return

        self.manifest_btn.setEnabled(True)
        self.manifest_btn.setText("Download Manifest")
        QMessageBox.warning(
            self,
            "HubcapDB Download Error",
            f"Failed to download manifest for {self.game.name} (App ID: {self.game.id}):\n\n{err_msg}",
        )
