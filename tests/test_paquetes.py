import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

import paquetes_maxobd as app


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.root = self.path / "data" / "archivos_android"
        self.root.mkdir(parents=True)
        self.data = b"original data"
        self.item = {"types": "1102", "file": "nissan/folder/A.BIN",
                     "url": "https://" + app.HOSTS[0] + "/MAXOBD/CarDat/NISSAN/V1.0.0/A.BIN",
                     "size": len(self.data), "md5": hashlib.md5(self.data).hexdigest(),
                     "sha256": hashlib.sha256(self.data).hexdigest()}
        self.group = {"types": "1102", "folder": "nissan", "car": "Nissan",
                      "files": 1, "bytes": len(self.data)}
        self.catalog = {"schema_version": 1, "package": app.PACKAGE,
                        "groups": [self.group], "files": [self.item]}
        self.manifest = self.path / "catalog.json"

    def write_catalog(self, value=None):
        self.manifest.write_text(json.dumps(self.catalog if value is None else value))
        return self.manifest

    def write_data(self, data=None):
        path = self.root / self.item["file"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.data if data is None else data)
        return path

    def test_catalog_rejects_traversal_wrong_host_and_duplicate_case(self):
        cases = []
        for field, value in [("file", "../escape"), ("url", "https://example.org/data"),
                             ("url", self.item["url"] + "?token=secret")]:
            catalog = copy.deepcopy(self.catalog)
            catalog["files"][0][field] = value
            cases.append(catalog)
        catalog = copy.deepcopy(self.catalog)
        duplicate = dict(self.item, file=self.item["file"].lower())
        catalog["files"].append(duplicate)
        cases.append(catalog)
        for value in cases:
            with self.subTest(value=value), self.assertRaises(app.PackageError):
                app.load_catalog(self.write_catalog(value))

    def test_catalog_rejects_inconsistent_group_totals(self):
        value = copy.deepcopy(self.catalog)
        value["groups"][0]["bytes"] += 1
        with self.assertRaises(app.PackageError):
            app.load_catalog(self.write_catalog(value))

    def test_redirect_cannot_leave_official_bucket(self):
        with self.assertRaises(app.PackageError):
            app.OfficialRedirects().redirect_request(None, None, 302, "", {}, "https://example.org/file")

    def test_symlink_cannot_escape_download_directory(self):
        outside = self.path / "outside"
        outside.mkdir()
        try:
            (self.root / "nissan").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks no disponibles")
        with self.assertRaises(app.PackageError):
            app.local_path(self.root, self.item["file"])

    def test_default_and_local_verification_never_use_adb_or_network(self):
        self.write_catalog()
        self.write_data()
        with patch.object(app, "Adb") as adb, patch.object(app, "build_opener") as opener:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(app.main(["--catalogo", str(self.manifest)]), 0)
                self.assertEqual(app.main(["--catalogo", str(self.manifest), "--destino", str(self.root.parent), "--verificar"]), 0)
            adb.assert_not_called()
            opener.assert_not_called()

    def test_valid_cache_does_not_download(self):
        self.write_data()
        with patch.object(app, "read_block") as network:
            self.assertEqual(app.download_one(self.root, self.item, 10), "cache")
            network.assert_not_called()

    def test_corrupt_download_preserves_existing_file(self):
        target = self.write_data(b"old user file")
        with patch.object(app, "read_block", return_value=b"x" * len(self.data)):
            with self.assertRaises(app.PackageError):
                app.download_one(self.root, self.item, 10)
        self.assertEqual(target.read_bytes(), b"old user file")
        self.assertEqual(list(target.parent.glob("*.part")), [])

    def test_range_response_must_match_offsets_and_total(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 206
        response.headers = {"Content-Range": "bytes 1-4/8"}
        response.read.return_value = b"abcd"
        opener = Mock()
        opener.open.return_value = response
        item = dict(self.item, size=8)
        with patch.object(app, "BLOCK", 4), patch.object(app, "build_opener", return_value=opener), patch.object(app.time, "sleep"):
            with self.assertRaises(app.PackageError):
                app.read_block(item, 0, 3, 10)
            response.headers = {"Content-Range": "bytes 0-3/8"}
            self.assertEqual(app.read_block(item, 0, 3, 10), b"abcd")

    def test_missing_or_corrupt_sources_stop_before_any_adb_command(self):
        adb = Mock()
        with self.assertRaises(app.PackageError):
            app.copy_packages(adb, self.root, [self.group], [self.item], self.path / "backup")
        adb.run.assert_not_called()

    def test_backup_failure_prevents_push(self):
        self.write_data()
        adb = Mock()
        def command(*args, **kwargs):
            if args[0] == "pull":
                raise app.InstallerError("Respaldo fallido")
            return "versionName=1.1.01 versionCode=57" if "dumpsys" in args else ""
        adb.run.side_effect = command
        with self.assertRaises(app.InstallerError):
            app.copy_packages(adb, self.root, [self.group], [self.item], self.path / "backup")
        self.assertFalse(any(call.args[0] == "push" for call in adb.run.call_args_list))

    def test_wrong_installed_version_prevents_stopping_app(self):
        self.write_data()
        adb = Mock()
        adb.run.return_value = "versionName=1.1.04 versionCode=60"
        with self.assertRaises(app.InstallerError):
            app.copy_packages(adb, self.root, [self.group], [self.item], self.path / "backup")
        self.assertEqual(len(adb.run.call_args_list), 1)

    def test_listing_understands_android5_and_newer_link_count(self):
        for row in ["-rw-rw---- u0_a84 sdcard_r 13 2026-11-16 00:00 A.BIN",
                    "-rw-rw---- 1 u0_a84 sdcard_r 13 2026-11-16 00:00 A.BIN"]:
            actual = app.parse_listing(app.BASE + "/nissan/folder:\n" + row)
            self.assertEqual(actual["nissan/folder/a.bin"][1], 13)

    def test_copy_stages_only_catalog_files_and_verifies_tablet_sample(self):
        self.write_data()
        (self.root / "nissan" / "unverified.part").write_bytes(b"do not copy")
        adb = Mock(executable="adb", serial="TEST_DEVICE")
        def command(*args, **kwargs):
            if "dumpsys" in args:
                return "versionName=1.1.01 versionCode=57"
            if args[:3] == ("shell", "ls", "-lR"):
                return app.BASE + "/nissan/folder:\n-rw-rw---- u0_a84 sdcard_r 13 2026-11-16 00:00 A.BIN\n"
            if args[0] == "push":
                staged = Path(args[1])
                self.assertEqual([x.name for x in staged.rglob("*") if x.is_file()], ["A.BIN"])
            return ""
        adb.run.side_effect = command
        with patch.object(app.subprocess, "run", return_value=Mock(stdout=self.data)), contextlib.redirect_stdout(io.StringIO()):
            app.copy_packages(adb, self.root, [self.group], [self.item], self.path / "backup")
        calls = [x.args[0] for x in adb.run.call_args_list]
        self.assertLess(calls.index("pull"), calls.index("push"))


if __name__ == "__main__":
    unittest.main()
