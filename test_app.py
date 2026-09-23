"""
Automated unit & integration tests for Steam Game Search desktop app
and HubcapDB manifest downloading functionality.
"""

import sys
import os
import unittest
from PyQt6.QtWidgets import QApplication, QLabel, QSizePolicy
from PyQt6.QtCore import Qt

from steam_api import search_games, SteamGame, parse_price
from image_loader import ImageCache
from ui_components import GameCardWidget
from app import SteamSearchWindow
from hubcap_api import (
    get_stored_api_key,
    set_stored_api_key,
    clear_stored_api_key,
    get_game_documents_dir,
    extract_downloads_left,
    HubcapClient,
    HubcapAuthError,
    HubcapNotFoundError,
)
from hubcap_dialog import ApiKeyDialog, ManifestNotFoundDialog
from ddm_manager import (
    sanitize_folder_name,
    get_steam_credentials,
    save_steam_credentials,
    clear_steam_credentials,
    parse_lua_file,
    build_ddm_command,
    find_manifest_file,
    generate_depotkeys_file_from_lua,
    replace_steam_api_dll,
    place_union_crax_ini,
    DDM_EXE,
)
from steam_login_dialog import SteamLoginDialog
from terminal_widget import TerminalWidget


class TestSteamApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_price_parsing(self):
        self.assertEqual(parse_price(None), "Free / N/A")
        self.assertEqual(parse_price({"currency": "USD", "final": 0}), "Free to Play")
        self.assertEqual(parse_price({"currency": "USD", "initial": 1999, "final": 1999}), "$19.99")
        discounted = parse_price({"currency": "USD", "initial": 2000, "final": 1000})
        self.assertIn("-50%", discounted)

    def test_steam_api_search(self):
        games = search_games("Portal", limit=5)
        self.assertGreater(len(games), 0)
        
        # Check first game properties
        game = games[0]
        self.assertIsInstance(game.id, int)
        self.assertGreater(game.id, 0)
        self.assertTrue("portal" in game.name.lower())
        self.assertTrue(game.header_image.startswith("http"))
        self.assertIn(str(game.id), game.store_url)
        self.assertIn(str(game.id), game.steam_client_url)

    def test_game_card_widget(self):
        game = SteamGame(
            id=620,
            name="Portal 2",
            tiny_image="https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/620/capsule_231x87.jpg",
            header_image="https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/620/header.jpg",
            price_formatted="$9.99",
            metascore="95",
            platforms={"windows": True, "mac": False, "linux": True},
        )
        card = GameCardWidget(game)
        self.assertIsNotNone(card)
        self.assertEqual(card.game.id, 620)
        
        # Test copy button functionality
        card._copy_app_id()
        clipboard = QApplication.clipboard()
        self.assertEqual(clipboard.text(), "620")

        # Test manifest button presence
        self.assertIsNotNone(card.manifest_btn)
        self.assertIn("Manifest", card.manifest_btn.text())

    def test_hubcap_target_dir(self):
        # Target directory path MUST be Documents\GameManifests\<AppID>
        # but it should NOT be eagerly created upon search/query!
        target = get_game_documents_dir(99999999)
        expected_subpath = os.path.join("Documents", "GameManifests", "99999999")
        self.assertTrue(target.endswith(expected_subpath))
        # Ensure it does NOT create the directory eagerly
        self.assertFalse(os.path.exists(target))

    def test_hubcap_stats_formatter(self):
        # Test extracting remaining downloads from various schemas
        stats1 = {"downloads_left": 42, "daily_limit": 50}
        self.assertEqual(extract_downloads_left(stats1), "42/50 downloads left")

        stats2 = {"remaining_downloads": 15}
        self.assertEqual(extract_downloads_left(stats2), "15 downloads left")

        stats3 = {"downloads": 99}
        self.assertEqual(extract_downloads_left(stats3), "99 downloads left")

    def test_hubcap_key_storage(self):
        original = get_stored_api_key()
        try:
            set_stored_api_key("smm_test_12345")
            self.assertEqual(get_stored_api_key(), "smm_test_12345")
            clear_stored_api_key()
            self.assertEqual(get_stored_api_key(), "")
        finally:
            if original:
                set_stored_api_key(original)

    def test_hubcap_dialog_ui(self):
        dialog = ApiKeyDialog(expired_notice=True)
        self.assertIsNotNone(dialog)
        self.assertTrue(dialog.expired_notice)
        self.assertEqual(dialog.windowTitle(), "HubcapDB API Key")
        dialog.close()

    def test_hubcap_not_found_exception(self):
        from unittest.mock import patch, MagicMock
        client = HubcapClient(api_key="smm_dummy_key")
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.ok = False
        with patch("requests.get", return_value=mock_resp):
            with self.assertRaises(HubcapNotFoundError):
                client.download_manifest(99999999)

    def test_manifest_not_found_dialog(self):
        dlg = ManifestNotFoundDialog("Unreleased Game XYZ", 99999999)
        self.assertIsNotNone(dlg)
        self.assertEqual(dlg.game_name, "Unreleased Game XYZ")
        self.assertEqual(dlg.app_id, 99999999)
        self.assertEqual(dlg.windowTitle(), "Game Manifest Not Available")
        dlg.close()

    def test_game_card_long_title_wrapping(self):
        long_title = "Super Long Game Title That Exceeds Normal Card Length On Single Line " * 4
        game = SteamGame(
            id=123456,
            name=long_title,
            tiny_image="https://example.com/tiny.jpg",
            header_image="https://example.com/header.jpg",
            price_formatted="$19.99",
            metascore="80",
            platforms={"windows": True, "mac": False, "linux": False},
        )
        card = GameCardWidget(game)
        self.assertIsNotNone(card)

        # Verify title QLabel has word wrap enabled and expanding size policy
        labels = card.findChildren(QLabel)
        title_lbl = next((lbl for lbl in labels if lbl.text() == long_title), None)
        self.assertIsNotNone(title_lbl)
        self.assertTrue(title_lbl.wordWrap())
        self.assertEqual(title_lbl.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Expanding)
        self.assertGreaterEqual(card.minimumHeight(), 148)
        card.close()

    def test_main_window_init(self):
        window = SteamSearchWindow()
        self.assertEqual(window.windowTitle(), "SDDMB")
        self.assertIsNotNone(window.hubcap_btn)
        self.assertIn("Hubcap", window.hubcap_btn.text())
        window.search_input.setText("Half-Life")
        self.assertEqual(window.search_input.text(), "Half-Life")
        if window.stats_worker and window.stats_worker.isRunning():
            window.stats_worker.wait(1000)
        window.close()


    def test_ddm_sanitize_folder_name(self):
        self.assertEqual(sanitize_folder_name("Game: Subtitle / Edition *?"), "Game Subtitle  Edition")
        self.assertEqual(sanitize_folder_name("Portal 2"), "Portal 2")
        self.assertEqual(sanitize_folder_name("///"), "Game")

    def test_ddm_lua_parser_reference_file(self):
        # Test parsing references/2406770.lua
        ref_path = os.path.join(os.path.dirname(__file__), "references", "2406770.lua")
        self.assertTrue(os.path.isfile(ref_path), f"Reference file not found: {ref_path}")
        
        parsed = parse_lua_file(ref_path, app_id=2406770)
        self.assertEqual(parsed["primary_depot"], 2406771)
        self.assertIn(2406771, parsed["all_depots"])
        self.assertIn(2406770, parsed["keys"])
        self.assertIn(2406771, parsed["keys"])
        self.assertEqual(parsed["manifests"].get(2406771), "4426140782612540492")

    def test_generate_depotkeys_file_from_lua(self):
        ref_path = os.path.join(os.path.dirname(__file__), "references", "2406770.lua")
        test_out = os.path.join(os.path.dirname(__file__), "references", "test_depotkeys.txt")
        try:
            result = generate_depotkeys_file_from_lua(ref_path, test_out)
            self.assertEqual(result, test_out)
            self.assertTrue(os.path.isfile(test_out))
            with open(test_out, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("2406770;70969ed45a39a813850ed9d81a50af9aabc5fc4ebd8fc1216ed260e04487cb50", content)
            self.assertIn("2406771;0456324ba6c023dafc26bedc6005e6145a7b03bfe59a6d2806bf7e07ef54e6c2", content)
            self.assertIn("228989;ad69276eb476cf06c40312df7376d63deac0c838b9a2767005be8bb306ffb853", content)
            self.assertIn("228990;44d8c45ce229a11c4f231a3d2a350eaf80b0d69a8af938ec7ccca720f694b0e8", content)
        finally:
            if os.path.isfile(test_out):
                os.remove(test_out)

    def test_ddm_command_builder(self):
        # First run with password and depotkeys file
        cmd1 = build_ddm_command(
            app_id=2406770,
            depot_id=2406771,
            install_dir=r"C:\Games\MyGame",
            username="my_steam_user",
            password="secret_password",
            remember_password=True,
            manifest_id="4426140782612540492",
            depotkeys_file=r"C:\Games\depotkeys.txt"
        )
        self.assertEqual(cmd1[0], DDM_EXE)
        self.assertIn("-app", cmd1)
        self.assertEqual(cmd1[cmd1.index("-app") + 1], "2406770")
        self.assertIn("-depot", cmd1)
        self.assertEqual(cmd1[cmd1.index("-depot") + 1], "2406771")
        self.assertIn("-dir", cmd1)
        self.assertEqual(cmd1[cmd1.index("-dir") + 1], r"C:\Games\MyGame")
        self.assertIn("-depotkeys", cmd1)
        self.assertEqual(cmd1[cmd1.index("-depotkeys") + 1], r"C:\Games\depotkeys.txt")
        self.assertIn("-username", cmd1)
        self.assertEqual(cmd1[cmd1.index("-username") + 1], "my_steam_user")
        self.assertIn("-password", cmd1)
        self.assertEqual(cmd1[cmd1.index("-password") + 1], "secret_password")
        self.assertIn("-remember-password", cmd1)
        self.assertIn("-manifest", cmd1)
        self.assertEqual(cmd1[cmd1.index("-manifest") + 1], "4426140782612540492")

        # Subsequent run without password (using saved credentials)
        cmd2 = build_ddm_command(
            app_id=2406770,
            depot_id=2406771,
            install_dir=r"C:\Games\MyGame",
            username="my_steam_user",
            password=None,
            remember_password=True
        )
        self.assertNotIn("-password", cmd2)
        self.assertIn("-remember-password", cmd2)

    def test_steam_credentials_persistence(self):
        orig_user, orig_saved = get_steam_credentials()
        try:
            save_steam_credentials("test_gamer", True)
            user, saved = get_steam_credentials()
            self.assertEqual(user, "test_gamer")
            self.assertTrue(saved)

            clear_steam_credentials()
            user, saved = get_steam_credentials()
            self.assertEqual(user, "")
            self.assertFalse(saved)
        finally:
            if orig_user:
                save_steam_credentials(orig_user, orig_saved)

    def test_steam_login_dialog_ui(self):
        dlg = SteamLoginDialog(saved_username="existing_user")
        self.assertIsNotNone(dlg)
        self.assertEqual(dlg.username_input.text(), "existing_user")
        dlg.close()

    def test_terminal_widget_ui(self):
        terminal = TerminalWidget()
        self.assertIsNotNone(terminal)
        terminal.append_stdout("Hello from DDM")
        terminal.append_stderr("Sample warning")
        self.assertFalse(terminal.is_running())
        terminal.clear()
        terminal.close()

    def test_replace_steam_api_dll(self):
        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()
        try:
            # Create a nested folder simulating downloaded game structure
            game_bin_dir = os.path.join(temp_dir, "Game", "Binaries", "Win64")
            os.makedirs(game_bin_dir, exist_ok=True)

            dummy_orig_content = b"ORIGINAL_OLD_STEAM_API_BYTES_12345"
            target_dll = os.path.join(game_bin_dir, "steam_api64.dll")
            with open(target_dll, "wb") as f:
                f.write(dummy_orig_content)

            # Perform replacement
            replaced = replace_steam_api_dll(temp_dir)
            self.assertEqual(len(replaced), 1)
            target_path, backup_path = replaced[0]

            # Verify original was backed up
            self.assertTrue(os.path.isfile(backup_path))
            with open(backup_path, "rb") as f:
                self.assertEqual(f.read(), dummy_orig_content)

            # Verify target was replaced with UC2 version
            uc2_dll = os.path.join(os.path.dirname(__file__), "UC2", "steam_api64.dll")
            with open(uc2_dll, "rb") as f:
                expected_uc2_bytes = f.read()

            with open(target_path, "rb") as f:
                self.assertEqual(f.read(), expected_uc2_bytes)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_place_union_crax_ini(self):
        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()
        try:
            # Create nested directories with an executable
            game_exe_dir = os.path.join(temp_dir, "GameFolder", "Binaries")
            os.makedirs(game_exe_dir, exist_ok=True)
            dummy_exe = os.path.join(game_exe_dir, "Game.exe")
            with open(dummy_exe, "wb") as f:
                f.write(b"DUMMY_EXE_DATA")

            placed = place_union_crax_ini(temp_dir)
            self.assertIsNotNone(placed)
            expected_path = os.path.join(game_exe_dir, "union-crax.ini")
            self.assertEqual(placed, expected_path)
            self.assertTrue(os.path.isfile(expected_path))

            # Verify contents match UC2\union-crax.ini
            uc2_ini = os.path.join(os.path.dirname(__file__), "UC2", "union-crax.ini")
            with open(uc2_ini, "r", encoding="utf-8") as f:
                expected_content = f.read()
            with open(expected_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), expected_content)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
