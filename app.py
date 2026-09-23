"""
Main entry point for the Windows Native Steam Game Search desktop app.
"""

import sys
import os
from pathlib import Path
from typing import List
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QLabel,
    QStatusBar,
    QProgressBar,
    QFrame,
    QDialog,
    QSplitter,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush

from steam_api import search_games, SteamGame
from ui_components import DARK_THEME_QSS, GameCardWidget
from hubcap_api import get_stored_api_key, UserStatsWorker
from hubcap_dialog import ApiKeyDialog
from terminal_widget import TerminalWidget
from ddm_manager import replace_steam_api_dll, place_union_crax_ini
from steamless_manager import unpack_executable


class SearchWorker(QThread):
    """Worker thread that executes the HTTP search query without blocking the GUI."""
    finished = pyqtSignal(int, str, list)  # generation, query, list[SteamGame]
    error = pyqtSignal(int, str, str)      # generation, query, error_message

    def __init__(self, generation: int, query: str):
        super().__init__()
        self.generation = generation
        self.query = query

    def run(self):
        try:
            results = search_games(self.query)
            self.finished.emit(self.generation, self.query, results)
        except Exception as ex:
            self.error.emit(self.generation, self.query, str(ex))


def create_app_icon() -> QIcon:
    """Create a high-resolution Steam-themed icon programmatically."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Dark blue-gray circular background
    painter.setBrush(QBrush(QColor("#171d25")))
    painter.setPen(QPen(QColor("#66c0f4"), 2))
    painter.drawRoundedRect(4, 4, 56, 56, 12, 12)

    # Steam blue accent circle
    painter.setBrush(QBrush(QColor("#66c0f4")))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(18, 18, 28, 28)

    # Inner core
    painter.setBrush(QBrush(QColor("#171d25")))
    painter.drawEllipse(25, 25, 14, 14)

    painter.end()
    return QIcon(pixmap)


class SteamSearchWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SDDMB")
        self.resize(880, 680)
        self.setMinimumSize(680, 500)
        self.setWindowIcon(create_app_icon())

        self.current_worker = None
        self.last_searched_query = ""
        self.search_generation = 0
        self.stats_worker = None
        self.last_ddm_install_dir = None

        # Search debouncing timer (350ms)
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(350)
        self.debounce_timer.timeout.connect(self._perform_search)

        self._init_ui()
        self.refresh_hubcap_stats()

    def _init_ui(self):
        # Central widget
        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Header Bar with Search input
        header = QFrame()
        header.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 12, 24, 12)
        header_layout.setSpacing(14)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText(
            "Search games on Steam (e.g. Portal, Cyberpunk, Elden Ring, Hollow Knight)..."
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_text_changed)
        self.search_input.returnPressed.connect(self._on_search_button_clicked)
        header_layout.addWidget(self.search_input, stretch=1)

        self.search_btn = QPushButton("Search")
        self.search_btn.setObjectName("SearchButton")
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.clicked.connect(self._on_search_button_clicked)
        header_layout.addWidget(self.search_btn)

        # Hubcap API Stats / Key configuration button
        self.hubcap_btn = QPushButton("Hubcap: Checking...")
        self.hubcap_btn.setObjectName("HubcapStatsBtn")
        self.hubcap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hubcap_btn.setToolTip("Click to configure HubcapDB API Key or view remaining download quota")
        self.hubcap_btn.clicked.connect(self._on_hubcap_btn_clicked)
        header_layout.addWidget(self.hubcap_btn)

        main_layout.addWidget(header)

        # 2. Progress Indicator
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate animation
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background: #121922; border: none; } "
            "QProgressBar::chunk { background-color: #66c0f4; }"
        )
        self.progress_bar.hide()
        main_layout.addWidget(self.progress_bar)

        # 3. Main Vertical Splitter: Results on top, CMD Terminal Console on bottom
        self.splitter = QSplitter(Qt.Orientation.Vertical)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(24, 18, 24, 24)
        self.results_layout.setSpacing(10)
        self.results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.results_container)
        self.splitter.addWidget(self.scroll_area)

        # Embedded Interactive CMD Terminal
        self.terminal_widget = TerminalWidget()
        self.terminal_widget.process_finished.connect(self._on_ddm_finished)
        self.splitter.addWidget(self.terminal_widget)
        self.splitter.setSizes([450, 220])

        main_layout.addWidget(self.splitter, stretch=1)

        # 4. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Enter a game name to search Steam.")

        # Show initial welcome state
        self._show_info_message("Search Steam Store", "Type a game title above to find its Steam listing.")

    def _on_text_changed(self, text: str):
        query = text.strip()
        if not query:
            self.debounce_timer.stop()
            self._show_info_message("Search Steam Store", "Type a game title above to find its Steam listing.")
            self.status_bar.showMessage("Ready.")
            return

        # Restart debounce timer for search-as-you-type
        self.debounce_timer.start()

    def _on_search_button_clicked(self):
        self.debounce_timer.stop()
        self._perform_search()

    def _perform_search(self):
        query = self.search_input.text().strip()
        if not query:
            return

        if query == self.last_searched_query and self.current_worker is not None:
            return

        self.last_searched_query = query
        self.search_generation += 1
        current_gen = self.search_generation

        self.status_bar.showMessage(f"Searching Steam for '{query}'...")
        self.progress_bar.show()

        # Disconnect old worker signals so obsolete results are ignored cleanly
        if self.current_worker and self.current_worker.isRunning():
            try:
                self.current_worker.finished.disconnect()
                self.current_worker.error.disconnect()
            except Exception:
                pass

        worker = SearchWorker(current_gen, query)
        self.current_worker = worker
        worker.finished.connect(self._on_search_finished)
        worker.error.connect(self._on_search_error)
        worker.start()

    def _clear_results_layout(self):
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _show_info_message(self, heading: str, subtext: str):
        self._clear_results_layout()

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 80, 40, 40)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)

        h_label = QLabel(heading)
        h_label.setStyleSheet("color: #66c0f4; font-size: 20px; font-weight: bold;")
        h_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(h_label)

        s_label = QLabel(subtext)
        s_label.setStyleSheet("color: #8f9ca8; font-size: 14px;")
        s_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(s_label)

        self.results_layout.addWidget(container)

    def _on_search_finished(self, generation: int, query: str, results: List[SteamGame]):
        if generation != self.search_generation:
            return

        self.progress_bar.hide()
        self.current_worker = None
        self._clear_results_layout()

        if not results:
            self._show_info_message(
                "No games found",
                f"Steam returned no matching games for '{query}'. Try another search term."
            )
            self.status_bar.showMessage(f"No results for '{query}'.")
            return

        for game in results:
            card = GameCardWidget(game)
            card.manifest_downloaded.connect(lambda app_id, target_dir: self.refresh_hubcap_stats())
            card.request_run_ddm.connect(self._run_ddm_command)
            self.results_layout.addWidget(card)

        count = len(results)
        item_word = "game" if count == 1 else "games"
        self.status_bar.showMessage(f"Found {count} {item_word} matching '{query}'.")

    def _run_ddm_command(self, cmd_args: list, cwd: str):
        if not cmd_args:
            return

        # Extract -dir target for post-completion file patching
        if "-dir" in cmd_args:
            try:
                idx = cmd_args.index("-dir")
                if idx + 1 < len(cmd_args):
                    self.last_ddm_install_dir = cmd_args[idx + 1]
            except Exception:
                self.last_ddm_install_dir = None

        program = cmd_args[0]
        arguments = cmd_args[1:]
        self.terminal_widget.start_command(program, arguments, cwd=cwd)

        # Expand terminal splitter if collapsed
        sizes = self.splitter.sizes()
        if len(sizes) == 2 and sizes[1] < 120:
            self.splitter.setSizes([450, 240])

        self.status_bar.showMessage("DepotDownloaderMod is running in the terminal below...")

    def _on_ddm_finished(self, exit_code: int):
        if exit_code == 0 and self.last_ddm_install_dir:
            install_dir = self.last_ddm_install_dir
            try:
                replace_steam_api_dll(install_dir)
                place_union_crax_ini(install_dir)
                self.terminal_widget.append_stdout("Replaced steam_api64.dll")
            except Exception:
                pass
            try:
                SEARCH_DIR = Path(install_dir)
                for exe_path in SEARCH_DIR.rglob("*.exe"):
                    if exe_path.name.endswith(".unpacked.exe"):
                        continue

                    backup_path = exe_path.with_name(f"{exe_path.name}.ORIGINAL")
                    if backup_path.exists():
                        continue

                    self.terminal_widget.append_stdout(f"Checking: {exe_path.relative_to(SEARCH_DIR)}")
                    if unpack_executable(exe_path, log_fn=self.terminal_widget.append_stdout):
                        self.terminal_widget.append_stdout(f"Steamless removed SteamStub DRM from {exe_path.relative_to(SEARCH_DIR)}")
                    else:
                        self.terminal_widget.append_stdout(f"SteamStub DRM not found in {exe_path.relative_to(SEARCH_DIR)}")
            except Exception as e:
                self.terminal_widget.append_stdout("[-] Failure: No unpackable SteamStub executables found in directory.")
                self.terminal_widget.append_stdout(f"error, {e}")
                pass
            self.terminal_widget.append_stdout("Happy Gaming!")
            self.status_bar.showMessage("Download complete!")

    def _on_search_error(self, generation: int, query: str, err_msg: str):
        if generation != self.search_generation:
            return

        self.progress_bar.hide()
        self.current_worker = None
        self._show_info_message(
            "Connection Error",
            f"Could not retrieve results from Steam Storefront API:\n{err_msg}"
        )
        self.status_bar.showMessage("Error communicating with Steam.")

    def _on_hubcap_btn_clicked(self):
        expired = "Expired" in self.hubcap_btn.text()
        dialog = ApiKeyDialog(self, expired_notice=expired)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_hubcap_stats()

    def refresh_hubcap_stats(self):
        key = get_stored_api_key()
        if not key:
            self.hubcap_btn.setText("Hubcap: Set API Key")
            self.hubcap_btn.setObjectName("HubcapStatsBtn")
            self.hubcap_btn.setStyle(self.hubcap_btn.style())
            return

        self.hubcap_btn.setText("Hubcap: Checking...")
        if self.stats_worker and self.stats_worker.isRunning():
            try:
                self.stats_worker.finished.disconnect()
                self.stats_worker.auth_error.disconnect()
                self.stats_worker.error.disconnect()
            except Exception:
                pass

        self.stats_worker = UserStatsWorker()
        self.stats_worker.finished.connect(self._on_stats_finished)
        self.stats_worker.auth_error.connect(self._on_stats_auth_error)
        self.stats_worker.error.connect(self._on_stats_error)
        self.stats_worker.start()

    def _on_stats_finished(self, stats: dict, formatted: str):
        self.hubcap_btn.setText(f"Hubcap: {formatted}")
        self.hubcap_btn.setObjectName("HubcapStatsBtn")
        self.hubcap_btn.setStyle(self.hubcap_btn.style())

    def _on_stats_auth_error(self, err_msg: str):
        self.hubcap_btn.setText("Hubcap: Key Expired")
        self.hubcap_btn.setObjectName("HubcapStatsBtnExpired")
        self.hubcap_btn.setStyle(self.hubcap_btn.style())

    def _on_stats_error(self, err_msg: str):
        self.hubcap_btn.setText("Hubcap: Offline / Error")

    def closeEvent(self, event):
        if hasattr(self, 'terminal_widget'):
            self.terminal_widget.stop_process()
        if self.stats_worker and self.stats_worker.isRunning():
            self.stats_worker.wait(1000)
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.wait(1000)
        super().closeEvent(event)


def main():
    # Enable High DPI scaling
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME_QSS)

    window = SteamSearchWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
